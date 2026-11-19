"""
Crash-proof SQLite WAL journal for Archive Rebuild.

Mirrors the Downloader's QueueJournal design:
- Single SQLite WAL database (`archive_rebuild_journal.db`) in the config dir.
- Atomic commits: a sudden power cut, crash, or hard kill always leaves the
  previous committed batch and file cursor intact.
- Stores discovered candidate file paths once after discovery, then advances
  a lightweight `cursor_pos` + `stats` checkpoint after every batch commit,
  on Pause, and on clean shutdown — so resuming skips re-walking the drive
  and skips already-indexed files.
- Fast startup check & summary query without loading the candidate list.
"""

import contextlib
import datetime
import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from core.logger import logger
from core.path_utils import get_config_dir

_UNFINISHED_STATUSES = ("discovering", "indexing", "paused")


class ArchiveRebuildJournal:
    def __init__(self, config_dir: Optional[str] = None, db_path: Optional[str] = None):
        if db_path:
            self.path = db_path
        else:
            self.config_dir = get_config_dir(config_dir)
            os.makedirs(self.config_dir, exist_ok=True)
            self.path = os.path.join(self.config_dir, "archive_rebuild_journal.db")
        self._lock = threading.RLock()
        self._schema_ready = False

    def _open(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0)
        try:
            self._prepare(conn)
        except Exception:
            conn.close()
            raise
        return conn

    def _prepare(self, conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        if not self._schema_ready:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    k TEXT PRIMARY KEY,
                    v TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    pos INTEGER PRIMARY KEY,
                    path TEXT NOT NULL
                );
                """
            )
            conn.commit()
            self._schema_ready = True

    @contextlib.contextmanager
    def _db(self):
        conn = self._open()
        try:
            yield conn
        finally:
            conn.close()

    def _delete_files_unlocked(self) -> None:
        self._schema_ready = False
        for suffix in ("", "-wal", "-shm"):
            p = self.path + suffix
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass

    def clear(self) -> None:
        """Removes the journal cleanly (called on completion, explicit cancel, or discard)."""
        with self._lock:
            self._delete_files_unlocked()

    def begin_session(self, directories: List[str], options: Dict[str, Any]) -> bool:
        """Records a new rebuild session before folder discovery starts."""
        with self._lock:
            try:
                with self._db() as conn:
                    conn.execute("DELETE FROM candidates;")
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    init_stats = {
                        "total_files": 0,
                        "processed_files": 0,
                        "added_count": 0,
                        "skipped_count": 0,
                        "error_count": 0,
                        "total_bytes_hashed": 0,
                        "total_creators": 0,
                        "total_posts": 0,
                        "elapsed_prior": 0.0,
                        "saved_at": now_str,
                    }
                    rows = [
                        ("status", "discovering"),
                        ("directories", json.dumps(list(directories))),
                        ("options", json.dumps(dict(options))),
                        ("cursor_pos", "0"),
                        ("stats", json.dumps(init_stats)),
                        ("saved_at", now_str),
                    ]
                    conn.executemany(
                        "INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?);",
                        rows,
                    )
                    conn.commit()
                return True
            except Exception as e:
                logger.warning(f"ArchiveRebuildJournal.begin_session failed: {e}", category="archive")
                return False

    def save_candidates(self, file_paths: List[str], stats: Dict[str, Any]) -> bool:
        """Atomically stores discovered file paths once so resume never has to re-walk."""
        with self._lock:
            try:
                with self._db() as conn:
                    conn.execute("DELETE FROM candidates;")
                    if file_paths:
                        conn.executemany(
                            "INSERT INTO candidates (pos, path) VALUES (?, ?);",
                            enumerate(file_paths),
                        )
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    payload = dict(stats)
                    payload["saved_at"] = now_str
                    conn.executemany(
                        "INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?);",
                        [
                            ("status", "indexing"),
                            ("cursor_pos", "0"),
                            ("stats", json.dumps(payload)),
                            ("saved_at", now_str),
                        ],
                    )
                    conn.commit()
                return True
            except Exception as e:
                logger.warning(f"ArchiveRebuildJournal.save_candidates failed: {e}", category="archive")
                return False

    def update_checkpoint(
        self,
        cursor_pos: int,
        stats: Dict[str, Any],
        status: str = "indexing",
    ) -> bool:
        """Lightweight atomic cursor & telemetry checkpoint after each committed DB batch."""
        with self._lock:
            try:
                with self._db() as conn:
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    payload = dict(stats)
                    payload["saved_at"] = now_str
                    conn.executemany(
                        "INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?);",
                        [
                            ("status", status),
                            ("cursor_pos", str(max(0, int(cursor_pos)))),
                            ("stats", json.dumps(payload)),
                            ("saved_at", now_str),
                        ],
                    )
                    conn.commit()
                return True
            except Exception as e:
                logger.warning(f"ArchiveRebuildJournal.update_checkpoint failed: {e}", category="archive")
                return False

    def has_unfinished_session(self) -> bool:
        """Fast startup check: returns True if an interrupted archive rebuild exists."""
        with self._lock:
            if not os.path.exists(self.path):
                return False
            try:
                with self._db() as conn:
                    row = conn.execute("SELECT v FROM meta WHERE k = 'status';").fetchone()
                    if not row or row[0] not in _UNFINISHED_STATUSES:
                        return False
                    dirs_row = conn.execute("SELECT v FROM meta WHERE k = 'directories';").fetchone()
                    dirs = json.loads(dirs_row[0]) if dirs_row else []
                    if not dirs:
                        return False
                    if row[0] == "discovering":
                        return True
                    # For indexing/paused, verify there are remaining candidates
                    cur_row = conn.execute("SELECT v FROM meta WHERE k = 'cursor_pos';").fetchone()
                    cur_pos = int(cur_row[0]) if cur_row else 0
                    rem = conn.execute(
                        "SELECT 1 FROM candidates WHERE pos >= ? LIMIT 1;",
                        (cur_pos,),
                    ).fetchone()
                    return rem is not None
            except sqlite3.DatabaseError as e:
                logger.warning(f"Corrupted archive rebuild journal detected, removing: {e}", category="archive")
                self._delete_files_unlocked()
                return False
            except Exception as e:
                logger.debug(f"ArchiveRebuildJournal.has_unfinished_session error: {e}", category="archive")
                return False

    def get_summary(self) -> Dict[str, Any]:
        """Fast metadata summary for startup UI without loading candidate rows."""
        with self._lock:
            if not os.path.exists(self.path):
                return {}
            try:
                with self._db() as conn:
                    meta = dict(conn.execute("SELECT k, v FROM meta;").fetchall())
                    status = meta.get("status", "")
                    if status not in _UNFINISHED_STATUSES:
                        return {}
                    dirs = json.loads(meta.get("directories", "[]"))
                    opts = json.loads(meta.get("options", "{}"))
                    stats = json.loads(meta.get("stats", "{}"))
                    cursor_pos = int(meta.get("cursor_pos", "0") or 0)
                    cand_count_row = conn.execute("SELECT COUNT(*) FROM candidates;").fetchone()
                    cand_count = int(cand_count_row[0]) if cand_count_row else 0
                    total_files = max(int(stats.get("total_files", 0) or 0), cand_count)
                    processed = max(int(stats.get("processed_files", 0) or 0), min(cursor_pos, total_files))
                    pct = round((processed / total_files) * 100.0, 1) if total_files > 0 else 0.0
                    return {
                        "status": status,
                        "directories": dirs,
                        "options": opts,
                        "cursor_pos": cursor_pos,
                        "total_files": total_files,
                        "processed_files": processed,
                        "remaining_files": max(0, total_files - processed),
                        "added_count": int(stats.get("added_count", 0) or 0),
                        "skipped_count": int(stats.get("skipped_count", 0) or 0),
                        "error_count": int(stats.get("error_count", 0) or 0),
                        "total_bytes_hashed": int(stats.get("total_bytes_hashed", 0) or 0),
                        "total_creators": int(stats.get("total_creators", 0) or 0),
                        "total_posts": int(stats.get("total_posts", 0) or 0),
                        "elapsed_prior": float(stats.get("elapsed_prior", 0.0) or 0.0),
                        "percent": pct,
                        "saved_at": meta.get("saved_at", stats.get("saved_at", "")),
                    }
            except sqlite3.DatabaseError as e:
                logger.warning(f"Corrupted archive rebuild journal on summary read, removing: {e}", category="archive")
                self._delete_files_unlocked()
                return {}
            except Exception as e:
                logger.debug(f"ArchiveRebuildJournal.get_summary error: {e}", category="archive")
                return {}

    def load_remaining_candidates(self, cursor_pos: int) -> List[str]:
        """Returns remaining candidate file paths starting from `cursor_pos`."""
        with self._lock:
            if not os.path.exists(self.path):
                return []
            try:
                with self._db() as conn:
                    rows = conn.execute(
                        "SELECT path FROM candidates WHERE pos >= ? ORDER BY pos ASC;",
                        (max(0, int(cursor_pos)),),
                    ).fetchall()
                    return [r[0] for r in rows]
            except Exception as e:
                logger.warning(f"ArchiveRebuildJournal.load_remaining_candidates failed: {e}", category="archive")
                return []
