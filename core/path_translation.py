"""
Paths saved by the app on the other operating system (dual boot with a shared drive, or the same data
used from Windows and WSL).

Windows names a shared drive "D:\\some\\folder"; Linux names it "/mnt/d/some/folder" (WSL) or wherever
the drive is mounted ("/media/me/DATA/some/folder", "/run/media/me/DATA/…"). Saved paths (the download
folder, Watchlist folders, storage drives, queued files, archive records, Gallery favourites) are
translated to this system's form when they're read, so they keep working on both. Other paths are left
as they are.

- On Linux, a Windows drive is looked for at WSL's "/mnt/<drive>" first, then among the mounted Windows
  drives (NTFS / exFAT / FAT): the one where the path's folders exist. settings.json can set a fixed
  pattern ("windows_drive_mount", e.g. "/media/me/{drive}").
- On Windows, "/mnt/<letter>/…" is that drive; "/media/<user>/<name>/…", "/run/media/<user>/<name>/…"
  and "/mnt/<name>/…" are the drive whose volume label is <name> (or where the path's folders exist).
"""

import os
import re
import string
import time
from typing import Dict, List, Optional

mount_pattern = "/mnt/{drive}"            # where Windows drives are on Linux; {drive} is the letter

_WIN_DRIVE = re.compile(r"^([A-Za-z]):(?:[\\/](.*))?$")
_LINUX_MOUNT = re.compile(r"^(?:/run/media/[^/]+|/media/[^/]+|/media|/mnt)/([^/]+)(?:/(.*))?$")
_WINDOWS_FS = {"ntfs", "ntfs3", "fuseblk", "exfat", "vfat", "msdos", "9p", "drvfs"}
# Drives found: a lookup costs file-system calls (150 µs on Windows), and a big queue saved on the other
# system has hundreds of thousands of paths. Not found: looked for again after a minute (drive plugged in).
_found_mounts: Dict[object, object] = {}
_MISS_TTL = 60.0


def _cached(key, find):
    hit = _found_mounts.get(key)
    if hit is not None and not (isinstance(hit, float) and time.monotonic() - hit > _MISS_TTL):
        return None if isinstance(hit, float) else hit
    found = find()
    if len(_found_mounts) > 4096:
        _found_mounts.clear()
    _found_mounts[key] = found if found else time.monotonic()
    return found


def _found_on(drive_key, first: str, find):
    """A drive once found is kept for every path on it; a miss is remembered per first folder."""
    hit = _found_mounts.get(drive_key)
    if isinstance(hit, str):
        return hit
    found = _cached(drive_key + (first.lower(),), find)
    if found:
        _found_mounts[drive_key] = found
    return found


def _linux_drive_regex():
    head, _, tail = mount_pattern.partition("{drive}")
    return re.compile("^" + re.escape(head) + r"([A-Za-z])" + re.escape(tail) + r"(?:/(.*))?$")


def _first_part(rest: str) -> str:
    return rest.split("/", 1)[0] if rest else ""


def _linux_mounts() -> List[str]:
    """Mount points of Windows-format drives on this Linux system."""
    out = []
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[2].lower() in _WINDOWS_FS:
                    out.append(parts[1].replace("\\040", " "))
    except OSError:
        pass
    return out


def _linux_root(letter: str, rest: str) -> str:
    """Where Windows drive <letter> is on this Linux system."""
    letter = letter.lower()
    pattern_root = mount_pattern.replace("{drive}", letter)
    if mount_pattern != "/mnt/{drive}":
        return pattern_root
    if _cached(("wsl", letter), lambda: pattern_root if os.path.isdir(pattern_root) else None):
        return pattern_root
    first = _first_part(rest)

    def find():
        for m in _linux_mounts():
            if first and os.path.exists(os.path.join(m, first)):
                return m
        return None
    return _found_on(("linux", letter), first, find) or pattern_root


def _windows_labels() -> Dict[str, str]:
    """{volume label (lower case): "D:"} of the drives on this Windows system."""
    labels = {}
    try:
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if not mask & (1 << i):
                continue
            buf = ctypes.create_unicode_buffer(261)
            if ctypes.windll.kernel32.GetVolumeInformationW(f"{letter}:\\", buf, 261, None, None, None, None, 0):
                if buf.value:
                    labels[buf.value.lower()] = f"{letter}:"
    except Exception:
        pass
    return labels


def _windows_drive_for(name: str, rest: str) -> Optional[str]:
    """The drive a Linux mount named <name> stands for: by volume label, else where the path's
    folders exist."""
    first = _first_part(rest)

    def find():
        drive = _windows_labels().get(name.lower())
        if drive:
            return drive
        if first:
            for letter in string.ascii_uppercase[2:]:
                if os.path.exists(f"{letter}:\\{first}"):
                    return f"{letter}:"
        return None
    return _found_on(("windows", name.lower()), first, find)


def localize_path(path: str, windows: bool = None) -> str:
    """The path as this system names it ("D:\\a\\b" ↔ "/mnt/d/a/b"); anything else unchanged.
    windows: the system to name it for (this one by default)."""
    if not path or not isinstance(path, str):
        return path
    if (os.name == "nt") if windows is None else windows:
        m = _linux_drive_regex().match(path)
        if m:
            rest = (m.group(2) or "").strip("/")
            return f"{m.group(1).upper()}:\\" + rest.replace("/", "\\")
        m = _LINUX_MOUNT.match(path)
        if m and os.name == "nt":
            rest = (m.group(2) or "").strip("/")
            drive = _windows_drive_for(m.group(1), rest)
            if drive:
                return drive + "\\" + rest.replace("/", "\\")
        return path
    m = _WIN_DRIVE.match(path)
    if m:
        rest = (m.group(2) or "").replace("\\", "/").strip("/")
        root = _linux_root(m.group(1), rest)
        return root + ("/" + rest if rest else "")
    return path


def localize_paths(paths):
    return [localize_path(p) for p in (paths or [])]
