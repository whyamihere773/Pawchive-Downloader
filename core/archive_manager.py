"""
Download Archive Database Subsystem
Provides optional, isolated persistence of successfully downloaded files (a "download archive", the idea
known from gallery-dl / yt-dlp; the files are this app's own format, not interchangeable with theirs).
When enabled, subsequent downloads query this database and skip files even if they have been
moved, unzipped, or deleted locally.
When disabled, the database is completely inactive and does not touch disk or perform queries.
"""

import os
import re
import json
import time
import sqlite3
import datetime
import threading
from typing import Optional, List, Dict, Any, Tuple, Callable
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


class ArchiveManager:
    """Manages the download archive SQLite database with complete opt-in isolation."""

    def __init__(self, config_dir: Optional[str] = None, enabled: bool = False):
        from core.path_utils import get_config_dir
        self.config_dir = get_config_dir(config_dir)

        self.db_path = os.path.join(self.config_dir, "download_archive.db")
        self._enabled = bool(enabled)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._stats_cache: Optional[Dict[str, Any]] = None
        self._stats_cache_time: float = 0.0
        # The Archive tab reads through its own connection: in WAL mode it can read while downloads
        # write, so a big archive no longer holds up downloads (and the window) on every refresh
        self._rconn: Optional[sqlite3.Connection] = None
        self._rlock = threading.Lock()
        self._last_count = 0
        # Which raw (service, creator_id, creator_name) rows make up each creator shown in the tab
        self._creator_members: Dict[Tuple[str, str], List[Tuple[str, str, str]]] = {}
        self.last_error = ""
        self._repair_lock = threading.Lock()
        self._auto_repair_tried = False        # repaired by itself at most once per session
        self.on_repair_finished: Optional[Callable[[Dict[str, Any]], None]] = None

        if self._enabled:
            self._init_db()

    @property
    def is_enabled(self) -> bool:
        """Return whether download archiving is actively enabled."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Toggle the archive database on or off with clean resource management."""
        with self._lock:
            new_state = bool(enabled)
            if self._enabled == new_state:
                return
            self._enabled = new_state
            if self._enabled:
                self._init_db_unlocked()
                logger.info("📦 Download Archive Database enabled.", category="archive")
            else:
                self._close_unlocked()
                logger.info("📦 Download Archive Database disabled.", category="archive")

    def _init_db(self) -> None:
        """Thread-safe database initialization."""
        with self._lock:
            self._init_db_unlocked()

    def _init_db_unlocked(self) -> None:
        """Initialize connection, schema, and perform non-destructive migrations."""
        if self._conn is not None:
            return
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            self._conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._create_schema(self._conn)
        except Exception as e:
            logger.error(f"Failed to initialize download archive database: {e}", category="archive")
            self._conn = None

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """Tables, columns added by later versions, indexes and the one-time data repair."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL,
                creator_id TEXT,
                creator_name TEXT,
                post_id TEXT NOT NULL,
                post_title TEXT,
                file_id TEXT NOT NULL,
                file_hash TEXT,
                filename TEXT,
                file_size INTEGER DEFAULT 0,
                file_ext TEXT,
                downloaded_at TEXT NOT NULL
            );
        """)

        # Migration check: ensure new columns exist for existing databases
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(downloaded_files);")
        existing_cols = {row[1] for row in cursor.fetchall()}
        cols_to_add = [
            ("creator_name", "TEXT"),
            ("post_title", "TEXT"),
            ("file_size", "INTEGER DEFAULT 0"),
            ("file_ext", "TEXT"),
            ("file_path", "TEXT"),
            ("is_missing", "INTEGER DEFAULT -1"),
            ("last_verified_at", "TEXT"),
        ]
        for col_name, col_type in cols_to_add:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE downloaded_files ADD COLUMN {col_name} {col_type};")
                except Exception as me:
                    logger.debug(f"Migration column {col_name} already present or failed: {me}", category="archive")

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_archive_unique
            ON downloaded_files(service, post_id, file_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archive_hash
            ON downloaded_files(file_hash);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archive_creator
            ON downloaded_files(service, creator_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archive_post
            ON downloaded_files(service, post_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archive_ext
            ON downloaded_files(file_ext);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archive_missing
            ON downloaded_files(is_missing);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archive_downloaded_at
            ON downloaded_files(downloaded_at);
        """)

        # Data repair and migration for legacy, imported, or partially-populated databases
        try:
            cursor.execute("PRAGMA user_version;")
            v_row = cursor.fetchone()
            schema_ver = int(v_row[0] or 0) if v_row else 0
            if schema_ver < 2:
                # 1. Backfill file_ext from filename if missing or empty
                cursor.execute(
                    "SELECT id, filename FROM downloaded_files "
                    "WHERE (file_ext IS NULL OR file_ext = '') "
                    "  AND filename IS NOT NULL AND filename != '';"
                )
                rows_to_fix = cursor.fetchall()
                if rows_to_fix:
                    ext_updates = []
                    for r_id, r_fn in rows_to_fix:
                        _, ext = os.path.splitext(r_fn)
                        ext_updates.append((ext.lower(), r_id))
                    cursor.executemany("UPDATE downloaded_files SET file_ext = ? WHERE id = ?;", ext_updates)

                # 2. Repair empty/NULL service
                conn.execute("""
                    UPDATE downloaded_files
                    SET service = 'unknown'
                    WHERE service IS NULL OR TRIM(service) = '';
                """)

                # 3. Synchronize / repair creator_name and creator_id
                conn.execute("""
                    UPDATE downloaded_files
                    SET creator_name = creator_id
                    WHERE (creator_name IS NULL OR TRIM(creator_name) = '')
                      AND creator_id IS NOT NULL AND TRIM(creator_id) != '';
                """)
                conn.execute("""
                    UPDATE downloaded_files
                    SET creator_id = creator_name
                    WHERE (creator_id IS NULL OR TRIM(creator_id) = '')
                      AND creator_name IS NOT NULL AND TRIM(creator_name) != '';
                """)
                conn.execute("""
                    UPDATE downloaded_files
                    SET creator_id = 'unknown', creator_name = 'Unknown Creator'
                    WHERE (creator_id IS NULL OR TRIM(creator_id) = '')
                      AND (creator_name IS NULL OR TRIM(creator_name) = '');
                """)

                # 4. Repair empty/NULL post_id and post_title
                conn.execute("""
                    UPDATE downloaded_files
                    SET post_id = COALESCE(NULLIF(TRIM(file_id), ''), CAST(id AS TEXT), 'unknown')
                    WHERE post_id IS NULL OR TRIM(post_id) = '';
                """)
                conn.execute("""
                    UPDATE downloaded_files
                    SET post_title = 'Archived Files'
                    WHERE (post_title IS NULL OR TRIM(post_title) = '')
                      AND (post_id = 'unknown' OR post_id = '0');
                """)
                conn.execute("PRAGMA user_version = 2;")
        except Exception as e_repair:
            logger.debug(f"Archive repair migration notice: {e_repair}", category="archive")

        conn.commit()

    def _close_unlocked(self) -> None:
        """Close database connection (must be called with self._lock held)."""
        with self._rlock:
            if self._rconn is not None:
                try:
                    self._rconn.close()
                except Exception:
                    pass
                self._rconn = None
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def close(self) -> None:
        """Safely close database connection."""
        with self._lock:
            self._close_unlocked()

    def checkpoint(self) -> None:
        """Fold the write-ahead log into the database file (when the app closes: if it is then
        stopped hard, nothing is left only in download_archive.db-wal)."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                except Exception as e:
                    logger.debug(f"Archive checkpoint skipped: {e}", category="archive")

    # ── Reading for the Archive tab ────────────────────────────────────────────

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

    def get_creator_summaries(self, query: str = "", service: str = "all", file_type: str = "all",
                              sort_by: str = "creator_az") -> List[Dict[str, Any]]:
        """One entry per creator (file / post counts, dates), without their posts and files: those
        are read with get_creator_posts when a creator is opened. Sending every file of a big archive
        to the window on each refresh froze it (#28)."""
        if not self._ensure_db():
            return []
        where, params = self._where(query, service, file_type)
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
                rows = conn.execute(sql, params).fetchall()
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
                          file_type: str = "all") -> List[Dict[str, Any]]:
        """The posts (with their files) of one creator from get_creator_summaries ("service|name")."""
        if not self._ensure_db():
            return []
        svc, _, name = str(creator_key or "").partition("|")
        key = (svc, name)
        where, params = self._where(query, service, file_type)
        member = self._creator_members.get(key) or []
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
                rows = [r for r in conn.execute(sql, params) if self._creator_key(r[1], r[2], r[3]) == key]
        except Exception as e:
            logger.error(f"Failed to read the archive's posts for {name}: {e}", category="archive")
            self._note_error(e)
            return []
        tree = self._build_hierarchy(rows, "creator_az")
        return tree[0]["posts"] if tree else []

    # ── Damaged database ───────────────────────────────────────────────────────

    @staticmethod
    def _is_damage(e: Exception) -> bool:
        msg = str(e).lower()
        return isinstance(e, sqlite3.DatabaseError) and (
            "malformed" in msg or "corrupt" in msg or "not a database" in msg)

    def _note_error(self, e: Exception) -> None:
        """Remembers the error for the window; a damaged database is repaired in the background."""
        self.last_error = str(e)
        if self._is_damage(e) and not self._auto_repair_tried and not self._repair_lock.locked():
            self._auto_repair_tried = True
            threading.Thread(target=self.repair, name="ArchiveRepair", daemon=True).start()

    def repair(self) -> Dict[str, Any]:
        """Repairs a damaged ("database disk image is malformed") archive.

        A copy of the damaged file is kept first. Damage in the indexes is fixed by REINDEX, which
        rebuilds them from the records; if the records themselves are damaged, every record that can
        still be read is copied into a new database file that replaces the old one."""
        result: Dict[str, Any] = {"ok": False, "method": "", "kept": 0, "lost": 0, "backup": "", "error": ""}
        if not self._repair_lock.acquire(blocking=False):
            result["error"] = "A repair is already running."
            return result
        try:
            with self._lock:
                if self._conn is None:
                    self._init_db_unlocked()
                if self._conn is None:
                    result["error"] = "The archive database can't be opened."
                    return self._finish_repair(result)
                logger.warning("📦 The download archive database is damaged; repairing it…", category="archive")
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                except Exception:
                    pass
                backup = f"{self.db_path}.damaged-{time.strftime('%Y%m%d-%H%M%S')}.bak"
                try:
                    import shutil
                    shutil.copy2(self.db_path, backup)
                    if os.path.exists(self.db_path + "-wal"):
                        shutil.copy2(self.db_path + "-wal", backup + "-wal")
                    result["backup"] = backup
                except OSError as be:
                    result["error"] = f"Couldn't make a backup copy first: {be}"
                    return self._finish_repair(result)

                # 1. Damaged indexes: rebuilt from the records
                try:
                    self._conn.execute("REINDEX;")
                    self._conn.commit()
                    if self._quick_check(self._conn):
                        count = self._conn.execute("SELECT COUNT(*) FROM downloaded_files;").fetchone()[0]
                        result.update(ok=True, method="reindex", kept=int(count or 0))
                        return self._finish_repair(result)
                except Exception as re_err:
                    logger.info(f"REINDEX didn't repair the archive ({re_err}); copying the readable records…",
                                category="archive")

                # 2. Damaged records: everything still readable goes into a new file
                kept, lost = self._salvage_unlocked()
                result.update(ok=kept >= 0, method="salvage", kept=max(kept, 0), lost=lost)
                if kept < 0:
                    result["error"] = "The readable records couldn't be copied (the damaged file was left as it was)."
                return self._finish_repair(result)
        except Exception as e:
            result["error"] = str(e)
            return self._finish_repair(result)
        finally:
            self._repair_lock.release()

    @staticmethod
    def _quick_check(conn: sqlite3.Connection) -> bool:
        try:
            row = conn.execute("PRAGMA quick_check;").fetchone()
            return bool(row) and str(row[0]).lower() == "ok"
        except Exception:
            return False

    def _salvage_unlocked(self) -> Tuple[int, int]:
        """Copies every readable record into a new database that then replaces the damaged one.
        Returns (records kept, records lost); kept is -1 when it failed (the old file is left)."""
        tmp = self.db_path + ".repairing"
        for f in (tmp, tmp + "-wal", tmp + "-shm"):
            if os.path.exists(f):
                os.remove(f)
        new = sqlite3.connect(tmp)
        try:
            self._create_schema(new)
            old_cols = [r[1] for r in self._conn.execute("PRAGMA table_info(downloaded_files);")]
            new_cols = {r[1] for r in new.execute("PRAGMA table_info(downloaded_files);")}
            cols = [c for c in old_cols if c in new_cols]
            col_sql = ", ".join(cols)
            insert = f"INSERT OR IGNORE INTO downloaded_files ({col_sql}) VALUES ({','.join(['?'] * len(cols))});"
            try:
                max_id = int(self._conn.execute("SELECT MAX(id) FROM downloaded_files;").fetchone()[0] or 0)
            except Exception:
                try:
                    row = self._conn.execute("SELECT seq FROM sqlite_sequence WHERE name='downloaded_files';").fetchone()
                    max_id = int(row[0] or 0) if row else 10_000_000
                except Exception:
                    max_id = 10_000_000

            def copy_range(lo: int, hi: int, step: int) -> Tuple[int, int]:
                """Copies ids lo..hi-1; a range that can't be read is split down to single records."""
                k = n_lost = 0
                for a in range(lo, hi, step):
                    b = min(a + step, hi)
                    try:
                        rows = self._conn.execute(
                            f"SELECT {col_sql} FROM downloaded_files WHERE id >= ? AND id < ?;", (a, b)).fetchall()
                        new.executemany(insert, rows)
                        k += len(rows)
                    except sqlite3.DatabaseError:
                        if step == 1:
                            n_lost += 1
                        else:
                            dk, dl = copy_range(a, b, max(1, step // 20))
                            k += dk
                            n_lost += dl
                return k, n_lost

            kept, lost = copy_range(0, max_id + 1, 5000)
            if kept == 0 and lost > 0:
                # Nothing at all could be read: an empty archive mustn't replace it
                raise sqlite3.DatabaseError("none of its records can be read")
            new.execute("PRAGMA user_version = 2;")
            new.commit()
            if not self._quick_check(new):
                raise sqlite3.DatabaseError("the repaired copy didn't pass its check")
        except Exception as e:
            logger.error(f"Couldn't repair the archive database: {e}", category="archive")
            new.close()
            for f in (tmp, tmp + "-wal", tmp + "-shm"):
                try:
                    os.remove(f)
                except OSError:
                    pass
            return -1, 0
        new.close()
        self._close_unlocked()
        for f in (self.db_path + "-wal", self.db_path + "-shm"):
            try:
                os.remove(f)
            except OSError:
                pass
        os.replace(tmp, self.db_path)
        self._init_db_unlocked()
        return kept, lost

    def _finish_repair(self, result: Dict[str, Any]) -> Dict[str, Any]:
        self._stats_cache = None
        if result.get("ok"):
            self.last_error = ""
            lost = f", {result['lost']} unreadable record(s) dropped" if result.get("lost") else ""
            logger.success(f"📦 Archive database repaired ({result['method']}): {result['kept']} records kept{lost}. "
                           f"A copy of the damaged file was kept: {result.get('backup')}", category="archive")
        else:
            logger.error(f"📦 Archive database repair failed: {result.get('error') or 'see the messages above'}",
                         category="archive")
        if self.on_repair_finished:
            try:
                self.on_repair_finished(dict(result))
            except Exception:
                pass
        return result

    def is_archived(
        self,
        service: str,
        post_id: str,
        file_id: str,
        file_hash: str = ""
    ) -> bool:
        """
        Check if a file has previously been downloaded and recorded in the archive.
        Returns False immediately if archiving is disabled or on error (fail-open).
        """
        if not self._enabled:
            return False

        with self._lock:
            if self._conn is None:
                self._init_db_unlocked()
            if self._conn is None:
                return False

            try:
                cursor = self._conn.cursor()
                # Fast path: check by service + post_id + file_id
                cursor.execute(
                    "SELECT 1 FROM downloaded_files WHERE service = ? AND post_id = ? AND file_id = ? LIMIT 1;",
                    (str(service or "").lower(), str(post_id or ""), str(file_id or ""))
                )
                if cursor.fetchone() is not None:
                    return True

                # Secondary check: if file_hash (SHA-256 / MD5) is provided and non-empty
                clean_hash = (file_hash or "").strip()
                if clean_hash:
                    cursor.execute(
                        "SELECT 1 FROM downloaded_files WHERE file_hash = ? LIMIT 1;",
                        (clean_hash,)
                    )
                    if cursor.fetchone() is not None:
                        return True

                return False
            except Exception as e:
                logger.warning(f"Archive lookup failed (failing open): {e}", category="archive")
                self._note_error(e)
                return False

    def record_file(
        self,
        service: str,
        creator_id: str,
        post_id: str,
        file_id: str,
        file_hash: str = "",
        filename: str = "",
        creator_name: str = "",
        post_title: str = "",
        file_size: int = 0,
        file_ext: str = "",
        file_path: str = ""
    ) -> bool:
        """
        Record a successfully downloaded file into the archive database.
        Returns False immediately if archiving is disabled.
        """
        if not self._enabled:
            return False

        with self._lock:
            if self._conn is None:
                self._init_db_unlocked()
            if self._conn is None:
                return False

            try:
                now_str = datetime.datetime.now().isoformat()
                clean_hash = (file_hash or "").strip()
                clean_filename = str(filename or "").strip()
                clean_path = str(file_path or "").strip()
                is_missing_val = 0 if clean_path else -1
                verified_at_val = now_str if clean_path else None

                if not file_ext and clean_filename:
                    _, ext = os.path.splitext(clean_filename.lower())
                    file_ext = ext
                else:
                    file_ext = str(file_ext or "").lower()

                self._conn.execute(
                    """
                    INSERT INTO downloaded_files
                    (service, creator_id, creator_name, post_id, post_title, file_id, file_hash, filename, file_size, file_ext, downloaded_at, file_path, is_missing, last_verified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(service, post_id, file_id) DO UPDATE SET
                        creator_name = CASE WHEN excluded.creator_name != '' THEN excluded.creator_name ELSE downloaded_files.creator_name END,
                        post_title = CASE WHEN excluded.post_title != '' THEN excluded.post_title ELSE downloaded_files.post_title END,
                        file_hash = CASE WHEN excluded.file_hash != '' THEN excluded.file_hash ELSE downloaded_files.file_hash END,
                        filename = CASE WHEN excluded.filename != '' THEN excluded.filename ELSE downloaded_files.filename END,
                        file_size = CASE WHEN excluded.file_size > 0 THEN excluded.file_size ELSE downloaded_files.file_size END,
                        file_ext = CASE WHEN excluded.file_ext != '' THEN excluded.file_ext ELSE downloaded_files.file_ext END,
                        downloaded_at = excluded.downloaded_at,
                        file_path = CASE WHEN excluded.file_path != '' THEN excluded.file_path ELSE downloaded_files.file_path END,
                        is_missing = CASE WHEN excluded.file_path != '' THEN 0 ELSE downloaded_files.is_missing END,
                        last_verified_at = CASE WHEN excluded.file_path != '' THEN excluded.last_verified_at ELSE downloaded_files.last_verified_at END;
                    """,
                    (
                        str(service or "").lower(),
                        str(creator_id or ""),
                        str(creator_name or ""),
                        str(post_id or ""),
                        str(post_title or ""),
                        str(file_id or ""),
                        clean_hash,
                        clean_filename,
                        int(file_size or 0),
                        file_ext,
                        now_str,
                        clean_path,
                        is_missing_val,
                        verified_at_val
                    )
                )
                self._conn.commit()
                self._stats_cache = None
                return True
            except Exception as e:
                logger.warning(f"Failed to record file in download archive: {e}", category="archive")
                self._note_error(e)
                return False

    def record_link(
        self,
        service: str,
        creator_id: str,
        post_id: str,
        url: str,
        creator_name: str = "",
        post_title: str = "",
        link_title: str = ""
    ) -> bool:
        """
        Record an external link/URL from a post into the archive database.
        Returns False immediately if archiving is disabled.
        """
        if not self._enabled or not url:
            return False
        clean_url = str(url).strip()
        if not clean_url:
            return False
        import hashlib
        link_hash = hashlib.sha256(clean_url.encode('utf-8', errors='ignore')).hexdigest()
        file_id = f"link_{link_hash[:16]}"
        display_name = (link_title.strip() if link_title else "") or clean_url
        return self.record_file(
            service=service,
            creator_id=creator_id,
            post_id=post_id,
            file_id=file_id,
            file_hash=link_hash,
            filename=display_name,
            creator_name=creator_name,
            post_title=post_title,
            file_size=0,
            file_ext="link"
        )

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
        where_clause, params = self._where(query, service, file_type)
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
        with self._lock:
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
                self._stats_cache = dict(stats)
                self._stats_cache_time = now
                return stats
            except Exception as e:
                logger.error(f"Failed to calculate archive statistics: {e}", category="archive")
                self._note_error(e)
                return stats

    def delete_record(self, record_id: int) -> bool:
        """Delete a single archive record by primary key."""
        with self._lock:
            if self._conn is None:
                if not os.path.exists(self.db_path):
                    return True
                self._init_db_unlocked()
            if self._conn is None:
                return False

            try:
                self._conn.execute("DELETE FROM downloaded_files WHERE id = ?;", (int(record_id),))
                self._conn.commit()
                self._stats_cache = None
                return True
            except Exception as e:
                logger.error(f"Failed to delete archive record {record_id}: {e}", category="archive")
                self._note_error(e)
                return False

    def delete_by_post(self, service: str, post_id: str) -> int:
        """Delete all file records belonging to a specific post."""
        with self._lock:
            if self._conn is None:
                if not os.path.exists(self.db_path):
                    return 0
                self._init_db_unlocked()
            if self._conn is None:
                return 0

            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "DELETE FROM downloaded_files WHERE service = ? AND post_id = ?;",
                    (str(service or "").lower(), str(post_id or ""))
                )
                affected = cursor.rowcount
                self._conn.commit()
                self._stats_cache = None
                return affected
            except Exception as e:
                logger.error(f"Failed to delete archive records for post {post_id}: {e}", category="archive")
                self._note_error(e)
                return -1

    def delete_by_creator(self, creator_id: str, service: str = "") -> int:
        """Delete all file records belonging to a specific creator."""
        with self._lock:
            if self._conn is None:
                if not os.path.exists(self.db_path):
                    return 0
                self._init_db_unlocked()
            if self._conn is None:
                return 0

            try:
                cursor = self._conn.cursor()
                clean_cid = str(creator_id or "")
                clean_svc = str(service or "").lower()
                if clean_svc:
                    cursor.execute(
                        "DELETE FROM downloaded_files WHERE (creator_id = ? OR creator_name = ?) AND service = ?;",
                        (clean_cid, clean_cid, clean_svc)
                    )
                else:
                    cursor.execute(
                        "DELETE FROM downloaded_files WHERE (creator_id = ? OR creator_name = ?);",
                        (clean_cid, clean_cid)
                    )
                affected = cursor.rowcount
                self._conn.commit()
                self._stats_cache = None
                return affected
            except Exception as e:
                logger.error(f"Failed to delete archive records for creator {creator_id}: {e}", category="archive")
                self._note_error(e)
                return -1

    def clear_archive(self) -> bool:
        """Wipe all records from the archive database and vacuum."""
        with self._lock:
            if self._conn is None:
                if not os.path.exists(self.db_path):
                    return True
                self._init_db_unlocked()
            if self._conn is None:
                return False

            try:
                self._conn.execute("DELETE FROM downloaded_files;")
                self._conn.commit()
                self._conn.execute("VACUUM;")
                self._stats_cache = None
                logger.info("🗑️ Download Archive Database cleared.", category="archive")
                return True
            except Exception as e:
                logger.error(f"Failed to clear download archive database: {e}", category="archive")
                self._note_error(e)
                return False

    def export_archive(self, filepath: str, export_format: str = "txt") -> int:
        """
        Export all records to a file. Returns the number exported, or -1 when it failed (the reason
        is in last_error).
        Formats:
        - "txt": plain text list, one "service post_id_file_id" per line (this app's own format)
        - "json": complete metadata JSON structure

        Records are written while they're read (a big archive was first loaded whole into memory),
        through the read connection, so downloads keep going meanwhile.
        """
        if not os.path.exists(self.db_path) or not self._ensure_db():
            return 0
        keys = ("service", "creator_id", "creator_name", "post_id", "post_title",
                "file_id", "file_hash", "filename", "file_size", "file_ext", "downloaded_at")
        tmp = f"{filepath}.part"
        count = 0
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with self._rlock:
                conn = self._reader()
                if conn is None:
                    return 0
                cursor = conn.execute(f"""
                    SELECT {", ".join(keys)}
                    FROM downloaded_files
                    ORDER BY service, post_id;
                """)
                with open(tmp, "w", encoding="utf-8") as f:
                    as_json = export_format.lower() == "json"
                    if as_json:
                        f.write("[")
                    while True:
                        rows = cursor.fetchmany(2000)
                        if not rows:
                            break
                        for r in rows:
                            if as_json:
                                f.write(("\n  " if count == 0 else ",\n  ") + json.dumps(dict(zip(keys, r)), ensure_ascii=False))
                            else:
                                # gallery-dl style: "<service> <post_id>_<file_id>"
                                f.write(f"{r[0]} {r[3]}_{r[5]}\n")
                            count += 1
                    if as_json:
                        f.write("\n]\n" if count else "]\n")
            if count == 0:
                os.remove(tmp)
                return 0
            os.replace(tmp, filepath)
            logger.info(f"📤 Exported {count} archive records to '{filepath}'", category="archive")
            return count
        except Exception as e:
            logger.error(f"Failed to export archive: {e}", category="archive")
            self._note_error(e)
            try:
                os.remove(tmp)
            except OSError:
                pass
            return -1

    def import_archive(self, filepath: str) -> int:
        """
        Import records from a text list exported by this app ("service post_id_file_id" per line) or a
        Pawchive JSON export. (gallery-dl's own archives are SQLite databases and can't be imported.)
        """
        if not os.path.exists(filepath):
            return 0

        with self._lock:
            if self._conn is None:
                self._init_db_unlocked()
            if self._conn is None:
                return 0

            try:
                now_str = datetime.datetime.now().isoformat()
                records_to_insert = []

                if filepath.lower().endswith(".json"):
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            svc = str(item.get("service") or "").lower()
                            pid = str(item.get("post_id") or "")
                            fid = str(item.get("file_id") or "")
                            if not svc or not pid or not fid:
                                continue
                            records_to_insert.append((
                                svc,
                                str(item.get("creator_id") or ""),
                                str(item.get("creator_name") or ""),
                                pid,
                                str(item.get("post_title") or ""),
                                fid,
                                str(item.get("file_hash") or ""),
                                str(item.get("filename") or ""),
                                int(item.get("file_size") or 0),
                                str(item.get("file_ext") or ""),
                                str(item.get("downloaded_at") or now_str)
                            ))
                else:
                    # Plain text gallery-dl format lines
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for raw_line in f:
                            line = raw_line.strip()
                            if not line or line.startswith("#"):
                                continue
                            parts = line.split()
                            if len(parts) >= 2:
                                svc = parts[0].lower()
                                target = parts[1]
                                # gallery-dl format is typically "<service> <post_id>_<file_id>" or "<service> <id>"
                                if "_" in target:
                                    subparts = target.split("_", 1)
                                    pid = subparts[0]
                                    fid = subparts[1]
                                else:
                                    pid = target
                                    fid = target
                                records_to_insert.append((
                                    svc, "", "", pid, "", fid, "", "", 0, "", now_str
                                ))

                if not records_to_insert:
                    return 0

                # Filled in the way the one-time repair of old databases does (it no longer runs on
                # every start): extension from the file name, creator id / name from each other
                fixed = []
                for (svc, cid, cname, pid, ptitle, fid, fhash, fname, fsize, fext, at) in records_to_insert:
                    if not fext and fname:
                        fext = os.path.splitext(fname)[1].lower()
                    if not cname and cid:
                        cname = cid
                    elif not cid and cname:
                        cid = cname
                    elif not cid and not cname:
                        cid, cname = "unknown", "Unknown Creator"
                    fixed.append((svc, cid, cname, pid, ptitle, fid, fhash, fname, fsize, fext, at))
                records_to_insert = fixed

                cursor = self._conn.cursor()
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO downloaded_files
                    (service, creator_id, creator_name, post_id, post_title, file_id, file_hash, filename, file_size, file_ext, downloaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    records_to_insert
                )
                imported_count = cursor.rowcount
                self._conn.commit()
                self._stats_cache = None
                logger.info(f"📥 Successfully imported {imported_count} archive records from '{filepath}'", category="archive")
                return imported_count
            except Exception as e:
                logger.error(f"Failed to import archive from '{filepath}': {e}", category="archive")
                self._note_error(e)
                return 0

    def verify_creator_integrity(
        self,
        service: str,
        creator_id: str,
        creator_name: str = "",
        candidate_dirs: Optional[List[str]] = None,
        progress_callback: Optional[Any] = None,
        known_artist_dirs: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Verify physical presence of files on disk for a specific creator.
        Checks existing file_path, and if not found, scans candidate directories
        (such as default download directory, watchlist folders, storage pool paths).
        Updates is_missing (0 = present, 1 = missing) and file_path in SQLite.

        The folder scan runs without holding the database lock (it used to block every download
        worker until the scan of a whole artist tree finished).
        """
        result = {
            "service": service,
            "creator_id": creator_id,
            "total": 0,
            "present": 0,
            "missing": 0,
            "checked_at": datetime.datetime.now().isoformat()
        }

        with self._lock:
            if self._conn is None:
                self._init_db_unlocked()
            if self._conn is None:
                return result
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    """
                    SELECT id, post_id, filename, file_path, file_size
                    FROM downloaded_files
                    WHERE service = ? AND creator_id = ?
                      AND LOWER(file_ext) NOT IN ('.link', '.url', 'link', 'url');
                    """,
                    (str(service).lower(), str(creator_id))
                )
                rows = cursor.fetchall()
            except Exception as e:
                logger.error(f"Failed to verify archive integrity for {creator_id}: {e}", category="archive")
                self._note_error(e)
                return result

        total = len(rows)
        result["total"] = total
        if total == 0:
            return result

        try:
            # 1. Creator folders: names must match exactly ("Al" used to match every folder containing "al")
            from core.filter_engine import FilterEngine
            c_name_clean = (creator_name or "").strip()
            c_id_clean = str(creator_id or "").strip()
            svc_clean = str(service or "").strip().lower()
            names = {n for n in (c_name_clean, c_id_clean,
                                 FilterEngine.clean_filesystem_text(c_name_clean, max_len=80, fallback="") if c_name_clean else "")
                     if n}
            targets = {n.lower() for n in names} | {f"{n} [{svc_clean}]".lower() for n in names}

            artist_dirs = set()
            for d in known_artist_dirs or []:
                if d and os.path.isdir(d):
                    artist_dirs.add(os.path.abspath(d))
            for root_cand in candidate_dirs or []:
                if not root_cand or not os.path.isdir(root_cand):
                    continue
                root_cand = os.path.abspath(root_cand)
                if os.path.basename(root_cand).lower() in targets:
                    artist_dirs.add(root_cand)
                search_roots = [root_cand]
                svc_cand = os.path.join(root_cand, svc_clean)
                if os.path.isdir(svc_cand):
                    search_roots.append(svc_cand)
                for s_root in search_roots:
                    try:
                        with os.scandir(s_root) as it:
                            for entry in it:
                                if entry.is_dir() and entry.name.lower() in targets:
                                    artist_dirs.add(entry.path)
                    except Exception:
                        pass

            # 2. File name index of those folders
            indexed_files: Dict[str, List[str]] = {}
            for a_dir in artist_dirs:
                try:
                    for root_dir, _, filenames in os.walk(a_dir):
                        for fn in filenames:
                            indexed_files.setdefault(fn.lower(), []).append(os.path.join(root_dir, fn))
                except Exception as wex:
                    logger.debug(f"Scan walk error in {a_dir}: {wex}", category="archive")

            # 3. Check each record. A file found elsewhere only counts when it belongs to the same post
            # (its path has the post ID) or has the recorded size; a bare name match ("1.jpg") doesn't.
            now_str = datetime.datetime.now().isoformat()
            updates = []  # (is_missing, file_path, last_verified_at, id)
            present_count = 0
            missing_count = 0
            for idx, row in enumerate(rows):
                r_id, r_post_id, r_fname, r_fpath, r_fsize = row
                found_path = ""
                if r_fpath and os.path.exists(r_fpath) and os.path.getsize(r_fpath) > 0:
                    found_path = r_fpath
                else:
                    candidates = indexed_files.get((r_fname or "").strip().lower(), [])
                    p_match = [c for c in candidates if r_post_id and str(r_post_id) in c]
                    if p_match:
                        found_path = p_match[0]
                    elif candidates and r_fsize:
                        found_path = next((c for c in candidates if os.path.getsize(c) == int(r_fsize)), "")
                    elif len(candidates) == 1:
                        found_path = candidates[0]

                if found_path and os.path.exists(found_path):
                    present_count += 1
                    updates.append((0, found_path, now_str, r_id))
                else:
                    missing_count += 1
                    updates.append((1, r_fpath or "", now_str, r_id))

                if progress_callback and (idx % 25 == 0 or idx == total - 1):
                    try:
                        progress_callback(idx + 1, total)
                    except Exception:
                        pass

            # 4. Save the results
            with self._lock:
                if self._conn is None:
                    return result
                self._conn.cursor().executemany(
                    """
                    UPDATE downloaded_files
                    SET is_missing = ?, file_path = ?, last_verified_at = ?
                    WHERE id = ?;
                    """,
                    updates
                )
                self._conn.commit()

            result["present"] = present_count
            result["missing"] = missing_count
            logger.info(
                f"Verified archive integrity for creator {creator_name} ({creator_id}): "
                f"{present_count} present, {missing_count} missing out of {total} files.",
                category="archive"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to verify archive integrity for {creator_id}: {e}", category="archive")
            self._note_error(e)
            return result

    def remove_missing_for_creator(self, service: str, creator_id: str) -> int:
        """Delete all archive records marked as missing (is_missing = 1) for a creator."""
        with self._lock:
            if self._conn is None:
                if not os.path.exists(self.db_path):
                    return 0
                self._init_db_unlocked()
            if self._conn is None:
                return 0
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "DELETE FROM downloaded_files WHERE service = ? AND creator_id = ? AND is_missing = 1;",
                    (str(service).lower(), str(creator_id))
                )
                deleted = cursor.rowcount
                self._conn.commit()
                self._stats_cache = None
                return deleted
            except Exception as e:
                logger.error(f"Failed to remove missing records for creator {creator_id}: {e}", category="archive")
                self._note_error(e)
                return -1

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


