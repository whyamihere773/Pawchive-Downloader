"""
Archive Database Maintenance, Backup, Corruption Repair & Disk Integrity Mixin
Decomposed from core/archive_manager.py to keep modules cohesive and under 1,000 lines.
"""

import datetime
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from core import archive_index
from core.logger import logger
from core.path_translation import localize_path


class ArchiveMaintenanceMixin:
    """Scheduled SQLite maintenance, automatic repair/salvage, disk verification, and file relocation."""

    MAINTENANCE_EVERY = 7 * 86400      # backups & tidy-up once a week

    def start_maintenance(self, delay: float = 300.0) -> None:
        """A while after start (in the background): the weekly check and safety copy, when due."""
        def _run():
            if self._maintenance_stop.wait(delay):
                return
            try:
                self.run_maintenance()
            except Exception as e:
                logger.debug(f"Archive maintenance skipped: {e}", category="archive")
        threading.Thread(target=_run, name="ArchiveMaintenance", daemon=True).start()

    def _meta(self, key: str, value: Optional[str] = None) -> str:
        with self._lock:
            if self._conn is None:
                return ""
            self._conn.execute("CREATE TABLE IF NOT EXISTS archive_meta (k TEXT PRIMARY KEY, v TEXT);")
            if value is not None:
                self._conn.execute("INSERT INTO archive_meta (k, v) VALUES (?, ?) "
                                   "ON CONFLICT(k) DO UPDATE SET v = excluded.v;", (key, value))
                self._conn.commit()
                return value
            row = self._conn.execute("SELECT v FROM archive_meta WHERE k = ?;", (key,)).fetchone()
            return row[0] if row else ""

    def _backup_records(self) -> str:
        """download_archive.db.bak: the downloaded_files table alone, read from a consistent snapshot
        (downloads keep recording meanwhile). Opened as the archive, everything else is rebuilt."""
        bak, tmp = self.db_path + ".bak", self.db_path + ".bak.tmp"
        for f in (tmp, tmp + "-journal"):
            if os.path.exists(f):
                os.remove(f)
        out = sqlite3.connect(tmp)
        try:
            out.execute("ATTACH DATABASE ? AS src;", (self.db_path,))       # (only read from)
            create = out.execute("SELECT sql FROM src.sqlite_master WHERE type = 'table' AND name = 'downloaded_files';").fetchone()[0]
            out.execute(create)
            out.execute("INSERT INTO main.downloaded_files SELECT * FROM src.downloaded_files;")
            seq = out.execute("SELECT seq FROM src.sqlite_sequence WHERE name = 'downloaded_files';").fetchone()
            if seq:
                out.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'downloaded_files';", (seq[0],))
            out.commit()
            out.execute("DETACH DATABASE src;")
        finally:
            out.close()
        os.replace(tmp, bak)
        return bak

    def run_maintenance(self, force: bool = False) -> Dict[str, Any]:
        """Once a week: checks the database for damage (repaired automatically if found) and keeps a
        safety copy of the records, download_archive.db.bak, when the drive has room for it plus 1 GB.
        Reads a snapshot, so downloads keep recording files meanwhile."""
        result: Dict[str, Any] = {"checked": False, "ok": None, "backup": ""}
        if not self._enabled or not os.path.exists(self.db_path) or not self._ensure_db():
            return result
        try:
            last = float(self._meta("maintenance_at") or 0)
        except ValueError:
            last = 0.0
        if not force and time.time() - last < self.MAINTENANCE_EVERY:
            return result
        t0 = time.time()
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=30.0)
        try:
            ok = self._quick_check(conn)
            result.update(checked=True, ok=ok)
            if not ok:
                conn.close()
                conn = None
                logger.warning("📦 The weekly check found damage in the download archive.", category="archive")
                self._note_error(sqlite3.DatabaseError("database disk image is malformed (weekly check)"))
                return result
            import shutil
            size = os.path.getsize(self.db_path)
            if os.path.exists(self.db_path + "-wal"):
                size += os.path.getsize(self.db_path + "-wal")
            free = shutil.disk_usage(self.config_dir).free
            # Only the records are copied (summaries, search index and other indexes are rebuilt from
            # them): a smaller copy that needs less room than the archive itself
            if free >= size + 1024 ** 3:
                conn.close()
                conn = None
                result["backup"] = self._backup_records()
            else:
                logger.info(f"📦 Archive safety copy skipped: not enough free space ({free / 1024 ** 3:.1f} GB free).",
                            category="archive")
        finally:
            if conn is not None:
                conn.close()
        self._meta("maintenance_at", str(time.time()))
        logger.info(f"📦 Weekly archive check: no problems found{'; safety copy saved' if result['backup'] else ''} "
                    f"({time.time() - t0:.0f} s).", category="archive")
        return result

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
                        try:
                            # The summaries and the search index may not match the records any more
                            archive_index.ensure(self._conn)
                            archive_index.restart(self._conn)
                            self._index_ready = False
                            self._start_backfill()
                        except Exception as ie:
                            logger.debug(f"Archive summaries not rebuilt after the repair: {ie}", category="archive")
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
            self._create_schema(new, summaries=False)      # (set up after the copy; filled in in the background)
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
            try:
                archive_index.ensure(new)
            except Exception as ie:
                logger.debug(f"Archive summaries not set up in the repaired copy: {ie}", category="archive")
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
        self._index_ready = False
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
                r_fpath = localize_path(r_fpath) if r_fpath else r_fpath     # (recorded on the other system)
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
            self._invalidate_stats_cache()

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

    @staticmethod
    def _path_key(p: str) -> str:
        return os.path.normcase(os.path.normpath(p))

    def records_under(self, folders: List[str]) -> Dict[str, int]:
        """{normalized file path: record id} of the records whose file is inside one of the folders
        (looked up once before files are moved; each record then follows its file by id)."""
        if not self._ensure_db():
            return {}

        def like(prefix: str) -> str:
            return prefix.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
        found: Dict[str, int] = {}
        with self._rlock:
            conn = self._reader()
            if conn is None:
                return {}
            try:
                for d in folders:
                    base = os.path.normpath(d)
                    for prefix in {base, base.replace("\\", "/")}:
                        for rid, fp in conn.execute(
                                "SELECT id, file_path FROM downloaded_files WHERE file_path LIKE ? ESCAPE '!';",
                                (like(prefix),)):
                            if fp:
                                found[self._path_key(fp)] = rid
            except Exception as e:
                logger.error(f"Couldn't read the archive's file paths: {e}", category="archive")
                self._note_error(e)
        return found

    def set_file_paths(self, changes: List[Tuple[int, str]]) -> int:
        """Stores new file paths for records (id, path), in one transaction."""
        if not changes or not self._ensure_db():
            return 0
        with self._lock:
            if self._conn is None:
                return 0
            try:
                self._conn.executemany("UPDATE downloaded_files SET file_path = ? WHERE id = ?;",
                                       [(p, rid) for rid, p in changes])
                self._conn.commit()
            except Exception as e:
                logger.error(f"Couldn't update the archive's file paths: {e}", category="archive")
                self._note_error(e)
                return 0
        self._invalidate_stats_cache()
        return len(changes)

    def relocate_files(self, old_dirs: List[str], moves: Dict[str, str]) -> int:
        """After files were moved: the records of files that were in old_dirs point to where the
        files are now. moves maps old path → new path (or a list of (old, new) tuples)."""
        if not moves:
            return 0
        moves_map = moves if isinstance(moves, dict) else dict(moves)
        ids = self.records_under(old_dirs)
        return self.set_file_paths([(ids[k], new) for old, new in moves_map.items()
                                    if (k := self._path_key(old)) in ids])

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
                self._invalidate_stats_cache()
                return deleted
            except Exception as e:
                logger.error(f"Failed to remove missing records for creator {creator_id}: {e}", category="archive")
                self._note_error(e)
                return -1
