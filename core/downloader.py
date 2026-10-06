"""
Core Downloader & Task Execution Engine
Coordinates concurrent chunk streaming, SHA-256 validation, adaptive backoff,
multipart acceleration, WebP conversion, retry queues, and telemetry reporting.
"""

import os
import traceback
import sys
import shutil
import re
import time
import datetime
import hashlib
import random
import threading
import requests
import urllib.parse
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from PIL import Image

# Ensure project root is on sys.path even when executed directly
if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger
from core.filter_engine import FilterEngine, FilterOptions, MediaTypes, fit_path_for_windows
from core.providers import cookie_for_url, is_disabled, disabled_message, provider_for_host, KEMONO, COOMER, PAWCHIVE
from core.atomic_io import replace_file, atomic_write_text
from core.file_order import order_files
from core.path_utils import post_id_tag, post_info_name
from core.known_manager import KnownManager
from core.session_manager import SessionManager
from core.archive_manager import ArchiveManager

# Services hosted on Coomer rather than Kemono (used to pick the right mirror for Pawchive files)
COOMER_SERVICES = {"onlyfans", "fansly", "candfans"}


# Sites that embed Vimeo players: domain-locked embeds only play for the creator's own site
EMBED_REFERERS = {
    "patreon": "https://www.patreon.com/",
    "fanbox": "https://www.fanbox.cc/",
    "fantia": "https://fantia.jp/",
    "subscribestar": "https://www.subscribestar.com/",
    "gumroad": "https://gumroad.com/",
    "boosty": "https://boosty.to/",
}

_NOT_A_VIDEO_ERRORS = ("unsupported url", "no video", "there's no video", "no media found", "not a video", "has no video")


def is_not_a_video_error(msg: str) -> bool:
    """yt-dlp couldn't find a video at the link at all (a web page, a picture post…)."""
    m = (msg or "").lower()
    return any(k in m for k in _NOT_A_VIDEO_ERRORS)


def is_preview_url(url: str) -> bool:
    """Thumbnail-server URLs: a small preview copy, never the full-size original."""
    return "/thumbnail/" in (url or "")


def needs_full_size_upgrade(existing_size: int, server_size: int, target_path: str, options) -> bool:
    """An existing file is a small / preview copy that should be replaced by the full-size one."""
    if options is None or getattr(options, "download_thumbnails_only", False):
        return False
    if server_size and server_size > 0 and existing_size < server_size * 0.75:
        return True
    if getattr(options, "redownload_small_files", False):
        min_lim, _ = FilterEngine.get_effective_size_limits(options)
        threshold = min_lim if min_lim else (150 * 1024)
        ext = os.path.splitext((target_path or "").lower())[1]
        return existing_size < threshold and (ext in MediaTypes.IMAGE_EXTS or ext == ".webp")
    return False


# Files download to "<name>.part" and get their real name only once complete, so a file under its
# real name is always a finished one (an interrupted download used to look complete on the next run)
PART_SUFFIX = ".part"

_CONTACT_HEADERS = {
    "X-Contact": "https://github.com/whyamihere773/Pawchive-Downloader",
    "X-Client-Notice": (
        "Pawchive Downloader user here! Love your site. If my client is ever causing server strain, "
        "please open an issue on GitHub instead of a hard ban and I'll fix my request pacing immediately."
    ),
}

_HASH_PATH_RE = re.compile(r"/[0-9a-f]{2}/[0-9a-f]{2}/([0-9a-f]{64})\.[^/?#]+(?:[?#]|$)", re.IGNORECASE)


def content_hash_from_url(url: str) -> str:
    """Kemono, Pawchive and Coomer store files as /ab/cd/<sha256>.<ext>: the name is the SHA-256 of the
    file's content, which gives a free check that a download arrived complete and undamaged."""
    if not url or is_preview_url(url) or provider_for_host(url) not in (KEMONO, COOMER, PAWCHIVE):
        return ""
    m = _HASH_PATH_RE.search(url.split("://", 1)[-1])
    return m.group(1).lower() if m else ""


def _fq(name: str) -> str:
    """A file name for the ?f= link parameter ('#', '&', '%' etc. used to cut the link short)."""
    return urllib.parse.quote(name, safe="")


def _content_range(value: str):
    """(start, total) from a Content-Range header; total is 0 when unknown."""
    m = re.match(r"^\s*bytes\s+(?:(\d+)-\d+|\*)/(\d+|\*)\s*$", value or "", re.IGNORECASE)
    if not m:
        return None, 0
    start = int(m.group(1)) if m.group(1) is not None else None
    return start, (int(m.group(2)) if m.group(2).isdigit() else 0)


def _remove_quietly(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


_post_info_lock = threading.Lock()


def _write_post_info(path: str, content: str, post_id: str = "") -> None:
    try:
        with _post_info_lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if not os.path.exists(path):
                atomic_write_text(path, content)
            else:
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        existing = f.read()
                except OSError:
                    existing = ""

                # Avoid duplicate entry if this post was already recorded
                if post_id and f"Post ID: {post_id}" in existing:
                    return

                separator = "\n" + "=" * 80 + "\n\n"
                with open(path, "a", encoding="utf-8", errors="replace") as f:
                    if existing and not existing.endswith("\n\n"):
                        if not existing.endswith("\n"):
                            f.write("\n")
                        f.write(separator)
                    f.write(content)
    except Exception as ex:
        logger.debug(f"Could not save {path}: {ex}", category="file")


from services.multipart_downloader import download_multipart_file
from services.link_extractor import LinkExtractor
from services.ytdlp_manager import YtDlpManager
from core.audio_tagger import AudioTagger
from services.telegram_service import TelegramService


class DownloadTask:
    def __init__(
        self,
        url: str,
        target_path: str,
        post_title: str,
        creator_name: str,
        service: str,
        post_id: str,
        file_id: str,
        file_size: int = 0,
        expected_sha256: str = "",
        is_ytdlp: bool = False,
        is_telegram: bool = False,
        telegram_channel_id: str = "",
        telegram_message_id: int = 0,
        batch_id: str = "",
        post_url: str = "",
        post_date: str = "",
        user_id: str = ""
    ):
        self.url = url
        self.target_path = target_path
        self.post_title = post_title
        self.creator_name = creator_name
        self.service = service
        self.user_id = user_id
        self.post_id = post_id
        self.file_id = file_id
        self.file_size = file_size
        self.expected_sha256 = expected_sha256
        self.is_ytdlp = is_ytdlp
        self.is_telegram = is_telegram
        self.telegram_channel_id = telegram_channel_id
        self.telegram_message_id = telegram_message_id
        self.batch_id = batch_id or (f"{service}_{creator_name}_{post_id}".strip("_") if (service or creator_name or post_id) else "batch_default")
        self.post_url = post_url
        self.post_date = post_date
        self.downloaded_bytes = 0
        self.status = "pending"  # "pending", "downloading", "completed", "failed", "cancelled"
        self.error_msg = ""
        self.retry_count = 0
        self.speed_bps = 0
        self.speed_str = "0 KB/s"
        self.eta_str = "--"
        self.progress_pct = 0
        self.fallback_urls: List[str] = []
        self._tried_urls: List[str] = []      # servers tried for this file (for the log)
        self.used_preview = False   # True when only the small preview copy could be fetched
        self.post_info_path = ""    # post_info.txt to write once this post's first file is saved

    @property
    def filename(self) -> str:
        return os.path.basename(self.target_path)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "target_path": self.target_path,
            "filename": self.filename,
            "post_title": self.post_title,
            "creator_name": self.creator_name,
            "service": self.service,
            "post_id": self.post_id,
            "file_id": self.file_id,
            "file_size": self.file_size,
            "downloaded_bytes": self.downloaded_bytes,
            "status": self.status,
            "error_msg": self.error_msg,
            "retry_count": self.retry_count,
            "is_ytdlp": self.is_ytdlp,
            "is_telegram": getattr(self, "is_telegram", False),
            "telegram_channel_id": getattr(self, "telegram_channel_id", ""),
            "telegram_message_id": getattr(self, "telegram_message_id", 0),
            "batch_id": getattr(self, "batch_id", ""),
            "post_url": getattr(self, "post_url", ""),
            "post_date": getattr(self, "post_date", ""),
            "user_id": getattr(self, "user_id", ""),
            "expected_sha256": getattr(self, "expected_sha256", ""),
            "fallback_urls": list(getattr(self, "fallback_urls", []) or []),
            "used_preview": bool(getattr(self, "used_preview", False)),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DownloadTask":
        t = cls(
            url=d.get("url", ""),
            target_path=d.get("target_path", ""),
            post_title=d.get("post_title", ""),
            creator_name=d.get("creator_name", ""),
            service=d.get("service", ""),
            post_id=str(d.get("post_id", "")),
            file_id=d.get("file_id", ""),
            file_size=int(d.get("file_size", 0)),
            expected_sha256=d.get("expected_sha256", ""),
            is_ytdlp=bool(d.get("is_ytdlp", False)),
            is_telegram=bool(d.get("is_telegram", False)),
            telegram_channel_id=str(d.get("telegram_channel_id", "")),
            telegram_message_id=int(d.get("telegram_message_id", 0)),
            batch_id=d.get("batch_id", ""),
            post_url=d.get("post_url", ""),
            post_date=d.get("post_date", ""),
            user_id=str(d.get("user_id", "") or "")
        )
        t.fallback_urls = [u for u in (d.get("fallback_urls") or []) if isinstance(u, str)]
        t.used_preview = bool(d.get("used_preview", False))
        t.downloaded_bytes = int(d.get("downloaded_bytes", 0))
        t.status = d.get("status", "pending")
        t.error_msg = d.get("error_msg", "")
        t.retry_count = int(d.get("retry_count", 0))
        return t


class KemonoDownloader:
    """
    Multi-threaded, resumable download engine with progress telemetry,
    smart 429 rate limit backoff, adaptive thread throttling, and yt-dlp embedded media support.
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
        self._rate_limit_lock = threading.Lock()
        self._rate_limit_cooldown_until = 0.0
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._is_running = False
        self._session_id: int = 0
        self._download_thread: Optional[threading.Thread] = None
        self.current_options: Optional[FilterOptions] = None
        self._active_responses: set = set()
        self._active_resp_lock = threading.Lock()
        self._worker_sessions: set = set()
        self._worker_sessions_lock = threading.Lock()
        self._thread_local = threading.local()
        self._clean_cookie: str = ""
        self._post_info_pending: Dict[str, str] = {}   # post_info.txt path -> text, written after the first file
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
        self._stable_clean_count: int = 0

        # Smart Learning ETA and speed smoothing telemetry
        self._speed_samples = deque(maxlen=40)
        self._smoothed_speed: float = 0.0
        self._medium_speed: float = 0.0
        self._smoothed_eta: Optional[float] = None
        self._last_eta_calc_time: float = 0.0
        self._last_progress_emit_time: float = 0.0

        # Harvested external cloud links (populated in links-only mode)
        self.harvested_links: Dict[str, List[str]] = {}
        self.harvested_links_records: List[Dict[str, Any]] = []

        # Callbacks for UI updates
        self.on_progress_update: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_task_status_changed: Optional[Callable[[DownloadTask], None]] = None
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
        if sess is None:
            sess = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=1)
            sess.mount("https://", adapter)
            sess.mount("http://", adapter)
            sess.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "*/*"
            })
            # No Cookie here: the login cookie is added per request, only for the site it belongs to
            # (it used to go to every host, Bunkr and other file servers included)
            self._thread_local.session = sess
            with self._worker_sessions_lock:
                self._worker_sessions.add(sess)
        return sess

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
            for resp in list(self._active_responses):
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
        logger.info("Download paused.", category="downloader")
        self._save_recovery_checkpoint()
        if self.on_pause_changed:
            try:
                self.on_pause_changed(True)
            except Exception as e:
                logger.error(f"Error in on_pause_changed callback: {e}", category="downloader")

    def resume(self):
        self._pause_event.clear()
        self._speed_samples.clear()
        self._smoothed_speed = 0.0
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
        self._smoothed_speed = 0.0
        self._medium_speed = 0.0
        self._smoothed_eta = None
        self._last_eta_calc_time = 0.0
        self._last_progress_emit_time = 0.0
        self.adaptive_state = "optimal"
        self.adaptive_status_text = ""
        logger.info("Downloader state fully reset.", category="downloader")

    def _save_recovery_checkpoint(self, options: Optional[FilterOptions] = None, async_write: bool = False):
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
            rec.save_checkpoint(tasks=self.tasks, settings=opts_dict, status=status, async_write=async_write)
        except Exception as e:
            logger.debug(f"Could not persist recovery checkpoint: {e}", category="session")

    @staticmethod
    def extract_passwords(text: str) -> list:
        """
        Smartly extracts password candidates from post text using CJK-aware boundary heuristics.
        Delegates to LinkExtractor.extract_passwords for unified multilingual password extraction.
        """
        if not text:
            return []
        return LinkExtractor.extract_passwords(text)

    @staticmethod
    def extract_norm_rel_key(f_dict: Dict[str, Any]) -> str:
        """
        Extracts a canonical relative key/hash identifying the exact underlying file across mirrors.
        Handles relative paths (/ab/cd/...), thumbnail URLs, CDN URLs, and cum.st storage keys.
        """
        if not isinstance(f_dict, dict):
            return ""
        rp = f_dict.get("path") or f_dict.get("storageKey") or ""
        if not rp:
            return ""
        rp = rp.split("?")[0]
        if re.match(r'^[0-9a-f]{16,}$', rp):
            return rp.lower()
        m_match = re.search(r'/(?:data|thumbnail/data)?(/[0-9a-f]{2}/[0-9a-f]{2}/[^\s?#]+)', rp, re.IGNORECASE)
        if m_match:
            return m_match.group(1).lower()
        if "://" in rp:
            rp = "/" + rp.split("://")[-1].partition("/")[-1]
        if rp.startswith("/data/"):
            rp = rp[5:]
        if not rp.startswith("/"):
            rp = f"/{rp}"
        return rp.lower()

    def _resolve_pawchive_deferred_attachments(self, post: Dict[str, Any], domain: str = "pawchive.pw") -> int:
        """
        Fetches the post HTML page and resolves signed t1.pawchive.pw temporary download URLs
        for attachments flagged with 'deferred: True' (oversized files in Pawchive's 30-day temporary storage).
        """
        if not isinstance(post, dict):
            return 0
        attachments = post.get("attachments", [])
        if not isinstance(attachments, list):
            return 0
        deferred_items = [
            a for a in attachments
            if isinstance(a, dict) and a.get("deferred") and not a.get("path")
        ]
        if not deferred_items:
            return 0

        post_id = str(post.get("id") or "")
        service = post.get("service") or ""
        user_id = str(post.get("user") or "")
        if not post_id or not service or not user_id:
            return 0

        eff_domain = domain if "pawchive" in (domain or "") else "pawchive.pw"
        page_url = f"https://{eff_domain}/{service}/user/{user_id}/post/{post_id}"
        logger.debug(f"Fetching post HTML to resolve {len(deferred_items)} temporary oversized file(s): {page_url}", category="downloader")

        session = requests.Session()
        session_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": f"https://{eff_domain}/",
            "X-Contact": "https://github.com/whyamihere773/Pawchive-Downloader",
            "X-Client-Notice": (
                "Pawchive Downloader user here! Love your site. If my client is ever causing server strain, "
                "please open an issue on GitHub instead of a hard ban and I'll fix my request pacing immediately."
            )
        }
        session.headers.update(session_headers)
        try:
            resp = session.get(page_url, timeout=20)
            if resp.status_code != 200 or not resp.text:
                logger.warning(f"Could not fetch HTML for post {post_id} (HTTP {resp.status_code}) to resolve temporary files", category="downloader")
                return 0

            matches = re.findall(r'(?:href|src)=["\'](https://t1\.pawchive\.pw/f/[^"\']+)["\']', resp.text)
            temp_map: Dict[str, str] = {}
            for raw_u in matches:
                u = raw_u.replace("&amp;", "&")
                path_part = u.split("?")[0].split("/")[-1]
                name = urllib.parse.unquote(path_part)
                if name and name not in temp_map:
                    temp_map[name] = u

            if not temp_map:
                logger.info(f"Post {post_id} has {len(deferred_items)} deferred attachment(s), but temporary links are expired or unavailable", category="downloader")
                return 0

            resolved_count = 0
            lower_map = {k.lower(): v for k, v in temp_map.items()}
            for att in deferred_items:
                att_name = att.get("name") or ""
                matched_url = temp_map.get(att_name) or lower_map.get(att_name.lower())
                if matched_url:
                    att["path"] = matched_url
                    att["is_temporary"] = True
                    resolved_count += 1

            if resolved_count > 0:
                logger.info(f"✨ Resolved {resolved_count}/{len(deferred_items)} temporary oversized file(s) from t1.pawchive.pw for post {post_id}", category="downloader")
            return resolved_count
        except Exception as e:
            logger.warning(f"Failed resolving temporary attachments for post {post_id}: {e}", category="downloader")
            return 0
        finally:
            try:
                session.close()
            except Exception:
                pass

    def build_tasks_from_posts(
        self,
        posts: List[Dict[str, Any]],
        creator_name: str,
        service: str,
        domain: str,
        base_dir: str,
        options: FilterOptions,
        batch_id: Optional[str] = None,
        artist_dir: Optional[str] = None,
        user_id: str = ""
    ) -> List[DownloadTask]:
        """
        Filters posts and attachments, building the list of download tasks with structured paths.
        """
        new_tasks = []
        self._unmatched_known_count = 0
        self.last_build_cancelled = False
        # cancel() bumps _session_id, so only a cancel issued during this build counts;
        # a stale flag left over from an earlier cancelled scan must not abort it.
        build_session_id = self._session_id

        def _build_cancelled() -> bool:
            return self._cancel_event.is_set() and self._session_id != build_session_id

        creator_clean = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")

        # ── 1. Manga / Comic Mode Sorting ─────────────────────────────────────
        posts_to_process = list(posts)
        if options.manga_mode:
            logger.info("Manga Mode active: Sorting posts chronologically (oldest first)...", category="downloader")
            def _post_date_key(p):
                pub = p.get("published") or p.get("added") or "0000-00-00"
                pid = str(p.get("id", "0"))
                return (pub, pid)
            posts_to_process.sort(key=_post_date_key)
        elif options.tag_folder_mode:
            logger.info("Tag Folder Mode active: Sorting posts by primary tag and chronological index...", category="downloader")
            def _post_tag_and_index_key(p):
                tags = FilterEngine.normalize_tags(p.get("tags"))
                primary_tag = tags[0].strip().lower() if tags else "zzz_untagged"
                pub = p.get("published") or p.get("added") or "0000-00-00"
                pid = str(p.get("id", "0"))
                return (primary_tag, pub, pid)
            posts_to_process.sort(key=_post_tag_and_index_key)

        # Character name discovery from post titles (reported only; nothing is added to the Known list)
        new_chars = self.known_manager.find_candidates_in_posts(posts_to_process)
        if new_chars:
            logger.debug(
                f"Spotted {len(new_chars)} possible character name(s) in post titles (not added to Known list): "
                f"{', '.join(new_chars[:6])}{'...' if len(new_chars) > 6 else ''}",
                category="known"
            )

        logger.info(f"Structuring download plan for {len(posts_to_process)} posts...", category="downloader")

        extracted_links_all: Dict[str, List[str]] = {}
        extracted_records_all: List[Dict[str, Any]] = []
        folder_file_counts: Dict[str, int] = defaultdict(int)
        post_folder_registry: Dict[str, str] = {}
        # Track target paths already assigned in this build mapping to metadata: {post_id, post_title, rel_path}
        _batch_paths: Dict[str, Dict[str, Any]] = {}
        _batch_rel_paths: Dict[str, Set[str]] = defaultdict(set)
        _post_dup_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        build_post_infos: Dict[Tuple[str, str], str] = {}
        build_text_posts: List[Tuple[str, str, str]] = []

        for post_idx, post in enumerate(posts_to_process, 1):
            if _build_cancelled():
                self.last_build_cancelled = True
                logger.info("Task structuring cancelled by user.", category="downloader")
                return []

            post_id = str(post.get("id", ""))
            raw_title = post.get("title") or ""
            if not raw_title:
                # cum.st uses captionHtml; strip tags for a plain-text title
                caption_raw = post.get("caption") or post.get("captionHtml") or ""
                caption_plain = re.sub(r'<[^>]+>', '', caption_raw).strip()
                raw_title = caption_plain[:80] if caption_plain else ""
            post_title = (raw_title or "Untitled").strip()
            published = post.get("published", "") or ""
            if isinstance(published, (int, float)):
                try:
                    date_str = datetime.datetime.fromtimestamp(published).strftime("%Y-%m-%d")
                except Exception:
                    date_str = str(published)
            else:
                pub_str = str(published)
                date_str = pub_str.split("T")[0] if "T" in pub_str else (pub_str[:10] if pub_str else "")

            # Construct canonical web post link for manual inspection/testing
            post_user = str(post.get("user") or "")
            if domain and service and post_user and post_id:
                task_post_url = f"https://{domain}/{service}/user/{post_user}/post/{post_id}"
            elif domain and service and post_id:
                task_post_url = f"https://{domain}/{service}/post/{post_id}"
            else:
                task_post_url = ""

            # Apply post filter (date range, skip words, character whitelist)
            keep_post, reason = FilterEngine.should_keep_post(post, options)
            if not keep_post:
                logger.debug(f"Skipped post [{post_id}] '{post_title}': {reason}", category="filter")
                continue

            # ── Link extraction in "Only Links" mode ───────────────────────────
            if options.file_type == MediaTypes.LINKS:
                found_links = LinkExtractor.extract_links_from_post(post)
                if found_links:
                    total_found = sum(len(v) for v in found_links.values())
                    logger.info(
                        f"🔗 [{post_title}] Found {total_found} external link(s):",
                        category="downloader"
                    )
                    for platform, urls in found_links.items():
                        for u in urls:
                            logger.info(f"   [{platform.upper()}] {u}", category="downloader")
                            extracted_records_all.append({
                                "title": post_title,
                                "url": u,
                                "platform": platform,
                                "service": service,
                                "creator": creator_name,
                                "post_id": post_id,
                                "tags": post.get("tags") or []
                            })
                        extracted_links_all.setdefault(platform, []).extend(urls)
                else:
                    logger.debug(
                        f"No external links found in post: '{post_title}'",
                        category="downloader"
                    )
                # Skip all media downloads for this post
                continue

            # Determine parent directory for this post
            creator_folder = f"{creator_clean} [{service}]"
            if artist_dir:
                norm_art = os.path.normpath(artist_dir)
                norm_base = os.path.normpath(base_dir) if base_dir else ""
                if norm_base and (norm_art == norm_base or norm_art.startswith(norm_base + os.sep)):
                    base_root = base_dir
                else:
                    base_root = os.path.dirname(norm_art) or base_dir
                creator_folder = os.path.basename(norm_art) or creator_folder
            else:
                base_root = base_dir

            if options.separate_by_known:
                folder_parts = [base_root]
                cand_filenames = []
                _mf = post.get("file")
                if isinstance(_mf, dict) and _mf.get("name"):
                    cand_filenames.append(_mf["name"])
                for _att in post.get("attachments") or []:
                    if isinstance(_att, dict) and _att.get("name"):
                        cand_filenames.append(_att["name"])

                creator_prof = None
                if getattr(self, "archive_manager", None) and self.archive_manager.is_enabled:
                    creator_prof = self.archive_manager.get_creator_character_profile(
                        service=service,
                        creator_id=creator_clean,
                        creator_name=creator_clean,
                        base_dirs=[d for d in {base_dir, base_root} if d]
                    )

                matched_hierarchy = self.known_manager.find_matching_hierarchy(
                    post_title,
                    tags=post.get("tags"),
                    filenames=cand_filenames,
                    content=post.get("content"),
                    creator_profile=creator_prof
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
                    self._unmatched_known_count = getattr(self, "_unmatched_known_count", 0) + 1
                    folder_parts.append("Other")

                folder_parts.append(creator_folder)
            else:
                if artist_dir:
                    folder_parts = [artist_dir]
                else:
                    folder_parts = [base_dir, creator_folder]

            # Tag-based subfolder (Pawchive / cum.st only — other providers have no tags)
            if options.tag_folder_mode:
                post_tags = FilterEngine.normalize_tags(post.get("tags"))
                if post_tags:
                    first_tag = FilterEngine.clean_filesystem_text(post_tags[0], max_len=60, fallback="tag")
                    folder_parts.append(first_tag)
                else:
                    folder_parts.append("Untagged")

            creator_base_parts = list(folder_parts)
            post_subfolder_name = ""

            # Post subfolder
            if options.subfolder_per_post:
                clean_title = FilterEngine.clean_filesystem_text(post_title, max_len=100, fallback="Untitled")
                if options.date_prefix and date_str:
                    folder_name = f"[{date_str}] {clean_title}"
                else:
                    folder_name = clean_title

                candidate_folder = os.path.join(*folder_parts, folder_name)
                # If another DIFFERENT post previously claimed this exact folder path (e.g. identical titles or blank titles),
                # append the post ID to ensure each post retains its own dedicated directory.
                if candidate_folder in post_folder_registry and post_folder_registry[candidate_folder] != post_id:
                    folder_name = f"{folder_name} [{post_id}]"
                    candidate_folder = os.path.join(*folder_parts, folder_name)
                    logger.debug(
                        f"Post folder collision: Different post with matching title detected. Separated into '{folder_name}'",
                        category="downloader"
                    )
                post_folder_registry[candidate_folder] = post_id
                folder_parts.append(folder_name)
                post_subfolder_name = folder_name

            post_folder = os.path.join(*folder_parts)

            def _get_dest_folder(fn: str) -> str:
                grp = getattr(options, "group_file_type", "none")
                if grp in ("post", "creator"):
                    cat = FilterEngine.get_file_type_category(fn)
                    if grp == "creator":
                        if options.subfolder_per_post and post_subfolder_name:
                            return os.path.join(*creator_base_parts, cat, post_subfolder_name)
                        return os.path.join(*creator_base_parts, cat)
                    else:  # "post"
                        return os.path.join(post_folder, cat)
                return post_folder

            # Smart password extraction (search full caption + comments)
            caption_text = post.get("content") or post.get("captionHtml") or post.get("caption") or ""
            caption_clean = re.sub(r'<br\s*/?>', '\n', caption_text, flags=re.IGNORECASE)
            caption_clean = re.sub(r'<[^>]+>', '', caption_clean).strip()
            _pw_search_text = caption_clean
            if post.get("comments_text"):
                _pw_search_text += "\n" + post.get("comments_text")
            passwords = self.extract_passwords(_pw_search_text)

            # Post info / description archiver: prepared now, written once a file of the post is saved
            # (planning used to create folders holding only post_info.txt for posts that were filtered
            # out, skipped or cancelled)
            post_task_start = len(new_tasks)
            post_info_path = ""
            post_info_content = ""
            if options.save_post_metadata:
                try:
                    # Grouped by type at the creator root, the post's own folders sit inside each type
                    # folder (Images/<post>, Video/<post>…); the info file goes where a text file of the
                    # post goes (Other/<post>) instead of a stray <post> folder at the creator root.
                    # Without a folder per post, all posts share the creator root folder into a single
                    # "post_info.txt" so the folder isn't cluttered with hundreds of text files.
                    info_dir = post_folder
                    info_name = post_info_name()
                    if not post_subfolder_name:
                        info_dir = _get_dest_folder(info_name)
                        info_name = post_info_name()
                    elif getattr(options, "group_file_type", "none") == "creator":
                        info_dir = _get_dest_folder(info_name)
                    info_path = fit_path_for_windows(os.path.join(info_dir, info_name))

                    should_prepare_info = True
                    if post_subfolder_name:
                        should_prepare_info = not os.path.exists(info_path)
                    elif os.path.exists(info_path):
                        try:
                            with open(info_path, "r", encoding="utf-8", errors="replace") as _chk_f:
                                should_prepare_info = f"Post ID: {post_id}" not in _chk_f.read()
                        except OSError:
                            should_prepare_info = True

                    if should_prepare_info:
                        tags_list = FilterEngine.normalize_tags(post.get("tags"))
                        tags_str = ", ".join(tags_list)

                        # Build creator profile URL
                        post_user = str(post.get("user") or "")
                        if domain and service and post_user:
                            creator_url = f"https://{domain}/{service}/user/{post_user}"
                        elif domain and service:
                            creator_url = f"https://{domain}/{service}"
                        else:
                            creator_url = ""

                        # Collect attached file names (built from the files already collected below)
                        all_file_names = []
                        seen_info_keys = set()
                        _main_f = post.get("file")
                        if isinstance(_main_f, dict) and (_main_f.get("path") or _main_f.get("storageKey")):
                            _k = self.extract_norm_rel_key(_main_f)
                            if _k:
                                seen_info_keys.add(_k)
                            _fname = (_main_f.get("name") or "").strip().rstrip(".,;!?")
                            if _fname:
                                all_file_names.append(_fname)
                        for _att in (post.get("attachments") or []):
                            if isinstance(_att, dict) and (_att.get("path") or _att.get("storageKey")):
                                _k = self.extract_norm_rel_key(_att)
                                if not options.keep_duplicates and _k and _k in seen_info_keys:
                                    continue
                                if _k:
                                    seen_info_keys.add(_k)
                                _fname = (_att.get("name") or "").strip().rstrip(".,;!?")
                                if _fname:
                                    all_file_names.append(_fname)

                        # Extract external links
                        ext_links_dict = LinkExtractor.extract_links_from_post(post)
                        ext_links_flat = []
                        for _plat, _urls in sorted(ext_links_dict.items()):
                            for _u in _urls:
                                ext_links_flat.append(f"[{_plat.upper()}] {_u}")

                        # Extract embedded media (yt-dlp targets)
                        embed_urls = LinkExtractor.extract_embed_urls(post)



                        info_content = f"Title: {post_title}\n"
                        info_content += f"Post ID: {post_id}\n"
                        info_content += f"Creator: {creator_name} [{service}]\n"
                        if creator_url:
                            info_content += f"Creator URL: {creator_url}\n"
                        if task_post_url:
                            info_content += f"Post URL: {task_post_url}\n"
                        info_content += f"Published: {date_str}\n"
                        if tags_str:
                            info_content += f"Tags: {tags_str}\n"

                        if passwords:
                            info_content += "\n--- Detected Password(s) ---\n"
                            for pw in passwords:
                                info_content += f"  {pw}\n"

                        info_content += f"\n--- Content ---\n{caption_clean}\n"

                        if post.get("comments_text"):
                            info_content += f"\n--- Comments ---\n{post.get('comments_text')}\n"

                        if all_file_names:
                            info_content += "\n--- Attached Files ---\n"
                            for fn in all_file_names:
                                info_content += f"  {fn}\n"

                        if ext_links_flat:
                            info_content += "\n--- External Links ---\n"
                            for lnk in ext_links_flat:
                                info_content += f"  {lnk}\n"

                        if embed_urls:
                            info_content += "\n--- Embedded Media ---\n"
                            for eu in embed_urls:
                                info_content += f"  {eu}\n"

                        post_info_path, post_info_content = info_path, info_content
                except Exception as ex:
                    logger.debug(f"Could not prepare post_info.txt for {post_id}: {ex}", category="file")

            # Automatically record external cloud links & embeds in download archive database
            if self.archive_manager and self.archive_manager.is_enabled:
                try:
                    ext_links = LinkExtractor.extract_links_from_post(post)
                    for _plat, _urls in ext_links.items():
                        for _u in _urls:
                            self.archive_manager.record_link(
                                service=service,
                                creator_id=user_id or post_user,
                                post_id=post_id,
                                url=_u,
                                creator_name=creator_name,
                                post_title=post_title,
                                link_title=f"[{_plat.upper()}] {_u}"
                            )
                    embed_links = LinkExtractor.extract_embed_urls(post)
                    for _eu in embed_links:
                        self.archive_manager.record_link(
                            service=service,
                            creator_id=user_id or post_user,
                            post_id=post_id,
                            url=_eu,
                            creator_name=creator_name,
                            post_title=post_title,
                            link_title=_eu
                        )
                except Exception as _ar_l_err:
                    logger.debug(f"Could not archive links for post {post_id}: {_ar_l_err}", category="archive")

            # Collect files: post.file and post.attachments with deduplication
            files_to_process = []
            seen_post_file_keys: Dict[str, int] = {}

            main_file = post.get("file")
            attachments = post.get("attachments", []) or []

            # If Pawchive post has deferred temporary attachments, resolve signed download URLs from post HTML
            if getattr(options, "download_pawchive_temporary_files", True):
                has_deferred = any(
                    isinstance(a, dict) and a.get("deferred") and not a.get("path")
                    for a in attachments
                )
                if has_deferred and ("pawchive" in (domain or "") or "pawchive" in str(post.get("origin", "")) or "pawchive" in str(post.get("domain", ""))):
                    self._resolve_pawchive_deferred_attachments(post, domain=domain or "pawchive.pw")
                    attachments = post.get("attachments", []) or []

            # Check if post contains attachments or inline content images
            has_valid_attachments = any(
                isinstance(a, dict) and (a.get("path") or a.get("storageKey")) and not a.get("locked")
                for a in attachments
            )
            has_content_images = False
            if options.scan_content_images:
                content_html = post.get("content", "") or post.get("captionHtml", "") or ""
                if FilterEngine.extract_content_images(content_html):
                    has_content_images = True
            has_other_files = has_valid_attachments or has_content_images

            # Determine whether to skip the primary post.file (cover picture)
            skip_main_cover = False
            if options.skip_post_covers:
                if has_other_files:
                    skip_main_cover = True
                elif main_file and isinstance(main_file, dict):
                    mf_name = (main_file.get("name") or main_file.get("originalFilename") or "").lower()
                    if mf_name.startswith("cover.") or mf_name.startswith("cover_") or mf_name.startswith("preview."):
                        skip_main_cover = True

            if not skip_main_cover and main_file and isinstance(main_file, dict) and (main_file.get("path") or main_file.get("storageKey")):
                k = self.extract_norm_rel_key(main_file)
                if k:
                    seen_post_file_keys[k] = 0
                files_to_process.append(dict(main_file))

            if isinstance(attachments, list):
                for att in attachments:
                    if isinstance(att, dict) and (att.get("path") or att.get("storageKey")):
                        # If skip_post_covers is enabled, skip attachments named cover.* when other files exist
                        if options.skip_post_covers and (has_other_files or len(attachments) > 1):
                            att_name = (att.get("name") or att.get("originalFilename") or "").lower()
                            if att_name.startswith("cover.") or att_name.startswith("cover_") or att_name.startswith("preview."):
                                continue

                        k = self.extract_norm_rel_key(att)
                        if not options.keep_duplicates and k and k in seen_post_file_keys:
                            # Upgrade metadata if att has non-preview or better name
                            idx = seen_post_file_keys[k]
                            existing = files_to_process[idx]
                            if existing.get("preview_only") and not att.get("preview_only"):
                                existing["preview_only"] = False
                            if att.get("name") and not att.get("name", "").lower().startswith("cover"):
                                existing["name"] = att.get("name")
                            continue
                        if k:
                            seen_post_file_keys[k] = len(files_to_process)
                        files_to_process.append(dict(att))

            post_file_count = len(files_to_process)

            # Scan inline content images if enabled
            if options.scan_content_images:
                allowed_exts = FilterEngine.parse_extensions_list(options.exact_extensions) if options.exact_extensions else None
                if allowed_exts is None or any(ext in MediaTypes.IMAGE_EXTS for ext in allowed_exts):
                    content_html = post.get("content", "") or post.get("captionHtml", "") or ""
                    content_imgs = FilterEngine.extract_content_images(content_html)
                    for ci in content_imgs:
                        ci_dict = {"name": os.path.basename(ci), "path": ci}
                        k = self.extract_norm_rel_key(ci_dict)
                        if not options.keep_duplicates and k and k in seen_post_file_keys:
                            continue
                        if k:
                            seen_post_file_keys[k] = len(files_to_process)
                        files_to_process.append(ci_dict)

            # "File order in posts": decides which file is #1. The post's own files and the pictures
            # embedded in its text are ordered separately, so the post's files are numbered the same
            # way the Post Selection window lists them.
            file_order = getattr(options, "file_order", "posted")
            if file_order != "posted" and len(files_to_process) > 1:
                def _order_name(f):
                    return f.get("name") or f.get("originalFilename") or ""
                files_to_process = (order_files(files_to_process[:post_file_count], file_order, _order_name)
                                    + order_files(files_to_process[post_file_count:], file_order, _order_name))

            # Process each file attachment
            for file_idx, fobj in enumerate(files_to_process, 1):
                # Ignore paywalled locked attachments
                if fobj.get("locked"):
                    continue

                raw_name = fobj.get("name") or fobj.get("originalFilename") or ""
                # API responses can include trailing commas/punctuation in filenames
                # (e.g. "cover.jpeg,") that corrupt CDN query params and file extensions.
                raw_name = raw_name.strip().rstrip(".,;!?")
                # Derive extension from mimeType when filename is missing or has no extension
                _mime_ext_map = {
                    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
                    "image/gif": ".gif", "image/webp": ".webp", "image/avif": ".avif",
                    "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
                    "video/x-matroska": ".mkv", "video/avi": ".avi",
                    "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/wav": ".wav",
                    "audio/flac": ".flac", "audio/aac": ".aac",
                }
                mime_type = fobj.get("mimeType") or fobj.get("mime_type") or ""
                mime_ext = _mime_ext_map.get(mime_type.lower().split(";")[0].strip(), "")
                if not raw_name or not os.path.splitext(raw_name)[1]:
                    # No filename or no extension — build one from storageKey/id + mimeType
                    base_id = (
                        fobj.get("storageKey") or
                        fobj.get("sha256") or
                        str(fobj.get("id") or f"file_{file_idx}")
                    )
                    raw_name = f"{base_id}{mime_ext or '.jpg'}" if not raw_name else f"{raw_name}{mime_ext}"
                rel_path = fobj.get("path") or fobj.get("storageKey") or ""
                if not rel_path:
                    continue

                # Filter file
                file_bytes = fobj.get("bytes")
                keep_file, f_reason = FilterEngine.should_keep_file(raw_name, options, file_size=file_bytes)
                if not keep_file:
                    logger.debug(f"Skipped file '{raw_name}': {f_reason}", category="filter")
                    continue

                # Normalize relative path (strip full host prefixes if present in inline content)
                original_url = None  # preserve original full URL as first candidate
                norm_path = rel_path

                # Detect if rel_path is a bare storageKey (hex-only, no slashes) — cum.st format
                is_storage_key = bool(
                    re.match(r'^[0-9a-f]+$', norm_path) and
                    not norm_path.startswith("http") and
                    "/" not in norm_path and
                    len(norm_path) >= 16  # at least 16 hex chars
                )

                variants_list = fobj.get("variants") or []
                extra_cum_variants = []

                if is_storage_key and "cum.st" in domain:
                    # Select best primary variant (e.g. original.jpg / original.mp4)
                    primary_variant = None
                    if isinstance(variants_list, list) and variants_list:
                        for v in variants_list:
                            if isinstance(v, dict) and v.get("name"):
                                vname = v.get("name")
                                if "original" in vname.lower():
                                    primary_variant = vname
                                else:
                                    extra_cum_variants.append(vname)
                        if not primary_variant and isinstance(variants_list[0], dict):
                            primary_variant = variants_list[0].get("name")

                    _fn_ext = os.path.splitext(raw_name)[1].lstrip(".")
                    ext = _fn_ext or (mime_ext.lstrip(".") if mime_ext else "") or "jpg"
                    if not primary_variant:
                        primary_variant = f"original.{ext}"

                    original_url = f"https://e1.cum.st/media/{norm_path}/{primary_variant}"
                    norm_path = f"/{norm_path[:2]}/{norm_path[2:4]}/{norm_path}.{ext}"  # legacy fallback path
                elif norm_path.startswith("http://") or norm_path.startswith("https://"):
                    is_pawchive_temp = "t1.pawchive.pw" in norm_path or bool(fobj.get("is_temporary"))
                    if is_pawchive_temp:
                        # Pawchive temporary oversized storage on t1.pawchive.pw uses signed URLs (?e=...&s=...)
                        # Preserve full signed URL with query parameters intact
                        original_url = norm_path
                        # Clean relative path for deduplication and file_id: /f/<hash>/<filename>
                        path_without_query = norm_path.split("?")[0]
                        clean_part = path_without_query.split("://")[-1].partition("/")[-1]
                        norm_path = f"/{clean_part}" if not clean_part.startswith("/") else clean_part
                    else:
                        # Preserve the original CDN URL as the first candidate
                        original_url = norm_path.split("?")[0]  # strip existing query params
                        # Check for e1.cum.st/media/ pattern — keep as-is, extract a norm_path for fallbacks
                        m_cumst = re.match(r'https?://[^/]*cum\.st/media/([0-9a-f]{64})/([^?#]+)', norm_path)
                        if m_cumst:
                            storage_key = m_cumst.group(1)
                            variant = m_cumst.group(2)  # e.g. "original.jpg"
                            ext = os.path.splitext(variant)[1].lstrip(".") or "jpg"
                            norm_path = f"/{storage_key[:2]}/{storage_key[2:4]}/{storage_key}.{ext}"
                        else:
                            match_data = re.search(r'/(?:data|thumbnail/data)?(/[0-9a-f]{2}/[0-9a-f]{2}/[^\s?#]+)', norm_path, re.IGNORECASE)
                            if match_data:
                                norm_path = match_data.group(1)
                            else:
                                norm_path = norm_path.split("://")[-1].partition("/")[-1]
                                norm_path = f"/{norm_path}" if not norm_path.startswith("/") else norm_path

                # Ensure path starts with / and doesn't duplicate /data
                clean_rel = norm_path if norm_path.startswith("/") else f"/{norm_path}"
                if clean_rel.startswith("/data/"):
                    clean_rel = clean_rel[5:]
                if not clean_rel.startswith("/"):
                    clean_rel = f"/{clean_rel}"

                # Deduplication check before incrementing folder file counts:
                # Prevents incrementing the sequence counter (001_, 002_, ...) for duplicate files
                norm_key = self.extract_norm_rel_key(fobj) or clean_rel.lower()
                target_dest_dir = _get_dest_folder(raw_name)
                if not options.keep_duplicates and norm_key in _batch_rel_paths[target_dest_dir]:
                    logger.debug(
                        f"Skipping identical duplicate attachment: '{raw_name}' ({clean_rel}) in post '{post_title}'",
                        category="file"
                    )
                    continue

                # Track sequential file index per folder
                folder_file_counts[target_dest_dir] += 1
                seq_idx = folder_file_counts[target_dest_dir]

                # Format filename based on selected naming style
                sanitized_name = FilterEngine.format_custom_filename(
                    original_filename=raw_name,
                    post_title=post_title,
                    post_date=date_str,
                    post_index=post_idx,
                    file_index=file_idx,
                    options=options,
                    folder_index=seq_idx,
                    post_id=post_id,
                    artist=creator_name,
                    service=service,
                    user_id=str(post.get("user") or "")
                )
                # Strip trailing punctuation/commas that would corrupt the ?f= CDN query parameter
                # and trigger ERR_RESPONSE_HEADERS_MULTIPLE_CONTENT_DISPOSITION in browsers.
                sanitized_name = sanitized_name.rstrip(".,;!? \t")

                # Auto-detect provider from original URL host if present (overrides domain arg)
                effective_domain = domain
                if original_url:
                    orig_host = original_url.split("://")[-1].split("/")[0].lower()
                    if "cum.st" in orig_host:
                        effective_domain = "cum.st"
                    elif "pawchive" in orig_host:
                        effective_domain = "pawchive.pw"
                    elif "coomer" in orig_host:
                        effective_domain = "coomer.st"
                    elif "kemono" in orig_host:
                        effective_domain = "kemono.cr"

                is_preview_only = bool(fobj.get("preview_only"))
                candidate_urls = []

                if is_preview_only or options.download_thumbnails_only:
                    # When download_thumbnails_only is enabled or an attachment is flagged preview_only,
                    # strictly query thumbnail CDN servers — never pull the heavy full-sized original file.
                    if "pawchive" in effective_domain:
                        thumb_host = "img.pawchive.pw"
                    elif "cum.st" in effective_domain:
                        thumb_host = "img.cum.st"
                    elif "coomer" in effective_domain:
                        thumb_host = "img.cum.st" if is_disabled("coomer.st") else "img.coomer.st"
                    else:
                        thumb_host = "img.pawchive.pw" if is_disabled("kemono.cr") else "img.kemono.cr"
                    candidate_urls.append(f"https://{thumb_host}/thumbnail/data{clean_rel}")

                    # If this is a video file, the thumbnail is served as an image, so adjust filename extension
                    _, orig_ext = os.path.splitext(sanitized_name.lower())
                    if orig_ext in MediaTypes.VIDEO_EXTS:
                        sanitized_name = f"{os.path.splitext(sanitized_name)[0]}.jpg"
                else:
                    is_pawchive_temp = bool(original_url and "t1.pawchive.pw" in original_url) or bool(fobj.get("is_temporary"))
                    if is_pawchive_temp and original_url:
                        # Temporary oversized files on t1.pawchive.pw are signed URLs.
                        # Append the signed URL directly as the primary candidate (do not fallback to file.pawchive.pw)
                        candidate_urls.append(original_url)
                    else:
                        is_thumbnail_url = bool(
                            original_url and (
                                "/thumbnail/" in original_url or
                                "img.pawchive" in original_url or
                                "img.kemono" in original_url or
                                "img.coomer" in original_url
                            )
                        )

                        # If original_url is not a thumbnail, try it first
                        if original_url and not is_thumbnail_url:
                            candidate_urls.append(f"{original_url}?f={_fq(sanitized_name)}")

                        fallback_thumb_url = None

                        if "cum.st" in effective_domain:
                            # Append any secondary variants (e.g. 720p.mp4, 240p.mp4) from the API as immediate fallbacks
                            if is_storage_key:
                                for ev in extra_cum_variants:
                                    u_ev = f"https://e1.cum.st/media/{rel_path}/{ev}"
                                    if u_ev not in candidate_urls:
                                        candidate_urls.append(u_ev)
                            elif not original_url or is_thumbnail_url:
                                candidate_urls.append(f"https://cum.st/data{clean_rel}?f={_fq(sanitized_name)}")
                            # Fallbacks
                            candidate_urls.append(f"https://cum.st/data{clean_rel}")
                            candidate_urls.append(f"https://img.cum.st/data{clean_rel}")
                            fallback_thumb_url = f"https://img.cum.st/thumbnail/data{clean_rel}"
                        elif "pawchive" in effective_domain:
                            # Pawchive first; then Kemono / Coomer, which hold the same files (same hash
                            # paths). Posts Pawchive imported from Kemono but hasn't copied yet
                            # (origin "kemono" / preview_state "pending") only exist there, so they go first.
                            full_url = f"https://file.pawchive.pw/data{clean_rel}?f={_fq(sanitized_name)}"
                            mirror_host = "coomer.st" if service.lower() in COOMER_SERVICES else "kemono.cr"
                            mirror_url = f"https://{mirror_host}/data{clean_rel}?f={_fq(sanitized_name)}"
                            not_copied_yet = str(post.get("origin", "")).lower() in ("kemono", "coomer") or str(post.get("preview_state", "")).lower() == "pending"
                            order = [mirror_url, full_url] if not_copied_yet else [full_url, mirror_url]
                            for u in order:
                                if u not in candidate_urls and not is_disabled(u):
                                    candidate_urls.append(u)
                            fallback_thumb_url = f"https://img.pawchive.pw/thumbnail/data{clean_rel}"
                        elif "coomer" in effective_domain:
                            # coomer.st/data/… redirects to the file server that holds the file.
                            # While Coomer is switched off, cum.st's file server is tried instead.
                            coomer_hosts = ["coomer.st", "n1.coomer.st", "n2.coomer.st", "n3.coomer.st", "n4.coomer.st"]
                            if is_disabled("coomer.st"):
                                coomer_hosts = ["cum.st"]
                            for host in coomer_hosts:
                                u = f"https://{host}/data{clean_rel}?f={_fq(sanitized_name)}"
                                if u not in candidate_urls:
                                    candidate_urls.append(u)
                            fallback_thumb_url = f"https://{'img.cum.st' if is_disabled('coomer.st') else 'img.coomer.st'}/thumbnail/data{clean_rel}"
                        else:  # kemono / default — kemono.cr/data/… redirects to the right file server
                            for host in ["kemono.cr", "n1.kemono.cr", "n2.kemono.cr", "n3.kemono.cr", "n4.kemono.cr"]:
                                u = f"https://{host}/data{clean_rel}?f={_fq(sanitized_name)}"
                                if u not in candidate_urls:
                                    candidate_urls.append(u)
                            paw_u = f"https://file.pawchive.pw/data{clean_rel}?f={_fq(sanitized_name)}"
                            if paw_u not in candidate_urls:
                                candidate_urls.append(paw_u)
                            fallback_thumb_url = f"https://{'img.pawchive.pw' if is_disabled('kemono.cr') else 'img.kemono.cr'}/thumbnail/data{clean_rel}"

                        # Only append thumbnail fallback if enabled in options
                        allow_thumb_fallback = getattr(options, "fallback_to_thumbnails", False)
                        if allow_thumb_fallback:
                            if fallback_thumb_url and fallback_thumb_url not in candidate_urls:
                                candidate_urls.append(fallback_thumb_url)
                            if is_thumbnail_url and original_url and original_url not in candidate_urls:
                                candidate_urls.append(f"{original_url}?f={_fq(sanitized_name)}")

                # Switched-off sites (Kemono / Coomer) are never contacted
                candidate_urls = [u for u in candidate_urls if not is_disabled(u)]
                file_url = candidate_urls[0] if candidate_urls else f"https://file.pawchive.pw/data{clean_rel}?f={_fq(sanitized_name)}"
                target_dest_dir = _get_dest_folder(sanitized_name)
                target_path = fit_path_for_windows(os.path.join(target_dest_dir, sanitized_name))
                file_id = f"{post_id}_{clean_rel}"

                # Resolve filename collisions: distinguish between duplicate attachments in the SAME post
                # versus collisions from a DIFFERENT post (e.g. when subfolders are disabled).
                if target_path in _batch_paths:
                    prev_entry = _batch_paths[target_path]
                    prev_post_id = prev_entry.get("post_id", "")
                    prev_post_title = prev_entry.get("post_title", "")
                    prev_rel = prev_entry.get("rel_path", "")

                    # Check if identical file attached twice in the same post
                    if prev_post_id == post_id and prev_rel == clean_rel and not options.keep_duplicates:
                        logger.debug(
                            f"Skipping identical duplicate attachment: '{sanitized_name}' in post '{post_title}'",
                            category="file"
                        )
                        continue

                    stem, ext = os.path.splitext(sanitized_name)

                    if prev_post_id != post_id:
                        # Collision across DIFFERENT posts (e.g. subfolder_per_post is disabled).
                        # Album "posts" use the file's link as their id: a link in a file name made
                        # an invalid path, so ids that aren't short and plain become a short hash.
                        pid_tag = post_id_tag(post_id)
                        disambig_name = f"{stem} [{pid_tag}]{ext}"
                        target_path = fit_path_for_windows(os.path.join(target_dest_dir, disambig_name))
                        counter = 2
                        while target_path in _batch_paths:
                            disambig_name = f"{stem} [{pid_tag}] ({counter}){ext}"
                            target_path = fit_path_for_windows(os.path.join(target_dest_dir, disambig_name))
                            counter += 1
                        logger.debug(
                            f"Different-post filename collision: '{sanitized_name}' belongs to post '{post_title}' ({post_id}), "
                            f"already used by previous post '{prev_post_title}' ({prev_post_id}) — saved as '{disambig_name}'",
                            category="file"
                        )
                    else:
                        # Duplicate attachment within the SAME post (e.g. raw and captioned versions, or multiple variants)
                        hash_hint = os.path.splitext(os.path.basename(clean_rel))[0][-6:] or \
                                    hashlib.md5(clean_rel.encode()).hexdigest()[:6]
                        disambig_name = f"{stem}_{hash_hint}{ext}"
                        target_path = fit_path_for_windows(os.path.join(target_dest_dir, disambig_name))
                        counter = 2
                        while target_path in _batch_paths:
                            disambig_name = f"{stem}_{hash_hint}_{counter}{ext}"
                            target_path = fit_path_for_windows(os.path.join(target_dest_dir, disambig_name))
                            counter += 1
                        logger.debug(
                            f"Same-post duplicate attachment: '{sanitized_name}' already queued in post '{post_title}' — "
                            f"saving variant as '{disambig_name}'",
                            category="file"
                        )

                    # Also update the candidate URLs to use the disambiguated display name
                    candidate_urls = [
                        u.replace(f"?f={_fq(sanitized_name)}", f"?f={_fq(disambig_name)}").replace(f"&f={_fq(sanitized_name)}", f"&f={_fq(disambig_name)}")
                        for u in candidate_urls
                    ]
                    file_url = candidate_urls[0] if candidate_urls else file_url

                _batch_paths[target_path] = {
                    "post_id": post_id,
                    "post_title": post_title,
                    "rel_path": clean_rel
                }
                # Record the normalised key so future files in this folder can detect duplicates
                # regardless of whether an index prefix changes their target filename.
                _batch_rel_paths[target_dest_dir].add(norm_key)

                webp_path = os.path.splitext(target_path)[0] + ".webp"
                raw_dest_dir = _get_dest_folder(raw_name)
                raw_path = os.path.join(raw_dest_dir, raw_name)
                raw_webp = os.path.splitext(raw_path)[0] + ".webp"
                # Also check for the prefixed variant on disk (e.g. "001_filename.jpg") so that
                # re-runs with index prefix enabled don't re-download already-saved files.
                prefixed_raw = os.path.join(raw_dest_dir, f"{seq_idx:03d}_{raw_name}")
                prefixed_webp = os.path.splitext(prefixed_raw)[0] + ".webp"

                expected_sha = str(fobj.get("sha256") or fobj.get("hash") or "")

                # Skip if already recorded in download archive database (gallery-dl style) — unless the
                # copy still on disk is a small / preview one that should be upgraded to full size
                if self.archive_manager and self.archive_manager.is_enabled:
                    if self.archive_manager.is_archived(service=service, post_id=post_id, file_id=file_id, file_hash=expected_sha):
                        on_disk = next((cp for cp in (target_path, webp_path, raw_path, raw_webp, prefixed_raw, prefixed_webp)
                                        if os.path.exists(cp) and os.path.getsize(cp) > 0), None)
                        if not (on_disk and needs_full_size_upgrade(os.path.getsize(on_disk), int(file_bytes or 0), target_path, options)):
                            logger.info(f"📦 Skipping archived file: '{os.path.basename(target_path)}' (present in download archive)", category="file")
                            continue

                # Skip if already exists on disk at target_path, webp path, or raw name path
                if not options.keep_duplicates:
                    existing_disk_path = None
                    for candidate_path in (target_path, webp_path, raw_path, raw_webp, prefixed_raw, prefixed_webp):
                        if os.path.exists(candidate_path) and os.path.getsize(candidate_path) > 0:
                            existing_disk_path = candidate_path
                            break

                    if existing_disk_path:
                        existing_sz = os.path.getsize(existing_disk_path)
                        should_upgrade = False

                        if not options.download_thumbnails_only:
                            # 1. If server file size is known and existing disk file is significantly smaller (< 75% of server file)
                            if file_bytes and file_bytes > 0 and existing_sz < (file_bytes * 0.75):
                                should_upgrade = True
                            # 2. If user requested re-downloading small / thumbnail files
                            elif getattr(options, "redownload_small_files", False):
                                min_lim, _ = FilterEngine.get_effective_size_limits(options)
                                threshold = min_lim if min_lim else (150 * 1024)
                                _, _ext = os.path.splitext(target_path.lower())
                                if existing_sz < threshold and (_ext in MediaTypes.IMAGE_EXTS or _ext == ".webp"):
                                    should_upgrade = True

                        if not should_upgrade:
                            logger.info(f"⏳ Skipping existing file: '{os.path.basename(target_path)}' (already present on disk)", category="file")
                            continue
                        else:
                            logger.info(
                                f"🔄 Re-downloading '{os.path.basename(target_path)}' ({FilterEngine.format_size_str(existing_sz)}) "
                                f"to upgrade to full resolution",
                                category="file"
                            )

                task = DownloadTask(
                    url=file_url,
                    target_path=target_path,
                    post_title=post_title,
                    creator_name=creator_name,
                    service=service,
                    post_id=post_id,
                    file_id=file_id,
                    file_size=int(file_bytes or 0),  # pre-populate from API metadata for progress
                    expected_sha256=expected_sha,
                    batch_id=batch_id,
                    post_url=task_post_url,
                    post_date=date_str,
                    user_id=user_id or post_user
                )
                task.fallback_urls = candidate_urls[1:]
                if passwords:
                    try:
                        from core.archive_password_manager import archive_password_manager
                        _, _ext = os.path.splitext(target_path.lower())
                        from services.bulk_decompressor import ARCHIVE_EXTENSIONS
                        if _ext in ARCHIVE_EXTENSIONS:
                            archive_password_manager.record_archive_password(target_path, passwords[0])
                    except Exception as _pwe:
                        logger.debug(f"Could not pair archive password for {target_path}: {_pwe}", category="downloader")
                new_tasks.append(task)

            # ── 3. Scan Embedded Media Players (yt-dlp: Vimeo, YouTube, Streamable, RedGifs, etc.)
            should_download_embeds = options.download_embeds and options.file_type in (MediaTypes.ALL, MediaTypes.VIDEOS, MediaTypes.AUDIO)
            if should_download_embeds and options.exact_extensions:
                allowed_exts = FilterEngine.parse_extensions_list(options.exact_extensions)
                if allowed_exts:
                    should_download_embeds = any(ext in (MediaTypes.VIDEO_EXTS | MediaTypes.AUDIO_EXTS) for ext in allowed_exts)

            if should_download_embeds:
                embed_urls = LinkExtractor.extract_embed_urls(post)
                for embed_idx, e_url in enumerate(embed_urls, 1):
                    e_host = re.sub(r'[^a-zA-Z0-9]', '', e_url.split("://")[-1].split("/")[0])
                    e_name = f"embed_{embed_idx}_{e_host}.mp4"
                    e_dest_dir = _get_dest_folder(e_name)
                    e_target_path = fit_path_for_windows(os.path.join(e_dest_dir, e_name))
                    e_file_id = f"embed_{post_id}_{embed_idx}"

                    if self.archive_manager and self.archive_manager.is_enabled:
                        if self.archive_manager.is_archived(service=service, post_id=post_id, file_id=e_file_id):
                            logger.info(f"📦 Skipping archived embedded media: '{e_name}' (present in download archive)", category="file")
                            continue

                    if not options.keep_duplicates and os.path.exists(e_target_path) and os.path.getsize(e_target_path) > 0:
                        continue

                    e_task = DownloadTask(
                        url=e_url,
                        target_path=e_target_path,
                        post_title=post_title,
                        creator_name=creator_name,
                        service=service,
                        post_id=post_id,
                        file_id=e_file_id,
                        is_ytdlp=True,
                        batch_id=batch_id,
                        post_url=task_post_url,
                        post_date=date_str,
                        user_id=user_id or post_user
                    )
                    new_tasks.append(e_task)

            post_tasks = new_tasks[post_task_start:]
            if passwords and post_tasks:
                try:
                    from core.archive_password_manager import archive_password_manager
                    archive_password_manager.add_passwords(passwords)
                except Exception as _pwe:
                    logger.debug(f"Could not save the passwords of post {post_id}: {_pwe}", category="downloader")
            if post_info_path:
                info_key = (post_info_path, post_id)
                if post_tasks:
                    build_post_infos[info_key] = post_info_content
                    for _t in post_tasks:
                        _t.post_info_path = post_info_path
                elif not files_to_process:
                    build_text_posts.append((post_info_path, post_info_content, post_id))
                elif os.path.isdir(os.path.dirname(post_info_path)):
                    _write_post_info(post_info_path, post_info_content, post_id)

        # Post texts: text-only posts are saved now; the others once their first file is downloaded
        self._post_info_pending.update(build_post_infos)
        for _path, _content, _pid in build_text_posts:
            _write_post_info(_path, _content, _pid)

        # In links-only mode, store the harvested links and report summary
        if options.file_type == MediaTypes.LINKS:
            # Deduplicate across all platforms
            self.harvested_links = {
                k: sorted(list(set(v)))
                for k, v in extracted_links_all.items() if v
            }
            # Deduplicate records by URL
            seen_urls = set()
            deduped_records = []
            for r in extracted_records_all:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    deduped_records.append(r)
            self.harvested_links_records = deduped_records

            if self.archive_manager and self.archive_manager.is_enabled:
                for r in deduped_records:
                    try:
                        self.archive_manager.record_link(
                            service=r.get("service", ""),
                            creator_id=r.get("creator_id", "") or user_id,
                            post_id=r.get("post_id", ""),
                            url=r.get("url", ""),
                            creator_name=r.get("creator_name", "") or r.get("creator", ""),
                            post_title=r.get("post_title", "") or r.get("title", ""),
                            link_title=r.get("title", "")
                        )
                    except Exception as _ar_rec_err:
                        pass

            total = sum(len(v) for v in self.harvested_links.values())
            if total:
                logger.success(
                    f"🔗 Links scan complete: {total} unique external link(s) found across "
                    f"{len(self.harvested_links)} platform(s). Click 'Download Links' or 'Export Links'.",
                    category="downloader"
                )
            else:
                logger.warning(
                    "Links scan complete: No external cloud links were found in any posts.",
                    category="downloader"
                )
        else:
            self.harvested_links = {}
            self.harvested_links_records = []

        logger.success(f"Prepared {len(new_tasks)} file download tasks.", category="downloader")
        return new_tasks

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

        self._keep_paths_apart(tasks, [])
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
        self._save_recovery_checkpoint(options)

        self._download_thread = threading.Thread(
            target=self._run_download_loop,
            args=(options, cookie_str, session_id),
            daemon=True
        )
        self._download_thread.start()

    def append_tasks(self, new_tasks: List[DownloadTask], options: Optional[FilterOptions] = None, cookie_str: str = "") -> int:
        """
        Thread-safely appends new tasks with deduplication.
        If worker loop is running, new pending tasks will be dynamically scheduled.
        If idle and options are provided, launches download loop.
        """
        if not new_tasks:
            return 0

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
        self.tasks.extend(deduped)
        logger.info(f"Appended {len(deduped)} new tasks to download queue (total in queue: {len(self.tasks)}).", category="downloader")

        if not self._is_running and options is not None:
            self.start_download_queue(self.tasks, options, cookie_str)

        return len(deduped)

    @staticmethod
    def _keep_paths_apart(new_tasks: List[DownloadTask], existing: List[DownloadTask]) -> int:
        """Two different files may never share a save path, whatever queued them.

        Sharing one made the second count as "already downloaded", overwrite the first, or — when
        both downloaded at once — mix into the same temporary file. Files not downloaded yet get
        "name (2).ext", "name (3).ext"…; returns how many were renamed."""
        taken: Dict[str, DownloadTask] = {}
        for t in existing:
            if getattr(t, "target_path", ""):
                taken[os.path.normcase(t.target_path)] = t
        renamed = 0
        for t in new_tasks:
            path = getattr(t, "target_path", "")
            if not path:
                continue
            key = os.path.normcase(path)
            other = taken.get(key)
            if other is not None and other is not t and other.url != t.url                     and t.status in ("pending", "failed", "cancelled"):
                stem, ext = os.path.splitext(path)
                n = 2
                while os.path.normcase(f"{stem} ({n}){ext}") in taken:
                    n += 1
                t.target_path = f"{stem} ({n}){ext}"
                key = os.path.normcase(t.target_path)
                renamed += 1
            taken.setdefault(key, t)
        if renamed:
            logger.debug(f"{renamed} queued file(s) shared a save path with another file and were renamed.",
                         category="downloader")
        return renamed

    def cancel_batch(self, batch_id: str, notify: bool = False) -> int:
        """Cancels all pending and downloading tasks belonging to a specific batch_id."""
        cancelled = 0
        for t in self.tasks:
            if getattr(t, "batch_id", "") == batch_id and t.status in ("pending", "downloading", "retrying"):
                t.status = "cancelled"
                t.error_msg = "Download cancelled by user"
                t.progress_pct = 0
                t.speed_bps = 0
                t.speed_str = "0 KB/s"
                t.eta_str = "--"
                cancelled += 1
                if notify and self.on_task_status_changed:
                    self.on_task_status_changed(t)
        return cancelled

    def retry_batch_failed(self, batch_id: str, options: Optional[FilterOptions] = None, cookie_str: str = "") -> int:
        """Resets failed/cancelled tasks in a specific batch to pending and resumes download."""
        failed = []
        for t in self.tasks:
            t_bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if t_bid == batch_id:
                if t.status in ("failed", "cancelled") or (not self._is_running and t.status == "pending"):
                    failed.append(t)

        for t in failed:
            t.status = "pending"
            t.error_msg = ""
            t.downloaded_bytes = 0
            t.progress_pct = 0
            t.retry_count = getattr(t, "retry_count", 0) + 1
            if self.on_task_status_changed:
                self.on_task_status_changed(t)
        if failed and not self._is_running and options:
            self.start_download_queue(self.tasks, options, cookie_str)
        return len(failed)

    def remove_batch(self, batch_id: str) -> int:
        """Removes non-active tasks belonging to a batch from the queue."""
        initial_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if (getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")) != batch_id or t.status == "downloading"]
        return initial_count - len(self.tasks)

    def _trigger_rate_limit_backoff(self, threads_locked: bool = False):
        with self._rate_limit_lock:
            now = time.time()
            if now >= self._rate_limit_cooldown_until:
                if threads_locked:
                    self._rate_limit_cooldown_until = now + 30.0
                    logger.warning(
                        f"⚡ [Rate Limit Cooldown] HTTP 429 encountered! Threads locked at {self.max_workers} (cooldown 30s)...",
                        category="downloader"
                    )
                    return

                self._rate_limit_cooldown_until = now + 14.0
                old_workers = self.max_workers
                
                # Remember and lock down the stable ceiling
                # If old_workers hit 429, the ceiling is at most old_workers - 1
                if self._learned_stable_ceiling is None:
                    self._learned_stable_ceiling = max(1, old_workers - 1)
                else:
                    self._learned_stable_ceiling = max(1, min(self._learned_stable_ceiling, old_workers - 1))
                
                self._stable_clean_count = 0
                self.max_workers = max(1, min(old_workers - 2, self._learned_stable_ceiling - 1) if self._learned_stable_ceiling > 2 else 1)
                
                logger.warning(
                    f"⚡ [Adaptive Backoff] HTTP 429 encountered! Locked stable ceiling to {self._learned_stable_ceiling} threads. Dropping concurrency to {self.max_workers} threads (cooldown 14s)...",
                    category="adaptive"
                )
                if self.on_concurrency_throttled:
                    self.on_concurrency_throttled(self.max_workers)

    def retry_failed_tasks(self, options: FilterOptions, cookie_str: str, max_auto_retries: int = 5,
                           include_cancelled: bool = True) -> int:
        """Resets all tasks with status 'failed' (and 'cancelled', unless include_cancelled is False)
        to 'pending' up to max_auto_retries (5) and resumes downloading.

        Automatic retries pass include_cancelled=False so files the user stopped stay stopped.
        """
        skip_404 = (
            getattr(self.current_options, "skip_retry_404", False)
            if self.current_options
            else getattr(options, "skip_retry_404", False)
        )
        retry_statuses = ("failed", "cancelled") if include_cancelled else ("failed",)
        all_failed = [
            t for t in self.tasks
            if t.status in retry_statuses
            or (not self._is_running and t.status == "pending" and (getattr(t, "error_msg", "") or getattr(t, "retry_count", 0) > 0))
        ]
        if not all_failed:
            logger.info("No failed tasks to retry.", category="downloader")
            return 0

        eligible_tasks = []
        for t in all_failed:
            err = str(getattr(t, "error_msg", "")).lower()
            if skip_404 and ("404" in err or getattr(t, "http_status", 0) == 404):
                continue

            is_fatal_auth = any(f in err for f in (
                "key is not registered",
                "session expired",
                "session revoked",
                "authkey",
                "auth_key",
                "unregistered",
                "unauthorized"
            ))
            if is_fatal_auth:
                t.retry_capped = True
                continue

            cur_retries = getattr(t, "retry_count", 0)
            if cur_retries >= max_auto_retries:
                t.retry_capped = True
                orig_err = getattr(t, "error_msg", "") or "Download failed"
                if f"({max_auto_retries} retries)" not in orig_err:
                    t.error_msg = f"{orig_err} (Stopped after {max_auto_retries} retries)"
                if self.on_task_status_changed:
                    self.on_task_status_changed(t)
            else:
                eligible_tasks.append(t)

        if not eligible_tasks:
            logger.info(f"All {len(all_failed)} failed task(s) reached max retry limit ({max_auto_retries}). Skipped by auto-retry but preserved in modal.", category="downloader")
            return 0

        for t in eligible_tasks:
            t.retry_count = getattr(t, "retry_count", 0) + 1
            t.retry_capped = False
            t.status = "pending"
            t.error_msg = ""
            t.progress_pct = 0
            t.downloaded_bytes = 0
            t.speed_bps = 0
            t.speed_str = "0 KB/s"
            t.eta_str = "--"
            if self.on_task_status_changed:
                self.on_task_status_changed(t)

        logger.info(f"Flagged {len(eligible_tasks)} failed tasks for retry (attempt {eligible_tasks[0].retry_count}/{max_auto_retries}).", category="downloader")

        if not self._is_running:
            self.start_download_queue(self.tasks, options, cookie_str)

        return len(eligible_tasks)

    def retry_selected_tasks(self, selected_ids: List[str], options: FilterOptions, cookie_str: str) -> int:
        """Resets only user-selected failed or cancelled tasks to 'pending' and resumes downloading."""
        if not selected_ids:
            logger.info("No tasks selected for retry.", category="downloader")
            return 0

        skip_404 = (
            getattr(self.current_options, "skip_retry_404", False)
            if self.current_options
            else getattr(options, "skip_retry_404", False)
        )
        selected_set = set(selected_ids)
        target_tasks = []
        for t in self.tasks:
            is_match = (t.file_id in selected_set or t.url in selected_set or t.filename in selected_set)
            if not is_match:
                continue
            is_eligible = (
                t.status in ("failed", "cancelled")
                or (not self._is_running and t.status == "pending")
            )
            if not is_eligible:
                continue
            if skip_404 and ("404" in str(getattr(t, "error_msg", "")).lower() or getattr(t, "http_status", 0) == 404):
                continue
            target_tasks.append(t)

        if not target_tasks:
            logger.info("No matching failed tasks found to retry.", category="downloader")
            return 0

        for t in target_tasks:
            t.retry_count = getattr(t, "retry_count", 0) + 1
            t.retry_capped = False
            t.status = "pending"
            t.error_msg = ""
            t.progress_pct = 0
            t.downloaded_bytes = 0
            t.speed_bps = 0
            t.speed_str = "0 KB/s"
            t.eta_str = "--"
            if self.on_task_status_changed:
                self.on_task_status_changed(t)

        logger.info(f"Flagged {len(target_tasks)} selected tasks for retry.", category="downloader")

        if not self._is_running:
            self.start_download_queue(self.tasks, options, cookie_str)

        return len(target_tasks)

    @staticmethod
    def _task_context(task: "DownloadTask") -> str:
        """Extra lines for the log file when a file fails: where it came from and what was tried."""
        lines = []
        creator = " / ".join(x for x in (getattr(task, "creator_name", ""), getattr(task, "service", ""), str(getattr(task, "user_id", "") or "")) if x)
        if creator:
            lines.append(f"creator: {creator}")
        if getattr(task, "post_id", "") or getattr(task, "post_title", ""):
            lines.append(f"post: {task.post_id} {task.post_title!r}" + (f" ({task.post_url})" if getattr(task, "post_url", "") else ""))
        lines.append(f"url: {task.url}")
        tried = getattr(task, "_tried_urls", None) or []
        if len(tried) > 1 or (tried and tried[0] != task.url):
            lines.append("servers tried: " + ", ".join(tried))
        if getattr(task, "target_path", ""):
            lines.append(f"save to: {task.target_path}")
        if getattr(task, "retry_count", 0):
            lines.append(f"retry: {task.retry_count}")
        return "\n".join(lines)

    def _describe_run(self, options: FilterOptions, cookie_str: str, run_count: int) -> str:
        """The settings a download ran with, for the log file (bug reports need them)."""
        lines = [
            f"files in queue: {len(self.tasks)} ({run_count} to download in this run)",
            f"workers: {self.max_workers}",
            "login cookie: " + ("set in settings" if (cookie_str or "").strip() else "not set in settings (a saved login may still be used)"),
        ]
        folders = sorted({os.path.dirname(t.target_path) for t in self.tasks if getattr(t, "target_path", "")})
        if folders:
            lines.append(f"save folders ({len(folders)}): " + "; ".join(folders[:5]) + (" …" if len(folders) > 5 else ""))
        for key, value in sorted(vars(options).items()):
            if key.startswith("_") or callable(value):
                continue
            text = repr(value)
            lines.append(f"{key} = {text[:200] + '…' if len(text) > 200 else text}")
        return "\n".join(lines)

    def _run_download_loop(self, options: FilterOptions, cookie_str: str, session_id: int = 0):
        self.current_options = options
        self.start_time = time.time()
        self.downloaded_bytes = 0
        self._speed_samples.clear()
        self._smoothed_speed = 0.0
        self._medium_speed = 0.0
        self._smoothed_eta = None
        self._last_eta_calc_time = 0.0
        self._last_progress_emit_time = 0.0
        cpu_cores = max(4, os.cpu_count() or 16)
        self.current_options = options
        is_locked = getattr(self.current_options or options, "threads_locked", False)
        # Adaptive threading tops out at 8: beyond that the file servers rate-limit and the app
        # mostly spends its time on bookkeeping (16 threads made the window stop responding, #24)
        target_max_workers = min(cpu_cores, 8) if (options.adaptive_threading and not is_locked) else max(1, self.max_workers)
        last_scale_time = time.time()
        last_checkpoint_time = time.time()
        consecutive_successes = 0
        scale_step_interval = 8.0 # Check scaling up every 8 seconds of healthy throughput

        # Strict Telegram Concurrency Lock: Under ANY circumstance, Telegram downloads must never exceed 2 threads
        is_pure_telegram = bool(self.tasks) and all(
            getattr(t, "is_telegram", False) or getattr(t, "service", "") == "telegram" or (t.url and t.url.startswith("tg://"))
            for t in self.tasks
        )

        if is_pure_telegram:
            self.max_workers = min(self.max_workers, 2)
            target_max_workers = 2
            is_locked = True
            options.adaptive_threading = False
            logger.info("🔒 [Telegram] Concurrency locked strictly to 2 worker threads for MTProto session stability.", category="telegram")
            if self.on_concurrency_throttled:
                self.on_concurrency_throttled(self.max_workers)
        # If Adaptive Threading is enabled and threads are not locked, start with 2 worker threads and scale up to CPU core count
        elif options.adaptive_threading and not is_locked:
            self.max_workers = min(2, target_max_workers)
            logger.info(f"⚡ [Adaptive Threading] Active: Starting with {self.max_workers} worker threads (Max CPU limit: {target_max_workers} threads)...", category="adaptive")
            if self.on_concurrency_throttled:
                self.on_concurrency_throttled(self.max_workers)
        else:
            lock_label = " (Locked)" if is_locked else ""
            logger.info(f"Starting download pool with {self.max_workers} worker threads{lock_label}...", category="downloader")

        self._run_tasks = [t for t in self.tasks if t.status == "pending"]
        logger.debug("Download settings saved to the log file.", category="downloader",
                     details=self._describe_run(options, cookie_str, len(self._run_tasks)))

        # Auto-normalize cookie if user pasted raw JWT token, or load from encrypted auth_manager vault
        clean_cookie = cookie_str.strip() if cookie_str else ""
        if not clean_cookie:
            try:
                from core.auth_manager import auth_manager
                clean_cookie = auth_manager.get_credential("kemono", "cookie")
            except Exception:
                pass

        if clean_cookie:
            if clean_cookie.startswith("eyJ") and "session=" not in clean_cookie:
                clean_cookie = f"session={clean_cookie}"
            elif "=" not in clean_cookie:
                clean_cookie = f"session={clean_cookie}"
            logger.debug(f"Applied authenticated session cookie ({len(clean_cookie)} chars)", category="downloader")

        self._clean_cookie = clean_cookie

        active_futures = {}
        last_count_time = 0.0

        with ThreadPoolExecutor(max_workers=max(32, target_max_workers)) as executor:
            while not self._cancel_event.is_set() and (session_id == self._session_id):
                now = time.time()
                is_locked = getattr(self.current_options or options, "threads_locked", False)

                # Effective ceiling: learned ceiling if we encountered 429, else user target
                effective_ceiling = self._learned_stable_ceiling if self._learned_stable_ceiling is not None else target_max_workers

                # 1. Check Adaptive Scaling timer (every 5 seconds)
                if options.adaptive_threading and not is_locked and (now - last_scale_time >= scale_step_interval):
                    last_scale_time = now
                    # Only scale up if not currently in rate-limit cooldown
                    if now >= self._rate_limit_cooldown_until:
                        if self.max_workers < effective_ceiling:
                            self.max_workers += 1
                            consecutive_successes = 0
                            logger.info(
                                f"⚡ [Adaptive Threading] Connection stable. Scaling up concurrency to {self.max_workers}/{effective_ceiling} threads (ceiling: {effective_ceiling})...",
                                category="adaptive"
                            )
                            if self.on_concurrency_throttled:
                                self.on_concurrency_throttled(self.max_workers)
                        elif self._stable_clean_count >= 50 and effective_ceiling < target_max_workers:
                            # Long-term stability probe after 50 consecutive error-free downloads
                            self._learned_stable_ceiling += 1
                            self.max_workers += 1
                            self._stable_clean_count = 0
                            consecutive_successes = 0
                            logger.info(
                                f"⚡ [Adaptive Threading] Long-term stability verified (50+ clean files). Probing higher concurrency (+1 to {self.max_workers} threads)...",
                                category="adaptive"
                            )
                            if self.on_concurrency_throttled:
                                self.on_concurrency_throttled(self.max_workers)

                # 2. Check if rate-limit cooldown is active
                if now < self._rate_limit_cooldown_until:
                    rem = int(self._rate_limit_cooldown_until - now)
                    time.sleep(min(1.0, self._rate_limit_cooldown_until - now))
                    continue

                while self._pause_event.is_set():
                    time.sleep(0.5)
                    if self._cancel_event.is_set():
                        break

                # 3. Check finished futures
                done_futures = [f for f in active_futures if f.done()]
                for f in done_futures:
                    task = active_futures.pop(f)
                    try:
                        success, msg = f.result()
                        if success:
                            if task.status == "skipped" or (msg and msg.startswith("Skipped:")):
                                task.status = "skipped"
                                if not task.error_msg and msg.startswith("Skipped:"):
                                    task.error_msg = msg[len("Skipped:"):].strip()
                                task.progress_pct = 100
                                task.eta_str = "Skipped"
                                self._write_pending_post_info(task)
                                if self.on_task_status_changed:
                                    self.on_task_status_changed(task)
                            else:
                                task.status = "completed"
                                task.error_msg = ""
                                consecutive_successes += 1
                                self._stable_clean_count += 1
                                self.session_manager.record_downloaded_file(task.file_id)
                                self._write_pending_post_info(task)
                                if self.archive_manager and self.archive_manager.is_enabled and not getattr(task, "used_preview", False):
                                    self.archive_manager.record_file(
                                        service=task.service,
                                        creator_id=task.user_id,
                                        post_id=task.post_id,
                                        file_id=task.file_id,
                                        file_hash=task.expected_sha256,
                                        filename=task.filename,
                                        creator_name=task.creator_name,
                                        post_title=task.post_title,
                                        file_size=task.file_size,
                                        file_path=task.target_path
                                    )
                                if self.on_task_status_changed:
                                    self.on_task_status_changed(task)

                                # Fast Adaptive Scaling: Scale up after 10 consecutive successful files if below ceiling and interval elapsed
                                if options.adaptive_threading and not is_locked and not is_pure_telegram and consecutive_successes >= 10 and (now - last_scale_time >= 6.0):
                                    effective_ceiling = self._learned_stable_ceiling if self._learned_stable_ceiling is not None else target_max_workers
                                    if now >= self._rate_limit_cooldown_until and self.max_workers < effective_ceiling:
                                        self.max_workers += 1
                                        consecutive_successes = 0
                                        last_scale_time = now
                                        logger.info(
                                            f"⚡ [Adaptive Threading] Fast-scaling concurrency to {self.max_workers}/{effective_ceiling} threads...",
                                            category="adaptive"
                                        )
                                        if self.on_concurrency_throttled:
                                            self.on_concurrency_throttled(self.max_workers)
                        else:
                            consecutive_successes = 0
                            self._stable_clean_count = 0
                            if msg.startswith("429_RATE_LIMIT"):
                                # 429 Rate Limit encountered -> auto-retry after cooldown (30s if locked, 15s if adaptive)
                                wait_secs = 30 if is_locked else 15
                                task.status = "pending"
                                task.error_msg = f"Rate limited (429) — cooling down for {wait_secs}s before auto-retry"
                                if self.on_task_status_changed:
                                    self.on_task_status_changed(task)
                                self._trigger_rate_limit_backoff(threads_locked=is_locked)
                                last_scale_time = time.time() + float(wait_secs)
                            elif "Disk full" in msg:
                                task.status = "pending"
                                task.error_msg = msg
                                if self.on_task_status_changed:
                                    self.on_task_status_changed(task)
                                if not self._pause_event.is_set():
                                    self.pause()
                                    logger.warning(
                                        "⚠️ [Disk Full Alert] Destination drive ran out of space! Downloads paused to prevent file corruption. Please free space on your drive and click Resume.",
                                        category="downloader"
                                    )
                            else:
                                task.status = "failed"
                                task.error_msg = msg
                                if self.on_task_status_changed:
                                    self.on_task_status_changed(task)
                    except Exception as e:
                        consecutive_successes = 0
                        task.status = "failed"
                        task.error_msg = str(e)
                        logger.error(f"Error downloading {task.filename}: {e}", category="downloader",
                                     details=self._task_context(task) + "\n" + traceback.format_exc())
                        if self.on_task_status_changed:
                            self.on_task_status_changed(task)

                # Emit progress (counted a few times a second: counting a 100,000-file queue every
                # 50 ms took a quarter of a CPU core and made the window stutter)
                if now - last_count_time >= 0.3:
                    last_count_time = now
                    completed_count = sum(1 for t in self.tasks if t.status in ("completed", "skipped"))
                    failed_count = sum(1 for t in self.tasks if t.status == "failed")
                    self._emit_progress(completed_count, failed_count, len(self.tasks))

                # 4. If in cooldown or paused or cancelled, wait
                if time.time() < self._rate_limit_cooldown_until or self._pause_event.is_set() or self._cancel_event.is_set():
                    time.sleep(0.2)
                    continue

                # 5. Dispatch pending tasks up to self.max_workers with Anti-Burst Staggering
                current_active = len(active_futures)
                slots_available = max(0, self.max_workers - current_active)
                if slots_available > 0:
                    pending_tasks = self._collect_pending(slots_available * 4 + 8, now)
                    if not pending_tasks and current_active == 0:
                        pending_tasks = self._collect_pending(slots_available * 4 + 8, now, full=True)
                    if not pending_tasks and current_active == 0:
                        # Check if "auto retry at the end" is enabled dynamically
                        auto_retry_active = (
                            getattr(self.current_options, "auto_retry_at_end", False)
                            if self.current_options
                            else options.auto_retry_at_end
                        )
                        if auto_retry_active and not self._cancel_event.is_set():
                            skip_404 = (
                                getattr(self.current_options, "skip_retry_404", False)
                                if self.current_options
                                else getattr(options, "skip_retry_404", False)
                            )
                            all_failed = [t for t in self.tasks if t.status == "failed"]
                            failed_tasks = []
                            for t in all_failed:
                                err = str(getattr(t, "error_msg", "")).lower()
                                if skip_404 and ("404" in err or getattr(t, "http_status", 0) == 404):
                                    continue
                                is_fatal_auth = any(f in err for f in (
                                    "key is not registered",
                                    "session expired",
                                    "session revoked",
                                    "authkey",
                                    "auth_key",
                                    "unregistered",
                                    "unauthorized"
                                ))
                                if is_fatal_auth:
                                    t.retry_capped = True
                                    continue
                                if getattr(t, "retry_count", 0) < 5:
                                    failed_tasks.append(t)
                                else:
                                    t.retry_capped = True
                                    orig_err = getattr(t, "error_msg", "") or "Download failed"
                                    if "(Stopped after 5 retries)" not in orig_err:
                                        t.error_msg = f"{orig_err} (Stopped after 5 retries)"
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(t)

                            if failed_tasks:
                                retry_attempt = getattr(failed_tasks[0], 'retry_count', 0) + 1
                                wait_time = min(6.0, 1.5 * retry_attempt)
                                logger.info(
                                    f"🔄 Auto-retry triggered for {len(failed_tasks)} failed files (attempt {retry_attempt}/5, cooling down {wait_time:.1f}s)...",
                                    category="downloader"
                                )
                                for t in failed_tasks:
                                    t.retry_count = getattr(t, "retry_count", 0) + 1
                                    t.retry_capped = False
                                    t.status = "pending"
                                    t.error_msg = ""
                                    t.progress_pct = 0
                                    t.downloaded_bytes = 0
                                    t.speed_bps = 0
                                    t.speed_str = "0 KB/s"
                                    t.eta_str = "--"
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(t)
                                time.sleep(wait_time)
                                continue

                        # All tasks completed or finished
                        break

                    # Telegram concurrency cap (strictly max 2 active Telegram downloads under any circumstance)
                    active_tg_count = sum(
                        1 for t in active_futures.values()
                        if getattr(t, "is_telegram", False) or getattr(t, "service", "") == "telegram" or (t.url and t.url.startswith("tg://"))
                    )

                    tasks_to_dispatch = []
                    for task in pending_tasks:
                        if len(tasks_to_dispatch) >= slots_available:
                            break
                        is_tg = getattr(task, "is_telegram", False) or getattr(task, "service", "") == "telegram" or (task.url and task.url.startswith("tg://"))
                        if is_tg and (active_tg_count >= 2):
                            continue
                        if is_tg:
                            active_tg_count += 1
                        tasks_to_dispatch.append(task)

                    for i, task in enumerate(tasks_to_dispatch):
                        if self._cancel_event.is_set():
                            break
                        # Feature 4: Jittered Inter-Request Staggering (Anti-Burst Smoothing)
                        if i > 0 and not self._cancel_event.is_set():
                            is_pawchive_target = "pawchive" in (task.url or "").lower() or (getattr(task, "service", None) and "pawchive" in str(task.service).lower())
                            stagger = random.uniform(0.12, 0.22) if is_pawchive_target else 0.06
                            time.sleep(stagger)

                        if self._cancel_event.is_set():
                            break

                        task.status = "downloading"
                        if self.on_task_status_changed:
                            self.on_task_status_changed(task)
                        try:
                            fut = executor.submit(self._worker_download_task, task, options)
                            active_futures[fut] = task
                        except RuntimeError:
                            # Executor was shut down (e.g. cancelled)
                            task.status = "pending"
                            break

                # Feature 5: Track Adaptive Health State
                if is_locked:
                    if now < self._rate_limit_cooldown_until:
                        self.adaptive_state = "cooldown"
                        rem = max(1, int(self._rate_limit_cooldown_until - now))
                        self.adaptive_status_text = f"Cooldown: {rem}s (Locked {self.max_workers} threads)"
                    else:
                        self.adaptive_state = "locked"
                        self.adaptive_status_text = f"Locked ({self.max_workers} threads)"
                elif options.adaptive_threading:
                    if now < self._rate_limit_cooldown_until:
                        self.adaptive_state = "cooldown"
                        rem = max(1, int(self._rate_limit_cooldown_until - now))
                        self.adaptive_status_text = f"Cooldown: {rem}s ({self.max_workers} threads)"
                    elif self._learned_stable_ceiling is not None and self.max_workers >= self._learned_stable_ceiling:
                        self.adaptive_state = "optimal"
                        self.adaptive_status_text = f"Stable Lock ({self.max_workers} threads)"
                    elif self.max_workers >= target_max_workers:
                        self.adaptive_state = "optimal"
                        self.adaptive_status_text = f"Optimal ({self.max_workers} threads)"
                    else:
                        self.adaptive_state = "scaling"
                        effective_ceiling = self._learned_stable_ceiling if self._learned_stable_ceiling is not None else target_max_workers
                        self.adaptive_status_text = f"Scaling ({self.max_workers}/{effective_ceiling} threads)"
                else:
                    self.adaptive_state = "manual"
                    self.adaptive_status_text = f"Manual ({self.max_workers} threads)"

                # Periodic crash-proof checkpoint (every 30 seconds), written in the background: writing
                # 1,000+ tasks with fsync here used to stop new downloads from starting for 30-50 s on
                # slow drives (e.g. a Windows drive mounted under /mnt on Linux)
                if now - last_checkpoint_time >= 30.0:
                    last_checkpoint_time = now
                    self._save_recovery_checkpoint(options, async_write=True)

                time.sleep(0.05)

            # Cancel remaining active futures if cancelling
            for f in list(active_futures.keys()):
                try:
                    f.cancel()
                except Exception:
                    pass

        self._close_worker_sessions()
        try:
            from core.memory_collector import MemoryCollector
            MemoryCollector.instance().collect(reason="download finished")
        except Exception:
            pass

        # Discard exit handlers if this thread has been superseded by a newer download session
        if session_id != self._session_id:
            logger.debug(f"Discarding exit of superseded download session {session_id} (active: {self._session_id}).", category="downloader")
            return

        self._is_running = False
        duration = time.time() - self.start_time
        completed_count = sum(1 for t in self.tasks if t.status == "completed")
        failed_count = sum(1 for t in self.tasks if t.status == "failed")
        skipped_count = sum(1 for t in self.tasks if t.status == "skipped")
        self._emit_progress(completed_count + skipped_count, failed_count, len(self.tasks), force=True)
        live_infos = {(t.post_info_path, getattr(t, "post_id", "")) for t in self.tasks
                      if getattr(t, "post_info_path", "") and t.status not in ("completed", "skipped")}
        live_paths = {p for p, _ in live_infos}
        for _key in list(self._post_info_pending):
            if isinstance(_key, tuple):
                if _key not in live_infos:
                    self._post_info_pending.pop(_key, None)
            elif _key not in live_paths:
                self._post_info_pending.pop(_key, None)

        if self._cancel_event.is_set():
            rec = getattr(self.session_manager, "recovery_manager", None)
            if rec:
                rec.discard_recovery()
            logger.warning(f"Download cancelled. Completed: {completed_count}, Skipped: {skipped_count}, Failed/Cancelled: {failed_count}", category="downloader")
            if self.on_download_finished:
                self.on_download_finished(False, "Download cancelled by user.")
        else:
            # Keep a recovery journal only when something can still be done: files that never got
            # their turn, or failures a retry may fix. Missing (404) / locked (403) files and files
            # out of retries used to bring the recovery prompt back on every launch.
            def _retryable(t):
                err = str(getattr(t, "error_msg", "") or "")
                return not getattr(t, "retry_capped", False) and "404" not in err and "403" not in err
            unfinished = [t for t in self.tasks if t.status in ("pending", "downloading", "retrying")
                          or (t.status in ("failed", "cancelled") and _retryable(t))]
            if not unfinished:
                rec = getattr(self.session_manager, "recovery_manager", None)
                if rec:
                    rec.discard_recovery()
            else:
                self._save_recovery_checkpoint(options)
            skip_msg = f", {skipped_count} skipped" if skipped_count > 0 else ""
            # What this run did (a retry only handles the files it retried, not the whole queue)
            run_tasks = getattr(self, "_run_tasks", None) or []
            run_note = ""
            if run_tasks and len(run_tasks) < len(self.tasks):
                run_ok = sum(1 for t in run_tasks if t.status in ("completed", "skipped"))
                run_note = f" This run: {run_ok} of {len(run_tasks)} file(s) succeeded."
            failed_tasks = [t for t in self.tasks if t.status == "failed"]
            failed_list = "\n".join(
                f"{t.filename}: {t.error_msg or 'unknown error'}  ({t.url})" for t in failed_tasks
            )
            logger.success(
                f"Download completed in {duration:.1f}s! ({completed_count} successful{skip_msg}, {failed_count} errors){run_note}",
                category="downloader",
                details=(f"Failed files ({len(failed_tasks)}):\n{failed_list}" if failed_tasks else "")
            )
            if getattr(options, "separate_by_known", False):
                unmatched = getattr(self, "_unmatched_known_count", 0)
                ai_active = self.known_manager and getattr(self.known_manager, "_ai_recognition_enabled", False)
                if unmatched > 0 and not ai_active:
                    logger.info(
                        f"💡 [AI Tip] {unmatched} post(s) were saved to 'Other' without a matching character in Known.txt. "
                        "Enable Pawchive's offline AI in Settings → AI & Recognition to deduce obscure characters automatically.",
                        category="ai"
                    )
            if self.on_download_finished:
                self.on_download_finished(True, f"Completed: {completed_count} downloaded{skip_msg}, {failed_count} failed.")

    def _write_pending_post_info(self, task: DownloadTask) -> None:
        path = getattr(task, "post_info_path", "")
        post_id = getattr(task, "post_id", "")
        if path:
            content = self._post_info_pending.pop((path, post_id), None)
            if content is None:
                content = self._post_info_pending.pop(path, None)
            if content is not None:
                _write_post_info(path, content, post_id)

    def _collect_pending(self, limit: int, now: float, full: bool = False) -> List[DownloadTask]:
        """Up to `limit` pending files, without walking the whole queue 20 times a second: finished
        files pile up at the front, so the scan starts where pending ones began last time. A full
        scan every second picks up files that were put back in line (retries, rate limits)."""
        tasks = self.tasks
        if full or now - self._last_full_scan >= 1.0 or self._dispatch_cursor > len(tasks):
            self._dispatch_cursor = 0
            self._last_full_scan = now
        found: List[DownloadTask] = []
        first = None
        for i in range(self._dispatch_cursor, len(tasks)):
            t = tasks[i]
            if t.status == "pending":
                if first is None:
                    first = i
                found.append(t)
                if len(found) >= limit:
                    break
        self._dispatch_cursor = first if first is not None else len(tasks)
        return found

    def _worker_download_task(self, task: DownloadTask, options: FilterOptions):
        worker_session = self._get_worker_session()
        return self._download_single_file(task, worker_session, options)

    def _download_single_file(self, task: DownloadTask, session: Optional[requests.Session] = None, options: Optional[FilterOptions] = None) -> (bool, str):
        if session is None:
            session = self._get_worker_session()
        if options is None:
            options = self.current_options or FilterOptions()
        if self._cancel_event.is_set():
            return False, "Cancelled"

        while self._pause_event.is_set():
            time.sleep(0.5)
            if self._cancel_event.is_set():
                return False, "Cancelled"

        task.target_path = fit_path_for_windows(task.target_path)
        os.makedirs(os.path.dirname(task.target_path), exist_ok=True)
        task.status = "downloading"
        if self.on_task_status_changed:
            self.on_task_status_changed(task)

        # Check if file is already recorded in download archive database — unless the copy on disk is a
        # small / preview one that should be replaced by the full-size file (planning allowed that,
        # but this second check used to mark those files "already archived" anyway)
        if self.archive_manager and self.archive_manager.is_enabled:
            _webp = os.path.splitext(task.target_path)[0] + ".webp"
            _on_disk = next((p for p in (task.target_path, _webp) if os.path.exists(p) and os.path.getsize(p) > 0), None)
            _upgrade = bool(_on_disk) and needs_full_size_upgrade(os.path.getsize(_on_disk), task.file_size, task.target_path, options)
            if not _upgrade and self.archive_manager.is_archived(service=task.service, post_id=task.post_id, file_id=task.file_id, file_hash=task.expected_sha256):
                task.status = "completed"
                task.progress_pct = 100
                task.eta_str = "Done"
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                logger.info(f"📦 Skipping archived file: '{task.filename}' (present in download archive)", category="file")
                return True, "Already archived"

        # Check if file already exists completely on disk (including webp converted version)
        webp_path = os.path.splitext(task.target_path)[0] + ".webp"
        found_existing_path = None
        if not options.keep_duplicates:
            if os.path.exists(task.target_path) and os.path.getsize(task.target_path) > 0:
                found_existing_path = task.target_path
            elif os.path.exists(webp_path) and os.path.getsize(webp_path) > 0:
                found_existing_path = webp_path

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

            # Check if this existing file is a low-res thumbnail that needs upgrade to full resolution
            should_upgrade = False
            if not options.download_thumbnails_only:
                if task.file_size > 0 and existing_disk_sz < (task.file_size * 0.75):
                    should_upgrade = True
                elif getattr(options, "redownload_small_files", False):
                    min_lim, _ = FilterEngine.get_effective_size_limits(options)
                    threshold = min_lim if min_lim else (150 * 1024)
                    _, _ext = os.path.splitext(task.target_path.lower())
                    if existing_disk_sz < threshold and (_ext in MediaTypes.IMAGE_EXTS or _ext == ".webp"):
                        should_upgrade = True

            if not should_upgrade:
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
                logger.info(f"⏳ Skipping existing file: '{task.filename}' (already present on disk)", category="file")
                return True, "Already downloaded"
            else:
                is_upgrade_download = True
                logger.info(
                    f"🔄 Upgrading existing '{task.filename}' ({FilterEngine.format_size_str(existing_disk_sz)}) to full-resolution...",
                    category="file"
                )

        # Gentle inter-file pacing for Pawchive targets to prevent burst strain on host
        is_pawchive_target = "pawchive" in (task.url or "").lower() or (getattr(task, "service", None) and "pawchive" in str(task.service).lower())
        if is_pawchive_target and not self._cancel_event.is_set():
            pacing_delay = random.uniform(0.25, 0.40)
            steps = int(pacing_delay / 0.05)
            for _ in range(steps):
                if self._cancel_event.is_set():
                    return False, "Cancelled"
                time.sleep(0.05)

        # ── yt-dlp embedded media download execution ─────────────────────────
        if task.is_ytdlp:
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
                logger.warning(f"✖ [yt-dlp] {task.filename}: {msg}", category="ytdlp")
                return False, msg

        # ── Telegram MTProto media download execution ────────────────────────
        if getattr(task, "is_telegram", False):
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
                if "Cancelled" in msg:
                    task.status = "cancelled"
                    task.error_msg = msg
                else:
                    task.status = "failed"
                    task.error_msg = msg
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                logger.warning(f"✖ [Telegram] {task.filename}: {msg}", category="telegram")
                return False, msg

        # Continue an interrupted download from its .part file
        part_path = task.target_path + PART_SUFFIX
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
        all_urls = [u for u in [task.url] + list(task.fallback_urls) if not is_disabled(u)]
        if not all_urls:
            msg = disabled_message(task.url) or "This file's server is turned off"
            logger.warning(f"  ✖ {task.filename}: {msg}", category="file")
            return False, msg
        if options is not None and getattr(options, "download_thumbnails_only", False):
            full_urls, preview_urls = all_urls, []
        else:
            full_urls = [u for u in all_urls if not is_preview_url(u)] or all_urls
            preview_urls = [u for u in all_urls if u not in full_urls]
        urls_to_try = full_urls
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
            # Two passes across full-size mirrors; small preview copy ONLY if fallback_to_thumbnails is enabled
            allow_thumb_fallback = getattr(options, "fallback_to_thumbnails", False)
            pass_lists = [full_urls, full_urls] + ([preview_urls] if (preview_urls and allow_thumb_fallback) else [])
            for pass_idx, urls_to_try in enumerate(pass_lists):
                if pass_idx == 1:
                    time.sleep(1.5) # Brief jittered pause before second pass if all mirrors were busy

                for attempt_url in urls_to_try:
                    if self._cancel_event.is_set():
                        return False, "Cancelled"
                    if attempt_url not in task._tried_urls:
                        task._tried_urls.append(attempt_url)

                    # Provider-specific headers per host
                    req_headers = dict(range_headers)
                    u_low = attempt_url.lower()
                    if "bunkr" in u_low or "cdn.cr" in u_low or "scdn.st" in u_low or (hasattr(task, "service") and task.service == "bunkr"):
                        req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        req_headers["Referer"] = "https://bunkr.cr/"
                        req_headers["Origin"] = "https://bunkr.cr"
                        req_headers["Accept"] = "*/*"
                    elif "erome" in u_low:
                        req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        req_headers["Referer"] = "https://www.erome.com/"
                        req_headers["Accept"] = "*/*"
                    elif "nhentai" in u_low:
                        req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        req_headers["Referer"] = "https://nhentai.net/"
                        req_headers["Accept"] = "*/*"
                    elif "coomer" in u_low:
                        req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        req_headers["Referer"] = "https://coomer.st/"
                        req_headers["Accept"] = "*/*"
                    elif "pawchive" in u_low:
                        req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        req_headers["Referer"] = "https://pawchive.pw/"
                        req_headers["Accept"] = "*/*"
                    elif "cum.st" in u_low:
                        req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        req_headers["Referer"] = "https://cum.st/"
                        req_headers["Accept"] = "*/*"
                    else:
                        req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        req_headers["Referer"] = "https://kemono.cr/"
                        req_headers["Accept"] = "*/*"

                    # The login cookie only goes to the archive site it belongs to
                    if provider_for_host(attempt_url):
                        site_cookie = cookie_for_url(attempt_url, self._clean_cookie)
                        if site_cookie:
                            req_headers["Cookie"] = site_cookie
                        else:
                            req_headers.update(_CONTACT_HEADERS)

                    stream_timeout = (25, 60)
                    try:
                        resp = session.get(attempt_url, stream=True, timeout=stream_timeout, headers=req_headers)
                        if resp.status_code in (200, 206, 416):
                            task.url = attempt_url
                            break
                        elif resp.status_code == 404 and len(urls_to_try) <= 1:
                            # Definitive 404 on single-mirror host — skip second pass to avoid redundant server load
                            msg = "404 Not Found — file does not exist on server"
                            logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                            resp.close()
                            resp = None
                            return False, msg
                        elif resp.status_code == 403:
                            # If we sent a Range header, the CDN might be rejecting range requests with 403.
                            # Retry from byte 0 without Range and without cookies.
                            if "Range" in req_headers:
                                no_range_headers = {k: v for k, v in req_headers.items() if k.lower() != "range"}
                                try:
                                    fresh_resp = session.get(attempt_url, stream=True, timeout=stream_timeout, headers=no_range_headers)
                                    if fresh_resp.status_code in (200, 206):
                                        resp.close()
                                        resp = fresh_resp
                                        task.url = attempt_url
                                        mode = "wb"
                                        existing_size = 0
                                        break
                                    else:
                                        fresh_resp.close()
                                except Exception:
                                    pass

                            # Try without cookie and with full browser navigation headers (bypasses Cloudflare burst bot filter)
                            try:
                                browser_headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                                    "Sec-Fetch-Dest": "document",
                                    "Sec-Fetch-Mode": "navigate",
                                    "Sec-Fetch-Site": "none",
                                    "Sec-Fetch-User": "?1",
                                    "Upgrade-Insecure-Requests": "1",
                                }
                                clean_resp = requests.get(attempt_url, stream=True, timeout=stream_timeout, headers=browser_headers)
                                if clean_resp.status_code in (200, 206):
                                    resp.close()
                                    resp = clean_resp
                                    task.url = attempt_url
                                    mode = "wb"
                                    existing_size = 0
                                    break
                                elif clean_resp.status_code == 403 and len(urls_to_try) == 1:
                                    # Single-mirror CDN (like file.pawchive.pw) transient burst 403 — progressive pause & retry
                                    clean_resp.close()
                                    for delay in (1.5, 3.0):
                                        time.sleep(delay)
                                        if self._cancel_event.is_set():
                                            break
                                        retry_resp = requests.get(attempt_url, stream=True, timeout=stream_timeout, headers=browser_headers)
                                        if retry_resp.status_code in (200, 206):
                                            resp.close()
                                            resp = retry_resp
                                            task.url = attempt_url
                                            mode = "wb"
                                            existing_size = 0
                                            break
                                        else:
                                            retry_resp.close()
                                else:
                                    clean_resp.close()
                                if resp and resp.status_code in (200, 206):
                                    break
                            except Exception:
                                pass

                            # Still 403 — rotate to next mirror
                            logger.debug(f"  ↪ Mirror 403 on {attempt_url} — trying next mirror...", category="file")
                            if resp:
                                resp.close()
                                resp = None
                            continue
                        elif resp.status_code == 429:
                            # 429 on this mirror — smoothly rotate to next available mirror
                            logger.debug(f"  ↪ Mirror 429 on {attempt_url} — rotating to next mirror...", category="file")
                            resp.close()
                            resp = None
                            continue
                        elif resp.status_code == 404 and len(urls_to_try) > 1:
                            logger.debug(f"  ↪ Mirror 404 on {attempt_url} — trying next mirror...", category="file")
                            resp.close()
                            resp = None
                            continue
                        else:
                            resp.close()
                            resp = None
                    except Exception as ex:
                        if resp:
                            try:
                                resp.close()
                            except Exception:
                                pass
                            resp = None
                        logger.debug(f"  ↪ Mirror connect error on {attempt_url}: {ex}", category="file")
                        continue

                if resp and resp.status_code in (200, 206, 416):
                    break

            if resp is None:
                return False, "Failed to connect to any file server"

            task.used_preview = is_preview_url(task.url) and not (options is not None and getattr(options, "download_thumbnails_only", False))
            if task.used_preview:
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
                msg = "403 Forbidden — content locked (membership tier access required)"
                logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg

            if status == 404:
                msg = "404 Not Found — file does not exist on any server mirror"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg

            if status == 429:
                retry_after = resp.headers.get("Retry-After", "30")
                msg = f"429_RATE_LIMIT (Retry-After: {retry_after}s)"
                logger.warning(f"  ⚠ {task.filename}: HTTP 429 Too Many Requests (Rate limited)", category="file")
                return False, msg

            if status not in (200, 206):
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
                            task.speed_str = KemonoDownloader.format_speed(task.speed_bps)
                            if task.speed_bps > 0:
                                rem = max(0, task.file_size - curr_bytes)
                                s = int(rem / task.speed_bps)
                                task.eta_str = f"{s//60}m {s%60}s" if s > 60 else f"{s}s"
                            else:
                                task.eta_str = "--"

                        stats = self._queue_stats(now_poll)
                        completed_c = int(stats.get("done_n", 0))
                        failed_c = sum(1 for t in self.tasks if t.status == "failed")
                        self._emit_progress(completed_c, failed_c, len(self.tasks))

                        if self.on_task_status_changed:
                            self.on_task_status_changed(task)

                mp_ok, mp_err = download_multipart_file(
                    url=task.url,
                    target_path=task.target_path,
                    headers=req_headers,
                    num_chunks=4,
                    progress_callback=_on_mp_progress,
                    cancel_event=self._cancel_event,
                    pause_event=self._pause_event,
                    timeout=(25, 60),
                    session=session
                )

                if mp_ok:
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
                                return True, f"Skipped: {f_reason}"

                        problem = self._verify_file_hash(task, final_mp_size)
                        if problem:
                            _remove_quietly(task.target_path)
                            logger.error(f"  ✖ {task.filename}: {problem}", category="file", details=self._task_context(task))
                            return False, problem
                        self._post_process_downloaded_file(task, options)
                        task.status = "completed"
                        task.downloaded_bytes = task.file_size
                        task.progress_pct = 100
                        if self.on_task_status_changed:
                            self.on_task_status_changed(task)
                        return True, "Completed"

                if not mp_ok:
                    if self._cancel_event.is_set():
                        return False, "Cancelled"

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
                        return False, mp_err

                    logger.info(f"  ↪ Multipart fallback: {mp_err} — switching to standard single stream download...", category="file")
                    existing_size = 0
                    mode = "wb"
                    resumed = False

                    # Re-acquire single stream response stream since resp was closed for multipart
                    try:
                        resp = session.get(task.url, stream=True, timeout=(25, 60), headers=req_headers)
                        if resp.status_code not in (200, 206):
                            clean_resp = requests.get(task.url, stream=True, timeout=(25, 60), headers=browser_headers)
                            if clean_resp.status_code in (200, 206):
                                resp.close()
                                resp = clean_resp
                            else:
                                clean_resp.close()
                        if resp.status_code not in (200, 206):
                            msg = f"HTTP {resp.status_code} on single-stream fallback"
                            logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                            resp.close()
                            resp = None
                            return False, msg
                    except Exception as ex:
                        if resp:
                            try:
                                resp.close()
                            except Exception:
                                pass
                            resp = None
                        msg = f"Single-stream fallback connection error: {ex}"
                        logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                        return False, msg

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

            with self._active_resp_lock:
                self._active_responses.add(resp)
            try:
                with open(part_path, mode) as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if self._cancel_event.is_set():
                            try:
                                resp.close()
                            except Exception:
                                pass
                            return False, "Cancelled"
                        was_paused = False
                        while self._pause_event.is_set():
                            was_paused = True
                            time.sleep(0.3)
                            if self._cancel_event.is_set():
                                try:
                                    resp.close()
                                except Exception:
                                    pass
                                return False, "Cancelled"
                        if was_paused:
                            last_speed_time = time.time()
                            bytes_since_speed = 0

                        if not chunk:
                            continue

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
                            task.speed_str = KemonoDownloader.format_speed(task.speed_bps)
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
                with self._active_resp_lock:
                    self._active_responses.discard(resp)


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

            if task.file_size > 0 and final_size == 0:
                _remove_quietly(part_path)
                msg = "Downloaded file is empty (0.00 MB saved)"
                logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return False, msg

            if task.file_size > 0 and final_size < task.file_size and not self._cancel_event.is_set():
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
            if self._cancel_event.is_set():
                return False, "Cancelled"
            msg = "Connection timed out"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
            return False, msg
        except requests.exceptions.ConnectionError as e:
            if self._cancel_event.is_set():
                return False, "Cancelled"
            msg = f"Connection error: {e}"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
            return False, msg
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError) as e:
            # A connection that drops mid-transfer (IncompleteRead). requests derives these from
            # IOError, so without this branch they'd land in the OSError handler below, be
            # mislabelled as disk errors and have their partial file deleted. Keeping the
            # partial file lets the retry resume from where it stopped.
            if self._cancel_event.is_set():
                return False, "Cancelled"
            msg = f"Connection dropped mid-download (will resume on retry): {e}"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
            return False, msg
        except OSError as e:
            if self._cancel_event.is_set():
                return False, "Cancelled"
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
            if self._cancel_event.is_set():
                return False, "Cancelled"
            logger.error(f"  ✖ {task.filename}: {type(e).__name__}: {e}", category="file",
                         details=self._task_context(task) + "\n" + traceback.format_exc())
            return False, str(e)
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass

    def _finalize_part(self, task: DownloadTask, options: FilterOptions, part_path: str, final_size: int,
                       hasher=None, strict_hash: bool = False, is_upgrade_download: bool = False,
                       found_existing_path: Optional[str] = None) -> Tuple[bool, str]:
        """Checks a finished .part file (size filter, checksum) and gives it its real name."""
        if final_size > 0 and options:
            keep_file, f_reason = FilterEngine.should_keep_file(task.filename, options, file_size=final_size)
            if not keep_file:
                _remove_quietly(part_path)
                with self._lock:
                    self.downloaded_bytes = max(0, self.downloaded_bytes - task.downloaded_bytes)
                logger.info(f"⏭️ Skipping {task.filename} ({FilterEngine.format_size_str(final_size)}): {f_reason}", category="filter")
                task.status = "skipped"
                task.error_msg = f_reason
                task.progress_pct = 100
                task.eta_str = "Skipped"
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                return True, f"Skipped: {f_reason}"

        # Checksum before any post-processing (tagging / WebP conversion change the bytes)
        problem = self._verify_file_hash(task, final_size, path=part_path, hasher=hasher, strict=strict_hash)
        if problem:
            _remove_quietly(part_path)
            with self._lock:
                self.downloaded_bytes = max(0, self.downloaded_bytes - task.downloaded_bytes)
            task.downloaded_bytes = 0
            task.progress_pct = 0
            logger.error(f"  ✖ {task.filename}: {problem}", category="file", details=self._task_context(task))
            return False, problem

        # One step: an older small copy under the same name stays until the full file replaces it
        replace_file(part_path, task.target_path)
        task.progress_pct = 100
        task.eta_str = "Done"

        # An older copy under another name (e.g. a .webp preview) is replaced by the full file
        if is_upgrade_download and found_existing_path and os.path.exists(found_existing_path):
            if os.path.abspath(found_existing_path) != os.path.abspath(task.target_path):
                _remove_quietly(found_existing_path)

        self._post_process_downloaded_file(task, options)

        # Thread cooldown delay to avoid CDN rate limiting (429)
        if options.download_delay > 0 and not self._cancel_event.is_set():
            time.sleep(options.download_delay)
        return True, "Success"

    def _verify_file_hash(self, task: DownloadTask, file_size: int, path: Optional[str] = None,
                          hasher=None, strict: bool = False) -> str:
        """Verifies downloaded file integrity using SHA-256 or MD5 before any post-processing.

        Returns an error message when the file is damaged (only for hashes known to be the real
        content hash, and only when strict), otherwise "".
        """
        path = path or task.target_path
        raw_hash = (task.expected_sha256 or "").strip().lower()
        # Kemono / Pawchive / Coomer file names are the content's SHA-256: the most reliable hash
        url_hash = content_hash_from_url(task.url)
        if url_hash:
            raw_hash = url_hash
        if not raw_hash or not os.path.exists(path):
            if file_size > 0:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                    category="file"
                )
            return ""

        precomputed = hasher
        # Determine hash algorithm by length
        if len(raw_hash) == 64 and all(c in "0123456789abcdef" for c in raw_hash):
            algo_name = "SHA-256"
            hasher = hashlib.sha256()
        elif len(raw_hash) == 32 and all(c in "0123456789abcdef" for c in raw_hash):
            algo_name = "MD5"
            hasher = hashlib.md5()
        else:
            # Non-standard hash format (e.g. storageKey or arbitrary identifier)
            if file_size > 0:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                    category="file"
                )
            return ""

        # Video variants and storage keys on cum.st or similar CDN mirrors often have rearranged
        # container atoms (moov atom faststart) or upstream transcode layouts where the served
        # media stream differs from the upstream ingest storageKey.
        _, ext = os.path.splitext(task.target_path.lower())
        is_video = ext in (".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi")
        is_storage_key_url = "cum.st/media/" in task.url or "e1.cum.st" in task.url
        if is_storage_key_url and is_video:
            if file_size > 0:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                    category="file"
                )
            return ""

        try:
            if precomputed is not None and algo_name == "SHA-256":
                computed_hash = precomputed.hexdigest().lower()
            else:
                with open(path, "rb") as check_f:
                    while chunk := check_f.read(1024 * 1024):
                        hasher.update(chunk)
                computed_hash = hasher.hexdigest().lower()
            if computed_hash == raw_hash:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved, {algo_name} verified)",
                    category="file"
                )
            elif url_hash and strict:
                return "The file arrived damaged (checksum mismatch); it downloads again on retry"
            else:
                # File completed successfully (Content-Length and TLS integrity validated),
                # but the server-provided hash was an upstream ingest ID, storage key, or CDN transcode variant.
                # Always confirm success to the user without false-alarm warnings.
                if file_size > 0:
                    logger.success(
                        f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                        category="file"
                    )
                (logger.warning if url_hash else logger.debug)(
                    f"{task.filename}: server metadata {algo_name} differs from delivered stream "
                    f"(expected {raw_hash[:8]}, got {computed_hash[:8]}; upstream storageKey/variant)",
                    category="file"
                )
        except Exception as ex:
            logger.debug(f"Hash calculation error for {task.filename}: {ex}", category="file")
            if file_size > 0:
                logger.success(
                    f"✔ {task.filename}  ({file_size / (1024*1024):.2f} MB saved)",
                    category="file"
                )
        return ""

    def _post_process_downloaded_file(self, task: DownloadTask, options: FilterOptions):
        """Runs post-download processing such as WebP compression and audio metadata tagging."""
        if not task.target_path or not os.path.exists(task.target_path):
            return

        # 1. WebP conversion (the task, archive and queue then point at the .webp file)
        if options.compress_to_webp:
            converted = self._convert_to_webp(task.target_path, getattr(options, "webp_quality", "balanced"))
            if converted:
                task.target_path = converted

        # 2. Audio metadata tagging
        if getattr(options, "write_audio_metadata", False) and AudioTagger.is_supported(task.target_path):
            AudioTagger.tag_audio_file(
                file_path=task.target_path,
                artist=task.creator_name,
                title=task.post_title or os.path.splitext(task.filename)[0],
                album=task.post_title or task.creator_name,
                date=getattr(task, "post_date", "") or "",
                comment=getattr(task, "post_url", "") or task.url
            )

    def _convert_to_webp(self, file_path: str, level: str = "balanced") -> Optional[str]:
        """Converts JPG/PNG to WebP at the chosen level; returns the new path, or None when the file
        was kept as it was (also when the WebP wouldn't be smaller, e.g. lossless on a photo)."""
        from core.filter_engine import WEBP_QUALITY_LEVELS
        try:
            _, ext = os.path.splitext(file_path.lower())
            if ext in (".jpg", ".jpeg", ".png"):
                webp_path = os.path.splitext(file_path)[0] + ".webp"
                tmp_path = webp_path + PART_SUFFIX
                quality = WEBP_QUALITY_LEVELS.get(str(level or "").lower(), 85)
                with Image.open(file_path) as img:
                    if quality is None:
                        img.save(tmp_path, "WEBP", lossless=True, exact=True, quality=100, method=6)
                    else:
                        img.save(tmp_path, "WEBP", quality=quality, method=4)
                if os.path.getsize(tmp_path) >= os.path.getsize(file_path):
                    _remove_quietly(tmp_path)
                    logger.debug(f"Kept {os.path.basename(file_path)}: as WebP it wasn't smaller.", category="downloader")
                    return None
                replace_file(tmp_path, webp_path)
                os.remove(file_path)
                return webp_path
        except Exception as e:
            _remove_quietly(os.path.splitext(file_path)[0] + ".webp" + PART_SUFFIX)
            logger.debug(f"WebP compression skipped for {file_path}: {e}", category="downloader")
        return None

    def _calculate_instant_speed(self, now: float) -> int:
        """
        Calculates 100% accurate, real-time download throughput.
        Tracks byte delta over recent 1.0-2.0 second window for responsive, accurate network monitoring.
        """
        with self._lock:
            current_bytes = self.downloaded_bytes

        # A gap of more than 2 s since the last sample (paused, stalled): measure afresh
        if self._speed_samples and (now - self._speed_samples[-1][0] > 2.0):
            self._speed_samples.clear()
            self._smoothed_speed = 0.0

        self._speed_samples.append((now, current_bytes))

        # Evict all samples older than 2.0 seconds
        while self._speed_samples and (now - self._speed_samples[0][0] > 2.0):
            self._speed_samples.popleft()

        if len(self._speed_samples) >= 2:
            dt = now - self._speed_samples[0][0]
            db = current_bytes - self._speed_samples[0][1]
            if dt >= 0.2:
                raw_speed = max(0.0, db / dt)
                if self._smoothed_speed <= 0:
                    self._smoothed_speed = raw_speed
                else:
                    self._smoothed_speed = 0.85 * raw_speed + 0.15 * self._smoothed_speed
                return max(0, int(self._smoothed_speed))

        return max(0, int(self._smoothed_speed))

    def _calculate_smart_eta(self, completed: int, failed: int, total: int, speed: int, elapsed: float) -> str:
        """
        Calculates a learning, countdown-stable ETA that resists transient network dips/crashes.
        Uses:
        1. Long-term learned session throughput average + medium-term EMA (instead of fluctuating instant speed).
        2. Empirical average file size learned from completed tasks.
        3. Dual-model blending (throughput model + task completion rate).
        4. Monotonic steady countdown with anti-jitter damping.
        """
        remaining_tasks = total - completed - failed
        if total <= 0 or remaining_tasks <= 0:
            self._smoothed_eta = None
            return "Done"

        now = time.time()
        time_since_last_calc = (now - self._last_eta_calc_time) if self._last_eta_calc_time > 0 else 0.0
        self._last_eta_calc_time = now

        # ── 1. Learned File Size Estimation ──────────────────────────────────
        st = self._queue_stats(now)
        if st["done_n"]:
            learned_avg_file_size = st["done_bytes"] / st["done_n"]
        elif st["known_n"]:
            learned_avg_file_size = st["known_bytes"] / st["known_n"]
        else:
            learned_avg_file_size = 4.5 * 1024 * 1024  # 4.5 MB realistic artwork fallback

        # Calculate estimated remaining bytes
        total_remaining_bytes = st["known_remaining"] + max(
            0.0, st["unknown_n"] * learned_avg_file_size - st["unknown_downloaded"])

        # ── 2. Derive Learning ETA Throughput Baseline ────────────────────────
        # Rather than using the raw 1-second fluctuating speed (which jumps on dips/crashes),
        # we compute a learned throughput baseline from historical session performance.
        with self._lock:
            current_bytes = self.downloaded_bytes

        session_avg_speed = current_bytes / max(1.0, elapsed)

        # Track medium-term pace
        if self._medium_speed <= 0:
            self._medium_speed = float(speed if speed > 0 else session_avg_speed)
        else:
            self._medium_speed = 0.05 * speed + 0.95 * self._medium_speed

        # Progressive learning anchor: As elapsed time increases, anchor heavily to the
        # sustained empirical average so brief speed crashes (e.g. 1.5MB/s -> 500KB/s) don't affect ETA
        learn_weight = min(0.85, max(0.20, (elapsed - 5.0) / 60.0))
        learned_eta_speed = (1.0 - learn_weight) * self._medium_speed + learn_weight * session_avg_speed

        # ── 3. Dual-Model Target ETA Derivation ──────────────────────────────
        target_candidates = []

        # Model A: Byte-Throughput ETA using learned sustained speed
        if learned_eta_speed > 512 and total_remaining_bytes > 0:
            target_candidates.append(total_remaining_bytes / learned_eta_speed)

        # Model B: Task Completion Rate ETA (empirically learned tasks/sec)
        done_count = completed + failed
        if done_count > 0 and elapsed > 2.0:
            tasks_per_second = done_count / elapsed
            if tasks_per_second > 0:
                target_candidates.append(remaining_tasks / tasks_per_second)

        if not target_candidates:
            if remaining_tasks == 0:
                return "Done"
            return "--"

        # Blend models (65% byte-throughput + 35% task completion rate if both available)
        if len(target_candidates) == 2:
            target_eta_seconds = 0.65 * target_candidates[0] + 0.35 * target_candidates[1]
        else:
            target_eta_seconds = target_candidates[0]

        # ── 4. Monotonic Countdown & Anti-Fluctuation Damping ────────────────
        if self._smoothed_eta is None:
            self._smoothed_eta = target_eta_seconds
        else:
            # First, tick down naturally by the elapsed real time
            if 0 < time_since_last_calc < 3.0:
                self._smoothed_eta = max(1.0, self._smoothed_eta - time_since_last_calc)

            # Then gently nudge towards target ETA using adaptive damping
            deviation = abs(target_eta_seconds - self._smoothed_eta) / max(1.0, self._smoothed_eta)
            if deviation > 0.60:
                alpha = 0.10
            elif deviation > 0.25:
                alpha = 0.04
            else:
                alpha = 0.015

            self._smoothed_eta = (1.0 - alpha) * self._smoothed_eta + alpha * target_eta_seconds

        eta_sec = max(1, int(round(self._smoothed_eta)))

        # ── 5. Format Output String ──────────────────────────────────────────
        if eta_sec >= 86400:
            return f"{eta_sec // 86400}d {(eta_sec % 86400) // 3600}h"
        elif eta_sec >= 3600:
            return f"{eta_sec // 3600}h {(eta_sec % 3600) // 60}m {eta_sec % 60}s"
        elif eta_sec >= 60:
            return f"{eta_sec // 60}m {eta_sec % 60}s"
        elif eta_sec > 1:
            return f"{eta_sec}s"
        else:
            return "< 1s"

    def _queue_stats(self, now: float) -> Dict[str, float]:
        """Byte totals over the whole queue for the ETA, gathered in one pass at most once a second
        (four passes five times a second were noticeable with 100,000-file queues)."""
        if self._task_stats and now - self._task_stats_time < 1.0:
            return self._task_stats
        done_bytes = done_n = known_bytes = known_n = 0
        known_remaining = unknown_n = unknown_downloaded = all_downloaded = 0
        for t in self.tasks:
            d = t.downloaded_bytes
            all_downloaded += d
            status = t.status
            if status == "completed":
                if d > 0:
                    done_bytes += d
                    done_n += 1
            elif status in ("pending", "downloading"):
                size = t.file_size
                if size > 0:
                    known_bytes += size
                    known_n += 1
                    known_remaining += max(0, size - d)
                else:
                    unknown_n += 1
                    unknown_downloaded += d
        self._task_stats = {
            "done_bytes": done_bytes, "done_n": done_n, "known_bytes": known_bytes, "known_n": known_n,
            "known_remaining": float(known_remaining), "unknown_n": unknown_n,
            "unknown_downloaded": float(unknown_downloaded), "all_downloaded": all_downloaded,
        }
        self._task_stats_time = now
        return self._task_stats

    def _emit_progress(self, completed: int, failed: int, total: int, force: bool = False):
        if not self.on_progress_update:
            return

        now = time.time()
        # Throttle progress emissions to max 5 times per second unless forced
        if not force and (now - self._last_progress_emit_time < 0.20):
            return
        self._last_progress_emit_time = now

        elapsed = max(0.1, now - self.start_time)
        speed = self._calculate_instant_speed(now)

        # Format elapsed time
        elapsed_int = int(elapsed)
        if elapsed_int >= 3600:
            elapsed_str = f"{elapsed_int // 3600}h {(elapsed_int % 3600) // 60}m {elapsed_int % 60}s"
        elif elapsed_int >= 60:
            elapsed_str = f"{elapsed_int // 60}m {elapsed_int % 60}s"
        else:
            elapsed_str = f"{elapsed_int}s"

        # Calculate ETA
        eta_str = self._calculate_smart_eta(completed, failed, total, speed, elapsed)

        # Calculate progress percent
        if total > 0:
            task_ratio = (completed + failed) / total
            percent = int(task_ratio * 100)
            percent = max(0, min(100, percent))
        else:
            percent = 0

        # Use the maximum of the running counter and the sum of per-task bytes.
        # The running counter can lag for multipart files (disk-poll vs in-flight bytes),
        # and the per-task sum stays accurate because _disk_poll updates task.downloaded_bytes.
        tasks_downloaded = self._queue_stats(now)["all_downloaded"]
        effective_bytes = max(self.downloaded_bytes, tasks_downloaded)
        dl_mb = effective_bytes / (1024 * 1024)
        if effective_bytes > 1024 * 1024 * 1024:
            saved_str = f"{effective_bytes / (1024 * 1024 * 1024):.2f} GB"
        else:
            saved_str = f"{dl_mb:.1f} MB"

        status_text = (
            "Progress: Paused" if self._pause_event.is_set() else (
                f"Downloading… ({completed}/{total} files)"
                if self._is_running else "Idle"
            )
        )

        info = {
            "completed": completed,
            "failed": failed,
            "total": total,
            "percent": percent,
            "speed_str": self.format_speed(speed),
            "eta_str": eta_str,
            "elapsed_str": elapsed_str,
            "downloaded_bytes": self.downloaded_bytes,
            "saved_str": saved_str,
            "status_text": status_text,
            "adaptive_state": self.adaptive_state,
            "adaptive_status_text": self.adaptive_status_text
        }
        self.on_progress_update(info)

    @staticmethod
    def format_speed(bps: int) -> str:
        if bps <= 0:
            return "0 KB/s"
        if bps >= 1024 * 1024:
            return f"{bps / (1024 * 1024):.2f} MB/s"
        elif bps >= 1024:
            return f"{bps / 1024:.1f} KB/s"
        return f"{bps} B/s"


