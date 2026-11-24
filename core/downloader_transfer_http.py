"""
Downloader HTTP Transfer — Mirror Negotiation, Range Resume & Single-Stream Chunk Loop
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import hashlib
import os
import re
import shutil
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.bandwidth_limiter import bandwidth_limiter
from core.downloader_models import (
    DownloadTask,
    PART_SUFFIX,
    UNIMPORTED_TASK_ERROR_MSG,
    _CONTACT_HEADERS,
    _content_range,
    _get_media_candidate_paths,
    _remove_quietly,
    content_hash_from_url,
    is_preview_url,
    needs_full_size_upgrade,
)
from core.filter_engine import FilterEngine, FilterOptions, fit_path_for_windows
from core.logger import logger
from core.providers import cookie_for_url, disabled_message, is_disabled, provider_for_host


class DownloaderTransferHttpMixin:
    """Handles HTTP mirror selection, range resumption, and chunked streaming."""

    def _download_single_file(self, task: DownloadTask, session: Optional[requests.Session] = None, options: Optional[FilterOptions] = None) -> (bool, str):
        if session is None:
            session = self._get_worker_session()
        task_opts = getattr(task, "options", None) or self.get_batch_options(getattr(task, "batch_id", "")) or options or self.current_options or FilterOptions()
        options = task_opts
        if self.is_batch_cancelled(task):
            return False, "Cancelled"

        if self.is_batch_paused(task) or task.status == "paused":
            task.status = "paused"
            task.speed_bps = 0
            task.speed_str = "0 KB/s"
            task.eta_str = "Paused"
            if self.on_task_status_changed:
                self.on_task_status_changed(task)
            return False, "Batch paused by user"

        while self._pause_event.is_set():
            if self.is_batch_cancelled(task):
                return False, "Cancelled"
            if self.is_batch_paused(task) or task.status == "paused":
                return False, "Batch paused by user"
            time.sleep(0.5)

        if self.is_batch_cancelled(task):
            return False, "Cancelled"

        # Non-retryable unimported Pawchive files aren't physically hosted on the server:
        # fail immediately without creating empty directories or making any HTTP requests.
        if getattr(task, "is_unimported", False) and not getattr(task, "is_unimported_preview", False):
            task.status = "failed"
            task.http_status = 404
            task.retry_capped = True
            task.error_msg = task.error_msg or UNIMPORTED_TASK_ERROR_MSG
            if self.on_task_status_changed:
                self.on_task_status_changed(task)
            return False, task.error_msg

        task.target_path = fit_path_for_windows(task.target_path)
        os.makedirs(os.path.dirname(task.target_path), exist_ok=True)
        task.status = "downloading"
        if self.on_task_status_changed:
            self.on_task_status_changed(task)

        force_redownload = bool(getattr(options, "force_redownload", False))
        sync_mode = str(getattr(options, "disk_sync_mode", "all") or "all").lower()
        is_disk_sync = sync_mode in ("missing_or_mismatched", "missing_only", "mismatched_only")
        check_size_mismatch = sync_mode in ("missing_or_mismatched", "mismatched_only")

        def _runtime_disk_mismatched(dpath: str, dsz: int) -> bool:
            if needs_full_size_upgrade(dsz, task.file_size, task.target_path, options, dpath):
                return True
            if not check_size_mismatch or task.file_size <= 0 or dsz == task.file_size:
                return False
            dext = os.path.splitext(dpath)[1].lower()
            if dext == ".webp":
                return False
            if getattr(options, "write_audio_metadata", False) and dext in (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"):
                return False
            return True

        # Check if file is already recorded in download archive database — unless the copy on disk is
        # missing (during Browser disk-sync) or small/mismatched and needs repair/upgrade
        _disk_cands = _get_media_candidate_paths(task.target_path)
        if not force_redownload and self.archive_manager and self.archive_manager.is_enabled:
            _on_disk = next((p for p in _disk_cands if os.path.exists(p) and os.path.getsize(p) > 0), None)
            _upgrade = bool(_on_disk) and _runtime_disk_mismatched(
                _on_disk, os.path.getsize(_on_disk)
            )
            _missing_sync = is_disk_sync and (_on_disk is None)
            if not _upgrade and not _missing_sync and self.archive_manager.is_archived(service=task.service, post_id=task.post_id, file_id=task.file_id, file_hash=task.expected_sha256):
                task.status = "completed"
                task.progress_pct = 100
                task.eta_str = "Done"
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                logger.info(f"📦 Skipping archived file: '{task.filename}' (present in download archive)", category="file",
                            to_file=False)
                with self._lock:
                    self._already_there["in the download archive"] += 1
                return True, "Already archived"

        # Check if file already exists completely on disk (including webp/avif and transcoded video versions)
        found_existing_path = None
        if not force_redownload and not options.keep_duplicates:
            for cand in _disk_cands:
                if os.path.exists(cand) and os.path.getsize(cand) > 0:
                    found_existing_path = cand
                    break

        is_upgrade_download = False
        if found_existing_path:
            existing_disk_sz = os.path.getsize(found_existing_path)
            keep_file, f_reason = FilterEngine.should_keep_file(task.filename, options, file_size=existing_disk_sz)
            if not keep_file:
                logger.info(f"⏭️ Skipping existing file: '{task.filename}' ({FilterEngine.format_size_str(existing_disk_sz)}): {f_reason}", category="filter")
                task.status = "skipped"
                task.error_msg = f_reason
                task.file_size = existing_disk_sz
                task.downloaded_bytes = existing_disk_sz
                task.progress_pct = 100
                task.eta_str = "Skipped"
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                return True, f"Skipped: {f_reason}"

            # Check if this existing file is a low-res thumbnail or size-mismatched file that needs repair
            should_upgrade = _runtime_disk_mismatched(found_existing_path, existing_disk_sz)

            if not should_upgrade:
                if self.is_batch_cancelled(task):
                    return False, "Cancelled"
                task.status = "completed"
                task.downloaded_bytes = existing_disk_sz
                task.file_size = task.downloaded_bytes
                task.progress_pct = 100
                task.eta_str = "Done"
                if self.archive_manager and self.archive_manager.is_enabled:
                    self.archive_manager.record_file(
                        service=task.service,
                        creator_id=task.user_id,
                        post_id=task.post_id,
                        file_id=task.file_id,
                        file_hash=task.expected_sha256,
                        filename=task.filename,
                        creator_name=task.creator_name,
                        post_title=task.post_title,
                        file_size=task.downloaded_bytes,
                        file_path=found_existing_path
                    )
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                logger.info(f"⏳ Skipping existing file: '{task.filename}' (already present on disk)", category="file",
                            to_file=False)
                with self._lock:
                    self._already_there["already on disk"] += 1
                return True, "Already downloaded"
            else:
                is_upgrade_download = True
                logger.info(
                    f"🔄 Upgrading existing '{task.filename}' ({FilterEngine.format_size_str(existing_disk_sz)}) to full-resolution...",
                    category="file"
                )

        # Cross-thread Pawchive request-start pacing is enforced right before each HTTP GET
        # via _wait_pawchive_pace_slot() so aggregate concurrency stays below Pawchive's rate limit.

        # ── yt-dlp embedded media download execution ─────────────────────────
        if task.is_ytdlp:
            return self._download_ytdlp_task(task, options)

        # ── Telegram MTProto media download execution ────────────────────────
        if getattr(task, "is_telegram", False):
            return self._download_telegram_task(task, options)

        # Continue an interrupted download from its .part file (unless forcing a clean redownload)
        part_path = task.target_path + PART_SUFFIX
        if force_redownload and os.path.exists(part_path):
            _remove_quietly(part_path)

        # Zero-HTTP cross-post SHA-256 deduplication: if an identical 64-char SHA-256 file was already
        # verified on disk (e.g. shared between a multi-variant pack post and an individual post),
        # copy it locally in milliseconds without touching the remote storage node.
        download_thumbs_only_early = getattr(options, "download_thumbnails_only", False) if options is not None else False
        if not force_redownload and not download_thumbs_only_early and not is_preview_url(task.url or ""):
            dedup_res = self._try_copy_from_verified_sha256(
                task=task,
                options=options,
                part_path=part_path,
                is_upgrade_download=is_upgrade_download,
                found_existing_path=found_existing_path,
            )
            if dedup_res is not None:
                return dedup_res
        existing_size = 0
        mode = "wb"
        range_headers = {}
        if os.path.exists(part_path):
            existing_size = os.path.getsize(part_path)
            if task.file_size > 0 and existing_size > task.file_size:
                _remove_quietly(part_path)      # bigger than the file itself: not a usable start
                existing_size = 0
            if existing_size > 0:
                range_headers["Range"] = f"bytes={existing_size}-"
                mode = "ab"
                logger.debug(
                    f"  ↪ Resume: {task.filename}  already have {existing_size // 1024}KB",
                    category="file"
                )
        resumed = existing_size > 0

        # Switched-off sites (Kemono / Coomer) are skipped, also for files queued before
        # Automatically migrate any legacy e1.cum.st URLs to the modern cdn.cum.st endpoint
        raw_urls = [task.url] + list(task.fallback_urls)
        all_urls = [
            u.replace("e1.cum.st", "cdn.cum.st")
            for u in raw_urls
            if not is_disabled(u)
        ]
        if task.url and "e1.cum.st" in task.url:
            task.url = task.url.replace("e1.cum.st", "cdn.cum.st")
        task.fallback_urls = [u.replace("e1.cum.st", "cdn.cum.st") for u in task.fallback_urls]
        if not all_urls:
            msg = disabled_message(task.url) or "This file's server is turned off"
            logger.warning(f"  ✖ {task.filename}: {msg}", category="file")
            return False, msg
        allow_thumb_fallback = getattr(options, "fallback_to_thumbnails", False)
        download_thumbs_only = getattr(options, "download_thumbnails_only", False) if options is not None else False

        if download_thumbs_only:
            full_urls, preview_urls = all_urls, []
        else:
            full_urls = [u for u in all_urls if not is_preview_url(u)]
            preview_urls = [u for u in all_urls if is_preview_url(u)]

        # If all candidates are preview/thumbnail URLs and thumbnail fallback is disabled, do not download
        if not full_urls and not download_thumbs_only:
            if not allow_thumb_fallback:
                msg = "Preview thumbnail skipped (fallback to thumbnails is disabled)"
                logger.info(f"  ⏭ {task.filename}: {msg}", category="file")
                return False, msg
            else:
                full_urls = preview_urls
                preview_urls = []

        task._tried_urls = []
        resp = None
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        try:
            resp, mode, existing_size, req_headers, early_err = self._acquire_http_response(
                task=task,
                session=session,
                options=options,
                full_urls=full_urls,
                preview_urls=preview_urls,
                allow_thumb_fallback=allow_thumb_fallback,
                range_headers=range_headers,
                mode=mode,
                existing_size=existing_size,
            )
            if early_err is not None:
                return early_err

            task.used_preview = (is_preview_url(task.url) or (resp and is_preview_url(getattr(resp, "url", "")))) and not (options is not None and getattr(options, "download_thumbnails_only", False))
            if task.used_preview:
                if getattr(task, "is_unimported_preview", False):
                    logger.info(
                        f"ℹ️ {task.filename}: not imported on Pawchive yet, so only the preview thumbnail was saved "
                        f"(full-size file isn't hosted on the site yet).",
                        category="file"
                    )
                else:
                    logger.warning(
                        f"⚠ {task.filename}: the full-size file couldn't be reached, so a smaller preview copy was saved. "
                        f"Turn on \"Re-download small / thumbnail files\" and download again later to replace it with the full one.",
                        category="file"
                    )

            status = resp.status_code

            # ── Handle error responses with helpful hints ─────────────────────
            if status == 416:
                # Asked to continue past the end: the .part file may already hold the whole file
                _, server_total = _content_range(resp.headers.get("Content-Range", ""))
                resp.close()
                resp = None
                if existing_size > 0 and (server_total == existing_size or (not server_total and task.file_size == existing_size)):
                    task.file_size = existing_size
                    task.downloaded_bytes = existing_size
                    return self._finalize_part(task, options, part_path, existing_size, hasher=None,
                                               strict_hash=True, is_upgrade_download=is_upgrade_download,
                                               found_existing_path=found_existing_path)
                _remove_quietly(part_path)
                msg = "The partly downloaded file didn't match the server's copy; it starts over on retry"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg

            if status == 403:
                task.http_status = 403
                msg = "403 Forbidden — content locked (membership tier access required)"
                logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg

            if status == 404:
                task.http_status = 404
                msg = "404 Not Found — file does not exist on any server mirror"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg

            if status == 429:
                task.http_status = 429
                retry_after = resp.headers.get("Retry-After", "30")
                msg = f"429_RATE_LIMIT (Retry-After: {retry_after}s)"
                logger.warning(f"  ⚠ {task.filename}: HTTP 429 Too Many Requests (Rate limited)", category="file")
                return False, msg

            if status not in (200, 206):
                task.http_status = status
                msg = f"HTTP {status}"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg

            # ── Determine file size and resume offset ─────────────────────────
            content_length = int(resp.headers.get("content-length", 0) or 0)
            api_size = task.file_size  # pre-populated from API metadata (fobj["bytes"])
            range_start, range_total = _content_range(resp.headers.get("Content-Range", ""))
            if status == 206 and range_start is not None and range_start != existing_size:
                resp.close()
                resp = None
                _remove_quietly(part_path)
                msg = "The server sent a different part of the file than asked; it starts over on retry"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg
            if status == 206:
                task.file_size = range_total or (existing_size + content_length)
                task.downloaded_bytes = existing_size
            else:
                # If CDN uses chunked transfer (no Content-Length), fall back to API-provided size
                task.file_size = content_length or api_size
                task.downloaded_bytes = 0
                mode = "wb"
                existing_size = 0
                resumed = False

            # ── Runtime size filter check ─────────────────────────────────────
            if task.file_size > 0 and options:
                keep_file, f_reason = FilterEngine.should_keep_file(task.filename, options, file_size=task.file_size)
                if not keep_file:
                    resp.close()
                    resp = None
                    _remove_quietly(part_path)
                    size_disp = FilterEngine.format_size_str(task.file_size)
                    logger.info(f"⏭️ Skipping {task.filename} ({size_disp}): {f_reason}", category="filter")
                    task.status = "skipped"
                    task.error_msg = f_reason
                    task.progress_pct = 100
                    task.eta_str = "Skipped"
                    if self.on_task_status_changed:
                        self.on_task_status_changed(task)
                    return True, f"Skipped: {f_reason}"

            size_str = FilterEngine.format_size_str(task.file_size) if task.file_size > 0 else "unknown size"
            logger.info(
                f"▶ {task.filename}  [{size_str}]  post: {task.post_title[:35]}",
                category="file"
            )

            # ── Storage Pool Auto-Spanning & Pre-flight disk space verification ──
            try:
                from core.storage_pool_manager import storage_pool_manager
                if storage_pool_manager.enabled and storage_pool_manager.overflow_dirs and existing_size == 0:
                    p_dir = storage_pool_manager.primary_dir
                    if p_dir and os.path.abspath(task.target_path).startswith(os.path.abspath(p_dir)):
                        rel_file = os.path.relpath(task.target_path, p_dir)
                        rel_folder = os.path.dirname(rel_file)
                        fn = os.path.basename(rel_file)
                        new_target, was_overflowed = storage_pool_manager.get_destination_target(
                            subfolder=rel_folder,
                            filename=fn,
                            estimated_bytes=task.file_size
                        )
                        if was_overflowed:
                            task.target_path = fit_path_for_windows(new_target)
                            part_path = task.target_path + PART_SUFFIX

                target_dir = os.path.dirname(os.path.abspath(task.target_path))
                os.makedirs(target_dir, exist_ok=True)
                usage = shutil.disk_usage(target_dir)
                # Room for the rest of this file plus a small margin (it used to start any file as long
                # as 25 MB were free, then fail half-way through big ones)
                needed = max(25 * 1024 * 1024, max(0, task.file_size - existing_size) + 20 * 1024 * 1024)
                if usage.free < needed:
                    resp.close()
                    msg = (f"Disk full: {FilterEngine.format_size_str(usage.free)} free, "
                           f"this file needs {FilterEngine.format_size_str(needed)}")
                    logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                    return False, msg
            except Exception:
                pass

            # ── Fast-path: Multipart chunking for large files (>= 25 MB) ─────
            # NOTE: For Pawchive, we intentionally use 1 continuous resumable stream
            # to protect their storage backend from multi-socket connection exhaustion.
            accept_ranges = resp.headers.get("Accept-Ranges", "").lower()
            is_pawchive = "pawchive" in (task.url or "").lower() or (getattr(task, "service", None) and "pawchive" in str(task.service).lower())
            if not is_pawchive and task.file_size >= 25 * 1024 * 1024 and existing_size == 0 and ("bytes" in accept_ranges or status == 206):
                resp.close()
                resp = None
                mp_terminal, mp_res, fallback_resp = self._download_multipart_task(
                    task=task,
                    options=options,
                    session=session,
                    req_headers=req_headers,
                    browser_headers=browser_headers,
                    size_str=size_str,
                )
                if mp_terminal:
                    return mp_res
                existing_size = 0
                mode = "wb"
                resumed = False
                resp = fallback_resp

            # ── Standard single stream download loop ──────────────────────────
            chunk_size = 131072 if (task.file_size > 10 * 1024 * 1024 or not task.file_size) else 65536
            last_speed_time = time.time()
            bytes_since_speed = 0

            _, max_size_limit = FilterEngine.get_effective_size_limits(options)
            stream_aborted_reason = None

            # SHA-256 computed while downloading (a resumed file first reads what it already has)
            hasher = None
            if content_hash_from_url(task.url) or len((task.expected_sha256 or "").strip()) == 64:
                hasher = hashlib.sha256()
                if mode == "ab" and existing_size > 0:
                    with open(part_path, "rb") as pf:
                        while True:
                            buf = pf.read(1024 * 1024)
                            if not buf:
                                break
                            hasher.update(buf)

            self._track_active_response(resp, self._task_batch_id(task))
            try:
                with open(part_path, mode) as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if self.is_batch_cancelled(task):
                            try:
                                resp.close()
                            except Exception:
                                pass
                            return False, "Cancelled"
                        if self.is_batch_paused(task) or task.status == "paused":
                            try:
                                resp.close()
                            except Exception:
                                pass
                            return False, "Batch paused by user"
                        was_paused = False
                        while self._pause_event.is_set():
                            was_paused = True
                            if self.is_batch_cancelled(task):
                                try:
                                    resp.close()
                                except Exception:
                                    pass
                                return False, "Cancelled"
                            if self.is_batch_paused(task) or task.status == "paused":
                                try:
                                    resp.close()
                                except Exception:
                                    pass
                                return False, "Batch paused by user"
                            time.sleep(0.3)
                        if was_paused:
                            last_speed_time = time.time()
                            bytes_since_speed = 0

                        if not chunk:
                            continue

                        if not bandwidth_limiter.wait_for(len(chunk), self._cancel_event, self._pause_event):
                            try:
                                resp.close()
                            except Exception:
                                pass
                            return False, "Cancelled"

                        f.write(chunk)
                        if hasher is not None:
                            hasher.update(chunk)
                        chunk_len = len(chunk)
                        task.downloaded_bytes += chunk_len
                        with self._lock:
                            self.downloaded_bytes += chunk_len

                        # Check if streaming has exceeded maximum file size limit (for chunked streams)
                        if max_size_limit and task.downloaded_bytes > max_size_limit:
                            try:
                                resp.close()
                            except Exception:
                                pass
                            stream_aborted_reason = f"File size ({FilterEngine.format_size_str(task.downloaded_bytes)}) exceeds maximum threshold ({FilterEngine.format_size_str(max_size_limit)})"
                            logger.info(f"⏭️ Aborted streaming {task.filename}: {stream_aborted_reason}", category="filter")
                            break

                        bytes_since_speed += chunk_len
                        now = time.time()

                        # Speed calculation every 0.5 s
                        delta_speed = now - last_speed_time
                        if delta_speed >= 0.5:
                            task.speed_bps = int(bytes_since_speed / delta_speed)
                            task.speed_str = self.format_speed(task.speed_bps)
                            if task.file_size > 0:
                                rem_bytes = max(0, task.file_size - task.downloaded_bytes)
                                task.progress_pct = int(task.downloaded_bytes / task.file_size * 100)
                                if task.speed_bps > 0:
                                    s = int(rem_bytes / task.speed_bps)
                                    task.eta_str = f"{s//60}m {s%60}s" if s > 60 else f"{s}s"
                            bytes_since_speed = 0
                            last_speed_time = now
                            if self.on_task_status_changed:
                                self.on_task_status_changed(task)
            finally:
                self._untrack_active_response(resp)

            final_size = os.path.getsize(part_path) if os.path.exists(part_path) else 0

            if stream_aborted_reason or (max_size_limit and final_size > max_size_limit):
                _remove_quietly(part_path)
                with self._lock:
                    self.downloaded_bytes = max(0, self.downloaded_bytes - task.downloaded_bytes)
                task.status = "skipped"
                f_reason = stream_aborted_reason or f"File size ({FilterEngine.format_size_str(final_size)}) exceeds maximum threshold ({FilterEngine.format_size_str(max_size_limit)})"
                task.error_msg = f_reason
                task.progress_pct = 100
                task.eta_str = "Skipped"
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                return True, f"Skipped: {f_reason}"

            if self.is_batch_cancelled(task):
                return False, "Cancelled"
            if self.is_batch_paused(task) or task.status == "paused":
                return False, "Batch paused by user"

            if task.file_size > 0 and final_size == 0:
                _remove_quietly(part_path)
                msg = "Downloaded file is empty (0.00 MB saved)"
                logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg

            if task.file_size > 0 and final_size < task.file_size and not self.is_batch_cancelled(task):
                # The .part file stays: the retry continues from here
                msg = (f"Incomplete download ({FilterEngine.format_size_str(final_size)} / "
                       f"{FilterEngine.format_size_str(task.file_size)}); it continues from there on retry")
                logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg

            # The server told us the size and we got exactly that: a checksum mismatch then means the
            # site serves a different version, not a damaged download. Without a confirmed size, or
            # when pieces from two attempts were joined, a mismatch means the file is damaged.
            size_confirmed = task.file_size > 0 and final_size == task.file_size and (content_length > 0 or range_total > 0)
            return self._finalize_part(task, options, part_path, final_size, hasher=hasher,
                                       strict_hash=resumed or not size_confirmed,
                                       is_upgrade_download=is_upgrade_download,
                                       found_existing_path=found_existing_path)

        except requests.exceptions.Timeout:
            if self.is_batch_cancelled(task):
                return False, "Cancelled"
            if self.is_batch_paused(task) or task.status == "paused":
                return False, "Batch paused by user"
            msg = "Connection timed out"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
            return False, msg
        except requests.exceptions.ConnectionError as e:
            if self.is_batch_cancelled(task):
                return False, "Cancelled"
            if self.is_batch_paused(task) or task.status == "paused":
                return False, "Batch paused by user"
            msg = f"Connection error: {e}"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
            return False, msg
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError) as e:
            # A connection that drops mid-transfer (IncompleteRead). requests derives these from
            # IOError, so without this branch they'd land in the OSError handler below, be
            # mislabelled as disk errors and have their partial file deleted. Keeping the
            # partial file lets the retry resume from where it stopped.
            if self.is_batch_cancelled(task):
                return False, "Cancelled"
            if self.is_batch_paused(task) or task.status == "paused":
                return False, "Batch paused by user"
            msg = f"Connection dropped mid-download (will resume on retry): {e}"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
            return False, msg
        except OSError as e:
            if self.is_batch_cancelled(task):
                return False, "Cancelled"
            if self.is_batch_paused(task) or task.status == "paused":
                return False, "Batch paused by user"
            is_disk_full = (
                getattr(e, "errno", None) == 28
                or getattr(e, "winerror", None) == 112
                or "space" in str(e).lower()
            )
            msg = "Disk full: Not enough free space on drive" if is_disk_full else f"Disk/IO error: {e}"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
            _remove_quietly(task.target_path + PART_SUFFIX)
            task.downloaded_bytes = 0
            task.progress_pct = 0
            task.speed_bps = 0
            task.speed_str = "0 KB/s"
            task.eta_str = "--"
            return False, msg
        except Exception as e:
            if self.is_batch_cancelled(task):
                return False, "Cancelled"
            if self.is_batch_paused(task) or task.status == "paused":
                return False, "Batch paused by user"
            logger.error(f"  ✖ {task.filename}: {type(e).__name__}: {e}", category="file",
                         details=self._task_context(task) + "\n" + traceback.format_exc())
            return False, str(e)
        finally:
            if resp is not None:
                self._untrack_active_response(resp)
                try:
                    resp.close()
                except Exception:
                    pass
