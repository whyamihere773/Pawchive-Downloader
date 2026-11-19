"""
Downloader Task Builder — Post Filtering, Folder Layout, Post Info & Embed Task Structuring
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import datetime
import os
import re
import time
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.downloader_models import (
    DownloadTask,
    _counts,
    _write_post_info,
    format_unimported_explanation,
    is_post_unimported_on_pawchive,
    is_preview_url,
)
from core.file_order import order_files
from core.filter_engine import FilterEngine, FilterOptions, MediaTypes, fit_path_for_windows
from core.logger import logger
from core.path_utils import post_info_name
from core.video_probe import VideoProbe
from services.link_extractor import LinkExtractor


class DownloaderTaskBuilderMixin:
    """Builds DownloadTask plans from post lists, folder layouts, post_info.txt, and embedded media."""

    def _collect_post_files(
        self,
        post: Dict[str, Any],
        options: FilterOptions,
        domain: str,
        service: str,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Collect and deduplicate post.file, post.attachments, and inline content images."""
        files_to_process: List[Dict[str, Any]] = []
        seen_post_file_keys: Dict[str, int] = {}

        main_file = post.get("file")
        attachments = post.get("attachments", []) or []

        # If Pawchive post has temporary or deferred attachments, resolve signed download URLs
        if getattr(options, "download_pawchive_temporary_files", True):
            if ("pawchive" in (domain or "") or "pawchive" in str(post.get("origin", "")) or "pawchive" in str(post.get("domain", "")) or "pawchive" in str(post.get("service", ""))):
                self._resolve_pawchive_deferred_attachments(post, domain=domain or "pawchive.pw")
                attachments = post.get("attachments", []) or []
                main_file = post.get("file")

        post_is_unimported = is_post_unimported_on_pawchive(post, domain=domain, service=service)

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
        allow_thumbnails = getattr(options, "download_thumbnails_only", False) or getattr(options, "fallback_to_thumbnails", False)
        if options.skip_post_covers:
            if has_other_files:
                skip_main_cover = True
            elif main_file and isinstance(main_file, dict):
                mf_name = (main_file.get("name") or main_file.get("originalFilename") or "").lower()
                if mf_name.startswith("cover.") or mf_name.startswith("cover_") or mf_name.startswith("preview."):
                    skip_main_cover = True
        elif has_other_files and not allow_thumbnails and main_file and isinstance(main_file, dict):
            # When all thumbnail settings are disabled and other attachments exist,
            # skip cover pictures that are thumbnails/previews (but keep full-size temporary files)
            mf_name = (main_file.get("name") or main_file.get("originalFilename") or "").lower()
            mf_path = str(main_file.get("path") or main_file.get("storageKey") or "").lower()
            is_mf_temp = bool(main_file.get("is_temporary")) or bool(re.search(r"\bt\d+\.pawchive\.pw\b", mf_path))
            if not is_mf_temp and (
                is_preview_url(mf_path) or
                bool(main_file.get("preview_only")) or
                mf_name.startswith(("cover.", "cover_", "preview.", "thumb.", "thumbnail.")) or
                bool(re.search(r'(_low|_thumb|\.thumb)\.[a-z0-9]+$', mf_name))
            ):
                skip_main_cover = True

        if not skip_main_cover and main_file and isinstance(main_file, dict) and (main_file.get("path") or main_file.get("storageKey")):
            k = self.extract_norm_rel_key(main_file)
            if k:
                seen_post_file_keys[k] = 0
            files_to_process.append(dict(main_file))

        if isinstance(attachments, list):
            for att in attachments:
                if isinstance(att, dict) and (att.get("path") or att.get("storageKey")):
                    # If skip_post_covers is enabled or thumbnail options are disabled, skip attachments named cover.* when other files exist
                    if (options.skip_post_covers or (has_other_files and not allow_thumbnails)) and (has_other_files or len(attachments) > 1):
                        att_name = (att.get("name") or att.get("originalFilename") or "").lower()
                        att_path = str(att.get("path") or att.get("storageKey") or "").lower()
                        is_att_temp = bool(att.get("is_temporary")) or bool(re.search(r"\bt\d+\.pawchive\.pw\b", att_path))
                        if not is_att_temp and (
                            att_name.startswith(("cover.", "cover_", "preview.", "thumb.", "thumbnail.")) or
                            is_preview_url(att_path) or
                            bool(re.search(r'(_low|_thumb|\.thumb)\.[a-z0-9]+$', att_name))
                        ):
                            continue

                    k = self.extract_norm_rel_key(att)
                    if k and k in seen_post_file_keys:
                        # Upgrade metadata if att has non-preview or better name / server
                        idx = seen_post_file_keys[k]
                        existing = files_to_process[idx]
                        if existing.get("preview_only") and not att.get("preview_only"):
                            existing["preview_only"] = False
                        if att.get("server") and not existing.get("server"):
                            existing["server"] = att.get("server")
                            if att.get("path"):
                                existing["path"] = att.get("path")
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
                    if k and k in seen_post_file_keys:
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

        return files_to_process, post_is_unimported

    def _build_embed_tasks_for_post(
        self,
        *,
        post: Dict[str, Any],
        post_id: str,
        post_title: str,
        post_user: str,
        date_str: str,
        task_post_url: str,
        creator_name: str,
        service: str,
        user_id: str,
        batch_id: Optional[str],
        options: FilterOptions,
        _get_dest_folder: Callable[[str], str],
        not_queued: Counter,
        new_tasks: List[DownloadTask],
    ) -> None:
        """Scan embedded media players (yt-dlp targets) and append DownloadTask entries."""
        should_download_embeds = options.download_embeds and options.file_type in (MediaTypes.ALL, MediaTypes.VIDEOS, MediaTypes.AUDIO)
        if should_download_embeds and options.exact_extensions:
            allowed_exts = FilterEngine.parse_extensions_list(options.exact_extensions)
            if allowed_exts:
                should_download_embeds = any(ext in (MediaTypes.VIDEO_EXTS | MediaTypes.AUDIO_EXTS) for ext in allowed_exts)

        if not should_download_embeds:
            return

        embed_urls = LinkExtractor.extract_embed_urls(post)
        for embed_idx, e_url in enumerate(embed_urls, 1):
            e_host = re.sub(r'[^a-zA-Z0-9]', '', e_url.split("://")[-1].split("/")[0])
            e_name = f"embed_{embed_idx}_{e_host}.mp4"
            e_dest_dir = _get_dest_folder(e_name)
            e_target_path = fit_path_for_windows(os.path.join(e_dest_dir, e_name))
            e_file_id = f"embed_{post_id}_{embed_idx}"

            if not getattr(options, "force_redownload", False) and self.archive_manager and self.archive_manager.is_enabled:
                if self.archive_manager.is_archived(service=service, post_id=post_id, file_id=e_file_id):
                    logger.info(f"📦 Skipping archived embedded media: '{e_name}' (present in download archive)",
                                category="file", to_file=False)
                    not_queued["in the download archive"] += 1
                    continue

            if not getattr(options, "force_redownload", False) and not options.keep_duplicates and os.path.exists(e_target_path) and os.path.getsize(e_target_path) > 0:
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
            e_task.options = options
            new_tasks.append(e_task)

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
        user_id: str = "",
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[DownloadTask]:
        """
        Filters posts and attachments, building the list of download tasks with structured paths.
        """
        new_tasks: List[DownloadTask] = []
        not_queued: Counter = Counter()          # files skipped / renamed while building: counted in the
        renamed: Counter = Counter()             # log file (a line each only in the log panel)
        self._unmatched_known_count = 0
        self.last_build_cancelled = False
        unimported_post_ids: Set[str] = set()
        unimported_files_skipped = 0
        unimported_thumbs_queued = 0
        unimported_tasks: List[DownloadTask] = []
        self.last_build_unimported_tasks = []
        self.last_build_unimported = {
            "posts": 0,
            "files": 0,
            "queued_thumbnails": 0,
            "post_ids": [],
            "creator_name": creator_name,
            "total_posts": len(posts),
            "service": service,
            "domain": domain,
        }
        # cancel() bumps _session_id, so only a cancel issued during this build counts;
        # a stale flag left over from an earlier cancelled scan must not abort it.
        build_session_id = self._session_id

        def _build_cancelled() -> bool:
            return self._cancel_event.is_set() and self._session_id != build_session_id

        creator_clean = FilterEngine.clean_filesystem_text(creator_name, max_len=80, fallback="creator")
        if (not creator_clean or creator_clean in ("creator", user_id, f"{service}_{user_id}")) and posts:
            for p in posts:
                better = p.get("creator_name") or p.get("artist_name") or p.get("username")
                if better and better not in ("creator", user_id, f"{service}_{user_id}"):
                    creator_clean = FilterEngine.clean_filesystem_text(better, max_len=80, fallback=creator_clean)
                    creator_name = better
                    break

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

        # CoomerFans media resolution: resolve full attachments before structuring tasks
        total_posts_count = len(posts_to_process)
        if progress_callback and total_posts_count > 0:
            try:
                progress_callback(0, total_posts_count, "Resolving media & filtering posts...")
            except Exception:
                pass
        if domain == "coomerfans.com" or any(p.get("_needs_coomerfans_media") for p in posts_to_process):
            from services.coomerfans_client import resolve_posts_media
            resolve_posts_media(posts_to_process, cancel_event=self._cancel_event)

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

        creator_folder_name = None          # (looked up once per scan)
        _last_build_prog_ts = 0.0
        for post_idx, post in enumerate(posts_to_process, 1):
            if _build_cancelled():
                self.last_build_cancelled = True
                logger.info("Task structuring cancelled by user.", category="downloader")
                return []
            if progress_callback and total_posts_count > 0:
                now_prog = time.monotonic()
                if post_idx == total_posts_count or post_idx % 50 == 0 or (now_prog - _last_build_prog_ts) >= 0.25:
                    _last_build_prog_ts = now_prog
                    try:
                        progress_callback(
                            post_idx,
                            total_posts_count,
                            f"Building queue: {post_idx:,}/{total_posts_count:,} posts ({len(new_tasks):,} files)"
                        )
                    except Exception:
                        pass

            post_id = str(post.get("id", ""))
            post_title, post_caption = FilterEngine.extract_post_title_and_caption(
                post, max_title_len=80, fallback_title="Untitled"
            )
            published = post.get("published", "") or ""
            if isinstance(published, (int, float)):
                try:
                    date_str = datetime.datetime.fromtimestamp(published).strftime("%Y-%m-%d")
                except Exception:
                    date_str = str(published)
            else:
                pub_str = str(published).strip()
                date_m = re.search(r'^\d{4}-\d{2}-\d{2}', pub_str)
                if date_m:
                    date_str = date_m.group(0)
                elif "T" in pub_str and not pub_str.startswith("T"):
                    date_str = pub_str.split("T")[0]
                elif " " in pub_str:
                    date_str = pub_str.split(" ")[0]
                else:
                    date_str = pub_str[:10] if pub_str else ""
                date_str = FilterEngine.clean_filesystem_text(date_str, max_len=20, fallback="")

            # Construct canonical web post link for manual inspection/testing
            post_user = str(post.get("user") or post.get("user_id") or post.get("artist_id") or user_id or "")
            is_dm = bool(post.get("is_dms") or post.get("is_dm") or post.get("type") == "dm" or post.get("dm"))
            route = "dm" if is_dm else "post"
            if domain == "cum.st":
                if service and post_user and post_id:
                    task_post_url = f"https://cum.st/creators/{service}/{post_user}/{route}/{post_id}"
                elif service and post_id:
                    task_post_url = f"https://cum.st/posts/{service}/{post_id}"
                else:
                    task_post_url = ""
            elif domain == "coomerfans.com":
                task_post_url = f"https://coomerfans.com/p/{post_id}/{post_user}/{service}"
            elif domain and service and post_user and post_id:
                task_post_url = f"https://{domain}/{service}/user/{post_user}/{route}/{post_id}"
            elif domain and service and post_id:
                task_post_url = f"https://{domain}/{service}/post/{post_id}"
            else:
                task_post_url = ""

            # Apply post filter (date range, skip words, character whitelist)
            keep_post, reason = FilterEngine.should_keep_post(post, options)
            if not keep_post:
                logger.debug(f"Skipped post [{post_id}] '{post_title}': {reason}", category="filter")
                continue

            # Filter posts by video length if enabled
            if getattr(options, "video_duration_filter_enabled", False):
                video_candidates = []
                mf = post.get("file")
                if isinstance(mf, dict):
                    mfn = (mf.get("name") or mf.get("originalFilename") or "").lower()
                    _, ext = os.path.splitext(mfn)
                    if ext in MediaTypes.VIDEO_EXTS or (mf.get("mimeType") or "").startswith("video/"):
                        video_candidates.append(mf)

                for att in (post.get("attachments") or []):
                    if isinstance(att, dict):
                        atn = (att.get("name") or att.get("originalFilename") or "").lower()
                        _, ext = os.path.splitext(atn)
                        if ext in MediaTypes.VIDEO_EXTS or (att.get("mimeType") or "").startswith("video/"):
                            video_candidates.append(att)

                embed_urls = LinkExtractor.extract_embed_urls(post) if options.download_embeds else []

                if not video_candidates and not embed_urls:
                    logger.debug(f"Skipped post [{post_id}] '{post_title}': Post contains no videos (Duration filter active)", category="filter")
                    continue

                has_matching_video = False
                probe_session = self._get_worker_session()
                for vc in video_candidates:
                    v_url = self._resolve_candidate_video_url(vc, domain or "")
                    dur = VideoProbe.get_video_duration(v_url, session=probe_session)
                    vc["_probed_duration"] = dur
                    ok, _ = FilterEngine.should_keep_video_duration(dur, options)
                    if ok:
                        has_matching_video = True

                if not has_matching_video and embed_urls:
                    for eu in embed_urls:
                        dur = VideoProbe.get_video_duration(eu, session=probe_session)
                        ok, _ = FilterEngine.should_keep_video_duration(dur, options)
                        if ok:
                            has_matching_video = True
                            break

                if not has_matching_video:
                    min_d, max_d = FilterEngine.get_effective_duration_limits(options)
                    min_s = FilterEngine.format_duration_str(min_d)
                    max_s = FilterEngine.format_duration_str(max_d)
                    logger.info(f"⏭️ Skipped post [{post_id}] '{post_title}': No videos match duration range [{min_s} – {max_s}]", category="filter")
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

            creator_folder_name, _creator_base_parts, post_subfolder_name, post_folder, _get_dest_folder = (
                self._resolve_post_folder_layout(
                    post=post,
                    post_id=post_id,
                    post_title=post_title,
                    date_str=date_str,
                    creator_clean=creator_clean,
                    creator_folder_name=creator_folder_name,
                    service=service,
                    base_dir=base_dir,
                    artist_dir=artist_dir,
                    options=options,
                    post_folder_registry=post_folder_registry,
                )
            )

            # Smart password extraction (search full caption + comments)
            caption_text = (
                post.get("captionText") or
                post.get("content") or
                post.get("captionHtml") or
                post.get("caption") or
                post.get("text") or
                post_caption or
                ""
            )
            caption_clean = post_caption or re.sub(r'<[^>]+>', '', re.sub(r'<br\s*/?>', '\n', str(caption_text), flags=re.IGNORECASE)).strip()
            _pw_search_text = caption_clean
            if post.get("comments_text"):
                _pw_search_text += "\n" + post.get("comments_text")
            passwords = self.extract_passwords(_pw_search_text)

            # Post info / description archiver: prepared now, written once a file of the post is saved
            post_task_start = len(new_tasks)
            post_info_path, post_info_content = self._prepare_post_info(
                post=post,
                post_id=post_id,
                post_title=post_title,
                date_str=date_str,
                caption_clean=caption_clean,
                passwords=passwords,
                creator_name=creator_name,
                service=service,
                domain=domain,
                user_id=user_id,
                task_post_url=task_post_url,
                post_folder=post_folder,
                post_subfolder_name=post_subfolder_name,
                options=options,
                _get_dest_folder=_get_dest_folder,
            )

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

            files_to_process, post_is_unimported = self._collect_post_files(post, options, domain, service)

            skipped_delta, thumbs_delta = self._build_file_tasks_for_post(
                post=post,
                post_idx=post_idx,
                post_id=post_id,
                post_title=post_title,
                post_user=post_user,
                date_str=date_str,
                caption_clean=caption_clean,
                task_post_url=task_post_url,
                creator_name=creator_name,
                service=service,
                domain=domain,
                user_id=user_id,
                batch_id=batch_id,
                options=options,
                files_to_process=files_to_process,
                post_is_unimported=post_is_unimported,
                passwords=passwords,
                _get_dest_folder=_get_dest_folder,
                folder_file_counts=folder_file_counts,
                _batch_paths=_batch_paths,
                _batch_rel_paths=_batch_rel_paths,
                not_queued=not_queued,
                renamed=renamed,
                unimported_post_ids=unimported_post_ids,
                unimported_tasks=unimported_tasks,
                new_tasks=new_tasks,
            )
            unimported_files_skipped += skipped_delta
            unimported_thumbs_queued += thumbs_delta

            # ── 3. Scan Embedded Media Players (yt-dlp: Vimeo, YouTube, Streamable, RedGifs, etc.)
            self._build_embed_tasks_for_post(
                post=post,
                post_id=post_id,
                post_title=post_title,
                post_user=post_user,
                date_str=date_str,
                task_post_url=task_post_url,
                creator_name=creator_name,
                service=service,
                user_id=user_id,
                batch_id=batch_id,
                options=options,
                _get_dest_folder=_get_dest_folder,
                not_queued=not_queued,
                new_tasks=new_tasks,
            )

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
        if batch_id and build_post_infos:
            for _info_key in build_post_infos:
                self._post_info_owners[_info_key] = batch_id
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

        self.last_build_unimported_tasks = unimported_tasks
        self.last_build_unimported = {
            "posts": len(unimported_post_ids),
            "files": unimported_files_skipped,
            "queued_thumbnails": unimported_thumbs_queued,
            "post_ids": sorted(unimported_post_ids),
            "creator_name": creator_name,
            "total_posts": len(posts_to_process),
            "service": service,
            "domain": domain,
        }
        if unimported_files_skipped > 0 or unimported_thumbs_queued > 0:
            _, unimp_msg = format_unimported_explanation(
                creator_name=creator_name,
                unimported_posts=len(unimported_post_ids),
                unimported_files=unimported_files_skipped,
                queued_thumbnails=unimported_thumbs_queued,
                is_single_post=(len(posts_to_process) == 1),
                all_unimported=(len(new_tasks) == 0 and unimported_files_skipped > 0),
            )
            logger.warning(f"⚠ {unimp_msg.replace(chr(10) + chr(10), ' ')}", category="downloader")

        notes = [f"Not queued: {_counts(not_queued)}." if not_queued else "",
                 f"Renamed to keep files apart: {_counts(renamed)}." if renamed else ""]
        logger.success(" ".join([f"Prepared {len(new_tasks)} file download tasks."] + [n for n in notes if n]),
                       category="downloader")
        return new_tasks
