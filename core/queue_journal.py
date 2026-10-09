"""
Crash journal for the download queue, in SQLite.

The queue used to be saved by rewriting all of it as JSON every 30 seconds (about 700 MB per save for a
million files). Here every task is a row and a save only writes the rows whose task changed (status,
path, error, retries) since the last save. SQLite commits are atomic, so a crash or power cut leaves the
previous save intact. The "unfinished download" check and its summary are SQL queries, so start-up
doesn't load the whole queue.
"""

import contextlib
import json
import os
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.logger import logger

_UNFINISHED = ("pending", "downloading", "retrying")


_MISSING = object()


def _val(t: Any, name: str, default: Any = None) -> Any:
    if isinstance(t, dict):
        return t.get(name, default)
    v = getattr(t, name, _MISSING)
    if v is _MISSING:
        to_dict = getattr(t, "to_dict", None)
        return to_dict().get(name, default) if callable(to_dict) else default
    return v


class QueueJournal:
    def __init__(self, path: str):
        self.path = path
        self._schema_ready = False
        self._lock = threading.RLock()
        self._fp: Dict[str, tuple] = {}         # row key -> what was saved (to find changes)
        self._saved_len = -1

    # ── Database ──────────────────────────────────────────────────────────────
    def _open(self) -> sqlite3.Connection:
        """A connection for one operation: the journal is used every 30 s at most, and an open file
        would stay locked on Windows (it couldn't be moved or deleted)."""
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0)
        try:
            self._prepare(conn)
        except Exception:
            conn.close()          # a damaged file must not stay locked
            raise
        return conn

    def _prepare(self, conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        if not self._schema_ready:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    key TEXT PRIMARY KEY,
                    pos INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    artist TEXT,
                    service TEXT,
                    platform TEXT,
                    total_bytes INTEGER DEFAULT 0,
                    downloaded INTEGER DEFAULT 0,
                    data TEXT NOT NULL,
                    group_key TEXT
                );
            """)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks);")}
            if "group_key" not in cols:
                conn.execute("ALTER TABLE tasks ADD COLUMN group_key TEXT;")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_status ON tasks(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_group ON tasks(group_key);")
            conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);")
            conn.commit()
            self._schema_ready = True

    @contextlib.contextmanager
    def _db(self):
        conn = self._open()
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:
        pass          # nothing stays open

    @staticmethod
    def task_key(t: Any) -> str:
        return f"{_val(t, 'url', '') or ''}\x00{_val(t, 'target_path', '') or ''}"

    @staticmethod
    def _fingerprint(t: Any) -> tuple:
        return (_val(t, "status", "pending"), _val(t, "target_path", ""), _val(t, "error_msg", ""),
                _val(t, "retry_count", 0), _val(t, "file_size", 0), _val(t, "downloaded_bytes", 0))

    # ── Writing ───────────────────────────────────────────────────────────────
    def sync(self, tasks: List[Any], batches: Optional[List[Dict[str, Any]]] = None,
             settings: Optional[Dict[str, Any]] = None, status: str = "interrupted",
             changed: Optional[Iterable[Any]] = None,
             artist_of: Optional[Callable[[Any], str]] = None,
             platform_of: Optional[Callable[[Any], str]] = None) -> int:
        """Saves the queue. With `changed` (tasks whose status changed since the last save) and the
        same number of tasks as last time, only those are looked at; otherwise every task is compared
        with what was saved. Returns the number of rows written."""
        artist_of = artist_of or (lambda t: _val(t, "creator_name", "") or "Unknown Artist")
        platform_of = platform_of or (lambda t: _val(t, "service", "") or "")
        with self._lock:
            with self._db() as conn:
                upserts: List[tuple] = []
                updates: List[tuple] = []
                deletes: List[tuple] = []
                if changed is not None and len(tasks) == self._saved_len and self._fp:
                    for t in changed:
                        k = self.task_key(t)
                        if k not in self._fp:
                            continue                    # not part of this queue (it was replaced)
                        fp = self._fingerprint(t)
                        if self._fp[k] != fp:
                            self._fp[k] = fp
                            updates.append(self._row(k, None, t, artist_of, platform_of))
                else:
                    now_keys = set()
                    for pos, t in enumerate(tasks):
                        k = self.task_key(t)
                        now_keys.add(k)
                        fp = self._fingerprint(t)
                        if self._fp.get(k) != fp:
                            self._fp[k] = fp
                            upserts.append(self._row(k, pos, t, artist_of, platform_of))
                    for k in [k for k in self._fp if k not in now_keys]:
                        del self._fp[k]
                        deletes.append((k,))
                    if not self._fp_loaded_from_disk(conn, now_keys):
                        # rows from an earlier run that aren't in this queue any more
                        deletes.extend((k,) for (k,) in conn.execute("SELECT key FROM tasks;") if k not in now_keys)
                meta = [("status", status), ("saved_at", time.strftime("%Y-%m-%dT%H:%M:%S")),
                        ("settings", json.dumps(settings or {}, ensure_ascii=False, default=str)),
                        ("batches", json.dumps(batches or [], ensure_ascii=False, default=str))]
                with conn:
                    if deletes:
                        conn.executemany("DELETE FROM tasks WHERE key = ?;", deletes)
                    if upserts:
                        conn.executemany("""
                            INSERT INTO tasks (key, pos, status, artist, service, platform, total_bytes, downloaded, data, group_key)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(key) DO UPDATE SET
                                pos = excluded.pos, status = excluded.status, artist = excluded.artist,
                                service = excluded.service, platform = excluded.platform,
                                total_bytes = excluded.total_bytes, downloaded = excluded.downloaded,
                                data = excluded.data, group_key = excluded.group_key;
                        """, upserts)
                    if updates:
                        conn.executemany("""
                            UPDATE tasks SET status = ?, artist = ?, service = ?, platform = ?, total_bytes = ?,
                                             downloaded = ?, data = ?, group_key = ?
                            WHERE key = ?;
                        """, [(u[2], u[3], u[4], u[5], u[6], u[7], u[8], u[9], u[0]) for u in updates])
                    conn.executemany("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?);", meta)
                self._saved_len = len(tasks)
                return len(upserts) + len(updates)

    def _fp_loaded_from_disk(self, conn, now_keys) -> bool:
        """True once the rows already on disk have been matched to this run's queue (the first full
        save of a run checks for leftovers from an earlier one)."""
        if getattr(self, "_disk_checked", False):
            return True
        self._disk_checked = True
        return False

    def _row(self, key: str, pos: Optional[int], t: Any, artist_of, platform_of) -> tuple:
        d = t.to_dict() if hasattr(t, "to_dict") else dict(t)
        f_size = int(d.get("file_size") or 0)
        d_bytes = int(d.get("downloaded_bytes") or 0)
        compact = {k: v for k, v in d.items() if v not in (None, "", 0, False, [], {}) or k == "status"}
        artist = artist_of(t)
        service = d.get("service") or ""
        return (key, pos, d.get("status") or "pending", artist, service, platform_of(t),
                max(f_size, d_bytes), d_bytes,
                json.dumps(compact, ensure_ascii=False, default=str, separators=(",", ":")),
                f"{artist}\x00{service}".lower())

    def clear(self) -> None:
        """Removes the journal file (nothing keeps it open); emptied instead if it can't be removed."""
        with self._lock:
            self._fp.clear()
            self._saved_len = -1
            self._disk_checked = True
            if not os.path.exists(self.path):
                return
            try:
                for f in (self.path, self.path + "-wal", self.path + "-shm"):
                    if os.path.exists(f):
                        os.remove(f)
                self._schema_ready = False
            except OSError:
                with self._db() as conn:
                    with conn:
                        conn.execute("DELETE FROM tasks;")
                        conn.execute("DELETE FROM meta;")

    # ── Reading ───────────────────────────────────────────────────────────────
    def _meta(self, conn) -> Dict[str, str]:
        return {k: v for k, v in conn.execute("SELECT k, v FROM meta;")}

    def has_rows(self) -> bool:
        if not os.path.exists(self.path):
            return False
        with self._lock:
            with self._db() as conn:
                return conn.execute("SELECT 1 FROM tasks LIMIT 1;").fetchone() is not None

    def has_unfinished(self) -> bool:
        """Files that never got their turn (failed ones are kept for Retry Failed instead)."""
        if not os.path.exists(self.path):
            return False
        with self._lock:
            with self._db() as conn:
                if self._meta(conn).get("status") == "completed":
                    return False
                row = conn.execute(f"SELECT 1 FROM tasks WHERE status IN ({','.join('?' * len(_UNFINISHED))}) LIMIT 1;",
                                   _UNFINISHED).fetchone()
                return row is not None

    def summary(self, format_size: Callable[[int], str]) -> Optional[Dict[str, Any]]:
        """The recovery prompt's summary, counted by SQLite (no tasks are loaded)."""
        if not os.path.exists(self.path):
            return None
        with self._lock:
            with self._db() as conn:
                total = conn.execute("""
                    SELECT COUNT(*), COALESCE(SUM(status = 'completed'), 0), COALESCE(SUM(status = 'failed'), 0),
                           COALESCE(SUM(total_bytes), 0), COALESCE(SUM(downloaded), 0) FROM tasks;
                """).fetchone()
                if not total or not total[0]:
                    return None
                n, done, failed, total_bytes, downloaded = (int(x or 0) for x in total)
                artists = []
                for (name, svc, platform, a_total, a_done, a_bytes, a_down) in conn.execute("""
                    SELECT MIN(artist), MIN(service), MIN(platform), COUNT(*), SUM(status = 'completed'),
                           SUM(total_bytes), SUM(downloaded)
                    FROM tasks GROUP BY group_key ORDER BY MIN(pos);
                """):
                    a_total, a_done = int(a_total or 0), int(a_done or 0)
                    artists.append({
                        "name": name or "Unknown Artist", "service": svc or "", "platform": platform or "",
                        "completed": a_done, "total": a_total,
                        "percent": round(a_done / a_total * 100.0, 1) if a_total else 0.0,
                        "formatted_downloaded": format_size(int(a_down or 0)),
                        "formatted_total": format_size(int(a_bytes or 0)),
                    })
                saved_at = self._meta(conn).get("saved_at", "")
        return {
            "artists": artists, "total_files": n, "completed_files": done, "pending_files": n - done - failed,
            "failed_files": failed, "downloaded_bytes": downloaded, "total_bytes": total_bytes,
            "percent": round(done / n * 100.0, 1) if n else 0.0,
            "formatted_downloaded": format_size(downloaded), "formatted_total": format_size(total_bytes),
            "saved_at": saved_at.replace("T", " "),
        }

    def load(self) -> Optional[Dict[str, Any]]:
        """Everything saved: {status, saved_at, settings, batches, tasks (dicts, in queue order)}."""
        if not os.path.exists(self.path):
            return None
        with self._lock:
            with self._db() as conn:
                tasks = [json.loads(d) for (d,) in conn.execute("SELECT data FROM tasks ORDER BY pos;")]
                if not tasks:
                    return None
                meta = self._meta(conn)

        def _j(v, default):
            try:
                return json.loads(v) if v else default
            except ValueError:
                return default
        return {"version": 2, "status": meta.get("status", "interrupted"), "saved_at": meta.get("saved_at", ""),
                "settings": _j(meta.get("settings"), {}), "batches": _j(meta.get("batches"), []), "tasks": tasks}

    def statuses(self) -> List[Tuple[str, int]]:
        if not os.path.exists(self.path):
            return []
        with self._lock:
            with self._db() as conn:
                return list(conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status;"))


def safe_journal_call(fn, default=None):
    """Runs a journal call; a damaged journal file is reported, never a crash."""
    try:
        return fn()
    except sqlite3.DatabaseError as e:
        logger.warning(f"The download recovery journal couldn't be read ({e}).", category="session")
        return default
