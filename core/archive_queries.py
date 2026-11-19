"""
Archive Database Query, Summary, Hierarchy & Statistics Mixin
Decomposed from core/archive_manager.py to keep modules cohesive and under 1,000 lines.
"""

import datetime
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from core import archive_index
from core.logger import logger

FILE_TYPE_CATEGORIES = {
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".001", ".cbz", ".cbr"},
    "graphics": {".psd", ".psb", ".clip", ".sai", ".sai2", ".ai", ".kra", ".cpt", ".xcf"},
    "images": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".tiff", ".tif", ".ico", ".avif", ".jfif"},
    "videos": {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".wmv", ".m4v", ".ts", ".m4s", ".vob"},
    "audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus", ".mid", ".midi"},
    "documents": {".pdf", ".txt", ".docx", ".doc", ".epub", ".rtf", ".csv", ".json", ".md", ".xlsx"},
    "links": {".link", ".url", "link", "url"},
}



class ArchiveQueriesMixin:
    """Read-only queries, creator/post summaries, statistics, and character profile extraction."""

    def _ensure_db(self) -> bool:
        """The database exists and its schema is up to date (reads use a second connection)."""
        if self._conn is not None:
            return True             # already open: reading never waits for a download's write
        if not os.path.exists(self.db_path) and not self._enabled:
            return False
        with self._lock:
            if self._conn is None:
                self._init_db_unlocked()
            return self._conn is not None

    def _reader(self) -> Optional[sqlite3.Connection]:
        """The read connection (call with self._rlock held)."""
        if self._rconn is None:
            if not os.path.exists(self.db_path):
                return None
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            conn.execute("PRAGMA query_only=1;")
            self._rconn = conn
        return self._rconn

    @staticmethod
    def _where(query: str = "", service: str = "all", file_type: str = "all") -> Tuple[str, List[Any]]:
        conditions: List[str] = []
        params: List[Any] = []
        clean_svc = (service or "").strip().lower()
        if clean_svc and clean_svc != "all":
            conditions.append("service = ?")
            params.append(clean_svc)
        clean_q = (query or "").strip()
        if clean_q:
            q_like = f"%{clean_q}%"
            conditions.append(
                "(filename LIKE ? OR post_title LIKE ? OR creator_name LIKE ? "
                "OR creator_id LIKE ? OR post_id LIKE ? OR file_hash LIKE ?)"
            )
            params.extend([q_like] * 6)
        clean_ft = (file_type or "").strip().lower()
        if clean_ft == "removed":
            conditions.append("is_missing = 1")
        elif clean_ft and clean_ft != "all" and clean_ft in FILE_TYPE_CATEGORIES:
            extensions = FILE_TYPE_CATEGORIES[clean_ft]
            conditions.append(f"LOWER(file_ext) IN ({','.join(['?'] * len(extensions))})")
            params.extend(list(extensions))
        return (f"WHERE {' AND '.join(conditions)}" if conditions else ""), params

    @staticmethod
    def _creator_key(service, creator_id, creator_name) -> Tuple[str, str]:
        """How records are grouped into creators in the tab (same rule as get_hierarchical_records)."""
        svc = str(service or "unknown").strip().lower() or "unknown"
        cname = str(creator_name or "").strip()
        cid = str(creator_id or "").strip()
        display = cname if cname else (cid if cid else "Unknown Creator")
        return svc, display.lower()

    def _summaries_ready(self, conn: sqlite3.Connection) -> bool:
        if not self._index_ready:
            try:
                self._index_ready = archive_index.is_ready(conn)
            except Exception:
                self._index_ready = False
        return self._index_ready

    def _fast_where(self, conn: sqlite3.Connection, query: str = "", service: str = "all",
                    file_type: str = "all") -> Tuple[str, List[Any]]:
        """_where, with the search text looked up in the search index when it's ready (LIKE over
        every record took seconds in a big archive)."""
        clean_q = (query or "").strip()
        fq = archive_index.fts_query(clean_q)
        if not clean_q or fq is None or not self._summaries_ready(conn) or not archive_index.state(conn)[2]:
            return self._where(query, service, file_type)
        where, params = self._where("", service, file_type)
        cond = f"id IN (SELECT rowid FROM archive_fts WHERE {archive_index.FTS_MATCH})"
        extra = list(fq)
        hq = clean_q.lower()
        if re.fullmatch(r"[0-9a-f]{8,64}", hq):
            cond = f"({cond} OR (file_hash >= ? AND file_hash < ?))"     # a file hash (its start)
            extra += [hq, hq + "g"]
        where = f"{where} AND {cond}" if where else f"WHERE {cond}"
        return where, list(params) + extra

    def _summaries_from_index(self, conn: sqlite3.Connection, service: str,
                              sort_by: str, cat: Optional[str] = None,
                              name_like: Optional[str] = None) -> List[Dict[str, Any]]:
        """get_creator_summaries from the summary table: one row per creator instead of grouping every
        record (cat: only that file type's files, from the per-type table)."""
        clean_svc = (service or "").strip().lower()
        conds: List[str] = []
        params: List[Any] = []
        if cat:
            conds.append("cat = ?")
            params.append(cat)
        if clean_svc and clean_svc != "all":
            conds.append("service = ?")
            params.append(clean_svc)
        if name_like:
            conds.append("(creator_name LIKE ? OR creator_id LIKE ?)")
            params += [f"%{name_like}%"] * 2
        sql = ("SELECT service, creator_id, creator_name, files, missing, verified, posts, newest, oldest, newest_id "
               f"FROM {'archive_creator_cats' if cat else 'archive_creators'}"
               + (f" WHERE {' AND '.join(conds)}" if conds else ""))
        rows = conn.execute(sql + ";", params).fetchall()
        creators: Dict[Tuple[str, str], Dict[str, Any]] = {}
        members: Dict[Tuple[str, str], set] = {}
        for (r_svc, r_cid, r_cname, n, n_missing, n_verified, n_posts, newest, oldest, newest_id) in rows:
            if not n:
                continue
            key = self._creator_key(r_svc, r_cid, r_cname)
            c = creators.get(key)
            if c is None:
                c = creators[key] = {
                    "service": key[0], "total_files": 0, "missing_count": 0, "verified_count": 0,
                    "unverified_count": 0, "post_count": 0, "posts": [], "_rank": None,
                }
                members[key] = set()
            rank = (str(newest or ""), int(newest_id or 0))
            if c["_rank"] is None or rank > c["_rank"]:
                c["_rank"] = rank
                clean_cname = str(r_cname or "").strip()
                clean_cid = str(r_cid or "").strip()
                c["creator_name"] = clean_cname or clean_cid or "Unknown Creator"
                c["creator_id"] = clean_cid or clean_cname or "unknown"
            members[key].add((r_svc, r_cid, r_cname))
            n, n_missing, n_verified = int(n or 0), int(n_missing or 0), int(n_verified or 0)
            c["total_files"] += n
            c["missing_count"] += n_missing
            c["verified_count"] += n_verified
            c["unverified_count"] += n - n_missing - n_verified
            c["post_count"] += int(n_posts or 0)
            if newest and (not c.get("newest_downloaded_at") or newest > c["newest_downloaded_at"]):
                c["newest_downloaded_at"] = newest
            if oldest and (not c.get("oldest_downloaded_at") or oldest < c["oldest_downloaded_at"]):
                c["oldest_downloaded_at"] = oldest
        result = []
        for key, c in creators.items():
            c.pop("_rank", None)
            c["key"] = f"{key[0]}|{key[1]}"
            mem = members[key]
            if len(mem) > 1:
                # One creator under several ids / spellings: a post shared by them counts once
                cond = " OR ".join(["(service = ? AND creator_id = ? AND creator_name = ?)"] * len(mem))
                if cat:
                    n_posts = conn.execute(f"SELECT COUNT(DISTINCT post_id) FROM archive_post_cats "
                                           f"WHERE cat = ? AND ({cond});", [cat] + [x for t in mem for x in t])
                else:
                    n_posts = conn.execute(f"SELECT COUNT(DISTINCT post_id) FROM archive_posts WHERE {cond};",
                                           [x for t in mem for x in t])
                c["post_count"] = int(n_posts.fetchone()[0] or 0)
            result.append(c)
        self._creator_members = {k: sorted(v, key=lambda t: tuple(str(x or "") for x in t))
                                 for k, v in members.items()}
        self._sort_creators(result, sort_by)
        return result

    def _members_of(self, conn: sqlite3.Connection, key: Tuple[str, str]) -> List[Tuple[str, str, str]]:
        """The raw (service, creator id, name) rows of a creator in the tab, from the last summaries or
        else from the summary table (without either, every record had to be read)."""
        member = self._creator_members.get(key)
        if member:
            return member
        if not self._summaries_ready(conn):
            return []
        found = sorted({(sv, cid, cn) for sv, cid, cn in
                        conn.execute("SELECT service, creator_id, creator_name FROM archive_creators WHERE service = ?;",
                                     (key[0],))
                        if self._creator_key(sv, cid, cn) == key})
        return found

    def get_creator_summaries(self, query: str = "", service: str = "all", file_type: str = "all",
                              sort_by: str = "creator_az",
                              should_stop: Optional[Callable[[], bool]] = None) -> Optional[List[Dict[str, Any]]]:
        """One entry per creator (file / post counts, dates), without their posts and files: those
        are read with get_creator_posts when a creator is opened. Sending every file of a big archive
        to the window on each refresh froze it (#28)."""
        if not self._ensure_db():
            return []
        clean_ft = (file_type or "all").strip().lower()
        clean_q = (query or "").strip()
        # (1-2 letters: the search index needs 3, and matching them in every file name took seconds and
        # matched nearly everything: such a search looks at creator names and ids)
        if (not clean_q or len(clean_q) < 3) and (clean_ft in ("", "all") or clean_ft in FILE_TYPE_CATEGORIES):
            try:
                with self._rlock:
                    conn = self._reader()
                    if conn is not None and self._summaries_ready(conn):
                        return self._summaries_from_index(conn, service, sort_by,
                                                          cat=clean_ft if clean_ft in FILE_TYPE_CATEGORIES else None,
                                                          name_like=clean_q or None)
            except Exception as e:
                logger.debug(f"Archive summaries not used: {e}", category="archive")
        with self._rlock:
            conn = self._reader()
            where, params = self._fast_where(conn, query, service, file_type) if conn is not None \
                else self._where(query, service, file_type)
        # Grouped by post: far fewer rows than files, and the creator's post count comes out of it
        sql = f"""
            SELECT service, creator_id, creator_name, post_id, post_title, COUNT(*),
                   SUM(CASE WHEN is_missing = 1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN is_missing = 0 THEN 1 ELSE 0 END),
                   MAX(downloaded_at), MIN(downloaded_at), MAX(id)
            FROM downloaded_files {where}
            GROUP BY service, creator_id, creator_name, post_id, post_title;
        """
        try:
            with self._rlock:
                conn = self._reader()
                if conn is None:
                    return []
                if should_stop is not None:
                    # A newer search makes this one stop (instead of each running to the end in turn)
                    conn.set_progress_handler(lambda: 1 if should_stop() else 0, 20000)
                try:
                    rows = conn.execute(sql, params).fetchall()
                finally:
                    if should_stop is not None:
                        conn.set_progress_handler(None, 0)
            if should_stop is not None and should_stop():
                return None                              # replaced by a newer search meanwhile
        except sqlite3.OperationalError as e:
            if should_stop is not None and should_stop():
                return None                          # replaced by a newer search
            logger.error(f"Failed to read the archive's creators: {e}", category="archive")
            self._note_error(e)
            return []
        except Exception as e:
            logger.error(f"Failed to read the archive's creators: {e}", category="archive")
            self._note_error(e)
            return []

        creators: Dict[Tuple[str, str], Dict[str, Any]] = {}
        members: Dict[Tuple[str, str], set] = {}
        for (r_svc, r_cid, r_cname, r_pid, r_ptitle, n, n_missing, n_verified, newest, oldest, max_id) in rows:
            key = self._creator_key(r_svc, r_cid, r_cname)
            c = creators.get(key)
            if c is None:
                c = creators[key] = {
                    "service": key[0],
                    "total_files": 0, "missing_count": 0, "verified_count": 0, "unverified_count": 0,
                    "post_keys": set(),
                    "posts": [],
                    "_rank": None,
                }
                members[key] = set()
            # Name and id as written on the newest record (as in the full tree)
            rank = (str(newest or ""), int(max_id or 0))
            if c["_rank"] is None or rank > c["_rank"]:
                c["_rank"] = rank
                clean_cname = str(r_cname or "").strip()
                clean_cid = str(r_cid or "").strip()
                c["creator_name"] = clean_cname or clean_cid or "Unknown Creator"
                c["creator_id"] = clean_cid or clean_cname or "unknown"
            members[key].add((r_svc, r_cid, r_cname))
            n, n_missing, n_verified = int(n or 0), int(n_missing or 0), int(n_verified or 0)
            c["total_files"] += n
            c["missing_count"] += n_missing
            c["verified_count"] += n_verified
            c["unverified_count"] += n - n_missing - n_verified
            if newest and (not c.get("newest_downloaded_at") or newest > c["newest_downloaded_at"]):
                c["newest_downloaded_at"] = newest
            if oldest and (not c.get("oldest_downloaded_at") or oldest < c["oldest_downloaded_at"]):
                c["oldest_downloaded_at"] = oldest
            clean_pid = str(r_pid or "").strip()
            clean_ptitle = str(r_ptitle or "").strip()
            c["post_keys"].add(clean_pid or clean_ptitle or f"general_{key[0]}")

        result = []
        for key, c in creators.items():
            c["post_count"] = len(c.pop("post_keys"))
            c.pop("_rank", None)
            c["key"] = f"{key[0]}|{key[1]}"
            result.append(c)
        self._creator_members = {k: sorted(v, key=lambda t: tuple(str(x or "") for x in t))
                                 for k, v in members.items()}
        self._sort_creators(result, sort_by)
        return result

    @staticmethod
    def _sort_creators(result: List[Dict[str, Any]], sort_by: str) -> None:
        clean_sort = (sort_by or "creator_az").lower()
        if clean_sort == "creator_za":
            result.sort(key=lambda x: str(x.get("creator_name") or "").lower(), reverse=True)
        elif clean_sort == "files_desc":
            result.sort(key=lambda x: int(x.get("total_files") or 0), reverse=True)
        elif clean_sort == "newest":
            result.sort(key=lambda x: str(x.get("newest_downloaded_at") or ""), reverse=True)
        elif clean_sort == "oldest":
            result.sort(key=lambda x: str(x.get("oldest_downloaded_at") or ""))
        else:
            result.sort(key=lambda x: str(x.get("creator_name") or "").lower())

    def get_creator_posts(self, creator_key: str, query: str = "", service: str = "all",
                          file_type: str = "all",
                          should_stop: Optional[Callable[[], bool]] = None) -> Optional[List[Dict[str, Any]]]:
        """The posts (with their files) of one creator from get_creator_summaries ("service|name")."""
        if not self._ensure_db():
            return []
        svc, _, name = str(creator_key or "").partition("|")
        key = (svc, name)
        with self._rlock:
            conn = self._reader()
            if conn is None:
                return []
            if 0 < len((query or "").strip()) < 3 and self._summaries_ready(conn):
                query = ""             # found by its name (a short search): all its files
            where, params = self._fast_where(conn, query, service, file_type)
            member = self._members_of(conn, key)
        ids = sorted({str(cid) for (_s, cid, _n) in member if cid not in (None, "")})
        svcs = sorted({str(sv) for (sv, _c, _n) in member if sv is not None})
        if member and ids and svcs and all(cid not in (None, "") for (_s, cid, _n) in member):
            # Indexed: only this creator's rows are read
            extra = (f"service IN ({','.join(['?'] * len(svcs))}) "
                     f"AND creator_id IN ({','.join(['?'] * len(ids))})")
            where = f"{where} AND {extra}" if where else f"WHERE {extra}"
            params = list(params) + svcs + ids
        sql = f"""
            SELECT id, service, creator_id, creator_name, post_id, post_title,
                   file_id, file_hash, filename, file_size, file_ext, downloaded_at,
                   file_path, is_missing, last_verified_at
            FROM downloaded_files {where}
            ORDER BY downloaded_at DESC, id DESC;
        """
        try:
            with self._rlock:
                conn = self._reader()
                if conn is None:
                    return []
                if should_stop is not None:
                    conn.set_progress_handler(lambda: 1 if should_stop() else 0, 20000)
                try:
                    raw_rows = conn.execute(sql, params).fetchall()
                finally:
                    if should_stop is not None:
                        conn.set_progress_handler(None, 0)
            if should_stop is not None and should_stop():
                return None
            rows = [r for r in raw_rows if self._creator_key(r[1], r[2], r[3]) == key]
        except sqlite3.OperationalError as e:
            if should_stop is not None and should_stop():
                return None
            logger.error(f"Failed to read the archive's posts for {name}: {e}", category="archive")
            self._note_error(e)
            return []
        except Exception as e:
            logger.error(f"Failed to read the archive's posts for {name}: {e}", category="archive")
            self._note_error(e)
            return []
        tree = self._build_hierarchy(rows, "creator_az")
        return tree[0]["posts"] if tree else []

    def get_total_count(self) -> int:
        """Return total count of archived file records. Returns 0 if disabled or empty.

        Read by the window: when the read connection is busy (a big Archive tab refresh), the last
        known count is returned instead of freezing the window until it's done."""
        if not self._enabled and not os.path.exists(self.db_path):
            return 0
        if not self._ensure_db():
            return 0
        if not self._rlock.acquire(timeout=0.05):
            return self._last_count
        try:
            conn = self._reader()
            if conn is None:
                return 0
            row = conn.execute("SELECT COUNT(*) FROM downloaded_files;").fetchone()
            self._last_count = int(row[0]) if row else 0
            return self._last_count
        except Exception as e:
            logger.debug(f"Failed to query archive record count: {e}", category="archive")
            self._note_error(e)
            return self._last_count
        finally:
            self._rlock.release()

    def get_hierarchical_records(
        self,
        query: str = "",
        service: str = "all",
        file_type: str = "all",
        sort_by: str = "creator_az"
    ) -> List[Dict[str, Any]]:
        """
        Returns records organized hierarchically:
        Creator Group ➔ Post Sub-Group ➔ File Items.
        Every file of the archive: the Archive tab uses get_creator_summaries / get_creator_posts.
        """
        if not self._ensure_db():
            return []
        with self._rlock:
            conn = self._reader()
            where_clause, params = self._fast_where(conn, query, service, file_type) if conn is not None \
                else self._where(query, service, file_type)
        sql = f"""
            SELECT id, service, creator_id, creator_name, post_id, post_title,
                   file_id, file_hash, filename, file_size, file_ext, downloaded_at,
                   file_path, is_missing, last_verified_at
            FROM downloaded_files
            {where_clause}
            ORDER BY downloaded_at DESC, id DESC;
        """
        try:
            with self._rlock:
                conn = self._reader()
                if conn is None:
                    return []
                rows = conn.execute(sql, params).fetchall()
            return self._build_hierarchy(rows, sort_by)
        except Exception as e:
            logger.error(f"Failed to query hierarchical archive records: {e}", category="archive")
            self._note_error(e)
            return []

    def _build_hierarchy(self, rows: List[tuple], sort_by: str = "creator_az") -> List[Dict[str, Any]]:
        """Creator ➔ post ➔ file tree from rows of get_hierarchical_records' query."""
        # Grouping data structure:
        # creators_map: key -> { creator_name, creator_id, service, posts: { post_id -> post_dict } }
        creators_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for row in rows:
            (r_id, r_svc, r_cid, r_cname, r_pid, r_ptitle,
             r_fid, r_fhash, r_fname, r_fsize, r_fext, r_down_at,
             r_fpath, r_is_missing, r_last_ver) = row

            clean_svc = str(r_svc or "unknown").strip().lower() or "unknown"
            clean_cname = str(r_cname or "").strip()
            clean_cid = str(r_cid or "").strip()
            display_creator = clean_cname if clean_cname else (clean_cid if clean_cid else "Unknown Creator")
            creator_key = (clean_svc, display_creator.lower())

            if creator_key not in creators_map:
                creators_map[creator_key] = {
                    "creator_name": display_creator,
                    "creator_id": clean_cid or clean_cname or "unknown",
                    "service": clean_svc,
                    "total_files": 0,
                    "missing_count": 0,
                    "verified_count": 0,
                    "unverified_count": 0,
                    "posts_map": {}
                }

            c_entry = creators_map[creator_key]
            c_entry["total_files"] += 1
            if r_down_at:
                if "newest_downloaded_at" not in c_entry or r_down_at > c_entry["newest_downloaded_at"]:
                    c_entry["newest_downloaded_at"] = r_down_at
                if "oldest_downloaded_at" not in c_entry or r_down_at < c_entry["oldest_downloaded_at"]:
                    c_entry["oldest_downloaded_at"] = r_down_at
            r_missing_int = int(r_is_missing if r_is_missing is not None else -1)
            if r_missing_int == 1:
                c_entry["missing_count"] += 1
            elif r_missing_int == 0:
                c_entry["verified_count"] += 1
            else:
                c_entry["unverified_count"] += 1

            # Post level
            clean_pid = str(r_pid or "").strip()
            clean_ptitle = str(r_ptitle or "").strip()
            display_post_title = clean_ptitle if clean_ptitle else (f"Post #{clean_pid}" if clean_pid else "General / Archived Files")
            p_key = clean_pid if clean_pid else (clean_ptitle if clean_ptitle else f"general_{clean_svc}")

            if p_key not in c_entry["posts_map"]:
                c_entry["posts_map"][p_key] = {
                    "post_id": clean_pid or p_key,
                    "post_title": display_post_title,
                    "service": clean_svc,
                    "creator_name": display_creator,
                    "creator_id": clean_cid or clean_cname or "unknown",
                    "missing_count": 0,
                    "files": []
                }

            if r_missing_int == 1:
                c_entry["posts_map"][p_key]["missing_count"] += 1

            # Format file size string
            fsize_int = int(r_fsize or 0)
            if fsize_int >= 1024 * 1024 * 1024:
                size_str = f"{fsize_int / (1024 * 1024 * 1024):.1f} GB"
            elif fsize_int >= 1024 * 1024:
                size_str = f"{fsize_int / (1024 * 1024):.1f} MB"
            elif fsize_int >= 1024:
                size_str = f"{fsize_int / 1024:.1f} KB"
            elif fsize_int > 0:
                size_str = f"{fsize_int} B"
            else:
                size_str = ""

            # Format downloaded_at string (fast-path string slicing for ISO timestamps)
            date_display = str(r_down_at or "")
            if len(date_display) >= 16 and (date_display[10] in ("T", " ")):
                date_display = f"{date_display[:10]} {date_display[11:16]}"
            elif date_display:
                try:
                    dt = datetime.datetime.fromisoformat(date_display)
                    date_display = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            # Determine clean extension
            clean_fname = str(r_fname or "").strip()
            clean_fid = str(r_fid or "").strip()
            ext_display = (str(r_fext or "")).replace(".", "").upper()
            if not ext_display and clean_fname:
                _, ext = os.path.splitext(clean_fname)
                ext_display = ext.replace(".", "").upper()

            c_entry["posts_map"][p_key]["files"].append({
                "id": r_id,
                "filename": clean_fname or f"file_{clean_fid or r_id}",
                "file_id": clean_fid or str(r_id),
                "file_hash": str(r_fhash or ""),
                "file_size": fsize_int,
                "file_size_str": size_str,
                "file_ext": ext_display,
                "downloaded_at": str(r_down_at or ""),
                "downloaded_at_str": date_display,
                "post_id": clean_pid or p_key,
                "service": clean_svc,
                "creator_id": clean_cid or clean_cname or "unknown",
                "file_path": str(r_fpath or ""),
                "is_missing": r_missing_int,
                "last_verified_at": str(r_last_ver or "")
            })

        # Assemble sorted list
        result: List[Dict[str, Any]] = []
        for c_entry in creators_map.values():
            # Convert posts_map to list
            posts_list = list(c_entry["posts_map"].values())
            for p in posts_list:
                p["file_count"] = len(p["files"])
            c_entry["posts"] = posts_list
            c_entry["post_count"] = len(posts_list)
            del c_entry["posts_map"]
            result.append(c_entry)

        self._sort_creators(result, sort_by)
        return result

    def get_statistics(self) -> Dict[str, Any]:
        """Return comprehensive telemetry regarding the archive database."""
        now = time.time()
        with self._stats_cache_lock:
            if self._stats_cache is not None and (now - self._stats_cache_time < 20.0):
                return dict(self._stats_cache)

        stats = {
            "total_files": 0,
            "total_creators": 0,
            "total_posts": 0,
            "db_size_bytes": 0,
            "db_size_str": "0 KB",
            "category_counts": {
                "archives": 0,
                "graphics": 0,
                "images": 0,
                "videos": 0,
                "audio": 0,
                "documents": 0,
                "links": 0,
                "removed": 0,
                "other": 0
            },
            "service_counts": {},
            "verified_files": 0,
            "missing_files": 0
        }

        if os.path.exists(self.db_path):
            try:
                stats["db_size_bytes"] = os.path.getsize(self.db_path)
                sz = stats["db_size_bytes"]
                if sz >= 1024 * 1024:
                    stats["db_size_str"] = f"{sz / (1024 * 1024):.1f} MB"
                else:
                    stats["db_size_str"] = f"{max(1, sz // 1024)} KB"
            except Exception:
                pass

        if not os.path.exists(self.db_path) or not self._ensure_db():
            return stats

        with self._rlock:
            conn = self._reader()
            if conn is None:
                return stats
            try:
                if self._summaries_ready(conn):
                    self._statistics_from_index(conn, stats)
                    with self._stats_cache_lock:
                        self._stats_cache = dict(stats)
                        self._stats_cache_time = now
                    return stats
            except Exception as e:
                logger.debug(f"Archive summaries not used for statistics: {e}", category="archive")

            try:
                cursor = conn.cursor()

                # Total files
                cursor.execute("SELECT COUNT(*) FROM downloaded_files;")
                stats["total_files"] = int(cursor.fetchone()[0] or 0)

                # Total creators (null-safe concatenation and fallback)
                cursor.execute("""
                    SELECT COUNT(DISTINCT 
                        COALESCE(NULLIF(TRIM(service), ''), 'unknown') || ':' || 
                        COALESCE(NULLIF(TRIM(creator_name), ''), NULLIF(TRIM(creator_id), ''), 'Unknown Creator')
                    ) FROM downloaded_files;
                """)
                stats["total_creators"] = int(cursor.fetchone()[0] or 0)

                # Total posts (null-safe concatenation and fallback)
                cursor.execute("""
                    SELECT COUNT(DISTINCT 
                        COALESCE(NULLIF(TRIM(service), ''), 'unknown') || ':' || 
                        COALESCE(NULLIF(TRIM(post_id), ''), NULLIF(TRIM(post_title), ''), CAST(id AS TEXT))
                    ) FROM downloaded_files;
                """)
                stats["total_posts"] = int(cursor.fetchone()[0] or 0)

                # Service breakdown
                cursor.execute("""
                    SELECT COALESCE(NULLIF(TRIM(LOWER(service)), ''), 'unknown'), COUNT(*)
                    FROM downloaded_files
                    GROUP BY COALESCE(NULLIF(TRIM(LOWER(service)), ''), 'unknown');
                """)
                for s_row in cursor.fetchall():
                    stats["service_counts"][str(s_row[0]).lower()] = int(s_row[1])

                # Extension / Category breakdown
                cursor.execute("SELECT LOWER(COALESCE(file_ext, '')), COUNT(*) FROM downloaded_files GROUP BY LOWER(COALESCE(file_ext, ''));")
                for ext_row in cursor.fetchall():
                    ext_str = str(ext_row[0] or "").lower()
                    cnt = int(ext_row[1])
                    matched_cat = False
                    for cat, ext_set in FILE_TYPE_CATEGORIES.items():
                        if ext_str in ext_set:
                            stats["category_counts"][cat] += cnt
                            matched_cat = True
                            break
                    if not matched_cat:
                        stats["category_counts"]["other"] += cnt

                # Missing & Verified telemetry
                cursor.execute("SELECT COUNT(*) FROM downloaded_files WHERE is_missing = 1;")
                missing_cnt = int(cursor.fetchone()[0] or 0)
                stats["category_counts"]["removed"] = missing_cnt
                stats["missing_files"] = missing_cnt

                cursor.execute("SELECT COUNT(*) FROM downloaded_files WHERE is_missing = 0;")
                stats["verified_files"] = int(cursor.fetchone()[0] or 0)

                stats["total_links"] = stats["category_counts"].get("links", 0)
                with self._stats_cache_lock:
                    self._stats_cache = dict(stats)
                    self._stats_cache_time = now
                return stats
            except Exception as e:
                logger.error(f"Failed to calculate archive statistics: {e}", category="archive")
                self._note_error(e)
                return stats

    def _statistics_from_index(self, conn: sqlite3.Connection, stats: Dict[str, Any]) -> None:
        """get_statistics from the summary tables (every record was counted several times over)."""
        creators = set()
        total = missing = verified = 0
        for svc, cid, cname, n, n_missing, n_verified in conn.execute(
                "SELECT service, creator_id, creator_name, files, missing, verified FROM archive_creators;"):
            if not n:
                continue
            s_key = (str(svc or "").strip() or "unknown")
            creators.add(s_key + ":" + (str(cname or "").strip() or str(cid or "").strip() or "Unknown Creator"))
            total += int(n or 0)
            missing += int(n_missing or 0)
            verified += int(n_verified or 0)
            sc = str(svc or "").strip().lower() or "unknown"
            stats["service_counts"][sc] = stats["service_counts"].get(sc, 0) + int(n or 0)
        stats["total_files"] = total
        stats["total_creators"] = len(creators)
        stats["total_posts"] = int(conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT service, post_id FROM archive_posts);").fetchone()[0] or 0)
        for ext, cnt in conn.execute("SELECT ext, files FROM archive_exts;"):
            ext_str = str(ext or "").lower()
            for cat, ext_set in FILE_TYPE_CATEGORIES.items():
                if ext_str in ext_set:
                    stats["category_counts"][cat] += int(cnt or 0)
                    break
            else:
                stats["category_counts"]["other"] += int(cnt or 0)
        stats["category_counts"]["removed"] = missing
        stats["missing_files"] = missing
        stats["verified_files"] = verified
        stats["total_links"] = stats["category_counts"].get("links", 0)

    def get_creator_character_profile(
        self,
        service: str,
        creator_id: str,
        creator_name: Optional[str] = None,
        limit: int = 5,
        base_dirs: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extracts recurring series, characters, folder hierarchies, and recent post titles
        for a given creator from past records in download_archive.db.
        Provides high-value contextual priors for AI reasoning and disambiguation.

        base_dirs: the download folder(s). Only folders between a download folder and the creator
        folder are franchise / character folders (otherwise the download folder itself, e.g.
        "KemonoDownloads", was taken for a franchise).
        """
        bases = [os.path.abspath(b) for b in (base_dirs or []) if b]
        clean_svc = str(service or "").strip().lower()
        clean_cid = str(creator_id or "").strip()
        clean_cname = str(creator_name or "").strip()

        result: Dict[str, Any] = {
            "creator_id": clean_cid,
            "creator_name": clean_cname,
            "total_posts": 0,
            "top_franchises": [],
            "top_characters": [],
            "sample_titles": [],
        }

        with self._lock:
            if self._conn is None:
                if not os.path.exists(self.db_path):
                    return result
                self._init_db_unlocked()
            if self._conn is None:
                return result

            try:
                cursor = self._conn.cursor()
                query = """
                    SELECT DISTINCT post_id, post_title, file_path
                    FROM downloaded_files
                    WHERE service = ?
                      AND (
                          creator_id = ?
                          OR (? != '' AND creator_name = ?)
                          OR (? != '' AND creator_id = ?)
                      )
                    ORDER BY id DESC
                    LIMIT 200;
                """
                cursor.execute(
                    query,
                    (clean_svc, clean_cid, clean_cname, clean_cname, clean_cname, clean_cname)
                )
                rows = cursor.fetchall()

                if not rows:
                    return result

                seen_posts = set()
                sample_titles = []
                franchise_counts: Dict[str, int] = {}
                character_counts: Dict[Tuple[str, str], int] = {}

                creator_folder_marker = f"[{clean_svc}]".lower()

                for post_id, post_title, file_path in rows:
                    if post_id not in seen_posts:
                        seen_posts.add(post_id)
                        if post_title and post_title.strip() and len(sample_titles) < 15:
                            sample_titles.append(post_title.strip())

                    # Parse file_path to extract franchise/character folder structure
                    if file_path:
                        if bases:
                            # Folders between the download folder and "Creator [service]":
                            # [download folder, Franchise, Character, Creator [service], ...]
                            # or [download folder, Franchise, Creator [service], ...]
                            full = os.path.abspath(file_path)
                            base = next((b for b in bases
                                         if os.path.normcase(full).startswith(os.path.normcase(b) + os.sep)), None)
                            if base is None:
                                continue
                            rel_parts = os.path.relpath(full, base).split(os.sep)[:-1]
                            creator_idx = next((i for i, part in enumerate(rel_parts)
                                                if creator_folder_marker in part.lower()), -1)
                            hierarchy = rel_parts[:creator_idx] if creator_idx >= 0 else []
                        else:
                            # Download folder unknown: everything before the creator folder (less exact)
                            parts = [p for p in os.path.normpath(file_path).replace("\\", "/").split("/") if p]
                            creator_idx = next((i for i, part in enumerate(parts)
                                                if creator_folder_marker in part.lower()), -1)
                            hierarchy = parts[:creator_idx] if creator_idx >= 1 else []
                        if hierarchy:
                            # Exclude drive letters or generic roots
                            valid_hierarchy = [
                                h for h in hierarchy
                                if not re.match(r"^[a-zA-Z]:$", h)
                                and h.lower() not in {"downloads", "kemono", "pawchive", "other", "content"}
                            ]
                            if len(valid_hierarchy) >= 2:
                                fr = valid_hierarchy[-2]
                                ch = valid_hierarchy[-1]
                                franchise_counts[fr] = franchise_counts.get(fr, 0) + 1
                                character_counts[(fr, ch)] = character_counts.get((fr, ch), 0) + 1
                            elif len(valid_hierarchy) == 1:
                                fr = valid_hierarchy[-1]
                                franchise_counts[fr] = franchise_counts.get(fr, 0) + 1

                result["total_posts"] = len(seen_posts)
                result["sample_titles"] = sample_titles

                # Sort top franchises
                sorted_fr = sorted(franchise_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
                result["top_franchises"] = [{"name": name, "count": count} for name, count in sorted_fr]

                # Sort top characters
                sorted_ch = sorted(character_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
                result["top_characters"] = [
                    {"franchise": fr, "character": ch, "count": count}
                    for (fr, ch), count in sorted_ch
                ]

                return result

            except Exception as e:
                logger.error(f"Failed to generate creator character profile: {e}", category="archive")
                self._note_error(e)
                return result
