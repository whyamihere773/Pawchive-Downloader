"""
Downloader Rate-Limit Backoff, Pawchive Pacing, Retries & Diagnostic Context Mixin
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import os
import random
import re
import threading
import time
from typing import List, Optional, Set, Tuple

from core.downloader_models import (
    DownloadTask,
    PART_SUFFIX,
    is_task_non_retryable,
)
from core.filter_engine import FilterEngine, FilterOptions
from core.logger import logger
from core.providers import is_disabled

_PAWCHIVE_STORAGE_NODE_RE = re.compile(r"\b(?:file|n\d+)\.pawchive\.pw\b", re.IGNORECASE)


class DownloaderRetriesPacingMixin:
    """Adaptive rate-limit backoff, Pawchive polite pacing, task retries, and log diagnostics."""

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
        """Sleep for `seconds` while honoring cancel, batch pause, and global pause."""
        early = self._wait_if_globally_paused(task)
        if early is not None:
            return early
        if seconds <= 0.0:
            return None
        steps = int(seconds / 0.1)
        rem = seconds - steps * 0.1
        for _ in range(steps):
            early = self._wait_if_globally_paused(task)
            if early is not None:
                return early
            time.sleep(0.1)
        if rem > 0.0:
            early = self._wait_if_globally_paused(task)
            if early is not None:
                return early
            time.sleep(rem)
        return self._wait_if_globally_paused(task)

    def _claim_429_probe_slot(self) -> bool:
        """Allow only one worker per cooldown window to run the Pass-1 verification probe."""
        with self._rate_limit_lock:
            cd_until = getattr(self, "_rate_limit_cooldown_until", 0.0)
            claimed_until = getattr(self, "_rate_limit_probe_claimed_until", 0.0)
            if cd_until > claimed_until:
                self._rate_limit_probe_claimed_until = cd_until
                return True
            return False

    def _on_pawchive_request_succeeded(self) -> None:
        """Reset consecutive 429 burst escalation and single-probe guard after a clean response."""
        with self._rate_limit_lock:
            self._consecutive_429_bursts = 0
            self._rate_limit_probe_needed = False

    def _trigger_rate_limit_backoff(self, threads_locked: bool = False, retry_after: float = 0.0):
        with self._rate_limit_lock:
            now = time.time()
            if now >= self._rate_limit_cooldown_until:
                burst = getattr(self, "_consecutive_429_bursts", 0) + 1
                self._consecutive_429_bursts = burst
                self._rate_limit_probe_needed = True
                if threads_locked:
                    locked_tiers = (30.0, 45.0, 60.0, 90.0)
                    base_cd = locked_tiers[min(burst - 1, len(locked_tiers) - 1)]
                    cooldown_s = min(120.0, max(base_cd, float(retry_after or 0.0)))
                    self._rate_limit_cooldown_until = now + cooldown_s
                    with self._pawchive_pace_lock:
                        self._pawchive_next_req_time = max(self._pawchive_next_req_time, self._rate_limit_cooldown_until)
                        self._pawchive_recovery_gap_until = max(
                            getattr(self, "_pawchive_recovery_gap_until", 0.0),
                            self._rate_limit_cooldown_until + 120.0,
                        )
                    logger.warning(
                        f"⚡ [Rate Limit Cooldown] HTTP 429 encountered (wave {burst})! Threads locked at {self.max_workers} (cooldown {int(cooldown_s)}s, 1-worker probe)...",
                        category="downloader"
                    )
                    return

                adaptive_tiers = (15.0, 30.0, 60.0, 90.0)
                base_cd = adaptive_tiers[min(burst - 1, len(adaptive_tiers) - 1)]
                cooldown_s = min(120.0, max(base_cd, float(retry_after or 0.0)))
                self._rate_limit_cooldown_until = now + cooldown_s
                with self._pawchive_pace_lock:
                    self._pawchive_next_req_time = max(self._pawchive_next_req_time, self._rate_limit_cooldown_until)
                    self._pawchive_recovery_gap_until = max(
                        getattr(self, "_pawchive_recovery_gap_until", 0.0),
                        self._rate_limit_cooldown_until + 120.0,
                    )
                old_workers = self.max_workers
                
                # Remember and lock down the stable ceiling
                # If old_workers hit 429, the ceiling is at most old_workers - 1
                if self._learned_stable_ceiling is None:
                    self._learned_stable_ceiling = max(1, old_workers - 1)
                else:
                    self._learned_stable_ceiling = max(1, min(self._learned_stable_ceiling, old_workers - 1))
                
                self._stable_clean_count = 0
                self.max_workers = max(1, min(old_workers - 2, self._learned_stable_ceiling - 1) if self._learned_stable_ceiling > 2 else 1)
                
                logger.warning(
                    f"⚡ [Adaptive Backoff] HTTP 429 encountered (wave {burst})! Locked stable ceiling to {self._learned_stable_ceiling} threads. Dropping concurrency to {self.max_workers} threads (cooldown {int(cooldown_s)}s)...",
                    category="adaptive"
                )
                if self.on_concurrency_throttled:
                    self.on_concurrency_throttled(self.max_workers)

    def _wait_pawchive_pace_slot(self, task: DownloadTask, url: str, respect_cooldown: bool = True) -> bool:
        """Cross-thread request-start pacer for Pawchive hosts.

        Keeps aggregate request starts across all concurrent worker threads comfortably below
        Pawchive's nginx rate-limit bucket (respecting active 429 cooldowns and global pause),
        while letting large file streams download at full parallel bandwidth once started.
        Returns False if the task was cancelled or batch-paused while waiting.
        """
        if self._wait_if_globally_paused(task) is not None:
            return False

        u_low = (url or "").lower()
        if "pawchive.pw" not in u_low:
            return True

        now_check = time.time()
        in_recovery = now_check < getattr(self, "_pawchive_recovery_gap_until", 0.0)
        if "img.pawchive.pw" in u_low:
            min_gap = 0.35 if in_recovery else 0.15
        elif _PAWCHIVE_STORAGE_NODE_RE.search(u_low):
            min_gap = 1.25 if in_recovery else 0.50
        else:
            min_gap = 0.90 if in_recovery else 0.38

        with self._pawchive_pace_lock:
            now = time.time()
            floor = max(now, self._rate_limit_cooldown_until) if respect_cooldown else now
            slot = max(floor, self._pawchive_next_req_time) if respect_cooldown else max(now, min(self._pawchive_next_req_time, now + min_gap))
            self._pawchive_next_req_time = max(self._pawchive_next_req_time, slot + min_gap)
            wait_s = max(0.0, slot - now)

        if wait_s <= 0.0:
            return self._wait_if_globally_paused(task) is None

        steps = int(wait_s / 0.05)
        rem = wait_s - steps * 0.05
        for _ in range(steps):
            if self._wait_if_globally_paused(task) is not None:
                return False
            time.sleep(0.05)
        if rem > 0.0:
            if self._wait_if_globally_paused(task) is not None:
                return False
            time.sleep(rem)
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
