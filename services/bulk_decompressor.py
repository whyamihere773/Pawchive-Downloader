"""
Bulk Decompressor Engine
Provides scanning of folders for archive files, disk space estimation,
and parallel extraction using the bundled 7za.exe standalone binary.
"""

import os
import re
import sys
import shutil
import threading
import subprocess
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable, Tuple

from core.logger import logger

ARCHIVE_EXTENSIONS = {
    ".7z", ".zip", ".rar", ".tar", ".gz", ".bz2", ".xz",
    ".tgz", ".tbz2", ".txz", ".zst", ".iso", ".cab", ".lzma"
}

# Regex to detect secondary split archive parts that shouldn't be extracted independently
SPLIT_SECONDARY_REGEX = re.compile(
    r'(?:\.part0*[2-9]\d*|\.part[1-9]\d{2,}|\.z0[1-9]|\.z[1-9]\d|\.r0[1-9]|\.r[1-9]\d|\.7z\.0*[2-9]\d*|\.7z\.[1-9]\d{2,})\.(?:rar|zip|7z)?$',
    re.IGNORECASE
)


def get_7za_path() -> str:
    """Resolve the path to the bundled or system 7za/7z executable."""
    # 1. Next to the executable — dependencies/ folder visible to the user
    #    (works both for compiled release and running from source)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_p = os.path.join(exe_dir, "dependencies", "7za.exe")
    if os.path.exists(local_p):
        return local_p

    # 2. PyInstaller _MEIPASS fallback (legacy / should not be reached in normal release)
    if hasattr(sys, "_MEIPASS"):
        meipass_p = os.path.join(sys._MEIPASS, "dependencies", "7za.exe")
        if os.path.exists(meipass_p):
            return meipass_p
        meipass_root = os.path.join(sys._MEIPASS, "7za.exe")
        if os.path.exists(meipass_root):
            return meipass_root

    # 3. System PATH fallback
    for binary in ["7za", "7z", "7za.exe", "7z.exe"]:
        found = shutil.which(binary)
        if found:
            return found

    return ""


def clean_archive_stem(filename: str) -> str:
    """Extract folder name without compound archive extensions."""
    lower = filename.lower()
    for compound in [".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst", ".7z.001", ".part1.rar", ".part01.rar"]:
        if lower.endswith(compound):
            return filename[:-len(compound)].rstrip(" ._")
    stem, _ = os.path.splitext(filename)
    return stem.rstrip(" ._") or "extracted_archive"


def get_unique_target_folder(parent_dir: str, base_name: str) -> str:
    """Return a unique directory path by appending numbered suffixes if collision occurs."""
    target = os.path.join(parent_dir, base_name)
    if not os.path.exists(target):
        return target
    i = 1
    while True:
        candidate = os.path.join(parent_dir, f"{base_name}_{i}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


@dataclass
class ArchiveItem:
    item_id: str
    path: str
    filename: str
    directory: str
    size: int
    creator: str
    scan_root: str = ""         # The top-level scanned folder (stable group key)
    selected: bool = True
    status: str = "pending"       # pending | extracting | done | error | skipped | password_required
    progress: float = 0.0         # 0.0 - 100.0
    error_message: str = ""
    target_dir: str = ""
    password: str = ""            # Known or verified archive password
    extracted_present: bool = False  # True if archive's extracted folder exists and has files
    extracted_dir: str = ""          # Absolute path to the extracted folder

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.item_id,
            "path": self.path,
            "filename": self.filename,
            "directory": self.directory,
            "scanRoot": self.scan_root,
            "size": self.size,
            "creator": self.creator,
            "selected": self.selected,
            "status": self.status,
            "progress": round(self.progress, 1),
            "errorMessage": self.error_message,
            "targetDir": self.target_dir,
            "password": self.password,
            "extractedPresent": self.extracted_present,
            "extractedDir": self.extracted_dir,
        }


@dataclass
class DiskCheckResult:
    drive: str
    archive_count: int
    total_archive_size: int
    estimated_required: int
    free_bytes: int
    is_sufficient: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drive": self.drive,
            "archiveCount": self.archive_count,
            "totalArchiveSize": self.total_archive_size,
            "estimatedRequired": self.estimated_required,
            "freeBytes": self.free_bytes,
            "isSufficient": self.is_sufficient,
        }


class BulkDecompressorEngine:
    """Scans for archives, performs pre-flight disk checks, and manages extraction jobs."""

    def __init__(self):
        self._7za_path = get_7za_path()
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()

    @property
    def has_7za(self) -> bool:
        if not self._7za_path or not os.path.exists(self._7za_path):
            self._7za_path = get_7za_path()
        return bool(self._7za_path and os.path.exists(self._7za_path))

    def scan_locations(
        self,
        locations: List[Tuple[str, str]],
        cancel_event: Optional[threading.Event] = None
    ) -> List[ArchiveItem]:
        """
        Recursively scan a list of (folder_path, creator_name) pairs for archives.
        Skips secondary parts of multi-volume archives (.part2.rar, etc.).
        Handles nested scan targets properly so deeper folders are scanned first
        and shallower parent folders do not swallow archives belonging to child targets.
        """
        items: List[ArchiveItem] = []
        seen_paths = set()
        item_counter = 0

        # Filter valid locations and sort by path depth descending
        # so specific child folders claim their archives with correct creator first.
        valid_locations = [(f, c) for f, c in locations if f and os.path.exists(f)]
        sorted_locations = sorted(
            valid_locations,
            key=lambda x: len(os.path.normpath(x[0]).split(os.sep)),
            reverse=True
        )

        all_target_roots = {os.path.normcase(os.path.normpath(f)) for f, _ in valid_locations}

        for folder, creator in sorted_locations:
            if cancel_event and cancel_event.is_set():
                break

            norm_folder = os.path.normcase(os.path.normpath(folder))
            other_targets = {r for r in all_target_roots if r != norm_folder}

            try:
                for root, dirs, files in os.walk(folder):
                    if cancel_event and cancel_event.is_set():
                        break

                    # Prune any subdirectory that is itself an independent scan target
                    norm_root = os.path.normcase(os.path.normpath(root))
                    dirs[:] = [
                        d for d in dirs
                        if os.path.normcase(os.path.normpath(os.path.join(norm_root, d))) not in other_targets
                    ]

                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        is_split_001 = f.lower().endswith(".001")
                        if ext in ARCHIVE_EXTENSIONS or is_split_001:
                            # Filter secondary split volumes
                            if SPLIT_SECONDARY_REGEX.search(f):
                                continue

                            full_path = os.path.normpath(os.path.join(root, f))
                            full_path_norm = os.path.normcase(full_path)
                            if full_path_norm in seen_paths:
                                continue
                            seen_paths.add(full_path_norm)

                            try:
                                sz = os.path.getsize(full_path)
                            except OSError:
                                sz = 0

                            stem = clean_archive_stem(f)
                            target_extracted_dir = os.path.join(root, stem)
                            is_extracted_present = False
                            if os.path.isdir(target_extracted_dir):
                                try:
                                    if any(os.scandir(target_extracted_dir)):
                                        is_extracted_present = True
                                except OSError:
                                    pass

                            item_counter += 1
                            item = ArchiveItem(
                                item_id=f"arc_{item_counter}",
                                path=full_path,
                                filename=f,
                                directory=root,
                                size=sz,
                                creator=creator or os.path.basename(folder),
                                scan_root=os.path.normpath(folder),
                                selected=not is_extracted_present,
                                status="done" if is_extracted_present else "pending",
                                progress=100.0 if is_extracted_present else 0.0,
                                extracted_present=is_extracted_present,
                                extracted_dir=target_extracted_dir if is_extracted_present else ""
                            )
                            items.append(item)
            except Exception as e:
                logger.error(f"Error scanning folder {folder}: {e}", category="decompressor")

        return items

    def check_disk_space(
        self,
        items: List[ArchiveItem],
        delete_after: bool = False
    ) -> List[DiskCheckResult]:
        """
        Group selected items by filesystem drive and estimate required free disk space.
        Conservative estimate: 2.0x archive size.
        If delete_after is enabled: peak space needed is ~1.2x.
        """
        drive_map: Dict[str, List[ArchiveItem]] = {}
        for item in items:
            if not item.selected:
                continue
            drive, _ = os.path.splitdrive(os.path.abspath(item.path))
            if not drive:
                drive = os.path.abspath(item.path)[:3]
            drive = drive.upper()
            drive_map.setdefault(drive, []).append(item)

        results: List[DiskCheckResult] = []
        for drive, drive_items in drive_map.items():
            total_arc_sz = sum(i.size for i in drive_items)
            # Estimation multiplier: 2.0x standard, 1.2x if archives are deleted as we go
            multiplier = 1.2 if delete_after else 2.0
            estimated_req = int(total_arc_sz * multiplier)

            free_bytes = 0
            try:
                usage = shutil.disk_usage(drive if drive.endswith("\\") else drive + "\\")
                free_bytes = usage.free
            except Exception:
                try:
                    usage = shutil.disk_usage(os.path.dirname(drive_items[0].path))
                    free_bytes = usage.free
                except Exception:
                    free_bytes = 10 * 1024 * 1024 * 1024  # Fallback 10GB if undetectable

            is_sufficient = free_bytes >= estimated_req
            results.append(DiskCheckResult(
                drive=drive,
                archive_count=len(drive_items),
                total_archive_size=total_arc_sz,
                estimated_required=estimated_req,
                free_bytes=free_bytes,
                is_sufficient=is_sufficient
            ))

        return results

    @staticmethod
    def is_password_error(error_message: str) -> bool:
        """Determines if 7za error output indicates an encrypted archive or incorrect password."""
        if not error_message:
            return False
        err_lower = error_message.lower()
        return any(phrase in err_lower for phrase in [
            "wrong password", "can not open encrypted archive",
            "data error in encrypted file", "enter password",
            "encrypted", "password"
        ])

    def test_password(
        self,
        archive_path: str,
        password: str,
        cancel_event: Optional[threading.Event] = None
    ) -> bool:
        """
        Fast non-extracting integrity test using '7za t' to verify if a password
        can decrypt the archive. Returns True if password is valid, False otherwise.
        """
        if not self.has_7za or not os.path.exists(archive_path):
            return False

        cmd = [
            self._7za_path,
            "t",
            "-y",
            f"-p{password}",
            archive_path
        ]

        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = 0x08000000

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            while proc.poll() is None:
                if cancel_event and cancel_event.is_set():
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    return False
                import time
                time.sleep(0.05)

            return proc.returncode == 0
        except Exception as e:
            logger.debug(f"test_password error on {archive_path}: {e}", category="decompressor")
            return False

    def probe_if_encrypted(self, archive_path: str) -> Tuple[bool, str]:
        """Fast in-memory test using '7za t' to check if an archive requires a password without touching the disk."""
        if not self.has_7za or not os.path.exists(archive_path):
            return False, ""
        cmd = [self._7za_path, "t", "-y", "-p-", archive_path]
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = 0x08000000
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                startupinfo=startupinfo,
                creationflags=creationflags,
                bufsize=1,
                encoding="utf-8",
                errors="replace"
            )
            out, _ = proc.communicate()
            if proc.returncode != 0 and self.is_password_error(out):
                return True, out.strip().splitlines()[-1] if out.strip() else "Encrypted"
            return False, ""
        except Exception:
            return False, ""

    def extract_single_archive(
        self,
        item: ArchiveItem,
        password: Optional[str] = None,
        threads_per_archive: int = 2,
        delete_after: bool = False,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        overwrite: bool = True
    ) -> Tuple[bool, str]:
        """
        Extract a single archive using 7za.exe into a folder named after the archive.
        Returns (success: bool, error_message: str).
        """
        if not self.has_7za:
            return False, "7za.exe standalone binary not found in dependencies."

        if not os.path.exists(item.path):
            return False, f"Archive file not found: {item.path}"

        effective_pw = password or item.password or ""

        # Pre-check: if no password was provided, probe in-memory first.
        # This prevents 7-Zip from creating a target folder and 0-byte ghost files on disk.
        if not effective_pw:
            is_enc, enc_err = self.probe_if_encrypted(item.path)
            if is_enc:
                return False, f"ERROR: Can not open encrypted archive. Wrong password? ({enc_err})"

        # Determine target output folder
        base_name = clean_archive_stem(item.filename)
        default_dir = os.path.join(item.directory, base_name)
        if overwrite and item.extracted_dir and os.path.exists(item.extracted_dir):
            target_dir = item.extracted_dir
        elif overwrite and os.path.exists(default_dir):
            target_dir = default_dir
        else:
            target_dir = get_unique_target_folder(item.directory, base_name)

        item.target_dir = target_dir
        dir_created_by_us = not os.path.exists(target_dir)

        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            return False, f"Could not create destination directory: {e}"

        cmd = [
            self._7za_path,
            "x",
            "-y",
            "-aoa",   # Overwrite existing files without prompting
            "-bsp1",  # Output progress to stdout
            f"-mmt={max(1, threads_per_archive)}",
            f"-o{target_dir}"
        ]
        if effective_pw:
            cmd.append(f"-p{effective_pw}")
        else:
            cmd.append("-p-")  # Prevent 7za from waiting for a password on stdin

        cmd.append(item.path)

        # Hide subprocess window on Windows
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = 0x08000000  # CREATE_NO_WINDOW

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                startupinfo=startupinfo,
                creationflags=creationflags,
                bufsize=1,
                encoding="utf-8",
                errors="replace"
            )
        except Exception as e:
            if dir_created_by_us and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            return False, f"Failed to launch 7za: {e}"

        with self._lock:
            self.active_processes[item.item_id] = proc

        progress_re = re.compile(r'(\d+)%')
        stdout_lines = []

        try:
            for line in proc.stdout:
                if cancel_event and cancel_event.is_set():
                    proc.kill()
                    if dir_created_by_us and os.path.exists(target_dir):
                        shutil.rmtree(target_dir, ignore_errors=True)
                    return False, "Cancelled by user"

                stdout_lines.append(line)
                if len(stdout_lines) > 50:
                    stdout_lines.pop(0)

                match = progress_re.search(line)
                if match and progress_callback:
                    try:
                        pct = float(match.group(1))
                        progress_callback(pct)
                    except ValueError:
                        pass

            proc.wait()
            ret_code = proc.returncode

        except Exception as e:
            try:
                proc.kill()
            except Exception:
                pass
            if dir_created_by_us and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            return False, f"Extraction process crashed: {e}"
        finally:
            with self._lock:
                self.active_processes.pop(item.item_id, None)

        if cancel_event and cancel_event.is_set():
            if dir_created_by_us and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            return False, "Cancelled by user"

        # 7-Zip Return Codes:
        # 0: Success
        # 1: Warning (Non fatal error(s))
        # 2: Fatal error
        # 7: Command line error
        # 8: Not enough memory
        # 255: User stopped the process
        if ret_code == 0:
            if progress_callback:
                progress_callback(100.0)

            if effective_pw:
                item.password = effective_pw

            item.extracted_present = True
            item.extracted_dir = target_dir

            # Safely delete archive if requested
            if delete_after:
                try:
                    os.remove(item.path)
                    logger.info(f"Deleted source archive after successful extraction: {item.path}", category="decompressor")
                except Exception as del_err:
                    logger.warning(f"Extracted successfully but failed to delete archive: {del_err}", category="decompressor")

            return True, ""
        else:
            # Clean up failed / partial / 0-byte folder on extraction error
            if dir_created_by_us and os.path.exists(target_dir):
                try:
                    shutil.rmtree(target_dir, ignore_errors=True)
                except Exception:
                    pass

            tail_err = "".join(stdout_lines[-10:]).strip()
            err_msg = f"7-Zip exited with code {ret_code}: {tail_err or 'Decompression failed'}"
            return False, err_msg

    def cancel_all(self):
        """Terminate all actively running extraction processes."""
        with self._lock:
            for proc in list(self.active_processes.values()):
                try:
                    proc.kill()
                except Exception:
                    pass
            self.active_processes.clear()
