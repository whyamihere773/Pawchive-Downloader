"""
Statistics Deep Disk, Archive, History & Watchlist Scanner Mixin
Decomposed from core/statistics_manager.py to keep modules cohesive and under 1,000 lines.
"""

import csv
import os
import shutil
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.atomic_io import atomic_write_json
from core.logger import logger
from core.statistics_http_hook import (
    _normalize_path_key,
    _utc_now_iso,
    classify_ext,
    format_bytes,
)

_CANCEL_POLL_INTERVAL = 512


class StatisticsScannerMixin:
    """Deep storage root deduplication, SQLite telemetry queries, DFS walk, and report export."""

    @staticmethod
    def _unique_roots(
        primary_dir: str,
        overflow_dirs: List[str],
        local_library_roots: List[str],
    ) -> List[Dict[str, str]]:
        """Deduplicate storage roots while preserving role precedence (Primary > Overflow > Extra)."""
        seen: List[str] = []
        roots: List[Dict[str, str]] = []
        candidates = (
            [(primary_dir, "Primary")]
            + [(d, "Overflow Pool") for d in (overflow_dirs or [])]
            + [(d, "Library Root") for d in (local_library_roots or [])]
        )
        for raw_path, role in candidates:
            clean = str(raw_path or "").strip()
            if not clean:
                continue
            norm = os.path.normpath(clean)
            key = _normalize_path_key(norm)
            is_duplicate_or_nested = False
            for existing_key in seen:
                try:
                    if existing_key == key or os.path.commonpath([existing_key, key]) == existing_key:
                        is_duplicate_or_nested = True
                        break
                except ValueError:
                    pass
            if is_duplicate_or_nested:
                continue
            seen.append(key)
            roots.append({"path": norm, "role": role})
        return roots

    @staticmethod
    def _query_archive_stats(archive_manager: Any) -> Dict[str, Any]:
        """Collect raw SQLite archive telemetry and per-creator aggregates cleanly."""
        out: Dict[str, Any] = {
            "db_path": "",
            "db_bytes": 0,
            "db_bytes_str": "0 B",
            "total_files": 0,
            "total_creators": 0,
            "total_posts": 0,
            "verified_files": 0,
            "missing_files": 0,
            "unverified_files": 0,
            "recorded_bytes": 0,
            "recorded_bytes_str": "0 B",
            "categories": {},
            "services": {},
            "creators": [],
        }
        if not archive_manager:
            return out

        db_path = str(getattr(archive_manager, "db_path", "") or "")
        out["db_path"] = db_path
        db_bytes = 0
        for suffix in ("", "-wal", "-shm"):
            cand = db_path + suffix
            if cand and os.path.isfile(cand):
                try:
                    db_bytes += os.path.getsize(cand)
                except OSError:
                    pass
        out["db_bytes"] = db_bytes
        out["db_bytes_str"] = format_bytes(db_bytes)

        try:
            summary = archive_manager.get_statistics() or {}
            out["total_files"] = int(summary.get("total_files") or 0)
            out["total_creators"] = int(summary.get("total_creators") or 0)
            out["total_posts"] = int(summary.get("total_posts") or 0)
            out["verified_files"] = int(summary.get("verified_files") or 0)
            out["missing_files"] = int(summary.get("missing_files") or 0)
            out["unverified_files"] = max(0, out["total_files"] - out["verified_files"] - out["missing_files"])
            out["categories"] = dict(summary.get("category_counts") or {})
        except Exception:
            pass

        if not db_path or not os.path.isfile(db_path):
            return out

        conn = None
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
            cur = conn.cursor()
            row = cur.execute("SELECT SUM(COALESCE(file_size, 0)) FROM downloaded_files;").fetchone()
            out["recorded_bytes"] = int((row[0] if row else 0) or 0)
            out["recorded_bytes_str"] = format_bytes(out["recorded_bytes"])

            svc_rows = cur.execute("""
                SELECT
                    COALESCE(NULLIF(TRIM(LOWER(service)), ''), 'unknown'),
                    COUNT(*),
                    COUNT(DISTINCT COALESCE(NULLIF(TRIM(creator_name), ''), NULLIF(TRIM(creator_id), ''), 'unknown')),
                    COUNT(DISTINCT COALESCE(NULLIF(TRIM(post_id), ''), NULLIF(TRIM(post_title), ''), CAST(id AS TEXT))),
                    SUM(COALESCE(file_size, 0))
                FROM downloaded_files
                GROUP BY COALESCE(NULLIF(TRIM(LOWER(service)), ''), 'unknown');
            """).fetchall()
            for svc, f_cnt, a_cnt, p_cnt, b_sum in svc_rows:
                out["services"][str(svc)] = {
                    "service": str(svc),
                    "files": int(f_cnt or 0),
                    "artists": int(a_cnt or 0),
                    "posts": int(p_cnt or 0),
                    "bytes": int(b_sum or 0),
                }

            creator_rows = cur.execute("""
                SELECT
                    COALESCE(NULLIF(TRIM(LOWER(service)), ''), 'unknown') AS svc,
                    TRIM(COALESCE(creator_id, '')) AS cid,
                    TRIM(COALESCE(creator_name, '')) AS cname,
                    COUNT(*) AS f_cnt,
                    COUNT(DISTINCT COALESCE(NULLIF(TRIM(post_id), ''), NULLIF(TRIM(post_title), ''), CAST(id AS TEXT))) AS p_cnt,
                    SUM(COALESCE(file_size, 0)) AS b_sum,
                    SUM(CASE WHEN is_missing = 1 THEN 1 ELSE 0 END) AS m_cnt,
                    SUM(CASE WHEN is_missing = 0 THEN 1 ELSE 0 END) AS v_cnt,
                    MAX(downloaded_at) AS newest_at
                FROM downloaded_files
                GROUP BY svc, cid, cname;
            """).fetchall()

            merged_creators: Dict[Tuple[str, str], Dict[str, Any]] = {}
            for svc, cid, cname, f_cnt, p_cnt, b_sum, m_cnt, v_cnt, newest_at in creator_rows:
                disp = cname or cid or "Unknown Creator"
                key = (svc, disp.lower())
                entry = merged_creators.get(key)
                if entry is None:
                    entry = merged_creators[key] = {
                        "service": svc,
                        "creator_id": cid or disp.lower(),
                        "artist_name": disp,
                        "archive_files": 0,
                        "posts": 0,
                        "archive_bytes": 0,
                        "missing_files": 0,
                        "verified_files": 0,
                        "last_downloaded_at": "",
                    }
                if cid and (not entry["creator_id"] or entry["creator_id"] == disp.lower()):
                    entry["creator_id"] = cid
                entry["archive_files"] += int(f_cnt or 0)
                entry["posts"] += int(p_cnt or 0)
                entry["archive_bytes"] += int(b_sum or 0)
                entry["missing_files"] += int(m_cnt or 0)
                entry["verified_files"] += int(v_cnt or 0)
                if newest_at and str(newest_at) > entry["last_downloaded_at"]:
                    entry["last_downloaded_at"] = str(newest_at)

            out["creators"] = list(merged_creators.values())
        except Exception as e:
            logger.debug(f"Statistics SQLite archive query note: {e}", category="archive")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        return out

    @staticmethod
    def _query_history_and_watchlist(history_store: Any, watchlist_manager: Any) -> Dict[str, Any]:
        info = {
            "history_sessions": 0,
            "history_files": 0,
            "history_db_bytes": 0,
            "history_db_str": "0 B",
            "watchlist_creators": 0,
            "watchlist_folder_map": {},  # norm_folder_key -> (svc, cid, cname)
        }
        if history_store:
            try:
                db_path = str(getattr(history_store, "path", "") or getattr(history_store, "db_path", "") or "")
                for suffix in ("", "-wal", "-shm"):
                    cand = db_path + suffix
                    if cand and os.path.isfile(cand):
                        info["history_db_bytes"] += os.path.getsize(cand)
                info["history_db_str"] = format_bytes(info["history_db_bytes"])
                info["history_files"] = int(history_store.file_count() or 0)
                if os.path.isfile(db_path):
                    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3.0)
                    try:
                        row = conn.execute("SELECT COUNT(*) FROM sessions;").fetchone()
                        info["history_sessions"] = int((row[0] if row else 0) or 0)
                    finally:
                        conn.close()
            except Exception:
                pass

        if watchlist_manager:
            try:
                entries = list(getattr(watchlist_manager, "entries", []) or [])
                info["watchlist_creators"] = len(entries)
                fmap = info["watchlist_folder_map"]
                for w in entries:
                    svc = (getattr(w, "service", "") or "unknown").strip().lower()
                    cid = str(getattr(w, "user_id", "") or "").strip()
                    cname = (getattr(w, "creator_name", "") or cid or "Unknown Creator").strip()
                    for d in [getattr(w, "download_dir", ""), *(getattr(w, "download_dirs", []) or [])]:
                        if d:
                            fmap[_normalize_path_key(d)] = (svc, cid, cname)
            except Exception:
                pass
        return info

    @staticmethod
    def _walk_subtree(
        start_dir: str,
        visited_dirs: Set[str],
        cancel_event: Optional[threading.Event],
        poll_counter: List[int],
    ) -> Tuple[int, int, int, int, int, Dict[str, Tuple[int, int]], Dict[str, Tuple[int, int]]]:
        """
        Iterative DFS walk over `start_dir` (excluding symlinks/already-visited trees).
        Returns: (files_count, folders_count, total_bytes, part_files, part_bytes, cat_counts, ext_counts)
        """
        files_n = 0
        folders_n = 0
        bytes_n = 0
        part_files_n = 0
        part_bytes_n = 0
        cats: Dict[str, List[int]] = {}
        exts: Dict[str, List[int]] = {}

        stack: List[str] = [start_dir]
        while stack:
            if cancel_event and cancel_event.is_set():
                break
            cur_dir = stack.pop()
            key = _normalize_path_key(cur_dir)
            if key in visited_dirs:
                continue
            visited_dirs.add(key)
            try:
                with os.scandir(cur_dir) as it:
                    for entry in it:
                        poll_counter[0] += 1
                        if poll_counter[0] % _CANCEL_POLL_INTERVAL == 0 and cancel_event and cancel_event.is_set():
                            return (
                                files_n,
                                folders_n,
                                bytes_n,
                                part_files_n,
                                part_bytes_n,
                                {k: (v[0], v[1]) for k, v in cats.items()},
                                {k: (v[0], v[1]) for k, v in exts.items()},
                            )
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name.startswith("."):
                                    continue
                                folders_n += 1
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                st_size = 0
                                try:
                                    st_size = int(entry.stat(follow_symlinks=False).st_size or 0)
                                except OSError:
                                    pass
                                files_n += 1
                                bytes_n += st_size
                                ext = os.path.splitext(entry.name)[1].lower()
                                if ext == ".part":
                                    part_files_n += 1
                                    part_bytes_n += st_size
                                cat = classify_ext(ext)
                                c_rec = cats.get(cat)
                                if c_rec is None:
                                    cats[cat] = [1, st_size]
                                else:
                                    c_rec[0] += 1
                                    c_rec[1] += st_size
                                ext_key = ext or "(no ext)"
                                e_rec = exts.get(ext_key)
                                if e_rec is None:
                                    exts[ext_key] = [1, st_size]
                                else:
                                    e_rec[0] += 1
                                    e_rec[1] += st_size
                        except OSError:
                            continue
            except OSError:
                continue

        return (
            files_n,
            folders_n,
            bytes_n,
            part_files_n,
            part_bytes_n,
            {k: (v[0], v[1]) for k, v in cats.items()},
            {k: (v[0], v[1]) for k, v in exts.items()},
        )

    @staticmethod
    def _merge_counts(dst: Dict[str, List[int]], src: Dict[str, Tuple[int, int]]) -> None:
        for k, (cnt, sz) in src.items():
            cur = dst.get(k)
            if cur is None:
                dst[k] = [cnt, sz]
            else:
                cur[0] += cnt
                cur[1] += sz

    def collect_full_snapshot(
        self,
        primary_dir: str = "",
        overflow_dirs: Optional[List[str]] = None,
        local_library_roots: Optional[List[str]] = None,
        archive_manager: Any = None,
        history_store: Any = None,
        watchlist_manager: Any = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Dict[str, Any]:
        """
        Scan configured storage roots and SQLite databases to produce a complete raw telemetry snapshot.
        Safe to run in a background worker thread.
        """
        from core.local_library import _extract_drive_label, _infer_service_and_name

        t0 = time.monotonic()
        archive_stats = self._query_archive_stats(archive_manager)
        aux_stats = self._query_history_and_watchlist(history_store, watchlist_manager)
        wl_folder_map = aux_stats["watchlist_folder_map"]

        roots = self._unique_roots(primary_dir, overflow_dirs or [], local_library_roots or [])
        visited_dirs: Set[str] = set()
        poll_counter = [0]

        disk_total_files = 0
        disk_total_folders = 0
        disk_artist_folders = 0
        disk_total_bytes = 0
        disk_part_files = 0
        disk_part_bytes = 0
        disk_cats: Dict[str, List[int]] = {}
        disk_exts: Dict[str, List[int]] = {}
        drives_rows: List[Dict[str, Any]] = []

        # Track per-artist aggregates indexed cleanly by archive metadata + folder inference
        artists_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        name_lookup: Dict[str, Tuple[str, str]] = {}

        for ac in archive_stats["creators"]:
            svc = ac["service"]
            disp = ac["artist_name"]
            akey = (svc, disp.lower())
            artists_map[akey] = {
                "artist_name": disp,
                "service": svc,
                "creator_id": ac["creator_id"],
                "disk_files": 0,
                "folders": 0,
                "size_bytes": 0,
                "archive_files": ac["archive_files"],
                "archive_bytes": ac["archive_bytes"],
                "posts": ac["posts"],
                "verified_files": ac["verified_files"],
                "missing_files": ac["missing_files"],
                "drives": set(),
                "folder_paths": [],
                "last_downloaded_at": ac["last_downloaded_at"],
            }
            for alias in (disp.lower(), f"{disp} ({svc})".lower(), f"{disp} [{svc}]".lower(), f"{disp}_{svc}".lower(), str(ac["creator_id"]).lower()):
                if alias:
                    name_lookup.setdefault(alias, akey)

        for rinfo in roots:
            if cancel_event and cancel_event.is_set():
                break
            rpath = rinfo["path"]
            role = rinfo["role"]
            exists = os.path.isdir(rpath)
            r_files = 0
            r_folders = 0
            r_bytes = 0
            r_artists = 0

            vol_total = 0
            vol_free = 0
            vol_used_pct = 0.0
            try:
                probe = rpath if exists else (os.path.splitdrive(rpath)[0] + os.sep if os.name == "nt" else os.path.dirname(rpath))
                if probe and os.path.exists(probe):
                    du = shutil.disk_usage(probe)
                    vol_total = int(du.total)
                    vol_free = int(du.free)
                    if vol_total > 0:
                        vol_used_pct = round(((vol_total - vol_free) / vol_total) * 100.0, 1)
            except OSError:
                pass

            if exists:
                root_key = _normalize_path_key(rpath)
                if root_key not in visited_dirs:
                    visited_dirs.add(root_key)
                    try:
                        entries = list(os.scandir(rpath))
                    except OSError:
                        entries = []

                    for entry in entries:
                        if cancel_event and cancel_event.is_set():
                            break
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name.startswith("."):
                                    continue
                                r_artists += 1
                                r_folders += 1
                                disk_artist_folders += 1
                                disk_total_folders += 1

                                norm_sub = os.path.normpath(entry.path)
                                sub_files, sub_folders, sub_bytes, sub_pf, sub_pb, sub_cats, sub_exts = self._walk_subtree(
                                    norm_sub, visited_dirs, cancel_event, poll_counter
                                )
                                r_files += sub_files
                                r_folders += sub_folders
                                r_bytes += sub_bytes
                                disk_total_files += sub_files
                                disk_total_folders += sub_folders
                                disk_total_bytes += sub_bytes
                                disk_part_files += sub_pf
                                disk_part_bytes += sub_pb
                                self._merge_counts(disk_cats, sub_cats)
                                self._merge_counts(disk_exts, sub_exts)

                                # Attribute artist stats
                                wl_match = wl_folder_map.get(_normalize_path_key(norm_sub))
                                if wl_match:
                                    a_svc, a_cid, a_name = wl_match
                                    akey = (a_svc, a_name.lower())
                                else:
                                    inferred_svc, inferred_name = _infer_service_and_name(entry.name)
                                    matched_key = name_lookup.get(entry.name.lower()) or name_lookup.get(inferred_name.lower())
                                    if matched_key is not None and (inferred_svc == "local" or matched_key[0] == inferred_svc):
                                        akey = matched_key
                                        a_svc, a_cid, a_name = matched_key[0], "", matched_key[1]
                                    else:
                                        a_svc = inferred_svc
                                        a_cid = ""
                                        a_name = inferred_name or entry.name
                                        akey = (a_svc, a_name.lower())

                                rec = artists_map.get(akey)
                                if rec is None:
                                    rec = artists_map[akey] = {
                                        "artist_name": a_name,
                                        "service": a_svc,
                                        "creator_id": a_cid,
                                        "disk_files": 0,
                                        "folders": 0,
                                        "size_bytes": 0,
                                        "archive_files": 0,
                                        "archive_bytes": 0,
                                        "posts": 0,
                                        "verified_files": 0,
                                        "missing_files": 0,
                                        "drives": set(),
                                        "folder_paths": [],
                                        "last_downloaded_at": "",
                                    }
                                rec["disk_files"] += sub_files
                                rec["folders"] += 1 + sub_folders
                                rec["size_bytes"] += sub_bytes
                                drv = _extract_drive_label(norm_sub)
                                if drv:
                                    rec["drives"].add(drv)
                                if norm_sub not in rec["folder_paths"]:
                                    rec["folder_paths"].append(norm_sub)

                            elif entry.is_file(follow_symlinks=False):
                                st_size = 0
                                try:
                                    st_size = int(entry.stat(follow_symlinks=False).st_size or 0)
                                except OSError:
                                    pass
                                r_files += 1
                                r_bytes += st_size
                                disk_total_files += 1
                                disk_total_bytes += st_size
                                ext = os.path.splitext(entry.name)[1].lower()
                                if ext == ".part":
                                    disk_part_files += 1
                                    disk_part_bytes += st_size
                                cat = classify_ext(ext)
                                c_rec = disk_cats.get(cat)
                                if c_rec is None:
                                    disk_cats[cat] = [1, st_size]
                                else:
                                    c_rec[0] += 1
                                    c_rec[1] += st_size
                                ext_key = ext or "(no ext)"
                                e_rec = disk_exts.get(ext_key)
                                if e_rec is None:
                                    disk_exts[ext_key] = [1, st_size]
                                else:
                                    e_rec[0] += 1
                                    e_rec[1] += st_size
                        except OSError:
                            continue

            drives_rows.append({
                "path": rpath,
                "label": _extract_drive_label(rpath) or rpath,
                "role": role,
                "exists": exists,
                "artist_folders": r_artists,
                "folders": r_folders,
                "files": r_files,
                "used_bytes": r_bytes,
                "used_str": format_bytes(r_bytes),
                "volume_total_bytes": vol_total,
                "volume_total_str": format_bytes(vol_total),
                "volume_free_bytes": vol_free,
                "volume_free_str": format_bytes(vol_free),
                "volume_used_pct": vol_used_pct,
            })

        # Build sorted artist rows + aggregated service breakdown
        artist_rows: List[Dict[str, Any]] = []
        services_agg: Dict[str, Dict[str, Any]] = {}
        for rec in artists_map.values():
            eff_bytes = rec["size_bytes"] if rec["size_bytes"] > 0 else rec["archive_bytes"]
            eff_files = rec["disk_files"] if rec["disk_files"] > 0 else rec["archive_files"]
            drives_list = sorted(rec["drives"])
            row = {
                "artist_name": rec["artist_name"],
                "service": rec["service"],
                "creator_id": rec["creator_id"],
                "disk_files": rec["disk_files"],
                "archive_files": rec["archive_files"],
                "files": eff_files,
                "folders": rec["folders"],
                "posts": rec["posts"],
                "size_bytes": eff_bytes,
                "size_str": format_bytes(eff_bytes),
                "verified_files": rec["verified_files"],
                "missing_files": rec["missing_files"],
                "drives": ", ".join(drives_list) if drives_list else "-",
                "folder_paths": list(rec["folder_paths"]),
                "primary_folder": rec["folder_paths"][0] if rec["folder_paths"] else "",
                "last_downloaded_at": rec["last_downloaded_at"] or "-",
            }
            artist_rows.append(row)

            s_key = rec["service"] or "unknown"
            s_entry = services_agg.get(s_key)
            if s_entry is None:
                s_entry = services_agg[s_key] = {
                    "service": s_key,
                    "artists": 0,
                    "posts": 0,
                    "disk_files": 0,
                    "archive_files": 0,
                    "folders": 0,
                    "size_bytes": 0,
                }
            s_entry["artists"] += 1
            s_entry["posts"] += rec["posts"]
            s_entry["disk_files"] += rec["disk_files"]
            s_entry["archive_files"] += rec["archive_files"]
            s_entry["folders"] += rec["folders"]
            s_entry["size_bytes"] += eff_bytes

        artist_rows.sort(key=lambda r: (r["size_bytes"], r["files"]), reverse=True)
        service_rows = sorted(
            [
                {
                    **sv,
                    "files": sv["disk_files"] if sv["disk_files"] > 0 else sv["archive_files"],
                    "size_str": format_bytes(sv["size_bytes"]),
                }
                for sv in services_agg.values()
            ],
            key=lambda r: (r["size_bytes"], r["files"]),
            reverse=True,
        )

        # File category breakdown (disk + archive)
        category_order = ("images", "videos", "audio", "archives", "graphics", "documents", "links", "other")
        category_rows: List[Dict[str, Any]] = []
        for cat in category_order:
            d_cnt, d_bytes = disk_cats.get(cat, [0, 0])
            a_cnt = int(archive_stats["categories"].get(cat, 0) or 0)
            pct = round((d_bytes / disk_total_bytes) * 100.0, 1) if disk_total_bytes > 0 else 0.0
            category_rows.append({
                "category": cat,
                "disk_files": d_cnt,
                "disk_bytes": d_bytes,
                "disk_bytes_str": format_bytes(d_bytes),
                "share_pct": pct,
                "archive_files": a_cnt,
            })

        ext_rows = sorted(
            [
                {
                    "ext": ext_name,
                    "files": vals[0],
                    "size_bytes": vals[1],
                    "size_str": format_bytes(vals[1]),
                    "category": classify_ext(ext_name),
                }
                for ext_name, vals in disk_exts.items()
            ],
            key=lambda r: (r["size_bytes"], r["files"]),
            reverse=True,
        )[:40]

        scan_ms = int(round((time.monotonic() - t0) * 1000))
        snapshot = {
            "scanned_at": _utc_now_iso(),
            "scan_duration_ms": scan_ms,
            "cancelled": bool(cancel_event and cancel_event.is_set()),
            "total_artists": len(artist_rows),
            "disk_total_files": disk_total_files,
            "disk_total_folders": disk_total_folders,
            "disk_artist_folders": disk_artist_folders,
            "disk_total_bytes": disk_total_bytes,
            "disk_total_str": format_bytes(disk_total_bytes),
            "disk_part_files": disk_part_files,
            "disk_part_bytes": disk_part_bytes,
            "disk_part_str": format_bytes(disk_part_bytes),
            "archive_files": archive_stats["total_files"],
            "archive_creators": archive_stats["total_creators"],
            "archive_posts": archive_stats["total_posts"],
            "archive_verified_files": archive_stats["verified_files"],
            "archive_missing_files": archive_stats["missing_files"],
            "archive_unverified_files": archive_stats["unverified_files"],
            "archive_recorded_bytes": archive_stats["recorded_bytes"],
            "archive_recorded_str": archive_stats["recorded_bytes_str"],
            "archive_db_bytes": archive_stats["db_bytes"],
            "archive_db_str": archive_stats["db_bytes_str"],
            "history_sessions": aux_stats["history_sessions"],
            "history_files": aux_stats["history_files"],
            "history_db_bytes": aux_stats["history_db_bytes"],
            "history_db_str": aux_stats["history_db_str"],
            "watchlist_creators": aux_stats["watchlist_creators"],
            "storage_roots_count": len(drives_rows),
            "drives": drives_rows,
            "categories": category_rows,
            "extensions": ext_rows,
            "services": service_rows,
            "artists": artist_rows,
        }

        if not snapshot["cancelled"]:
            with self._lock:
                self._cached_storage_snapshot = dict(snapshot)
        return snapshot

    @staticmethod
    def export_report(target_path: str, snapshot: Dict[str, Any]) -> bool:
        """Write raw telemetry + disk/artist snapshot to JSON or CSV."""
        if not target_path:
            return False
        ext = os.path.splitext(target_path)[1].lower()
        try:
            parent = os.path.dirname(target_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            if ext == ".csv":
                artists = snapshot.get("artists") or []
                with open(target_path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "Artist", "Service", "Creator ID", "Files", "Folders",
                        "Posts", "Size (Bytes)", "Size (Formatted)",
                        "Archive Files", "Verified", "Missing", "Drives", "Last Downloaded",
                    ])
                    for a in artists:
                        writer.writerow([
                            a.get("artist_name", ""),
                            a.get("service", ""),
                            a.get("creator_id", ""),
                            a.get("files", 0),
                            a.get("folders", 0),
                            a.get("posts", 0),
                            a.get("size_bytes", 0),
                            a.get("size_str", ""),
                            a.get("archive_files", 0),
                            a.get("verified_files", 0),
                            a.get("missing_files", 0),
                            a.get("drives", ""),
                            a.get("last_downloaded_at", ""),
                        ])
                return True

            atomic_write_json(target_path, snapshot, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to export statistics report to {target_path}: {e}", category="system")
            return False
