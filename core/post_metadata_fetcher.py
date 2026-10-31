"""
Post Metadata Fetcher & Synchronizer
Fetches full post metadata (captions, descriptions, tags, published dates) from Pawchive / Kemono
APIs for local files and saves them to disk as post_info.txt and post_metadata.json.
"""

import os
import re
import json
import logging
from typing import Optional, Dict, List, Any, Set, Tuple
from core.atomic_io import atomic_write_text, atomic_write_json
from core.parser import URLParseResult

logger = logging.getLogger("pawchive.metadata_fetcher")


class PostMetadataFetcher:
    """
    Scans local files to detect post IDs and creator context, queries the API
    to fetch missing post metadata, and writes post_info.txt and JSON sidecars.
    """

    KNOWN_SERVICES = {
        "patreon", "fanbox", "subscribestar", "fantia", "boosty",
        "gumroad", "discord", "onlyfans", "fansly", "afdian", "candfans"
    }

    def __init__(self, api_client=None, archive_manager=None, default_domain: str = "pawchive.pw"):
        self.api_client = api_client
        self.archive_manager = archive_manager
        self.default_domain = default_domain

    @classmethod
    def extract_context_from_path(cls, path: str) -> Dict[str, str]:
        """
        Extracts creator name, service, and post ID from a file path or folder name.
        Example: '.../Whisperfoot [patreon]/63145170_Salad Cat.zip' ->
                 {'creator': 'Whisperfoot', 'service': 'patreon', 'post_id': '63145170'}
        """
        norm = os.path.normpath(os.path.abspath(path))
        parts = norm.split(os.sep)
        filename = os.path.basename(norm)
        base_name, _ = os.path.splitext(filename)

        creator = ""
        service = ""
        post_id = ""

        # 1. Search for [service] or [creator] in folder parts from bottom up
        for p in reversed(parts[:-1]):
            # Check for pattern "Creator [service]"
            m_svc = re.search(r'\[([a-zA-Z0-9_\-]+)\]', p)
            if m_svc:
                cand_svc = m_svc.group(1).lower()
                if cand_svc in cls.KNOWN_SERVICES:
                    service = cand_svc
                    creator = re.sub(r'\s*\[.*?\]', '', p).strip()
                    break
                elif not creator:
                    creator = m_svc.group(1).strip()

        # 2. Extract numeric Post ID (5-10 digits)
        # Check filename first
        pid_m = re.search(r'(?<!\d)(\d{5,10})(?!\d)', base_name)
        if pid_m:
            post_id = pid_m.group(1)
        else:
            # Check parent folder name
            for p in reversed(parts[:-1]):
                pid_m = re.search(r'(?<!\d)(\d{5,10})(?!\d)', p)
                if pid_m:
                    post_id = pid_m.group(1)
                    break

        return {
            "creator": creator,
            "service": service,
            "post_id": post_id
        }

    def detect_posts_in_folder(self, folder_path: str, file_paths: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Scans a folder (or specific file list) and discovers distinct posts to fetch.
        Returns a list of post lookup descriptors: [{'service', 'creator_id', 'creator_name', 'post_id', 'files'}].
        """
        if not folder_path or not os.path.exists(folder_path):
            return []

        if not file_paths:
            try:
                entries = [os.path.join(folder_path, f) for f in os.listdir(folder_path)]
                file_paths = [f for f in entries if os.path.isfile(f)]
            except OSError:
                file_paths = []

        posts_map: Dict[str, Dict[str, Any]] = {}

        # Pre-query archive if available
        archive_map = {}
        if self.archive_manager and getattr(self.archive_manager, "_conn", None):
            try:
                with self.archive_manager._lock:
                    cur = self.archive_manager._conn.cursor()
                    basenames = [os.path.basename(fp) for fp in file_paths]
                    if basenames:
                        # Batch lookup in chunks of 500
                        for i in range(0, len(basenames), 500):
                            chunk = basenames[i:i + 500]
                            placeholders = ",".join("?" for _ in chunk)
                            cur.execute(
                                f"SELECT filename, service, creator_id, creator_name, post_id, post_title "
                                f"FROM downloaded_files WHERE filename IN ({placeholders})",
                                chunk
                            )
                            for row in cur.fetchall():
                                archive_map[row[0]] = {
                                    "service": row[1] or "",
                                    "creator_id": row[2] or "",
                                    "creator_name": row[3] or "",
                                    "post_id": row[4] or "",
                                    "post_title": row[5] or ""
                                }
            except Exception as e:
                logger.debug(f"Archive lookup failed during metadata detection: {e}")

        # Scan each file
        for fp in file_paths:
            fn = os.path.basename(fp)
            ctx = self.extract_context_from_path(fp)
            arch_info = archive_map.get(fn, {})

            service = arch_info.get("service") or ctx.get("service") or ""
            creator_id = arch_info.get("creator_id") or ""
            creator_name = arch_info.get("creator_name") or ctx.get("creator") or ""
            post_id = arch_info.get("post_id") or ctx.get("post_id") or ""

            if not post_id:
                continue

            # Key by post_id
            if post_id not in posts_map:
                posts_map[post_id] = {
                    "service": service,
                    "creator_id": creator_id,
                    "creator_name": creator_name,
                    "post_id": post_id,
                    "files": [fp]
                }
            else:
                posts_map[post_id]["files"].append(fp)
                if not posts_map[post_id]["service"] and service:
                    posts_map[post_id]["service"] = service
                if not posts_map[post_id]["creator_id"] and creator_id:
                    posts_map[post_id]["creator_id"] = creator_id
                if not posts_map[post_id]["creator_name"] and creator_name:
                    posts_map[post_id]["creator_name"] = creator_name

        # For posts missing creator_id, try to resolve from other posts of the same creator
        known_creators = {p["creator_name"]: (p["service"], p["creator_id"])
                          for p in posts_map.values() if p["creator_name"] and p["creator_id"]}
        for p in posts_map.values():
            if not p["creator_id"] and p["creator_name"] in known_creators:
                svc, cid = known_creators[p["creator_name"]]
                p["creator_id"] = cid
                if not p["service"]:
                    p["service"] = svc

        return list(posts_map.values())

    def fetch_and_save_metadata(
        self,
        folder_path: str,
        file_paths: Optional[List[str]] = None,
        save_json: bool = True,
        save_txt: bool = True,
        save_to_documents_subfolder: bool = False
    ) -> Dict[str, Any]:
        """
        Discovers posts in the specified folder, queries Pawchive / Kemono APIs for each post,
        writes post_info.txt and post_metadata.json, and returns details including clean captions.
        """
        results = {
            "success": True,
            "posts_found": 0,
            "posts_fetched": 0,
            "files_written": 0,
            "captions_by_post": {},
            "errors": []
        }

        posts_to_fetch = self.detect_posts_in_folder(folder_path, file_paths)
        results["posts_found"] = len(posts_to_fetch)

        if not posts_to_fetch:
            return results

        if not self.api_client:
            results["success"] = False
            results["errors"].append("API client is not configured.")
            return results

        # Determine target metadata output directories
        target_dir = folder_path
        if save_to_documents_subfolder:
            docs_dir = os.path.join(folder_path, "Documents")
            os.makedirs(docs_dir, exist_ok=True)
            target_dir = docs_dir

        for p_desc in posts_to_fetch:
            post_id = p_desc["post_id"]
            service = p_desc["service"] or "patreon"
            creator_id = p_desc["creator_id"] or p_desc["creator_name"] or ""

            post_obj = None

            # 1. Fetch from default domain (pawchive.pw)
            parsed = URLParseResult(
                raw_url=f"https://{self.default_domain}/{service}/user/{creator_id}/post/{post_id}",
                domain=self.default_domain,
                service=service,
                user_id=creator_id,
                post_id=post_id,
                is_valid=True
            )
            try:
                post_obj = self.api_client.fetch_single_post(parsed)
            except Exception as e:
                logger.debug(f"fetch_single_post failed on {self.default_domain}: {e}")

            # 2. Fallback to kemono.cr / coomer.st if pawchive returned None
            if not post_obj:
                fallback_domain = "kemono.cr" if service != "onlyfans" and service != "fansly" else "coomer.st"
                parsed_fb = URLParseResult(
                    raw_url=f"https://{fallback_domain}/{service}/user/{creator_id}/post/{post_id}",
                    domain=fallback_domain,
                    service=service,
                    user_id=creator_id,
                    post_id=post_id,
                    is_valid=True
                )
                try:
                    post_obj = self.api_client.fetch_single_post(parsed_fb)
                except Exception as e:
                    logger.debug(f"fetch_single_post fallback failed: {e}")

            if not post_obj:
                results["errors"].append(f"Post {post_id} not found on server")
                continue

            results["posts_fetched"] += 1

            # Extract fields
            title = str(post_obj.get("title") or "").strip()
            raw_content = (
                post_obj.get("captionText") or
                post_obj.get("content") or
                post_obj.get("captionHtml") or
                post_obj.get("caption") or
                ""
            )
            published = str(post_obj.get("published") or "")[:10]
            creator_name = p_desc["creator_name"] or str(post_obj.get("user") or "")
            tags = post_obj.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            # Clean caption text for filesystem and renaming tokens
            clean_caption = re.sub(r'<br\s*/?>', ' ', str(raw_content), flags=re.IGNORECASE)
            clean_caption = re.sub(r'<[^>]+>', ' ', clean_caption)
            import html as _html
            clean_caption = _html.unescape(clean_caption)
            clean_caption = re.sub(r'[\r\n\t]+', ' ', clean_caption)
            clean_caption = re.sub(r'\s+', ' ', clean_caption).strip()

            results["captions_by_post"][post_id] = clean_caption or title

            # Attached files list
            attached_files = []
            main_f = post_obj.get("file")
            if isinstance(main_f, dict) and main_f.get("name"):
                attached_files.append(main_f.get("name"))
            for att in post_obj.get("attachments") or []:
                if isinstance(att, dict) and att.get("name"):
                    attached_files.append(att.get("name"))

            # Also associate the local files we detected
            for local_fp in p_desc["files"]:
                l_fn = os.path.basename(local_fp)
                if l_fn not in attached_files:
                    attached_files.append(l_fn)

            # ── 1. Write post_metadata.json ───────────────────────────────
            if save_json:
                json_meta = {
                    "post_id": post_id,
                    "title": title,
                    "creator": creator_name,
                    "service": service,
                    "user_id": creator_id,
                    "published": published,
                    "tags": tags,
                    "caption": clean_caption,
                    "captionText": clean_caption,
                    "raw_content": raw_content,
                    "attached_files": attached_files
                }
                # Per-post JSON
                json_path = os.path.join(target_dir, f"post_{post_id}.json" if len(posts_to_fetch) > 1 else "post_metadata.json")
                try:
                    atomic_write_json(json_path, json_meta, indent=2)
                    results["files_written"] += 1
                except Exception as ex:
                    results["errors"].append(f"Could not write {json_path}: {ex}")

            # ── 2. Write or update post_info.txt ──────────────────────────
            if save_txt:
                txt_path = os.path.join(target_dir, f"post_info_{post_id}.txt" if len(posts_to_fetch) > 1 else "post_info.txt")
                txt_lines = [
                    f"Title: {title}",
                    f"Post ID: {post_id}",
                    f"Creator: {creator_name} [{service}]" if service else f"Creator: {creator_name}",
                    f"Published: {published}"
                ]
                if tags:
                    txt_lines.append(f"Tags: {', '.join(tags)}")
                txt_lines.append("")
                txt_lines.append("--- Content ---")
                txt_lines.append(clean_caption or raw_content)
                txt_lines.append("")
                if attached_files:
                    txt_lines.append("--- Attached Files ---")
                    for af in attached_files:
                        txt_lines.append(af)
                    txt_lines.append("")

                try:
                    atomic_write_text(txt_path, "\n".join(txt_lines) + "\n")
                    results["files_written"] += 1
                except Exception as ex:
                    results["errors"].append(f"Could not write {txt_path}: {ex}")

        return results
