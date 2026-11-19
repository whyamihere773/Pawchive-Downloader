"""
Archive Database CRUD, Bulk Delete & Export/Import Mixin
Decomposed from core/archive_manager.py to keep modules cohesive and under 1,000 lines.
"""

import datetime
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

from core import archive_index
from core.logger import logger


class ArchiveIOMixin:
    """File/link recording, lookup, single/bulk deletions, and TXT/JSON/SQLite export & import."""

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
                cond = "(creator_id = ? OR creator_name = ?)" + (" AND service = ?" if clean_svc else "")
                cparams = (clean_cid, clean_cid, clean_svc) if clean_svc else (clean_cid, clean_cid)
                wm, done, fts = archive_index.state(self._conn)
                bulk = wm > 0 or done > 0
                with self._paused_index(self._conn, enabled=bulk):
                    if bulk:
                        # A creator can have hundreds of thousands of records: the summaries and the search
                        # index are fixed up in a few statements instead of record by record
                        counted = f"{cond} AND (id <= ? OR id > ?)"
                        if fts:
                            cursor.execute(
                                "INSERT INTO archive_fts (archive_fts, rowid, filename, post_title, creator_name, creator_id, post_id) "
                                f"SELECT 'delete', id, filename, post_title, creator_name, creator_id, post_id FROM downloaded_files WHERE {counted};",
                                cparams + (done, wm))
                        exts = cursor.execute(
                            f"SELECT LOWER(IFNULL(file_ext, '')), COUNT(*) FROM downloaded_files WHERE {counted} GROUP BY 1;",
                            cparams + (done, wm)).fetchall()
                    cursor.execute(f"DELETE FROM downloaded_files WHERE {cond};", cparams)
                    affected = cursor.rowcount
                    if bulk:
                        for table in ("archive_post_cats", "archive_creator_cats", "archive_posts", "archive_creators"):
                            cursor.execute(f"DELETE FROM {table} WHERE {cond};", cparams)
                        for ext, n in exts:
                            cursor.execute("UPDATE archive_exts SET files = files - ? WHERE ext = ?;", (n, ext))
                        cursor.execute("DELETE FROM archive_exts WHERE files <= 0;")
                self._conn.commit()
                if affected >= 1000:
                    self._passive_wal_checkpoint(self._conn)
                self._stats_cache = None
                return affected
            except Exception as e:
                try:
                    self._conn.rollback()       # (never leave the summaries paused)
                except Exception:
                    pass
                logger.error(f"Failed to delete archive records for creator {creator_id}: {e}", category="archive")
                self._note_error(e)
                return -1

    def get_file_paths_for_creator(self, creator_id: str, service: str = "") -> List[str]:
        """Return distinct non-empty stored file paths belonging to a specific creator."""
        with self._lock:
            if self._conn is None:
                if not os.path.exists(self.db_path):
                    return []
                self._init_db_unlocked()
            if self._conn is None:
                return []
            try:
                clean_cid = str(creator_id or "")
                clean_svc = str(service or "").lower()
                cond = "(creator_id = ? OR creator_name = ?)" + (" AND service = ?" if clean_svc else "")
                params = (clean_cid, clean_cid, clean_svc) if clean_svc else (clean_cid, clean_cid)
                rows = self._conn.execute(
                    f"SELECT DISTINCT file_path FROM downloaded_files WHERE {cond} AND file_path IS NOT NULL AND file_path != '';",
                    params,
                ).fetchall()
                return [str(r[0]) for r in rows if r and r[0]]
            except Exception as e:
                logger.debug(f"Failed to query file paths for creator {creator_id}: {e}", category="archive")
                return []

    def delete_under_paths(self, folders: List[str]) -> int:
        """Delete archive file records whose stored file_path sits strictly inside `folders`."""
        clean_dirs = [os.path.normpath(d) for d in (folders or []) if d]
        if not clean_dirs:
            return 0
        with self._lock:
            if self._conn is None:
                if not os.path.exists(self.db_path):
                    return 0
                self._init_db_unlocked()
            if self._conn is None:
                return 0
            try:
                dir_keys = [self._path_key(d).rstrip("\\/") for d in clean_dirs]
                candidates = self.records_under(clean_dirs)
                row_ids = [
                    rid for fp_key, rid in candidates.items()
                    if any(fp_key == dk or fp_key.startswith(dk + os.sep) for dk in dir_keys if dk)
                ]
                if not row_ids:
                    return 0
                cursor = self._conn.cursor()
                wm, done, fts = archive_index.state(self._conn)
                bulk = wm > 0 or done > 0
                total_deleted = 0
                with self._paused_index(self._conn, enabled=bulk):
                    for start in range(0, len(row_ids), 400):
                        chunk = row_ids[start:start + 400]
                        placeholders = ",".join("?" for _ in chunk)
                        if bulk:
                            if fts:
                                cursor.execute(
                                    "INSERT INTO archive_fts (archive_fts, rowid, filename, post_title, creator_name, creator_id, post_id) "
                                    f"SELECT 'delete', id, filename, post_title, creator_name, creator_id, post_id "
                                    f"FROM downloaded_files WHERE id IN ({placeholders}) AND (id <= ? OR id > ?);",
                                    tuple(chunk) + (done, wm),
                                )
                            exts = cursor.execute(
                                f"SELECT LOWER(IFNULL(file_ext, '')), COUNT(*) FROM downloaded_files "
                                f"WHERE id IN ({placeholders}) AND (id <= ? OR id > ?) GROUP BY 1;",
                                tuple(chunk) + (done, wm),
                            ).fetchall()
                            for ext, n in exts:
                                cursor.execute("UPDATE archive_exts SET files = files - ? WHERE ext = ?;", (n, ext))
                        cursor.execute(f"DELETE FROM downloaded_files WHERE id IN ({placeholders});", tuple(chunk))
                        total_deleted += max(0, cursor.rowcount)
                    if bulk:
                        cursor.execute("DELETE FROM archive_exts WHERE files <= 0;")
                self._conn.commit()
                if total_deleted >= 1000:
                    self._passive_wal_checkpoint(self._conn)
                self._stats_cache = None
                return total_deleted
            except Exception as e:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                logger.error(f"Failed to delete archive records under paths: {e}", category="archive")
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
                has_idx = archive_index.state(self._conn) != (0, 0, False)
                with self._paused_index(self._conn, enabled=has_idx):
                    self._conn.execute("DELETE FROM downloaded_files;")
                    if has_idx:
                        archive_index.forget_all(self._conn)
                self._conn.commit()
                self._conn.execute("VACUUM;")
                self._passive_wal_checkpoint(self._conn)
                self._stats_cache = None
                logger.info("🗑️ Download Archive Database cleared.", category="archive")
                return True
            except Exception as e:
                try:
                    self._conn.rollback()       # (never leave the summaries paused)
                except Exception:
                    pass
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
                "file_id", "file_hash", "filename", "file_size", "file_ext", "downloaded_at", "file_path")
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
        Import records from a Pawchive JSON backup (full metadata), another Pawchive SQLite
        archive database (.db), or an ID-only text list ("service post_id_file_id" per line).
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

                is_sqlite = filepath.lower().endswith((".db", ".sqlite", ".sqlite3"))
                if not is_sqlite:
                    try:
                        with open(filepath, "rb") as _hdr_f:
                            is_sqlite = _hdr_f.read(16) == b"SQLite format 3\x00"
                    except OSError:
                        is_sqlite = False

                if is_sqlite:
                    if os.path.abspath(filepath) == os.path.abspath(self.db_path):
                        logger.info("Archive import skipped: selected database is already the active archive.", category="archive")
                        return 0
                    src_conn = sqlite3.connect(filepath, timeout=15.0)
                    try:
                        src_cur = src_conn.cursor()
                        src_cur.execute("PRAGMA table_info(downloaded_files);")
                        src_cols = {row[1] for row in src_cur.fetchall()}
                        if not {"service", "post_id", "file_id"}.issubset(src_cols):
                            logger.warning(f"SQLite file '{filepath}' does not contain a Pawchive downloaded_files table.", category="archive")
                            return 0
                        wanted = (
                            "service", "creator_id", "creator_name", "post_id", "post_title",
                            "file_id", "file_hash", "filename", "file_size", "file_ext", "downloaded_at", "file_path",
                        )
                        select_exprs = [c if c in src_cols else "''" for c in wanted]
                        src_cur.execute(f"SELECT {', '.join(select_exprs)} FROM downloaded_files;")
                        while True:
                            chunk = src_cur.fetchmany(5000)
                            if not chunk:
                                break
                            for row in chunk:
                                svc = str(row[0] or "").lower()
                                pid = str(row[3] or "")
                                fid = str(row[5] or "")
                                if not svc or not pid or not fid:
                                    continue
                                records_to_insert.append((
                                    svc,
                                    str(row[1] or ""),
                                    str(row[2] or ""),
                                    pid,
                                    str(row[4] or ""),
                                    fid,
                                    str(row[6] or ""),
                                    str(row[7] or ""),
                                    int(row[8] or 0),
                                    str(row[9] or ""),
                                    str(row[10] or now_str),
                                    str(row[11] or ""),
                                ))
                    finally:
                        src_conn.close()
                elif filepath.lower().endswith(".json"):
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
                                str(item.get("downloaded_at") or now_str),
                                str(item.get("file_path") or ""),
                            ))
                else:
                    # Plain text ID-only format lines: "<service> <post_id>_<file_id>"
                    # Split on the first whitespace only so file_ids containing spaces stay intact.
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for raw_line in f:
                            line = raw_line.strip()
                            if not line or line.startswith("#"):
                                continue
                            parts = line.split(None, 1)
                            if len(parts) >= 2:
                                svc = parts[0].lower()
                                target = parts[1].strip()
                                if "_" in target:
                                    subparts = target.split("_", 1)
                                    pid = subparts[0]
                                    fid = subparts[1]
                                else:
                                    pid = target
                                    fid = target
                                records_to_insert.append((
                                    svc, "", "", pid, "", fid, "", "", 0, "", now_str, ""
                                ))

                if not records_to_insert:
                    return 0

                # Filled in the way the one-time repair of old databases does (it no longer runs on
                # every start): extension from the file name, creator id / name from each other
                fixed = []
                for (svc, cid, cname, pid, ptitle, fid, fhash, fname, fsize, fext, at, fpath) in records_to_insert:
                    if not fext and fname:
                        fext = os.path.splitext(fname)[1].lower()
                    if not cname and cid:
                        cname = cid
                    elif not cid and cname:
                        cid = cname
                    elif not cid and not cname:
                        cid, cname = "unknown", "Unknown Creator"
                    fixed.append((svc, cid, cname, pid, ptitle, fid, fhash, fname, fsize, fext, at, fpath))
                records_to_insert = fixed

                cursor = self._conn.cursor()
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO downloaded_files
                    (service, creator_id, creator_name, post_id, post_title, file_id, file_hash, filename, file_size, file_ext, downloaded_at, file_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
