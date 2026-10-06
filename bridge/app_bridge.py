"""
Application Bridge Subsystem
Binds the PySide6/Qt Core engine with the QML User Interface, providing
reactive properties, slots, session persistence, telemetry signals, and async orchestration.
"""

import os
import sys
import shutil
import time
import subprocess
import threading
import json
import re
import datetime
from typing import Optional, Dict, Any, List, Tuple
from PySide6.QtCore import QObject, Signal, Property, Slot, Qt, QUrl, QCoreApplication, QTimer
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog, QApplication

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.watchlist_manager import post_id_is_newer  # noqa: F401  (kept for older imports)


def _post_order_key(date: str, post_id: str):
    pid = str(post_id or "")
    return (str(date or "")[:10], int(pid) if pid.isdigit() else -1)


def watchlist_cutoff(done_posts, unfinished_posts):
    """Where the Watchlist's "downloaded up to" point may move, from what actually finished.

    done_posts / unfinished_posts: iterables of (date, post_id). The point only advances through
    posts that are older than every post that didn't finish (failed, cancelled, never started), so
    nothing is skipped by a later check. Returns (post_id, date, ids_of_done_posts_on_that_date),
    or ("", "", []) when nothing can be recorded.
    """
    done = [(str(d or "")[:10], str(p or "")) for d, p in done_posts if d]
    unfinished = [(str(d or "")[:10], str(p or "")) for d, p in unfinished_posts if d]
    if unfinished:
        first_open = min(_post_order_key(d, p) for d, p in unfinished)
        done = [(d, p) for d, p in done if _post_order_key(d, p) < first_open]
    if not done:
        return "", "", []
    newest_date, newest_pid = max(done, key=lambda dp: _post_order_key(*dp))
    day_ids = sorted({p for d, p in done if d == newest_date and p})
    return newest_pid, newest_date, day_ids
from core.logger import logger
from core.parser import KemonoURLParser, URLParseResult
from core.filter_engine import FilterEngine, FilterOptions, FilenameStyles
from core.file_order import normalize_file_order, order_files
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
from bridge.telegram_bridge import TelegramBridge
from services.telegram_service import TelegramService
from services.cloud_downloader import (
    download_mega_link,
    download_gdrive_link,
    download_dropbox_link,
    download_gofile_link
)
from core.text_utils import clean_text, sanitize_filesystem_name, safe_file_name
from core.path_utils import unique_name_in_batch
from core.archive_manager import ArchiveManager
from core.archive_rebuilder import ArchiveRebuilder, ArchiveRebuildOptions
from services.model_manager import ModelManager, MODEL_CATALOG
from core.hardware_detector import HardwareDetector



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
    dateAfterChanged = Signal()
    dateBeforeChanged = Signal()
    dateAutoScanPagesChanged = Signal()
    minFileSizeChanged = Signal()
    maxFileSizeChanged = Signal()
    currentFpsChanged = Signal()
    screenHzChanged = Signal()
    filterTypeChanged = Signal()
    exactExtensionsChanged = Signal()
    savedCustomExtensionsChanged = Signal()
    skipArchivesChanged = Signal()
    downloadThumbnailsOnlyChanged = Signal()
    fallbackToThumbnailsChanged = Signal()
    redownloadSmallFilesChanged = Signal()
    skipPostCoversChanged = Signal()
    scanContentImagesChanged = Signal()
    downloadPawchiveTemporaryFilesChanged = Signal()
    compressWebpChanged = Signal()
    webpQualityChanged = Signal()
    writeAudioMetadataChanged = Signal()
    keepDuplicatesChanged = Signal()
    favoriteModeChanged = Signal()
    subfolderPerPostChanged = Signal()
    datePrefixChanged = Signal()
    fileIndexPrefixChanged = Signal()
    separateFoldersByKnownChanged = Signal()
    downloadRevisionsChanged = Signal()
    adaptiveThreadingChanged = Signal()
    autoRetryAtEndChanged = Signal()
    skipRetry404Changed = Signal()
    mangaModeChanged = Signal()
    filenameStyleChanged = Signal()
    filenameTemplateChanged = Signal()
    postSelectionLoadingChanged = Signal()
    postSelectionReady = Signal(list, str, int)
    postSelectionError = Signal(str)
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
    aiRecognitionEnabledChanged = Signal()
    aiEngineModeChanged = Signal()
    aiModelProgressChanged = Signal(str, str, float, str, str)  # (model_key, status, percent, speed_str, error)
    aiHardwareInfoChanged = Signal()
    languageChanged = Signal()
    postActionCountdownStarted = Signal(str)  # carries human label e.g. "Shutdown"
    exportCompleted = Signal(str, bool)       # (filePath, wasDownloading)
    importCompleted = Signal(int, int)        # (taskCount, creatorCount)
    exportFailed = Signal(str)
    importFailed = Signal(str)
    hasRecoverySessionChanged = Signal()
    recoverySessionDetected   = Signal('QVariant')
    sessionDiscardedWarning   = Signal(str)       # carries old artist description when auto-discarding

    enableDownloadArchiveChanged = Signal()
    archiveRecordCountChanged    = Signal()
    archiveUpdated               = Signal()
    archiveCreatorVerificationStarted  = Signal(str, str)
    archiveCreatorVerificationProgress = Signal(str, str, int, int)
    archiveCreatorVerificationFinished = Signal(str, str, 'QVariant')
    archiveRebuildProgress             = Signal('QVariant')
    archiveRebuildFinished            = Signal('QVariant')
    archiveRebuildStatusChanged        = Signal()

    tagFolderModeChanged      = Signal()
    groupFileTypeChanged      = Signal()
    fileOrderChanged          = Signal()
    watchlistChanged          = Signal()
    watchlistCheckStarted     = Signal()
    watchlistCheckFinished    = Signal(int)  # total new posts found
    watchlistArtistChecking   = Signal(str, str, bool) # (userId, service, isChecking)
    watchlistArtistChecked    = Signal(str, str, int)  # (userId, service, newPostCount)
    watchlistApplyGlobalSettingsChanged = Signal()

    # Link Vault signals
    linkVaultChanged          = Signal()
    linkVaultProbingStarted   = Signal()
    linkVaultProbingFinished  = Signal()
    vaultHarvestStarted       = Signal(str)             # (creatorName)
    vaultHarvestProgress      = Signal(str, int, int)   # (statusMsg, currentPage, currentLinks)
    vaultHarvestFinished      = Signal(bool, str, int, int)  # (success, creatorName, newLinks, totalPosts)

    # Telegram integration signals
    telegramAuthRequested     = Signal(bool)                 # (is_private)
    telegramScopeRequested    = Signal(str, str, bool, str)  # (channelId, rawUrl, isPrivate, defaultAction)
    telegramSafetyAcknowledgedChanged = Signal()
    telegramLiabilityAcknowledgedChanged = Signal()


    # Storage Pool signals
    storagePoolChanged        = Signal()

    # Cookie Watchdog signals
    cookieWatchdogChanged     = Signal()
    cookieImportCompleted     = Signal(bool, str)

    # Provider & Credential Vault signals
    providersChanged          = Signal()
    providerValidationFinished = Signal(str, bool, str)
    providerLoginFinished     = Signal(str, bool, str)
    favoriteAuthRequired      = Signal(str)

    # Task Scheduler signals
    schedulerChanged          = Signal()

    # File Explorer & Media Gallery signals
    folderStatsCalculated     = Signal(str, 'qint64', 'qint64', 'qint64')  # (path, total_size, file_count, folder_count)
    galleryBookmarksChanged   = Signal()
    drivesUpdated             = Signal('QVariantList')   # drives with fresh free space (Gallery)
    galleryShowRequested      = Signal(str, bool)   # (path, is_dir): other tabs ask the Gallery to open a place

    _progressSignal    = Signal(dict)    # carries progress info dict
    _taskSignal        = Signal(object)  # carries a DownloadTask object
    _finishedSignal    = Signal(bool, str)
    _throttledSignal   = Signal(int)     # carries new worker concurrency count
    _pauseSignal       = Signal(bool)    # carries pause state (True=paused, False=resumed)
    _creatorSignal     = Signal(str, str)  # (link it was looked up for, resolved creator name)
    _setTasksSignal    = Signal(list)    # safely sends new task list to GUI thread
    _appendTasksSignal = Signal(list)    # safely appends new tasks to GUI thread queue
    _watchlistResultSignal = Signal(list)  # carries per-entry new-post lists
    _watchlistArtistResultSignal = Signal(str, str, int)  # (userId, service, newCount)
    _scheduledCreatorSyncSignal = Signal(str)  # scheduler thread -> GUI thread
    # Slow folder scans run in the background; QML gets the answer here: (request id, result)
    asyncResultReady = Signal(str, 'QVariant')
    # A switched-off site (Kemono / Coomer) was used: (message, same link on the replacement site or "", context)
    providerDisabled = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # File explorer folder stats cache & worker token
        self._folder_stats_cache = {}
        self._folder_stats_worker_token = 0

        # Core systems
        self.known_manager = KnownManager()
        self.session_manager = SessionManager()
        saved_settings = self.session_manager.load_settings()
        self._enable_download_archive = bool(saved_settings.get("enable_download_archive", False))
        self.archive_manager = ArchiveManager(
            config_dir=self.session_manager.config_dir,
            enabled=self._enable_download_archive
        )
        self.downloader = KemonoDownloader(
            known_manager=self.known_manager,
            session_manager=self.session_manager,
            max_workers=4,
            archive_manager=self.archive_manager
        )
        self.api_client = KemonoApiClient()

        # Models
        self._log_model = LogModel(self)
        self._queue_model = QueueModel(self)
        self._active_queue_model = QueueModel(self, enable_groups=False)
        self._active_queue_model.filterStatus = "downloading"
        self._active_queue_model.minFileSize = 50 * 1024 * 1024  # 50 MB threshold
        self._known_model = KnownModel(self.known_manager, self)

        # Settings defaults
        self._current_url = ""
        self._page_start = 1
        self._page_end = 999999
        self._download_dir = saved_settings.get("download_dir", os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads"))
        self._filter_characters = ""
        self._character_scope = saved_settings.get("character_scope", "title")
        self._skip_words = ""
        self._skip_scope = saved_settings.get("skip_scope", "posts")
        self._remove_words = ""
        # Date range filters apply to one download; remembering them silently skipped posts later
        self._date_after = ""
        self._date_before = ""
        self._date_auto_scan_pages = bool(saved_settings.get("date_auto_scan_pages", True))
        self._min_file_size = str(saved_settings.get("min_file_size", ""))
        self._max_file_size = str(saved_settings.get("max_file_size", ""))
        self._filter_type = "all"
        self._exact_extensions = str(saved_settings.get("exact_extensions", "")).strip()
        self._saved_custom_extensions = [
            ext.strip().lower() for ext in saved_settings.get("saved_custom_extensions", [])
            if isinstance(ext, str) and ext.strip()
        ]
        self._skip_archives = False
        self._download_thumbnails_only = bool(saved_settings.get("download_thumbnails_only", False))
        self._fallback_to_thumbnails = bool(saved_settings.get("fallback_to_thumbnails", False))
        self._redownload_small_files = bool(saved_settings.get("redownload_small_files", False))
        self._skip_post_covers = bool(saved_settings.get("skip_post_covers", False))
        self._scan_content_images = saved_settings.get("scan_content_images", True)
        self._download_pawchive_temporary_files = saved_settings.get("download_pawchive_temporary_files", True)
        self._compress_webp = saved_settings.get("compress_webp", False)
        self._webp_quality = str(saved_settings.get("webp_quality", "balanced"))
        self._write_audio_metadata = bool(saved_settings.get("write_audio_metadata", False))
        self._keep_duplicates = saved_settings.get("keep_duplicates", False)
        self._last_archive_emit_time: float = 0.0
        self._archive_rebuilder: Optional[ArchiveRebuilder] = None
        self._is_archive_rebuilding: bool = False
        self._is_archive_rebuild_paused: bool = False
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
        self._skip_retry_404 = bool(saved_settings.get("skip_retry_404", False))
        self._manga_mode = saved_settings.get("manga_mode", False)
        self._filename_style = saved_settings.get("filename_style", "post_title")
        self._filename_template = saved_settings.get("filename_template", "{title} - {orig_name}")
        self._is_post_selection_loading = False
        self._selection_cached_posts = []
        self._selection_parsed = None
        self._selection_creator_name = ""
        self._gallery_bookmarks = list(saved_settings.get("gallery_bookmarks", []) or [])
        if not self._gallery_bookmarks:
            self._gallery_bookmarks = self._get_default_gallery_bookmarks()
        self._proxy_url = saved_settings.get("proxy_url", "")
        self._max_cpu_threads = max(4, os.cpu_count() or 16)
        self._threads_count = int(saved_settings.get("threads", min(8, self._max_cpu_threads)))
        self.downloader.max_workers = self._threads_count
        try:
            from core.auth_manager import auth_manager
            vault_cookie = auth_manager.get_credential("kemono", "cookie")
        except Exception:
            vault_cookie = ""
        self._cookie_string = vault_cookie or saved_settings.get("cookie", "")
        self._cookie_save_timer = QTimer(self)
        self._cookie_save_timer.setSingleShot(True)
        self._cookie_save_timer.setInterval(800)
        self._cookie_save_timer.timeout.connect(self._persist_cookie)
        # Downloader-tab settings are saved shortly after the last change (sliders and text boxes
        # change many times in a row); they used to be saved only when some other setting changed
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(500)
        self._settings_save_timer.timeout.connect(self.saveSettings)
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
        self._ai_recognition_enabled = bool(saved_settings.get("ai_recognition_enabled", False))
        self._ai_engine_mode = str(saved_settings.get("ai_engine_mode", "hybrid"))
        self.model_manager = ModelManager()
        self.known_manager.enable_ai(self._ai_recognition_enabled, model_manager=self.model_manager)
        self.known_manager.set_ai_engine_mode(self._ai_engine_mode)

        def _on_model_progress(data: dict):
            key = data.get("model_key", "")
            st = data.get("status", "")
            pct = float(data.get("percent", 0.0))
            spd = f"{data.get('speed_mbps', 0.0):.1f} MB/s" if st == "downloading" else ""
            err = str(data.get("error", ""))
            self.aiModelProgressChanged.emit(key, st, pct, spd, err)
            if st in ("ready", "not_downloaded", "error"):
                self.aiRecognitionEnabledChanged.emit()

        self._ai_deep_reasoner_variant = str(saved_settings.get("ai_deep_reasoner_variant", "light"))
        self.model_manager.register_callback("fast_semantic", _on_model_progress)
        self.model_manager.register_callback("deep_reasoner_light", _on_model_progress)
        self.model_manager.register_callback("deep_reasoner_heavy", _on_model_progress)
        self.model_manager.register_callback("deep_reasoner", _on_model_progress)

        self._language = str(saved_settings.get("language", "auto"))
        self._console_width = int(saved_settings.get("console_width", 620))
        self._current_fps = 0
        self._screen_hz = 60
        self._creator_name = ""
        self._tag_folder_mode = bool(saved_settings.get("tag_folder_mode", False))
        self._group_file_type = str(saved_settings.get("group_file_type", "none"))
        self._file_order = normalize_file_order(saved_settings.get("file_order", "posted"))
        self._telegram_safety_acknowledged = bool(saved_settings.get("telegram_safety_acknowledged", False))
        self._telegram_liability_acknowledged = bool(saved_settings.get("telegram_liability_acknowledged", False))
        self._telegram_pending_action = ""

        # Watchlist
        self._watchlist_manager = WatchlistManager(self.session_manager.config_dir)
        self._watchlist_manager.load()
        self._watchlist_model = WatchlistModel(self._watchlist_manager, self)
        # Watchlist downloads: new posts that needed no files (already saved or filtered out),
        # counted as done when the download finishes
        self._watchlist_pending_updates: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
        self._watchlist_result_signal_connected = False
        self._watchlist_apply_global_settings = bool(saved_settings.get("watchlist_apply_global_settings", True))

        # Bulk Decompressor
        self._decompressor_bridge = DecompressorBridge(self._watchlist_manager, self, self)

        # Telegram Bridge
        self._telegram_bridge = TelegramBridge(self)

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
        def _safe_emit(sig, *args):
            try:
                sig.emit(*args)
            except (RuntimeError, ReferenceError):
                pass

        self.downloader.on_progress_update        = lambda info: _safe_emit(self._progressSignal, info)
        self.downloader.on_task_status_changed    = lambda task: _safe_emit(self._taskSignal, task)
        self.downloader.on_download_finished      = lambda ok, msg: _safe_emit(self._finishedSignal, ok, msg)
        self.downloader.on_concurrency_throttled  = lambda count: _safe_emit(self._throttledSignal, count)
        self.downloader.on_pause_changed          = lambda paused: _safe_emit(self._pauseSignal, paused)

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
        self._scheduledCreatorSyncSignal.connect(self._handle_scheduled_creator_sync, Qt.QueuedConnection)
        # Keep the computer awake while downloads run (Scheduler → "Sleep prevention")
        self._scheduled_sweep_retry = False
        self.isDownloadingChanged.connect(self._update_sleep_prevention)

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

        logger.info(f"Filename style loaded: '{self._filename_style}'", category="system")
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
                        args=(parsed, val_clean),
                        daemon=True
                    ).start()
                    if self._favorite_mode:
                        self.checkFavoriteModeAuth()
                else:
                    self._creator_name = ""
                    self.creatorNameChanged.emit()
            else:
                self._creator_name = ""
                self.creatorNameChanged.emit()

    @Property(bool, notify=currentUrlChanged)
    def isTelegramUrl(self) -> bool:
        url = (self._current_url or "").strip()
        if url:
            if re.search(r'(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:me|dog)|telegram\.org)/', url, re.I) or url.startswith("tg://"):
                return True
            parsed = KemonoURLParser.parse(url)
            if parsed.is_valid and parsed.provider == "telegram":
                return True
        if hasattr(self, "downloader") and self.downloader.tasks:
            return any(
                getattr(t, "is_telegram", False) or getattr(t, "service", "") == "telegram" or (t.url and t.url.startswith("tg://"))
                for t in self.downloader.tasks
                if t.status in ("pending", "downloading")
            )
        return False

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
            self._settings_save_timer.start()
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
            self._settings_save_timer.start()

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
            self._settings_save_timer.start()

    @Property(str, notify=removeWordsChanged)
    def removeWords(self) -> str:
        return self._remove_words

    @removeWords.setter
    def removeWords(self, val: str):
        if self._remove_words != val:
            self._remove_words = val
            self.removeWordsChanged.emit()

    @Property(str, notify=dateAfterChanged)
    def dateAfter(self) -> str:
        return self._date_after

    @dateAfter.setter
    def dateAfter(self, val: str):
        if self._date_after != val:
            self._date_after = val
            self.dateAfterChanged.emit()

    @Property(str, notify=dateBeforeChanged)
    def dateBefore(self) -> str:
        return self._date_before

    @dateBefore.setter
    def dateBefore(self, val: str):
        if self._date_before != val:
            self._date_before = val
            self.dateBeforeChanged.emit()

    @Property(bool, notify=dateAutoScanPagesChanged)
    def dateAutoScanPages(self) -> bool:
        return self._date_auto_scan_pages

    @dateAutoScanPages.setter
    def dateAutoScanPages(self, val: bool):
        if self._date_auto_scan_pages != val:
            self._date_auto_scan_pages = val
            self.dateAutoScanPagesChanged.emit()
            self.saveSettings()

    @Property(str, notify=minFileSizeChanged)
    def minFileSize(self) -> str:
        return self._min_file_size

    @minFileSize.setter
    def minFileSize(self, val: str):
        if self._min_file_size != val:
            self._min_file_size = val
            self.minFileSizeChanged.emit()
            self.saveSettings()

    @Property(str, notify=maxFileSizeChanged)
    def maxFileSize(self) -> str:
        return self._max_file_size

    @maxFileSize.setter
    def maxFileSize(self, val: str):
        if self._max_file_size != val:
            self._max_file_size = val
            self.maxFileSizeChanged.emit()
            self.saveSettings()

    @Property(int, notify=currentFpsChanged)
    def currentFps(self) -> int:
        return self._current_fps

    @Slot(int)
    def setCurrentFps(self, val: int):
        if self._current_fps != val:
            self._current_fps = val
            self.currentFpsChanged.emit()

    @Property(int, notify=screenHzChanged)
    def screenHz(self) -> int:
        return self._screen_hz

    @Slot(int)
    def setScreenHz(self, val: int):
        if self._screen_hz != val:
            self._screen_hz = val
            self.screenHzChanged.emit()

    @Property(str, notify=filterTypeChanged)
    def filterType(self) -> str:
        return self._filter_type

    @filterType.setter
    def filterType(self, val: str):
        if self._filter_type != val:
            self._filter_type = val
            self.filterTypeChanged.emit()

    @Property(str, notify=exactExtensionsChanged)
    def exactExtensions(self) -> str:
        return self._exact_extensions

    @exactExtensions.setter
    def exactExtensions(self, val: str):
        val_clean = str(val or "").strip()
        if self._exact_extensions != val_clean:
            self._exact_extensions = val_clean
            self.exactExtensionsChanged.emit()
            self.saveSettings()

    @Slot(str)
    def toggleExactExtension(self, ext: str):
        """Toggles an extension (e.g. '.zip' or 'zip' or '*.zip') in the active comma-separated list."""
        ext = ext.strip().lower().lstrip("*")
        if not ext.startswith("."):
            ext = "." + ext
        tokens = [t.strip().lower().lstrip("*") for t in re.split(r'[,;\s]+', self._exact_extensions) if t.strip()]
        norm_tokens = [(t if t.startswith(".") else "." + t) for t in tokens if t]
        unique_tokens = []
        for t in norm_tokens:
            if t not in unique_tokens:
                unique_tokens.append(t)
        if ext in unique_tokens:
            unique_tokens = [t for t in unique_tokens if t != ext]
        else:
            unique_tokens.append(ext)
        self.exactExtensions = ", ".join(unique_tokens)

    @Slot(str, result=bool)
    def isExactExtensionActive(self, ext: str) -> bool:
        """Returns True if the specified extension is in the current exact extensions list."""
        if not self._exact_extensions:
            return False
        ext = ext.strip().lower()
        if not ext.startswith("."):
            ext = "." + ext
        allowed = FilterEngine.parse_extensions_list(self._exact_extensions)
        return ext in allowed

    @Slot()
    def clearExactExtensions(self):
        """Clears all exact extension filters."""
        self.exactExtensions = ""

    @Property('QVariantList', notify=exactExtensionsChanged)
    def activeExtensionsList(self) -> list:
        """Returns the list of currently active extensions in sorted order."""
        if not self._exact_extensions:
            return []
        parsed = FilterEngine.parse_extensions_list(self._exact_extensions)
        return sorted(list(parsed))

    @Property('QVariantList', notify=savedCustomExtensionsChanged)
    def savedCustomExtensions(self) -> list:
        """Returns the list of saved custom extensions."""
        return self._saved_custom_extensions

    @Slot(str)
    def addSavedCustomExtension(self, ext: str):
        """Adds one or more custom extensions (comma/space separated) to the permanent saved list and activates them."""
        if not ext:
            return
        tokens = FilterEngine.parse_extensions_list(ext)
        if not tokens:
            return
        changed = False
        for t in sorted(tokens):
            if t not in self._saved_custom_extensions:
                self._saved_custom_extensions.append(t)
                changed = True
            if not self.isExactExtensionActive(t):
                self.toggleExactExtension(t)
        if changed:
            self.savedCustomExtensionsChanged.emit()
            self.saveSettings()

    @Slot(str)
    def removeSavedCustomExtension(self, ext: str):
        """Removes a custom extension from the permanent saved list."""
        if not ext:
            return
        ext = ext.strip().lower().lstrip("*")
        if not ext.startswith("."):
            ext = "." + ext
        if ext in self._saved_custom_extensions:
            self._saved_custom_extensions.remove(ext)
            self.savedCustomExtensionsChanged.emit()
            self.saveSettings()
        if self.isExactExtensionActive(ext):
            self.toggleExactExtension(ext)

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
            self.saveSettings()

    @Property(bool, notify=fallbackToThumbnailsChanged)
    def fallbackToThumbnails(self) -> bool:
        return self._fallback_to_thumbnails

    @fallbackToThumbnails.setter
    def fallbackToThumbnails(self, val: bool):
        if self._fallback_to_thumbnails != val:
            self._fallback_to_thumbnails = val
            self.fallbackToThumbnailsChanged.emit()
            self.saveSettings()

    @Property(bool, notify=redownloadSmallFilesChanged)
    def redownloadSmallFiles(self) -> bool:
        return self._redownload_small_files

    @redownloadSmallFiles.setter
    def redownloadSmallFiles(self, val: bool):
        if self._redownload_small_files != val:
            self._redownload_small_files = val
            self.redownloadSmallFilesChanged.emit()
            self.saveSettings()

    @Property(bool, notify=skipPostCoversChanged)
    def skipPostCovers(self) -> bool:
        return self._skip_post_covers

    @skipPostCovers.setter
    def skipPostCovers(self, val: bool):
        if self._skip_post_covers != val:
            self._skip_post_covers = val
            self.skipPostCoversChanged.emit()
            self.saveSettings()

    @Property(bool, notify=scanContentImagesChanged)
    def scanContentImages(self) -> bool:
        return self._scan_content_images

    @scanContentImages.setter
    def scanContentImages(self, val: bool):
        if self._scan_content_images != val:
            self._scan_content_images = val
            self.scanContentImagesChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=downloadPawchiveTemporaryFilesChanged)
    def downloadPawchiveTemporaryFiles(self) -> bool:
        return self._download_pawchive_temporary_files

    @downloadPawchiveTemporaryFiles.setter
    def downloadPawchiveTemporaryFiles(self, val: bool):
        if self._download_pawchive_temporary_files != val:
            self._download_pawchive_temporary_files = val
            self.downloadPawchiveTemporaryFilesChanged.emit()
            self.saveSettings()

    @Property(bool, notify=compressWebpChanged)
    def compressWebp(self) -> bool:
        return self._compress_webp

    @compressWebp.setter
    def compressWebp(self, val: bool):
        if self._compress_webp != val:
            self._compress_webp = val
            self.compressWebpChanged.emit()
            self._settings_save_timer.start()

    @Property(str, notify=webpQualityChanged)
    def webpQuality(self) -> str:
        """How strongly "Compress to WebP" compresses: lossless / high / balanced / small / smallest."""
        return self._webp_quality

    @webpQuality.setter
    def webpQuality(self, val: str):
        from core.filter_engine import WEBP_QUALITY_LEVELS
        val = str(val or "").lower()
        if val not in WEBP_QUALITY_LEVELS:
            val = "balanced"
        if self._webp_quality != val:
            self._webp_quality = val
            self.webpQualityChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=writeAudioMetadataChanged)
    def writeAudioMetadata(self) -> bool:
        return self._write_audio_metadata

    @writeAudioMetadata.setter
    def writeAudioMetadata(self, val: bool):
        if self._write_audio_metadata != val:
            self._write_audio_metadata = val
            self.writeAudioMetadataChanged.emit()
            self.saveSettings()

    @Property(bool, notify=keepDuplicatesChanged)
    def keepDuplicates(self) -> bool:
        return self._keep_duplicates

    @keepDuplicates.setter
    def keepDuplicates(self, val: bool):
        if self._keep_duplicates != val:
            self._keep_duplicates = val
            self.keepDuplicatesChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=favoriteModeChanged)
    def favoriteMode(self) -> bool:
        return self._favorite_mode

    @favoriteMode.setter
    def favoriteMode(self, val: bool):
        if self._favorite_mode != val:
            self._favorite_mode = val
            self.favoriteModeChanged.emit()
            if self._favorite_mode:
                self.checkFavoriteModeAuth()

    def get_provider_for_domain(self, domain_or_url: str) -> str:
        d = (domain_or_url or "").lower()
        if "coomer" in d:
            return "coomer"
        if "pawchive" in d:
            return "pawchive"
        if "cum.st" in d or "cumst" in d:
            return "cumst"
        return "kemono"

    @Slot(result=bool)
    def checkFavoriteModeAuth(self) -> bool:
        """
        Validates whether the user has a valid account connected for the current URL
        (or at least one account connected if no URL is entered) when Favorite Mode is active.
        If not authenticated, emits favoriteAuthRequired with the provider name.
        Returns True if authenticated, False if auth is required.
        """
        if not self._favorite_mode:
            return True

        from core.auth_manager import auth_manager
        url_input = (self._current_url or "").strip()
        if url_input:
            from core.parser import KemonoURLParser
            parsed = KemonoURLParser.parse(url_input)
            if parsed.is_valid:
                prov_id = self.get_provider_for_domain(parsed.domain)
                if not auth_manager.is_logged_in(prov_id):
                    meta = auth_manager.get_provider_summary(prov_id)
                    pname = meta.get("name", prov_id.capitalize())
                    logger.warning(f"⭐ Favorite Mode active but no account connected for {pname}.", category="auth")
                    self.favoriteAuthRequired.emit(pname)
                    return False
                return True

        # No URL or invalid URL: check if ANY provider is logged in
        from core.providers import is_disabled
        if not any(auth_manager.is_logged_in(p) for p in ("kemono", "coomer", "pawchive", "cumst") if not is_disabled(p)):
            logger.warning("⭐ Favorite Mode requires a connected account.", category="auth")
            self.favoriteAuthRequired.emit("Kemono")
            return False

        return True

    @Property(bool, notify=subfolderPerPostChanged)
    def subfolderPerPost(self) -> bool:
        return self._subfolder_per_post

    @subfolderPerPost.setter
    def subfolderPerPost(self, val: bool):
        if self._subfolder_per_post != val:
            self._subfolder_per_post = val
            self.subfolderPerPostChanged.emit()
            self._settings_save_timer.start()

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
            self._settings_save_timer.start()

    @Property(bool, notify=downloadRevisionsChanged)
    def downloadRevisions(self) -> bool:
        return self._download_revisions

    @downloadRevisions.setter
    def downloadRevisions(self, val: bool):
        if self._download_revisions != val:
            self._download_revisions = val
            self.downloadRevisionsChanged.emit()
            self._settings_save_timer.start()

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
            if val and not self._is_downloading and self._has_failed_tasks():
                logger.info("Auto-Retry enabled with failed tasks present — starting retry queue...", category="downloader")
                self._retry_failed(include_cancelled=False)

    @Slot()
    def toggleAutoRetry(self):
        """Toggles auto-retry; if turning on (or if already on with failed tasks idle), immediately retries failed tasks."""
        if not self._auto_retry_at_end:
            self.autoRetryAtEnd = True
        else:
            if not self._is_downloading and self._has_failed_tasks():
                logger.info("Auto-Retry activated for failed tasks...", category="downloader")
                self._retry_failed(include_cancelled=False)
            else:
                self.autoRetryAtEnd = False

    @Property(bool, notify=skipRetry404Changed)
    def skipRetry404(self) -> bool:
        return self._skip_retry_404

    @skipRetry404.setter
    def skipRetry404(self, val: bool):
        val = bool(val)
        if self._skip_retry_404 != val:
            self._skip_retry_404 = val
            self.skipRetry404Changed.emit()
            self.saveSettings()
            if hasattr(self.downloader, "current_options") and self.downloader.current_options:
                self.downloader.current_options.skip_retry_404 = val
            if hasattr(self, "_queue_model") and self._queue_model:
                self._queue_model.failedCountChanged.emit()

    @Property(bool, notify=mangaModeChanged)
    def mangaMode(self) -> bool:
        return self._manga_mode

    @mangaMode.setter
    def mangaMode(self, val: bool):
        if self._manga_mode != val:
            self._manga_mode = val
            self.mangaModeChanged.emit()
            self._settings_save_timer.start()

    @Property(str, notify=filenameStyleChanged)
    def filenameStyle(self) -> str:
        return self._filename_style

    @filenameStyle.setter
    def filenameStyle(self, val: str):
        if self._filename_style != val:
            self._filename_style = val
            self.filenameStyleChanged.emit()
            self.saveSettings()

    @Property(str, notify=filenameTemplateChanged)
    def filenameTemplate(self) -> str:
        return self._filename_template

    @filenameTemplate.setter
    def filenameTemplate(self, val: str):
        if self._filename_template != val:
            self._filename_template = val
            self.filenameTemplateChanged.emit()
            self.saveSettings()

    @Property(bool, notify=postSelectionLoadingChanged)
    def postSelectionLoading(self) -> bool:
        return self._is_post_selection_loading

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
        # Strict Telegram ceiling: Under any circumstance, clamp to max 2 threads for Telegram
        is_pure_tg = False
        if hasattr(self, "downloader") and self.downloader.tasks:
            is_pure_tg = all(
                getattr(t, "is_telegram", False) or getattr(t, "service", "") == "telegram" or (t.url and t.url.startswith("tg://"))
                for t in self.downloader.tasks
            )
        if is_pure_tg:
            val = min(val, 2)

        if self._threads_count != val:
            self._threads_count = max(1, min(self._max_cpu_threads, val))
            self.downloader.max_workers = self._threads_count
            self.threadsCountChanged.emit()
            self._settings_save_timer.start()

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
            self._cookie_save_timer.start()      # saved once typing stops
            self.cookieStringChanged.emit()

    @Slot()
    def _persist_cookie(self):
        try:
            from core.auth_manager import auth_manager
            # The general cookie is kept in the vault's "kemono" slot (never in settings.json)
            auth_manager.set_credential("kemono", {"cookie": self._cookie_string})
            self.providersChanged.emit()
        except Exception as e:
            logger.debug(f"Could not save the cookie: {e}", category="auth")

    @Property(str, notify=userAgentChanged)
    def userAgent(self) -> str:
        return self._user_agent

    @userAgent.setter
    def userAgent(self, val: str):
        if self._user_agent != val:
            self._user_agent = val
            self.api_client.set_user_agent(val)
            self.userAgentChanged.emit()
            self._settings_save_timer.start()

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

    @hasError.setter
    def hasError(self, val: bool):
        val = bool(val)
        if self._has_error != val:
            self._has_error = val
            self.hasErrorChanged.emit()

    @Property(str, notify=lastErrorMessageChanged)
    def lastErrorMessage(self) -> str:
        return self._last_error_message

    @lastErrorMessage.setter
    def lastErrorMessage(self, val: str):
        val = str(val or "")
        if self._last_error_message != val:
            self._last_error_message = val
            self.lastErrorMessageChanged.emit()

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

    # ── Download Archive Database (gallery-dl style) ─────────────────────────
    @Property(bool, notify=enableDownloadArchiveChanged)
    def enableDownloadArchive(self) -> bool:
        return self._enable_download_archive

    @enableDownloadArchive.setter
    def enableDownloadArchive(self, val: bool):
        val = bool(val)
        if self._enable_download_archive != val:
            self._enable_download_archive = val
            self.archive_manager.set_enabled(val)
            self.enableDownloadArchiveChanged.emit()
            self.archiveRecordCountChanged.emit()
            self.saveSettings()

    @Property(int, notify=archiveRecordCountChanged)
    def archiveRecordCount(self) -> int:
        return self.archive_manager.get_total_count()

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
        """The Archive view's data, read in the background (a big archive froze the window on every
        refresh, every 1.5 s while downloading)."""
        def _load():
            return {
                "hierarchy": self.archive_manager.get_hierarchical_records(
                    query=query, service=service, file_type=fileType, sort_by=sortBy),
                "statistics": self.archive_manager.get_statistics(),
            }
        self._run_async(request_id, _load)

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

    @Property(bool, notify=archiveRebuildStatusChanged)
    def isArchiveRebuilding(self) -> bool:
        return self._is_archive_rebuilding

    @Property(bool, notify=archiveRebuildStatusChanged)
    def isArchiveRebuildPaused(self) -> bool:
        return self._is_archive_rebuild_paused

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

    @Slot(str, str, result=str)
    @Slot(str, result=str)
    @Slot(result=str)
    def browseFolderDialog(self, title: str = "Select Directory", initialDir: str = "") -> str:
        """Open a native OS directory picker dialog and return the selected folder path."""
        start_dir = initialDir if (initialDir and os.path.isdir(initialDir)) else (self._download_dir or os.path.expanduser("~"))
        folder = QFileDialog.getExistingDirectory(None, title or "Select Directory", start_dir)
        return os.path.normpath(folder) if folder else ""

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
        Completely non-blocking to the Qt main thread with live telemetry streaming.
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

        def _on_progress(data: dict):
            self._is_archive_rebuild_paused = data.get("is_paused", False)
            self.archiveRebuildProgress.emit(data)

        def _on_finished(stats: dict):
            self._is_archive_rebuilding = False
            self._is_archive_rebuild_paused = False
            self._archive_rebuilder = None
            self.archiveRecordCountChanged.emit()
            self.archiveUpdated.emit()
            self.archiveRebuildStatusChanged.emit()
            self.archiveRebuildFinished.emit(stats)

        self._archive_rebuilder = ArchiveRebuilder(
            archive_manager=self.archive_manager,
            directories=valid_dirs,
            options=opts,
            on_progress=_on_progress,
            on_finished=_on_finished
        )

        started = self._archive_rebuilder.start()
        if started:
            self._is_archive_rebuilding = True
            self._is_archive_rebuild_paused = False
            self.archiveRebuildStatusChanged.emit()
        return started

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
                    subprocess.Popen(["open", "-R" if os.path.isfile(clean_path) else "", clean_path])
                else:
                    subprocess.Popen(["xdg-open", os.path.dirname(clean_path) if os.path.isfile(clean_path) else clean_path])
                return True
        except Exception as e:
            logger.error(f"Failed to reveal file {filePath}: {e}", category="archive")
            return False

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

    @Property(bool, notify=aiRecognitionEnabledChanged)
    def aiRecognitionEnabled(self) -> bool:
        return self._ai_recognition_enabled

    @aiRecognitionEnabled.setter
    def aiRecognitionEnabled(self, val: bool):
        val = bool(val)
        if self._ai_recognition_enabled != val:
            self._ai_recognition_enabled = val
            self.known_manager.enable_ai(val, model_manager=self.model_manager)
            self.aiRecognitionEnabledChanged.emit()
            self.saveSettings()

    @Property(str, notify=aiEngineModeChanged)
    def aiEngineMode(self) -> str:
        return self._ai_engine_mode

    @aiEngineMode.setter
    def aiEngineMode(self, val: str):
        allowed = {"semantic_only", "hybrid"}
        if val in allowed and self._ai_engine_mode != val:
            self._ai_engine_mode = val
            self.known_manager.set_ai_engine_mode(val)
            self.aiEngineModeChanged.emit()
            self.saveSettings()

    @Property(str, notify=aiHardwareInfoChanged)
    def aiHardwareBadge(self) -> str:
        info = HardwareDetector.cached_info()
        if info is None:
            # Detected in the background; the badge updates when it's known
            HardwareDetector.probe_async(lambda: self.aiHardwareInfoChanged.emit())
            return "Detecting hardware…"
        return str(info.get("provider_name", "CPU Mode"))

    @Property(bool, notify=aiRecognitionEnabledChanged)
    def aiFastSemanticReady(self) -> bool:
        return self.model_manager.is_model_ready("fast_semantic")

    @Property(bool, notify=aiRecognitionEnabledChanged)
    def aiDeepReasonerReady(self) -> bool:
        from core.ai_reasoner import has_llama_cpp
        if not has_llama_cpp():
            return False
        return (
            self.model_manager.is_model_ready("deep_reasoner_heavy")
            or self.model_manager.is_model_ready("deep_reasoner_light")
            or self.model_manager.is_model_ready("deep_reasoner")
        )

    @Property(str, notify=aiRecognitionEnabledChanged)
    def aiDeepReasonerVariant(self) -> str:
        return self._ai_deep_reasoner_variant

    @aiDeepReasonerVariant.setter
    def aiDeepReasonerVariant(self, val: str):
        allowed = {"light", "heavy"}
        if val in allowed and self._ai_deep_reasoner_variant != val:
            self._ai_deep_reasoner_variant = val
            self.aiRecognitionEnabledChanged.emit()
            self.saveSettings()

    @Property(bool, notify=aiRecognitionEnabledChanged)
    def aiDeepReasonerLightReady(self) -> bool:
        return self.model_manager.is_model_ready("deep_reasoner_light")

    @Property(bool, notify=aiRecognitionEnabledChanged)
    def aiDeepReasonerHeavyReady(self) -> bool:
        return self.model_manager.is_model_ready("deep_reasoner_heavy")


    @Slot(str, result="QVariant")
    def getAiModelStatus(self, model_key: str):
        if HardwareDetector.cached_info() is None:
            # Hardware is detected in the background; the AI section refreshes when it's known
            HardwareDetector.probe_async(lambda: self.aiHardwareInfoChanged.emit())
        return self.model_manager.get_status(model_key)

    @Slot(str)
    def startAiModelDownload(self, model_key: str):
        self.model_manager.start_download(model_key)

    @Slot(str)
    def cancelAiModelDownload(self, model_key: str):
        self.model_manager.cancel_download(model_key)

    @Slot(str, result=bool)
    def deleteAiModel(self, model_key: str) -> bool:
        # A loaded model keeps its files open (Windows won't delete them), so unload it first
        km = getattr(self, "known_manager", None)
        for engine in (getattr(km, "semantic_matcher", None), getattr(km, "contextual_reasoner", None)):
            if engine is not None and hasattr(engine, "unload"):
                try:
                    engine.unload()
                except Exception:
                    logger.exception("Couldn't unload an AI model before deleting it", category="ai")
        res = self.model_manager.delete_model(model_key)
        self.aiRecognitionEnabledChanged.emit()
        return res

    @Slot(str, result="QVariant")
    def testAiRecognition(self, test_title: str):
        """Runs test inference across Tier 0, Tier 1, and Tier 2 for interactive sandbox."""
        clean_t = (test_title or "").strip()
        if not clean_t:
            return {"error": "Empty test title"}

        # Tier 0 (Fast heuristic)
        t0_res = self.known_manager._find_matching_hierarchy_fast(clean_t, [], [])
        t0_str = f"{t0_res[1]} ({t0_res[0]})" if (t0_res and t0_res[1]) else (t0_res[0] if t0_res else "None")

        # Tier 1 (Semantic matcher)
        t1_str = "Not available (model not downloaded)"
        if self.model_manager.is_model_ready("fast_semantic"):
            if self.known_manager.semantic_matcher:
                if self.known_manager.semantic_matcher._cached_vectors is None:
                    self.known_manager.semantic_matcher.build_known_index(self.known_manager)
                m = self.known_manager.semantic_matcher.find_match(clean_t, threshold=0.70)
                if m:
                    t1_str = f"{m[1]} ({m[0]}) [score={m[2]:.2f}]"
                else:
                    t1_str = "No match above threshold"

        # Final resolved hierarchy using standard engine
        final = self.known_manager.find_matching_hierarchy(clean_t)
        final_str = f"{final[1]} ({final[0]})" if (final and final[1]) else (final[0] if final else "Uncategorized")

        return {
            "title": clean_t,
            "tier0": t0_str,
            "tier1": t1_str,
            "final": final_str,
            "hardware": (HardwareDetector.cached_info() or {}).get("provider_name", "Detecting hardware…")
        }

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

    @Property(bool, notify=watchlistApplyGlobalSettingsChanged)
    def watchlistApplyGlobalSettings(self) -> bool:
        return self._watchlist_apply_global_settings

    @watchlistApplyGlobalSettings.setter
    def watchlistApplyGlobalSettings(self, val: bool):
        b_val = bool(val)
        if self._watchlist_apply_global_settings != b_val:
            self._watchlist_apply_global_settings = b_val
            self.watchlistApplyGlobalSettingsChanged.emit()
            self.saveSettings()

    @Property(QObject, constant=True)
    def decompressorBridge(self) -> DecompressorBridge:
        return self._decompressor_bridge

    @Property(QObject, constant=True)
    def telegramBridge(self) -> TelegramBridge:
        return self._telegram_bridge

    @Property(bool, notify=tagFolderModeChanged)
    def tagFolderMode(self) -> bool:
        return self._tag_folder_mode

    @tagFolderMode.setter
    def tagFolderMode(self, val: bool):
        if self._tag_folder_mode != val:
            self._tag_folder_mode = val
            self.tagFolderModeChanged.emit()
            self.saveSettings()

    @Property(str, notify=groupFileTypeChanged)
    def groupFileType(self) -> str:
        return self._group_file_type

    @groupFileType.setter
    def groupFileType(self, val: str):
        val = str(val or "none").lower()
        if val not in ("none", "post", "creator"):
            val = "none"
        if self._group_file_type != val:
            self._group_file_type = val
            self.groupFileTypeChanged.emit()
            self.saveSettings()

    @Property(str, notify=fileOrderChanged)
    def fileOrder(self) -> str:
        """Order of the files inside a post: "posted", "reversed" or "name"."""
        return self._file_order

    @fileOrder.setter
    def fileOrder(self, val: str):
        val = normalize_file_order(val)
        if self._file_order != val:
            self._file_order = val
            self.fileOrderChanged.emit()
            self._settings_save_timer.start()

    @Slot("QVariantList", result="QVariantList")
    def orderPostFiles(self, files):
        """A post's files in the order they'll be numbered (for the Post Selection window).

        Each file remembers its place on the site ("postedIndex"), so switching the order back and
        forth always starts from the posted order.
        """
        items = [dict(f) for f in (files or []) if isinstance(f, dict)]
        for i, f in enumerate(items):
            f.setdefault("postedIndex", i)
        items.sort(key=lambda f: int(f.get("postedIndex") or 0))
        return order_files(items, self._file_order, lambda f: str(f.get("name") or ""))

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

    @Property(bool, notify=telegramSafetyAcknowledgedChanged)
    def telegramSafetyAcknowledged(self) -> bool:
        return self._telegram_safety_acknowledged

    @telegramSafetyAcknowledged.setter
    def telegramSafetyAcknowledged(self, val: bool):
        if self._telegram_safety_acknowledged != val:
            self._telegram_safety_acknowledged = val
            self.telegramSafetyAcknowledgedChanged.emit()
            self.saveSettings()

    @Property(bool, notify=telegramLiabilityAcknowledgedChanged)
    def telegramLiabilityAcknowledged(self) -> bool:
        return self._telegram_liability_acknowledged

    @telegramLiabilityAcknowledged.setter
    def telegramLiabilityAcknowledged(self, val: bool):
        if self._telegram_liability_acknowledged != val:
            self._telegram_liability_acknowledged = val
            self.telegramLiabilityAcknowledgedChanged.emit()
            self.saveSettings()

    @Slot(bool)
    def setTelegramSafetyAcknowledged(self, val: bool):
        self.telegramSafetyAcknowledged = val

    @Slot(bool)
    def setTelegramLiabilityAcknowledged(self, val: bool):
        self.telegramLiabilityAcknowledged = val

    @Slot()
    def resetTelegramWarnings(self):
        self._telegram_safety_acknowledged = False
        self._telegram_liability_acknowledged = False
        self.telegramSafetyAcknowledgedChanged.emit()
        self.telegramLiabilityAcknowledgedChanged.emit()
        self.saveSettings()
        logger.info("Telegram warning modals reset.", category="telegram")

    def _get_filter_options(self) -> FilterOptions:
        return FilterOptions(
            characters=self._filter_characters,
            character_scope=self._character_scope,
            skip_words=self._skip_words,
            skip_scope=self._skip_scope,
            remove_words=self._remove_words,
            file_type=self._filter_type,
            exact_extensions=self._exact_extensions,
            skip_archives=self._skip_archives,
            download_thumbnails_only=self._download_thumbnails_only,
            fallback_to_thumbnails=self._fallback_to_thumbnails,
            redownload_small_files=self._redownload_small_files,
            scan_content_images=self._scan_content_images,
            compress_to_webp=self._compress_webp,
            webp_quality=self._webp_quality,
            keep_duplicates=self._keep_duplicates,
            favorite_mode=self._favorite_mode,
            subfolder_per_post=self._subfolder_per_post,
            date_prefix=self._date_prefix,
            file_index_prefix=self._file_index_prefix,
            separate_by_known=self._separate_folders_by_known,
            download_revisions=self._download_revisions,
            adaptive_threading=self._adaptive_threading,
            threads_locked=self._threads_locked,
            # Scheduled runs with "Sweep auto-retry pass" retry failed files at the end
            auto_retry_at_end=self._auto_retry_at_end or getattr(self, "_scheduled_sweep_retry", False),
            manga_mode=self._manga_mode,
            filename_style=self._filename_style,
            filename_template=self._filename_template,
            proxy_url=self._proxy_url,
            page_start=self._page_start,
            page_end=self._page_end,
            download_delay=self._download_delay,
            save_post_metadata=self._save_post_metadata,
            download_embeds=self._download_embeds,
            tag_folder_mode=self._tag_folder_mode,
            skip_post_covers=self._skip_post_covers,
            date_after=self._date_after,
            date_before=self._date_before,
            download_pawchive_temporary_files=self._download_pawchive_temporary_files,
            min_file_size=self._min_file_size,
            max_file_size=self._max_file_size,
            write_audio_metadata=self._write_audio_metadata,
            skip_retry_404=self._skip_retry_404,
            group_file_type=self._group_file_type,
            file_order=self._file_order
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
            if parsed_current.is_valid and self._refuse_if_disabled(url_input):
                return
            if parsed_current.is_valid:
                if parsed_current.provider == "telegram":
                    has_pending_telegram = any(
                        getattr(t, "is_telegram", False) and t.status in ("pending", "failed", "cancelled")
                        for t in self.downloader.tasks
                    ) or any(
                        getattr(t, "is_telegram", False) and t.status in ("pending", "failed", "cancelled")
                        for t in self._queue_model.tasks
                    )
                    if has_pending or has_pending_telegram:
                        # Tasks already queued — fall through to start existing queue
                        url_input = ""
                        parsed_current = None
                        url_is_already_queued = False
                    else:
                        # Empty queue: open Scope Modal for criteria-based download
                        self.telegramScopeRequested.emit(
                            str(parsed_current.user_id),
                            str(parsed_current.raw_url),
                            bool(parsed_current.extra_data.get("is_private", False)),
                            "download"
                        )
                        return
                else:
                    _, identity_key, parent_artist_key, _ = self._get_link_identity(parsed_current)
                    if identity_key in self._queued_links or (parent_artist_key and parent_artist_key in self._queued_links):
                        url_is_already_queued = True

        # Case 1: Start existing queue directly if URL is empty or already queued
        if has_pending and (not url_input or url_is_already_queued):
            # Under ANY circumstance, lock Telegram downloads to max 2 threads
            is_pure_tg = bool(self.downloader.tasks) and all(
                getattr(t, "is_telegram", False) or getattr(t, "service", "") == "telegram" or (t.url and t.url.startswith("tg://"))
                for t in self.downloader.tasks
            )
            if is_pure_tg:
                self._threads_count = min(self._threads_count, 2)
                self.downloader.max_workers = min(self.downloader.max_workers, 2)
                self.threadsCountChanged.emit()

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
            if self._favorite_mode:
                if not self.checkFavoriteModeAuth():
                    self._status_text = "Favorite Mode: Please connect account in Settings → Accounts"
                    self.statusTextChanged.emit()
                    return
                self._start_favorites_download_worker()
                return

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
        if self._favorite_mode:
            if not self.checkFavoriteModeAuth():
                return

        # Files already in the queue (or left by an interrupted session) are kept: the new link's
        # files are added to them. This used to throw the queue and the crash-recovery journal away.
        # A queue holding only finished files is cleared, so it doesn't keep growing.
        current = self.downloader.tasks or self._queue_model.tasks
        if current and all(t.status in ("completed", "skipped") for t in current):
            self._queue_model.clear()
            self._active_queue_model.clear()
            self.downloader.reset_state()
        if self._has_recovery_session and not self.downloader.tasks and self._queue_model.rowCount() == 0:
            recovered = self._load_recovery_tasks()
            if recovered:
                self._queue_model.setTasks(recovered)
                self._active_queue_model.setTasks(recovered)
                self.downloader.tasks = list(recovered)
                left = sum(1 for t in recovered if t.status not in ("completed", "skipped"))
                logger.info(f"Kept {left} unfinished file(s) from the interrupted session in the queue.", category="session")
            self._has_recovery_session = False
            self._recovery_summary = {}
            self.hasRecoverySessionChanged.emit()
        if not self.downloader.tasks and self._queue_model.rowCount() > 0:
            self.downloader.tasks = list(self._queue_model.tasks)


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
                if self._refuse_if_disabled(u):
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

    @Slot(str, result=str)
    def previewCustomFilename(self, template: str) -> str:
        """Evaluate a custom filename template against realistic sample metadata for live preview."""
        opts = FilterOptions(
            filename_style=FilenameStyles.CUSTOM,
            filename_template=template
        )
        return FilterEngine.format_custom_filename(
            original_filename="sample_illustration.png",
            post_title="Excited Artwork #10",
            post_date="2026-09-17",
            post_index=1,
            file_index=1,
            options=opts,
            folder_index=1,
            post_id="167342511",
            artist="SampleArtist",
            service="patreon",
            user_id="82901778"
        )

    @Slot()
    def fetchPostsForSelection(self):
        """
        Fetches creator profile and posts in a background worker for the interactive
        PostSelectionModal so the user can visually review and check/uncheck items before downloading.
        """
        if self._is_post_selection_loading:
            return

        url_input = (self._current_url or "").strip()
        if not url_input:
            if self._favorite_mode:
                if not self.checkFavoriteModeAuth():
                    self.postSelectionError.emit("Favorite Mode requires an account login in Settings → Accounts.")
                    return
                self._start_favorites_post_selection_worker()
                return
            self.postSelectionError.emit("Please enter a creator or post URL first.")
            return

        parsed = KemonoURLParser.parse(url_input)
        if not parsed.is_valid:
            self.postSelectionError.emit(parsed.error_msg or "Invalid URL")
            return
        if self._refuse_if_disabled(url_input):
            from core.providers import disabled_message
            self.postSelectionError.emit(disabled_message(url_input))
            return

        if self._favorite_mode:
            if not self.checkFavoriteModeAuth():
                prov_id = self.get_provider_for_domain(parsed.domain)
                self.postSelectionError.emit(f"Favorite Mode requires an account login for {prov_id.capitalize()} in Settings → Accounts.")
                return

        self._is_post_selection_loading = True
        self.postSelectionLoadingChanged.emit()

        def _worker():
            try:
                creator_name = ""
                posts = []

                if parsed.is_external_provider:
                    creator_name = parsed.domain
                    if parsed.provider == "bunkr":
                        album_title, files = fetch_bunkr_album(parsed.raw_url, resolve_files=True)
                        creator_name = clean_text(album_title) or "Bunkr Album"
                        posts = [{"id": f["url"], "title": f.get("filename", "File"), "published": "", "file": {"path": f["url"], "name": f.get("filename", "")}, "attachments": []} for f in files]
                    elif parsed.provider == "erome":
                        album_title, files = fetch_erome_album(parsed.raw_url)
                        creator_name = clean_text(album_title) or "Erome Album"
                        posts = [{"id": f["url"], "title": f.get("filename", "File"), "published": "", "file": {"path": f["url"], "name": f.get("filename", "")}, "attachments": []} for f in files]
                    elif parsed.provider == "nhentai":
                        gallery_title, files = fetch_nhentai_gallery(parsed.post_id or parsed.raw_url)
                        creator_name = clean_text(gallery_title) or f"Gallery {parsed.post_id}"
                        posts = [{"id": f["url"], "title": f.get("filename", "File"), "published": "", "file": {"path": f["url"], "name": f.get("filename", "")}, "attachments": []} for f in files]
                    elif parsed.provider == "telegram":
                        self._telegram_pending_action = "select"
                        if not TelegramService.instance().is_logged_in():
                            self._is_post_selection_loading = False
                            self.postSelectionLoadingChanged.emit()
                            self.telegramAuthRequested.emit(bool(parsed.extra_data.get("is_private", False)))
                            return

                        if parsed.is_single_post:
                            post = TelegramService.instance().fetch_single_post(parsed.user_id, int(parsed.post_id))
                            if post:
                                creator_name = clean_text(post.get("channel_title", parsed.user_id))
                                posts = [{
                                    "id": str(post["id"]),
                                    "title": post.get("title", f"Telegram {post['id']}"),
                                    "published": post.get("date", ""),
                                    "file": {"name": post.get("filename", ""), "path": post["url"], "size": post.get("file_size", 0)},
                                    "attachments": [],
                                    "extra_data": {
                                        "channel_id": str(post.get("channel_id", parsed.user_id)),
                                        "message_id": int(post.get("message_id", 0))
                                    }
                                }]
                        else:
                            self._is_post_selection_loading = False
                            self.postSelectionLoadingChanged.emit()
                            self.telegramScopeRequested.emit(
                                str(parsed.user_id),
                                str(parsed.raw_url),
                                bool(parsed.extra_data.get("is_private", False)),
                                "select"
                            )
                            return
                else:
                    profile = self.api_client.fetch_creator_profile(parsed)
                    creator_name = clean_text(profile.get("name", parsed.user_id) or parsed.user_id)
                    if parsed.is_single_post:
                        single = self.api_client.fetch_single_post(parsed)
                        posts = [single] if single else []
                    else:
                        effective_page_end = self._page_end
                        if self._date_auto_scan_pages and (self._date_after or self._date_before):
                            effective_page_end = 999999
                        posts = self.api_client.fetch_user_posts(
                            parsed=parsed,
                            page_start=self._page_start,
                            page_end=effective_page_end,
                            date_after=self._date_after,
                            date_before=self._date_before,
                            cancel_event=self._scan_cancel_event
                        )

                if not posts:
                    self._is_post_selection_loading = False
                    self.postSelectionLoadingChanged.emit()
                    self.postSelectionError.emit(f"No posts found for {creator_name or 'URL'}.")
                    return

                self._selection_cached_posts = list(posts)
                self._selection_parsed = parsed
                self._selection_creator_name = creator_name

                # Build cards list for UI
                cards = []
                domain = parsed.domain or "pawchive.pw"
                for p in posts:
                    pid = str(p.get("id", ""))
                    raw_title = p.get("title") or p.get("caption") or "Untitled Post"
                    title = re.sub(r'<[^>]+>', '', str(raw_title)).strip() or "Untitled Post"
                    published = str(p.get("published") or "")[:10]

                    image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif")
                    def _is_image(p_str: str) -> bool:
                        if not p_str:
                            return False
                        return p_str.lower().split("?")[0].endswith(image_exts)

                    thumb_url = ""
                    f = p.get("file")
                    if f and isinstance(f, dict):
                        fpath = f.get("path") or ""
                        fname = f.get("name") or ""
                        if fpath and (_is_image(fpath) or _is_image(fname)):
                            clean_p = fpath if fpath.startswith("/") else f"/{fpath}"
                            if clean_p.startswith("/data/"):
                                clean_p = clean_p[5:]
                            thumb_url = f"https://img.{domain}/thumbnail/data{clean_p}"
                    if not thumb_url:
                        for att in p.get("attachments", []) or []:
                            if isinstance(att, dict) and att.get("path"):
                                apath = att["path"]
                                aname = att.get("name") or ""
                                if _is_image(apath) or _is_image(aname):
                                    clean_p = apath if apath.startswith("/") else f"/{apath}"
                                    if clean_p.startswith("/data/"):
                                        clean_p = clean_p[5:]
                                    thumb_url = f"https://img.{domain}/thumbnail/data{clean_p}"
                                    break

                    post_files = []
                    # 1. Main post file
                    if f and isinstance(f, dict) and (f.get("path") or f.get("storageKey")):
                        mf_name = f.get("name") or os.path.basename(f.get("path", "") or "main_file")
                        mf_path = f.get("path") or ""
                        mf_thumb = ""
                        if mf_path and (_is_image(mf_path) or _is_image(mf_name)):
                            clean_p = mf_path if mf_path.startswith("/") else f"/{mf_path}"
                            if clean_p.startswith("/data/"):
                                clean_p = clean_p[5:]
                            mf_thumb = f"https://img.{domain}/thumbnail/data{clean_p}"
                        post_files.append({
                            "name": mf_name,
                            "path": mf_path,
                            "thumbnail": mf_thumb,
                            "previewUrl": mf_thumb,
                            "is_main": True,
                            "selected": True
                        })

                    # 2. Attachments
                    for att in p.get("attachments", []) or []:
                        if isinstance(att, dict) and (att.get("path") or att.get("storageKey")):
                            att_name = att.get("name") or os.path.basename(att.get("path", "") or "attachment")
                            att_path = att.get("path") or ""
                            att_thumb = ""
                            if att_path and (_is_image(att_path) or _is_image(att_name)):
                                clean_p = att_path if att_path.startswith("/") else f"/{att_path}"
                                if clean_p.startswith("/data/"):
                                    clean_p = clean_p[5:]
                                att_thumb = f"https://img.{domain}/thumbnail/data{clean_p}"
                            post_files.append({
                                "name": att_name,
                                "path": att_path,
                                "thumbnail": att_thumb,
                                "previewUrl": att_thumb,
                                "is_main": False,
                                "selected": True
                            })

                    # Clean post content / description
                    import html
                    raw_content = p.get("content") or p.get("captionHtml") or p.get("caption") or ""
                    clean_content = re.sub(r'<br\s*/?>', '\n', str(raw_content), flags=re.IGNORECASE)
                    clean_content = html.unescape(re.sub(r'<[^>]+>', '', clean_content).strip())

                    cards.append({
                        "id": pid,
                        "title": title,
                        "content": clean_content,
                        "published": published,
                        "thumbnail": thumb_url,
                        "fileCount": len(post_files),
                        "files": [dict(pf, postedIndex=i) for i, pf in enumerate(post_files)],
                        "selected": True
                    })

                self._is_post_selection_loading = False
                self.postSelectionLoadingChanged.emit()
                self.postSelectionReady.emit(cards, creator_name, len(cards))

            except Exception as ex:
                logger.error(f"Error fetching posts for selection: {ex}", category="api")
                self._has_error = True
                self._last_error_message = str(ex)
                self.hasErrorChanged.emit()
                self.lastErrorMessageChanged.emit()
                self._is_post_selection_loading = False
                self.postSelectionLoadingChanged.emit()
                self.postSelectionError.emit(str(ex))

        threading.Thread(target=_worker, daemon=True).start()

    def _start_favorites_post_selection_worker(self):
        """Fetches account favorites for display in the interactive post selector modal."""
        self._is_post_selection_loading = True
        self.postSelectionLoadingChanged.emit()

        def _worker():
            try:
                from core.auth_manager import auth_manager
                from core.providers import is_disabled
                # The first site with a login that isn't switched off (Kemono / Coomer are off for now)
                domain, prov_id = "pawchive.pw", "pawchive"
                for _dom, _prov in (("kemono.cr", "kemono"), ("coomer.st", "coomer"),
                                    ("pawchive.pw", "pawchive"), ("cum.st", "cumst")):
                    if not is_disabled(_prov) and auth_manager.is_logged_in(_prov):
                        domain, prov_id = _dom, _prov
                        break

                saved_cookie = auth_manager.get_credential(prov_id, "cookie")
                if saved_cookie:
                    self._cookie_string = saved_cookie
                    self.api_client.set_cookie(saved_cookie)

                creator_name = "Account Favorites"
                posts = self.api_client.fetch_user_favorites(
                    domain=domain,
                    fav_type="post",
                    cancel_event=self._scan_cancel_event
                )

                if not posts:
                    self._is_post_selection_loading = False
                    self.postSelectionLoadingChanged.emit()
                    self.postSelectionError.emit("No favorited posts found on your account.")
                    return

                self._selection_cached_posts = list(posts)
                self._selection_parsed = KemonoURLParser.parse(f"https://{domain}/favorites")
                self._selection_creator_name = creator_name

                # Build cards list for UI
                cards = []
                image_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif")
                for p in posts:
                    pid = str(p.get("id", ""))
                    raw_title = p.get("title") or p.get("caption") or "Untitled Post"
                    title = re.sub(r'<[^>]+>', '', str(raw_title)).strip() or "Untitled Post"
                    published = str(p.get("published") or "")[:10]

                    thumb_url = ""
                    f = p.get("file")
                    if f and isinstance(f, dict):
                        fpath = f.get("path") or ""
                        fname = f.get("name") or ""
                        if any((fpath or fname).lower().split("?")[0].endswith(ext) for ext in image_exts):
                            thumb_url = fpath if fpath.startswith("http") else f"https://{domain}/data{fpath}"

                    if not thumb_url:
                        for att in (p.get("attachments") or []):
                            if isinstance(att, dict):
                                apath = att.get("path") or ""
                                aname = att.get("name") or ""
                                if any((apath or aname).lower().split("?")[0].endswith(ext) for ext in image_exts):
                                    thumb_url = apath if apath.startswith("http") else f"https://{domain}/data{apath}"
                                    break

                    p_service = p.get("service") or "post"
                    p_user = p.get("username") or p.get("user") or ""
                    post_files_count = (1 if p.get("file") else 0) + len(p.get("attachments") or [])
                    cards.append({
                        "id": pid,
                        "title": f"[{p_user}] {title}" if p_user else title,
                        "published": published,
                        "service": p_service,
                        "userId": p_user,
                        "thumbnailUrl": thumb_url,
                        "filesCount": post_files_count,
                        "selected": True,
                        "files": []
                    })

                self._is_post_selection_loading = False
                self.postSelectionLoadingChanged.emit()
                self.postSelectionReady.emit(cards, creator_name, len(cards))
            except Exception as ex:
                logger.error(f"Error fetching favorites for selection: {ex}", category="api")
                self._is_post_selection_loading = False
                self.postSelectionLoadingChanged.emit()
                self.postSelectionError.emit(str(ex))

        threading.Thread(target=_worker, daemon=True, name="FavSelectionWorker").start()

    @Slot()
    def resumeTelegramAction(self):
        """
        Resumes the pending action (fetchPostsForSelection or startDownload)
        after the user completes Telegram authentication.
        """
        action = self._telegram_pending_action or "select"
        self._telegram_pending_action = ""
        if action == "download":
            self.startDownload()
        else:
            self.fetchPostsForSelection()

    @Slot(str, list)
    @Slot(str, list, bool)
    def queueTelegramFiles(self, channel_title: str, files: list, auto_start: bool = True):
        """
        Queues resolved media files from TelegramScopeModal into the download engine.
        """
        if not files:
            return
        creator_name = clean_text(channel_title) or "Telegram Channel"
        folder_name = sanitize_filesystem_name(creator_name, fallback="Telegram")
        folder = os.path.join(self._download_dir, f"Telegram - {folder_name}")
        os.makedirs(folder, exist_ok=True)

        tasks = []
        taken = set()      # an album can hold different files with the same name
        for f in files:
            extra = f.get("extra_data", {}) if isinstance(f.get("extra_data"), dict) else {}
            cid = str(f.get("channel_id") or extra.get("channel_id", ""))
            mid = int(f.get("message_id") or extra.get("message_id", 0))
            f_obj = f.get("file") if isinstance(f.get("file"), dict) else {}
            # The uploader chooses this name: it must never lead outside the folder
            fn = safe_file_name(f.get("filename") or f_obj.get("name"), fallback=f"file_{mid}")
            url = f.get("url") or f_obj.get("path") or f"tg://{cid}/{mid}"
            fsize = int(f.get("file_size") or f_obj.get("size") or 0)

            t = DownloadTask(
                url=url,
                target_path=unique_name_in_batch(folder, fn, taken),
                post_title=creator_name,
                creator_name=creator_name,
                service="telegram",
                post_id=str(mid),
                file_id=str(f.get("id", mid)),
                file_size=fsize,
                is_telegram=True,
                telegram_channel_id=cid,
                telegram_message_id=mid,
                batch_id=f"telegram_{creator_name}"
            )
            tasks.append(t)

        self._queue_model.add_tasks(tasks)
        logger.info(f"Queued {len(tasks)} Telegram file(s) for '{creator_name}'.", category="telegram")

        # Under ANY circumstance, lock Telegram downloads to max 2 threads
        self._threads_count = min(self._threads_count, 2)
        self.downloader.max_workers = min(self.downloader.max_workers, 2)
        self.threadsCountChanged.emit()

        if auto_start and not self._is_downloading:
            self.startDownload()

    @Slot(str, list)
    @Slot(str, list, str)
    def openTelegramPostSelection(self, channel_title: str, messages: list, raw_url: str = ""):
        """
        Takes fetched Telegram channel messages, formats them into cards for PostSelectionModal,
        caches them for selection, and emits postSelectionReady to open the modal.
        """
        if not messages:
            self._is_post_selection_loading = False
            self.postSelectionLoadingChanged.emit()
            self.postSelectionError.emit(f"No media found in {channel_title or 'Telegram channel'}.")
            return

        creator_name = clean_text(channel_title) or "Telegram Channel"
        self._selection_cached_posts = list(messages)
        parsed_url = raw_url or (self._current_url or "")
        self._selection_parsed = KemonoURLParser.parse(parsed_url)
        self._selection_creator_name = creator_name

        cards = []
        for m in messages:
            mid = str(m.get("id") or m.get("message_id", ""))
            fn = m.get("filename") or f"file_{mid}"
            title = fn or m.get("title") or f"Telegram Media {mid}"
            caption = m.get("caption") or ""
            thumb = m.get("thumbnail") or ""
            fsize = int(m.get("file_size") or 0)
            url = m.get("url") or f"tg://{m.get('channel_id')}/{mid}"

            file_item = {
                "name": fn,
                "path": url,
                "thumbnail": thumb,
                "previewUrl": thumb,
                "size": fsize,
                "is_main": True,
                "selected": True
            }

            cards.append({
                "id": mid,
                "title": title,
                "content": caption,
                "published": m.get("date", "")[:10] if m.get("date") else "",
                "thumbnail": thumb,
                "fileCount": 1,
                "files": [file_item],
                "selected": True
            })

        self._is_post_selection_loading = False
        self.postSelectionLoadingChanged.emit()
        self.postSelectionReady.emit(cards, creator_name, len(cards))

    @Slot(list, bool)
    @Slot(list, bool, 'QVariant')
    def startDownloadSelectedPosts(self, selectedPostIds: list, autoStart: bool, selectedFilesMap: Any = None):
        """
        Given the list of selected post IDs from the PostSelectionModal,
        filters cached posts and builds download tasks for queueing or immediate start.
        If selectedFilesMap ({postId: [allowedPaths]}) is provided, only selected files are queued.
        """
        if not self._selection_cached_posts or not self._selection_parsed:
            logger.warning("No cached selection posts available.", category="downloader")
            return

        if hasattr(selectedFilesMap, "toVariant"):
            selectedFilesMap = selectedFilesMap.toVariant()
        elif isinstance(selectedFilesMap, str):
            try:
                selectedFilesMap = json.loads(selectedFilesMap)
            except Exception:
                pass

        files_map = {str(k): v for k, v in selectedFilesMap.items()} if isinstance(selectedFilesMap, dict) else {}

        def _norm_path(p):
            if not p:
                return ""
            s = str(p).replace("\\", "/").strip()
            if s.startswith("/data/"):
                s = s[5:]
            if not s.startswith("/"):
                s = "/" + s
            return s.lower()

        if hasattr(selectedPostIds, "toVariant"):
            selectedPostIds = selectedPostIds.toVariant()
        elif isinstance(selectedPostIds, str):
            try:
                selectedPostIds = json.loads(selectedPostIds)
            except Exception:
                pass
        if not isinstance(selectedPostIds, (list, set, tuple)):
            selectedPostIds = [selectedPostIds] if selectedPostIds else []

        selected_id_set = {str(pid) for pid in selectedPostIds}
        filtered_posts = []
        for p in self._selection_cached_posts:
            pid = str(p.get("id", ""))
            if pid not in selected_id_set:
                continue

            if files_map and pid in files_map:
                raw_allowed = files_map[pid]
                if isinstance(raw_allowed, list):
                    allowed_set = set(str(x) for x in raw_allowed)
                    allowed_norm = {_norm_path(x) for x in raw_allowed}
                    allowed_names = {os.path.basename(str(x)).lower() for x in raw_allowed if x}

                    def _keep_f(f_dict):
                        if not isinstance(f_dict, dict):
                            return False
                        fp = str(f_dict.get("path") or f_dict.get("storageKey") or "")
                        fn = (f_dict.get("name") or os.path.basename(fp) or "").lower()
                        if fp in allowed_set or _norm_path(fp) in allowed_norm:
                            return True
                        if fn and fn in allowed_names:
                            return True
                        return False

                    p_copy = dict(p)
                    if "attachments" in p and isinstance(p["attachments"], list):
                        p_copy["attachments"] = [
                            att for att in p["attachments"]
                            if _keep_f(att)
                        ]
                    if "file" in p and isinstance(p["file"], dict):
                        if not _keep_f(p["file"]):
                            p_copy["file"] = {}
                    filtered_posts.append(p_copy)
                else:
                    filtered_posts.append(p)
            else:
                filtered_posts.append(p)

        if not filtered_posts:
            logger.warning("No posts were selected for download.", category="downloader")
            return

        parsed = self._selection_parsed
        creator_name = self._selection_creator_name

        if parsed and parsed.provider == "telegram":
            self.queueTelegramFiles(creator_name, filtered_posts, auto_start=autoStart)
            return

        options = self._get_filter_options()

        # Build download tasks
        tasks = self.downloader.build_tasks_from_posts(
            posts=filtered_posts,
            creator_name=creator_name,
            service=parsed.service,
            domain=parsed.domain,
            base_dir=self._download_dir,
            options=options,
            batch_id=f"{parsed.service}_{parsed.user_id}"
        )

        if not tasks:
            logger.warning("No downloadable files found matching active filters in selected posts.", category="downloader")
            return

        if autoStart:
            if self._is_downloading:
                self._handle_append_tasks(tasks)
                self.downloader.append_tasks(tasks, options=options, cookie_str=self._cookie_string)
                logger.info(f"Appended {len(tasks)} tasks from {len(filtered_posts)} selected posts to active queue.", category="downloader")
            else:
                self._queue_model.clear()
                self._active_queue_model.clear()
                self._queued_links.clear()
                self.downloader.reset_state()
                self.downloader.tasks = list(tasks)
                self._handle_set_tasks(tasks)

                self._scan_cancel_event.clear()
                self._has_error = False
                self.hasErrorChanged.emit()
                self._is_downloading = True
                self.isDownloadingChanged.emit()
                self.isPausedChanged.emit()
                self._status_text = f"Starting download for {len(tasks)} selected files..."
                self.statusTextChanged.emit()

                logger.info(f"Starting download for {len(tasks)} file(s) across {len(filtered_posts)} selected posts...", category="downloader")
                self.downloader.start_download_queue(
                    tasks=tasks,
                    options=options,
                    cookie_str=self._cookie_string
                )
        else:
            self._handle_append_tasks(tasks)
            self.downloader.append_tasks(tasks)
            self._status_text = f"Queued {len(tasks)} files ({creator_name})."
            self.statusTextChanged.emit()
            logger.success(f"Added {len(tasks)} tasks from {len(filtered_posts)} selected posts to queue.", category="queue")

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

                    if self.archive_manager and self.archive_manager.is_enabled:
                        archived_link_count = 0
                        for hp in harvested_posts:
                            p_id = str(hp.get("post_id") or "")
                            p_title = str(hp.get("post_title") or "")
                            for lk in hp.get("links", []):
                                u = lk.get("url")
                                if u:
                                    if self.archive_manager.record_link(
                                        service=service,
                                        creator_id=user_id,
                                        post_id=p_id,
                                        url=u,
                                        creator_name=creator_name or user_id,
                                        post_title=p_title,
                                        link_title=lk.get("title") or u
                                    ):
                                        archived_link_count += 1
                        if archived_link_count > 0:
                            self.archiveUpdated.emit()
            except Exception as e:
                logger.debug(f"Link Vault auto-harvest error: {e}", category="vault")

        threading.Thread(target=_worker, daemon=True).start()

    def _async_fetch_and_start(self, parsed: URLParseResult, auto_start: bool):
        try:
            if self._refuse_if_disabled(getattr(parsed, "raw_url", "") or parsed.domain):
                self._is_downloading = bool(self.downloader._is_running)
                self._status_text = "Progress: Idle"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                return
            if self._scan_cancel_event.is_set():
                self._is_downloading = bool(self.downloader._is_running)
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
                    taken = set()      # an album can hold different files with the same name
                    for f in files:
                        t = DownloadTask(
                            url=f["url"],
                            target_path=unique_name_in_batch(folder, f["filename"], taken),
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
                    taken = set()      # an album can hold different files with the same name
                    for f in files:
                        t = DownloadTask(
                            url=f["url"],
                            target_path=unique_name_in_batch(folder, f["filename"], taken),
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
                    taken = set()      # an album can hold different files with the same name
                    for f in files:
                        t = DownloadTask(
                            url=f["url"],
                            target_path=unique_name_in_batch(folder, f["filename"], taken),
                            post_title=creator_name,
                            creator_name=creator_name,
                            service="nhentai",
                            post_id=parsed.post_id or "nhentai",
                            file_id=f["url"],
                            batch_id=f"nhentai_{parsed.post_id or creator_name or 'nhentai'}"
                        )
                        tasks.append(t)

                elif parsed.provider == "telegram":
                    self._telegram_pending_action = "download"
                    if not TelegramService.instance().is_logged_in():
                        self._is_downloading = bool(self.downloader._is_running)
                        self.isDownloadingChanged.emit()
                        self.telegramAuthRequested.emit(bool(parsed.extra_data.get("is_private", False)))
                        return

                    if parsed.is_single_post:
                        post = TelegramService.instance().fetch_single_post(parsed.user_id, int(parsed.post_id))
                        if post:
                            creator_name = clean_text(post.get("channel_title", parsed.user_id))
                            folder_name = sanitize_filesystem_name(creator_name, fallback="Telegram")
                            folder = os.path.join(self._download_dir, f"Telegram - {folder_name}")
                            os.makedirs(folder, exist_ok=True)
                            fn = safe_file_name(post.get("filename"), fallback=f"file_{post['id']}")
                            t = DownloadTask(
                                url=post["url"],
                                target_path=os.path.join(folder, fn),
                                post_title=creator_name,
                                creator_name=creator_name,
                                service="telegram",
                                post_id=str(post["message_id"]),
                                file_id=str(post["id"]),
                                file_size=int(post.get("file_size", 0)),
                                is_telegram=True,
                                telegram_channel_id=str(post.get("channel_id", parsed.user_id)),
                                telegram_message_id=int(post.get("message_id", 0)),
                                batch_id=f"telegram_{creator_name}"
                            )
                            tasks.append(t)
                    else:
                        self._is_downloading = bool(self.downloader._is_running)
                        self.isDownloadingChanged.emit()
                        self.telegramScopeRequested.emit(
                            str(parsed.user_id),
                            str(parsed.raw_url),
                            bool(parsed.extra_data.get("is_private", False)),
                            "download"
                        )
                        return

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
                    self._is_downloading = bool(self.downloader._is_running)
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                # 2. Fetch posts
                if parsed.is_single_post:
                    single = self.api_client.fetch_single_post(parsed)
                    posts = [single] if single else []
                else:
                    # If date auto-scan is enabled and a date filter is active,
                    # override page_end to scan all pages; the API client will
                    # stop early once it passes the requested date range.
                    effective_page_end = self._page_end
                    if self._date_auto_scan_pages and (self._date_after or self._date_before):
                        effective_page_end = 999999
                    posts = self.api_client.fetch_user_posts(
                        parsed=parsed,
                        page_start=self._page_start,
                        page_end=effective_page_end,
                        date_after=self._date_after,
                        date_before=self._date_before,
                        cancel_event=self._scan_cancel_event
                    )

                    if options.favorite_mode and posts:
                        from core.auth_manager import auth_manager
                        prov_id = self.get_provider_for_domain(parsed.domain)
                        if not auth_manager.is_logged_in(prov_id):
                            meta = auth_manager.get_provider_summary(prov_id)
                            pname = meta.get("name", prov_id.capitalize())
                            logger.warning(f"⭐ Favorite Mode active but not logged into {pname}. Showing auth prompt.", category="auth")
                            self.favoriteAuthRequired.emit(pname)
                        else:
                            logger.info(f"⭐ Favorite Mode active: Filtering {len(posts)} post(s) against account favorites...", category="downloader")
                            fav_posts = self.api_client.fetch_user_favorites(domain=parsed.domain, fav_type="post", cancel_event=self._scan_cancel_event)
                            fav_ids = {str(f.get("id")) for f in fav_posts if f.get("id")}
                            before_cnt = len(posts)
                            posts = [p for p in posts if str(p.get("id")) in fav_ids]
                            logger.info(f"⭐ Favorite Mode filter: {len(posts)} of {before_cnt} post(s) matched user favorites.", category="downloader")

                if self._scan_cancel_event.is_set():
                    self._is_downloading = bool(self.downloader._is_running)
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                if not posts:
                    logger.warning(f"No posts found for {creator_name} ({parsed.service}).", category="api")
                    self._is_downloading = bool(self.downloader._is_running)
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
                    self._is_downloading = bool(self.downloader._is_running)
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
                    artist_dir = None
                    if existing_entry and existing_entry.download_dir:
                        from core.filter_engine import FilterEngine
                        clean_c = FilterEngine.clean_filesystem_text(creator_name or parsed.user_id, max_len=80, fallback="creator")
                        norm_existing = os.path.normpath(existing_entry.download_dir)
                        norm_base = os.path.normpath(self._download_dir) if self._download_dir else ""
                        # If old folder does not exist on disk, or if user changed self._download_dir:
                        # re-anchor to active self._download_dir so user changes are 100% respected!
                        if not os.path.exists(norm_existing) or (norm_base and not norm_existing.startswith(norm_base)):
                            new_artist_dir = os.path.join(norm_base, f"{clean_c} [{parsed.service}]") if norm_base else norm_existing
                            existing_entry.download_dir = new_artist_dir
                            self._watchlist_manager.save()
                            artist_dir = new_artist_dir
                            logger.info(f"Download location updated to active download folder: '{new_artist_dir}'", category="downloader")
                        else:
                            artist_dir = norm_existing

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
                self._is_downloading = bool(self.downloader._is_running)
                self._status_text = "Progress: Cancelled"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                return

            if options.file_type == "links":
                h_count = len(self.downloader.harvested_links_records)
                self._is_downloading = bool(self.downloader._is_running)
                self._status_text = f"Links extraction complete ({h_count} links found). Ready to download or export."
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                self.harvestedLinksChanged.emit()
                return

            if not tasks:
                self._is_downloading = bool(self.downloader._is_running)
                if getattr(self.downloader, "last_build_cancelled", False):
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return
                logger.warning("No files matched filtering criteria.", category="downloader")
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

            # Auto-track artist in watchlist immediately if not a single post / external provider.
            # Nothing is recorded as downloaded yet: that happens when the download finishes, from the
            # posts that actually downloaded (recording the newest post here marked posts excluded by
            # filters, failed or cancelled as downloaded, so the Watchlist never offered them).
            if not parsed.is_single_post and not parsed.is_external_provider and parsed.user_id:
                try:
                    canonical_url = getattr(parsed, "raw_url", "") or f"https://{parsed.domain}/{parsed.service}/user/{parsed.user_id}"
                    target_download_dir = ""
                    if artist_dir:
                        target_download_dir = artist_dir
                    elif tasks and not self._separate_folders_by_known:
                        target_download_dir = self.extract_artist_folder_from_path(
                            tasks[0].target_path,
                            creator_name or parsed.user_id,
                            parsed.service,
                            fallback_dir=self._download_dir
                        )
                    else:
                        from core.filter_engine import FilterEngine
                        clean_c = FilterEngine.clean_filesystem_text(creator_name or parsed.user_id, max_len=80, fallback="creator")
                        target_download_dir = os.path.join(self._download_dir, f"{clean_c} [{parsed.service}]")

                    self._watchlist_manager.add_entry(
                        url=canonical_url,
                        creator_name=creator_name or parsed.user_id,
                        user_id=parsed.user_id,
                        service=parsed.service,
                        domain=parsed.domain,
                        download_dir=target_download_dir,
                        options=options.to_dict() if hasattr(options, "to_dict") else {},
                    )
                    self._watchlist_model.refresh()
                    self.watchlistChanged.emit()
                except Exception as e:
                    logger.debug(f"Watchlist auto-track error: {e}", category="watchlist")


            if auto_start:
                if self.downloader._is_running or self.downloader.tasks:
                    # Running, or files kept in the queue: add to it (starts the queue when idle)
                    self._appendTasksSignal.emit(tasks)
                    self.downloader.append_tasks(tasks, options=options, cookie_str=self._cookie_string)
                else:
                    self._setTasksSignal.emit(tasks)
                    self.downloader.start_download_queue(
                        tasks=tasks,
                        options=options,
                        cookie_str=self._cookie_string
                    )
                    if not self._is_downloading:
                        self._is_downloading = True
                        self.isDownloadingChanged.emit()
            else:
                self._appendTasksSignal.emit(tasks)
                self.downloader.append_tasks(tasks)
                self._status_text = f"Queued {len(tasks)} files ({creator_name})."
                self.statusTextChanged.emit()

        except Exception as e:
            logger.error(f"Error during task initialization: {e}", category="downloader")
            self._is_downloading = bool(self.downloader._is_running)
            self._has_error = True
            self._last_error_message = str(e)
            self.isDownloadingChanged.emit()
            self.hasErrorChanged.emit()
            self.lastErrorMessageChanged.emit()

    def _on_scan_progress(self, page: int, count: int):
        """Callback from api_client during favorites scanning."""
        self._status_text = f"Fetching favorites: Page {page} ({count} posts)..."
        self.statusTextChanged.emit()

    def _start_favorites_download_worker(self):
        """Worker thread to fetch all user favorites from Kemono/Coomer/Pawchive and build tasks."""
        self._scan_cancel_event.clear()
        self._has_error = False
        self.hasErrorChanged.emit()
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self.isPausedChanged.emit()
        self._status_text = "Fetching account favorites..."
        self.statusTextChanged.emit()

        def _worker():
            try:
                from core.auth_manager import auth_manager
                from core.providers import is_disabled
                # The first site with a login that isn't switched off (Kemono / Coomer are off for now)
                domain, prov_id = "pawchive.pw", "pawchive"
                for _dom, _prov in (("kemono.cr", "kemono"), ("coomer.st", "coomer"),
                                    ("pawchive.pw", "pawchive"), ("cum.st", "cumst")):
                    if not is_disabled(_prov) and auth_manager.is_logged_in(_prov):
                        domain, prov_id = _dom, _prov
                        break

                saved_cookie = auth_manager.get_credential(prov_id, "cookie")
                if saved_cookie:
                    self._cookie_string = saved_cookie
                    self.api_client.set_cookie(saved_cookie)

                self._creator_name = "Account Favorites"
                self.creatorNameChanged.emit()

                fav_posts = self.api_client.fetch_user_favorites(
                    domain=domain,
                    fav_type="post",
                    cancel_event=self._scan_cancel_event,
                    progress_callback=self._on_scan_progress
                )

                if self._scan_cancel_event.is_set():
                    self._is_downloading = False
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                if not fav_posts:
                    self._is_downloading = False
                    self._status_text = "Progress: Idle (0 favorites found)"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    logger.warning("No favorited posts found on your account.", category="api")
                    return

                options = self._get_filter_options()
                batch_id = "favorites_sync"
                tasks = self.downloader.build_tasks_from_posts(
                    posts=fav_posts,
                    creator_name="Favorites",
                    service="favorites",
                    domain=domain,
                    base_dir=self._download_dir,
                    options=options,
                    batch_id=batch_id
                )

                if not tasks:
                    self._is_downloading = False
                    self._status_text = "Progress: Idle (All favorites filtered out)"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                self._setTasksSignal.emit(tasks)      # models change on the GUI thread only
                self.downloader.tasks = list(tasks)
                self.downloader.start_download_queue(
                    tasks=self.downloader.tasks,
                    options=options,
                    cookie_str=self._cookie_string
                )
            except Exception as e:
                logger.error(f"Favorites download failed: {e}", category="downloader")
                self._is_downloading = False
                self._status_text = f"Error: {e}"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()

        threading.Thread(target=_worker, daemon=True, name="FavoritesDownloadWorker").start()

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
        checkpoint = self.recovery_manager.load_checkpoint()
        if not checkpoint:
            logger.warning("No recovery checkpoint found to resume.", category="session")
            return

        loaded_tasks = self._load_recovery_tasks(checkpoint)
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
        failed_or_cancelled = [t for t in all_tasks if t.status in ("failed", "cancelled")]

        if was_downloading:
            logger.info("Application closing: stopping downloads and saving the session...", category="system")
            self.downloader.cancel()

        def _persist():
            try:
                self.session_manager.flush_history()
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
        """True if any task actually failed. Tasks the user cancelled don't count."""
        tasks = self.downloader.tasks or (self._queue_model.tasks if self._queue_model else [])
        if any(t.status == "failed" for t in tasks):
            return True
        try:
            spilled = self.recovery_manager.load_retries() or []
        except Exception:
            spilled = []
        return any((d.get("status") if isinstance(d, dict) else getattr(d, "status", "")) == "failed" for d in spilled)

    @Slot()
    def retryFailed(self):
        """Retries all failed and cancelled tasks in the queue (the manual Retry Failed button)."""
        self._retry_failed(include_cancelled=True)

    def _retry_failed(self, include_cancelled: bool = True):
        """Shared retry logic. Automatic retries pass include_cancelled=False."""
        options = self._get_filter_options()
        self._is_downloading = True
        self.isDownloadingChanged.emit()

        if (not self.downloader.tasks or len(self.downloader.tasks) < len(self._queue_model.tasks)) and self._queue_model.tasks:
            self.downloader.tasks = self._queue_model.getTasks()

        # If no failed tasks are in memory, check if they were spilled to disk
        if not any(t.status in ("failed", "cancelled") for t in self.downloader.tasks):
            spilled = self.recovery_manager.load_retries()
            if spilled:
                from core.downloader import DownloadTask
                restored = [DownloadTask.from_dict(d) if isinstance(d, dict) else d for d in spilled]
                self.downloader.tasks.extend(restored)
                if self._queue_model:
                    self._queue_model.addTasks(restored)

        count = self.downloader.retry_failed_tasks(options, self._cookie_string, include_cancelled=include_cancelled)
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

        if (not self.downloader.tasks or len(self.downloader.tasks) < len(self._queue_model.tasks)) and self._queue_model.tasks:
            self.downloader.tasks = self._queue_model.getTasks()

        existing_ids = {t.file_id for t in self.downloader.tasks} | {t.url for t in self.downloader.tasks} | {t.filename for t in self.downloader.tasks}
        if any(sid not in existing_ids for sid in selected_ids):
            spilled = self.recovery_manager.load_retries()
            if spilled:
                from core.downloader import DownloadTask
                restored = [DownloadTask.from_dict(d) if isinstance(d, dict) else d for d in spilled]
                new_tasks = [t for t in restored if (t.file_id not in existing_ids and t.url not in existing_ids and t.filename not in existing_ids)]
                if new_tasks:
                    self.downloader.tasks.extend(new_tasks)
                    if self._queue_model:
                        self._queue_model.addTasks(new_tasks)

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

        if (not self.downloader.tasks or len(self.downloader.tasks) < len(self._queue_model.tasks)) and self._queue_model.tasks:
            self.downloader.tasks = self._queue_model.getTasks()

        existing_ids = {t.file_id for t in self.downloader.tasks} | {t.url for t in self.downloader.tasks} | {t.filename for t in self.downloader.tasks}
        if file_id not in existing_ids:
            spilled = self.recovery_manager.load_retries()
            if spilled:
                from core.downloader import DownloadTask
                restored = [DownloadTask.from_dict(d) if isinstance(d, dict) else d for d in spilled]
                matching = [t for t in restored if (t.file_id == file_id or t.url == file_id or t.filename == file_id)]
                if matching:
                    self.downloader.tasks.extend(matching)
                    if self._queue_model:
                        self._queue_model.addTasks(matching)

        count = self.downloader.retry_selected_tasks([file_id], options, self._cookie_string)
        if count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._status_text = "Progress: Idle"
            self.statusTextChanged.emit()
        elif count > 0:
            logger.info(f"Retrying single task: {file_id}", category="downloader")

    @Slot()
    @Slot("QVariantList")
    def clearFailedTasks(self, selected_ids: Optional[list] = None):
        """Removes failed and cancelled tasks from both queue models, downloader, and disk."""
        if self._queue_model:
            self._queue_model.clearFailedTasks(selected_ids)
        if self._active_queue_model:
            self._active_queue_model.clearFailedTasks(selected_ids)
        if self.downloader:
            if selected_ids:
                s_set = set(selected_ids)
                self.downloader.tasks = [
                    t for t in self.downloader.tasks
                    if not (t.status in ("failed", "cancelled") and (t.file_id in s_set or t.url in s_set or t.filename in s_set))
                ]
            else:
                self.downloader.tasks = [t for t in self.downloader.tasks if t.status not in ("failed", "cancelled")]
        if self.recovery_manager:
            if selected_ids:
                spilled = self.recovery_manager.load_retries()
                if spilled:
                    s_set = set(selected_ids)
                    remaining = [
                        item for item in spilled
                        if not ((item.get("file_id") if isinstance(item, dict) else getattr(item, "file_id", "")) in s_set
                                or (item.get("url") if isinstance(item, dict) else getattr(item, "url", "")) in s_set
                                or (item.get("filename") if isinstance(item, dict) else getattr(item, "filename", "")) in s_set)
                    ]
                    if remaining:
                        self.recovery_manager.dump_retries(remaining)
                    else:
                        self.recovery_manager.clear_retries()
            else:
                self.recovery_manager.clear_retries()
        logger.info("Cleared failed tasks from queue.", category="queue")

    @Slot()
    def cancelDownload(self):
        # Signal workers to stop
        self._scan_cancel_event.set()
        self.downloader.cancel()
        self.cancelCloudDownloads()
        try:
            from services.telegram_service import TelegramService
            TelegramService.instance().cancel_all_downloads()
        except Exception:
            pass
        try:
            from services.multipart_downloader import cancel_all_multipart
            cancel_all_multipart()
        except Exception:
            pass
        try:
            if hasattr(self.downloader, "ytdlp_manager") and self.downloader.ytdlp_manager:
                self.downloader.ytdlp_manager.cancel_all()
        except Exception:
            pass

        self._queued_links.clear()

        # Update downloading and pending tasks to "cancelled", but preserve completed, skipped, and failed
        if self._queue_model:
            self._queue_model.cancel_all_pending()

        for t in self.downloader.tasks:
            if t.status in ("pending", "downloading", "retrying"):
                t.status = "cancelled"
                t.error_msg = "Download cancelled by user"
                t.progress_pct = 0
                t.speed_bps = 0
                t.speed_str = "0 KB/s"
                t.eta_str = "--"

        if self._active_queue_model:
            self._active_queue_model.clear()

        # Update downloader internal state without dropping tasks.
        # DO NOT call self.downloader._cancel_event.clear() here: the worker thread in
        # _run_download_loop is concurrently shutting down and must observe is_set() == True.
        # _cancel_event will be cleared cleanly whenever a new download session begins.
        self.downloader._pause_event.clear()
        self.downloader._is_running = False
        self.downloader._speed_samples.clear()
        self.downloader._smoothed_speed = 0.0
        self.downloader._medium_speed = 0.0
        self.downloader._smoothed_eta = None
        self.downloader.downloaded_bytes = 0
        if self.downloader.on_pause_changed:
            try:
                self.downloader.on_pause_changed(False)
            except Exception:
                pass

        # Discard recovery journal and saved session so restart doesn't prompt for cancelled download
        self.recovery_manager.discard_recovery()
        self.session_manager.discard_session()
        self._has_recovery_session = False
        self._has_saved_session = False
        self._recovery_summary = {}
        self.hasRecoverySessionChanged.emit()
        self.hasSavedSessionChanged.emit()

        # Dump any genuine failed tasks to retries file (in background thread) so they are preserved
        all_tasks = self._queue_model.getTasks() if self._queue_model else list(self.downloader.tasks)
        failed_tasks = [t for t in all_tasks if t.status == "failed"]
        if failed_tasks:
            self.recovery_manager.dump_retries(failed_tasks, async_write=True)
        else:
            self.recovery_manager.clear_retries()

        # Reset errors
        self._has_error = False
        self._last_error_message = ""
        self.hasErrorChanged.emit()
        self.lastErrorMessageChanged.emit()

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

        if self._queue_model:
            self._queue_model.failedCountChanged.emit()

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

        base_dir = dest_folder.strip() or self._download_dir
        os.makedirs(base_dir, exist_ok=True)

        self._is_cloud_downloading = True
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self._cloud_cancel_event.clear()
        self._cloud_pause_event.clear()

        def _worker():
            total = len(selected_links)
            concurrency = min(total, max(1, self._threads_count))
            logger.info(f"☁️ Starting concurrent cloud downloads for {total} link(s) ({concurrency} parallel streams) to: {base_dir}", category="downloader")
            self._status_text = f"Cloud Download: 0/{total} completed"
            self.statusTextChanged.emit()

            filter_opts = self._get_filter_options()

            # Index harvested records by URL to recover any post metadata (tags, service, creator, title, post_id)
            harvested_map = {}
            for r in getattr(self.downloader, "harvested_links_records", []):
                if isinstance(r, dict) and r.get("url"):
                    harvested_map[r["url"]] = r

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
                record = harvested_map.get(url, {})
                title = (item.get("title") if isinstance(item, dict) else None) or record.get("title") or "Cloud File"
                platform = (item.get("platform") if isinstance(item, dict) else None) or record.get("platform") or "other"
                creator = (item.get("creator") if isinstance(item, dict) else None) or record.get("creator") or ""
                service = (item.get("service") if isinstance(item, dict) else None) or record.get("service") or ""
                tags = (item.get("tags") if isinstance(item, dict) else None) or record.get("tags") or []
                post_id = (item.get("post_id") if isinstance(item, dict) else None) or record.get("post_id") or ""
                content = (item.get("content") if isinstance(item, dict) else None) or record.get("content") or ""

                if "mega.nz" in url or "mega.co.nz" in url or "mega.io" in url:
                    platform = "mega"
                elif "drive.google.com" in url or "docs.google.com" in url or "drive.usercontent.google.com" in url:
                    platform = "gdrive"
                elif "dropbox.com" in url:
                    platform = "dropbox"
                elif "gofile.io" in url:
                    platform = "gofile"

                # Check post-level filters (character whitelist & skip words)
                if filter_opts.characters or (filter_opts.skip_words and filter_opts.skip_scope in ("posts", "both")):
                    fake_post = {"title": title, "tags": tags, "id": post_id, "content": content}
                    keep_post, reason = FilterEngine.should_keep_post(fake_post, filter_opts)
                    if not keep_post:
                        logger.info(f"☁️ Skipping cloud link for '{title}': {reason}", category="filter")
                        return True

                # Determine target folder hierarchy
                folder_parts = [base_dir]

                # Franchise -> Character hierarchy if Character Sorting is enabled
                if self._separate_folders_by_known:
                    cloud_filenames = [os.path.basename(url.split("?")[0])] if url else []
                    creator_prof = None
                    if getattr(self, "archive_manager", None) and self.archive_manager.is_enabled:
                        creator_prof = self.archive_manager.get_creator_character_profile(
                            service=service,
                            creator_id=creator,
                            creator_name=creator,
                            base_dirs=[base_dir]
                        )
                    matched_hierarchy = self.known_manager.find_matching_hierarchy(
                        title, tags=tags, filenames=cloud_filenames, content=content, creator_profile=creator_prof
                    )
                    if matched_hierarchy:
                        franchise, char_name = matched_hierarchy
                        if franchise and franchise.strip() and franchise not in ("Other", "General"):
                            clean_fr = FilterEngine.clean_filesystem_text(franchise, max_len=60, fallback="Franchise")
                            folder_parts.append(clean_fr)
                        if char_name and char_name.strip() and char_name.lower() != (franchise or "").lower():
                            clean_ch = FilterEngine.clean_filesystem_text(char_name, max_len=60, fallback="Character")
                            folder_parts.append(clean_ch)
                    else:
                        folder_parts.append("Other")

                # Creator subfolder
                creator_clean = FilterEngine.clean_filesystem_text(creator, max_len=80, fallback="") if creator else ""
                if creator_clean:
                    if service:
                        folder_parts.append(f"{creator_clean} [{service}]")
                    else:
                        folder_parts.append(creator_clean)

                # Post subfolder
                if self._subfolder_per_post and title and title not in ("Cloud File", "Untitled"):
                    clean_title = FilterEngine.clean_filesystem_text(title, max_len=100, fallback="Untitled")
                    folder_parts.append(clean_title)

                target_dir = os.path.join(*folder_parts)
                os.makedirs(target_dir, exist_ok=True)

                logger.info(f"☁️ [{platform.upper()}] Starting ({idx}/{total}) -> {target_dir}: {url}", category="downloader")

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

                def _cloud_log(msg):
                    # The cloud downloaders report everything through one callback; ❌ / ⚠ mark problems
                    text = str(msg)
                    if "❌" in text:
                        logger.error(text, category="cloud", details=f"link: {url}")
                    elif "⚠" in text:
                        logger.warning(text, category="cloud", details=f"link: {url}")
                    else:
                        logger.info(text, category="cloud")

                try:
                    if platform == "mega":
                        ok = download_mega_link(url, target_dir, log_func=_cloud_log, progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, max_workers=workers_per_link, skip_words=filter_opts.skip_words, options=filter_opts)
                    elif platform in ("gdrive", "google drive"):
                        ok = download_gdrive_link(url, target_dir, log_func=_cloud_log, progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, skip_words=filter_opts.skip_words, options=filter_opts)
                    elif platform == "dropbox":
                        ok = download_dropbox_link(url, target_dir, log_func=_cloud_log, progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, skip_words=filter_opts.skip_words, options=filter_opts)
                    elif platform == "gofile":
                        ok = download_gofile_link(url, target_dir, log_func=_cloud_log, progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, max_workers=workers_per_link, skip_words=filter_opts.skip_words, options=filter_opts)
                    else:
                        logger.warning(f"Platform '{platform}' cannot be directly auto-downloaded (URL: {url}).", category="downloader")
                except Exception as ex:
                    logger.exception(f"Error downloading {url}: {ex}", category="cloud")

                if not ok and not self._cloud_cancel_event.is_set():
                    logger.warning(f"☁️ [{platform.upper()}] ({idx}/{total}) didn't finish: {url}", category="cloud")

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
        try:
            from services.cloud_downloader import cancel_all_cloud_downloads
            cancel_all_cloud_downloads()
        except Exception:
            pass
        if self._is_cloud_downloading:
            self._cloud_cancel_event.set()
            self._is_cloud_downloading = False
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            logger.warning("Cloud downloads cancellation requested.", category="downloader")



    @Slot()
    def exportLogs(self):
        """Save a copy of this session's full log file (not just what the console panel still shows)."""
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export Log",
            os.path.join(self._download_dir, f"Pawchive log {stamp}.log"),
            "Log Files (*.log *.txt);;All Files (*)"
        )
        if save_path:
            try:
                session_file = logger.get_current_log_file()
                if session_file and os.path.isfile(session_file):
                    shutil.copyfile(session_file, save_path)
                else:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(self._log_model.get_all_text())
                logger.success(f"Log exported to: {save_path}", category="logger")
            except Exception:
                logger.exception("Failed to export the log", category="logger")

    @Slot()
    def clearLogs(self):
        self._log_model.clearLogs()

    @Slot(str)
    def logsUsageAsync(self, request_id: str):
        """logsUsage in the background (answer: asyncResultReady). Sizing thousands of log files
        held up the Settings page while it opened."""
        self._run_async(request_id, self.logsUsage)

    @Slot(result="QVariant")
    def logsUsage(self) -> dict:
        """How many log files there are and how much space they take (Settings → Logs)."""
        u = logger.logs_usage()
        return {
            "files": u["files"],
            "bytes": u["bytes"],
            "text": f"{u['files']:,} file{'s' if u['files'] != 1 else ''} · {FilterEngine.format_size_str(u['bytes'])}",
            "folder": logger.get_logs_dir(),
        }

    @Slot(result="QVariant")
    def deleteAllLogs(self) -> dict:
        """Delete every log file except the one this session is writing. Only runs when the user asks."""
        r = logger.delete_all_logs()
        text = f"Deleted {r['deleted']:,} log file(s), freed {FilterEngine.format_size_str(r['freed'])}."
        if r["failed"]:
            text += f" {r['failed']} file(s) couldn't be deleted (in use or read-only)."
        logger.info(text + " (Requested from Settings.)", category="logger")
        return {"deleted": r["deleted"], "failed": r["failed"], "text": text}

    @Slot()
    def openLogsFolder(self):
        logs_dir = logger.get_logs_dir()
        os.makedirs(logs_dir, exist_ok=True)
        if os.name == "nt":
            os.startfile(logs_dir)
        else:
            subprocess.Popen(["xdg-open", logs_dir])

    @Slot(str)
    def copyToClipboard(self, text: str):
        """Copies given text to the system clipboard in a thread-safe manner."""
        try:
            from PySide6.QtGui import QGuiApplication
            cb = QGuiApplication.clipboard()
            if cb:
                cb.setText(str(text))
        except Exception as e:
            logger.debug(f"Failed to copy to clipboard: {e}", category="system")

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
            if parsed.is_valid and self._refuse_if_disabled(u):
                continue
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
            "user_agent": self._user_agent,
            "page_start": 1,
            "page_end": 999999,
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
            "filename_template": self._filename_template,
            "proxy_url": self._proxy_url,
            "compress_webp": self._compress_webp,
            "webp_quality": self._webp_quality,
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
            "ai_recognition_enabled": self._ai_recognition_enabled,
            "ai_engine_mode": self._ai_engine_mode,
            "ai_deep_reasoner_variant": self._ai_deep_reasoner_variant,
            "language": self._language,
            "console_width": self._console_width,
            "tag_folder_mode": self._tag_folder_mode,
            "skip_post_covers": self._skip_post_covers,
            "download_thumbnails_only": self._download_thumbnails_only,
            "fallback_to_thumbnails": self._fallback_to_thumbnails,
            "redownload_small_files": self._redownload_small_files,
            "date_auto_scan_pages": self._date_auto_scan_pages,
            "enable_download_archive": self._enable_download_archive,
            "download_pawchive_temporary_files": self._download_pawchive_temporary_files,
            "min_file_size": self._min_file_size,
            "max_file_size": self._max_file_size,
            "exact_extensions": self._exact_extensions,
            "saved_custom_extensions": self._saved_custom_extensions,
            "gallery_bookmarks": self._gallery_bookmarks,
            "write_audio_metadata": self._write_audio_metadata,
            "telegram_safety_acknowledged": self._telegram_safety_acknowledged,
            "telegram_liability_acknowledged": self._telegram_liability_acknowledged,
            "skip_retry_404": self._skip_retry_404,
            "group_file_type": self._group_file_type,
            "file_order": self._file_order,
            "watchlist_apply_global_settings": self._watchlist_apply_global_settings
        }
        self.session_manager.save_settings(settings_dict, silent=True)

    # ── Thread-safe downloader event handlers ─────────────────────────────────
    # These slots run on the MAIN thread (via QueuedConnection) so it is safe
    # to read/write Qt properties and update models here.

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

    @Slot(object)
    def _handle_task_status(self, task: DownloadTask):
        if self.downloader._is_running and not self._is_downloading:
            self._is_downloading = True
            self.isDownloadingChanged.emit()

        self._queue_model.updateTask(task)
        self._active_queue_model.updateTask(task)
        if task.status == "completed":
            self._invalidate_folder_stats(getattr(task, "target_path", ""))
        if task.status == "completed" and self._enable_download_archive:
            now = time.time()
            if now - self._last_archive_emit_time >= 2.0:
                self._last_archive_emit_time = now
                self.archiveRecordCountChanged.emit()

    def _invalidate_folder_stats(self, file_path: str):
        """Forget the Gallery's cached totals for every folder above a new file. They are checked
        against a folder's own date, which doesn't change when files land in its subfolders, so a
        creator folder kept showing its old size and file count."""
        if not file_path or not self._folder_stats_cache:
            return
        folder = os.path.normpath(os.path.dirname(file_path))
        while folder:
            self._folder_stats_cache.pop(folder, None)
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent

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

    @Slot(str)
    def _handle_batch_cancel(self, batch_id: str):
        self.downloader.cancel_batch(batch_id)

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
            try:
                from services import update_service as _us
                app_version = str(_us._read_version_file(_us.get_app_dir()).get("version") or "")
            except Exception:
                app_version = ""

            snapshot = {
                "_summary": {
                    "title": "Pawchive Downloader Queue State Backup",
                    "app_version": app_version,
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
                    # (no login cookie: exported files get shared, and the cookie is your login)
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

            raw_tasks = data.get("tasks", []) if isinstance(data, dict) else []
            if not isinstance(raw_tasks, list) or not raw_tasks:
                raise ValueError("The selected JSON file does not contain a valid 'tasks' list.")

            # Where the files were meant to go on the computer that exported the queue
            old_root = ""
            if isinstance(data.get("settings"), dict):
                old_root = str(data["settings"].get("download_dir") or "")
            if not old_root and isinstance(data.get("_summary"), dict):
                old_root = str(data["_summary"].get("destination_directory") or "")

            loaded_tasks: List[DownloadTask] = []
            moved_inside = 0
            skipped_links = 0
            for t_dict in raw_tasks:
                if not isinstance(t_dict, dict):
                    continue
                task = DownloadTask.from_dict(t_dict)
                if not re.match(r"^(https?|tg)://", task.url or "", re.IGNORECASE):
                    skipped_links += 1
                    continue
                safe_path, was_moved = self._safe_import_path(task.target_path, old_root)
                if not safe_path:
                    skipped_links += 1
                    continue
                task.target_path = safe_path
                moved_inside += int(was_moved)
                self._verify_task_on_disk(task)
                loaded_tasks.append(task)
            if moved_inside:
                logger.warning(
                    f"{moved_inside} file(s) in the imported queue pointed outside your download folders; "
                    f"they'll be saved inside {self._download_dir} instead.", category="session")
            if skipped_links:
                logger.warning(f"{skipped_links} entr(y/ies) in the imported queue had no usable link and were left out.",
                               category="session")

            if merge_mode == "replace":
                self._queue_model.setTasks(loaded_tasks)
                self._active_queue_model.setTasks(loaded_tasks)
                self.downloader.tasks = list(loaded_tasks)
            else:
                # Only files not already queued: the list and the downloader must agree (files the
                # downloader ignored as duplicates used to show up as rows that never downloaded)
                if not self.downloader.tasks and self._queue_model.tasks:
                    self.downloader.tasks = list(self._queue_model.tasks)
                seen = set()
                for t in self.downloader.tasks:
                    seen.add((t.url, t.target_path))
                    if t.file_id:
                        seen.add(t.file_id)
                fresh = []
                for t in loaded_tasks:
                    if (t.url, t.target_path) in seen or (t.file_id and t.file_id in seen):
                        continue
                    seen.add((t.url, t.target_path))
                    if t.file_id:
                        seen.add(t.file_id)
                    fresh.append(t)
                loaded_tasks = fresh
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

    def _allowed_download_roots(self) -> List[str]:
        roots = [self._download_dir]
        try:
            from core.storage_pool_manager import storage_pool_manager
            roots.extend(storage_pool_manager.overflow_dirs or [])
        except Exception:
            pass
        try:
            for e in list(self._watchlist_manager.entries):
                roots.extend(d for d in [e.download_dir, *(e.download_dirs or [])] if d)
        except Exception:
            pass
        return [os.path.normpath(os.path.abspath(r)) for r in roots if r]

    def _safe_import_path(self, target_path: str, old_root: str = ""):
        """Where an imported queue file may be saved: (path, pointed_somewhere_unexpected).

        A queue file can come from anywhere, so its paths are never trusted as they are: one could
        otherwise make the app write files into any folder (e.g. the Windows Startup folder).
        Paths inside your download folders are kept; paths under the exporting computer's download
        folder are moved under yours; anything else is placed inside your download folder.
        """
        if not target_path or not self._download_dir:
            return "", False
        from core.filter_engine import FilterEngine
        base = os.path.normpath(os.path.abspath(self._download_dir))

        def _inside(p: str, root: str) -> bool:
            try:
                return os.path.commonpath([os.path.normcase(p), os.path.normcase(root)]) == os.path.normcase(root)
            except ValueError:
                return False

        norm = os.path.normpath(os.path.abspath(target_path)) if os.path.isabs(target_path) else ""
        if norm and any(_inside(norm, r) and norm != r for r in self._allowed_download_roots()):
            return norm, False
        # Rebuild the path from its last folders, cleaned, inside the download folder
        rel = ""
        if old_root and norm:
            old = os.path.normpath(os.path.abspath(old_root))
            if _inside(norm, old) and norm != old:
                rel = os.path.relpath(norm, old)
        parts = [p for p in re.split(r"[\\/]+", rel or target_path) if p and p not in (".", "..") and not p.endswith(":")]
        if not parts:
            return "", False
        if not rel:
            parts = parts[-3:]          # creator / post / file
        clean = [FilterEngine.clean_filesystem_text(p, max_len=150, fallback="file") for p in parts]
        new_path = os.path.normpath(os.path.join(base, *clean))
        if not _inside(new_path, base) or new_path == base:
            return "", False
        return new_path, not rel       # True: the path pointed somewhere unexpected

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
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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

        # Calculate actual completed percentage
        tasks = self._queue_model.getTasks()
        if tasks:
            completed_c = sum(1 for t in tasks if t.status == "completed")
            failed_c = sum(1 for t in tasks if t.status in ("failed", "cancelled"))
            if failed_c > 0:
                failed_tasks = [t for t in tasks if t.status in ("failed", "cancelled")]
                self.recovery_manager.dump_retries(failed_tasks, async_write=True)
            self._overall_progress = int(completed_c / len(tasks) * 100)
            if failed_c > 0:
                self._status_text = f"Finished with {failed_c} error(s) ({completed_c}/{len(tasks)} completed)"
            else:
                self._overall_progress = 100
                self._status_text = f"Completed ({completed_c}/{len(tasks)} files)"
        else:
            self._overall_progress = 100 if success else self._overall_progress
            self._status_text = f"Progress: {message}"

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
                        posts_all_404 = {}
                        for _t in c_tasks:
                            pid = str(getattr(_t, "post_id", "") or "")
                            date = getattr(_t, "post_date", "") or ""
                            ok = getattr(_t, "status", "") in ("completed", "skipped")
                            err = str(getattr(_t, "error_msg", "") or "")
                            is_404 = "404" in err or "not exist" in err.lower()
                            prev = posts_state.get(pid)
                            posts_state[pid] = (date or (prev[0] if prev else ""), ok and (prev[1] if prev else True))
                            if not ok:
                                posts_all_404[pid] = posts_all_404.get(pid, True) and is_404
                        done_posts = [(d, p) for p, (d, ok) in posts_state.items() if ok]
                        # Don't let posts that permanently 404 block cutoff advancement forever
                        open_posts = [(d, p) for p, (d, ok) in posts_state.items() if not ok and not posts_all_404.get(p, False)]

                        existing = self._watchlist_manager._find(uid, svc)
                        if not existing:
                            t0 = c_tasks[0]
                            existing = next((e for e in self._watchlist_manager.entries if e.service.lower() == svc and (e.creator_name.lower() == t0.creator_name.lower() or e.user_id.lower() == t0.creator_name.lower())), None)

                        if existing:
                            done_posts += self._watchlist_pending_updates.pop((existing.service.lower(), existing.user_id.lower()), None) or []

                        if done_posts:
                            newest_done_date, newest_done_pid = max(done_posts, key=lambda dp: _post_order_key(dp[0], dp[1]))
                            done_day_ids = sorted({p for d, p in done_posts if d == newest_done_date and p})
                        else:
                            newest_done_date, newest_done_pid, done_day_ids = "", "", []

                        c_latest_pid, c_latest_date, c_day_ids = watchlist_cutoff(done_posts, open_posts)
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

                    url_clean = (self._current_url or "").strip()
                    from core.parser import KemonoURLParser
                    _parsed = KemonoURLParser.parse(url_clean) if url_clean else None
                    if _parsed and _parsed.is_valid and not _parsed.is_external_provider and not _parsed.is_single_post:
                        c_key = (_parsed.service.lower(), _parsed.user_id.lower())
                        c_tasks = grouped.get(c_key, tasks_done)
                        c_latest_pid, c_latest_date = cutoffs.get(c_key, ("", ""))
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
                            last_post_id=c_latest_pid,
                            last_post_date=c_latest_date,
                            download_dir=t_dir,
                            options=self._get_filter_options().to_dict(),
                        )

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
                    album_title, _ = fetch_bunkr_album(parsed.raw_url, resolve_files=False)
                    if album_title:
                        self._creatorSignal.emit(for_url, clean_text(album_title))
                elif parsed.provider == "erome":
                    album_title, _ = fetch_erome_album(parsed.raw_url)
                    if album_title:
                        self._creatorSignal.emit(for_url, clean_text(album_title))
                elif parsed.provider == "nhentai":
                    gallery_title, _ = fetch_nhentai_gallery(parsed.post_id or parsed.raw_url)
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

    def _check_and_resolve_if_already_downloaded(self, entry, new_posts: list) -> list:
        """If all files in new_posts already exist on disk or in the download archive,
        auto-advance the cutoff to the latest post and return an empty list so no false
        update badge is displayed."""
        if not new_posts:
            return []
        try:
            options = self._get_effective_watchlist_options(entry)
            artist_folder = self.resolve_artist_download_dir(entry)
            tasks = self.downloader.build_tasks_from_posts(
                posts=new_posts,
                creator_name=entry.creator_name,
                service=entry.service,
                domain=entry.domain,
                base_dir=self._download_dir,
                options=options,
                batch_id=f"check_{entry.service}_{entry.user_id}",
                artist_dir=artist_folder,
                user_id=entry.user_id
            )
            if not tasks:
                # All files across new_posts were already archived, on disk, or filtered
                latest_p = new_posts[-1]
                latest_pid = str(latest_p.get("id", ""))
                latest_pdate = self._post_day(latest_p)
                latest_day_ids = [str(p.get("id", "")) for p in new_posts if self._post_day(p) == latest_pdate]
                self._watchlist_manager.resolve_posts(
                    entry.user_id,
                    entry.service,
                    post_ids=None,
                    latest_post_id=latest_pid,
                    latest_post_date=latest_pdate,
                    day_ids=latest_day_ids
                )
                entry.new_post_count = 0
                entry.cached_new_posts = []
                self._watchlist_manager.save()
                return []
        except Exception as e:
            logger.debug(f"Watchlist check pre-flight verification error: {e}", category="watchlist")
        return new_posts

    @Slot(str, str)
    def checkWatchlistArtist(self, userId: str, service: str):
        """Asynchronously check a single watchlist artist for new posts."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            logger.warning(f"checkWatchlistArtist: entry not found for {userId}/{service}", category="watchlist")
            return
        if self._refuse_if_disabled(entry.url or entry.domain, context="watchlist"):
            self.watchlistArtistChecked.emit(userId, service, 0)
            return

        self.watchlistArtistChecking.emit(userId, service, True)

        def _run():
            try:
                new_posts = self._watchlist_manager.get_posts_since(entry, self.api_client)
                new_posts = self._check_and_resolve_if_already_downloaded(entry, new_posts)
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
        1. If multi-drive overflow is enabled:
           - Automatically chooses the drive with the MOST free space among
             existing artist directories and storage pool drives.
        2. Otherwise:
           - If entry.download_dir is set and non-empty, resolve it.
           - Otherwise, construct the default path inside self._download_dir.
        """
        from core.filter_engine import FilterEngine
        from core.storage_pool_manager import storage_pool_manager

        clean_c = FilterEngine.clean_filesystem_text(entry.creator_name or entry.user_id, max_len=80, fallback="creator")
        expected_folder = f"{clean_c} [{entry.service}]"

        if storage_pool_manager.enabled and storage_pool_manager.overflow_dirs:
            # Multi-drive overflow active: discover existing artist folders across drives
            reg_paths = list(getattr(entry, "download_dirs", []) or [])
            if entry.download_dir and entry.download_dir not in reg_paths:
                reg_paths.insert(0, entry.download_dir)

            existing_locs = storage_pool_manager.find_artist_locations(
                creator_name=entry.creator_name or entry.user_id,
                service=entry.service,
                additional_paths=reg_paths
            )
            # Sync discovered back into entry.download_dirs
            synced = False
            for loc in existing_locs:
                if loc not in entry.download_dirs:
                    entry.download_dirs.append(loc)
                    synced = True
            if synced:
                self._watchlist_manager.save()

            if existing_locs:
                # Pick the existing artist location that sits on the disk with the MOST free space
                best_loc, _ = storage_pool_manager.get_most_free_drive(existing_locs)
                return best_loc
            else:
                # No artist folder exists yet -> pick among primary and all overflow roots by most free disk
                roots = ([storage_pool_manager.primary_dir] if storage_pool_manager.primary_dir else [self._download_dir]) + list(storage_pool_manager.overflow_dirs)
                best_root, _ = storage_pool_manager.get_most_free_drive(roots)
                target = os.path.join(best_root, expected_folder)
                if target not in entry.download_dirs:
                    entry.download_dirs.append(target)
                    self._watchlist_manager.save()
                return target

        # Standard single-drive fallback
        target = (getattr(entry, "download_dir", "") or "").strip()
        if target:
            if os.path.exists(target):
                return self.resolve_artist_download_dir_for_folder(target, entry.creator_name or entry.user_id, entry.service)
            elif not self._watchlist_apply_global_settings:
                return self.resolve_artist_download_dir_for_folder(target, entry.creator_name or entry.user_id, entry.service)

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

        if fallback_dir:
            return os.path.join(fallback_dir, f"{clean_c} [{service}]")
        return os.path.dirname(sample_path) if sample_path else os.path.join(self._download_dir, f"{clean_c} [{service}]")

    @Slot(str, str)
    def _get_effective_watchlist_options(self, entry) -> FilterOptions:
        """
        Determines the FilterOptions to use for a watchlist download:
        - If watchlistApplyGlobalSettings is True: returns current global UI options with
          transient search/date filters cleared so watchlist cutoff dates apply cleanly.
        - If False: merges entry.options over current global options to preserve legacy
          creator overrides without falling back to hardcoded defaults for newly added keys.
        """
        from core.filter_engine import FilterOptions
        if self._watchlist_apply_global_settings:
            options = self._get_filter_options()
            options.date_after = ""
            options.date_before = ""
            options.page_start = 1
            options.page_end = 999999
            options.characters = ""
            return options
        elif getattr(entry, "options", None):
            base_dict = self._get_filter_options().to_dict()
            base_dict.update(entry.options)
            base_dict["date_after"] = ""
            base_dict["date_before"] = ""
            base_dict["page_start"] = 1
            base_dict["page_end"] = 999999
            base_dict["characters"] = ""
            return FilterOptions.from_dict(base_dict)
        else:
            options = self._get_filter_options()
            options.date_after = ""
            options.date_before = ""
            options.page_start = 1
            options.page_end = 999999
            options.characters = ""
            return options

    @staticmethod
    def _post_day(post: dict) -> str:
        pub = post.get("published") or post.get("added") or ""
        if isinstance(pub, (int, float)):
            try:
                return datetime.datetime.fromtimestamp(pub).strftime("%Y-%m-%d")
            except Exception:
                return ""
        p_str = str(pub)
        return p_str.split("T")[0] if "T" in p_str else p_str[:10]

    def _process_watchlist_entry_download(self, entry, postIds: Optional[list] = None):
        """Worker logic to fetch, structure, and append download tasks for a single watchlist entry."""
        from core.providers import is_disabled
        if is_disabled(entry.url or entry.domain):
            logger.warning(f"Watchlist: {entry.creator_name!r} is on a switched-off site; skipped.", category="watchlist")
            return
        new_posts = self._watchlist_manager.get_posts_since(entry, self.api_client)
        if not new_posts:
            logger.info(f"No new posts found for {entry.creator_name!r}.", category="watchlist")
            if entry.new_post_count > 0:
                entry.new_post_count = 0
                entry.cached_new_posts = []
                self._watchlist_manager.save()
                self._watchlist_model.update_new_counts()
                self._watchlist_model.refresh()
                self.watchlistChanged.emit()
            return

        # If specific postIds were requested (selective download), filter to only those
        if postIds:
            p_set = set(str(pid) for pid in postIds)
            new_posts = [p for p in new_posts if str(p.get("id")) in p_set]
            if not new_posts:
                logger.info(f"None of the requested posts for {entry.creator_name!r} were available.", category="watchlist")
                self._watchlist_manager.resolve_posts(entry.user_id, entry.service, post_ids=list(p_set))
                self._watchlist_model.update_new_counts()
                self._watchlist_model.refresh()
                self.watchlistChanged.emit()
                return

        # Extract latest post id and date evaluated in this batch
        latest_p = new_posts[-1]
        latest_pid = str(latest_p.get("id", ""))
        pub = latest_p.get("published") or latest_p.get("added") or ""
        if isinstance(pub, (int, float)):
            try:
                import datetime
                latest_pdate = datetime.datetime.fromtimestamp(pub).strftime("%Y-%m-%d")
            except Exception:
                latest_pdate = ""
        else:
            p_str = str(pub)
            latest_pdate = p_str.split("T")[0] if "T" in p_str else (p_str[:10] if p_str else "")

        options = self._get_effective_watchlist_options(entry)
        if self._scheduled_sweep_retry:
            options.auto_retry_at_end = True     # Scheduler → "Sweep auto-retry pass"

        artist_folder = self.resolve_artist_download_dir(entry)
        # Ensure the entry knows its download_dir and download_dirs
        if not entry.download_dir:
            entry.download_dir = artist_folder
        if hasattr(entry, "download_dirs") and isinstance(entry.download_dirs, list):
            if artist_folder not in entry.download_dirs:
                entry.download_dirs.insert(0, artist_folder)
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
            post_ids_with_files = {str(t.post_id) for t in tasks}
            no_file_posts = [(self._post_day(p), str(p.get("id", ""))) for p in new_posts
                             if str(p.get("id", "")) not in post_ids_with_files]
            if no_file_posts:
                key = (entry.service.lower(), entry.user_id.lower())
                self._watchlist_pending_updates.setdefault(key, []).extend(no_file_posts)
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
        else:
            # All files across new_posts were already archived, already exist on disk, or were filtered out.
            req_pids = [str(pid) for pid in postIds] if postIds else None
            self._watchlist_manager.resolve_posts(
                entry.user_id,
                entry.service,
                post_ids=req_pids,
                latest_post_id=latest_pid,
                latest_post_date=latest_pdate,
                day_ids=[str(p.get("id", "")) for p in new_posts if self._post_day(p) == latest_pdate]
            )
            self._watchlist_model.update_new_counts()
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()
            if req_pids:
                logger.info(
                    f"Watchlist: selected post(s) for {entry.creator_name!r} are already archived or downloaded. Review drawer updated.",
                    category="watchlist"
                )
            else:
                logger.info(
                    f"Watchlist: all {len(new_posts)} new post(s) for {entry.creator_name!r} are already archived or downloaded. Marked as up to date.",
                    category="watchlist"
                )

    @Slot(str, str)
    @Slot(str, str, "QVariantList")
    def downloadNewPosts(self, userId: str, service: str, postIds: Optional[list] = None):
        """Queue only posts newer than the last_post_date for the given artist."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            logger.warning(f"downloadNewPosts: entry not found for {userId}/{service}", category="watchlist")
            return
        if self._refuse_if_disabled(entry.url or entry.domain, context="watchlist"):
            return
        if entry.new_post_count == 0 and not postIds:
            logger.info(f"No new posts queued for {entry.creator_name!r} — all up to date.", category="watchlist")
            return

        def _run():
            self._process_watchlist_entry_download(entry, postIds)

        threading.Thread(target=_run, daemon=True).start()

    @Slot()
    def downloadAllNewPosts(self):
        """Batch download new posts for all watchlist artists with pending updates sequentially."""
        from core.providers import is_disabled
        updated_entries = [e for e in self._watchlist_manager.entries
                           if (getattr(e, "new_post_count", 0) or 0) > 0 and not is_disabled(e.url or e.domain)]
        if not updated_entries:
            logger.info("No watchlist artists have pending updates.", category="watchlist")
            return
        logger.info(f"Queueing updates for {len(updated_entries)} watchlist creator(s)...", category="watchlist")

        def _run_batch():
            for e in updated_entries:
                try:
                    self._process_watchlist_entry_download(e)
                except Exception as err:
                    logger.error(f"Error downloading updates for {e.creator_name!r}: {err}", category="watchlist")

        threading.Thread(target=_run_batch, daemon=True).start()

    @Slot(str, result=bool)
    @Slot(str, str, str)
    def addArtistToWatchlistAsync(self, request_id: str, url: str, custom_download_dir: str = ""):
        """addArtistToWatchlist in the background (answer: asyncResultReady(request_id, bool)).
        Looking up the creator's name and newest post used to freeze the window, for a minute
        when the site was slow."""
        self._run_async(request_id, self.addArtistToWatchlist, url, custom_download_dir)

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
        if self._refuse_if_disabled(raw_url):
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
        """Re-queue the full download for a watched artist (all posts, not just new).

        Only this creator's entry in the queue is replaced: their waiting files are taken out and a
        fresh entry is added, while everything else keeps going. It also works during a download
        (it used to do nothing then, and otherwise threw the whole queue away). Files of this
        creator that are downloading right now are left to finish, so no file is downloaded twice
        at the same time; the fresh entry skips files that are already complete on disk.
        """
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return
        parsed = KemonoURLParser.parse(entry.url or "")
        if not parsed.is_valid:
            logger.error(f"Can't re-download {entry.creator_name or userId}: {parsed.error_msg}", category="watchlist")
            return
        if self._refuse_if_disabled(entry.url):
            return

        removed = self._drop_creator_from_queue(parsed.service, parsed.user_id)
        _, identity_key, _, display_name = self._get_link_identity(parsed)
        self._queued_links.add(identity_key)
        name = entry.creator_name or display_name
        if removed:
            logger.info(f"Re-download: replaced {removed} queued file(s) of {name!r} with a fresh entry.", category="watchlist")
        else:
            logger.info(f"Re-download: adding {name!r} to the queue.", category="watchlist")

        self._scan_cancel_event.clear()
        if not self._is_downloading:
            self._has_error = False
            self.hasErrorChanged.emit()
            self._is_downloading = True
            self.isDownloadingChanged.emit()
            self.isPausedChanged.emit()
            self._status_text = "Fetching metadata..."
            self.statusTextChanged.emit()
        threading.Thread(target=self._async_fetch_and_start, args=(parsed, True), daemon=True,
                         name="WatchlistRedownload").start()

    def _drop_creator_from_queue(self, service: str, user_id: str) -> int:
        """Take one creator's waiting / finished / failed files out of the queue (GUI thread).

        Files of theirs that are downloading right now stay until they finish."""
        svc, uid = str(service or "").lower(), str(user_id or "").lower()
        whole = {f"artist_{svc}_{uid}", f"watchlist_{svc}_{uid}", f"gallery_{svc}_{uid}"}
        post_prefix = f"post_{svc}_{uid}_"

        def mine(t) -> bool:
            bid = str(getattr(t, "batch_id", "") or "").lower()
            return bid in whole or bid.startswith(post_prefix)

        tasks = list(self._queue_model.tasks) or list(self.downloader.tasks)
        batch_ids = {getattr(t, "batch_id", "") for t in tasks if mine(t)}
        if not batch_ids:
            return 0
        # Waiting files are cancelled first, so the running download can't pick one up meanwhile
        for t in list(self.downloader.tasks) + tasks:
            if mine(t) and t.status == "pending":
                t.status = "cancelled"
        before = len(tasks)
        for bid in batch_ids:
            self._queue_model.removeBatch(bid)       # also removes them from the downloader
        after = len(self._queue_model.tasks) if self._queue_model.tasks else len(self.downloader.tasks)
        return max(0, before - after)

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

    @Slot(str, str, result="QVariantList")
    def getArtistDownloadDirs(self, userId: str, service: str) -> list:
        """
        Returns all discovered and registered filesystem paths for an artist across
        primary storage and overflow drives, enriched with free space statistics.
        """
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return []

        import shutil
        from core.storage_pool_manager import storage_pool_manager

        registered = list(getattr(entry, "download_dirs", []) or [])
        if entry.download_dir and entry.download_dir not in registered:
            registered.insert(0, entry.download_dir)

        # Discovered on-disk folders across primary & overflow drives
        discovered = storage_pool_manager.find_artist_locations(
            creator_name=entry.creator_name or entry.user_id,
            service=entry.service,
            additional_paths=registered
        )

        updated = False
        for p in discovered:
            if p not in registered:
                registered.append(p)
                updated = True
        if updated:
            entry.download_dirs = registered
            self._watchlist_manager.save()
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()

        if not registered:
            default_p = self.resolve_artist_download_dir(entry)
            registered = [default_p]

        results = []
        for p in registered:
            norm = os.path.normpath(p)
            exists = os.path.exists(norm)
            free_gb = 0.0
            total_gb = 0.0
            drive_label = ""
            try:
                drive_root = norm if exists else (os.path.splitdrive(norm)[0] or norm)
                if os.path.exists(drive_root):
                    usage = shutil.disk_usage(drive_root)
                    free_gb = round(getattr(usage, "free", usage[2] if len(usage) > 2 else 0) / (1024 ** 3), 1)
                    total_gb = round(getattr(usage, "total", usage[0] if len(usage) > 0 else 0) / (1024 ** 3), 1)
                    drive_label = os.path.splitdrive(norm)[0]
            except Exception:
                pass

            results.append({
                "path": norm,
                "exists": exists,
                "freeGb": free_gb,
                "totalGb": total_gb,
                "driveLabel": drive_label,
                "isPrimary": (norm == entry.download_dir or (registered and norm == registered[0]))
            })

        return results

    @Slot(str, str, str)
    def removeArtistDownloadDir(self, userId: str, service: str, path: str):
        """Remove a location path from an artist's tracked download_dirs list."""
        if self._watchlist_manager.remove_download_dir(userId, service, path):
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()

    @Slot(str, str, str)
    def addArtistDownloadDir(self, userId: str, service: str, path: str):
        """Add a custom location path to an artist's tracked download_dirs list."""
        entry = self._watchlist_manager._find(userId, service)
        if entry:
            resolved = self.resolve_artist_download_dir_for_folder(path, entry.creator_name, entry.service)
        else:
            resolved = os.path.normpath(path)
        if self._watchlist_manager.add_download_dir(userId, service, resolved):
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()

    @Slot(str, str)
    def browseAndAddArtistDownloadDir(self, userId: str, service: str):
        """Open a folder picker and append the chosen path to the artist's download_dirs list."""
        entry = self._watchlist_manager._find(userId, service)
        initial_dir = (
            entry.download_dir
            if entry and entry.download_dir and os.path.exists(entry.download_dir)
            else self._download_dir
        )
        folder = QFileDialog.getExistingDirectory(
            None,
            f"Add Storage Location for {entry.creator_name if entry else userId}",
            initial_dir
        )
        if folder:
            norm_folder = os.path.normpath(folder)
            if self._watchlist_manager.add_download_dir(userId, service, norm_folder):
                self._watchlist_model.refresh()
                self.watchlistChanged.emit()
                logger.info(
                    f"Added storage location {norm_folder!r} for {entry.creator_name if entry else userId}.",
                    category="watchlist"
                )

    @Slot(str)
    def showInGallery(self, path: str):
        """Switch to the Gallery tab and open this folder (or the folder of this file, highlighted)."""
        if not path:
            return
        norm = os.path.normpath(path)
        if os.path.isdir(norm):
            self.galleryShowRequested.emit(norm, True)
        elif os.path.exists(norm):
            self.galleryShowRequested.emit(norm, False)
        else:
            # The file isn't there (yet): open the closest folder that exists
            parent = os.path.dirname(norm)
            while parent and not os.path.isdir(parent) and os.path.dirname(parent) != parent:
                parent = os.path.dirname(parent)
            if parent and os.path.isdir(parent):
                self.galleryShowRequested.emit(parent, True)

    @Slot()
    def showDownloadsInGallery(self):
        """Open the Gallery at the folder of the current / last download, or the downloads folder."""
        folder = ""
        try:
            dirs = [os.path.dirname(t.target_path) for t in (self.downloader.tasks or []) if getattr(t, "target_path", "")]
            if dirs:
                folder = os.path.commonpath(dirs)
        except ValueError:
            folder = ""  # tasks on different drives
        if not folder or not os.path.isdir(folder):
            folder = self._download_dir or os.path.expanduser("~")
        self.showInGallery(folder)

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
        from core.providers import is_disabled, disabled_message
        total_new = 0
        skipped_off = [e for e in list(self._watchlist_manager.entries) if is_disabled(e.domain) or is_disabled(e.url)]
        if skipped_off:
            logger.warning(
                f"Watchlist: {len(skipped_off)} artist(s) on a switched-off site were not checked. "
                + disabled_message(skipped_off[0].url or skipped_off[0].domain), category="watchlist")
            if not getattr(self, "_warned_disabled_watchlist", False):
                self._warned_disabled_watchlist = True      # once per run
                kemono_n = self.kemonoWatchlistCount()
                msg = (f"Kemono and Coomer are turned off for now because they mostly aren't working, so "
                       f"{len(skipped_off)} Watchlist artist(s) on those sites weren't checked.")
                if kemono_n:
                    msg += " Pawchive has the same creators as Kemono: you can move your Kemono artists there."
                if len(skipped_off) > kemono_n:
                    msg += " For Coomer artists, look them up on cum.st and add them again."
                self.providerDisabled.emit(msg, "", "watchlist")
        for entry in list(self._watchlist_manager.entries):
            if entry in skipped_off:
                continue
            try:
                new = self._watchlist_manager.get_posts_since(entry, self.api_client)
                new = self._check_and_resolve_if_already_downloaded(entry, new)
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

    @Slot(str, 'QVariant', result=bool)
    def updateVaultLinkPasswords(self, linkId: str, passwords) -> bool:
        from core.link_vault_manager import link_vault_manager
        pw_list = []
        if isinstance(passwords, str):
            pw_list = [p.strip() for p in passwords.split(",") if p.strip()]
        elif isinstance(passwords, (list, tuple)):
            pw_list = [str(p).strip() for p in passwords if str(p).strip()]
        res = link_vault_manager.update_link_passwords(linkId, pw_list)
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
                if self._refuse_if_disabled(clean_url):
                    self.vaultHarvestFinished.emit(False, "Site turned off", 0, 0)
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
    @Slot(result=bool)
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

    # ── Providers & Credential Vault Slots ──────────────────────────────────
    @Slot(result=list)
    def getProvidersList(self) -> list:
        from core.auth_manager import auth_manager
        return auth_manager.get_all_providers_summary()

    @Slot(str, str, result=bool)
    def saveProviderCredential(self, providerId: str, credVal: str) -> bool:
        from core.auth_manager import auth_manager, SUPPORTED_PROVIDERS
        meta = SUPPORTED_PROVIDERS.get(providerId, {})
        auth_type = meta.get("auth_type", "cookie")
        key = "cookie" if auth_type == "cookie" else ("token" if auth_type == "token" else ("api_key" if auth_type == "api_key" else "cookie"))

        ok = auth_manager.set_credential(providerId, {key: credVal.strip()})
        if providerId == "kemono":
            self.cookieString = credVal.strip()
            self.saveSettings()
            self.cookieWatchdogChanged.emit()
        self.providersChanged.emit()
        return ok

    @Slot(str, result=bool)
    def clearProviderCredential(self, providerId: str) -> bool:
        from core.auth_manager import auth_manager
        ok = auth_manager.clear_credential(providerId)
        if providerId == "kemono":
            self.cookieString = ""
            self.saveSettings()
            self.cookieWatchdogChanged.emit()
        self.providersChanged.emit()
        return ok

    @Slot(str)
    def validateProviderSession(self, providerId: str):
        def _val_worker():
            from core.auth_manager import auth_manager
            ok, msg, _ = auth_manager.validate_session(providerId)
            self.providerValidationFinished.emit(providerId, ok, msg)
            self.providersChanged.emit()

        threading.Thread(target=_val_worker, daemon=True, name=f"ValWorker_{providerId}").start()

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def importBrowserCookiesToProvider(self, providerId: str, browserId: str = "") -> bool:
        from services.cookie_importer import browser_cookie_importer
        from core.auth_manager import auth_manager
        try:
            res = browser_cookie_importer.import_auto_detect(preferred_browser=browserId or None)
            c_str = res.get("cookie_string", "")
            if c_str:
                auth_manager.set_credential(providerId, {"cookie": c_str})
                if providerId == "kemono":
                    self.cookieString = c_str
                    self.saveSettings()
                self.providersChanged.emit()
                self.cookieWatchdogChanged.emit()
                self.cookieImportCompleted.emit(True, res.get("browser_name", "Browser"))
                return True
        except Exception as e:
            logger.error(f"Browser cookie import to {providerId} failed: {e}", category="cookie")
            self.cookieImportCompleted.emit(False, str(e))
        return False

    @Slot(str, str, str)
    def loginProviderWithCredentials(self, providerId: str, username: str, password: str):
        def _worker():
            from core.auth_manager import auth_manager
            ok, msg, details = auth_manager.login_with_credentials(providerId, username, password)
            self.providerLoginFinished.emit(providerId, ok, msg)
            if ok:
                if providerId == "kemono":
                    c = auth_manager.get_credential("kemono", "cookie")
                    if c:
                        self.cookieString = c
                        self.saveSettings()
                self.providersChanged.emit()

        threading.Thread(target=_worker, daemon=True, name=f"Login_{providerId}").start()

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
        self._update_sleep_prevention()
        self.schedulerChanged.emit()

    @Slot()
    def _update_sleep_prevention(self):
        try:
            from core.task_scheduler import task_scheduler
            from core.power import sleep_inhibitor
            sleep_inhibitor.set_active(bool(self._is_downloading and task_scheduler.prevent_sleep))
        except Exception as e:
            logger.debug(f"Sleep prevention update failed: {e}", category="system")

    def _run_scheduled_watchlist_sync(self):
        """Called by the TaskScheduler (in its background thread) when a Watchlist Sync schedule
        triggers: checks every watchlist artist, then downloads their new posts. (It used to only
        count new posts, so nothing was ever downloaded automatically.)"""
        from core.task_scheduler import task_scheduler
        from core.providers import is_disabled
        logger.info("Scheduler: Watchlist Sync — checking all watchlist artists for new posts...", category="scheduler")
        self._async_watchlist_check()          # runs right here, in the scheduler's thread
        updated = [e for e in list(self._watchlist_manager.entries)
                   if (getattr(e, "new_post_count", 0) or 0) > 0 and not is_disabled(e.domain)]
        if not updated:
            logger.info("Scheduler: Watchlist Sync — nothing new to download.", category="scheduler")
            return
        self._scheduled_sweep_retry = bool(task_scheduler.sweep_retry)
        logger.info(f"Scheduler: Watchlist Sync — downloading new posts for {len(updated)} artist(s)...", category="scheduler")
        for e in updated:
            try:
                self._process_watchlist_entry_download(e)
            except Exception as err:
                logger.error(f"Scheduler: could not download updates for {e.creator_name!r}: {err}", category="scheduler")

    def _run_scheduled_creator_sync(self, url: str):
        """Called by the TaskScheduler (background thread) when a Creator schedule triggers.
        The download is started on the GUI thread."""
        if url:
            self._scheduledCreatorSyncSignal.emit(url)

    @Slot(str)
    def _handle_scheduled_creator_sync(self, url: str):
        from core.task_scheduler import task_scheduler
        self._scheduled_sweep_retry = bool(task_scheduler.sweep_retry)
        self.currentUrl = url
        if self._is_downloading:
            # A download is already running: add this creator to it instead of skipping the schedule
            logger.info(f"Scheduler: a download is running — adding '{url}' to the queue.", category="scheduler")
            self.addToQueue()
        else:
            logger.info(f"Scheduler: Initiating automated Creator Sync for '{url}'...", category="scheduler")
            self.startDownload()

    # ── Integrated File Explorer & Media Gallery ─────────────────────────────

    @Slot(result=str)
    def getDownloadDir(self) -> str:
        """Return the user's active download directory."""
        return self._download_dir or os.path.expanduser("~")

    @Slot(str, int, result='QVariantList')
    def listDirectory(self, path: str = "", max_entries: int = 1500) -> list:
        """
        High-performance on-demand lazy directory listing.
        Engineered for libraries with millions of files:
        - Only scans immediate directory children (never recurses on main thread).
        - Uses os.scandir for direct cached stat retrieval.
        - Provides immediate shallow child counts.
        - Asynchronously calculates deep recursive file count & size in background.
        - Caps return count to max_entries to guarantee 0 UI lag; the full entry count
          is still tallied (without stat calls) and exposed via getLastListingTotal().
        """
        if not path:
            path = self._download_dir or os.path.expanduser("~")

        self._last_listing_total = 0
        path = os.path.normpath(os.path.abspath(path))
        if not os.path.exists(path) or not os.path.isdir(path):
            return []

        # Invalidate old background worker tasks
        self._folder_stats_worker_token += 1
        current_token = self._folder_stats_worker_token
        subfolders_to_scan = []

        items = []
        try:
            with os.scandir(path) as it:
                count = 0
                skipped = 0
                for entry in it:
                    if count >= max_entries:
                        skipped += 1
                        continue
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                        norm_p = os.path.normpath(entry.path)
                        if is_dir:
                            # Counts and sizes come from the background worker: opening every
                            # subfolder here to count its items froze the window on big folders
                            # and network drives. Cached stats are used only while the folder is
                            # unchanged (they used to be shown even after files were added).
                            try:
                                dir_mtime = entry.stat(follow_symlinks=False).st_mtime
                            except OSError:
                                dir_mtime = 0
                            cached = self._folder_stats_cache.get(norm_p)
                            if cached and cached.get("mtime") == dir_mtime:
                                size = cached["size"]
                                file_count = cached["files"]
                                folder_count = cached["dirs"]
                            else:
                                size = -1
                                file_count = -1
                                folder_count = -1
                                subfolders_to_scan.append(norm_p)

                            items.append({
                                "name": entry.name,
                                "path": norm_p,
                                "is_dir": True,
                                "size": size,
                                "file_count": file_count,
                                "folder_count": folder_count,
                                "child_count": -1,
                                "mtime": dir_mtime,
                                "ext": ""
                            })
                        else:
                            st = entry.stat(follow_symlinks=False)
                            size = st.st_size if st else 0
                            mtime = st.st_mtime if st else 0
                            ext = os.path.splitext(entry.name)[1].lower()
                            items.append({
                                "name": entry.name,
                                "path": norm_p,
                                "is_dir": False,
                                "size": size,
                                "file_count": 0,
                                "folder_count": 0,
                                "child_count": 0,
                                "mtime": mtime,
                                "ext": ext
                            })
                        count += 1
                    except (PermissionError, OSError):
                        continue
                self._last_listing_total = count + skipped
        except (PermissionError, OSError):
            return []

        # Launch background worker for un-cached folders
        if subfolders_to_scan:
            threading.Thread(
                target=self._batch_calculate_folder_stats,
                args=(subfolders_to_scan, current_token),
                daemon=True
            ).start()

        # Sort folders first, then alphabetical by name
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return items

    @Slot(result=int)
    def getLastListingTotal(self) -> int:
        """Total entries in the folder last passed to listDirectory, including any past the cap."""
        return getattr(self, "_last_listing_total", 0)

    def _compute_folder_stats(self, folder_path: str, token: int):
        """Worker function executed in background thread."""
        try:
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                return

            mtime = os.path.getmtime(folder_path)
            cached = self._folder_stats_cache.get(folder_path)
            if cached and cached.get("mtime") == mtime:
                self.folderStatsCalculated.emit(
                    os.path.normpath(folder_path),
                    cached["size"],
                    cached["files"],
                    cached["dirs"]
                )
                return

            total_size = 0
            total_files = 0
            total_dirs = 0
            max_files = 250000

            for root, dirs, files in os.walk(folder_path):
                if token != self._folder_stats_worker_token:
                    return
                total_dirs += len(dirs)
                total_files += len(files)
                for f in files:
                    try:
                        fp = os.path.join(root, f)
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass
                if total_files >= max_files:
                    break

            stats = {
                "size": total_size,
                "files": total_files,
                "dirs": total_dirs,
                "mtime": mtime
            }
            self._folder_stats_cache[folder_path] = stats

            if token == self._folder_stats_worker_token:
                self.folderStatsCalculated.emit(
                    os.path.normpath(folder_path),
                    total_size,
                    total_files,
                    total_dirs
                )
        except Exception:
            pass

    def _batch_calculate_folder_stats(self, paths: list, token: int):
        for p in paths:
            if token != self._folder_stats_worker_token:
                break
            self._compute_folder_stats(p, token)

    @Slot(str, result='QVariantMap')
    def getFolderStats(self, folder_path: str) -> dict:
        """Return cached stats for a folder or trigger immediate lookup."""
        norm_path = os.path.normpath(os.path.abspath(folder_path))
        cached = self._folder_stats_cache.get(norm_path)
        if cached:
            return cached
        return {"size": -1, "files": -1, "dirs": -1}


    @Slot(str, result='QVariantList')
    def getBreadcrumbs(self, path: str = "") -> list:
        """Return list of breadcrumb segments for the given path."""
        if not path:
            path = self._download_dir or os.path.expanduser("~")
        path = os.path.normpath(os.path.abspath(path))
        crumbs = []
        curr = path
        while curr:
            parent = os.path.dirname(curr)
            name = os.path.basename(curr)
            if not name:
                name = curr  # Root drive (e.g. C:\ or /)
            crumbs.append({"name": name, "path": curr})
            if parent == curr or not parent:
                break
            curr = parent
        crumbs.reverse()
        return crumbs

    @staticmethod
    def _drive_space_info(drive_path: str) -> dict:
        """Free / total space of one drive, formatted for the Gallery (blank when unknown)."""
        def _fmt_gb(gb_val: float) -> str:
            if gb_val >= 1000:
                return f"{gb_val / 1024:.1f} TB"
            elif gb_val >= 10:
                return f"{gb_val:.0f} GB"
            else:
                return f"{gb_val:.1f} GB"

        try:
            total, used, free = shutil.disk_usage(drive_path)
            free_gb = free / (1024**3)
            total_gb = total / (1024**3)

            if total_gb >= 1000 and free_gb < 1000:
                space_label = f"{_fmt_gb(free_gb)} / {_fmt_gb(total_gb)}"
            else:
                f_num = f"{free_gb:.0f}" if free_gb >= 10 else f"{free_gb:.1f}"
                t_num = f"{total_gb:.0f}" if total_gb >= 10 else f"{total_gb:.1f}"
                space_label = f"{f_num}/{t_num} GB"

            pct_free = (free / total * 100) if total > 0 else 0
            return {
                "free_bytes": free,
                "total_bytes": total,
                "used_bytes": used,
                "free_str": _fmt_gb(free_gb),
                "total_str": _fmt_gb(total_gb),
                "space_label": space_label,
                "percent_free": pct_free
            }
        except Exception:
            return dict(AppBridge._NO_SPACE_INFO)

    _NO_SPACE_INFO = {"free_bytes": 0, "total_bytes": 0, "used_bytes": 0, "free_str": "",
                      "total_str": "", "space_label": "", "percent_free": 100}

    @staticmethod
    def _drive_roots() -> list:
        """[(name, path)] of the drives / volumes to show (instant: nothing is opened)."""
        roots = []
        if sys.platform == "win32":
            import string
            from ctypes import windll
            try:
                bitmask = windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        roots.append((f"{letter}:", f"{letter}:\\"))
                    bitmask >>= 1
            except Exception:
                roots.append(("C:", "C:\\"))
        else:
            roots.append(("Root (/)", "/"))
            home = os.path.expanduser("~")
            if os.path.exists(home):
                roots.append(("Home (~)", home))
        return roots

    @Slot(result='QVariantList')
    def getSystemDrives(self) -> list:
        """The drives with their last known free space, returned right away.

        Asking a drive for its free space can hang (an offline network drive waits for a network
        timeout), and the Gallery asks on every folder change, so the space is refreshed in the
        background and sent with drivesUpdated."""
        cache = getattr(self, "_drive_space_cache", None)
        if cache is None:
            cache = self._drive_space_cache = {}
        drives = []
        for name, path in self._drive_roots():
            item = {"name": name, "path": path}
            item.update(cache.get(path) or self._NO_SPACE_INFO)
            drives.append(item)
        self._refresh_drive_space(drives)
        return drives

    def _refresh_drive_space(self, drives: list):
        now = time.time()
        if getattr(self, "_drive_refresh_running", False) or now - getattr(self, "_drive_refresh_at", 0.0) < 5.0:
            return
        self._drive_refresh_running = True
        self._drive_refresh_at = now
        slow = getattr(self, "_slow_drives", None)
        if slow is None:
            slow = self._slow_drives = {}

        def _job():
            try:
                results, threads = {}, []
                for d in drives:
                    path = d["path"]
                    if slow.get(path, 0.0) > time.time():
                        continue                  # didn't answer recently: leave it for a minute
                    def _probe(p=path):
                        results[p] = self._drive_space_info(p)
                    t = threading.Thread(target=_probe, daemon=True, name="DriveSpace")
                    t.start()
                    threads.append((path, t))
                deadline = time.time() + 4.0
                for path, t in threads:
                    t.join(max(0.0, deadline - time.time()))
                    if t.is_alive():
                        slow[path] = time.time() + 60.0
                self._drive_space_cache.update(results)
                updated = []
                for d in drives:
                    item = {"name": d["name"], "path": d["path"]}
                    item.update(self._drive_space_cache.get(d["path"]) or self._NO_SPACE_INFO)
                    updated.append(item)
                self.drivesUpdated.emit(updated)
            except RuntimeError:
                pass      # the app is closing
            except Exception as e:
                logger.debug(f"Drive space refresh failed: {e}", category="gallery")
            finally:
                self._drive_refresh_running = False
        threading.Thread(target=_job, daemon=True, name="DriveSpaceRefresh").start()

    def _get_default_gallery_bookmarks(self) -> list:
        defaults = []
        if self._download_dir and os.path.exists(self._download_dir):
            defaults.append({"name": "Downloads", "path": os.path.normpath(self._download_dir), "icon": "📥"})
        home = os.path.expanduser("~")
        sys_dl = os.path.join(home, "Downloads")
        if os.path.exists(sys_dl) and (not self._download_dir or os.path.normpath(sys_dl) != os.path.normpath(self._download_dir)):
            defaults.append({"name": "System Downloads", "path": os.path.normpath(sys_dl), "icon": "📁"})
        sys_pics = os.path.join(home, "Pictures")
        if os.path.exists(sys_pics):
            defaults.append({"name": "Pictures", "path": os.path.normpath(sys_pics), "icon": "🖼️"})
        sys_vids = os.path.join(home, "Videos")
        if os.path.exists(sys_vids):
            defaults.append({"name": "Videos", "path": os.path.normpath(sys_vids), "icon": "🎬"})
        return defaults

    @Property('QVariantList', notify=galleryBookmarksChanged)
    def galleryBookmarks(self) -> list:
        return self._gallery_bookmarks

    @Slot(result='QVariantList')
    def getGalleryBookmarks(self) -> list:
        return self._gallery_bookmarks

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def addGalleryBookmark(self, path: str, name: str = "") -> bool:
        if not path:
            return False
        norm = os.path.normpath(path)
        norm_case = os.path.normcase(norm)
        for b in self._gallery_bookmarks:
            if os.path.normcase(os.path.normpath(b.get("path", ""))) == norm_case:
                return False
        b_name = name.strip() if name and name.strip() else os.path.basename(norm)
        if not b_name:
            b_name = norm
        self._gallery_bookmarks.append({
            "name": b_name,
            "path": norm,
            "icon": "⭐"
        })
        self.saveSettings()
        self.galleryBookmarksChanged.emit()
        return True

    @Slot(str, result=bool)
    def removeGalleryBookmark(self, path: str) -> bool:
        if not path:
            return False
        norm_case = os.path.normcase(os.path.normpath(path))
        before_len = len(self._gallery_bookmarks)
        self._gallery_bookmarks = [
            b for b in self._gallery_bookmarks
            if os.path.normcase(os.path.normpath(b.get("path", ""))) != norm_case
        ]
        if len(self._gallery_bookmarks) != before_len:
            self.saveSettings()
            self.galleryBookmarksChanged.emit()
            return True
        return False

    @Slot(str, result=bool)
    def isGalleryBookmarked(self, path: str) -> bool:
        if not path:
            return False
        norm_case = os.path.normcase(os.path.normpath(path))
        for b in self._gallery_bookmarks:
            if os.path.normcase(os.path.normpath(b.get("path", ""))) == norm_case:
                return True
        return False

    @Slot(str)
    def openPathInSystem(self, path: str):
        """Open the given file or folder with the OS default application."""
        if not path:
            path = self._download_dir
        if not os.path.exists(path):
            return
        if os.path.isdir(path):
            self.openFolder(path)
        else:
            try:
                if sys.platform == "win32":
                    os.startfile(os.path.normpath(path))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            except Exception as e:
                logger.warning(f"Could not open file in system: {e}", category="system")

    @Slot(str, result=str)
    def pathToUrl(self, local_path: str) -> str:
        """Convert local filesystem path to QUrl string for QML components."""
        if not local_path:
            return ""
        from PySide6.QtCore import QUrl
        return QUrl.fromLocalFile(os.path.abspath(local_path)).toString()

    @Slot(str, result=int)
    def detectNextIndex(self, folder_path: str) -> int:
        """
        Scan folder for existing numbered files and detect the next sequential index.
        E.g., if files end or contain 100, returns 101.
        Filters out non-media binaries (.dll, .exe, etc.), architecture codes (x64, x86), and version numbers.
        If current folder is a numbered volume/chapter, safely checks the previous numbered sibling volume.
        If no numbers found anywhere, returns 1.
        """
        if not folder_path or not os.path.exists(folder_path):
            return 1

        VALID_MEDIA_EXTS = {
            '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.avif', '.heic', '.tiff', '.svg',
            '.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v', '.flv', '.wmv',
            '.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus',
            '.zip', '.cbz', '.cbr', '.rar', '.7z', '.tar', '.gz', '.pdf', '.txt', '.epub'
        }

        def extract_sequence_number(name: str, is_dir: bool = False):
            base, ext = os.path.splitext(name)
            if not is_dir:
                if ext.lower() not in VALID_MEDIA_EXTS and not base.isdigit():
                    return None
            # Filter out system architectures and video resolutions (e.g. x64, x86, 1080p, 720p, 4k)
            if re.search(r'\b(?:x86|x64|win32|win64|amd64|arm64|1080p|720p|4k|2160p|480p)\b', base, re.I) or base.lower() in ('x64', 'x86', 'win64', 'win32'):
                return None
            # Avoid dotted version numbers like 8.0.23.53103 or IP addresses
            if re.search(r'\d+\.\d+', base):
                return None
            # 1. Pure digits: '001', '100'
            if base.isdigit():
                val = int(base)
                return val if 0 < val < 10000 else None
            # 2. Number separated by separator or brackets: 'img_100', 'page-100', 'photo 100', 'art (100)'
            m = re.search(r'[\s_\-\(\[\{](\d+)\s*[\)\]\}]?$', base)
            if m:
                val = int(m.group(1))
                return val if 0 < val < 10000 else None
            # 3. Leading sequence number: '001_img', '100 - photo'
            m = re.search(r'^(\d+)[\s_\-\)\]\}]', base)
            if m:
                val = int(m.group(1))
                return val if 0 < val < 10000 else None
            # 4. Standard series keyword with number: 'Ch10', 'Vol2', 'Part3'
            m = re.search(r'(?:ch(?:apter)?|vol(?:ume)?|part|season|folder|set|page)?[\s_\-\#\[\(]?(\d+)$', base, re.I)
            if m:
                val = int(m.group(1))
                return val if 0 < val < 10000 else None
            return None

        def extract_max_from_dir(dpath: str) -> int:
            if not os.path.isdir(dpath):
                return 0
            candidate_numbers = []
            try:
                for entry in os.scandir(dpath):
                    if entry.is_file():
                        num = extract_sequence_number(entry.name, is_dir=False)
                        if num is not None:
                            candidate_numbers.append(num)
            except Exception:
                pass
            return max(candidate_numbers) if candidate_numbers else 0

        # 1. Scan files directly in folder_path
        max_num = extract_max_from_dir(folder_path)
        if max_num > 0:
            return max_num + 1

        # 2. If folder_path has no files with numbers, check subfolders within folder_path
        try:
            sub_candidates = []
            for entry in os.scandir(folder_path):
                if entry.is_dir():
                    num = extract_sequence_number(entry.name, is_dir=True)
                    if num is not None:
                        sub_candidates.append(num)
            if sub_candidates:
                return max(sub_candidates) + 1
        except Exception:
            pass

        # 3. Check sibling ONLY if parent is not root/desktop/downloads and folder shares a series prefix
        try:
            norm_p = os.path.normpath(os.path.abspath(folder_path))
            parent = os.path.dirname(norm_p)
            cur_name = os.path.basename(norm_p)

            user_home = os.path.expanduser('~')
            skip_parents = {
                os.path.normcase(user_home),
                os.path.normcase(os.path.join(user_home, 'Desktop')),
                os.path.normcase(os.path.join(user_home, 'Downloads')),
                os.path.normcase(os.path.join(user_home, 'Documents')),
                os.path.normcase(os.path.dirname(user_home))
            }
            if os.path.splitdrive(norm_p)[1] in ('\\', '/', ''):
                skip_parents.add(os.path.normcase(parent))

            if os.path.normcase(parent) not in skip_parents and parent and os.path.isdir(parent):
                m_cur = re.search(r'^(.*?)(\d+)\s*$', cur_name)
                if m_cur:
                    prefix = m_cur.group(1).lower()
                    cur_num = int(m_cur.group(2))
                    siblings = []
                    for entry in os.scandir(parent):
                        if entry.is_dir():
                            m_sib = re.search(r'^(.*?)(\d+)\s*$', entry.name)
                            if m_sib and m_sib.group(1).lower() == prefix:
                                siblings.append((int(m_sib.group(2)), entry.path))
                    siblings.sort(key=lambda x: x[0])
                    prev_siblings = [path for num, path in siblings if num < cur_num]
                    if prev_siblings:
                        prev_max = extract_max_from_dir(prev_siblings[-1])
                        if prev_max > 0:
                            return prev_max + 1
        except Exception:
            pass

        return 1

    @Slot(str, 'QVariantList', str, str, str, str, str, str, result='QVariantList')
    @Slot(str, 'QVariantList', str, str, str, str, str, str, int, result='QVariantList')
    @Slot(str, 'QVariantList', str, str, str, str, str, str, int, bool, result='QVariantList')
    @Slot(str, 'QVariantList', str, str, str, str, str, str, int, bool, bool, result='QVariantList')
    @Slot(str, 'QVariantList', str, str, str, str, str, str, int, bool, bool, str, result='QVariantList')
    def previewBatchRename(
        self,
        folder_path: str,
        files: list,
        pattern: str = "{name}.{ext}",
        find_text: str = "",
        replace_text: str = "",
        prefix: str = "",
        suffix: str = "",
        case_mode: str = "keep",
        start_index: int = 1,
        include_subfolders: bool = False,
        move_to_folder: bool = False,
        destination_folder: str = ""
    ) -> list:
        """
        Preview batch renaming results for files with metadata variable interpolation.
        Supports variables: {name}, {ext}, {artist}, {title}, {post_id}, {date}, {index}, {0index}, {00index}, {000index}.
        Supports custom start index, cross-folder continuous numbering, and moving/flattening to folder.
        """
        if not folder_path or not os.path.exists(folder_path):
            return []

        folder_name = os.path.basename(os.path.normpath(folder_path))
        parent_folder_name = os.path.basename(os.path.dirname(os.path.normpath(folder_path)))

        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

        if include_subfolders:
            collected = []
            for root_dir, dirs, filenames in os.walk(folder_path):
                dirs.sort(key=natural_sort_key)
                filenames.sort(key=natural_sort_key)
                for fn in filenames:
                    collected.append({
                        "name": fn,
                        "path": os.path.join(root_dir, fn)
                    })
            files = collected
        elif not files:
            try:
                files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
            except OSError:
                return []
            try:
                files = sorted(files, key=natural_sort_key)
            except Exception:
                pass
        else:
            try:
                def file_sort_val(x):
                    if isinstance(x, dict):
                        return x.get("path", x.get("name", ""))
                    return str(x)
                files = sorted(files, key=lambda x: natural_sort_key(file_sort_val(x)))
            except Exception:
                pass

        dest_dir = destination_folder.strip() if (destination_folder and destination_folder.strip()) else folder_path
        results = []
        new_names_seen = {}

        try:
            start_idx = max(0, int(start_index))
        except (ValueError, TypeError):
            start_idx = 1

        for idx, item in enumerate(files, start=start_idx):
            if isinstance(item, dict):
                filename = item.get("name", "")
                filepath = item.get("path", os.path.join(folder_path, filename))
            else:
                filename = str(item)
                filepath = os.path.join(folder_path, filename) if not os.path.isabs(filename) else filename
                filename = os.path.basename(filepath)

            base_name, ext = os.path.splitext(filename)
            raw_ext = ext.lstrip(".").lower()

            item_dir = os.path.dirname(filepath)
            item_folder_name = os.path.basename(item_dir)

            # Metadata extraction
            artist_match = re.search(r'\[([^\]]+)\]', base_name)
            artist = artist_match.group(1).strip() if artist_match else (item_folder_name if item_folder_name else (folder_name if folder_name else parent_folder_name))

            post_id_match = re.search(r'\b(\d{5,10})\b', base_name)
            if not post_id_match:
                post_id_match = re.search(r'\b(\d{5,10})\b', item_folder_name)
            if not post_id_match:
                post_id_match = re.search(r'\b(\d{5,10})\b', folder_name)
            post_id = post_id_match.group(1) if post_id_match else ""

            try:
                mtime = os.path.getmtime(filepath)
                date_str = time.strftime("%Y-%m-%d", time.localtime(mtime))
            except OSError:
                date_str = time.strftime("%Y-%m-%d")

            cleaned_title = base_name
            if artist_match:
                cleaned_title = cleaned_title.replace(artist_match.group(0), "")
            if post_id:
                cleaned_title = re.sub(rf'\b{post_id}\b', '', cleaned_title)
            cleaned_title = cleaned_title.strip(" -_") or base_name

            working_pattern = pattern if pattern else "{name}.{ext}"
            if not raw_ext:
                working_pattern = working_pattern.replace(".{ext}", "").replace("{ext}", "")

            new_name = working_pattern
            new_name = new_name.replace("{name}", base_name)
            new_name = new_name.replace("{ext}", raw_ext)
            new_name = new_name.replace("{artist}", artist)
            new_name = new_name.replace("{title}", cleaned_title)
            new_name = new_name.replace("{post_id}", post_id)
            new_name = new_name.replace("{date}", date_str)
            new_name = new_name.replace("{index}", str(idx))
            new_name = new_name.replace("{0index}", f"{idx:02d}")
            new_name = new_name.replace("{00index}", f"{idx:03d}")
            new_name = new_name.replace("{000index}", f"{idx:04d}")

            if find_text:
                new_name = new_name.replace(find_text, replace_text)

            if prefix or suffix:
                n_base, n_ext = os.path.splitext(new_name)
                new_name = f"{prefix}{n_base}{suffix}{n_ext}"

            if case_mode == "lower":
                n_base, n_ext = os.path.splitext(new_name)
                new_name = f"{n_base.lower()}{n_ext.lower()}"
            elif case_mode == "upper":
                n_base, n_ext = os.path.splitext(new_name)
                new_name = f"{n_base.upper()}{n_ext.lower()}"
            elif case_mode == "title":
                n_base, n_ext = os.path.splitext(new_name)
                new_name = f"{n_base.title()}{n_ext.lower()}"

            sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', new_name).strip(" .")
            if not sanitized_name:
                sanitized_name = filename

            if move_to_folder:
                new_filepath = os.path.join(dest_dir, sanitized_name)
            else:
                new_filepath = os.path.join(item_dir, sanitized_name)

            norm_dest = os.path.normcase(os.path.normpath(new_filepath))
            norm_src = os.path.normcase(os.path.normpath(filepath))

            status = "ready"
            err = ""

            if norm_dest == norm_src:
                status = "unchanged"
            elif norm_dest in new_names_seen:
                status = "collision"
                err = f"Duplicates another planned file: {sanitized_name}"
            elif os.path.exists(new_filepath) and norm_dest != norm_src:
                status = "collision"
                err = f"File already exists on disk: {sanitized_name}"

            new_names_seen[norm_dest] = filepath

            results.append({
                "old_name": filename,
                "new_name": sanitized_name,
                "old_path": filepath,
                "new_path": new_filepath,
                "status": status,
                "error": err,
                "valid": status in ("ready", "unchanged"),
                "is_move": move_to_folder and (os.path.normcase(os.path.dirname(filepath)) != os.path.normcase(dest_dir))
            })

        return results

    @Slot('QVariantList', result='QVariantMap')
    def executeBatchRename(self, plan: list) -> dict:
        """Execute a batch renaming/moving plan safely with two-phase rename for circular collisions."""
        import uuid
        import shutil
        renamed = 0
        failed = 0
        errors = []
        done = []          # (old, new) of every rename, for the log

        to_rename = [item for item in plan if item.get("status") == "ready" and item.get("valid", True)]
        if not to_rename:
            return {"success": True, "renamed": 0, "failed": 0, "errors": []}

        temp_renames = []
        for item in to_rename:
            src = os.path.normpath(item["old_path"])
            dst = os.path.normpath(item["new_path"])
            safety_src = self.getPathSafetyInfo(src)
            safety_dst = self.getPathSafetyInfo(dst)
            if safety_src.get("is_blocked") or safety_src.get("is_drive_root") or safety_dst.get("is_blocked") or safety_dst.get("is_drive_root"):
                failed += 1
                errors.append(f"Batch rename blocked on system/root path: {os.path.basename(src)}")
                continue

            if not os.path.exists(src):
                failed += 1
                errors.append(f"Source file not found: {os.path.basename(src)}")
                continue

            dst_dir = os.path.dirname(dst)
            if not os.path.exists(dst_dir):
                try:
                    os.makedirs(dst_dir, exist_ok=True)
                except Exception as e:
                    failed += 1
                    errors.append(f"Cannot create destination directory {dst_dir}: {e}")
                    continue

            needs_temp = False
            if os.path.normcase(src) == os.path.normcase(dst):
                needs_temp = True
            elif os.path.exists(dst):
                needs_temp = True

            if needs_temp:
                temp_path = f"{src}.tmp_batch_{uuid.uuid4().hex[:6]}"
                try:
                    shutil.move(src, temp_path)
                    temp_renames.append((temp_path, dst, src))
                except Exception as e:
                    failed += 1
                    errors.append(f"Cannot temp-rename {os.path.basename(src)}: {e}")
            else:
                try:
                    shutil.move(src, dst)
                    renamed += 1
                    done.append((src, dst))
                except Exception as e:
                    failed += 1
                    errors.append(f"Cannot rename {os.path.basename(src)}: {e}")

        for temp_src, final_dst, orig_src in temp_renames:
            try:
                os.makedirs(os.path.dirname(final_dst), exist_ok=True)
                shutil.move(temp_src, final_dst)
                renamed += 1
                done.append((orig_src, final_dst))
            except Exception as e:
                failed += 1
                errors.append(f"Cannot finalize rename to {os.path.basename(final_dst)}: {e}")
                try:
                    shutil.move(temp_src, orig_src)
                except Exception as back_err:
                    # The file is now only reachable under its temporary name: say exactly where
                    errors.append(f"Couldn't restore the original name either; the file is at {temp_src} ({back_err})")
                    logger.error(f"Batch rename left a file under a temporary name: {temp_src}", category="gallery",
                                 details=f"original name: {orig_src}\nintended name: {final_dst}\n{back_err!r}")

        if done:
            logger.info(f"Batch rename: renamed {renamed} item(s).", category="gallery",
                        details="\n".join(f"{a}  ->  {b}" for a, b in done))
        if errors:
            logger.warning(f"Batch rename: {failed} item(s) couldn't be renamed.", category="gallery",
                           details="\n".join(errors))

        return {
            "success": failed == 0,
            "renamed": renamed,
            "failed": failed,
            "errors": errors
        }

    @Slot(str, bool, result='QVariantList')
    def scanBrokenFiles(self, folder_path: str, recursive: bool = False) -> list:
        """Scan folder for 0-byte files, incomplete download temp files (.part, .crdownload, etc.), and empty folders."""
        if not folder_path or not os.path.exists(folder_path):
            return []

        safety = self.getPathSafetyInfo(folder_path)
        if safety.get("is_blocked"):
            logger.warning(f"scanBrokenFiles blocked on {folder_path} for system safety")
            return []

        norm_root = os.path.normpath(os.path.abspath(folder_path))
        broken = []
        temp_exts = {".part", ".crdownload", ".~tmp", ".download", ".temp", ".ytdl"}

        if not recursive:
            try:
                for entry in os.scandir(norm_root):
                    try:
                        p = os.path.normpath(entry.path)
                        rel_path = os.path.relpath(p, norm_root)
                        if entry.is_file(follow_symlinks=False):
                            sz = entry.stat().st_size
                            ext = os.path.splitext(entry.name)[1].lower()
                            if sz == 0:
                                broken.append({
                                    "path": p,
                                    "name": entry.name,
                                    "rel_path": rel_path,
                                    "type": "zero_byte",
                                    "type_label": "0-Byte Corrupt File",
                                    "size": 0,
                                    "mtime": entry.stat().st_mtime
                                })
                            elif ext in temp_exts:
                                broken.append({
                                    "path": p,
                                    "name": entry.name,
                                    "rel_path": rel_path,
                                    "type": "temp_file",
                                    "type_label": f"Incomplete Download ({ext})",
                                    "size": sz,
                                    "mtime": entry.stat().st_mtime
                                })
                        elif entry.is_dir(follow_symlinks=False):
                            try:
                                if not os.listdir(p):
                                    broken.append({
                                        "path": p,
                                        "name": entry.name,
                                        "rel_path": rel_path,
                                        "type": "empty_folder",
                                        "type_label": "Empty Directory",
                                        "size": 0,
                                        "mtime": entry.stat().st_mtime
                                    })
                            except OSError:
                                pass
                    except OSError:
                        pass
            except OSError:
                pass
        else:
            try:
                for root, dirs, files in os.walk(norm_root, topdown=False):
                    for d in dirs:
                        dp = os.path.join(root, d)
                        try:
                            if not os.listdir(dp):
                                broken.append({
                                    "path": os.path.normpath(dp),
                                    "name": d,
                                    "rel_path": os.path.relpath(dp, norm_root),
                                    "type": "empty_folder",
                                    "type_label": "Empty Directory",
                                    "size": 0,
                                    "mtime": os.path.getmtime(dp)
                                })
                        except OSError:
                            pass
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            sz = os.path.getsize(fp)
                            ext = os.path.splitext(f)[1].lower()
                            if sz == 0:
                                broken.append({
                                    "path": os.path.normpath(fp),
                                    "name": f,
                                    "rel_path": os.path.relpath(fp, norm_root),
                                    "type": "zero_byte",
                                    "type_label": "0-Byte Corrupt File",
                                    "size": 0,
                                    "mtime": os.path.getmtime(fp)
                                })
                            elif ext in temp_exts:
                                broken.append({
                                    "path": os.path.normpath(fp),
                                    "name": f,
                                    "rel_path": os.path.relpath(fp, norm_root),
                                    "type": "temp_file",
                                    "type_label": f"Incomplete Download ({ext})",
                                    "size": sz,
                                    "mtime": os.path.getmtime(fp)
                                })
                        except OSError:
                            pass
            except OSError:
                pass

        return broken

    @Slot('QVariantList', result='QVariantMap')
    def deleteItems(self, paths: list) -> dict:
        """Move files or folders to the Recycle Bin / Trash so deletions can be undone.

        Never falls back to a permanent delete: items the OS cannot trash
        (e.g. some network drives) are reported as failures instead.
        """
        from PySide6.QtCore import QFile

        deleted = 0
        failed = 0
        errors = []
        trashed = []

        for p in paths:
            if not p:
                continue
            norm_p = os.path.normpath(p)
            safety = self.getPathSafetyInfo(norm_p)
            if safety.get("is_blocked") or safety.get("is_drive_root"):
                failed += 1
                errors.append(f"Deletion blocked for system or root directory: {norm_p}")
                continue
            if not os.path.exists(norm_p):
                failed += 1
                errors.append(f"Target does not exist: {norm_p}")
                continue
            try:
                if QFile.moveToTrash(norm_p):
                    deleted += 1
                    trashed.append(norm_p)
                else:
                    failed += 1
                    errors.append(f"Could not move {os.path.basename(norm_p)} to the Recycle Bin")
            except Exception as e:
                failed += 1
                errors.append(f"Failed deleting {os.path.basename(norm_p)}: {e}")

        if deleted:
            logger.info(f"Moved {deleted} item(s) to the Recycle Bin.", category="gallery",
                        details="\n".join(trashed))
        if errors:
            logger.warning(f"{failed} item(s) couldn't be moved to the Recycle Bin.", category="gallery",
                           details="\n".join(errors))

        return {"deleted": deleted, "failed": failed, "errors": errors}

    @Slot('QVariantList', str, result='QVariantMap')
    def moveItems(self, paths: list, destDir: str) -> dict:
        """Move files or folders into destDir, never overwriting an existing item."""
        moved = 0
        failed = 0
        errors = []
        moved_pairs = []   # [source, target] for every item that moved, so it can be undone
        dest = os.path.normpath(destDir or "")
        if not dest or not os.path.isdir(dest):
            return {"moved": 0, "failed": len(paths), "errors": [f"Destination folder does not exist: {destDir}"], "pairs": []}
        dest_safety = self.getPathSafetyInfo(dest)
        if dest_safety.get("is_blocked"):
            return {"moved": 0, "failed": len(paths), "errors": [f"Moving into a protected system folder is blocked: {dest}"], "pairs": []}

        dest_case = os.path.normcase(dest)
        for p in paths:
            if not p:
                continue
            src = os.path.normpath(p)
            safety = self.getPathSafetyInfo(src)
            if safety.get("is_blocked") or safety.get("is_drive_root"):
                failed += 1
                errors.append(f"Move blocked for system or root directory: {src}")
                continue
            if not os.path.exists(src):
                failed += 1
                errors.append(f"Target does not exist: {src}")
                continue
            if os.path.normcase(os.path.dirname(src)) == dest_case:
                continue  # already there
            src_case = os.path.normcase(src)
            if dest_case == src_case or dest_case.startswith(src_case + os.sep):
                failed += 1
                errors.append(f"Cannot move a folder into itself: {os.path.basename(src)}")
                continue
            target = os.path.join(dest, os.path.basename(src))
            if os.path.exists(target):
                failed += 1
                errors.append(f"An item named '{os.path.basename(src)}' already exists in the destination")
                continue
            try:
                shutil.move(src, target)
                moved += 1
                moved_pairs.append([src, target])
            except Exception as e:
                failed += 1
                errors.append(f"Failed moving {os.path.basename(src)}: {e}")

        if moved:
            logger.info(f"Moved {moved} item(s) to '{dest}'.", category="gallery",
                        details="\n".join(f"{a}  ->  {b}" for a, b in moved_pairs))
        if errors:
            logger.warning(f"{failed} item(s) couldn't be moved to '{dest}'.", category="gallery",
                           details="\n".join(errors))

        return {"moved": moved, "failed": failed, "errors": errors, "pairs": moved_pairs}

    @Slot(str, str, result='QVariantMap')
    def renameItem(self, path: str, newName: str) -> dict:
        """Rename a single file or folder in place."""
        src = os.path.normpath(path or "")
        new_name = (newName or "").strip()
        if not src or not os.path.exists(src):
            return {"success": False, "error": "The item no longer exists.", "new_path": ""}
        if not new_name or new_name in (".", "..") or any(c in new_name for c in '<>:"/\\|?*') or new_name.endswith((".", " ")):
            return {"success": False, "error": "That name contains characters that aren't allowed.", "new_path": ""}
        safety = self.getPathSafetyInfo(src)
        if safety.get("is_blocked") or safety.get("is_drive_root"):
            return {"success": False, "error": "Renaming is blocked for system or root directories.", "new_path": ""}
        dst = os.path.join(os.path.dirname(src), new_name)
        if os.path.normcase(dst) == os.path.normcase(src) and dst == src:
            return {"success": True, "error": "", "new_path": src}
        # A case-only rename points at the same file on Windows, so it is not a collision.
        if os.path.exists(dst) and os.path.normcase(dst) != os.path.normcase(src):
            return {"success": False, "error": f"An item named '{new_name}' already exists here.", "new_path": ""}
        try:
            os.rename(src, dst)
        except Exception as e:
            logger.warning(f"Couldn't rename '{os.path.basename(src)}' to '{new_name}': {e}", category="gallery",
                           details=src)
            return {"success": False, "error": str(e), "new_path": ""}
        logger.info(f"Renamed '{os.path.basename(src)}' to '{new_name}'.", category="gallery",
                    details=f"{src}  ->  {dst}")
        return {"success": True, "error": "", "new_path": dst}

    @Slot(str, bool, result='QVariantList')
    def scanDuplicates(self, folder_path: str, recursive: bool = False) -> list:
        """
        Fast two-tier duplicate file finder using size grouping and SHA-256 chunked hashing.
        Returns duplicate groups sorted by wasted storage space descending.
        """
        import hashlib
        if not folder_path or not os.path.exists(folder_path):
            return []

        safety = self.getPathSafetyInfo(folder_path)
        if safety.get("is_blocked"):
            logger.warning(f"scanDuplicates blocked on {folder_path} for system safety")
            return []

        norm_root = os.path.normpath(os.path.abspath(folder_path))
        size_groups = {}

        def register_file(p):
            try:
                sz = os.path.getsize(p)
                if sz > 0:
                    if sz not in size_groups:
                        size_groups[sz] = []
                    size_groups[sz].append(p)
            except OSError:
                pass

        if not recursive:
            try:
                for entry in os.scandir(norm_root):
                    if entry.is_file(follow_symlinks=False):
                        register_file(entry.path)
            except OSError:
                pass
        else:
            try:
                for root, _, files in os.walk(norm_root):
                    for f in files:
                        register_file(os.path.join(root, f))
            except OSError:
                pass

        partial_groups = {}
        for sz, flist in size_groups.items():
            if len(flist) < 2:
                continue
            for p in flist:
                try:
                    with open(p, "rb") as f:
                        header = f.read(65536)
                        p_hash = hashlib.md5(header).hexdigest()
                        key = (sz, p_hash)
                        if key not in partial_groups:
                            partial_groups[key] = []
                        partial_groups[key].append(p)
                except OSError:
                    pass

        duplicate_groups = []
        for (sz, _), flist in partial_groups.items():
            if len(flist) < 2:
                continue
            full_groups = {}
            for p in flist:
                try:
                    h = hashlib.sha256()
                    with open(p, "rb") as f:
                        while chunk := f.read(65536):
                            h.update(chunk)
                    full_hash = h.hexdigest()
                    if full_hash not in full_groups:
                        full_groups[full_hash] = []
                    full_groups[full_hash].append(p)
                except OSError:
                    pass

            for fhash, matches in full_groups.items():
                if len(matches) >= 2:
                    files_info = []
                    for mp in matches:
                        try:
                            mtime = os.path.getmtime(mp)
                        except OSError:
                            mtime = 0
                        files_info.append({
                            "path": os.path.normpath(mp),
                            "name": os.path.basename(mp),
                            "rel_path": os.path.relpath(mp, norm_root),
                            "mtime": mtime
                        })
                    files_info.sort(key=lambda x: x["mtime"])
                    duplicate_groups.append({
                        "hash": fhash[:12],
                        "size": sz,
                        "count": len(files_info),
                        "wasted_size": (len(files_info) - 1) * sz,
                        "files": files_info
                    })

        duplicate_groups.sort(key=lambda g: g["wasted_size"], reverse=True)
        return duplicate_groups

    @Slot(str, result='QVariantMap')
    def getPathSafetyInfo(self, path: str) -> dict:
        """
        Analyze path to verify safety for bulk operations like Clean, Delete, Auto-Sort, and Batch Rename.
        Foolproof protection blocking OS drive root, Users folder, Program Files, Python installations,
        and Windows/application directories on the system drive.
        """
        if not path or not path.strip():
            return {
                "is_blocked": True,
                "is_system_root": False,
                "is_system_dir": False,
                "is_drive_root": False,
                "is_other_root": False,
                "system_drive": "C:",
                "drive_letter": "",
                "path": "",
                "message": "Empty or invalid folder path."
            }

        norm = os.path.normpath(os.path.abspath(path.strip()))
        norm_case = os.path.normcase(norm)

        # 1. Detect OS System Drive & System Root
        windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or "C:\\Windows"
        system_drive_env = os.environ.get("SystemDrive")
        if not system_drive_env and windir:
            drive_part, _ = os.path.splitdrive(windir)
            system_drive_env = drive_part if drive_part else "C:"
        elif not system_drive_env:
            system_drive_env = "C:"
        system_drive = system_drive_env.upper().rstrip(":") + ":"
        sys_drive_root = system_drive + "\\"
        norm_sys_root = os.path.normcase(os.path.normpath(sys_drive_root))

        drive, tail = os.path.splitdrive(norm)
        drive_letter = drive.upper() if drive else ""
        tail_stripped = tail.strip("\\/")

        if sys.platform == "win32":
            is_drive_root = bool(drive_letter and (tail_stripped == ""))
            is_system_root = is_drive_root and (drive_letter == system_drive)
        else:
            is_drive_root = (norm == "/" or os.path.ismount(norm))
            is_system_root = (norm == "/")

        if is_system_root:
            return {
                "is_blocked": True,
                "is_system_root": True,
                "is_system_dir": False,
                "is_drive_root": True,
                "is_other_root": False,
                "system_drive": system_drive,
                "drive_letter": drive_letter,
                "path": norm,
                "message": f"Operations are permanently disabled on the operating system drive root ({drive_letter}\\) for system stability."
            }

        # 2. Windows system & core OS directories
        if sys.platform == "win32":
            protected_system_dirs = [
                windir,
                os.path.join(sys_drive_root, "Windows"),
                os.path.join(sys_drive_root, "System Volume Information"),
                os.path.join(sys_drive_root, "$Recycle.Bin"),
                os.path.join(sys_drive_root, "Recovery"),
                os.path.join(sys_drive_root, "PerfLogs"),
                os.path.join(sys_drive_root, "Boot"),
                os.path.join(sys_drive_root, "Documents and Settings"),
                os.path.join(sys_drive_root, "MSOCache"),
                os.path.join(sys_drive_root, "Config.Msi"),
                os.path.join(sys_drive_root, "inetpub"),
            ]
            for s_dir in protected_system_dirs:
                p_case = os.path.normcase(os.path.normpath(s_dir))
                if norm_case == p_case or norm_case.startswith(p_case + os.path.sep):
                    return {
                        "is_blocked": True,
                        "is_system_root": False,
                        "is_system_dir": True,
                        "is_drive_root": False,
                        "is_other_root": False,
                        "system_drive": system_drive,
                        "drive_letter": drive_letter,
                        "path": norm,
                        "message": "Operations are permanently disabled on protected operating system directories."
                    }

            # Check for $ prefix on system drive (e.g. $Windows.~BT, $WinREAgent)
            if norm_case.startswith(norm_sys_root) and any(part.startswith("$") for part in norm_case.split(os.path.sep)):
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": "Operations are permanently disabled on Windows system cache/recovery directories."
                }
        else:
            def _blocked(message: str) -> dict:
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": message
                }

            # Removable / extra disks are mounted below these; the disks themselves are allowed
            # (as drive roots, with double confirmation), the folders holding them are not
            mount_parents = ["/media", "/mnt", "/run/media", "/Volumes"]
            protected_unix_dirs = [
                "/bin", "/boot", "/dev", "/etc", "/lib", "/lib32", "/lib64", "/libx32", "/opt",
                "/proc", "/root", "/sbin", "/snap", "/sys", "/usr", "/var",
                "/System", "/Library", "/Applications", "/private", "/cores",
            ]
            for u_dir in protected_unix_dirs:
                if norm == u_dir or norm.startswith(u_dir + "/"):
                    return _blocked(f"Operations are permanently disabled on protected system directory ({u_dir}).")
            if norm == "/run" or (norm.startswith("/run/") and not norm.startswith("/run/media/")):
                return _blocked("Operations are permanently disabled on protected system directory (/run).")

            # Home folders: the same protection Windows gets for C:\Users (this was Windows-only, so
            # Flatten / Auto-sort / Delete / Batch rename could run on /home/<user> or ~/.ssh)
            home = os.path.normpath(os.path.expanduser("~"))
            user_roots = ["/home", "/Users"]
            if norm in user_roots or norm in mount_parents:
                return _blocked(f"Operations are permanently disabled on {norm}, which holds user accounts or disks.")
            if os.path.dirname(norm) in user_roots or norm == home:
                return _blocked("Operations are permanently disabled directly on a home folder to protect its settings "
                                "and hidden folders. Please select a subfolder (such as Downloads or Pictures).")
            for m_parent in ("/media", "/run/media"):
                if os.path.dirname(norm) == m_parent:      # /media/<user>: holds that user's disks
                    return _blocked(f"Operations are permanently disabled on {norm}, which holds mounted disks.")
            in_home = norm.startswith(home + "/") or any(norm.startswith(r + "/") for r in user_roots)
            if in_home:
                for part in norm.split("/"):
                    if part.startswith(".") and part not in (".", ".."):
                        return _blocked(f"Operations are permanently disabled on hidden application configuration folders ({part}).")

        # 3. Program Files & ProgramData (on any drive)
        parts = [p.lower() for p in norm_case.split(os.path.sep)]
        if "program files" in parts or "program files (x86)" in parts or "programdata" in parts or "windowsapps" in parts:
            return {
                "is_blocked": True,
                "is_system_root": False,
                "is_system_dir": True,
                "is_drive_root": False,
                "is_other_root": False,
                "system_drive": system_drive,
                "drive_letter": drive_letter,
                "path": norm,
                "message": "Operations are permanently disabled inside Program Files / ProgramData to protect installed software."
            }

        # 4. Users Directory & Profile Roots
        if sys.platform == "win32":
            users_dir_case = os.path.normcase(os.path.join(sys_drive_root, "Users"))
            if norm_case == users_dir_case:
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": f"Operations are permanently disabled on the Users directory ({drive_letter}\\Users) to protect user account data."
                }

            # Check if target is directly a User profile root (e.g. C:\Users\silvi or C:\Users\Public)
            if os.path.normcase(os.path.dirname(norm)) == users_dir_case:
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": "Operations are permanently disabled directly on your User Profile home folder to protect profile configuration and system directories. Please select a subfolder (such as Downloads or Pictures)."
                }

            # Inside user directory: AppData, Application Data, Local Settings (except system Temp dir)
            import tempfile
            sys_temp_case = os.path.normcase(os.path.normpath(tempfile.gettempdir()))
            is_temp_dir = (norm_case == sys_temp_case or norm_case.startswith(sys_temp_case + os.path.sep))
            if not is_temp_dir and ("appdata" in parts or "application data" in parts or "local settings" in parts):
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": "Operations are permanently disabled inside AppData to protect application configurations and local data."
                }

            # Inside user directory: dot-configuration folders (.vscode, .cargo, .gemini, etc.)
            if norm_case.startswith(users_dir_case + os.path.sep):
                for part in parts:
                    if part.startswith(".") and part not in (".", ".."):
                        return {
                            "is_blocked": True,
                            "is_system_root": False,
                            "is_system_dir": True,
                            "is_drive_root": False,
                            "is_other_root": False,
                            "system_drive": system_drive,
                            "drive_letter": drive_letter,
                            "path": norm,
                            "message": f"Operations are permanently disabled on hidden application configuration folders ({part})."
                        }

        # 5. Python & Runtime Environment Installations
        for part in parts:
            if part.startswith(("python", "pymanager", "miniconda", "anaconda", "virtualenv", "venv")):
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": "Operations are permanently disabled on Python and runtime environment installations."
                }

        # Check for python executables or venv marker in directory or immediate parent
        check_dirs = [norm]
        parent_dir = os.path.dirname(norm)
        if parent_dir and parent_dir != norm:
            check_dirs.append(parent_dir)
        for cd in check_dirs:
            try:
                if os.path.exists(os.path.join(cd, "python.exe")) or \
                   os.path.exists(os.path.join(cd, "py.exe")) or \
                   os.path.exists(os.path.join(cd, "pyvenv.cfg")) or \
                   os.path.exists(os.path.join(cd, "Scripts", "pip.exe")):
                    return {
                        "is_blocked": True,
                        "is_system_root": False,
                        "is_system_dir": True,
                        "is_drive_root": False,
                        "is_other_root": False,
                        "system_drive": system_drive,
                        "drive_letter": drive_letter,
                        "path": norm,
                        "message": "Operations are permanently disabled on Python and runtime environment installations."
                    }
            except OSError:
                pass

        # 6. Apps, Games, Web Servers, and Tool Directories on System Drive (C:\)
        if sys.platform == "win32" and norm_case.startswith(norm_sys_root):
            rel_to_sys = os.path.relpath(norm, sys_drive_root)
            top_folder = rel_to_sys.split(os.path.sep)[0].lower()

            known_c_app_folders = {
                "games", "xboxgames", "riot games", "steamcmd", "steam", "steamlibrary",
                "epic games", "gog games", "ubisoft", "battle.net",
                "qt", "certbot", "xamp", "xampp", "wamp", "nginx", "apache",
                "tools", "bin", "vcpkg", "mingw", "cygwin", "msys", "llvm",
                "prism hub", "rootline prism"
            }
            if top_folder in known_c_app_folders or top_folder.startswith(("borderless", "app", "game")):
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": f"Operations are permanently disabled on application and game installation directories ({top_folder})."
                }

            # Check if top-level directory on C:\ contains application executables/binaries
            top_abs = os.path.join(sys_drive_root, top_folder)
            safe_c_folders = {
                "downloads", "testdownloads", "test", "tmp", "workspace",
                "media", "data", "backup", "kemono", "pawchive"
            }
            if top_folder not in safe_c_folders:
                try:
                    for item in os.scandir(top_abs):
                        ext = os.path.splitext(item.name)[1].lower()
                        if ext in (".exe", ".dll", ".sys") or item.name.lower().startswith(("uninstall", "unins")):
                            return {
                                "is_blocked": True,
                                "is_system_root": False,
                                "is_system_dir": True,
                                "is_drive_root": False,
                                "is_other_root": False,
                                "system_drive": system_drive,
                                "drive_letter": drive_letter,
                                "path": norm,
                                "message": f"Operations are permanently disabled on application and software directories ({top_folder})."
                            }
                except OSError:
                    pass

        # 7. Other Root Disks (e.g. D:\)
        is_other_root = is_drive_root and not is_system_root
        msg = ""
        if is_other_root:
            where = f"{drive_letter}\\" if sys.platform == "win32" else norm
            msg = f"Target is the root of drive ({where}). Executing operations here affects the entire drive and requires double confirmation."

        return {
            "is_blocked": False,
            "is_system_root": False,
            "is_system_dir": False,
            "is_drive_root": is_drive_root,
            "is_other_root": is_other_root,
            "system_drive": system_drive,
            "drive_letter": drive_letter,
            "path": norm,
            "message": msg
        }

    def _refuse_if_disabled(self, url_or_domain: str, context: str = "link") -> bool:
        """True (after telling the user) when the link belongs to a switched-off site.
        Kemono and Coomer are switched off for now; the message points to Pawchive / cum.st."""
        from core.providers import is_disabled, disabled_message, alternative_url
        if not url_or_domain or not is_disabled(url_or_domain):
            return False
        msg = disabled_message(url_or_domain)
        alt = alternative_url(url_or_domain) if "/" in url_or_domain else ""
        logger.warning(msg + (f" Same link on Pawchive: {alt}" if alt else ""), category="parser")
        self.providerDisabled.emit(msg, alt, context)
        return True

    @Slot(result=int)
    def kemonoWatchlistCount(self) -> int:
        from core.providers import provider_for_host, KEMONO
        return sum(1 for e in list(self._watchlist_manager.entries)
                   if provider_for_host(e.domain) == KEMONO or provider_for_host(e.url) == KEMONO)

    @Slot(result=int)
    def switchWatchlistToPawchive(self) -> int:
        """Moves the Watchlist's Kemono artists to Pawchive (it uses the same creator IDs)."""
        from core.providers import provider_for_host, alternative_url, KEMONO
        changed = 0
        with self._watchlist_manager._lock:
            for e in self._watchlist_manager.entries:
                if provider_for_host(e.domain) == KEMONO or provider_for_host(e.url) == KEMONO:
                    new_url = alternative_url(e.url) or f"https://pawchive.pw/{e.service}/user/{e.user_id}"
                    e.url = new_url
                    e.domain = "pawchive.pw"
                    changed += 1
            if changed:
                self._watchlist_manager.save()
        if changed:
            logger.success(f"Moved {changed} Watchlist artist(s) from Kemono to Pawchive.", category="watchlist")
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()
        return changed

    def _run_async(self, request_id: str, fn, *args) -> None:
        """Runs fn(*args) in a background thread and sends the result to QML with asyncResultReady.
        (Scans that ran on the window thread froze the app on big folders.)"""
        def _job():
            try:
                result = fn(*args)
            except Exception as e:
                logger.error(f"Background task failed: {e}", category="system")
                result = None
            try:
                self.asyncResultReady.emit(request_id, result)
            except RuntimeError:
                pass      # the app is closing
        threading.Thread(target=_job, daemon=True, name=f"async:{request_id[:24]}").start()

    @Slot(str, str, bool)
    def scanBrokenFilesAsync(self, request_id: str, folder_path: str, recursive: bool = False):
        self._run_async(request_id, self.scanBrokenFiles, folder_path, recursive)

    @Slot(str, str, bool)
    def scanDuplicatesAsync(self, request_id: str, folder_path: str, recursive: bool = False):
        self._run_async(request_id, self.scanDuplicates, folder_path, recursive)

    @Slot(str, str, str, bool)
    def autoSortFolderAsync(self, request_id: str, folder_path: str, mode: str = "type", recursive: bool = False):
        self._run_async(request_id, self.autoSortFolder, folder_path, mode, recursive)

    @Slot(str, str)
    def undoFlattenAsync(self, request_id: str, folder_path: str):
        self._run_async(request_id, self.undoFlatten, folder_path)

    @Slot(str, str, 'QVariantList', str, str, str, str, str, str, int, bool, bool, str)
    def previewBatchRenameAsync(self, request_id: str, folder_path: str, files: list, pattern: str,
                                find_text: str, replace_text: str, prefix: str, suffix: str, case_mode: str,
                                start_index: int, include_subfolders: bool, move_to_folder: bool,
                                destination_folder: str):
        self._run_async(request_id, self.previewBatchRename, folder_path, list(files or []), pattern, find_text,
                        replace_text, prefix, suffix, case_mode, start_index, include_subfolders,
                        move_to_folder, destination_folder)

    @Slot(str, str)
    def detectNextIndexAsync(self, request_id: str, folder_path: str):
        self._run_async(request_id, self.detectNextIndex, folder_path)

    @Slot(str, 'QVariantList')
    def executeBatchRenameAsync(self, request_id: str, plan: list):
        self._run_async(request_id, self.executeBatchRename, list(plan or []))

    @staticmethod
    def _flatten_log_path(folder_path: str) -> str:
        import hashlib
        from core.path_utils import get_config_dir
        key = hashlib.md5(os.path.normcase(os.path.normpath(os.path.abspath(folder_path))).encode("utf-8")).hexdigest()
        return os.path.join(get_config_dir(), "undo", f"flatten_{key}.json")

    @Slot(str, result=bool)
    def hasFlattenUndo(self, folder_path: str) -> bool:
        return bool(folder_path) and os.path.exists(self._flatten_log_path(folder_path))

    @Slot(str, result='QVariantMap')
    def undoFlatten(self, folder_path: str) -> dict:
        """Moves the files of the last Flatten back into the folders they came from."""
        import json
        import shutil
        log_path = self._flatten_log_path(folder_path)
        if not os.path.exists(log_path):
            return {"moved": 0, "errors": ["There is nothing to undo for this folder."]}
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception as e:
            return {"moved": 0, "errors": [f"The undo record couldn't be read: {e}"]}
        root = os.path.normpath(os.path.abspath(folder_path))
        restored, errors = 0, []
        for src_rel, dst_rel in reversed(log.get("moves", [])):
            src = os.path.normpath(os.path.join(root, src_rel))
            dst = os.path.normpath(os.path.join(root, dst_rel))
            # Never outside the folder, even with an edited record
            if not (src.startswith(root + os.sep) and dst.startswith(root + os.sep)):
                continue
            if not os.path.exists(dst):
                errors.append(f"{dst_rel} is no longer there")
                continue
            if os.path.exists(src):
                errors.append(f"{src_rel} already exists")
                continue
            try:
                os.makedirs(os.path.dirname(src), exist_ok=True)
                shutil.move(dst, src)
                restored += 1
            except Exception as e:
                errors.append(f"Could not move {dst_rel} back: {e}")
        try:
            os.remove(log_path)
        except OSError:
            pass
        logger.info(f"Undo flatten: moved {restored} file(s) back into their folders in {root}.", category="file")
        return {"moved": restored, "errors": errors[:20], "mode": "undo"}

    @Slot(str, str, bool, result='QVariantMap')
    @Slot(str, str, result='QVariantMap')
    def autoSortFolder(self, folder_path: str, mode: str = "type", recursive: bool = False) -> dict:
        """
        Auto-organize files in a folder into clean subfolder hierarchies by type, date, or extension.
        When recursive=True, recursively organizes loose attachments inside every post subfolder
        (e.g. Creator/[Post 1]/Images/, Creator/[Post 2]/Videos/) without re-downloading.
        """
        import shutil
        if not folder_path or not os.path.exists(folder_path):
            return {"moved": 0, "errors": ["Folder does not exist"]}

        safety = self.getPathSafetyInfo(folder_path)
        if safety.get("is_blocked"):
            return {
                "moved": 0,
                "errors": [safety.get("message") or "Operation blocked on system root or protected folders."]
            }

        norm_root = os.path.normpath(os.path.abspath(folder_path))
        moved = 0
        errors = []

        # ── Mode: Dump / Flatten (Move everything into root folder) ──────────
        if mode in ("dump", "flatten"):
            undo_moves = []
            try:
                for root_dir, dirs, files in os.walk(norm_root, topdown=False):
                    if os.path.normcase(root_dir) == os.path.normcase(norm_root):
                        continue
                    for fname in files:
                        src = os.path.normpath(os.path.join(root_dir, fname))
                        base, ext = os.path.splitext(fname)
                        target_file = os.path.normpath(os.path.join(norm_root, fname))

                        if os.path.exists(target_file) and os.path.normcase(src) != os.path.normcase(target_file):
                            counter = 1
                            while True:
                                target_file = os.path.normpath(os.path.join(norm_root, f"{base} ({counter}){ext}"))
                                if not os.path.exists(target_file):
                                    break
                                counter += 1

                        try:
                            shutil.move(src, target_file)
                            moved += 1
                            undo_moves.append([os.path.relpath(src, norm_root), os.path.relpath(target_file, norm_root)])
                        except Exception as e:
                            errors.append(f"Could not move {fname}: {e}")

                # Clean up empty subdirectories left behind
                for root_dir, dirs, files in os.walk(norm_root, topdown=False):
                    if os.path.normcase(root_dir) == os.path.normcase(norm_root):
                        continue
                    try:
                        os.rmdir(root_dir)
                    except OSError:
                        pass
            except Exception as e:
                errors.append(f"Flatten/dump error: {e}")

            # A record of every move, so the flatten can be undone (it couldn't be before)
            if undo_moves:
                try:
                    from core.atomic_io import atomic_write_json
                    atomic_write_json(self._flatten_log_path(norm_root),
                                      {"folder": norm_root, "created": time.time(), "moves": undo_moves})
                    logger.info(f"Flatten: moved {moved} file(s) into {norm_root} (can be undone).", category="file")
                except Exception as e:
                    logger.warning(f"Flatten: couldn't save the undo record: {e}", category="file")
            return {"moved": moved, "errors": errors, "mode": "flatten", "undo_available": bool(undo_moves)}

        type_map = {
            "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico"},
            "video": {".mp4", ".mkv", ".webm", ".mov", ".avi", ".ts", ".flv", ".m4v"},
            "audio": {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".opus", ".aac"},
            "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
            "document": {".txt", ".pdf", ".json", ".html", ".md", ".epub", ".doc", ".docx"}
        }

        # Names of category folders that shouldn't be nested recursively inside themselves
        PROTECTED_SUBDIR_NAMES = {
            "images", "videos", "audio", "archives", "documents", "other"
        }

        def _sort_single_directory(target_dir_path: str) -> int:
            nonlocal errors
            dir_moved = 0
            try:
                entries = [e for e in os.scandir(target_dir_path) if e.is_file(follow_symlinks=False)]
            except OSError as e:
                errors.append(f"Cannot read {target_dir_path}: {e}")
                return 0

            for entry in entries:
                src = os.path.normpath(entry.path)
                fname = entry.name
                base, ext = os.path.splitext(fname)
                ext_lower = ext.lower()

                if mode == "date":
                    try:
                        mtime = entry.stat().st_mtime
                        sub_name = time.strftime("%Y-%m", time.localtime(mtime))
                    except OSError:
                        sub_name = "Unknown_Date"
                elif mode == "extension":
                    sub_name = ext_lower.lstrip(".").upper() or "NO_EXT"
                else:
                    sub_name = "Other"
                    for cat, extensions in type_map.items():
                        if ext_lower in extensions:
                            sub_name = cat.capitalize() + "s" if cat in ("image", "video", "archive", "document") else "Audio"
                            break

                dest_dir = os.path.join(target_dir_path, sub_name)
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except OSError as e:
                    errors.append(f"Cannot create directory {sub_name} in {target_dir_path}: {e}")
                    continue

                target_file = os.path.join(dest_dir, fname)
                if os.path.exists(target_file) and os.path.normcase(src) != os.path.normcase(target_file):
                    counter = 1
                    while True:
                        target_file = os.path.join(dest_dir, f"{base} ({counter}){ext}")
                        if not os.path.exists(target_file):
                            break
                        counter += 1

                try:
                    shutil.move(src, target_file)
                    dir_moved += 1
                except Exception as e:
                    errors.append(f"Could not move {fname}: {e}")

            return dir_moved

        def _is_sort_folder(name: str) -> bool:
            """A folder a sort creates (in any mode): sorting inside it again nested folders."""
            n = name.lower()
            return (n in PROTECTED_SUBDIR_NAMES or n == "unknown_date"
                    or re.fullmatch(r"\d{4}-\d{2}", name) is not None
                    or (mode == "extension" and re.fullmatch(r"[A-Z0-9]{1,10}|NO_EXT", name) is not None))

        # The folders to sort are listed before anything moves, so folders this run creates are skipped
        targets = [norm_root]
        if recursive:
            try:
                for root_dir, dirs, _ in os.walk(norm_root):
                    dirs[:] = [d for d in dirs if not _is_sort_folder(d)]
                    targets.extend(os.path.join(root_dir, d) for d in dirs)
            except Exception as e:
                errors.append(f"Recursive walk error: {e}")

        for target in targets:
            moved += _sort_single_directory(target)

        return {"moved": moved, "errors": errors, "mode": mode}



