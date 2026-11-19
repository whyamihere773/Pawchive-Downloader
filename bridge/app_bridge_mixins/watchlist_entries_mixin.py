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



class WatchlistEntriesMixin(AppBridgeSignalsMixin):
    @Slot(str, str)
    @Slot(str, str, str)
    def addArtistToWatchlistAsync(self, request_id: str, url: str, custom_download_dir: str = ""):
        """addArtistToWatchlist in the background (answer: asyncResultReady(request_id, bool)).
        Looking up the creator's name and newest post used to freeze the window, for a minute
        when the site was slow."""
        self._run_async(request_id, self.addArtistToWatchlist, url, custom_download_dir)

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
        if self._refuse_if_disabled(raw_url):
            return False

        creator_name = self.api_client.resolve_creator_name(parsed) or parsed.user_id
        target_dir = ""
        is_custom_dir = bool(custom_download_dir and str(custom_download_dir).strip())
        if is_custom_dir:
            target_dir = self.resolve_explicit_watch_folder(
                folder=str(custom_download_dir),
                creator_name=creator_name,
                service=parsed.service,
                allow_empty_leaf=False,
            )
            try:
                os.makedirs(target_dir, exist_ok=True)
            except OSError:
                pass
        else:
            from core.filter_engine import FilterEngine
            clean_c = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")
            target_dir = pick_creator_folder(self._download_dir, clean_c, parsed.service)

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
            custom_folder=True if is_custom_dir else None,
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

    def _get_creator_redownload_delete_targets(self, entry) -> Tuple[List[str], List[str], int, int]:
        """Identify creator-exclusive directories and archived files to remove before re-download.

        Global download roots, drive roots, and directories belonging to other watchlist creators
        are never deleted recursively; inside shared directories only files recorded for this
        creator in the archive are listed. Returns (exclusive_dirs, loose_files, file_count, total_bytes).
        """
        from core.folder_mover import count_files
        from core.filter_engine import FilterEngine

        clean_c = FilterEngine.clean_filesystem_text(
            entry.creator_name or entry.user_id, max_len=80, fallback="creator"
        )
        protected_roots = self._protected_root_dirs()
        root_keys = {self._norm_path_key(r).rstrip("\\/") for r in protected_roots if r}

        other_dirs: List[str] = []
        other_keys = set()
        for other in self._watchlist_manager.get_all():
            if other.user_id == entry.user_id and other.service == entry.service:
                continue
            for od in [other.download_dir, *(getattr(other, "download_dirs", None) or [])]:
                if od:
                    other_dirs.append(od)
                    other_keys.add(self._norm_path_key(od).rstrip("\\/"))

        raw_candidates: List[str] = []
        for d in [entry.download_dir, *(getattr(entry, "download_dirs", None) or []), self.resolve_artist_download_dir(entry)]:
            if d and d not in raw_candidates:
                raw_candidates.append(d)

        candidate_exclusive: List[str] = []
        seen_keys = set()
        entry_dir_key = self._norm_path_key(entry.download_dir).rstrip("\\/") if entry.download_dir else ""
        for d in raw_candidates:
            if not d or not os.path.isdir(d):
                continue
            norm_d = os.path.normpath(d)
            k = self._norm_path_key(norm_d).rstrip("\\/")
            if not k or k in seen_keys:
                continue
            abs_d = os.path.abspath(norm_d)
            is_drive_root = os.path.dirname(abs_d) == abs_d
            if is_drive_root or k in root_keys or any(self._is_ancestor_dir(norm_d, r) for r in protected_roots):
                continue
            if k in other_keys or any(self._is_ancestor_dir(norm_d, od) for od in other_dirs):
                continue
            base = os.path.basename(norm_d)
            matches_creator = (
                is_creator_folder(base, clean_c, entry.service)
                or is_creator_folder(base, entry.user_id, entry.service)
                or bool(entry.service and base.lower().startswith(f"{clean_c.lower()} ["))
            )
            dedicated_custom = bool(getattr(entry, "custom_folder", False)) and k == entry_dir_key
            if not (matches_creator or dedicated_custom):
                continue
            seen_keys.add(k)
            candidate_exclusive.append(norm_d)

        exclusive_dirs = [
            d for d in candidate_exclusive
            if not any(self._is_ancestor_dir(parent_d, d) for parent_d in candidate_exclusive if parent_d != d)
        ]

        archived_paths = set(self.archive_manager.get_file_paths_for_creator(entry.user_id, entry.service))
        if entry.creator_name and entry.creator_name != entry.user_id:
            archived_paths.update(self.archive_manager.get_file_paths_for_creator(entry.creator_name, entry.service))

        excl_keys = [self._norm_path_key(d).rstrip("\\/") for d in exclusive_dirs]
        loose_files: List[str] = []
        for fp in archived_paths:
            if not fp or not os.path.isfile(fp):
                continue
            fp_key = self._norm_path_key(fp)
            if any(fp_key.startswith(ek + os.sep) for ek in excl_keys if ek):
                continue
            loose_files.append(os.path.normpath(fp))

        total_files = 0
        total_bytes = 0
        for d in exclusive_dirs:
            cnt, sz = count_files(d)
            total_files += cnt
            total_bytes += sz
        for fp in loose_files:
            try:
                total_files += 1
                total_bytes += os.path.getsize(fp)
            except OSError:
                pass
        return exclusive_dirs, loose_files, total_files, total_bytes

    def _wipe_creator_before_redownload(self, entry) -> None:
        """Delete existing files and archive records for `entry`, then re-create its target folder."""
        exclusive_dirs, loose_files, _, _ = self._get_creator_redownload_delete_targets(entry)

        for fp in loose_files:
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
                    self._invalidate_folder_stats(fp)
            except OSError as e:
                logger.warning(f"Could not delete file '{fp}' during re-download reset: {e}", category="watchlist")

        for d in exclusive_dirs:
            try:
                shutil.rmtree(d, ignore_errors=False)
            except Exception:
                shutil.rmtree(d, ignore_errors=True)
            self._invalidate_folder_stats(os.path.join(d, "x"))

        if self._enable_download_archive or os.path.exists(self.archive_manager.db_path):
            self.archive_manager.delete_by_creator(entry.user_id, entry.service)
            if entry.creator_name and entry.creator_name != entry.user_id:
                self.archive_manager.delete_by_creator(entry.creator_name, entry.service)
            if exclusive_dirs:
                self.archive_manager.delete_under_paths(exclusive_dirs)

        target_dir = os.path.normpath(self.resolve_artist_download_dir(entry))
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            logger.warning(f"Could not create download folder '{target_dir}': {e}", category="watchlist")
        self._watchlist_manager.reset_for_redownload(entry.user_id, entry.service, keep_dir=target_dir)

        def _refresh_ui():
            self._watchlist_model.update_new_counts()
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()
        self._callOnGui.emit(_refresh_ui)

    @Slot(str, str, result="QVariantMap")
    def requestRedownloadPreview(self, userId: str, service: str) -> dict:
        """Return creator info synchronously and count existing files asynchronously for confirmation dialog."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return {"ok": False}
        eff = self._get_effective_watchlist_options(entry)
        target_dir = self.resolve_artist_download_dir(entry)
        is_custom = bool((getattr(entry, "options", None) or {}).get("use_custom_settings", False))

        def _count():
            from core.filter_engine import FilterEngine
            excl_dirs, loose_files, n_files, total_bytes = self._get_creator_redownload_delete_targets(entry)
            folder_summary = "\n".join(excl_dirs) if excl_dirs else target_dir
            if loose_files and excl_dirs:
                folder_summary += f"\n(+ {len(loose_files)} archived file(s) in shared folder)"
            elif loose_files and not excl_dirs:
                folder_summary = f"{target_dir} ({len(loose_files)} archived file(s))"
            size_text = FilterEngine.format_size_str(total_bytes)
            self._callOnGui.emit(
                lambda: self.watchlistRedownloadPreviewReady.emit(
                    userId, service, int(n_files), size_text, folder_summary
                )
            )

        threading.Thread(target=_count, daemon=True, name="RedownloadPreviewCount").start()
        return {
            "ok": True,
            "userId": entry.user_id,
            "service": entry.service,
            "creatorName": entry.creator_name or entry.user_id,
            "targetDir": target_dir,
            "fileType": eff.file_type,
            "useCustomSettings": is_custom,
        }

    @Slot(str, str)
    @Slot(str, str, bool)
    def redownloadWatchlistEntry(self, userId: str, service: str, delete_existing: bool = True):
        """Wipe existing downloads (when delete_existing=True) and re-queue the watched artist
        using their current Watchlist folder and effective Watchlist settings.
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
            logger.info(f"Re-download: preparing full re-download for {name!r}.", category="watchlist")

        self._scan_cancel_event.clear()
        if not self._is_downloading:
            self._has_error = False
            self.hasErrorChanged.emit()
            self._is_downloading = True
            self.isDownloadingChanged.emit()
            self.isPausedChanged.emit()
            self._status_text = f"Removing old files for {name}..." if delete_existing else "Fetching metadata..."
            self.statusTextChanged.emit()

        active_bids = set(self.downloader.active_batch_ids_for(parsed.user_id, parsed.service))

        def _worker():
            if active_bids:
                self.downloader.quiesce_batches(active_bids, mode="cancel", timeout=15.0)
                if self._queue_model:
                    self._callOnGui.emit(lambda: [self._queue_model.removeBatch(b) for b in active_bids])
            if delete_existing:
                self._wipe_creator_before_redownload(entry)
                if not self._scan_cancel_event.is_set():
                    self._callOnGui.emit(lambda: (
                        setattr(self, "_status_text", "Fetching metadata..."),
                        self.statusTextChanged.emit(),
                    ))
            self._async_fetch_and_start(
                parsed,
                True,
                force_redownload=True,
                from_watchlist=True,
                watchlist_entry=entry,
            )

        threading.Thread(target=_worker, daemon=True, name="WatchlistRedownload").start()

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

    @Slot(bool)
    def setAllWatchlistAutoCheck(self, enabled: bool):
        """Enable or disable auto-check on startup for all artists in the watchlist."""
        self._watchlist_manager.set_all_auto_check(enabled)
        self._watchlist_model.refresh()
        self.watchlistChanged.emit()

    @Slot()
    def disableAllWatchlistAutoCheck(self):
        """Disable auto-check on startup for all artists in the watchlist."""
        self.setAllWatchlistAutoCheck(False)

    @Slot(str, result=str)
    def selectExistingDirectory(self, initialDir: str = "") -> str:
        """Open a folder picker dialog and return chosen directory path or empty string."""
        start = initialDir if (initialDir and os.path.exists(initialDir)) else (self._download_dir or os.path.expanduser("~"))
        chosen = _app_bridge_mod().QFileDialog.getExistingDirectory(None, "Select Folder", start)
        return os.path.normpath(chosen) if chosen else ""

    @Slot(result=str)
    def getWatchlistJson(self) -> str:
        """Return a JSON string of all watchlist entries for QML."""
        return self._watchlist_manager.to_json_list()

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
