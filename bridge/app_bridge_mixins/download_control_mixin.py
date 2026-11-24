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



class DownloadControlMixin(AppBridgeSignalsMixin):
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
            download_dms=self._download_dms,
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
            date_folder_mode=self._date_folder_mode,
            file_order=self._file_order,
            write_sidecars=self._write_sidecars,
            sidecar_format=self._sidecar_format,
            sidecar_scope=self._sidecar_scope,
            video_duration_filter_enabled=self._video_duration_filter_enabled,
            min_video_duration=self._min_video_duration,
            max_video_duration=self._max_video_duration
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

    @Slot()
    def startDownload(self):
        """
        Starts downloading queued works, or parses URL, fetches posts, and starts download.
        If tasks are already queued and current URL is blank or already queued, directly starts the queue.
        """
        url_input = (self._current_url or "").strip()

        if self._is_downloading:
            if url_input:
                parsed_cur = KemonoURLParser.parse(url_input)
                if not parsed_cur.is_valid:
                    logger.error(f"Invalid URL: {parsed_cur.error_msg} ({url_input})", category="parser")
                    return
                if self._refuse_if_disabled(url_input):
                    return
                link_type, identity_key, parent_artist_key, display_name = self._get_link_identity(parsed_cur)
                if identity_key in self._queued_links or (parent_artist_key and parent_artist_key in self._queued_links):
                    logger.warning(f"Skipping duplicate: {display_name} is already in queue.", category="queue")
                    return
                self._queued_links.add(identity_key)
                logger.info(f"Active download running: adding '{display_name}' to end of queue with current filter settings...", category="queue")
                self._current_url = ""
                self.currentUrlChanged.emit()
                self._scan_cancel_event.clear()
                threading.Thread(
                    target=self._async_fetch_and_start,
                    args=(parsed_cur, True),
                    daemon=True
                ).start()
                return
            else:
                logger.warning("Download process is already running!", category="system")
                return

        # Ensure downloader tasks list is synced with queue model if needed
        if not self.downloader.tasks and self._queue_model.tasks:
            self.downloader.tasks = list(self._queue_model.tasks)

        has_pending = any(t.status in ("pending", "failed", "cancelled") for t in self.downloader.tasks) or (self._queue_model.pendingCount > 0)

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
                self._async_fetch_and_start(parsed, auto_start=False, from_batch=(len(raw_urls) > 1))

        threading.Thread(
            target=_batch_queue_worker,
            daemon=True
        ).start()

    @Slot("QVariantList", bool, bool, str, bool, str)
    @Slot("QVariantList", bool, bool, str, bool)
    @Slot("QVariantList", bool, bool)
    @Slot("QVariantList", bool)
    @Slot("QVariantList")
    def enqueueBatchUrls(
        self,
        urls: list,
        autoStart: bool = True,
        forceRedownload: bool = False,
        downloadDir: str = "",
        createCreatorFolder: bool = True,
        diskSyncMode: str = "all",
    ) -> None:
        """
        Enqueues a batch of creator or post URLs (e.g. from the Browser selection cart)
        directly into the normal Downloader & Queue pipeline.
        """
        raw_urls = [str(u or "").strip() for u in (urls or []) if str(u or "").strip()]
        if not raw_urls:
            return
        clean_dir = os.path.normpath(str(downloadDir or "").strip()) if str(downloadDir or "").strip() else ""
        from core.filter_options import normalize_disk_sync_mode
        norm_sync_mode = normalize_disk_sync_mode(diskSyncMode)

        self._scan_cancel_event.clear()
        if autoStart:
            self._has_error = False
            self.hasErrorChanged.emit()
            if not self._is_downloading:
                self._is_downloading = True
                self.isDownloadingChanged.emit()
            if norm_sync_mode != "all":
                self._status_text = f"Scanning {len(raw_urls)} item(s) for missing/mismatched files on disk…"
            else:
                self._status_text = f"Fetching {len(raw_urls)} marked item(s) for download…"
            self.statusTextChanged.emit()

        def _batch_worker():
            is_multi = len(raw_urls) > 1
            try:
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
                    if not forceRedownload and norm_sync_mode == "all":
                        if identity_key in self._queued_links:
                            logger.info(f"Skipping duplicate {link_type}: {display_name} is already in queue.", category="queue")
                            continue
                        if parent_artist_key and parent_artist_key in self._queued_links:
                            logger.info(f"Skipping post: entire artist ({parsed.user_id}) is already in queue.", category="queue")
                            continue

                    self._queued_links.add(identity_key)
                    self._async_fetch_and_start(
                        parsed,
                        auto_start=autoStart,
                        force_redownload=bool(forceRedownload),
                        override_download_dir=clean_dir,
                        create_creator_folder=bool(createCreatorFolder),
                        from_batch=is_multi,
                        disk_sync_mode=norm_sync_mode,
                    )
            finally:
                if autoStart and not self.downloader._is_running:
                    has_pending = any(t.status == "pending" for t in (self.downloader.tasks or []))
                    if not has_pending and self._is_downloading:
                        self._is_downloading = False
                        self.isDownloadingChanged.emit()

        threading.Thread(target=_batch_worker, daemon=True, name="BrowserBatchQueueWorker").start()

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
            user_id="82901778",
            caption="Excited artwork preview details and description"
        )

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

        # Dump any genuine retryable failed tasks to retries file (in background thread) so they are preserved
        all_tasks = self._queue_model.getTasks() if self._queue_model else list(self.downloader.tasks)
        failed_tasks = [t for t in all_tasks if t.status == "failed" and not is_task_non_retryable(t)]
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
        folder = _app_bridge_mod().QFileDialog.getExistingDirectory(
            None,
            "Select Download Directory",
            self._download_dir
        )
        if folder:
            self.downloadDir = folder
            self.saveSettings()

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
                    args=(parsed, True),
                    kwargs={"from_batch": len(urls) > 1},
                    daemon=True
                ).start()
            else:
                logger.warning(f"Skipped invalid URL in batch: {u}", category="batch")
        return len(urls)
