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



class PostSelectionQueueMixin(AppBridgeSignalsMixin):
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
        tg_parsed = KemonoURLParser.parse(parsed_url)
        cache_key, session_key = self._build_selection_keys(parsed_url, tg_parsed)
        self._selection_parsed = tg_parsed
        self._selection_creator_name = creator_name

        from core.browser_providers.base import build_media_attachment_dto

        cards = []
        for m in messages:
            mid = str(m.get("id") or m.get("message_id", ""))
            fn = m.get("filename") or f"file_{mid}"
            title = fn or m.get("title") or f"Telegram Media {mid}"
            caption = m.get("caption") or ""
            thumb = m.get("thumbnail") or ""
            fsize = int(m.get("file_size") or 0)
            url = m.get("url") or f"tg://{m.get('channel_id')}/{mid}"
            dto = build_media_attachment_dto(
                name=fn,
                url=url,
                thumbnail_url=thumb,
                local_path=thumb if thumb and os.path.isfile(str(thumb)) else "",
                file_size=fsize,
            )

            file_item = {
                "name": fn,
                "path": url,
                "url": url,
                "thumbnail": thumb,
                "previewUrl": thumb,
                "thumbnail_url": thumb,
                "ext": dto["ext"],
                "media_type": dto["media_type"],
                "is_loop": bool(dto["is_loop"]),
                "file_size": fsize,
                "size": fsize,
                "provider_id": "telegram",
                "postUrl": "",
                "postId": mid,
                "is_main": True,
                "selected": True,
            }

            cards.append({
                "id": mid,
                "title": title,
                "content": caption,
                "published": m.get("date", "")[:10] if m.get("date") else "",
                "thumbnail": thumb,
                "fileCount": 1,
                "files": [file_item],
                "selected": True,
                "provider_id": "telegram",
                "service": "telegram",
                "creator_id": str(m.get("channel_id") or ""),
                "url": "",
                "is_dm": False,
                "is_unimported": False,
                "hasVideo": dto["media_type"] == "video",
                "hasGif": bool(dto["is_loop"] or dto["ext"] == ".gif"),
            })

        self._selection_cached_cards = list(cards)
        self._selection_cache_key = cache_key
        self._selection_session_key = session_key
        self._selection_creator_unimported = False
        self.selectionCacheChanged.emit()

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

        options = FilterOptions.from_dict(self._get_filter_options().to_dict())

        sel_batch_id = f"{parsed.service}_{parsed.user_id}"
        # Build download tasks
        tasks = self.downloader.build_tasks_from_posts(
            posts=filtered_posts,
            creator_name=creator_name,
            service=parsed.service,
            domain=parsed.domain,
            base_dir=self._download_dir,
            options=options,
            batch_id=sel_batch_id,
            user_id=parsed.user_id if not parsed.is_external_provider else ""
        )

        unimp_info = dict(getattr(self.downloader, "last_build_unimported", {}) or {})
        unimp_tasks = list(getattr(self.downloader, "last_build_unimported_tasks", []) or [])
        if not tasks:
            if int(unimp_info.get("files", 0) or 0) > 0:
                if unimp_tasks:
                    # Place pre-failed non-retryable entries into the queue & Retry Modal
                    # without stopping any active or pending downloads.
                    if self._is_downloading or self.downloader.tasks:
                        self._handle_append_tasks(unimp_tasks)
                        self.downloader.append_tasks(unimp_tasks, options=None)
                    else:
                        self._queue_model.clear()
                        self._active_queue_model.clear()
                        self.downloader.reset_state()
                        self.downloader.tasks = list(unimp_tasks)
                        self._handle_set_tasks(unimp_tasks)
                    if self._queue_model:
                        self._queue_model.failedCountChanged.emit()
                has_pending_existing = any(t.status == "pending" for t in (self.downloader.tasks or []))
                if has_pending_existing and not self.downloader._is_running:
                    self.downloader.start_download_queue(
                        tasks=self.downloader.tasks,
                        options=options,
                        cookie_str=self._cookie_string,
                    )
                    if not self._is_downloading:
                        self._is_downloading = True
                        self.isDownloadingChanged.emit()
                if not self.downloader._is_running and not has_pending_existing:
                    self._status_text = "Marked as Not Imported on Pawchive (full files aren't hosted on the site yet)"
                    self.statusTextChanged.emit()
                self._emit_unimported_notice_if_needed(
                    unimp_info,
                    queued_count=0,
                    is_single_post=(len(filtered_posts) == 1),
                    allow_modal=True,
                )
            else:
                logger.warning("No downloadable files found matching active filters in selected posts.", category="downloader")
            return
        if int(unimp_info.get("files", 0) or 0) > 0 or int(unimp_info.get("queued_thumbnails", 0) or 0) > 0:
            self._emit_unimported_notice_if_needed(
                unimp_info,
                queued_count=len(tasks),
                is_single_post=(len(filtered_posts) == 1),
                allow_modal=False,
            )

        queued_tasks = list(tasks) + unimp_tasks

        self.downloader.register_batch_context(
            BatchBuildContext(
                batch_id=sel_batch_id,
                parsed=parsed,
                creator_name=creator_name,
                service=parsed.service,
                user_id=parsed.user_id if not parsed.is_external_provider else "",
                domain=parsed.domain,
                base_dir=self._download_dir,
                artist_dir=None,
                from_watchlist=False,
                posts=list(filtered_posts),
                fetched_dms=bool(getattr(parsed, "is_dms", False)),
                fetched_comments=(options.character_scope in ("comments", "all")),
                scan_page_start=1,
                scan_page_end=999999,
                applied_options=options,
                applied_download_dir=str(self._download_dir or ""),
                applied_site_in_folder_name=bool(folder_naming.include_service),
            )
        )

        if autoStart:
            if self._is_downloading:
                self._handle_append_tasks(queued_tasks)
                self.downloader.append_tasks(queued_tasks, options=options, cookie_str=self._cookie_string)
                logger.info(f"Appended {len(tasks)} tasks from {len(filtered_posts)} selected posts to active queue.", category="downloader")
            else:
                self._queue_model.clear()
                self._active_queue_model.clear()
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
                self.downloader.reset_state()
                self.downloader.tasks = list(queued_tasks)
                self._handle_set_tasks(queued_tasks)

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
                    tasks=queued_tasks,
                    options=options,
                    cookie_str=self._cookie_string
                )
        else:
            self._handle_append_tasks(queued_tasks)
            self.downloader.append_tasks(queued_tasks)
            self._status_text = f"Queued {len(tasks)} files ({creator_name})."
            self.statusTextChanged.emit()
            logger.success(f"Added {len(tasks)} tasks from {len(filtered_posts)} selected posts to queue.", category="queue")
