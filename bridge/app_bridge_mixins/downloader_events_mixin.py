"""Auto-extracted AppBridge domain mixin (see bridge/app_bridge.py)."""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import Property, QCoreApplication, QObject, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QApplication, QFileDialog

from bridge.app_bridge_mixins.signals_mixin import AppBridgeSignalsMixin
from bridge.archive_creators_model import ArchiveCreatorsModel, RecordListModel
from bridge.decompressor_bridge import DecompressorBridge
from bridge.known_model import KnownModel
from bridge.log_model import LogModel
from bridge.queue_model import QueueModel
from bridge.telegram_bridge import TelegramBridge
from bridge.thumbnail_provider import VIDEO_EXTENSIONS
from bridge.watchlist_model import WatchlistModel
from core import folder_naming
from core.api_client import KemonoApiClient
from core.archive_manager import ArchiveManager
from core.archive_rebuild_journal import ArchiveRebuildJournal
from core.archive_rebuilder import ArchiveRebuilder, ArchiveRebuildOptions
from core.bandwidth_limiter import bandwidth_limiter
from core.downloader import (
    BatchBuildContext,
    DownloadTask,
    KemonoDownloader,
    is_permanent_failure,
    is_task_non_retryable,
)
from core.file_order import normalize_file_order, order_files
from core.filter_engine import (
    FILTER_PROFILES,
    REMOVE_WORDS_PROFILES,
    FilenameStyles,
    FilterEngine,
    FilterOptions,
    classify_settings_change,
)
from core.folder_naming import is_creator_folder, pick_creator_folder
from core.hardware_detector import HardwareDetector
from core.known_manager import KnownManager
from core.logger import logger
from core.parser import KemonoURLParser, URLParseResult, canonical_site_url, normalize_archive_url
from core.path_utils import (
    clean_subprocess_env,
    post_info_files,
    post_info_for_file,
    subprocess_env_kwargs,
    unique_name_in_batch,
)
from core.post_metadata_index import parse_post_info_content
from core.session_manager import SessionManager
from core.text_utils import clean_text, safe_file_name, sanitize_filesystem_name
from core.watchlist_manager import WatchlistManager
from services.batch_loader import BatchLoader
from services.link_extractor import LinkExtractor
from services.model_manager import MODEL_CATALOG, ModelManager
from services.telegram_service import TelegramService
from services.text_exporter import TextExporter

_FOLDER_PREVIEW_IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
    ".avif", ".apng", ".tif", ".tiff", ".jfif",
}


def _app_bridge_mod():
    import bridge.app_bridge as _ab
    return _ab



class DownloaderEventsMixin(AppBridgeSignalsMixin):
    @Slot(dict)
    def _handle_progress(self, info: Dict[str, Any]):
        if self.downloader._is_running and not self._is_downloading:
            self._is_downloading = True
            self.isDownloadingChanged.emit()

        completed = info.get("completed", 0)
        total     = info.get("total", 0)
        failed    = info.get("failed", 0)

        new_progress = info.get("percent", info.get("progress", 0))
        if self._overall_progress != new_progress:
            self._overall_progress = new_progress
            self.overallProgressChanged.emit()

        new_saved = info.get("saved_str", "0 MB")
        if self._saved_bytes_text != new_saved:
            self._saved_bytes_text = new_saved
            self.savedBytesTextChanged.emit()

        if self.downloader._pause_event.is_set():
            new_status = "Progress: Paused"
            new_speed = "0 KB/s"
            new_eta = "--"
        else:
            new_speed = info.get("speed_str", "0 KB/s")
            new_eta = info.get("eta_str", "--")
            new_status = info.get("status_text", f"Downloading\u2026 {completed}/{total}")

        if self._current_speed != new_speed:
            self._current_speed = new_speed
            self.currentSpeedChanged.emit()

        if self._eta_text != new_eta:
            self._eta_text = new_eta
            self.etaTextChanged.emit()

        if self._status_text != new_status:
            self._status_text = new_status
            self.statusTextChanged.emit()

        new_files_count = info.get("files_count_text") if info.get("files_count_text") else (f"{completed}/{total}" if total > 0 else "")
        if self._files_count_text != new_files_count:
            self._files_count_text = new_files_count
            self.filesCountTextChanged.emit()

        new_adaptive_state = info.get("adaptive_state", "optimal")
        if self._adaptive_state != new_adaptive_state:
            self._adaptive_state = new_adaptive_state
            self.adaptiveStateChanged.emit()

        new_adaptive_status = info.get("adaptive_status_text", "")
        if self._adaptive_status_text != new_adaptive_status:
            self._adaptive_status_text = new_adaptive_status
            self.adaptiveStatusTextChanged.emit()

        new_elapsed = info.get("elapsed_str", "0s")
        if self._elapsed_time_text != new_elapsed:
            self._elapsed_time_text = new_elapsed
            self.elapsedTimeTextChanged.emit()

        now_rg = time.monotonic()
        if now_rg - getattr(self, "_last_rate_guard_ui_emit", 0.0) >= 1.0:
            self._last_rate_guard_ui_emit = now_rg
            self.pawchiveRateGuardChanged.emit()

    @Slot(object)
    def _handle_task_status(self, task: DownloadTask):
        if self.downloader._is_running and not self._is_downloading:
            self._is_downloading = True
            self.isDownloadingChanged.emit()

        self._queue_model.updateTask(task)
        self._active_queue_model.updateTask(task)
        if task.status == "completed":
            self._invalidate_folder_stats(getattr(task, "target_path", ""))
            if self.recovery_manager and self.recovery_manager.retry_counts_cached()[0] > 0:
                if self.recovery_manager.remove_completed_tasks([task], async_write=True):
                    self._queue_model.failedCountChanged.emit()
        if task.status == "completed" and self._enable_download_archive:
            now = time.time()
            if now - self._last_archive_emit_time >= 2.0:
                self._last_archive_emit_time = now
                self.archiveRecordCountChanged.emit()
            self._dirty_archive_completed += 1
            creator_key = (
                str(getattr(task, "service", "") or "").lower(),
                str(getattr(task, "user_id", "") or getattr(task, "creator_name", "") or "").lower(),
            )
            is_new_creator = creator_key not in self._seen_session_archive_creators
            elapsed_full = now - self._last_archive_full_emit_time
            if (is_new_creator and elapsed_full >= 1.5) or elapsed_full >= 6.0:
                self._seen_session_archive_creators.add(creator_key)
                self._dirty_archive_completed = 0
                self._last_archive_full_emit_time = now
                self.archiveUpdated.emit()

    def _cleanup_after_run(self):
        """Memory cleanup after a download run, on the window thread (see MemoryCollector.collect)."""
        try:
            from core.memory_collector import MemoryCollector
            MemoryCollector.instance().collect(reason="download finished")
        except Exception:
            pass

    @Slot(list)
    def _handle_tasks_status(self, tasks: list):
        """Many files changed at once (a retry of thousands): the lists are updated a few hundred files
        per event-loop turn, so the window keeps answering meanwhile (all at once froze it for seconds)."""
        queue = self.__dict__.setdefault("_task_update_queue", [])
        queue.extend(tasks)
        if not getattr(self, "_task_updates_scheduled", False):
            self._task_updates_scheduled = True
            QTimer.singleShot(0, self._apply_task_updates)

    def _apply_task_updates(self):
        queue = self._task_update_queue
        batch, self._task_update_queue = queue[:self.TASK_UPDATES_PER_TURN], queue[self.TASK_UPDATES_PER_TURN:]
        for task in batch:
            self._handle_task_status(task)
        if self._task_update_queue:
            QTimer.singleShot(0, self._apply_task_updates)
        else:
            self._task_updates_scheduled = False

    def _invalidate_folder_stats(self, file_path: str):
        """Forget the Gallery's cached totals and previews for every folder above or under a changed path."""
        if not file_path:
            return
        if not self._folder_stats_cache and not self._folder_previews_cache:
            return
        cur = os.path.normpath(file_path)
        prefix = os.path.normcase(cur) + os.sep
        for cache in (self._folder_stats_cache, self._folder_previews_cache):
            stale = [k for k in list(cache.keys()) if os.path.normcase(k).startswith(prefix)]
            for k in stale:
                cache.pop(k, None)
        while cur:
            self._folder_stats_cache.pop(cur, None)
            self._folder_previews_cache.pop(cur, None)
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

    @Slot(str)
    def invalidateFolderCache(self, folder_path: str = ""):
        """Forget cached Gallery stats and previews (all, or folder_path and its subtree/ancestors)."""
        if not folder_path:
            self._folder_stats_cache.clear()
            self._folder_previews_cache.clear()
            return
        self._invalidate_folder_stats(os.path.normpath(os.path.abspath(folder_path)))

    @Slot(int)
    def _handle_throttled(self, new_count: int):
        if self._threads_count != new_count:
            old_count = self._threads_count
            self._threads_count = new_count
            self.threadsCountChanged.emit()
            if new_count < old_count:
                logger.info(f"Download threads lowered to {new_count} to avoid rate limiting.", category="system")
            elif new_count > old_count:
                logger.debug(f"Download threads raised to {new_count}.", category="system")

    @Slot(bool)
    def _handle_pause_changed(self, paused: bool):
        if paused:
            self._cloud_pause_event.set()
            self._status_text = "Progress: Paused"
            self._current_speed = "0 KB/s"
            self._eta_text = "--"
            self.currentSpeedChanged.emit()
            self.etaTextChanged.emit()
            self.statusTextChanged.emit()
            self.isPausedChanged.emit()
        else:
            self._cloud_pause_event.clear()
            if "Paused" in self._status_text:
                self._status_text = "Progress: Resumed"
                self.statusTextChanged.emit()
            self.isPausedChanged.emit()

    @Slot(list)
    def _handle_set_tasks(self, tasks: list):
        self._queue_model.setTasks(tasks)
        self._active_queue_model.setTasks(tasks)

    @Slot(list)
    def _handle_append_tasks(self, tasks: list):
        self._queue_model.appendTasks(tasks)
        self._active_queue_model.appendTasks(tasks)

    @Slot(object, list)
    def _handle_replace_batches(self, batch_ids, replacement_tasks: list):
        """Atomically splices rebuilt batch tasks into QueueModel and ActiveQueueModel on GUI thread."""
        target_bids = {str(b) for b in (batch_ids or ()) if b}
        self._queue_model.replace_batches(target_bids, replacement_tasks)
        if self._active_queue_model:
            self._active_queue_model.replace_batches(target_bids, replacement_tasks)
        self._is_downloading = bool(self.downloader._is_running)
        self.isDownloadingChanged.emit()
        self.isPausedChanged.emit()

    @Slot(str)
    def _handle_batch_cancel(self, batch_id: str):
        self.downloader.cancel_batch(batch_id)

    @Slot(str)
    def _handle_batch_pause(self, batch_id: str):
        if not batch_id:
            return
        paused_count = self.downloader.pause_batch(batch_id)
        logger.info(f"Paused batch '{batch_id}' ({paused_count} tasks paused).", category="downloader")

    def _set_ui_state(
        self,
        *,
        is_downloading=None,
        status_text=None,
        creator_name=None,
        has_error=None,
        last_error_message=None,
    ) -> None:
        """Safely update Qt backing fields & emit signals on the GUI thread."""
        from PySide6.QtCore import QThread

        def _apply():
            if is_downloading is not None:
                self._is_downloading = bool(is_downloading)
                self.isDownloadingChanged.emit()
            if status_text is not None:
                self._status_text = str(status_text)
                self.statusTextChanged.emit()
            if creator_name is not None:
                self._creator_name = str(creator_name)
                self.creatorNameChanged.emit()
            if has_error is not None:
                self._has_error = bool(has_error)
                self.hasErrorChanged.emit()
            if last_error_message is not None:
                self._last_error_message = str(last_error_message)
                self.lastErrorMessageChanged.emit()

        if QThread.currentThread() is self.thread():
            _apply()
        else:
            self._callOnGui.emit(_apply)

    @Slot(str)
    def _handle_batch_resume(self, batch_id: str):
        if not batch_id:
            return
        if not self.downloader.tasks and self._queue_model.tasks:
            self.downloader.tasks = self._queue_model.getTasks()
        options = self._get_filter_options()
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        resumed_count = self.downloader.resume_batch(batch_id, options=options, cookie_str=self._cookie_string)
        if resumed_count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
        elif resumed_count > 0:
            logger.info(f"Resumed batch '{batch_id}' ({resumed_count} tasks restored).", category="downloader")

    @Slot(str)
    def _handle_batch_retry(self, batch_id: str):
        if not self.downloader.tasks and self._queue_model.tasks:
            self.downloader.tasks = self._queue_model.getTasks()
        options = self._get_filter_options()
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        count = self.downloader.retry_batch_failed(batch_id, options=options, cookie_str=self._cookie_string)
        if count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._status_text = "Progress: Idle"
            self.statusTextChanged.emit()
        elif count > 0:
            logger.info(f"Retrying {count} tasks for batch '{batch_id}'...", category="downloader")

    @Slot(str)
    def _handle_batch_remove(self, batch_id: str):
        self.downloader.remove_batch(batch_id)
        # Discard batch from _queued_links
        if batch_id.startswith("artist_"):
            parts = batch_id.split("_", 2)
            if len(parts) == 3:
                self._queued_links.discard(f"artist:{parts[1].lower()}:{parts[2].lower()}")
        elif batch_id.startswith("post_"):
            parts = batch_id.split("_", 3)
            if len(parts) == 4:
                self._queued_links.discard(f"post:{parts[1].lower()}:{parts[2].lower()}:{parts[3].lower()}")

    @Slot()
    def _handle_queue_cleared(self):
        self.downloader.tasks.clear()
        self._queued_links.clear()
        self._apply_cancel_event.set()
        self._settings_apply_gen += 1
        self._scan_ui_gen += 1
        self._update_scan_progress("", 0, 0, force=True, active=False, update_status_text=False)
        self._seen_session_archive_creators.clear()
        self._dirty_archive_completed = 0
        self._settings_dismissed_baseline = None
        if self._has_pending_download_settings_changes:
            self._has_pending_download_settings_changes = False
            self._pending_settings_diff_summary = ""
            self.hasPendingDownloadSettingsChangesChanged.emit()
            self.pendingSettingsDiffSummaryChanged.emit()
        logger.info("Download queue cleared.", category="queue")

    def _execute_post_action(self):
        """Shows 15-second countdown modal — actual action runs only if user doesn't cancel."""
        action = getattr(self, "_post_download_action", "none")
        # Reset the setting immediately so it doesn't persist
        self.postDownloadAction = "none"
        if not action or action == "none":
            return

        # Human-readable labels for the modal
        _labels = {
            "close_app": "Close App",
            "shutdown":  "Shutdown",
            "restart":   "Restart",
            "sleep":     "Sleep",
            "hibernate": "Hibernate",
        }
        label = _labels.get(action, action.capitalize())
        self._pending_post_action = action

        # Generate comprehensive Desktop report before action executes (if enabled)
        if self._generate_desktop_report:
            try:
                from services.report_generator import generate_completion_report
                tasks = self._queue_model.getTasks() if self._queue_model else (self.downloader.tasks if self.downloader else [])
                report_paths = generate_completion_report(
                    tasks=tasks,
                    action_name=label,
                    elapsed_seconds=getattr(self.downloader, "_elapsed_seconds", 0.0) if self.downloader else 0.0
                )
                if report_paths.get("html"):
                    logger.info(f"📊 Download completion report saved to Desktop: {report_paths['html']}", category="system")
            except Exception as e:
                logger.warning(f"Could not generate desktop report: {e}", category="system")

        logger.info(f"Post-download action '{label}' queued — showing 15s countdown modal.", category="system")
        # Emit to QML — the modal handles the countdown and calls confirmPostAction() or cancelPostAction()
        self.postActionCountdownStarted.emit(label)

    @Slot()
    def cancelPostAction(self):
        """Called by QML when user clicks Cancel in the countdown modal. Clears the pending action."""
        logger.info(f"Post-download action '{self._pending_post_action}' cancelled by user.", category="system")
        self._pending_post_action = "none"

    @Slot()
    def confirmPostAction(self):
        """Called by QML when the countdown reaches 0. Runs the actual system action."""
        action = self._pending_post_action
        self._pending_post_action = "none"
        if not action or action == "none":
            return

        logger.info(f"Executing post-download action: {action}", category="system")
        try:
            if action == "close_app":
                logger.info("Closing application as requested after download.", category="system")
                app = QCoreApplication.instance() or QGuiApplication.instance()
                if app:
                    app.quit()
                else:
                    sys.exit(0)
            elif action in ("shutdown", "restart", "sleep", "hibernate"):
                for cmd in self._power_commands(action):
                    try:
                        # (sleep / hibernate return only after the computer wakes up again)
                        res = subprocess.run(cmd, check=False, capture_output=True, text=True,
                                             timeout=None if action in ("sleep", "hibernate") else 30,
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                             **subprocess_env_kwargs())
                    except (OSError, subprocess.SubprocessError) as e:
                        logger.debug(f"'{cmd[0]}' unavailable: {e}", category="system")
                        continue
                    if res.returncode == 0:
                        break
                    logger.debug(f"'{' '.join(cmd)}' failed ({res.returncode}): {(res.stderr or '').strip()[:200]}", category="system")
                else:
                    logger.error(f"Couldn't {action} the computer automatically (not allowed for this user?).", category="system")
        except Exception as e:
            logger.error(f"Failed to execute post-download action '{action}': {e}", category="system")

    @staticmethod
    def _power_commands(action: str) -> list:
        """Commands to try, in order, for a power action after downloads finish.

        Windows: no forced close of other apps (with a delay, "shutdown" force-closes them and
        unsaved work is lost); the app already showed its own countdown. Linux: systemctl works for
        a normal desktop user, "shutdown -h now" needs root and is only a fallback.
        """
        if sys.platform == "win32":
            return {
                "shutdown": [["shutdown", "/s", "/t", "0"]],
                "restart": [["shutdown", "/r", "/t", "0"]],
                "sleep": [["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]],
                "hibernate": [["shutdown", "/h"]],
            }.get(action, [])
        if sys.platform == "darwin":
            return {
                "shutdown": [["osascript", "-e", 'tell app "System Events" to shut down']],
                "restart": [["osascript", "-e", 'tell app "System Events" to restart']],
                "sleep": [["pmset", "sleepnow"]],
                "hibernate": [["pmset", "sleepnow"]],
            }.get(action, [])
        return {
            "shutdown": [["systemctl", "poweroff"], ["loginctl", "poweroff"], ["shutdown", "-h", "now"]],
            "restart": [["systemctl", "reboot"], ["loginctl", "reboot"], ["shutdown", "-r", "now"]],
            "sleep": [["systemctl", "suspend"], ["loginctl", "suspend"]],
            "hibernate": [["systemctl", "hibernate"], ["loginctl", "hibernate"]],
        }.get(action, [])

    @Slot(bool, str)
    def _handle_finished(self, success: bool, message: str):
        if self.downloader.is_running:
            logger.debug(f"Ignoring _handle_finished ('{message}') because downloader is actively running a new session.", category="downloader")
            return
        self._is_downloading = False
        self._active_queue_model.clear()
        self._scheduled_sweep_retry = False
        # Links that finished can be queued again (e.g. to fetch a creator's newer posts later)
        self._queued_links.clear()
        self._seen_session_archive_creators.clear()
        self._dirty_archive_completed = 0
        self._evaluate_pending_download_settings()
        self._apply_cancel_event.set()
        self._settings_apply_gen += 1
        self._scan_ui_gen += 1
        self._update_scan_progress("", 0, 0, force=True, active=False, update_status_text=False)
        self._settings_dismissed_baseline = None
        if self._has_pending_download_settings_changes:
            self._has_pending_download_settings_changes = False
            self._pending_settings_diff_summary = ""
            self.hasPendingDownloadSettingsChangesChanged.emit()
            self.pendingSettingsDiffSummaryChanged.emit()

        # Calculate actual completed percentage
        tasks = self._queue_model.getTasks()
        if tasks:
            completed_c = sum(1 for t in tasks if t.status == "completed")
            unimp_c = sum(1 for t in tasks if t.status == "failed" and is_task_non_retryable(t))
            retryable_failed_tasks = [
                t for t in tasks
                if t.status in ("failed", "cancelled") and not is_task_non_retryable(t)
            ]
            retryable_failed_c = len(retryable_failed_tasks)
            if self.recovery_manager:
                completed_tasks = [t for t in tasks if t.status == "completed"]
                if completed_tasks:
                    self.recovery_manager.remove_completed_tasks(completed_tasks, async_write=False)
                if retryable_failed_c > 0:
                    self.recovery_manager.dump_retries(retryable_failed_tasks, async_write=True)
                elif not self.recovery_manager.load_retries():
                    self.recovery_manager.clear_retries()
            self._overall_progress = int(completed_c / len(tasks) * 100)
            if retryable_failed_c > 0 and unimp_c > 0:
                self._status_text = f"Finished with {retryable_failed_c} error(s) and {unimp_c} not imported ({completed_c}/{len(tasks)} completed)"
            elif retryable_failed_c > 0:
                self._status_text = f"Finished with {retryable_failed_c} error(s) ({completed_c}/{len(tasks)} completed)"
            elif unimp_c > 0:
                self._status_text = f"Finished — {unimp_c} file(s) not imported on Pawchive ({completed_c}/{len(tasks)} completed)"
            else:
                self._overall_progress = 100
                self._status_text = f"Completed ({completed_c}/{len(tasks)} files)"
        else:
            self._overall_progress = 100 if success else self._overall_progress
            self._status_text = f"Progress: {message}"

        if self._queue_model:
            self._queue_model.failedCountChanged.emit()

        if self._enable_download_archive:
            self.archiveRecordCountChanged.emit()
            self.archiveUpdated.emit()

        self.isDownloadingChanged.emit()
        self.isPausedChanged.emit()
        self.overallProgressChanged.emit()
        self.statusTextChanged.emit()
        if not success:
            self._watchlist_pending_updates.clear()
            if message == "Download cancelled by user." or self._scan_cancel_event.is_set():
                self._has_error = False
                self._last_error_message = ""
                self._status_text = "Progress: Cancelled"
            else:
                self._has_error = True
                self._last_error_message = message
            self.hasErrorChanged.emit()
            self.lastErrorMessageChanged.emit()
        else:
            self.session_manager.discard_session()
            self._has_saved_session = False
            self.hasSavedSessionChanged.emit()
            
            # 1. Play sound if requested
            if self._play_completion_sound:
                try:
                    if sys.platform == "win32":
                        import winsound
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except Exception:
                    pass

            # 2. Open folder if requested
            if self._open_folder_on_complete and self._download_dir:
                try:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(self._download_dir))
                except Exception:
                    pass

            # 3. Post-download action (close app, shutdown, sleep, etc.)
            if self._post_download_action and self._post_download_action != "none":
                self._execute_post_action()
            elif self._generate_desktop_report:
                try:
                    from services.report_generator import generate_completion_report
                    tasks = self._queue_model.getTasks() if self._queue_model else (self.downloader.tasks if self.downloader else [])
                    report_paths = generate_completion_report(
                        tasks=tasks,
                        action_name="Completion",
                        elapsed_seconds=getattr(self.downloader, "_elapsed_seconds", 0.0) if self.downloader else 0.0
                    )
                    if report_paths.get("html"):
                        logger.info(f"📊 Download completion report saved to Desktop: {report_paths['html']}", category="system")
                except Exception as e:
                    logger.warning(f"Could not generate desktop report: {e}", category="system")

            # 4. Auto-add / update completed artist in watchlist. "Downloaded up to" only moves through
            # posts whose files all finished (completed or skipped by the filters).
            try:
                tasks_done = self._queue_model.getTasks()
                if tasks_done:
                    # Group tasks by (service, user_id or creator_name)
                    grouped = {}
                    for _t in tasks_done:
                        svc = getattr(_t, "service", "").strip().lower()
                        uid = (getattr(_t, "user_id", "") or getattr(_t, "creator_name", "")).strip().lower()
                        if svc and uid:
                            key = (svc, uid)
                            if key not in grouped:
                                grouped[key] = []
                            grouped[key].append(_t)

                    cutoffs = {}
                    for (svc, uid), c_tasks in grouped.items():
                        posts_state = {}
                        for _t in c_tasks:
                            pid = str(getattr(_t, "post_id", "") or "")
                            date = getattr(_t, "post_date", "") or ""
                            # A file that can never be downloaded (gone from the server, a private or
                            # removed video, out of retries) doesn't keep its post "new": such posts
                            # were offered again after every download, failing the same way (#28)
                            ok = (getattr(_t, "status", "") in ("completed", "skipped")
                                  or (getattr(_t, "status", "") == "failed" and is_permanent_failure(_t)))
                            prev = posts_state.get(pid)
                            posts_state[pid] = (date or (prev[0] if prev else ""), ok and (prev[1] if prev else True))
                        done_posts = [(d, p) for p, (d, ok) in posts_state.items() if ok]
                        open_posts = [(d, p) for p, (d, ok) in posts_state.items() if not ok]

                        if done_posts:
                            newest_done_date, newest_done_pid = max(done_posts, key=lambda dp: _app_bridge_mod()._post_order_key(dp[0], dp[1]))
                            done_day_ids = sorted({p for d, p in done_posts if d == newest_done_date and p})
                        else:
                            newest_done_date, newest_done_pid, done_day_ids = "", "", []

                        c_latest_pid, c_latest_date, c_day_ids = _app_bridge_mod().watchlist_cutoff(done_posts, open_posts)
                        eff_pid = c_latest_pid or newest_done_pid
                        eff_date = c_latest_date or newest_done_date
                        eff_day_ids = c_day_ids or done_day_ids

                        existing = self._watchlist_manager._find(uid, svc)
                        if not existing:
                            t0 = c_tasks[0]
                            existing = next((e for e in self._watchlist_manager.entries if e.service.lower() == svc and (e.creator_name.lower() == t0.creator_name.lower() or e.user_id.lower() == t0.creator_name.lower())), None)
                            if not existing:
                                t_uid = (getattr(t0, "user_id", "") or uid).strip()
                                t_svc = (getattr(t0, "service", "") or svc).strip()
                                is_external = getattr(t0, "is_ytdlp", False) or getattr(t0, "is_telegram", False) or t_svc.lower() in ("bunkr", "coomer_bunkr", "kemono_bunkr", "external")
                                if t_uid and t_svc and not is_external:
                                    t_name = getattr(t0, "creator_name", "").strip() or t_uid
                                    t_domain = getattr(t0, "domain", "") or ("coomer.st" if t_svc.lower() in ("onlyfans", "fansly", "candfans") else "pawchive.pw")
                                    t_url = normalize_archive_url(getattr(t0, "artist_url", "")) or canonical_site_url(t_domain, t_svc, t_uid)
                                    t_dir = self.extract_artist_folder_from_path(
                                        t0.target_path,
                                        t_name,
                                        t_svc,
                                        fallback_dir=self._download_dir
                                    )
                                    self._watchlist_manager.add_entry(
                                        url=t_url,
                                        creator_name=t_name,
                                        user_id=t_uid,
                                        service=t_svc,
                                        domain=t_domain,
                                        last_post_id=eff_pid,
                                        last_post_date=eff_date,
                                        download_dir=t_dir,
                                        options=self._get_filter_options().to_dict(),
                                    )
                                    existing = self._watchlist_manager._find(t_uid, t_svc)

                        if existing:
                            extra_done = self._watchlist_pending_updates.pop((existing.service.lower(), existing.user_id.lower()), None) or []
                            if extra_done:
                                done_posts += extra_done
                                newest_done_date, newest_done_pid = max(done_posts, key=lambda dp: _app_bridge_mod()._post_order_key(dp[0], dp[1]))
                                done_day_ids = sorted({p for d, p in done_posts if d == newest_done_date and p})
                                c_latest_pid, c_latest_date, c_day_ids = _app_bridge_mod().watchlist_cutoff(done_posts, open_posts)
                                eff_pid = c_latest_pid or newest_done_pid
                                eff_date = c_latest_date or newest_done_date
                                eff_day_ids = c_day_ids or done_day_ids

                        cutoffs[(svc, uid)] = (eff_pid, eff_date)

                        if existing:
                            if eff_date or eff_pid:
                                self._watchlist_manager.update_last_download(
                                    existing.user_id, existing.service,
                                    eff_pid, eff_date, day_ids=eff_day_ids
                                )
                            # Resolve completed posts from cached_new_posts so pending update badges update immediately
                            done_pids = [p for d, p in done_posts if p]
                            if done_pids:
                                self._watchlist_manager.resolve_posts(
                                    existing.user_id, existing.service,
                                    post_ids=done_pids,
                                    latest_post_id=eff_pid,
                                    latest_post_date=eff_date,
                                    day_ids=eff_day_ids
                                )
                            # ONLY assign download_dir if it was previously empty (protect manual changes!)
                            if not existing.download_dir:
                                t_dir = self.extract_artist_folder_from_path(
                                    c_tasks[0].target_path,
                                    existing.creator_name,
                                    existing.service,
                                    fallback_dir=self._download_dir
                                )
                                self._watchlist_manager.set_download_dir(existing.user_id, existing.service, t_dir)

                    self._watchlist_pending_updates.clear()
                    self._watchlist_model.update_new_counts()
                    self._watchlist_model.refresh()
                    self.watchlistChanged.emit()
            except Exception as e:
                self._watchlist_pending_updates.clear()
                logger.debug(f"Watchlist update error on finish: {e}", category="watchlist")

    def _async_resolve_creator_name(self, parsed: URLParseResult, for_url: str = ""):
        try:
            if parsed.is_external_provider:
                if parsed.provider == "bunkr":
                    album_title, _ = _app_bridge_mod().fetch_bunkr_album(parsed.raw_url, resolve_files=False)
                    if album_title:
                        self._creatorSignal.emit(for_url, clean_text(album_title))
                elif parsed.provider == "erome":
                    album_title, _ = _app_bridge_mod().fetch_erome_album(parsed.raw_url)
                    if album_title:
                        self._creatorSignal.emit(for_url, clean_text(album_title))
                elif parsed.provider == "nhentai":
                    gallery_title, _ = _app_bridge_mod().fetch_nhentai_gallery(parsed.post_id or parsed.raw_url)
                    if gallery_title:
                        self._creatorSignal.emit(for_url, clean_text(gallery_title))
                elif parsed.provider == "saint2":
                    self._creatorSignal.emit(for_url, clean_text(parsed.user_id))
            else:
                profile = self.api_client.fetch_creator_profile(parsed)
                name = profile.get("displayName") or profile.get("name") or profile.get("user") or profile.get("username") or parsed.user_id
                if name:
                    self._creatorSignal.emit(for_url, clean_text(str(name)))
        except Exception:
            pass

    @Slot(str, str)
    def _handle_creator_resolved(self, for_url: str, name: str):
        # Lookups finish in any order: a slow answer for an earlier link must not replace the name
        if for_url and for_url != (self._current_url or "").strip():
            return
        cleaned = clean_text(name)
        if cleaned and self._creator_name != cleaned:
            self._creator_name = cleaned
            self.creatorNameChanged.emit()
