"""
The Watchlist's storage, in SQLite (watchlist.db).

watchlist.json was rewritten whole on every change: tens of MB for a big watchlist, many times a minute
while downloading. Here every creator is a row and a save writes only the creators that changed. Most
creators share the same download settings, so identical settings are stored once. Updates found by a
check are stored too (they used to be forgotten when the app closed).
"""

import contextlib
import hashlib
import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.logger import logger


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def options_id(options_json: str) -> str:
    return hashlib.sha1(options_json.encode("utf-8")).hexdigest()


class WatchlistStore:
    def __init__(self, path: str):
        self.path = path
        self._schema_ready = False
        self._lock = threading.Lock()
        self._known_options: set = set()        # settings already stored

    # ── Database ──────────────────────────────────────────────────────────────
    def exists(self) -> bool:
        return os.path.exists(self.path)

    def _open(self) -> sqlite3.Connection:
        """A connection per operation: an open file stays locked on Windows (it couldn't be backed
        up, moved or deleted), and the watchlist is written a few times a minute at most."""
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            if not self._schema_ready:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS creators (
                        rid INTEGER PRIMARY KEY,
                        pos INTEGER NOT NULL,
                        service TEXT,
                        user_id TEXT,
                        creator_name TEXT,
                        data TEXT NOT NULL,
                        options_id TEXT,
                        new_posts TEXT
                    );
                    CREATE TABLE IF NOT EXISTS options (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
                """)
                conn.commit()
                self._schema_ready = True
        except Exception:
            conn.close()          # a damaged file must not stay locked
            raise
        return conn

    @contextlib.contextmanager
    def _db(self):
        conn = self._open()
        try:
            yield conn
        finally:
            conn.close()

    # ── Reading ───────────────────────────────────────────────────────────────
    def has_rows(self) -> bool:
        if not self.exists():
            return False
        with self._lock, self._db() as conn:
            return conn.execute("SELECT 1 FROM creators LIMIT 1;").fetchone() is not None

    def load(self) -> List[Tuple[int, int, Dict[str, Any], List[Dict[str, Any]]]]:
        """Every creator as (rid, pos, fields incl. "options", updates found), in watchlist order.
        Raises if the database can't be read (the caller falls back to a backup)."""
        with self._lock, self._db() as conn:
            check = conn.execute("PRAGMA quick_check;").fetchone()
            if not check or check[0] != "ok":
                raise sqlite3.DatabaseError(f"watchlist.db is damaged ({check[0] if check else 'no answer'})")
            options = {oid: json.loads(data) for oid, data in conn.execute("SELECT id, data FROM options;")}
            self._known_options = set(options)
            rows = []
            for rid, pos, data, oid, new_posts in conn.execute(
                    "SELECT rid, pos, data, options_id, new_posts FROM creators ORDER BY pos, rid;"):
                d = json.loads(data)
                d["options"] = dict(options.get(oid) or {}) if oid else {}
                rows.append((rid, pos, d, json.loads(new_posts) if new_posts else []))
            return rows

    def get_meta(self, key: str, default: str = "") -> str:
        with self._lock, self._db() as conn:
            row = conn.execute("SELECT v FROM meta WHERE k = ?;", (key,)).fetchone()
            return row[0] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._db() as conn:
            conn.execute("INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v;",
                         (key, value))
            conn.commit()

    # ── Writing ───────────────────────────────────────────────────────────────
    def write(self, rows: Iterable[Tuple[int, int, Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]],
              deleted: Iterable[int] = (), replace_all: bool = False) -> int:
        """Writes creators given as (rid, pos, fields without "options", options, updates found) and
        removes the rids in `deleted`, in one transaction. replace_all empties the table first."""
        prepared = []
        new_options: Dict[str, str] = {}
        for rid, pos, fields, opts, new_posts in rows:
            o_json = _dumps(opts or {})
            oid = options_id(o_json) if opts else None
            if oid and oid not in self._known_options:
                new_options[oid] = o_json
            prepared.append((rid, pos, fields.get("service", ""), fields.get("user_id", ""),
                             fields.get("creator_name", ""), _dumps(fields), oid,
                             _dumps(new_posts) if new_posts else None))
        deleted = [(int(r),) for r in deleted]
        with self._lock, self._db() as conn:
            with conn:                                          # one transaction
                if replace_all:
                    conn.execute("DELETE FROM creators;")
                if new_options:
                    conn.executemany("INSERT OR IGNORE INTO options (id, data) VALUES (?, ?);",
                                     list(new_options.items()))
                if prepared:
                    conn.executemany("""
                        INSERT INTO creators (rid, pos, service, user_id, creator_name, data, options_id, new_posts)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(rid) DO UPDATE SET
                            pos = excluded.pos, service = excluded.service, user_id = excluded.user_id,
                            creator_name = excluded.creator_name, data = excluded.data,
                            options_id = excluded.options_id, new_posts = excluded.new_posts;
                    """, prepared)
                if deleted:
                    conn.executemany("DELETE FROM creators WHERE rid = ?;", deleted)
            self._known_options.update(new_options)
        return len(prepared) + len(deleted)

    def drop_unused_options(self) -> None:
        with self._lock, self._db() as conn:
            conn.execute("DELETE FROM options WHERE id NOT IN "
                         "(SELECT DISTINCT options_id FROM creators WHERE options_id IS NOT NULL);")
            conn.commit()
            self._known_options = {r[0] for r in conn.execute("SELECT id FROM options;")}

    # ── Safety copies ─────────────────────────────────────────────────────────
    def backup(self, dest: Optional[str] = None) -> Optional[str]:
        """A consistent copy of the database (SQLite's backup API, safe while it's in use)."""
        dest = dest or self.path + ".bak"
        tmp = dest + ".tmp"
        try:
            with self._lock, self._db() as conn:
                out = sqlite3.connect(tmp)
                try:
                    conn.backup(out)
                finally:
                    out.close()
            os.replace(tmp, dest)
            return dest
        except Exception as e:
            if os.path.isdir(os.path.dirname(os.path.abspath(self.path))):
                logger.warning(f"Couldn't back up the watchlist: {e}", category="watchlist")
            try:
                os.remove(tmp)
            except OSError:
                pass
            return None

    def set_aside(self) -> Optional[str]:
        """Renames a damaged database (and its WAL files) out of the way; never deletes it."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        kept = f"{self.path}.damaged-{stamp}"
        for suffix in ("", "-wal", "-shm"):
            src = self.path + suffix
            if os.path.exists(src):
                try:
                    os.replace(src, kept + suffix)
                except OSError as e:
                    logger.warning(f"Couldn't move the damaged {os.path.basename(src)} aside: {e}",
                                   category="watchlist")
                    return None
        self._schema_ready = False
        self._known_options = set()
        return kept
