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



class GallerySafetySortMixin(AppBridgeSignalsMixin):
    @Slot(str, result='QVariantMap')
    def getPathSafetyInfo(self, path: str) -> dict:
        """
        Analyze path to verify safety for bulk operations like Clean, Delete, Auto-Sort, and Batch Rename.
        Foolproof protection blocking OS drive root, Users folder, Program Files, Python installations,
        and Windows/application directories on the system drive.

        Answers are kept for 30 s: QML bindings ask on every folder change and repaint, and the check
        touches the disk (slow on network drives).
        """
        cache = _app_bridge_mod()._PATH_SAFETY_CACHE
        key = path or ""
        hit = cache.get(key)
        now = time.monotonic()
        if hit and now - hit[0] < 30.0:
            return dict(hit[1])
        info = type(self)._path_safety_info(self, path)
        if len(cache) > 500:
            cache.clear()
        cache[key] = (now, info)
        return dict(info)

    def _path_safety_info(self, path: str) -> dict:
        if not path or not path.strip():
            return {
                "is_blocked": True,
                "is_system_root": False,
                "is_system_dir": False,
                "is_drive_root": False,
                "is_other_root": False,
                "system_drive": "C:",
                "drive_letter": "",
                "path": "",
                "message": "Empty or invalid folder path."
            }

        norm = os.path.normpath(os.path.abspath(path.strip()))
        norm_case = os.path.normcase(norm)

        # 1. Detect OS System Drive & System Root
        windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or "C:\\Windows"
        system_drive_env = os.environ.get("SystemDrive")
        if not system_drive_env and windir:
            drive_part, _ = os.path.splitdrive(windir)
            system_drive_env = drive_part if drive_part else "C:"
        elif not system_drive_env:
            system_drive_env = "C:"
        system_drive = system_drive_env.upper().rstrip(":") + ":"
        sys_drive_root = system_drive + "\\"
        norm_sys_root = os.path.normcase(os.path.normpath(sys_drive_root))

        drive, tail = os.path.splitdrive(norm)
        drive_letter = drive.upper() if drive else ""
        tail_stripped = tail.strip("\\/")

        if sys.platform == "win32":
            is_drive_root = bool(drive_letter and (tail_stripped == ""))
            is_system_root = is_drive_root and (drive_letter == system_drive)
        else:
            is_drive_root = (norm == "/" or os.path.ismount(norm))
            is_system_root = (norm == "/")

        if is_system_root:
            return {
                "is_blocked": True,
                "is_system_root": True,
                "is_system_dir": False,
                "is_drive_root": True,
                "is_other_root": False,
                "system_drive": system_drive,
                "drive_letter": drive_letter,
                "path": norm,
                "message": f"Operations are permanently disabled on the operating system drive root ({drive_letter}\\) for system stability."
            }

        # 2. Windows system & core OS directories
        if sys.platform == "win32":
            protected_system_dirs = [
                windir,
                os.path.join(sys_drive_root, "Windows"),
                os.path.join(sys_drive_root, "System Volume Information"),
                os.path.join(sys_drive_root, "$Recycle.Bin"),
                os.path.join(sys_drive_root, "Recovery"),
                os.path.join(sys_drive_root, "PerfLogs"),
                os.path.join(sys_drive_root, "Boot"),
                os.path.join(sys_drive_root, "Documents and Settings"),
                os.path.join(sys_drive_root, "MSOCache"),
                os.path.join(sys_drive_root, "Config.Msi"),
                os.path.join(sys_drive_root, "inetpub"),
            ]
            for s_dir in protected_system_dirs:
                p_case = os.path.normcase(os.path.normpath(s_dir))
                if norm_case == p_case or norm_case.startswith(p_case + os.path.sep):
                    return {
                        "is_blocked": True,
                        "is_system_root": False,
                        "is_system_dir": True,
                        "is_drive_root": False,
                        "is_other_root": False,
                        "system_drive": system_drive,
                        "drive_letter": drive_letter,
                        "path": norm,
                        "message": "Operations are permanently disabled on protected operating system directories."
                    }

            # Check for $ prefix on system drive (e.g. $Windows.~BT, $WinREAgent)
            if norm_case.startswith(norm_sys_root) and any(part.startswith("$") for part in norm_case.split(os.path.sep)):
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": "Operations are permanently disabled on Windows system cache/recovery directories."
                }
        else:
            def _blocked(message: str) -> dict:
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": message
                }

            # Removable / extra disks are mounted below these; the disks themselves are allowed
            # (as drive roots, with double confirmation), the folders holding them are not
            mount_parents = ["/media", "/mnt", "/run/media", "/Volumes"]
            protected_unix_dirs = [
                "/bin", "/boot", "/dev", "/etc", "/lib", "/lib32", "/lib64", "/libx32", "/opt",
                "/proc", "/root", "/sbin", "/snap", "/sys", "/usr", "/var",
                "/System", "/Library", "/Applications", "/private", "/cores",
            ]
            for u_dir in protected_unix_dirs:
                if norm == u_dir or norm.startswith(u_dir + "/"):
                    return _blocked(f"Operations are permanently disabled on protected system directory ({u_dir}).")
            if norm == "/run" or (norm.startswith("/run/") and not norm.startswith("/run/media/")):
                return _blocked("Operations are permanently disabled on protected system directory (/run).")

            # Home folders: the same protection Windows gets for C:\Users (this was Windows-only, so
            # Flatten / Auto-sort / Delete / Batch rename could run on /home/<user> or ~/.ssh)
            home = os.path.normpath(os.path.expanduser("~"))
            user_roots = ["/home", "/Users"]
            if norm in user_roots or norm in mount_parents:
                return _blocked(f"Operations are permanently disabled on {norm}, which holds user accounts or disks.")
            if os.path.dirname(norm) in user_roots or norm == home:
                return _blocked("Operations are permanently disabled directly on a home folder to protect its settings "
                                "and hidden folders. Please select a subfolder (such as Downloads or Pictures).")
            for m_parent in ("/media", "/run/media"):
                if os.path.dirname(norm) == m_parent:      # /media/<user>: holds that user's disks
                    return _blocked(f"Operations are permanently disabled on {norm}, which holds mounted disks.")
            in_home = norm.startswith(home + "/") or any(norm.startswith(r + "/") for r in user_roots)
            if in_home:
                for part in norm.split("/"):
                    if part.startswith(".") and part not in (".", ".."):
                        return _blocked(f"Operations are permanently disabled on hidden application configuration folders ({part}).")

        # 3. Program Files & ProgramData (on any drive)
        parts = [p.lower() for p in norm_case.split(os.path.sep)]
        if "program files" in parts or "program files (x86)" in parts or "programdata" in parts or "windowsapps" in parts:
            return {
                "is_blocked": True,
                "is_system_root": False,
                "is_system_dir": True,
                "is_drive_root": False,
                "is_other_root": False,
                "system_drive": system_drive,
                "drive_letter": drive_letter,
                "path": norm,
                "message": "Operations are permanently disabled inside Program Files / ProgramData to protect installed software."
            }

        # 4. Users Directory & Profile Roots
        if sys.platform == "win32":
            users_dir_case = os.path.normcase(os.path.join(sys_drive_root, "Users"))
            if norm_case == users_dir_case:
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": f"Operations are permanently disabled on the Users directory ({drive_letter}\\Users) to protect user account data."
                }

            # Check if target is directly a User profile root (e.g. C:\Users\User or C:\Users\Public)
            if os.path.normcase(os.path.dirname(norm)) == users_dir_case:
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": "Operations are permanently disabled directly on your User Profile home folder to protect profile configuration and system directories. Please select a subfolder (such as Downloads or Pictures)."
                }

            # Inside user directory: AppData, Application Data, Local Settings (except system Temp dir)
            import tempfile
            sys_temp_case = os.path.normcase(os.path.normpath(tempfile.gettempdir()))
            is_temp_dir = (norm_case == sys_temp_case or norm_case.startswith(sys_temp_case + os.path.sep))
            if not is_temp_dir and ("appdata" in parts or "application data" in parts or "local settings" in parts):
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": "Operations are permanently disabled inside AppData to protect application configurations and local data."
                }

            # Inside user directory: dot-configuration folders (.vscode, .cargo, .gemini, etc.)
            if norm_case.startswith(users_dir_case + os.path.sep):
                for part in parts:
                    if part.startswith(".") and part not in (".", ".."):
                        return {
                            "is_blocked": True,
                            "is_system_root": False,
                            "is_system_dir": True,
                            "is_drive_root": False,
                            "is_other_root": False,
                            "system_drive": system_drive,
                            "drive_letter": drive_letter,
                            "path": norm,
                            "message": f"Operations are permanently disabled on hidden application configuration folders ({part})."
                        }

        # 5. Python & Runtime Environment Installations
        for part in parts:
            if part.startswith(("python", "pymanager", "miniconda", "anaconda", "virtualenv", "venv")):
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": "Operations are permanently disabled on Python and runtime environment installations."
                }

        # Check for python executables or venv marker in directory or immediate parent
        check_dirs = [norm]
        parent_dir = os.path.dirname(norm)
        if parent_dir and parent_dir != norm:
            check_dirs.append(parent_dir)
        for cd in check_dirs:
            try:
                if os.path.exists(os.path.join(cd, "python.exe")) or \
                   os.path.exists(os.path.join(cd, "py.exe")) or \
                   os.path.exists(os.path.join(cd, "pyvenv.cfg")) or \
                   os.path.exists(os.path.join(cd, "Scripts", "pip.exe")):
                    return {
                        "is_blocked": True,
                        "is_system_root": False,
                        "is_system_dir": True,
                        "is_drive_root": False,
                        "is_other_root": False,
                        "system_drive": system_drive,
                        "drive_letter": drive_letter,
                        "path": norm,
                        "message": "Operations are permanently disabled on Python and runtime environment installations."
                    }
            except OSError:
                pass

        # 6. Apps, Games, Web Servers, and Tool Directories on System Drive (C:\)
        if sys.platform == "win32" and norm_case.startswith(norm_sys_root):
            rel_to_sys = os.path.relpath(norm, sys_drive_root)
            top_folder = rel_to_sys.split(os.path.sep)[0].lower()

            known_c_app_folders = {
                "games", "xboxgames", "riot games", "steamcmd", "steam", "steamlibrary",
                "epic games", "gog games", "ubisoft", "battle.net",
                "qt", "certbot", "xamp", "xampp", "wamp", "nginx", "apache",
                "tools", "bin", "vcpkg", "mingw", "cygwin", "msys", "llvm",
                "prism hub", "rootline prism"
            }
            if top_folder in known_c_app_folders or top_folder.startswith(("borderless", "app", "game")):
                return {
                    "is_blocked": True,
                    "is_system_root": False,
                    "is_system_dir": True,
                    "is_drive_root": False,
                    "is_other_root": False,
                    "system_drive": system_drive,
                    "drive_letter": drive_letter,
                    "path": norm,
                    "message": f"Operations are permanently disabled on application and game installation directories ({top_folder})."
                }

            # Check if top-level directory on C:\ contains application executables/binaries
            top_abs = os.path.join(sys_drive_root, top_folder)
            safe_c_folders = {
                "downloads", "testdownloads", "test", "tmp", "workspace",
                "media", "data", "backup", "kemono", "pawchive"
            }
            if top_folder not in safe_c_folders:
                try:
                    for item in os.scandir(top_abs):
                        ext = os.path.splitext(item.name)[1].lower()
                        if ext in (".exe", ".dll", ".sys") or item.name.lower().startswith(("uninstall", "unins")):
                            return {
                                "is_blocked": True,
                                "is_system_root": False,
                                "is_system_dir": True,
                                "is_drive_root": False,
                                "is_other_root": False,
                                "system_drive": system_drive,
                                "drive_letter": drive_letter,
                                "path": norm,
                                "message": f"Operations are permanently disabled on application and software directories ({top_folder})."
                            }
                except OSError:
                    pass

        # 7. Other Root Disks (e.g. D:\)
        is_other_root = is_drive_root and not is_system_root
        msg = ""
        if is_other_root:
            where = f"{drive_letter}\\" if sys.platform == "win32" else norm
            msg = f"Target is the root of drive ({where}). Executing operations here affects the entire drive and requires double confirmation."

        return {
            "is_blocked": False,
            "is_system_root": False,
            "is_system_dir": False,
            "is_drive_root": is_drive_root,
            "is_other_root": is_other_root,
            "system_drive": system_drive,
            "drive_letter": drive_letter,
            "path": norm,
            "message": msg
        }

    @Slot(object)
    def _run_on_gui(self, fn) -> None:
        try:
            fn()
        except Exception:
            logger.exception("A background job's last step failed", category="system")

    def _run_async(self, request_id: str, fn, *args) -> None:
        """Runs fn(*args) in a background thread and sends the result to QML with asyncResultReady.
        (Scans that ran on the window thread froze the app on big folders.)"""
        def _job():
            try:
                result = fn(*args)
            except Exception as e:
                logger.error(f"Background task failed: {e}", category="system")
                result = None
            try:
                self.asyncResultReady.emit(request_id, result)
            except RuntimeError:
                pass      # the app is closing
        threading.Thread(target=_job, daemon=True, name=f"async:{request_id[:24]}").start()

    @Slot(str, str, bool)
    def scanBrokenFilesAsync(self, request_id: str, folder_path: str, recursive: bool = False):
        self._run_async(request_id, self.scanBrokenFiles, folder_path, recursive)

    @Slot(str, str, bool)
    def scanDuplicatesAsync(self, request_id: str, folder_path: str, recursive: bool = False):
        self._run_async(request_id, self.scanDuplicates, folder_path, recursive)

    @Slot(str, str, str, bool)
    def autoSortFolderAsync(self, request_id: str, folder_path: str, mode: str = "type", recursive: bool = False):
        self._run_async(request_id, self.autoSortFolder, folder_path, mode, recursive)

    @Slot(str, str)
    def undoFlattenAsync(self, request_id: str, folder_path: str):
        self._run_async(request_id, self.undoFlatten, folder_path)

    @Slot(str, str, 'QVariantList', str, str, str, str, str, str, int, bool, bool, str)
    def previewBatchRenameAsync(self, request_id: str, folder_path: str, files: list, pattern: str,
                                find_text: str, replace_text: str, prefix: str, suffix: str, case_mode: str,
                                start_index: int, include_subfolders: bool, move_to_folder: bool,
                                destination_folder: str):
        self._run_async(request_id, self.previewBatchRename, folder_path, list(files or []), pattern, find_text,
                        replace_text, prefix, suffix, case_mode, start_index, include_subfolders,
                        move_to_folder, destination_folder)

    @Slot(str, str)
    def detectNextIndexAsync(self, request_id: str, folder_path: str):
        self._run_async(request_id, self.detectNextIndex, folder_path)

    @Slot(str, 'QVariantList')
    def executeBatchRenameAsync(self, request_id: str, plan: list):
        self._run_async(request_id, self.executeBatchRename, list(plan or []))

    @Slot(str, result='QVariantMap')
    @Slot(str, 'QVariantList', result='QVariantMap')
    @Slot(str, 'QVariantList', bool, result='QVariantMap')
    def refreshPostMetadata(self, folder_path: str, file_paths: list = None, save_to_documents: bool = False) -> dict:
        """
        Discovers post IDs for files in folder_path, fetches their full post metadata (captions,
        descriptions, tags, published dates) from Pawchive / Kemono APIs, and writes post_info.txt
        and post_metadata.json to disk.
        """
        from core.post_metadata_fetcher import PostMetadataFetcher
        fetcher = PostMetadataFetcher(api_client=self.api_client, archive_manager=self.archive_manager)
        flist = [f.get("path", f.get("name", str(f))) if isinstance(f, dict) else str(f) for f in (file_paths or [])]
        return fetcher.fetch_and_save_metadata(
            folder_path=folder_path,
            file_paths=flist if flist else None,
            save_json=True,
            save_txt=True,
            save_to_documents_subfolder=save_to_documents
        )

    @Slot(str, str)
    @Slot(str, str, 'QVariantList')
    @Slot(str, str, 'QVariantList', bool)
    def refreshPostMetadataAsync(self, request_id: str, folder_path: str, file_paths: list = None, save_to_documents: bool = False):
        self._run_async(request_id, self.refreshPostMetadata, folder_path, list(file_paths or []), save_to_documents)

    @Slot(str, result='QVariantMap')
    @Slot(str, bool, result='QVariantMap')
    def fingerprintVideos(self, folder_path: str, recursive: bool = True) -> dict:
        """
        Scans a directory for existing video files, computes their SHA-256 hashes and media
        signatures, and indexes them into Pawchive's ArchiveManager database to enable file
        recognition and prevent duplicate downloads.
        """
        from core.video_fingerprinter import VideoFingerprinter
        fingerprinter = VideoFingerprinter(archive_manager=self.archive_manager)
        return fingerprinter.fingerprint_and_index(folder_path, recursive=recursive)

    @Slot(str, str)
    @Slot(str, str, bool)
    def fingerprintVideosAsync(self, request_id: str, folder_path: str, recursive: bool = True):
        self._run_async(request_id, self.fingerprintVideos, folder_path, recursive)

    @staticmethod
    def _flatten_log_path(folder_path: str) -> str:
        import hashlib
        from core.path_utils import get_config_dir
        key = hashlib.md5(os.path.normcase(os.path.normpath(os.path.abspath(folder_path))).encode("utf-8")).hexdigest()
        return os.path.join(get_config_dir(), "undo", f"flatten_{key}.json")

    @Slot(str, result=bool)
    def hasFlattenUndo(self, folder_path: str) -> bool:
        return bool(folder_path) and os.path.exists(self._flatten_log_path(folder_path))

    @Slot(str, result='QVariantMap')
    def undoFlatten(self, folder_path: str) -> dict:
        """Moves the files of the last Flatten back into the folders they came from."""
        import json
        import shutil
        log_path = self._flatten_log_path(folder_path)
        if not os.path.exists(log_path):
            return {"moved": 0, "errors": ["There is nothing to undo for this folder."]}
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception as e:
            return {"moved": 0, "errors": [f"The undo record couldn't be read: {e}"]}
        root = os.path.normpath(os.path.abspath(folder_path))
        restored, errors = 0, []
        for src_rel, dst_rel in reversed(log.get("moves", [])):
            src = os.path.normpath(os.path.join(root, src_rel))
            dst = os.path.normpath(os.path.join(root, dst_rel))
            # Never outside the folder, even with an edited record
            if not (src.startswith(root + os.sep) and dst.startswith(root + os.sep)):
                continue
            if not os.path.exists(dst):
                errors.append(f"{dst_rel} is no longer there")
                continue
            if os.path.exists(src):
                errors.append(f"{src_rel} already exists")
                continue
            try:
                os.makedirs(os.path.dirname(src), exist_ok=True)
                shutil.move(dst, src)
                restored += 1
            except Exception as e:
                errors.append(f"Could not move {dst_rel} back: {e}")
        try:
            os.remove(log_path)
        except OSError:
            pass
        logger.info(f"Undo flatten: moved {restored} file(s) back into their folders in {root}.", category="file")
        return {"moved": restored, "errors": errors[:20], "mode": "undo"}

    @Slot(str, str, bool, result='QVariantMap')
    @Slot(str, str, result='QVariantMap')
    def autoSortFolder(self, folder_path: str, mode: str = "type", recursive: bool = False) -> dict:
        """
        Auto-organize files in a folder into clean subfolder hierarchies by type, date, or extension.
        When recursive=True, recursively organizes loose attachments inside every post subfolder
        (e.g. Creator/[Post 1]/Images/, Creator/[Post 2]/Videos/) without re-downloading.
        """
        import shutil
        if not folder_path or not os.path.exists(folder_path):
            return {"moved": 0, "errors": ["Folder does not exist"]}

        safety = self.getPathSafetyInfo(folder_path)
        if safety.get("is_blocked"):
            return {
                "moved": 0,
                "errors": [safety.get("message") or "Operation blocked on system root or protected folders."]
            }

        norm_root = os.path.normpath(os.path.abspath(folder_path))
        moved = 0
        errors = []

        # ── Mode: Dump / Flatten (Move everything into root folder) ──────────
        if mode in ("dump", "flatten"):
            undo_moves = []
            try:
                for root_dir, dirs, files in os.walk(norm_root, topdown=False):
                    if os.path.normcase(root_dir) == os.path.normcase(norm_root):
                        continue
                    for fname in files:
                        src = os.path.normpath(os.path.join(root_dir, fname))
                        base, ext = os.path.splitext(fname)
                        target_file = os.path.normpath(os.path.join(norm_root, fname))

                        if os.path.exists(target_file) and os.path.normcase(src) != os.path.normcase(target_file):
                            counter = 1
                            while True:
                                target_file = os.path.normpath(os.path.join(norm_root, f"{base} ({counter}){ext}"))
                                if not os.path.exists(target_file):
                                    break
                                counter += 1

                        try:
                            shutil.move(src, target_file)
                            moved += 1
                            undo_moves.append([os.path.relpath(src, norm_root), os.path.relpath(target_file, norm_root)])
                        except Exception as e:
                            errors.append(f"Could not move {fname}: {e}")

                # Clean up empty subdirectories left behind
                for root_dir, dirs, files in os.walk(norm_root, topdown=False):
                    if os.path.normcase(root_dir) == os.path.normcase(norm_root):
                        continue
                    try:
                        os.rmdir(root_dir)
                    except OSError:
                        pass
            except Exception as e:
                errors.append(f"Flatten/dump error: {e}")

            # A record of every move, so the flatten can be undone (it couldn't be before)
            if undo_moves:
                try:
                    from core.atomic_io import atomic_write_json
                    atomic_write_json(self._flatten_log_path(norm_root),
                                      {"folder": norm_root, "created": time.time(), "moves": undo_moves})
                    logger.info(f"Flatten: moved {moved} file(s) into {norm_root} (can be undone).", category="file")
                except Exception as e:
                    logger.warning(f"Flatten: couldn't save the undo record: {e}", category="file")
            return {"moved": moved, "errors": errors, "mode": "flatten", "undo_available": bool(undo_moves)}

        type_map = {
            "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico"},
            "video": {".mp4", ".mkv", ".webm", ".mov", ".avi", ".ts", ".flv", ".m4v"},
            "audio": {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".opus", ".aac"},
            "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
            "document": {".txt", ".pdf", ".json", ".html", ".md", ".epub", ".doc", ".docx"}
        }

        # Names of category folders that shouldn't be nested recursively inside themselves
        PROTECTED_SUBDIR_NAMES = {
            "images", "videos", "audio", "archives", "documents", "other"
        }

        def _sort_single_directory(target_dir_path: str) -> int:
            nonlocal errors
            dir_moved = 0
            try:
                entries = [e for e in os.scandir(target_dir_path) if e.is_file(follow_symlinks=False)]
            except OSError as e:
                errors.append(f"Cannot read {target_dir_path}: {e}")
                return 0

            for entry in entries:
                src = os.path.normpath(entry.path)
                fname = entry.name
                base, ext = os.path.splitext(fname)
                ext_lower = ext.lower()

                if mode == "date":
                    try:
                        mtime = entry.stat().st_mtime
                        sub_name = time.strftime("%Y-%m", time.localtime(mtime))
                    except OSError:
                        sub_name = "Unknown_Date"
                elif mode == "extension":
                    sub_name = ext_lower.lstrip(".").upper() or "NO_EXT"
                else:
                    sub_name = "Other"
                    for cat, extensions in type_map.items():
                        if ext_lower in extensions:
                            sub_name = cat.capitalize() + "s" if cat in ("image", "video", "archive", "document") else "Audio"
                            break

                dest_dir = os.path.join(target_dir_path, sub_name)
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except OSError as e:
                    errors.append(f"Cannot create directory {sub_name} in {target_dir_path}: {e}")
                    continue

                target_file = os.path.join(dest_dir, fname)
                if os.path.exists(target_file) and os.path.normcase(src) != os.path.normcase(target_file):
                    counter = 1
                    while True:
                        target_file = os.path.join(dest_dir, f"{base} ({counter}){ext}")
                        if not os.path.exists(target_file):
                            break
                        counter += 1

                try:
                    shutil.move(src, target_file)
                    dir_moved += 1
                except Exception as e:
                    errors.append(f"Could not move {fname}: {e}")

            return dir_moved

        def _is_sort_folder(name: str) -> bool:
            """A folder a sort creates (in any mode): sorting inside it again nested folders."""
            n = name.lower()
            return (n in PROTECTED_SUBDIR_NAMES or n == "unknown_date"
                    or re.fullmatch(r"\d{4}-\d{2}", name) is not None
                    or (mode == "extension" and re.fullmatch(r"[A-Z0-9]{1,10}|NO_EXT", name) is not None))

        # The folders to sort are listed before anything moves, so folders this run creates are skipped
        targets = [norm_root]
        if recursive:
            try:
                for root_dir, dirs, _ in os.walk(norm_root):
                    dirs[:] = [d for d in dirs if not _is_sort_folder(d)]
                    targets.extend(os.path.join(root_dir, d) for d in dirs)
            except Exception as e:
                errors.append(f"Recursive walk error: {e}")

        for target in targets:
            moved += _sort_single_directory(target)

        return {"moved": moved, "errors": errors, "mode": mode}
