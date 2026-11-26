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



class RecoveryRetryMixin(AppBridgeSignalsMixin):
    @Slot()
    def checkRecoverySession(self):
        """Called by QML on completion to prompt for unfinished crash recovery if detected."""
        if self._has_recovery_session and self._recovery_summary:
            self.recoverySessionDetected.emit(self._recovery_summary)

    def _load_recovery_tasks(self, checkpoint: Optional[dict] = None) -> List[DownloadTask]:
        """The files of the crash-recovery journal, checked against what's on disk."""
        checkpoint = checkpoint or self.recovery_manager.load_checkpoint() or {}
        loaded_tasks: List[DownloadTask] = []
        for t_dict in checkpoint.get("tasks", []) or []:
            try:
                task = DownloadTask.from_dict(t_dict)
            except Exception:
                continue
            self._verify_task_on_disk(task)
            loaded_tasks.append(task)
        return loaded_tasks

    @Slot()
    def resumeRecoverySession(self):
        """
        Restores the interrupted download session from the crash-proof journal.
        Verifies already downloaded files on disk, updates the queue model,
        and seamlessly resumes downloading the remaining files.
        """
        # Reading the journal, rebuilding the files and checking which are already on disk run in the
        # background (seconds for big queues); the queue is filled and started on the window thread
        if getattr(self, "_resuming", False):
            return
        self._resuming = True
        self._status_text = "Reading the interrupted download…"
        self.statusTextChanged.emit()

        def _read():
            try:
                checkpoint = self.recovery_manager.load_checkpoint()
                loaded = self._load_recovery_tasks(checkpoint) if checkpoint else []
            except Exception:
                logger.exception("Couldn't read the interrupted download", category="session")
                checkpoint, loaded = None, []
            self._callOnGui.emit(lambda: self._finish_resume(checkpoint, loaded))
        threading.Thread(target=_read, name="ResumeRead", daemon=True).start()

    def _finish_resume(self, checkpoint, loaded_tasks):
        self._resuming = False
        if not checkpoint:
            logger.warning("No recovery checkpoint found to resume.", category="session")
            return
        if not loaded_tasks:
            logger.warning("Recovery checkpoint contains no tasks.", category="session")
            return

        # Populate models
        self._queue_model.setTasks(loaded_tasks)
        self._active_queue_model.setTasks(loaded_tasks)
        self.downloader.tasks = list(loaded_tasks)

        batches = checkpoint.get("batches", [])
        if batches:
            self._queue_model.groups = batches

        options = self._get_filter_options()

        self._has_recovery_session = False
        self._has_saved_session = False
        self.hasRecoverySessionChanged.emit()
        self.hasSavedSessionChanged.emit()

        self._scan_cancel_event.clear()
        self._has_error = False
        self.hasErrorChanged.emit()
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self.isPausedChanged.emit()
        self._status_text = "Resuming recovered download session..."
        self.statusTextChanged.emit()

        self.downloader.start_download_queue(
            tasks=self.downloader.tasks,
            options=options,
            cookie_str=self._cookie_string
        )
        logger.success(
            f"Resumed {len(loaded_tasks)} tasks from recovery session.",
            category="session"
        )

    @Slot()
    def discardRecoverySession(self):
        """Discards the saved recovery journal."""
        self.recovery_manager.discard_recovery()
        self._has_recovery_session = False
        self._recovery_summary = {}
        self.hasRecoverySessionChanged.emit()
        logger.info("Recovery session discarded.", category="session")

    @Slot()
    def restoreDownload(self):
        if self._has_recovery_session:
            self.resumeRecoverySession()
            return
        saved = self.session_manager.get_saved_session()
        if not saved:
            logger.warning("No saved download session found.", category="session")
            return

        logger.info(f"Restoring session for {saved.get('creator')} ({saved.get('url')})...", category="session")
        self._current_url = saved.get("url", self._current_url)
        self.currentUrlChanged.emit()
        self.startDownload()

    @Slot()
    def discardSession(self):
        # Discard cancels active download automatically as requested
        if self._is_downloading:
            self.cancelDownload()
        self._queue_model.clear()
        self._active_queue_model.clear()
        self.session_manager.discard_session()
        self.recovery_manager.discard_recovery()
        self._has_saved_session = False
        self._has_recovery_session = False
        self._recovery_summary = {}
        self.hasSavedSessionChanged.emit()
        self.hasRecoverySessionChanged.emit()
        logger.info("Active download stopped and session discarded.", category="session")

    @Slot()
    def onAppClosing(self):
        """Called when user closes the window — preserves active session and stops threads cleanly.

        Runs once (the window's close and the app's aboutToQuit both call it). Downloads are
        stopped first, then the session is saved on a helper thread: on a slow drive that save can
        take many seconds, and doing it on the window thread froze the window instead of closing it.
        """
        if getattr(self, "_closing_handled", False):
            return
        self._closing_handled = True

        # Settings or a cookie changed just before closing are still waiting for their delayed save
        try:
            if self._settings_save_timer.isActive():
                self._settings_save_timer.stop()
                self.saveSettings()
            if self._cookie_save_timer.isActive():
                self._cookie_save_timer.stop()
                self._persist_cookie()
            gov = getattr(self, "pawchive_governor", None)
            if gov is not None and hasattr(gov, "flush_to_disk"):
                gov.flush_to_disk()
        except Exception as e:
            logger.debug(f"Couldn't save settings while closing: {e}", category="system")

        was_downloading = self._is_downloading
        # The queue is kept whenever it has unfinished files, also when nothing was downloading
        # (files added with "Add to queue" but not started yet used to be lost on exit)
        queued = list(self._queue_model.tasks) if self._queue_model.tasks else list(self.downloader.tasks or [])
        has_unfinished = any(t.status in ("pending", "downloading", "retrying") for t in queued)
        tasks = queued if (was_downloading or has_unfinished) else []
        batches = list(self._queue_model.groups) if tasks else None
        settings = vars(self._get_filter_options()) if tasks else None
        all_tasks = self._queue_model.getTasks() if self._queue_model else (self.downloader.tasks if self.downloader else [])
        failed_or_cancelled = [
            t for t in all_tasks
            if t.status in ("failed", "cancelled") and not is_task_non_retryable(t)
        ]

        if was_downloading:
            logger.info("Application closing: stopping downloads and saving the session...", category="system")
            self.downloader.cancel()
        self._scan_cancel_event.set()
        self._apply_cancel_event.set()
        self._settings_apply_gen += 1
        self._scan_ui_gen += 1
        checker = self._watchlist_checker
        if checker is not None:
            checker.cancel()        # continues where it stopped at the next check
        move_cancel = getattr(self, "_folder_move_cancel", None)
        if move_cancel is not None:
            move_cancel.set()      # stops after the file it's moving; the archive keeps what moved
            mover = getattr(self, "_folder_move_thread", None)
            if mover is not None:
                mover.join(timeout=10)

        rebuilder = getattr(self, "_archive_rebuilder", None)
        if rebuilder is not None and rebuilder.is_running:
            rebuilder.stop_and_preserve(timeout=3.5)

        def _persist():
            try:
                from core.statistics_manager import statistics_manager
                statistics_manager.set_download_active(False)
                statistics_manager.flush()
            except Exception:
                pass
            try:
                self.session_manager.flush_history()
            except Exception:
                pass
            try:
                self.archive_manager.checkpoint()
            except Exception:
                pass
            try:
                self._watchlist_manager.flush()
            except Exception:
                pass
            try:
                if tasks:
                    self.recovery_manager.save_checkpoint(tasks=tasks, batches=batches, settings=settings,
                                                          status="paused" if was_downloading else "interrupted")
                if failed_or_cancelled and self.recovery_manager:
                    self.recovery_manager.dump_retries(failed_or_cancelled, async_write=False)
            except Exception as e:
                logger.warning(f"Couldn't save the session while closing: {e}", category="system")

        try:
            from core.power import sleep_inhibitor
            sleep_inhibitor.set_active(False)
        except Exception:
            pass

        # History is always written; the queue / retries when there are any
        saver = threading.Thread(target=_persist, name="SaveOnClose")   # not daemon: allowed to finish
        saver.start()
        saver.join(timeout=4.0)
        if saver.is_alive():
            logger.info("Still saving the session in the background (slow drive)…", category="system")

    def _has_failed_tasks(self) -> bool:
        """True if any retryable task actually failed. Cancelled and unimported Pawchive placeholders don't count."""
        tasks = self.downloader.tasks or (self._queue_model.tasks if self._queue_model else [])
        if any(t.status == "failed" and not is_task_non_retryable(t) for t in tasks):
            return True
        try:
            spilled = self.recovery_manager.load_retries() or []
        except Exception:
            spilled = []
        return any(
            (d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) == "failed"
            and not is_task_non_retryable(d)
            for d in spilled
        )

    @Slot()
    def retryFailed(self):
        """Retries all failed and cancelled tasks in the queue (the manual Retry Failed button)."""
        self._retry_failed(include_cancelled=True)

    def _retry_failed(self, include_cancelled: bool = True):
        """Shared retry logic. Automatic retries pass include_cancelled=False."""
        self._start_retry(None, include_cancelled)

    @Slot("QVariantList")
    def retrySelectedTasks(self, selected_ids: list):
        """Retries only selected failed tasks (strictly excluding non-retryable unimported files)."""
        ids = [str(i) for i in (selected_ids or []) if i]
        if ids:
            queue_tasks = self._queue_model.getTasks() if self._queue_model else []
            all_known = queue_tasks or self.downloader.tasks
            key = KemonoDownloader.task_key
            non_retryable_keys = set()
            blocked_404_keys = set()
            for t in all_known:
                k = key(t)
                if is_task_non_retryable(t):
                    non_retryable_keys.add(k)
                    if getattr(t, "file_id", ""):
                        non_retryable_keys.add(str(t.file_id))
                    continue
                if self._skip_retry_404:
                    is_404 = "404" in str(getattr(t, "error_msg", "")).lower() or getattr(t, "http_status", 0) == 404
                    if is_404:
                        blocked_404_keys.add(k)
            ids = [i for i in ids if i not in non_retryable_keys and i not in blocked_404_keys]
        if not ids:
            return
        self._start_retry(ids, True)

    @Slot(str)
    def retrySingleTask(self, file_id: str):
        """Retries only a single specific failed task (blocked for unimported Pawchive files)."""
        if not file_id:
            return
        all_known = (self._queue_model.getTasks() if self._queue_model else []) or self.downloader.tasks
        for t in all_known:
            if (getattr(t, "file_id", "") == file_id or KemonoDownloader.task_key(t) == file_id) and is_task_non_retryable(t):
                return
        self._start_retry([file_id], True)

    def _start_retry(self, selected: Optional[list], include_cancelled: bool):
        """Gets failed files ready for a retry (selected: their names in the Retry Failed list; None:
        all). Reading the failed files saved on disk, rebuilding them and matching them against the
        queue run in the background: on the window thread they froze it for seconds with thousands of
        files. The retry itself starts back on the window thread."""
        if selected is not None and not selected:
            return
        if getattr(self, "_retry_preparing", False):
            return                            # a retry is already being prepared
        self._retry_preparing = True
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self._status_text = "Preparing the retry…"
        self.statusTextChanged.emit()
        queue_tasks = self._queue_model.getTasks() if self._queue_model.tasks else []
        current = self.downloader.tasks

        def _prepare():
            restored = []
            base = current
            try:
                if (not base or len(base) < len(queue_tasks)) and queue_tasks:
                    base = queue_tasks
                key = KemonoDownloader.task_key
                if selected is None:
                    need_saved = not any(
                        t.status in ("failed", "cancelled") and not is_task_non_retryable(t)
                        for t in base
                    )
                else:
                    have = {key(t) for t in base}
                    wanted = set(selected)
                    need_saved = bool(wanted - have)
                if need_saved:
                    spilled = self.recovery_manager.load_retries()
                    if spilled:
                        from core.downloader import DownloadTask
                        restored = [DownloadTask.from_dict(d) if isinstance(d, dict) else d for d in spilled]
                        if selected is not None:
                            restored = [t for t in restored if key(t) not in have and key(t) in wanted]
            except Exception as e:
                logger.error(f"Couldn't prepare the retry: {e}", category="downloader")
            self._callOnGui.emit(lambda: self._finish_retry(base, restored, selected, include_cancelled))
        threading.Thread(target=_prepare, name="RetryPrepare", daemon=True).start()

    def _finish_retry(self, base: list, restored: list, selected: Optional[list], include_cancelled: bool):
        self._retry_preparing = False
        if base is not self.downloader.tasks:
            self.downloader.tasks = base
        if restored:
            self.downloader.tasks.extend(restored)
            if self._queue_model:
                self._queue_model.addTasks(restored)
        options = self._get_filter_options()
        if selected is None:
            count = self.downloader.retry_failed_tasks(options, self._cookie_string, include_cancelled=include_cancelled)
        else:
            count = self.downloader.retry_selected_tasks(selected, options, self._cookie_string)
        if count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._status_text = "Progress: Idle (no failed tasks)" if selected is None else "Progress: Idle (no selected tasks to retry)"
            self.statusTextChanged.emit()
        elif count > 0:
            logger.info(f"Retrying {count} {'failed' if selected is None else 'selected'} task(s) with "
                        f"{self._threads_count} worker threads...", category="downloader")

    @Slot()
    @Slot("QVariantList")
    def clearFailedTasks(self, selected_ids: Optional[list] = None):
        """Removes failed and cancelled tasks from both queue models, downloader, and disk.

        The failed files saved on disk are updated first (and not in the background): the Retry
        Failed button counts them when the queue has none, so updating the queue first made it
        recount while the old file was still there and keep showing "Retry Failed (1)" (#28).
        Cleared files are also taken out of the crash journal, and a save of the failed files still
        waiting in the background is dropped: either brought them back after a restart."""
        s_set = set(selected_ids) if selected_ids else None

        def cleared(t) -> bool:
            if t.status not in ("failed", "cancelled"):
                return False
            return s_set is None or t.file_id in s_set or t.url in s_set or t.filename in s_set

        queue_tasks = self._queue_model.getTasks() if self._queue_model else []
        gone = {id(t): t for t in queue_tasks if cleared(t)}
        if self.downloader:
            gone.update((id(t), t) for t in self.downloader.tasks if cleared(t))
        # What the Retry Failed list holds after this: the queue's retryable failed files, else the saved ones
        left_in_queue = [
            t for t in queue_tasks
            if t.status in ("failed", "cancelled") and id(t) not in gone and not is_task_non_retryable(t)
        ]

        if self.recovery_manager:
            if left_in_queue:
                self.recovery_manager.dump_retries(left_in_queue, async_write=True)
            elif s_set:
                spilled = self.recovery_manager.load_retries()
                remaining = [
                    item for item in spilled
                    if not ((item.get("file_id") if isinstance(item, dict) else getattr(item, "file_id", "")) in s_set
                            or (item.get("url") if isinstance(item, dict) else getattr(item, "url", "")) in s_set
                            or (item.get("filename") if isinstance(item, dict) else getattr(item, "filename", "")) in s_set)
                ]
                if remaining:
                    self.recovery_manager.dump_retries(remaining, async_write=False)
                else:
                    self.recovery_manager.clear_retries()
            else:
                self.recovery_manager.clear_retries()
            if gone:
                self.recovery_manager.forget_tasks(list(gone.values()))
        if self.downloader:
            self.downloader.tasks = [t for t in self.downloader.tasks if not cleared(t)]
        if self._queue_model:
            self._queue_model.clearFailedTasks(selected_ids)
        if self._active_queue_model:
            self._active_queue_model.clearFailedTasks(selected_ids)
        logger.info("Cleared failed tasks from queue.", category="queue")

    @staticmethod
    def _verify_task_on_disk(task) -> None:
        """Marks a restored file finished when it's already saved (downloads are written to
        "<name>.part" first, so a file under its real name is complete)."""
        if os.path.exists(task.target_path) and os.path.getsize(task.target_path) > 0:
            actual_sz = os.path.getsize(task.target_path)
            if task.file_size <= 0 or actual_sz >= task.file_size:
                task.status = "completed"
                task.downloaded_bytes = actual_sz
                task.progress_pct = 100
                return
            task.status = "pending"
        elif task.status in ("downloading", "retrying"):
            task.status = "pending"
