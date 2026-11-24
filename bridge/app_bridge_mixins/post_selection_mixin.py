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



class PostSelectionMixin(AppBridgeSignalsMixin):
    def _build_selection_keys(self, url_input: str, parsed: Optional[URLParseResult]) -> Tuple[str, str]:
        """Return (fetch_cache_key, session_identity_key) for the post selection modal.

        `session_identity_key` stays stable across re-fetches and page tweaks so user checkmarks
        survive; `fetch_cache_key` also includes page/date/DM bounds so changing scan scope
        triggers a fresh fetch instead of serving stale truncated results.
        """
        raw = str(getattr(parsed, "raw_url", "") or url_input or "").strip().rstrip("/").lower()
        session_key = "|".join([
            "1" if getattr(self, "_favorite_mode", False) else "0",
            str(getattr(parsed, "domain", "") or "").lower(),
            str(getattr(parsed, "provider", "") or "").lower(),
            str(getattr(parsed, "service", "") or "").lower(),
            str(getattr(parsed, "user_id", "") or ""),
            str(getattr(parsed, "post_id", "") or ""),
            "1" if getattr(parsed, "is_dms", False) else "0",
            raw,
        ])
        effective_page_end = (
            999999
            if (getattr(self, "_date_auto_scan_pages", False) and (getattr(self, "_date_after", "") or getattr(self, "_date_before", "")))
            else getattr(self, "_page_end", 999999)
        )
        cache_key = "|".join([
            session_key,
            str(getattr(self, "_page_start", 1)),
            str(effective_page_end),
            str(getattr(self, "_date_after", "") or ""),
            str(getattr(self, "_date_before", "") or ""),
            "1" if getattr(self, "_download_dms", False) else "0",
        ])
        return cache_key, session_key

    @Property(bool, notify=AppBridgeSignalsMixin.selectionCacheChanged)
    def hasCachedSelectionForCurrentUrl(self) -> bool:
        """True when already-fetched posts match the active URL and scan bounds."""
        url_input = (self._current_url or "").strip()
        if not url_input or not self._selection_cache_key or not self._selection_cached_cards:
            return False
        parsed = KemonoURLParser.parse(url_input)
        if not parsed.is_valid:
            return False
        cache_key, _ = self._build_selection_keys(url_input, parsed)
        return cache_key == self._selection_cache_key

    @Property(bool, notify=AppBridgeSignalsMixin.selectionCacheChanged)
    def selectionCreatorUnimported(self) -> bool:
        """True when the creator loaded into PostSelectionModal is flagged unimported on Pawchive."""
        return bool(getattr(self, "_selection_creator_unimported", False))

    @Slot(result=str)
    def getSelectionSessionKey(self) -> str:
        """Return the creator/source key used by PostSelectionModal to preserve selections."""
        return self._selection_session_key or self._selection_cache_key or ""

    def _resolve_selection_creator_unimported(
        self,
        profile: Optional[Dict[str, Any]],
        parsed: Optional[URLParseResult],
    ) -> bool:
        """Determines creator-level unimported status from profile payload or local catalog cache."""
        if isinstance(profile, dict):
            if "ever_imported" in profile and profile.get("ever_imported") is not None:
                return profile.get("ever_imported") is False
            if profile.get("is_unimported") is not None:
                return bool(profile.get("is_unimported"))
        if parsed and not parsed.is_external_provider and parsed.service and parsed.user_id:
            prov_id = self.get_provider_for_domain(parsed.domain or "")
            if prov_id:
                try:
                    from core.browser_providers import browser_registry
                    prov = browser_registry.get_provider(prov_id)
                    if prov and hasattr(prov, "is_creator_unimported_cached"):
                        return bool(prov.is_creator_unimported_cached(parsed.service, parsed.user_id))
                except Exception:
                    pass
        return False

    def _build_selection_file_item(
        self,
        fobj: Dict[str, Any],
        raw_post: Dict[str, Any],
        domain: str,
        prov_id: str,
        post_url: str,
        post_id: str,
        is_main: bool,
    ) -> Optional[Dict[str, Any]]:
        """Formats a post file or attachment dict for PostSelectionModal + MediaLightboxModal."""
        if not isinstance(fobj, dict):
            return None
        from core.browser_providers.base import build_media_attachment_dto, resolve_kemono_media_urls
        from core.browser_providers.cumst_provider import resolve_cumst_media_dto

        domain_lower = (domain or "").strip().lower()
        dto = None
        if "cum.st" in domain_lower or "cumst" in domain_lower or (bool(fobj.get("storageKey")) and not fobj.get("path")):
            dto = resolve_cumst_media_dto(fobj)
        elif prov_id in ("pawchive", "kemono", "coomer") or not str(fobj.get("path") or fobj.get("url") or "").startswith(("http://", "https://")):
            resolved = resolve_kemono_media_urls(fobj, base_domain=domain or "pawchive.pw", post_raw=raw_post)
            if resolved:
                fname, full_url, thumb_url = resolved
                dto = build_media_attachment_dto(
                    name=fname,
                    url=full_url,
                    thumbnail_url=thumb_url,
                    file_size=int(fobj.get("size") or fobj.get("file_size") or 0),
                )
        else:
            raw_url = str(fobj.get("temp_download_url") or fobj.get("temp_url") or fobj.get("url") or fobj.get("path") or "").strip()
            if raw_url:
                fname = str(fobj.get("name") or fobj.get("filename") or os.path.basename(raw_url.split("?")[0]) or "file")
                thumb_url = str(fobj.get("thumbnailUrl") or fobj.get("thumbnail") or fobj.get("previewUrl") or "").strip()
                dto = build_media_attachment_dto(
                    name=fname,
                    url=raw_url,
                    thumbnail_url=thumb_url,
                    file_size=int(fobj.get("size") or fobj.get("file_size") or 0),
                )

        if not dto:
            return None

        selection_path = str(fobj.get("path") or fobj.get("storageKey") or fobj.get("url") or dto["url"] or "")
        thumb = dto.get("thumbnail_url") or ""
        return {
            "name": dto["name"],
            "path": selection_path,
            "url": dto["url"],
            "thumbnail": thumb,
            "previewUrl": thumb,
            "thumbnail_url": thumb,
            "ext": dto["ext"],
            "media_type": dto["media_type"],
            "is_loop": bool(dto["is_loop"]),
            "file_size": int(dto.get("file_size") or 0),
            "provider_id": prov_id,
            "postUrl": post_url,
            "postId": str(post_id or ""),
            "is_main": bool(is_main),
            "selected": True,
        }

    def _build_selection_post_card(
        self,
        raw_post: Dict[str, Any],
        parsed: Optional[URLParseResult],
        default_domain: str = "pawchive.pw",
        creator_is_unimported: bool = False,
        title_prefix: str = "",
    ) -> Dict[str, Any]:
        """Normalizes a raw API post dict into a PostSelectionModal card with full media + unimported metadata."""
        import html as _html

        pid = str(raw_post.get("id") or "")
        domain = (
            raw_post.get("domain")
            or (getattr(parsed, "domain", "") if parsed else "")
            or default_domain
            or "pawchive.pw"
        )
        svc = str(raw_post.get("service") or (getattr(parsed, "service", "") if parsed else "") or "").strip().lower()
        cid = str(
            raw_post.get("user")
            or raw_post.get("creatorId")
            or raw_post.get("creator_id")
            or (getattr(parsed, "user_id", "") if parsed else "")
            or ""
        ).strip()
        is_dm = bool(raw_post.get("is_dm") or raw_post.get("is_dms") or (getattr(parsed, "is_dms", False) if parsed else False))
        is_ext = bool(getattr(parsed, "is_external_provider", False)) if parsed else False
        prov_id = "" if is_ext else self.get_provider_for_domain(domain)

        if not is_ext and domain and svc and cid and pid:
            post_url = canonical_site_url(domain, svc, cid, "dm" if is_dm else "post", pid)
        else:
            from core.parser import normalize_archive_url
            post_url = normalize_archive_url(
                str(raw_post.get("url") or ""),
                fallback_service=svc,
                fallback_user_id=cid,
                fallback_post_id=pid,
            )

        if "has_full" in raw_post:
            post_is_unimported = raw_post.get("has_full") is False
        elif raw_post.get("is_unimported") is not None:
            post_is_unimported = bool(raw_post.get("is_unimported"))
        else:
            post_is_unimported = bool(creator_is_unimported and not is_ext)

        title, _ = FilterEngine.extract_post_title_and_caption(raw_post, fallback_title="Untitled Post")
        if title_prefix:
            title = f"{title_prefix}{title}"
        published = str(raw_post.get("published") or raw_post.get("added") or "")[:10]

        post_files: List[Dict[str, Any]] = []
        seen_selection_keys: Set[str] = set()

        def _append_fobj(fobj: Dict[str, Any], is_main: bool) -> None:
            if not isinstance(fobj, dict):
                return
            if not (fobj.get("path") or fobj.get("storageKey") or fobj.get("url") or fobj.get("temp_download_url") or fobj.get("temp_url")):
                return
            sel_key = KemonoDownloader.extract_norm_rel_key(fobj) or str(fobj.get("path") or fobj.get("url") or fobj.get("storageKey") or "").lower()
            if sel_key and sel_key in seen_selection_keys:
                if not is_main and post_files and post_files[0].get("is_main"):
                    att_name = str(fobj.get("name") or os.path.basename(str(fobj.get("path") or "")) or "")
                    if att_name and not att_name.lower().startswith(("cover", "preview")):
                        post_files[0]["name"] = att_name
                return
            if sel_key:
                seen_selection_keys.add(sel_key)
            item = self._build_selection_file_item(
                fobj,
                raw_post=raw_post,
                domain=domain,
                prov_id=prov_id,
                post_url=post_url,
                post_id=pid,
                is_main=is_main,
            )
            if item:
                post_files.append(item)

        _append_fobj(raw_post.get("file"), is_main=True)
        for att in raw_post.get("attachments", []) or []:
            _append_fobj(att, is_main=False)

        thumb_url = str(raw_post.get("thumbnail") or "").strip()
        if not thumb_url:
            for pf in post_files:
                if pf.get("thumbnail"):
                    thumb_url = str(pf["thumbnail"])
                    break

        raw_content = raw_post.get("content") or raw_post.get("captionHtml") or raw_post.get("caption") or ""
        clean_content = re.sub(r"<br\s*/?>", "\n", str(raw_content), flags=re.IGNORECASE)
        clean_content = _html.unescape(re.sub(r"<[^>]+>", "", clean_content).strip())

        has_video = any(pf.get("media_type") == "video" for pf in post_files)
        has_gif = any(pf.get("is_loop") or pf.get("ext") == ".gif" for pf in post_files)

        return {
            "id": pid,
            "title": title,
            "content": clean_content,
            "published": published,
            "thumbnail": thumb_url,
            "fileCount": len(post_files),
            "files": [dict(pf, postedIndex=i) for i, pf in enumerate(post_files)],
            "selected": True,
            "provider_id": prov_id,
            "service": svc,
            "creator_id": cid,
            "url": post_url,
            "is_dm": is_dm,
            "is_unimported": post_is_unimported,
            "hasVideo": has_video,
            "hasGif": has_gif,
        }

    @Slot()
    def fetchPostsForSelection(self):
        """
        Fetches creator profile and posts in a background worker for PostSelectionModal,
        reusing cached posts when the same URL and scan bounds were already fetched.
        """
        self._fetch_posts_for_selection_impl(force_refresh=False)

    @Slot()
    def refetchPostsForSelection(self):
        """Force a fresh network fetch of posts for PostSelectionModal, bypassing the session cache."""
        self._fetch_posts_for_selection_impl(force_refresh=True)

    def _fetch_posts_for_selection_impl(self, force_refresh: bool = False):
        if self._is_post_selection_loading:
            return

        url_input = (self._current_url or "").strip()
        if not url_input:
            if self._favorite_mode:
                if not self.checkFavoriteModeAuth():
                    self.postSelectionError.emit("Favorite Mode requires a Pawchive login in Settings → Accounts.")
                    return
                self.fetchFavoriteArtists()
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

        cache_key, session_key = self._build_selection_keys(url_input, parsed)
        if (
            not force_refresh
            and cache_key
            and cache_key == self._selection_cache_key
            and self._selection_cached_posts
            and self._selection_cached_cards
        ):
            self._selection_parsed = parsed
            cached_cards = list(self._selection_cached_cards)
            self.postSelectionReady.emit(cached_cards, self._selection_creator_name, len(cached_cards))
            return

        self._scan_cancel_event.clear()
        self._is_post_selection_loading = True
        self.postSelectionLoadingChanged.emit()
        self._emit_post_selection_progress(0, 0, 0, "Looking up creator profile…")

        def _worker():
            try:
                creator_name = ""
                posts = []
                profile = {}

                if parsed.is_external_provider:
                    creator_name = parsed.domain
                    if parsed.provider == "bunkr":
                        self._emit_post_selection_progress(1, 0, 0, "Resolving Bunkr album files…")
                        album_title, files = _app_bridge_mod().fetch_bunkr_album(parsed.raw_url, resolve_files=True)
                        creator_name = clean_text(album_title) or "Bunkr Album"
                        self._emit_post_selection_progress(1, len(files), len(files), f"Found {len(files)} files in album")
                        posts = [{"id": f["url"], "title": f.get("filename", "File"), "published": "", "file": {"path": f["url"], "name": f.get("filename", "")}, "attachments": []} for f in files]
                    elif parsed.provider == "erome":
                        self._emit_post_selection_progress(1, 0, 0, "Resolving Erome album media…")
                        album_title, files = _app_bridge_mod().fetch_erome_album(parsed.raw_url)
                        creator_name = clean_text(album_title) or "Erome Album"
                        self._emit_post_selection_progress(1, len(files), len(files), f"Found {len(files)} files in album")
                        posts = [{"id": f["url"], "title": f.get("filename", "File"), "published": "", "file": {"path": f["url"], "name": f.get("filename", "")}, "attachments": []} for f in files]
                    elif parsed.provider == "nhentai":
                        self._emit_post_selection_progress(1, 0, 0, "Resolving gallery pages…")
                        gallery_title, files = _app_bridge_mod().fetch_nhentai_gallery(parsed.post_id or parsed.raw_url)
                        creator_name = clean_text(gallery_title) or f"Gallery {parsed.post_id}"
                        self._emit_post_selection_progress(1, len(files), len(files), f"Found {len(files)} pages in gallery")
                        posts = [{"id": f["url"], "title": f.get("filename", "File"), "published": "", "file": {"path": f["url"], "name": f.get("filename", "")}, "attachments": []} for f in files]
                    elif parsed.provider == "telegram":
                        self._telegram_pending_action = "select"
                        if not TelegramService.instance().is_logged_in():
                            self._is_post_selection_loading = False
                            self.postSelectionLoadingChanged.emit()
                            self.telegramAuthRequested.emit(bool(parsed.extra_data.get("is_private", False)))
                            return

                        if parsed.is_single_post:
                            self._emit_post_selection_progress(1, 0, 1, "Loading Telegram message…")
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
                    self._emit_post_selection_progress(0, 0, 0, f"Connecting to {parsed.domain or 'server'}…")
                    profile = self.api_client.fetch_creator_profile(parsed)
                    creator_name = clean_text(profile.get("name", parsed.user_id) or parsed.user_id)
                    if parsed.is_single_post:
                        self._emit_post_selection_progress(1, 0, 1, "Fetching single post…")
                        single = self.api_client.fetch_single_post(parsed)
                        posts = [single] if single else []
                        if posts:
                            self._emit_post_selection_progress(1, 1, 1, "Post loaded")
                    else:
                        effective_page_end = self._page_end
                        if self._date_auto_scan_pages and (self._date_after or self._date_before):
                            effective_page_end = 999999

                        known_total_holder = [0]

                        def _on_posts_progress(page: int, count: int, total: Optional[int] = None):
                            if total is not None:
                                try:
                                    t_val = int(total)
                                    if t_val > 0:
                                        known_total_holder[0] = t_val
                                except (ValueError, TypeError):
                                    pass
                            tot = known_total_holder[0]
                            if tot > 0:
                                pct = int((count / tot) * 100) if tot else 0
                                msg = f"Page {page} • {count} / {tot} posts ({pct}%)"
                            elif count > 0:
                                msg = f"Page {page} • {count} posts discovered so far"
                            else:
                                msg = f"Fetching page {page}…"
                            self._emit_post_selection_progress(page, count, tot, msg)

                        if parsed.is_dms:
                            posts = self.api_client.fetch_user_dms(
                                parsed=parsed,
                                page_start=self._page_start,
                                page_end=effective_page_end,
                                date_after=self._date_after,
                                date_before=self._date_before,
                                progress_callback=_on_posts_progress,
                                cancel_event=self._scan_cancel_event
                            )
                        else:
                            posts = self.api_client.fetch_user_posts(
                                parsed=parsed,
                                page_start=self._page_start,
                                page_end=effective_page_end,
                                date_after=self._date_after,
                                date_before=self._date_before,
                                progress_callback=_on_posts_progress,
                                cancel_event=self._scan_cancel_event
                            )
                            if self._download_dms and ("cum.st" in (parsed.domain or "").lower() or "pawchive" in (parsed.domain or "").lower()):
                                dms = self.api_client.fetch_user_dms(
                                    parsed=parsed,
                                    page_start=self._page_start,
                                    page_end=effective_page_end,
                                    date_after=self._date_after,
                                    date_before=self._date_before,
                                    progress_callback=_on_posts_progress,
                                    cancel_event=self._scan_cancel_event
                                )
                                if dms:
                                    posts = (posts or []) + dms

                if self._scan_cancel_event.is_set():
                    self._is_post_selection_loading = False
                    self.postSelectionLoadingChanged.emit()
                    return

                if not posts:
                    self._is_post_selection_loading = False
                    self._emit_post_selection_progress(0, 0, 0, f"No posts found for {creator_name or 'URL'}.")
                    self.postSelectionLoadingChanged.emit()
                    self.postSelectionError.emit(f"No posts found for {creator_name or 'URL'}.")
                    return

                total_posts_found = len(posts)
                self._emit_post_selection_progress(
                    0,
                    total_posts_found,
                    total_posts_found,
                    f"Formatting {total_posts_found} posts for preview…"
                )

                # Build cards list for UI
                cards = []
                domain = parsed.domain or "pawchive.pw"
                creator_is_unimported = self._resolve_selection_creator_unimported(profile, parsed)
                for idx, p in enumerate(posts, 1):
                    if self._scan_cancel_event.is_set():
                        break
                    if idx % 100 == 0 or idx == total_posts_found:
                        self._emit_post_selection_progress(
                            0,
                            idx,
                            total_posts_found,
                            f"Preparing previews ({idx}/{total_posts_found})…"
                        )
                    cards.append(
                        self._build_selection_post_card(
                            p,
                            parsed=parsed,
                            default_domain=domain,
                            creator_is_unimported=creator_is_unimported,
                        )
                    )

                if self._scan_cancel_event.is_set():
                    self._is_post_selection_loading = False
                    self.postSelectionLoadingChanged.emit()
                    return

                self._selection_cached_posts = list(posts)
                self._selection_cached_cards = list(cards)
                self._selection_cache_key = cache_key
                self._selection_session_key = session_key
                self._selection_parsed = parsed
                self._selection_creator_name = creator_name
                self._selection_creator_unimported = bool(creator_is_unimported)
                self.selectionCacheChanged.emit()

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

    @Slot()
    def cancelPostSelection(self):
        """Cancels an active creator post selection fetch."""
        self._scan_cancel_event.set()
        self._is_post_selection_loading = False
        self._emit_post_selection_progress(0, 0, 0, "Cancelled")
        self.postSelectionLoadingChanged.emit()

    def _start_favorites_post_selection_worker(self):
        """Fetches account favorites for display in the interactive post selector modal."""
        self._scan_cancel_event.clear()
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

                if self._scan_cancel_event.is_set():
                    self._is_post_selection_loading = False
                    self.postSelectionLoadingChanged.emit()
                    return

                if not posts:
                    self._is_post_selection_loading = False
                    self.postSelectionLoadingChanged.emit()
                    self.postSelectionError.emit("No favorited posts found on your account.")
                    return

                # Build cards list for UI
                fav_parsed = KemonoURLParser.parse(f"https://{domain}/favorites")
                cards = []
                for p in posts:
                    p_user = p.get("username") or p.get("user") or ""
                    cards.append(
                        self._build_selection_post_card(
                            p,
                            parsed=fav_parsed,
                            default_domain=domain,
                            creator_is_unimported=False,
                            title_prefix=f"[{p_user}] " if p_user else "",
                        )
                    )

                if self._scan_cancel_event.is_set():
                    self._is_post_selection_loading = False
                    self.postSelectionLoadingChanged.emit()
                    return

                fav_key = f"favorites_posts|{domain}"
                self._selection_cached_posts = list(posts)
                self._selection_cached_cards = list(cards)
                self._selection_cache_key = fav_key
                self._selection_session_key = fav_key
                self._selection_parsed = fav_parsed
                self._selection_creator_name = creator_name
                self._selection_creator_unimported = False
                self.selectionCacheChanged.emit()

                self._is_post_selection_loading = False
                self.postSelectionLoadingChanged.emit()
                self.postSelectionReady.emit(cards, creator_name, len(cards))
            except Exception as ex:
                logger.error(f"Error fetching favorites for selection: {ex}", category="api")
                self._is_post_selection_loading = False
                self.postSelectionLoadingChanged.emit()
                self.postSelectionError.emit(str(ex))

        threading.Thread(target=_worker, daemon=True, name="FavSelectionWorker").start()
