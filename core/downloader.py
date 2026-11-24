"""
Core Downloader & Task Execution Engine
Coordinates concurrent chunk streaming, SHA-256 validation, adaptive backoff,
multipart acceleration, WebP conversion, retry queues, and telemetry reporting.
"""

import os
import shutil
import sys
import threading
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests

# Ensure project root is on sys.path even when executed directly
if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.archive_manager import ArchiveManager
from core.bandwidth_limiter import bandwidth_limiter
from core.downloader_batch_ops import DownloaderBatchOpsMixin
from core.downloader_loop import DownloaderLoopMixin
from core.downloader_models import (
    BatchBuildContext,
    COOMER_SERVICES,
    DEAD_VIDEO_HOSTS,
    DownloadTask,
    EMBED_REFERERS,
    PART_SUFFIX,
    StatusCounter,
    UNIMPORTED_TASK_ERROR_MSG,
    _CONTACT_HEADERS,
    _HASH_PATH_RE,
    _NOT_A_VIDEO_ERRORS,
    _PERMANENT_EMBED_ERRORS,
    _PERMANENT_ERRORS,
    _content_range,
    _counts,
    _fq,
    _get_media_candidate_paths,
    _post_info_lock,
    _remove_quietly,
    _write_post_info,
    atomic_move_part,
    content_hash_from_url,
    format_unimported_explanation,
    friendly_embed_error,
    is_not_a_video_error,
    is_permanent_failure,
    is_post_unimported_on_pawchive,
    is_preview_url,
    is_task_non_retryable,
    needs_full_size_upgrade,
)
from core.downloader_retries_pacing import DownloaderRetriesPacingMixin
from core.downloader_post_layout import DownloaderPostLayoutMixin
from core.downloader_task_builder import DownloaderTaskBuilderMixin
from core.downloader_task_builder_files import DownloaderTaskBuilderFilesMixin
from core.downloader_telemetry import DownloaderTelemetryMixin
from core.downloader_http_negotiator import DownloaderHttpNegotiatorMixin
from core.downloader_transfer_http import DownloaderTransferHttpMixin
from core.downloader_transfer_protocols import DownloaderTransferProtocolsMixin
from core.downloader_url_postprocess import DownloaderUrlPostprocessMixin
from core.filter_engine import FilterEngine, FilterOptions, MediaTypes, fit_path_for_windows
from core.known_manager import KnownManager
from core.logger import logger
from core.providers import COOMER, KEMONO, PAWCHIVE, cookie_for_url, disabled_message, is_disabled, provider_for_host
from core.session_manager import SessionManager
from services.multipart_downloader import download_multipart_file
from services.ytdlp_manager import YtDlpManager


class KemonoDownloader(
    DownloaderUrlPostprocessMixin,
    DownloaderTaskBuilderFilesMixin,
    DownloaderPostLayoutMixin,
    DownloaderTaskBuilderMixin,
    DownloaderBatchOpsMixin,
    DownloaderRetriesPacingMixin,
    DownloaderLoopMixin,
    DownloaderTransferProtocolsMixin,
    DownloaderHttpNegotiatorMixin,
    DownloaderTransferHttpMixin,
    DownloaderTelemetryMixin,
):
    """
    Multithreaded, fault-tolerant download queue engine.
    Supports resume, deduplication, speed limits, and custom naming.
    """

    def __init__(
        self,
        known_manager: KnownManager,
        session_manager: SessionManager,
        max_workers: int = 4,
        archive_manager: Optional[ArchiveManager] = None
    ):
        self.known_manager = known_manager
        self.session_manager = session_manager
        self.max_workers = max_workers
        self.archive_manager = archive_manager
        self.ytdlp_manager = YtDlpManager()

        self.tasks: List[DownloadTask] = []
        self._lock = threading.Lock()
        self._mutation_lock = threading.RLock()
        self._workers_drained_cond = threading.Condition(self._mutation_lock)
        self._rate_limit_lock = threading.Lock()
        self._rate_limit_cooldown_until = 0.0
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._paused_batches: set = set()
        self._cancelled_batches: Set[str] = set()
        self._pending_rebuild_batches: Set[str] = set()
        self._active_batch_workers: Dict[str, int] = defaultdict(int)
        self._paused_batches_lock = threading.Lock()
        self._is_running = False
        self._session_id: int = 0
        self._download_thread: Optional[threading.Thread] = None
        self.current_options: Optional[FilterOptions] = None
        self._batch_options: Dict[str, FilterOptions] = {}
        self._batch_options_lock = threading.Lock()
        self._batch_contexts: Dict[str, BatchBuildContext] = {}
        self._batch_contexts_lock = threading.Lock()
        self._active_responses: Dict[Any, str] = {}
        self._active_resp_lock = threading.Lock()
        self._worker_sessions: set = set()
        self._worker_sessions_lock = threading.Lock()
        self._thread_local = threading.local()
        self._worker_session_epoch: int = 0
        self._proxy_url: str = ""
        self._clean_cookie: str = ""
        self._post_info_pending: Dict[Any, str] = {}   # post_info.txt path -> text, written after the first file
        self._post_info_owners: Dict[Tuple[str, str], str] = {}
        self._already_there = Counter()
        self._status_counter = StatusCounter()
        self._counter_sig = None
        self._dispatch_cursor = 0          # queue position where pending files started on the last scan
        self._last_full_scan = 0.0
        self._task_stats: Dict[str, float] = {}
        self._task_stats_time = 0.0

        self.total_bytes = 0
        self.downloaded_bytes = 0
        self.start_time = 0.0
        self.adaptive_state = "optimal"       # "optimal", "scaling", "cooldown", "manual"
        self.adaptive_status_text = ""
        self._learned_stable_ceiling: Optional[int] = None
        self._manual_target_workers: Optional[int] = None
        self._stable_clean_count: int = 0
        self._consecutive_429_bursts: int = 0
        self._rate_limit_probe_needed: bool = False
        self._rate_limit_probe_claimed_until: float = 0.0
        self._unscoped_cooldown_until: float = 0.0
        self._host_cooldown_until: Dict[str, float] = {}
        self._host_consecutive_429: Dict[str, int] = defaultdict(int)
        self._host_probe_needed: Dict[str, bool] = {}
        self._host_probe_claimed_until: Dict[str, float] = {}
        # Cross-thread Pawchive request-start pacer & sliding-window self-calibration
        self._pawchive_pace_lock = threading.Lock()
        self._pawchive_next_req_time: float = 0.0
        self._pawchive_global_next_time: float = 0.0
        self._pawchive_recovery_gap_until: float = 0.0
        self._host_next_req_time: Dict[str, float] = {}
        self._host_recovery_gap_until: Dict[str, float] = {}
        self._host_req_timestamps: Dict[str, deque] = defaultdict(deque)
        self._host_calibrated_rpm: Dict[str, int] = {}
        self._host_slow_ttfb_until: Dict[str, float] = {}
        # Verified SHA-256 -> (path, webp_quality_or_none) for zero-HTTP cross-post local copies
        self._verified_hash_lock = threading.Lock()
        self._verified_hash_paths: Dict[str, Tuple[str, Optional[str]]] = {}

        # Smart Learning ETA and speed smoothing telemetry
        self._speed_samples = deque(maxlen=40)
        self._rolling_speed_samples: deque = deque()
        self._smoothed_speed: float = 0.0
        self._medium_speed: float = 0.0
        self._smoothed_eta: Optional[float] = None
        self._last_eta_calc_time: float = 0.0
        self._last_progress_emit_time: float = 0.0
        self._total_paused_time: float = 0.0
        self._pause_start_time: float = 0.0
        self._first_byte_time: float = 0.0

        # Harvested external cloud links (populated in links-only mode)
        self.harvested_links: Dict[str, List[str]] = {}
        self.harvested_links_records: List[Dict[str, Any]] = []
        self.last_build_unimported: Dict[str, Any] = {
            "posts": 0,
            "files": 0,
            "queued_thumbnails": 0,
            "post_ids": [],
            "creator_name": "",
            "total_posts": 0,
            "service": "",
            "domain": "",
        }
        self.last_build_unimported_tasks: List[DownloadTask] = []

        # Callbacks for UI updates
        self.on_progress_update: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_task_status_changed: Optional[Callable[[DownloadTask], None]] = None
        self.on_tasks_changed: Optional[Callable[[List[DownloadTask]], None]] = None     # many at once
        self.on_cleanup_wanted: Optional[Callable[[], None]] = None     # memory cleanup after a run
        self.on_download_finished: Optional[Callable[[bool, str], None]] = None
        self.on_concurrency_throttled: Optional[Callable[[int], None]] = None
        self.on_pause_changed: Optional[Callable[[bool], None]] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def _get_worker_session(self, clean_cookie: str = "") -> requests.Session:
        sess = getattr(self._thread_local, "session", None)
        sess_epoch = getattr(self._thread_local, "session_epoch", -1)
        if sess is None or sess_epoch != self._worker_session_epoch:
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
                with self._worker_sessions_lock:
                    self._worker_sessions.discard(sess)
            sess = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=1)
            sess.mount("https://", adapter)
            sess.mount("http://", adapter)
            sess.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "*/*"
            })
            if self._proxy_url:
                sess.proxies = {"http": self._proxy_url, "https": self._proxy_url}
            # No Cookie here: the login cookie is added per request, only for the site it belongs to
            # (it used to go to every host, Bunkr and other file servers included)
            self._thread_local.session = sess
            self._thread_local.session_epoch = self._worker_session_epoch
            with self._worker_sessions_lock:
                self._worker_sessions.add(sess)
        return sess

    def bump_worker_session_epoch(self, proxy_url: Optional[str] = None) -> None:
        """Applies updated proxy settings cleanly for subsequent requests without breaking in-flight chunks."""
        if proxy_url is not None:
            self._proxy_url = str(proxy_url or "").strip()
        self._worker_session_epoch += 1

    def _close_worker_sessions(self):
        with self._worker_sessions_lock:
            for s in list(self._worker_sessions):
                try:
                    s.close()
                except Exception:
                    pass
            self._worker_sessions.clear()
        if hasattr(self._thread_local, "session"):
            self._thread_local.session = None

    def cancel(self):
        self._session_id += 1
        self._cancel_event.set()
        self._pause_event.clear()  # Ensure paused workers wake up to handle cancel
        logger.warning("Download cancellation requested.", category="downloader")

        # 1. Instantly abort any active Telegram downloads
        try:
            from services.telegram_service import TelegramService
            TelegramService.instance().cancel_all_downloads()
        except Exception:
            pass

        # 2. Instantly abort all active multipart downloads (Bunkr, Kemono, Coomer, Erome, etc.)
        try:
            from services.multipart_downloader import cancel_all_multipart
            cancel_all_multipart()
        except Exception:
            pass

        # 3. Instantly kill all active yt-dlp child processes
        try:
            if hasattr(self, "ytdlp_manager") and self.ytdlp_manager:
                self.ytdlp_manager.cancel_all()
        except Exception:
            pass

        # 4. Instantly abort any active cloud downloads (Mega, Dropbox, Gofile)
        try:
            from services.cloud_downloader import cancel_all_cloud_downloads
            cancel_all_cloud_downloads()
        except Exception:
            pass

        # 5. Instantly close active single-stream HTTP responses to terminate open network sockets
        with self._active_resp_lock:
            for resp in list(self._active_responses.keys()):
                try:
                    resp.close()
                    if hasattr(resp, "raw") and resp.raw:
                        resp.raw.close()
                except Exception:
                    pass
            self._active_responses.clear()

        # 6. Instantly close worker sessions to terminate open socket pools
        self._close_worker_sessions()

        rec = getattr(self.session_manager, "recovery_manager", None)
        if rec:
            rec.discard_recovery()
        if self.on_pause_changed:
            try:
                self.on_pause_changed(False)
            except Exception as e:
                logger.error(f"Error in on_pause_changed callback: {e}", category="downloader")

    def pause(self):
        self._pause_event.set()
        if self._pause_start_time <= 0:
            self._pause_start_time = time.time()
        logger.info("Download paused.", category="downloader")
        self._save_recovery_checkpoint(async_write=True)      # called from the window
        if self.on_pause_changed:
            try:
                self.on_pause_changed(True)
            except Exception as e:
                logger.error(f"Error in on_pause_changed callback: {e}", category="downloader")

    def resume(self):
        now = time.time()
        if self._pause_start_time > 0:
            self._total_paused_time += max(0.0, now - self._pause_start_time)
            self._pause_start_time = 0.0
        self._pause_event.clear()
        self._speed_samples.clear()
        self._rolling_speed_samples.clear()
        self._smoothed_speed = 0.0
        self._last_eta_calc_time = now
        logger.info("Download resumed.", category="downloader")
        if self.on_pause_changed:
            try:
                self.on_pause_changed(False)
            except Exception as e:
                logger.error(f"Error in on_pause_changed callback: {e}", category="downloader")

    def reset_state(self):
        """Fully resets download state so a new session starts cleanly."""
        self._session_id += 1
        self._cancel_event.clear()
        self._pause_event.clear()
        with self._paused_batches_lock:
            self._paused_batches.clear()
            self._cancelled_batches.clear()
        with self._mutation_lock:
            self._pending_rebuild_batches.clear()
            self._active_batch_workers.clear()
            self._workers_drained_cond.notify_all()
        with self._batch_contexts_lock:
            self._batch_contexts.clear()
        self._post_info_pending.clear()
        self._post_info_owners.clear()
        if self.on_pause_changed:
            try:
                self.on_pause_changed(False)
            except Exception:
                pass
        self.tasks = []
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.start_time = 0.0
        self._is_running = False
        self._speed_samples.clear()
        self._rolling_speed_samples.clear()
        self._smoothed_speed = 0.0
        self._medium_speed = 0.0
        self._smoothed_eta = None
        self._last_eta_calc_time = 0.0
        self._last_progress_emit_time = 0.0
        self._total_paused_time = 0.0
        self._pause_start_time = 0.0
        self._first_byte_time = 0.0
        self.adaptive_state = "optimal"
        self.adaptive_status_text = ""
        self._manual_target_workers = None
        self._consecutive_429_bursts = 0
        self._rate_limit_probe_needed = False
        self._rate_limit_probe_claimed_until = 0.0
        self._rate_limit_cooldown_until = 0.0
        self._unscoped_cooldown_until = 0.0
        with self._rate_limit_lock:
            self._host_cooldown_until.clear()
            self._host_consecutive_429.clear()
            self._host_probe_needed.clear()
            self._host_probe_claimed_until.clear()
        with self._pawchive_pace_lock:
            self._pawchive_next_req_time = 0.0
            self._pawchive_global_next_time = 0.0
            self._pawchive_recovery_gap_until = 0.0
            self._host_next_req_time.clear()
            self._host_recovery_gap_until.clear()
            self._host_req_timestamps.clear()
            self._host_calibrated_rpm.clear()
            self._host_slow_ttfb_until.clear()
        with self._verified_hash_lock:
            self._verified_hash_paths.clear()
        logger.info("Downloader state fully reset.", category="downloader")

    def status_counts(self) -> Dict[str, int]:
        """Tasks per status. Recounted only when the task list itself changed (replaced or grew)."""
        tasks = self.tasks
        sig = (id(tasks), len(tasks))
        if sig != self._counter_sig:
            self._status_counter.reset(tasks)
            self._counter_sig = sig
        return self._status_counter.counts

    def _save_recovery_checkpoint(self, options: Optional[FilterOptions] = None, async_write: bool = False,
                                  force_full: bool = False):
        """Persists current download tasks to the crash-proof recovery journal."""
        try:
            if not self.tasks:
                return
            rec = getattr(self.session_manager, "recovery_manager", None)
            if not rec:
                return
            eff_opts = options or self.current_options
            opts_dict = vars(eff_opts) if eff_opts else {}
            status = "paused" if self.is_paused else ("cancelled" if self._cancel_event.is_set() else "in_progress")
            # Only tasks whose status changed since the last checkpoint need saving,
            # unless tasks/paths were rebuilt (force_full=True bypasses QueueJournal's equal-len fast path).
            self.status_counts()
            changed = self._status_counter.take_changed()
            rec.save_checkpoint(tasks=self.tasks, settings=opts_dict, status=status, async_write=async_write,
                                changed=(None if force_full else changed))
        except Exception as e:
            logger.debug(f"Could not persist recovery checkpoint: {e}", category="session")

    def start_download_queue(self, tasks: List[DownloadTask], options: FilterOptions, cookie_str: str = ""):
        """
        Starts worker pool in a background thread.
        """
        if self._download_thread and self._download_thread.is_alive():
            self._session_id += 1          # the previous run stops at its next check
            self._cancel_event.set()
            try:
                self._download_thread.join(timeout=5.0)
            except Exception:
                pass
            if self._download_thread.is_alive():
                logger.warning("The previous download run is still stopping; files it was working on may need a retry.",
                               category="downloader")
            else:
                # Files the previous run was downloading when it stopped go back in line
                for t in tasks:
                    if t.status == "downloading":
                        t.status = "pending"

        self._session_id += 1
        self._dispatch_cursor = 0
        session_id = self._session_id

        self.tasks = tasks
        self.current_options = options
        self._cancel_event.clear()
        self._pause_event.clear()
        if self.on_pause_changed:
            try:
                self.on_pause_changed(False)
            except Exception:
                pass
        self._is_running = True
        # (the save-path check and the first recovery save run at the start of the download thread:
        # on a big queue they took the window thread most of a second)
        self._download_thread = threading.Thread(
            target=self._run_download_loop,
            args=(options, cookie_str, session_id),
            daemon=True
        )
        self._download_thread.start()

    def append_tasks(self, new_tasks: List[DownloadTask], options: Optional[FilterOptions] = None,
                     cookie_str: str = "",
                     progress_callback: Optional[Callable[[int, int, str], None]] = None) -> int:
        """
        Thread-safely appends new tasks with deduplication.
        If worker loop is running, new pending tasks will be dynamically scheduled.
        If idle and options are provided, launches download loop.
        """
        if not new_tasks:
            return 0

        if progress_callback:
            try:
                progress_callback(0, len(new_tasks), f"Deduplicating & reserving paths ({len(new_tasks):,} files)...")
            except Exception:
                pass

        existing_signatures = set()
        for t in self.tasks:
            existing_signatures.add((t.url, t.target_path))
            if t.file_id:
                existing_signatures.add(t.file_id)

        deduped = []
        for t in new_tasks:
            sig1 = (t.url, t.target_path)
            sig2 = t.file_id
            if sig1 in existing_signatures or (sig2 and sig2 in existing_signatures):
                continue
            existing_signatures.add(sig1)
            if sig2:
                existing_signatures.add(sig2)
            deduped.append(t)

        if not deduped:
            logger.info("All new tasks were duplicates and already exist in the queue.", category="downloader")
            return 0

        self._keep_paths_apart(deduped, self.tasks)
        if options is not None:
            batch_opts_cache: Dict[str, FilterOptions] = {}
            for t in deduped:
                bid = self._task_batch_id(t)
                if getattr(t, "options", None) is None:
                    if bid:
                        if bid not in batch_opts_cache:
                            batch_opts_cache[bid] = FilterOptions.from_dict(options.to_dict())
                        t.options = batch_opts_cache[bid]
                    else:
                        t.options = FilterOptions.from_dict(options.to_dict())
                if bid:
                    self.set_batch_options(bid, t.options)
        self.tasks.extend(deduped)
        logger.info(f"Appended {len(deduped)} new tasks to download queue (total in queue: {len(self.tasks)}).", category="downloader")

        if not self._is_running and options is not None and any(t.status == "pending" for t in deduped):
            self.start_download_queue(self.tasks, FilterOptions.from_dict(options.to_dict()), cookie_str)

        return len(deduped)

    @staticmethod
    def _keep_paths_apart(new_tasks: List[DownloadTask], existing: List[DownloadTask]) -> int:
        """Two different files may never share a save path, whatever queued them.

        Sharing one made the second count as "already downloaded", overwrite the first, or — when
        both downloaded at once — mix into the same temporary file. Files not downloaded yet get
        "name (2).ext", "name (3).ext"…; returns how many were renamed."""
        if os.sep == "\\":
            def norm(p: str) -> str:          # os.path.normcase, without its slow Windows call per path
                return p.replace("/", "\\").lower()
        else:
            norm = os.path.normcase
        taken: Dict[str, DownloadTask] = {}
        for t in existing:
            if getattr(t, "target_path", ""):
                taken[norm(t.target_path)] = t
        renamed = 0
        for t in new_tasks:
            path = getattr(t, "target_path", "")
            if not path:
                continue
            key = norm(path)
            other = taken.get(key)
            if other is not None and other is not t and other.url != t.url                     and t.status in ("pending", "failed", "cancelled"):
                stem, ext = os.path.splitext(path)
                n = 2
                while norm(f"{stem} ({n}){ext}") in taken:
                    n += 1
                t.target_path = f"{stem} ({n}){ext}"
                key = norm(t.target_path)
                renamed += 1
            taken.setdefault(key, t)
        if renamed:
            logger.debug(f"{renamed} queued file(s) shared a save path with another file and were renamed.",
                         category="downloader")
        return renamed
