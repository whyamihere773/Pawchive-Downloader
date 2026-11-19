"""
Local Library Creator/Post Querying & Multi-Drive Relocation Mixin
Decomposed from core/local_library.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.browser_providers.base import build_media_attachment_dto, build_post_card_dto
from core.folder_mover import count_files, move_folder_contents
from core.local_library_helpers import (
    _MEDIA_EXTS,
    _POST_PREFIX_RE,
    _extract_drive_label,
    _to_thumb_url,
)
from core.logger import logger
from core.post_metadata_index import GLOBAL_POST_META_INDEX


class LocalLibraryPostsRelocateMixin:
    """Serves local creators/posts listings and relocates creator folders across drives."""

    def list_local_creators(
        self,
        query: str = "",
        service: str = "all",
        drive_filter: str = "all",
        sort: str = "updated",
        offset: int = 0,
        limit: int = 50,
        force_refresh: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        if force_refresh or not self._creators_cache or (time.time() - self._last_scan_time) > 30.0:
            self.refresh_catalog(heal_moved_paths=force_refresh)

        with self._lock:
            items = list(self._creators_cache.values())

        clean_q = (query or "").strip().lower()
        clean_svc = (service or "all").strip().lower()
        clean_drv = (drive_filter or "all").strip().upper()

        filtered = []
        for c in items:
            if clean_svc not in ("", "all") and c.get("service", "").lower() != clean_svc:
                continue
            if clean_drv not in ("", "ALL") and clean_drv not in [d.upper() for d in (c.get("local_drives") or [])]:
                continue
            if clean_q:
                haystack = f"{c.get('name', '')} {c.get('creator_id', '')} {c.get('service', '')}".lower()
                if clean_q not in haystack:
                    continue
            filtered.append(c)

        if sort == "name":
            filtered.sort(key=lambda x: x.get("name", "").lower())
        elif sort == "popular" or sort == "files_desc":
            filtered.sort(key=lambda x: (int(x.get("local_file_count") or 0), int(x.get("post_count") or 0)), reverse=True)
        elif sort == "size_desc":
            filtered.sort(key=lambda x: int(x.get("local_size_bytes") or 0), reverse=True)
        else:
            filtered.sort(key=lambda x: (x.get("updated_at") or "", int(x.get("local_file_count") or 0)), reverse=True)

        total = len(filtered)
        page_slice = filtered[offset : offset + limit] if limit > 0 else filtered
        return page_slice, total

    def list_local_creator_posts(
        self,
        creator_key: str,
        query: str = "",
        drive_filter: str = "all",
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Builds normalized `PostCardDTO` items for a local creator across all drives they reside on,
        enriching each post with `post_info.txt` metadata (`GLOBAL_POST_META_INDEX`).
        """
        with self._lock:
            creator = self._creators_cache.get(creator_key)
        if not creator:
            self.refresh_catalog(heal_moved_paths=False)
            with self._lock:
                creator = self._creators_cache.get(creator_key)
        if not creator:
            return [], 0

        provider_id = creator.get("provider_id") or "pawchive"
        svc = creator.get("service") or "local"
        cid = creator.get("creator_id") or ""
        cname = creator.get("name") or cid
        archive_key = creator.get("archive_key") or ""
        local_dirs = creator.get("local_dirs") or []
        clean_q = (query or "").strip().lower()
        clean_drv = (drive_filter or "all").strip().upper()

        posts_by_id: Dict[str, Dict[str, Any]] = {}
        seen_files: Set[str] = set()

        def _norm_f(p: str) -> str:
            return os.path.normcase(os.path.normpath(p))

        # 1. Posts recorded in ArchiveManager
        if archive_key and self.archive_manager:
            try:
                arch_posts = self.archive_manager.get_creator_posts(archive_key) or []
            except Exception:
                arch_posts = []

            for ap in arch_posts:
                pid = str(ap.get("post_id") or "").strip()
                ptitle = str(ap.get("post_title") or "").strip()
                atts: List[Dict[str, Any]] = []
                post_drives: Set[str] = set()
                post_folder = ""

                for f in ap.get("files") or []:
                    fpath = str(f.get("file_path") or "").strip()
                    if not fpath or self.is_path_excluded(fpath) or not os.path.isfile(fpath):
                        continue
                    drv = _extract_drive_label(fpath)
                    if clean_drv not in ("", "ALL") and drv.upper() != clean_drv:
                        continue
                    seen_files.add(_norm_f(fpath))
                    if drv:
                        post_drives.add(drv)
                    if not post_folder:
                        post_folder = os.path.dirname(fpath)
                    file_url = "file:///" + os.path.normpath(fpath).replace("\\", "/").lstrip("/")
                    thumb_url = _to_thumb_url(fpath)
                    _disk_sz, _disk_mt = self._file_stat_size_mtime(fpath)
                    atts.append(
                        build_media_attachment_dto(
                            name=str(f.get("filename") or os.path.basename(fpath)),
                            url=file_url,
                            thumbnail_url=thumb_url,
                            local_path=fpath,
                            file_size=int(f.get("file_size") or 0) or _disk_sz,
                            modified_at=_disk_mt,
                        )
                    )

                if not atts:
                    continue

                # Enrich from post_info.txt if present
                recs = GLOBAL_POST_META_INDEX.get_folder_records(post_folder) if post_folder else []
                meta = recs[0] if recs else None
                tags = sorted(meta.all_tags) if (meta and getattr(meta, "all_tags", None)) else (sorted(meta.tags) if (meta and meta.tags) else [])
                content_snippet = (meta.content or "")[:300] if meta else ""
                full_content = (meta.content or "") if meta else ""
                published = (getattr(meta, "published", "") or str(ap.get("downloaded_at") or ""))[:10]
                if meta and meta.title and (not ptitle or ptitle == "General / Uncategorized"):
                    ptitle = meta.title
                if not pid and meta and meta.post_id:
                    pid = meta.post_id

                dto = build_post_card_dto(
                    provider_id=provider_id,
                    service=svc,
                    creator_id=cid,
                    creator_name=cname,
                    post_id=pid or ptitle or f"local_{len(posts_by_id)}",
                    title=ptitle or f"Post #{pid}",
                    url=self._build_post_online_url(provider_id, svc, cid, pid, meta=meta),
                    published_at=published,
                    content_snippet=content_snippet,
                    attachments=atts,
                    tags=tags,
                    is_on_disk=True,
                    local_folder=post_folder,
                    local_drives=sorted(post_drives),
                )
                dto["content_full"] = full_content
                posts_by_id[dto["key"]] = dto

        # 2. Scan creator's local_dirs on disk for any subfolders/files not yet in posts_by_id
        for artist_dir in local_dirs:
            if not os.path.isdir(artist_dir) or self.is_path_excluded(artist_dir):
                continue
            drv = _extract_drive_label(artist_dir)
            if clean_drv not in ("", "ALL") and drv.upper() != clean_drv:
                continue

            try:
                for root, _dirs, files in os.walk(artist_dir):
                    media_files = []
                    for fname in sorted(files):
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in _MEDIA_EXTS:
                            continue
                        full_p = os.path.join(root, fname)
                        if _norm_f(full_p) in seen_files:
                            continue
                        seen_files.add(_norm_f(full_p))
                        media_files.append(full_p)

                    if not media_files:
                        continue

                    recs = GLOBAL_POST_META_INDEX.get_folder_records(root)
                    meta = recs[0] if recs else None
                    folder_basename = os.path.basename(root)
                    m = None
                    num_m = None
                    if root == artist_dir:
                        pid = meta.post_id if (meta and meta.post_id) else "root_files"
                        ptitle = meta.title if (meta and meta.title) else f"{cname} — Root Files"
                    else:
                        m = _POST_PREFIX_RE.match(folder_basename)
                        num_m = None if m else re.match(r"^(?:post[_\-\s]*)?(\d{4,16})$", folder_basename, re.IGNORECASE)
                        pid = (meta.post_id if (meta and meta.post_id) else (m.group(2) if m else (num_m.group(1) if num_m else folder_basename)))
                        ptitle = (meta.title if (meta and meta.title) else (m.group(3) if m else folder_basename))

                    atts = []
                    latest_mt = 0.0
                    for fp in media_files:
                        if self.is_path_excluded(fp):
                            continue
                        sz = 0
                        mt = 0.0
                        try:
                            st = os.stat(fp)
                            sz = st.st_size
                            mt = float(st.st_mtime or 0.0)
                            if st.st_mtime > latest_mt:
                                latest_mt = st.st_mtime
                        except OSError:
                            pass
                        file_url = "file:///" + os.path.normpath(fp).replace("\\", "/").lstrip("/")
                        atts.append(
                            build_media_attachment_dto(
                                name=os.path.basename(fp),
                                url=file_url,
                                thumbnail_url=_to_thumb_url(fp),
                                local_path=fp,
                                file_size=sz,
                                modified_at=mt,
                            )
                        )

                    pub = (
                        getattr(meta, "published", "")[:10]
                        if (meta and getattr(meta, "published", ""))
                        else (time.strftime("%Y-%m-%d", time.localtime(latest_mt)) if latest_mt > 0 else "")
                    )
                    resolved_online_pid = (
                        meta.post_id if (meta and getattr(meta, "post_id", ""))
                        else (m.group(2) if (root != artist_dir and m) else (num_m.group(1) if (root != artist_dir and num_m) else ""))
                    )
                    dto = build_post_card_dto(
                        provider_id=provider_id,
                        service=svc,
                        creator_id=cid,
                        creator_name=cname,
                        post_id=pid,
                        title=ptitle,
                        url=self._build_post_online_url(provider_id, svc, cid, resolved_online_pid, meta=meta),
                        published_at=pub,
                        content_snippet=(meta.content or "")[:300] if meta else "",
                        attachments=atts,
                        tags=sorted(meta.tags) if (meta and meta.tags) else [],
                        is_on_disk=True,
                        local_folder=root,
                        local_drives=[drv] if drv else [],
                    )
                    dto["content_full"] = (meta.content or "") if meta else ""
                    posts_by_id[dto["key"]] = dto
            except OSError:
                pass

        all_posts = list(posts_by_id.values())
        if clean_q:
            all_posts = [
                p
                for p in all_posts
                if clean_q in p.get("title", "").lower()
                or clean_q in p.get("content_snippet", "").lower()
                or any(clean_q in t.lower() for t in (p.get("tags") or []))
            ]

        all_posts.sort(key=lambda p: (p.get("published_at") or "", p.get("post_id") or ""), reverse=True)
        total = len(all_posts)
        page_slice = all_posts[offset : offset + limit] if limit > 0 else all_posts
        return page_slice, total

    # ── Multi-Drive Creator Relocation ("Move Creator to Another Drive…") ──────

    def relocate_creator_to_drive(
        self,
        creator_key: str,
        target_root_dir: str = "",
        cancel_event: Optional[threading.Event] = None,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        destination_root_dir: str = "",
    ) -> Dict[str, Any]:
        """
        Moves all on-disk folders of a creator to `target_root_dir` (e.g., on another drive),
        merging safely via `core.folder_mover.move_folder_contents`, and atomically updating
        `ArchiveManager` (`set_file_paths`) and `WatchlistManager` (`download_dir` / `download_dirs`).
        """
        target_root_dir = target_root_dir or destination_root_dir
        with self._lock:
            creator = self._creators_cache.get(creator_key)
        if not creator:
            return {"ok": False, "error": "Creator not found in local catalog."}

        old_dirs = [d for d in (creator.get("local_dirs") or []) if d and os.path.isdir(d)]
        if not old_dirs:
            return {"ok": False, "error": "No source folders found on disk for this creator."}

        norm_target_root = os.path.normpath(target_root_dir.strip())
        folder_basename = os.path.basename(old_dirs[0])
        dest_artist_dir = os.path.normpath(os.path.join(norm_target_root, folder_basename))

        sources_to_move = [d for d in old_dirs if os.path.normcase(d) != os.path.normcase(dest_artist_dir)]
        if not sources_to_move:
            return {"ok": True, "moved": 0, "dest_dir": dest_artist_dir, "message": "Creator is already in the selected folder."}

        try:
            os.makedirs(dest_artist_dir, exist_ok=True)
        except OSError as e:
            return {"ok": False, "error": f"Could not create destination folder: {e}"}

        total_files = sum(count_files(d)[0] for d in sources_to_move)
        record_ids = self.archive_manager.records_under(sources_to_move) if self.archive_manager else {}
        path_key_fn = self.archive_manager._path_key if self.archive_manager else (lambda p: p)
        pending_updates: List[Tuple[int, str]] = []
        state = {"done": 0, "relocated": 0, "last_emit": 0.0}

        def _flush_db():
            if pending_updates and self.archive_manager:
                state["relocated"] += self.archive_manager.set_file_paths(list(pending_updates))
                pending_updates.clear()

        def _on_file_moved(old_p: str, new_p: str):
            state["done"] += 1
            if self.archive_manager:
                rid = record_ids.get(path_key_fn(old_p))
                if rid is not None:
                    pending_updates.append((rid, new_p))
                    if len(pending_updates) >= 150:
                        _flush_db()
            now = time.monotonic()
            if progress_cb and (now - state["last_emit"] >= 0.12 or state["done"] >= total_files):
                state["last_emit"] = now
                progress_cb(state["done"], max(1, total_files), os.path.basename(new_p))

        moved = dup = renamed = 0
        errors: List[str] = []
        try:
            for src_d in sources_to_move:
                res = move_folder_contents(src_d, dest_artist_dir, cancel=cancel_event, on_file=_on_file_moved)
                moved += res.moved
                dup += res.duplicates
                renamed += res.renamed
                errors.extend(res.errors)
                if cancel_event and cancel_event.is_set():
                    break
        finally:
            _flush_db()

        # Update WatchlistManager if artist is tracked
        if self.watchlist_manager:
            try:
                svc = creator.get("service", "")
                cid = creator.get("creator_id", "")
                cname = creator.get("name", "")
                for w in list(getattr(self.watchlist_manager, "entries", []) or []):
                    if (str(w.user_id).lower() == str(cid).lower() and str(w.service).lower() == str(svc).lower()) or (
                        str(w.creator_name).lower() == str(cname).lower()
                    ):
                        w.download_dir = dest_artist_dir
                        w.custom_folder = True
                        remaining = [d for d in old_dirs if os.path.isdir(d)]
                        if dest_artist_dir not in remaining:
                            remaining.insert(0, dest_artist_dir)
                        w.download_dirs = remaining
                        self.watchlist_manager.save(w)
                        break
            except Exception as e:
                logger.debug(f"[LocalLibrary] Watchlist update after move warning: {e}", category="watchlist")

        self.refresh_catalog(heal_moved_paths=False)
        return {
            "ok": len(errors) == 0,
            "moved": moved,
            "duplicates": dup,
            "renamed": renamed,
            "relocated_records": state["relocated"],
            "dest_dir": dest_artist_dir,
            "drive": _extract_drive_label(dest_artist_dir),
            "errors": errors,
        }
