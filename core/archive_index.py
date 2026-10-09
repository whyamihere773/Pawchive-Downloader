"""
Summary tables and the search index of the download archive (download_archive.db).

The Archive tab used to group every record on each open (seconds at a few million records, a minute at
ten million) and searched with LIKE over every record. Here:

- archive_creators / archive_posts hold the file / post counts and dates per creator and per post, and
  archive_exts the file count per extension. archive_creator_cats / archive_post_cats hold the same per
  file type (images, videos…: the tab's type filter; archive_ext_cats maps extensions to types).
  Triggers keep them up to date in the same transaction as every insert, change or removal, whichever
  code makes it.
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
    newest TEXT, oldest TEXT, max_id INTEGER NOT NULL DEFAULT 0, newest_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (service, creator_id, creator_name, post_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS archive_creators (
    service TEXT NOT NULL, creator_id TEXT NOT NULL, creator_name TEXT NOT NULL,
    files INTEGER NOT NULL DEFAULT 0, missing INTEGER NOT NULL DEFAULT 0, verified INTEGER NOT NULL DEFAULT 0,
    posts INTEGER NOT NULL DEFAULT 0, newest TEXT, oldest TEXT, max_id INTEGER NOT NULL DEFAULT 0, newest_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (service, creator_id, creator_name)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS archive_exts (
    ext TEXT PRIMARY KEY, files INTEGER NOT NULL DEFAULT 0
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS archive_ext_cats (
    ext TEXT PRIMARY KEY, cat TEXT NOT NULL
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS archive_post_cats (
    service TEXT NOT NULL, creator_id TEXT NOT NULL, creator_name TEXT NOT NULL, cat TEXT NOT NULL,
    post_id TEXT NOT NULL,
    files INTEGER NOT NULL DEFAULT 0, missing INTEGER NOT NULL DEFAULT 0, verified INTEGER NOT NULL DEFAULT 0,
    newest TEXT, oldest TEXT, max_id INTEGER NOT NULL DEFAULT 0, newest_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (service, creator_id, creator_name, cat, post_id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS archive_creator_cats (
    cat TEXT NOT NULL, service TEXT NOT NULL, creator_id TEXT NOT NULL, creator_name TEXT NOT NULL,
    files INTEGER NOT NULL DEFAULT 0, missing INTEGER NOT NULL DEFAULT 0, verified INTEGER NOT NULL DEFAULT 0,
    posts INTEGER NOT NULL DEFAULT 0, newest TEXT, oldest TEXT, max_id INTEGER NOT NULL DEFAULT 0, newest_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (cat, service, creator_id, creator_name)
) WITHOUT ROWID;
"""

_SUMMARY_TABLES = ("archive_posts", "archive_creators", "archive_exts", "archive_post_cats", "archive_creator_cats")

# A record (OLD / NEW) is counted by the summaries
_COUNTED = ("(SELECT paused FROM archive_state WHERE id = 1) = 0 AND ({r}.id <= (SELECT done_upto FROM archive_state WHERE id = 1) "
            "OR {r}.id > (SELECT watermark FROM archive_state WHERE id = 1))")


def _post_key(r: str) -> str:
    return (f"service = {r}.service AND creator_id = IFNULL({r}.creator_id, '') "
            f"AND creator_name = IFNULL({r}.creator_name, '') AND post_id = {r}.post_id")


def _creator_key(r: str) -> str:
    return f"service = {r}.service AND creator_id = IFNULL({r}.creator_id, '') AND creator_name = IFNULL({r}.creator_name, '')"


_COUNT_COLS = "files, missing, verified, newest, oldest, max_id, newest_id"

# newest_id: the id of the newest record (the highest id among the newest ones): the tab shows a
# creator's name and id as written on it
_UPSERT_COUNTS = """files = files + excluded.files, missing = missing + excluded.missing,
        verified = verified + excluded.verified,
        newest_id = CASE WHEN newest IS NULL OR excluded.newest > newest THEN excluded.newest_id
                         WHEN excluded.newest = newest THEN MAX(newest_id, excluded.newest_id) ELSE newest_id END,
        newest = CASE WHEN newest IS NULL OR excluded.newest > newest THEN excluded.newest ELSE newest END,
        oldest = CASE WHEN oldest IS NULL OR excluded.oldest < oldest THEN excluded.oldest ELSE oldest END,
        max_id = MAX(max_id, excluded.max_id)"""


def _ext(r: str) -> str:
    return f"LOWER(IFNULL({r}.file_ext, ''))"


def _cat(r: str) -> str:
    return f"(SELECT cat FROM archive_ext_cats WHERE ext = {_ext(r)})"


def _one(r: str) -> str:
    """The summary columns for the single record r."""
    return (f"1, ({r}.is_missing IS 1), ({r}.is_missing IS 0), {r}.downloaded_at, {r}.downloaded_at, "
            f"{r}.id, {r}.id")


def _add(r: str) -> str:
    """Adds record r to the post and creator summaries."""
    who = f"{r}.service, IFNULL({r}.creator_id, ''), IFNULL({r}.creator_name, '')"
    return f"""
    INSERT INTO archive_posts (service, creator_id, creator_name, post_id, {_COUNT_COLS})
    VALUES ({who}, {r}.post_id, {_one(r)})
    ON CONFLICT DO UPDATE SET {_UPSERT_COUNTS};
    INSERT INTO archive_creators (service, creator_id, creator_name, {_COUNT_COLS})
    VALUES ({who}, {_one(r)})
    ON CONFLICT DO UPDATE SET {_UPSERT_COUNTS};
    """


def _add_cat(r: str) -> str:
    """Adds record r to the summaries of its file type (none for other types)."""
    who = f"{r}.service, IFNULL({r}.creator_id, ''), IFNULL({r}.creator_name, '')"
    return f"""
    INSERT INTO archive_post_cats (service, creator_id, creator_name, cat, post_id, {_COUNT_COLS})
    SELECT {who}, c.cat, {r}.post_id, {_one(r)} FROM archive_ext_cats c WHERE c.ext = {_ext(r)}
    ON CONFLICT DO UPDATE SET {_UPSERT_COUNTS};
    INSERT INTO archive_creator_cats (cat, service, creator_id, creator_name, {_COUNT_COLS})
    SELECT c.cat, {who}, {_one(r)} FROM archive_ext_cats c WHERE c.ext = {_ext(r)}
    ON CONFLICT DO UPDATE SET {_UPSERT_COUNTS};
    """


def _remove_from(r: str, posts: str, creators: str, by_type: bool) -> str:
    """Takes record r out of a pair of post / creator summary tables; newest / oldest / ids are looked
    up again when r was one of them."""
    of_type = f" AND cat = {_cat(r)}" if by_type else ""
    pk, ck = _post_key(r) + of_type, _creator_key(r) + of_type

    def same_post(a):
        cond = (f"{a}.service = {r}.service AND {a}.post_id = {r}.post_id "
                f"AND IFNULL({a}.creator_id, '') = IFNULL({r}.creator_id, '') "
                f"AND IFNULL({a}.creator_name, '') = IFNULL({r}.creator_name, '')")
        if by_type:
            cond += f" AND LOWER(IFNULL({a}.file_ext, '')) IN (SELECT ext FROM archive_ext_cats e WHERE e.cat = {posts}.cat)"
        return cond

    def same_creator(a):
        cond = (f"{a}.service = {r}.service AND {a}.creator_id = IFNULL({r}.creator_id, '') "
                f"AND {a}.creator_name = IFNULL({r}.creator_name, '')")
        if by_type:
            cond += f" AND {a}.cat = {creators}.cat"
        return cond

    edge = (f"(newest IS {r}.downloaded_at OR oldest IS {r}.downloaded_at OR max_id = {r}.id "
            f"OR newest_id = {r}.id)")
    return f"""
    UPDATE {posts} SET files = files - 1, missing = missing - ({r}.is_missing IS 1),
        verified = verified - ({r}.is_missing IS 0) WHERE {pk};
    DELETE FROM {posts} WHERE {pk} AND files <= 0;
    UPDATE {posts} SET
        newest = (SELECT MAX(d.downloaded_at) FROM downloaded_files d WHERE {same_post("d")}),
        oldest = (SELECT MIN(d.downloaded_at) FROM downloaded_files d WHERE {same_post("d")}),
        max_id = IFNULL((SELECT MAX(d.id) FROM downloaded_files d WHERE {same_post("d")}), 0),
        newest_id = IFNULL((SELECT MAX(d.id) FROM downloaded_files d WHERE {same_post("d")} AND d.downloaded_at IS
                            (SELECT MAX(d2.downloaded_at) FROM downloaded_files d2 WHERE {same_post("d2")})), 0)
    WHERE {pk} AND {edge};
    UPDATE {creators} SET files = files - 1, missing = missing - ({r}.is_missing IS 1),
        verified = verified - ({r}.is_missing IS 0) WHERE {ck};
    UPDATE {creators} SET
        newest = (SELECT MAX(p.newest) FROM {posts} p WHERE {same_creator("p")}),
        oldest = (SELECT MIN(p.oldest) FROM {posts} p WHERE {same_creator("p")}),
        max_id = IFNULL((SELECT MAX(p.max_id) FROM {posts} p WHERE {same_creator("p")}), 0),
        newest_id = IFNULL((SELECT MAX(p.newest_id) FROM {posts} p WHERE {same_creator("p")} AND p.newest IS
                            (SELECT MAX(p2.newest) FROM {posts} p2 WHERE {same_creator("p2")})), 0)
    WHERE {ck} AND {edge};
    DELETE FROM {creators} WHERE {ck} AND files <= 0;
    """


def _remove(r: str) -> str:
    return _remove_from(r, "archive_posts", "archive_creators", False)


def _remove_cat(r: str) -> str:
    return _remove_from(r, "archive_post_cats", "archive_creator_cats", True)


def _aggregate(a: str = "") -> str:
    """The summary columns for a group of records (alias a)."""
    return (f"COUNT(*), SUM({a}is_missing IS 1), SUM({a}is_missing IS 0), MAX({a}downloaded_at), "
            f"MIN({a}downloaded_at), MAX({a}id), "
            f"CAST(substr(MAX(printf('%s|%020d', {a}downloaded_at, {a}id)), -20) AS INTEGER)")


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
    CREATE TRIGGER IF NOT EXISTS archive_post_cats_added AFTER INSERT ON archive_post_cats BEGIN
        INSERT INTO archive_creator_cats (cat, service, creator_id, creator_name, posts)
        VALUES (NEW.cat, NEW.service, NEW.creator_id, NEW.creator_name, 1)
        ON CONFLICT DO UPDATE SET posts = posts + 1;
    END;
    CREATE TRIGGER IF NOT EXISTS archive_post_cats_removed AFTER DELETE ON archive_post_cats BEGIN
        UPDATE archive_creator_cats SET posts = posts - 1
        WHERE cat = OLD.cat AND service = OLD.service AND creator_id = OLD.creator_id AND creator_name = OLD.creator_name;
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_insert AFTER INSERT ON downloaded_files WHEN {new} BEGIN
        {_add("NEW")}
        {_add_cat("NEW")}
        INSERT INTO archive_exts (ext, files) VALUES ({_ext("NEW")}, 1)
        ON CONFLICT DO UPDATE SET files = files + 1;
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_delete AFTER DELETE ON downloaded_files WHEN {old} BEGIN
        {_remove("OLD")}
        {_remove_cat("OLD")}
        UPDATE archive_exts SET files = files - 1 WHERE ext = {_ext("OLD")};
        DELETE FROM archive_exts WHERE ext = {_ext("OLD")} AND files <= 0;
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_move
    AFTER UPDATE OF service, creator_id, creator_name, post_id, downloaded_at ON downloaded_files
    WHEN {old} AND {_KEY_CHANGED} BEGIN
        {_remove("OLD")}
        {_add("NEW")}
        {_remove_cat("OLD")}
        {_add_cat("NEW")}
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_missing AFTER UPDATE OF is_missing ON downloaded_files
    WHEN {old} AND (OLD.is_missing IS NOT NEW.is_missing) AND NOT {_KEY_CHANGED} BEGIN
        UPDATE archive_posts SET missing = missing - (OLD.is_missing IS 1) + (NEW.is_missing IS 1),
            verified = verified - (OLD.is_missing IS 0) + (NEW.is_missing IS 0) WHERE {_post_key("OLD")};
        UPDATE archive_creators SET missing = missing - (OLD.is_missing IS 1) + (NEW.is_missing IS 1),
            verified = verified - (OLD.is_missing IS 0) + (NEW.is_missing IS 0) WHERE {_creator_key("OLD")};
        UPDATE archive_post_cats SET missing = missing - (OLD.is_missing IS 1) + (NEW.is_missing IS 1),
            verified = verified - (OLD.is_missing IS 0) + (NEW.is_missing IS 0)
        WHERE {_post_key("OLD")} AND cat = {_cat("OLD")} AND {_ext("OLD")} IS {_ext("NEW")};
        UPDATE archive_creator_cats SET missing = missing - (OLD.is_missing IS 1) + (NEW.is_missing IS 1),
            verified = verified - (OLD.is_missing IS 0) + (NEW.is_missing IS 0)
        WHERE {_creator_key("OLD")} AND cat = {_cat("OLD")} AND {_ext("OLD")} IS {_ext("NEW")};
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_ext AFTER UPDATE OF file_ext ON downloaded_files
    WHEN {old} AND {_ext("OLD")} IS NOT {_ext("NEW")} BEGIN
        UPDATE archive_exts SET files = files - 1 WHERE ext = {_ext("OLD")};
        DELETE FROM archive_exts WHERE ext = {_ext("OLD")} AND files <= 0;
        INSERT INTO archive_exts (ext, files) VALUES ({_ext("NEW")}, 1) ON CONFLICT DO UPDATE SET files = files + 1;
    END;
    CREATE TRIGGER IF NOT EXISTS archive_sum_ext_cat AFTER UPDATE OF file_ext ON downloaded_files
    WHEN {old} AND {_ext("OLD")} IS NOT {_ext("NEW")} AND NOT {_KEY_CHANGED} BEGIN
        {_remove_cat("OLD")}
        {_add_cat("NEW")}
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
                 "archive_sum_move", "archive_sum_missing", "archive_sum_ext", "archive_sum_ext_cat",
                 "archive_post_cats_added", "archive_post_cats_removed",
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
    for t in ("archive_posts", "archive_creators", "archive_post_cats", "archive_creator_cats"):
        if "newest_id" not in {r[1] for r in conn.execute(f"PRAGMA table_info({t});")}:
            conn.execute(f"ALTER TABLE {t} ADD COLUMN newest_id INTEGER NOT NULL DEFAULT 0;")
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
    from core.archive_manager import FILE_TYPE_CATEGORIES
    wanted = {ext: cat for cat, exts in FILE_TYPE_CATEGORIES.items() for ext in sorted(exts)}
    have = dict(conn.execute("SELECT ext, cat FROM archive_ext_cats;"))
    if have != wanted:
        # New file types (or summaries from before the per-type ones): every record is counted again
        conn.execute("DELETE FROM archive_ext_cats;")
        conn.executemany("INSERT INTO archive_ext_cats (ext, cat) VALUES (?, ?);", list(wanted.items()))
        if row is not None:
            conn.commit()
            restart(conn)
    if fts and _has_table(conn, "archive_fts"):
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'archive_fts';").fetchone()[0] or ""
        if "detail=none" not in sql.replace(" ", "").lower():
            # An index from the first version of this (twice the size): made again, every record counted again
            for t in _ALL_TRIGGERS:
                conn.execute(f"DROP TRIGGER IF EXISTS {t};")
            conn.execute("DROP TABLE archive_fts;")
            conn.execute(f"CREATE VIRTUAL TABLE archive_fts USING fts5({_FTS_COLS}, content='downloaded_files', "
                         f"content_rowid='id', tokenize='trigram', detail=none);")
            conn.commit()
            restart(conn)
    if fts and not _has_table(conn, "archive_fts"):
        conn.execute(f"CREATE VIRTUAL TABLE archive_fts USING fts5({_FTS_COLS}, content='downloaded_files', "
                     f"content_rowid='id', tokenize='trigram', detail=none);")
    # Made again on every open, so they always match this version (CREATE … IF NOT EXISTS would keep an
    # older version's)
    for t in _ALL_TRIGGERS:
        conn.execute(f"DROP TRIGGER IF EXISTS {t};")
    conn.executescript(_summary_triggers())
    if fts:
        conn.executescript(_fts_triggers())
    conn.commit()


def drop(conn: sqlite3.Connection) -> None:
    """Removes the summaries, the search index and their triggers (they're rebuilt by ensure())."""
    for t in _ALL_TRIGGERS:
        conn.execute(f"DROP TRIGGER IF EXISTS {t};")
    for t in _SUMMARY_TABLES + ("archive_ext_cats", "archive_state"):
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


_NEWEST_ID_OF_GROUPS = "CAST(substr(MAX(printf('%s|%020d', newest, newest_id)), -20) AS INTEGER)"


def backfill_step(conn: sqlite3.Connection, chunk: int = 2000) -> bool:
    """Fills in the next slice of records; True once everything is in. The slice is grouped by post and
    file type once (a temporary table); the four summaries are made from that instead of reading the
    records four times."""
    wm, done, fts = state(conn)
    if done >= wm:
        return True
    hi = min(wm, done + chunk)
    rng = (done, hi)
    with conn:
        conn.execute(f"""
            CREATE TEMP TABLE IF NOT EXISTS backfill_slice (
                service TEXT, creator_id TEXT, creator_name TEXT, post_id TEXT, cat TEXT,
                files INTEGER, missing INTEGER, verified INTEGER, newest TEXT, oldest TEXT,
                max_id INTEGER, newest_id INTEGER);
        """)
        conn.execute("DELETE FROM temp.backfill_slice;")
        conn.execute(f"""
            INSERT INTO temp.backfill_slice
            SELECT d.service, IFNULL(d.creator_id, ''), IFNULL(d.creator_name, ''), d.post_id, IFNULL(c.cat, ''),
                   {_aggregate("d.")}
            FROM downloaded_files d LEFT JOIN archive_ext_cats c ON c.ext = LOWER(IFNULL(d.file_ext, ''))
            WHERE d.id > ? AND d.id <= ? GROUP BY 1, 2, 3, 4, 5;
        """, rng)
        groups = f"""SUM(files), SUM(missing), SUM(verified), MAX(newest), MIN(oldest), MAX(max_id),
                     {_NEWEST_ID_OF_GROUPS}"""
        conn.execute(f"""
            INSERT INTO archive_posts (service, creator_id, creator_name, post_id, {_COUNT_COLS})
            SELECT service, creator_id, creator_name, post_id, {groups}
            FROM temp.backfill_slice WHERE true GROUP BY 1, 2, 3, 4
            ON CONFLICT DO UPDATE SET {_UPSERT_COUNTS};
        """)
        conn.execute(f"""
            INSERT INTO archive_creators (service, creator_id, creator_name, {_COUNT_COLS})
            SELECT service, creator_id, creator_name, {groups}
            FROM temp.backfill_slice WHERE true GROUP BY 1, 2, 3
            ON CONFLICT DO UPDATE SET {_UPSERT_COUNTS};
        """)
        conn.execute(f"""
            INSERT INTO archive_post_cats (service, creator_id, creator_name, cat, post_id, {_COUNT_COLS})
            SELECT service, creator_id, creator_name, cat, post_id,
                   files, missing, verified, newest, oldest, max_id, newest_id
            FROM temp.backfill_slice WHERE cat != ''
            ON CONFLICT DO UPDATE SET {_UPSERT_COUNTS};
        """)
        conn.execute(f"""
            INSERT INTO archive_creator_cats (cat, service, creator_id, creator_name, {_COUNT_COLS})
            SELECT cat, service, creator_id, creator_name, {groups}
            FROM temp.backfill_slice WHERE cat != '' GROUP BY 1, 2, 3, 4
            ON CONFLICT DO UPDATE SET {_UPSERT_COUNTS};
        """)
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
             pause: float = 0.01) -> bool:
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
    for t in _SUMMARY_TABLES:
        conn.execute(f"DELETE FROM {t};")
    if state(conn)[2]:
        conn.execute("INSERT INTO archive_fts (archive_fts) VALUES ('delete-all');")
    wm = int(conn.execute("SELECT IFNULL(MAX(seq), 0) FROM sqlite_sequence WHERE name = 'downloaded_files';").fetchone()[0] or 0)
    conn.execute("UPDATE archive_state SET watermark = ?, done_upto = ? WHERE id = 1;", (wm, wm))


def restart(conn: sqlite3.Connection) -> None:
    """Empties the summaries and the search index and fills them in again from scratch (after a repair
    or when they might not match the records)."""
    paused(conn, True)
    for t in _SUMMARY_TABLES:
        conn.execute(f"DELETE FROM {t};")
    if state(conn)[2]:
        conn.execute("INSERT INTO archive_fts (archive_fts) VALUES ('delete-all');")
    wm = int(conn.execute("SELECT IFNULL(MAX(id), 0) FROM downloaded_files;").fetchone()[0] or 0)
    conn.execute("UPDATE archive_state SET watermark = ?, done_upto = 0, paused = 0 WHERE id = 1;", (wm,))
    conn.commit()


# Rows of archive_fts holding the search text (the trigram index answers LIKE '%…%' itself)
FTS_MATCH = " OR ".join(f"{c.strip()} LIKE ?" for c in _FTS_COLS.split(","))


def fts_query(text: str) -> Optional[list]:
    """The parameters of FTS_MATCH for the search text, matching it anywhere like LIKE '%…%' (None:
    too short for the index, which needs 3 characters)."""
    q = (text or "").strip()
    if len(q) < 3:
        return None
    return [f"%{q}%"] * len(_FTS_COLS.split(","))
