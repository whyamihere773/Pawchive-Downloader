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



class GalleryMaintenanceMixin(AppBridgeSignalsMixin):
    @Slot(str, bool, result='QVariantList')
    def scanBrokenFiles(self, folder_path: str, recursive: bool = False) -> list:
        """Scan folder for 0-byte files, incomplete download temp files (.part, .crdownload, etc.), and empty folders."""
        if not folder_path or not os.path.exists(folder_path):
            return []

        safety = self.getPathSafetyInfo(folder_path)
        if safety.get("is_blocked"):
            logger.warning(f"scanBrokenFiles blocked on {folder_path} for system safety")
            return []

        norm_root = os.path.normpath(os.path.abspath(folder_path))
        broken = []
        temp_exts = {".part", ".crdownload", ".~tmp", ".download", ".temp", ".ytdl"}

        if not recursive:
            try:
                for entry in os.scandir(norm_root):
                    try:
                        p = os.path.normpath(entry.path)
                        rel_path = os.path.relpath(p, norm_root)
                        if entry.is_file(follow_symlinks=False):
                            sz = entry.stat().st_size
                            ext = os.path.splitext(entry.name)[1].lower()
                            if sz == 0:
                                broken.append({
                                    "path": p,
                                    "name": entry.name,
                                    "rel_path": rel_path,
                                    "type": "zero_byte",
                                    "type_label": "0-Byte Corrupt File",
                                    "size": 0,
                                    "mtime": entry.stat().st_mtime
                                })
                            elif ext in temp_exts:
                                broken.append({
                                    "path": p,
                                    "name": entry.name,
                                    "rel_path": rel_path,
                                    "type": "temp_file",
                                    "type_label": f"Incomplete Download ({ext})",
                                    "size": sz,
                                    "mtime": entry.stat().st_mtime
                                })
                        elif entry.is_dir(follow_symlinks=False):
                            try:
                                if not os.listdir(p):
                                    broken.append({
                                        "path": p,
                                        "name": entry.name,
                                        "rel_path": rel_path,
                                        "type": "empty_folder",
                                        "type_label": "Empty Directory",
                                        "size": 0,
                                        "mtime": entry.stat().st_mtime
                                    })
                            except OSError:
                                pass
                    except OSError:
                        pass
            except OSError:
                pass
        else:
            try:
                for root, dirs, files in os.walk(norm_root, topdown=False):
                    for d in dirs:
                        dp = os.path.join(root, d)
                        try:
                            if not os.listdir(dp):
                                broken.append({
                                    "path": os.path.normpath(dp),
                                    "name": d,
                                    "rel_path": os.path.relpath(dp, norm_root),
                                    "type": "empty_folder",
                                    "type_label": "Empty Directory",
                                    "size": 0,
                                    "mtime": os.path.getmtime(dp)
                                })
                        except OSError:
                            pass
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            sz = os.path.getsize(fp)
                            ext = os.path.splitext(f)[1].lower()
                            if sz == 0:
                                broken.append({
                                    "path": os.path.normpath(fp),
                                    "name": f,
                                    "rel_path": os.path.relpath(fp, norm_root),
                                    "type": "zero_byte",
                                    "type_label": "0-Byte Corrupt File",
                                    "size": 0,
                                    "mtime": os.path.getmtime(fp)
                                })
                            elif ext in temp_exts:
                                broken.append({
                                    "path": os.path.normpath(fp),
                                    "name": f,
                                    "rel_path": os.path.relpath(fp, norm_root),
                                    "type": "temp_file",
                                    "type_label": f"Incomplete Download ({ext})",
                                    "size": sz,
                                    "mtime": os.path.getmtime(fp)
                                })
                        except OSError:
                            pass
            except OSError:
                pass

        return broken

    @Slot('QVariantList', result='QVariantMap')
    def deleteItems(self, paths: list) -> dict:
        """Move files or folders to the Recycle Bin / Trash so deletions can be undone.

        Never falls back to a permanent delete: items the OS cannot trash
        (e.g. some network drives) are reported as failures instead.
        """
        from PySide6.QtCore import QFile

        deleted = 0
        failed = 0
        errors = []
        trashed = []

        for p in paths:
            if not p:
                continue
            norm_p = os.path.normpath(p)
            safety = self.getPathSafetyInfo(norm_p)
            if safety.get("is_blocked") or safety.get("is_drive_root"):
                failed += 1
                errors.append(f"Deletion blocked for system or root directory: {norm_p}")
                continue
            if not os.path.exists(norm_p):
                failed += 1
                errors.append(f"Target does not exist: {norm_p}")
                continue
            try:
                if QFile.moveToTrash(norm_p):
                    deleted += 1
                    trashed.append(norm_p)
                else:
                    failed += 1
                    errors.append(f"Could not move {os.path.basename(norm_p)} to the Recycle Bin")
            except Exception as e:
                failed += 1
                errors.append(f"Failed deleting {os.path.basename(norm_p)}: {e}")

        if deleted:
            for p in trashed:
                self._invalidate_folder_stats(p)
            logger.info(f"Moved {deleted} item(s) to the Recycle Bin.", category="gallery",
                        details="\n".join(trashed))
        if errors:
            logger.warning(f"{failed} item(s) couldn't be moved to the Recycle Bin.", category="gallery",
                           details="\n".join(errors))

        return {"deleted": deleted, "failed": failed, "errors": errors}

    @Slot('QVariantList', str, result='QVariantMap')
    def moveItems(self, paths: list, destDir: str) -> dict:
        """Move files or folders into destDir, never overwriting an existing item."""
        moved = 0
        failed = 0
        errors = []
        moved_pairs = []   # [source, target] for every item that moved, so it can be undone
        dest = os.path.normpath(destDir or "")
        if not dest or not os.path.isdir(dest):
            return {"moved": 0, "failed": len(paths), "errors": [f"Destination folder does not exist: {destDir}"], "pairs": []}
        dest_safety = self.getPathSafetyInfo(dest)
        if dest_safety.get("is_blocked"):
            return {"moved": 0, "failed": len(paths), "errors": [f"Moving into a protected system folder is blocked: {dest}"], "pairs": []}

        dest_case = os.path.normcase(dest)
        for p in paths:
            if not p:
                continue
            src = os.path.normpath(p)
            safety = self.getPathSafetyInfo(src)
            if safety.get("is_blocked") or safety.get("is_drive_root"):
                failed += 1
                errors.append(f"Move blocked for system or root directory: {src}")
                continue
            if not os.path.exists(src):
                failed += 1
                errors.append(f"Target does not exist: {src}")
                continue
            if os.path.normcase(os.path.dirname(src)) == dest_case:
                continue  # already there
            src_case = os.path.normcase(src)
            if dest_case == src_case or dest_case.startswith(src_case + os.sep):
                failed += 1
                errors.append(f"Cannot move a folder into itself: {os.path.basename(src)}")
                continue
            target = os.path.join(dest, os.path.basename(src))
            if os.path.exists(target):
                failed += 1
                errors.append(f"An item named '{os.path.basename(src)}' already exists in the destination")
                continue
            try:
                shutil.move(src, target)
                moved += 1
                moved_pairs.append([src, target])
            except Exception as e:
                failed += 1
                errors.append(f"Failed moving {os.path.basename(src)}: {e}")

        if moved:
            for a, b in moved_pairs:
                self._invalidate_folder_stats(a)
                self._invalidate_folder_stats(b)
            if getattr(self, "archive_manager", None) and moved_pairs:
                try:
                    old_dirs = list({os.path.dirname(a) for a, _b in moved_pairs})
                    self.archive_manager.relocate_files(old_dirs, [(a, b) for a, b in moved_pairs])
                except Exception as e:
                    logger.debug(f"Archive relocate after moveItems warning: {e}", category="archive")
            logger.info(f"Moved {moved} item(s) to '{dest}'.", category="gallery",
                        details="\n".join(f"{a}  ->  {b}" for a, b in moved_pairs))
        if errors:
            logger.warning(f"{failed} item(s) couldn't be moved to '{dest}'.", category="gallery",
                           details="\n".join(errors))

        return {"moved": moved, "failed": failed, "errors": errors, "pairs": moved_pairs}

    @Slot(str, str, result='QVariantMap')
    def renameItem(self, path: str, newName: str) -> dict:
        """Rename a single file or folder in place."""
        src = os.path.normpath(path or "")
        new_name = (newName or "").strip()
        if not src or not os.path.exists(src):
            return {"success": False, "error": "The item no longer exists.", "new_path": ""}
        if not new_name or new_name in (".", "..") or any(c in new_name for c in '<>:"/\\|?*') or new_name.endswith((".", " ")):
            return {"success": False, "error": "That name contains characters that aren't allowed.", "new_path": ""}
        safety = self.getPathSafetyInfo(src)
        if safety.get("is_blocked") or safety.get("is_drive_root"):
            return {"success": False, "error": "Renaming is blocked for system or root directories.", "new_path": ""}
        dst = os.path.join(os.path.dirname(src), new_name)
        if os.path.normcase(dst) == os.path.normcase(src) and dst == src:
            return {"success": True, "error": "", "new_path": src}
        # A case-only rename points at the same file on Windows, so it is not a collision.
        if os.path.exists(dst) and os.path.normcase(dst) != os.path.normcase(src):
            return {"success": False, "error": f"An item named '{new_name}' already exists here.", "new_path": ""}
        try:
            os.rename(src, dst)
        except Exception as e:
            logger.warning(f"Couldn't rename '{os.path.basename(src)}' to '{new_name}': {e}", category="gallery",
                           details=src)
            return {"success": False, "error": str(e), "new_path": ""}
        self._invalidate_folder_stats(src)
        self._invalidate_folder_stats(dst)
        logger.info(f"Renamed '{os.path.basename(src)}' to '{new_name}'.", category="gallery",
                    details=f"{src}  ->  {dst}")
        return {"success": True, "error": "", "new_path": dst}

    @Slot(str, bool, result='QVariantList')
    def scanDuplicates(self, folder_path: str, recursive: bool = False) -> list:
        """
        Fast two-tier duplicate file finder using size grouping and SHA-256 chunked hashing.
        Returns duplicate groups sorted by wasted storage space descending.
        """
        import hashlib
        if not folder_path or not os.path.exists(folder_path):
            return []

        safety = self.getPathSafetyInfo(folder_path)
        if safety.get("is_blocked"):
            logger.warning(f"scanDuplicates blocked on {folder_path} for system safety")
            return []

        norm_root = os.path.normpath(os.path.abspath(folder_path))
        size_groups = {}

        def register_file(p):
            try:
                sz = os.path.getsize(p)
                if sz > 0:
                    if sz not in size_groups:
                        size_groups[sz] = []
                    size_groups[sz].append(p)
            except OSError:
                pass

        if not recursive:
            try:
                for entry in os.scandir(norm_root):
                    if entry.is_file(follow_symlinks=False):
                        register_file(entry.path)
            except OSError:
                pass
        else:
            try:
                for root, _, files in os.walk(norm_root):
                    for f in files:
                        register_file(os.path.join(root, f))
            except OSError:
                pass

        partial_groups = {}
        for sz, flist in size_groups.items():
            if len(flist) < 2:
                continue
            for p in flist:
                try:
                    with open(p, "rb") as f:
                        header = f.read(65536)
                        p_hash = hashlib.md5(header).hexdigest()
                        key = (sz, p_hash)
                        if key not in partial_groups:
                            partial_groups[key] = []
                        partial_groups[key].append(p)
                except OSError:
                    pass

        duplicate_groups = []
        for (sz, _), flist in partial_groups.items():
            if len(flist) < 2:
                continue
            full_groups = {}
            for p in flist:
                try:
                    h = hashlib.sha256()
                    with open(p, "rb") as f:
                        while chunk := f.read(65536):
                            h.update(chunk)
                    full_hash = h.hexdigest()
                    if full_hash not in full_groups:
                        full_groups[full_hash] = []
                    full_groups[full_hash].append(p)
                except OSError:
                    pass

            for fhash, matches in full_groups.items():
                if len(matches) >= 2:
                    files_info = []
                    for mp in matches:
                        try:
                            mtime = os.path.getmtime(mp)
                        except OSError:
                            mtime = 0
                        files_info.append({
                            "path": os.path.normpath(mp),
                            "name": os.path.basename(mp),
                            "rel_path": os.path.relpath(mp, norm_root),
                            "mtime": mtime
                        })
                    files_info.sort(key=lambda x: x["mtime"])
                    duplicate_groups.append({
                        "hash": fhash[:12],
                        "size": sz,
                        "count": len(files_info),
                        "wasted_size": (len(files_info) - 1) * sz,
                        "files": files_info
                    })

        duplicate_groups.sort(key=lambda g: g["wasted_size"], reverse=True)
        return duplicate_groups
