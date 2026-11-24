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
from core.file_order import name_sort_key, normalize_file_order, order_files
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



class GalleryRenameMixin(AppBridgeSignalsMixin):
    @Slot(str, result=int)
    def detectNextIndex(self, folder_path: str) -> int:
        """
        Scan folder for existing numbered files and detect the next sequential index.
        E.g., if files end or contain 100, returns 101.
        Filters out non-media binaries (.dll, .exe, etc.), architecture codes (x64, x86), and version numbers.
        If current folder is a numbered volume/chapter, safely checks the previous numbered sibling volume.
        If no numbers found anywhere, returns 1.
        """
        if not folder_path or not os.path.exists(folder_path):
            return 1

        VALID_MEDIA_EXTS = {
            '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.avif', '.heic', '.tiff', '.svg',
            '.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v', '.flv', '.wmv',
            '.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus',
            '.zip', '.cbz', '.cbr', '.rar', '.7z', '.tar', '.gz', '.pdf', '.txt', '.epub'
        }

        def extract_sequence_number(name: str, is_dir: bool = False):
            base, ext = os.path.splitext(name)
            if not is_dir:
                if ext.lower() not in VALID_MEDIA_EXTS and not base.isdigit():
                    return None
            # Filter out system architectures and video resolutions (e.g. x64, x86, 1080p, 720p, 4k)
            if re.search(r'\b(?:x86|x64|win32|win64|amd64|arm64|1080p|720p|4k|2160p|480p)\b', base, re.I) or base.lower() in ('x64', 'x86', 'win64', 'win32'):
                return None
            # Avoid dotted version numbers like 8.0.23.53103 or IP addresses
            if re.search(r'\d+\.\d+', base):
                return None
            # 1. Pure digits: '001', '100'
            if base.isdigit():
                val = int(base)
                return val if 0 < val < 10000 else None
            # 2. Number separated by separator or brackets: 'img_100', 'page-100', 'photo 100', 'art (100)'
            m = re.search(r'[\s_\-\(\[\{](\d+)\s*[\)\]\}]?$', base)
            if m:
                val = int(m.group(1))
                return val if 0 < val < 10000 else None
            # 3. Leading sequence number: '001_img', '100 - photo'
            m = re.search(r'^(\d+)[\s_\-\)\]\}]', base)
            if m:
                val = int(m.group(1))
                return val if 0 < val < 10000 else None
            # 4. Standard series keyword with number: 'Ch10', 'Vol2', 'Part3'
            m = re.search(r'(?:ch(?:apter)?|vol(?:ume)?|part|season|folder|set|page)?[\s_\-\#\[\(]?(\d+)$', base, re.I)
            if m:
                val = int(m.group(1))
                return val if 0 < val < 10000 else None
            return None

        def extract_max_from_dir(dpath: str) -> int:
            if not os.path.isdir(dpath):
                return 0
            candidate_numbers = []
            try:
                for entry in os.scandir(dpath):
                    if entry.is_file():
                        num = extract_sequence_number(entry.name, is_dir=False)
                        if num is not None:
                            candidate_numbers.append(num)
            except Exception:
                pass
            return max(candidate_numbers) if candidate_numbers else 0

        # 1. Scan files directly in folder_path
        max_num = extract_max_from_dir(folder_path)
        if max_num > 0:
            return max_num + 1

        # 2. If folder_path has no files with numbers, check subfolders within folder_path
        try:
            sub_candidates = []
            for entry in os.scandir(folder_path):
                if entry.is_dir():
                    num = extract_sequence_number(entry.name, is_dir=True)
                    if num is not None:
                        sub_candidates.append(num)
            if sub_candidates:
                return max(sub_candidates) + 1
        except Exception:
            pass

        # 3. Check sibling ONLY if parent is not root/desktop/downloads and folder shares a series prefix
        try:
            norm_p = os.path.normpath(os.path.abspath(folder_path))
            parent = os.path.dirname(norm_p)
            cur_name = os.path.basename(norm_p)

            user_home = os.path.expanduser('~')
            skip_parents = {
                os.path.normcase(user_home),
                os.path.normcase(os.path.join(user_home, 'Desktop')),
                os.path.normcase(os.path.join(user_home, 'Downloads')),
                os.path.normcase(os.path.join(user_home, 'Documents')),
                os.path.normcase(os.path.dirname(user_home))
            }
            if os.path.splitdrive(norm_p)[1] in ('\\', '/', ''):
                skip_parents.add(os.path.normcase(parent))

            if os.path.normcase(parent) not in skip_parents and parent and os.path.isdir(parent):
                m_cur = re.search(r'^(.*?)(\d+)\s*$', cur_name)
                if m_cur:
                    prefix = m_cur.group(1).lower()
                    cur_num = int(m_cur.group(2))
                    siblings = []
                    for entry in os.scandir(parent):
                        if entry.is_dir():
                            m_sib = re.search(r'^(.*?)(\d+)\s*$', entry.name)
                            if m_sib and m_sib.group(1).lower() == prefix:
                                siblings.append((int(m_sib.group(2)), entry.path))
                    siblings.sort(key=lambda x: x[0])
                    prev_siblings = [path for num, path in siblings if num < cur_num]
                    if prev_siblings:
                        prev_max = extract_max_from_dir(prev_siblings[-1])
                        if prev_max > 0:
                            return prev_max + 1
        except Exception:
            pass

        return 1

    @Slot(str, 'QVariantList', str, str, str, str, str, str, result='QVariantList')
    @Slot(str, 'QVariantList', str, str, str, str, str, str, int, result='QVariantList')
    @Slot(str, 'QVariantList', str, str, str, str, str, str, int, bool, result='QVariantList')
    @Slot(str, 'QVariantList', str, str, str, str, str, str, int, bool, bool, result='QVariantList')
    @Slot(str, 'QVariantList', str, str, str, str, str, str, int, bool, bool, str, result='QVariantList')
    def previewBatchRename(
        self,
        folder_path: str,
        files: list,
        pattern: str = "{name}.{ext}",
        find_text: str = "",
        replace_text: str = "",
        prefix: str = "",
        suffix: str = "",
        case_mode: str = "keep",
        start_index: int = 1,
        include_subfolders: bool = False,
        move_to_folder: bool = False,
        destination_folder: str = ""
    ) -> list:
        """
        Preview batch renaming results for files with metadata variable interpolation.
        Supports variables: {name}, {ext}, {artist}, {title}, {captionText}, {caption}, {post_id}, {date}, {index}, {0index}, {00index}, {000index}.
        Supports custom start index, cross-folder continuous numbering, and moving/flattening to folder.
        """
        if not folder_path or not os.path.exists(folder_path):
            return []

        folder_name = os.path.basename(os.path.normpath(folder_path))
        parent_folder_name = os.path.basename(os.path.dirname(os.path.normpath(folder_path)))

        def natural_sort_key(s):
            return name_sort_key(str(s if s is not None else ""))

        if include_subfolders:
            collected = []
            for root_dir, dirs, filenames in os.walk(folder_path):
                dirs.sort(key=natural_sort_key)
                filenames.sort(key=natural_sort_key)
                for fn in filenames:
                    collected.append({
                        "name": fn,
                        "path": os.path.join(root_dir, fn)
                    })
            files = collected
        elif not files:
            try:
                files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
            except OSError:
                return []
            try:
                files = sorted(files, key=natural_sort_key)
            except Exception:
                pass
        else:
            try:
                def file_sort_val(x):
                    if isinstance(x, dict):
                        return x.get("path", x.get("name", ""))
                    return str(x)
                files = sorted(files, key=lambda x: natural_sort_key(file_sort_val(x)))
            except Exception:
                pass

        dest_dir = destination_folder.strip() if (destination_folder and destination_folder.strip()) else folder_path
        results = []
        new_names_seen = {}
        info_records_cache = {}

        try:
            start_idx = max(0, int(start_index))
        except (ValueError, TypeError):
            start_idx = 1

        for idx, item in enumerate(files, start=start_idx):
            if isinstance(item, dict):
                filename = item.get("name", "")
                filepath = item.get("path", os.path.join(folder_path, filename))
            else:
                filename = str(item)
                filepath = os.path.join(folder_path, filename) if not os.path.isabs(filename) else filename
                filename = os.path.basename(filepath)

            base_name, ext = os.path.splitext(filename)
            raw_ext = ext.lstrip(".").lower()

            item_dir = os.path.dirname(filepath)
            item_folder_name = os.path.basename(item_dir)

            # Metadata extraction
            artist_match = re.search(r'\[([^\]]+)\]', base_name)
            if not artist_match:
                artist_match = re.search(r'\[([^\]]+)\]', item_folder_name)
            if not artist_match:
                artist_match = re.search(r'\[([^\]]+)\]', folder_name)
            artist = artist_match.group(1).strip() if artist_match else (item_folder_name if item_folder_name else (folder_name if folder_name else parent_folder_name))

            post_id_match = re.search(r'(?<!\d)(\d{5,10})(?!\d)', base_name)
            if not post_id_match:
                post_id_match = re.search(r'(?<!\d)(\d{5,10})(?!\d)', item_folder_name)
            if not post_id_match:
                post_id_match = re.search(r'(?<!\d)(\d{5,10})(?!\d)', folder_name)
            post_id = post_id_match.group(1) if post_id_match else ""

            try:
                mtime = os.path.getmtime(filepath)
                date_str = time.strftime("%Y-%m-%d", time.localtime(mtime))
            except OSError:
                date_str = time.strftime("%Y-%m-%d")

            cleaned_title = base_name
            if artist_match:
                cleaned_title = cleaned_title.replace(artist_match.group(0), "")
            if post_id:
                cleaned_title = re.sub(rf'\b{post_id}\b', '', cleaned_title)
            cleaned_title = cleaned_title.strip(" -_") or base_name

            # Caption extraction for {captionText} / {caption} tokens
            clean_caption = ""
            info_file = post_info_for_file(item_dir, filename, post_id)
            if not info_file and folder_path and folder_path != item_dir:
                info_file = post_info_for_file(folder_path, filename, post_id)
            if not info_file:
                for candidate_dir in (item_dir, folder_path):
                    if candidate_dir and os.path.isdir(candidate_dir):
                        candidates = post_info_files(candidate_dir, limit=5)
                        if candidates:
                            info_file = candidates[0]
                            break

            if info_file:
                if info_file not in info_records_cache:
                    try:
                        with open(info_file, "r", encoding="utf-8", errors="replace") as f:
                            info_records_cache[info_file] = parse_post_info_content(f.read())
                    except Exception:
                        info_records_cache[info_file] = []
                records = info_records_cache.get(info_file, [])
                matched_record = None
                if post_id:
                    matched_record = next((r for r in records if r.post_id == post_id), None)
                if not matched_record:
                    fn_low = filename.lower()
                    matched_record = next((r for r in records if any(att.lower() == fn_low for att in r.attached_files)), None)
                if not matched_record and len(records) == 1:
                    matched_record = records[0]

                if matched_record:
                    raw_caption = matched_record.content or matched_record.title
                    if raw_caption:
                        raw_caption = re.sub(r'<br\s*/?>', ' ', raw_caption, flags=re.IGNORECASE)
                        raw_caption = re.sub(r'<[^>]+>', ' ', raw_caption)
                        import html as _html
                        raw_caption = _html.unescape(raw_caption)
                        raw_caption = re.sub(r'[\r\n\t]+', ' ', raw_caption)
                        raw_caption = re.sub(r'\s+', ' ', raw_caption).strip()
                        clean_caption = FilterEngine.clean_filesystem_text(raw_caption, max_len=100, fallback="")

            # If info_file not found or caption empty, check JSON metadata sidecars
            if not clean_caption:
                json_candidates = []
                for c_dir in (item_dir, folder_path, os.path.join(item_dir, "Documents"), os.path.join(folder_path, "Documents")):
                    if c_dir and os.path.isdir(c_dir):
                        if post_id:
                            json_candidates.append(os.path.join(c_dir, f"post_{post_id}.json"))
                        json_candidates.append(os.path.join(c_dir, "post_metadata.json"))
                        json_candidates.append(os.path.join(c_dir, f"{base_name}.json"))
                for jc in json_candidates:
                    if os.path.isfile(jc):
                        try:
                            with open(jc, "r", encoding="utf-8", errors="replace") as jf:
                                jdata = json.load(jf)
                                raw_c = jdata.get("captionText") or jdata.get("caption") or jdata.get("raw_content") or jdata.get("content")
                                if raw_c:
                                    raw_c = re.sub(r'<br\s*/?>', ' ', str(raw_c), flags=re.IGNORECASE)
                                    raw_c = re.sub(r'<[^>]+>', ' ', raw_c)
                                    import html as _html
                                    raw_c = _html.unescape(raw_c)
                                    raw_c = re.sub(r'[\r\n\t]+', ' ', raw_c)
                                    raw_c = re.sub(r'\s+', ' ', raw_c).strip()
                                    clean_caption = FilterEngine.clean_filesystem_text(raw_c, max_len=100, fallback="")
                                    if clean_caption:
                                        break
                        except Exception:
                            pass

            if not clean_caption:
                clean_caption = cleaned_title

            working_pattern = pattern if pattern else "{name}.{ext}"
            if not raw_ext:
                working_pattern = working_pattern.replace(".{ext}", "").replace("{ext}", "")

            new_name = working_pattern
            new_name = new_name.replace("{name}", base_name)
            new_name = new_name.replace("{ext}", raw_ext)
            new_name = new_name.replace("{artist}", artist)
            new_name = new_name.replace("{title}", cleaned_title)
            new_name = new_name.replace("{captionText}", clean_caption)
            new_name = new_name.replace("{caption_text}", clean_caption)
            new_name = new_name.replace("{caption}", clean_caption)
            new_name = new_name.replace("{post_id}", post_id)
            new_name = new_name.replace("{date}", date_str)
            new_name = new_name.replace("{index}", str(idx))
            new_name = new_name.replace("{0index}", f"{idx:02d}")
            new_name = new_name.replace("{00index}", f"{idx:03d}")
            new_name = new_name.replace("{000index}", f"{idx:04d}")

            if find_text:
                new_name = new_name.replace(find_text, replace_text)

            if prefix or suffix:
                n_base, n_ext = os.path.splitext(new_name)
                new_name = f"{prefix}{n_base}{suffix}{n_ext}"

            if case_mode == "lower":
                n_base, n_ext = os.path.splitext(new_name)
                new_name = f"{n_base.lower()}{n_ext.lower()}"
            elif case_mode == "upper":
                n_base, n_ext = os.path.splitext(new_name)
                new_name = f"{n_base.upper()}{n_ext.lower()}"
            elif case_mode == "title":
                n_base, n_ext = os.path.splitext(new_name)
                new_name = f"{n_base.title()}{n_ext.lower()}"

            sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', new_name).strip(" .")
            if not sanitized_name:
                sanitized_name = filename

            if move_to_folder:
                new_filepath = os.path.join(dest_dir, sanitized_name)
            else:
                new_filepath = os.path.join(item_dir, sanitized_name)

            norm_dest = os.path.normcase(os.path.normpath(new_filepath))
            norm_src = os.path.normcase(os.path.normpath(filepath))

            status = "ready"
            err = ""

            if norm_dest == norm_src:
                status = "unchanged"
            elif norm_dest in new_names_seen:
                status = "collision"
                err = f"Duplicates another planned file: {sanitized_name}"
            elif os.path.exists(new_filepath) and norm_dest != norm_src:
                status = "collision"
                err = f"File already exists on disk: {sanitized_name}"

            new_names_seen[norm_dest] = filepath

            results.append({
                "old_name": filename,
                "new_name": sanitized_name,
                "old_path": filepath,
                "new_path": new_filepath,
                "status": status,
                "error": err,
                "valid": status in ("ready", "unchanged"),
                "is_move": move_to_folder and (os.path.normcase(os.path.dirname(filepath)) != os.path.normcase(dest_dir))
            })

        return results

    @Slot('QVariantList', result='QVariantMap')
    def executeBatchRename(self, plan: list) -> dict:
        """Execute a batch renaming/moving plan safely with two-phase rename for circular collisions."""
        import uuid
        import shutil
        renamed = 0
        failed = 0
        errors = []
        done = []          # (old, new) of every rename, for the log

        to_rename = [item for item in plan if item.get("status") == "ready" and item.get("valid", True)]
        if not to_rename:
            return {"success": True, "renamed": 0, "failed": 0, "errors": []}

        temp_renames = []
        for item in to_rename:
            src = os.path.normpath(item["old_path"])
            dst = os.path.normpath(item["new_path"])
            safety_src = self.getPathSafetyInfo(src)
            safety_dst = self.getPathSafetyInfo(dst)
            if safety_src.get("is_blocked") or safety_src.get("is_drive_root") or safety_dst.get("is_blocked") or safety_dst.get("is_drive_root"):
                failed += 1
                errors.append(f"Batch rename blocked on system/root path: {os.path.basename(src)}")
                continue

            if not os.path.exists(src):
                failed += 1
                errors.append(f"Source file not found: {os.path.basename(src)}")
                continue

            dst_dir = os.path.dirname(dst)
            if not os.path.exists(dst_dir):
                try:
                    os.makedirs(dst_dir, exist_ok=True)
                except Exception as e:
                    failed += 1
                    errors.append(f"Cannot create destination directory {dst_dir}: {e}")
                    continue

            needs_temp = False
            if os.path.normcase(src) == os.path.normcase(dst):
                needs_temp = True
            elif os.path.exists(dst):
                needs_temp = True

            if needs_temp:
                temp_path = f"{src}.tmp_batch_{uuid.uuid4().hex[:6]}"
                try:
                    shutil.move(src, temp_path)
                    temp_renames.append((temp_path, dst, src))
                except Exception as e:
                    failed += 1
                    errors.append(f"Cannot temp-rename {os.path.basename(src)}: {e}")
            else:
                try:
                    shutil.move(src, dst)
                    renamed += 1
                    done.append((src, dst))
                except Exception as e:
                    failed += 1
                    errors.append(f"Cannot rename {os.path.basename(src)}: {e}")

        for temp_src, final_dst, orig_src in temp_renames:
            try:
                os.makedirs(os.path.dirname(final_dst), exist_ok=True)
                shutil.move(temp_src, final_dst)
                renamed += 1
                done.append((orig_src, final_dst))
            except Exception as e:
                failed += 1
                errors.append(f"Cannot finalize rename to {os.path.basename(final_dst)}: {e}")
                try:
                    shutil.move(temp_src, orig_src)
                except Exception as back_err:
                    # The file is now only reachable under its temporary name: say exactly where
                    errors.append(f"Couldn't restore the original name either; the file is at {temp_src} ({back_err})")
                    logger.error(f"Batch rename left a file under a temporary name: {temp_src}", category="gallery",
                                 details=f"original name: {orig_src}\nintended name: {final_dst}\n{back_err!r}")

        if done:
            logger.info(f"Batch rename: renamed {renamed} item(s).", category="gallery",
                        details="\n".join(f"{a}  ->  {b}" for a, b in done))
        if errors:
            logger.warning(f"Batch rename: {failed} item(s) couldn't be renamed.", category="gallery",
                           details="\n".join(errors))

        return {
            "success": failed == 0,
            "renamed": renamed,
            "failed": failed,
            "errors": errors
        }
