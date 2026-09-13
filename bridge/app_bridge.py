"""
Application Bridge Subsystem
Binds the PySide6/Qt Core engine with the QML User Interface, providing
reactive properties, slots, session persistence, telemetry signals, and async orchestration.
"""

import os
import sys
import time
import subprocess
import threading
import json
from typing import Optional, Dict, Any, List
from PySide6.QtCore import QObject, Signal, Property, Slot, Qt, QUrl, QCoreApplication
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog, QApplication

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger
from core.parser import KemonoURLParser, URLParseResult
from core.filter_engine import FilterEngine, FilterOptions
from core.api_client import KemonoApiClient
from core.downloader import KemonoDownloader, DownloadTask
from core.session_manager import SessionManager
from core.known_manager import KnownManager
from bridge.log_model import LogModel
from bridge.queue_model import QueueModel
from bridge.known_model import KnownModel
from bridge.watchlist_model import WatchlistModel
from bridge.decompressor_bridge import DecompressorBridge
from core.watchlist_manager import WatchlistManager
from services.batch_loader import BatchLoader
from services.link_extractor import LinkExtractor
from services.text_exporter import TextExporter
from services.bunkr_client import fetch_bunkr_album
from services.erome_client import fetch_erome_album
from services.nhentai_client import fetch_nhentai_gallery
from services.cloud_downloader import (
    download_mega_link,
    download_gdrive_link,
    download_dropbox_link,
    download_gofile_link
)
from core.text_utils import clean_text, sanitize_filesystem_name


class AppBridge(QObject):
    # Signals for properties
    currentUrlChanged = Signal()
    pageStartChanged = Signal()
    pageEndChanged = Signal()
    downloadDirChanged = Signal()
    filterCharactersChanged = Signal()
    characterScopeChanged = Signal()
    skipWordsChanged = Signal()
    skipScopeChanged = Signal()
    removeWordsChanged = Signal()
    filterTypeChanged = Signal()
    skipArchivesChanged = Signal()
    downloadThumbnailsOnlyChanged = Signal()
    scanContentImagesChanged = Signal()
    compressWebpChanged = Signal()
    keepDuplicatesChanged = Signal()
    favoriteModeChanged = Signal()
    subfolderPerPostChanged = Signal()
    datePrefixChanged = Signal()
    fileIndexPrefixChanged = Signal()
    separateFoldersByKnownChanged = Signal()
    downloadRevisionsChanged = Signal()
    adaptiveThreadingChanged = Signal()
    autoRetryAtEndChanged = Signal()
    mangaModeChanged = Signal()
    filenameStyleChanged = Signal()
    proxyUrlChanged = Signal()
    threadsCountChanged = Signal()
    threadsLockedChanged = Signal()
    maxCpuThreadsChanged = Signal()
    cookieStringChanged = Signal()
    userAgentChanged = Signal()
    isDownloadingChanged = Signal()
    isPausedChanged = Signal()
    statusTextChanged = Signal()
    overallProgressChanged = Signal()
    currentSpeedChanged = Signal()
    etaTextChanged = Signal()
    savedBytesTextChanged = Signal()
    hasSavedSessionChanged = Signal()
    hasErrorChanged = Signal()
    lastErrorMessageChanged = Signal()
    creatorNameChanged = Signal()
    downloadHistoryChanged = Signal()
    adaptiveStatusTextChanged = Signal()
    adaptiveStateChanged = Signal()
    elapsedTimeTextChanged = Signal()
    downloadDelayChanged = Signal()
    savePostMetadataChanged = Signal()
    downloadEmbedsChanged = Signal()
    openFolderOnCompleteChanged = Signal()
    playCompletionSoundChanged = Signal()
    generateDesktopReportChanged = Signal()
    saveDesktopReportChanged = Signal()
    filesCountTextChanged = Signal()
    harvestedLinksChanged = Signal()
    consoleWidthChanged = Signal()
    postDownloadActionChanged = Signal()
    knownRecognitionModeChanged = Signal()
    languageChanged = Signal()
    postActionCountdownStarted = Signal(str)  # carries human label e.g. "Shutdown"
    exportCompleted = Signal(str, bool)       # (filePath, wasDownloading)
    importCompleted = Signal(int, int)        # (taskCount, creatorCount)
    exportFailed = Signal(str)
    importFailed = Signal(str)
    hasRecoverySessionChanged = Signal()
    recoverySessionDetected   = Signal('QVariant')

    tagFolderModeChanged      = Signal()
    watchlistChanged          = Signal()
    watchlistCheckStarted     = Signal()
    watchlistCheckFinished    = Signal(int)  # total new posts found
    watchlistArtistChecking   = Signal(str, str, bool) # (userId, service, isChecking)
    watchlistArtistChecked    = Signal(str, str, int)  # (userId, service, newPostCount)

    # Link Vault signals
    linkVaultChanged          = Signal()
    linkVaultProbingStarted   = Signal()
    linkVaultProbingFinished  = Signal()
    vaultHarvestStarted       = Signal(str)             # (creatorName)
    vaultHarvestProgress      = Signal(str, int, int)   # (statusMsg, currentPage, currentLinks)
    vaultHarvestFinished      = Signal(bool, str, int, int)  # (success, creatorName, newLinks, totalPosts)


    # Storage Pool signals
    storagePoolChanged        = Signal()

    # Cookie Watchdog signals
    cookieWatchdogChanged     = Signal()
    cookieImportCompleted     = Signal(bool, str)

    # Task Scheduler signals
    schedulerChanged          = Signal()

    _progressSignal    = Signal(dict)    # carries progress info dict
    _taskSignal        = Signal(object)  # carries a DownloadTask object
    _finishedSignal    = Signal(bool, str)
    _throttledSignal   = Signal(int)     # carries new worker concurrency count
    _pauseSignal       = Signal(bool)    # carries pause state (True=paused, False=resumed)
    _creatorSignal     = Signal(str)     # carries resolved creator name
    _setTasksSignal    = Signal(list)    # safely sends new task list to GUI thread
    _appendTasksSignal = Signal(list)    # safely appends new tasks to GUI thread queue
    _watchlistResultSignal = Signal(list)  # carries per-entry new-post lists
    _watchlistArtistResultSignal = Signal(str, str, int)  # (userId, service, newCount)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Core systems
        self.known_manager = KnownManager()
        self.session_manager = SessionManager()
        self.downloader = KemonoDownloader(
            known_manager=self.known_manager,
            session_manager=self.session_manager,
            max_workers=4
        )
        self.api_client = KemonoApiClient()

        # Models
        self._log_model = LogModel(self)
        self._queue_model = QueueModel(self)
        self._active_queue_model = QueueModel(self)
        self._active_queue_model.filterStatus = "downloading"
        self._active_queue_model.minFileSize = 50 * 1024 * 1024  # 50 MB threshold
        self._known_model = KnownModel(self.known_manager, self)

        # Settings defaults
        saved_settings = self.session_manager.load_settings()
        self._current_url = ""
        self._page_start = int(saved_settings.get("page_start", 1))
        self._page_end = int(saved_settings.get("page_end", 999))
        self._download_dir = saved_settings.get("download_dir", os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads"))
        self._filter_characters = ""
        self._character_scope = saved_settings.get("character_scope", "title")
        self._skip_words = ""
        self._skip_scope = saved_settings.get("skip_scope", "posts")
        self._remove_words = ""
        self._filter_type = "all"
        self._skip_archives = False
        self._download_thumbnails_only = False
        self._scan_content_images = saved_settings.get("scan_content_images", True)
        self._compress_webp = saved_settings.get("compress_webp", False)
        self._keep_duplicates = saved_settings.get("keep_duplicates", False)
        self._favorite_mode = False
        self._subfolder_per_post = saved_settings.get("subfolder_per_post", True)
        self._date_prefix = saved_settings.get("date_prefix", True)
        self._file_index_prefix = bool(saved_settings.get("file_index_prefix", False))
        self._separate_folders_by_known = saved_settings.get("separate_by_known", False)
        self._download_revisions = saved_settings.get("download_revisions", False)
        self._adaptive_threading = saved_settings.get("adaptive_threading", False)
        self._threads_locked = bool(saved_settings.get("threads_locked", False))
        if self._threads_locked:
            self._adaptive_threading = False
        self._auto_retry_at_end = saved_settings.get("auto_retry_at_end", False)
        self._manga_mode = saved_settings.get("manga_mode", False)
        self._filename_style = saved_settings.get("filename_style", "post_title")
        self._proxy_url = saved_settings.get("proxy_url", "")
        self._max_cpu_threads = max(4, os.cpu_count() or 16)
        self._threads_count = int(saved_settings.get("threads", min(8, self._max_cpu_threads)))
        self.downloader.max_workers = self._threads_count
        self._cookie_string = saved_settings.get("cookie", "")
        self._user_agent = saved_settings.get("user_agent", "")
        self._download_delay = float(saved_settings.get("download_delay", 2.0))
        self._save_post_metadata = bool(saved_settings.get("save_post_metadata", True))
        self._download_embeds = bool(saved_settings.get("download_embeds", True))
        self._open_folder_on_complete = bool(saved_settings.get("open_folder_on_complete", False))
        self._play_completion_sound = bool(saved_settings.get("play_completion_sound", False))
        self._generate_desktop_report = bool(saved_settings.get("generate_desktop_report", saved_settings.get("save_desktop_report", False)))
        self._post_download_action = "none" # Always default to 'none' (Do Nothing) on startup
        self._known_recognition_mode = str(saved_settings.get("known_recognition_mode", "hybrid"))
        self.known_manager.set_mode(self._known_recognition_mode)
        self._language = str(saved_settings.get("language", "auto"))
        self._console_width = int(saved_settings.get("console_width", 620))
        self._creator_name = ""
        self._tag_folder_mode = bool(saved_settings.get("tag_folder_mode", False))

        # Watchlist
        self._watchlist_manager = WatchlistManager(self.session_manager.config_dir)
        self._watchlist_manager.load()
        self._watchlist_model = WatchlistModel(self._watchlist_manager, self)
        self._watchlist_result_signal_connected = False
        self._watchlistResultSignal.connect(self._handle_watchlist_result, Qt.QueuedConnection)

        # Bulk Decompressor
        self._decompressor_bridge = DecompressorBridge(self._watchlist_manager, self, self)

        # Scan & Cloud cancellation state
        self._scan_cancel_event = threading.Event()
        self._cloud_cancel_event = threading.Event()
        self._cloud_pause_event = threading.Event()
        self._is_cloud_downloading = False

        # Post-action countdown state
        self._pending_post_action: str = "none"  # action queued for countdown confirmation

        # Trigger background auto-check / update for standalone dependencies/yt-dlp.exe
        self.downloader.ytdlp_manager.check_for_updates_async()

        # Status & In-depth Telemetry
        self._is_downloading = False
        self._status_text = "Progress: Idle"
        self._overall_progress = 0
        self._current_speed = "0 KB/s"
        self._eta_text = "--"
        self._saved_bytes_text = "0 MB"
        self._adaptive_status_text = ""
        self._adaptive_state = "optimal"
        self._elapsed_time_text = "0s"
        self._files_count_text = ""
        self._has_error = False
        self._last_error_message = ""

        # Link Vault state
        self._vault_search = ""
        self._vault_platform = "all"
        self._vault_harvesting = False
        self._vault_harvest_status = ""
        self._vault_harvest_cancel = threading.Event()

        try:
            from core.storage_pool_manager import storage_pool_manager
            storage_pool_manager.set_primary_dir(self._download_dir)
            from core.task_scheduler import task_scheduler
            task_scheduler.on_trigger_watchlist_sync = self._run_scheduled_watchlist_sync
            task_scheduler.on_trigger_creator_sync = self._run_scheduled_creator_sync
            task_scheduler.start()
        except Exception as e:
            logger.debug(f"Scheduler/StoragePool init note: {e}", category="system")

        # Check saved session & recovery journal
        self.recovery_manager = getattr(self.session_manager, "recovery_manager", None)
        if not self.recovery_manager:
            from core.recovery_manager import RecoveryManager
            self.recovery_manager = RecoveryManager(self.session_manager.config_dir)
        self._has_recovery_session = self.recovery_manager.has_unfinished_session()
        self._recovery_summary = self.recovery_manager.get_recovery_summary() if self._has_recovery_session else {}

        saved_sess = self.session_manager.get_saved_session()
        self._has_saved_session = bool(saved_sess) or self._has_recovery_session
        if self._has_recovery_session:
            logger.warning("Unfinished download session detected from previous crash. Ready for recovery.", category="session")

        # Hook downloader callbacks — they emit our private signals (thread-safe)
        self.downloader.on_progress_update        = lambda info: self._progressSignal.emit(info)
        self.downloader.on_task_status_changed    = lambda task: self._taskSignal.emit(task)
        self.downloader.on_download_finished      = lambda ok, msg: self._finishedSignal.emit(ok, msg)
        self.downloader.on_concurrency_throttled  = lambda count: self._throttledSignal.emit(count)
        self.downloader.on_pause_changed          = lambda paused: self._pauseSignal.emit(paused)

        # Connect private signals to main-thread handlers with QueuedConnection
        self._progressSignal.connect(self._handle_progress,    Qt.QueuedConnection)
        self._taskSignal.connect(self._handle_task_status,     Qt.QueuedConnection)
        self._finishedSignal.connect(self._handle_finished,    Qt.QueuedConnection)
        self._throttledSignal.connect(self._handle_throttled,  Qt.QueuedConnection)
        self._pauseSignal.connect(self._handle_pause_changed,  Qt.QueuedConnection)
        self._creatorSignal.connect(self._handle_creator_resolved, Qt.QueuedConnection)
        self._setTasksSignal.connect(self._handle_set_tasks,       Qt.QueuedConnection)
        self._appendTasksSignal.connect(self._handle_append_tasks, Qt.QueuedConnection)
        self._watchlistResultSignal.connect(self._handle_watchlist_result, Qt.QueuedConnection)
        self._watchlistArtistResultSignal.connect(self._handle_watchlist_artist_result, Qt.QueuedConnection)

        # Auto-check watchlist entries on startup (background, non-blocking)
        if any(e.auto_check for e in self._watchlist_manager.entries):
            threading.Thread(target=self._async_watchlist_check, daemon=True).start()

        # Hook queue model retry & batch signals
        self._queue_model.retryRequested.connect(self.retryFailed)
        self._queue_model.singleRetryRequested.connect(self.retrySingleTask)
        self._queue_model.retrySelectedRequested.connect(self.retrySelectedTasks)
        self._queue_model.batchRetryRequested.connect(self._handle_batch_retry)
        self._queue_model.batchCancelRequested.connect(self._handle_batch_cancel)
        self._queue_model.batchRemoveRequested.connect(self._handle_batch_remove)
        self._queue_model.cleared.connect(self._handle_queue_cleared)
        self._queued_links: set[str] = set()

        # Apply initial client config
        if self._cookie_string:
            self.api_client.set_cookie(self._cookie_string)
        if self._user_agent:
            self.api_client.set_user_agent(self._user_agent)

        logger.info(f"filename style loaded: 'post_title'", category="system")
        logger.info(f"Skip words scope loaded: '{self._skip_scope}'", category="system")
        logger.info(f"Character filter scope set to default: '{self._character_scope}'", category="system")
        if self._has_saved_session:
            logger.warning("Incomplete download session found. UI updated for restore.", category="session")

    # Property Getters / Setters
    @Property(str, notify=currentUrlChanged)
    def currentUrl(self) -> str:
        return self._current_url

    @currentUrl.setter
    def currentUrl(self, val: str):
        if self._current_url != val:
            self._current_url = val
            self.currentUrlChanged.emit()

            val_clean = val.strip()
            if val_clean:
                parsed = KemonoURLParser.parse(val_clean)
                if parsed.is_valid:
                    initial_name = parsed.user_id if parsed.user_id not in ("bunkr_user", "erome_user") else parsed.domain
                    self._creator_name = initial_name
                    self.creatorNameChanged.emit()
                    threading.Thread(
                        target=self._async_resolve_creator_name,
                        args=(parsed,),
                        daemon=True
                    ).start()
                else:
                    self._creator_name = ""
                    self.creatorNameChanged.emit()
            else:
                self._creator_name = ""
                self.creatorNameChanged.emit()

    @Property(int, notify=pageStartChanged)
    def pageStart(self) -> int:
        return self._page_start

    @pageStart.setter
    def pageStart(self, val: int):
        if self._page_start != val:
            self._page_start = max(1, val)
            self.pageStartChanged.emit()

    @Property(int, notify=pageEndChanged)
    def pageEnd(self) -> int:
        return self._page_end

    @pageEnd.setter
    def pageEnd(self, val: int):
        if self._page_end != val:
            self._page_end = max(1, val)
            self.pageEndChanged.emit()

    @Property(str, notify=downloadDirChanged)
    def downloadDir(self) -> str:
        return self._download_dir

    @downloadDir.setter
    def downloadDir(self, val: str):
        if self._download_dir != val:
            self._download_dir = val
            self.downloadDirChanged.emit()
            try:
                from core.storage_pool_manager import storage_pool_manager
                storage_pool_manager.set_primary_dir(val)
                self.storagePoolChanged.emit()
            except Exception:
                pass

    @Property(str, notify=filterCharactersChanged)
    def filterCharacters(self) -> str:
        return self._filter_characters

    @filterCharacters.setter
    def filterCharacters(self, val: str):
        if self._filter_characters != val:
            self._filter_characters = val
            self.filterCharactersChanged.emit()

    @Property(str, notify=characterScopeChanged)
    def characterScope(self) -> str:
        return self._character_scope

    @characterScope.setter
    def characterScope(self, val: str):
        if self._character_scope != val:
            self._character_scope = val
            self.characterScopeChanged.emit()

    @Property(str, notify=skipWordsChanged)
    def skipWords(self) -> str:
        return self._skip_words

    @skipWords.setter
    def skipWords(self, val: str):
        if self._skip_words != val:
            self._skip_words = val
            self.skipWordsChanged.emit()

    @Property(str, notify=skipScopeChanged)
    def skipScope(self) -> str:
        return self._skip_scope

    @skipScope.setter
    def skipScope(self, val: str):
        if self._skip_scope != val:
            self._skip_scope = val
            self.skipScopeChanged.emit()

    @Property(str, notify=removeWordsChanged)
    def removeWords(self) -> str:
        return self._remove_words

    @removeWords.setter
    def removeWords(self, val: str):
        if self._remove_words != val:
            self._remove_words = val
            self.removeWordsChanged.emit()

    @Property(str, notify=filterTypeChanged)
    def filterType(self) -> str:
        return self._filter_type

    @filterType.setter
    def filterType(self, val: str):
        if self._filter_type != val:
            self._filter_type = val
            self.filterTypeChanged.emit()

    @Property(bool, notify=skipArchivesChanged)
    def skipArchives(self) -> bool:
        return self._skip_archives

    @skipArchives.setter
    def skipArchives(self, val: bool):
        if self._skip_archives != val:
            self._skip_archives = val
            self.skipArchivesChanged.emit()

    @Property(bool, notify=downloadThumbnailsOnlyChanged)
    def downloadThumbnailsOnly(self) -> bool:
        return self._download_thumbnails_only

    @downloadThumbnailsOnly.setter
    def downloadThumbnailsOnly(self, val: bool):
        if self._download_thumbnails_only != val:
            self._download_thumbnails_only = val
            self.downloadThumbnailsOnlyChanged.emit()

    @Property(bool, notify=scanContentImagesChanged)
    def scanContentImages(self) -> bool:
        return self._scan_content_images

    @scanContentImages.setter
    def scanContentImages(self, val: bool):
        if self._scan_content_images != val:
            self._scan_content_images = val
            self.scanContentImagesChanged.emit()

    @Property(bool, notify=compressWebpChanged)
    def compressWebp(self) -> bool:
        return self._compress_webp

    @compressWebp.setter
    def compressWebp(self, val: bool):
        if self._compress_webp != val:
            self._compress_webp = val
            self.compressWebpChanged.emit()

    @Property(bool, notify=keepDuplicatesChanged)
    def keepDuplicates(self) -> bool:
        return self._keep_duplicates

    @keepDuplicates.setter
    def keepDuplicates(self, val: bool):
        if self._keep_duplicates != val:
            self._keep_duplicates = val
            self.keepDuplicatesChanged.emit()

    @Property(bool, notify=favoriteModeChanged)
    def favoriteMode(self) -> bool:
        return self._favorite_mode

    @favoriteMode.setter
    def favoriteMode(self, val: bool):
        if self._favorite_mode != val:
            self._favorite_mode = val
            self.favoriteModeChanged.emit()

    @Property(bool, notify=subfolderPerPostChanged)
    def subfolderPerPost(self) -> bool:
        return self._subfolder_per_post

    @subfolderPerPost.setter
    def subfolderPerPost(self, val: bool):
        if self._subfolder_per_post != val:
            self._subfolder_per_post = val
            self.subfolderPerPostChanged.emit()

    @Property(bool, notify=datePrefixChanged)
    def datePrefix(self) -> bool:
        return self._date_prefix

    @datePrefix.setter
    def datePrefix(self, val: bool):
        if self._date_prefix != val:
            self._date_prefix = val
            self.datePrefixChanged.emit()
            self.saveSettings()

    @Property(bool, notify=fileIndexPrefixChanged)
    def fileIndexPrefix(self) -> bool:
        return self._file_index_prefix

    @fileIndexPrefix.setter
    def fileIndexPrefix(self, val: bool):
        if self._file_index_prefix != val:
            self._file_index_prefix = val
            self.fileIndexPrefixChanged.emit()
            self.saveSettings()

    @Property(bool, notify=separateFoldersByKnownChanged)
    def separateFoldersByKnown(self) -> bool:
        return self._separate_folders_by_known

    @separateFoldersByKnown.setter
    def separateFoldersByKnown(self, val: bool):
        if self._separate_folders_by_known != val:
            self._separate_folders_by_known = val
            self.separateFoldersByKnownChanged.emit()

    @Property(bool, notify=downloadRevisionsChanged)
    def downloadRevisions(self) -> bool:
        return self._download_revisions

    @downloadRevisions.setter
    def downloadRevisions(self, val: bool):
        if self._download_revisions != val:
            self._download_revisions = val
            self.downloadRevisionsChanged.emit()

    @Property(bool, notify=adaptiveThreadingChanged)
    def adaptiveThreading(self) -> bool:
        return self._adaptive_threading

    @adaptiveThreading.setter
    def adaptiveThreading(self, val: bool):
        # Cannot enable adaptive threading if threads are locked
        if self._threads_locked and val:
            return
        if self._adaptive_threading != val:
            self._adaptive_threading = val
            self.adaptiveThreadingChanged.emit()
            self.saveSettings()

    @Property(bool, notify=threadsLockedChanged)
    def threadsLocked(self) -> bool:
        return self._threads_locked

    @threadsLocked.setter
    def threadsLocked(self, val: bool):
        val = bool(val)
        if self._threads_locked != val:
            self._threads_locked = val
            self.threadsLockedChanged.emit()
            if val:
                # Lock applied -> disable adaptive threading
                self.adaptiveThreading = False
            if hasattr(self.downloader, "current_options") and self.downloader.current_options:
                self.downloader.current_options.threads_locked = val
            self.saveSettings()

    @Property(bool, notify=autoRetryAtEndChanged)
    def autoRetryAtEnd(self) -> bool:
        return self._auto_retry_at_end

    @autoRetryAtEnd.setter
    def autoRetryAtEnd(self, val: bool):
        if self._auto_retry_at_end != val:
            self._auto_retry_at_end = val
            self.autoRetryAtEndChanged.emit()
            self.saveSettings()
            if hasattr(self.downloader, "current_options") and self.downloader.current_options:
                self.downloader.current_options.auto_retry_at_end = val
            if val and not self._is_downloading and self._queue_model.failedCount > 0:
                logger.info("Auto-Retry enabled with failed tasks present — starting retry queue...", category="downloader")
                self.retryFailed()

    @Slot()
    def toggleAutoRetry(self):
        """Toggles auto-retry; if turning on (or if already on with failed tasks idle), immediately retries failed tasks."""
        if not self._auto_retry_at_end:
            self.autoRetryAtEnd = True
        else:
            if not self._is_downloading and self._queue_model.failedCount > 0:
                logger.info("Auto-Retry activated for failed tasks...", category="downloader")
                self.retryFailed()
            else:
                self.autoRetryAtEnd = False

    @Property(bool, notify=mangaModeChanged)
    def mangaMode(self) -> bool:
        return self._manga_mode

    @mangaMode.setter
    def mangaMode(self, val: bool):
        if self._manga_mode != val:
            self._manga_mode = val
            self.mangaModeChanged.emit()

    @Property(str, notify=filenameStyleChanged)
    def filenameStyle(self) -> str:
        return self._filename_style

    @filenameStyle.setter
    def filenameStyle(self, val: str):
        if self._filename_style != val:
            self._filename_style = val
            self.filenameStyleChanged.emit()

    @Property(str, notify=proxyUrlChanged)
    def proxyUrl(self) -> str:
        return self._proxy_url

    @proxyUrl.setter
    def proxyUrl(self, val: str):
        if self._proxy_url != val:
            self._proxy_url = val
            self.api_client.set_proxy(val)
            self.proxyUrlChanged.emit()
            self.saveSettings()

    @Property(int, notify=threadsCountChanged)
    def threadsCount(self) -> int:
        return self._threads_count

    @threadsCount.setter
    def threadsCount(self, val: int):
        if self._threads_count != val:
            self._threads_count = max(1, min(self._max_cpu_threads, val))
            self.downloader.max_workers = self._threads_count
            self.threadsCountChanged.emit()

    @Property(int, notify=maxCpuThreadsChanged)
    def maxCpuThreads(self) -> int:
        return self._max_cpu_threads

    @Property(str, notify=etaTextChanged)
    def etaText(self) -> str:
        return self._eta_text

    @Property(str, notify=savedBytesTextChanged)
    def savedBytesText(self) -> str:
        return self._saved_bytes_text

    @Property(str, notify=adaptiveStatusTextChanged)
    def adaptiveStatusText(self) -> str:
        return self._adaptive_status_text

    @Property(str, notify=adaptiveStateChanged)
    def adaptiveState(self) -> str:
        return self._adaptive_state

    @Property(str, notify=elapsedTimeTextChanged)
    def elapsedTimeText(self) -> str:
        return self._elapsed_time_text

    @Property(str, notify=filesCountTextChanged)
    def filesCountText(self) -> str:
        return self._files_count_text

    @Property(str, notify=cookieStringChanged)
    def cookieString(self) -> str:
        return self._cookie_string

    @cookieString.setter
    def cookieString(self, val: str):
        val = val.strip()
        if val and val.startswith("eyJ") and "session=" not in val:
            val = f"session={val}"
        elif val and "=" not in val:
            val = f"session={val}"
        if self._cookie_string != val:
            self._cookie_string = val
            self.api_client.set_cookie(val)
            self.cookieStringChanged.emit()

    @Property(str, notify=userAgentChanged)
    def userAgent(self) -> str:
        return self._user_agent

    @userAgent.setter
    def userAgent(self, val: str):
        if self._user_agent != val:
            self._user_agent = val
            self.api_client.set_user_agent(val)
            self.userAgentChanged.emit()

    @Property(bool, notify=isDownloadingChanged)
    def isDownloading(self) -> bool:
        return self._is_downloading

    @Property(bool, notify=isPausedChanged)
    def isPaused(self) -> bool:
        return self.downloader.is_paused or self._cloud_pause_event.is_set() or ("Paused" in self._status_text)

    @Property(str, notify=statusTextChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(int, notify=overallProgressChanged)
    def overallProgress(self) -> int:
        return self._overall_progress

    @Property(str, notify=currentSpeedChanged)
    def currentSpeed(self) -> str:
        return self._current_speed

    @Property(str, notify=currentSpeedChanged)
    def speedText(self) -> str:
        return self._current_speed

    @Property(bool, notify=hasSavedSessionChanged)
    def hasSavedSession(self) -> bool:
        return self._has_saved_session

    @Property(bool, notify=hasRecoverySessionChanged)
    def hasRecoverySession(self) -> bool:
        return self._has_recovery_session

    @Property('QVariant', notify=hasRecoverySessionChanged)
    def recoverySummary(self) -> dict:
        return self._recovery_summary or {}

    @Property(bool, notify=hasErrorChanged)
    def hasError(self) -> bool:
        return self._has_error

    @Property(str, notify=lastErrorMessageChanged)
    def lastErrorMessage(self) -> str:
        return self._last_error_message

    @Property(str, notify=creatorNameChanged)
    def creatorName(self) -> str:
        return self._creator_name

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, val: str):
        if self._language != val:
            self._language = val
            self.languageChanged.emit()
            self.saveSettings()

    @Property(float, notify=downloadDelayChanged)
    def downloadDelay(self) -> float:
        return self._download_delay

    @downloadDelay.setter
    def downloadDelay(self, val: float):
        val = round(float(val), 2)
        if self._download_delay != val:
            self._download_delay = val
            self.downloadDelayChanged.emit()
            self.saveSettings()

    @Property(bool, notify=savePostMetadataChanged)
    def savePostMetadata(self) -> bool:
        return self._save_post_metadata

    @savePostMetadata.setter
    def savePostMetadata(self, val: bool):
        if self._save_post_metadata != val:
            self._save_post_metadata = val
            self.savePostMetadataChanged.emit()
            self.saveSettings()

    @Property(bool, notify=downloadEmbedsChanged)
    def downloadEmbeds(self) -> bool:
        return self._download_embeds

    @downloadEmbeds.setter
    def downloadEmbeds(self, val: bool):
        if self._download_embeds != val:
            self._download_embeds = val
            self.downloadEmbedsChanged.emit()
            self.saveSettings()

    @Property(bool, notify=openFolderOnCompleteChanged)
    def openFolderOnComplete(self) -> bool:
        return self._open_folder_on_complete

    @openFolderOnComplete.setter
    def openFolderOnComplete(self, val: bool):
        if self._open_folder_on_complete != val:
            self._open_folder_on_complete = val
            self.openFolderOnCompleteChanged.emit()
            self.saveSettings()

    @Property(bool, notify=playCompletionSoundChanged)
    def playCompletionSound(self) -> bool:
        return self._play_completion_sound

    @playCompletionSound.setter
    def playCompletionSound(self, val: bool):
        if self._play_completion_sound != val:
            self._play_completion_sound = val
            self.playCompletionSoundChanged.emit()
            self.saveSettings()

    @Property(bool, notify=generateDesktopReportChanged)
    def generateDesktopReport(self) -> bool:
        return self._generate_desktop_report

    @generateDesktopReport.setter
    def generateDesktopReport(self, val: bool):
        if self._generate_desktop_report != val:
            self._generate_desktop_report = val
            self.generateDesktopReportChanged.emit()
            self.saveDesktopReportChanged.emit()
            self.saveSettings()

    @Property(bool, notify=saveDesktopReportChanged)
    def saveDesktopReport(self) -> bool:
        return self._generate_desktop_report

    @saveDesktopReport.setter
    def saveDesktopReport(self, val: bool):
        self.generateDesktopReport = val

    @Property(int, notify=consoleWidthChanged)
    def consoleWidth(self) -> int:
        return self._console_width

    @consoleWidth.setter
    def consoleWidth(self, val: int):
        val = max(280, min(1400, int(val)))
        if self._console_width != val:
            self._console_width = val
            self.consoleWidthChanged.emit()
            self.saveSettings()

    @Property(str, notify=postDownloadActionChanged)
    def postDownloadAction(self) -> str:
        return self._post_download_action

    @postDownloadAction.setter
    def postDownloadAction(self, val: str):
        allowed = {"none", "close_app", "sleep", "hibernate", "shutdown", "restart"}
        if val not in allowed:
            val = "none"
        if self._post_download_action != val:
            self._post_download_action = val
            self.postDownloadActionChanged.emit()

    @Property(str, notify=knownRecognitionModeChanged)
    def knownRecognitionMode(self) -> str:
        return self._known_recognition_mode

    @knownRecognitionMode.setter
    def knownRecognitionMode(self, val: str):
        allowed = {"hybrid", "database_only", "learning_only"}
        if val not in allowed:
            val = "hybrid"
        if self._known_recognition_mode != val:
            self._known_recognition_mode = val
            self.known_manager.set_mode(val)
            self.knownRecognitionModeChanged.emit()
            self.saveSettings()

    # Model Properties
    @Property(QObject, constant=True)
    def logModel(self) -> LogModel:
        return self._log_model

    @Property(QObject, constant=True)
    def queueModel(self) -> QueueModel:
        return self._queue_model

    @Property(QObject, constant=True)
    def activeQueueModel(self) -> QueueModel:
        return self._active_queue_model

    @Property(QObject, constant=True)
    def knownModel(self) -> KnownModel:
        return self._known_model

    @Property(QObject, constant=True)
    def watchlistModel(self) -> WatchlistModel:
        return self._watchlist_model

    @Property(QObject, constant=True)
    def decompressorBridge(self) -> DecompressorBridge:
        return self._decompressor_bridge

    @Property(bool, notify=tagFolderModeChanged)
    def tagFolderMode(self) -> bool:
        return self._tag_folder_mode

    @tagFolderMode.setter
    def tagFolderMode(self, val: bool):
        if self._tag_folder_mode != val:
            self._tag_folder_mode = val
            self.tagFolderModeChanged.emit()
            self.saveSettings()

    @Property(bool, notify=harvestedLinksChanged)
    def hasHarvestedLinks(self) -> bool:
        return bool(self.downloader.harvested_links_records)

    @Property(int, notify=harvestedLinksChanged)
    def harvestedLinksCount(self) -> int:
        return len(self.downloader.harvested_links_records)

    @Property(list, notify=harvestedLinksChanged)
    def harvestedLinks(self) -> list:
        return self.downloader.harvested_links_records

    @Property(bool, notify=isDownloadingChanged)
    def isCloudDownloading(self) -> bool:
        return self._is_cloud_downloading

    # ── Link Vault Properties ────────────────────────────────────────────────
    @Property(str, notify=linkVaultChanged)
    def linkVaultTreeJson(self) -> str:
        from core.link_vault_manager import link_vault_manager
        return json.dumps(link_vault_manager.get_tree_model(self._vault_search, self._vault_platform), ensure_ascii=False)

    @Property(int, notify=linkVaultChanged)
    def linkVaultTotalLinks(self) -> int:
        from core.link_vault_manager import link_vault_manager
        return len(link_vault_manager.data.get("links", []))

    @Property(int, notify=linkVaultChanged)
    def linkVaultTotalCreators(self) -> int:
        from core.link_vault_manager import link_vault_manager
        return len(link_vault_manager.data.get("creators", {}))

    @Property(bool, notify=linkVaultChanged)
    def linkVaultProbingActive(self) -> bool:
        from core.link_vault_manager import link_vault_manager
        return link_vault_manager._probing_active

    @Property(bool, notify=linkVaultChanged)
    def linkVaultHarvestingActive(self) -> bool:
        return self._vault_harvesting

    @Property(str, notify=linkVaultChanged)
    def linkVaultHarvestingStatus(self) -> str:
        return self._vault_harvest_status

    # ── Storage Pool Properties ──────────────────────────────────────────────
    @Property(bool, notify=storagePoolChanged)
    def storagePoolEnabled(self) -> bool:
        from core.storage_pool_manager import storage_pool_manager
        return storage_pool_manager.enabled

    @Property(float, notify=storagePoolChanged)
    def storagePoolMarginGB(self) -> float:
        from core.storage_pool_manager import storage_pool_manager
        return storage_pool_manager.safety_margin_gb

    @Property(str, notify=storagePoolChanged)
    def storagePoolStatusJson(self) -> str:
        from core.storage_pool_manager import storage_pool_manager
        return json.dumps(storage_pool_manager.get_pool_status(), ensure_ascii=False)

    # ── Cookie Watchdog Properties ───────────────────────────────────────────
    @Property(str, notify=cookieWatchdogChanged)
    def cookieWatchdogStatus(self) -> str:
        from services.cookie_importer import browser_cookie_importer
        info = browser_cookie_importer.calculate_expiration_info(self._cookie_string)
        return info.get("status", "missing")

    @Property(str, notify=cookieWatchdogChanged)
    def cookieWatchdogText(self) -> str:
        from services.cookie_importer import browser_cookie_importer
        info = browser_cookie_importer.calculate_expiration_info(self._cookie_string)
        return info.get("status_text", "")

    @Property(str, notify=cookieWatchdogChanged)
    def cookieWatchdogColor(self) -> str:
        from services.cookie_importer import browser_cookie_importer
        info = browser_cookie_importer.calculate_expiration_info(self._cookie_string)
        return info.get("color", "#94A3B8")

    @Property('QVariant', notify=cookieWatchdogChanged)
    def detectedBrowsersList(self):
        from services.cookie_importer import browser_cookie_importer
        return browser_cookie_importer.get_supported_browsers()

    # ── Task Scheduler Properties ────────────────────────────────────────────
    @Property(bool, notify=schedulerChanged)
    def schedulerEnabled(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.enabled

    @Property(bool, notify=schedulerChanged)
    def schedulerLockThreadsDelay(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.lock_threads_delay

    @Property(bool, notify=schedulerChanged)
    def schedulerNightOwlEnabled(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.night_owl_enabled

    @Property(str, notify=schedulerChanged)
    def schedulerNightOwlStart(self) -> str:
        from core.task_scheduler import task_scheduler
        return task_scheduler.night_owl_start

    @Property(str, notify=schedulerChanged)
    def schedulerNightOwlEnd(self) -> str:
        from core.task_scheduler import task_scheduler
        return task_scheduler.night_owl_end

    @Property(bool, notify=schedulerChanged)
    def schedulerPreventSleep(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.prevent_sleep

    @Property(bool, notify=schedulerChanged)
    def schedulerSweepRetry(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.sweep_retry

    @Property(str, notify=schedulerChanged)
    def schedulerSchedulesJson(self) -> str:
        from core.task_scheduler import task_scheduler
        return json.dumps(task_scheduler.schedules, ensure_ascii=False)

    @Slot(result="QVariantList")
    def getHarvestedLinks(self):
        return self.downloader.harvested_links_records

    @Slot(result="QVariantList")
    def getDownloadHistory(self):
        """Return download history as a list of dicts for the History tab."""
        return self.session_manager.get_download_history()

    def _get_filter_options(self) -> FilterOptions:
        return FilterOptions(
            characters=self._filter_characters,
            character_scope=self._character_scope,
            skip_words=self._skip_words,
            skip_scope=self._skip_scope,
            remove_words=self._remove_words,
            file_type=self._filter_type,
            skip_archives=self._skip_archives,
            download_thumbnails_only=self._download_thumbnails_only,
            scan_content_images=self._scan_content_images,
            compress_to_webp=self._compress_webp,
            keep_duplicates=self._keep_duplicates,
            favorite_mode=self._favorite_mode,
            subfolder_per_post=self._subfolder_per_post,
            date_prefix=self._date_prefix,
            file_index_prefix=self._file_index_prefix,
            separate_by_known=self._separate_folders_by_known,
            download_revisions=self._download_revisions,
            adaptive_threading=self._adaptive_threading,
            threads_locked=self._threads_locked,
            auto_retry_at_end=self._auto_retry_at_end,
            manga_mode=self._manga_mode,
            filename_style=self._filename_style,
            proxy_url=self._proxy_url,
            page_start=self._page_start,
            page_end=self._page_end,
            download_delay=self._download_delay,
            save_post_metadata=self._save_post_metadata,
            download_embeds=self._download_embeds,
            tag_folder_mode=self._tag_folder_mode
        )

    def _get_link_identity(self, parsed: URLParseResult) -> tuple[str, str, Optional[str], str]:
        """
        Returns (link_type, identity_key, parent_artist_key, display_name).
        link_type: 'artist' | 'post' | 'external'
        identity_key: unique canonical string for this link
        parent_artist_key: artist key if this is a single post, else None
        display_name: human-readable name for logging
        """
        if parsed.is_external_provider:
            pid = parsed.post_id or parsed.raw_url
            key = f"{parsed.provider.lower()}:{pid}"
            display = f"{parsed.provider.capitalize()} ({pid})"
            return "external", key, None, display

        service = (parsed.service or "").lower()
        user_id = (parsed.user_id or "").lower()
        artist_key = f"artist:{service}:{user_id}"

        if parsed.is_single_post and parsed.post_id:
            post_id = str(parsed.post_id).lower()
            post_key = f"post:{service}:{user_id}:{post_id}"
            display = f"post {parsed.post_id} ({parsed.service} / user {parsed.user_id})"
            return "post", post_key, artist_key, display
        else:
            display = f"artist {parsed.user_id} ({parsed.service})"
            return "artist", artist_key, None, display

    # Actions / Slots
    @Slot()
    def startDownload(self):
        """
        Starts downloading queued works, or parses URL, fetches posts, and starts download.
        If tasks are already queued and current URL is blank or already queued, directly starts the queue.
        """
        if self._is_downloading:
            logger.warning("Download process is already running!", category="system")
            return

        # Ensure downloader tasks list is synced with queue model if needed
        if not self.downloader.tasks and self._queue_model.tasks:
            self.downloader.tasks = list(self._queue_model.tasks)

        has_pending = any(t.status in ("pending", "failed", "cancelled") for t in self.downloader.tasks) or (self._queue_model.pendingCount > 0)
        url_input = (self._current_url or "").strip()

        # Check if URL input matches an already queued item
        url_is_already_queued = False
        parsed_current = None
        if url_input:
            parsed_current = KemonoURLParser.parse(url_input)
            if parsed_current.is_valid:
                _, identity_key, parent_artist_key, _ = self._get_link_identity(parsed_current)
                if identity_key in self._queued_links or (parent_artist_key and parent_artist_key in self._queued_links):
                    url_is_already_queued = True

        # Case 1: Start existing queue directly if URL is empty or already queued
        if has_pending and (not url_input or url_is_already_queued):
            options = self._get_filter_options()
            self._scan_cancel_event.clear()
            self._has_error = False
            self.hasErrorChanged.emit()
            self._is_downloading = True
            self.isDownloadingChanged.emit()
            self.isPausedChanged.emit()
            self._status_text = "Starting download queue..."
            self.statusTextChanged.emit()
            logger.info(f"Starting download for {len(self.downloader.tasks)} queued task(s)...", category="downloader")
            self.downloader.start_download_queue(
                tasks=self.downloader.tasks,
                options=options,
                cookie_str=self._cookie_string
            )
            return

        # Case 2: No pending tasks and no URL provided
        if not url_input:
            if self._queue_model.rowCount() > 0:
                logger.info("All tasks in queue are already completed. Use 'Retry Failed' to re-download failed items.", category="downloader")
            else:
                logger.warning("Please enter a URL to start download or add to queue.", category="parser")
            return

        # Case 3: URL provided but invalid
        if not parsed_current or not parsed_current.is_valid:
            if has_pending:
                logger.warning(f"URL is invalid ({parsed_current.error_msg if parsed_current else 'empty'}). Starting existing queued tasks...", category="downloader")
                options = self._get_filter_options()
                self._scan_cancel_event.clear()
                self._has_error = False
                self.hasErrorChanged.emit()
                self._is_downloading = True
                self.isDownloadingChanged.emit()
                self.isPausedChanged.emit()
                self._status_text = "Starting download queue..."
                self.statusTextChanged.emit()
                self.downloader.start_download_queue(
                    tasks=self.downloader.tasks,
                    options=options,
                    cookie_str=self._cookie_string
                )
                return
            else:
                self._has_error = True
                self._last_error_message = parsed_current.error_msg if parsed_current else "Invalid URL"
                self.hasErrorChanged.emit()
                self.lastErrorMessageChanged.emit()
                logger.error(f"Invalid URL: {self._last_error_message}", category="parser")
                return

        # Case 4: Valid new URL -> mark queued, fetch and start
        _, identity_key, _, _ = self._get_link_identity(parsed_current)
        self._queued_links.add(identity_key)

        self._scan_cancel_event.clear()
        self._has_error = False
        self.hasErrorChanged.emit()
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self.isPausedChanged.emit()
        self._status_text = "Fetching metadata..."
        self.statusTextChanged.emit()

        threading.Thread(
            target=self._async_fetch_and_start,
            args=(parsed_current, True),
            daemon=True
        ).start()

    @Slot()
    def addToQueue(self):
        """
        Parses URL(s), fetches posts, and appends to the queue without immediate download.
        Supports pasting multiple URLs (comma or newline separated).
        Deduplicates against already queued artist or post links.
        """
        raw_urls = [u.strip() for u in self._current_url.replace(",", "\n").splitlines() if u.strip()]
        if not raw_urls:
            logger.warning("Please enter a URL to add to queue.", category="parser")
            return

        self._scan_cancel_event.clear()

        def _batch_queue_worker():
            for u in raw_urls:
                if self._scan_cancel_event.is_set():
                    break
                parsed = KemonoURLParser.parse(u)
                if not parsed.is_valid:
                    logger.error(f"Invalid URL: {parsed.error_msg} ({u})", category="parser")
                    continue

                link_type, identity_key, parent_artist_key, display_name = self._get_link_identity(parsed)

                # Check duplicate link
                if identity_key in self._queued_links:
                    logger.warning(f"Skipping duplicate {link_type}: {display_name} is already in queue.", category="queue")
                    continue

                # Check if this is a single post whose parent artist is already in queue
                if parent_artist_key and parent_artist_key in self._queued_links:
                    logger.info(f"Skipping post: entire artist ({parsed.user_id}) is already in queue.", category="queue")
                    continue

                self._queued_links.add(identity_key)
                self._async_fetch_and_start(parsed, auto_start=False)

        threading.Thread(
            target=_batch_queue_worker,
            daemon=True
        ).start()

    def _auto_harvest_posts_to_vault(self, posts: List[Dict[str, Any]], creator_name: str, domain: str, service: str, user_id: str):
        """
        Background worker to harvest cloud links, smart passwords, and post metadata
        from posts into the permanent Link Vault during downloads or queue additions.
        """
        if not posts or not service or not user_id:
            return

        posts_copy = list(posts)

        def _worker():
            try:
                from services.link_extractor import LinkExtractor
                from core.link_vault_manager import link_vault_manager

                harvested_posts = []
                for p in posts_copy:
                    rec = LinkExtractor.extract_post_vault_record(
                        post=p,
                        api_client=None,
                        domain=domain,
                        service=service,
                        user_id=user_id
                    )
                    if rec and rec.get("links"):
                        harvested_posts.append(rec)

                if harvested_posts:
                    new_links_count = link_vault_manager.add_harvested_data(
                        creator_name=creator_name or user_id,
                        service=service,
                        user_id=user_id,
                        harvested_posts=harvested_posts
                    )
                    if new_links_count > 0:
                        logger.success(
                            f"Link Vault: Auto-harvested and permanently saved {new_links_count} new link(s) for '{creator_name or user_id}'.",
                            category="vault"
                        )
                        self.linkVaultChanged.emit()
            except Exception as e:
                logger.debug(f"Link Vault auto-harvest error: {e}", category="vault")

        threading.Thread(target=_worker, daemon=True).start()

    def _async_fetch_and_start(self, parsed: URLParseResult, auto_start: bool):
        try:
            if self._scan_cancel_event.is_set():
                self._is_downloading = False
                self._status_text = "Progress: Cancelled"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                return

            options = self._get_filter_options()

            # ── Handle Integrated Third-Party Providers ───────────────────────
            if parsed.is_external_provider:
                creator_name = parsed.domain
                tasks = []

                if parsed.provider == "bunkr":
                    album_title, files = fetch_bunkr_album(parsed.raw_url, resolve_files=True)
                    creator_name = clean_text(album_title) or "Bunkr Album"
                    folder_name = sanitize_filesystem_name(creator_name, fallback="Bunkr Album")
                    folder = os.path.join(self._download_dir, f"Bunkr - {folder_name}")
                    for f in files:
                        t = DownloadTask(
                            url=f["url"],
                            target_path=os.path.join(folder, f["filename"]),
                            post_title=creator_name,
                            creator_name=creator_name,
                            service="bunkr",
                            post_id=parsed.post_id or "bunkr",
                            file_id=f["url"],
                            file_size=f.get("size", 0),
                            batch_id=f"bunkr_{parsed.post_id or creator_name or 'bunkr'}"
                        )
                        tasks.append(t)

                elif parsed.provider == "erome":
                    album_title, files = fetch_erome_album(parsed.raw_url)
                    creator_name = clean_text(album_title) or "Erome Album"
                    folder_name = sanitize_filesystem_name(creator_name, fallback="Erome Album")
                    folder = os.path.join(self._download_dir, f"Erome - {folder_name}")
                    for f in files:
                        t = DownloadTask(
                            url=f["url"],
                            target_path=os.path.join(folder, f["filename"]),
                            post_title=creator_name,
                            creator_name=creator_name,
                            service="erome",
                            post_id=parsed.post_id or "erome",
                            file_id=f["url"],
                            batch_id=f"erome_{parsed.post_id or creator_name or 'erome'}"
                        )
                        tasks.append(t)

                elif parsed.provider == "nhentai":
                    gallery_title, files = fetch_nhentai_gallery(parsed.post_id or parsed.raw_url)
                    creator_name = clean_text(gallery_title) or f"Gallery {parsed.post_id}"
                    folder_name = sanitize_filesystem_name(creator_name, fallback=f"Gallery {parsed.post_id}")
                    folder = os.path.join(self._download_dir, f"nHentai - {folder_name}")
                    for f in files:
                        t = DownloadTask(
                            url=f["url"],
                            target_path=os.path.join(folder, f["filename"]),
                            post_title=creator_name,
                            creator_name=creator_name,
                            service="nhentai",
                            post_id=parsed.post_id or "nhentai",
                            file_id=f["url"],
                            batch_id=f"nhentai_{parsed.post_id or creator_name or 'nhentai'}"
                        )
                        tasks.append(t)

                self._creator_name = creator_name
                self.creatorNameChanged.emit()

            else:
                # ── Standard Kemono / Coomer / Pawchive Provider ───────────────
                # 1. Fetch profile
                profile = self.api_client.fetch_creator_profile(parsed)
                creator_name = clean_text(profile.get("name", parsed.user_id) or parsed.user_id)
                self._creator_name = creator_name
                self.creatorNameChanged.emit()

                if self._scan_cancel_event.is_set():
                    self._is_downloading = False
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                # 2. Fetch posts
                if parsed.is_single_post:
                    single = self.api_client.fetch_single_post(parsed)
                    posts = [single] if single else []
                else:
                    posts = self.api_client.fetch_user_posts(
                        parsed=parsed,
                        page_start=self._page_start,
                        page_end=self._page_end,
                        cancel_event=self._scan_cancel_event
                    )

                if self._scan_cancel_event.is_set():
                    self._is_downloading = False
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                if not posts:
                    logger.warning(f"No posts found for {creator_name} ({parsed.service}).", category="api")
                    self._is_downloading = False
                    self._status_text = "Progress: Idle (0 posts found)"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                # If character filter uses comments scope, attach comments to post dictionaries
                if options.character_scope in ("comments", "all"):
                    for p in posts:
                        if self._scan_cancel_event.is_set():
                            break
                        pid = str(p.get("id", ""))
                        if pid:
                            comms = self.api_client.fetch_post_comments(parsed.domain, parsed.service, parsed.user_id, pid)
                            p["comments_text"] = "\n".join(c.get("content", "") for c in comms if isinstance(c, dict))

                if self._scan_cancel_event.is_set():
                    self._is_downloading = False
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                # 3. Build tasks
                if parsed.is_single_post and parsed.post_id:
                    batch_id = f"post_{parsed.service}_{parsed.user_id}_{parsed.post_id}"
                    artist_dir = None
                else:
                    batch_id = f"artist_{parsed.service}_{parsed.user_id}"
                    existing_entry = self._watchlist_manager._find(parsed.user_id, parsed.service) if (not parsed.is_external_provider and parsed.user_id) else None
                    artist_dir = self.resolve_artist_download_dir(existing_entry) if (existing_entry and existing_entry.download_dir) else None

                tasks = self.downloader.build_tasks_from_posts(
                    posts=posts,
                    creator_name=creator_name,
                    service=parsed.service,
                    domain=parsed.domain,
                    base_dir=self._download_dir,
                    options=options,
                    batch_id=batch_id,
                    artist_dir=artist_dir,
                    user_id=parsed.user_id if not parsed.is_external_provider else ""
                )

                # Auto-harvest cloud storage links into permanent Link Vault
                self._auto_harvest_posts_to_vault(
                    posts=posts,
                    creator_name=creator_name,
                    domain=parsed.domain,
                    service=parsed.service,
                    user_id=parsed.user_id
                )

            if self._scan_cancel_event.is_set():
                self._is_downloading = False
                self._status_text = "Progress: Cancelled"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                return

            if options.file_type == "links":
                h_count = len(self.downloader.harvested_links_records)
                self._is_downloading = False
                self._status_text = f"Links extraction complete ({h_count} links found). Ready to download or export."
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                self.harvestedLinksChanged.emit()
                return

            if not tasks:
                logger.warning("No files matched filtering criteria.", category="downloader")
                self._is_downloading = False
                self._status_text = "Progress: Idle (All files filtered out)"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                return

            # Record to history for History tab
            self.session_manager.record_download_session(
                creator_name=creator_name,
                url=getattr(parsed, "raw_url", self._current_url),
                service=parsed.service,
                file_count=len(tasks)
            )
            self.downloadHistoryChanged.emit()

            # Auto-track artist in watchlist immediately if not a single post / external provider
            if not parsed.is_single_post and not parsed.is_external_provider and parsed.user_id:
                try:
                    latest_pid = ""
                    latest_pdate = ""
                    for p in posts:
                        pub = p.get("published") or p.get("added") or ""
                        if isinstance(pub, (int, float)):
                            try:
                                d_str = datetime.datetime.fromtimestamp(pub).strftime("%Y-%m-%d")
                            except Exception:
                                d_str = str(pub)
                        else:
                            p_str = str(pub)
                            d_str = p_str.split("T")[0] if "T" in p_str else (p_str[:10] if p_str else "")
                        pid = str(p.get("id", ""))
                        if d_str and d_str > latest_pdate:
                            latest_pdate = d_str
                            latest_pid = pid
                        elif not latest_pdate and not latest_pid and pid:
                            latest_pid = pid

                    canonical_url = getattr(parsed, "raw_url", "") or f"https://{parsed.domain}/{parsed.service}/user/{parsed.user_id}"
                    target_download_dir = ""
                    if artist_dir:
                        target_download_dir = artist_dir
                    elif tasks:
                        target_download_dir = self.extract_artist_folder_from_path(
                            tasks[0].target_path,
                            creator_name or parsed.user_id,
                            parsed.service,
                            fallback_dir=self._download_dir
                        )
                    else:
                        from core.filter_engine import FilterEngine
                        clean_c = FilterEngine.clean_filesystem_text(creator_name or parsed.user_id, max_len=80, fallback="creator")
                        cand = os.path.join(self._download_dir, f"{clean_c} [{parsed.service}]")
                        target_download_dir = cand if os.path.exists(cand) else self._download_dir

                    self._watchlist_manager.add_entry(
                        url=canonical_url,
                        creator_name=creator_name or parsed.user_id,
                        user_id=parsed.user_id,
                        service=parsed.service,
                        domain=parsed.domain,
                        last_post_id=latest_pid,
                        last_post_date=latest_pdate,
                        download_dir=target_download_dir,
                        options=options.to_dict() if hasattr(options, "to_dict") else {},
                    )
                    self._watchlist_model.refresh()
                    self.watchlistChanged.emit()
                except Exception as e:
                    logger.debug(f"Watchlist auto-track error: {e}", category="watchlist")


            if auto_start:
                if self.downloader._is_running:
                    self._appendTasksSignal.emit(tasks)
                    self.downloader.append_tasks(tasks, options=options, cookie_str=self._cookie_string)
                else:
                    if len(self.downloader.tasks) > 0 or self._queue_model.rowCount() > 0:
                        if not self.downloader.tasks and self._queue_model.tasks:
                            self.downloader.tasks = list(self._queue_model.tasks)
                        self._appendTasksSignal.emit(tasks)
                        self.downloader.append_tasks(tasks)
                        self.downloader.start_download_queue(
                            tasks=self.downloader.tasks,
                            options=options,
                            cookie_str=self._cookie_string
                        )
                    else:
                        self._setTasksSignal.emit(tasks)
                        self.downloader.start_download_queue(
                            tasks=tasks,
                            options=options,
                            cookie_str=self._cookie_string
                        )
            else:
                self._appendTasksSignal.emit(tasks)
                self.downloader.append_tasks(tasks)
                self._status_text = f"Queued {len(tasks)} files ({creator_name})."
                self.statusTextChanged.emit()

        except Exception as e:
            logger.error(f"Error during task initialization: {e}", category="downloader")
            self._is_downloading = False
            self._has_error = True
            self._last_error_message = str(e)
            self.isDownloadingChanged.emit()
            self.hasErrorChanged.emit()
            self.lastErrorMessageChanged.emit()

    @Slot()
    def checkRecoverySession(self):
        """Called by QML on completion to prompt for unfinished crash recovery if detected."""
        if self._has_recovery_session and self._recovery_summary:
            self.recoverySessionDetected.emit(self._recovery_summary)

    @Slot()
    def resumeRecoverySession(self):
        """
        Restores the interrupted download session from the crash-proof journal.
        Verifies already downloaded files on disk, updates the queue model,
        and seamlessly resumes downloading the remaining files.
        """
        checkpoint = self.recovery_manager.load_checkpoint()
        if not checkpoint:
            logger.warning("No recovery checkpoint found to resume.", category="session")
            return

        raw_tasks = checkpoint.get("tasks", [])
        if not raw_tasks:
            logger.warning("Recovery checkpoint contains no tasks.", category="session")
            return

        loaded_tasks: List[DownloadTask] = []
        for t_dict in raw_tasks:
            task = DownloadTask.from_dict(t_dict)
            # Disk verification to skip already downloaded files
            if os.path.exists(task.target_path):
                actual_sz = os.path.getsize(task.target_path)
                if task.file_size > 0 and actual_sz >= task.file_size:
                    task.status = "completed"
                    task.downloaded_bytes = task.file_size
                    task.progress_pct = 100
                elif actual_sz > 0:
                    task.downloaded_bytes = actual_sz
                    task.status = "pending"
            elif task.status in ("downloading", "retrying"):
                task.status = "pending"
            loaded_tasks.append(task)

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
        """Called when user closes the window — preserves active session and stops threads cleanly."""
        if self._is_downloading:
            logger.info("Application closing: saving active session and stopping threads...", category="system")
            if self._queue_model.tasks:
                self.recovery_manager.save_checkpoint(
                    tasks=self._queue_model.tasks,
                    batches=self._queue_model.groups,
                    settings=vars(self._get_filter_options()),
                    status="paused"
                )
            self.downloader.cancel()

    @Slot()
    def retryFailed(self):
        """Retries all failed tasks in the queue."""
        options = self._get_filter_options()
        self._is_downloading = True
        self.isDownloadingChanged.emit()

        if not self.downloader.tasks and self._queue_model.tasks:
            self.downloader.tasks = self._queue_model.getTasks()

        count = self.downloader.retry_failed_tasks(options, self._cookie_string)
        if count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._status_text = "Progress: Idle (no failed tasks)"
            self.statusTextChanged.emit()
        elif count > 0:
            logger.info(f"Retrying {count} failed tasks with {self._threads_count} worker threads...", category="downloader")

    @Slot("QVariantList")
    def retrySelectedTasks(self, selected_ids: list):
        """Retries only selected failed tasks."""
        options = self._get_filter_options()
        self._is_downloading = True
        self.isDownloadingChanged.emit()

        if not self.downloader.tasks and self._queue_model.tasks:
            self.downloader.tasks = self._queue_model.getTasks()

        count = self.downloader.retry_selected_tasks(selected_ids, options, self._cookie_string)
        if count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._status_text = "Progress: Idle (no selected tasks to retry)"
            self.statusTextChanged.emit()
        elif count > 0:
            logger.info(f"Retrying {count} selected tasks...", category="downloader")

    @Slot(str)
    def retrySingleTask(self, file_id: str):
        """Retries only a single specific failed task."""
        if not file_id:
            return
        options = self._get_filter_options()
        self._is_downloading = True
        self.isDownloadingChanged.emit()

        if not self.downloader.tasks and self._queue_model.tasks:
            self.downloader.tasks = self._queue_model.getTasks()

        count = self.downloader.retry_selected_tasks([file_id], options, self._cookie_string)
        if count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._status_text = "Progress: Idle"
            self.statusTextChanged.emit()
        elif count > 0:
            logger.info(f"Retrying single task: {file_id}", category="downloader")

    @Slot()
    def cancelDownload(self):
        # Signal workers to stop
        self._scan_cancel_event.set()
        self.downloader.cancel()
        self.cancelCloudDownloads()

        # Full session reset — clear all queue state so the next download starts fresh
        self._queued_links.clear()
        self._queue_model.setTasks([])
        self._active_queue_model.clear()
        self.downloader.reset_state()

        # Reset telemetry back to Idle / zero
        self._overall_progress = 0
        self.overallProgressChanged.emit()
        self._current_speed = "0 KB/s"
        self.currentSpeedChanged.emit()
        self._eta_text = "--"
        self.etaTextChanged.emit()
        self._saved_bytes_text = "0 MB"
        self.savedBytesTextChanged.emit()
        self._elapsed_time_text = "0s"
        self.elapsedTimeTextChanged.emit()
        self._files_count_text = ""
        self.filesCountTextChanged.emit()

        self._is_downloading = False
        self.isDownloadingChanged.emit()
        self.isPausedChanged.emit()
        self._status_text = "Progress: Cancelled"
        self.statusTextChanged.emit()

    @Slot()
    def pauseDownload(self):
        self.downloader.pause()
        self._cloud_pause_event.set()
        self._status_text = "Progress: Paused"
        self._current_speed = "0 KB/s"
        self._eta_text = "--"
        self.currentSpeedChanged.emit()
        self.etaTextChanged.emit()
        self.statusTextChanged.emit()
        self.isPausedChanged.emit()

    @Slot()
    def resumeDownload(self):
        self.downloader.resume()
        self._cloud_pause_event.clear()
        self._status_text = "Progress: Resumed"
        self.statusTextChanged.emit()
        self.isPausedChanged.emit()

    @Slot()
    def selectDownloadDirectory(self):
        folder = QFileDialog.getExistingDirectory(
            None,
            "Select Download Directory",
            self._download_dir
        )
        if folder:
            self.downloadDir = folder
            self.saveSettings()

    @Slot()
    def exportAllLinks(self):
        # In links-only mode, export the harvested external cloud links
        harvested = self.downloader.harvested_links
        if harvested:
            save_path, _ = QFileDialog.getSaveFileName(
                None,
                "Export Harvested Links",
                os.path.join(self._download_dir, "harvested_links.txt"),
                "Text Files (*.txt);;All Files (*)"
            )
            if not save_path:
                return

            lines = [
                f"Kemono Downloader — Harvested External Links",
                f"Exported: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 60,
                "",
            ]
            total = 0
            for platform, urls in sorted(harvested.items()):
                lines.append(f"[{platform.upper()}]  ({len(urls)} link(s))")
                for u in urls:
                    lines.append(f"  {u}")
                    total += 1
                lines.append("")
            lines.append(f"Total: {total} unique link(s)")

            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                logger.success(f"🔗 Exported {total} harvested link(s) to: {save_path}", category="session")
            except Exception as e:
                logger.error(f"Failed to export harvested links: {e}", category="session")
            return

        # Fallback: export raw download task URLs from the queue
        tasks = self._queue_model.getTasks()
        if not tasks:
            logger.warning("No harvested links or queued tasks to export.", category="session")
            return

        links = [t.url for t in tasks]
        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export Links",
            os.path.join(self._download_dir, "links_export.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        if save_path:
            self.session_manager.export_links_to_file(links, save_path)

    @Slot("QVariantList", str)
    def startCloudDownloads(self, selected_links: list, dest_folder: str = ""):
        """Downloads selected harvested cloud links (Mega, Drive, Dropbox, GoFile) with live progress telemetry."""
        if self._is_cloud_downloading or self._is_downloading:
            logger.warning("Download process is already running!", category="system")
            return

        if not selected_links:
            logger.warning("No links selected for cloud download.", category="downloader")
            return

        target_dir = dest_folder.strip() or self._download_dir
        os.makedirs(target_dir, exist_ok=True)

        self._is_cloud_downloading = True
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self._cloud_cancel_event.clear()
        self._cloud_pause_event.clear()

        def _worker():
            total = len(selected_links)
            concurrency = min(total, max(1, self._threads_count))
            logger.info(f"☁️ Starting concurrent cloud downloads for {total} link(s) ({concurrency} parallel streams) to: {target_dir}", category="downloader")
            self._status_text = f"Cloud Download: 0/{total} completed"
            self.statusTextChanged.emit()

            success_count = 0
            start_time = time.time()
            total_downloaded_bytes = 0
            progress_lock = threading.Lock()
            last_calc_time = time.time()
            last_calc_bytes = 0
            link_progress_map = {}

            def _process_link(idx, item):
                nonlocal success_count, total_downloaded_bytes, last_calc_time, last_calc_bytes
                if self._cloud_cancel_event.is_set():
                    return False

                url = item.get("url", "") if isinstance(item, dict) else str(item)
                title = item.get("title", "File") if isinstance(item, dict) else "Cloud File"
                platform = item.get("platform", "other").lower() if isinstance(item, dict) else "other"

                if "mega.nz" in url or "mega.co.nz" in url or "mega.io" in url:
                    platform = "mega"
                elif "drive.google.com" in url or "docs.google.com" in url or "drive.usercontent.google.com" in url:
                    platform = "gdrive"
                elif "dropbox.com" in url:
                    platform = "dropbox"
                elif "gofile.io" in url:
                    platform = "gofile"

                logger.info(f"☁️ [{platform.upper()}] Starting ({idx}/{total}): {url}", category="downloader")

                def _prog(fname, dl, tot, file_idx=1, file_tot=1):
                    nonlocal last_calc_time, last_calc_bytes
                    with progress_lock:
                        link_progress_map[idx] = {
                            "fname": fname,
                            "dl": dl,
                            "tot": tot,
                            "file_idx": file_idx,
                            "file_tot": file_tot,
                            "platform": platform
                        }
                        now = time.time()
                        dt = now - last_calc_time
                        current_total_dl = sum(p["dl"] for p in link_progress_map.values()) + total_downloaded_bytes

                        speed_str = ""
                        eta_str = "--"
                        if dt >= 0.5:
                            d_bytes = max(0, current_total_dl - last_calc_bytes)
                            speed = d_bytes / dt if dt > 0 else 0
                            last_calc_time = now
                            last_calc_bytes = current_total_dl
                            if speed > 1024 * 1024:
                                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                            elif speed > 1024:
                                speed_str = f"{speed / 1024:.0f} KB/s"
                            else:
                                speed_str = f"{speed:.0f} B/s"

                        # Calculate aggregated progress across all links
                        sum_fraction = 0.0
                        for l_idx in range(1, total + 1):
                            if l_idx in link_progress_map:
                                p = link_progress_map[l_idx]
                                f_tot = p["file_tot"]
                                f_idx = p["file_idx"]
                                f_dl = p["dl"]
                                f_t = p["tot"]
                                f_frac = (f_idx - 1 + (f_dl / f_t if f_t > 0 else 0)) / f_tot if f_tot > 0 else 0
                                sum_fraction += f_frac
                            elif l_idx < idx:
                                sum_fraction += 1.0

                        pct = int((sum_fraction / total) * 100) if total > 0 else 0
                        elapsed_sec = int(now - start_time)
                        elapsed_str = f"{elapsed_sec}s" if elapsed_sec < 60 else f"{elapsed_sec // 60}m {elapsed_sec % 60}s"
                        saved_mb = current_total_dl / (1024 * 1024)
                        saved_str = f"{saved_mb:.1f} MB" if saved_mb < 1024 else f"{saved_mb / 1024:.2f} GB"

                        if total == 1:
                            files_badge = f"{file_idx}/{file_tot}" if file_tot > 1 else "1/1"
                        else:
                            files_badge = f"{success_count}/{total} links"

                        status_msg = f"[{platform.upper()}] {fname}"
                        if tot > 0:
                            status_msg += f" ({dl // 1024 // 1024}MB / {tot // 1024 // 1024}MB)"

                        self._progressSignal.emit({
                            "percent": max(0, min(100, pct)),
                            "speed_str": speed_str or self._current_speed,
                            "eta_str": eta_str,
                            "saved_str": saved_str,
                            "elapsed_str": elapsed_str,
                            "files_count_text": files_badge,
                            "status_text": status_msg
                        })

                workers_per_link = max(1, min(self._threads_count, 8))
                ok = False
                try:
                    if platform == "mega":
                        ok = download_mega_link(url, target_dir, log_func=lambda msg: logger.info(msg, category="downloader"), progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, max_workers=workers_per_link)
                    elif platform in ("gdrive", "google drive"):
                        ok = download_gdrive_link(url, target_dir, log_func=lambda msg: logger.info(msg, category="downloader"), progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event)
                    elif platform == "dropbox":
                        ok = download_dropbox_link(url, target_dir, log_func=lambda msg: logger.info(msg, category="downloader"), progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event)
                    elif platform == "gofile":
                        ok = download_gofile_link(url, target_dir, log_func=lambda msg: logger.info(msg, category="downloader"), progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, max_workers=workers_per_link)
                    else:
                        logger.warning(f"Platform '{platform}' cannot be directly auto-downloaded (URL: {url}).", category="downloader")
                except Exception as ex:
                    logger.error(f"Error downloading {url}: {ex}", category="downloader")

                with progress_lock:
                    if ok:
                        success_count += 1
                        if idx in link_progress_map:
                            total_downloaded_bytes += link_progress_map[idx].get("tot", 0)

                return ok

            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=concurrency) as link_executor:
                futures = [link_executor.submit(_process_link, idx, item) for idx, item in enumerate(selected_links, 1)]
                for future in as_completed(futures):
                    if self._cloud_cancel_event.is_set():
                        for f in futures:
                            f.cancel()
                        break
                    try:
                        future.result()
                    except Exception:
                        pass

            self._is_cloud_downloading = False
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._overall_progress = 100 if success_count == total else int((success_count / total) * 100)
            self.overallProgressChanged.emit()
            self._status_text = f"Cloud Download completed: {success_count}/{total} succeeded."
            self.statusTextChanged.emit()
            logger.success(f"☁️ Cloud downloads finished: {success_count}/{total} succeeded.", category="downloader")

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def cancelCloudDownloads(self):
        if self._is_cloud_downloading:
            self._cloud_cancel_event.set()
            self._is_cloud_downloading = False
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            logger.warning("Cloud downloads cancellation requested.", category="downloader")



    @Slot()
    def exportLogs(self):
        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export Console Logs",
            os.path.join(self._download_dir, "kemono_console.log"),
            "Log Files (*.log *.txt);;All Files (*)"
        )
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(self._log_model.get_all_text())
                logger.success(f"Console logs exported to: {save_path}", category="logger")
            except Exception as e:
                logger.error(f"Failed to export console logs: {e}", category="logger")

    @Slot()
    def clearLogs(self):
        self._log_model.clearLogs()

    @Slot()
    def openLogsFolder(self):
        logs_dir = logger.get_logs_dir()
        os.makedirs(logs_dir, exist_ok=True)
        if os.name == "nt":
            os.startfile(logs_dir)
        else:
            subprocess.Popen(["xdg-open", logs_dir])

    @Slot()
    def openDownloadFolder(self):
        os.makedirs(self._download_dir, exist_ok=True)
        if os.name == "nt":
            os.startfile(self._download_dir)
        else:
            subprocess.Popen(["xdg-open", self._download_dir])

    @Slot()
    def openKnownTxt(self):
        path = self.known_manager.file_path
        if not os.path.exists(path):
            self.known_manager.save()
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])

    @Slot(str)
    def addKnownCharacter(self, name: str):
        if self._known_model.addEntry(name):
            logger.success(f"Added '{name}' to Known list.", category="known")

    @Slot(int)
    def removeKnownCharacter(self, index: int):
        self._known_model.removeIndex(index)

    @Slot(str)
    def applyCharacterToFilter(self, name: str):
        if not self._filter_characters:
            self.filterCharacters = name
        else:
            parts = [p.strip() for p in self._filter_characters.split(",") if p.strip()]
            if name not in parts:
                parts.append(name)
                self.filterCharacters = ", ".join(parts)
        logger.info(f"Added '{name}' to character filter.", category="filter")

    @Slot(str, result=int)
    def batchLoadUrls(self, input_text_or_path: str) -> int:
        """
        Parses multiple URLs from a file path or pasted multi-line text and queues them.
        """
        if os.path.exists(input_text_or_path):
            urls, err = BatchLoader.load_urls_from_file(input_text_or_path)
            if err:
                logger.error(err, category="batch")
                return 0
        else:
            urls = BatchLoader.parse_urls_from_text(input_text_or_path)

        if not urls:
            logger.warning("No valid URLs found in batch input.", category="batch")
            return 0

        logger.info(f"Loaded {len(urls)} URLs for batch processing.", category="batch")
        for u in urls:
            parsed = KemonoURLParser.parse(u)
            if parsed.is_valid:
                link_type, identity_key, parent_artist_key, display_name = self._get_link_identity(parsed)
                if identity_key in self._queued_links:
                    logger.warning(f"Skipping duplicate {link_type}: {display_name} is already in queue.", category="batch")
                    continue
                if parent_artist_key and parent_artist_key in self._queued_links:
                    logger.info(f"Skipping post: entire artist ({parsed.user_id}) is already in queue.", category="batch")
                    continue
                self._queued_links.add(identity_key)
                threading.Thread(
                    target=self._async_fetch_and_start,
                    args=(parsed, False),
                    daemon=True
                ).start()
            else:
                logger.warning(f"Skipped invalid URL in batch: {u}", category="batch")
        return len(urls)

    @Slot(result=str)
    def exportExtractedLinks(self) -> str:
        """
        Exports extracted external links to a user-chosen text file.
        """
        tasks = self._queue_model.tasks
        if not tasks:
            return ""

        all_text = ""
        for t in tasks:
            if t.url:
                all_text += f"{t.url}\n"

        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export External Links",
            os.path.join(self._download_dir, "extracted_links.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(all_text)
                logger.success(f"Links exported to: {save_path}", category="file")
                return save_path
            except Exception as e:
                logger.error(f"Failed to export links: {e}", category="file")
        return ""

    @Slot(list, result=str)
    def exportFailedTasks(self, selected_file_ids: list = None) -> str:
        """
        Exports failed tasks with direct download links, post links, filenames, and error details
        to a user-chosen text file for manual verification and testing.
        """
        all_failed = [t for t in self._queue_model.tasks if t.status == "failed"]
        if not all_failed:
            logger.warning("No failed tasks to export.", category="session")
            return ""

        if selected_file_ids:
            sel_set = set(str(x) for x in selected_file_ids if x)
            tasks_to_export = [
                t for t in all_failed
                if t.file_id in sel_set or t.url in sel_set or t.filename in sel_set
            ]
            if not tasks_to_export:
                tasks_to_export = all_failed
        else:
            tasks_to_export = all_failed

        import datetime
        default_name = f"failed_downloads_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export Failed Download Links & Post URLs",
            os.path.join(self._download_dir, default_name),
            "Text Files (*.txt);;All Files (*.*)"
        )
        if not save_path:
            return ""

        try:
            lines = [
                "=" * 80,
                "Pawchive Downloader — Failed Downloads Manual Inspection & Links Export",
                f"Export Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Total Failed Tasks Exported: {len(tasks_to_export)}",
                "=" * 80,
                "",
            ]

            for idx, t in enumerate(tasks_to_export, 1):
                p_url = getattr(t, "post_url", "") or ""
                if not p_url and t.service and t.post_id:
                    p_url = f"https://pawchive.pw/{t.service}/user/{t.creator_name}/post/{t.post_id}"

                lines.append(f"[{idx}] File: {t.filename}")
                lines.append(f"    File Size: {self._queue_model._format_size(t.file_size)}")
                lines.append(f"    Post Title: {t.post_title or 'Untitled'}")
                lines.append(f"    Post ID: {t.post_id or 'N/A'}")
                lines.append(f"    Creator: {t.creator_name or 'Unknown'} [{t.service or 'N/A'}]")
                lines.append(f"    Post Link: {p_url or 'N/A'}")
                lines.append(f"    Direct Download Link: {t.url}")
                lines.append(f"    Target Destination: {t.target_path}")
                lines.append(f"    Error Reason: {t.error_msg or 'Download failed'}")
                lines.append(f"    Retries Attempted: {getattr(t, 'retry_count', 0)}")
                if getattr(t, "fallback_urls", None):
                    lines.append(f"    Alternative Mirror URLs:")
                    for fb in t.fallback_urls[:3]:
                        lines.append(f"      - {fb}")
                lines.append("")

            lines.extend([
                "=" * 80,
                "RAW DIRECT DOWNLOAD URLS (For curl / wget / browser / download manager):",
                "=" * 80,
            ])
            for t in tasks_to_export:
                if t.url:
                    lines.append(t.url)

            lines.extend([
                "",
                "=" * 80,
                "RAW CANONICAL POST URLS (For browser inspection):",
                "=" * 80,
            ])
            post_urls_seen = set()
            for t in tasks_to_export:
                p_url = getattr(t, "post_url", "") or ""
                if not p_url and t.service and t.post_id:
                    p_url = f"https://pawchive.pw/{t.service}/user/{t.creator_name}/post/{t.post_id}"
                if p_url and p_url not in post_urls_seen:
                    post_urls_seen.add(p_url)
                    lines.append(p_url)

            lines.append("")

            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            logger.success(f"📤 Exported {len(tasks_to_export)} failed link(s) to: {save_path}", category="session")
            return save_path
        except Exception as e:
            logger.error(f"Failed to export failed links: {e}", category="session")
            return ""

    @Slot(result=str)
    def exportAllFailedTasks(self) -> str:
        """Convenience slot to export all failed tasks without filtering."""
        return self.exportFailedTasks([])

    @Slot()
    def saveSettings(self):
        settings_dict = {
            "download_dir": self._download_dir,
            "threads": self._threads_count,
            "cookie": self._cookie_string,
            "user_agent": self._user_agent,
            "page_start": self._page_start,
            "page_end": self._page_end,
            "character_scope": self._character_scope,
            "skip_scope": self._skip_scope,
            "subfolder_per_post": self._subfolder_per_post,
            "date_prefix": self._date_prefix,
            "file_index_prefix": self._file_index_prefix,
            "separate_by_known": self._separate_folders_by_known,
            "download_revisions": self._download_revisions,
            "adaptive_threading": self._adaptive_threading,
            "threads_locked": self._threads_locked,
            "auto_retry_at_end": self._auto_retry_at_end,
            "manga_mode": self._manga_mode,
            "filename_style": self._filename_style,
            "proxy_url": self._proxy_url,
            "compress_webp": self._compress_webp,
            "keep_duplicates": self._keep_duplicates,
            "scan_content_images": self._scan_content_images,
            "download_delay": self._download_delay,
            "save_post_metadata": self._save_post_metadata,
            "download_embeds": self._download_embeds,
            "open_folder_on_complete": self._open_folder_on_complete,
            "play_completion_sound": self._play_completion_sound,
            "generate_desktop_report": self._generate_desktop_report,
            "post_download_action": "none",
            "known_recognition_mode": self._known_recognition_mode,
            "language": self._language,
            "console_width": self._console_width,
            "tag_folder_mode": self._tag_folder_mode
        }
        self.session_manager.save_settings(settings_dict, silent=True)

    # ── Thread-safe downloader event handlers ─────────────────────────────────
    # These slots run on the MAIN thread (via QueuedConnection) so it is safe
    # to read/write Qt properties and update models here.

    @Slot(dict)
    def _handle_progress(self, info: Dict[str, Any]):
        completed = info.get("completed", 0)
        total     = info.get("total", 0)
        failed    = info.get("failed", 0)
        self._overall_progress   = info.get("percent", info.get("progress", 0))
        self._saved_bytes_text   = info.get("saved_str", "0 MB")
        if self.downloader._pause_event.is_set():
            self._status_text = "Progress: Paused"
            self._current_speed = "0 KB/s"
            self._eta_text = "--"
        else:
            self._current_speed = info.get("speed_str", "0 KB/s")
            self._eta_text      = info.get("eta_str", "--")
            self._status_text   = info.get("status_text", f"Downloading\u2026 {completed}/{total}")
        self._files_count_text   = info.get("files_count_text") if info.get("files_count_text") else (f"{completed}/{total}" if total > 0 else "")
        self._adaptive_state     = info.get("adaptive_state", "optimal")
        self._adaptive_status_text = info.get("adaptive_status_text", "")
        self._elapsed_time_text  = info.get("elapsed_str", "0s")

        self.overallProgressChanged.emit()
        self.currentSpeedChanged.emit()
        self.etaTextChanged.emit()
        self.savedBytesTextChanged.emit()
        self.statusTextChanged.emit()
        self.filesCountTextChanged.emit()
        self.adaptiveStateChanged.emit()
        self.adaptiveStatusTextChanged.emit()
        self.elapsedTimeTextChanged.emit()

    @Slot(object)
    def _handle_task_status(self, task: DownloadTask):
        self._queue_model.updateTask(task)
        self._active_queue_model.updateTask(task)

    @Slot(int)
    def _handle_throttled(self, new_count: int):
        self._threads_count = new_count
        self.threadsCountChanged.emit()
        logger.info(f"UI concurrency slider auto-throttled to {new_count} threads due to rate limiting.", category="system")

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

    @Slot(str)
    def _handle_batch_cancel(self, batch_id: str):
        self.downloader.cancel_batch(batch_id)

    @Slot(str)
    def _handle_batch_retry(self, batch_id: str):
        options = self._get_filter_options()
        self.downloader.retry_batch_failed(batch_id, options=options, cookie_str=self._cookie_string)

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
        logger.info("Download queue cleared.", category="queue")

    @Slot()
    def exportQueueState(self):
        """
        Safely freezes active downloads, serializes queue state with human-readable summary,
        and prompts the user whether to keep downloads stopped or resume.
        """
        import datetime
        import json
        was_downloading = self.downloader._is_running and not self.downloader._pause_event.is_set()
        if was_downloading:
            logger.info("Auto-pausing active downloads to safely freeze queue state for export...", category="session")
            self.downloader.pause()
            time.sleep(0.2)  # Allow socket buffers and chunk writers to flush cleanly

        default_name = f"Pawchive_Queue_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export Queue State Snapshot",
            os.path.join(self._download_dir, default_name),
            "JSON Files (*.json);;All Files (*.*)"
        )

        if not save_path:
            # User cancelled the file dialog
            if was_downloading:
                logger.info("Export cancelled — resuming downloads.", category="session")
                self.downloader.resume()
            return

        try:
            all_tasks = self._queue_model.tasks
            completed_count = sum(1 for t in all_tasks if t.status == "completed")
            failed_count = sum(1 for t in all_tasks if t.status == "failed")
            pending_count = sum(1 for t in all_tasks if t.status in ("pending", "cancelled"))
            downloading_count = sum(1 for t in all_tasks if t.status in ("downloading", "retrying"))

            total_bytes_sum = sum(max(t.file_size, t.downloaded_bytes) for t in all_tasks)
            downloaded_bytes_sum = sum(t.downloaded_bytes for t in all_tasks)
            overall_pct = (downloaded_bytes_sum / total_bytes_sum * 100.0) if total_bytes_sum > 0 else (100.0 if completed_count == len(all_tasks) and all_tasks else 0.0)

            unique_creators = sorted(list(set(t.creator_name for t in all_tasks if t.creator_name)))
            unique_sources = sorted(list(set(t.url for t in all_tasks if t.url)))

            snapshot = {
                "_summary": {
                    "title": "Pawchive Downloader Queue State Backup",
                    "app_version": "1.0.6",
                    "exported_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "creators": unique_creators,
                    "total_batches": len(self._queue_model.groups),
                    "total_files": len(all_tasks),
                    "completed_files": completed_count,
                    "pending_files": pending_count + downloading_count,
                    "failed_files": failed_count,
                    "overall_progress": f"{overall_pct:.1f}%",
                    "current_saved_data": self._queue_model._format_size(downloaded_bytes_sum),
                    "total_queue_data": self._queue_model._format_size(total_bytes_sum),
                    "destination_directory": self._download_dir
                },
                "settings": {
                    "download_dir": self._download_dir,
                    "threads": self._threads_count,
                    "cookie": self._cookie_string,
                    "user_agent": self._user_agent,
                    "manga_mode": self._manga_mode,
                    "subfolder_per_post": self._subfolder_per_post,
                    "date_prefix": self._date_prefix,
                    "file_index_prefix": self._file_index_prefix,
                    "separate_by_known": self._separate_folders_by_known
                },
                "batches": self._queue_model.groups,
                "tasks": [t.to_dict() for t in all_tasks]
            }

            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)

            logger.success(f"Queue snapshot exported successfully to: {save_path}", category="session")
            self.exportCompleted.emit(save_path, was_downloading)

        except Exception as e:
            logger.error(f"Failed to export queue state: {e}", category="session")
            if was_downloading:
                self.downloader.resume()
            self.exportFailed.emit(str(e))

    @Slot()
    def resumeAfterExport(self):
        """Called if user clicks 'Resume Downloading' on the post-export modal."""
        self.downloader.resume()
        self._status_text = "Downloading resumed."
        self.statusTextChanged.emit()
        self.isPausedChanged.emit()

    @Slot()
    def stopAfterExport(self):
        """Called if user clicks 'Keep Stopped / Exit Ready' on the post-export modal."""
        self.downloader.pause()
        self._status_text = "Downloads paused (Safe to exit or shut down)."
        self.statusTextChanged.emit()
        self.isPausedChanged.emit()

    @Slot(str)
    def importQueueState(self, merge_mode: str = "merge"):
        """
        Loads a saved queue snapshot file, verifies existing files on disk,
        and merges or replaces the current queue.
        """
        import json
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Import Queue State Snapshot",
            self._download_dir,
            "JSON Files (*.json);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_tasks = data.get("tasks", [])
            if not raw_tasks and not isinstance(raw_tasks, list):
                raise ValueError("The selected JSON file does not contain a valid 'tasks' list.")

            loaded_tasks: List[DownloadTask] = []
            for t_dict in raw_tasks:
                task = DownloadTask.from_dict(t_dict)
                # Disk verification
                if os.path.exists(task.target_path):
                    actual_sz = os.path.getsize(task.target_path)
                    if task.file_size > 0 and actual_sz >= task.file_size:
                        task.status = "completed"
                        task.downloaded_bytes = task.file_size
                    elif actual_sz > 0:
                        task.downloaded_bytes = actual_sz
                        task.status = "pending"
                elif task.status == "downloading":
                    task.status = "pending"
                loaded_tasks.append(task)

            if merge_mode == "replace":
                self._queue_model.setTasks(loaded_tasks)
                self._active_queue_model.setTasks(loaded_tasks)
                self.downloader.tasks = list(loaded_tasks)
            else:
                self._queue_model.appendTasks(loaded_tasks)
                self._active_queue_model.appendTasks(loaded_tasks)
                self.downloader.append_tasks(loaded_tasks)

            creators = set(t.creator_name for t in loaded_tasks if t.creator_name)
            logger.success(
                f"Successfully imported {len(loaded_tasks)} tasks ({len(creators)} creators) from: {os.path.basename(file_path)}",
                category="session"
            )
            self._status_text = f"Imported {len(loaded_tasks)} tasks from backup."
            self.statusTextChanged.emit()
            self.importCompleted.emit(len(loaded_tasks), len(creators))

        except Exception as e:
            logger.error(f"Failed to import queue state: {e}", category="session")
            self.importFailed.emit(str(e))

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
            elif action == "shutdown":
                if sys.platform == "win32":
                    subprocess.run(["shutdown", "/s", "/f", "/t", "5", "/c", "Pawchive Downloader: shutting down..."], check=False)
                elif sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", 'tell app "System Events" to shut down'], check=False)
                else:
                    subprocess.run(["shutdown", "-h", "-f", "now"], check=False)
            elif action == "restart":
                if sys.platform == "win32":
                    subprocess.run(["shutdown", "/r", "/f", "/t", "5", "/c", "Pawchive Downloader: restarting..."], check=False)
                elif sys.platform == "darwin":
                    subprocess.run(["osascript", "-e", 'tell app "System Events" to restart'], check=False)
                else:
                    subprocess.run(["shutdown", "-r", "-f", "now"], check=False)
            elif action == "sleep":
                if sys.platform == "win32":
                    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)
                elif sys.platform == "darwin":
                    subprocess.run(["pmset", "sleepnow"], check=False)
                else:
                    subprocess.run(["systemctl", "suspend"], check=False)
            elif action == "hibernate":
                if sys.platform == "win32":
                    subprocess.run(["shutdown", "/h", "/f"], check=False)
                elif sys.platform == "darwin":
                    subprocess.run(["pmset", "sleepnow"], check=False)
                else:
                    subprocess.run(["systemctl", "hibernate"], check=False)
        except Exception as e:
            logger.error(f"Failed to execute post-download action '{action}': {e}", category="system")

    @Slot(bool, str)
    def _handle_finished(self, success: bool, message: str):
        self._is_downloading = False
        self._active_queue_model.clear()
        
        # Calculate actual completed percentage
        tasks = self._queue_model.getTasks()
        if tasks:
            completed_c = sum(1 for t in tasks if t.status == "completed")
            failed_c = sum(1 for t in tasks if t.status == "failed")
            self._overall_progress = int(completed_c / len(tasks) * 100)
            if failed_c > 0:
                self._status_text = f"Finished with {failed_c} error(s) ({completed_c}/{len(tasks)} completed)"
            else:
                self._overall_progress = 100
                self._status_text = f"Completed ({completed_c}/{len(tasks)} files)"
        else:
            self._overall_progress = 100 if success else self._overall_progress
            self._status_text = f"Progress: {message}"

        self.isDownloadingChanged.emit()
        self.isPausedChanged.emit()
        self.overallProgressChanged.emit()
        self.statusTextChanged.emit()
        if not success:
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

            # 4. Auto-add / update completed artist in watchlist
            try:
                tasks_done = self._queue_model.getTasks()
                if tasks_done:
                    # Group completed tasks by (service, user_id or creator_name)
                    grouped = {}
                    for _t in tasks_done:
                        svc = getattr(_t, "service", "").strip().lower()
                        uid = (getattr(_t, "user_id", "") or getattr(_t, "creator_name", "")).strip().lower()
                        if svc and uid:
                            key = (svc, uid)
                            if key not in grouped:
                                grouped[key] = []
                            grouped[key].append(_t)

                    for (svc, uid), c_tasks in grouped.items():
                        c_latest_date = ""
                        c_latest_pid = ""
                        for _t in c_tasks:
                            t_date = getattr(_t, "post_date", "") or ""
                            t_pid = getattr(_t, "post_id", "") or ""
                            if t_date and t_date > c_latest_date:
                                c_latest_date = t_date
                                c_latest_pid = t_pid
                            elif t_date == c_latest_date and t_pid > c_latest_pid:
                                c_latest_pid = t_pid

                        existing = self._watchlist_manager._find(uid, svc)
                        if not existing:
                            t0 = c_tasks[0]
                            existing = next((e for e in self._watchlist_manager.entries if e.service.lower() == svc and (e.creator_name.lower() == t0.creator_name.lower() or e.user_id.lower() == t0.creator_name.lower())), None)

                        if existing:
                            if c_latest_date or c_latest_pid:
                                self._watchlist_manager.update_last_download(
                                    existing.user_id, existing.service,
                                    c_latest_pid or existing.last_post_id,
                                    c_latest_date or existing.last_post_date
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

                    url_clean = (self._current_url or "").strip()
                    from core.parser import KemonoURLParser
                    _parsed = KemonoURLParser.parse(url_clean) if url_clean else None
                    if _parsed and _parsed.is_valid and not _parsed.is_external_provider and not _parsed.is_single_post:
                        c_tasks = grouped.get((_parsed.service.lower(), _parsed.user_id.lower()), tasks_done)
                        t_dir = self.extract_artist_folder_from_path(
                            c_tasks[0].target_path,
                            self._creator_name or _parsed.user_id,
                            _parsed.service,
                            fallback_dir=self._download_dir
                        )
                        self._watchlist_manager.add_entry(
                            url=url_clean,
                            creator_name=self._creator_name or _parsed.user_id,
                            user_id=_parsed.user_id,
                            service=_parsed.service,
                            domain=_parsed.domain,
                            last_post_id=c_latest_pid if 'c_latest_pid' in locals() else "",
                            last_post_date=c_latest_date if 'c_latest_date' in locals() else "",
                            download_dir=t_dir,
                            options=self._get_filter_options().to_dict(),
                        )

                    self._watchlist_model.refresh()
                    self.watchlistChanged.emit()
            except Exception as e:
                logger.debug(f"Watchlist update error on finish: {e}", category="watchlist")


    def _async_resolve_creator_name(self, parsed: URLParseResult):
        try:
            if parsed.is_external_provider:
                if parsed.provider == "bunkr":
                    album_title, _ = fetch_bunkr_album(parsed.raw_url, resolve_files=False)
                    if album_title:
                        self._creatorSignal.emit(clean_text(album_title))
                elif parsed.provider == "erome":
                    album_title, _ = fetch_erome_album(parsed.raw_url)
                    if album_title:
                        self._creatorSignal.emit(clean_text(album_title))
                elif parsed.provider == "nhentai":
                    gallery_title, _ = fetch_nhentai_gallery(parsed.post_id or parsed.raw_url)
                    if gallery_title:
                        self._creatorSignal.emit(clean_text(gallery_title))
                elif parsed.provider == "saint2":
                    self._creatorSignal.emit(clean_text(parsed.user_id))
            else:
                profile = self.api_client.fetch_creator_profile(parsed)
                name = profile.get("displayName") or profile.get("name") or profile.get("user") or profile.get("username") or parsed.user_id
                if name:
                    self._creatorSignal.emit(clean_text(str(name)))
        except Exception:
            pass

    @Slot(str)
    def _handle_creator_resolved(self, name: str):
        cleaned = clean_text(name)
        if cleaned and self._creator_name != cleaned:
            self._creator_name = cleaned
            self.creatorNameChanged.emit()

    # ── Watchlist Slots ────────────────────────────────────────────────────────

    @Slot(str, str)
    def removeFromWatchlist(self, userId: str, service: str):
        """Remove an entry from the watchlist by userId + service."""
        self._watchlist_manager.remove_entry(userId, service)
        self._watchlist_model.refresh()
        self.watchlistChanged.emit()

    @Slot()
    def checkWatchlist(self):
        """Asynchronously check all watchlist entries for new posts."""
        self.watchlistCheckStarted.emit()
        threading.Thread(target=self._async_watchlist_check, daemon=True).start()

    @Slot(str, str)
    def checkWatchlistArtist(self, userId: str, service: str):
        """Asynchronously check a single watchlist artist for new posts."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            logger.warning(f"checkWatchlistArtist: entry not found for {userId}/{service}", category="watchlist")
            return

        self.watchlistArtistChecking.emit(userId, service, True)

        def _run():
            try:
                new_posts = self._watchlist_manager.get_posts_since(entry, self.api_client)
                count = len(new_posts)
                entry.new_post_count = count
            except Exception as e:
                logger.warning(f"Watchlist check error for {entry.creator_name!r}: {e}", category="watchlist")
                count = 0
            self._watchlistArtistResultSignal.emit(userId, service, count)

        threading.Thread(target=_run, daemon=True).start()

    def resolve_artist_download_dir(self, entry) -> str:
        """
        Return the exact directory to download an artist into:
        1. If entry.download_dir is set and non-empty, resolve it (ensuring no duplicate creator folder).
        2. Otherwise, construct the default path inside self._download_dir: os.path.join(self._download_dir, f"{clean_c} [{service}]").
        """
        from core.filter_engine import FilterEngine
        clean_c = FilterEngine.clean_filesystem_text(entry.creator_name or entry.user_id, max_len=80, fallback="creator")
        expected_folder = f"{clean_c} [{entry.service}]"

        target = (getattr(entry, "download_dir", "") or "").strip()
        if target:
            return self.resolve_artist_download_dir_for_folder(target, entry.creator_name or entry.user_id, entry.service)

        # Default fallback: inside self._download_dir
        base_dir = self._download_dir or os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads")
        return os.path.join(base_dir, expected_folder)

    def resolve_artist_download_dir_for_folder(self, folder: str, creator_name: str, service: str) -> str:
        r"""
        Resolves a selected or configured folder to ensure it points directly to the creator's folder:
        - If folder basename already matches creator or creator [service], return folder as-is.
        - If an existing subfolder matching the creator exists inside folder, return that subfolder.
        - Otherwise, if folder is a parent directory (e.g. D:\Archive), assign folder/creator [service].
        """
        from core.filter_engine import FilterEngine
        clean_c = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")
        expected_folder = f"{clean_c} [{service}]"
        folder = os.path.normpath(folder)
        base = os.path.basename(folder)
        if base.lower() == expected_folder.lower() or base.lower() == clean_c.lower() or (service and base.lower().startswith(f"{clean_c.lower()} [")):
            return folder
        cand1 = os.path.join(folder, expected_folder)
        if os.path.exists(cand1):
            return cand1
        cand2 = os.path.join(folder, clean_c)
        if os.path.exists(cand2):
            return cand2
        return os.path.join(folder, expected_folder)

    def extract_artist_folder_from_path(self, sample_path: str, creator_name: str, service: str, fallback_dir: str = "") -> str:
        """
        Safely walk up parent directories from a sample file target path to locate
        the creator folder, completely avoiding cross-drive ValueError from os.path.relpath.
        """
        from core.filter_engine import FilterEngine
        clean_c = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")
        expected = f"{clean_c} [{service}]".lower()
        clean_lower = clean_c.lower()

        try:
            curr = os.path.dirname(os.path.abspath(sample_path))
            while curr and curr != os.path.dirname(curr):
                base = os.path.basename(curr).lower()
                if base == expected or base == clean_lower or (service and base.startswith(f"{clean_lower} [")):
                    return curr
                curr = os.path.dirname(curr)
        except Exception:
            pass

        return fallback_dir or (os.path.dirname(sample_path) if sample_path else self._download_dir)

    @Slot(str, str)
    @Slot(str, str, "QVariantList")
    def downloadNewPosts(self, userId: str, service: str, postIds: Optional[list] = None):
        """Queue only posts newer than the last_post_date for the given artist, reusing saved settings."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            logger.warning(f"downloadNewPosts: entry not found for {userId}/{service}", category="watchlist")
            return
        if entry.new_post_count == 0 and not postIds:
            logger.info(f"No new posts queued for {entry.creator_name!r} — all up to date.", category="watchlist")
            return

        def _run():
            new_posts = self._watchlist_manager.get_posts_since(entry, self.api_client)
            if not new_posts:
                logger.info(f"No new posts found for {entry.creator_name!r}.", category="watchlist")
                return

            # If specific postIds were requested (selective download), filter to only those
            if postIds:
                p_set = set(str(pid) for pid in postIds)
                new_posts = [p for p in new_posts if str(p.get("id")) in p_set]
                if not new_posts:
                    logger.info(f"None of the requested posts for {entry.creator_name!r} were available.", category="watchlist")
                    return

            # Reuse saved settings if present, otherwise fallback to current UI settings
            from core.filter_engine import FilterOptions
            if entry.options:
                options = FilterOptions.from_dict(entry.options)
            else:
                options = self._get_filter_options()

            artist_folder = self.resolve_artist_download_dir(entry)
            # Ensure the entry knows its download_dir if it was previously empty
            if not entry.download_dir:
                entry.download_dir = artist_folder
                self._watchlist_manager.save()
                self._watchlist_model.refresh()
                self.watchlistChanged.emit()

            tasks = self.downloader.build_tasks_from_posts(
                posts=new_posts,
                creator_name=entry.creator_name,
                service=entry.service,
                domain=entry.domain,
                base_dir=self._download_dir,
                options=options,
                batch_id=f"watchlist_{entry.service}_{entry.user_id}",
                artist_dir=artist_folder,
                user_id=entry.user_id
            )

            # Auto-harvest new posts' cloud links into permanent Link Vault
            self._auto_harvest_posts_to_vault(
                posts=new_posts,
                creator_name=entry.creator_name,
                domain=entry.domain,
                service=entry.service,
                user_id=entry.user_id
            )
            if tasks:
                self._appendTasksSignal.emit(tasks)
                self.downloader.append_tasks(tasks, options=options, cookie_str=self._cookie_string)
                if not self._is_downloading and self.downloader._is_running:
                    self._is_downloading = True
                    self.isDownloadingChanged.emit()
                    self._status_text = f"Downloading updates for {entry.creator_name}..."
                    self.statusTextChanged.emit()
                logger.success(
                    f"Watchlist: queued {len(tasks)} new file(s) for {entry.creator_name!r} at {artist_folder}.",
                    category="watchlist"
                )

        threading.Thread(target=_run, daemon=True).start()

    @Slot()
    def downloadAllNewPosts(self):
        """Batch download new posts for all watchlist artists with pending updates."""
        updated_entries = [e for e in self._watchlist_manager.entries if (getattr(e, "new_post_count", 0) or 0) > 0]
        if not updated_entries:
            logger.info("No watchlist artists have pending updates.", category="watchlist")
            return
        logger.info(f"Queueing updates for {len(updated_entries)} watchlist creator(s)...", category="watchlist")
        for e in updated_entries:
            self.downloadNewPosts(e.user_id, e.service)

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def addArtistToWatchlist(self, url: str, custom_download_dir: str = "") -> bool:
        """
        Manually add an artist to the watchlist by URL without downloading past posts.
        Fetches the latest post to set cutoff point so only future posts are considered new.
        """
        raw_url = (url or "").strip()
        if not raw_url:
            return False
        from core.parser import KemonoURLParser
        parsed = KemonoURLParser.parse(raw_url)
        if not parsed.is_valid:
            logger.warning(f"Cannot add to watchlist: invalid URL ({raw_url})", category="watchlist")
            return False

        creator_name = self.api_client.resolve_creator_name(parsed) or parsed.user_id
        target_dir = ""
        if custom_download_dir:
            target_dir = self.resolve_artist_download_dir_for_folder(custom_download_dir, creator_name, parsed.service)
        else:
            from core.filter_engine import FilterEngine
            clean_c = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")
            target_dir = os.path.join(self._download_dir, f"{clean_c} [{parsed.service}]")

        # Fetch page 1 to set latest post id and date as cutoff
        latest_pid = ""
        latest_pdate = ""
        try:
            posts = self.api_client.fetch_user_posts(parsed, page_start=1, page_end=1, page_size=10)
            if posts:
                p0 = posts[0]
                latest_pid = str(p0.get("id", ""))
                pub = p0.get("published") or p0.get("added") or ""
                if isinstance(pub, (int, float)):
                    try:
                        latest_pdate = datetime.datetime.fromtimestamp(pub).strftime("%Y-%m-%d")
                    except Exception:
                        latest_pdate = ""
                else:
                    p_str = str(pub)
                    latest_pdate = p_str.split("T")[0] if "T" in p_str else (p_str[:10] if p_str else "")
        except Exception as e:
            logger.debug(f"Could not fetch latest post for new artist: {e}", category="watchlist")

        canonical_url = getattr(parsed, "raw_url", "") or f"https://{parsed.domain}/{parsed.service}/user/{parsed.user_id}"
        options_dict = self._get_filter_options().to_dict()

        created = self._watchlist_manager.add_entry(
            url=canonical_url,
            creator_name=creator_name,
            user_id=parsed.user_id,
            service=parsed.service,
            domain=parsed.domain,
            last_post_id=latest_pid,
            last_post_date=latest_pdate,
            download_dir=target_dir,
            options=options_dict,
        )
        self._watchlist_model.refresh()
        self.watchlistChanged.emit()
        logger.success(f"Added {creator_name!r} [{parsed.service}] to watchlist (tracking new posts).", category="watchlist")
        return True

    @Slot(str, str, str)
    def ignoreWatchlistPost(self, userId: str, service: str, postId: str):
        """Ignore a specific post for an artist so it won't be downloaded."""
        if self._watchlist_manager.ignore_post(userId, service, postId):
            self._watchlist_model.update_new_counts()
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()

    @Slot(str, str, str)
    def unignoreWatchlistPost(self, userId: str, service: str, postId: str):
        """Unignore a previously ignored post for an artist."""
        if self._watchlist_manager.unignore_post(userId, service, postId):
            self._watchlist_model.update_new_counts()
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()

    @Slot(str, str)
    def unignoreAllWatchlistPosts(self, userId: str, service: str):
        """Unignore all posts for an artist and re-check."""
        if self._watchlist_manager.unignore_all(userId, service):
            self._watchlist_model.update_new_counts()
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()
            self.checkWatchlistArtist(userId, service)

    @Slot(str, str)
    def ignoreCurrentNewPosts(self, userId: str, service: str):
        """Ignore all currently discovered new posts for this artist."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return
        if entry.cached_new_posts:
            for p in list(entry.cached_new_posts):
                pid = str(p.get("id", "")).strip()
                if pid:
                    self._watchlist_manager.ignore_post(userId, service, pid)
        if entry.cached_new_posts:
            latest = entry.cached_new_posts[-1]
            entry.last_post_id = str(latest.get("id", "")) or entry.last_post_id
            pub = latest.get("published") or latest.get("added") or ""
            d_str = str(pub).split("T")[0] if "T" in str(pub) else str(pub)[:10]
            if d_str:
                entry.last_post_date = d_str
        entry.new_post_count = 0
        entry.cached_new_posts = []
        self._watchlist_manager.save()
        self._watchlist_model.update_new_counts()
        self._watchlist_model.refresh()
        self.watchlistChanged.emit()
        logger.info(f"Ignored current updates for {entry.creator_name!r}.", category="watchlist")

    @Slot(str, str)
    def redownloadWatchlistEntry(self, userId: str, service: str):
        """Re-queue the full download for a watched artist (all posts, not just new)."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return
        # Reuse currentUrl approach — set the URL and fire startDownload flow
        self._current_url = entry.url
        self.currentUrlChanged.emit()
        self.startDownload()

    @Slot(str, str, bool)
    def setWatchlistAutoCheck(self, userId: str, service: str, enabled: bool):
        """Toggle per-entry auto-check on startup."""
        self._watchlist_manager.set_auto_check(userId, service, enabled)
        self._watchlist_model.refresh()
        self.watchlistChanged.emit()

    @Slot(str, str, str)
    def setWatchlistDownloadDir(self, userId: str, service: str, download_dir: str):
        """Set or update the custom download directory for a watchlist artist."""
        if self._watchlist_manager.set_download_dir(userId, service, download_dir):
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()

    @Slot(str, str, str, result=str)
    def setWatchlistLastDownloadDate(self, userId: str, service: str, dateStr: str) -> str:
        """
        Manually set or update the last downloaded cutoff date for an artist.
        Converts and normalizes user input into canonical 'YYYY-MM-DD' (or '' if cleared).
        Returns the normalized date string on success, or '' on failure.
        """
        ok, res = self._watchlist_manager.set_last_post_date(userId, service, dateStr)
        if ok:
            self._watchlist_model.update_new_counts()
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()
            return res
        else:
            logger.warning(f"Failed to update last download date: {res}", category="watchlist")
            return ""

    @Slot(str, result=str)
    def normalizeWatchlistDate(self, dateStr: str) -> str:
        """Helper to preview/validate date conversion live from QML."""
        res = self._watchlist_manager.normalize_date(dateStr)
        return res if res is not None else "INVALID"

    @Slot(str, str)
    def browseWatchlistDownloadDir(self, userId: str, service: str):
        """Open a directory picker dialog to set custom download dir for a watchlist entry."""
        entry = self._watchlist_manager._find(userId, service)
        initial_dir = entry.download_dir if entry and entry.download_dir and os.path.exists(entry.download_dir) else self._download_dir
        folder = QFileDialog.getExistingDirectory(
            None,
            f"Select Download Folder for {entry.creator_name if entry else userId}",
            initial_dir
        )
        if folder:
            norm_folder = os.path.normpath(folder)
            if entry:
                resolved = self.resolve_artist_download_dir_for_folder(norm_folder, entry.creator_name, entry.service)
            else:
                resolved = norm_folder
            self.setWatchlistDownloadDir(userId, service, resolved)

    @Slot(str)
    def openFolder(self, path: str):
        """Open the specified or enclosing directory in the OS file manager."""
        if not path:
            path = self._download_dir
        target = path if os.path.isdir(path) else os.path.dirname(path)
        if not os.path.exists(target):
            try:
                os.makedirs(target, exist_ok=True)
            except Exception:
                target = self._download_dir
        if os.path.exists(target):
            import subprocess
            if sys.platform == "win32":
                subprocess.Popen(["explorer", os.path.normpath(target)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])

    @Slot(result=str)
    def getWatchlistJson(self) -> str:
        """Return a JSON string of all watchlist entries for QML."""
        return self._watchlist_manager.to_json_list()

    # ── Async Watchlist Check ─────────────────────────────────────────────────

    def _async_watchlist_check(self):
        """
        Background thread: check all watchlist entries for new posts.
        Updates new_post_count on each entry, then emits _watchlistResultSignal
        so the GUI can refresh safely.
        """
        total_new = 0
        for entry in list(self._watchlist_manager.entries):
            try:
                new = self._watchlist_manager.get_posts_since(entry, self.api_client)
                entry.new_post_count = len(new)
                total_new += len(new)
                if new:
                    logger.info(
                        f"Watchlist: {entry.creator_name!r} has {len(new)} new post(s).",
                        category="watchlist"
                    )
            except Exception as e:
                logger.warning(f"Watchlist check error for {entry.creator_name!r}: {e}", category="watchlist")
        self._watchlistResultSignal.emit([total_new])

    @Slot(list)
    def _handle_watchlist_result(self, result: list):
        """Main-thread handler: refresh model and emit finished signal."""
        total_new = result[0] if result else 0
        self._watchlist_model.update_new_counts()
        self._watchlist_model.refresh()
        self.watchlistCheckFinished.emit(total_new)
        if total_new > 0:
            logger.success(
                f"Watchlist check complete — {total_new} new post(s) found across all entries.",
                category="watchlist"
            )
        else:
            logger.info("Watchlist check complete — all artists up to date.", category="watchlist")

    @Slot(str, str, int)
    def _handle_watchlist_artist_result(self, userId: str, service: str, count: int):
        """Main-thread handler: update counts and emit finished signals for a single artist."""
        entry = self._watchlist_manager._find(userId, service)
        name = entry.creator_name if entry else f"{userId} [{service}]"
        self._watchlist_model.update_new_counts()
        self._watchlist_model.refresh()
        self.watchlistArtistChecking.emit(userId, service, False)
        self.watchlistArtistChecked.emit(userId, service, count)
        self.watchlistChanged.emit()
        if count > 0:
            logger.success(
                f"Watchlist check complete — {count} new post(s) found for {name!r}.",
                category="watchlist"
            )
        else:
            logger.info(
                f"Watchlist check complete — {name!r} is up to date (no new posts).",
                category="watchlist"
            )

    # ── Link Vault Slots ─────────────────────────────────────────────────────
    @Slot(str, str)
    def refreshLinkVault(self, search: str = "", platform: str = ""):
        self._vault_search = search
        self._vault_platform = platform
        self.linkVaultChanged.emit()

    @Slot(str, result=bool)
    def deleteVaultLink(self, linkId: str) -> bool:
        from core.link_vault_manager import link_vault_manager
        res = link_vault_manager.delete_link(linkId)
        if res:
            self.linkVaultChanged.emit()
        return res

    @Slot(str, result=bool)
    def deleteVaultPost(self, postId: str) -> bool:
        from core.link_vault_manager import link_vault_manager
        res = link_vault_manager.delete_post(postId)
        if res:
            self.linkVaultChanged.emit()
        return res

    @Slot(str, result=bool)
    def deleteVaultCreator(self, creatorKey: str) -> bool:
        from core.link_vault_manager import link_vault_manager
        res = link_vault_manager.delete_creator(creatorKey)
        if res:
            self.linkVaultChanged.emit()
        return res

    @Slot(result=int)
    def cleanDeadVaultLinks(self) -> int:
        from core.link_vault_manager import link_vault_manager
        count = link_vault_manager.clean_dead_links()
        self.linkVaultChanged.emit()
        return count

    @Slot()
    def probeVaultHealth(self):
        from core.link_vault_manager import link_vault_manager
        self.linkVaultProbingStarted.emit()
        def _on_done(done, total, url):
            self.linkVaultChanged.emit()
        def _on_complete():
            self.linkVaultChanged.emit()
            self.linkVaultProbingFinished.emit()
        link_vault_manager.probe_all_links_async(
            progress_callback=_on_done,
            completion_callback=_on_complete
        )

    @Slot(str, bool, int, int)
    def harvestArtistToVault(self, url: str, probeHealth: bool = True, pageStart: int = 1, pageEnd: int = 999999):
        clean_url = (url or "").strip()
        if not clean_url:
            self.vaultHarvestFinished.emit(False, "", 0, 0)
            return
        if self._vault_harvesting:
            logger.warning("Artist harvesting to Link Vault is already running.", category="vault")
            return

        def _worker():
            self._vault_harvesting = True
            self._vault_harvest_cancel.clear()
            self._vault_harvest_status = "Connecting..."
            self.linkVaultChanged.emit()

            try:
                parsed = KemonoURLParser.parse(clean_url)
                if not parsed.is_valid:
                    logger.error(f"Link Vault Harvest: Invalid artist URL '{clean_url}'", category="vault")
                    self.vaultHarvestFinished.emit(False, "Invalid URL", 0, 0)
                    return

                # Fetch artist profile
                profile = self.api_client.fetch_creator_profile(parsed)
                creator_name = clean_text(profile.get("name", parsed.user_id) or parsed.user_id)
                creator_key = f"{parsed.service}:{parsed.user_id}".lower()

                self._vault_harvest_status = f"Scanning posts for {creator_name}..."
                self.linkVaultChanged.emit()
                self.vaultHarvestStarted.emit(creator_name)

                # Fetch all posts in range
                if parsed.is_single_post:
                    single = self.api_client.fetch_single_post(parsed)
                    posts = [single] if single else []
                else:
                    posts = self.api_client.fetch_user_posts(
                        parsed=parsed,
                        page_start=pageStart,
                        page_end=pageEnd,
                        cancel_event=self._vault_harvest_cancel
                    )

                if self._vault_harvest_cancel.is_set():
                    logger.warning(f"Link Vault Harvest: Cancelled during post fetch for {creator_name}.", category="vault")
                    self.vaultHarvestFinished.emit(False, creator_name, 0, len(posts))
                    return

                if not posts:
                    logger.info(f"Link Vault Harvest: No posts found for {creator_name}.", category="vault")
                    self.vaultHarvestFinished.emit(True, creator_name, 0, 0)
                    return

                # Process posts into vault records
                harvested_posts = []
                total_links_found = 0
                for idx, p in enumerate(posts):
                    if self._vault_harvest_cancel.is_set():
                        break

                    rec = LinkExtractor.extract_post_vault_record(
                        post=p,
                        api_client=self.api_client,
                        domain=parsed.domain,
                        service=parsed.service,
                        user_id=parsed.user_id
                    )
                    if rec and rec.get("links"):
                        harvested_posts.append(rec)
                        total_links_found += len(rec["links"])

                    if (idx + 1) % 10 == 0 or idx == len(posts) - 1:
                        status_msg = f"Processed {idx + 1}/{len(posts)} posts ({total_links_found} links found)"
                        self._vault_harvest_status = status_msg
                        self.linkVaultChanged.emit()
                        self.vaultHarvestProgress.emit(status_msg, idx + 1, total_links_found)

                if self._vault_harvest_cancel.is_set():
                    logger.warning(f"Link Vault Harvest: Cancelled during link extraction for {creator_name}.", category="vault")
                    self.vaultHarvestFinished.emit(False, creator_name, 0, len(posts))
                    return

                # Store harvested posts into Link Vault
                from core.link_vault_manager import link_vault_manager
                new_links_count = link_vault_manager.add_harvested_data(
                    creator_name=creator_name,
                    service=parsed.service,
                    user_id=parsed.user_id,
                    harvested_posts=harvested_posts
                )
                self.linkVaultChanged.emit()

                # Optionally probe links health
                if probeHealth and new_links_count > 0 and not self._vault_harvest_cancel.is_set():
                    self._vault_harvest_status = f"Probing links for {creator_name}..."
                    self.linkVaultChanged.emit()
                    self.linkVaultProbingStarted.emit()
                    def _on_probe_progress(done, tot, u):
                        self.linkVaultChanged.emit()
                    def _on_probe_complete():
                        self.linkVaultChanged.emit()
                        self.linkVaultProbingFinished.emit()
                    link_vault_manager.probe_all_links_async(
                        progress_callback=_on_probe_progress,
                        cancel_event=self._vault_harvest_cancel,
                        creator_key=creator_key,
                        completion_callback=_on_probe_complete
                    )

                logger.success(
                    f"Link Vault: Finished harvesting {creator_name} ({new_links_count} new links saved from {len(posts)} posts).",
                    category="vault"
                )
                self.vaultHarvestFinished.emit(True, creator_name, new_links_count, len(posts))

            except Exception as e:
                logger.error(f"Link Vault Harvest failed: {e}", category="vault")
                self.vaultHarvestFinished.emit(False, str(e), 0, 0)
            finally:
                self._vault_harvesting = False
                self._vault_harvest_status = ""
                self.linkVaultChanged.emit()

        t = threading.Thread(target=_worker, daemon=True, name="VaultArtistHarvester")
        t.start()

    @Slot()
    def cancelVaultHarvest(self):
        self._vault_harvest_cancel.set()
        self._vault_harvesting = False
        self._vault_harvest_status = "Cancelled"
        self.linkVaultChanged.emit()

    @Slot(result=int)
    def copyPasswordsToDecompressor(self) -> int:
        from core.link_vault_manager import link_vault_manager
        pws = link_vault_manager.get_all_passwords()
        count = len(pws)
        if hasattr(self, "_decompressor_bridge") and self._decompressor_bridge:
            for pw in pws:
                if pw and hasattr(self._decompressor_bridge, "addPassword"):
                    self._decompressor_bridge.addPassword(pw)
        logger.success(f"Copied {count} password(s) from Link Vault to Bulk Decompressor.", category="vault")
        return count

    # ── Storage Pool Slots ───────────────────────────────────────────────────
    @Slot(bool)
    def setStoragePoolEnabled(self, enabled: bool):
        from core.storage_pool_manager import storage_pool_manager
        storage_pool_manager.set_enabled(enabled)
        self.storagePoolChanged.emit()

    @Slot(float)
    def setStoragePoolMargin(self, marginGB: float):
        from core.storage_pool_manager import storage_pool_manager
        storage_pool_manager.set_safety_margin(marginGB)
        self.storagePoolChanged.emit()

    @Slot(str, result=bool)
    def addStoragePoolDrive(self, path: str) -> bool:
        from core.storage_pool_manager import storage_pool_manager
        res = storage_pool_manager.add_overflow_dir(path)
        if res:
            self.storagePoolChanged.emit()
        return res

    @Slot(str, result=bool)
    def removeStoragePoolDrive(self, path: str) -> bool:
        from core.storage_pool_manager import storage_pool_manager
        res = storage_pool_manager.remove_overflow_dir(path)
        if res:
            self.storagePoolChanged.emit()
        return res

    @Slot(result=str)
    def selectStoragePoolDirectory(self) -> str:
        folder = QFileDialog.getExistingDirectory(
            None,
            "Select Storage Overflow Directory",
            ""
        )
        if folder:
            self.addStoragePoolDrive(folder)
            return folder
        return ""

    @Slot()
    def refreshStoragePools(self):
        self.storagePoolChanged.emit()

    # ── Cookie Importer Slots ────────────────────────────────────────────────
    @Slot(str, result=bool)
    def importBrowserCookies(self, browserId: str = "") -> bool:
        from services.cookie_importer import browser_cookie_importer
        try:
            res = browser_cookie_importer.import_auto_detect(preferred_browser=browserId or None)
            c_str = res.get("cookie_string", "")
            if c_str:
                self.cookieString = c_str
                self.saveSettings()
                self.cookieWatchdogChanged.emit()
                self.cookieImportCompleted.emit(True, res.get("browser_name", "Browser"))
                return True
        except Exception as e:
            logger.error(f"Browser cookie import failed: {e}", category="cookie")
            self.cookieImportCompleted.emit(False, str(e))
        return False

    @Slot()
    def refreshCookieWatchdog(self):
        self.cookieWatchdogChanged.emit()

    # ── Task Scheduler Slots ─────────────────────────────────────────────────
    @Slot(str, str, str, str, int, str, result=str)
    def addSchedulerTask(self, name: str, targetType: str, targetUrl: str, triggerType: str, intervalHours: int, timeOfDay: str) -> str:
        from core.task_scheduler import task_scheduler
        sid = task_scheduler.add_schedule(name, targetType, targetUrl, triggerType, intervalHours, timeOfDay)
        self.schedulerChanged.emit()
        return sid

    @Slot(str, result=bool)
    def deleteSchedulerTask(self, schedId: str) -> bool:
        from core.task_scheduler import task_scheduler
        res = task_scheduler.delete_schedule(schedId)
        if res:
            self.schedulerChanged.emit()
        return res

    @Slot(str, bool, result=bool)
    def toggleSchedulerTask(self, schedId: str, enabled: bool) -> bool:
        from core.task_scheduler import task_scheduler
        res = task_scheduler.toggle_schedule(schedId, enabled)
        if res:
            self.schedulerChanged.emit()
        return res

    @Slot(str, str, str, str, str, int, str, result=bool)
    def updateSchedulerTask(self, schedId: str, name: str, targetType: str, targetUrl: str, triggerType: str, intervalHours: int, timeOfDay: str) -> bool:
        from core.task_scheduler import task_scheduler
        res = task_scheduler.update_schedule(schedId, name, targetType, targetUrl, triggerType, intervalHours, timeOfDay)
        if res:
            self.schedulerChanged.emit()
        return res


    @Slot(bool, bool, bool, str, str, bool, bool)
    def setSchedulerSettings(self, enabled: bool, lockThreads: bool, nightOwl: bool, start: str, end: str, preventSleep: bool, sweepRetry: bool):
        from core.task_scheduler import task_scheduler
        task_scheduler.enabled = enabled
        task_scheduler.lock_threads_delay = lockThreads
        self.threadsLocked = lockThreads
        task_scheduler.night_owl_enabled = nightOwl
        task_scheduler.night_owl_start = start
        task_scheduler.night_owl_end = end
        task_scheduler.prevent_sleep = preventSleep
        task_scheduler.sweep_retry = sweepRetry
        task_scheduler.save()
        self.schedulerChanged.emit()

    def _run_scheduled_watchlist_sync(self):
        """Called by background TaskScheduler when a Watchlist Sync schedule triggers."""
        logger.info("Scheduler: Initiating automated Watchlist Sync check...", category="scheduler")
        self.checkWatchlist()

    def _run_scheduled_creator_sync(self, url: str):
        """Called by background TaskScheduler when a Custom Creator schedule triggers."""
        if url:
            logger.info(f"Scheduler: Initiating automated Creator Sync for '{url}'...", category="scheduler")
            self.currentUrl = url
            self.startDownload()


