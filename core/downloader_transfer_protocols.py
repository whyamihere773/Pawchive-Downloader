"""
Downloader Protocol Transfers — yt-dlp Embeds, Telegram MTProto & Multipart Chunking
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

import requests

from core.downloader_models import (
    DownloadTask,
    EMBED_REFERERS,
    _remove_quietly,
    friendly_embed_error,
    is_not_a_video_error,
)
from core.filter_engine import FilterEngine, FilterOptions
from core.logger import logger
from core.video_probe import VideoProbe
from services.multipart_downloader import download_multipart_file as _default_download_multipart_file
from services.telegram_service import TelegramService


def _get_multipart_fn():
    """Resolve download_multipart_file through core.downloader so test patches work."""
    mod = sys.modules.get("core.downloader")
    if mod is not None and hasattr(mod, "download_multipart_file"):
        return mod.download_multipart_file
    return _default_download_multipart_file


class DownloaderTransferProtocolsMixin:
    """Specialized protocol handlers for yt-dlp embeds, Telegram MTProto, and multipart transfers."""

    def _download_ytdlp_task(self, task: DownloadTask, options: Optional[FilterOptions]) -> Tuple[bool, str]:
        """Execute a yt-dlp embedded media download task."""
        if options and getattr(options, "video_duration_filter_enabled", False):
            dur = VideoProbe.get_video_duration(task.url, session=self._get_worker_session())
            keep_dur, dur_reason = FilterEngine.should_keep_video_duration(dur, options)
            if not keep_dur:
                logger.info(f"⏭️ Skipping [yt-dlp] {task.url}: {dur_reason}", category="filter")
                task.status = "skipped"
                task.error_msg = dur_reason
                task.progress_pct = 100
                task.eta_str = "Skipped"
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                return True, f"Skipped: {dur_reason}"

        logger.info(f"▶ [yt-dlp] Downloading embedded player media: {task.url}", category="ytdlp")
        _prev_ytdlp_bytes = [0]

        def _ytdlp_prog(done_b, total_b, speed_s, eta_s):
            delta = done_b - _prev_ytdlp_bytes[0]
            if delta > 0:
                with self._lock:
                    self.downloaded_bytes += delta
                _prev_ytdlp_bytes[0] = done_b
            task.downloaded_bytes = done_b
            task.file_size = total_b or task.file_size
            task.speed_str = speed_s
            task.eta_str = eta_s
            if total_b > 0:
                task.progress_pct = min(99, int(done_b / total_b * 100))
            if self.on_task_status_changed:
                self.on_task_status_changed(task)

        target_folder = os.path.dirname(task.target_path)
        custom_fn = os.path.basename(task.target_path)
        ok, msg = self.ytdlp_manager.download_media(
            url=task.url,
            target_folder=target_folder,
            custom_filename=custom_fn,
            cancel_event=self._cancel_event,
            pause_event=self._pause_event,
            progress_callback=_ytdlp_prog,
            referer=EMBED_REFERERS.get((task.service or "").lower(), "")
        )
        if not ok and is_not_a_video_error(msg):
            logger.info(f"⏭️ [yt-dlp] Skipping {task.url}: not a video link", category="ytdlp")
            task.status = "skipped"
            task.error_msg = "Not a video link"
            task.progress_pct = 100
            task.eta_str = "Skipped"
            if self.on_task_status_changed:
                self.on_task_status_changed(task)
            return True, "Skipped: not a video link"
        if ok:
            if self.is_batch_cancelled(task):
                _remove_quietly(task.target_path)
                return False, "Cancelled"
            final_ytdlp_sz = os.path.getsize(task.target_path) if os.path.exists(task.target_path) else 0
            if final_ytdlp_sz > 0 and options:
                keep_file, f_reason = FilterEngine.should_keep_file(task.filename, options, file_size=final_ytdlp_sz)
                if not keep_file:
                    if os.path.exists(task.target_path):
                        try:
                            os.remove(task.target_path)
                        except OSError:
                            pass
                    with self._lock:
                        self.downloaded_bytes = max(0, self.downloaded_bytes - task.downloaded_bytes)
                    logger.info(f"⏭️ Skipping [yt-dlp] {task.filename} ({FilterEngine.format_size_str(final_ytdlp_sz)}): {f_reason}", category="filter")
                    task.status = "skipped"
                    task.error_msg = f_reason
                    task.progress_pct = 100
                    task.eta_str = "Skipped"
                    if self.on_task_status_changed:
                        self.on_task_status_changed(task)
                    return True, f"Skipped: {f_reason}"

            task.status = "completed"
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
                    file_path=task.target_path
                )
            if self.on_task_status_changed:
                self.on_task_status_changed(task)
            logger.success(f"✔ [yt-dlp] {task.filename} successfully downloaded", category="ytdlp")
            return True, "Completed"
        else:
            if self.is_batch_cancelled(task):
                return False, "Cancelled"
            if self.is_batch_paused(task) or task.status == "paused":
                return False, "Batch paused by user"
            msg = friendly_embed_error(msg, task.url)
            logger.warning(f"✖ [yt-dlp] {task.filename}: {msg}", category="ytdlp")
            return False, msg

    def _download_telegram_task(self, task: DownloadTask, options: Optional[FilterOptions]) -> Tuple[bool, str]:
        """Execute a Telegram MTProto media download task."""
        logger.info(f"▶ [Telegram] Downloading MTProto media: {task.url}", category="telegram")
        _prev_tg_bytes = [0]
        _last_tg_emit = [0.0]

        def _tg_prog(done_b, total_b, speed_s, eta_s):
            delta = done_b - _prev_tg_bytes[0]
            if delta > 0:
                with self._lock:
                    self.downloaded_bytes += delta
                _prev_tg_bytes[0] = done_b
            task.downloaded_bytes = done_b
            task.file_size = total_b or task.file_size
            task.speed_str = speed_s
            task.eta_str = eta_s
            if total_b > 0:
                task.progress_pct = min(99, int(done_b / total_b * 100))

            now = time.time()
            is_done = (total_b > 0 and done_b >= total_b)
            if is_done or (now - _last_tg_emit[0] >= 0.25):
                _last_tg_emit[0] = now
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)

        tg_service = TelegramService.instance()
        channel_id = getattr(task, "telegram_channel_id", "") or task.user_id
        message_id = getattr(task, "telegram_message_id", 0) or int(task.post_id if str(task.post_id).isdigit() else 0)

        ok, msg = tg_service.download_media(
            channel_id=channel_id,
            message_id=message_id,
            target_path=task.target_path,
            progress_callback=_tg_prog,
            cancel_event=self._cancel_event,
            pause_event=self._pause_event
        )
        if ok:
            if self.is_batch_cancelled(task):
                _remove_quietly(task.target_path)
                return False, "Cancelled"
            final_tg_sz = os.path.getsize(task.target_path) if os.path.exists(task.target_path) else 0
            if final_tg_sz > 0 and options:
                keep_file, f_reason = FilterEngine.should_keep_file(task.filename, options, file_size=final_tg_sz)
                if not keep_file:
                    if os.path.exists(task.target_path):
                        try:
                            os.remove(task.target_path)
                        except OSError:
                            pass
                    with self._lock:
                        self.downloaded_bytes = max(0, self.downloaded_bytes - task.downloaded_bytes)
                    logger.info(f"⏭️ Skipping [Telegram] {task.filename} ({FilterEngine.format_size_str(final_tg_sz)}): {f_reason}", category="filter")
                    task.status = "skipped"
                    task.error_msg = f_reason
                    task.progress_pct = 100
                    task.eta_str = "Skipped"
                    if self.on_task_status_changed:
                        self.on_task_status_changed(task)
                    return True, f"Skipped: {f_reason}"

            task.status = "completed"
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
                    file_path=task.target_path
                )
            if self.on_task_status_changed:
                self.on_task_status_changed(task)
            logger.success(f"✔ [Telegram] {task.filename} successfully downloaded", category="telegram")
            return True, "Completed"
        else:
            if self.is_batch_cancelled(task) or "Cancelled" in msg:
                task.status = "cancelled"
                task.error_msg = msg
            elif self.is_batch_paused(task) or task.status == "paused":
                return False, "Batch paused by user"
            else:
                task.status = "failed"
                task.error_msg = msg
            if self.on_task_status_changed:
                self.on_task_status_changed(task)
            logger.warning(f"✖ [Telegram] {task.filename}: {msg}", category="telegram")
            return False, msg

    def _download_multipart_task(
        self,
        *,
        task: DownloadTask,
        options: Optional[FilterOptions],
        session: requests.Session,
        req_headers: Dict[str, str],
        browser_headers: Dict[str, str],
        size_str: str,
    ) -> Tuple[bool, Tuple[bool, str], Any]:
        """Attempt 4-part parallel chunked download; on failure acquire single-stream fallback response.

        Returns (terminal, (ok, msg), fallback_resp).
        When terminal is True, caller immediately returns (ok, msg).
        When terminal is False, caller continues single-stream download using fallback_resp.
        """
        logger.info(f"  ⚡ Activating 4-part parallel chunked download for {task.filename} ({size_str})", category="file")

        _prev_mp_bytes = [0]
        _last_mp_emit = [time.time()]
        _last_mp_speed_bytes = [0]

        def _on_mp_progress(curr_bytes: int, total_b: int):
            if curr_bytes < _prev_mp_bytes[0]:
                _prev_mp_bytes[0] = curr_bytes
            else:
                delta = curr_bytes - _prev_mp_bytes[0]
                if delta > 0:
                    with self._lock:
                        self.downloaded_bytes += delta
                    _prev_mp_bytes[0] = curr_bytes

            task.downloaded_bytes = curr_bytes
            if total_b > 0:
                task.file_size = total_b
                task.progress_pct = min(99, int(curr_bytes / total_b * 100))

            now_poll = time.time()
            dt_poll = now_poll - _last_mp_emit[0]
            if dt_poll >= 1.0:
                bytes_diff = max(0, curr_bytes - _last_mp_speed_bytes[0])
                _last_mp_speed_bytes[0] = curr_bytes
                _last_mp_emit[0] = now_poll

                if task.file_size > 0:
                    spd_bps = max(0.0, bytes_diff / max(0.1, dt_poll))
                    task.speed_bps = int(spd_bps)
                    task.speed_str = self.format_speed(task.speed_bps)
                    if task.speed_bps > 0:
                        rem = max(0, task.file_size - curr_bytes)
                        s = int(rem / task.speed_bps)
                        task.eta_str = f"{s//60}m {s%60}s" if s > 60 else f"{s}s"
                    else:
                        task.eta_str = "--"

                stats = self._queue_stats(now_poll)
                completed_c = int(stats.get("done_n", 0))
                failed_c = int(self.status_counts().get("failed", 0))
                self._emit_progress(completed_c, failed_c, len(self.tasks))

                if self.on_task_status_changed:
                    self.on_task_status_changed(task)

        mp_ok, mp_err = _get_multipart_fn()(
            url=task.url,
            target_path=task.target_path,
            headers=req_headers,
            num_chunks=4,
            progress_callback=_on_mp_progress,
            cancel_event=self._cancel_event,
            pause_event=self._pause_event,
            timeout=(25, 60),
            session=session,
            abort_check=lambda: self.is_batch_cancelled(task) or self.is_batch_paused(task) or task.status == "paused",
        )

        if mp_ok:
            if self.is_batch_cancelled(task):
                _remove_quietly(task.target_path)
                return True, (False, "Cancelled"), None
            final_mp_size = os.path.getsize(task.target_path) if os.path.exists(task.target_path) else 0
            if task.file_size > 0 and final_mp_size == 0:
                if os.path.exists(task.target_path):
                    try:
                        os.remove(task.target_path)
                    except OSError:
                        pass
                mp_ok = False
                mp_err = "Multipart download resulted in empty 0-byte file"
            else:
                if final_mp_size > 0 and options:
                    keep_file, f_reason = FilterEngine.should_keep_file(task.filename, options, file_size=final_mp_size)
                    if not keep_file:
                        if os.path.exists(task.target_path):
                            try:
                                os.remove(task.target_path)
                            except OSError:
                                pass
                        with self._lock:
                            self.downloaded_bytes = max(0, self.downloaded_bytes - task.downloaded_bytes)
                        size_disp = FilterEngine.format_size_str(final_mp_size)
                        logger.info(f"⏭️ Skipping {task.filename} ({size_disp}): {f_reason}", category="filter")
                        task.status = "skipped"
                        task.error_msg = f_reason
                        task.progress_pct = 100
                        task.eta_str = "Skipped"
                        if self.on_task_status_changed:
                            self.on_task_status_changed(task)
                        return True, (True, f"Skipped: {f_reason}"), None

                problem = self._verify_file_hash(task, final_mp_size)
                if problem:
                    _remove_quietly(task.target_path)
                    logger.error(f"  ✖ {task.filename}: {problem}", category="file", details=self._task_context(task))
                    return True, (False, problem), None
                self._post_process_downloaded_file(task, options)
                task.status = "completed"
                task.downloaded_bytes = task.file_size
                task.progress_pct = 100
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                return True, (True, "Completed"), None

        if self.is_batch_cancelled(task):
            return True, (False, "Cancelled"), None
        if self.is_batch_paused(task) or task.status == "paused" or "Batch paused by user" in str(mp_err):
            return True, (False, "Batch paused by user"), None

        # Clean up temporary file from multipart attempt
        if os.path.exists(f"{task.target_path}.tmp"):
            try:
                os.remove(f"{task.target_path}.tmp")
            except OSError:
                pass

        # Reset task progress tracking
        with self._lock:
            if task.downloaded_bytes > 0:
                self.downloaded_bytes = max(0, self.downloaded_bytes - task.downloaded_bytes)
        task.downloaded_bytes = 0
        task.progress_pct = 0
        task.speed_bps = 0
        task.speed_str = "0 KB/s"
        task.eta_str = "--"

        if "Disk full" in mp_err:
            return True, (False, mp_err), None

        logger.info(f"  ↪ Multipart fallback: {mp_err} — switching to standard single stream download...", category="file")

        # Re-acquire single stream response stream since resp was closed for multipart
        resp = None
        try:
            resp = session.get(task.url, stream=True, timeout=(25, 60), headers=req_headers)
            if resp.status_code not in (200, 206):
                clean_sess = self._new_cookieless_session()
                clean_resp = clean_sess.get(task.url, stream=True, timeout=(25, 60), headers=browser_headers)
                if clean_resp.status_code in (200, 206):
                    resp.close()
                    resp = clean_resp
                else:
                    clean_resp.close()
                    clean_sess.close()
            if resp.status_code not in (200, 206):
                msg = f"HTTP {resp.status_code} on single-stream fallback"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                resp.close()
                resp = None
                return True, (False, msg), None
        except Exception as ex:
            if resp:
                try:
                    resp.close()
                except Exception:
                    pass
                resp = None
            msg = f"Single-stream fallback connection error: {ex}"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
            return True, (False, msg), None

        return False, (True, ""), resp
