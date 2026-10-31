"""
Video Fingerprinting and Archive Indexing Engine
Scans existing video files on disk, computes their SHA-256 hashes and media signatures,
and registers them into Pawchive's ArchiveManager database to enable file recognition
and prevent duplicate downloads.
"""

import os
import re
import time
import hashlib
import logging
from typing import Optional, Dict, List, Any, Callable
from core.post_metadata_fetcher import PostMetadataFetcher

logger = logging.getLogger("pawchive.video_fingerprinter")


VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v",
    ".flv", ".wmv", ".ts", ".mts", ".m2ts", ".3gp"
}


def compute_file_sha256(file_path: str, chunk_size: int = 65536) -> str:
    """Calculates SHA-256 hash in 64KB chunks to keep memory usage minimal."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def compute_fast_sample_hash(file_path: str, sample_size: int = 32768) -> str:
    """
    Computes a fast perceptual sample hash from head, middle, and tail chunks.
    Useful for quick preliminary match checks across gigabyte-sized videos.
    """
    try:
        sz = os.path.getsize(file_path)
        if sz <= sample_size * 3:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()

        h = hashlib.md5()
        with open(file_path, "rb") as f:
            h.update(f.read(sample_size))
            f.seek(sz // 2)
            h.update(f.read(sample_size))
            f.seek(max(0, sz - sample_size))
            h.update(f.read(sample_size))
        return h.hexdigest()
    except OSError:
        return ""


class VideoFingerprinter:
    """
    Scans folders for video media, generates cryptographic & media fingerprints,
    and indexes them into the local ArchiveManager database.
    """

    def __init__(self, archive_manager=None):
        self.archive_manager = archive_manager

    @classmethod
    def is_video_file(cls, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in VIDEO_EXTENSIONS

    def scan_video_files(self, folder_path: str, recursive: bool = True) -> List[str]:
        """Collects all video files inside folder_path."""
        if not folder_path or not os.path.exists(folder_path):
            return []

        norm_root = os.path.normpath(os.path.abspath(folder_path))
        video_paths = []

        if not recursive:
            try:
                for entry in os.scandir(norm_root):
                    if entry.is_file(follow_symlinks=False) and self.is_video_file(entry.path):
                        video_paths.append(entry.path)
            except OSError as ex:
                logger.warning(f"Failed to scan directory {norm_root}: {ex}")
        else:
            try:
                for root, _, files in os.walk(norm_root):
                    for f in files:
                        if self.is_video_file(f):
                            video_paths.append(os.path.join(root, f))
            except OSError as ex:
                logger.warning(f"Failed to walk directory {norm_root}: {ex}")

        return video_paths

    def fingerprint_and_index(
        self,
        folder_path: str,
        recursive: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        Scans video files in folder_path, computes their SHA-256 fingerprints,
        and registers them in ArchiveManager.
        """
        start_time = time.time()
        result = {
            "success": True,
            "total_scanned": 0,
            "newly_indexed": 0,
            "already_archived": 0,
            "total_bytes": 0,
            "elapsed_seconds": 0.0,
            "errors": []
        }

        videos = self.scan_video_files(folder_path, recursive)
        total = len(videos)
        result["total_scanned"] = total

        if total == 0:
            return result

        # Ensure archive manager is enabled so records can be inserted
        if self.archive_manager and not self.archive_manager.is_enabled:
            self.archive_manager.set_enabled(True)

        for idx, v_path in enumerate(videos, start=1):
            if cancel_check and cancel_check():
                result["errors"].append("Fingerprinting cancelled by user.")
                break

            filename = os.path.basename(v_path)
            if progress_callback:
                try:
                    progress_callback(idx, total, filename)
                except Exception:
                    pass

            try:
                file_sz = os.path.getsize(v_path)
                result["total_bytes"] += file_sz
                sha256_hash = compute_file_sha256(v_path)
            except Exception as e:
                logger.warning(f"Failed to compute hash for {v_path}: {e}")
                result["errors"].append(f"Could not hash {filename}: {e}")
                continue

            # Context extraction (post ID, creator, service)
            ctx = PostMetadataFetcher.extract_context_from_path(v_path)
            service = ctx.get("service") or "local"
            creator_name = ctx.get("creator") or "Local Videos"
            creator_id = ctx.get("creator") or "local"
            post_id = ctx.get("post_id") or ""
            post_title = os.path.splitext(filename)[0]

            # Try to refine post info from nearby post_info.txt or JSON sidecars
            dir_name = os.path.dirname(v_path)
            info_txt = os.path.join(dir_name, "post_info.txt")
            if os.path.exists(info_txt):
                try:
                    with open(info_txt, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                        if not post_id:
                            m_pid = re.search(r'Post ID:\s*(\d+)', content)
                            if m_pid:
                                post_id = m_pid.group(1)
                        m_title = re.search(r'Title:\s*(.+)', content)
                        if m_title and post_title == os.path.splitext(filename)[0]:
                            post_title = m_title.group(1).strip()
                        m_cr = re.search(r'Creator:\s*(.+?)(?:\s*\[(.*?)\])?$', content, re.MULTILINE)
                        if m_cr:
                            creator_name = m_cr.group(1).strip()
                            if m_cr.group(2):
                                service = m_cr.group(2).strip().lower()
                except Exception:
                    pass

            file_id = sha256_hash[:16]

            # Check if already archived
            is_already = False
            if self.archive_manager:
                try:
                    # Direct file_hash lookup
                    if getattr(self.archive_manager, "_conn", None):
                        with self.archive_manager._lock:
                            cur = self.archive_manager._conn.cursor()
                            cur.execute("SELECT id, file_path FROM downloaded_files WHERE file_hash = ? LIMIT 1;", (sha256_hash,))
                            row = cur.fetchone()
                            if row:
                                is_already = True
                                # If path is empty or moved, update it
                                if not row[1] or row[1] != os.path.abspath(v_path):
                                    cur.execute(
                                        "UPDATE downloaded_files SET file_path = ?, file_size = ?, is_missing = 0 WHERE id = ?;",
                                        (os.path.abspath(v_path), file_sz, row[0])
                                    )
                                    self.archive_manager._conn.commit()
                except Exception as ex:
                    logger.debug(f"Archive lookup error: {ex}")

            if is_already:
                result["already_archived"] += 1
            else:
                # Record into archive
                if self.archive_manager:
                    try:
                        self.archive_manager.record_file(
                            service=service,
                            creator_id=creator_id,
                            post_id=post_id,
                            file_id=file_id,
                            file_hash=sha256_hash,
                            filename=filename,
                            creator_name=creator_name,
                            post_title=post_title,
                            file_size=file_sz,
                            file_ext=os.path.splitext(filename)[1].lower(),
                            file_path=os.path.abspath(v_path)
                        )
                        result["newly_indexed"] += 1
                    except Exception as ex:
                        logger.warning(f"Could not record file {filename} in archive: {ex}")
                        result["errors"].append(f"Archive error for {filename}: {ex}")
                else:
                    result["newly_indexed"] += 1

        result["elapsed_seconds"] = round(time.time() - start_time, 2)
        logger.info(
            f"🎬 Video fingerprinting complete for '{folder_path}': "
            f"{result['newly_indexed']} indexed, {result['already_archived']} already in archive "
            f"({result['total_scanned']} total) in {result['elapsed_seconds']}s"
        )
        return result
