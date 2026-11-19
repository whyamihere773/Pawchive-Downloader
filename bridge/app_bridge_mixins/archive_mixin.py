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



class ArchiveMixin(AppBridgeSignalsMixin):
    @Slot(str, str, str, str, result="QVariantList")
    def getArchiveHierarchy(self, query: str = "", service: str = "all", fileType: str = "all", sortBy: str = "creator_az"):
        return self.archive_manager.get_hierarchical_records(
            query=query,
            service=service,
            file_type=fileType,
            sort_by=sortBy
        )

    @Slot(result="QVariantMap")
    def getArchiveStatistics(self):
        return self.archive_manager.get_statistics()

    @Slot(str, str, str, str, str)
    def getArchiveDataAsync(self, request_id: str, query: str = "", service: str = "all",
                            fileType: str = "all", sortBy: str = "creator_az"):
        """The Archive view's creators and statistics, read in the background. Only one entry per
        creator: a creator's posts and files are read when it's opened (getArchiveCreatorPostsAsync).
        Sending every file of a big archive to the window on each refresh froze it (#28)."""
        # The creators go into archiveCreatorsModel (the view applies them with applyPending());
        # sending them all to the window as one list took seconds with tens of thousands of creators.
        # A newer request stops an older one that's still reading.
        gen = self.__dict__.get("_archive_data_gen", 0) + 1
        self._archive_data_gen = gen
        stale = lambda: self._archive_data_gen != gen  # noqa: E731

        def _job():
            try:
                creators = self.archive_manager.get_creator_summaries(
                    query=query, service=service, file_type=fileType, sort_by=sortBy, should_stop=stale)
                if creators is None or stale():
                    return                              # replaced by a newer request
                stats = self.archive_manager.get_statistics()
            except Exception as e:
                logger.error(f"Background task failed: {e}", category="system")
                creators, stats = [], {}

            def _deliver():
                if stale():
                    return
                self._archive_creators_model.set_pending(creators)
                self.asyncResultReady.emit(request_id, {"count": len(creators), "statistics": stats})
            try:
                self._callOnGui.emit(_deliver)
            except RuntimeError:
                pass      # the app is closing
        threading.Thread(target=_job, daemon=True, name=f"async:{request_id[:24]}").start()

    @Slot(str, str, str, str, str)
    def getArchiveCreatorPostsAsync(self, request_id: str, creatorKey: str, query: str = "",
                                    service: str = "all", fileType: str = "all"):
        """The posts and files of one creator in the Archive view (its "key" from getArchiveDataAsync)."""
        gen = self.__dict__.get("_archive_posts_gen", 0) + 1
        self._archive_posts_gen = gen
        stale = lambda: self._archive_posts_gen != gen  # noqa: E731

        def _job():
            res = self.archive_manager.get_creator_posts(
                creatorKey, query, service, fileType, should_stop=stale
            )
            if stale() or res is None:
                return None
            return res

        self._run_async(request_id, _job)

    @Slot(str, str, str)
    def exportArchiveFileAsync(self, request_id: str, filepath: str, exportFormat: str = "txt"):
        """Exports the archive in the background: the result is the number of records, -1 if it failed."""
        clean_path = filepath.replace("file:///", "").replace("file://", "")
        self._run_async(request_id, self.archive_manager.export_archive, clean_path, exportFormat)

    @Slot(result=str)
    def archiveLastError(self) -> str:
        """Why the last archive change failed (shown to the user)."""
        return self.archive_manager.last_error or ""

    def _on_archive_repaired(self, result: dict):
        """From the repair's thread: the window refreshes and says what happened."""
        try:
            self.archiveRepairFinished.emit(result)
            if result.get("ok"):
                self.archiveRecordCountChanged.emit()
                self.archiveUpdated.emit()
        except RuntimeError:
            pass      # the app is closing

    @Slot(int, result=bool)
    def deleteArchiveRecord(self, recordId: int) -> bool:
        ok = self.archive_manager.delete_record(recordId)
        if ok:
            self.archiveRecordCountChanged.emit()
            self.archiveUpdated.emit()
        return ok

    @Slot(str, str, result=int)
    def deleteArchivePost(self, service: str, postId: str) -> int:
        count = self.archive_manager.delete_by_post(service, postId)
        if count > 0:
            self.archiveRecordCountChanged.emit()
            self.archiveUpdated.emit()
        return count

    @Slot(str, str, result=int)
    def deleteArchiveCreator(self, creatorId: str, service: str = "") -> int:
        count = self.archive_manager.delete_by_creator(creatorId, service)
        if count > 0:
            self.archiveRecordCountChanged.emit()
            self.archiveUpdated.emit()
        return count

    @Slot(result=bool)
    def clearDownloadArchive(self) -> bool:
        success = self.archive_manager.clear_archive()
        self.archiveRecordCountChanged.emit()
        self.archiveUpdated.emit()
        return success

    @Slot(str, str, result=int)
    def exportArchiveFile(self, filepath: str, exportFormat: str = "txt") -> int:
        clean_path = filepath.replace("file:///", "").replace("file://", "")
        return self.archive_manager.export_archive(clean_path, exportFormat)

    @Slot(str, result=int)
    def importArchiveFile(self, filepath: str) -> int:
        clean_path = filepath.replace("file:///", "").replace("file://", "")
        count = self.archive_manager.import_archive(clean_path)
        if count > 0:
            self.archiveRecordCountChanged.emit()
            self.archiveUpdated.emit()
        return count

    @Slot(str, str, str)
    def verifyCreatorArchiveIntegrity(self, service: str, creatorId: str, creatorName: str = "") -> None:
        """Runs verify_creator_integrity in a background daemon thread."""
        def _worker():
            self.archiveCreatorVerificationStarted.emit(service, creatorId)
            candidates = []
            if self._download_dir:
                candidates.append(self._download_dir)
            try:
                from core.storage_pool_manager import storage_pool_manager
                if storage_pool_manager.enabled and storage_pool_manager.overflow_dirs:
                    candidates.extend(storage_pool_manager.overflow_dirs)
            except Exception:
                pass
            artist_dirs = []
            try:
                # The creator's Watchlist folders are scanned as they are, whatever their name
                for item in list(self._watchlist_manager.entries if self._watchlist_manager else []):
                    if str(item.user_id) == str(creatorId) and str(item.service).lower() == str(service).lower():
                        artist_dirs.extend(d for d in [item.download_dir, *(item.download_dirs or [])] if d)
            except Exception:
                pass

            last_prog_emit = [0.0]
            def _prog(cur, tot):
                now = time.time()
                if cur < tot and (now - last_prog_emit[0] < 0.1):
                    return
                last_prog_emit[0] = now
                self.archiveCreatorVerificationProgress.emit(service, creatorId, cur, tot)

            res = self.archive_manager.verify_creator_integrity(
                service=service,
                creator_id=creatorId,
                creator_name=creatorName,
                candidate_dirs=candidates,
                progress_callback=_prog,
                known_artist_dirs=artist_dirs
            )
            self.archiveCreatorVerificationFinished.emit(service, creatorId, res)
            self.archiveUpdated.emit()

        threading.Thread(target=_worker, daemon=True).start()

    @Slot(str, str, result=int)
    def removeMissingArchiveRecordsForCreator(self, service: str, creatorId: str) -> int:
        deleted = self.archive_manager.remove_missing_for_creator(service, creatorId)
        if deleted > 0:
            self.archiveRecordCountChanged.emit()
            self.archiveUpdated.emit()
        return deleted

    def _archive_change_async(self, request_id: str, fn, *args) -> None:
        def _job():
            try:
                result = fn(*args)
            except Exception as exc:
                self.archive_manager.last_error = str(exc)
                logger.error(f"Archive operation failed: {exc}", category="archive")
                return -1
            changed = (result is True) or (isinstance(result, int) and not isinstance(result, bool) and result > 0)
            if changed:
                self.archiveRecordCountChanged.emit()
                self.archiveUpdated.emit()
            return result
        self._run_async(request_id, _job)

    @Slot(str, int)
    def deleteArchiveRecordAsync(self, request_id: str, recordId: int):
        self._archive_change_async(request_id, self.archive_manager.delete_record, recordId)

    @Slot(str, str, str)
    def deleteArchivePostAsync(self, request_id: str, service: str, postId: str):
        self._archive_change_async(request_id, self.archive_manager.delete_by_post, service, postId)

    @Slot(str, str, str)
    def deleteArchiveCreatorAsync(self, request_id: str, creatorId: str, service: str = ""):
        def _guarded_delete():
            if self.downloader.has_active_tasks_for_creator(service, creatorId):
                self.archive_manager.last_error = (
                    "This creator is currently downloading — pause or cancel its active download before removing archive records."
                )
                logger.warning(self.archive_manager.last_error, category="archive")
                return -1
            return self.archive_manager.delete_by_creator(creatorId, service)
        self._archive_change_async(request_id, _guarded_delete)

    @Slot(str, str, str)
    def removeMissingArchiveRecordsForCreatorAsync(self, request_id: str, service: str, creatorId: str):
        self._archive_change_async(request_id, self.archive_manager.remove_missing_for_creator, service, creatorId)

    @Slot(str)
    def clearDownloadArchiveAsync(self, request_id: str):
        def _clear():
            if self.downloader.is_running or self.downloader.active_unfinished_batch_ids():
                self.archive_manager.last_error = (
                    "Downloads are currently active — pause or cancel active downloads before clearing the Archive database."
                )
                logger.warning(self.archive_manager.last_error, category="archive")
                return False
            ok = self.archive_manager.clear_archive()
            if ok:
                self.archiveRecordCountChanged.emit()
                self.archiveUpdated.emit()
            return ok
        self._run_async(request_id, _clear)

    @Slot(str, str)
    def importArchiveFileAsync(self, request_id: str, filepath: str):
        clean_path = filepath.replace("file:///", "").replace("file://", "")
        self._archive_change_async(request_id, self.archive_manager.import_archive, clean_path)

    @Property(bool, notify=AppBridgeSignalsMixin.archiveRebuildStatusChanged)
    def isArchiveRebuilding(self) -> bool:
        return self._is_archive_rebuilding

    @Property(bool, notify=AppBridgeSignalsMixin.archiveRebuildStatusChanged)
    def isArchiveRebuildPaused(self) -> bool:
        return self._is_archive_rebuild_paused

    @Property(bool, notify=AppBridgeSignalsMixin.archiveRebuildRecoveryChanged)
    def hasSavedArchiveRebuild(self) -> bool:
        return bool(getattr(self, "_has_saved_archive_rebuild", False))

    @Property("QVariantMap", notify=AppBridgeSignalsMixin.archiveRebuildRecoveryChanged)
    def archiveRebuildRecoverySummary(self) -> dict:
        return dict(getattr(self, "_archive_rebuild_recovery_summary", {}) or {})

    @Slot(result="QVariantList")
    def getSuggestedRebuildDirectories(self) -> list:
        """Returns candidate download folders across active settings, storage pools, and watchlist."""
        candidates = []
        if self._download_dir and os.path.isdir(self._download_dir):
            candidates.append(os.path.normpath(self._download_dir))
        try:
            from core.storage_pool_manager import storage_pool_manager
            if storage_pool_manager.enabled and storage_pool_manager.overflow_dirs:
                for d in storage_pool_manager.overflow_dirs:
                    if d and os.path.isdir(d):
                        candidates.append(os.path.normpath(d))
        except Exception:
            pass
        try:
            if self._watchlist_manager:
                for item in self._watchlist_manager.get_all():
                    df = getattr(item, "download_folder", None) or getattr(item, "folder_path", None)
                    if df and os.path.isdir(df):
                        candidates.append(os.path.normpath(df))
        except Exception:
            pass
        return list(dict.fromkeys(candidates))

    @Property(str, notify=AppBridgeSignalsMixin.browserLastDownloadDirChanged)
    def browserLastDownloadDir(self) -> str:
        return getattr(self, "_browser_last_download_dir", "") or ""

    @browserLastDownloadDir.setter
    def browserLastDownloadDir(self, val: str):
        clean = os.path.normpath(str(val or "").strip()) if str(val or "").strip() else ""
        if getattr(self, "_browser_last_download_dir", "") != clean:
            self._browser_last_download_dir = clean
            self.browserLastDownloadDirChanged.emit()
            self.saveSettings()

    @Slot(str, result=str)
    @Slot(result=str)
    def browseBrowserDownloadDir(self, initialDir: str = "") -> str:
        """Open native directory picker for Browser downloads starting at the last remembered Browser path."""
        start_dir = ""
        for cand in (initialDir, getattr(self, "_browser_last_download_dir", ""), self._download_dir, os.path.expanduser("~")):
            c = str(cand or "").strip()
            if c and os.path.isdir(c):
                start_dir = c
                break
        folder = _app_bridge_mod().QFileDialog.getExistingDirectory(None, "Select Browser Download Folder", start_dir)
        if not folder:
            return ""
        norm = os.path.normpath(folder)
        self.browserLastDownloadDir = norm
        return norm

    @Slot(str, str, result=str)
    @Slot(str, result=str)
    @Slot(result=str)
    def browseFolderDialog(self, title: str = "Select Directory", initialDir: str = "") -> str:
        """Open a native OS directory picker dialog and return the selected folder path."""
        start_dir = initialDir if (initialDir and os.path.isdir(initialDir)) else (self._download_dir or os.path.expanduser("~"))
        folder = _app_bridge_mod().QFileDialog.getExistingDirectory(None, title or "Select Directory", start_dir)
        return os.path.normpath(folder) if folder else ""

    def _launch_archive_rebuilder(
        self,
        directories: list,
        opts: ArchiveRebuildOptions,
        resume_state: Optional[dict] = None,
    ) -> bool:
        def _on_progress(data: dict):
            self._is_archive_rebuild_paused = data.get("is_paused", False)
            self.archiveRebuildProgress.emit(data)

        def _on_finished(stats: dict):
            self._is_archive_rebuilding = False
            self._is_archive_rebuild_paused = False
            self._archive_rebuilder = None
            self._has_saved_archive_rebuild = self.archive_rebuild_journal.has_unfinished_session()
            self._archive_rebuild_recovery_summary = (
                self.archive_rebuild_journal.get_summary() if self._has_saved_archive_rebuild else {}
            )
            self.archiveRecordCountChanged.emit()
            self.archiveUpdated.emit()
            self.archiveRebuildRecoveryChanged.emit()
            self.archiveRebuildStatusChanged.emit()
            self.archiveRebuildFinished.emit(stats)

        self._archive_rebuilder = ArchiveRebuilder(
            archive_manager=self.archive_manager,
            directories=directories,
            options=opts,
            on_progress=_on_progress,
            on_finished=_on_finished,
            journal=self.archive_rebuild_journal,
            resume_state=resume_state,
        )

        started = self._archive_rebuilder.start()
        if started:
            self._is_archive_rebuilding = True
            self._is_archive_rebuild_paused = False
            self._has_saved_archive_rebuild = False
            self._archive_rebuild_recovery_summary = {}
            self.archiveRebuildRecoveryChanged.emit()
            self.archiveRebuildStatusChanged.emit()
        return started

    @Slot("QVariantList", str, bool, bool, result=bool)
    @Slot(list, str, bool, bool, result=bool)
    @Slot("QVariantList", result=bool)
    @Slot(list, result=bool)
    def startArchiveRebuild(
        self,
        directories: list,
        hashMode: str = "full",
        detectPostInfo: bool = True,
        skipExisting: bool = True
    ) -> bool:
        """
        Asynchronously scans and rebuilds the archive database from multiple directories.
        Completely non-blocking to the Qt main thread with live telemetry streaming and
        crash-proof SQLite WAL checkpointing.
        """
        if self._is_archive_rebuilding:
            return False

        valid_dirs = [os.path.normpath(d) for d in directories if d and os.path.isdir(d)]
        if not valid_dirs:
            return False

        opts = ArchiveRebuildOptions(
            hash_mode=hashMode,
            detect_post_info=detectPostInfo,
            skip_existing=skipExisting
        )
        return self._launch_archive_rebuilder(valid_dirs, opts, resume_state=None)

    @Slot(result=bool)
    def resumeSavedArchiveRebuild(self) -> bool:
        """Resumes an interrupted Archive Rebuild directly from its SQLite WAL checkpoint."""
        if self._is_archive_rebuilding:
            return False
        summary = self.archive_rebuild_journal.get_summary()
        if not summary:
            self._has_saved_archive_rebuild = False
            self._archive_rebuild_recovery_summary = {}
            self.archiveRebuildRecoveryChanged.emit()
            return False

        dirs = [os.path.normpath(d) for d in (summary.get("directories") or []) if d and os.path.isdir(d)]
        raw_opts = summary.get("options") or {}
        opts = ArchiveRebuildOptions(
            hash_mode=str(raw_opts.get("hash_mode", "full")),
            detect_post_info=bool(raw_opts.get("detect_post_info", True)),
            skip_existing=bool(raw_opts.get("skip_existing", True)),
            exclude_temp=bool(raw_opts.get("exclude_temp", True)),
        )
        if not dirs and summary.get("status") == "discovering":
            self.discardSavedArchiveRebuild()
            return False
        return self._launch_archive_rebuilder(dirs, opts, resume_state=summary)

    @Slot()
    def discardSavedArchiveRebuild(self) -> None:
        """Clears the saved Archive Rebuild checkpoint without resuming."""
        self.archive_rebuild_journal.clear()
        self._has_saved_archive_rebuild = False
        self._archive_rebuild_recovery_summary = {}
        self.archiveRebuildRecoveryChanged.emit()

    @Slot()
    def pauseArchiveRebuild(self) -> None:
        if self._archive_rebuilder and self._archive_rebuilder.is_running:
            self._archive_rebuilder.pause()
            self._is_archive_rebuild_paused = True
            self.archiveRebuildStatusChanged.emit()

    @Slot()
    def resumeArchiveRebuild(self) -> None:
        if self._archive_rebuilder and self._archive_rebuilder.is_running:
            self._archive_rebuilder.resume()
            self._is_archive_rebuild_paused = False
            self.archiveRebuildStatusChanged.emit()

    @Slot()
    def cancelArchiveRebuild(self) -> None:
        if self._archive_rebuilder and self._archive_rebuilder.is_running:
            self._archive_rebuilder.cancel()

    @Slot(str, result=bool)
    def revealFileInExplorer(self, filePath: str) -> bool:
        """Reveals file or directory in Windows File Explorer / OS file manager."""
        if not filePath:
            return False
        clean_path = os.path.normpath(filePath.replace("file:///", "").replace("file://", ""))
        if not os.path.exists(clean_path):
            d = os.path.dirname(clean_path)
            if os.path.exists(d):
                clean_path = d
            else:
                return False
        try:
            import subprocess
            if os.name == 'nt':
                if os.path.isfile(clean_path):
                    subprocess.Popen(f'explorer /select,"{clean_path}"')
                else:
                    subprocess.Popen(f'explorer "{clean_path}"')
                return True
            else:
                import sys
                if sys.platform == 'darwin':
                    subprocess.Popen(["open", "-R" if os.path.isfile(clean_path) else "", clean_path], **subprocess_env_kwargs())
                else:
                    subprocess.Popen(["xdg-open", os.path.dirname(clean_path) if os.path.isfile(clean_path) else clean_path], **subprocess_env_kwargs())
                return True
        except Exception as e:
            logger.error(f"Failed to reveal file {filePath}: {e}", category="archive")
            return False
