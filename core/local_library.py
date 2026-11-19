"""
Site-Agnostic Multi-Drive Local Library Engine (`LocalLibraryService`).

Powers the "Local Disk Mode" of the Native Browser tab so users can browse ONLY
the creators and posts they have on disk with the exact same native site-like UI
as Online Mode — even when creators or posts are spread across multiple physical
drives or moved to another disk due to low space.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.browser_providers.base import build_creator_card_dto
from core.local_library_disk_index import LocalLibraryDiskIndexMixin
from core.local_library_helpers import (
    _IMAGE_EXTS,
    _KNOWN_SERVICES,
    _MEDIA_EXTS,
    _POST_PREFIX_RE,
    _TYPE_SUBFOLDERS,
    _extract_drive_label,
    _infer_service_and_name,
    _normalize_post_title,
    _to_thumb_url,
)
from core.local_library_posts_relocate import LocalLibraryPostsRelocateMixin
from core.logger import logger
from core.parser import canonical_site_url, normalize_archive_url
from core.post_metadata_index import GLOBAL_POST_META_INDEX
from core.storage_pool_manager import StoragePoolManager


class LocalLibraryService(LocalLibraryDiskIndexMixin, LocalLibraryPostsRelocateMixin):
    """
    Discovers, merges, and serves on-disk creators and posts across all configured drives,
    and relocates artists between drives while keeping `ArchiveManager` and `WatchlistManager` synced.
    """

    def __init__(
        self,
        archive_manager=None,
        watchlist_manager=None,
        storage_pool_manager: Optional[StoragePoolManager] = None,
        get_primary_dir: Optional[Callable[[], str]] = None,
        get_extra_roots: Optional[Callable[[], List[str]]] = None,
        get_excluded_drives: Optional[Callable[[], List[str]]] = None,
        get_excluded_roots: Optional[Callable[[], List[str]]] = None,
        get_creator_links: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.archive_manager = archive_manager
        self.watchlist_manager = watchlist_manager
        self.storage_pool_manager = storage_pool_manager
        self._get_primary_dir = get_primary_dir or (lambda: "")
        self._get_extra_roots = get_extra_roots or (lambda: [])
        self._get_excluded_drives = get_excluded_drives or (lambda: [])
        self._get_excluded_roots = get_excluded_roots or (lambda: [])
        self._get_creator_links = get_creator_links or (lambda: {})
        self._lock = threading.RLock()
        self._creators_cache: Dict[str, Dict[str, Any]] = {}
        self._on_disk_creator_keys: Set[Tuple[str, str]] = set()
        self._on_disk_post_keys: Set[Tuple[str, str]] = set()
        self._last_scan_time: float = 0.0

    # ── Configured Multi-Drive Roots ───────────────────────────────────────────

    @staticmethod
    def normalize_drive_key(value: str) -> str:
        s = str(value or "").strip()
        if not s:
            return ""
        if os.name == "nt":
            drv, _ = os.path.splitdrive(os.path.normpath(s))
            if drv:
                return drv.rstrip("\\/").upper()
            if len(s) >= 2 and s[1] == ":":
                return s[:2].upper()
            if len(s) == 1 and s.isalpha():
                return (s + ":").upper()
        norm = os.path.normpath(s)
        return norm.rstrip("\\/").lower() if os.name == "nt" else norm.rstrip("/") or "/"

    def _excluded_drive_keys(self) -> Set[str]:
        return {k for k in (self.normalize_drive_key(d) for d in (self._get_excluded_drives() or [])) if k}

    def _excluded_root_keys(self) -> Set[str]:
        out: Set[str] = set()
        for r in (self._get_excluded_roots() or []):
            if r and str(r).strip():
                norm = os.path.normpath(str(r).strip())
                out.add(norm.lower() if os.name == "nt" else norm)
        return out

    def is_path_excluded(self, path: str) -> bool:
        if not path or not str(path).strip():
            return False
        norm = os.path.normpath(str(path).strip())
        drv = self.normalize_drive_key(norm)
        if drv and drv in self._excluded_drive_keys():
            return True
        ex_roots = self._excluded_root_keys()
        if ex_roots:
            key = norm.lower() if os.name == "nt" else norm
            sep = os.path.sep
            for er in ex_roots:
                if key == er or key.startswith(er.rstrip("\\/") + sep):
                    return True
        return False

    @staticmethod
    def _file_stat_size_mtime(fpath: str) -> Tuple[int, float]:
        try:
            st = os.stat(fpath)
            return int(st.st_size or 0), float(st.st_mtime or 0.0)
        except OSError:
            return 0, 0.0

    def get_all_library_roots(self, include_excluded: bool = False) -> List[str]:
        """Returns all unique root directories where artists may live across drives."""
        roots: List[str] = []
        seen: Set[str] = set()

        def _add(p: str):
            if not p or not str(p).strip():
                return
            norm = os.path.normpath(str(p).strip())
            if not include_excluded and self.is_path_excluded(norm):
                return
            key = norm.lower() if os.name == "nt" else norm
            if key not in seen:
                seen.add(key)
                roots.append(norm)

        _add(self._get_primary_dir())
        if self.storage_pool_manager:
            _add(getattr(self.storage_pool_manager, "primary_dir", ""))
            for d in getattr(self.storage_pool_manager, "overflow_dirs", []) or []:
                _add(d)
        for r in self._get_extra_roots() or []:
            _add(r)
        return roots

    def get_available_drives_summary(self, include_excluded: bool = False) -> List[Dict[str, Any]]:
        """Returns drive capacity cards for all library roots and available system drives."""
        excluded_drvs = self._excluded_drive_keys()
        roots = self.get_all_library_roots(include_excluded=include_excluded)
        drive_map: Dict[str, Dict[str, Any]] = {}

        for root_path in roots:
            if not include_excluded and self.is_path_excluded(root_path):
                continue
            drv = _extract_drive_label(root_path)
            if not drv:
                continue
            stats = StoragePoolManager.get_drive_stats(root_path)
            if drv not in drive_map:
                drive_map[drv] = {
                    "drive": drv,
                    "root_path": root_path,
                    "roots": [root_path],
                    "exists": stats.get("exists", False),
                    "total_gb": stats.get("total_gb", 0.0),
                    "used_gb": stats.get("used_gb", 0.0),
                    "free_gb": stats.get("free_gb", 0.0),
                    "percent_used": stats.get("percent_used", 0.0),
                    "is_excluded": self.normalize_drive_key(drv) in excluded_drvs,
                }
            else:
                if root_path not in drive_map[drv]["roots"]:
                    drive_map[drv]["roots"].append(root_path)

        # On Windows, also detect other mounted drive letters so user can relocate to a fresh disk
        if os.name == "nt":
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                drv = f"{letter}:"
                if drv in drive_map:
                    continue
                is_excl = self.normalize_drive_key(drv) in excluded_drvs
                if not include_excluded and is_excl:
                    continue
                drv_root = f"{drv}\\"
                if os.path.exists(drv_root):
                    stats = StoragePoolManager.get_drive_stats(drv_root)
                    if stats.get("exists") and stats.get("total_gb", 0) > 0:
                        drive_map[drv] = {
                            "drive": drv,
                            "root_path": os.path.join(drv_root, "KemonoDownloads"),
                            "roots": [],
                            "exists": True,
                            "total_gb": stats.get("total_gb", 0.0),
                            "used_gb": stats.get("used_gb", 0.0),
                            "free_gb": stats.get("free_gb", 0.0),
                            "percent_used": stats.get("percent_used", 0.0),
                            "is_excluded": is_excl,
                        }

        return list(drive_map.values())

    @staticmethod
    def _build_post_online_url(
        provider_id: str,
        service: str,
        creator_id: str,
        post_id: str,
        meta: Any = None,
        is_dm: bool = False,
    ) -> str:
        if meta and getattr(meta, "post_url", ""):
            return normalize_archive_url(str(meta.post_url).strip())
        svc = (service or "").strip().lower()
        cid = str(creator_id or "").strip()
        pid = str(post_id or "").strip()
        if not svc or svc == "local" or not cid or not pid or pid == "root_files" or pid.startswith("local_"):
            return ""
        if provider_id == "coomerfans" or svc == "coomerfans":
            uid = cid.split("|", 1)[0].strip()
            return f"https://coomerfans.com/p/{pid}/{uid}/{svc}"
        route = "dm" if is_dm else "post"
        dom = "cum.st" if (provider_id == "cumst" or svc in ("onlyfans", "fansly", "candfans")) else "pawchive.pw"
        return canonical_site_url(dom, svc, cid, route, pid)

    # ── Fast O(1) Lookup for Online Browser Badges ─────────────────────────────


    def refresh_catalog(self, heal_moved_paths: bool = True) -> List[Dict[str, Any]]:
        """
        Aggregates all creators present on disk across:
        1. `ArchiveManager` (`download_archive.db`)
        2. `WatchlistManager` (`download_dir` + `download_dirs`)
        3. All configured library roots (`primary_dir`, `overflow_dirs`, `local_library_roots`)
        Automatically heals paths if an artist folder was moved to another drive.
        """
        roots = self.get_all_library_roots()
        existing_roots = [r for r in roots if os.path.isdir(r)]

        # Map of folder basename (lower) -> list of actual existing directories across all drives
        disk_folders_by_name: Dict[str, List[str]] = {}
        for r in existing_roots:
            try:
                for entry in os.scandir(r):
                    if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                        disk_folders_by_name.setdefault(entry.name.lower(), []).append(os.path.normpath(entry.path))
            except OSError:
                pass

        # Also include explicit Watchlist artist folders across drives
        watchlist_by_key: Dict[Tuple[str, str], Any] = {}
        watchlist_by_name: Dict[str, Any] = {}
        if self.watchlist_manager:
            try:
                for w in list(getattr(self.watchlist_manager, "entries", []) or []):
                    w_svc = (getattr(w, "service", "") or "").strip().lower()
                    w_cid = str(getattr(w, "user_id", "") or "").strip().lower()
                    w_name = (getattr(w, "creator_name", "") or "").strip().lower()
                    if w_svc and w_cid:
                        watchlist_by_key[(w_svc, w_cid)] = w
                    if w_name:
                        watchlist_by_name[w_name] = w
                    for d in [getattr(w, "download_dir", ""), *(getattr(w, "download_dirs", []) or [])]:
                        if d and os.path.isdir(d) and not self.is_path_excluded(d):
                            norm_d = os.path.normpath(d)
                            bname = os.path.basename(norm_d).lower()
                            lst = disk_folders_by_name.setdefault(bname, [])
                            if norm_d not in lst:
                                lst.append(norm_d)
            except Exception:
                pass

        merged_creators: Dict[str, Dict[str, Any]] = {}
        claimed_dirs: Set[str] = set()

        def _norm_key(p: str) -> str:
            return os.path.normcase(os.path.normpath(p))

        # 1. Pull creators from ArchiveManager
        if self.archive_manager:
            try:
                summaries = self.archive_manager.get_creator_summaries() or []
            except Exception:
                summaries = []

            for s in summaries:
                svc = (s.get("service") or "local").strip().lower()
                cid = str(s.get("creator_id") or "").strip()
                cname = (s.get("creator_name") or cid or "Unknown Creator").strip()
                archive_key = str(s.get("key") or f"{svc}|{cname.lower()}")

                # Find matching folders on disk across all drives
                candidate_dirs: List[str] = []
                w_entry = watchlist_by_key.get((svc, cid.lower())) or watchlist_by_name.get(cname.lower())
                if w_entry:
                    for wd in [getattr(w_entry, "download_dir", ""), *(getattr(w_entry, "download_dirs", []) or [])]:
                        if wd and os.path.isdir(wd) and not self.is_path_excluded(wd):
                            norm_wd = os.path.normpath(wd)
                            if norm_wd not in candidate_dirs:
                                candidate_dirs.append(norm_wd)

                for folder_variant in (
                    cname.lower(),
                    f"{cname} ({svc})".lower(),
                    f"{cname}_{svc}".lower(),
                    cid.lower(),
                ):
                    for found_d in disk_folders_by_name.get(folder_variant, []):
                        if found_d not in candidate_dirs:
                            candidate_dirs.append(found_d)

                # Inspect archive posts to discover any other drive paths or heal moved folders
                posts = []
                try:
                    posts = self.archive_manager.get_creator_posts(archive_key) or []
                except Exception:
                    posts = []

                missing_dirs_map: Dict[str, List[Tuple[str, str]]] = {}
                valid_file_count = 0
                total_bytes = 0
                cover_path = ""
                drives_set: Set[str] = set()

                for p in posts:
                    for f in p.get("files") or []:
                        fpath = str(f.get("file_path") or "").strip()
                        if not fpath or self.is_path_excluded(fpath):
                            continue
                        if os.path.isfile(fpath):
                            valid_file_count += 1
                            total_bytes += int(f.get("file_size") or 0)
                            drv = _extract_drive_label(fpath)
                            if drv:
                                drives_set.add(drv)
                            if not cover_path and os.path.splitext(fpath)[1].lower() in _IMAGE_EXTS:
                                cover_path = fpath
                            # Track its parent artist folder if under any root
                            for r in existing_roots:
                                try:
                                    rel = os.path.relpath(fpath, r)
                                    if not rel.startswith(".."):
                                        top_dir = os.path.normpath(os.path.join(r, rel.split(os.sep)[0]))
                                        if os.path.isdir(top_dir) and top_dir not in candidate_dirs:
                                            candidate_dirs.append(top_dir)
                                except ValueError:
                                    pass
                        elif heal_moved_paths and candidate_dirs:
                            # File was moved to another drive? Check if relative path exists in any candidate_dir!
                            fname = os.path.basename(fpath)
                            parent_name = os.path.basename(os.path.dirname(fpath))
                            for cdir in candidate_dirs:
                                cand1 = os.path.join(cdir, parent_name, fname)
                                cand2 = os.path.join(cdir, fname)
                                found_target = cand1 if os.path.isfile(cand1) else (cand2 if os.path.isfile(cand2) else "")
                                if found_target:
                                    old_artist_dir = os.path.dirname(os.path.dirname(fpath)) if cand1 == found_target else os.path.dirname(fpath)
                                    missing_dirs_map.setdefault(old_artist_dir, []).append((fpath, found_target))
                                    valid_file_count += 1
                                    total_bytes += int(f.get("file_size") or 0)
                                    drv = _extract_drive_label(found_target)
                                    if drv:
                                        drives_set.add(drv)
                                    if not cover_path and os.path.splitext(found_target)[1].lower() in _IMAGE_EXTS:
                                        cover_path = found_target
                                    break

                # Auto-heal relocated files in ArchiveManager
                if heal_moved_paths and missing_dirs_map:
                    all_moves = [mv for moves in missing_dirs_map.values() for mv in moves]
                    old_dirs = list(missing_dirs_map.keys())
                    try:
                        self.archive_manager.relocate_files(old_dirs, all_moves)
                        logger.info(
                            f"[LocalLibrary] Auto-healed {len(all_moves)} relocated file path(s) for '{cname}' across drives.",
                            category="archive",
                        )
                    except Exception as e:
                        logger.debug(f"[LocalLibrary] Auto-heal skipped: {e}", category="archive")

                for cdir in candidate_dirs:
                    claimed_dirs.add(_norm_key(cdir))
                    drv = _extract_drive_label(cdir)
                    if drv:
                        drives_set.add(drv)
                    if not cover_path:
                        cover_path = self._find_first_image(cdir)

                # Only include creators that actually have files or folders present on disk
                if valid_file_count == 0 and not candidate_dirs:
                    continue

                if valid_file_count == 0 and candidate_dirs:
                    # Count files directly from candidate_dirs if archive only had unverified/empty paths
                    for cdir in candidate_dirs:
                        fc, sz = self._quick_count_media(cdir)
                        valid_file_count += fc
                        total_bytes += sz
                    if valid_file_count == 0:
                        continue

                provider_id = "cumst" if svc in ("onlyfans", "fansly", "candfans") else ("coomerfans" if svc == "coomerfans" else "pawchive")
                url = (
                    normalize_archive_url(getattr(w_entry, "url", ""))
                    if (w_entry and getattr(w_entry, "url", ""))
                    else canonical_site_url("cum.st" if provider_id == "cumst" else "pawchive.pw", svc, cid)
                )

                dto = build_creator_card_dto(
                    provider_id=provider_id,
                    service=svc,
                    creator_id=cid or cname.lower(),
                    name=cname,
                    url=url,
                    avatar_url=_to_thumb_url(cover_path),
                    banner_url=_to_thumb_url(cover_path),
                    post_count=max(int(s.get("post_count") or 0), 1),
                    updated_at=str(s.get("newest_downloaded_at") or "")[:10],
                    is_on_disk=True,
                    local_post_count=max(int(s.get("post_count") or 0), 1),
                    local_file_count=valid_file_count,
                    local_size_bytes=total_bytes,
                    local_drives=sorted(drives_set),
                    local_dirs=candidate_dirs,
                )
                dto["archive_key"] = archive_key
                merged_creators[dto["key"]] = dto

        # 2. Scan remaining unclaimed artist directories across all configured drives
        #    (e.g., folders moved from another PC, or downloaded before archive tracking)
        unclaimed_by_artist: Dict[Tuple[str, str], List[str]] = {}
        for folder_lower, dir_list in disk_folders_by_name.items():
            for d in dir_list:
                if _norm_key(d) in claimed_dirs:
                    continue
                svc, clean_name = _infer_service_and_name(os.path.basename(d))
                unclaimed_by_artist.setdefault((svc, clean_name.lower()), []).append(d)

        for (svc, name_lower), dir_list in unclaimed_by_artist.items():
            total_files = 0
            total_bytes = 0
            post_folders = 0
            cover_path = ""
            drives_set: Set[str] = set()
            latest_mtime = 0.0
            display_name = os.path.basename(dir_list[0])
            _, parsed_name = _infer_service_and_name(display_name)
            if parsed_name:
                display_name = parsed_name

            # Check if any post_info.txt inside tells us the exact service & creator name
            detected_service = svc
            for d in dir_list:
                drv = _extract_drive_label(d)
                if drv:
                    drives_set.add(drv)
                fc, sz, pf, cov, mt, meta_svc, meta_creator = self._inspect_unindexed_artist_dir(d)
                total_files += fc
                total_bytes += sz
                post_folders += pf
                if not cover_path and cov:
                    cover_path = cov
                if mt > latest_mtime:
                    latest_mtime = mt
                if detected_service == "local" and meta_svc:
                    detected_service = meta_svc.lower()
                if meta_creator and display_name.lower() == name_lower:
                    display_name = meta_creator

            if total_files == 0:
                continue

            saved_links = self._get_creator_links() or {}
            folder_key = os.path.basename(dir_list[0]).strip().lower()
            saved_link = (
                saved_links.get(f"local:{name_lower}")
                or saved_links.get(name_lower)
                or saved_links.get(folder_key)
                or saved_links.get(display_name.lower())
            )
            w_entry = watchlist_by_name.get(display_name.lower()) or watchlist_by_name.get(name_lower)
            cid = str(
                (saved_link.get("creator_id") if isinstance(saved_link, dict) else "")
                or getattr(w_entry, "user_id", "")
                or display_name.lower()
            )
            if detected_service == "local":
                if isinstance(saved_link, dict) and saved_link.get("service"):
                    detected_service = str(saved_link["service"]).lower()
                elif w_entry and getattr(w_entry, "service", ""):
                    detected_service = str(w_entry.service).lower()

            if isinstance(saved_link, dict) and saved_link.get("provider_id"):
                provider_id = str(saved_link["provider_id"]).lower()
            else:
                provider_id = "cumst" if detected_service in ("onlyfans", "fansly", "candfans") else ("coomerfans" if detected_service == "coomerfans" else "pawchive")
            linked_url = (
                str(saved_link.get("url") or "") if isinstance(saved_link, dict) else ""
            ) or (getattr(w_entry, "url", "") if w_entry else "")
            upd_str = time.strftime("%Y-%m-%d", time.localtime(latest_mtime)) if latest_mtime > 0 else ""

            dto = build_creator_card_dto(
                provider_id=provider_id,
                service=detected_service,
                creator_id=cid,
                name=display_name,
                url=linked_url,
                avatar_url=_to_thumb_url(cover_path),
                banner_url=_to_thumb_url(cover_path),
                post_count=max(post_folders, 1),
                updated_at=upd_str,
                is_on_disk=True,
                local_post_count=max(post_folders, 1),
                local_file_count=total_files,
                local_size_bytes=total_bytes,
                local_drives=sorted(drives_set),
                local_dirs=dir_list,
            )
            dto["archive_key"] = ""
            # Merge if key already exists
            if dto["key"] in merged_creators:
                existing = merged_creators[dto["key"]]
                for d in dir_list:
                    if d not in existing["local_dirs"]:
                        existing["local_dirs"].append(d)
                for drv in drives_set:
                    if drv not in existing["local_drives"]:
                        existing["local_drives"].append(drv)
                existing["local_file_count"] += total_files
                existing["local_size_bytes"] += total_bytes
            else:
                merged_creators[dto["key"]] = dto

        with self._lock:
            self._creators_cache = merged_creators
            self._last_scan_time = time.time()

        return list(merged_creators.values())

    @staticmethod
    def _find_first_image(folder: str) -> str:
        try:
            for root, _dirs, files in os.walk(folder):
                for f in sorted(files):
                    if os.path.splitext(f)[1].lower() in _IMAGE_EXTS:
                        return os.path.join(root, f)
        except OSError:
            pass
        return ""

    @staticmethod
    def _quick_count_media(folder: str) -> Tuple[int, int]:
        count = 0
        size = 0
        try:
            for root, _dirs, files in os.walk(folder):
                for f in files:
                    if os.path.splitext(f)[1].lower() in _MEDIA_EXTS:
                        count += 1
                        try:
                            size += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            pass
        except OSError:
            pass
        return count, size

    @staticmethod
    def _inspect_unindexed_artist_dir(folder: str) -> Tuple[int, int, int, str, float, str, str]:
        files_count = 0
        total_bytes = 0
        post_folders = 0
        cover_path = ""
        latest_mtime = 0.0
        meta_svc = ""
        meta_creator = ""
        try:
            for root, dirs, files in os.walk(folder):
                if root == folder:
                    post_folders = len([d for d in dirs if not d.startswith(".")])
                if "post_info.txt" in files and not meta_svc:
                    recs = GLOBAL_POST_META_INDEX.get_folder_records(root)
                    meta = recs[0] if recs else None
                    if meta:
                        meta_svc = meta.service or ""
                        meta_creator = meta.creator or ""
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in _MEDIA_EXTS:
                        continue
                    full_p = os.path.join(root, f)
                    files_count += 1
                    try:
                        st = os.stat(full_p)
                        total_bytes += st.st_size
                        if st.st_mtime > latest_mtime:
                            latest_mtime = st.st_mtime
                    except OSError:
                        pass
                    if not cover_path and ext in _IMAGE_EXTS:
                        cover_path = full_p
        except OSError:
            pass
        return files_count, total_bytes, post_folders, cover_path, latest_mtime, meta_svc, meta_creator
