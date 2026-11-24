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



class DownloadFetchMixin(AppBridgeSignalsMixin):
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

    def _async_fetch_and_start(
        self,
        parsed: URLParseResult,
        auto_start: bool,
        force_redownload: bool = False,
        *,
        from_watchlist: bool = False,
        watchlist_entry=None,
        override_download_dir: str = "",
        create_creator_folder: bool = True,
        from_batch: bool = False,
        disk_sync_mode: str = "all",
    ):
        from core.filter_options import normalize_disk_sync_mode
        norm_disk_sync = normalize_disk_sync_mode(disk_sync_mode)
        scan_gen = self._scan_ui_gen
        with self._scan_jobs_lock:
            self._active_scan_jobs += 1
        scan_label = getattr(parsed, "user_id", "") or getattr(parsed, "domain", "") or "creator"
        self._update_scan_progress(f"Preparing scan ({scan_label})...", 0, 0, force=True, gen=scan_gen, active=True)
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

            wl_entry = watchlist_entry or (
                self._watchlist_manager._find(parsed.user_id, parsed.service)
                if (from_watchlist and not parsed.is_external_provider and parsed.user_id)
                else None
            )
            options = (
                self._get_effective_watchlist_options(wl_entry)
                if (from_watchlist and wl_entry)
                else self._get_filter_options()
            )
            options = FilterOptions.from_dict(options.to_dict())
            if force_redownload:
                options.force_redownload = True
            has_override_dir = bool(str(override_download_dir or "").strip())
            effective_download_dir = (
                os.path.normpath(str(override_download_dir).strip())
                if has_override_dir
                else str(self._download_dir or "")
            )
            baseline_download_dir = effective_download_dir
            baseline_site_in_name = bool(folder_naming.include_service)

            raw_posts_for_ctx: List[Dict[str, Any]] = []
            external_files_for_ctx: List[Dict[str, Any]] = []
            ctx_fav_ids: Optional[Set[str]] = None
            ctx_fetched_dms = bool(getattr(parsed, "is_dms", False))
            ctx_fetched_comments = False
            ctx_page_start = int(getattr(options, "page_start", 1) or 1)
            ctx_page_end = int(getattr(options, "page_end", 999999) or 999999)
            ctx_date_after = str(getattr(options, "date_after", "") or "")
            ctx_date_before = str(getattr(options, "date_before", "") or "")
            ctx_artist_dir: Optional[str] = None
            ctx_base_dir = baseline_download_dir
            batch_id = ""

            # ── Handle Integrated Third-Party Providers ───────────────────────
            if parsed.is_external_provider:
                creator_name = parsed.domain
                tasks = []

                if parsed.provider == "bunkr":
                    self._update_scan_progress("Resolving Bunkr album...", 0, 0, force=True, gen=scan_gen)
                    album_title, files = _app_bridge_mod().fetch_bunkr_album(parsed.raw_url, resolve_files=True)
                    creator_name = clean_text(album_title) or "Bunkr Album"
                    folder_name = sanitize_filesystem_name(creator_name, fallback="Bunkr Album")
                    folder = (
                        os.path.join(effective_download_dir, f"Bunkr - {folder_name}")
                        if create_creator_folder
                        else effective_download_dir
                    )
                    batch_id = f"bunkr_{parsed.post_id or creator_name or 'bunkr'}"
                    external_files_for_ctx = list(files or [])
                    ctx_artist_dir = folder
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
                            batch_id=batch_id
                        )
                        t.options = options
                        tasks.append(t)

                elif parsed.provider == "erome":
                    self._update_scan_progress("Resolving Erome album...", 0, 0, force=True, gen=scan_gen)
                    album_title, files = _app_bridge_mod().fetch_erome_album(parsed.raw_url)
                    creator_name = clean_text(album_title) or "Erome Album"
                    folder_name = sanitize_filesystem_name(creator_name, fallback="Erome Album")
                    folder = (
                        os.path.join(effective_download_dir, f"Erome - {folder_name}")
                        if create_creator_folder
                        else effective_download_dir
                    )
                    batch_id = f"erome_{parsed.post_id or creator_name or 'erome'}"
                    external_files_for_ctx = list(files or [])
                    ctx_artist_dir = folder
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
                            batch_id=batch_id
                        )
                        t.options = options
                        tasks.append(t)

                elif parsed.provider == "nhentai":
                    self._update_scan_progress("Resolving nHentai gallery...", 0, 0, force=True, gen=scan_gen)
                    gallery_title, files = _app_bridge_mod().fetch_nhentai_gallery(parsed.post_id or parsed.raw_url)
                    creator_name = clean_text(gallery_title) or f"Gallery {parsed.post_id}"
                    folder_name = sanitize_filesystem_name(creator_name, fallback=f"Gallery {parsed.post_id}")
                    folder = (
                        os.path.join(effective_download_dir, f"nHentai - {folder_name}")
                        if create_creator_folder
                        else effective_download_dir
                    )
                    batch_id = f"nhentai_{parsed.post_id or creator_name or 'nhentai'}"
                    external_files_for_ctx = list(files or [])
                    ctx_artist_dir = folder
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
                            batch_id=batch_id
                        )
                        t.options = options
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
                            folder = (
                                os.path.join(effective_download_dir, f"Telegram - {folder_name}")
                                if create_creator_folder
                                else effective_download_dir
                            )
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
                            t.options = options
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

                homog_ctx = None
                if norm_disk_sync != "all":
                    from core.homogeneous_sync import resolve_homogeneous_creator_context
                    b_bridge = getattr(self, "_browser_bridge", None)
                    loc_lib = getattr(b_bridge, "_local_library", None) if b_bridge is not None else None
                    homog_ctx = resolve_homogeneous_creator_context(
                        service=parsed.service,
                        user_id=parsed.user_id,
                        creator_name=creator_name,
                        base_options=options,
                        fallback_dir=effective_download_dir or str(self._download_dir or ""),
                        disk_sync_mode=norm_disk_sync,
                        local_library=loc_lib,
                        watchlist_manager=self._watchlist_manager,
                        create_creator_folder=create_creator_folder,
                    )
                    options = homog_ctx["options"]
                    logger.info(
                        f"🔄 [Homogeneous Sync] '{creator_name}' ({norm_disk_sync}) → folder='{homog_ctx['artist_dir']}'  [{homog_ctx['summary']}]",
                        category="downloader",
                    )

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
                    use_opt_bounds = from_watchlist or (norm_disk_sync != "all")
                    scan_page_start = options.page_start if use_opt_bounds else self._page_start
                    scan_page_end = options.page_end if use_opt_bounds else self._page_end
                    scan_date_after = options.date_after if use_opt_bounds else self._date_after
                    scan_date_before = options.date_before if use_opt_bounds else self._date_before
                    scan_download_dms = (
                        bool(getattr(options, "download_dms", False))
                        if use_opt_bounds
                        else bool(getattr(options, "download_dms", False) or self._download_dms)
                    )
                    effective_page_end = scan_page_end
                    if not from_watchlist and self._date_auto_scan_pages and (scan_date_after or scan_date_before):
                        effective_page_end = 999999
                    ctx_page_start = int(scan_page_start or 1)
                    ctx_page_end = int(effective_page_end or 999999)
                    ctx_date_after = str(scan_date_after or "")
                    ctx_date_before = str(scan_date_before or "")

                    def _on_posts_scan_prog(page: int, count: int, known_total: Optional[int] = None):
                        total_pages = ((known_total + 49) // 50) if (known_total and known_total > 0) else 0
                        cur_val = min(page, total_pages) if total_pages else 0
                        txt = f"Fetching posts ({creator_name}): Page {page}" + (f"/{total_pages}" if total_pages else "") + f" ({count:,} posts)..."
                        self._update_scan_progress(txt, cur_val, total_pages, gen=scan_gen)

                    def _on_dms_scan_prog(page: int, count: int, known_total: Optional[int] = None):
                        total_pages = ((known_total + 49) // 50) if (known_total and known_total > 0) else 0
                        cur_val = min(page, total_pages) if total_pages else 0
                        txt = f"Fetching DMs ({creator_name}): Page {page}" + (f"/{total_pages}" if total_pages else "") + f" ({count:,} messages)..."
                        self._update_scan_progress(txt, cur_val, total_pages, gen=scan_gen)

                    if parsed.is_dms:
                        posts = self.api_client.fetch_user_dms(
                            parsed=parsed,
                            page_start=scan_page_start,
                            page_end=effective_page_end,
                            date_after=scan_date_after,
                            date_before=scan_date_before,
                            progress_callback=_on_dms_scan_prog,
                            cancel_event=self._scan_cancel_event
                        )
                        ctx_fetched_dms = True
                    else:
                        posts = self.api_client.fetch_user_posts(
                            parsed=parsed,
                            page_start=scan_page_start,
                            page_end=effective_page_end,
                            date_after=scan_date_after,
                            date_before=scan_date_before,
                            progress_callback=_on_posts_scan_prog,
                            cancel_event=self._scan_cancel_event
                        )
                        if scan_download_dms and ("cum.st" in (parsed.domain or "").lower() or "pawchive" in (parsed.domain or "").lower()):
                            ctx_fetched_dms = True
                            logger.info(f"Direct messages enabled: scanning DMs for {creator_name}...", category="downloader")
                            dms = self.api_client.fetch_user_dms(
                                parsed=parsed,
                                page_start=scan_page_start,
                                page_end=effective_page_end,
                                date_after=scan_date_after,
                                date_before=scan_date_before,
                                progress_callback=_on_dms_scan_prog,
                                cancel_event=self._scan_cancel_event
                            )
                            if dms:
                                posts = (posts or []) + dms

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

                if homog_ctx is not None:
                    from core.homogeneous_sync import filter_posts_for_disk_sync
                    b_bridge = getattr(self, "_browser_bridge", None)
                    loc_lib = getattr(b_bridge, "_local_library", None) if b_bridge is not None else None
                    self._update_scan_progress(
                        f"Comparing {len(posts):,} post(s) against local disk ({creator_name})...",
                        0, 0, force=True, gen=scan_gen
                    )
                    posts, sync_stats = filter_posts_for_disk_sync(
                        posts=posts,
                        disk_sync_mode=norm_disk_sync,
                        service=parsed.service,
                        user_id=parsed.user_id,
                        creator_name=creator_name,
                        domain=parsed.domain,
                        artist_dir=homog_ctx["artist_dir"],
                        options=options,
                        downloader=self.downloader,
                        local_library=loc_lib,
                    )
                    logger.info(
                        f"🔍 [Homogeneous Sync] '{creator_name}': {sync_stats['complete']} complete skipped, "
                        f"{sync_stats['missing']} not on disk, {sync_stats['mismatched']} mismatched → {len(posts)} post(s) selected.",
                        category="downloader",
                    )
                    if not posts:
                        msg_done = f"✔ {creator_name}: Already complete & matched on disk ({sync_stats['complete']} post(s) verified)"
                        logger.success(msg_done, category="downloader")
                        if b_bridge is not None and hasattr(b_bridge, "toastRequested"):
                            b_bridge.toastRequested.emit(msg_done, "info")
                        if not from_batch and not self.downloader._is_running and self._active_scan_jobs <= 1:
                            self._set_ui_state(is_downloading=False, status_text=msg_done)
                        return

                # If character filter uses comments scope, attach comments to post dictionaries
                if options.character_scope in ("comments", "all"):
                    ctx_fetched_comments = True
                    total_comment_posts = len(posts)
                    for idx_c, p in enumerate(posts, 1):
                        if self._scan_cancel_event.is_set():
                            break
                        self._update_scan_progress(
                            f"Scanning comments ({creator_name}): {idx_c:,}/{total_comment_posts:,} posts...",
                            idx_c,
                            total_comment_posts,
                            gen=scan_gen
                        )
                        pid = str(p.get("id", ""))
                        if pid:
                            comms = self.api_client.fetch_post_comments(parsed.domain, parsed.service, parsed.user_id, pid)
                            p["comments_text"] = "\n".join(c.get("content", "") for c in comms if isinstance(c, dict))

                raw_posts_for_ctx = list(posts)
                if options.favorite_mode and posts:
                    from core.auth_manager import auth_manager
                    prov_id = self.get_provider_for_domain(parsed.domain)
                    if not auth_manager.is_logged_in(prov_id):
                        meta = auth_manager.get_provider_summary(prov_id)
                        pname = meta.get("name", prov_id.capitalize())
                        logger.warning(f"⭐ Favorite Mode active but not logged into {pname}. Showing auth prompt.", category="auth")
                        self.favoriteAuthRequired.emit(pname)
                    else:
                        self._update_scan_progress(f"Filtering account favorites ({creator_name})...", 0, 0, force=True, gen=scan_gen)
                        logger.info(f"⭐ Favorite Mode active: Filtering {len(posts)} post(s) against account favorites...", category="downloader")
                        fav_posts = self.api_client.fetch_user_favorites(domain=parsed.domain, fav_type="post", cancel_event=self._scan_cancel_event)
                        fav_ids = {str(f.get("id")) for f in fav_posts if f.get("id")}
                        ctx_fav_ids = fav_ids
                        before_cnt = len(posts)
                        posts = [p for p in posts if str(p.get("id")) in fav_ids]
                        logger.info(f"⭐ Favorite Mode filter: {len(posts)} of {before_cnt} post(s) matched user favorites.", category="downloader")

                if self._scan_cancel_event.is_set():
                    self._is_downloading = bool(self.downloader._is_running)
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                # 3. Build tasks
                if homog_ctx is not None and homog_ctx.get("artist_dir"):
                    batch_id = (
                        f"post_{parsed.service}_{parsed.user_id}_{parsed.post_id}"
                        if (parsed.is_single_post and parsed.post_id)
                        else f"artist_{parsed.service}_{parsed.user_id}"
                    )
                    artist_dir = homog_ctx["artist_dir"]
                    tasks_base_dir = homog_ctx["base_dir"] or os.path.dirname(os.path.abspath(artist_dir))
                elif has_override_dir:
                    from core.filter_engine import FilterEngine
                    batch_id = (
                        f"post_{parsed.service}_{parsed.user_id}_{parsed.post_id}"
                        if (parsed.is_single_post and parsed.post_id)
                        else f"artist_{parsed.service}_{parsed.user_id}"
                    )
                    if create_creator_folder:
                        clean_c = FilterEngine.clean_filesystem_text(creator_name or parsed.user_id, max_len=80, fallback="creator")
                        if is_creator_folder(os.path.basename(effective_download_dir), clean_c, parsed.service):
                            artist_dir = effective_download_dir
                        else:
                            artist_dir = pick_creator_folder(effective_download_dir, clean_c, parsed.service)
                    else:
                        artist_dir = effective_download_dir
                    tasks_base_dir = effective_download_dir
                elif parsed.is_single_post and parsed.post_id:
                    batch_id = f"post_{parsed.service}_{parsed.user_id}_{parsed.post_id}"
                    artist_dir = None
                    tasks_base_dir = effective_download_dir
                else:
                    batch_id = f"artist_{parsed.service}_{parsed.user_id}"
                    existing_entry = wl_entry or (
                        self._watchlist_manager._find(parsed.user_id, parsed.service)
                        if (not parsed.is_external_provider and parsed.user_id)
                        else None
                    )
                    artist_dir = None
                    if from_watchlist and wl_entry:
                        artist_dir = os.path.normpath(self.resolve_artist_download_dir(wl_entry))
                        try:
                            os.makedirs(artist_dir, exist_ok=True)
                        except OSError:
                            pass
                        if not wl_entry.download_dir:
                            wl_entry.download_dir = artist_dir
                            if hasattr(wl_entry, "download_dirs") and isinstance(wl_entry.download_dirs, list):
                                if artist_dir not in wl_entry.download_dirs:
                                    wl_entry.download_dirs.insert(0, artist_dir)
                            self._watchlist_manager.save(wl_entry)
                    elif existing_entry and existing_entry.download_dir:
                        from core.filter_engine import FilterEngine
                        clean_c = FilterEngine.clean_filesystem_text(creator_name or parsed.user_id, max_len=80, fallback="creator")
                        norm_existing = os.path.normpath(existing_entry.download_dir)
                        norm_base = os.path.normpath(effective_download_dir) if effective_download_dir else ""
                        if getattr(existing_entry, "custom_folder", False):
                            artist_dir = norm_existing           # chosen by the user: never overridden by downloader path
                            try:
                                os.makedirs(artist_dir, exist_ok=True)
                            except OSError:
                                pass
                        else:
                            # Compare direct parent dir (not prefix startswith) so moving Downloader path
                            # shallower (e.g. cg2/21 -> cg2) properly creates cg2/<Author> instead of staying deep.
                            parent_mismatch = bool(norm_base) and (
                                (
                                    not self._separate_folders_by_known
                                    and self._norm_path_key(os.path.dirname(norm_existing)) != self._norm_path_key(norm_base)
                                )
                                or (
                                    self._separate_folders_by_known
                                    and not self._is_ancestor_dir(norm_base, norm_existing)
                                )
                            )
                            existing_base = os.path.basename(norm_existing)
                            not_creator_dir = not (
                                is_creator_folder(existing_base, clean_c, parsed.service)
                                or (parsed.service and existing_base.lower().startswith(f"{clean_c.lower()} ["))
                            )
                            if not os.path.exists(norm_existing) or parent_mismatch or not_creator_dir:
                                new_artist_dir = pick_creator_folder(norm_base, clean_c, parsed.service) if norm_base else norm_existing
                                try:
                                    os.makedirs(new_artist_dir, exist_ok=True)
                                except OSError:
                                    pass
                                existing_entry.download_dir = new_artist_dir
                                self._watchlist_manager.save(existing_entry)
                                artist_dir = new_artist_dir
                                logger.info(f"Download location updated to active download folder: '{new_artist_dir}'", category="downloader")
                            else:
                                artist_dir = norm_existing

                    tasks_base_dir = (
                        os.path.dirname(os.path.abspath(artist_dir))
                        if (from_watchlist and artist_dir)
                        else effective_download_dir
                    )
                ctx_base_dir = tasks_base_dir
                ctx_artist_dir = artist_dir
                tasks = self.downloader.build_tasks_from_posts(
                    posts=posts,
                    creator_name=creator_name,
                    service=parsed.service,
                    domain=parsed.domain,
                    base_dir=tasks_base_dir,
                    options=options,
                    batch_id=batch_id,
                    artist_dir=artist_dir,
                    user_id=parsed.user_id if not parsed.is_external_provider else "",
                    progress_callback=lambda cur, tot, txt: self._update_scan_progress(txt, cur, tot, gen=scan_gen),
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
                self._set_ui_state(
                    is_downloading=bool(self.downloader._is_running),
                    status_text=f"Links extraction complete ({h_count} links found). Ready to download or export.",
                )
                self._callOnGui.emit(self.harvestedLinksChanged.emit)
                return

            unimp_info = dict(getattr(self.downloader, "last_build_unimported", {}) or {})
            unimp_tasks = list(getattr(self.downloader, "last_build_unimported_tasks", []) or [])
            if not tasks:
                if getattr(self.downloader, "last_build_cancelled", False):
                    self._set_ui_state(
                        is_downloading=bool(self.downloader._is_running),
                        status_text="Progress: Cancelled",
                    )
                    return
                if int(unimp_info.get("files", 0) or 0) > 0:
                    if unimp_tasks:
                        # Surface pre-failed non-retryable entries marked as Not Imported in Queue & Retry Modal
                        # without interrupting any active or queued downloads.
                        if self.downloader._is_running or self.downloader.tasks:
                            self._appendTasksSignal.emit(unimp_tasks)
                            self.downloader.append_tasks(unimp_tasks, options=None)
                        else:
                            self.downloader.tasks = list(unimp_tasks)
                            self._setTasksSignal.emit(unimp_tasks)
                        if self._queue_model:
                            self._callOnGui.emit(lambda: self._queue_model.failedCountChanged.emit())
                    has_pending_existing = any(t.status == "pending" for t in (self.downloader.tasks or []))
                    if auto_start and has_pending_existing and not self.downloader._is_running:
                        self.downloader.start_download_queue(
                            tasks=self.downloader.tasks,
                            options=options,
                            cookie_str=self._cookie_string,
                        )
                    keep_going = bool(
                        from_batch
                        or self.downloader._is_running
                        or has_pending_existing
                        or self._active_scan_jobs > 1
                    )
                    if keep_going:
                        if not self._is_downloading and (self.downloader._is_running or from_batch):
                            self._set_ui_state(is_downloading=True)
                    else:
                        self._set_ui_state(
                            is_downloading=False,
                            status_text="Marked as Not Imported on Pawchive (full files aren't hosted on the site yet)",
                        )
                    self._emit_unimported_notice_if_needed(
                        unimp_info,
                        queued_count=0,
                        is_single_post=bool(getattr(parsed, "is_single_post", False)),
                        allow_modal=True,
                    )
                    return
                if not from_batch and not self.downloader._is_running and self._active_scan_jobs <= 1:
                    self._set_ui_state(
                        is_downloading=False,
                        status_text="Progress: Idle (All files filtered out)",
                    )
                logger.warning("No files matched filtering criteria.", category="downloader")
                return
            if int(unimp_info.get("files", 0) or 0) > 0 or int(unimp_info.get("queued_thumbnails", 0) or 0) > 0:
                self._emit_unimported_notice_if_needed(
                    unimp_info,
                    queued_count=len(tasks),
                    is_single_post=bool(getattr(parsed, "is_single_post", False)),
                    allow_modal=False,
                )

            queued_tasks = list(tasks) + unimp_tasks

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
                    canonical_url = normalize_archive_url(getattr(parsed, "raw_url", "")) or canonical_site_url(parsed.domain, parsed.service, parsed.user_id)
                    target_download_dir = ""
                    if artist_dir:
                        target_download_dir = artist_dir
                    elif tasks and not self._separate_folders_by_known:
                        target_download_dir = self.extract_artist_folder_from_path(
                            tasks[0].target_path,
                            creator_name or parsed.user_id,
                            parsed.service,
                            fallback_dir=effective_download_dir
                        )
                    else:
                        from core.filter_engine import FilterEngine
                        clean_c = FilterEngine.clean_filesystem_text(creator_name or parsed.user_id, max_len=80, fallback="creator")
                        target_download_dir = pick_creator_folder(effective_download_dir, clean_c, parsed.service)

                    track_entry = wl_entry or self._watchlist_manager._find(parsed.user_id, parsed.service)
                    keep_custom_opts = from_watchlist or bool(
                        track_entry
                        and isinstance(getattr(track_entry, "options", None), dict)
                        and track_entry.options.get("use_custom_settings")
                    )
                    self._watchlist_manager.add_entry(
                        url=canonical_url,
                        creator_name=creator_name or parsed.user_id,
                        user_id=parsed.user_id,
                        service=parsed.service,
                        domain=parsed.domain,
                        download_dir=target_download_dir,
                        options=None if keep_custom_opts else (options.to_dict() if hasattr(options, "to_dict") else {}),
                        custom_folder=True if (track_entry and getattr(track_entry, "custom_folder", False)) else None,
                    )
                    self._watchlist_model.refresh()
                    self.watchlistChanged.emit()
                except Exception as e:
                    logger.debug(f"Watchlist auto-track error: {e}", category="watchlist")


            eff_batch_id = batch_id or (self.downloader._task_batch_id(tasks[0]) if tasks else "")
            if eff_batch_id:
                self.downloader.register_batch_context(
                    BatchBuildContext(
                        batch_id=eff_batch_id,
                        parsed=parsed,
                        creator_name=creator_name,
                        service=parsed.service if not parsed.is_external_provider else parsed.provider,
                        user_id=parsed.user_id if not parsed.is_external_provider else "",
                        domain=parsed.domain,
                        base_dir=ctx_base_dir,
                        artist_dir=ctx_artist_dir,
                        from_watchlist=bool(from_watchlist),
                        custom_folder=bool(wl_entry and getattr(wl_entry, "custom_folder", False)),
                        posts=raw_posts_for_ctx,
                        external_files=external_files_for_ctx,
                        provider=parsed.provider if parsed.is_external_provider else "",
                        post_id=parsed.post_id or "",
                        fetched_dms=ctx_fetched_dms,
                        fetched_comments=ctx_fetched_comments,
                        fetched_fav_ids=ctx_fav_ids,
                        scan_page_start=ctx_page_start,
                        scan_page_end=ctx_page_end,
                        scan_date_after=ctx_date_after,
                        scan_date_before=ctx_date_before,
                        applied_options=options,
                        applied_download_dir=baseline_download_dir,
                        applied_site_in_folder_name=baseline_site_in_name,
                        force_redownload=bool(force_redownload),
                    )
                )

            _append_prog = lambda cur, tot, txt: self._update_scan_progress(txt, cur, tot, gen=scan_gen)  # noqa: E731
            if auto_start:
                if self.downloader._is_running or self.downloader.tasks:
                    # Running, or files kept in the queue: add to it (starts the queue when idle)
                    self._appendTasksSignal.emit(queued_tasks)
                    self.downloader.append_tasks(queued_tasks, options=options, cookie_str=self._cookie_string, progress_callback=_append_prog)
                    if self.downloader._is_running:
                        self._set_ui_state(
                            is_downloading=True if not self._is_downloading else None,
                            has_error=False if self._has_error else None,
                        )
                else:
                    self._setTasksSignal.emit(queued_tasks)
                    self.downloader.start_download_queue(
                        tasks=queued_tasks,
                        options=options,
                        cookie_str=self._cookie_string
                    )
                    if not self._is_downloading:
                        self._set_ui_state(is_downloading=True)
            else:
                self._appendTasksSignal.emit(queued_tasks)
                self.downloader.append_tasks(queued_tasks, options=options, cookie_str=self._cookie_string, progress_callback=_append_prog)
                self._set_ui_state(status_text=f"Queued {len(tasks)} files ({creator_name}).")

        except Exception as e:
            logger.error(f"Error during task initialization: {e}", category="downloader")
            self._set_ui_state(
                is_downloading=bool(self.downloader._is_running),
                has_error=True,
                last_error_message=str(e),
            )
        finally:
            should_hide = False
            with self._scan_jobs_lock:
                self._active_scan_jobs = max(0, self._active_scan_jobs - 1)
                should_hide = (self._active_scan_jobs == 0)
            if should_hide:
                self._update_scan_progress("", 0, 0, force=True, active=False, update_status_text=False)

    def _emit_unimported_notice_if_needed(
        self,
        unimp_info: Optional[Dict[str, Any]],
        queued_count: int = 0,
        is_single_post: bool = False,
        allow_modal: bool = True,
    ) -> bool:
        """Emits a clear UI explanation (modal when nothing could be downloaded, toast otherwise)
        whenever Pawchive posts haven't been imported onto Pawchive's storage servers yet."""
        if not isinstance(unimp_info, dict):
            return False
        unimp_files = int(unimp_info.get("files", 0) or 0)
        queued_thumbs = int(unimp_info.get("queued_thumbnails", 0) or 0)
        unimp_posts = int(unimp_info.get("posts", 0) or 0)
        if unimp_files <= 0 and queued_thumbs <= 0:
            return False
        from core.downloader import format_unimported_explanation
        all_unimported = (queued_count == 0 and unimp_files > 0)
        title, message = format_unimported_explanation(
            creator_name=str(unimp_info.get("creator_name") or ""),
            unimported_posts=max(1, unimp_posts),
            unimported_files=unimp_files,
            queued_thumbnails=queued_thumbs,
            is_single_post=bool(is_single_post),
            all_unimported=all_unimported,
        )
        show_modal = bool(allow_modal and all_unimported)
        if show_modal:
            if self._hide_unimported_notice:
                # User opted into "Do not show again": suppress modal while Progress Log keeps the warning.
                return False
            self.unimportedNotice.emit(title, message, True)
        else:
            # Keep toast concise on a single line
            toast_msg = message.split("\n\n")[0]
            self.unimportedNotice.emit(title, toast_msg, False)
        return True

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
