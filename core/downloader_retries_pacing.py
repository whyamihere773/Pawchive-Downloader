"""
Downloader Rate-Limit Backoff, Pawchive Pacing, Retries & Diagnostic Context Mixin
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

from collections import deque
import os
import random
import re
import threading
import time
from typing import Dict, List, Optional, Set, Tuple

from core.downloader_models import (
    DownloadTask,
    PART_SUFFIX,
    is_task_non_retryable,
)
from core.filter_engine import FilterEngine, FilterOptions
from core.logger import logger
from core.providers import is_disabled

_PAWCHIVE_STORAGE_NODE_RE = re.compile(r"^(?:file|[nt]\d+)\.pawchive\.pw$", re.IGNORECASE)


def extract_url_host(url: str) -> str:
    """Fast O(1) lowercase hostname extraction without urllib parsing overhead."""
    if not url:
        return ""
    u = str(url).strip().lower()
    if "://" in u:
        u = u.split("://", 1)[1]
    return u.split("/", 1)[0].split("?", 1)[0].split(":", 1)[0]


def is_pawchive_storage_host(host: str) -> bool:
    """True for Pawchive primary/temp storage shards (file, n1-n9, t1-t9) rather than img CDN."""
    return bool(host and _PAWCHIVE_STORAGE_NODE_RE.match(host))


class DownloaderRetriesPacingMixin:
    """Adaptive rate-limit backoff, per-host Pawchive pacing/calibration, task retries, and diagnostics."""

    @staticmethod
    def _task_primary_host(task: DownloadTask) -> str:
        cached = getattr(task, "_cached_host", None)
        cached_src = getattr(task, "_cached_host_url", None)
        cur_url = getattr(task, "url", "") or ""
        if cached is not None and cached_src == cur_url:
            return cached
        h = extract_url_host(cur_url)
        task._cached_host = h
        task._cached_host_url = cur_url
        return h

    def _sync_cooldown_mirrors_unlocked(self) -> None:
        """If external caller/test reset `_rate_limit_cooldown_until` to 0, clear stale host cooldowns."""
        if self._rate_limit_cooldown_until <= 0.0:
            self._unscoped_cooldown_until = 0.0
            self._host_cooldown_until.clear()
            gov = getattr(self, "pawchive_governor", None)
            if gov is not None and gov._domain_cooldown_until > 0.0:
                with gov._lock:
                    gov._domain_cooldown_until = 0.0
                    if gov._state == "cooldown":
                        gov._state = "probing"

    def get_host_cooldown_until(self, host: str = "") -> float:
        """Return active cooldown expiry timestamp applying to `host` (domain-wide for *.pawchive.pw)."""
        h = (host or "").strip().lower()
        gov = getattr(self, "pawchive_governor", None)
        with self._rate_limit_lock:
            self._sync_cooldown_mirrors_unlocked()
            unscoped = getattr(self, "_unscoped_cooldown_until", 0.0)
            if not h:
                gov_cd = gov.get_cooldown_until() if gov is not None else 0.0
                return max(unscoped, self._rate_limit_cooldown_until, gov_cd)
            if "pawchive.pw" in h and gov is not None:
                return max(unscoped, gov.get_cooldown_until(), self._host_cooldown_until.get(h, 0.0))
            return max(unscoped, self._host_cooldown_until.get(h, 0.0))

    def is_host_cooling_down(self, host: str, now: Optional[float] = None) -> bool:
        ts = time.time() if now is None else now
        return ts < self.get_host_cooldown_until(host)

    def max_active_cooldown_remaining(self, now: Optional[float] = None) -> Tuple[float, str]:
        """Return (max_remaining_seconds, host_label) across any active Pawchive or unscoped cooldown."""
        ts = time.time() if now is None else now
        gov = getattr(self, "pawchive_governor", None)
        with self._rate_limit_lock:
            self._sync_cooldown_mirrors_unlocked()
            best_rem = max(0.0, getattr(self, "_unscoped_cooldown_until", 0.0) - ts)
            best_host = ""
            if gov is not None:
                gov_rem = max(0.0, gov.get_cooldown_until(ts) - ts)
                if gov_rem > best_rem:
                    best_rem = gov_rem
                    best_host = "pawchive.pw"
            for h, exp in list(self._host_cooldown_until.items()):
                rem = exp - ts
                if rem > best_rem:
                    best_rem = rem
                    best_host = h
                elif rem <= 0.0:
                    self._host_cooldown_until.pop(h, None)
            return best_rem, best_host

    def is_host_probe_needed(self, host: str = "") -> bool:
        h = (host or "").strip().lower()
        gov = getattr(self, "pawchive_governor", None)
        if h and "pawchive.pw" in h and gov is not None:
            return gov.is_probing()
        with self._rate_limit_lock:
            if h and h in self._host_probe_needed:
                return bool(self._host_probe_needed.get(h, False))
            if not h:
                gov_p = gov.is_probing() if gov is not None else False
                return bool(self._rate_limit_probe_needed or gov_p or any(self._host_probe_needed.values()))
            return False

    def any_host_probe_needed(self) -> bool:
        gov = getattr(self, "pawchive_governor", None)
        if gov is not None and gov.is_probing():
            return True
        with self._rate_limit_lock:
            return bool(self._rate_limit_probe_needed or any(self._host_probe_needed.values()))

    def _wait_if_globally_paused(self, task: DownloadTask) -> Optional[Tuple[bool, str]]:
        """Block cleanly while the global pause event is set; return an early error tuple if cancelled/batch-paused."""
        while self._pause_event.is_set():
            if self._cancel_event.is_set() or self.is_batch_cancelled(task):
                return (False, "Cancelled")
            if self.is_batch_paused(task) or task.status == "paused":
                return (False, "Batch paused by user")
            time.sleep(0.1)
        if self._cancel_event.is_set() or self.is_batch_cancelled(task):
            return (False, "Cancelled")
        if self.is_batch_paused(task) or task.status == "paused":
            return (False, "Batch paused by user")
        return None

    def _sleep_interruptible(self, task: DownloadTask, seconds: float) -> Optional[Tuple[bool, str]]:
        """Sleep until wall-clock `now + seconds` while honoring cancel, batch pause, and global pause.

        Anchors `deadline` before waiting on global pause so time spent paused always counts toward
        cooldown expiration (resuming after a long pause never double-waits), while bounding slice
        iterations so mocked-sleep unit tests complete instantaneously.
        """
        deadline = time.time() + max(0.0, float(seconds or 0.0))
        early = self._wait_if_globally_paused(task)
        if early is not None:
            return early
        if seconds <= 0.0:
            return None
        max_slices = int(seconds / 0.1) + 2
        for _ in range(max_slices):
            rem = deadline - time.time()
            if rem <= 0.0:
                break
            early = self._wait_if_globally_paused(task)
            if early is not None:
                return early
            rem = deadline - time.time()
            if rem <= 0.0:
                break
            time.sleep(min(0.1, rem))
        return self._wait_if_globally_paused(task)

    def _claim_429_probe_slot(self, host: str = "") -> bool:
        """Allow only one worker per cooldown window to run the Pass-1 verification probe."""
        h = (host or "").strip().lower()
        gov = getattr(self, "pawchive_governor", None)
        if h and "pawchive.pw" in h and gov is not None:
            return gov.claim_probe_slot()
        with self._rate_limit_lock:
            self._sync_cooldown_mirrors_unlocked()
            if h:
                cd_until = max(
                    getattr(self, "_unscoped_cooldown_until", 0.0),
                    self._host_cooldown_until.get(h, 0.0),
                    getattr(self, "_rate_limit_cooldown_until", 0.0),
                )
                claimed_until = self._host_probe_claimed_until.get(h, 0.0)
                if cd_until > claimed_until:
                    self._host_probe_claimed_until[h] = cd_until
                    self._rate_limit_probe_claimed_until = max(self._rate_limit_probe_claimed_until, cd_until)
                    return True
                return False
            cd_until = getattr(self, "_rate_limit_cooldown_until", 0.0)
            claimed_until = getattr(self, "_rate_limit_probe_claimed_until", 0.0)
            if cd_until > claimed_until:
                self._rate_limit_probe_claimed_until = cd_until
                return True
            return False

    def _on_pawchive_request_succeeded(self, host: str = "") -> None:
        """Notify the Two-Layer Pawchive Rate Governor of a clean HTTP 200/206/416 response."""
        h = (host or "").strip().lower()
        gov = getattr(self, "pawchive_governor", None)
        if gov is not None and (not h or "pawchive.pw" in h):
            gov.on_request_succeeded(h)
        with self._rate_limit_lock:
            if h:
                self._host_consecutive_429.pop(h, None)
                self._host_probe_needed.pop(h, None)
                if not self._host_probe_needed and (gov is None or not gov.is_probing()):
                    self._consecutive_429_bursts = 0
                    self._rate_limit_probe_needed = False
            else:
                self._consecutive_429_bursts = 0
                self._rate_limit_probe_needed = False
                self._host_consecutive_429.clear()
                self._host_probe_needed.clear()

    def _note_pawchive_ttfb(self, host: str, ttfb_s: float) -> None:
        """Secondary overload signal: gently widen spacing on a storage node if TTFB spikes (>= 2.5s)."""
        h = (host or "").strip().lower()
        if not h or "pawchive.pw" not in h:
            return
        gov = getattr(self, "pawchive_governor", None)
        if gov is not None:
            gov.note_ttfb(h, ttfb_s)
        if ttfb_s >= 2.5:
            with self._pawchive_pace_lock:
                self._host_slow_ttfb_until[h] = max(self._host_slow_ttfb_until.get(h, 0.0), time.time() + 30.0)

    def _calibrate_host_rate_on_429_unlocked(self, host: str, now: float, cooldown_until: float) -> Optional[int]:
        """Auto-calibrate a storage node's 60s request budget to ~75% of the rate that triggered 429."""
        if not host or "pawchive.pw" not in host:
            return None
        default_rpm = 45 if "img.pawchive.pw" in host else 24
        ts_dq = self._host_req_timestamps.get(host)
        observed_60s = 0
        if ts_dq:
            cutoff = now - 60.0
            while ts_dq and ts_dq[0] <= cutoff:
                ts_dq.popleft()
            observed_60s = sum(1 for t in ts_dq if t <= now)
        prev_rpm = self._host_calibrated_rpm.get(host, default_rpm)
        if observed_60s >= 4:
            tuned = max(6, min(prev_rpm - 2, int(observed_60s * 0.75)))
        else:
            tuned = max(6, prev_rpm - 3)
        self._host_calibrated_rpm[host] = tuned
        self._host_next_req_time[host] = max(self._host_next_req_time.get(host, 0.0), cooldown_until)
        self._host_recovery_gap_until[host] = max(self._host_recovery_gap_until.get(host, 0.0), cooldown_until + 120.0)
        return tuned

    @staticmethod
    def _evict_pawchive_pools_from_session(sess) -> int:
        """Evict and close `*.pawchive.pw` urllib3 pools on a single idle `requests.Session`."""
        closed = 0
        adapters = getattr(sess, "adapters", None)
        if not isinstance(adapters, dict):
            return 0
        for adapter in list(adapters.values()):
            pm = getattr(adapter, "poolmanager", None)
            pools = getattr(pm, "pools", None)
            if pools is None:
                continue
            evicted = []
            try:
                p_lock = getattr(pools, "lock", None)
                if p_lock is not None:
                    with p_lock:
                        container = getattr(pools, "_container", None)
                        keys = list(container.keys()) if isinstance(container, dict) else []
                        for k in keys:
                            kh = str(getattr(k, "key_host", "") or k).lower()
                            if "pawchive.pw" in kh:
                                pool_obj = container.pop(k, None)
                                if pool_obj is not None:
                                    evicted.append(pool_obj)
                for pool_obj in evicted:
                    try:
                        pool_obj.close()
                        closed += 1
                    except Exception:
                        pass
            except Exception:
                pass
        return closed

    def _close_idle_pawchive_connections(self) -> int:
        """Close pooled idle Keep-Alive HTTP connections to `*.pawchive.pw` during 429 cooldowns.

        Sessions actively executing a request on another worker thread are never closed cross-thread
        (avoiding `HTTPSConnectionPool: Pool is closed` mid-request); instead `_pawchive_pool_reset_epoch`
        is bumped so busy workers recycle their own Pawchive pools as soon as their request finishes.
        """
        sessions_lock = getattr(self, "_worker_sessions_lock", None)
        if sessions_lock is None:
            return 0
        tl = getattr(self, "_thread_local", None)
        cur_sess = getattr(tl, "session", None) if tl is not None else None
        with sessions_lock:
            new_epoch = getattr(self, "_pawchive_pool_reset_epoch", 0) + 1
            self._pawchive_pool_reset_epoch = new_epoch
            in_flight = getattr(self, "_in_flight_sessions", None) or {}
            safe_sessions = [
                s for s in getattr(self, "_worker_sessions", ())
                if s is cur_sess or in_flight.get(s, 0) <= 0
            ]
        closed_pools = 0
        for sess in safe_sessions:
            closed_pools += self._evict_pawchive_pools_from_session(sess)
            if sess is cur_sess and tl is not None:
                tl.pawchive_pool_epoch = new_epoch
        return closed_pools

    def _trigger_rate_limit_backoff(self, threads_locked: bool = False, retry_after: float = 0.0, host: str = ""):
        h = (host or "").strip().lower()
        gov = getattr(self, "pawchive_governor", None)

        # Pawchive domain-wide Two-Layer Governor path (handles shared IP + per-node calibration & Ban-Shield)
        if h and "pawchive.pw" in h and gov is not None:
            with self._rate_limit_lock:
                self._sync_cooldown_mirrors_unlocked()
            info = gov.on_429(host=h, retry_after=retry_after)
            with self._rate_limit_lock:
                cd_until = float(info["cooldown_until"])
                self._rate_limit_cooldown_until = max(self._rate_limit_cooldown_until, cd_until)
                self._consecutive_429_bursts = max(self._consecutive_429_bursts, int(info["wave"]))
                self._rate_limit_probe_needed = True
                self._pawchive_next_req_time = max(self._pawchive_next_req_time, cd_until)

                if not threads_locked:
                    old_workers = self.max_workers
                    if self._learned_stable_ceiling is None:
                        self._learned_stable_ceiling = max(1, old_workers - 1)
                    else:
                        self._learned_stable_ceiling = max(1, min(self._learned_stable_ceiling, old_workers - 1))
                    self._stable_clean_count = 0
                    self.max_workers = max(1, min(old_workers - 2, self._learned_stable_ceiling - 1) if self._learned_stable_ceiling > 2 else 1)
                    if self.on_concurrency_throttled:
                        self.on_concurrency_throttled(self.max_workers)

            if info.get("entered_cooldown"):
                closed_n = self._close_idle_pawchive_connections()
                if closed_n > 0:
                    logger.debug(
                        f"🔌 [Pawchive Rate Guard] Closed {closed_n} idle Pawchive HTTP connection pool(s) for clean cooldown reset.",
                        category="downloader",
                    )

            if info.get("should_auto_pause") and not self._pause_event.is_set():
                self.pause()
                logger.warning(
                    "🛡️ [Pawchive Ban-Shield] 3 consecutive post-cooldown test requests returned HTTP 429 — "
                    "downloads paused automatically to protect your IP from a ban. Wait a few minutes, then click Resume.",
                    category="downloader",
                )
            return

        with self._rate_limit_lock:
            self._sync_cooldown_mirrors_unlocked()
            now = time.time()
            active_cd = self._host_cooldown_until.get(h, 0.0) if h else self._rate_limit_cooldown_until
            if now >= active_cd:
                if h:
                    burst = self._host_consecutive_429.get(h, 0) + 1
                    self._host_consecutive_429[h] = burst
                    self._host_probe_needed[h] = True
                    self._consecutive_429_bursts = max(self._consecutive_429_bursts, burst)
                else:
                    burst = getattr(self, "_consecutive_429_bursts", 0) + 1
                    self._consecutive_429_bursts = burst
                self._rate_limit_probe_needed = True

                tiers = (30.0, 45.0, 60.0, 90.0) if threads_locked else (15.0, 30.0, 60.0, 90.0)
                base_cd = tiers[min(burst - 1, len(tiers) - 1)]
                cooldown_s = min(120.0, max(base_cd, float(retry_after or 0.0)))
                new_cd_until = now + cooldown_s

                if h:
                    self._host_cooldown_until[h] = new_cd_until
                    self._rate_limit_cooldown_until = max(self._rate_limit_cooldown_until, new_cd_until)
                else:
                    self._unscoped_cooldown_until = new_cd_until
                    self._rate_limit_cooldown_until = new_cd_until

                with self._pawchive_pace_lock:
                    self._pawchive_next_req_time = max(self._pawchive_next_req_time, new_cd_until)
                    self._pawchive_recovery_gap_until = max(
                        getattr(self, "_pawchive_recovery_gap_until", 0.0),
                        new_cd_until + 120.0,
                    )

                host_tag = f" on {h}" if h else ""
                if threads_locked:
                    logger.warning(
                        f"⚡ [Rate Limit Cooldown] HTTP 429 encountered{host_tag} (wave {burst})! Threads locked at {self.max_workers} (cooldown {int(cooldown_s)}s, 1-worker probe)...",
                        category="downloader"
                    )
                    return

                old_workers = self.max_workers
                if self._learned_stable_ceiling is None:
                    self._learned_stable_ceiling = max(1, old_workers - 1)
                else:
                    self._learned_stable_ceiling = max(1, min(self._learned_stable_ceiling, old_workers - 1))

                self._stable_clean_count = 0
                self.max_workers = max(1, min(old_workers - 2, self._learned_stable_ceiling - 1) if self._learned_stable_ceiling > 2 else 1)

                logger.warning(
                    f"⚡ [Adaptive Backoff] HTTP 429 encountered{host_tag} (wave {burst})! Locked stable ceiling to {self._learned_stable_ceiling} threads. Dropping concurrency to {self.max_workers} threads (cooldown {int(cooldown_s)}s)...",
                    category="adaptive"
                )
                if self.on_concurrency_throttled:
                    self.on_concurrency_throttled(self.max_workers)

    def _wait_pawchive_pace_slot(self, task: DownloadTask, url: str, respect_cooldown: bool = True) -> bool:
        """Two-Layer (Per-Node + Master *.pawchive.pw IP) pacer delegated to `PawchiveRateGovernor`."""
        if self._wait_if_globally_paused(task) is not None:
            return False

        host = extract_url_host(url)
        if "pawchive.pw" not in host:
            return True

        gov = getattr(self, "pawchive_governor", None)
        if gov is not None:
            wait_s = gov.reserve_pace_slot(host, respect_cooldown=respect_cooldown)
            with self._pawchive_pace_lock:
                self._pawchive_next_req_time = max(self._pawchive_next_req_time, time.time() + max(0.0, wait_s) + 0.45)
        else:
            wait_s = 0.0

        if wait_s <= 0.0:
            return self._wait_if_globally_paused(task) is None

        deadline = time.time() + wait_s
        max_slices = int(wait_s / 0.05) + 2
        for _ in range(max_slices):
            rem = deadline - time.time()
            if rem <= 0.0:
                break
            if self._wait_if_globally_paused(task) is not None:
                return False
            rem = deadline - time.time()
            if rem <= 0.0:
                break
            time.sleep(min(0.05, rem))
        return self._wait_if_globally_paused(task) is None

    @staticmethod
    def task_key(t) -> str:
        """How the Retry Failed list names a file (its id, else its URL, else its name)."""
        return t.file_id or t.url or t.filename

    def _notify_many(self, tasks) -> None:
        """Tells the window about many changed files at once (one message per file piled up into
        seconds-long pauses when thousands were retried)."""
        if not tasks:
            return
        if self.on_tasks_changed:
            self.on_tasks_changed(list(tasks))
        elif self.on_task_status_changed:
            for t in tasks:
                self.on_task_status_changed(t)

    def retry_failed_tasks(self, options: FilterOptions, cookie_str: str, max_auto_retries: int = 5,
                           include_cancelled: bool = True) -> int:
        """Resets all tasks with status 'failed' (and 'cancelled', unless include_cancelled is False)
        to 'pending' up to max_auto_retries (5) and resumes downloading.

        Automatic retries pass include_cancelled=False so files the user stopped stay stopped.
        """
        skip_404 = (
            getattr(options, "skip_retry_404", False)
            if options is not None
            else getattr(self.current_options, "skip_retry_404", False)
        )
        if self.current_options and options is not None:
            self.current_options.skip_retry_404 = skip_404
        retry_statuses = ("failed", "cancelled") if include_cancelled else ("failed",)
        all_failed = [
            t for t in self.tasks
            if t.status in retry_statuses
            or (not self._is_running and t.status == "pending" and (getattr(t, "error_msg", "") or getattr(t, "retry_count", 0) > 0))
        ]
        if not all_failed:
            logger.info("No failed tasks to retry.", category="downloader")
            return 0

        eligible_tasks = []
        capped = []
        for t in all_failed:
            if is_task_non_retryable(t):
                continue
            err = str(getattr(t, "error_msg", "")).lower()
            if skip_404 and ("404" in err or getattr(t, "http_status", 0) == 404):
                continue

            is_fatal_auth = any(f in err for f in (
                "key is not registered",
                "session expired",
                "session revoked",
                "authkey",
                "auth_key",
                "unregistered",
                "unauthorized"
            ))
            if is_fatal_auth:
                t.retry_capped = True
                continue

            cur_retries = getattr(t, "retry_count", 0)
            if cur_retries >= max_auto_retries:
                t.retry_capped = True
                orig_err = getattr(t, "error_msg", "") or "Download failed"
                if f"({max_auto_retries} retries)" not in orig_err:
                    t.error_msg = f"{orig_err} (Stopped after {max_auto_retries} retries)"
                capped.append(t)
            else:
                eligible_tasks.append(t)
        self._notify_many(capped)

        if not eligible_tasks:
            if all(is_task_non_retryable(t) for t in all_failed):
                logger.info(
                    f"Skipped retry for {len(all_failed)} unimported Pawchive file(s) — full files aren't hosted on Pawchive yet.",
                    category="downloader",
                )
            else:
                logger.info(f"All {len(all_failed)} failed task(s) reached max retry limit ({max_auto_retries}). Skipped by auto-retry but preserved in modal.", category="downloader")
            return 0

        for t in eligible_tasks:
            t.retry_count = getattr(t, "retry_count", 0) + 1
            t.retry_capped = False
            t.status = "pending"
            t.error_msg = ""
            t.http_status = 0
            t.progress_pct = 0
            t.downloaded_bytes = 0
            t.speed_bps = 0
            t.speed_str = "0 KB/s"
            t.eta_str = "--"
        self._notify_many(eligible_tasks)

        logger.info(f"Flagged {len(eligible_tasks)} failed tasks for retry (attempt {eligible_tasks[0].retry_count}/{max_auto_retries}).", category="downloader")

        if not self._is_running:
            self.start_download_queue(self.tasks, options, cookie_str)

        return len(eligible_tasks)

    def retry_selected_tasks(self, selected_ids: List[str], options: FilterOptions, cookie_str: str) -> int:
        """Resets only user-selected failed or cancelled tasks to 'pending' and resumes downloading."""
        if not selected_ids:
            logger.info("No tasks selected for retry.", category="downloader")
            return 0

        skip_404 = (
            getattr(options, "skip_retry_404", False)
            if options is not None
            else getattr(self.current_options, "skip_retry_404", False)
        )
        if self.current_options and options is not None:
            self.current_options.skip_retry_404 = skip_404

        if skip_404:
            for t in self.tasks:
                if t.status == "pending" and ("404" in str(getattr(t, "error_msg", "")).lower() or getattr(t, "http_status", 0) == 404):
                    t.status = "failed"
        selected_set = set(selected_ids)
        target_tasks = []
        for t in self.tasks:
            # Matched by the same name the list gives it (a file name used to match every file with
            # that name, e.g. all "001.jpg"s of other posts)
            if self.task_key(t) not in selected_set:
                continue
            if is_task_non_retryable(t):
                continue
            is_eligible = (
                t.status in ("failed", "cancelled")
                or (not self._is_running and t.status == "pending")
            )
            if not is_eligible:
                continue
            if skip_404 and ("404" in str(getattr(t, "error_msg", "")).lower() or getattr(t, "http_status", 0) == 404):
                continue
            target_tasks.append(t)

        if not target_tasks:
            logger.info("No matching failed tasks found to retry.", category="downloader")
            return 0

        for t in target_tasks:
            t.retry_count = getattr(t, "retry_count", 0) + 1
            t.retry_capped = False
            t.status = "pending"
            t.error_msg = ""
            t.http_status = 0
            t.progress_pct = 0
            t.downloaded_bytes = 0
            t.speed_bps = 0
            t.speed_str = "0 KB/s"
            t.eta_str = "--"
        self._notify_many(target_tasks)

        logger.info(f"Flagged {len(target_tasks)} selected tasks for retry.", category="downloader")

        if not self._is_running:
            self.start_download_queue(self.tasks, options, cookie_str)

        return len(target_tasks)

    @staticmethod
    def _task_context(task: "DownloadTask") -> str:
        """Extra lines for the log file when a file fails: where it came from and what was tried."""
        lines = []
        creator = " / ".join(x for x in (getattr(task, "creator_name", ""), getattr(task, "service", ""), str(getattr(task, "user_id", "") or "")) if x)
        if creator:
            lines.append(f"creator: {creator}")
        if getattr(task, "post_id", "") or getattr(task, "post_title", ""):
            lines.append(f"post: {task.post_id} {task.post_title!r}" + (f" ({task.post_url})" if getattr(task, "post_url", "") else ""))
        lines.append(f"url: {task.url}")
        tried = getattr(task, "_tried_urls", None) or []
        if len(tried) > 1 or (tried and tried[0] != task.url):
            lines.append("servers tried: " + ", ".join(tried))
        if getattr(task, "target_path", ""):
            lines.append(f"save to: {task.target_path}")
        if getattr(task, "retry_count", 0):
            lines.append(f"retry: {task.retry_count}")
        return "\n".join(lines)

    def _describe_run(self, options: FilterOptions, cookie_str: str, run_count: int) -> str:
        """The settings a download ran with, for the log file (bug reports need them)."""
        lines = [
            f"files in queue: {len(self.tasks)} ({run_count} to download in this run)",
            f"workers: {self.max_workers}",
            "login cookie: " + ("set in settings" if (cookie_str or "").strip() else "not set in settings (a saved login may still be used)"),
        ]
        folders = sorted({os.path.dirname(t.target_path) for t in self.tasks if getattr(t, "target_path", "")})
        if folders:
            lines.append(f"save folders ({len(folders)}): " + "; ".join(folders[:5]) + (" …" if len(folders) > 5 else ""))
        for key, value in sorted(vars(options).items()):
            if key.startswith("_") or callable(value):
                continue
            text = repr(value)
            lines.append(f"{key} = {text[:200] + '…' if len(text) > 200 else text}")
        return "\n".join(lines)
