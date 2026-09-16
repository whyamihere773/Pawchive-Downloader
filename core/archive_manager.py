"""
Download Archive Database Subsystem
Provides optional, isolated persistence of successfully downloaded files (gallery-dl / yt-dlp style).
When enabled, subsequent downloads query this database and skip files even if they have been
moved, unzipped, or deleted locally.
When disabled, the database is completely inactive and does not touch disk or perform queries.
"""

import os
import sys
import sqlite3
import datetime
import threading
from typing import Optional
from core.logger import logger


class ArchiveManager:
    """Manages the download archive SQLite database with complete opt-in isolation."""

    def __init__(self, config_dir: Optional[str] = None, enabled: bool = False):
        if not config_dir:
            if getattr(sys, "frozen", False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_dir = os.path.join(base_dir, "config")
        else:
            self.config_dir = config_dir

        self.db_path = os.path.join(self.config_dir, "download_archive.db")
        self._enabled = bool(enabled)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

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
        """Initialize connection and schema (must be called with self._lock held)."""
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
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS downloaded_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT NOT NULL,
                    creator_id TEXT,
                    post_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    file_hash TEXT,
                    filename TEXT,
                    downloaded_at TEXT NOT NULL
                );
            """)
            self._conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_archive_unique
                ON downloaded_files(service, post_id, file_id);
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_archive_hash
                ON downloaded_files(file_hash);
            """)
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize download archive database: {e}", category="archive")
            self._conn = None

    def _close_unlocked(self) -> None:
        """Close database connection (must be called with self._lock held)."""
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
                    (service, str(post_id), str(file_id))
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
                return False

    def record_file(
        self,
        service: str,
        creator_id: str,
        post_id: str,
        file_id: str,
        file_hash: str = "",
        filename: str = ""
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
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO downloaded_files
                    (service, creator_id, post_id, file_id, file_hash, filename, downloaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        str(service or ""),
                        str(creator_id or ""),
                        str(post_id or ""),
                        str(file_id or ""),
                        clean_hash,
                        str(filename or ""),
                        now_str
                    )
                )
                self._conn.commit()
                return True
            except Exception as e:
                logger.warning(f"Failed to record file in download archive: {e}", category="archive")
                return False

    def get_total_count(self) -> int:
        """Return total count of archived file records. Returns 0 if disabled or empty."""
        if not self._enabled and not os.path.exists(self.db_path):
            return 0

        with self._lock:
            if self._conn is None:
                if not os.path.exists(self.db_path):
                    return 0
                self._init_db_unlocked()
            if self._conn is None:
                return 0

            try:
                cursor = self._conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM downloaded_files;")
                row = cursor.fetchone()
                return int(row[0]) if row else 0
            except Exception as e:
                logger.debug(f"Failed to query archive record count: {e}", category="archive")
                return 0

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
                logger.info("🗑️ Download Archive Database cleared.", category="archive")
                return True
            except Exception as e:
                logger.error(f"Failed to clear download archive database: {e}", category="archive")
                return False
