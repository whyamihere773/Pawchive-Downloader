"""
Paths saved by the app on the other operating system (dual boot with a shared drive, or the same data
used from Windows and WSL).

Windows names a shared drive "D:\\some\\folder", Linux / WSL "/mnt/d/some/folder". Saved paths (the
download folder, Watchlist folders, storage drives, queued files, archive records) are translated to
this system's form when they're read, so they keep working on both. Other paths are left as they are.
The Linux side follows WSL's "/mnt/<drive>"; settings.json can set another pattern
("windows_drive_mount", e.g. "/media/me/{drive}").
"""

import os
import re

mount_pattern = "/mnt/{drive}"            # where Windows drives are on Linux; {drive} is the letter

_WIN_DRIVE = re.compile(r"^([A-Za-z]):(?:[\\/](.*))?$")


def _linux_drive_regex():
    head, _, tail = mount_pattern.partition("{drive}")
    return re.compile("^" + re.escape(head) + r"([A-Za-z])" + re.escape(tail) + r"(?:/(.*))?$")


def localize_path(path: str, windows: bool = None) -> str:
    """The path as this system names it ("D:\\a\\b" ↔ "/mnt/d/a/b"); anything else unchanged."""
    if not path or not isinstance(path, str):
        return path
    if (os.name == "nt") if windows is None else windows:     # (windows: the system to name it for)
        m = _linux_drive_regex().match(path)
        if m:
            rest = (m.group(2) or "").strip("/")
            return f"{m.group(1).upper()}:\\" + rest.replace("/", "\\")
        return path
    m = _WIN_DRIVE.match(path)
    if m:
        rest = (m.group(2) or "").replace("\\", "/").strip("/")
        root = mount_pattern.replace("{drive}", m.group(1).lower())
        return root + ("/" + rest if rest else "")
    return path


def localize_paths(paths):
    return [localize_path(p) for p in (paths or [])]
