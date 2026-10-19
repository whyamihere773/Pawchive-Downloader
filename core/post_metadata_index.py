"""
Scalable Metadata & Content Indexer for Gallery and Search.
Handles high-performance parsing, caching, tag extraction, and keyword search
across post_info.txt, metadata files, and KnownManager character hierarchies.
"""

import os
import re
import threading
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Set, Tuple

from core.logger import logger
from core.path_utils import is_post_info_name, post_info_files, info_dirs_for, POST_INFO_NAME


_SPLIT_PATTERN = re.compile(r"(?:\r?\n)?={30,}(?:\r?\n)?")
_WORD_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]{2,}")


class PostMetaRecord:
    """Represents the parsed content and tags of a single post."""
    __slots__ = (
        "post_id", "title", "creator", "service", "tags",
        "content", "attached_files", "known_tags", "all_tags",
        "search_tokens", "search_blob", "_enriched"
    )

    def __init__(
        self,
        post_id: str = "",
        title: str = "",
        creator: str = "",
        service: str = "",
        tags: Optional[List[str]] = None,
        content: str = "",
        attached_files: Optional[Set[str]] = None,
    ):
        self.post_id = post_id.strip()
        self.title = title.strip()
        self.creator = creator.strip()
        self.service = service.strip()
        self.tags = [t.strip() for t in (tags or []) if t and t.strip()]
        self.content = content.strip()
        self.attached_files = {f.strip().lower() for f in (attached_files or set()) if f and f.strip()}
        self.known_tags: List[str] = []
        self.all_tags: List[str] = list(self.tags)
        self._enriched = False

        # Build search tokens and search blob for fast keyword checking
        parts = [self.title, self.creator, self.service]
        parts.extend(self.tags)
        if self.content:
            # Index up to 4000 chars of body content/caption
            parts.append(self.content[:4000])

        full_text = " ".join(p for p in parts if p).lower()
        self.search_blob = full_text
        self.search_tokens = set(_WORD_TOKEN_RE.findall(full_text))

    def enrich_known_tags(self, km) -> List[str]:
        """Runs KnownManager over title and content to discover character / series tags."""
        if not km or self._enriched:
            return self.known_tags

        self._enriched = True
        found_tags: List[str] = []
        seen = {t.lower() for t in self.all_tags}

        # 1. Match from title
        if self.title:
            try:
                hit = km.find_matching_hierarchy(self.title)
                if hit:
                    fr, ch = hit
                    for n in (ch, fr):
                        if n and n.lower() != "general" and n.lower() not in seen:
                            found_tags.append(n)
                            seen.add(n.lower())
            except Exception:
                pass

        # 2. Match from content/caption (first 600 chars)
        if self.content:
            try:
                hit = km.find_matching_hierarchy(self.content[:600])
                if hit:
                    fr, ch = hit
                    for n in (ch, fr):
                        if n and n.lower() != "general" and n.lower() not in seen:
                            found_tags.append(n)
                            seen.add(n.lower())
            except Exception:
                pass

        self.known_tags = found_tags
        # Prepend known tags so character tags appear first in tag list
        self.all_tags = found_tags + self.all_tags
        for kt in found_tags:
            self.search_tokens.add(kt.lower())
            for tok in _WORD_TOKEN_RE.findall(kt.lower()):
                self.search_tokens.add(tok)

        return self.known_tags

    def matches_query(self, words: List[str], tag_filters: List[str]) -> bool:
        """Evaluates whether this post matches the specified search words and tag filters."""
        # Check required tags
        if tag_filters:
            tag_set = {t.lower() for t in self.all_tags}
            for tf in tag_filters:
                tfl = tf.lower()
                if not any(tfl in t for t in tag_set):
                    return False

        # Check search words
        if words:
            for w in words:
                wl = w.lower()
                # Fast token hit or substring in search blob
                if wl not in self.search_tokens and wl not in self.search_blob:
                    return False

        return True


def parse_post_info_content(content: str) -> List[PostMetaRecord]:
    """Parse single or multi-post content blocks from post_info.txt."""
    if not content or not content.strip():
        return []

    blocks = _SPLIT_PATTERN.split(content)
    records: List[PostMetaRecord] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        meta: Dict[str, str] = {}
        lines = block.splitlines()
        content_lines: List[str] = []
        attached_files: Set[str] = set()

        in_content = False
        in_files = False
        in_header = True

        for line in lines:
            trimmed = line.strip()
            if trimmed.startswith("--- "):
                in_header = False
                in_content = (trimmed == "--- Content ---")
                in_files = (trimmed == "--- Attached Files ---")
                continue

            if in_header:
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
            elif in_content:
                content_lines.append(line)
            elif in_files and trimmed:
                attached_files.add(trimmed)

        # Extract parsed fields
        post_id = meta.get("post id", "")
        title = meta.get("title", "")
        creator = meta.get("creator", "")
        service = ""
        if "[" in creator and creator.endswith("]"):
            service_idx = creator.rfind("[")
            service = creator[service_idx + 1:-1].strip()
            creator = creator[:service_idx].strip()

        raw_tags_str = meta.get("tags", "")
        tags = [t.strip() for t in raw_tags_str.split(",") if t.strip()] if raw_tags_str else []
        content_text = "\n".join(content_lines).strip()

        if title or post_id or tags or content_text or attached_files:
            records.append(PostMetaRecord(
                post_id=post_id,
                title=title,
                creator=creator,
                service=service,
                tags=tags,
                content=content_text,
                attached_files=attached_files,
            ))

    return records


class PostMetadataCache:
    """
    High-performance, bounded, thread-safe cache for post metadata.
    Avoids redundant file I/O across large galleries with 100,000+ files.
    """
    def __init__(self, max_files: int = 25000):
        self._max_files = max_files
        self._lock = threading.Lock()
        # path -> (mtime, size, List[PostMetaRecord])
        self._file_cache: OrderedDict[str, Tuple[float, int, List[PostMetaRecord]]] = OrderedDict()
        # folder -> (mtime, List[str] post_info_paths)
        self._folder_index: OrderedDict[str, Tuple[float, List[str]]] = OrderedDict()

    def get_records_for_file_path(self, info_path: str) -> List[PostMetaRecord]:
        """Retrieves or parses post metadata from a specific post_info file."""
        norm_path = os.path.normcase(os.path.normpath(info_path))
        try:
            st = os.stat(info_path)
            mtime, size = st.st_mtime, st.st_size
        except OSError:
            return []

        with self._lock:
            cached = self._file_cache.get(norm_path)
            if cached and cached[0] == mtime and cached[1] == size:
                self._file_cache.move_to_end(norm_path)
                return cached[2]

        try:
            with open(info_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            records = parse_post_info_content(content)
        except Exception as ex:
            logger.debug(f"Could not read metadata {info_path}: {ex}", category="file")
            records = []

        with self._lock:
            self._file_cache[norm_path] = (mtime, size, records)
            if len(self._file_cache) > self._max_files:
                self._file_cache.popitem(last=False)

        return records

    def get_folder_records(self, folder_path: str) -> List[PostMetaRecord]:
        """Retrieves all post metadata records associated with the given folder."""
        if not folder_path or not os.path.isdir(folder_path):
            return []

        norm_folder = os.path.normcase(os.path.normpath(folder_path))
        try:
            folder_mtime = os.path.getmtime(folder_path)
        except OSError:
            folder_mtime = 0.0

        with self._lock:
            cached_folder = self._folder_index.get(norm_folder)
            if cached_folder and cached_folder[0] == folder_mtime:
                info_files = cached_folder[1]
            else:
                info_files = None

        if info_files is None:
            # Find post_info files in folder and candidate type folders
            info_files = []
            for d in info_dirs_for(folder_path):
                if os.path.isdir(d):
                    found = post_info_files(d, limit=20)
                    if found:
                        info_files.extend(found)

            with self._lock:
                self._folder_index[norm_folder] = (folder_mtime, info_files)
                if len(self._folder_index) > self._max_files:
                    self._folder_index.popitem(last=False)

        all_records: List[PostMetaRecord] = []
        for ip in info_files:
            all_records.extend(self.get_records_for_file_path(ip))

        return all_records

    def get_record_for_file(self, file_path: str) -> Optional[PostMetaRecord]:
        """Finds the specific post metadata record corresponding to a media file."""
        folder = os.path.dirname(file_path)
        records = self.get_folder_records(folder)
        if not records:
            return None

        file_name = os.path.basename(file_path).lower()
        # 1. Match by attached file list
        for r in records:
            if file_name in r.attached_files:
                return r

        # 2. Match by post_id prefix in file name (e.g. 12345_image.png)
        match = re.match(r"^(\d{5,})_", file_name)
        if match:
            pid = match.group(1)
            for r in records:
                if r.post_id == pid:
                    return r

        # 3. If folder only contains one record, it belongs to this post
        if len(records) == 1:
            return records[0]

        return records[0] if records else None

    def search_folder_records(
        self,
        folder_path: str,
        words: List[str],
        tag_filters: List[str]
    ) -> Tuple[bool, Set[str]]:
        """
        Fast search evaluation for an entire folder.
        Returns:
            all_match: True if all media in the folder matches the query.
            matching_files: Specific lowercase attached file names that matched.
        """
        records = self.get_folder_records(folder_path)
        if not records:
            return False, set()

        matching_attached: Set[str] = set()
        matched_any = False

        for r in records:
            if r.matches_query(words, tag_filters):
                matched_any = True
                if r.attached_files:
                    matching_attached.update(r.attached_files)

        # If a single-record folder matched or all records matched, everything in folder matches
        if matched_any and (len(records) == 1 or not matching_attached):
            return True, matching_attached

        return False, matching_attached

    def extract_tags_for_file(
        self,
        file_path: str,
        title: str = "",
        km = None,
        legacy_tags: Optional[List[str]] = None
    ) -> List[str]:
        """
        Combines legacy KnownManager character/series tags with post metadata tags and
        content-scanned keywords, deduplicating cleanly.
        """
        result = list(legacy_tags or [])
        seen = {t.lower() for t in result}

        record = self.get_record_for_file(file_path)
        if record:
            if km is not None:
                record.enrich_known_tags(km)
            for t in record.all_tags:
                if t.lower() not in seen:
                    result.append(t)
                    seen.add(t.lower())

        return result

    def clear(self):
        """Clears all caches."""
        with self._lock:
            self._file_cache.clear()
            self._folder_index.clear()


# Global singleton instance for gallery and search
GLOBAL_POST_META_INDEX = PostMetadataCache()
