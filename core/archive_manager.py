"""
Download Archive Database Subsystem
Provides optional, isolated persistence of successfully downloaded files (gallery-dl / yt-dlp style).
When enabled, subsequent downloads query this database and skip files even if they have been
moved, unzipped, or deleted locally.
When disabled, the database is completely inactive and does not touch disk or perform queries.
"""

import os
import sys
import re
import json
import sqlite3
import datetime
import threading
from typing import Optional, List, Dict, Any, Tuple
from core.logger import logger


FILE_TYPE_CATEGORIES = {
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".001", ".cbz", ".cbr"},
    "graphics": {".psd", ".psb", ".clip", ".sai", ".sai2", ".ai", ".kra", ".cpt", ".xcf"},
    "images": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".tiff", ".tif", ".ico", ".avif", ".jfif"},
    "videos": {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".wmv", ".m4v", ".ts", ".m4s", ".vob"},
    "audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus", ".mid", ".midi"},
    "documents": {".pdf", ".txt", ".docx", ".doc", ".epub", ".rtf", ".csv", ".json", ".md", ".xlsx"},
    "links": {".link", ".url", "link", "url"},
}


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
            self._conn.execute("""
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
            cursor = self._conn.cursor()
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
                        self._conn.execute(f"ALTER TABLE downloaded_files ADD COLUMN {col_name} {col_type};")
                    except Exception as me:
                        logger.debug(f"Migration column {col_name} already present or failed: {me}", category="archive")

            self._conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_archive_unique
                ON downloaded_files(service, post_id, file_id);
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_archive_hash
                ON downloaded_files(file_hash);
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_archive_creator
                ON downloaded_files(service, creator_id);
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_archive_post
                ON downloaded_files(service, post_id);
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_archive_ext
                ON downloaded_files(file_ext);
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_archive_missing
                ON downloaded_files(is_missing);
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
                return True
            except Exception as e:
                logger.warning(f"Failed to record file in download archive: {e}", category="archive")
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

    def get_hierarchical_records(
        self,
        query: str = "",
        service: str = "all",
        file_type: str = "all",
        sort_by: str = "creator_az"
    ) -> List[Dict[str, Any]]:
        """
        Returns records organized hierarchically:
        Creator Group ➔ Post Sub-Group ➔ File Items.
        """
        if not os.path.exists(self.db_path):
            return []

        with self._lock:
            if self._conn is None:
                self._init_db_unlocked()
            if self._conn is None:
                return []

            try:
                conditions = []
                params = []

                # Filter by service
                clean_svc = (service or "").strip().lower()
                if clean_svc and clean_svc != "all":
                    conditions.append("service = ?")
                    params.append(clean_svc)

                # Filter by search query
                clean_q = (query or "").strip()
                if clean_q:
                    q_like = f"%{clean_q}%"
                    conditions.append(
                        "(filename LIKE ? OR post_title LIKE ? OR creator_name LIKE ? "
                        "OR creator_id LIKE ? OR post_id LIKE ? OR file_hash LIKE ?)"
                    )
                    params.extend([q_like, q_like, q_like, q_like, q_like, q_like])

                # Filter by file type category
                clean_ft = (file_type or "").strip().lower()
                if clean_ft == "removed":
                    conditions.append("is_missing = 1")
                elif clean_ft and clean_ft != "all" and clean_ft in FILE_TYPE_CATEGORIES:
                    extensions = FILE_TYPE_CATEGORIES[clean_ft]
                    placeholders = ",".join(["?"] * len(extensions))
                    conditions.append(f"LOWER(file_ext) IN ({placeholders})")
                    params.extend(list(extensions))

                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

                sql = f"""
                    SELECT id, service, creator_id, creator_name, post_id, post_title,
                           file_id, file_hash, filename, file_size, file_ext, downloaded_at,
                           file_path, is_missing, last_verified_at
                    FROM downloaded_files
                    {where_clause}
                    ORDER BY downloaded_at DESC;
                """

                cursor = self._conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()

                # Grouping data structure:
                # creators_map: key -> { creator_name, creator_id, service, posts: { post_id -> post_dict } }
                creators_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

                for row in rows:
                    (r_id, r_svc, r_cid, r_cname, r_pid, r_ptitle,
                     r_fid, r_fhash, r_fname, r_fsize, r_fext, r_down_at,
                     r_fpath, r_is_missing, r_last_ver) = row

                    display_creator = r_cname.strip() if (r_cname and r_cname.strip()) else (r_cid.strip() or "Unknown")
                    creator_key = (r_svc.lower(), display_creator.lower())

                    if creator_key not in creators_map:
                        creators_map[creator_key] = {
                            "creator_name": display_creator,
                            "creator_id": r_cid,
                            "service": r_svc.lower(),
                            "total_files": 0,
                            "missing_count": 0,
                            "verified_count": 0,
                            "unverified_count": 0,
                            "posts_map": {}
                        }

                    c_entry = creators_map[creator_key]
                    c_entry["total_files"] += 1
                    r_missing_int = int(r_is_missing if r_is_missing is not None else -1)
                    if r_missing_int == 1:
                        c_entry["missing_count"] += 1
                    elif r_missing_int == 0:
                        c_entry["verified_count"] += 1
                    else:
                        c_entry["unverified_count"] += 1

                    # Post level
                    display_post_title = r_ptitle.strip() if (r_ptitle and r_ptitle.strip()) else f"Post #{r_pid}"
                    p_key = str(r_pid)

                    if p_key not in c_entry["posts_map"]:
                        c_entry["posts_map"][p_key] = {
                            "post_id": str(r_pid),
                            "post_title": display_post_title,
                            "service": r_svc.lower(),
                            "creator_name": display_creator,
                            "creator_id": r_cid,
                            "files": []
                        }

                    # Format file size string
                    fsize_int = int(r_fsize or 0)
                    if fsize_int >= 1024 * 1024 * 1024:
                        size_str = f"{fsize_int / (1024 * 1024 * 1024):.1f} GB"
                    elif fsize_int >= 1024 * 1024:
                        size_str = f"{fsize_int / (1024 * 1024):.1f} MB"
                    elif fsize_int >= 1024:
                        size_str = f"{fsize_int / 1024:.1f} KB"
                    elif fsize_int > 0:
                        size_str = f"{fsize_int} B"
                    else:
                        size_str = ""

                    # Format downloaded_at string
                    date_display = r_down_at
                    try:
                        dt = datetime.datetime.fromisoformat(r_down_at)
                        date_display = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass

                    # Determine clean extension
                    ext_display = (r_fext or "").replace(".", "").upper()
                    if not ext_display and r_fname:
                        _, ext = os.path.splitext(r_fname)
                        ext_display = ext.replace(".", "").upper()

                    c_entry["posts_map"][p_key]["files"].append({
                        "id": r_id,
                        "filename": r_fname or f"file_{r_fid}",
                        "file_id": str(r_fid),
                        "file_hash": r_fhash or "",
                        "file_size": fsize_int,
                        "file_size_str": size_str,
                        "file_ext": ext_display,
                        "downloaded_at": r_down_at,
                        "downloaded_at_str": date_display,
                        "post_id": str(r_pid),
                        "service": r_svc.lower(),
                        "creator_id": r_cid,
                        "file_path": r_fpath or "",
                        "is_missing": r_missing_int,
                        "last_verified_at": r_last_ver or ""
                    })

                # Assemble sorted list
                result: List[Dict[str, Any]] = []
                for c_entry in creators_map.values():
                    # Convert posts_map to list
                    posts_list = list(c_entry["posts_map"].values())
                    for p in posts_list:
                        p["file_count"] = len(p["files"])
                    c_entry["posts"] = posts_list
                    c_entry["post_count"] = len(posts_list)
                    del c_entry["posts_map"]
                    result.append(c_entry)

                # Sorting creators
                clean_sort = (sort_by or "creator_az").lower()
                if clean_sort == "creator_az":
                    result.sort(key=lambda x: x["creator_name"].lower())
                elif clean_sort == "creator_za":
                    result.sort(key=lambda x: x["creator_name"].lower(), reverse=True)
                elif clean_sort == "files_desc":
                    result.sort(key=lambda x: x["total_files"], reverse=True)
                elif clean_sort == "newest":
                    result.sort(
                        key=lambda x: max((f["downloaded_at"] for p in x["posts"] for f in p["files"]), default=""),
                        reverse=True
                    )
                elif clean_sort == "oldest":
                    result.sort(
                        key=lambda x: min((f["downloaded_at"] for p in x["posts"] for f in p["files"]), default="")
                    )
                else:
                    result.sort(key=lambda x: x["creator_name"].lower())

                return result
            except Exception as e:
                logger.error(f"Failed to query hierarchical archive records: {e}", category="archive")
                return []

    def get_statistics(self) -> Dict[str, Any]:
        """Return comprehensive telemetry regarding the archive database."""
        stats = {
            "total_files": 0,
            "total_creators": 0,
            "total_posts": 0,
            "db_size_bytes": 0,
            "db_size_str": "0 KB",
            "category_counts": {
                "archives": 0,
                "graphics": 0,
                "images": 0,
                "videos": 0,
                "audio": 0,
                "documents": 0,
                "links": 0,
                "removed": 0,
                "other": 0
            },
            "service_counts": {},
            "verified_files": 0,
            "missing_files": 0
        }

        if os.path.exists(self.db_path):
            try:
                stats["db_size_bytes"] = os.path.getsize(self.db_path)
                sz = stats["db_size_bytes"]
                if sz >= 1024 * 1024:
                    stats["db_size_str"] = f"{sz / (1024 * 1024):.1f} MB"
                else:
                    stats["db_size_str"] = f"{max(1, sz // 1024)} KB"
            except Exception:
                pass

        if not os.path.exists(self.db_path):
            return stats

        with self._lock:
            if self._conn is None:
                self._init_db_unlocked()
            if self._conn is None:
                return stats

            try:
                cursor = self._conn.cursor()

                # Total files
                cursor.execute("SELECT COUNT(*) FROM downloaded_files;")
                stats["total_files"] = int(cursor.fetchone()[0] or 0)

                # Total creators
                cursor.execute("SELECT COUNT(DISTINCT service || ':' || creator_id) FROM downloaded_files;")
                stats["total_creators"] = int(cursor.fetchone()[0] or 0)

                # Total posts
                cursor.execute("SELECT COUNT(DISTINCT service || ':' || post_id) FROM downloaded_files;")
                stats["total_posts"] = int(cursor.fetchone()[0] or 0)

                # Service breakdown
                cursor.execute("SELECT service, COUNT(*) FROM downloaded_files GROUP BY service;")
                for s_row in cursor.fetchall():
                    stats["service_counts"][str(s_row[0]).lower()] = int(s_row[1])

                # Extension / Category breakdown
                cursor.execute("SELECT LOWER(file_ext), COUNT(*) FROM downloaded_files GROUP BY LOWER(file_ext);")
                for ext_row in cursor.fetchall():
                    ext_str = str(ext_row[0] or "").lower()
                    cnt = int(ext_row[1])
                    matched_cat = False
                    for cat, ext_set in FILE_TYPE_CATEGORIES.items():
                        if ext_str in ext_set:
                            stats["category_counts"][cat] += cnt
                            matched_cat = True
                            break
                    if not matched_cat:
                        stats["category_counts"]["other"] += cnt

                # Missing & Verified telemetry
                cursor.execute("SELECT COUNT(*) FROM downloaded_files WHERE is_missing = 1;")
                missing_cnt = int(cursor.fetchone()[0] or 0)
                stats["category_counts"]["removed"] = missing_cnt
                stats["missing_files"] = missing_cnt

                cursor.execute("SELECT COUNT(*) FROM downloaded_files WHERE is_missing = 0;")
                stats["verified_files"] = int(cursor.fetchone()[0] or 0)

                stats["total_links"] = stats["category_counts"].get("links", 0)
                return stats
            except Exception as e:
                logger.error(f"Failed to calculate archive statistics: {e}", category="archive")
                return stats

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
                return True
            except Exception as e:
                logger.error(f"Failed to delete archive record {record_id}: {e}", category="archive")
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
                    (service.lower(), str(post_id))
                )
                affected = cursor.rowcount
                self._conn.commit()
                return affected
            except Exception as e:
                logger.error(f"Failed to delete archive records for post {post_id}: {e}", category="archive")
                return 0

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
                if service:
                    cursor.execute(
                        "DELETE FROM downloaded_files WHERE creator_id = ? AND service = ?;",
                        (str(creator_id), service.lower())
                    )
                else:
                    cursor.execute(
                        "DELETE FROM downloaded_files WHERE creator_id = ?;",
                        (str(creator_id),)
                    )
                affected = cursor.rowcount
                self._conn.commit()
                return affected
            except Exception as e:
                logger.error(f"Failed to delete archive records for creator {creator_id}: {e}", category="archive")
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

    def export_archive(self, filepath: str, export_format: str = "txt") -> int:
        """
        Export all records to a file.
        Formats:
        - "txt": gallery-dl compatible plain text format (space-separated: service post_id_file_id)
        - "json": complete metadata JSON structure
        """
        if not os.path.exists(self.db_path):
            return 0

        with self._lock:
            if self._conn is None:
                self._init_db_unlocked()
            if self._conn is None:
                return 0

            try:
                cursor = self._conn.cursor()
                cursor.execute("""
                    SELECT service, creator_id, creator_name, post_id, post_title,
                           file_id, file_hash, filename, file_size, file_ext, downloaded_at
                    FROM downloaded_files
                    ORDER BY service, post_id;
                """)
                rows = cursor.fetchall()
                if not rows:
                    return 0

                count = len(rows)
                os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

                if export_format.lower() == "json":
                    export_data = []
                    for r in rows:
                        export_data.append({
                            "service": r[0],
                            "creator_id": r[1],
                            "creator_name": r[2],
                            "post_id": r[3],
                            "post_title": r[4],
                            "file_id": r[5],
                            "file_hash": r[6],
                            "filename": r[7],
                            "file_size": r[8],
                            "file_ext": r[9],
                            "downloaded_at": r[10]
                        })
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False)
                else:
                    # gallery-dl standard format: "<service> <post_id>_<file_id>" or "<service> <file_id>"
                    lines = []
                    for r in rows:
                        svc = r[0]
                        pid = r[3]
                        fid = r[5]
                        lines.append(f"{svc} {pid}_{fid}\n")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.writelines(lines)

                logger.info(f"📤 Exported {count} archive records to '{filepath}'", category="archive")
                return count
            except Exception as e:
                logger.error(f"Failed to export archive: {e}", category="archive")
                return 0

    def import_archive(self, filepath: str) -> int:
        """
        Import records from an existing gallery-dl archive text file or Pawchive JSON export.
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

                if filepath.lower().endswith(".json"):
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
                                str(item.get("downloaded_at") or now_str)
                            ))
                else:
                    # Plain text gallery-dl format lines
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for raw_line in f:
                            line = raw_line.strip()
                            if not line or line.startswith("#"):
                                continue
                            parts = line.split()
                            if len(parts) >= 2:
                                svc = parts[0].lower()
                                target = parts[1]
                                # gallery-dl format is typically "<service> <post_id>_<file_id>" or "<service> <id>"
                                if "_" in target:
                                    subparts = target.split("_", 1)
                                    pid = subparts[0]
                                    fid = subparts[1]
                                else:
                                    pid = target
                                    fid = target
                                records_to_insert.append((
                                    svc, "", "", pid, "", fid, "", "", 0, "", now_str
                                ))

                if not records_to_insert:
                    return 0

                cursor = self._conn.cursor()
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO downloaded_files
                    (service, creator_id, creator_name, post_id, post_title, file_id, file_hash, filename, file_size, file_ext, downloaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    records_to_insert
                )
                imported_count = cursor.rowcount
                self._conn.commit()
                logger.info(f"📥 Successfully imported {imported_count} archive records from '{filepath}'", category="archive")
                return imported_count
            except Exception as e:
                logger.error(f"Failed to import archive from '{filepath}': {e}", category="archive")
                return 0

    def verify_creator_integrity(
        self,
        service: str,
        creator_id: str,
        creator_name: str = "",
        candidate_dirs: Optional[List[str]] = None,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Verify physical presence of files on disk for a specific creator.
        Checks existing file_path, and if not found, scans candidate directories
        (such as default download directory, watchlist folders, storage pool paths).
        Updates is_missing (0 = present, 1 = missing) and file_path in SQLite.
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
                total = len(rows)
                result["total"] = total
                if total == 0:
                    return result

                # 1. Discover potential creator subfolders across candidate directories
                artist_dirs = set()
                c_name_clean = (creator_name or "").strip()
                c_id_clean = str(creator_id or "").strip()
                svc_clean = str(service or "").strip().lower()

                if candidate_dirs:
                    for root_cand in candidate_dirs:
                        if not root_cand or not os.path.exists(root_cand):
                            continue
                        root_cand = os.path.abspath(root_cand)
                        # Case A: root_cand might itself be the artist directory
                        base_cand = os.path.basename(root_cand).lower()
                        if (c_id_clean and c_id_clean.lower() in base_cand) or (c_name_clean and c_name_clean.lower() in base_cand):
                            artist_dirs.add(root_cand)

                        # Case B: Standard service/artist subfolders
                        svc_cand = os.path.join(root_cand, svc_clean)
                        search_roots = [root_cand]
                        if os.path.exists(svc_cand):
                            search_roots.append(svc_cand)

                        for s_root in search_roots:
                            try:
                                with os.scandir(s_root) as it:
                                    for entry in it:
                                        if entry.is_dir():
                                            name_l = entry.name.lower()
                                            if (c_id_clean and c_id_clean.lower() in name_l) or (c_name_clean and c_name_clean.lower() in name_l):
                                                artist_dirs.add(entry.path)
                            except Exception:
                                pass

                # 2. Build fast filename index from discovered artist directories
                # Mapping: filename_lower -> list of full paths
                indexed_files: Dict[str, List[str]] = {}
                for a_dir in artist_dirs:
                    try:
                        for root_dir, _, filenames in os.walk(a_dir):
                            for fn in filenames:
                                fn_l = fn.lower()
                                fp = os.path.join(root_dir, fn)
                                indexed_files.setdefault(fn_l, []).append(fp)
                    except Exception as wex:
                        logger.debug(f"Scan walk error in {a_dir}: {wex}", category="archive")

                # 3. Check each file record
                now_str = datetime.datetime.now().isoformat()
                updates = []  # (is_missing, file_path, last_verified_at, id)
                present_count = 0
                missing_count = 0

                for idx, row in enumerate(rows):
                    r_id, r_post_id, r_fname, r_fpath, r_fsize = row
                    found_path = ""

                    # (a) Check stored path
                    if r_fpath and os.path.exists(r_fpath) and os.path.getsize(r_fpath) > 0:
                        found_path = r_fpath
                    else:
                        # (b) Check indexed files
                        clean_fn = (r_fname or "").strip().lower()
                        if clean_fn in indexed_files:
                            candidates = indexed_files[clean_fn]
                            # Best match: path containing post_id
                            p_match = [p for p in candidates if str(r_post_id) in p]
                            if p_match:
                                found_path = p_match[0]
                            else:
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

                # 4. Batch commit updates
                cursor.executemany(
                    """
                    UPDATE downloaded_files
                    SET is_missing = ?, file_path = ?, last_verified_at = ?
                    WHERE id = ?;
                    """,
                    updates
                )
                self._conn.commit()

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
                return result

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
                return deleted
            except Exception as e:
                logger.error(f"Failed to remove missing records for creator {creator_id}: {e}", category="archive")
                return 0

