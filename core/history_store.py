"""
Download history in SQLite (history.db).

history.json was rewritten whole a few seconds after every downloaded file, with up to 50,000 file ids in
it (the oldest were dropped to keep it at that size). Here a downloaded file is one row added in a batch
with the others of the last few seconds, nothing is dropped, and the History tab's sessions are rows
too.
"""

import contextlib
import os
import sqlite3
import threading
import time
from typing import Any, Dict, Iterable, List

from core.logger import logger

SESSIONS_SHOWN = 500


class HistoryStore:
    def __init__(self, path: str):
        self.path = path
        self._schema_ready = False
        self._lock = threading.Lock()

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def _open(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            if not self._schema_ready:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, at REAL) WITHOUT ROWID;
                    CREATE TABLE IF NOT EXISTS sessions (
                        seq INTEGER PRIMARY KEY AUTOINCREMENT,
                        creator TEXT, url TEXT, service TEXT, files INTEGER, date TEXT
                    );
                """)
                conn.commit()
                self._schema_ready = True
        except Exception:
            conn.close()
            raise
        return conn

    @contextlib.contextmanager
    def _db(self):
        with self._lock:
            conn = self._open()
            try:
                yield conn
            finally:
                conn.close()

    def has_rows(self) -> bool:
        if not self.exists():
            return False
        with self._db() as conn:
            return (conn.execute("SELECT 1 FROM files LIMIT 1;").fetchone() is not None
                    or conn.execute("SELECT 1 FROM sessions LIMIT 1;").fetchone() is not None)

    def add_files(self, ids: Iterable[str]) -> None:
        now = time.time()
        rows = [(str(i), now) for i in ids if i]
        if not rows:
            return
        with self._db() as conn:
            with conn:
                conn.executemany("INSERT OR IGNORE INTO files (id, at) VALUES (?, ?);", rows)

    def has_file(self, file_id: str) -> bool:
        if not self.exists():
            return False
        with self._db() as conn:
            return conn.execute("SELECT 1 FROM files WHERE id = ?;", (str(file_id),)).fetchone() is not None

    def file_count(self) -> int:
        if not self.exists():
            return 0
        with self._db() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM files;").fetchone()[0] or 0)

    def add_sessions(self, entries: List[Dict[str, Any]]) -> None:
        """Oldest first."""
        rows = [(e.get("creator", ""), e.get("url", ""), e.get("service", ""), int(e.get("files") or 0),
                 e.get("date", "")) for e in entries]
        if not rows:
            return
        with self._db() as conn:
            with conn:
                conn.executemany("INSERT INTO sessions (creator, url, service, files, date) VALUES (?, ?, ?, ?, ?);", rows)

    def recent_sessions(self, limit: int = SESSIONS_SHOWN) -> List[Dict[str, Any]]:
        """Newest first."""
        if not self.exists():
            return []
        with self._db() as conn:
            return [{"creator": c, "url": u, "service": s, "files": n, "date": d}
                    for c, u, s, n, d in conn.execute(
                        "SELECT creator, url, service, files, date FROM sessions ORDER BY seq DESC LIMIT ?;", (limit,))]


def import_legacy_json(store: HistoryStore, data: Dict[str, Any]) -> int:
    """Copies an older version's history.json into the database; returns the number of rows."""
    files = [f for f in (data.get("downloaded_files") or []) if isinstance(f, str)]
    sessions = [s for s in (data.get("download_history") or []) if isinstance(s, dict)]
    store.add_files(files)
    store.add_sessions(list(reversed(sessions)))        # the JSON list is newest first
    logger.info(f"Download history moved to the new format ({len(files)} file(s), {len(sessions)} session(s)).",
                category="session")
    return len(files) + len(sessions)
