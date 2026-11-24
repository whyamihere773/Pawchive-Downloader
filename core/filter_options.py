"""
Filtering & Path Sanitization Engine
Filters posts and media attachments by character tags, skip words, size constraints,
media categories, and formats safe cross-platform filesystem filenames.
"""

import re
import os
import math
import unicodedata
import csv
import io
import datetime
import html
from typing import List, Dict, Any, Optional, Tuple


_NUMERIC_STR_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def safe_int(value: Any, default: int = 0) -> int:
    """Coerce arbitrary JSON/UI values (int, float, numeric str, bool, None) to int without raising."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) else default
    s = str(value).strip()
    if not s:
        return default
    try:
        return int(s)
    except ValueError:
        try:
            f = float(s)
            return int(f) if math.isfinite(f) else default
        except (ValueError, OverflowError):
            return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce arbitrary JSON/UI values to finite float without raising."""
    if value is None:
        return default
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else default
    s = str(value).strip()
    if not s:
        return default
    try:
        f = float(s)
        return f if math.isfinite(f) else default
    except (ValueError, OverflowError):
        return default


def _timestamp_to_datetime(raw_ts: float) -> Optional[datetime.datetime]:
    """Convert Unix seconds or milliseconds (>1e11) safely on all platforms including Windows."""
    if not math.isfinite(raw_ts) or raw_ts <= 0:
        return None
    ts = raw_ts / 1000.0 if raw_ts >= 1e11 else raw_ts
    try:
        return datetime.datetime.fromtimestamp(ts)
    except (OSError, OverflowError, ValueError):
        try:
            return datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=ts)
        except (OverflowError, ValueError):
            return None


def normalize_post_date_ymd(value: Any, fallback: str = "") -> str:
    """Normalize any post date (ISO str, Unix sec/ms int/float/str, or None) into 'YYYY-MM-DD' or fallback."""
    if value is None or isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        dt = _timestamp_to_datetime(float(value))
        return dt.strftime("%Y-%m-%d") if dt is not None else fallback
    s = str(value).strip()
    if not s or s == "0000-00-00":
        return fallback
    if _NUMERIC_STR_RE.match(s):
        # 4-digit year ("2025") is a partial year, whereas 9+ digits is a Unix s/ms timestamp
        digits_only = s.lstrip("+-").split(".", 1)[0]
        if len(digits_only) >= 9:
            dt = _timestamp_to_datetime(safe_float(s, -1.0))
            return dt.strftime("%Y-%m-%d") if dt is not None else fallback
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    if "T" in s and not s.startswith("T"):
        head = s.split("T", 1)[0].strip()
        return head[:10] if head else fallback
    if " " in s:
        head = s.split(" ", 1)[0].strip()
        return head[:10] if head else fallback
    return s[:10] if s else fallback


def normalize_post_timestamp_str(value: Any, fallback: str = "") -> str:
    """Normalize any post date/timestamp into a homogeneous sortable ISO string (never int/None)."""
    if value is None or isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        dt = _timestamp_to_datetime(float(value))
        return dt.strftime("%Y-%m-%dT%H:%M:%S") if dt is not None else fallback
    s = str(value).strip()
    if not s:
        return fallback
    if _NUMERIC_STR_RE.match(s):
        digits_only = s.lstrip("+-").split(".", 1)[0]
        if len(digits_only) >= 9:
            dt = _timestamp_to_datetime(safe_float(s, -1.0))
            return dt.strftime("%Y-%m-%dT%H:%M:%S") if dt is not None else fallback
    return s


def post_id_sort_key(post_id: Any) -> Tuple[int, int, str]:
    """Homogeneous sort key for numeric and alphanumeric post IDs (avoids Unicode isdigit traps)."""
    s = str(post_id if post_id is not None else "").strip()
    if s and s.isascii() and s.isdigit():
        return (0, int(s), s)
    return (1, 0, s)


class MediaTypes:
    ALL = "all"
    IMAGES = "images"
    VIDEOS = "videos"
    ARCHIVES = "archives"
    AUDIO = "audio"
    LINKS = "links"

    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg", ".psd", ".clip", ".sai",
                  ".avif", ".jfif", ".tif", ".tiff", ".heic", ".heif"}
    VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".flv", ".wmv"}
    AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
    ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"}

    @staticmethod
    def get_file_type_category(filename: str) -> str:
        """
        Returns broad category folder name ('Images', 'Video', 'Archive', 'Audio', 'Other')
        for organizing attachments by file type.
        """
        if not filename:
            return "Other"
        _, ext = os.path.splitext(filename.lower())
        if ext in {
            ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg",
            ".ico", ".tiff", ".tif", ".avif", ".heic", ".heif", ".jfif"
        }:
            return "Images"
        elif ext in {
            ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".flv",
            ".wmv", ".ts", ".mts", ".m2ts", ".3gp"
        }:
            return "Video"
        elif ext in {
            ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
            ".psd", ".clip", ".sai", ".sai2", ".cpt", ".procreate", ".7zip", ".tgz"
        }:
            return "Archive"
        elif ext in {
            ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus",
            ".wma", ".aiff", ".alac", ".mka"
        }:
            return "Audio"
        return "Other"


# Scripts written without spaces between words: \b word boundaries never match inside them
_NO_SPACE_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af\u0e00-\u0e7f]")


def contains_term(text: str, term: str) -> bool:
    """Whole-word match for Latin-script terms; plain substring match for Japanese, Chinese, Korean
    and Thai terms (their titles have no spaces, so "初音ミクのイラスト" contains "初音ミク")."""
    if not term or not text:
        return False
    if _NO_SPACE_SCRIPT.search(term):
        return term.casefold() in text.casefold()
    return re.search(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE) is not None


def _plain_text(html: str) -> str:
    """Post content without HTML tags (so skip words don't match inside links or attributes)."""
    return re.sub(r"<[^>]+>", " ", html or "")


# Windows refuses paths of 260+ characters unless long paths are enabled system-wide
WINDOWS_MAX_PATH = 250


def fit_path_for_windows(path: str, max_len: int = WINDOWS_MAX_PATH) -> str:
    """Shorten a too-long Windows path: first the file name, then the deepest folder names.
    Shortened parts keep their start and get a short hash, so different names stay different."""
    import sys as _sys
    import hashlib as _hashlib
    if _sys.platform != "win32" or len(os.path.abspath(path)) <= max_len:
        return path

    def _short(name: str, keep: int, keep_ext: bool) -> str:
        stem, ext = os.path.splitext(name) if keep_ext else (name, "")
        digest = _hashlib.md5(name.encode("utf-8", "replace")).hexdigest()[:6]
        keep = max(8, keep - len(ext) - 7)
        return f"{stem[:keep].rstrip(' ._')}_{digest}{ext}"

    folder, name = os.path.split(os.path.abspath(path))
    # The folder part is shortened the same way for every file in it (it never depends on the
    # file name), so files of one post never end up split across differently shortened folders.
    room = max_len - len(folder) - 1
    if room < 60:
        parts = folder.split(os.sep)
        i = len(parts) - 1
        while len(os.sep.join(parts)) > max_len - 61 and i > 1:
            if len(parts[i]) > 24:
                parts[i] = _short(parts[i], 24, False)
            i -= 1
        folder = os.sep.join(parts)
        room = max_len - len(folder) - 1
    if len(name) > room:
        name = _short(name, room, True)
    return os.path.join(folder, name)


# "Compress to WebP" levels: Pillow quality (None = lossless)
WEBP_QUALITY_LEVELS = {"lossless": None, "high": 95, "balanced": 85, "small": 70, "smallest": 50}

# Date-based folder sorting modes inside each creator folder
DATE_FOLDER_MODES = ("none", "year", "month", "year_month")

# Browser disk-sync modes ("all" = standard; others skip complete posts & auto-reuse creator path/layout)
DISK_SYNC_MODES = ("all", "missing_or_mismatched", "missing_only", "mismatched_only")


def normalize_disk_sync_mode(value: Any) -> str:
    """Normalize a Browser disk-sync mode string to one of DISK_SYNC_MODES."""
    v = str(value or "all").strip().lower().replace("-", "_").replace(" ", "_")
    if v in ("all", "off", "false", "none", ""):
        return "all"
    if v in ("missing_or_mismatched", "missing_and_mismatched", "sync", "both"):
        return "missing_or_mismatched"
    if v in ("missing_only", "missing", "not_on_disk"):
        return "missing_only"
    if v in ("mismatched_only", "mismatched", "partial", "incomplete"):
        return "mismatched_only"
    return "all"


def normalize_date_folder_mode(value: Any) -> str:
    """Normalize a date folder sorting mode to one of DATE_FOLDER_MODES."""
    v = str(value or "none").strip().lower().replace("-", "_").replace("/", "_")
    if v in ("none", "off", "false", ""):
        return "none"
    if v in ("year", "years", "yearly"):
        return "year"
    if v in ("month", "months", "monthly"):
        return "month"
    if v in ("year_month", "yearmonth", "years_months", "both"):
        return "year_month"
    return "none"


class FilenameStyles:
    POST_TITLE = "post_title"
    DATE_POST_TITLE = "date_post_title"
    DATE_BASED = "date_based"
    POST_TITLE_GLOBAL_NUMBERING = "post_title_global_numbering"
    CUSTOM = "custom"


def normalize_size_str(s: str) -> str:
    """
    Normalizes a size string into canonical human-readable format like '1.5 GB', '500 MB'.
    Handles shorthand ('1g' -> '1 GB', '500' -> '500 MB', '1kb1' -> '1 KB').
    Returns empty string if invalid or 0.
    """
    if not s:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    m = re.match(r'^([\d.]+)\s*([A-Za-z]+)?', s)
    if not m or not m.group(1):
        return ""
    try:
        val = float(m.group(1))
        if val <= 0:
            return ""
    except ValueError:
        return ""

    raw_unit = (m.group(2) or "MB").upper()
    unit_map = {
        "B": "B", "BYTE": "B", "BYTES": "B",
        "K": "KB", "KB": "KB", "KIB": "KB",
        "M": "MB", "MB": "MB", "MIB": "MB",
        "G": "GB", "GB": "GB", "GIB": "GB",
        "T": "TB", "TB": "TB", "TIB": "TB",
        "P": "PB", "PB": "PB", "PIB": "PB",
    }
    unit = unit_map.get(raw_unit, "MB")
    val_str = f"{val:g}"
    return f"{val_str} {unit}"



def parse_duration_seconds(raw: str) -> Optional[float]:
    """
    Parses a duration string into seconds (float).
    Supports:
      - Pure seconds: '45', '45s', '90.5'
      - Minutes: '5m', '1.5m', '10min'
      - Hours: '1h', '2.5h'
      - Colon format: '1:30' (MM:SS), '01:30', '01:15:30' (HH:MM:SS)
    """
    if not raw:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None

    # Colon format: HH:MM:SS or MM:SS
    if ":" in s:
        parts = s.split(":")
        try:
            if len(parts) == 2:
                mins = float(parts[0])
                secs = float(parts[1])
                return max(0.0, mins * 60.0 + secs)
            elif len(parts) == 3:
                hrs = float(parts[0])
                mins = float(parts[1])
                secs = float(parts[2])
                return max(0.0, hrs * 3600.0 + mins * 60.0 + secs)
        except ValueError:
            return None

    # Suffix format: '30s', '5m', '1h', '10min'
    m = re.match(r"^([\d.]+)\s*(s|sec|secs|m|min|mins|h|hr|hrs)?$", s)
    if m:
        val_str, unit = m.groups()
        try:
            val = float(val_str)
        except ValueError:
            return None
        if not unit or unit in ("s", "sec", "secs"):
            return max(0.0, val)
        if unit in ("m", "min", "mins"):
            return max(0.0, val * 60.0)
        if unit in ("h", "hr", "hrs"):
            return max(0.0, val * 3600.0)

    return None


def format_duration_str(seconds: Optional[float]) -> str:
    """
    Formats seconds into a human-readable duration string:
    e.g. 45 -> '0:45', 90 -> '1:30', 3665 -> '1:01:05'
    """
    if seconds is None:
        return ""
    sec_val = safe_float(seconds, -1.0)
    if sec_val < 0:
        return ""
    total_secs = int(round(sec_val))
    hrs = total_secs // 3600
    mins = (total_secs % 3600) // 60
    secs = total_secs % 60
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def normalize_duration_str(raw: str) -> str:
    """Normalizes a raw duration string into standard format (MM:SS or HH:MM:SS)."""
    sec = parse_duration_seconds(raw)
    return format_duration_str(sec) if sec is not None else ""


class FilterOptions:
    def __init__(
        self,
        characters: str = "",
        character_scope: str = "title",
        skip_words: str = "",
        skip_scope: str = "posts",
        remove_words: str = "",
        file_type: str = "all",
        skip_archives: bool = False,
        download_thumbnails_only: bool = False,
        scan_content_images: bool = True,
        download_dms: bool = False,
        compress_to_webp: bool = False,
        keep_duplicates: bool = False,
        favorite_mode: bool = False,
        subfolder_per_post: bool = True,
        date_prefix: bool = True,
        separate_by_known: bool = False,
        download_revisions: bool = False,
        adaptive_threading: bool = False,
        threads_locked: bool = False,
        auto_retry_at_end: bool = False,
        manga_mode: bool = False,
        filename_style: str = "post_title",
        filename_template: str = "{title} - {orig_name}",
        proxy_url: str = "",
        page_start: int = 1,
        page_end: int = 999999,
        download_delay: float = 2.0,
        save_post_metadata: bool = True,
        download_embeds: bool = True,
        file_index_prefix: bool = False,
        tag_folder_mode: bool = False,
        skip_post_covers: bool = False,
        date_after: str = "",
        date_before: str = "",
        download_pawchive_temporary_files: bool = True,
        min_file_size: str = "",
        max_file_size: str = "",
        write_audio_metadata: bool = False,
        fallback_to_thumbnails: bool = False,
        redownload_small_files: bool = False,
        exact_extensions: str = "",
        skip_retry_404: bool = False,
        group_file_type: str = "none",
        date_folder_mode: str = "none",
        file_order: str = "posted",
        webp_quality: str = "balanced",
        write_sidecars: bool = False,
        sidecar_format: str = "json",
        sidecar_scope: str = "per_file",
        video_duration_filter_enabled: bool = False,
        min_video_duration: str = "",
        max_video_duration: str = "",
        force_redownload: bool = False,
        disk_sync_mode: str = "all",
    ):
        self.characters = characters
        self.character_scope = character_scope
        self.skip_words = skip_words
        self.skip_scope = skip_scope
        self.remove_words = remove_words
        self.file_type = file_type
        self.exact_extensions = str(exact_extensions or "").strip()
        self.skip_archives = skip_archives
        self.download_thumbnails_only = download_thumbnails_only
        self.scan_content_images = scan_content_images
        self.download_dms = download_dms
        self.compress_to_webp = compress_to_webp
        self.keep_duplicates = keep_duplicates
        self.favorite_mode = favorite_mode
        self.subfolder_per_post = subfolder_per_post
        self.date_prefix = date_prefix
        self.separate_by_known = separate_by_known
        self.tag_folder_mode = tag_folder_mode
        self.download_revisions = download_revisions
        self.adaptive_threading = adaptive_threading
        self.threads_locked = threads_locked
        self.auto_retry_at_end = auto_retry_at_end
        self.manga_mode = manga_mode
        self.filename_style = filename_style
        self.filename_template = filename_template or "{title} - {orig_name}"
        self.proxy_url = proxy_url
        self.page_start = max(1, safe_int(page_start, 1))
        self.page_end = max(1, safe_int(page_end, 999999))
        self.download_delay = max(0.0, safe_float(download_delay, 2.0))
        self.save_post_metadata = save_post_metadata
        self.download_embeds = download_embeds
        self.file_index_prefix = file_index_prefix
        self.skip_post_covers = skip_post_covers
        self.date_after = date_after
        self.date_before = date_before
        self.download_pawchive_temporary_files = download_pawchive_temporary_files
        self.min_file_size = normalize_size_str(min_file_size) if min_file_size else ""
        self.max_file_size = normalize_size_str(max_file_size) if max_file_size else ""
        self.write_audio_metadata = bool(write_audio_metadata)
        self.fallback_to_thumbnails = bool(fallback_to_thumbnails)
        self.redownload_small_files = bool(redownload_small_files)
        self.skip_retry_404 = bool(skip_retry_404)
        self.group_file_type = str(group_file_type).lower() if str(group_file_type).lower() in ("none", "post", "creator") else "none"
        self.date_folder_mode = normalize_date_folder_mode(date_folder_mode)
        # Order of the files inside a post: "posted", "reversed" or "name" (see core/file_order.py)
        from core.file_order import normalize_file_order
        self.file_order = normalize_file_order(file_order)
        # How strongly "Compress to WebP" compresses: lossless / high / balanced / small / smallest
        self.webp_quality = str(webp_quality).lower() if str(webp_quality).lower() in WEBP_QUALITY_LEVELS else "balanced"
        self.write_sidecars = bool(write_sidecars)
        self.sidecar_format = str(sidecar_format).lower() if str(sidecar_format).lower() in ("json", "txt", "both") else "json"
        self.sidecar_scope = str(sidecar_scope).lower() if str(sidecar_scope).lower() in ("per_file", "per_post") else "per_file"
        self.video_duration_filter_enabled = bool(video_duration_filter_enabled)
        self.min_video_duration = normalize_duration_str(min_video_duration) if min_video_duration else ""
        self.max_video_duration = normalize_duration_str(max_video_duration) if max_video_duration else ""
        self.force_redownload = bool(force_redownload)
        self.disk_sync_mode = normalize_disk_sync_mode(disk_sync_mode)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize filter options to dictionary for persistence."""
        return {
            "characters": self.characters,
            "character_scope": self.character_scope,
            "skip_words": self.skip_words,
            "skip_scope": self.skip_scope,
            "remove_words": self.remove_words,
            "file_type": self.file_type,
            "skip_archives": self.skip_archives,
            "download_thumbnails_only": self.download_thumbnails_only,
            "scan_content_images": self.scan_content_images,
            "download_dms": self.download_dms,
            "compress_to_webp": self.compress_to_webp,
            "keep_duplicates": self.keep_duplicates,
            "favorite_mode": self.favorite_mode,
            "subfolder_per_post": self.subfolder_per_post,
            "date_prefix": self.date_prefix,
            "separate_by_known": self.separate_by_known,
            "tag_folder_mode": self.tag_folder_mode,
            "download_revisions": self.download_revisions,
            "adaptive_threading": self.adaptive_threading,
            "threads_locked": self.threads_locked,
            "auto_retry_at_end": self.auto_retry_at_end,
            "manga_mode": self.manga_mode,
            "filename_style": self.filename_style,
            "filename_template": self.filename_template,
            "proxy_url": self.proxy_url,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "download_delay": self.download_delay,
            "save_post_metadata": self.save_post_metadata,
            "download_embeds": self.download_embeds,
            "file_index_prefix": self.file_index_prefix,
            "skip_post_covers": self.skip_post_covers,
            "date_after": self.date_after,
            "date_before": self.date_before,
            "download_pawchive_temporary_files": self.download_pawchive_temporary_files,
            "min_file_size": self.min_file_size,
            "max_file_size": self.max_file_size,
            "write_audio_metadata": self.write_audio_metadata,
            "fallback_to_thumbnails": self.fallback_to_thumbnails,
            "redownload_small_files": self.redownload_small_files,
            "exact_extensions": self.exact_extensions,
            "skip_retry_404": self.skip_retry_404,
            "group_file_type": self.group_file_type,
            "date_folder_mode": self.date_folder_mode,
            "file_order": self.file_order,
            "webp_quality": self.webp_quality,
            "write_sidecars": self.write_sidecars,
            "sidecar_format": self.sidecar_format,
            "sidecar_scope": self.sidecar_scope,
            "video_duration_filter_enabled": self.video_duration_filter_enabled,
            "min_video_duration": self.min_video_duration,
            "max_video_duration": self.max_video_duration,
            "force_redownload": self.force_redownload,
            "disk_sync_mode": self.disk_sync_mode,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FilterOptions":
        """Reconstruct FilterOptions from a dictionary."""
        if not isinstance(d, dict):
            return cls()
        return cls(
            characters=d.get("characters", ""),
            character_scope=d.get("character_scope", "title"),
            skip_words=d.get("skip_words", ""),
            skip_scope=d.get("skip_scope", "posts"),
            remove_words=d.get("remove_words", ""),
            file_type=d.get("file_type", "all"),
            skip_archives=bool(d.get("skip_archives", False)),
            download_thumbnails_only=bool(d.get("download_thumbnails_only", False)),
            scan_content_images=bool(d.get("scan_content_images", True)),
            download_dms=bool(d.get("download_dms", False)),
            compress_to_webp=bool(d.get("compress_to_webp", False)),
            keep_duplicates=bool(d.get("keep_duplicates", False)),
            favorite_mode=bool(d.get("favorite_mode", False)),
            subfolder_per_post=bool(d.get("subfolder_per_post", True)),
            date_prefix=bool(d.get("date_prefix", True)),
            separate_by_known=bool(d.get("separate_by_known", False)),
            tag_folder_mode=bool(d.get("tag_folder_mode", False)),
            download_revisions=bool(d.get("download_revisions", False)),
            adaptive_threading=bool(d.get("adaptive_threading", False)),
            threads_locked=bool(d.get("threads_locked", False)),
            auto_retry_at_end=bool(d.get("auto_retry_at_end", False)),
            manga_mode=bool(d.get("manga_mode", False)),
            filename_style=d.get("filename_style", "post_title"),
            filename_template=d.get("filename_template", "{title} - {orig_name}"),
            proxy_url=d.get("proxy_url", ""),
            page_start=max(1, safe_int(d.get("page_start", 1), 1)),
            page_end=max(1, safe_int(d.get("page_end", 999999), 999999)),
            download_delay=max(0.0, safe_float(d.get("download_delay", 2.0), 2.0)),
            save_post_metadata=bool(d.get("save_post_metadata", True)),
            download_embeds=bool(d.get("download_embeds", True)),
            file_index_prefix=bool(d.get("file_index_prefix", False)),
            skip_post_covers=bool(d.get("skip_post_covers", False)),
            date_after=d.get("date_after", ""),
            date_before=d.get("date_before", ""),
            download_pawchive_temporary_files=bool(d.get("download_pawchive_temporary_files", True)),
            min_file_size=d.get("min_file_size", ""),
            max_file_size=d.get("max_file_size", ""),
            write_audio_metadata=bool(d.get("write_audio_metadata", False)),
            fallback_to_thumbnails=bool(d.get("fallback_to_thumbnails", False)),
            redownload_small_files=bool(d.get("redownload_small_files", False)),
            exact_extensions=d.get("exact_extensions", ""),
            skip_retry_404=bool(d.get("skip_retry_404", False)),
            group_file_type=d.get("group_file_type", "none"),
            date_folder_mode=d.get("date_folder_mode", "none"),
            file_order=d.get("file_order", "posted"),
            webp_quality=d.get("webp_quality", "balanced"),
            write_sidecars=bool(d.get("write_sidecars", False)),
            sidecar_format=d.get("sidecar_format", "json"),
            sidecar_scope=d.get("sidecar_scope", "per_file"),
            video_duration_filter_enabled=bool(d.get("video_duration_filter_enabled", False)),
            min_video_duration=d.get("min_video_duration", ""),
            max_video_duration=d.get("max_video_duration", ""),
            force_redownload=bool(d.get("force_redownload", False)),
            disk_sync_mode=d.get("disk_sync_mode", "all"),
        )


def _norm_setting_path(path: str) -> str:
    p = str(path or "").strip()
    if not p:
        return ""
    return os.path.normcase(os.path.normpath(p))


def _norm_scan_date(date_str: str) -> str:
    return str(date_str or "").strip()


def classify_settings_change(
    old_opts: FilterOptions,
    new_opts: FilterOptions,
    old_dir: str = "",
    new_dir: str = "",
    old_site_in_name: Optional[bool] = None,
    new_site_in_name: Optional[bool] = None,
    old_known_mode: str = "",
    new_known_mode: str = "",
    old_ai_enabled: Optional[bool] = None,
    new_ai_enabled: Optional[bool] = None,
    old_ai_engine: str = "",
    new_ai_engine: str = "",
    *,
    has_comments_fetched: bool = False,
    fetched_dms: bool = False,
    has_favs_fetched: bool = False,
    scan_bounds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare old vs new download settings and classify impact Tier (0/2/3/4).

    Tiers:
      0: No impactful change (UI / post-session only)
      2: Runtime transport / post-processing only (no task rebuild needed)
      3: Task plan / filter / naming / path rebuild from cached posts
      4: API scan scope expansion required (DMs, comments, favorites, wider pages/dates)
    """
    changed_fields: List[str] = []
    labels: List[str] = []
    tier = 0

    def _bump(new_tier: int, field_name: str, label: str):
        nonlocal tier
        if field_name not in changed_fields:
            changed_fields.append(field_name)
        if label and label not in labels:
            labels.append(label)
        if new_tier > tier:
            tier = new_tier

    # Destination / site naming
    if old_dir or new_dir:
        if _norm_setting_path(old_dir) != _norm_setting_path(new_dir):
            _bump(3, "download_dir", "Download folder")
    if old_site_in_name is not None and new_site_in_name is not None and bool(old_site_in_name) != bool(new_site_in_name):
        _bump(3, "site_in_folder_name", "Site in creator folder")
    if (old_known_mode or new_known_mode) and str(old_known_mode) != str(new_known_mode):
        _bump(3, "known_recognition_mode", "Character detection mode")
    if old_ai_enabled is not None and new_ai_enabled is not None and bool(old_ai_enabled) != bool(new_ai_enabled):
        _bump(3, "ai_recognition_enabled", "AI character detection")
    if (old_ai_engine or new_ai_engine) and str(old_ai_engine) != str(new_ai_engine):
        _bump(3, "ai_engine_mode", "AI engine mode")

    # Tier 2 runtime/transport/post-processing options
    runtime_checks = (
        ("proxy_url", "Proxy URL"),
        ("download_delay", "Download delay"),
        ("adaptive_threading", "Adaptive threading"),
        ("threads_locked", "Locked thread count"),
        ("auto_retry_at_end", "Auto-retry failed"),
        ("skip_retry_404", "Skip retrying 404s"),
        ("fallback_to_thumbnails", "Thumbnail fallback"),
        ("redownload_small_files", "Re-download small files"),
        ("webp_quality", "WebP quality"),
        ("write_audio_metadata", "Audio metadata tags"),
        ("min_file_size", "Minimum file size"),
        ("max_file_size", "Maximum file size"),
    )
    proxy_changed = str(getattr(old_opts, "proxy_url", "") or "").strip() != str(getattr(new_opts, "proxy_url", "") or "").strip()
    for attr, lbl in runtime_checks:
        if getattr(old_opts, attr, None) != getattr(new_opts, attr, None):
            _bump(2, attr, lbl)

    # Tier 3 local plan / naming / filter / folder structure options
    plan_checks = (
        ("characters", "Character filter"),
        ("skip_words", "Skip keywords"),
        ("skip_scope", "Skip keyword scope"),
        ("remove_words", "Remove filename words"),
        ("file_type", "File type filter"),
        ("exact_extensions", "Exact extensions"),
        ("skip_archives", "Skip archives"),
        ("download_thumbnails_only", "Thumbnails only"),
        ("scan_content_images", "Inline content images"),
        ("compress_to_webp", "WebP conversion"),
        ("keep_duplicates", "Keep duplicate files"),
        ("subfolder_per_post", "Subfolder per post"),
        ("date_prefix", "Date prefix"),
        ("separate_by_known", "Separate folders by character"),
        ("tag_folder_mode", "Sort by tags"),
        ("download_revisions", "Post revisions"),
        ("manga_mode", "Manga numbering mode"),
        ("filename_style", "Filename style"),
        ("filename_template", "Filename template"),
        ("save_post_metadata", "Save post metadata"),
        ("download_embeds", "Embedded media"),
        ("file_index_prefix", "File index prefix"),
        ("skip_post_covers", "Skip post covers"),
        ("download_pawchive_temporary_files", "Pawchive temporary files"),
        ("group_file_type", "Group by file type"),
        ("date_folder_mode", "Sort by date folder"),
        ("file_order", "File order"),
        ("write_sidecars", "Metadata sidecars"),
        ("sidecar_format", "Sidecar format"),
        ("sidecar_scope", "Sidecar scope"),
        ("video_duration_filter_enabled", "Video duration filter"),
        ("min_video_duration", "Min video duration"),
        ("max_video_duration", "Max video duration"),
    )
    for attr, lbl in plan_checks:
        if getattr(old_opts, attr, None) != getattr(new_opts, attr, None):
            _bump(3, attr, lbl)

    # Tier 4 API scope expansion checks
    requires_dm_scan = False
    requires_comments_scan = False
    requires_fav_scan = False
    requires_window_expand = False
    requires_links_rescan = False

    old_dms = bool(getattr(old_opts, "download_dms", False))
    new_dms = bool(getattr(new_opts, "download_dms", False))
    if old_dms != new_dms:
        if new_dms and not fetched_dms:
            requires_dm_scan = True
            _bump(4, "download_dms", "Direct messages")
        else:
            _bump(3, "download_dms", "Direct messages")

    old_fav = bool(getattr(old_opts, "favorite_mode", False))
    new_fav = bool(getattr(new_opts, "favorite_mode", False))
    if old_fav != new_fav:
        if new_fav and not has_favs_fetched:
            requires_fav_scan = True
            _bump(4, "favorite_mode", "Favorite mode")
        else:
            _bump(3, "favorite_mode", "Favorite mode")

    old_cscope = str(getattr(old_opts, "character_scope", "title") or "title").lower()
    new_cscope = str(getattr(new_opts, "character_scope", "title") or "title").lower()
    if old_cscope != new_cscope:
        if new_cscope in ("comments", "all") and not has_comments_fetched and bool(str(getattr(new_opts, "characters", "") or "").strip()):
            requires_comments_scan = True
            _bump(4, "character_scope", "Character comment scope")
        else:
            _bump(3, "character_scope", "Character scope")
    elif new_cscope in ("comments", "all") and str(getattr(new_opts, "characters", "") or "").strip() and not has_comments_fetched:
        requires_comments_scan = True
        _bump(4, "characters", "Character comment filter")

    bounds = scan_bounds or {}
    scanned_p_start = max(1, safe_int(bounds.get("page_start", getattr(old_opts, "page_start", 1)), 1))
    scanned_p_end = max(1, safe_int(bounds.get("page_end", getattr(old_opts, "page_end", 999999)), 999999))
    new_p_start = max(1, safe_int(getattr(new_opts, "page_start", 1), 1))
    new_p_end = max(1, safe_int(getattr(new_opts, "page_end", 999999), 999999))
    old_p_start = max(1, safe_int(getattr(old_opts, "page_start", 1), 1))
    old_p_end = max(1, safe_int(getattr(old_opts, "page_end", 999999), 999999))
    if new_p_start != old_p_start or new_p_end != old_p_end:
        if new_p_start < scanned_p_start or new_p_end > scanned_p_end:
            requires_window_expand = True
            _bump(4, "page_range", "Page range")
        else:
            _bump(3, "page_range", "Page range")

    scanned_after = _norm_scan_date(bounds.get("date_after", getattr(old_opts, "date_after", "")))
    scanned_before = _norm_scan_date(bounds.get("date_before", getattr(old_opts, "date_before", "")))
    new_after = _norm_scan_date(getattr(new_opts, "date_after", ""))
    new_before = _norm_scan_date(getattr(new_opts, "date_before", ""))
    if new_after != _norm_scan_date(getattr(old_opts, "date_after", "")) or new_before != _norm_scan_date(getattr(old_opts, "date_before", "")):
        expanded_after = bool(scanned_after) and (not new_after or new_after < scanned_after)
        expanded_before = bool(scanned_before) and (not new_before or new_before > scanned_before)
        if expanded_after or expanded_before:
            requires_window_expand = True
            _bump(4, "date_range", "Date filter")
        else:
            _bump(3, "date_range", "Date filter")

    old_ft = str(getattr(old_opts, "file_type", "all") or "all").lower()
    new_ft = str(getattr(new_opts, "file_type", "all") or "all").lower()
    if (old_ft == "links") != (new_ft == "links"):
        requires_links_rescan = True

    dest_changed = any(f in changed_fields for f in (
        "download_dir", "site_in_folder_name", "subfolder_per_post", "date_prefix",
        "separate_by_known", "tag_folder_mode", "group_file_type", "date_folder_mode",
        "filename_style", "filename_template", "manga_mode", "file_index_prefix"
    ))

    if not labels:
        summary = ""
    elif len(labels) <= 3:
        summary = ", ".join(labels)
    else:
        summary = f"{', '.join(labels[:3])} (+{len(labels) - 3} more)"

    return {
        "tier": tier,
        "has_changes": tier > 0,
        "changed_fields": changed_fields,
        "labels": labels,
        "summary": summary,
        "proxy_changed": proxy_changed,
        "dest_changed": dest_changed,
        "requires_dm_scan": requires_dm_scan,
        "requires_comments_scan": requires_comments_scan,
        "requires_fav_scan": requires_fav_scan,
        "requires_window_expand": requires_window_expand,
        "requires_links_rescan": requires_links_rescan,
    }
FILTER_PROFILES = {
    "wip_sketches": {
        "id": "wip_sketches",
        "name": "WIP & Sketches",
        "keywords": "WIP, sketch, draft, rough, lineart, doodle",
        "description": "Skip work-in-progress, sketches, drafts, roughs, and lineart",
    },
    "low_quality": {
        "id": "low_quality",
        "name": "Low Quality & Previews",
        "keywords": "preview, thumbnail, sample, lowres, [>=500KB]",
        "description": "Skip low-resolution previews, thumbnails, samples, and files under 500KB",
    },
    "wip_and_low_quality": {
        "id": "wip_and_low_quality",
        "name": "WIP, Sketches & Low-Res",
        "keywords": "WIP, sketch, draft, rough, lineart, preview, thumbnail, sample, lowres, [>=500KB]",
        "description": "Skip both drafts/sketches and low-resolution preview files",
    },
    "watermarks_samples": {
        "id": "watermarks_samples",
        "name": "Watermarks & Samples",
        "keywords": "sample, watermark, [sample], preview",
        "description": "Skip watermarked files, samples, and promotional previews",
    },
    "final_art_only": {
        "id": "final_art_only",
        "name": "Final Art Only",
        "keywords": "WIP, draft, sketch, preview, sample, promo, cover, teaser",
        "description": "Keep only completed final artwork by skipping drafts, sketches, and promo teasers",
    },
    "large_media_only": {
        "id": "large_media_only",
        "name": "Large Media Only",
        "keywords": "preview, thumbnail, sample, [>=1MB]",
        "description": "Skip small files under 1MB and sample previews",
    },
}

REMOVE_WORDS_PROFILES = {
    "clean_names": {
        "id": "clean_names",
        "name": "Clean Names",
        "keywords": "patreon, fanbox, HD, [sample], preview",
        "description": "Remove common platform labels and sample markers from filenames",
    },
    "patreon_promo": {
        "id": "patreon_promo",
        "name": "Patreon & Promo Tags",
        "keywords": "patreon, fanbox, gumroad, subpost, [sample]",
        "description": "Remove creator subscription platform tags and promo suffixes",
    },
    "watermark_tags": {
        "id": "watermark_tags",
        "name": "Watermark Tags",
        "keywords": "watermark, sample, preview, promo",
        "description": "Strip watermark and sample terms from filenames",
    },
}


