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


def init_bridge_core_state(self) -> None:

    # File explorer folder stats & preview caches + worker token
    self._folder_stats_cache = {}
    self._folder_previews_cache = {}
    self._folder_stats_worker_token = 0

    # Core systems
    self.known_manager = KnownManager()
    self.session_manager = SessionManager()
    saved_settings = self.session_manager.load_settings()
    self._loaded_decompressor_settings = saved_settings.get("decompressor") or {}   # (until it exists)
    self._enable_download_archive = bool(saved_settings.get("enable_download_archive", False))
    self.archive_manager = ArchiveManager(
        config_dir=self.session_manager.config_dir,
        enabled=self._enable_download_archive
    )
    self.archive_manager.on_repair_finished = self._on_archive_repaired
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
    self._skip_words = saved_settings.get("skip_words", "")
    self._skip_scope = saved_settings.get("skip_scope", "posts")
    self._remove_words = saved_settings.get("remove_words", "")
    self._filter_profile = saved_settings.get("filter_profile", FilterEngine.match_filter_profile(self._skip_words))
    self._remove_words_profile = saved_settings.get("remove_words_profile", FilterEngine.match_remove_words_profile(self._remove_words))
    # Date range filters apply to one download; remembering them silently skipped posts later
    self._date_after = ""
    self._date_before = ""
    self._date_auto_scan_pages = bool(saved_settings.get("date_auto_scan_pages", True))
    self._min_file_size = str(saved_settings.get("min_file_size", ""))
    self._max_file_size = str(saved_settings.get("max_file_size", ""))
    self._video_duration_filter_enabled = bool(saved_settings.get("video_duration_filter_enabled", False))
    self._min_video_duration = str(saved_settings.get("min_video_duration", ""))
    self._max_video_duration = str(saved_settings.get("max_video_duration", ""))
    self._filter_type = "all"
    self._exact_extensions = str(saved_settings.get("exact_extensions", "")).strip()
    self._saved_custom_extensions = [
        ext.strip().lower() for ext in saved_settings.get("saved_custom_extensions", [])
        if isinstance(ext, str) and ext.strip()
    ]
    self._skip_archives = False
    self._download_thumbnails_only = bool(saved_settings.get("download_thumbnails_only", False))
    self._fallback_to_thumbnails = bool(saved_settings.get("fallback_to_thumbnails", False))
    self._hide_unimported_notice = bool(saved_settings.get("hide_unimported_notice", False))
    self._redownload_small_files = bool(saved_settings.get("redownload_small_files", False))
    self._skip_post_covers = bool(saved_settings.get("skip_post_covers", False))
    self._scan_content_images = saved_settings.get("scan_content_images", True)
    self._download_dms = bool(saved_settings.get("download_dms", False))
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
    folder_naming.include_service = bool(saved_settings.get("site_in_folder_name", True))
    self._file_index_prefix = bool(saved_settings.get("file_index_prefix", False))
    self._separate_folders_by_known = saved_settings.get("separate_by_known", False)
    self._download_revisions = saved_settings.get("download_revisions", False)
    self._adaptive_threading = saved_settings.get("adaptive_threading", False)
    self._threads_locked = bool(saved_settings.get("threads_locked", False))
    if self._threads_locked:
        self._adaptive_threading = False
    self._auto_retry_at_end = saved_settings.get("auto_retry_at_end", False)
    self._skip_retry_404 = bool(saved_settings.get("skip_retry_404", False))
    self._privacy_pin = str(saved_settings.get("privacy_pin", "") or "")
    self._privacy_mode_active = False  # NEVER remains active on app restart
    self._failed_pin_attempts = 0
    self._privacy_lockout_active = False
    self._pending_pin_reset = bool(saved_settings.get("pending_pin_reset", False))
    self._safe_mode_active = self._pending_pin_reset
    self._privacy_idle_minutes = max(0, min(60, int(saved_settings.get("privacy_idle_minutes", 5))))
    self._manga_mode = saved_settings.get("manga_mode", False)
    self._filename_style = saved_settings.get("filename_style", "post_title")
    self._filename_template = saved_settings.get("filename_template", "{title} - {orig_name}")
    self._is_post_selection_loading = False
    self._post_selection_progress_page = 0
    self._post_selection_progress_count = 0
    self._post_selection_progress_total = 0
    self._post_selection_progress_status = ""
    self._selection_cached_posts = []
    self._selection_cached_cards = []
    self._selection_cache_key = ""
    self._selection_session_key = ""
    self._selection_parsed = None
    self._selection_creator_name = ""
    self._selection_creator_unimported = False
    self._gallery_bookmarks = list(saved_settings.get("gallery_bookmarks", []) or [])
    if not self._gallery_bookmarks:
        self._gallery_bookmarks = self._get_default_gallery_bookmarks()
    self._proxy_url = saved_settings.get("proxy_url", "")
    self._bandwidth_limit_enabled = bool(saved_settings.get("bandwidth_limit_enabled", False))
    try:
        self._bandwidth_limit_value = float(saved_settings.get("bandwidth_limit_value", 10.0))
    except (ValueError, TypeError):
        self._bandwidth_limit_value = 10.0
    self._bandwidth_limit_unit = str(saved_settings.get("bandwidth_limit_unit", "MB/s")).strip()
    if self._bandwidth_limit_unit not in ("MB/s", "mbps"):
        self._bandwidth_limit_unit = "MB/s"
    bandwidth_limiter.update(
        self._bandwidth_limit_enabled,
        self._bandwidth_limit_value,
        self._bandwidth_limit_unit
    )
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
    self._write_sidecars = bool(saved_settings.get("write_sidecars", False))
    self._sidecar_format = str(saved_settings.get("sidecar_format", "json"))
    self._sidecar_scope = str(saved_settings.get("sidecar_scope", "per_file"))
    self._download_embeds = bool(saved_settings.get("download_embeds", True))
    # Embedded videos that need a sign-in (RedGifs, private Vimeo…) use this browser's ("" = none)
    self._embed_cookies_browser = str(saved_settings.get("embed_cookies_browser", "") or "")
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
    self.model_manager.register_callback("visual_clip_vit", _on_model_progress)
    self.model_manager.register_callback("visual_vlm_light", _on_model_progress)

    self._disabled_tabs = [
        str(t).strip().lower()
        for t in (saved_settings.get("disabled_tabs") or [])
        if str(t).strip().lower() and str(t).strip().lower() not in ("downloader", "settings")
    ]
    self._local_library_roots = list(saved_settings.get("local_library_roots") or [])
    self._browser_last_download_dir = str(saved_settings.get("browser_last_download_dir") or "").strip()

    self._language = str(saved_settings.get("language", "auto"))
    raw_scale = saved_settings.get("ui_scale", 1.0)
    try:
        scale_f = float(raw_scale)
        if scale_f > 10.0:
            scale_f = scale_f / 100.0
        self._ui_scale = max(0.5, min(3.5, round(scale_f, 2)))
    except Exception:
        self._ui_scale = 1.0
    try:
        act = float(os.environ.get("QT_SCALE_FACTOR", "1.0"))
        if act > 10.0:
            act = act / 100.0
        self._active_ui_scale = max(0.5, min(3.5, round(act, 2)))
    except Exception:
        self._active_ui_scale = 1.0
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
    self._watchlist_manager.background_saves = True     # written off the window thread
    self._watchlist_model = WatchlistModel(self._watchlist_manager, self)
    self._archive_creators_model = ArchiveCreatorsModel(self)
    self._vault_creators_model = RecordListModel(self, key_field="creator_key")
    # Watchlist downloads: new posts that needed no files (already saved or filtered out),
    # counted as done when the download finishes
    self._watchlist_pending_updates: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    self._watchlist_result_signal_connected = False
    self._watchlist_apply_global_settings = bool(saved_settings.get("watchlist_apply_global_settings", True))
    self._watchlist_check_on_startup = bool(saved_settings.get("watchlist_check_on_startup", True))

    # Bulk Decompressor
    self._decompressor_bridge = DecompressorBridge(self._watchlist_manager, self, self)
    self._decompressor_bridge.load_settings(saved_settings.get("decompressor") or {})

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


def init_bridge_runtime_and_signals(self) -> None:
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
    self._is_favorite_artists_loading = False
    self._is_scanning = False
    self._scan_phase_text = ""
    self._scan_progress_current = 0
    self._scan_progress_total = 0
    self._scan_ui_gen = 0
    self._last_scan_ui_emit = 0.0
    self._active_scan_jobs = 0
    self._scan_jobs_lock = threading.Lock()
    self._has_pending_download_settings_changes = False
    self._pending_settings_diff_summary = ""
    self._is_applying_mid_download = False
    self._mid_download_apply_status_text = ""
    self._settings_apply_gen = 0
    self._apply_cancel_event = threading.Event()
    self._settings_dismissed_baseline = None
    self._dirty_archive_completed = 0
    self._seen_session_archive_creators: Set[Tuple[str, str]] = set()
    self._last_archive_full_emit_time = 0.0
    self._archive_posts_gen = 0
    self._settings_dirty_timer = QTimer(self)
    self._settings_dirty_timer.setSingleShot(True)
    self._settings_dirty_timer.setInterval(250)
    self._settings_dirty_timer.timeout.connect(self._evaluate_pending_download_settings)

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
    # The failed files saved for Retry Failed are read in the background; the button recounts
    # (on the window thread) once they're in
    self.recovery_manager.on_retries_loaded = lambda: self._queue_model._guiCall.emit(
        self._queue_model.failedCountChanged.emit)
    self.recovery_manager.retry_counts(wait=False)
    self._has_recovery_session = self.recovery_manager.has_unfinished_session()
    self._recovery_summary = self.recovery_manager.get_recovery_summary() if self._has_recovery_session else {}

    saved_sess = self.session_manager.get_saved_session()
    self._has_saved_session = bool(saved_sess) or self._has_recovery_session
    if self._has_recovery_session:
        logger.warning("Unfinished download session detected from previous crash. Ready for recovery.", category="session")

    # Check crash-proof SQLite WAL journal for any interrupted Archive Rebuild
    self.archive_rebuild_journal = ArchiveRebuildJournal(self.session_manager.config_dir)
    self._has_saved_archive_rebuild = self.archive_rebuild_journal.has_unfinished_session()
    self._archive_rebuild_recovery_summary = (
        self.archive_rebuild_journal.get_summary() if self._has_saved_archive_rebuild else {}
    )
    if self._has_saved_archive_rebuild:
        logger.warning(
            "Unfinished archive rebuild detected from previous session. Ready to resume from checkpoint.",
            category="archive",
        )

    # Hook downloader callbacks — they emit our private signals (thread-safe)
    def _safe_emit(sig, *args):
        try:
            sig.emit(*args)
        except (RuntimeError, ReferenceError):
            pass

    self.downloader.on_progress_update        = lambda info: _safe_emit(self._progressSignal, info)
    self.downloader.on_task_status_changed    = lambda task: _safe_emit(self._taskSignal, task)
    self.downloader.on_tasks_changed          = lambda tasks: _safe_emit(self._tasksSignal, tasks)
    self.downloader.on_cleanup_wanted         = lambda: _safe_emit(self._callOnGui, self._cleanup_after_run)
    self.downloader.on_download_finished      = lambda ok, msg: _safe_emit(self._finishedSignal, ok, msg)
    self.downloader.on_concurrency_throttled  = lambda count: _safe_emit(self._throttledSignal, count)
    self.downloader.on_pause_changed          = lambda paused: _safe_emit(self._pauseSignal, paused)

    # Connect private signals to main-thread handlers with QueuedConnection
    self._progressSignal.connect(self._handle_progress,    Qt.QueuedConnection)
    self._taskSignal.connect(self._handle_task_status,     Qt.QueuedConnection)
    self._tasksSignal.connect(self._handle_tasks_status,   Qt.QueuedConnection)
    self._callOnGui.connect(self._run_on_gui, Qt.QueuedConnection)
    self._finishedSignal.connect(self._handle_finished,    Qt.QueuedConnection)
    self._throttledSignal.connect(self._handle_throttled,  Qt.QueuedConnection)
    self._pauseSignal.connect(self._handle_pause_changed,  Qt.QueuedConnection)
    self._creatorSignal.connect(self._handle_creator_resolved, Qt.QueuedConnection)
    self._setTasksSignal.connect(self._handle_set_tasks,       Qt.QueuedConnection)
    self._appendTasksSignal.connect(self._handle_append_tasks, Qt.QueuedConnection)
    self._replaceBatchesSignal.connect(self._handle_replace_batches, Qt.QueuedConnection)
    self._watchlistResultSignal.connect(self._handle_watchlist_result, Qt.QueuedConnection)
    self._watchlistArtistResultSignal.connect(self._handle_watchlist_artist_result, Qt.QueuedConnection)
    self._scheduledCreatorSyncSignal.connect(self._handle_scheduled_creator_sync, Qt.QueuedConnection)
    for _sig_name in (
        "pageStartChanged", "pageEndChanged", "downloadDirChanged", "filterCharactersChanged",
        "characterScopeChanged", "skipWordsChanged", "skipScopeChanged", "removeWordsChanged",
        "dateAfterChanged", "dateBeforeChanged", "minFileSizeChanged", "maxFileSizeChanged",
        "videoDurationFilterEnabledChanged", "minVideoDurationChanged", "maxVideoDurationChanged",
        "filterTypeChanged", "exactExtensionsChanged", "skipArchivesChanged",
        "downloadThumbnailsOnlyChanged", "fallbackToThumbnailsChanged", "redownloadSmallFilesChanged",
        "skipPostCoversChanged", "scanContentImagesChanged", "downloadDmsChanged",
        "downloadPawchiveTemporaryFilesChanged", "compressWebpChanged", "webpQualityChanged",
        "writeAudioMetadataChanged", "keepDuplicatesChanged", "favoriteModeChanged",
        "subfolderPerPostChanged", "datePrefixChanged", "siteInFolderNameChanged",
        "fileIndexPrefixChanged", "separateFoldersByKnownChanged", "downloadRevisionsChanged",
        "adaptiveThreadingChanged", "autoRetryAtEndChanged", "skipRetry404Changed",
        "mangaModeChanged", "filenameStyleChanged", "filenameTemplateChanged",
        "proxyUrlChanged", "bandwidthLimitEnabledChanged", "bandwidthLimitValueChanged",
        "bandwidthLimitUnitChanged", "threadsCountChanged", "threadsLockedChanged",
        "downloadDelayChanged", "savePostMetadataChanged", "writeSidecarsChanged",
        "sidecarFormatChanged", "sidecarScopeChanged", "downloadEmbedsChanged",
        "embedCookiesBrowserChanged", "knownRecognitionModeChanged", "aiRecognitionEnabledChanged",
        "aiEngineModeChanged", "tagFolderModeChanged", "groupFileTypeChanged", "fileOrderChanged",
    ):
        _sig = getattr(self, _sig_name, None)
        if _sig is not None:
            _sig.connect(self._on_download_setting_mutated)
    for _sig_name in (
        "currentUrlChanged", "favoriteModeChanged", "pageStartChanged", "pageEndChanged",
        "dateAfterChanged", "dateBeforeChanged", "downloadDmsChanged", "dateAutoScanPagesChanged",
    ):
        _sig = getattr(self, _sig_name, None)
        if _sig is not None:
            _sig.connect(self.selectionCacheChanged)
    # Keep the computer awake while downloads run (Scheduler → "Sleep prevention")
    self._scheduled_sweep_retry = False
    self.isDownloadingChanged.connect(self._update_sleep_prevention)

    # Auto-check watchlist entries on startup (background, non-blocking): the artists with
    # auto-check on (if startup check is enabled)
    if self._watchlist_check_on_startup and any(e.auto_check for e in self._watchlist_manager.entries):
        threading.Thread(target=lambda: self._async_watchlist_check(automatic=True),
                         name="WatchlistAutoCheck", daemon=True).start()

    # Hook queue model retry & batch signals
    self._queue_model.retryRequested.connect(self.retryFailed)
    self._queue_model.singleRetryRequested.connect(self.retrySingleTask)
    self._queue_model.retrySelectedRequested.connect(self.retrySelectedTasks)
    self._queue_model.batchRetryRequested.connect(self._handle_batch_retry)
    self._queue_model.batchCancelRequested.connect(self._handle_batch_cancel)
    self._queue_model.batchRemoveRequested.connect(self._handle_batch_remove)
    self._queue_model.batchPauseRequested.connect(self._handle_batch_pause)
    self._queue_model.batchResumeRequested.connect(self._handle_batch_resume)
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
