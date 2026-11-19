"""
Downloader Main Worker Loop & Dynamic Queue Dispatch Mixin
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import os
import random
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor as _DefaultThreadPoolExecutor
from typing import List

from core.downloader_models import (
    DownloadTask,
    _counts,
    is_permanent_failure,
    is_task_non_retryable,
)
from core.filter_engine import FilterOptions
from core.logger import logger
from core.statistics_manager import statistics_manager


def _get_executor_cls():
    """Resolve ThreadPoolExecutor through core.downloader so test patches work."""
    mod = sys.modules.get("core.downloader")
    if mod is not None and hasattr(mod, "ThreadPoolExecutor"):
        return mod.ThreadPoolExecutor
    return _DefaultThreadPoolExecutor


class DownloaderLoopMixin:
    """Runs the dynamic concurrent download pool, adaptive scaling, and auto-retry rounds."""

    def _run_download_loop(self, options: FilterOptions, cookie_str: str, session_id: int = 0):
        self._keep_paths_apart(self.tasks, [])
        self._save_recovery_checkpoint(options, async_write=True)
        self.current_options = options
        self.start_time = time.time()
        self.downloaded_bytes = 0
        statistics_manager.set_download_active(True)
        self._speed_samples.clear()
        self._rolling_speed_samples.clear()
        self._smoothed_speed = 0.0
        self._medium_speed = 0.0
        self._smoothed_eta = None
        self._last_eta_calc_time = 0.0
        self._last_progress_emit_time = 0.0
        self._total_paused_time = 0.0
        self._pause_start_time = 0.0
        self._first_byte_time = 0.0
        cpu_cores = max(4, os.cpu_count() or 16)
        is_locked = getattr(self.current_options or options, "threads_locked", False)
        # Adaptive threading tops out at 8: beyond that the file servers rate-limit and the app
        # mostly spends its time on bookkeeping (16 threads made the window stop responding, #24).
        # For Pawchive queues, cap Adaptive Threading at 4 threads to respect Pawchive's ~30 req/10s
        # nginx rate limit and avoid overloading storage nodes (e.g. n2.pawchive.pw timeouts).
        is_pawchive_queue = bool(self.tasks) and any(
            "pawchive" in (getattr(t, "url", "") or "").lower()
            or "pawchive" in (getattr(t, "post_url", "") or "").lower()
            for t in self.tasks
            if getattr(t, "status", "") == "pending"
        )
        adaptive_cap = 4 if is_pawchive_queue else 8
        target_max_workers = min(cpu_cores, adaptive_cap) if (options.adaptive_threading and not is_locked) else max(1, self.max_workers)
        last_scale_time = time.time()
        last_checkpoint_time = time.time()
        consecutive_successes = 0
        scale_step_interval = 8.0 # Check scaling up every 8 seconds of healthy throughput

        # Strict Telegram Concurrency Lock: Under ANY circumstance, Telegram downloads must never exceed 2 threads
        is_pure_telegram = bool(self.tasks) and all(
            getattr(t, "is_telegram", False) or getattr(t, "service", "") == "telegram" or (t.url and t.url.startswith("tg://"))
            for t in self.tasks
        )

        if is_pure_telegram:
            self.max_workers = min(self.max_workers, 2)
            target_max_workers = 2
            is_locked = True
            options.adaptive_threading = False
            logger.info("🔒 [Telegram] Concurrency locked strictly to 2 worker threads for MTProto session stability.", category="telegram")
            if self.on_concurrency_throttled:
                self.on_concurrency_throttled(self.max_workers)
        # If Adaptive Threading is enabled and threads are not locked, start with 2 worker threads and scale up to CPU core count
        elif options.adaptive_threading and not is_locked:
            self.max_workers = min(2, target_max_workers)
            logger.info(f"⚡ [Adaptive Threading] Active: Starting with {self.max_workers} worker threads (Max CPU limit: {target_max_workers} threads)...", category="adaptive")
            if self.on_concurrency_throttled:
                self.on_concurrency_throttled(self.max_workers)
        else:
            lock_label = " (Locked)" if is_locked else ""
            logger.info(f"Starting download pool with {self.max_workers} worker threads{lock_label}...", category="downloader")

        skip_404_active = (
            getattr(options, "skip_retry_404", False)
            if options is not None
            else getattr(self.current_options, "skip_retry_404", False)
        )
        if skip_404_active:
            for t in self.tasks:
                if t.status == "pending" and ("404" in str(getattr(t, "error_msg", "")).lower() or getattr(t, "http_status", 0) == 404):
                    t.status = "failed"
            self._run_tasks = [
                t for t in self.tasks
                if t.status == "pending" and not ("404" in str(getattr(t, "error_msg", "")).lower() or getattr(t, "http_status", 0) == 404)
            ]
        else:
            self._run_tasks = [t for t in self.tasks if t.status == "pending"]
        self._already_there = Counter()          # files found downloaded already (counted in the log file)
        logger.debug("Download settings saved to the log file.", category="downloader",
                     details=self._describe_run(options, cookie_str, len(self._run_tasks)))

        # Auto-normalize cookie if user pasted raw JWT token, or load from encrypted auth_manager vault
        clean_cookie = cookie_str.strip() if cookie_str else ""
        if not clean_cookie:
            try:
                from core.auth_manager import auth_manager
                clean_cookie = auth_manager.get_credential("kemono", "cookie")
            except Exception:
                pass

        if clean_cookie:
            if clean_cookie.startswith("eyJ") and "session=" not in clean_cookie:
                clean_cookie = f"session={clean_cookie}"
            elif "=" not in clean_cookie:
                clean_cookie = f"session={clean_cookie}"
            logger.debug(f"Applied authenticated session cookie ({len(clean_cookie)} chars)", category="downloader")

        self._clean_cookie = clean_cookie

        active_futures = {}
        last_count_time = 0.0

        try:
            with _get_executor_cls()(max_workers=max(32, target_max_workers)) as executor:
                while not self._cancel_event.is_set() and (session_id == self._session_id):
                    now = time.time()
                    is_locked = getattr(self.current_options or options, "threads_locked", False)

                    # Effective ceiling: learned ceiling if we encountered 429, else user target
                    effective_ceiling = self._learned_stable_ceiling if self._learned_stable_ceiling is not None else target_max_workers

                    # 1. Check Adaptive Scaling timer (every 5 seconds)
                    if options.adaptive_threading and not is_locked and (now - last_scale_time >= scale_step_interval):
                        last_scale_time = now
                        # Only scale up if not currently in rate-limit cooldown
                        if now >= self._rate_limit_cooldown_until:
                            if self.max_workers < effective_ceiling:
                                self.max_workers += 1
                                consecutive_successes = 0
                                logger.info(
                                    f"⚡ [Adaptive Threading] Connection stable. Scaling up concurrency to {self.max_workers}/{effective_ceiling} threads (ceiling: {effective_ceiling})...",
                                    category="adaptive"
                                )
                                if self.on_concurrency_throttled:
                                    self.on_concurrency_throttled(self.max_workers)
                            elif self._stable_clean_count >= 50 and effective_ceiling < target_max_workers:
                                # Long-term stability probe after 50 consecutive error-free downloads
                                self._learned_stable_ceiling += 1
                                self.max_workers += 1
                                self._stable_clean_count = 0
                                consecutive_successes = 0
                                logger.info(
                                    f"⚡ [Adaptive Threading] Long-term stability verified (50+ clean files). Probing higher concurrency (+1 to {self.max_workers} threads)...",
                                    category="adaptive"
                                )
                                if self.on_concurrency_throttled:
                                    self.on_concurrency_throttled(self.max_workers)

                    # 2-3. Always drain finished futures first (even during cooldown/pause) so per-batch
                    # quiescence never stalls waiting on un-popped futures.
                    done_futures = [f for f in active_futures if f.done()]
                    for f in done_futures:
                        task = active_futures.pop(f)
                        bid = self._task_batch_id(task)
                        try:
                            success, msg = f.result()
                            if self.is_batch_cancelled(task):
                                task.status = "cancelled"
                                task.error_msg = "Download cancelled by user"
                                task.speed_bps = 0
                                task.speed_str = "0 KB/s"
                                task.eta_str = "--"
                                if self.on_task_status_changed:
                                    self.on_task_status_changed(task)
                            elif success:
                                if task.status == "skipped" or (msg and msg.startswith("Skipped:")):
                                    task.status = "skipped"
                                    if not task.error_msg and msg.startswith("Skipped:"):
                                        task.error_msg = msg[len("Skipped:"):].strip()
                                    task.progress_pct = 100
                                    task.eta_str = "Skipped"
                                    statistics_manager.record_file_result("skipped")
                                    self._write_pending_post_info(task)
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(task)
                                else:
                                    task.status = "completed"
                                    task.error_msg = ""
                                    statistics_manager.record_file_result("completed")
                                    consecutive_successes += 1
                                    self._stable_clean_count += 1
                                    self.session_manager.record_downloaded_file(task.file_id)
                                    self._write_pending_post_info(task)
                                    if self.archive_manager and self.archive_manager.is_enabled and not getattr(task, "used_preview", False):
                                        self.archive_manager.record_file(
                                            service=task.service,
                                            creator_id=task.user_id,
                                            post_id=task.post_id,
                                            file_id=task.file_id,
                                            file_hash=task.expected_sha256,
                                            filename=task.filename,
                                            creator_name=task.creator_name,
                                            post_title=task.post_title,
                                            file_size=task.file_size,
                                            file_path=task.target_path
                                        )
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(task)

                                    # Fast Adaptive Scaling: Scale up after 10 consecutive successful files if below ceiling and interval elapsed
                                    if options.adaptive_threading and not is_locked and not is_pure_telegram and consecutive_successes >= 10 and (now - last_scale_time >= 6.0):
                                        effective_ceiling = self._learned_stable_ceiling if self._learned_stable_ceiling is not None else target_max_workers
                                        if now >= self._rate_limit_cooldown_until and self.max_workers < effective_ceiling:
                                            self.max_workers += 1
                                            consecutive_successes = 0
                                            last_scale_time = now
                                            logger.info(
                                                f"⚡ [Adaptive Threading] Fast-scaling concurrency to {self.max_workers}/{effective_ceiling} threads...",
                                                category="adaptive"
                                            )
                                            if self.on_concurrency_throttled:
                                                self.on_concurrency_throttled(self.max_workers)
                            else:
                                consecutive_successes = 0
                                self._stable_clean_count = 0
                                if msg.startswith("429_RATE_LIMIT"):
                                    # 429 Rate Limit encountered -> auto-retry after cooldown (30s if locked, 15s if adaptive)
                                    wait_secs = 30 if is_locked else 15
                                    task.status = "pending"
                                    task.error_msg = f"Rate limited (429) — cooling down for {wait_secs}s before auto-retry"
                                    statistics_manager.record_retry()
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(task)
                                    self._trigger_rate_limit_backoff(threads_locked=is_locked)
                                    last_scale_time = time.time() + float(wait_secs)
                                elif "Disk full" in msg:
                                    task.status = "pending"
                                    task.error_msg = msg
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(task)
                                    if not self._pause_event.is_set():
                                        self.pause()
                                        logger.warning(
                                            "⚠️ [Disk Full Alert] Destination drive ran out of space! Downloads paused to prevent file corruption. Please free space on your drive and click Resume.",
                                            category="downloader"
                                        )
                                elif "Batch paused by user" in msg or self.is_batch_paused(task) or task.status == "paused":
                                    task.status = "paused"
                                    task.error_msg = ""
                                    task.speed_bps = 0
                                    task.speed_str = "0 KB/s"
                                    task.eta_str = "Paused"
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(task)
                                elif msg == "Cancelled":
                                    task.status = "cancelled"
                                    task.error_msg = "Download cancelled by user"
                                    task.speed_bps = 0
                                    task.speed_str = "0 KB/s"
                                    task.eta_str = "--"
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(task)
                                else:
                                    task.status = "failed"
                                    task.error_msg = msg
                                    statistics_manager.record_file_result("failed")
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(task)
                        except Exception as e:
                            consecutive_successes = 0
                            task.status = "failed"
                            task.error_msg = str(e)
                            statistics_manager.record_file_result("failed")
                            logger.error(f"Error downloading {task.filename}: {e}", category="downloader",
                                         details=self._task_context(task) + "\n" + traceback.format_exc())
                            if self.on_task_status_changed:
                                self.on_task_status_changed(task)
                        finally:
                            self._decrement_batch_worker(bid)

                    # Emit progress a few times a second, from counts kept as statuses change (counting
                    # a huge queue by looping over it used a lot of CPU and made the window stutter)
                    if now - last_count_time >= 0.3:
                        last_count_time = now
                        counts = self.status_counts()
                        completed_count = counts["completed"] + counts["skipped"]
                        failed_count = counts["failed"]
                        self._emit_progress(completed_count, failed_count, len(self.tasks))

                    # 4. If in cooldown or paused or cancelled, wait
                    if time.time() < self._rate_limit_cooldown_until or self._pause_event.is_set() or self._cancel_event.is_set():
                        time.sleep(0.2)
                        continue

                    # 5. Dispatch pending tasks up to self.max_workers with Anti-Burst Staggering
                    current_active = len(active_futures)
                    slots_available = max(0, self.max_workers - current_active)
                    if slots_available > 0:
                        pending_tasks = self._collect_pending(slots_available * 4 + 8, now)
                        if not pending_tasks and current_active == 0:
                            pending_tasks = self._collect_pending(slots_available * 4 + 8, now, full=True)
                        if not pending_tasks and current_active == 0:
                            has_paused_tasks = any(
                                (self.is_batch_paused(t) or t.status == "paused")
                                for t in self.tasks
                                if t.status in ("pending", "paused")
                            )
                            rebuild_active = self.has_pending_rebuilds()
                            if (has_paused_tasks or rebuild_active) and not self._cancel_event.is_set():
                                time.sleep(0.25)
                                continue

                            # Check if "auto retry at the end" is enabled dynamically
                            auto_retry_active = (
                                getattr(self.current_options, "auto_retry_at_end", False)
                                if self.current_options
                                else options.auto_retry_at_end
                            )
                            if auto_retry_active and not self._cancel_event.is_set():
                                skip_404 = (
                                    getattr(self.current_options, "skip_retry_404", False)
                                    if self.current_options is not None
                                    else getattr(options, "skip_retry_404", False)
                                )
                                all_failed = [t for t in self.tasks if t.status == "failed"]
                                failed_tasks = []
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
                                    if getattr(t, "retry_count", 0) < 5:
                                        failed_tasks.append(t)
                                    else:
                                        t.retry_capped = True
                                        orig_err = getattr(t, "error_msg", "") or "Download failed"
                                        if "(Stopped after 5 retries)" not in orig_err:
                                            t.error_msg = f"{orig_err} (Stopped after 5 retries)"
                                        if self.on_task_status_changed:
                                            self.on_task_status_changed(t)

                                if failed_tasks:
                                    retry_attempt = getattr(failed_tasks[0], 'retry_count', 0) + 1
                                    wait_time = min(6.0, 1.5 * retry_attempt)
                                    logger.info(
                                        f"🔄 Auto-retry triggered for {len(failed_tasks)} failed files (attempt {retry_attempt}/5, cooling down {wait_time:.1f}s)...",
                                        category="downloader"
                                    )
                                    for t in failed_tasks:
                                        t.retry_count = getattr(t, "retry_count", 0) + 1
                                        t.retry_capped = False
                                        t.status = "pending"
                                        t.error_msg = ""
                                        t.progress_pct = 0
                                        t.downloaded_bytes = 0
                                        t.speed_bps = 0
                                        t.speed_str = "0 KB/s"
                                        t.eta_str = "--"
                                        if self.on_task_status_changed:
                                            self.on_task_status_changed(t)
                                    time.sleep(wait_time)
                                    continue

                            # All tasks completed or finished
                            break

                        # Telegram concurrency cap (strictly max 2 active Telegram downloads under any circumstance)
                        active_tg_count = sum(
                            1 for t in active_futures.values()
                            if getattr(t, "is_telegram", False) or getattr(t, "service", "") == "telegram" or (t.url and t.url.startswith("tg://"))
                        )

                        tasks_to_dispatch = []
                        for task in pending_tasks:
                            if len(tasks_to_dispatch) >= slots_available:
                                break
                            is_tg = getattr(task, "is_telegram", False) or getattr(task, "service", "") == "telegram" or (task.url and task.url.startswith("tg://"))
                            if is_tg and (active_tg_count >= 2):
                                continue
                            if is_tg:
                                active_tg_count += 1
                            tasks_to_dispatch.append(task)

                        for i, task in enumerate(tasks_to_dispatch):
                            if self._cancel_event.is_set():
                                break
                            # Feature 4: Jittered Inter-Request Staggering (Anti-Burst Smoothing)
                            if i > 0 and not self._cancel_event.is_set():
                                is_pawchive_target = "pawchive" in (task.url or "").lower() or (getattr(task, "service", None) and "pawchive" in str(task.service).lower())
                                stagger = random.uniform(0.12, 0.22) if is_pawchive_target else 0.06
                                time.sleep(stagger)

                            if self._cancel_event.is_set():
                                break
                            bid = self._task_batch_id(task)
                            if self.is_batch_paused(bid) or self.is_batch_cancelled(bid):
                                continue
                            with self._mutation_lock:
                                if bid in self._pending_rebuild_batches:
                                    continue

                            task.status = "downloading"
                            if self.on_task_status_changed:
                                self.on_task_status_changed(task)
                            self._increment_batch_worker(bid)
                            try:
                                task_opts = getattr(task, "options", None) or self.get_batch_options(bid) or options
                                fut = executor.submit(self._worker_download_task, task, task_opts)
                                active_futures[fut] = task
                            except RuntimeError:
                                self._decrement_batch_worker(bid)
                                # Executor was shut down (e.g. cancelled)
                                task.status = "pending"
                                break

                    # Feature 5: Track Adaptive Health State
                    if is_locked:
                        if now < self._rate_limit_cooldown_until:
                            self.adaptive_state = "cooldown"
                            rem = max(1, int(self._rate_limit_cooldown_until - now))
                            self.adaptive_status_text = f"Cooldown: {rem}s (Locked {self.max_workers} threads)"
                        else:
                            self.adaptive_state = "locked"
                            self.adaptive_status_text = f"Locked ({self.max_workers} threads)"
                    elif options.adaptive_threading:
                        if now < self._rate_limit_cooldown_until:
                            self.adaptive_state = "cooldown"
                            rem = max(1, int(self._rate_limit_cooldown_until - now))
                            self.adaptive_status_text = f"Cooldown: {rem}s ({self.max_workers} threads)"
                        elif self._learned_stable_ceiling is not None and self.max_workers >= self._learned_stable_ceiling:
                            self.adaptive_state = "optimal"
                            self.adaptive_status_text = f"Stable Lock ({self.max_workers} threads)"
                        elif self.max_workers >= target_max_workers:
                            self.adaptive_state = "optimal"
                            self.adaptive_status_text = f"Optimal ({self.max_workers} threads)"
                        else:
                            self.adaptive_state = "scaling"
                            effective_ceiling = self._learned_stable_ceiling if self._learned_stable_ceiling is not None else target_max_workers
                            self.adaptive_status_text = f"Scaling ({self.max_workers}/{effective_ceiling} threads)"
                    else:
                        self.adaptive_state = "manual"
                        self.adaptive_status_text = f"Manual ({self.max_workers} threads)"

                    # Periodic crash-proof checkpoint (every 30 seconds), written in the background: writing
                    # 1,000+ tasks with fsync here used to stop new downloads from starting for 30-50 s on
                    # slow drives (e.g. a Windows drive mounted under /mnt on Linux)
                    if now - last_checkpoint_time >= 30.0:
                        last_checkpoint_time = now
                        self._save_recovery_checkpoint(options, async_write=True)

                    time.sleep(0.05)

                # Cancel remaining active futures if cancelling
                for f in list(active_futures.keys()):
                    try:
                        f.cancel()
                    except Exception:
                        pass
        finally:
            for f, t in list(active_futures.items()):
                self._decrement_batch_worker(self._task_batch_id(t))
            active_futures.clear()

        self._close_worker_sessions()
        # The memory cleanup runs on the window thread: a Qt object freed by it on this thread
        # crashes the app
        if self.on_cleanup_wanted:
            try:
                self.on_cleanup_wanted()
            except Exception:
                pass

        # Discard exit handlers if this thread has been superseded by a newer download session
        if session_id != self._session_id:
            statistics_manager.set_download_active(False)
            logger.debug(f"Discarding exit of superseded download session {session_id} (active: {self._session_id}).", category="downloader")
            return

        statistics_manager.set_download_active(False)
        self._is_running = False
        duration = self._get_active_elapsed(time.time())
        completed_count = sum(1 for t in self.tasks if t.status == "completed")
        failed_count = sum(1 for t in self.tasks if t.status == "failed")
        skipped_count = sum(1 for t in self.tasks if t.status == "skipped")
        self._emit_progress(completed_count + skipped_count, failed_count, len(self.tasks), force=True)
        live_infos = {(t.post_info_path, getattr(t, "post_id", "")) for t in self.tasks
                      if getattr(t, "post_info_path", "") and t.status not in ("completed", "skipped")}
        live_paths = {p for p, _ in live_infos}
        for _key in list(self._post_info_pending):
            if isinstance(_key, tuple):
                if _key not in live_infos:
                    self._post_info_pending.pop(_key, None)
            elif _key not in live_paths:
                self._post_info_pending.pop(_key, None)

        if self._cancel_event.is_set():
            rec = getattr(self.session_manager, "recovery_manager", None)
            if rec:
                rec.discard_recovery()
            logger.warning(f"Download cancelled. Completed: {completed_count}, Skipped: {skipped_count}, Failed/Cancelled: {failed_count}", category="downloader")
            if self.on_download_finished:
                self.on_download_finished(False, "Download cancelled by user.")
        else:
            # Keep a recovery journal only for files that never got their turn. Failed files are kept
            # for Retry Failed instead: in the journal they brought the recovery prompt back on every
            # launch, and resuming (which only downloads pending files) couldn't do anything (#28).
            unfinished = [t for t in self.tasks if t.status in ("pending", "downloading", "retrying")]
            if not unfinished:
                rec = getattr(self.session_manager, "recovery_manager", None)
                if rec:
                    rec.discard_recovery()
            else:
                self._save_recovery_checkpoint(options)
            skip_msg = f", {skipped_count} skipped" if skipped_count > 0 else ""
            # What this run did (a retry only handles the files it retried, not the whole queue)
            run_tasks = getattr(self, "_run_tasks", None) or []
            run_note = ""
            if run_tasks and len(run_tasks) < len(self.tasks):
                run_ok = sum(1 for t in run_tasks if t.status in ("completed", "skipped"))
                run_note = f" This run: {run_ok} of {len(run_tasks)} file(s) succeeded."
            already = getattr(self, "_already_there", None)
            if already:
                run_note += f" Found downloaded already: {_counts(already)}."
            failed_tasks = [t for t in self.tasks if t.status == "failed"]
            failed_list = "\n".join(
                f"{t.filename}: {t.error_msg or 'unknown error'}  ({t.url})" for t in failed_tasks
            )
            logger.success(
                f"Download completed in {duration:.1f}s! ({completed_count} successful{skip_msg}, {failed_count} errors){run_note}",
                category="downloader",
                details=(f"Failed files ({len(failed_tasks)}):\n{failed_list}" if failed_tasks else "")
            )
            statistics_manager.record_batch_completed()
            if getattr(options, "separate_by_known", False):
                unmatched = getattr(self, "_unmatched_known_count", 0)
                ai_active = self.known_manager and getattr(self.known_manager, "_ai_recognition_enabled", False)
                if unmatched > 0 and not ai_active:
                    logger.info(
                        f"💡 [AI Tip] {unmatched} post(s) were saved to 'Other' without a matching character in Known.txt. "
                        "Enable Pawchive's offline AI in Settings → AI & Recognition to deduce obscure characters automatically.",
                        category="ai"
                    )
            if self.on_download_finished:
                self.on_download_finished(True, f"Completed: {completed_count} downloaded{skip_msg}, {failed_count} failed.")

    def _collect_pending(self, limit: int, now: float, full: bool = False) -> List[DownloadTask]:
        """Up to `limit` pending files, without walking the whole queue 20 times a second: finished
        files pile up at the front, so the scan starts where pending ones began last time. A full
        scan every second picks up files that were put back in line (retries, rate limits)."""
        tasks = self.tasks
        if full or now - self._last_full_scan >= 1.0 or self._dispatch_cursor > len(tasks):
            self._dispatch_cursor = 0
            self._last_full_scan = now
        found: List[DownloadTask] = []
        first = None
        for i in range(self._dispatch_cursor, len(tasks)):
            t = tasks[i]
            if t.status == "pending" and not self.is_batch_paused(t) and not self.is_batch_cancelled(t):
                if first is None:
                    first = i
                found.append(t)
                if len(found) >= limit:
                    break
        self._dispatch_cursor = first if first is not None else len(tasks)
        return found

    def _worker_download_task(self, task: DownloadTask, options: FilterOptions):
        try:
            worker_session = self._get_worker_session()
            task_opts = getattr(task, "options", None) or self.get_batch_options(getattr(task, "batch_id", "")) or options
            return self._download_single_file(task, worker_session, task_opts)
        except Exception as e:
            return False, str(e)
