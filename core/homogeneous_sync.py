"""
Homogeneous Creator Sync Engine for Browser Mode.

Automatically locates a creator's existing on-disk folder across all drives, reconstructs
their exact folder/naming/format `FilterOptions` (combining saved Watchlist metadata with
physical filesystem layout inference so downloads stay 100% homogeneous), and filters
fetched online posts to only those missing from disk and/or mismatched in file count/size.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.downloader_models import is_post_unimported_on_pawchive, needs_full_size_upgrade
from core.filter_options import (
    FilterOptions,
    MediaTypes,
    normalize_date_folder_mode,
    normalize_disk_sync_mode,
)
from core.folder_naming import is_creator_folder, pick_creator_folder
from core.local_library_helpers import _MEDIA_EXTS, _POST_PREFIX_RE, _normalize_post_title
from core.logger import logger
from core.post_metadata_index import GLOBAL_POST_META_INDEX

_YEAR_DIR_RE = re.compile(r"^(19\d\d|20\d\d)$")
_YEAR_MONTH_DIR_RE = re.compile(r"^(19\d\d|20\d\d)-(0[1-9]|1[0-2])$")
_MONTH_SUBDIR_RE = re.compile(r"^(0[1-9]|1[0-2])\s*-\s*[A-Za-z]+$")
_DATE_PREFIX_DIR_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2}\]\s+.+")
_INDEX_PREFIX_FILE_RE = re.compile(r"^\d{2,4}_.+")
_TYPE_DIRS_CANON = {"images", "video", "videos", "archive", "archives", "audio", "other"}
_IMAGE_CHECK_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp", ".tif", ".tiff"}


def _count_media_quick(folder: str, limit: int = 400) -> int:
    """Fast bounded count of media files inside `folder` to pick the primary creator directory."""
    if not folder or not os.path.isdir(folder):
        return 0
    total = 0
    try:
        for _root, _dirs, files in os.walk(folder):
            for fn in files:
                if os.path.splitext(fn)[1].lower() in _MEDIA_EXTS:
                    total += 1
                    if total >= limit:
                        return total
    except OSError:
        pass
    return total


def infer_folder_layout_overrides(artist_dir: str) -> Dict[str, Any]:
    """Inspect an existing creator directory on disk and infer layout/naming overrides
    so newly synced posts land in the exact same structure as existing ones."""
    if not artist_dir or not os.path.isdir(artist_dir):
        return {}

    overrides: Dict[str, Any] = {}
    try:
        top_entries = list(os.scandir(artist_dir))
    except OSError:
        return {}
    if not top_entries:
        return {}

    top_dirs = [e for e in top_entries if e.is_dir(follow_symlinks=False)]
    top_files = [e for e in top_entries if e.is_file(follow_symlinks=False)]
    top_media_files = [
        e.name for e in top_files
        if os.path.splitext(e.name)[1].lower() in _MEDIA_EXTS
    ]

    # 1. Detect Date Folder Sorting (`year_month`, `month`, `year`, or `none`)
    year_dirs = [d for d in top_dirs if _YEAR_DIR_RE.match(d.name)]
    ym_dirs = [d for d in top_dirs if _YEAR_MONTH_DIR_RE.match(d.name)]
    content_roots: List[str] = []

    if ym_dirs and len(ym_dirs) >= max(1, len(top_dirs) // 3):
        overrides["date_folder_mode"] = "month"
        content_roots = [d.path for d in ym_dirs[:8]]
    elif year_dirs and len(year_dirs) >= max(1, len(top_dirs) // 3):
        saw_month_sub = False
        sub_roots: List[str] = []
        for yd in year_dirs[:6]:
            try:
                subs = [s for s in os.scandir(yd.path) if s.is_dir(follow_symlinks=False)]
            except OSError:
                subs = []
            m_subs = [s for s in subs if _MONTH_SUBDIR_RE.match(s.name)]
            if m_subs:
                saw_month_sub = True
                sub_roots.extend(s.path for s in m_subs[:4])
            else:
                sub_roots.append(yd.path)
        overrides["date_folder_mode"] = "year_month" if saw_month_sub else "year"
        content_roots = sub_roots or [d.path for d in year_dirs[:6]]
    else:
        overrides["date_folder_mode"] = "none"
        content_roots = [artist_dir]

    # 2. Inspect content roots for `group_file_type`, `subfolder_per_post`, and `date_prefix`
    sample_dirs: List[os.DirEntry] = []
    flat_media_names: List[str] = []
    saw_post_info = any(e.name.lower() == "post_info.txt" for e in top_files)

    for c_root in content_roots[:8]:
        try:
            entries = list(os.scandir(c_root))
        except OSError:
            continue
        for e in entries:
            if e.is_dir(follow_symlinks=False):
                sample_dirs.append(e)
            elif e.is_file(follow_symlinks=False):
                if e.name.lower() == "post_info.txt":
                    saw_post_info = True
                elif os.path.splitext(e.name)[1].lower() in _MEDIA_EXTS:
                    flat_media_names.append(e.name)

    type_dirs = [d for d in sample_dirs if d.name.lower() in _TYPE_DIRS_CANON]
    non_type_dirs = [d for d in sample_dirs if d.name.lower() not in _TYPE_DIRS_CANON and d.name != "Unknown Date"]

    post_dirs_to_check: List[os.DirEntry] = []
    if type_dirs and not non_type_dirs:
        overrides["group_file_type"] = "creator"
        for td in type_dirs[:4]:
            try:
                t_entries = list(os.scandir(td.path))
            except OSError:
                continue
            for te in t_entries:
                if te.is_dir(follow_symlinks=False):
                    post_dirs_to_check.append(te)
                elif te.is_file(follow_symlinks=False) and os.path.splitext(te.name)[1].lower() in _MEDIA_EXTS:
                    flat_media_names.append(te.name)
    else:
        post_dirs_to_check = non_type_dirs[:25]

    if post_dirs_to_check:
        overrides["subfolder_per_post"] = True
        dated_cnt = sum(1 for d in post_dirs_to_check if _DATE_PREFIX_DIR_RE.match(d.name))
        overrides["date_prefix"] = dated_cnt >= max(1, len(post_dirs_to_check) // 2)

        # Check inside sample post subfolders for `group_file_type == "post"`, filenames, WebP, and post_info.txt
        nested_type_hits = 0
        sampled_files: List[str] = []
        orig_non_webp_in_info = False
        for pd in post_dirs_to_check[:12]:
            try:
                p_entries = list(os.scandir(pd.path))
            except OSError:
                continue
            p_subdirs = [pe for pe in p_entries if pe.is_dir(follow_symlinks=False)]
            if p_subdirs and all(pe.name.lower() in _TYPE_DIRS_CANON for pe in p_subdirs):
                nested_type_hits += 1
                for psd in p_subdirs[:3]:
                    try:
                        for f_e in os.scandir(psd.path):
                            if f_e.is_file(follow_symlinks=False) and os.path.splitext(f_e.name)[1].lower() in _MEDIA_EXTS:
                                sampled_files.append(f_e.name)
                    except OSError:
                        pass
            for pe in p_entries:
                if pe.is_file(follow_symlinks=False):
                    if pe.name.lower() == "post_info.txt":
                        saw_post_info = True
                        try:
                            with open(pe.path, "r", encoding="utf-8", errors="replace") as _inf:
                                if re.search(r"\.(?:png|jpe?g)\b", _inf.read(16384), re.IGNORECASE):
                                    orig_non_webp_in_info = True
                        except OSError:
                            pass
                    elif os.path.splitext(pe.name)[1].lower() in _MEDIA_EXTS:
                        sampled_files.append(pe.name)

        if "group_file_type" not in overrides:
            overrides["group_file_type"] = "post" if nested_type_hits >= max(1, min(3, len(post_dirs_to_check)) // 2) else "none"
    elif flat_media_names or top_media_files:
        overrides["subfolder_per_post"] = False
        if "group_file_type" not in overrides:
            overrides["group_file_type"] = "none"
        sampled_files = (flat_media_names + top_media_files)[:40]
        orig_non_webp_in_info = False
    else:
        sampled_files = []
        orig_non_webp_in_info = False

    # 3. Infer file numbering & WebP homogeneity from sampled media files
    if sampled_files:
        idx_hits = sum(1 for fn in sampled_files if _INDEX_PREFIX_FILE_RE.match(fn))
        if idx_hits >= max(2, int(len(sampled_files) * 0.7)):
            overrides["file_index_prefix"] = True
        elif idx_hits == 0 and len(sampled_files) >= 3:
            overrides["file_index_prefix"] = False

        imgs = [fn for fn in sampled_files if os.path.splitext(fn)[1].lower() in _IMAGE_CHECK_EXTS]
        if len(imgs) >= 3:
            webp_cnt = sum(1 for fn in imgs if fn.lower().endswith(".webp"))
            if webp_cnt >= int(len(imgs) * 0.85) and orig_non_webp_in_info:
                overrides["compress_to_webp"] = True
            elif webp_cnt == 0:
                overrides["compress_to_webp"] = False

    if saw_post_info:
        overrides["save_post_metadata"] = True

    return overrides


def format_homogeneous_summary(options: FilterOptions, on_disk: bool) -> str:
    """Short human-readable summary of the reused layout & naming configuration."""
    parts: List[str] = []
    parts.append("Existing folder on disk" if on_disk else "New creator folder")
    if options.subfolder_per_post:
        parts.append("Subfolder per post" + (" ([Date] prefix)" if options.date_prefix else ""))
    else:
        parts.append("Flat creator folder")
    dfm = getattr(options, "date_folder_mode", "none")
    if dfm == "year":
        parts.append("Sort: Year")
    elif dfm == "month":
        parts.append("Sort: Month")
    elif dfm == "year_month":
        parts.append("Sort: Year → Month")
    gft = getattr(options, "group_file_type", "none")
    if gft in ("creator", "post"):
        parts.append(f"Group by type ({gft})")
    if options.file_index_prefix:
        parts.append("Numbered files")
    if options.compress_to_webp:
        parts.append("WebP")
    return "  •  ".join(parts)


def resolve_homogeneous_creator_context(
    *,
    service: str,
    user_id: str,
    creator_name: str,
    base_options: FilterOptions,
    fallback_dir: str,
    disk_sync_mode: str = "missing_or_mismatched",
    local_library=None,
    watchlist_manager=None,
    explicit_local_dirs: Optional[List[str]] = None,
    create_creator_folder: bool = True,
) -> Dict[str, Any]:
    """Locate a creator's existing directory on disk and construct homogeneous `FilterOptions`."""
    from core.filter_engine import FilterEngine

    svc = (service or "").strip().lower()
    uid = str(user_id or "").strip()
    cname = (creator_name or uid or "Creator").strip()
    clean_c = FilterEngine.clean_filesystem_text(cname, max_len=80, fallback="creator")
    norm_sync = normalize_disk_sync_mode(disk_sync_mode)

    # 1. Discover existing on-disk creator directory across LocalLibrary + Watchlist + explicit hints
    candidate_dirs: List[str] = []
    for d in (explicit_local_dirs or []):
        if d and os.path.isdir(d) and d not in candidate_dirs:
            candidate_dirs.append(os.path.normpath(d))

    if local_library is not None:
        try:
            matches = local_library._find_matching_local_creators(svc, uid, cname, ensure_loaded=True)
            for m in matches:
                for ld in (m.get("local_dirs") or []):
                    if ld and os.path.isdir(ld):
                        nld = os.path.normpath(ld)
                        if nld not in candidate_dirs:
                            candidate_dirs.append(nld)
        except Exception as ex:
            logger.debug(f"[HomogeneousSync] LocalLibrary lookup skipped: {ex}", category="downloader")

    wl_entry = None
    if watchlist_manager is not None and uid and svc:
        try:
            wl_entry = watchlist_manager._find(uid, svc)
        except Exception:
            wl_entry = None

    if wl_entry and getattr(wl_entry, "download_dir", ""):
        wdir = os.path.normpath(str(wl_entry.download_dir).strip())
        if os.path.isdir(wdir) and wdir not in candidate_dirs:
            candidate_dirs.append(wdir)
        for extra_d in (getattr(wl_entry, "download_dirs", None) or []):
            if extra_d and os.path.isdir(extra_d):
                ned = os.path.normpath(str(extra_d))
                if ned not in candidate_dirs:
                    candidate_dirs.append(ned)

    existing_artist_dir = ""
    if len(candidate_dirs) == 1:
        existing_artist_dir = candidate_dirs[0]
    elif len(candidate_dirs) > 1:
        existing_artist_dir = max(candidate_dirs, key=_count_media_quick)

    on_disk = bool(existing_artist_dir and os.path.isdir(existing_artist_dir))
    if on_disk:
        artist_dir = existing_artist_dir
    else:
        clean_fb = os.path.normpath(str(fallback_dir or "").strip()) if str(fallback_dir or "").strip() else ""
        if not clean_fb:
            artist_dir = ""
        elif create_creator_folder:
            if is_creator_folder(os.path.basename(clean_fb), clean_c, svc):
                artist_dir = clean_fb
            else:
                artist_dir = pick_creator_folder(clean_fb, clean_c, svc)
        else:
            artist_dir = clean_fb

    # 2. Build homogeneous FilterOptions: base -> saved Watchlist creator options -> physical folder inference
    opts_dict = base_options.to_dict()
    opts_dict["date_after"] = ""
    opts_dict["date_before"] = ""
    opts_dict["page_start"] = 1
    opts_dict["page_end"] = 999999
    opts_dict["characters"] = ""
    opts_dict["force_redownload"] = False

    saved_opts = getattr(wl_entry, "options", None) if wl_entry is not None else None
    has_explicit_custom = False
    if isinstance(saved_opts, dict) and saved_opts:
        has_explicit_custom = bool(saved_opts.get("use_custom_settings"))
        merged_saved = dict(saved_opts)
        merged_saved.pop("use_custom_settings", None)
        # Never carry over transient page/date bounds when syncing full missing/mismatched state
        for k_skip in ("date_after", "date_before", "page_start", "page_end", "force_redownload"):
            merged_saved.pop(k_skip, None)
        opts_dict.update(merged_saved)

    if on_disk:
        inferred = infer_folder_layout_overrides(artist_dir)
        if inferred:
            if has_explicit_custom:
                # Even with custom Watchlist settings, fill any structural keys missing from older configs
                for k, v in inferred.items():
                    if k not in (saved_opts or {}):
                        opts_dict[k] = v
            else:
                # Physical disk structure is ground truth so new files never clash with existing folders
                opts_dict.update(inferred)

    if norm_sync in ("missing_or_mismatched", "mismatched_only"):
        opts_dict["redownload_small_files"] = True
    opts_dict["disk_sync_mode"] = norm_sync

    homog_opts = FilterOptions.from_dict(opts_dict)
    return {
        "on_disk": on_disk,
        "artist_dir": artist_dir,
        "base_dir": os.path.dirname(os.path.abspath(artist_dir)) if artist_dir else fallback_dir,
        "options": homog_opts,
        "summary": format_homogeneous_summary(homog_opts, on_disk),
    }


def _scan_single_dir_into_index(artist_dir: str) -> Dict[str, Any]:
    """Build a lightweight disk presence index directly from `artist_dir` when LocalLibrary has no entry yet."""
    by_post_id: Dict[str, Dict[str, Any]] = {}
    by_date_title: Dict[Tuple[str, str], Dict[str, Any]] = {}
    by_title: Dict[str, Dict[str, Any]] = {}

    if not artist_dir or not os.path.isdir(artist_dir):
        return {
            "creator_on_disk": False,
            "by_post_id": by_post_id,
            "by_date_title": by_date_title,
            "by_title": by_title,
            "all_sizes_by_stem": {},
        }

    all_sizes_by_name: Dict[str, List[Tuple[str, int]]] = {}

    def _bucket(pid: str, pub: str, title: str) -> Dict[str, Any]:
        cpid = str(pid or "").strip()
        cpub = str(pub or "").strip()[:10]
        nt = _normalize_post_title(title)
        b = (
            by_post_id.get(cpid)
            or ((cpub and nt) and by_date_title.get((cpub, nt)))
            or ((len(nt) >= 4) and by_title.get(nt))
        )
        if b is None:
            b = {"paths": set(), "file_map": {}, "archived_count": 0, "has_folder": True, "folder": ""}
        if cpid:
            by_post_id[cpid] = b
        if cpub and nt:
            by_date_title[(cpub, nt)] = b
        if len(nt) >= 4:
            by_title[nt] = b
        return b

    try:
        for root, _dirs, files in os.walk(artist_dir):
            folder_base = os.path.basename(root)
            post_dir = os.path.dirname(root) if (root != artist_dir and folder_base.lower() in _TYPE_DIRS_CANON) else root
            recs = GLOBAL_POST_META_INDEX.get_folder_records(post_dir) if post_dir != artist_dir else []
            pbase = os.path.basename(post_dir)
            m_pref = _POST_PREFIX_RE.match(pbase) if post_dir != artist_dir else None
            def_rec = recs[0] if len(recs) == 1 else None
            dpid = str(def_rec.post_id).strip() if (def_rec and getattr(def_rec, "post_id", "")) else (m_pref.group(2) if m_pref else "")
            dtitle = str(def_rec.title).strip() if (def_rec and getattr(def_rec, "title", "")) else (m_pref.group(3) if m_pref else (pbase if post_dir != artist_dir else ""))
            dpub = str(def_rec.published)[:10] if (def_rec and getattr(def_rec, "published", "")) else (m_pref.group(1) if (m_pref and m_pref.group(1)) else "")

            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in _MEDIA_EXTS:
                    continue
                fp = os.path.join(root, fn)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    sz = 0
                norm_fp = os.path.normcase(os.path.normpath(fp))
                bare_low = re.sub(r"^\d+_", "", fn.lower())
                all_sizes_by_name.setdefault(fn.lower(), []).append((fp, sz))
                if bare_low != fn.lower():
                    all_sizes_by_name.setdefault(bare_low, []).append((fp, sz))

                if dpid or dtitle:
                    b = _bucket(dpid, dpub, dtitle)
                    b["paths"].add(norm_fp)
                    b["file_map"][fn.lower()] = (fp, sz)
                    b["file_map"][bare_low] = (fp, sz)
                    if not b["folder"]:
                        b["folder"] = post_dir
    except OSError:
        pass

    return {
        "creator_on_disk": bool(by_post_id or by_title or all_sizes_by_name),
        "by_post_id": by_post_id,
        "by_date_title": by_date_title,
        "by_title": by_title,
        "all_sizes_by_name": all_sizes_by_name,
    }


def filter_posts_for_disk_sync(
    *,
    posts: List[Dict[str, Any]],
    disk_sync_mode: str,
    service: str,
    user_id: str,
    creator_name: str,
    domain: str,
    artist_dir: str,
    options: FilterOptions,
    downloader,
    local_library=None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Filter raw API `posts` down to only `"missing"` and/or `"mismatched"` posts on disk.

    Returns `(kept_posts, stats_dict)` where `stats_dict` has keys `complete`, `missing`, `mismatched`.
    """
    norm_mode = normalize_disk_sync_mode(disk_sync_mode)
    stats = {"complete": 0, "missing": 0, "mismatched": 0}
    if norm_mode == "all" or not posts:
        return list(posts), stats

    disk_idx = None
    if local_library is not None:
        try:
            disk_idx = local_library.get_creator_post_disk_index(service, user_id, creator_name)
        except Exception:
            disk_idx = None

    direct_idx = _scan_single_dir_into_index(artist_dir) if (artist_dir and os.path.isdir(artist_dir)) else None
    creator_has_disk = bool(
        (disk_idx and disk_idx.get("creator_on_disk"))
        or (direct_idx and direct_idx.get("creator_on_disk"))
    )

    if not creator_has_disk:
        stats["missing"] = len(posts)
        if norm_mode == "mismatched_only":
            return [], stats
        return list(posts), stats

    allow_thumbs = bool(getattr(options, "download_thumbnails_only", False) or getattr(options, "fallback_to_thumbnails", False))
    kept: List[Dict[str, Any]] = []

    for post in posts:
        pid = str(post.get("id") or "").strip()
        raw_title = str(post.get("title") or "").strip()
        ntitle = _normalize_post_title(raw_title)
        pub_raw = str(post.get("published") or post.get("added") or "").strip()
        pub_date = pub_raw[:10] if len(pub_raw) >= 10 else ""

        # Skip unimported Pawchive posts when thumbnails are off so they don't look perpetually missing
        if not allow_thumbs and is_post_unimported_on_pawchive(post, domain=domain, service=service):
            continue

        expected_files, _ = downloader._collect_post_files(post, options, domain, service)
        expected_cnt = len(expected_files)

        entry = None
        for idx_src in (disk_idx, direct_idx):
            if not idx_src:
                continue
            if pid and pid in (idx_src.get("by_post_id") or {}):
                entry = idx_src["by_post_id"][pid]
                break
            if pub_date and ntitle and (pub_date, ntitle) in (idx_src.get("by_date_title") or {}):
                entry = idx_src["by_date_title"][(pub_date, ntitle)]
                break
            if len(ntitle) >= 4 and ntitle in (idx_src.get("by_title") or {}):
                entry = idx_src["by_title"][ntitle]
                break

        if entry is None:
            # Flat creator folder fallback: check if every attachment filename already exists in artist_dir
            all_by_name = (direct_idx or {}).get("all_sizes_by_name") or {}
            if expected_cnt > 0 and all_by_name and not options.subfolder_per_post:
                matched_flat = 0
                has_size_mismatch = False
                for fobj in expected_files:
                    fn = os.path.basename(str(fobj.get("name") or fobj.get("originalFilename") or "")).strip().lower()
                    if not fn:
                        continue
                    stem = os.path.splitext(fn)[0]
                    cands = all_by_name.get(fn) or all_by_name.get(f"{stem}.webp") or []
                    if cands:
                        matched_flat += 1
                        disk_fp, disk_sz = cands[0]
                        api_sz = int(fobj.get("bytes") or fobj.get("size") or 0)
                        if disk_sz <= 0 or needs_full_size_upgrade(disk_sz, api_sz, disk_fp, options, disk_fp):
                            has_size_mismatch = True
                        elif api_sz > 0 and disk_sz != api_sz and not disk_fp.lower().endswith(".webp"):
                            has_size_mismatch = True
                if matched_flat == 0:
                    state = "missing"
                elif matched_flat < expected_cnt or has_size_mismatch:
                    state = "mismatched"
                else:
                    state = "complete"
            else:
                state = "missing"
        else:
            local_paths = list(entry.get("paths") or ())
            local_cnt = len(local_paths)
            archived_cnt = int(entry.get("archived_count") or 0)
            has_folder = bool(entry.get("has_folder"))

            if expected_cnt > 0:
                if local_cnt <= 0:
                    state = "mismatched" if archived_cnt > 0 else "missing"
                elif local_cnt < expected_cnt:
                    state = "mismatched"
                else:
                    # Count matches: check for 0-byte, preview thumbnail, or byte-size mismatch on disk
                    has_file_mismatch = False
                    dir_entry = (direct_idx or {}).get("by_post_id", {}).get(pid) if pid else None
                    fmap = (dir_entry or entry).get("file_map") or {}
                    for lp in local_paths:
                        try:
                            sz = os.path.getsize(lp)
                            if sz <= 0:
                                has_file_mismatch = True
                                break
                        except OSError:
                            has_file_mismatch = True
                            break
                    if not has_file_mismatch and fmap:
                        for fobj in expected_files:
                            fn = os.path.basename(str(fobj.get("name") or fobj.get("originalFilename") or "")).strip().lower()
                            if not fn:
                                continue
                            stem = os.path.splitext(fn)[0]
                            hit = fmap.get(fn) or fmap.get(f"{stem}.webp")
                            if hit:
                                disk_fp, disk_sz = hit
                                api_sz = int(fobj.get("bytes") or fobj.get("size") or 0)
                                if disk_sz <= 0 or needs_full_size_upgrade(disk_sz, api_sz, disk_fp, options, disk_fp):
                                    has_file_mismatch = True
                                    break
                                if api_sz > 0 and disk_sz != api_sz and not disk_fp.lower().endswith(".webp"):
                                    has_file_mismatch = True
                                    break
                    state = "mismatched" if has_file_mismatch else "complete"
            else:
                if local_cnt > 0:
                    state = "mismatched" if archived_cnt > local_cnt else "complete"
                elif has_folder:
                    state = "complete"
                else:
                    state = "missing"

        stats[state] += 1
        if norm_mode == "missing_or_mismatched" and state in ("missing", "mismatched"):
            kept.append(post)
        elif norm_mode == "missing_only" and state == "missing":
            kept.append(post)
        elif norm_mode == "mismatched_only" and state == "mismatched":
            kept.append(post)

    return kept, stats
