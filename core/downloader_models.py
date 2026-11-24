"""
Core Downloader Models, Constants & File/URL Helpers
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import os
import re
import shutil
import sys
import threading
import time
import urllib.parse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.atomic_io import atomic_write_text, replace_file
from core.filter_engine import FilterEngine, FilterOptions, MediaTypes, fit_path_for_windows
from core.filter_options import safe_int
from core.logger import logger
from core.path_utils import post_info_name
from core.providers import COOMER, KEMONO, PAWCHIVE, is_disabled, provider_for_host


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


# Errors that trying again won't fix: the file is gone from the server, or the video is private /
# removed. (403 isn't here: on these sites it's often a temporary block.)
_PERMANENT_ERRORS = (
    "404", "410", "not found", "not exist", "no longer available", "has been removed", "been deleted",
    "not imported", "not physically hosted", "not available on pawchive",
    "private video", "video unavailable", "this video is unavailable", "video is private",
    "account associated with this video has been terminated", "members-only", "join this channel",
)


def is_post_unimported_on_pawchive(post: Dict[str, Any], domain: str = "", service: str = "") -> bool:
    """True when Pawchive only holds metadata/previews for this post and has not imported its
    full-size files onto its storage nodes (and no upstream fallback mirror is enabled)."""
    if not isinstance(post, dict):
        return False
    dom = str(domain or post.get("domain") or "").lower()
    orig = str(post.get("origin") or "").lower()
    if "pawchive" not in dom and "pawchive" not in orig:
        return False
    svc = str(service or post.get("service") or "").lower()
    mirror_host = "coomer.st" if svc in COOMER_SERVICES else "kemono.cr"
    if not is_disabled(mirror_host):
        return False
    if "has_full" in post:
        return post.get("has_full") is False
    if post.get("is_unimported") is not None:
        return bool(post.get("is_unimported"))
    return orig in ("kemono", "coomer") and str(post.get("preview_state") or "").lower() == "pending"


def format_unimported_explanation(
    creator_name: str,
    unimported_posts: int,
    unimported_files: int,
    queued_thumbnails: int = 0,
    is_single_post: bool = False,
    all_unimported: bool = True,
) -> Tuple[str, str]:
    """Returns a clear, plain-English (title, message) pair explaining why unimported Pawchive
    posts cannot be downloaded at full size."""
    who = (creator_name or "this creator").strip()
    post_word = "post" if unimported_posts == 1 else "posts"
    file_word = "file" if unimported_files == 1 else "files"
    thumb_word = "preview" if queued_thumbnails == 1 else "previews"

    if queued_thumbnails > 0 and unimported_files == 0:
        title = "Unimported Posts — Downloading Previews Only"
        msg = (
            f"{unimported_posts} {post_word} ({queued_thumbnails} {thumb_word}) for {who} haven't been imported "
            f"onto Pawchive's servers yet, so full-size files aren't physically hosted on the site. "
            f"Downloading small preview thumbnails directly because \"Fallback to Thumbnails\" is enabled."
        )
        return title, msg

    title = "Not Imported on Pawchive Yet"
    if is_single_post:
        msg = (
            f"This post's full-size files haven't been imported on Pawchive yet ({unimported_files} {file_word}), "
            f"so they were marked as Not Imported.\n\n"
            f"Right now Pawchive only lists the post details and small preview thumbnails — the actual files "
            f"aren't physically stored on Pawchive's servers, so there's nothing full-size to download until "
            f"Pawchive imports them.\n\n"
            f"Tip: If you only want the small preview thumbnails for now, turn on "
            f"\"Fallback to thumbnails if full-size missing\" in Downloader → Quick → Download Quality & Thumbnails."
        )
    elif all_unimported:
        msg = (
            f"These full-size files for {who} haven't been imported on Pawchive yet "
            f"({unimported_posts} {post_word}, {unimported_files} {file_word}), so they were marked as Not Imported.\n\n"
            f"Right now Pawchive only has the post metadata and small preview thumbnails — the actual files "
            f"aren't physically hosted on Pawchive's servers, so there's nothing full-size to download until "
            f"Pawchive finishes importing them.\n\n"
            f"Tip: If you only want the small preview thumbnails for now, turn on "
            f"\"Fallback to thumbnails if full-size missing\" in Downloader → Quick → Download Quality & Thumbnails."
        )
    else:
        msg = (
            f"Skipped {unimported_posts} unimported {post_word} ({unimported_files} {file_word}) for {who} — "
            f"Pawchive hasn't imported those full-size files onto its servers yet (only preview thumbnails exist "
            f"on the site, so nothing can be downloaded for them until Pawchive imports them)."
        )
    return title, msg


UNIMPORTED_TASK_ERROR_MSG = (
    "Not imported on Pawchive — full-size file isn't physically hosted on the site yet "
    "(previews only; retry disabled)"
)


def is_task_non_retryable(task) -> bool:
    """True for tasks whose full-size files are known not to exist on the server at all
    (e.g. Pawchive posts not yet imported onto Pawchive's storage nodes), so retrying is pointless."""
    if task is None:
        return False
    if isinstance(task, dict):
        if task.get("is_unimported"):
            return True
        err = str(task.get("error_msg") or "").lower()
    else:
        if getattr(task, "is_unimported", False):
            return True
        err = str(getattr(task, "error_msg", "") or "").lower()
    return "not imported on pawchive" in err


# Embedded-video sites that no longer exist: their links never work again
DEAD_VIDEO_HOSTS = ("gfycat.com",)

# For embedded videos (yt-dlp) only what the site states plainly counts as permanent. A bare
# "404" / "410" doesn't: RedGifs answers "410 Gone" for videos some users can still play in a browser.
_PERMANENT_EMBED_ERRORS = (
    "private video", "video unavailable", "this video is unavailable", "video is private",
    "account associated with this video has been terminated", "members-only", "join this channel",
)


def friendly_embed_error(msg: str, url: str = "") -> str:
    """yt-dlp's error for an embedded video, said plainly for the known cases."""
    m, u = (msg or "").lower(), (url or "").lower()
    if any(h in u or h in m for h in DEAD_VIDEO_HOSTS):
        return "Gfycat shut down in 2023: this video can't be downloaded any more"
    if "redgifs" in (u + m) and ("410" in m or "gone" in m):
        return ("RedGifs says this video was deleted (HTTP 410). If it still plays in your browser, it "
                "may only be available while logged in there: pick that browser under \"Use browser "
                "sign-in\" in Settings, then Retry")
    return msg


def is_permanent_failure(task) -> bool:
    """A failed file that will fail the same way every time (missing on the server, a private or
    removed video, a site that no longer exists, or out of retries). The Watchlist counts these
    posts as done, so it stops offering the same posts again after every download (#28)."""
    # Unimported Pawchive posts aren't permanently gone — Pawchive simply hasn't imported them
    # yet, so Watchlist must NOT mark them as done (it should detect them once imported).
    if is_task_non_retryable(task):
        return False
    if getattr(task, "retry_capped", False):
        return True
    m = str(getattr(task, "error_msg", "") or "").lower()
    url = str(getattr(task, "url", "") or "").lower()
    if any(h in url for h in DEAD_VIDEO_HOSTS) or "gfycat shut down" in m:
        return True
    if getattr(task, "is_ytdlp", False):
        return any(k in m for k in _PERMANENT_EMBED_ERRORS) or is_not_a_video_error(m)
    if getattr(task, "http_status", 0) in (404, 410):
        return True
    return any(k in m for k in _PERMANENT_ERRORS) or is_not_a_video_error(m)


def is_preview_url(url: str) -> bool:
    """Thumbnail-server URLs: a small preview copy, never the full-size original."""
    if not url:
        return False
    u_low = url.lower()
    if "/thumbnail/" in u_low:
        return True
    if any(host in u_low for host in ("img.pawchive.pw", "img.kemono.cr", "img.coomer.st", "img.cum.st")):
        return True
    return False


def _get_media_candidate_paths(file_path: str) -> List[str]:
    """Return possible on-disk variants of a media path (e.g. .webp/.avif for images, .mp4/.mkv/.webm for videos)."""
    if not file_path:
        return []
    stem, ext = os.path.splitext(file_path)
    ext_lower = ext.lower()
    variants = [file_path]
    if ext_lower in MediaTypes.VIDEO_EXTS:
        for v_ext in (".mp4", ".mkv", ".webm"):
            if v_ext != ext_lower:
                variants.append(stem + v_ext)
    elif ext_lower in MediaTypes.IMAGE_EXTS or ext_lower in (".webp", ".avif"):
        for i_ext in (".webp", ".avif"):
            if i_ext != ext_lower:
                variants.append(stem + i_ext)
    return variants


def needs_full_size_upgrade(existing_size: int, server_size: int, target_path: str, options,
                            existing_path: str = "") -> bool:
    """An existing file is a small / preview copy that should be replaced by the full-size one.

    When the server tells the file's size, that decides: a copy as big as the original is never
    downloaded again. Small originals (an image under 150 KB) used to count as previews and were
    "upgraded" on every run (#28). A .webp or .avif the app made with compression is the user's own
    smaller copy, not a preview, so it isn't replaced either (#28, #39). Videos are never preview
    thumbnails; compressed or transcoded videos on disk (which are smaller than server size) must
    never be re-downloaded (#39)."""
    if options is None or getattr(options, "download_thumbnails_only", False):
        return False

    target_ext = os.path.splitext((target_path or "").lower())[1]
    exist_ext = os.path.splitext((existing_path or "").lower())[1] if existing_path else ""

    # Videos are never low-resolution preview thumbnails; compressed or transcoded videos
    # on disk (which are smaller than server size) must never be re-downloaded (#39).
    if target_ext in MediaTypes.VIDEO_EXTS or exist_ext in MediaTypes.VIDEO_EXTS:
        return False

    # Locally compressed WebP or AVIF images are smaller by design and should not be replaced
    if exist_ext in (".webp", ".avif") and target_ext not in (".webp", ".avif"):
        return False

    existing_sz = max(0, safe_int(existing_size, 0))
    server_sz = max(0, safe_int(server_size, 0))

    if server_sz > 0:
        return existing_sz < server_sz * 0.75

    if getattr(options, "redownload_small_files", False):
        min_lim, _ = FilterEngine.get_effective_size_limits(options)
        threshold = min_lim if min_lim else (150 * 1024)
        return existing_sz < threshold and (target_ext in MediaTypes.IMAGE_EXTS or target_ext in (".webp", ".avif"))

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

_HASH_PATH_RE = re.compile(r"/[0-9a-f]{2,3}/[0-9a-f]{2}/([0-9a-f]{64})\.[^/?#]+(?:[?#]|$)", re.IGNORECASE)


def _get_provider_for_host():
    mod = sys.modules.get("core.downloader")
    if mod is not None and hasattr(mod, "provider_for_host"):
        return mod.provider_for_host
    return provider_for_host


def content_hash_from_url(url: str) -> str:
    """Kemono, Pawchive and Coomer store files as /ab/cd/<sha256>.<ext>: the name is the SHA-256 of the
    file's content, which gives a free check that a download arrived complete and undamaged."""
    if not url or is_preview_url(url) or _get_provider_for_host()(url) not in (KEMONO, COOMER, PAWCHIVE):
        return ""
    m = _HASH_PATH_RE.search(url.split("://", 1)[-1])
    return m.group(1).lower() if m else ""


def _fq(name: str) -> str:
    """A file name for the ?f= link parameter ('#', '&', '%' etc. used to cut the link short)."""
    return urllib.parse.quote(name, safe="")


def _counts(c: Counter) -> str:
    """"12 already on disk, 3 filtered out" """
    return ", ".join(f"{n} {why}" for why, n in c.most_common())


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




class StatusCounter:
    """How many tasks are in each status, kept up to date as statuses change (DownloadTask.status).
    Counting a big queue by looping over it a few times a second used a lot of CPU and, holding
    Python's lock, made the window stutter. reset() starts a new generation: tasks that left the
    list keep their old generation and no longer change the counts."""

    def __init__(self):
        self.counts: Dict[str, int] = defaultdict(int)
        self.gen = 0
        self._lock = threading.Lock()
        self._changed: Dict[int, Any] = {}      # tasks whose status changed since the last checkpoint

    def move(self, old: Optional[str], new: str, task: Any = None) -> None:
        with self._lock:
            if old is not None:
                self.counts[old] -= 1
            self.counts[new] += 1
            if task is not None:
                self._changed[id(task)] = task

    def take_changed(self) -> List[Any]:
        with self._lock:
            changed, self._changed = list(self._changed.values()), {}
            return changed

    def reset(self, tasks) -> None:
        with self._lock:
            self.gen += 1
            counts: Dict[str, int] = defaultdict(int)
            for t in tasks:
                d = t.__dict__
                d["_counter"] = self
                d["_counter_gen"] = self.gen
                counts[d.get("_status", "pending")] += 1
            self.counts = counts


class DownloadTask:
    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        d = self.__dict__
        old = d.get("_status")
        d["_status"] = value
        if old != value:
            c = d.get("_counter")
            if c is not None and d.get("_counter_gen") == c.gen:
                c.move(old, value, self)

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
        user_id: str = "",
        options: Optional[Any] = None
    ):
        self.options = options
        self.url = url
        self.target_path = target_path
        self.post_title = post_title
        self.creator_name = creator_name
        self.service = str(service or "")
        self.user_id = str(user_id if user_id is not None else "")
        self.post_id = str(post_id if post_id is not None else "")
        self.file_id = str(file_id if file_id is not None else "")
        self.file_size = max(0, safe_int(file_size, 0))
        self.expected_sha256 = expected_sha256
        self.is_ytdlp = is_ytdlp
        self.is_telegram = is_telegram
        self.telegram_channel_id = str(telegram_channel_id or "")
        self.telegram_message_id = safe_int(telegram_message_id, 0)
        self.batch_id = batch_id or (f"{self.service}_{creator_name}_{self.post_id}".strip("_") if (self.service or creator_name or self.post_id) else "batch_default")
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
        self.is_unimported = False  # True when full-size file isn't hosted on Pawchive yet (non-retryable)
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
            "is_unimported": bool(getattr(self, "is_unimported", False)),
            "options": self.options.to_dict() if (getattr(self, "options", None) and hasattr(self.options, "to_dict")) else None,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DownloadTask":
        from core.path_translation import localize_path      # (saved on the other system: D:\ ↔ /mnt/d)
        t = cls(
            url=d.get("url", ""),
            target_path=localize_path(d.get("target_path", "")),
            post_title=d.get("post_title", ""),
            creator_name=d.get("creator_name", ""),
            service=d.get("service", ""),
            post_id=str(d.get("post_id", "") or ""),
            file_id=str(d.get("file_id", "") or ""),
            file_size=max(0, safe_int(d.get("file_size", 0), 0)),
            expected_sha256=d.get("expected_sha256", ""),
            is_ytdlp=bool(d.get("is_ytdlp", False)),
            is_telegram=bool(d.get("is_telegram", False)),
            telegram_channel_id=str(d.get("telegram_channel_id", "") or ""),
            telegram_message_id=safe_int(d.get("telegram_message_id", 0), 0),
            batch_id=d.get("batch_id", ""),
            post_url=d.get("post_url", ""),
            post_date=d.get("post_date", ""),
            user_id=str(d.get("user_id", "") or "")
        )
        t.fallback_urls = [u for u in (d.get("fallback_urls") or []) if isinstance(u, str)]
        t.used_preview = bool(d.get("used_preview", False))
        t.is_unimported = bool(d.get("is_unimported", False))
        t.downloaded_bytes = max(0, safe_int(d.get("downloaded_bytes", 0), 0))
        t.status = d.get("status", "pending")
        t.error_msg = d.get("error_msg", "")
        t.retry_count = max(0, safe_int(d.get("retry_count", 0), 0))
        opts_raw = d.get("options")
        if opts_raw and isinstance(opts_raw, dict):
            from core.filter_engine import FilterOptions
            t.options = FilterOptions.from_dict(opts_raw)
        return t


@dataclass
class BatchBuildContext:
    """Bounded snapshot of the inputs used to plan one active download batch so mid-download
    settings changes can rebuild remaining work without re-scraping already-fetched posts."""
    batch_id: str
    parsed: Any
    creator_name: str
    service: str
    user_id: str
    domain: str
    base_dir: str
    artist_dir: Optional[str] = None
    provider: str = ""
    post_id: str = ""
    from_watchlist: bool = False
    custom_folder: bool = False
    posts: List[Dict[str, Any]] = field(default_factory=list)
    external_files: List[Dict[str, Any]] = field(default_factory=list)
    fetched_dms: bool = False
    fetched_comments: bool = False
    fetched_fav_ids: Optional[Set[str]] = None
    scan_page_start: int = 1
    scan_page_end: int = 999999
    scan_date_after: str = ""
    scan_date_before: str = ""
    applied_options: Optional[FilterOptions] = None
    applied_download_dir: str = ""
    applied_site_in_folder_name: bool = False
    applied_known_mode: str = "filename_only"
    applied_ai_enabled: bool = False
    applied_ai_engine: str = "fast"
    link_identity: str = ""
    force_redownload: bool = False


def atomic_move_part(src_part: str, dst_part: str) -> bool:
    """Moves an interrupted .part resume file to a new destination path safely across drives."""
    if not src_part or not dst_part:
        return False
    try:
        src_abs = os.path.abspath(src_part)
        dst_norm = fit_path_for_windows(dst_part)
        dst_abs = os.path.abspath(dst_norm)
        if os.path.normcase(src_abs) == os.path.normcase(dst_abs):
            return os.path.isfile(src_abs)
        if not os.path.isfile(src_abs):
            return False
        src_size = os.path.getsize(src_abs)
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        if os.path.isfile(dst_abs):
            dst_size = os.path.getsize(dst_abs)
            if dst_size >= src_size:
                _remove_quietly(src_abs)
                return True
        try:
            os.replace(src_abs, dst_abs)
            return True
        except OSError:
            tmp_dst = dst_abs + ".moving"
            try:
                shutil.copyfile(src_abs, tmp_dst)
                with open(tmp_dst, "r+b") as _tf:
                    os.fsync(_tf.fileno())
                os.replace(tmp_dst, dst_abs)
                _remove_quietly(src_abs)
                return True
            except OSError:
                _remove_quietly(tmp_dst)
                return False
    except OSError:
        return False

