"""
Site-Agnostic Multi-Drive Local Library Engine (`LocalLibraryService`).

Powers the "Local Disk Mode" of the Native Browser tab so users can browse ONLY
the creators and posts they have on disk with the exact same native site-like UI
as Online Mode — even when creators or posts are spread across multiple physical
drives (`C:\\`, `D:\\`, `E:\\`) or moved to another disk due to low space.

Reuses:
- `ArchiveManager` (`core/archive_manager.py`)
- `StoragePoolManager` (`core/storage_pool_manager.py`)
- `WatchlistManager` (`core/watchlist_manager.py`)
- `GLOBAL_POST_META_INDEX` (`core/post_metadata_index.py`)
- `move_folder_contents` / `count_files` (`core/folder_mover.py`)
"""

from __future__ import annotations

import os
import re
import time
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.browser_providers.base import (
    build_creator_card_dto,
    build_media_attachment_dto,
    build_post_card_dto,
)
from core.folder_mover import count_files, move_folder_contents
from core.logger import logger
from core.parser import canonical_site_url, normalize_archive_url
from core.post_metadata_index import GLOBAL_POST_META_INDEX
from core.storage_pool_manager import StoragePoolManager


_KNOWN_SERVICES = {
    "onlyfans", "fansly", "candfans", "patreon", "fanbox",
    "fantia", "boosty", "gumroad", "subscribestar", "dlsite",
    "afdian", "coomerfans", "telegram",
}

_MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif",
    ".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi",
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac",
    ".zip", ".rar", ".7z",
}

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
_POST_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})?[_\-\s]*(?:post[_\-\s]*)?([0-9a-zA-Z]{4,24})[_\-\s]+(.+)$")


def _extract_drive_label(path: str) -> str:
    if not path:
        return ""
    norm = os.path.normpath(path)
    drive, _ = os.path.splitdrive(norm)
    if drive:
        return drive.upper()
    parts = [p for p in norm.split(os.sep) if p]
    if len(parts) >= 2 and parts[0] in ("mnt", "media", "volumes"):
        return f"/{parts[0]}/{parts[1]}"
    return "/"


def _to_thumb_url(local_path: str) -> str:
    if not local_path:
        return ""
    norm = os.path.normpath(local_path).replace("\\", "/")
    return f"image://thumb/{norm}"


def _infer_service_and_name(folder_name: str) -> Tuple[str, str]:
    """Parses 'CreatorName (patreon)' or 'CreatorName [onlyfans]' or plain 'CreatorName'."""
    raw = (folder_name or "").strip()
    m = re.match(r"^(.+?)\s*[\(\[]([a-zA-Z0-9_.-]+)[\)\]]$", raw)
    if m:
        name_part, svc_part = m.group(1).strip(), m.group(2).strip().lower()
        if svc_part in _KNOWN_SERVICES:
            return svc_part, name_part
    for svc in _KNOWN_SERVICES:
        suffix = f"_{svc}"
        if raw.lower().endswith(suffix) and len(raw) > len(suffix):
            return svc, raw[: -len(suffix)].strip()
    return "local", raw


class LocalLibraryService:
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

    def is_creator_on_disk(self, service: str, creator_id: str, creator_name: str = "") -> Tuple[bool, int, List[str]]:
        svc = (service or "").strip().lower()
        cid = str(creator_id or "").strip().lower()
        cname = (creator_name or "").strip().lower()
        with self._lock:
            for c in self._creators_cache.values():
                c_svc = c.get("service", "").lower()
                if svc and c_svc != svc and c_svc != "local":
                    continue
                if (cid and c.get("creator_id", "").lower() == cid) or (cname and c.get("creator_name", "").lower() == cname):
                    return True, int(c.get("post_count") or 0), list(c.get("local_drives") or [])
        return False, 0, []

    # ── Multi-Drive Discovery & Automatic Path Healing ─────────────────────────

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

    # ── Querying Local Creators & Posts ────────────────────────────────────────

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
