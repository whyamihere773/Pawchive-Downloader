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



class FavoritesMixin(AppBridgeSignalsMixin):
    @Slot()
    def fetchFavoriteArtists(self):
        """Fetches favorited creators from connected providers (Pawchive, cum.st) and synchronizes them with Watchlist."""
        if getattr(self, "_is_favorite_artists_loading", False):
            return
        if not self.checkFavoriteModeAuth():
            return
        self._is_favorite_artists_loading = True
        self.favoriteArtistsLoadingChanged.emit()

        def _worker():
            try:
                from core.auth_manager import auth_manager
                providers_to_sync = []
                if auth_manager.is_logged_in("pawchive"):
                    providers_to_sync.append(("pawchive.pw", "pawchive"))
                if auth_manager.is_logged_in("cumst"):
                    providers_to_sync.append(("cum.st", "cumst"))

                if not providers_to_sync:
                    self._is_favorite_artists_loading = False
                    self.favoriteArtistsLoadingChanged.emit()
                    self.favoriteArtistsReady.emit([])
                    return

                all_raw_artists = []
                for p_domain, p_id in providers_to_sync:
                    if self._scan_cancel_event.is_set():
                        break
                    raw = self.api_client.fetch_user_favorites(
                        domain=p_domain,
                        fav_type="artist",
                        cancel_event=self._scan_cancel_event
                    )
                    if raw:
                        for item in raw:
                            if not item.get("domain"):
                                item["domain"] = p_domain
                        all_raw_artists.extend(raw)

                if not all_raw_artists:
                    self._is_favorite_artists_loading = False
                    self.favoriteArtistsLoadingChanged.emit()
                    self.favoriteArtistsReady.emit([])
                    return

                artist_cards = []
                cards_dict = {}
                entries_with_last_post = []
                for a in all_raw_artists:
                    uid = str(a.get("id") or "").strip()
                    svc = str(a.get("service") or "").strip()
                    name = a.get("name") or uid
                    avatar = a.get("avatar") or ""
                    dom = a.get("domain") or "pawchive.pw"
                    is_c = "cum.st" in dom or "cumst" in dom
                    url = f"https://cum.st/creators/{svc}/{uid}" if is_c else f"https://{dom}/{svc}/user/{uid}"
                    entry = self._watchlist_manager.add_or_update_favorite_creator(
                        user_id=uid,
                        service=svc,
                        creator_name=name,
                        domain=dom,
                        url=url,
                        is_favorite=True
                    )
                    status_text = "Synced" if (entry and entry.last_post_date) else "Not downloaded"
                    new_count = int(getattr(entry, "new_post_count", 0) or 0)
                    card = {
                        "id": uid,
                        "userId": uid,
                        "service": svc,
                        "name": name,
                        "avatar": avatar,
                        "url": url,
                        "domain": dom,
                        "provider": "cumst" if is_c else ("pawchive" if "pawchive" in dom else ("kemono" if "kemono" in dom else ("coomer" if "coomer" in dom else "pawchive"))),
                        "lastPostDate": entry.last_post_date if entry else "",
                        "status": status_text,
                        "newPostCount": new_count,
                        "isFavorite": True
                    }
                    if (uid, svc) not in cards_dict:
                        artist_cards.append(card)
                        cards_dict[(uid, svc)] = card
                    if entry and entry.last_post_date:
                        entries_with_last_post.append(entry)

                self._watchlist_model.refresh()
                self._watchlist_model.countChanged.emit()
                self.watchlistChanged.emit()

                self._is_favorite_artists_loading = False
                self.favoriteArtistsLoadingChanged.emit()
                self.favoriteArtistsReady.emit(artist_cards)

                # Concurrently check for new posts since last download for downloaded artists
                if entries_with_last_post and not self._scan_cancel_event.is_set():
                    def _check_one_entry(ent):
                        if self._scan_cancel_event.is_set():
                            return
                        try:
                            new_posts = self._watchlist_manager.get_posts_since(
                                ent,
                                self.api_client,
                                page_start=1,
                                page_end=2
                            )
                            ent.new_post_count = len(new_posts)
                            ent.cached_new_posts = new_posts
                            c = cards_dict.get((ent.user_id, ent.service))
                            if c:
                                c["newPostCount"] = len(new_posts)
                        except Exception:
                            pass

                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                        list(executor.map(_check_one_entry, entries_with_last_post))

                    self._watchlist_model.update_new_counts()
                    self._watchlist_model.refresh()
                    self.watchlistChanged.emit()
                    self.favoriteArtistsReady.emit(list(cards_dict.values()))
            except Exception as ex:
                logger.error(f"Error fetching favorite artists: {ex}", category="api")
                self._is_favorite_artists_loading = False
                self.favoriteArtistsLoadingChanged.emit()
                self.favoriteArtistsError.emit(str(ex))

        threading.Thread(target=_worker, daemon=True, name="FavoriteArtistsWorker").start()

    @Slot(str, str, str, str)
    @Slot(str, str, str)
    def fetchArtistPostsForSelection(self, user_id: str, service: str, creator_name: str = "", artist_url: str = ""):
        """Fetches posts for a specific favorite artist to display in PostSelectionModal."""
        if not user_id or not service:
            return
        if artist_url:
            self.currentUrl = artist_url
        else:
            entry = self._watchlist_manager._find(user_id, service)
            if entry and entry.url:
                artist_url = entry.url
            elif entry and entry.domain and ("cum.st" in entry.domain or "cumst" in entry.domain):
                artist_url = f"https://cum.st/creators/{service}/{user_id}"
            else:
                domain = entry.domain if (entry and entry.domain) else "pawchive.pw"
                if "cum.st" in domain or "cumst" in domain:
                    artist_url = f"https://cum.st/creators/{service}/{user_id}"
                else:
                    artist_url = f"https://{domain}/{service}/user/{user_id}"
            self.currentUrl = artist_url
        self.fetchPostsForSelection()

    @Slot(str, str, result=str)
    def getArtistDownloadDir(self, user_id: str, service: str) -> str:
        """Returns the configured or default download directory for an artist."""
        entry = self._watchlist_manager._find(user_id, service)
        if entry and entry.download_dir:
            return entry.download_dir
        if entry:
            return self.resolve_artist_download_dir(entry)
        return self._download_dir

    @Slot(str, str, int, int, str)
    @Slot(str, str, int, int)
    @Slot(str, str)
    def downloadFavoriteArtist(
        self,
        user_id: str,
        service: str,
        page_start: int = 1,
        page_end: int = 999999,
        download_dir: str = ""
    ):
        """Incrementally downloads updates or full backlog for an individual favorited artist."""
        if not user_id or not service:
            return
        if not self.checkFavoriteModeAuth():
            return
        entry = self._watchlist_manager._find(user_id, service)
        if not entry:
            entry = self._watchlist_manager.add_or_update_favorite_creator(
                user_id=user_id,
                service=service,
                creator_name=user_id,
                is_favorite=True
            )
        if download_dir:
            resolved_fav = self.resolve_explicit_watch_folder(
                entry,
                download_dir,
                creator_name=entry.creator_name or user_id,
                service=service,
                allow_empty_leaf=False,
            )
            try:
                os.makedirs(resolved_fav, exist_ok=True)
            except OSError:
                pass
            entry.download_dir = resolved_fav
            entry.custom_folder = True
            if hasattr(entry, "download_dirs") and isinstance(entry.download_dirs, list):
                if resolved_fav not in entry.download_dirs:
                    entry.download_dirs.insert(0, resolved_fav)
            self._watchlist_manager.save(entry)
            download_dir = resolved_fav

        def _run():
            try:
                self._process_watchlist_entry_download(
                    entry,
                    page_start=page_start,
                    page_end=page_end,
                    custom_dir=download_dir
                )
            except Exception as e:
                logger.error(f"Error downloading favorite artist {user_id}: {e}", category="downloader")
        threading.Thread(target=_run, daemon=True, name="FavoriteArtistSingleWorker").start()

    @Slot(int, int, str)
    @Slot(int, int)
    @Slot()
    def downloadAllFavoriteArtists(
        self,
        page_start: int = 1,
        page_end: int = 999999,
        download_dir: str = ""
    ):
        """Incrementally syncs all favorited artists."""
        if not self.checkFavoriteModeAuth():
            return
        self._start_favorites_download_worker(
            page_start=page_start,
            page_end=page_end,
            download_dir=download_dir
        )

    @Slot()
    def syncPawchiveFavorites(self):
        """Shortcut to fetch and sync Pawchive favorites."""
        self.fetchFavoriteArtists()

    def _on_scan_progress(self, page: int, count: int):
        """Callback from api_client during favorites scanning."""
        self._status_text = f"Fetching favorites: Page {page} ({count} posts)..."
        self.statusTextChanged.emit()

    def _start_favorites_download_worker(self, page_start: int = 1, page_end: int = 999999, download_dir: str = ""):
        """Worker thread to incrementally sync all favorited artists from connected providers."""
        self._scan_cancel_event.clear()
        self._has_error = False
        self.hasErrorChanged.emit()
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self.isPausedChanged.emit()
        self._status_text = "Fetching favorited artists..."
        self.statusTextChanged.emit()

        def _worker():
            try:
                from core.auth_manager import auth_manager
                providers_to_sync = []
                if auth_manager.is_logged_in("pawchive"):
                    providers_to_sync.append(("pawchive.pw", "pawchive"))
                if auth_manager.is_logged_in("cumst"):
                    providers_to_sync.append(("cum.st", "cumst"))

                self._creator_name = "Favorite Artists"
                self.creatorNameChanged.emit()

                fav_artists = []
                for p_domain, p_id in providers_to_sync:
                    if self._scan_cancel_event.is_set():
                        break
                    p_res = self.api_client.fetch_user_favorites(
                        domain=p_domain,
                        fav_type="artist",
                        cancel_event=self._scan_cancel_event,
                    )
                    if p_res:
                        for item in p_res:
                            if not item.get("domain"):
                                item["domain"] = p_domain
                        fav_artists.extend(p_res)

                if self._scan_cancel_event.is_set():
                    self._is_downloading = False
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                if not fav_artists:
                    self._is_downloading = False
                    self._status_text = "Progress: Idle (0 favorite artists found)"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    logger.warning("No favorited artists found on connected accounts.", category="api")
                    return

                logger.info(f"⭐ Favorite Mode: Found {len(fav_artists)} favorited creator(s). Starting incremental sync...", category="downloader")
                entries_to_process = []
                for a in fav_artists:
                    uid = str(a.get("id") or "").strip()
                    svc = str(a.get("service") or "").strip()
                    name = a.get("name") or uid
                    dom = a.get("domain") or "pawchive.pw"
                    is_c = "cum.st" in dom or "cumst" in dom
                    url = f"https://cum.st/creators/{svc}/{uid}" if is_c else f"https://{dom}/{svc}/user/{uid}"
                    entry = self._watchlist_manager.add_or_update_favorite_creator(
                        user_id=uid,
                        service=svc,
                        creator_name=name,
                        domain=dom,
                        url=url,
                        is_favorite=True
                    )
                    entries_to_process.append(entry)

                self._watchlist_model.refresh()
                self._watchlist_model.countChanged.emit()
                self.watchlistChanged.emit()

                total_entries = len(entries_to_process)
                for idx, entry in enumerate(entries_to_process, 1):
                    if self._scan_cancel_event.is_set():
                        break
                    self._status_text = f"Syncing favorites ({idx}/{total_entries}): {entry.creator_name}..."
                    self.statusTextChanged.emit()
                    try:
                        self._process_watchlist_entry_download(
                            entry,
                            page_start=page_start,
                            page_end=page_end,
                            custom_dir=download_dir
                        )
                    except Exception as err:
                        logger.error(f"Error syncing favorite artist {entry.creator_name!r}: {err}", category="downloader")

                if not self.downloader.tasks and not self._queue_model.rowCount():
                    self._is_downloading = False
                    self._status_text = "Favorites: All artists are up to date"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                else:
                    self._status_text = "Queued updates for favorite artists. Downloading..."
                    self.statusTextChanged.emit()

            except Exception as e:
                logger.error(f"Favorites sync failed: {e}", category="downloader")
                self._is_downloading = False
                self._status_text = f"Error: {e}"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()

        threading.Thread(target=_worker, daemon=True, name="FavoritesDownloadWorker").start()
