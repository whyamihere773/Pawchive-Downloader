"""
Archive Rebuilder Engine — Asynchronous Multi-Directory Deep Indexer
Recursively scans one or multiple root directories across any drives,
parses folder structures and post_info.txt metadata, computes streaming
SHA-256 hashes in parallel worker threads, and bulk-inserts entries into
download_archive.db with high-throughput WAL SQLite transactions.
"""

import os
import re
import time
import hashlib
import datetime
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Set, Tuple

from core.logger import logger


# Ignored filenames and extensions
IGNORED_EXTENSIONS = {
    ".part", ".tmp", ".crdownload", ".aria2", ".download",
    ".bak", ".swp", ".swo", ".temp", ".ds_store"
}
IGNORED_FILENAMES = {
    "thumbs.db", "desktop.ini", ".ds_store", "post_info.txt", "info.txt"
}
IGNORED_DIRNAMES = {
    ".git", ".svn", ".hg", "__pycache__", ".idea", ".vscode", "$recycle.bin", "system volume information"
}

KNOWN_SERVICES = {
    "patreon", "fanbox", "fantia", "subscribestar", "boosty",
    "gumroad", "discord", "dlsite", "afdian", "bunkr", "coomer", "kemono"
}


@dataclass
class ArchiveRebuildOptions:
    hash_mode: str = "full"            # "full" (SHA-256) or "fast" (size+mtime)
    detect_post_info: bool = True       # Parse post_info.txt when found in post directory
    skip_existing: bool = True          # Skip files already cataloged in archive
    exclude_temp: bool = True           # Exclude .part, .tmp, .aria2, etc.
    max_workers: int = 4                # Number of parallel workers for hashing


@dataclass
class ArchiveRebuildStats:
    total_files: int = 0
    processed_files: int = 0
    added_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    total_bytes_hashed: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    creators_found: Set[str] = field(default_factory=set)
    posts_found: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        now = self.end_time if self.end_time > 0 else time.time()
        elapsed = max(0.001, now - self.start_time)
        fps = self.processed_files / elapsed
        mbps = (self.total_bytes_hashed / (1024 * 1024)) / elapsed
        pct = (self.processed_files / self.total_files * 100.0) if self.total_files > 0 else 0.0

        return {
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "added_count": self.added_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "total_creators": len(self.creators_found),
            "total_posts": len(self.posts_found),
            "elapsed_seconds": round(elapsed, 1),
            "files_per_sec": round(fps, 1),
            "mb_per_sec": round(mbps, 2),
            "percentage": round(pct, 1),
        }


def parse_post_info_file(info_path: str) -> Dict[str, str]:
    """Parse key metadata out of a post_info.txt or info.txt file."""
    meta = {}
    if not os.path.isfile(info_path):
        return meta

    try:
        with open(info_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k_clean = k.strip().lower()
                v_clean = v.strip()

                if k_clean == "title":
                    meta["post_title"] = v_clean
                elif k_clean == "post id":
                    meta["post_id"] = v_clean
                elif k_clean == "creator":
                    # Format: CreatorName [service]
                    m = re.match(r"^(.*?)(?:\s*\[(.*?)\])?$", v_clean)
                    if m:
                        meta["creator_name"] = m.group(1).strip()
                        if m.group(2):
                            meta["service"] = m.group(2).strip().lower()
                elif k_clean == "creator url":
                    # Extract creator_id from URL like /user/12345 or /creator/12345
                    m = re.search(r"/(?:user|creator)/([^/?#]+)", v_clean)
                    if m:
                        meta["creator_id"] = m.group(1).strip()
                elif k_clean == "url":
                    meta["post_url"] = v_clean
                    # If post_id wasn't found yet, extract from URL /post/12345
                    if "post_id" not in meta:
                        m_pid = re.search(r"/post/([^/?#]+)", v_clean)
                        if m_pid:
                            meta["post_id"] = m_pid.group(1).strip()
    except Exception as e:
        logger.debug(f"Error parsing post_info at {info_path}: {e}", category="archive")

    return meta


def compute_file_sha256(filepath: str, cancel_flag: Callable[[], bool], chunk_size: int = 65536) -> Tuple[str, int]:
    """Stream file content and compute SHA-256 hash. Returns (hex_digest, total_bytes)."""
    hasher = hashlib.sha256()
    total_bytes = 0
    with open(filepath, "rb") as f:
        while True:
            if cancel_flag():
                return "", 0
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            total_bytes += len(chunk)
    return hasher.hexdigest().lower(), total_bytes


class ArchiveRebuilder:
    """
    Asynchronous coordinator for scanning multiple directories, deducing post/creator
    identities, computing checksums, and bulk-committing records to ArchiveManager.
    """

    def __init__(
        self,
        archive_manager: Any,
        directories: List[str],
        options: Optional[ArchiveRebuildOptions] = None,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_finished: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.archive_manager = archive_manager
        self.directories = [os.path.normpath(d) for d in (directories or []) if d and os.path.isdir(d)]
        self.options = options or ArchiveRebuildOptions()
        self.on_progress = on_progress
        self.on_finished = on_finished

        self.stats = ArchiveRebuildStats()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def start(self) -> bool:
        """Start rebuilder in a background thread."""
        if self._is_running:
            return False
        if not self.directories:
            logger.warning("ArchiveRebuilder: No valid directories specified.", category="archive")
            return False

        self._stop_event.clear()
        self._pause_event.set()
        self._is_running = True
        self.stats = ArchiveRebuildStats()

        self._thread = threading.Thread(target=self._run_pipeline, name="ArchiveRebuilderThread", daemon=True)
        self._thread.start()
        return True

    def pause(self) -> None:
        """Pause processing."""
        self._pause_event.clear()
        logger.info("⏸️ Archive Rebuilder paused.", category="archive")

    def resume(self) -> None:
        """Resume processing."""
        self._pause_event.set()
        logger.info("▶️ Archive Rebuilder resumed.", category="archive")

    def cancel(self) -> None:
        """Cooperatively stop scanning."""
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused
        logger.info("⏹️ Archive Rebuilder cancellation requested.", category="archive")

    def _notify(self, phase: str, current_file: str = ""):
        if not self.on_progress:
            return
        d = self.stats.to_dict()
        d["phase"] = phase
        d["current_file"] = os.path.basename(current_file) if current_file else ""
        d["current_path"] = current_file
        d["is_paused"] = not self._pause_event.is_set()
        try:
            self.on_progress(d)
        except Exception as ex:
            logger.debug(f"Progress notification error: {ex}", category="archive")

    def _run_pipeline(self) -> None:
        """Main pipeline executed on worker thread."""
        logger.info(f"🔨 Starting Archive Rebuilder across {len(self.directories)} root director(ies)...", category="archive")
        self._notify("discovering")

        # 1. Discover all candidate files across all roots
        file_candidates: List[str] = []
        dir_meta_cache: Dict[str, Dict[str, str]] = {}

        for root_dir in self.directories:
            if self._stop_event.is_set():
                break
            for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
                if self._stop_event.is_set():
                    break
                # Filter out system/ignored subdirectories in-place
                dirnames[:] = [d for d in dirnames if d.lower() not in IGNORED_DIRNAMES and not d.startswith(".")]

                # Check for post_info.txt in this folder
                if self.options.detect_post_info and "post_info.txt" in filenames:
                    info_path = os.path.join(dirpath, "post_info.txt")
                    parsed = parse_post_info_file(info_path)
                    if parsed:
                        dir_meta_cache[dirpath] = parsed

                for fn in filenames:
                    fn_lower = fn.lower()
                    if fn_lower in IGNORED_FILENAMES or fn_lower.startswith("."):
                        continue
                    _, ext = os.path.splitext(fn_lower)
                    if self.options.exclude_temp and ext in IGNORED_EXTENSIONS:
                        continue

                    full_path = os.path.join(dirpath, fn)
                    file_candidates.append(full_path)

        self.stats.total_files = len(file_candidates)
        logger.info(f"🔍 Discovered {self.stats.total_files} candidate file(s) across selected directories.", category="archive")

        if self.stats.total_files == 0:
            self.stats.end_time = time.time()
            self._is_running = False
            self._notify("complete")
            if self.on_finished:
                self.on_finished(self.stats.to_dict())
            return

        # 2. Pre-fetch existing archive index for fast in-memory skipping
        existing_hashes: Set[str] = set()
        existing_keys: Set[Tuple[str, str, str]] = set()

        if self.options.skip_existing and getattr(self.archive_manager, "is_enabled", False):
            try:
                with self.archive_manager._lock:
                    if self.archive_manager._conn is None:
                        self.archive_manager._init_db_unlocked()
                    if self.archive_manager._conn:
                        cursor = self.archive_manager._conn.cursor()
                        cursor.execute("SELECT file_hash, service, post_id, file_id FROM downloaded_files;")
                        for row in cursor.fetchall():
                            h, s, p, fid = row
                            if h:
                                existing_hashes.add(str(h).lower())
                            if s and p and fid:
                                existing_keys.add((str(s).lower(), str(p), str(fid)))
            except Exception as e:
                logger.debug(f"Failed to prefetch existing archive items: {e}", category="archive")

        # 3. Process files and batch insert
        self._notify("indexing")
        batch_records: List[Dict[str, Any]] = []
        BATCH_SIZE = 300
        last_ui_time = time.time()

        for idx, file_path in enumerate(file_candidates):
            # Check pause / cancel
            while not self._pause_event.is_set():
                if self._stop_event.is_set():
                    break
                self._notify("paused", file_path)
                time.sleep(0.15)

            if self._stop_event.is_set():
                logger.info(f"⏹️ Rebuild stopped by user at file {idx + 1}/{self.stats.total_files}.", category="archive")
                break

            try:
                file_size = os.path.getsize(file_path)
            except OSError:
                self.stats.processed_files += 1
                self.stats.error_count += 1
                continue

            parent_dir = os.path.dirname(file_path)
            fn = os.path.basename(file_path)
            _, ext = os.path.splitext(fn.lower())

            # DEDUCE METADATA
            meta = self._deduce_metadata(file_path, dir_meta_cache)
            service = meta.get("service") or "kemono"
            creator_id = meta.get("creator_id") or ""
            creator_name = meta.get("creator_name") or "Unknown Creator"
            post_id = meta.get("post_id") or ""
            post_title = meta.get("post_title") or "Untitled Post"

            self.stats.creators_found.add(creator_name)
            self.stats.posts_found.add(f"{service}:{creator_name}:{post_id or post_title}")

            # FILE HASH & SKIPPING
            file_hash = ""
            is_skipped = False

            if self.options.hash_mode == "full":
                try:
                    file_hash, bytes_read = compute_file_sha256(
                        file_path,
                        cancel_flag=lambda: self._stop_event.is_set()
                    )
                    self.stats.total_bytes_hashed += bytes_read
                except Exception as ex:
                    logger.debug(f"Hashing failed for {file_path}: {ex}", category="archive")
                    file_hash = ""
            else:
                # Fast mode: deterministic synthetic hash from size + mtime + filename
                try:
                    mtime = int(os.path.getmtime(file_path))
                    raw_sig = f"{fn}_{file_size}_{mtime}"
                    file_hash = hashlib.md5(raw_sig.encode("utf-8")).hexdigest()
                except OSError:
                    file_hash = ""

            # Standard Kemono attachment ID convention: use hash or fallback to clean filename
            file_id = file_hash if file_hash else re.sub(r"[^\w\-.]", "_", fn)

            # Check if duplicate in archive
            if self.options.skip_existing:
                if file_hash and file_hash in existing_hashes:
                    is_skipped = True
                elif (service.lower(), str(post_id), str(file_id)) in existing_keys:
                    is_skipped = True

            if is_skipped:
                self.stats.skipped_count += 1
                self.stats.processed_files += 1
            else:
                record = {
                    "service": service,
                    "creator_id": creator_id,
                    "creator_name": creator_name,
                    "post_id": post_id or file_id,
                    "post_title": post_title,
                    "file_id": file_id,
                    "file_hash": file_hash,
                    "filename": fn,
                    "file_size": file_size,
                    "file_ext": ext,
                    "downloaded_at": datetime.datetime.fromtimestamp(
                        os.path.getctime(file_path) if os.path.exists(file_path) else time.time()
                    ).isoformat(),
                    "file_path": file_path,
                }
                batch_records.append(record)
                if file_hash:
                    existing_hashes.add(file_hash)
                existing_keys.add((service.lower(), str(post_id or file_id), str(file_id)))

                self.stats.added_count += 1
                self.stats.processed_files += 1

            # Commit batch if threshold reached
            if len(batch_records) >= BATCH_SIZE:
                self._commit_batch(batch_records)
                batch_records.clear()

            # Throttle UI notifications to ~10 times per second for silky smooth rendering
            now = time.time()
            if now - last_ui_time >= 0.1:
                self._notify("indexing", file_path)
                last_ui_time = now

        # Flush any remaining records
        if batch_records:
            self._commit_batch(batch_records)
            batch_records.clear()

        self.stats.end_time = time.time()
        self._is_running = False

        status = "cancelled" if self._stop_event.is_set() else "complete"
        self._notify(status)
        logger.success(
            f"🎉 Archive Rebuilder finished ({status}): {self.stats.added_count} added, "
            f"{self.stats.skipped_count} skipped, {self.stats.error_count} errors "
            f"in {round(self.stats.end_time - self.stats.start_time, 1)}s.",
            category="archive"
        )

        if self.on_finished:
            self.on_finished(self.stats.to_dict())

    def _deduce_metadata(self, file_path: str, dir_meta_cache: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        """
        Deduce post metadata using cached post_info.txt files or hierarchy analysis.
        Handles nested file-type folders (/Images, /Video, /Archive, etc.).
        """
        parent_dir = os.path.dirname(file_path)

        # 1. Direct post_info in immediate folder
        if parent_dir in dir_meta_cache:
            return dir_meta_cache[parent_dir].copy()

        # 2. Check if immediate parent is a file-type grouping folder (/Images, /Video, etc.)
        parent_name = os.path.basename(parent_dir)
        grandparent_dir = os.path.dirname(parent_dir)

        if parent_name.lower() in {"images", "video", "archive", "audio", "other", "extra", "files"}:
            if grandparent_dir in dir_meta_cache:
                return dir_meta_cache[grandparent_dir].copy()
            post_folder_name = os.path.basename(grandparent_dir)
            creator_folder_name = os.path.basename(os.path.dirname(grandparent_dir))
        else:
            post_folder_name = parent_name
            creator_folder_name = os.path.basename(grandparent_dir)

        # 3. Parse date and title from post folder name, e.g. "[2024-05-12] Some Post Title"
        post_title = post_folder_name
        post_id = ""
        date_match = re.match(r"^\[(\d{4}-\d{2}-\d{2})\]\s*(.*)$", post_folder_name)
        if date_match:
            post_title = date_match.group(2).strip() or post_folder_name

        # If post title contains an ID hint, e.g. "Title (123456)"
        id_match = re.search(r"\((\d{4,12})\)$", post_folder_name)
        if id_match:
            post_id = id_match.group(1)

        # Check if creator folder or higher folder has a service hint, e.g. "Patreon"
        service = "kemono"
        creator_name = creator_folder_name or "Unknown Creator"

        for part in file_path.replace("\\", "/").split("/"):
            part_lower = part.lower().strip()
            if part_lower in KNOWN_SERVICES:
                service = part_lower
                break

        return {
            "service": service,
            "creator_id": "",
            "creator_name": creator_name,
            "post_id": post_id or re.sub(r"[^\w\-.]", "_", post_title)[:60],
            "post_title": post_title,
        }

    def _commit_batch(self, records: List[Dict[str, Any]]) -> None:
        """Commit a batch of records inside SQLite transaction."""
        if not records:
            return

        with self.archive_manager._lock:
            if self.archive_manager._conn is None:
                self.archive_manager._init_db_unlocked()
            if self.archive_manager._conn is None:
                return

            try:
                now_str = datetime.datetime.now().isoformat()
                params = []
                for r in records:
                    params.append((
                        r.get("service", "kemono").lower(),
                        str(r.get("creator_id", "")),
                        str(r.get("creator_name", "")),
                        str(r.get("post_id", "")),
                        str(r.get("post_title", "")),
                        str(r.get("file_id", "")),
                        str(r.get("file_hash", "")),
                        str(r.get("filename", "")),
                        int(r.get("file_size", 0)),
                        str(r.get("file_ext", "")).lower(),
                        r.get("downloaded_at", now_str),
                        str(r.get("file_path", "")),
                        0,          # is_missing = 0 (file physically verified on disk)
                        now_str     # last_verified_at
                    ))

                self.archive_manager._conn.executemany(
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
                        file_path = excluded.file_path,
                        is_missing = 0,
                        last_verified_at = excluded.last_verified_at;
                    """,
                    params
                )
                self.archive_manager._conn.commit()
            except Exception as e:
                logger.error(f"Error committing batch to archive database: {e}", category="archive")
                self.stats.error_count += len(records)
