"""
Core Downloader & Task Execution Engine
Coordinates concurrent chunk streaming, SHA-256 validation, adaptive backoff,
multipart acceleration, WebP conversion, retry queues, and telemetry reporting.
"""

import os
import sys
import re
import time
import datetime
import hashlib
import threading
import requests
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable
from PIL import Image

# Ensure project root is on sys.path even when executed directly
if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger
from core.filter_engine import FilterEngine, FilterOptions, MediaTypes
from core.known_manager import KnownManager
from core.session_manager import SessionManager
from services.multipart_downloader import download_multipart_file
from services.link_extractor import LinkExtractor
from services.ytdlp_manager import YtDlpManager


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
        is_ytdlp: bool = False
    ):
        self.url = url
        self.target_path = target_path
        self.post_title = post_title
        self.creator_name = creator_name
        self.service = service
        self.post_id = post_id
        self.file_id = file_id
        self.file_size = file_size
        self.expected_sha256 = expected_sha256
        self.is_ytdlp = is_ytdlp
        self.downloaded_bytes = 0
        self.status = "pending"  # "pending", "downloading", "completed", "failed", "cancelled"
        self.error_msg = ""
        self.retry_count = 0
        self.speed_bps = 0
        self.speed_str = "0 KB/s"
        self.eta_str = "--"
        self.progress_pct = 0
        self.fallback_urls: List[str] = []

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
            "is_ytdlp": self.is_ytdlp
        }

class KemonoDownloader:
    """
    Multi-threaded, resumable download engine with progress telemetry,
    smart 429 rate limit backoff, adaptive thread throttling, and yt-dlp embedded media support.
    """

    def __init__(
        self,
        known_manager: KnownManager,
        session_manager: SessionManager,
        max_workers: int = 4
    ):
        self.known_manager = known_manager
        self.session_manager = session_manager
        self.max_workers = max_workers
        self.ytdlp_manager = YtDlpManager()

        self.tasks: List[DownloadTask] = []
        self._lock = threading.Lock()
        self._rate_limit_lock = threading.Lock()
        self._rate_limit_cooldown_until = 0.0
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._is_running = False

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

    @property
    def is_running(self) -> bool:
        return self._is_running

    def cancel(self):
        self._cancel_event.set()
        self._pause_event.clear()  # Ensure paused workers wake up to handle cancel
        logger.warning("Download cancellation requested.", category="downloader")

    def pause(self):
        self._pause_event.set()
        logger.info("Download paused.", category="downloader")

    def resume(self):
        self._pause_event.clear()
        logger.info("Download resumed.", category="downloader")

    def build_tasks_from_posts(
        self,
        posts: List[Dict[str, Any]],
        creator_name: str,
        service: str,
        domain: str,
        base_dir: str,
        options: FilterOptions
    ) -> List[DownloadTask]:
        """
        Filters posts and attachments, building the list of download tasks with structured paths.
        """
        new_tasks = []
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

        # Smart character auto-discovery from posts
        new_chars = self.known_manager.add_candidates_from_posts(posts_to_process)
        if new_chars:
            logger.info(
                f"✨ Auto-learned {len(new_chars)} character(s) into Known list: {', '.join(new_chars[:6])}{'...' if len(new_chars) > 6 else ''}",
                category="known"
            )

        logger.info(f"Structuring download plan for {len(posts_to_process)} posts...", category="downloader")

        extracted_links_all: Dict[str, List[str]] = {}
        extracted_records_all: List[Dict[str, Any]] = []

        for post_idx, post in enumerate(posts_to_process, 1):
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

            # ── Link extraction in "Only Links" mode ───────────────────────────
            if options.file_type == MediaTypes.LINKS:
                # Build the fullest possible text corpus from this post
                content_html = (
                    post.get("content") or
                    post.get("captionHtml") or
                    post.get("caption") or ""
                )
                # Strip HTML tags for cleaner URL regex matching
                content_plain = re.sub(r'<[^>]+>', ' ', content_html)
                comments_text = post.get("comments_text") or ""
                full_text = f"{post_title}\n{content_plain}\n{comments_text}"

                found_links = LinkExtractor.extract_links_from_text(full_text)
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
                                "creator": creator_name
                            })
                        extracted_links_all.setdefault(platform, []).extend(urls)
                else:
                    logger.debug(
                        f"No external links found in post: '{post_title}'",
                        category="downloader"
                    )
                # Skip all media downloads for this post
                continue

            # Apply post filter
            keep_post, reason = FilterEngine.should_keep_post(post, options)
            if not keep_post:
                logger.debug(f"Skipped post [{post_id}] '{post_title}': {reason}", category="filter")
                continue

            # Determine parent directory for this post
            folder_parts = [base_dir]

            # Separate by Known.txt if requested (Franchise -> Character hierarchy)
            if options.separate_by_known:
                matched_hierarchy = self.known_manager.find_matching_hierarchy(
                    post_title, tags=post.get("tags")
                )
                if matched_hierarchy:
                    franchise, char_name = matched_hierarchy
                    if franchise and franchise.strip() and franchise != "Other":
                        clean_fr = FilterEngine.clean_filesystem_text(franchise, max_len=60, fallback="Franchise")
                        folder_parts.append(clean_fr)
                    if char_name and char_name.strip() and char_name.lower() != (franchise or "").lower():
                        clean_ch = FilterEngine.clean_filesystem_text(char_name, max_len=60, fallback="Character")
                        folder_parts.append(clean_ch)
                else:
                    folder_parts.append("Other")

            # Creator folder
            folder_parts.append(f"{creator_clean} [{service}]")

            # Post subfolder
            if options.subfolder_per_post:
                clean_title = FilterEngine.clean_filesystem_text(post_title, max_len=100, fallback="Untitled")
                if options.date_prefix and date_str:
                    folder_name = f"[{date_str}] {clean_title}"
                else:
                    folder_name = clean_title
                folder_parts.append(folder_name)

            post_folder = os.path.join(*folder_parts)

            # Save post info / description archiver
            if options.save_post_metadata:
                try:
                    os.makedirs(post_folder, exist_ok=True)
                    info_path = os.path.join(post_folder, "post_info.txt")
                    if not os.path.exists(info_path):
                        caption_text = post.get("content") or post.get("captionHtml") or post.get("caption") or ""
                        caption_clean = re.sub(r'<br\s*/?>', '\n', caption_text, flags=re.IGNORECASE)
                        caption_clean = re.sub(r'<[^>]+>', '', caption_clean).strip()
                        tags_list = post.get("tags") or []
                        tags_str = ", ".join(tags_list) if isinstance(tags_list, list) else str(tags_list)
                        
                        info_content = f"Title: {post_title}\n"
                        info_content += f"Post ID: {post_id}\n"
                        info_content += f"Creator: {creator_name} [{service}]\n"
                        info_content += f"Published: {date_str}\n"
                        if tags_str:
                            info_content += f"Tags: {tags_str}\n"
                        info_content += f"\n--- Content ---\n{caption_clean}\n"
                        
                        if post.get("comments_text"):
                            info_content += f"\n--- Comments ---\n{post.get('comments_text')}\n"
                        
                        with open(info_path, "w", encoding="utf-8") as inf_f:
                            inf_f.write(info_content)
                except Exception as ex:
                    logger.debug(f"Could not save post_info.txt for {post_id}: {ex}", category="file")

            # Collect files: post.file and post.attachments
            files_to_process = []
            main_file = post.get("file")
            if main_file and isinstance(main_file, dict) and (main_file.get("path") or main_file.get("storageKey")):
                files_to_process.append(main_file)

            attachments = post.get("attachments", [])
            if isinstance(attachments, list):
                for att in attachments:
                    if isinstance(att, dict) and (att.get("path") or att.get("storageKey")):
                        files_to_process.append(att)

            # Scan inline content images if enabled
            if options.scan_content_images:
                content_html = post.get("content", "") or post.get("captionHtml", "") or ""
                content_imgs = FilterEngine.extract_content_images(content_html)
                for ci in content_imgs:
                    files_to_process.append({"name": os.path.basename(ci), "path": ci})

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

                # Format filename based on selected naming style
                sanitized_name = FilterEngine.format_custom_filename(
                    original_filename=raw_name,
                    post_title=post_title,
                    post_date=date_str,
                    post_index=post_idx,
                    file_index=file_idx,
                    options=options
                )
                # Strip trailing punctuation/commas that would corrupt the ?f= CDN query parameter
                # and trigger ERR_RESPONSE_HEADERS_MULTIPLE_CONTENT_DISPOSITION in browsers.
                sanitized_name = sanitized_name.rstrip(".,;!? \t")

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

                # Auto-detect provider from original URL host if present (overrides domain arg)
                effective_domain = domain
                if original_url:
                    orig_host = original_url.split("://")[-1].split("/")[0].lower()
                    if "cum.st" in orig_host:
                        effective_domain = "cum.st"
                    elif "pawchive" in orig_host:
                        effective_domain = "pawchive.pw"
                    elif "coomer" in orig_host:
                        effective_domain = "coomer.su"
                    elif "kemono" in orig_host:
                        effective_domain = "kemono.su"

                candidate_urls = []
                # Always try the original source URL first if we have one
                if original_url:
                    candidate_urls.append(f"{original_url}?f={sanitized_name}")

                if "cum.st" in effective_domain:
                    if options.download_thumbnails_only:
                        if not original_url:
                            candidate_urls.append(f"https://img.cum.st/thumbnail/data{clean_rel}")
                    else:
                        # Append any secondary variants (e.g. 720p.mp4, 240p.mp4) from the API as immediate fallbacks
                        if is_storage_key:
                            for ev in extra_cum_variants:
                                u_ev = f"https://e1.cum.st/media/{rel_path}/{ev}"
                                if u_ev not in candidate_urls:
                                    candidate_urls.append(u_ev)
                        elif not original_url:
                            candidate_urls.append(f"https://cum.st/data{clean_rel}?f={sanitized_name}")
                        # Fallbacks
                        candidate_urls.append(f"https://cum.st/data{clean_rel}")
                        candidate_urls.append(f"https://img.cum.st/data{clean_rel}")
                elif "pawchive" in effective_domain:
                    if options.download_thumbnails_only:
                        if not original_url:
                            candidate_urls.append(f"https://img.pawchive.pw/thumbnail/data{clean_rel}")
                    else:
                        # Only use confirmed live Pawchive mirrors
                        if "file.pawchive.pw" not in (original_url or ""):
                            candidate_urls.append(f"https://file.pawchive.pw/data{clean_rel}?f={sanitized_name}")
                elif "coomer" in effective_domain:
                    if options.download_thumbnails_only:
                        if not original_url:
                            candidate_urls.append(f"https://img.coomer.su/thumbnail/data{clean_rel}")
                    else:
                        for sub in ["c1", "c2", "c3", "n1", "n2", "n3", "n4"]:
                            u = f"https://{sub}.coomer.su/data{clean_rel}?f={sanitized_name}"
                            if u not in candidate_urls:
                                candidate_urls.append(u)
                else:  # kemono.su / default
                    if options.download_thumbnails_only:
                        if not original_url:
                            candidate_urls.append(f"https://img.kemono.su/thumbnail/data{clean_rel}")
                    else:
                        for sub in ["c1", "c2", "c3", "n1", "n2", "n3", "n4"]:
                            u = f"https://{sub}.kemono.su/data{clean_rel}?f={sanitized_name}"
                            if u not in candidate_urls:
                                candidate_urls.append(u)
                        candidate_urls.append(f"https://file.pawchive.pw/data{clean_rel}?f={sanitized_name}")

                file_url = candidate_urls[0] if candidate_urls else f"https://file.pawchive.pw/data{clean_rel}?f={sanitized_name}"
                target_path = os.path.join(post_folder, sanitized_name)
                file_id = f"{post_id}_{clean_rel}"

                webp_path = os.path.splitext(target_path)[0] + ".webp"
                raw_path = os.path.join(post_folder, raw_name)
                raw_webp = os.path.splitext(raw_path)[0] + ".webp"

                # Skip if already exists on disk at target_path, webp path, or raw name path
                if not options.keep_duplicates:
                    if (os.path.exists(target_path) and os.path.getsize(target_path) > 0) or \
                       (os.path.exists(webp_path) and os.path.getsize(webp_path) > 0) or \
                       (os.path.exists(raw_path) and os.path.getsize(raw_path) > 0) or \
                       (os.path.exists(raw_webp) and os.path.getsize(raw_webp) > 0):
                        logger.info(f"⏳ Skipping existing file: '{sanitized_name}' (already present on disk)", category="file")
                        continue

                expected_sha = str(fobj.get("sha256") or fobj.get("hash") or "")

                task = DownloadTask(
                    url=file_url,
                    target_path=target_path,
                    post_title=post_title,
                    creator_name=creator_name,
                    service=service,
                    post_id=post_id,
                    file_id=file_id,
                    file_size=int(file_bytes or 0),  # pre-populate from API metadata for progress
                    expected_sha256=expected_sha
                )
                task.fallback_urls = candidate_urls[1:]
                new_tasks.append(task)

            # ── 3. Scan Embedded Media Players (yt-dlp: Vimeo, YouTube, Streamable, RedGifs, etc.)
            if options.download_embeds and options.file_type in (MediaTypes.ALL, MediaTypes.VIDEOS, MediaTypes.AUDIO):
                embed_urls = LinkExtractor.extract_embed_urls(post)
                for embed_idx, e_url in enumerate(embed_urls, 1):
                    e_host = re.sub(r'[^a-zA-Z0-9]', '', e_url.split("://")[-1].split("/")[0])
                    e_name = f"embed_{embed_idx}_{e_host}.mp4"
                    e_target_path = os.path.join(post_folder, e_name)
                    e_file_id = f"embed_{post_id}_{embed_idx}"

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
                        is_ytdlp=True
                    )
                    new_tasks.append(e_task)

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
        if self._is_running:
            logger.warning("Downloader is already active.", category="downloader")
            return

        self.tasks = tasks
        self._cancel_event.clear()
        self._pause_event.clear()
        self._is_running = True

        threading.Thread(
            target=self._run_download_loop,
            args=(options, cookie_str),
            daemon=True
        ).start()

    def _trigger_rate_limit_backoff(self):
        with self._rate_limit_lock:
            now = time.time()
            if now >= self._rate_limit_cooldown_until:
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

    def retry_failed_tasks(self, options: FilterOptions, cookie_str: str) -> int:
        """Resets all tasks with status 'failed' to 'pending' and resumes downloading."""
        failed_tasks = [t for t in self.tasks if t.status == "failed"]
        if not failed_tasks:
            logger.info("No failed tasks to retry.", category="downloader")
            return 0

        for t in failed_tasks:
            t.status = "pending"
            t.error_msg = ""
            t.progress_pct = 0
            if self.on_task_status_changed:
                self.on_task_status_changed(t)

        logger.info(f"Flagged {len(failed_tasks)} failed tasks for retry.", category="downloader")

        if not self._is_running:
            self.start_download_queue(self.tasks, options, cookie_str)

        return len(failed_tasks)

    def retry_selected_tasks(self, selected_ids: List[str], options: FilterOptions, cookie_str: str) -> int:
        """Resets only user-selected failed tasks to 'pending' and resumes downloading."""
        if not selected_ids:
            logger.info("No tasks selected for retry.", category="downloader")
            return 0

        target_tasks = []
        for t in self.tasks:
            if t.status == "failed" and (t.file_id in selected_ids or t.url in selected_ids or t.filename in selected_ids):
                target_tasks.append(t)

        if not target_tasks:
            logger.info("No matching failed tasks found to retry.", category="downloader")
            return 0

        for t in target_tasks:
            t.status = "pending"
            t.error_msg = ""
            t.progress_pct = 0
            if self.on_task_status_changed:
                self.on_task_status_changed(t)

        logger.info(f"Flagged {len(target_tasks)} selected tasks for retry.", category="downloader")

        if not self._is_running:
            self.start_download_queue(self.tasks, options, cookie_str)

        return len(target_tasks)

    def _run_download_loop(self, options: FilterOptions, cookie_str: str):
        self.start_time = time.time()
        self.downloaded_bytes = 0
        self._speed_samples.clear()
        self._smoothed_speed = 0.0
        self._medium_speed = 0.0
        self._smoothed_eta = None
        self._last_eta_calc_time = 0.0
        self._last_progress_emit_time = 0.0
        cpu_cores = max(4, os.cpu_count() or 16)
        target_max_workers = cpu_cores if options.adaptive_threading else max(1, self.max_workers)
        last_scale_time = time.time()
        consecutive_successes = 0
        scale_step_interval = 5.0 # Check scaling up every 5 seconds of healthy throughput

        # If Adaptive Threading is enabled, start with 2 worker threads and scale up to CPU core count
        if options.adaptive_threading:
            self.max_workers = min(2, target_max_workers)
            logger.info(f"⚡ [Adaptive Threading] Active: Starting with {self.max_workers} worker threads (Max CPU limit: {target_max_workers} threads)...", category="adaptive")
            if self.on_concurrency_throttled:
                self.on_concurrency_throttled(self.max_workers)
        else:
            logger.info(f"Starting download pool with {self.max_workers} worker threads...", category="downloader")

        # Auto-normalize cookie if user pasted raw JWT token
        clean_cookie = cookie_str.strip() if cookie_str else ""
        if clean_cookie:
            if clean_cookie.startswith("eyJ") and "session=" not in clean_cookie:
                clean_cookie = f"session={clean_cookie}"
            elif "=" not in clean_cookie:
                clean_cookie = f"session={clean_cookie}"
            logger.debug(f"Applied authenticated session cookie ({len(clean_cookie)} chars)", category="downloader")

        session = requests.Session()
        # Configure high-concurrency connection adapter to prevent connection pool starvation across worker threads
        adapter = requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=1)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*"
        })
        if clean_cookie:
            session.headers["Cookie"] = clean_cookie

        active_futures = {}
        auto_retried_once = False

        with ThreadPoolExecutor(max_workers=max(32, target_max_workers)) as executor:
            while not self._cancel_event.is_set():
                now = time.time()

                # Effective ceiling: learned ceiling if we encountered 429, else user target
                effective_ceiling = self._learned_stable_ceiling if self._learned_stable_ceiling is not None else target_max_workers

                # 1. Check Adaptive Scaling timer (every 6 seconds)
                if options.adaptive_threading and (now - last_scale_time >= scale_step_interval):
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
                            task.status = "completed"
                            task.error_msg = ""
                            consecutive_successes += 1
                            self._stable_clean_count += 1
                            self.session_manager.record_downloaded_file(task.file_id)
                            if self.on_task_status_changed:
                                self.on_task_status_changed(task)

                            # Fast Adaptive Scaling: Scale up after 4 consecutive successful files if below ceiling
                            if options.adaptive_threading and consecutive_successes >= 4 and (now - last_scale_time >= 3.0):
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
                                # 429 Rate Limit encountered -> auto-retry after cooldown
                                task.status = "pending"
                                task.error_msg = "Rate limited (429) — cooling down for 15s before auto-retry"
                                if self.on_task_status_changed:
                                    self.on_task_status_changed(task)
                                self._trigger_rate_limit_backoff()
                                last_scale_time = time.time() + 15.0
                            else:
                                task.status = "failed"
                                task.error_msg = msg
                                if self.on_task_status_changed:
                                    self.on_task_status_changed(task)
                    except Exception as e:
                        consecutive_successes = 0
                        task.status = "failed"
                        task.error_msg = str(e)
                        logger.error(f"Error downloading {task.filename}: {e}", category="downloader")
                        if self.on_task_status_changed:
                            self.on_task_status_changed(task)

                # Emit progress
                completed_count = sum(1 for t in self.tasks if t.status == "completed")
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
                    pending_tasks = [t for t in self.tasks if t.status == "pending"]
                    if not pending_tasks and current_active == 0:
                        # Check if "auto retry at the end" is enabled
                        if options.auto_retry_at_end and not auto_retried_once:
                            failed_tasks = [t for t in self.tasks if t.status == "failed"]
                            if failed_tasks:
                                auto_retried_once = True
                                logger.info(f"🔄 Auto-retry at the end triggered for {len(failed_tasks)} failed files...", category="downloader")
                                for t in failed_tasks:
                                    t.status = "pending"
                                    t.error_msg = ""
                                    if self.on_task_status_changed:
                                        self.on_task_status_changed(t)
                                continue

                        # All tasks completed or finished
                        break

                    for i, task in enumerate(pending_tasks[:slots_available]):
                        if self._cancel_event.is_set():
                            break
                        # Feature 4: Jittered Inter-Request Staggering (Anti-Burst Smoothing)
                        if i > 0 and not self._cancel_event.is_set():
                            time.sleep(0.06) # 60ms micro-stagger between concurrent request launches

                        if self._cancel_event.is_set():
                            break

                        task.status = "downloading"
                        if self.on_task_status_changed:
                            self.on_task_status_changed(task)
                        try:
                            fut = executor.submit(self._download_single_file, task, session, options)
                            active_futures[fut] = task
                        except RuntimeError:
                            # Executor was shut down (e.g. cancelled)
                            task.status = "pending"
                            break

                # Feature 5: Track Adaptive Health State
                if options.adaptive_threading:
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

                time.sleep(0.05)

            # Wait for remaining active futures if cancelling
            for f in list(active_futures.keys()):
                try:
                    f.result(timeout=1.0)
                except Exception:
                    pass

        self._is_running = False
        duration = time.time() - self.start_time
        completed_count = sum(1 for t in self.tasks if t.status == "completed")
        failed_count = sum(1 for t in self.tasks if t.status == "failed")

        if self._cancel_event.is_set():
            logger.warning(f"Download cancelled. Completed: {completed_count}, Failed/Cancelled: {failed_count}", category="downloader")
            if self.on_download_finished:
                self.on_download_finished(False, "Download cancelled by user.")
        else:
            logger.success(
                f"Download completed in {duration:.1f}s! ({completed_count} successful, {failed_count} errors)",
                category="downloader"
            )
            if self.on_download_finished:
                self.on_download_finished(True, f"Completed: {completed_count} downloaded, {failed_count} failed.")

    def _download_single_file(self, task: DownloadTask, session: requests.Session, options: FilterOptions) -> (bool, str):
        if self._cancel_event.is_set():
            return False, "Cancelled"

        while self._pause_event.is_set():
            time.sleep(0.5)
            if self._cancel_event.is_set():
                return False, "Cancelled"

        os.makedirs(os.path.dirname(task.target_path), exist_ok=True)
        task.status = "downloading"
        if self.on_task_status_changed:
            self.on_task_status_changed(task)

        # Check if file already exists completely on disk (including webp converted version)
        webp_path = os.path.splitext(task.target_path)[0] + ".webp"
        found_existing_path = None
        if not options.keep_duplicates:
            if os.path.exists(task.target_path) and os.path.getsize(task.target_path) > 0:
                found_existing_path = task.target_path
            elif os.path.exists(webp_path) and os.path.getsize(webp_path) > 0:
                found_existing_path = webp_path

        if found_existing_path:
            task.status = "completed"
            task.downloaded_bytes = os.path.getsize(found_existing_path)
            task.file_size = task.downloaded_bytes
            task.progress_pct = 100
            task.eta_str = "Done"
            if self.on_task_status_changed:
                self.on_task_status_changed(task)
            logger.info(f"⏳ Skipping existing file: '{task.filename}' (already present on disk)", category="file")
            return True, "Already downloaded"

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
                progress_callback=_ytdlp_prog
            )
            if ok:
                task.status = "completed"
                task.progress_pct = 100
                task.eta_str = "Done"
                if self.on_task_status_changed:
                    self.on_task_status_changed(task)
                logger.success(f"✔ [yt-dlp] {task.filename} successfully downloaded", category="ytdlp")
                return True, "Completed"
            else:
                logger.warning(f"✖ [yt-dlp] {task.filename}: {msg}", category="ytdlp")
                return False, msg

        # Check existing file for resume capability
        existing_size = 0
        mode = "wb"
        range_headers = {}
        if os.path.exists(task.target_path):
            existing_size = os.path.getsize(task.target_path)
            if existing_size > 0:
                range_headers["Range"] = f"bytes={existing_size}-"
                mode = "ab"
                logger.debug(
                    f"  ↪ Resume: {task.filename}  already have {existing_size // 1024}KB",
                    category="file"
                )

        urls_to_try = [task.url] + list(task.fallback_urls)
        resp = None

        try:
            for pass_idx in range(2): # Up to 2 passes across available CDN mirrors
                if pass_idx > 0:
                    time.sleep(1.5) # Brief jittered pause before second pass if all mirrors were busy

                for attempt_url in urls_to_try:
                    if self._cancel_event.is_set():
                        return False, "Cancelled"

                    # Provider-specific headers per host
                    req_headers = dict(range_headers)
                    u_low = attempt_url.lower()
                    if "bunkr" in u_low:
                        req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        req_headers["Referer"] = "https://bunkr.is/"
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
                        req_headers["Referer"] = "https://coomer.su/"
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
                        req_headers["Referer"] = "https://kemono.su/"
                        req_headers["Accept"] = "*/*"

                    try:
                        resp = session.get(attempt_url, stream=True, timeout=30, headers=req_headers)
                        if resp.status_code in (200, 206, 416):
                            task.url = attempt_url
                            break
                        elif resp.status_code == 403:
                            # If we sent a Range header, the CDN might be rejecting range requests with 403.
                            # Retry from byte 0 without Range and without cookies.
                            if "Range" in req_headers:
                                no_range_headers = {k: v for k, v in req_headers.items() if k.lower() != "range"}
                                try:
                                    fresh_resp = session.get(attempt_url, stream=True, timeout=30, headers=no_range_headers)
                                    if fresh_resp.status_code in (200, 206):
                                        resp = fresh_resp
                                        task.url = attempt_url
                                        mode = "wb"
                                        existing_size = 0
                                        break
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
                                clean_resp = requests.get(attempt_url, stream=True, timeout=30, headers=browser_headers)
                                if clean_resp.status_code in (200, 206):
                                    resp = clean_resp
                                    task.url = attempt_url
                                    mode = "wb"
                                    existing_size = 0
                                    break
                                elif clean_resp.status_code == 403 and len(urls_to_try) == 1:
                                    # Single-mirror CDN (like file.pawchive.pw) transient burst 403 — progressive pause & retry
                                    for delay in (1.5, 3.0):
                                        time.sleep(delay)
                                        if self._cancel_event.is_set():
                                            break
                                        retry_resp = requests.get(attempt_url, stream=True, timeout=30, headers=browser_headers)
                                        if retry_resp.status_code in (200, 206):
                                            resp = retry_resp
                                            task.url = attempt_url
                                            mode = "wb"
                                            existing_size = 0
                                            break
                                    if resp and resp.status_code in (200, 206):
                                        break
                            except Exception:
                                pass

                            # Still 403 — rotate to next mirror
                            logger.debug(f"  ↪ Mirror 403 on {attempt_url} — trying next mirror...", category="file")
                            continue
                        elif resp.status_code == 429:
                            # 429 on this mirror — smoothly rotate to next available mirror
                            logger.debug(f"  ↪ Mirror 429 on {attempt_url} — rotating to next mirror...", category="file")
                            continue
                        elif resp.status_code == 404 and len(urls_to_try) > 1:
                            logger.debug(f"  ↪ Mirror 404 on {attempt_url} — trying next mirror...", category="file")
                            continue
                    except Exception as ex:
                        logger.debug(f"  ↪ Mirror connect error on {attempt_url}: {ex}", category="file")
                        continue

                if resp and resp.status_code in (200, 206, 416):
                    break

            if resp is None:
                return False, "Failed to connect to any file server"

            status = resp.status_code

            # ── Handle error responses with helpful hints ─────────────────────
            if status == 416:
                # Already fully downloaded
                task.status = "completed"
                task.downloaded_bytes = existing_size
                task.file_size = existing_size
                logger.info(f"⏳ Skipping existing file: '{task.filename}' (already complete on disk)", category="file")
                return True, "Already downloaded"

            if status == 403:
                msg = "403 Forbidden — content locked (membership tier access required)"
                logger.error(f"  ✖ {task.filename}: {msg}", category="file")
                return False, msg

            if status == 404:
                msg = "404 Not Found — file does not exist on any server mirror"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file")
                return False, msg

            if status == 429:
                retry_after = resp.headers.get("Retry-After", "30")
                msg = f"429_RATE_LIMIT (Retry-After: {retry_after}s)"
                logger.warning(f"  ⚠ {task.filename}: HTTP 429 Too Many Requests (Rate limited)", category="file")
                return False, msg

            if status not in (200, 206):
                msg = f"HTTP {status}"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file")
                return False, msg

            # ── Determine file size and resume offset ─────────────────────────
            content_length = int(resp.headers.get("content-length", 0))
            api_size = task.file_size  # pre-populated from API metadata (fobj["bytes"])
            if status == 206:
                task.file_size = existing_size + content_length
                task.downloaded_bytes = existing_size
            else:
                # If CDN uses chunked transfer (no Content-Length), fall back to API-provided size
                task.file_size = content_length or api_size
                task.downloaded_bytes = 0
                mode = "wb"
                existing_size = 0

            size_str = f"{task.file_size / (1024*1024):.2f} MB" if task.file_size > 0 else "unknown size"
            logger.info(
                f"▶ {task.filename}  [{size_str}]  post: {task.post_title[:35]}",
                category="file"
            )

            # ── Fast-path: Multipart chunking for large files (>= 25 MB) ─────
            accept_ranges = resp.headers.get("Accept-Ranges", "").lower()
            if task.file_size >= 25 * 1024 * 1024 and existing_size == 0 and ("bytes" in accept_ranges or status == 206):
                resp.close()
                logger.info(f"  ⚡ Activating 4-part parallel chunked download for {task.filename} ({size_str})", category="file")

                # ── Disk-polling progress thread ──────────────────────────────
                # Instead of relying on in-memory chunk callbacks (which can be
                # unreliable through the multipart layer), we poll the actual
                # .partN temp files on disk every 0.5 s and update progress.
                _poll_stop = threading.Event()
                _part_paths = [f"{task.target_path}.part{i}" for i in range(4)]
                _prev_disk_bytes = [0]

                def _disk_poll():
                    while not _poll_stop.is_set():
                        try:
                            disk_bytes = sum(
                                os.path.getsize(p) for p in _part_paths if os.path.exists(p)
                            )
                            # Also count the target file itself if it already started assembling
                            if os.path.exists(task.target_path):
                                disk_bytes = max(disk_bytes, os.path.getsize(task.target_path))
                            if disk_bytes > 0:
                                delta = disk_bytes - _prev_disk_bytes[0]
                                if delta > 0:
                                    with self._lock:
                                        self.downloaded_bytes += delta
                                    _prev_disk_bytes[0] = disk_bytes
                                task.downloaded_bytes = disk_bytes
                                if task.file_size > 0:
                                    task.progress_pct = min(99, int(disk_bytes / task.file_size * 100))
                                if self.on_task_status_changed:
                                    self.on_task_status_changed(task)
                        except Exception:
                            pass
                        _poll_stop.wait(0.5)

                _poll_thread = threading.Thread(target=_disk_poll, daemon=True)
                _poll_thread.start()

                try:
                    mp_ok, mp_err = download_multipart_file(
                        url=task.url,
                        target_path=task.target_path,
                        headers=dict(session.headers),
                        num_chunks=4,
                        progress_callback=None,  # disk poller handles progress
                        cancel_event=self._cancel_event,
                        pause_event=self._pause_event,
                        timeout=30,
                        session=session
                    )
                finally:
                    _poll_stop.set()

                if mp_ok:
                    task.status = "completed"
                    task.downloaded_bytes = task.file_size
                    task.progress_pct = 100
                    if self.on_task_status_changed:
                        self.on_task_status_changed(task)
                    return True, "Completed"
                else:
                    if self._cancel_event.is_set():
                        return False, "Cancelled"
                    logger.debug(f"  ↪ Multipart fallback: {mp_err}", category="file")

            # ── Standard single stream download loop ──────────────────────────
            chunk_size = 64 * 1024  # 64 KB
            last_speed_time = time.time()
            last_log_time   = time.time()
            bytes_since_speed = 0

            with open(task.target_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if self._cancel_event.is_set():
                        try:
                            resp.close()
                        except Exception:
                            pass
                        return False, "Cancelled"
                    while self._pause_event.is_set():
                        time.sleep(0.3)
                        if self._cancel_event.is_set():
                            try:
                                resp.close()
                            except Exception:
                                pass
                            return False, "Cancelled"

                    if not chunk:
                        continue

                    f.write(chunk)
                    chunk_len = len(chunk)
                    task.downloaded_bytes += chunk_len
                    with self._lock:
                        self.downloaded_bytes += chunk_len

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

                    # Per-file progress log every ~1.5 s
                    delta_log = now - last_log_time
                    if delta_log >= 1.5 and task.file_size > 0:
                        pct    = task.progress_pct
                        dl_mb  = task.downloaded_bytes / (1024 * 1024)
                        tot_mb = task.file_size / (1024 * 1024)
                        spd    = task.speed_str
                        logger.debug(
                            f"  ↳ {task.filename[:45]:<45}  {pct:3d}%  "
                            f"{dl_mb:5.1f}/{tot_mb:.1f}MB  @ {spd} (ETA: {task.eta_str})",
                            category="file"
                        )
                        last_log_time = now

            # ── Post-download processing ───────────────────────────────────────
            if options.compress_to_webp:
                self._convert_to_webp(task.target_path)

            final_size = os.path.getsize(task.target_path)
            task.progress_pct = 100
            task.eta_str = "Done"

            # Verify SHA-256 hash if provided
            if task.expected_sha256 and os.path.exists(task.target_path):
                hasher = hashlib.sha256()
                try:
                    with open(task.target_path, "rb") as check_f:
                        while chunk := check_f.read(65536):
                            hasher.update(chunk)
                    computed_hash = hasher.hexdigest().lower()
                    if computed_hash == task.expected_sha256.lower():
                        logger.success(
                            f"✔ {task.filename}  ({final_size / (1024*1024):.2f} MB saved, SHA-256 verified)",
                            category="file"
                        )
                    else:
                        logger.warning(
                            f"⚠ {task.filename}: SHA-256 hash mismatch! (expected {task.expected_sha256[:8]}, got {computed_hash[:8]})",
                            category="file"
                        )
                except Exception as ex:
                    logger.debug(f"Hash calculation error for {task.filename}: {ex}", category="file")
            else:
                logger.success(
                    f"✔ {task.filename}  ({final_size / (1024*1024):.2f} MB saved)",
                    category="file"
                )

            # Thread cooldown delay to avoid CDN rate limiting (429)
            if options.download_delay > 0 and not self._cancel_event.is_set():
                time.sleep(options.download_delay)

            return True, "Success"

        except requests.exceptions.Timeout:
            msg = "Connection timed out"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file")
            return False, msg
        except requests.exceptions.ConnectionError as e:
            msg = f"Connection error: {e}"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file")
            return False, msg
        except OSError as e:
            msg = f"Disk/IO error: {e}"
            logger.error(f"  ✖ {task.filename}: {msg}", category="file")
            return False, msg
        except Exception as e:
            logger.error(f"  ✖ {task.filename}: {type(e).__name__}: {e}", category="file")
            return False, str(e)

    def _convert_to_webp(self, file_path: str):
        try:
            _, ext = os.path.splitext(file_path.lower())
            if ext in (".jpg", ".jpeg", ".png"):
                webp_path = os.path.splitext(file_path)[0] + ".webp"
                with Image.open(file_path) as img:
                    img.save(webp_path, "WEBP", quality=85)
                os.remove(file_path)
        except Exception as e:
            logger.debug(f"WebP compression skipped for {file_path}: {e}", category="downloader")

    def _calculate_instant_speed(self, now: float) -> int:
        """
        Calculates a robust, learning-averaged download throughput.
        Blends short-term window velocity, medium-term exponential moving average,
        and long-term cumulative session throughput to prevent erratic fluctuations.
        """
        with self._lock:
            current_bytes = self.downloaded_bytes

        self._speed_samples.append((now, current_bytes))

        # Keep samples within a ~8-10 second rolling window
        while len(self._speed_samples) > 2 and (now - self._speed_samples[0][0] > 10.0):
            self._speed_samples.popleft()

        # 1. Short-term window velocity
        window_speed = 0.0
        if len(self._speed_samples) >= 2:
            dt = now - self._speed_samples[0][0]
            db = current_bytes - self._speed_samples[0][1]
            if dt >= 0.4 and db >= 0:
                window_speed = db / dt

        # 2. Cumulative session average speed (the true historical ground truth)
        elapsed = max(0.5, now - self.start_time)
        session_avg_speed = current_bytes / elapsed

        # Initialize trackers if starting fresh
        if self._smoothed_speed <= 0:
            self._smoothed_speed = window_speed if window_speed > 0 else session_avg_speed
        if self._medium_speed <= 0:
            self._medium_speed = self._smoothed_speed

        # 3. Update Medium-term EMA (smooth trend tracker)
        if window_speed > 0:
            self._medium_speed = 0.12 * window_speed + 0.88 * self._medium_speed
        elif session_avg_speed > 0:
            self._medium_speed = 0.05 * session_avg_speed + 0.95 * self._medium_speed

        # 4. Learning blend: As session elapsed time increases, progressively anchor to
        # the proven session average so transient dips (e.g. 1.5 MB/s -> 500 KB/s for 10s)
        # do not cause erratic jumps.
        learn_weight = min(0.70, max(0.15, (elapsed - 5.0) / 75.0))
        effective_speed = (1.0 - learn_weight) * self._medium_speed + learn_weight * session_avg_speed
        self._smoothed_speed = 0.15 * effective_speed + 0.85 * self._smoothed_speed

        return max(0, int(self._smoothed_speed))

    def _calculate_smart_eta(self, completed: int, failed: int, total: int, speed: int, elapsed: float) -> str:
        """
        Calculates a learning, countdown-stable ETA using:
        1. Learned empirical file sizes from completed tasks.
        2. Dual-model blending (byte-throughput model + task-cadence model).
        3. Monotonic drift control (steady 1-second countdown with gentle regression).
        """
        remaining_tasks = total - completed - failed
        if total <= 0 or remaining_tasks <= 0:
            self._smoothed_eta = None
            return "Done"

        now = time.time()
        time_since_last_calc = (now - self._last_eta_calc_time) if self._last_eta_calc_time > 0 else 0.0
        self._last_eta_calc_time = now

        # ── 1. Learned File Size Estimation ──────────────────────────────────
        completed_tasks_bytes = [t.downloaded_bytes for t in self.tasks if t.status == "completed" and t.downloaded_bytes > 0]
        known_pending_bytes = [t.file_size for t in self.tasks if t.status in ("pending", "downloading") and t.file_size > 0]

        if completed_tasks_bytes:
            learned_avg_file_size = sum(completed_tasks_bytes) / len(completed_tasks_bytes)
        elif known_pending_bytes:
            learned_avg_file_size = sum(known_pending_bytes) / len(known_pending_bytes)
        else:
            learned_avg_file_size = 4.5 * 1024 * 1024  # 4.5 MB realistic artwork fallback

        # Calculate estimated remaining bytes
        total_remaining_bytes = 0.0
        for t in self.tasks:
            if t.status in ("pending", "downloading"):
                task_size = t.file_size if t.file_size > 0 else learned_avg_file_size
                rem = max(0.0, float(task_size - t.downloaded_bytes))
                total_remaining_bytes += rem

        # ── 2. Dual-Model Target ETA Derivation ──────────────────────────────
        target_candidates = []

        # Model A: Byte-Throughput ETA
        if speed > 512 and total_remaining_bytes > 0:
            target_candidates.append(total_remaining_bytes / speed)

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

        # ── 3. Monotonic Countdown & Anti-Fluctuation Damping ────────────────
        if self._smoothed_eta is None:
            self._smoothed_eta = target_eta_seconds
        else:
            # First, tick down naturally by the elapsed real time
            if 0 < time_since_last_calc < 3.0:
                self._smoothed_eta = max(1.0, self._smoothed_eta - time_since_last_calc)

            # Then gently nudge towards target ETA using adaptive damping
            deviation = abs(target_eta_seconds - self._smoothed_eta) / max(1.0, self._smoothed_eta)
            if deviation > 0.60:
                alpha = 0.12
            elif deviation > 0.25:
                alpha = 0.06
            else:
                alpha = 0.02

            self._smoothed_eta = (1.0 - alpha) * self._smoothed_eta + alpha * target_eta_seconds

        eta_sec = max(1, int(round(self._smoothed_eta)))

        # ── 4. Format Output String ──────────────────────────────────────────
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

        dl_mb = self.downloaded_bytes / (1024 * 1024)
        if self.downloaded_bytes > 1024 * 1024 * 1024:
            saved_str = f"{self.downloaded_bytes / (1024 * 1024 * 1024):.2f} GB"
        else:
            saved_str = f"{dl_mb:.1f} MB"

        status_text = (
            f"Downloading… ({completed}/{total} files)"
            if self._is_running else "Idle"
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
        if bps > 1024 * 1024:
            return f"{bps / (1024 * 1024):.2f} MB/s"
        elif bps > 1024:
            return f"{bps / 1024:.1f} KB/s"
        return f"{bps} B/s"


