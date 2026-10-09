"""
FFmpeg for compressing videos (Decompressor → "Compress after extracting").

Not bundled with the app (it's ~200 MB): used from the dependencies folder or the system PATH, or downloaded
on request from the FFmpeg builds GitHub publishes (BtbN/FFmpeg-Builds), checked against the release's
SHA-256 list. Only ffmpeg itself is kept from the download.
"""

import hashlib
import io
import os
import re
import shutil
import sys
import tarfile
import threading
import zipfile
from typing import Callable, Optional, Tuple

import requests

from core.logger import logger

RELEASES_API = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
_BINARY = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
_PLATFORM = "win64" if sys.platform == "win32" else "linux64"


def _dependencies_dir() -> str:
    from core.path_utils import get_dependencies_dir
    return get_dependencies_dir()


def find_ffmpeg() -> str:
    """Path of an ffmpeg executable, or ""."""
    try:
        local = os.path.join(_dependencies_dir(), _BINARY)
        if os.path.isfile(local):
            return local
    except Exception:
        pass
    return shutil.which("ffmpeg") or ""


def pick_asset(assets) -> Tuple[str, str, int]:
    """(name, url, size) of the newest stable GPL build for this system (x264 / x265 / SVT-AV1 included),
    falling back to the development build."""
    ext = ".zip" if _PLATFORM == "win64" else ".tar.xz"
    stable, master = [], None
    for a in assets or []:
        n = a.get("name", "")
        if not n.endswith(ext) or "shared" in n or f"-{_PLATFORM}-gpl" not in n:
            continue
        m = re.match(r"ffmpeg-n(\d+)\.(\d+)-latest-", n)
        if m:
            stable.append(((int(m.group(1)), int(m.group(2))), a))
        elif n.startswith("ffmpeg-master-latest-"):
            master = a
    best = max(stable, key=lambda x: x[0])[1] if stable else master
    if not best:
        return "", "", 0
    return best["name"], best["browser_download_url"], int(best.get("size") or 0)


class FfmpegDownloader:
    """Downloads and installs ffmpeg into the dependencies folder (one download at a time)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.cancel_event = threading.Event()

    def download(self, on_progress: Optional[Callable[[int, int], None]] = None) -> Tuple[bool, str]:
        """(True, path) or (False, a message for the user)."""
        if not self._lock.acquire(blocking=False):
            return False, "FFmpeg is already being downloaded."
        self.cancel_event.clear()
        try:
            return self._download(on_progress)
        except requests.RequestException as e:
            return False, f"FFmpeg couldn't be downloaded: {e}"
        except Exception as e:
            logger.exception("FFmpeg download failed", category="ffmpeg")
            return False, f"FFmpeg couldn't be installed: {e}"
        finally:
            self._lock.release()

    def _download(self, on_progress) -> Tuple[bool, str]:
        rel = requests.get(RELEASES_API, timeout=30)
        rel.raise_for_status()
        assets = rel.json().get("assets", [])
        name, url, size = pick_asset(assets)
        if not url:
            return False, "No FFmpeg build for this system was found."
        sums_url = next((a["browser_download_url"] for a in assets if a.get("name") == "checksums.sha256"), "")
        expected = ""
        if sums_url:
            for line in requests.get(sums_url, timeout=30).text.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].lstrip("*") == name:
                    expected = parts[0].lower()
        if not expected:
            return False, "FFmpeg's checksum couldn't be found, so it wasn't installed."

        logger.info(f"Downloading FFmpeg ({name}, {size / 1e6:.0f} MB)…", category="ffmpeg")
        buf = io.BytesIO()
        h = hashlib.sha256()
        done = 0
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or size or 0)
            for chunk in r.iter_content(1024 * 1024):
                if self.cancel_event.is_set():
                    return False, "Cancelled"
                buf.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done, total)
        if h.hexdigest() != expected:
            return False, "The FFmpeg download was damaged (checksum mismatch), so it wasn't installed."

        dest_dir = _dependencies_dir()
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, _BINARY)
        tmp = dest + ".part"
        buf.seek(0)
        if name.endswith(".zip"):
            with zipfile.ZipFile(buf) as z:
                member = next((m for m in z.namelist() if m.endswith("/bin/" + _BINARY)), None)
                if not member:
                    return False, "ffmpeg wasn't found in the download."
                with z.open(member) as src, open(tmp, "wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
        else:
            with tarfile.open(fileobj=buf, mode="r:xz") as t:
                member = next((m for m in t.getmembers() if m.name.endswith("/bin/" + _BINARY)), None)
                if not member:
                    return False, "ffmpeg wasn't found in the download."
                with t.extractfile(member) as src, open(tmp, "wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
            os.chmod(tmp, 0o755)
        os.replace(tmp, dest)
        logger.success(f"FFmpeg installed ({name}).", category="ffmpeg")
        return True, dest
