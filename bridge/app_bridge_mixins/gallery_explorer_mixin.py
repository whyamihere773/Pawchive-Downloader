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



class GalleryExplorerMixin(AppBridgeSignalsMixin):
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
        previews_to_scan = []

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

                            cached_prev = self._folder_previews_cache.get(norm_p)
                            if cached_prev and cached_prev.get("mtime") == dir_mtime:
                                previews = list(cached_prev.get("previews") or [])
                            else:
                                previews = []
                                previews_to_scan.append(norm_p)

                            items.append({
                                "name": entry.name,
                                "path": norm_p,
                                "is_dir": True,
                                "size": size,
                                "file_count": file_count,
                                "folder_count": folder_count,
                                "child_count": -1,
                                "previews": previews,
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
                                "previews": [],
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
        if subfolders_to_scan or previews_to_scan:
            threading.Thread(
                target=self._batch_calculate_folder_stats,
                args=(subfolders_to_scan, current_token, previews_to_scan),
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

    def _find_folder_previews(
        self,
        folder_path: str,
        token: Optional[int] = None,
        max_items: int = 4,
        max_dirs: int = 120,
        max_entries: int = 2000,
    ) -> List[str]:
        """Breadth-first scan for up to `max_items` previewable media files in `folder_path`.

        Checks immediate children before nested subfolders (sorted case-insensitively) so
        Creator -> Post hierarchies resolve quickly within bounded I/O. Images take priority;
        on Windows, video files are included as fallback thumbnails.
        """
        images: List[str] = []
        videos: List[str] = []
        allow_videos = sys.platform == "win32"
        queue: deque = deque([folder_path])
        visited_dirs = 0
        scanned_entries = 0

        while queue and visited_dirs < max_dirs and scanned_entries < max_entries:
            if token is not None and token != self._folder_stats_worker_token:
                return []
            cur_dir = queue.popleft()
            visited_dirs += 1
            raw_entries = []
            try:
                budget = max(1, max_entries - scanned_entries)
                with os.scandir(cur_dir) as it:
                    for entry in it:
                        raw_entries.append(entry)
                        if len(raw_entries) >= budget:
                            break
            except (PermissionError, OSError):
                continue

            raw_entries.sort(key=lambda e: e.name.lower())
            subdirs: List[str] = []
            for entry in raw_entries:
                if token is not None and token != self._folder_stats_worker_token:
                    return []
                scanned_entries += 1
                name = entry.name
                if name.startswith(".") or name == "__pycache__":
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        subdirs.append(os.path.normpath(entry.path))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    ext = os.path.splitext(name)[1].lower()
                    is_img = ext in _FOLDER_PREVIEW_IMAGE_EXTS
                    is_vid = allow_videos and (ext in VIDEO_EXTENSIONS)
                    if not (is_img or is_vid):
                        continue
                    if entry.stat(follow_symlinks=False).st_size <= 0:
                        continue
                    norm_entry = os.path.normpath(entry.path)
                    if is_img:
                        images.append(norm_entry)
                        if len(images) >= max_items:
                            return images[:max_items]
                    elif len(videos) < max_items:
                        videos.append(norm_entry)
                except (PermissionError, OSError):
                    continue

            for sub in subdirs:
                if visited_dirs + len(queue) >= max_dirs:
                    break
                queue.append(sub)

        return (images + videos)[:max_items]

    def _compute_folder_previews(self, folder_path: str, token: int):
        """Worker function executed in background thread to populate folder thumbnail previews."""
        try:
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                return
            mtime = os.path.getmtime(folder_path)
            cached = self._folder_previews_cache.get(folder_path)
            if cached and cached.get("mtime") == mtime:
                previews = list(cached.get("previews") or [])
            else:
                previews = self._find_folder_previews(folder_path, token=token)
                if token != self._folder_stats_worker_token:
                    return
                self._folder_previews_cache[folder_path] = {
                    "previews": list(previews),
                    "mtime": mtime,
                }
            if token == self._folder_stats_worker_token and previews:
                self.folderPreviewsCalculated.emit(
                    os.path.normpath(folder_path),
                    previews,
                )
        except Exception:
            pass

    def _batch_calculate_folder_stats(self, paths: list, token: int, preview_paths: Optional[list] = None):
        # Resolve lightweight folder previews first so folder cards show artwork
        # within milliseconds instead of waiting for full recursive size scans.
        for p in (preview_paths or []):
            if token != self._folder_stats_worker_token:
                return
            self._compute_folder_previews(p, token)
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
            return dict(AppBridgeSignalsMixin._NO_SPACE_INFO)

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

    @Property('QVariantList', notify=AppBridgeSignalsMixin.galleryBookmarksChanged)
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
                    subprocess.Popen(["open", path], **subprocess_env_kwargs())
                else:
                    subprocess.Popen(["xdg-open", path], **subprocess_env_kwargs())
            except Exception as e:
                logger.warning(f"Could not open file in system: {e}", category="system")

    @Slot(str, result=str)
    def pathToUrl(self, local_path: str) -> str:
        """Convert local filesystem path to QUrl string for QML components."""
        if not local_path:
            return ""
        from PySide6.QtCore import QUrl
        return QUrl.fromLocalFile(os.path.abspath(local_path)).toString()
