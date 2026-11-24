"""
Downloader Task Builder — Per-File Attachment Normalization, URL Resolution & Collision Handling
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import hashlib
import os
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.downloader_models import (
    COOMER_SERVICES,
    DownloadTask,
    UNIMPORTED_TASK_ERROR_MSG,
    _fq,
    _get_media_candidate_paths,
    is_post_unimported_on_pawchive,
    needs_full_size_upgrade,
)
from core.filter_engine import FilterEngine, FilterOptions, MediaTypes, fit_path_for_windows
from core.logger import logger
from core.path_utils import post_id_tag
from core.providers import is_disabled


_MIME_EXT_MAP = {
    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
    "image/gif": ".gif", "image/webp": ".webp", "image/avif": ".avif",
    "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
    "video/x-matroska": ".mkv", "video/avi": ".avi",
    "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/wav": ".wav",
    "audio/flac": ".flac", "audio/aac": ".aac",
}


class DownloaderTaskBuilderFilesMixin:
    """Per-file attachment normalization, candidate URL construction, and collision resolution."""

    def _normalize_attachment_url(
        self,
        fobj: Dict[str, Any],
        post: Dict[str, Any],
        rel_path: str,
        raw_name: str,
        mime_ext: str,
        domain: str,
    ) -> Tuple[Optional[str], str, str, bool, List[str]]:
        """Normalize attachment relative path/storageKey/URL into (original_url, norm_path, clean_rel, is_storage_key, extra_cum_variants)."""
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
        extra_cum_variants: List[str] = []

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

            original_url = f"https://cdn.cum.st/media/{norm_path}/{primary_variant}"
            norm_path = f"/{norm_path[:2]}/{norm_path[2:4]}/{norm_path}.{ext}"  # legacy fallback path
        elif norm_path.startswith("http://") or norm_path.startswith("https://"):
            is_pawchive_temp = bool(re.search(r"\bt\d+\.pawchive\.pw\b", norm_path)) or bool(fobj.get("is_temporary")) or "coomerfans.com" in norm_path
            if is_pawchive_temp:
                # Pawchive temporary oversized storage on t1-t4.pawchive.pw uses signed URLs (?e=...&s=...)
                # Preserve full signed URL with query parameters intact
                original_url = norm_path
                # Clean relative path for deduplication and file_id: /f/<hash>/<filename>
                path_without_query = norm_path.split("?")[0]
                clean_part = path_without_query.split("://")[-1].partition("/")[-1]
                norm_path = f"/{clean_part}" if not clean_part.startswith("/") else clean_part
            else:
                # Preserve the original CDN URL as the first candidate
                original_url = norm_path.split("?")[0]  # strip existing query params
                if "e1.cum.st" in original_url:
                    original_url = original_url.replace("e1.cum.st", "cdn.cum.st")
                elif re.match(r"^https?://pawchive\.pw/data/", original_url, re.IGNORECASE):
                    # Bare pawchive.pw/data/... returns 404; route to assigned n1-n4 server or file.pawchive.pw
                    _srv = str(fobj.get("server") or post.get("server") or "").strip().rstrip("/")
                    if not _srv and fobj.get("node") is not None:
                        _srv = f"https://n{fobj.get('node')}.pawchive.pw"
                    if _srv and not _srv.startswith(("http://", "https://")):
                        _srv = f"https://{_srv}"
                    original_url = re.sub(
                        r"^https?://pawchive\.pw",
                        _srv or "https://file.pawchive.pw",
                        original_url,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                # Check for cum.st/media/ pattern (e1.cum.st or cdn.cum.st) — keep as-is, extract a norm_path for fallbacks
                m_cumst = re.match(r'https?://[^/]*cum\.st/media/([0-9a-f]{64})/([^?#]+)', norm_path)
                if m_cumst:
                    storage_key = m_cumst.group(1)
                    variant = m_cumst.group(2)  # e.g. "original.jpg"
                    ext = os.path.splitext(variant)[1].lstrip(".") or "jpg"
                    norm_path = f"/{storage_key[:2]}/{storage_key[2:4]}/{storage_key}.{ext}"
                else:
                    match_data = re.search(r'/(?:data|thumbnail/data)?(/[0-9a-f]{2,3}/[0-9a-f]{2}/[^\s?#]+)', norm_path, re.IGNORECASE)
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

        return original_url, norm_path, clean_rel, is_storage_key, extra_cum_variants

    def _build_candidate_urls(
        self,
        fobj: Dict[str, Any],
        post: Dict[str, Any],
        options: FilterOptions,
        effective_domain: str,
        service: str,
        original_url: Optional[str],
        rel_path: str,
        clean_rel: str,
        sanitized_name: str,
        is_preview_only: bool,
        is_storage_key: bool,
        extra_cum_variants: List[str],
    ) -> Tuple[List[str], str]:
        """Build ordered candidate download URLs and adjust filename extension for video thumbnails."""
        candidate_urls: List[str] = []

        if is_preview_only or options.download_thumbnails_only:
            # When download_thumbnails_only is enabled or an attachment is preview-only / unimported,
            # strictly query thumbnail CDN servers — never hammer full-size storage nodes with 404s.
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
            is_pawchive_temp = (
                bool(original_url and (re.search(r"\bt\d+\.pawchive\.pw\b", original_url) or "coomerfans.com" in original_url))
                or bool(fobj.get("is_temporary"))
            )
            if is_pawchive_temp and original_url:
                # Temporary oversized files on t1-t4.pawchive.pw are signed URLs.
                # Append the signed URL directly as the primary candidate (do not fallback to file.pawchive.pw)
                candidate_urls.append(original_url)
            else:
                is_thumbnail_url = bool(
                    original_url and (
                        "/thumbnail/" in original_url or
                        "img.pawchive" in original_url or
                        "img.kemono" in original_url or
                        "img.coomer" in original_url or
                        "img.cum.st" in original_url
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
                            u_ev = f"https://cdn.cum.st/media/{rel_path}/{ev}"
                            if u_ev not in candidate_urls:
                                candidate_urls.append(u_ev)
                    elif not original_url or is_thumbnail_url:
                        candidate_urls.append(f"https://cum.st/data{clean_rel}?f={_fq(sanitized_name)}")
                    # Fallbacks
                    candidate_urls.append(f"https://cum.st/data{clean_rel}")
                    candidate_urls.append(f"https://img.cum.st/data{clean_rel}")
                    fallback_thumb_url = f"https://img.cum.st/thumbnail/data{clean_rel}"
                elif "pawchive" in effective_domain:
                    # Each Pawchive file lives on one assigned storage node (fobj['server'] or n{node})
                    # and file.pawchive.pw routes to the right node. Never blindly probe all four
                    # n1-n4 nodes — hitting the 3 wrong shards generates guaranteed 404s that exhaust
                    # Pawchive's ~30 req/10s nginx rate-limit bucket.
                    srv_raw = str(
                        (fobj.get("server") if isinstance(fobj, dict) else "")
                        or (post.get("server") if isinstance(post, dict) else "")
                        or ""
                    ).strip().rstrip("/")
                    if srv_raw and not srv_raw.startswith(("http://", "https://")):
                        srv_raw = f"https://{srv_raw}"
                    node_num = fobj.get("node") if isinstance(fobj, dict) else None
                    if not node_num and isinstance(post, dict):
                        node_num = post.get("node")
                    if not srv_raw and node_num is not None:
                        srv_raw = f"https://n{node_num}.pawchive.pw"

                    full_url = f"https://file.pawchive.pw/data{clean_rel}?f={_fq(sanitized_name)}"
                    srv_url = f"{srv_raw}/data{clean_rel}?f={_fq(sanitized_name)}" if srv_raw else None
                    mirror_host = "coomer.st" if service.lower() in COOMER_SERVICES else "kemono.cr"
                    mirror_url = f"https://{mirror_host}/data{clean_rel}?f={_fq(sanitized_name)}"
                    not_copied_yet = str(post.get("origin", "")).lower() in ("kemono", "coomer") or str(post.get("preview_state", "")).lower() == "pending"

                    # Only fall back to file.pawchive.pw when the assigned nX storage node is unknown;
                    # file.pawchive.pw 302-redirects straight back to nX, which would double-hit the same shard.
                    primary_paw_list = [srv_url] if srv_url else [full_url]
                    order = ([mirror_url] + primary_paw_list) if not_copied_yet else (primary_paw_list + [mirror_url])
                    for u in order:
                        if u and u not in candidate_urls and not is_disabled(u):
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
        return candidate_urls, sanitized_name

    def _resolve_filename_collision(
        self,
        target_path: str,
        target_dest_dir: str,
        sanitized_name: str,
        clean_rel: str,
        post_id: str,
        post_title: str,
        candidate_urls: List[str],
        file_url: str,
        _batch_paths: Dict[str, Dict[str, Any]],
        not_queued: Counter,
        renamed: Counter,
    ) -> Tuple[bool, str, List[str], str]:
        """Resolve same-post / cross-post target_path collisions. Returns (skip, target_path, candidate_urls, file_url)."""
        if target_path not in _batch_paths:
            return False, target_path, candidate_urls, file_url

        prev_entry = _batch_paths[target_path]
        prev_post_id = prev_entry.get("post_id", "")
        prev_post_title = prev_entry.get("post_title", "")
        prev_rel = prev_entry.get("rel_path", "")

        # Check if identical file attached twice in the same post
        if prev_post_id == post_id and prev_rel == clean_rel:
            logger.debug(
                f"Skipping identical duplicate attachment: '{sanitized_name}' in post '{post_title}'",
                category="file", to_file=False
            )
            not_queued["identical duplicates"] += 1
            return True, target_path, candidate_urls, file_url

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
                category="file", to_file=False
            )
            renamed["name used by another post"] += 1
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
                category="file", to_file=False
            )
            renamed["same name twice in a post"] += 1

        # Also update the candidate URLs to use the disambiguated display name
        candidate_urls = [
            u.replace(f"?f={_fq(sanitized_name)}", f"?f={_fq(disambig_name)}").replace(f"&f={_fq(sanitized_name)}", f"&f={_fq(disambig_name)}")
            for u in candidate_urls
        ]
        file_url = candidate_urls[0] if candidate_urls else file_url
        return False, target_path, candidate_urls, file_url

    def _build_file_tasks_for_post(
        self,
        *,
        post: Dict[str, Any],
        post_idx: int,
        post_id: str,
        post_title: str,
        post_user: str,
        date_str: str,
        caption_clean: str,
        task_post_url: str,
        creator_name: str,
        service: str,
        domain: str,
        user_id: str,
        batch_id: Optional[str],
        options: FilterOptions,
        files_to_process: List[Dict[str, Any]],
        post_is_unimported: bool,
        passwords: List[str],
        _get_dest_folder: Callable[[str], str],
        folder_file_counts: Dict[str, int],
        _batch_paths: Dict[str, Dict[str, Any]],
        _batch_rel_paths: Dict[str, Set[str]],
        not_queued: Counter,
        renamed: Counter,
        unimported_post_ids: Set[str],
        unimported_tasks: List[DownloadTask],
        new_tasks: List[DownloadTask],
    ) -> Tuple[int, int]:
        """Process all file attachments for a single post. Returns (unimported_files_skipped_delta, unimported_thumbs_queued_delta)."""
        unimported_files_skipped = 0
        unimported_thumbs_queued = 0

        for file_idx, fobj in enumerate(files_to_process, 1):
            # Ignore paywalled locked attachments
            if fobj.get("locked"):
                continue

            raw_name = fobj.get("name") or fobj.get("originalFilename") or ""
            # API responses can include trailing commas/punctuation in filenames
            # (e.g. "cover.jpeg,") that corrupt CDN query params and file extensions.
            raw_name = raw_name.strip().rstrip(".,;!?")
            # Derive extension from mimeType when filename is missing or has no extension
            mime_type = fobj.get("mimeType") or fobj.get("mime_type") or ""
            mime_ext = _MIME_EXT_MAP.get(mime_type.lower().split(";")[0].strip(), "")
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
            keep_file, f_reason = FilterEngine.should_keep_file(raw_name, options, file_size=file_bytes, duration=fobj.get("_probed_duration"))
            if not keep_file:
                logger.debug(f"Skipped file '{raw_name}': {f_reason}", category="filter", to_file=False)
                not_queued["filtered out"] += 1
                continue

            original_url, norm_path, clean_rel, is_storage_key, extra_cum_variants = self._normalize_attachment_url(
                fobj, post, rel_path, raw_name, mime_ext, domain
            )

            # Deduplication check before incrementing folder file counts:
            # Prevents incrementing the sequence counter (001_, 002_, ...) for duplicate files
            norm_key = self.extract_norm_rel_key(fobj) or clean_rel.lower()
            target_dest_dir = _get_dest_folder(raw_name)
            if not options.keep_duplicates and norm_key in _batch_rel_paths[target_dest_dir]:
                logger.debug(
                    f"Skipping identical duplicate attachment: '{raw_name}' ({clean_rel}) in post '{post_title}'",
                    category="file", to_file=False
                )
                not_queued["identical duplicates"] += 1
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
                user_id=str(post.get("user") or ""),
                caption=caption_clean
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

            is_temp_resolved = (
                bool(fobj.get("is_temporary")) or
                bool(re.search(r"\bt\d+\.pawchive\.pw\b", str(original_url or norm_path or fobj.get("path") or "")))
            )
            file_is_unimported = bool(
                (post_is_unimported or is_post_unimported_on_pawchive(post, domain=effective_domain, service=service))
                and not is_temp_resolved
            )
            is_preview_only = (
                (bool(fobj.get("preview_only")) or file_is_unimported) and
                not is_temp_resolved
            )
            allow_thumb_fallback = getattr(options, "fallback_to_thumbnails", False)
            allow_thumbnails = getattr(options, "download_thumbnails_only", False) or allow_thumb_fallback

            # If the post hasn't been imported onto Pawchive's storage nodes yet (or only has a preview)
            # and thumbnail options are disabled, skip cleanly without spamming 404 requests.
            if is_preview_only and not allow_thumbnails:
                if file_is_unimported:
                    unimported_files_skipped += 1
                    if post_id:
                        unimported_post_ids.add(str(post_id))
                    not_queued["not imported on Pawchive (previews only)"] += 1
                    unimp_target_path = fit_path_for_windows(os.path.join(target_dest_dir, sanitized_name))
                    unimp_file_id = f"{post_id}_{clean_rel}"
                    unimp_task = DownloadTask(
                        url="",
                        target_path=unimp_target_path,
                        post_title=post_title,
                        creator_name=creator_name,
                        service=service,
                        post_id=post_id,
                        file_id=unimp_file_id,
                        file_size=int(file_bytes or 0),
                        batch_id=batch_id,
                        post_url=task_post_url,
                        post_date=date_str,
                        user_id=user_id or post_user,
                        options=options,
                    )
                    unimp_task.status = "failed"
                    unimp_task.is_unimported = True
                    unimp_task.retry_capped = True
                    unimp_task.http_status = 404
                    unimp_task.error_msg = UNIMPORTED_TASK_ERROR_MSG
                    unimported_tasks.append(unimp_task)
                    logger.debug(
                        f"Skipping unimported Pawchive file '{raw_name}' (post {post_id}): full file isn't hosted on Pawchive yet",
                        category="filter", to_file=False
                    )
                else:
                    logger.debug(
                        f"Skipping preview-only attachment '{raw_name}': thumbnail fallback is disabled",
                        category="filter", to_file=False
                    )
                    not_queued["filtered out"] += 1
                continue

            candidate_urls, sanitized_name = self._build_candidate_urls(
                fobj=fobj,
                post=post,
                options=options,
                effective_domain=effective_domain,
                service=service,
                original_url=original_url,
                rel_path=rel_path,
                clean_rel=clean_rel,
                sanitized_name=sanitized_name,
                is_preview_only=is_preview_only,
                is_storage_key=is_storage_key,
                extra_cum_variants=extra_cum_variants,
            )

            file_url = candidate_urls[0] if candidate_urls else f"https://file.pawchive.pw/data{clean_rel}?f={_fq(sanitized_name)}"
            target_dest_dir = _get_dest_folder(sanitized_name)
            target_path = fit_path_for_windows(os.path.join(target_dest_dir, sanitized_name))
            file_id = f"{post_id}_{clean_rel}"

            skip_dup, target_path, candidate_urls, file_url = self._resolve_filename_collision(
                target_path=target_path,
                target_dest_dir=target_dest_dir,
                sanitized_name=sanitized_name,
                clean_rel=clean_rel,
                post_id=post_id,
                post_title=post_title,
                candidate_urls=candidate_urls,
                file_url=file_url,
                _batch_paths=_batch_paths,
                not_queued=not_queued,
                renamed=renamed,
            )
            if skip_dup:
                continue

            _batch_paths[target_path] = {
                "post_id": post_id,
                "post_title": post_title,
                "rel_path": clean_rel
            }
            # Record the normalised key so future files in this folder can detect duplicates
            # regardless of whether an index prefix changes their target filename.
            _batch_rel_paths[target_dest_dir].add(norm_key)

            raw_dest_dir = _get_dest_folder(raw_name)
            raw_path = os.path.join(raw_dest_dir, raw_name)
            # Also check for the prefixed variant on disk (e.g. "001_filename.jpg") so that
            # re-runs with index prefix enabled don't re-download already-saved files.
            prefixed_raw = os.path.join(raw_dest_dir, f"{seq_idx:03d}_{raw_name}")

            # Candidate paths on disk (target name, raw name, prefixed variants, plus .webp/.avif and .mp4/.mkv/.webm)
            candidate_disk_paths = []
            for _base_p in (target_path, raw_path, prefixed_raw):
                candidate_disk_paths.extend(_get_media_candidate_paths(_base_p))
            _seen_cands = set()
            disk_candidates = []
            for _cp in candidate_disk_paths:
                if _cp and _cp not in _seen_cands:
                    _seen_cands.add(_cp)
                    disk_candidates.append(_cp)

            expected_sha = str(fobj.get("sha256") or fobj.get("hash") or "")

            force_redownload = bool(getattr(options, "force_redownload", False))

            # Skip if already recorded in download archive database (gallery-dl style) — unless the
            # copy still on disk is a small / preview one that should be upgraded to full size
            if not force_redownload and self.archive_manager and self.archive_manager.is_enabled:
                if self.archive_manager.is_archived(service=service, post_id=post_id, file_id=file_id, file_hash=expected_sha):
                    on_disk = next((cp for cp in disk_candidates
                                    if os.path.exists(cp) and os.path.getsize(cp) > 0), None)
                    if not (on_disk and needs_full_size_upgrade(os.path.getsize(on_disk), int(file_bytes or 0), target_path, options, on_disk)):
                        logger.info(f"📦 Skipping archived file: '{os.path.basename(target_path)}' (present in download archive)",
                                    category="file", to_file=False)
                        not_queued["in the download archive"] += 1
                        continue

            # Skip if already exists on disk at target_path, webp path, or raw name path
            if not force_redownload and not options.keep_duplicates:
                existing_disk_path = next((cp for cp in disk_candidates
                                           if os.path.exists(cp) and os.path.getsize(cp) > 0), None)

                if existing_disk_path:
                    existing_sz = os.path.getsize(existing_disk_path)
                    # A small / preview copy is replaced by the full-size file
                    should_upgrade = needs_full_size_upgrade(existing_sz, int(file_bytes or 0), target_path,
                                                             options, existing_disk_path)

                    if not should_upgrade:
                        logger.info(f"⏳ Skipping existing file: '{os.path.basename(target_path)}' (already present on disk)",
                                    category="file", to_file=False)
                        not_queued["already on disk"] += 1
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
            task.options = options
            task.fallback_urls = candidate_urls[1:]
            if file_is_unimported:
                task.is_unimported_preview = True
                unimported_thumbs_queued += 1
                if post_id:
                    unimported_post_ids.add(str(post_id))
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

        return unimported_files_skipped, unimported_thumbs_queued
