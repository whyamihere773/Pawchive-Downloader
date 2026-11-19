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



class WatchlistSyncMixin(AppBridgeSignalsMixin):
    @Slot(str, str)
    def removeFromWatchlist(self, userId: str, service: str):
        """Remove an entry from the watchlist by userId + service."""
        self._watchlist_manager.remove_entry(userId, service)
        self._watchlist_model.refresh()
        self.watchlistChanged.emit()

    @Slot()
    @Slot(bool)
    def checkWatchlist(self, filtered_only: bool = True):
        """Asynchronously check watchlist entries for new posts. While a check runs, this stops
        it (the next check continues where it stopped). When filtered_only is True and a filter
        or search is active on the WatchlistModel, only visible entries are checked."""
        running = getattr(self, "_watchlist_checker", None)
        if running is not None:
            running.cancel()
            logger.info("Watchlist check stopped; the next check continues from here.", category="watchlist")
            return

        entries_to_check = None
        if filtered_only and getattr(self, "_watchlist_model", None):
            model = self._watchlist_model
            if model._service_filter != "all" or model._search_text:
                entries_to_check = list(model._display_entries)
                logger.info(
                    f"Checking {len(entries_to_check)} artist(s) matching active filter.",
                    category="watchlist"
                )

        threading.Thread(
            target=lambda: self._async_watchlist_check(entries_to_check=entries_to_check),
            name="WatchlistCheck",
            daemon=True
        ).start()

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
            unimp_info = dict(getattr(self.downloader, "last_build_unimported", {}) or {})
            unimp_post_ids = {str(pid) for pid in (unimp_info.get("post_ids") or [])}
            unimp_files = int(unimp_info.get("files", 0) or 0)
            if not tasks:
                if unimp_files > 0:
                    # Unimported posts aren't physically hosted on Pawchive yet: clear the badge so
                    # Watchlist doesn't nag or loop on them, but do NOT advance last_post_date/id
                    # so Watchlist picks them up automatically as soon as Pawchive imports them.
                    entry.new_post_count = 0
                    entry.cached_new_posts = []
                    self._watchlist_manager.save()
                    logger.info(
                        f"Watchlist: skipped {len(unimp_post_ids) or len(new_posts)} unimported post(s) for "
                        f"{entry.creator_name!r} (not imported on Pawchive yet — will be detected automatically once imported).",
                        category="watchlist",
                    )
                    return []
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
            # Only the posts that still have something to download are new (one missing file used
            # to keep every post of the check listed)
            with_work = {str(getattr(t, "post_id", "") or "") for t in tasks}
            remaining = [p for p in new_posts if str(p.get("id", "")) in with_work]
            if remaining and len(remaining) < len(new_posts):
                done_ids = [
                    str(p.get("id", "")) for p in new_posts
                    if str(p.get("id", "")) not in with_work and str(p.get("id", "")) not in unimp_post_ids
                ]
                if done_ids:
                    self._watchlist_manager.resolve_posts(entry.user_id, entry.service, post_ids=done_ids)
                entry.cached_new_posts = remaining
                entry.new_post_count = len(remaining)
                return remaining
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
                # Auto-heal creator name if profile resolves to a different name
                from core.parser import KemonoURLParser
                parsed = KemonoURLParser.parse(entry.url or f"https://{entry.domain}/{entry.service}/user/{entry.user_id}")
                if parsed.is_valid and hasattr(self.api_client, "resolve_creator_name"):
                    try:
                        resolved = self.api_client.resolve_creator_name(parsed)
                        if resolved and resolved != entry.user_id and resolved != entry.creator_name:
                            old_name = entry.creator_name
                            entry.creator_name = resolved
                            self._watchlist_manager.save(entry)
                            self._watchlist_model.entry_changed(entry)
                            self.watchlistChanged.emit()
                            logger.info(f"Auto-healed creator name in watchlist: {old_name!r} -> {resolved!r}", category="watchlist")
                    except Exception as e:
                        logger.debug(f"Could not auto-heal creator name for {entry.user_id}: {e}", category="watchlist")

                count = self._check_watchlist_entry(entry)
                entry.last_checked_at = time.time()
                self._watchlist_manager.save(entry)
            except Exception as e:
                # (the updates found earlier stay listed)
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

        if getattr(entry, "custom_folder", False) and entry.download_dir:
            return entry.download_dir          # a folder the user chose, used as it is

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
                self._watchlist_manager.save(entry)

            if existing_locs:
                # Pick the existing artist location that sits on the disk with the MOST free space
                best_loc, _ = storage_pool_manager.get_most_free_drive(existing_locs)
                return best_loc
            else:
                # No artist folder exists yet -> pick among primary and all overflow roots by most free disk
                roots = ([storage_pool_manager.primary_dir] if storage_pool_manager.primary_dir else [self._download_dir]) + list(storage_pool_manager.overflow_dirs)
                best_root, _ = storage_pool_manager.get_most_free_drive(roots)
                target = pick_creator_folder(best_root, clean_c, entry.service)
                if target not in entry.download_dirs:
                    entry.download_dirs.append(target)
                    self._watchlist_manager.save(entry)
                return target

        # Standard single-drive fallback
        target = (getattr(entry, "download_dir", "") or "").strip()
        if target:
            if os.path.exists(target):
                return self.resolve_artist_download_dir_for_folder(target, entry.creator_name or entry.user_id, entry.service)
            elif not self._watchlist_apply_global_settings:
                return self.resolve_artist_download_dir_for_folder(target, entry.creator_name or entry.user_id, entry.service)

        base_dir = self._download_dir or os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads")
        return pick_creator_folder(base_dir, clean_c, entry.service)

    def resolve_artist_download_dir_for_folder(self, folder: str, creator_name: str, service: str) -> str:
        r"""
        Resolves a selected or configured folder to ensure it points directly to the creator's folder:
        - If folder basename already matches creator or creator [service], return folder as-is.
        - If an existing subfolder matching the creator exists inside folder, return that subfolder.
        - Otherwise, if folder is a parent directory (e.g. D:\Archive), assign folder/creator [service].
        """
        from core.filter_engine import FilterEngine
        clean_c = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")
        raw = (folder or "").strip()
        if not raw:
            base_dir = self._download_dir or os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads")
            return pick_creator_folder(base_dir, clean_c, service)
        folder = os.path.normpath(raw)
        base = os.path.basename(folder)
        if is_creator_folder(base, clean_c, service) or (service and base.lower().startswith(f"{clean_c.lower()} [")):
            return folder
        return pick_creator_folder(folder, clean_c, service)

    @staticmethod
    def _norm_path_key(path: str) -> str:
        """Canonical case-insensitive normalized path key for directory tree comparisons."""
        if not path:
            return ""
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))

    @classmethod
    def _is_ancestor_dir(cls, ancestor: str, descendant: str) -> bool:
        """Return True if `ancestor` strictly contains `descendant`."""
        a = cls._norm_path_key(ancestor).rstrip("\\/")
        d = cls._norm_path_key(descendant).rstrip("\\/")
        return bool(a and d and a != d and d.startswith(a + os.sep))

    def _protected_root_dirs(self) -> List[str]:
        """Return global download root folders that must never receive loose creator files."""
        from core.storage_pool_manager import storage_pool_manager
        return [
            r for r in [
                self._download_dir,
                storage_pool_manager.primary_dir,
                *(storage_pool_manager.overflow_dirs or []),
                os.path.expanduser("~"),
                os.path.join(os.path.expanduser("~"), "Downloads"),
            ] if r
        ]

    def resolve_explicit_watch_folder(
        self,
        entry=None,
        folder: str = "",
        *,
        creator_name: str = "",
        service: str = "",
        allow_empty_leaf: bool = False,
    ) -> str:
        """Resolve an explicitly chosen/typed Watchlist folder path.

        If the user picks a shallower parent folder (e.g. D:/cg2 when old was D:/cg2/21),
        automatically resolves to `<folder>/<Creator [service]>` instead of downloading loose
        or nowhere.
        """
        raw = (folder or "").strip()
        if not raw:
            return ""
        norm_folder = os.path.normpath(raw)
        cname = (
            creator_name
            or (getattr(entry, "creator_name", "") if entry else "")
            or (getattr(entry, "user_id", "") if entry else "")
            or "creator"
        )
        svc = service or (getattr(entry, "service", "") if entry else "") or ""

        if allow_empty_leaf and os.path.isdir(norm_folder):
            try:
                is_empty = not os.listdir(norm_folder)
            except OSError:
                is_empty = False
            if is_empty:
                folder_key = self._norm_path_key(norm_folder).rstrip("\\/")
                abs_folder = os.path.abspath(norm_folder)
                is_drive_root = os.path.dirname(abs_folder) == abs_folder
                root_keys = {self._norm_path_key(r).rstrip("\\/") for r in self._protected_root_dirs()}
                existing_dirs = []
                if entry:
                    existing_dirs = [entry.download_dir, *(getattr(entry, "download_dirs", None) or [])]
                is_ancestor_of_old = any(self._is_ancestor_dir(norm_folder, d) for d in existing_dirs if d)
                if not is_drive_root and folder_key not in root_keys and not is_ancestor_of_old:
                    return norm_folder

        return self.resolve_artist_download_dir_for_folder(norm_folder, cname, svc)

    def extract_artist_folder_from_path(self, sample_path: str, creator_name: str, service: str, fallback_dir: str = "") -> str:
        """
        Safely walk up parent directories from a sample file target path to locate
        the creator folder, completely avoiding cross-drive ValueError from os.path.relpath.
        """
        from core.filter_engine import FilterEngine
        clean_c = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")
        clean_lower = clean_c.lower()

        try:
            curr = os.path.dirname(os.path.abspath(sample_path))
            while curr and curr != os.path.dirname(curr):
                base = os.path.basename(curr)
                if is_creator_folder(base, clean_c, service) or (service and base.lower().startswith(f"{clean_lower} [")):
                    return curr
                curr = os.path.dirname(curr)
        except Exception:
            pass

        if fallback_dir:
            return pick_creator_folder(fallback_dir, clean_c, service)
        return os.path.dirname(sample_path) if sample_path else pick_creator_folder(self._download_dir, clean_c, service)

    def _get_effective_watchlist_options(self, entry) -> FilterOptions:
        """
        Determines the FilterOptions to use for a watchlist download:
        - If watchlistApplyGlobalSettings is True: returns current global UI options with
          transient search/date filters cleared so watchlist cutoff dates apply cleanly.
        - If False: merges entry.options over current global options to preserve legacy
          creator overrides without falling back to hardcoded defaults for newly added keys.
        """
        from core.filter_engine import FilterOptions
        entry_opts = getattr(entry, "options", None) or {}
        if entry_opts.get("use_custom_settings"):
            base_dict = self._get_filter_options().to_dict()
            base_dict["date_after"] = ""
            base_dict["date_before"] = ""
            base_dict["page_start"] = 1
            base_dict["page_end"] = 999999
            base_dict["characters"] = ""
            base_dict.update(entry_opts)
            base_dict.pop("use_custom_settings", None)
            return FilterOptions.from_dict(base_dict)
        if self._watchlist_apply_global_settings:
            options = self._get_filter_options()
            options.date_after = ""
            options.date_before = ""
            options.page_start = 1
            options.page_end = 999999
            options.characters = ""
            return options
        elif entry_opts:
            base_dict = self._get_filter_options().to_dict()
            base_dict.update(entry_opts)
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

    def _process_watchlist_entry_download(
        self,
        entry,
        postIds: Optional[list] = None,
        page_start: int = 1,
        page_end: int = 999999,
        custom_dir: str = "",
        allow_modal: bool = True,
    ):
        """Worker logic to fetch, structure, and append download tasks for a single watchlist entry."""
        from core.providers import is_disabled
        if is_disabled(entry.url or entry.domain):
            logger.warning(f"Watchlist: {entry.creator_name!r} is on a switched-off site; skipped.", category="watchlist")
            return
        new_posts = self._watchlist_manager.get_posts_since(
            entry,
            self.api_client,
            page_start=page_start,
            page_end=page_end
        )
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
        if page_start > 1 or page_end < 999999:
            options.page_start = page_start
            options.page_end = page_end
        if self._scheduled_sweep_retry:
            options.auto_retry_at_end = True     # Scheduler → "Sweep auto-retry pass"

        if custom_dir:
            artist_folder = self.resolve_artist_download_dir_for_folder(
                custom_dir,
                entry.creator_name or entry.user_id,
                entry.service
            )
        else:
            artist_folder = self.resolve_artist_download_dir(entry)

        if artist_folder:
            try:
                os.makedirs(artist_folder, exist_ok=True)
            except OSError:
                pass

        # Ensure the entry knows its download_dir and download_dirs
        if not entry.download_dir or custom_dir:
            entry.download_dir = artist_folder
        if hasattr(entry, "download_dirs") and isinstance(entry.download_dirs, list):
            if artist_folder not in entry.download_dirs:
                entry.download_dirs.insert(0, artist_folder)
        self._watchlist_manager.save(entry)
        self._watchlist_model.refresh()
        self.watchlistChanged.emit()

        options = FilterOptions.from_dict(options.to_dict())
        wl_batch_id = f"watchlist_{entry.service}_{entry.user_id}"
        wl_parsed = KemonoURLParser.parse(getattr(entry, "url", "") or "")
        if not wl_parsed.is_valid:
            wl_parsed = URLParseResult(
                is_valid=True,
                raw_url=getattr(entry, "url", "") or "",
                domain=entry.domain,
                service=entry.service,
                user_id=entry.user_id,
            )

        base_download_dir = os.path.dirname(artist_folder) if os.path.isabs(artist_folder) else (custom_dir or self._download_dir)
        wl_prog = lambda cur, tot, txt: self._update_scan_progress(txt, cur, tot)  # noqa: E731
        tasks = self.downloader.build_tasks_from_posts(
            posts=new_posts,
            creator_name=entry.creator_name,
            service=entry.service,
            domain=entry.domain,
            base_dir=base_download_dir,
            options=options,
            batch_id=wl_batch_id,
            artist_dir=artist_folder,
            user_id=entry.user_id,
            progress_callback=wl_prog,
        )

        # Auto-harvest new posts' cloud links into permanent Link Vault
        self._auto_harvest_posts_to_vault(
            posts=new_posts,
            creator_name=entry.creator_name,
            domain=entry.domain,
            service=entry.service,
            user_id=entry.user_id
        )
        unimp_info = dict(getattr(self.downloader, "last_build_unimported", {}) or {})
        unimp_tasks = list(getattr(self.downloader, "last_build_unimported_tasks", []) or [])
        unimp_post_ids = {str(pid) for pid in (unimp_info.get("post_ids") or [])}
        unimp_files = int(unimp_info.get("files", 0) or 0)
        if tasks:
            self.downloader.register_batch_context(
                BatchBuildContext(
                    batch_id=wl_batch_id,
                    parsed=wl_parsed,
                    creator_name=entry.creator_name or entry.user_id,
                    service=entry.service,
                    user_id=entry.user_id,
                    domain=entry.domain,
                    base_dir=base_download_dir,
                    artist_dir=artist_folder,
                    from_watchlist=True,
                    custom_folder=bool(getattr(entry, "custom_folder", False)),
                    posts=list(new_posts),
                    fetched_dms=bool(getattr(options, "download_dms", False)),
                    scan_page_start=int(getattr(options, "page_start", 1) or 1),
                    scan_page_end=int(getattr(options, "page_end", 999999) or 999999),
                    applied_options=options,
                    applied_download_dir=str(self._download_dir or ""),
                    applied_site_in_folder_name=bool(folder_naming.include_service),
                )
            )
            post_ids_with_files = {str(t.post_id) for t in tasks}
            no_file_posts = [
                (self._post_day(p), str(p.get("id", ""))) for p in new_posts
                if str(p.get("id", "")) not in post_ids_with_files and str(p.get("id", "")) not in unimp_post_ids
            ]
            if no_file_posts:
                key = (entry.service.lower(), entry.user_id.lower())
                self._watchlist_pending_updates.setdefault(key, []).extend(no_file_posts)
            queued_tasks = list(tasks) + unimp_tasks
            self._appendTasksSignal.emit(queued_tasks)
            self.downloader.append_tasks(queued_tasks, options=options, cookie_str=self._cookie_string, progress_callback=wl_prog)
            if not self._is_downloading and self.downloader._is_running:
                self._is_downloading = True
                self.isDownloadingChanged.emit()
                self._status_text = f"Downloading updates for {entry.creator_name}..."
                self.statusTextChanged.emit()
            if unimp_files > 0 or int(unimp_info.get("queued_thumbnails", 0) or 0) > 0:
                self._emit_unimported_notice_if_needed(
                    unimp_info,
                    queued_count=len(tasks),
                    is_single_post=(len(new_posts) == 1),
                    allow_modal=False,
                )
            logger.success(
                f"Watchlist: queued {len(tasks)} new file(s) for {entry.creator_name!r} at {artist_folder}.",
                category="watchlist"
            )
        else:
            if unimp_files > 0:
                if unimp_tasks:
                    # Surface pre-failed non-retryable entries in Queue & Retry Modal
                    # without starting workers (0 download requests).
                    self._appendTasksSignal.emit(unimp_tasks)
                    self.downloader.append_tasks(unimp_tasks, options=None)
                    if self._queue_model:
                        self._callOnGui.emit(lambda: self._queue_model.failedCountChanged.emit())
                # Don't advance last_post_date/id past unimported posts so Watchlist will
                # automatically pick them up once Pawchive imports their full-size files.
                entry.new_post_count = 0
                entry.cached_new_posts = []
                self._watchlist_manager.save()
                self._watchlist_model.update_new_counts()
                self._watchlist_model.refresh()
                self.watchlistChanged.emit()
                self._emit_unimported_notice_if_needed(
                    unimp_info,
                    queued_count=0,
                    is_single_post=(len(new_posts) == 1),
                    allow_modal=allow_modal,
                )
                return
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
                    self._process_watchlist_entry_download(e, allow_modal=False)
                except Exception as err:
                    logger.error(f"Error downloading updates for {e.creator_name!r}: {err}", category="watchlist")

        threading.Thread(target=_run_batch, daemon=True).start()

    def _check_watchlist_entry(self, entry) -> int:
        """Checks one artist for new posts (raises when its post list couldn't be fetched, so the
        updates found earlier are kept and it's tried again next time)."""
        checker = getattr(self, "_watchlist_checker", None)
        cancel = getattr(checker, "cancel_event", None) if checker else None
        new = self._watchlist_manager.get_posts_since(entry, self.api_client, raise_on_error=True, cancel_event=cancel)
        # Looking for the files on disk / in the archive uses the downloader: one artist at a time
        with self._watchlist_resolve_lock:
            new = self._check_and_resolve_if_already_downloaded(entry, new)
        entry.new_post_count = len(new)
        if new:
            logger.info(f"Watchlist: {entry.creator_name!r} has {len(new)} new post(s).", category="watchlist")
        return len(new)

    def _async_watchlist_check(self, automatic: bool = False, wait_if_running: bool = False, entries_to_check: Optional[list] = None):
        """
        Background thread: check the watchlist for new posts (all artists or entries_to_check; automatic
        checks only those with auto-check on). Sites are checked in parallel, results show up as they
        come in, and a check that was stopped continues where it left off (see WatchlistChecker). Ends
        with _watchlistResultSignal so the GUI can refresh safely.
        """
        from core.providers import is_disabled, disabled_message
        from core.watchlist_checker import WatchlistChecker
        with self._watchlist_check_lock:
            running = getattr(self, "_watchlist_checker", None)
            if running is None:
                done = threading.Event()
                last_progress = [0.0]

                def _progress(n_done, n_total):
                    now = time.monotonic()
                    if n_done >= n_total or now - last_progress[0] > 0.25:
                        last_progress[0] = now
                        self.watchlistCheckProgress.emit(n_done, n_total)

                checker = WatchlistChecker(
                    self._watchlist_manager, self._check_watchlist_entry,
                    on_result=lambda e, n: self._watchlist_model.entry_changed(e),
                    on_progress=_progress,
                    listing=self.api_client.fetch_creator_updates,
                    listing_cost=self.api_client.creator_listing_cost)
                checker.done_event = done
                self._watchlist_checker = checker
        if running is not None:
            if wait_if_running:
                running.done_event.wait()
            return
        try:
            self.watchlistCheckStarted.emit()
            entries = entries_to_check if entries_to_check is not None else self._watchlist_manager.get_all()
            skipped_off = [e for e in entries if is_disabled(e.domain) or is_disabled(e.url)]
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
            off = {id(e) for e in skipped_off}
            to_check = [e for e in entries if id(e) not in off and (e.auto_check or not automatic)]
            total_new = checker.run(to_check)
            if checker.failed:
                logger.warning(f"Watchlist: {checker.failed} artist(s) couldn't be checked; they're tried "
                               f"again next time.", category="watchlist")
        except Exception as e:
            logger.error(f"Watchlist check failed: {e}", category="watchlist")
            total_new = checker.total_new
        finally:
            with self._watchlist_check_lock:
                self._watchlist_checker = None
            done.set()
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
