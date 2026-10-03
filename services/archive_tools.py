"""
Gallery archive tools: create ZIP / 7z archives and extract archives with 7-Zip.

Extraction reuses BulkDecompressorEngine (progress parsing, encrypted-archive
probing, cleanup of partial output). The bundled 7za cannot read RAR, so RAR
files fall back to a full 7-Zip install when one is present.
"""

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Callable, List, Optional, Tuple

from core.logger import logger
from services.bulk_decompressor import (
    ARCHIVE_EXTENSIONS,
    ArchiveItem,
    BulkDecompressorEngine,
    get_7za_path,
)

# Formats the bundled 7za can read (it has no RAR or ISO support)
SEVEN_ZA_EXTENSIONS = {
    ".7z", ".zip", ".zipx", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".tbz",
    ".xz", ".txz", ".zst", ".tzst", ".cab", ".lzma",
}
FULL_7Z_ONLY_EXTENSIONS = {".rar", ".iso"}

COMPRESSION_LEVELS = {"store": 0, "fast": 1, "normal": 5, "max": 9}
ARCHIVE_FORMATS = {"zip": ".zip", "7z": ".7z"}

_INVALID_NAME_CHARS = set('<>:"/\\|?*')


def find_full_7z() -> str:
    """Locate a full 7-Zip install (7z.exe + codecs), which can also read RAR."""
    candidates = []
    if sys.platform == "win32":
        for env in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
            base = os.environ.get(env)
            if base:
                candidates.append(os.path.join(base, "7-Zip", "7z.exe"))
    for c in candidates:
        if os.path.isfile(c):
            return c
    found = shutil.which("7z")
    return found or ""


def archive_extension(filename: str) -> str:
    """Lower-case archive extension, treating split '.001' volumes as archives."""
    lower = filename.lower()
    if lower.endswith(".001"):
        return ".001"
    return os.path.splitext(lower)[1]


def is_archive_name(filename: str) -> bool:
    ext = archive_extension(filename)
    return ext == ".001" or ext in ARCHIVE_EXTENSIONS or ext in SEVEN_ZA_EXTENSIONS


def unique_archive_path(dest_dir: str, base_name: str, ext: str) -> str:
    """'name.zip', then 'name (2).zip', 'name (3).zip'… so nothing is ever overwritten."""
    target = os.path.join(dest_dir, base_name + ext)
    n = 2
    while os.path.exists(target):
        target = os.path.join(dest_dir, f"{base_name} ({n}){ext}")
        n += 1
    return target


def validate_archive_name(name: str) -> str:
    """Return an error message, or '' if the name is usable."""
    if not name or not name.strip():
        return "Please enter a name for the archive."
    if any(c in _INVALID_NAME_CHARS for c in name) or name.strip().endswith("."):
        return "The archive name contains characters that aren't allowed."
    return ""


class ProgressMeter:
    """Turns cumulative 'bytes done' samples into percent, speed and ETA.

    Speed is measured over a short sliding window and smoothed, so it reacts to
    slowdowns without jumping around on every 7-Zip update.
    """

    WINDOW = 4.0

    def __init__(self, total_bytes: int):
        self.total = max(0, int(total_bytes))
        self.start = time.monotonic()
        self._samples = deque()
        self._speed = 0.0

    def elapsed(self) -> float:
        return time.monotonic() - self.start

    def sample(self, done_bytes: float) -> dict:
        now = time.monotonic()
        done = max(0.0, min(float(self.total), float(done_bytes))) if self.total else 0.0
        self._samples.append((now, done))
        while len(self._samples) > 2 and now - self._samples[0][0] > self.WINDOW:
            self._samples.popleft()
        t0, b0 = self._samples[0]
        if now - t0 >= 0.5 and done >= b0:
            inst = (done - b0) / (now - t0)
            self._speed = inst if self._speed <= 0 else self._speed * 0.6 + inst * 0.4
        eta = -1.0
        if self._speed > 0 and self.elapsed() >= 2.0 and self.total:
            eta = (self.total - done) / self._speed
        return {
            "percent": (done / self.total * 100.0) if self.total else 0.0,
            "speed": self._speed,
            "eta": eta,
            "doneBytes": done,
            "totalBytes": self.total,
            "elapsed": self.elapsed(),
        }


def path_size(path: str) -> int:
    """Size of a file, or the total size of everything inside a folder."""
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    for dirpath, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def _hidden_window_kwargs() -> dict:
    if sys.platform != "win32":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return {"startupinfo": si, "creationflags": 0x08000000}  # CREATE_NO_WINDOW


class ArchiveTools:
    def __init__(self):
        self.engine = BulkDecompressorEngine()
        self._full_7z = find_full_7z()
        self.full_engine: Optional[BulkDecompressorEngine] = None
        if self._full_7z:
            self.full_engine = BulkDecompressorEngine()
            self.full_engine._7za_path = self._full_7z
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.engine.has_7za or bool(self._full_7z)

    def can_extract(self, filename: str) -> Tuple[bool, str]:
        """Whether this archive type can be opened, and why not if it can't."""
        ext = archive_extension(filename)
        if ext in FULL_7Z_ONLY_EXTENSIONS:
            if self.full_engine:
                return True, ""
            return False, f"{ext.lstrip('.').upper()} files need the full 7-Zip app installed (7-zip.org)."
        if not is_archive_name(filename):
            return False, "Not an archive."
        if not self.available:
            return False, "7-Zip is missing from the app's dependencies folder."
        return True, ""

    def engine_for(self, filename: str) -> BulkDecompressorEngine:
        ext = archive_extension(filename)
        if ext in FULL_7Z_ONLY_EXTENSIONS and self.full_engine:
            return self.full_engine
        if not self.engine.has_7za and self.full_engine:
            return self.full_engine
        return self.engine

    def cancel(self):
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self.engine.cancel_all()
        if self.full_engine:
            self.full_engine.cancel_all()

    def extract(
        self,
        archive_path: str,
        dest_dir: str,
        password: Optional[str],
        progress_cb: Optional[Callable[[float], None]],
        cancel_event: threading.Event,
        item_id: str,
    ) -> Tuple[bool, str, str]:
        """Extract into a new folder named after the archive inside dest_dir.

        Returns (success, error message, output folder).
        """
        name = os.path.basename(archive_path)
        try:
            size = os.path.getsize(archive_path)
        except OSError:
            size = 0
        item = ArchiveItem(
            item_id=item_id,
            path=archive_path,
            filename=name,
            directory=dest_dir,
            size=size,
            creator="",
        )
        engine = self.engine_for(name)
        # The engine's own encryption check runs a full '7za t', which reads the whole
        # archive with no progress output. Reading the header listing is near-instant.
        if not password and self.is_encrypted(archive_path, engine):
            return False, "ERROR: Can not open encrypted archive. Wrong password?", ""
        ok, err = engine.extract_single_archive(
            item=item,
            password=password,
            threads_per_archive=2,
            delete_after=False,
            progress_callback=progress_cb,
            cancel_event=cancel_event,
            overwrite=False,
            probe=False,
        )
        return ok, err, item.target_dir if ok else ""

    @staticmethod
    def is_encrypted(archive_path: str, engine: BulkDecompressorEngine) -> bool:
        """Fast check via the archive's file listing: flags encrypted entries or headers."""
        if not engine.has_7za:
            return False
        try:
            r = subprocess.run(
                [engine._7za_path, "l", "-slt", "-p-", "--", archive_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=120,
                **_hidden_window_kwargs(),
            )
        except Exception:
            return False
        out = r.stdout.decode("utf-8", errors="replace")
        if "Encrypted = +" in out:
            return True
        return r.returncode != 0 and engine.is_password_error(out)

    def create_archive(
        self,
        sources: List[str],
        dest_path: str,
        fmt: str,
        level: str,
        password: str,
        progress_cb: Optional[Callable[[float], None]],
        cancel_event: threading.Event,
    ) -> Tuple[bool, str]:
        """Pack files/folders into dest_path. Folders keep their name as the top level."""
        exe = get_7za_path() or self._full_7z
        if not exe:
            return False, "7-Zip is missing from the app's dependencies folder."
        if fmt not in ARCHIVE_FORMATS:
            return False, f"Unsupported archive format: {fmt}"

        parents = {os.path.normcase(os.path.dirname(os.path.normpath(s))) for s in sources}
        if len(parents) == 1:
            cwd = os.path.dirname(os.path.normpath(sources[0]))
            names = [os.path.basename(os.path.normpath(s)) for s in sources]
        else:
            cwd = None
            names = [os.path.normpath(s) for s in sources]

        cmd = [
            exe, "a",
            f"-t{fmt}",
            f"-mx={COMPRESSION_LEVELS.get(level, 5)}",
            "-bsp1",   # progress to stdout
            "-bb0",
            "-y",
            "-ssw",    # include files that are open for writing
        ]
        if password:
            cmd.append(f"-p{password}")
            if fmt == "zip":
                cmd.append("-mem=AES256")
            else:
                cmd.append("-mhe=on")  # also hide file names inside the 7z
        cmd.append("--")
        cmd.append(dest_path)
        cmd.extend(names)

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                **_hidden_window_kwargs(),
            )
        except Exception as e:
            return False, f"Failed to launch 7-Zip: {e}"

        with self._lock:
            self._proc = proc

        progress_re = re.compile(r"(\d+)%")
        tail: List[str] = []
        try:
            for line in proc.stdout:
                if cancel_event.is_set():
                    proc.kill()
                    break
                tail.append(line)
                if len(tail) > 40:
                    tail.pop(0)
                m = progress_re.search(line)
                if m and progress_cb:
                    try:
                        progress_cb(float(m.group(1)))
                    except ValueError:
                        pass
            proc.wait()
        except Exception as e:
            try:
                proc.kill()
            except Exception:
                pass
            self._remove_partial(dest_path)
            return False, f"Archiving crashed: {e}"
        finally:
            with self._lock:
                self._proc = None

        if cancel_event.is_set():
            self._remove_partial(dest_path)
            return False, "Cancelled by user"

        # 0 = OK, 1 = warning (e.g. a file was locked and skipped)
        if proc.returncode in (0, 1):
            if progress_cb:
                progress_cb(100.0)
            if proc.returncode == 1:
                warn = "".join(tail[-6:]).strip()
                return True, f"Created with warnings: {warn}" if warn else "Created with warnings"
            return True, ""

        self._remove_partial(dest_path)
        detail = "".join(tail[-8:]).strip()
        return False, f"7-Zip exited with code {proc.returncode}: {detail or 'archiving failed'}"

    @staticmethod
    def _remove_partial(path: str):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as e:
            logger.debug(f"Could not remove partial archive {path}: {e}", category="gallery")
