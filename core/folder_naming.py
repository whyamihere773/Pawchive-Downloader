"""
How creator folders are named: "Artist [onlyfans]" (the default) or just "Artist", set with
"Site in Folder Name" (Downloader → Folder Organization & Naming).

New folders follow the setting; existing folders are found under either name, so turning it on or
off never loses track of what was downloaded before.
"""

import os
from typing import List

include_service = True


def creator_folder(name: str, service: str) -> str:
    """The folder name for a creator (name already cleaned for the file system)."""
    return f"{name} [{service}]" if include_service and service else name


def creator_folder_names(name: str, service: str) -> List[str]:
    """Every name a creator's folder may have, the current setting's first."""
    tagged = f"{name} [{service}]" if service else name
    first = creator_folder(name, service)
    return [first] + [n for n in (tagged, name) if n != first]


def pick_creator_folder(parent: str, name: str, service: str) -> str:
    """The creator's folder inside parent: one that already exists under either name, else a new
    one named by the setting (switching the setting doesn't start a second folder next to the old)."""
    for n in creator_folder_names(name, service):
        path = os.path.join(parent, n)
        if os.path.isdir(path):
            return path
    return os.path.join(parent, creator_folder(name, service))


def is_creator_folder(folder_name: str, name: str, service: str) -> bool:
    """The folder is this creator's, under either name (case doesn't matter)."""
    low = (folder_name or "").lower()
    return any(low == n.lower() for n in creator_folder_names(name, service))
