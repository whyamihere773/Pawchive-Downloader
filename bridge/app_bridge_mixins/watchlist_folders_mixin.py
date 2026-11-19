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



class WatchlistFoldersMixin(AppBridgeSignalsMixin):
    @Slot(str, str, result="QVariantMap")
    def getWatchlistEntrySettings(self, userId: str, service: str) -> dict:
        """Return full editable Watchlist settings and resolved folder info for `entry`."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return {"ok": False}
        eff = self._get_effective_watchlist_options(entry)
        entry_opts = getattr(entry, "options", None) or {}
        return {
            "ok": True,
            "userId": entry.user_id,
            "service": entry.service,
            "creatorName": entry.creator_name or entry.user_id,
            "url": entry.url or "",
            "downloadDir": entry.download_dir or "",
            "resolvedDir": self.resolve_artist_download_dir(entry),
            "customFolder": bool(getattr(entry, "custom_folder", False)),
            "autoCheck": bool(entry.auto_check),
            "lastPostDate": entry.last_post_date or "",
            "useCustomSettings": bool(entry_opts.get("use_custom_settings", False)),
            "options": eff.to_dict(),
        }

    @Slot(str, str, str, result=str)
    @Slot(str, str, str, bool, result=str)
    def previewWatchlistResolvedFolder(
        self,
        userId: str,
        service: str,
        rawFolder: str,
        allowEmptyLeaf: bool = False,
    ) -> str:
        """Preview which folder path Watchlist will create/use for the given input."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return ""
        raw = (rawFolder or "").strip()
        if not raw:
            from core.filter_engine import FilterEngine
            clean_c = FilterEngine.clean_filesystem_text(
                entry.creator_name or entry.user_id, max_len=80, fallback="creator"
            )
            base_dir = self._download_dir or os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads")
            return pick_creator_folder(base_dir, clean_c, entry.service)
        return self.resolve_explicit_watch_folder(entry, raw, allow_empty_leaf=bool(allowEmptyLeaf))

    @Slot(str, str, str, result="QVariantMap")
    def browseFolderForWatchlistSettings(self, userId: str, service: str, currentDir: str = "") -> dict:
        """Open directory picker for Watchlist entry settings modal without committing yet."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return {"picked": "", "resolved": "", "isLeaf": False}
        initial = (
            currentDir
            if (currentDir and os.path.exists(currentDir))
            else (entry.download_dir if (entry.download_dir and os.path.exists(entry.download_dir)) else self._download_dir)
        )
        chosen = _app_bridge_mod().QFileDialog.getExistingDirectory(
            None,
            f"Select Download Folder for {entry.creator_name or userId}",
            initial or os.path.expanduser("~"),
        )
        if not chosen:
            return {"picked": "", "resolved": "", "isLeaf": False}
        norm_picked = os.path.normpath(chosen)
        resolved = self.resolve_explicit_watch_folder(entry, norm_picked, allow_empty_leaf=True)
        is_leaf = self._norm_path_key(norm_picked) == self._norm_path_key(resolved)
        return {"picked": norm_picked, "resolved": resolved, "isLeaf": bool(is_leaf)}

    @Slot(str, str, "QVariantMap", result="QVariantMap")
    def saveWatchlistEntrySettings(self, userId: str, service: str, settings: dict) -> dict:
        """Persist per-creator Watchlist folder, auto-check, cutoff date, and custom filter/download options."""
        from core.filter_engine import FilterOptions
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return {"ok": False, "error": "Creator not found in Watchlist."}
        data = dict(settings or {})

        raw_date = data.get("lastPostDate")
        if raw_date is not None:
            norm_date = self._watchlist_manager.normalize_date(str(raw_date))
            if norm_date is None:
                return {"ok": False, "error": "Invalid cutoff date. Use YYYY-MM-DD, DD/MM/YYYY, or leave empty."}

        conflict_bids = self.downloader.active_batch_ids_for(userId, service)
        prev_eff_opts = self._get_effective_watchlist_options(entry)
        if conflict_bids:
            ctx0 = self.downloader.get_batch_context(conflict_bids[0])
            if ctx0 and ctx0.applied_options:
                prev_eff_opts = FilterOptions.from_dict(ctx0.applied_options.to_dict())
            prev_resolved_dir = (ctx0.artist_dir if (ctx0 and ctx0.artist_dir) else None) or self.resolve_artist_download_dir(entry)
        else:
            prev_resolved_dir = self.resolve_artist_download_dir(entry)

        use_custom = bool(data.get("useCustomSettings", False))
        raw_opts = data.get("options")
        if isinstance(raw_opts, dict):
            base_dict = self._get_filter_options().to_dict()
            base_dict.update(raw_opts)
            base_dict["date_after"] = ""
            base_dict["date_before"] = ""
            base_dict["page_start"] = 1
            base_dict["page_end"] = 999999
            sanitized = FilterOptions.from_dict(base_dict).to_dict()
            sanitized["use_custom_settings"] = use_custom
        else:
            sanitized = dict(getattr(entry, "options", None) or {})
            sanitized["use_custom_settings"] = use_custom

        auto_check = data.get("autoCheck")
        self._watchlist_manager.update_entry_settings(
            userId,
            service,
            auto_check=bool(auto_check) if auto_check is not None else None,
            options=sanitized,
            last_post_date=str(raw_date) if raw_date is not None else None,
        )

        # Handle folder updates (explicit folder vs reset to default global location)
        move_prompt = False
        raw_dir = str(data.get("downloadDir") or "").strip() if "downloadDir" in data else None
        if raw_dir is not None:
            if not raw_dir:
                self._watchlist_manager.set_download_dir(userId, service, "", custom_folder=False)
                resolved_out = self.resolve_artist_download_dir(entry)
            else:
                picked_as_leaf = bool(data.get("pickedAsLeaf", False))
                resolved = self.resolve_explicit_watch_folder(entry, raw_dir, allow_empty_leaf=picked_as_leaf)
                old_key = self._norm_path_key(entry.download_dir) if entry.download_dir else ""
                new_key = self._norm_path_key(resolved)
                prompt_move = bool(data.get("promptMoveIfNeeded", True)) and not conflict_bids
                olds = self._folders_to_move(entry, resolved) if old_key != new_key else []
                has_existing_files = False
                if olds and prompt_move:
                    for d in olds:
                        for _, _, files in os.walk(d):
                            if files:
                                has_existing_files = True
                                break
                        if has_existing_files:
                            break
                if has_existing_files:
                    self._request_folder_change(entry, resolved)
                    move_prompt = True
                else:
                    try:
                        os.makedirs(resolved, exist_ok=True)
                    except OSError as e:
                        return {"ok": False, "error": f"Could not create folder '{resolved}': {e}"}
                    self._watchlist_manager.set_download_dir(userId, service, resolved, custom_folder=True)
                resolved_out = resolved
        else:
            resolved_out = self.resolve_artist_download_dir(entry)

        self._watchlist_model.update_new_counts()
        self._watchlist_model.refresh()
        self.watchlistChanged.emit()

        if conflict_bids:
            new_eff_opts = self._get_effective_watchlist_options(entry)
            site_flag = bool(folder_naming.include_service)
            diff_info = classify_settings_change(
                prev_eff_opts,
                new_eff_opts,
                prev_resolved_dir,
                resolved_out,
                site_flag,
                site_flag,
            )
            if diff_info.get("tier", 0) > 0:
                return {
                    "ok": True,
                    "resolvedDir": resolved_out,
                    "movePrompt": False,
                    "activeDownloadConflict": True,
                    "conflictUserId": str(userId),
                    "conflictService": str(service),
                    "conflictCreatorName": entry.creator_name or str(userId),
                    "conflictSummary": diff_info.get("summary") or "Download settings updated",
                    "conflictRequiresScan": bool(diff_info.get("tier", 0) >= 4),
                }

        return {"ok": True, "resolvedDir": resolved_out, "movePrompt": move_prompt}

    @Slot(str, str, str)
    def setWatchlistDownloadDir(self, userId: str, service: str, download_dir: str):
        """Set or update the custom download directory for a watchlist artist."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry:
            return
        raw = (download_dir or "").strip()
        if not raw:
            if self._watchlist_manager.set_download_dir(userId, service, "", custom_folder=False):
                self._watchlist_model.refresh()
                self.watchlistChanged.emit()
            return
        resolved = self.resolve_explicit_watch_folder(entry, raw, allow_empty_leaf=False)
        try:
            os.makedirs(resolved, exist_ok=True)
        except OSError:
            pass
        if self._watchlist_manager.set_download_dir(userId, service, resolved, custom_folder=True):
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
        folder = _app_bridge_mod().QFileDialog.getExistingDirectory(
            None,
            f"Select Download Folder for {entry.creator_name if entry else userId}",
            initial_dir
        )
        if not folder or not entry:
            return
        resolved = self.resolve_explicit_watch_folder(entry, folder, allow_empty_leaf=True)
        self._request_folder_change(entry, resolved)

    def _folders_to_move(self, entry, new_dir: str) -> List[str]:
        """The artist's current folders whose files could follow them to new_dir: never the main
        download folder or a storage drive's root, nor a folder that contains new_dir or sits in it."""
        new_k = self._norm_path_key(new_dir)
        roots = {self._norm_path_key(r) for r in self._protected_root_dirs() if r}
        out, seen = [], set()
        for d in [entry.download_dir, *(entry.download_dirs or [])]:
            if not d or not os.path.isdir(d):
                continue
            k = self._norm_path_key(d)
            if k in seen or k == new_k or k in roots or new_k.startswith(k + os.sep) or k.startswith(new_k + os.sep):
                continue
            seen.add(k)
            out.append(os.path.normpath(d))
        return out

    def _request_folder_change(self, entry, new_dir: str):
        """Counts the files in the artist's current folder(s) (in the background: it can be a lot), then
        asks whether to move them (watchlistFolderChangeRequested), or changes the folder at once when
        there's nothing to move."""
        from core.folder_mover import count_files
        uid, svc = entry.user_id, entry.service
        olds = self._folders_to_move(entry, new_dir)

        def _count():
            n = size = 0
            for d in olds:
                a, b = count_files(d)
                n, size = n + a, size + b

            def _ask():
                if n == 0:
                    self.applyWatchlistFolderChange(uid, svc, new_dir, False)
                else:
                    from core.filter_engine import FilterEngine
                    self.watchlistFolderChangeRequested.emit(uid, svc, entry.creator_name, "\n".join(olds), new_dir, n,
                                                             FilterEngine.format_size_str(size))
            self._callOnGui.emit(_ask)
        threading.Thread(target=_count, name="FolderCount", daemon=True).start()

    @Slot(str, str, str, bool)
    def applyWatchlistFolderChange(self, userId: str, service: str, new_dir: str, move_files: bool):
        """Makes new_dir the artist's download folder. move_files: their files move there too (in the
        background) and the archive's records follow them; otherwise the old folders are kept as
        extra locations, so files already downloaded are still recognised."""
        entry = self._watchlist_manager._find(userId, service)
        if not entry or not new_dir:
            return
        new_dir = os.path.normpath(new_dir)
        olds = self._folders_to_move(entry, new_dir)

        def _set(keep_old: bool):
            entry.download_dir = new_dir
            entry.download_dirs = [new_dir] + ([d for d in olds if os.path.isdir(d)] if keep_old else [])
            entry.custom_folder = True
            self._watchlist_manager.save(entry)
            self._watchlist_model.refresh()
            self.watchlistChanged.emit()

        if not move_files or not olds:
            try:
                os.makedirs(new_dir, exist_ok=True)
            except OSError as e:
                self.watchlistFolderChanged.emit(userId, service, f"The folder couldn't be created: {e}")
                return
            _set(keep_old=True)
            logger.info(f"Watchlist: new downloads for {entry.creator_name!r} go to '{new_dir}'.", category="watchlist")
            self.watchlistFolderChanged.emit(userId, service, "")
            return

        self._status_text = f"Moving {entry.creator_name}'s files…"
        self.statusTextChanged.emit()
        cancel = threading.Event()
        self._folder_move_cancel = cancel

        def _move():
            from core.folder_mover import move_folder_contents, count_files
            total = sum(count_files(d)[0] for d in olds)
            # The archive's records are found once, then follow their files a batch at a time: a move
            # that's stopped (or the app closed) leaves every moved file's record right
            record_ids = self.archive_manager.records_under(olds) if self._enable_download_archive else {}
            key = self.archive_manager._path_key
            pending: List[Tuple[int, str]] = []
            state = {"done": 0, "relocated": 0, "last": 0.0}

            def _flush():
                if pending:
                    state["relocated"] += self.archive_manager.set_file_paths(list(pending))
                    pending.clear()

            def _on_file(old, new):
                state["done"] += 1
                rid = record_ids.get(key(old))
                if rid is not None:
                    pending.append((rid, new))
                    if len(pending) >= 200:
                        _flush()
                now = time.monotonic()
                if now - state["last"] > 0.2:
                    state["last"] = now
                    self.watchlistFolderMoveProgress.emit(userId, service, state["done"], total)

            moved = dup = renamed = 0
            errors = []
            try:
                for d in olds:
                    r = move_folder_contents(d, new_dir, cancel=cancel, on_file=_on_file)
                    moved, dup, renamed = moved + r.moved, dup + r.duplicates, renamed + r.renamed
                    errors += r.errors
                    if cancel.is_set():
                        break
            finally:
                _flush()
            stopped = cancel.is_set()
            relocated = state["relocated"]

            def _done():
                self._folder_move_cancel = None
                # stopped or not all moved: the artist's files are in both folders, both stay known
                _set(keep_old=bool(errors) or stopped)
                for d in olds:
                    self._invalidate_folder_stats(os.path.join(d, "x"))
                self._invalidate_folder_stats(os.path.join(new_dir, "x"))
                msg = f"Moved {moved} file(s) of {entry.creator_name} to '{new_dir}'"
                if dup:
                    msg += f", {dup} already there"
                if renamed:
                    msg += f", {renamed} renamed to keep both"
                if relocated:
                    msg += f"; {relocated} archive record(s) updated"
                if stopped:
                    msg += ". Stopped before the end: the rest stays in the old folder"
                (logger.warning if errors or stopped else logger.success)(
                    msg + (f". {len(errors)} couldn't be moved: {errors[0]}" if errors else "."), category="watchlist")
                self._status_text = "Progress: Idle"
                self.statusTextChanged.emit()
                note = ""
                if errors:
                    note = f"{len(errors)} file(s) couldn't be moved (see the log)"
                elif stopped:
                    note = f"Stopped: {moved} of {total} file(s) moved"
                self.watchlistFolderChanged.emit(userId, service, note)
            self._callOnGui.emit(_done)
        thread = threading.Thread(target=_move, name="FolderMove", daemon=True)
        self._folder_move_thread = thread
        thread.start()

    @Slot()
    def cancelWatchlistFolderMove(self):
        """Stops a running "Move files" after the file it's moving (what's moved stays moved)."""
        cancel = getattr(self, "_folder_move_cancel", None)
        if cancel is not None:
            cancel.set()

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
        folder = _app_bridge_mod().QFileDialog.getExistingDirectory(
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
                subprocess.Popen(["open", target], **subprocess_env_kwargs())
            else:
                subprocess.Popen(["xdg-open", target], **subprocess_env_kwargs())
