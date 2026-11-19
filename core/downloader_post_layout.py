"""
Downloader Post Folder Layout & post_info.txt Builder Mixin
Decomposed from core/downloader_task_builder.py for proactive modularity.
"""

import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.filter_engine import FilterEngine, FilterOptions, fit_path_for_windows
from core.logger import logger
from core.path_utils import post_info_name
from services.link_extractor import LinkExtractor


class DownloaderPostLayoutMixin:
    """Resolves creator/post folder hierarchies and prepares post_info.txt metadata."""

    def _resolve_post_folder_layout(
        self,
        *,
        post: Dict[str, Any],
        post_id: str,
        post_title: str,
        date_str: str,
        creator_clean: str,
        creator_folder_name: Optional[str],
        service: str,
        base_dir: str,
        artist_dir: Optional[str],
        options: FilterOptions,
        post_folder_registry: Dict[str, str],
    ) -> Tuple[str, List[str], str, str, Callable[[str], str]]:
        """Determine parent folder hierarchy and per-file destination resolver for a post."""
        if creator_folder_name is None:
            from core.folder_naming import pick_creator_folder
            creator_folder_name = os.path.basename(pick_creator_folder(base_dir or "", creator_clean, service))
        creator_folder = creator_folder_name
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

        return creator_folder_name, creator_base_parts, post_subfolder_name, post_folder, _get_dest_folder

    def _prepare_post_info(
        self,
        *,
        post: Dict[str, Any],
        post_id: str,
        post_title: str,
        date_str: str,
        caption_clean: str,
        passwords: List[str],
        creator_name: str,
        service: str,
        domain: str,
        user_id: str,
        task_post_url: str,
        post_folder: str,
        post_subfolder_name: str,
        options: FilterOptions,
        _get_dest_folder: Callable[[str], str],
    ) -> Tuple[str, str]:
        """Prepare post_info.txt destination path and text content (deferred until download)."""
        if not options.save_post_metadata:
            return "", ""
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

            if not should_prepare_info:
                return "", ""

            tags_list = FilterEngine.normalize_tags(post.get("tags"))
            if getattr(self, "known_manager", None):
                try:
                    hit = self.known_manager.find_matching_hierarchy(post_title)
                    if hit:
                        fr, ch = hit
                        for n in (ch, fr):
                            if n and n.lower() != "general" and n not in tags_list:
                                tags_list.insert(0, n)
                except Exception:
                    pass
            tags_str = ", ".join(tags_list)

            # Build creator profile URL
            post_user = str(post.get("user") or post.get("user_id") or post.get("artist_id") or user_id or "")
            if domain == "cum.st":
                if service and post_user:
                    creator_url = f"https://cum.st/creators/{service}/{post_user}"
                elif service:
                    creator_url = f"https://cum.st/creators/{service}"
                else:
                    creator_url = ""
            elif domain and service and post_user:
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
                    if _k and _k in seen_info_keys:
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

            return info_path, info_content
        except Exception as ex:
            logger.debug(f"Could not prepare post_info.txt for {post_id}: {ex}", category="file")
            return "", ""
