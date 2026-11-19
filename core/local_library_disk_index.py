"""
Local Library On-Disk Post Presence Index & Online Badge Evaluator Mixin
Decomposed from core/local_library.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.local_library_helpers import (
    _MEDIA_EXTS,
    _POST_PREFIX_RE,
    _TYPE_SUBFOLDERS,
    _extract_drive_label,
    _normalize_post_title,
)
from core.post_metadata_index import GLOBAL_POST_META_INDEX


class LocalLibraryDiskIndexMixin:
    """Builds per-post physical disk presence indexes for Online Mode badges."""

    def _find_matching_local_creators(
        self,
        service: str,
        creator_id: str,
        creator_name: str = "",
        ensure_loaded: bool = False,
    ) -> List[Dict[str, Any]]:
        if ensure_loaded:
            with self._lock:
                needs_load = (not self._creators_cache and self._last_scan_time == 0.0)
            if needs_load:
                try:
                    self.refresh_catalog(heal_moved_paths=False)
                except Exception:
                    pass

        svc = (service or "").strip().lower()
        cid = str(creator_id or "").strip().lower()
        cname = (creator_name or "").strip().lower()
        matches: List[Dict[str, Any]] = []
        with self._lock:
            for c in self._creators_cache.values():
                c_svc = (c.get("service") or "").strip().lower()
                if svc and c_svc != svc and c_svc != "local":
                    continue
                if (cid and (c.get("creator_id") or "").strip().lower() == cid) or (
                    cname and (c.get("creator_name") or "").strip().lower() == cname
                ):
                    matches.append(dict(c))
        return matches

    def is_creator_on_disk(self, service: str, creator_id: str, creator_name: str = "") -> Tuple[bool, int, List[str]]:
        matches = self._find_matching_local_creators(service, creator_id, creator_name, ensure_loaded=False)
        if not matches:
            return False, 0, []
        total_posts = sum(int(m.get("post_count") or 0) for m in matches)
        drives = sorted({d for m in matches for d in (m.get("local_drives") or []) if d})
        return True, total_posts, drives

    def get_creator_post_disk_index(
        self,
        service: str,
        creator_id: str,
        creator_name: str = "",
    ) -> Dict[str, Any]:
        """
        Builds a per-post physical disk presence index for a creator across all drives
        and `ArchiveManager`, used in Online Mode to outline posts as:
          - "complete" (green): all files physically present on disk
          - "partial"  (yellow): some files physically present, others pruned/skipped
          - "none"     (neutral): not present on disk
        """
        matches = self._find_matching_local_creators(service, creator_id, creator_name, ensure_loaded=True)
        if not matches:
            return {
                "creator_on_disk": False,
                "by_post_id": {},
                "by_date_title": {},
                "by_title": {},
                "local_drives": [],
            }

        by_post_id: Dict[str, Dict[str, Any]] = {}
        by_date_title: Dict[Tuple[str, str], Dict[str, Any]] = {}
        by_title: Dict[str, Dict[str, Any]] = {}
        seen_files: Set[str] = set()
        creator_drives: Set[str] = set()

        def _norm_f(p: str) -> str:
            return os.path.normcase(os.path.normpath(p))

        def _get_or_create_bucket(pid: str, pub_date: str, title: str) -> Dict[str, Any]:
            clean_pid = str(pid or "").strip()
            clean_date = str(pub_date or "").strip()[:10]
            ntitle = _normalize_post_title(title)

            bucket = None
            if clean_pid and clean_pid in by_post_id:
                bucket = by_post_id[clean_pid]
            elif clean_date and ntitle and (clean_date, ntitle) in by_date_title:
                bucket = by_date_title[(clean_date, ntitle)]
            elif len(ntitle) >= 4 and ntitle in by_title:
                bucket = by_title[ntitle]

            if bucket is None:
                bucket = {
                    "paths": set(),
                    "archived_count": 0,
                    "has_folder": False,
                    "folder": "",
                    "drives": set(),
                }
            if clean_pid:
                by_post_id[clean_pid] = bucket
            if clean_date and ntitle:
                by_date_title[(clean_date, ntitle)] = bucket
            if len(ntitle) >= 4:
                by_title[ntitle] = bucket
            return bucket

        # 1. Inspect ArchiveManager posts (checks actual os.path.isfile so pruned files reduce count!)
        archive_keys = list(dict.fromkeys(str(m.get("archive_key") or "").strip() for m in matches if m.get("archive_key")))
        local_dirs: List[str] = []
        for m in matches:
            for d in m.get("local_drives") or []:
                if d:
                    creator_drives.add(d)
            for ld in m.get("local_dirs") or []:
                if ld and os.path.isdir(ld) and not self.is_path_excluded(ld) and ld not in local_dirs:
                    local_dirs.append(ld)

        if self.archive_manager:
            for akey in archive_keys:
                try:
                    arch_posts = self.archive_manager.get_creator_posts(akey) or []
                except Exception:
                    arch_posts = []
                for ap in arch_posts:
                    pid = str(ap.get("post_id") or "").strip()
                    ptitle = str(ap.get("post_title") or "").strip()
                    pub = str(ap.get("downloaded_at") or "")[:10]
                    files_list = ap.get("files") or []
                    existing_in_post: List[str] = []
                    post_folder = ""
                    for f in files_list:
                        fpath = str(f.get("file_path") or "").strip()
                        if not fpath or self.is_path_excluded(fpath):
                            continue
                        if os.path.isfile(fpath):
                            existing_in_post.append(fpath)
                            if not post_folder:
                                post_folder = os.path.dirname(fpath)
                    if post_folder:
                        recs = GLOBAL_POST_META_INDEX.get_folder_records(post_folder)
                        if recs:
                            meta0 = recs[0]
                            if not pid and getattr(meta0, "post_id", ""):
                                pid = str(meta0.post_id).strip()
                            if (not ptitle or ptitle == "General / Uncategorized") and getattr(meta0, "title", ""):
                                ptitle = str(meta0.title).strip()
                            if getattr(meta0, "published", ""):
                                pub = str(meta0.published)[:10]

                    if not existing_in_post and not pid and not ptitle:
                        continue
                    bucket = _get_or_create_bucket(pid, pub, ptitle)
                    bucket["archived_count"] = max(bucket["archived_count"], len(files_list))
                    for fp in existing_in_post:
                        nf = _norm_f(fp)
                        seen_files.add(nf)
                        bucket["paths"].add(nf)
                        drv = _extract_drive_label(fp)
                        if drv:
                            bucket["drives"].add(drv)
                            creator_drives.add(drv)
                    if post_folder and not bucket["folder"]:
                        bucket["folder"] = post_folder
                    if post_folder and os.path.isdir(post_folder):
                        bucket["has_folder"] = True

        # 2. Walk local_dirs to catch any unindexed/relocated files and text-only post folders
        for artist_dir in local_dirs:
            try:
                for root, _dirs, files in os.walk(artist_dir):
                    if self.is_path_excluded(root):
                        continue
                    # Collapse file-type grouping subfolders (/Images, /Videos, etc.) into their parent post folder
                    folder_base = os.path.basename(root)
                    if root != artist_dir and folder_base.lower() in _TYPE_SUBFOLDERS:
                        post_dir = os.path.dirname(root)
                    else:
                        post_dir = root

                    recs = GLOBAL_POST_META_INDEX.get_folder_records(post_dir) if post_dir != artist_dir else []
                    # Also handle multi-post combined post_info.txt attribution by filename
                    att_to_rec: Dict[str, Any] = {}
                    if len(recs) > 1:
                        for r in recs:
                            for att_name in (getattr(r, "attached_files", None) or []):
                                att_to_rec[str(att_name).strip().lower()] = r

                    post_dir_base = os.path.basename(post_dir)
                    m_pref = _POST_PREFIX_RE.match(post_dir_base) if post_dir != artist_dir else None
                    m_num = (
                        None
                        if (m_pref or post_dir == artist_dir)
                        else re.match(r"^(?:post[_\-\s]*)?(\d{4,16})$", post_dir_base, re.IGNORECASE)
                    )
                    default_rec = recs[0] if len(recs) == 1 else None
                    default_pid = (
                        str(default_rec.post_id).strip()
                        if (default_rec and getattr(default_rec, "post_id", ""))
                        else (m_pref.group(2) if m_pref else (m_num.group(1) if m_num else ""))
                    )
                    default_title = (
                        str(default_rec.title).strip()
                        if (default_rec and getattr(default_rec, "title", ""))
                        else (m_pref.group(3) if m_pref else (post_dir_base if post_dir != artist_dir else ""))
                    )
                    default_pub = (
                        str(default_rec.published)[:10]
                        if (default_rec and getattr(default_rec, "published", ""))
                        else (m_pref.group(1) if (m_pref and m_pref.group(1)) else "")
                    )

                    # Text-only post folders that contain post_info.txt still count as present
                    if recs:
                        for r in recs:
                            r_pid = str(getattr(r, "post_id", "") or "").strip()
                            r_title = str(getattr(r, "title", "") or "").strip()
                            r_pub = str(getattr(r, "published", "") or "")[:10]
                            if r_pid or r_title:
                                b = _get_or_create_bucket(r_pid, r_pub, r_title)
                                b["has_folder"] = True
                                if not b["folder"]:
                                    b["folder"] = post_dir
                                drv = _extract_drive_label(post_dir)
                                if drv:
                                    b["drives"].add(drv)
                                    creator_drives.add(drv)

                    for fname in files:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext not in _MEDIA_EXTS:
                            continue
                        full_p = os.path.join(root, fname)
                        nf = _norm_f(full_p)
                        if nf in seen_files:
                            continue
                        seen_files.add(nf)

                        rec = att_to_rec.get(fname.lower()) or default_rec
                        pid = (
                            str(getattr(rec, "post_id", "") or "").strip()
                            if rec is not None
                            else default_pid
                        )
                        ptitle = (
                            str(getattr(rec, "title", "") or "").strip()
                            if rec is not None
                            else default_title
                        )
                        pub = (
                            str(getattr(rec, "published", "") or "")[:10]
                            if rec is not None
                            else default_pub
                        )
                        if not pid and not ptitle:
                            continue
                        b = _get_or_create_bucket(pid, pub, ptitle)
                        b["paths"].add(nf)
                        b["has_folder"] = True
                        if not b["folder"]:
                            b["folder"] = post_dir
                        drv = _extract_drive_label(full_p)
                        if drv:
                            b["drives"].add(drv)
                            creator_drives.add(drv)
            except OSError:
                pass

        return {
            "creator_on_disk": True,
            "by_post_id": by_post_id,
            "by_date_title": by_date_title,
            "by_title": by_title,
            "local_drives": sorted(creator_drives),
        }

    @staticmethod
    def evaluate_online_post_disk_status(
        post_dto: Dict[str, Any],
        disk_index: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compares an online `PostCardDTO` against the creator's `disk_index` and returns:
          - disk_status: "complete" (green) | "partial" (yellow) | "none" (neutral)
          - is_on_disk: bool
          - local_file_count: int (physical files currently on disk)
          - expected_file_count: int (online attachments count)
          - local_folder: str
          - local_drives: list[str]
        """
        atts = post_dto.get("attachments") or []
        expected = max(len(atts), int(post_dto.get("file_count") or 0))
        if not disk_index or not disk_index.get("creator_on_disk"):
            return {
                "disk_status": "none",
                "is_on_disk": False,
                "local_file_count": 0,
                "expected_file_count": expected,
                "local_folder": "",
                "local_drives": [],
            }

        pid = str(post_dto.get("post_id") or "").strip()
        pub = str(post_dto.get("published_at") or "").strip()[:10]
        ntitle = _normalize_post_title(str(post_dto.get("title") or ""))

        entry = None
        if pid and pid in (disk_index.get("by_post_id") or {}):
            entry = disk_index["by_post_id"][pid]
        elif pub and ntitle and (pub, ntitle) in (disk_index.get("by_date_title") or {}):
            entry = disk_index["by_date_title"][(pub, ntitle)]
        elif len(ntitle) >= 4 and ntitle in (disk_index.get("by_title") or {}):
            entry = disk_index["by_title"][ntitle]

        if not entry:
            return {
                "disk_status": "none",
                "is_on_disk": False,
                "local_file_count": 0,
                "expected_file_count": expected,
                "local_folder": "",
                "local_drives": [],
            }

        local_count = len(entry.get("paths") or ())
        archived_count = int(entry.get("archived_count") or 0)
        has_folder = bool(entry.get("has_folder"))

        if expected > 0:
            if local_count <= 0:
                status = "none"
            elif local_count >= expected:
                status = "complete"
            else:
                status = "partial"
        else:
            if local_count > 0:
                status = "partial" if archived_count > local_count else "complete"
            elif has_folder:
                status = "complete"
            else:
                status = "none"

        return {
            "disk_status": status,
            "is_on_disk": status in ("complete", "partial"),
            "local_file_count": local_count,
            "expected_file_count": expected,
            "local_folder": str(entry.get("folder") or "") if status != "none" else "",
            "local_drives": sorted(entry.get("drives") or ()) if status != "none" else [],
        }
