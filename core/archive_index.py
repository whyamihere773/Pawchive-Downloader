"""
Summary tables and the search index of the download archive (download_archive.db).

The Archive tab used to group every record on each open (seconds at a few million records, a minute at
ten million) and searched with LIKE over every record. Here:

- archive_creators / archive_posts hold the file / post counts and dates per creator and per post, and
  archive_exts the file count per extension. Triggers keep them up to date in the same transaction as
  every insert, change or removal, whichever code makes it.
- archive_fts is a full-text index (FTS5, trigram: matches any part of a word, like LIKE '%…%') over
  file names, post titles, creator names and ids. Created only where SQLite has FTS5.

An existing archive is filled in in the background, a slice of records at a time (backfill), so
downloads never wait long for it. Until it's done, readers use the old queries (is_ready()).

Which records the summaries count: those with id <= done_upto (filled in) and those added after the
summaries were set up (id > watermark). The triggers only touch counted records; the backfill adds the
rest. Bulk changes (clearing, removing a creator) pause the triggers and fix the summaries themselves.
"""

import sqlite3
import time
from typing import Callable, Optional, Tuple

STATE = "archive_state"

_TABLES = """
CREATE TABLE IF NOT EXISTS archive_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    watermark INTEGER NOT NULL DEFAULT 0,
    done_upto INTEGER NOT NULL DEFAULT 0,
    paused INTEGER NOT NULL DEFAULT 0,
    fts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS archive_posts (
    service TEXT NOT NULL, creator_id TEXT NOT NULL, creator_name TEXT NOT NULL, post_id TEXT NOT NULL,
    files INTEGER NOT NULL DEFAULT 0, missing INTEGER NOT NULL DEFAULT 0, verified INTEGER NOT NULL DEFAULT 0,
    newest TEXT, oldest TEXT, max_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (service, creator_id, creator_name, post_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS archive_creators (
    service TEXT NOT NULL, creator_id TEXT NOT NULL, creator_name TEXT NOT NULL,
    files INTEGER NOT NULL DEFAULT 0, missing INTEGER NOT NULL DEFAULT 0, verified INTEGER NOT NULL DEFAULT 0,
    posts INTEGER NOT NULL DEFAULT 0, newest TEXT, oldest TEXT, max_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (service, creator_id, creator_name)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS archive_exts (
    ext TEXT PRIMARY KEY, files INTEGER NOT NULL DEFAULT 0
) WITHOUT ROWID;
"""

# A record (OLD / NEW) is counted by the summaries
_COUNTED = ("(SELECT paused FROM archive_state WHERE id = 1) = 0 AND ({r}.id <= (SELECT done_upto FROM archive_state WHERE id = 1) "
            "OR {r}.id > (SELECT watermark FROM archive_state WHERE id = 1))")


def _post_key(r: str) -> str:
    return (f"service = {r}.service AND creator_id = IFNULL({r}.creator_id, '') "
            f"AND creator_name = IFNULL({r}.creator_name, '') AND post_id = {r}.post_id")


def _creator_key(r: str) -> str:
    return f"service = {r}.service AND creator_id = IFNULL({r}.creator_id, '') AND creator_name = IFNULL({r}.creator_name, '')"


def _add(r: str) -> str:
    """Adds record r to the post and creator summaries."""
    return f"""
    INSERT INTO archive_posts (service, creator_id, creator_name, post_id, files, missing, verified, newest, oldest, max_id)
    VALUES ({r}.service, IFNULL({r}.creator_id, ''), IFNULL({r}.creator_name, ''), {r}.post_id, 1,
            ({r}.is_missing IS 1), ({r}.is_missing IS 0), {r}.downloaded_at, {r}.downloaded_at, {r}.id)
    ON CONFLICT DO UPDATE SET files = files + 1, missing = missing + excluded.missing,
        verified = verified + excluded.verified,
        newest = CASE WHEN newest IS NULL OR excluded.newest > newest THEN excluded.newest ELSE newest END,
        oldest = CASE WHEN oldest IS NULL OR excluded.oldest < oldest THEN excluded.oldest ELSE oldest END,
        max_id = MAX(max_id, excluded.max_id);
    INSERT INTO archive_creators (service, creator_id, creator_name, files, missing, verified, newest, oldest, max_id)
    VALUES ({r}.service, IFNULL({r}.creator_id, ''), IFNULL({r}.creator_name, ''), 1,
            ({r}.is_missing IS 1), ({r}.is_missing IS 0), {r}.downloaded_at, {r}.downloaded_at, {r}.id)
    ON CONFLICT DO UPDATE SET files = files + 1, missing = missing + excluded.missing,
        verified = verified + excluded.verified,
        newest = CASE WHEN newest IS NULL OR excluded.newest > newest THEN excluded.newest ELSE newest END,
        oldest = CASE WHEN oldest IS NULL OR excluded.oldest < oldest THEN excluded.oldest ELSE oldest END,
        max_id = MAX(max_id, excluded.max_id);
    """


def _remove(r: str) -> str:
    """Takes record r out of the post and creator summaries (newest / oldest are looked up again when
    r was the newest or oldest)."""
    pk, ck = _post_key(r), _creator_key(r)
    same_post = (f"d.service = {r}.service AND d.post_id = {r}.post_id AND IFNULL(d.creator_id, '') = IFNULL({r}.creator_id, '') "
                 f"AND IFNULL(d.creator_name, '') = IFNULL({r}.creator_name, '')")
    same_creator = (f"p.service = {r}.service AND p.creator_id = IFNULL({r}.creator_id, '') "
                    f"AND p.creator_name = IFNULL({r}.creator_name, '')")
    return f"""
    UPDATE archive_posts SET files = files - 1, missing = missing - ({r}.is_missing IS 1),
        verified = verified - ({r}.is_missing IS 0) WHERE {pk};
    DELETE FROM archive_posts WHERE {pk} AND files <= 0;
    UPDATE archive_posts SET
        newest = (SELECT MAX(d.downloaded_at) FROM downloaded_files d WHERE {same_post}),
        oldest = (SELECT MIN(d.downloaded_at) FROM downloaded_files d WHERE {same_post}),
        max_id = IFNULL((SELECT MAX(d.id) FROM downloaded_files d WHERE {same_post}), 0)
    WHERE {pk} AND (newest IS {r}.downloaded_at OR oldest IS {r}.downloaded_at OR max_id = {r}.id);
    UPDATE archive_creators SET files = files - 1, missing = missing - ({r}.is_missing IS 1),
        verified = verified - ({r}.is_missing IS 0) WHERE {ck};
    UPDATE archive_creators SET
        newest = (SELECT MAX(p.newest) FROM archive_posts p WHERE {same_creator}),
        oldest = (SELECT MIN(p.oldest) FROM archive_posts p WHERE {same_creator}),
        max_id = IFNULL((SELECT MAX(p.max_id) FROM archive_posts p WHERE {same_creator}), 0)
    WHERE {ck} AND (newest IS {r}.downloaded_at OR oldest IS {r}.downloaded_at OR max_id = {r}.id);
    DELETE FROM archive_creators WHERE {ck} AND files <= 0;
    """


def _ext(r: str) -> str:
    return f"LOWER(IFNULL({r}.file_ext, ''))"


_KEY_CHANGED = ("(OLD.service IS NOT NEW.service OR IFNULL(OLD.creator_id, '') IS NOT IFNULL(NEW.creator_id, '') "
                "OR IFNULL(OLD.creator_name, '') IS NOT IFNULL(NEW.creator_name, '') OR OLD.post_id IS NOT NEW.post_id "
                "OR OLD.downloaded_at IS NOT NEW.downloaded_at)")


def _summary_triggers() -> str:
    old, new = _COUNTED.format(r="OLD"), _COUNTED.format(r="NEW")
    return f"""
    CREATE TRIGGER IF NOT EXISTS archive_posts_added AFTER INSERT ON archive_posts BEGIN
        INSERT INTO archive_creators (service, creator_id, creator_name, posts)
        VALUES (NEW.service, NEW.creator_id, NEW.creator_name, 1)
        ON CONFLICT DO UPDATE SET posts = posts + 1;
    END;
    CREATE TRIGGER IF NOT EXISTS archive_posts_removed AFTER DELETE ON archive_posts BEGIN
        UPDATE archive_creators SET posts = posts - 1
        WHERE service = OLD.service AND creator_id = OLD.creator_id AND creator_name = OLD.creator_name;
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_insert AFTER INSERT ON downloaded_files WHEN {new} BEGIN
        {_add("NEW")}
        INSERT INTO archive_exts (ext, files) VALUES ({_ext("NEW")}, 1)
        ON CONFLICT DO UPDATE SET files = files + 1;
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_delete AFTER DELETE ON downloaded_files WHEN {old} BEGIN
        {_remove("OLD")}
        UPDATE archive_exts SET files = files - 1 WHERE ext = {_ext("OLD")};
        DELETE FROM archive_exts WHERE ext = {_ext("OLD")} AND files <= 0;
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_move
    AFTER UPDATE OF service, creator_id, creator_name, post_id, downloaded_at ON downloaded_files
    WHEN {old} AND {_KEY_CHANGED} BEGIN
        {_remove("OLD")}
        {_add("NEW")}
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_missing AFTER UPDATE OF is_missing ON downloaded_files
    WHEN {old} AND (OLD.is_missing IS NOT NEW.is_missing) AND NOT {_KEY_CHANGED} BEGIN
        UPDATE archive_posts SET missing = missing - (OLD.is_missing IS 1) + (NEW.is_missing IS 1),
            verified = verified - (OLD.is_missing IS 0) + (NEW.is_missing IS 0) WHERE {_post_key("OLD")};
        UPDATE archive_creators SET missing = missing - (OLD.is_missing IS 1) + (NEW.is_missing IS 1),
            verified = verified - (OLD.is_missing IS 0) + (NEW.is_missing IS 0) WHERE {_creator_key("OLD")};
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_ext AFTER UPDATE OF file_ext ON downloaded_files
    WHEN {old} AND {_ext("OLD")} IS NOT {_ext("NEW")} BEGIN
        UPDATE archive_exts SET files = files - 1 WHERE ext = {_ext("OLD")};
        DELETE FROM archive_exts WHERE ext = {_ext("OLD")} AND files <= 0;
        INSERT INTO archive_exts (ext, files) VALUES ({_ext("NEW")}, 1) ON CONFLICT DO UPDATE SET files = files + 1;
    END;
    """


_FTS_COLS = "filename, post_title, creator_name, creator_id, post_id"


def _fts_triggers() -> str:
    old, new = _COUNTED.format(r="OLD"), _COUNTED.format(r="NEW")
    vals = lambda r: ", ".join(f"{r}.{c.strip()}" for c in _FTS_COLS.split(","))  # noqa: E731
    return f"""
    CREATE TRIGGER IF NOT EXISTS archive_fts_insert AFTER INSERT ON downloaded_files WHEN {new} BEGIN
        INSERT INTO archive_fts (rowid, {_FTS_COLS}) VALUES (NEW.id, {vals("NEW")});
    END;
    CREATE TRIGGER IF NOT EXISTS archive_fts_delete AFTER DELETE ON downloaded_files WHEN {old} BEGIN
        INSERT INTO archive_fts (archive_fts, rowid, {_FTS_COLS}) VALUES ('delete', OLD.id, {vals("OLD")});
    END;
    CREATE TRIGGER IF NOT EXISTS archive_fts_update
    AFTER UPDATE OF {_FTS_COLS} ON downloaded_files WHEN {old} BEGIN
        INSERT INTO archive_fts (archive_fts, rowid, {_FTS_COLS}) VALUES ('delete', OLD.id, {vals("OLD")});
        INSERT INTO archive_fts (rowid, {_FTS_COLS}) VALUES (NEW.id, {vals("NEW")});
    END;
    """


_ALL_TRIGGERS = ("archive_posts_added", "archive_posts_removed", "archive_sum_insert", "archive_sum_delete",
                 "archive_sum_move", "archive_sum_missing", "archive_sum_ext",
                 "archive_fts_insert", "archive_fts_delete", "archive_fts_update")

_fts_support: Optional[bool] = None


def fts_available() -> bool:
    """SQLite here has FTS5 with the trigram tokenizer (SQLite 3.34+ built with FTS5)."""
    global _fts_support
    if _fts_support is None:
        try:
            c = sqlite3.connect(":memory:")
            try:
                c.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram');")
                c.execute("INSERT INTO t (x) VALUES ('abcdef');")
                _fts_support = c.execute("SELECT COUNT(*) FROM t WHERE t MATCH '\"bcd\"';").fetchone()[0] == 1
            finally:
                c.close()
        except Exception:
            _fts_support = False
    return _fts_support


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?;", (name,)).fetchone() is not None


def ensure(conn: sqlite3.Connection) -> None:
    """Creates the summary tables, the search index and their triggers if they're missing. A new state
    row means every record already there is filled in by the backfill."""
    fts = fts_available()
    conn.executescript(_TABLES)
    row = conn.execute("SELECT fts FROM archive_state WHERE id = 1;").fetchone()
    if row is not None and bool(row[0]) != fts:
        # Opened with an SQLite that has (or lacks) the search index the summaries were built with
        drop(conn)
        conn.executescript(_TABLES)
        row = None
    if row is None:
        wm = int(conn.execute("SELECT IFNULL(MAX(id), 0) FROM downloaded_files;").fetchone()[0] or 0)
        conn.execute("INSERT INTO archive_state (id, watermark, done_upto, paused, fts) VALUES (1, ?, 0, 0, ?);",
                     (wm, int(fts)))
    if fts and not _has_table(conn, "archive_fts"):
        conn.execute(f"CREATE VIRTUAL TABLE archive_fts USING fts5({_FTS_COLS}, content='downloaded_files', "
                     f"content_rowid='id', tokenize='trigram');")
    conn.executescript(_summary_triggers())
    if fts:
        conn.executescript(_fts_triggers())
    conn.commit()


def drop(conn: sqlite3.Connection) -> None:
    """Removes the summaries, the search index and their triggers (they're rebuilt by ensure())."""
    for t in _ALL_TRIGGERS:
        conn.execute(f"DROP TRIGGER IF EXISTS {t};")
    for t in ("archive_posts", "archive_creators", "archive_exts", "archive_state"):
        conn.execute(f"DROP TABLE IF EXISTS {t};")
    try:
        conn.execute("DROP TABLE IF EXISTS archive_fts;")
    except sqlite3.OperationalError:
        pass            # (no FTS5 here: the index can't be removed, but nothing uses it any more)
    conn.commit()


def state(conn: sqlite3.Connection) -> Tuple[int, int, bool]:
    """(watermark, done_upto, has search index); (0, 0, False) without the tables."""
    try:
        row = conn.execute("SELECT watermark, done_upto, fts FROM archive_state WHERE id = 1;").fetchone()
    except sqlite3.OperationalError:
        return 0, 0, False
    return (int(row[0]), int(row[1]), bool(row[2])) if row else (0, 0, False)


def is_ready(conn: sqlite3.Connection) -> bool:
    wm, done, _ = state(conn)
    try:
        return done >= wm and _has_table(conn, "archive_creators")
    except sqlite3.Error:
        return False


def backfill_step(conn: sqlite3.Connection, chunk: int = 10000) -> bool:
    """Fills in the next slice of records; True once everything is in."""
    wm, done, fts = state(conn)
    if done >= wm:
        return True
    hi = min(wm, done + chunk)
    rng = (done, hi)
    with conn:
        conn.execute("""
            INSERT INTO archive_posts (service, creator_id, creator_name, post_id, files, missing, verified, newest, oldest, max_id)
            SELECT service, IFNULL(creator_id, ''), IFNULL(creator_name, ''), post_id, COUNT(*),
                   SUM(is_missing IS 1), SUM(is_missing IS 0), MAX(downloaded_at), MIN(downloaded_at), MAX(id)
            FROM downloaded_files WHERE id > ? AND id <= ? GROUP BY 1, 2, 3, 4
            ON CONFLICT DO UPDATE SET files = files + excluded.files, missing = missing + excluded.missing,
                verified = verified + excluded.verified,
                newest = CASE WHEN newest IS NULL OR excluded.newest > newest THEN excluded.newest ELSE newest END,
                oldest = CASE WHEN oldest IS NULL OR excluded.oldest < oldest THEN excluded.oldest ELSE oldest END,
                max_id = MAX(max_id, excluded.max_id);
        """, rng)
        conn.execute("""
            INSERT INTO archive_creators (service, creator_id, creator_name, files, missing, verified, newest, oldest, max_id)
            SELECT service, IFNULL(creator_id, ''), IFNULL(creator_name, ''), COUNT(*),
                   SUM(is_missing IS 1), SUM(is_missing IS 0), MAX(downloaded_at), MIN(downloaded_at), MAX(id)
            FROM downloaded_files WHERE id > ? AND id <= ? GROUP BY 1, 2, 3
            ON CONFLICT DO UPDATE SET files = files + excluded.files, missing = missing + excluded.missing,
                verified = verified + excluded.verified,
                newest = CASE WHEN newest IS NULL OR excluded.newest > newest THEN excluded.newest ELSE newest END,
                oldest = CASE WHEN oldest IS NULL OR excluded.oldest < oldest THEN excluded.oldest ELSE oldest END,
                max_id = MAX(max_id, excluded.max_id);
        """, rng)
        conn.execute("""
            INSERT INTO archive_exts (ext, files)
            SELECT LOWER(IFNULL(file_ext, '')), COUNT(*) FROM downloaded_files WHERE id > ? AND id <= ? GROUP BY 1
            ON CONFLICT DO UPDATE SET files = files + excluded.files;
        """, rng)
        if fts:
            conn.execute(f"INSERT INTO archive_fts (rowid, {_FTS_COLS}) "
                         f"SELECT id, {_FTS_COLS} FROM downloaded_files WHERE id > ? AND id <= ?;", rng)
        conn.execute("UPDATE archive_state SET done_upto = ? WHERE id = 1;", (hi,))
    return hi >= wm


def backfill(run_step: Callable[[], bool], should_stop: Callable[[], bool] = lambda: False,
             pause: float = 0.05) -> bool:
    """Runs backfill steps until done (each step through run_step, which takes the writer's lock)."""
    while not should_stop():
        if run_step():
            return True
        time.sleep(pause)          # downloads recording files get in between
    return False


def paused(conn: sqlite3.Connection, on: bool) -> None:
    """While paused, the triggers leave the summaries alone (for bulk changes that fix them up)."""
    conn.execute("UPDATE archive_state SET paused = ? WHERE id = 1;", (1 if on else 0,))


def forget_all(conn: sqlite3.Connection) -> None:
    """After every record was removed (call while paused)."""
    conn.execute("DELETE FROM archive_posts;")
    conn.execute("DELETE FROM archive_creators;")
    conn.execute("DELETE FROM archive_exts;")
    if state(conn)[2]:
        conn.execute("INSERT INTO archive_fts (archive_fts) VALUES ('delete-all');")
    wm = int(conn.execute("SELECT IFNULL(MAX(seq), 0) FROM sqlite_sequence WHERE name = 'downloaded_files';").fetchone()[0] or 0)
    conn.execute("UPDATE archive_state SET watermark = ?, done_upto = ? WHERE id = 1;", (wm, wm))


def restart(conn: sqlite3.Connection) -> None:
    """Empties the summaries and the search index and fills them in again from scratch (after a repair
    or when they might not match the records)."""
    paused(conn, True)
    conn.execute("DELETE FROM archive_posts;")
    conn.execute("DELETE FROM archive_creators;")
    conn.execute("DELETE FROM archive_exts;")
    if state(conn)[2]:
        conn.execute("INSERT INTO archive_fts (archive_fts) VALUES ('delete-all');")
    wm = int(conn.execute("SELECT IFNULL(MAX(id), 0) FROM downloaded_files;").fetchone()[0] or 0)
    conn.execute("UPDATE archive_state SET watermark = ?, done_upto = 0, paused = 0 WHERE id = 1;", (wm,))
    conn.commit()


def fts_query(text: str) -> Optional[str]:
    """The search text as an FTS5 query matching it anywhere (None: too short for the index, which
    needs 3 characters)."""
    q = (text or "").strip()
    if len(q) < 3:
        return None
    return '"' + q.replace('"', '""') + '"'
