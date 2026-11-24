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



class QueueCloudMixin(AppBridgeSignalsMixin):
    @Slot()
    def exportAllLinks(self):
        # In links-only mode, export the harvested external cloud links
        harvested = self.downloader.harvested_links
        if harvested:
            save_path, _ = _app_bridge_mod().QFileDialog.getSaveFileName(
                None,
                "Export Harvested Links",
                os.path.join(self._download_dir, "harvested_links.txt"),
                "Text Files (*.txt);;All Files (*)"
            )
            if not save_path:
                return

            lines = [
                f"Kemono Downloader — Harvested External Links",
                f"Exported: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 60,
                "",
            ]
            total = 0
            for platform, urls in sorted(harvested.items()):
                lines.append(f"[{platform.upper()}]  ({len(urls)} link(s))")
                for u in urls:
                    lines.append(f"  {u}")
                    total += 1
                lines.append("")
            lines.append(f"Total: {total} unique link(s)")

            payload = "\n".join(lines)

            def _write_harvested():
                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(payload)
                    logger.success(f"🔗 Exported {total} harvested link(s) to: {save_path}", category="session")
                except Exception as e:
                    logger.error(f"Failed to export harvested links: {e}", category="session")

            threading.Thread(target=_write_harvested, daemon=True, name="ExportHarvestedLinks").start()
            return

        # Fallback: export raw download task URLs from the queue
        tasks = self._queue_model.getTasks()
        if not tasks:
            logger.warning("No harvested links or queued tasks to export.", category="session")
            return

        links = [t.url for t in tasks]
        save_path, _ = _app_bridge_mod().QFileDialog.getSaveFileName(
            None,
            "Export Links",
            os.path.join(self._download_dir, "links_export.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        if save_path:
            threading.Thread(
                target=self.session_manager.export_links_to_file,
                args=(links, save_path),
                daemon=True,
                name="ExportQueueLinks",
            ).start()

    @Slot("QVariantList", str)
    def startCloudDownloads(self, selected_links: list, dest_folder: str = ""):
        """Downloads selected harvested cloud links (Mega, Drive, Dropbox, GoFile) with live progress telemetry."""
        if self._is_cloud_downloading or self._is_downloading:
            logger.warning("Download process is already running!", category="system")
            return

        if not selected_links:
            logger.warning("No links selected for cloud download.", category="downloader")
            return

        base_dir = dest_folder.strip() or self._download_dir
        os.makedirs(base_dir, exist_ok=True)

        self._is_cloud_downloading = True
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self._cloud_cancel_event.clear()
        self._cloud_pause_event.clear()

        def _worker():
            total = len(selected_links)
            concurrency = min(total, max(1, self._threads_count))
            logger.info(f"☁️ Starting concurrent cloud downloads for {total} link(s) ({concurrency} parallel streams) to: {base_dir}", category="downloader")
            self._status_text = f"Cloud Download: 0/{total} completed"
            self.statusTextChanged.emit()

            filter_opts = self._get_filter_options()

            # Index harvested records by URL to recover any post metadata (tags, service, creator, title, post_id)
            harvested_map = {}
            for r in getattr(self.downloader, "harvested_links_records", []):
                if isinstance(r, dict) and r.get("url"):
                    harvested_map[r["url"]] = r

            success_count = 0
            start_time = time.time()
            total_downloaded_bytes = 0
            progress_lock = threading.Lock()
            last_calc_time = time.time()
            last_calc_bytes = 0
            link_progress_map = {}

            def _process_link(idx, item):
                nonlocal success_count, total_downloaded_bytes, last_calc_time, last_calc_bytes
                if self._cloud_cancel_event.is_set():
                    return False

                url = item.get("url", "") if isinstance(item, dict) else str(item)
                record = harvested_map.get(url, {})
                title = (item.get("title") if isinstance(item, dict) else None) or record.get("title") or "Cloud File"
                platform = (item.get("platform") if isinstance(item, dict) else None) or record.get("platform") or "other"
                creator = (item.get("creator") if isinstance(item, dict) else None) or record.get("creator") or ""
                service = (item.get("service") if isinstance(item, dict) else None) or record.get("service") or ""
                tags = (item.get("tags") if isinstance(item, dict) else None) or record.get("tags") or []
                post_id = (item.get("post_id") if isinstance(item, dict) else None) or record.get("post_id") or ""
                content = (item.get("content") if isinstance(item, dict) else None) or record.get("content") or ""

                if "mega.nz" in url or "mega.co.nz" in url or "mega.io" in url:
                    platform = "mega"
                elif "drive.google.com" in url or "docs.google.com" in url or "drive.usercontent.google.com" in url:
                    platform = "gdrive"
                elif "dropbox.com" in url:
                    platform = "dropbox"
                elif "gofile.io" in url:
                    platform = "gofile"

                # Check post-level filters (character whitelist & skip words)
                if filter_opts.characters or (filter_opts.skip_words and filter_opts.skip_scope in ("posts", "both")):
                    fake_post = {"title": title, "tags": tags, "id": post_id, "content": content}
                    keep_post, reason = FilterEngine.should_keep_post(fake_post, filter_opts)
                    if not keep_post:
                        logger.info(f"☁️ Skipping cloud link for '{title}': {reason}", category="filter")
                        return True

                # Determine target folder hierarchy
                folder_parts = [base_dir]

                # Franchise -> Character hierarchy if Character Sorting is enabled
                if self._separate_folders_by_known:
                    cloud_filenames = [os.path.basename(url.split("?")[0])] if url else []
                    creator_prof = None
                    if getattr(self, "archive_manager", None) and self.archive_manager.is_enabled:
                        creator_prof = self.archive_manager.get_creator_character_profile(
                            service=service,
                            creator_id=creator,
                            creator_name=creator,
                            base_dirs=[base_dir]
                        )
                    matched_hierarchy = self.known_manager.find_matching_hierarchy(
                        title, tags=tags, filenames=cloud_filenames, content=content, creator_profile=creator_prof
                    )
                    if matched_hierarchy:
                        franchise, char_name = matched_hierarchy
                        if franchise and franchise.strip() and franchise not in ("Other", "General"):
                            clean_fr = FilterEngine.clean_filesystem_text(franchise, max_len=60, fallback="Franchise")
                            folder_parts.append(clean_fr)
                        if char_name and char_name.strip() and char_name.lower() != (franchise or "").lower():
                            clean_ch = FilterEngine.clean_filesystem_text(char_name, max_len=60, fallback="Character")
                            folder_parts.append(clean_ch)
                    else:
                        folder_parts.append("Other")

                # Creator subfolder
                creator_clean = FilterEngine.clean_filesystem_text(creator, max_len=80, fallback="") if creator else ""
                if creator_clean:
                    if service:
                        folder_parts.append(os.path.basename(pick_creator_folder(os.path.join(*folder_parts), creator_clean, service)))
                    else:
                        folder_parts.append(creator_clean)

                # Post subfolder
                if self._subfolder_per_post and title and title not in ("Cloud File", "Untitled"):
                    clean_title = FilterEngine.clean_filesystem_text(title, max_len=100, fallback="Untitled")
                    folder_parts.append(clean_title)

                target_dir = os.path.join(*folder_parts)
                os.makedirs(target_dir, exist_ok=True)

                logger.info(f"☁️ [{platform.upper()}] Starting ({idx}/{total}) -> {target_dir}: {url}", category="downloader")

                def _prog(fname, dl, tot, file_idx=1, file_tot=1):
                    nonlocal last_calc_time, last_calc_bytes
                    with progress_lock:
                        link_progress_map[idx] = {
                            "fname": fname,
                            "dl": dl,
                            "tot": tot,
                            "file_idx": file_idx,
                            "file_tot": file_tot,
                            "platform": platform
                        }
                        now = time.time()
                        dt = now - last_calc_time
                        current_total_dl = sum(p["dl"] for p in link_progress_map.values()) + total_downloaded_bytes

                        speed_str = ""
                        eta_str = "--"
                        if dt >= 0.5:
                            d_bytes = max(0, current_total_dl - last_calc_bytes)
                            speed = d_bytes / dt if dt > 0 else 0
                            last_calc_time = now
                            last_calc_bytes = current_total_dl
                            if speed > 1024 * 1024:
                                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                            elif speed > 1024:
                                speed_str = f"{speed / 1024:.0f} KB/s"
                            else:
                                speed_str = f"{speed:.0f} B/s"

                        # Calculate aggregated progress across all links
                        sum_fraction = 0.0
                        for l_idx in range(1, total + 1):
                            if l_idx in link_progress_map:
                                p = link_progress_map[l_idx]
                                f_tot = p["file_tot"]
                                f_idx = p["file_idx"]
                                f_dl = p["dl"]
                                f_t = p["tot"]
                                f_frac = (f_idx - 1 + (f_dl / f_t if f_t > 0 else 0)) / f_tot if f_tot > 0 else 0
                                sum_fraction += f_frac
                            elif l_idx < idx:
                                sum_fraction += 1.0

                        pct = int((sum_fraction / total) * 100) if total > 0 else 0
                        elapsed_sec = int(now - start_time)
                        elapsed_str = f"{elapsed_sec}s" if elapsed_sec < 60 else f"{elapsed_sec // 60}m {elapsed_sec % 60}s"
                        saved_mb = current_total_dl / (1024 * 1024)
                        saved_str = f"{saved_mb:.1f} MB" if saved_mb < 1024 else f"{saved_mb / 1024:.2f} GB"

                        if total == 1:
                            files_badge = f"{file_idx}/{file_tot}" if file_tot > 1 else "1/1"
                        else:
                            files_badge = f"{success_count}/{total} links"

                        status_msg = f"[{platform.upper()}] {fname}"
                        if tot > 0:
                            status_msg += f" ({dl // 1024 // 1024}MB / {tot // 1024 // 1024}MB)"

                        self._progressSignal.emit({
                            "percent": max(0, min(100, pct)),
                            "speed_str": speed_str or self._current_speed,
                            "eta_str": eta_str,
                            "saved_str": saved_str,
                            "elapsed_str": elapsed_str,
                            "files_count_text": files_badge,
                            "status_text": status_msg
                        })

                workers_per_link = max(1, min(self._threads_count, 8))
                ok = False

                def _cloud_log(msg):
                    # The cloud downloaders report everything through one callback; ❌ / ⚠ mark problems
                    text = str(msg)
                    if "❌" in text:
                        logger.error(text, category="cloud", details=f"link: {url}")
                    elif "⚠" in text:
                        logger.warning(text, category="cloud", details=f"link: {url}")
                    else:
                        logger.info(text, category="cloud")

                try:
                    if platform == "mega":
                        ok = _app_bridge_mod().download_mega_link(url, target_dir, log_func=_cloud_log, progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, max_workers=workers_per_link, skip_words=filter_opts.skip_words, options=filter_opts)
                    elif platform in ("gdrive", "google drive"):
                        ok = _app_bridge_mod().download_gdrive_link(url, target_dir, log_func=_cloud_log, progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, skip_words=filter_opts.skip_words, options=filter_opts)
                    elif platform == "dropbox":
                        ok = _app_bridge_mod().download_dropbox_link(url, target_dir, log_func=_cloud_log, progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, skip_words=filter_opts.skip_words, options=filter_opts)
                    elif platform == "gofile":
                        ok = _app_bridge_mod().download_gofile_link(url, target_dir, log_func=_cloud_log, progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, max_workers=workers_per_link, skip_words=filter_opts.skip_words, options=filter_opts)
                    else:
                        logger.warning(f"Platform '{platform}' cannot be directly auto-downloaded (URL: {url}).", category="downloader")
                except Exception as ex:
                    logger.exception(f"Error downloading {url}: {ex}", category="cloud")

                if not ok and not self._cloud_cancel_event.is_set():
                    logger.warning(f"☁️ [{platform.upper()}] ({idx}/{total}) didn't finish: {url}", category="cloud")

                with progress_lock:
                    if ok:
                        success_count += 1
                        if idx in link_progress_map:
                            total_downloaded_bytes += link_progress_map[idx].get("tot", 0)

                return ok

            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=concurrency) as link_executor:
                futures = [link_executor.submit(_process_link, idx, item) for idx, item in enumerate(selected_links, 1)]
                for future in as_completed(futures):
                    if self._cloud_cancel_event.is_set():
                        for f in futures:
                            f.cancel()
                        break
                    try:
                        future.result()
                    except Exception:
                        pass

            self._is_cloud_downloading = False
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._overall_progress = 100 if success_count == total else int((success_count / total) * 100)
            self.overallProgressChanged.emit()
            self._status_text = f"Cloud Download completed: {success_count}/{total} succeeded."
            self.statusTextChanged.emit()
            logger.success(f"☁️ Cloud downloads finished: {success_count}/{total} succeeded.", category="downloader")

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def cancelCloudDownloads(self):
        try:
            from services.cloud_downloader import cancel_all_cloud_downloads
            cancel_all_cloud_downloads()
        except Exception:
            pass
        if self._is_cloud_downloading:
            self._cloud_cancel_event.set()
            self._is_cloud_downloading = False
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            logger.warning("Cloud downloads cancellation requested.", category="downloader")

    @Slot()
    def exportLogs(self):
        """Save a copy of this session's full log file (not just what the console panel still shows)."""
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        save_path, _ = _app_bridge_mod().QFileDialog.getSaveFileName(
            None,
            "Export Log",
            os.path.join(self._download_dir, f"Pawchive log {stamp}.log"),
            "Log Files (*.log *.txt);;All Files (*)"
        )
        if not save_path:
            return
        logger.flush()
        session_file = logger.get_current_log_file()
        # The panel's text is read here (window thread); the copy / write runs in the background
        # (a long session's log is many MB)
        text = None if (session_file and os.path.isfile(session_file)) else self._log_model.get_all_text()

        def _write():
            try:
                if text is None:
                    shutil.copyfile(session_file, save_path)
                else:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(text)
                logger.success(f"Log exported to: {save_path}", category="logger")
            except Exception:
                logger.exception("Failed to export the log", category="logger")
        threading.Thread(target=_write, name="LogExport", daemon=True).start()

    @Slot(result=str)
    def exportExtractedLinks(self) -> str:
        """
        Exports extracted external links to a user-chosen text file.
        """
        tasks = self._queue_model.tasks
        if not tasks:
            return ""

        all_text = ""
        for t in tasks:
            if t.url:
                all_text += f"{t.url}\n"

        save_path, _ = _app_bridge_mod().QFileDialog.getSaveFileName(
            None,
            "Export External Links",
            os.path.join(self._download_dir, "extracted_links.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(all_text)
                logger.success(f"Links exported to: {save_path}", category="file")
                return save_path
            except Exception as e:
                logger.error(f"Failed to export links: {e}", category="file")
        return ""

    @Slot(list, result=str)
    def exportFailedTasks(self, selected_file_ids: list = None) -> str:
        """
        Exports failed tasks with direct download links, post links, filenames, and error details
        to a user-chosen text file for manual verification and testing.
        """
        all_failed = [t for t in self._queue_model.tasks if t.status == "failed"]
        if not all_failed:
            logger.warning("No failed tasks to export.", category="session")
            return ""

        if selected_file_ids:
            sel_set = set(str(x) for x in selected_file_ids if x)
            tasks_to_export = [
                t for t in all_failed
                if (t.file_id or t.url or t.filename) in sel_set
            ]
            if not tasks_to_export:
                tasks_to_export = all_failed
        else:
            tasks_to_export = all_failed

        import datetime
        default_name = f"failed_downloads_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        save_path, _ = _app_bridge_mod().QFileDialog.getSaveFileName(
            None,
            "Export Failed Download Links & Post URLs",
            os.path.join(self._download_dir, default_name),
            "Text Files (*.txt);;All Files (*.*)"
        )
        if not save_path:
            return ""

        try:
            lines = [
                "=" * 80,
                "Pawchive Downloader — Failed Downloads Manual Inspection & Links Export",
                f"Export Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Total Failed Tasks Exported: {len(tasks_to_export)}",
                "=" * 80,
                "",
            ]

            from core.parser import canonical_site_url, normalize_archive_url

            def _resolve_task_post_url(t_obj) -> str:
                svc = str(getattr(t_obj, "service", "") or "").strip().lower()
                uid = str(getattr(t_obj, "user_id", "") or getattr(t_obj, "creator_name", "") or "").strip()
                pid = str(getattr(t_obj, "post_id", "") or "").strip()
                raw_p = str(getattr(t_obj, "post_url", "") or "").strip()
                if raw_p:
                    return normalize_archive_url(raw_p, fallback_service=svc, fallback_user_id=uid, fallback_post_id=pid)
                if svc and uid and pid:
                    dom = "cum.st" if (svc in ("onlyfans", "fansly", "candfans") or "cum.st" in str(getattr(t_obj, "url", "")).lower()) else "pawchive.pw"
                    return canonical_site_url(dom, svc, uid, "post", pid)
                return ""

            for idx, t in enumerate(tasks_to_export, 1):
                p_url = _resolve_task_post_url(t)

                lines.append(f"[{idx}] File: {t.filename}")
                lines.append(f"    File Size: {self._queue_model._format_size(t.file_size)}")
                lines.append(f"    Post Title: {t.post_title or 'Untitled'}")
                lines.append(f"    Post ID: {t.post_id or 'N/A'}")
                lines.append(f"    Creator: {t.creator_name or 'Unknown'} [{t.service or 'N/A'}]")
                lines.append(f"    Post Link: {p_url or 'N/A'}")
                lines.append(f"    Direct Download Link: {t.url}")
                lines.append(f"    Target Destination: {t.target_path}")
                lines.append(f"    Error Reason: {t.error_msg or 'Download failed'}")
                lines.append(f"    Retries Attempted: {getattr(t, 'retry_count', 0)}")
                if getattr(t, "fallback_urls", None):
                    lines.append(f"    Alternative Mirror URLs:")
                    for fb in t.fallback_urls[:3]:
                        lines.append(f"      - {fb}")
                lines.append("")

            lines.extend([
                "=" * 80,
                "RAW DIRECT DOWNLOAD URLS (For curl / wget / browser / download manager):",
                "=" * 80,
            ])
            for t in tasks_to_export:
                if t.url:
                    lines.append(t.url)

            lines.extend([
                "",
                "=" * 80,
                "RAW CANONICAL POST URLS (For browser inspection):",
                "=" * 80,
            ])
            post_urls_seen = set()
            for t in tasks_to_export:
                p_url = _resolve_task_post_url(t)
                if p_url and p_url not in post_urls_seen:
                    post_urls_seen.add(p_url)
                    lines.append(p_url)

            lines.append("")

            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            logger.success(f"📤 Exported {len(tasks_to_export)} failed link(s) to: {save_path}", category="session")
            return save_path
        except Exception as e:
            logger.error(f"Failed to export failed links: {e}", category="session")
            return ""

    @Slot(result=str)
    def exportAllFailedTasks(self) -> str:
        """Convenience slot to export all failed tasks without filtering."""
        return self.exportFailedTasks([])

    @Slot()
    def exportQueueState(self):
        """
        Safely freezes active downloads, serializes queue state with human-readable summary,
        and prompts the user whether to keep downloads stopped or resume.
        """
        import datetime
        import json
        was_downloading = self.downloader._is_running and not self.downloader._pause_event.is_set()
        if was_downloading:
            logger.info("Auto-pausing active downloads to safely freeze queue state for export...", category="session")
            self.downloader.pause()
            time.sleep(0.2)  # Allow socket buffers and chunk writers to flush cleanly

        default_name = f"Pawchive_Queue_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_path, _ = _app_bridge_mod().QFileDialog.getSaveFileName(
            None,
            "Export Queue State Snapshot",
            os.path.join(self._download_dir, default_name),
            "JSON Files (*.json);;All Files (*.*)"
        )

        if not save_path:
            # User cancelled the file dialog
            if was_downloading:
                logger.info("Export cancelled — resuming downloads.", category="session")
                self.downloader.resume()
            return

        # Written in the background: a big queue took seconds to serialize on the window thread
        all_tasks = list(self._queue_model.tasks)
        groups = list(self._queue_model.groups)

        def _write():
            try:
                completed_count = sum(1 for t in all_tasks if t.status == "completed")
                failed_count = sum(1 for t in all_tasks if t.status == "failed")
                pending_count = sum(1 for t in all_tasks if t.status in ("pending", "cancelled"))
                downloading_count = sum(1 for t in all_tasks if t.status in ("downloading", "retrying"))

                total_bytes_sum = sum(max(t.file_size, t.downloaded_bytes) for t in all_tasks)
                downloaded_bytes_sum = sum(t.downloaded_bytes for t in all_tasks)
                overall_pct = (downloaded_bytes_sum / total_bytes_sum * 100.0) if total_bytes_sum > 0 else (100.0 if completed_count == len(all_tasks) and all_tasks else 0.0)

                unique_creators = sorted(list(set(t.creator_name for t in all_tasks if t.creator_name)))
                try:
                    from services import update_service as _us
                    app_version = str(_us._read_version_file(_us.get_app_dir()).get("version") or "")
                except Exception:
                    app_version = ""

                snapshot = {
                    "_summary": {
                        "title": "Pawchive Downloader Queue State Backup",
                        "app_version": app_version,
                        "exported_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "creators": unique_creators,
                        "total_batches": len(groups),
                        "total_files": len(all_tasks),
                        "completed_files": completed_count,
                        "pending_files": pending_count + downloading_count,
                        "failed_files": failed_count,
                        "overall_progress": f"{overall_pct:.1f}%",
                        "current_saved_data": self._queue_model._format_size(downloaded_bytes_sum),
                        "total_queue_data": self._queue_model._format_size(total_bytes_sum),
                        "destination_directory": self._download_dir
                    },
                    "settings": {
                        "download_dir": self._download_dir,
                        "threads": self._threads_count,
                        # (no login cookie: exported files get shared, and the cookie is your login)
                        "user_agent": self._user_agent,
                        "manga_mode": self._manga_mode,
                        "subfolder_per_post": self._subfolder_per_post,
                        "date_prefix": self._date_prefix,
                        "file_index_prefix": self._file_index_prefix,
                        "separate_by_known": self._separate_folders_by_known
                    },
                    "batches": groups,
                    "tasks": [t.to_dict() for t in all_tasks]
                }

                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, indent=2, ensure_ascii=False)

                logger.success(f"Queue snapshot exported successfully to: {save_path}", category="session")
                self.exportCompleted.emit(save_path, was_downloading)

            except Exception as e:
                logger.error(f"Failed to export queue state: {e}", category="session")
                if was_downloading:
                    self.downloader.resume()
                self.exportFailed.emit(str(e))

        threading.Thread(target=_write, name="QueueExport", daemon=True).start()

    @Slot()
    def resumeAfterExport(self):
        """Called if user clicks 'Resume Downloading' on the post-export modal."""
        self.downloader.resume()
        self._status_text = "Downloading resumed."
        self.statusTextChanged.emit()
        self.isPausedChanged.emit()

    @Slot()
    def stopAfterExport(self):
        """Called if user clicks 'Keep Stopped / Exit Ready' on the post-export modal."""
        self.downloader.pause()
        self._status_text = "Downloads paused (Safe to exit or shut down)."
        self.statusTextChanged.emit()
        self.isPausedChanged.emit()

    @Slot(str)
    def importQueueState(self, merge_mode: str = "merge"):
        """
        Loads a saved queue snapshot file, verifies existing files on disk,
        and merges or replaces the current queue.
        """
        import json
        file_path, _ = _app_bridge_mod().QFileDialog.getOpenFileName(
            None,
            "Import Queue State Snapshot",
            self._download_dir,
            "JSON Files (*.json);;All Files (*.*)"
        )

        if not file_path:
            return

        # Reading, checking every file on disk and building the tasks run in the background (a big
        # queue file froze the window); the queue itself changes on the window thread
        def _read():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                raw_tasks = data.get("tasks", []) if isinstance(data, dict) else []
                if not isinstance(raw_tasks, list) or not raw_tasks:
                    raise ValueError("The selected JSON file does not contain a valid 'tasks' list.")

                # Where the files were meant to go on the computer that exported the queue
                old_root = ""
                if isinstance(data.get("settings"), dict):
                    old_root = str(data["settings"].get("download_dir") or "")
                if not old_root and isinstance(data.get("_summary"), dict):
                    old_root = str(data["_summary"].get("destination_directory") or "")

                loaded_tasks: List[DownloadTask] = []
                moved_inside = 0
                skipped_links = 0
                for t_dict in raw_tasks:
                    if not isinstance(t_dict, dict):
                        continue
                    task = DownloadTask.from_dict(t_dict)
                    if not re.match(r"^(https?|tg)://", task.url or "", re.IGNORECASE):
                        skipped_links += 1
                        continue
                    safe_path, was_moved = self._safe_import_path(task.target_path, old_root)
                    if not safe_path:
                        skipped_links += 1
                        continue
                    task.target_path = safe_path
                    moved_inside += int(was_moved)
                    self._verify_task_on_disk(task)
                    loaded_tasks.append(task)
                if moved_inside:
                    logger.warning(
                        f"{moved_inside} file(s) in the imported queue pointed outside your download folders; "
                        f"they'll be saved inside {self._download_dir} instead.", category="session")
                if skipped_links:
                    logger.warning(f"{skipped_links} entr(y/ies) in the imported queue had no usable link and were left out.",
                                   category="session")
            except Exception as e:
                logger.error(f"Failed to import queue state: {e}", category="session")
                self.importFailed.emit(str(e))
                return
            self._callOnGui.emit(lambda: _apply(loaded_tasks))

        def _apply(loaded_tasks):
            if merge_mode == "replace":
                self._queue_model.setTasks(loaded_tasks)
                self._active_queue_model.setTasks(loaded_tasks)
                self.downloader.tasks = list(loaded_tasks)
            else:
                # Only files not already queued: the list and the downloader must agree (files the
                # downloader ignored as duplicates used to show up as rows that never downloaded)
                if not self.downloader.tasks and self._queue_model.tasks:
                    self.downloader.tasks = list(self._queue_model.tasks)
                seen = set()
                for t in self.downloader.tasks:
                    seen.add((t.url, t.target_path))
                    if t.file_id:
                        seen.add(t.file_id)
                fresh = []
                for t in loaded_tasks:
                    if (t.url, t.target_path) in seen or (t.file_id and t.file_id in seen):
                        continue
                    seen.add((t.url, t.target_path))
                    if t.file_id:
                        seen.add(t.file_id)
                    fresh.append(t)
                loaded_tasks = fresh
                self._queue_model.appendTasks(loaded_tasks)
                self._active_queue_model.appendTasks(loaded_tasks)
                self.downloader.append_tasks(loaded_tasks)

            creators = set(t.creator_name for t in loaded_tasks if t.creator_name)
            logger.success(
                f"Successfully imported {len(loaded_tasks)} tasks ({len(creators)} creators) from: {os.path.basename(file_path)}",
                category="session"
            )
            self._status_text = f"Imported {len(loaded_tasks)} tasks from backup."
            self.statusTextChanged.emit()
            self.importCompleted.emit(len(loaded_tasks), len(creators))

        threading.Thread(target=_read, name="QueueImport", daemon=True).start()

    def _allowed_download_roots(self) -> List[str]:
        roots = [self._download_dir]
        try:
            from core.storage_pool_manager import storage_pool_manager
            roots.extend(storage_pool_manager.overflow_dirs or [])
        except Exception:
            pass
        try:
            for e in list(self._watchlist_manager.entries):
                roots.extend(d for d in [e.download_dir, *(e.download_dirs or [])] if d)
        except Exception:
            pass
        return [os.path.normpath(os.path.abspath(r)) for r in roots if r]

    def _inside_allowed_root(self, norm: str) -> bool:
        """True when the (normalized, absolute) path is inside one of the download folders. The
        folders are collected once and kept for 30 s, and the path's parent folders are looked up:
        comparing every file of an imported queue with every Watchlist folder took ages for big
        watchlists."""
        cache = getattr(self, "_allowed_roots_cache", None)
        if cache is None or time.monotonic() - cache[0] > 30:
            cache = (time.monotonic(), {os.path.normcase(r) for r in self._allowed_download_roots()})
            self._allowed_roots_cache = cache
        roots = cache[1]
        p = os.path.normcase(norm)
        parent = os.path.dirname(p)
        while parent and parent != p:
            if parent in roots:
                return True
            p, parent = parent, os.path.dirname(parent)
        return False

    def _safe_import_path(self, target_path: str, old_root: str = ""):
        """Where an imported queue file may be saved: (path, pointed_somewhere_unexpected).

        A queue file can come from anywhere, so its paths are never trusted as they are: one could
        otherwise make the app write files into any folder (e.g. the Windows Startup folder).
        Paths inside your download folders are kept; paths under the exporting computer's download
        folder are moved under yours; anything else is placed inside your download folder.
        """
        if not target_path or not self._download_dir:
            return "", False
        from core.filter_engine import FilterEngine
        base = os.path.normpath(os.path.abspath(self._download_dir))

        def _inside(p: str, root: str) -> bool:
            try:
                return os.path.commonpath([os.path.normcase(p), os.path.normcase(root)]) == os.path.normcase(root)
            except ValueError:
                return False

        from core.path_translation import localize_path
        target_path, old_root = localize_path(target_path), localize_path(old_root)   # (from the other system)
        norm = os.path.normpath(os.path.abspath(target_path)) if os.path.isabs(target_path) else ""
        if norm and self._inside_allowed_root(norm):
            return norm, False
        # Rebuild the path from its last folders, cleaned, inside the download folder
        rel = ""
        if old_root and norm:
            old = os.path.normpath(os.path.abspath(old_root))
            if _inside(norm, old) and norm != old:
                rel = os.path.relpath(norm, old)
        parts = [p for p in re.split(r"[\\/]+", rel or target_path) if p and p not in (".", "..") and not p.endswith(":")]
        if not parts:
            return "", False
        if not rel:
            parts = parts[-3:]          # creator / post / file
        clean = [FilterEngine.clean_filesystem_text(p, max_len=150, fallback="file") for p in parts]
        new_path = os.path.normpath(os.path.join(base, *clean))
        if not _inside(new_path, base) or new_path == base:
            return "", False
        return new_path, not rel       # True: the path pointed somewhere unexpected
