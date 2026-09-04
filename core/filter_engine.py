"""
Filtering & Path Sanitization Engine
Filters posts and media attachments by character tags, skip words, size constraints,
media categories, and formats safe cross-platform filesystem filenames.
"""

import re
import os
import unicodedata
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
        proxy_url: str = "",
        page_start: int = 1,
        page_end: int = 999999,
        download_delay: float = 2.0,
        save_post_metadata: bool = True,
        download_embeds: bool = True
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
        self.download_revisions = download_revisions
        self.adaptive_threading = adaptive_threading
        self.threads_locked = threads_locked
        self.auto_retry_at_end = auto_retry_at_end
        self.manga_mode = manga_mode
        self.filename_style = filename_style
        self.proxy_url = proxy_url
        self.page_start = page_start
        self.page_end = page_end
        self.download_delay = download_delay
        self.save_post_metadata = save_post_metadata
        self.download_embeds = download_embeds


class FilterEngine:
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

    @classmethod
    def get_min_file_size_bytes(cls, skip_words: str) -> Optional[int]:
        if not skip_words:
            return None
        match = re.search(r'\[(\d+)\]', skip_words)
        if match:
            mb_val = int(match.group(1))
            return mb_val * 1024 * 1024
        return None

    @classmethod
    def should_keep_post(cls, post: Dict[str, Any], options: FilterOptions) -> Tuple[bool, str]:
        title = post.get("title", "") or ""
        content = post.get("content", "") or ""

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
            min_size = cls.get_min_file_size_bytes(options.skip_words)
            if min_size and file_size < min_size:
                return False, f"File size ({file_size // 1024 // 1024} MB) is below minimum threshold ({min_size // 1024 // 1024} MB)"

        if options.skip_archives and ext in MediaTypes.ARCHIVE_EXTS:
            return False, "Archive skipped due to 'Skip Archives' setting"

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
        options: FilterOptions
    ) -> str:
        clean_orig = cls.sanitize_filename(original_filename, options)
        name_stem, ext = os.path.splitext(clean_orig)
        clean_title = cls.clean_filesystem_text(post_title, max_len=100, fallback="Post")
        date_str = (post_date or "")[:10]

        style = options.filename_style or FilenameStyles.POST_TITLE

        if style == FilenameStyles.DATE_POST_TITLE:
            res = f"{date_str} - {clean_title} - {clean_orig}" if date_str else f"{clean_title} - {clean_orig}"
        elif style == FilenameStyles.DATE_BASED:
            res = f"{date_str}_{post_index:03d}_{file_index:02d}{ext}" if date_str else f"{post_index:03d}_{file_index:02d}{ext}"
        elif style == FilenameStyles.POST_TITLE_GLOBAL_NUMBERING:
            res = f"{post_index:03d}_{clean_title}_{file_index:02d}{ext}"
        else:
            res = clean_orig

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
