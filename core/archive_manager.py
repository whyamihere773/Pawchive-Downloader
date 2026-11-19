"""
Download Archive Manager (gallery-dl style persistent download history)
Tracks previously downloaded files in an embedded SQLite database (download_archive.db)
so that files are never re-downloaded even if moved, renamed, or deleted from disk.
Stores full metadata (creator, post, filename, size, extension) for the hierarchical Archive Manager UI.
"""

from contextlib import contextmanager
import os
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import archive_index
from core.archive_io import ArchiveIOMixin
from core.archive_maintenance import ArchiveMaintenanceMixin
from core.archive_queries import ArchiveQueriesMixin, FILE_TYPE_CATEGORIES
from core.logger import logger
from core.path_utils import get_data_dir


class ArchiveManager(
    ArchiveQueriesMixin,
    ArchiveMaintenanceMixin,
    ArchiveIOMixin,
):
    """Thread-safe SQLite-backed download archive manager with full hierarchical querying."""

    def __init__(self, config_dir: Optional[str] = None, enabled: bool = False):
        from core.path_utils import get_config_dir
        self.config_dir = get_config_dir(config_dir)

        self.db_path = os.path.join(self.config_dir, "download_archive.db")
        self._enabled = bool(enabled)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._stats_cache_lock = threading.Lock()
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
        # Summary tables + search index (core/archive_index.py), filled in for existing archives
        self._backfill_thread: Optional[threading.Thread] = None
        self._index_ready = False
        self._maintenance_stop = threading.Event()
        self._paused_depth = 0

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
            return
        self._start_backfill()

    def _create_schema(self, conn: sqlite3.Connection, summaries: bool = True) -> None:
        """Tables, columns added by later versions, indexes, the one-time data repair and (summaries)
        the summary tables + search index."""
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
        # Not needed: (service, post_id) lookups use idx_archive_unique, and the file-type filter /
        # statistics never used the extension index (they compare LOWER(file_ext)). Each one cost
        # hundreds of MB in a big archive.
        conn.execute("DROP INDEX IF EXISTS idx_archive_post;")
        conn.execute("DROP INDEX IF EXISTS idx_archive_ext;")
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
        if summaries:
            try:
                archive_index.ensure(conn)
                if archive_index.is_paused(conn):
                    logger.warning("Detected interrupted archive summary pause state on startup; rebuilding summaries...", category="archive")
                    archive_index.restart(conn)
            except Exception as e_idx:
                logger.warning(f"Archive summaries unavailable ({e_idx}); the Archive tab uses slower queries.",
                               category="archive")

    @contextmanager
    def _paused_index(self, conn: sqlite3.Connection, enabled: bool = True):
        """Re-entrant guard around archive_index.paused so triggers never remain permanently disabled."""
        if not enabled:
            yield
            return
        self._paused_depth += 1
        did_set = False
        if self._paused_depth == 1:
            archive_index.paused(conn, True)
            did_set = True
        try:
            yield
            if self._paused_depth == 1 and did_set:
                archive_index.paused(conn, False)
        except BaseException:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            self._paused_depth = max(0, self._paused_depth - 1)

    def _passive_wal_checkpoint(self, conn: Optional[sqlite3.Connection]) -> None:
        """Runs a non-blocking WAL checkpoint so bulk deletes don't bloat -wal on large archives."""
        if conn is None:
            return
        try:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
        except Exception:
            pass

    def _start_backfill(self) -> None:
        """Fills the summaries / search index in for records that existed before them (an archive
        from an older version, or after a repair), a slice at a time in the background."""
        if self._backfill_thread is not None and self._backfill_thread.is_alive():
            return
        conn = self._conn
        if conn is None:
            return
        try:
            wm, done, _ = archive_index.state(conn)
        except Exception:
            return
        if done >= wm:
            return
        self._index_ready = False

        def _step() -> bool:
            with self._lock:
                if self._conn is None:
                    return True
                try:
                    return archive_index.backfill_step(self._conn)
                except Exception as e:
                    logger.warning(f"Preparing the archive summaries stopped: {e}", category="archive")
                    self._note_error(e)
                    return True

        def _run():
            t0 = time.time()
            if wm - done > 200_000:
                logger.info(f"📦 Preparing the download archive for fast browsing and search "
                            f"({wm - done:,} records, in the background)…", category="archive")
            if archive_index.backfill(_step, should_stop=lambda: self._conn is None) and self._conn is not None:
                self._invalidate_stats_cache()
                if wm - done > 200_000:
                    logger.info(f"📦 Download archive ready for fast browsing ({time.time() - t0:.0f} s).",
                                category="archive")
        self._backfill_thread = threading.Thread(target=_run, name="ArchiveSummaries", daemon=True)
        self._backfill_thread.start()

    def _invalidate_stats_cache(self) -> None:
        with self._stats_cache_lock:
            self._stats_cache = None
            self._stats_cache_time = 0.0

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
        self._maintenance_stop.set()
        with self._lock:
            self._close_unlocked()

    def checkpoint(self) -> None:
        """Fold the write-ahead log into the database file (when the app closes: if it is then
        stopped hard, nothing is left only in download_archive.db-wal)."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    self._conn.execute("PRAGMA optimize;")      # keeps the query planner's numbers fresh
                except Exception as e:
                    logger.debug(f"Archive checkpoint skipped: {e}", category="archive")
