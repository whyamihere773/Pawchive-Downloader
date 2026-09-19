"""
Filtering & Path Sanitization Engine
Filters posts and media attachments by character tags, skip words, size constraints,
media categories, and formats safe cross-platform filesystem filenames.
"""

import re
import os
import unicodedata
import csv
import io
import datetime
from typing import List, Dict, Any, Optional, Tuple


class MediaTypes:
    ALL = "all"
    IMAGES = "images"
    VIDEOS = "videos"
    ARCHIVES = "archives"
    AUDIO = "audio"
    LINKS = "links"

    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg", ".psd", ".clip", ".sai"}
    VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".flv", ".wmv"}
    AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
    ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"}


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
        write_audio_metadata: bool = True
    ):
        self.characters = characters
        self.character_scope = character_scope
        self.skip_words = skip_words
        self.skip_scope = skip_scope
        self.remove_words = remove_words
        self.file_type = file_type
        self.skip_archives = skip_archives
        self.download_thumbnails_only = download_thumbnails_only
        self.scan_content_images = scan_content_images
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
        self.page_start = page_start
        self.page_end = page_end
        self.download_delay = download_delay
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
            page_start=int(d.get("page_start", 1)),
            page_end=int(d.get("page_end", 999999)),
            download_delay=float(d.get("download_delay", 2.0)),
            save_post_metadata=bool(d.get("save_post_metadata", True)),
            download_embeds=bool(d.get("download_embeds", True)),
            file_index_prefix=bool(d.get("file_index_prefix", False)),
            skip_post_covers=bool(d.get("skip_post_covers", False)),
            date_after=d.get("date_after", ""),
            date_before=d.get("date_before", ""),
            download_pawchive_temporary_files=bool(d.get("download_pawchive_temporary_files", True)),
            min_file_size=d.get("min_file_size", ""),
            max_file_size=d.get("max_file_size", ""),
            write_audio_metadata=bool(d.get("write_audio_metadata", True)),
        )



class FilterEngine:
    @staticmethod
    def normalize_date(date_str: str) -> str:
        """Normalizes user-supplied date string into YYYY-MM-DD format.

        Supports:
          - YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD  → returned as-is (fully expanded)
          - YYYY-MM / YYYY/MM / YYYY.MM           → returned as YYYY-MM (caller expands)
          - YYYY                                   → returned as YYYY (caller expands)
        """
        if not date_str:
            return ""
        s = date_str.strip().replace("/", "-").replace(".", "-")
        parts = s.split("-")
        if len(parts) == 3:
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                return f"{y:04d}-{m:02d}-{d:02d}"
            except ValueError:
                pass
        elif len(parts) == 2:
            try:
                y, m = int(parts[0]), int(parts[1])
                return f"{y:04d}-{m:02d}"
            except ValueError:
                pass
        elif len(parts) == 1 and parts[0].isdigit() and len(parts[0]) == 4:
            return parts[0]  # bare year e.g. "2024"
        return s[:10]

    @classmethod
    def expand_date_start(cls, date_str: str) -> str:
        """Expand a partial date to the *earliest* possible full YYYY-MM-DD.

        Examples:
          "2024"    → "2024-01-01"
          "2024-06" → "2024-06-01"
          "2024-06-15" → "2024-06-15"  (unchanged)
        """
        n = cls.normalize_date(date_str)
        if not n:
            return ""
        parts = n.split("-")
        if len(parts) == 1:   # bare year
            return f"{n}-01-01"
        if len(parts) == 2:   # year-month
            return f"{n}-01"
        return n              # already full

    @classmethod
    def expand_date_end(cls, date_str: str) -> str:
        """Expand a partial date to the *latest* possible full YYYY-MM-DD.

        Examples:
          "2024"    → "2024-12-31"
          "2024-06" → "2024-06-30"
          "2024-02" → "2024-02-29" (leap year aware)
          "2024-06-15" → "2024-06-15"  (unchanged)
        """
        import calendar as _cal
        n = cls.normalize_date(date_str)
        if not n:
            return ""
        parts = n.split("-")
        if len(parts) == 1:   # bare year
            return f"{n}-12-31"
        if len(parts) == 2:   # year-month
            try:
                y, m = int(parts[0]), int(parts[1])
                last_day = _cal.monthrange(y, m)[1]
                return f"{y:04d}-{m:02d}-{last_day:02d}"
            except (ValueError, IndexError):
                return f"{n}-30"  # safe fallback
        return n              # already full

    @staticmethod
    def _parse_comma_list(text: str) -> List[str]:
        if not text:
            return []
        items = []
        for part in text.split(","):
            cleaned = part.strip()
            if cleaned:
                items.append(cleaned)
        return items

    normalize_size_str = staticmethod(normalize_size_str)

    @classmethod
    def _parse_size_str(cls, s: str) -> int:
        if not s:
            return 0
        norm = normalize_size_str(s)
        if not norm:
            return 0
        m = re.match(r'^([\d.]+)\s*(B|KB|MB|GB|TB|PB)$', norm)
        if not m:
            return 0
        try:
            val = float(m.group(1))
            unit = m.group(2)
            multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4, 'PB': 1024**5}
            return int(val * multipliers.get(unit, 1024**2))
        except (ValueError, TypeError):
            return 0

    @classmethod
    def get_file_size_range_bytes(cls, skip_words: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parses size range filters embedded in skip_words inside brackets:
        - Ranges: [1GB-2GB], [1GB..2GB], [1024-2048], [1.5GB to 3GB]
        - Minimums: [>=1GB], [>1GB], [1GB+], [1000] (legacy min MB)
        - Maximums: [<=2GB], [<500MB]
        Returns (min_bytes, max_bytes).
        """
        if not skip_words:
            return None, None
        m = re.search(r'\[\s*(?:size:)?\s*([^\]]+)\]', skip_words, re.IGNORECASE)
        if not m:
            return None, None
        expr = m.group(1).strip()

        # Range: A - B or A..B or A to B
        range_m = re.match(r'^([\d.]+\s*(?:[KMGTP]?B)?)\s*(?:-|–|\.\.|to|<=)\s*([\d.]+\s*(?:[KMGTP]?B)?)$', expr, re.IGNORECASE)
        if range_m:
            min_b = cls._parse_size_str(range_m.group(1))
            max_b = cls._parse_size_str(range_m.group(2))
            if min_b and max_b and min_b > max_b:
                min_b, max_b = max_b, min_b
            return (min_b, max_b)

        # Minimum only: >= A or > A or A+
        gt_m = re.match(r'^(?:>=|>|\+)?\s*([\d.]+\s*(?:[KMGTP]?B)?)\+?$', expr, re.IGNORECASE)
        if expr.startswith(('>', '>=')) or expr.endswith('+'):
            return (cls._parse_size_str(gt_m.group(1)), None)

        # Maximum only: <= B or < B
        lt_m = re.match(r'^(?:<=|<)\s*([\d.]+\s*(?:[KMGTP]?B)?)$', expr, re.IGNORECASE)
        if lt_m:
            return (None, cls._parse_size_str(lt_m.group(1)))

        # Single number (backward compatible: min MB if no unit, or unit-aware)
        single_m = re.match(r'^([\d.]+\s*(?:[KMGTP]?B)?)$', expr, re.IGNORECASE)
        if single_m:
            return (cls._parse_size_str(single_m.group(1)), None)

        return None, None

    @classmethod
    def get_min_file_size_bytes(cls, skip_words: str) -> Optional[int]:
        min_size, _ = cls.get_file_size_range_bytes(skip_words)
        return min_size

    @classmethod
    def should_keep_post(cls, post: Dict[str, Any], options: FilterOptions) -> Tuple[bool, str]:
        title = post.get("title", "") or ""
        content = post.get("content", "") or ""

        # Date range filtering (From / To)
        if options.date_after or options.date_before:
            published = post.get("published") or post.get("added") or ""
            post_date = ""
            if isinstance(published, (int, float)):
                try:
                    post_date = datetime.datetime.fromtimestamp(published).strftime("%Y-%m-%d")
                except Exception:
                    post_date = str(published)[:10]
            elif published:
                pub_str = str(published).strip()
                post_date = pub_str.split("T")[0] if "T" in pub_str else pub_str[:10]

            if not post_date or post_date == "0000-00-00":
                return False, "Post has no valid publication date"

            norm_after = cls.expand_date_start(options.date_after)
            norm_before = cls.expand_date_end(options.date_before)

            # Auto-correct inverted date range if user entered newer date in "From" and older date in "To"
            if norm_after and norm_before and norm_after > norm_before:
                norm_after, norm_before = norm_before, norm_after

            if norm_after and post_date < norm_after:
                return False, f"Post date ({post_date}) is before {norm_after}"

            if norm_before and post_date > norm_before:
                return False, f"Post date ({post_date}) is after {norm_before}"

        if options.skip_words and options.skip_scope in ("posts", "both"):
            skip_list = cls._parse_comma_list(options.skip_words)
            for word in skip_list:
                if word.startswith("[") and word.endswith("]"):
                    continue
                if re.search(r"\b" + re.escape(word) + r"\b", title, re.IGNORECASE) or \
                   re.search(r"\b" + re.escape(word) + r"\b", content, re.IGNORECASE):
                    return False, f"Post contains skipped word: '{word}'"

        if options.characters:
            char_list = cls._parse_comma_list(options.characters)
            matched = False
            
            if options.character_scope == "title":
                search_text = title
            elif options.character_scope == "content":
                search_text = content
            elif options.character_scope == "comments":
                comments = post.get("comments_text", "")
                search_text = f"{title}\n{comments}"
            else:
                comments = post.get("comments_text", "")
                search_text = f"{title}\n{content}\n{comments}"

            for char_term in char_list:
                term_clean = char_term.strip("()")
                sub_terms = [t.strip() for t in term_clean.split("/") if t.strip()]
                if not sub_terms:
                    sub_terms = [term_clean]

                for st in sub_terms:
                    if re.search(r"\b" + re.escape(st) + r"\b", search_text, re.IGNORECASE):
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                return False, f"Post did not match character filter: '{options.characters}'"

        return True, "Passed filter"

    @classmethod
    def should_keep_file(cls, filename: str, options: FilterOptions, file_size: Optional[int] = None) -> Tuple[bool, str]:
        if not filename:
            return False, "Empty filename"

        _, ext = os.path.splitext(filename.lower())

        if file_size is not None and file_size > 0:
            # Check explicit min/max fields first, then bracket expression in skip_words
            opt_min_str = (getattr(options, "min_file_size", "") or "").strip()
            opt_max_str = (getattr(options, "max_file_size", "") or "").strip()
            min_size = cls._parse_size_str(opt_min_str) if opt_min_str else None
            max_size = cls._parse_size_str(opt_max_str) if opt_max_str else None

            # If either is not set, check skip_words bracket expression e.g. [1GB-2GB]
            sw_min, sw_max = cls.get_file_size_range_bytes(options.skip_words)
            if min_size is None and sw_min is not None:
                min_size = sw_min
            if max_size is None and sw_max is not None:
                max_size = sw_max

            # Auto-correct inverted range (e.g. Min: 2GB, Max: 1GB) so downloads don't fail
            if min_size is not None and max_size is not None and min_size > max_size:
                min_size, max_size = max_size, min_size

            if min_size is not None and file_size < min_size:
                min_str = f"{min_size / (1024 * 1024 * 1024):.1f} GB" if min_size >= 1024**3 else f"{min_size // (1024 * 1024)} MB"
                curr_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB" if file_size >= 1024**3 else f"{file_size // (1024 * 1024)} MB"
                return False, f"File size ({curr_str}) is below minimum threshold ({min_str})"
            if max_size is not None and file_size > max_size:
                max_str = f"{max_size / (1024 * 1024 * 1024):.1f} GB" if max_size >= 1024**3 else f"{max_size // (1024 * 1024)} MB"
                curr_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB" if file_size >= 1024**3 else f"{file_size // (1024 * 1024)} MB"
                return False, f"File size ({curr_str}) exceeds maximum threshold ({max_str})"

        if options.skip_archives and ext in MediaTypes.ARCHIVE_EXTS:
            return False, "Archive skipped due to 'Skip Archives' setting"

        if options.download_thumbnails_only:
            if ext in MediaTypes.ARCHIVE_EXTS:
                return False, f"Archive skipped (no thumbnails available for {ext})"
            if ext in MediaTypes.AUDIO_EXTS:
                return False, f"Audio skipped (no thumbnails available for {ext})"
            if ext not in MediaTypes.IMAGE_EXTS and ext not in MediaTypes.VIDEO_EXTS:
                return False, f"Non-visual file skipped (no thumbnails available for {ext})"

        if options.skip_words and options.skip_scope in ("files", "both"):
            skip_list = cls._parse_comma_list(options.skip_words)
            stem = os.path.splitext(filename)[0]
            for word in skip_list:
                if word.startswith("[") and word.endswith("]"):
                    continue
                pattern = r"(?:^|[_\-\s])" + re.escape(word) + r"(?:[_\-\s]|$)"
                if re.search(pattern, stem, re.IGNORECASE):
                    return False, f"File contains skipped word: '{word}'"

        if options.file_type == MediaTypes.IMAGES:
            if ext not in MediaTypes.IMAGE_EXTS:
                return False, f"Not an image file ({ext})"
        elif options.file_type == MediaTypes.VIDEOS:
            if ext not in MediaTypes.VIDEO_EXTS:
                return False, f"Not a video file ({ext})"
        elif options.file_type == MediaTypes.ARCHIVES:
            if ext not in MediaTypes.ARCHIVE_EXTS:
                return False, f"Not an archive file ({ext})"
        elif options.file_type == MediaTypes.AUDIO:
            if ext not in MediaTypes.AUDIO_EXTS:
                return False, f"Not an audio file ({ext})"

        return True, "Passed file filter"

    @staticmethod
    def clean_filesystem_text(text: str, max_len: int = 120, fallback: str = "Untitled") -> str:
        if not text:
            return fallback

        text = unicodedata.normalize("NFC", text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'[\r\n\t]+', ' ', text)
        text = re.sub(r'[\\/*?:"<>|\x00-\x1f\x7f]', '_', text)

        cleaned_chars = []
        for ch in text:
            cat = unicodedata.category(ch)
            if cat.startswith(('L', 'N', 'M', 'P')) or cat == 'Zs':
                cleaned_chars.append(ch)
            elif ch in ('+', '=', '~', '$', '%', '^', '&', '@', '#', '`'):
                cleaned_chars.append(ch)
            elif cat in ('So', 'Sk', 'Sm', 'Sc', 'Cf', 'Co', 'Cs', 'Cc'):
                continue
            else:
                cleaned_chars.append(ch)

        text = "".join(cleaned_chars)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'_+', '_', text)
        text = text.strip(" ._\t\r\n")

        reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
                    "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
                    "LPT6", "LPT7", "LPT8", "LPT9"}
        if text.upper() in reserved:
            text = f"_{text}_"

        if max_len and len(text) > max_len:
            text = text[:max_len].strip(" ._")

        return text or fallback

    @classmethod
    def sanitize_filename(cls, filename: str, options: FilterOptions) -> str:
        # Strip trailing punctuation/whitespace BEFORE splitext.
        # Without this, 'cover.jpeg,' splits into name='cover.jpeg', ext=','
        # which results in a doubled/corrupt extension like 'cover.jpeg,'.
        filename = filename.rstrip(".,;!? \t")

        name, ext = os.path.splitext(filename)

        if options.remove_words:
            remove_list = cls._parse_comma_list(options.remove_words)
            for word in remove_list:
                name = re.sub(re.escape(word), "", name, flags=re.IGNORECASE)

        clean_name = cls.clean_filesystem_text(name, max_len=180, fallback="unnamed_file")
        clean_ext = cls.clean_filesystem_text(ext, max_len=16, fallback="")
        if clean_ext and not clean_ext.startswith("."):
            clean_ext = f".{clean_ext}"

        return f"{clean_name}{clean_ext or ext}"

    @classmethod
    def format_custom_filename(
        cls,
        original_filename: str,
        post_title: str,
        post_date: str,
        post_index: int,
        file_index: int,
        options: FilterOptions,
        folder_index: Optional[int] = None,
        post_id: str = "",
        artist: str = "",
        service: str = "",
        user_id: str = ""
    ) -> str:
        clean_orig = cls.sanitize_filename(original_filename, options)
        name_stem, ext = os.path.splitext(clean_orig)
        clean_title = cls.clean_filesystem_text(post_title, max_len=100, fallback="Post")
        clean_artist = cls.clean_filesystem_text(artist, max_len=80, fallback="Artist")
        date_str = (post_date or "")[:10]
        year = date_str[:4] if len(date_str) >= 4 else ""
        month = date_str[5:7] if len(date_str) >= 7 else ""
        day = date_str[8:10] if len(date_str) >= 10 else ""
        f_idx = folder_index if folder_index is not None else file_index

        style = options.filename_style or FilenameStyles.POST_TITLE

        if style == FilenameStyles.CUSTOM:
            tpl = getattr(options, "filename_template", "") or "{title} - {orig_name}"
            replacements = {
                "{post_id}": str(post_id or ""),
                "{artist}": clean_artist,
                "{service}": str(service or ""),
                "{user_id}": str(user_id or ""),
                "{title}": clean_title,
                "{date}": date_str,
                "{year}": year,
                "{month}": month,
                "{day}": day,
                "{orig_name}": clean_orig,
                "{name}": name_stem,
                "{ext}": ext,
                "{file_index}": f"{file_index:02d}",
                "{post_index}": f"{post_index:03d}",
                "{seq_idx}": f"{f_idx:03d}" if f_idx is not None else f"{file_index:03d}",
                "{folder_index}": f"{f_idx:03d}" if f_idx is not None else f"{file_index:03d}",
            }
            res = tpl
            for k, v in replacements.items():
                res = res.replace(k, v)

            # If user template didn't include {ext} or {orig_name}, ensure the file extension is preserved
            if "{ext}" not in tpl and "{orig_name}" not in tpl and ext:
                if not res.lower().endswith(ext.lower()):
                    res = f"{res}{ext}"

            res = cls.clean_filesystem_text(res, max_len=220, fallback=clean_orig)
        elif style == FilenameStyles.DATE_POST_TITLE:
            res = f"{date_str} - {clean_title} - {clean_orig}" if date_str else f"{clean_title} - {clean_orig}"
        elif style == FilenameStyles.DATE_BASED:
            res = f"{date_str}_{post_index:03d}_{file_index:02d}{ext}" if date_str else f"{post_index:03d}_{file_index:02d}{ext}"
        elif style == FilenameStyles.POST_TITLE_GLOBAL_NUMBERING:
            res = f"{post_index:03d}_{clean_title}_{file_index:02d}{ext}"
        else:
            res = clean_orig

        if getattr(options, "file_index_prefix", False) and style != FilenameStyles.CUSTOM:
            idx = folder_index if folder_index is not None else file_index
            if idx is not None and idx > 0:
                res = f"{idx:03d}_{res}"

        return res

    @classmethod
    def extract_content_images(cls, html_content: str) -> List[str]:
        if not html_content:
            return []

        pattern = r'(?:src|href)=["\']([^"\']+)["\']'
        matches = re.findall(pattern, html_content)
        images = []
        for m in matches:
            ext = os.path.splitext(m.lower().split("?")[0])[1]
            if ext in MediaTypes.IMAGE_EXTS:
                images.append(m)
        return images

    @classmethod
    def normalize_tags(cls, raw_tags: Any) -> List[str]:
        """
        Normalizes tag representations into a list of clean strings.
        Handles:
        - Python list of strings: ["tag1", "tag2"]
        - Python list of dicts (cum.st): [{"label": "..."}, {"slug": "..."}]
        - PostgreSQL array strings (Pawchive): '{"tag1","tag2"}' or '{tag1,tag2}'
        - Comma-separated strings: "tag1, tag2"
        """
        if not raw_tags:
            return []
        if isinstance(raw_tags, list):
            out = []
            for t in raw_tags:
                if isinstance(t, dict):
                    val = t.get("label") or t.get("slug") or t.get("tag") or ""
                else:
                    val = str(t)
                val = val.strip().strip('"\'')
                if val:
                    out.append(val)
            return out
        if isinstance(raw_tags, str):
            s = raw_tags.strip()
            if s.startswith("{") and s.endswith("}"):
                s = s[1:-1].strip()
            if not s:
                return []
            try:
                reader = csv.reader(io.StringIO(s))
                for row in reader:
                    return [r.strip().strip('"\'') for r in row if r.strip()]
            except Exception:
                return [t.strip().strip('"\'') for t in s.split(",") if t.strip()]
        return []

