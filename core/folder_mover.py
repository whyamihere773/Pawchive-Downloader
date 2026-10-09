"""
Moving an artist's downloaded files to another folder ("Change download folder" in the Watchlist).

Everything in the old folder goes into the new one, keeping sub-folders. Folders that exist on both
sides are merged; a file that's already there with the same size is a duplicate (the old copy is
removed); a different file with the same name is kept as "name (2).ext". Nothing is overwritten. The
old folder is removed only when it ends up empty.
"""

import os
import shutil
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class MoveResult:
    moved: int = 0
    duplicates: int = 0
    renamed: int = 0
    errors: List[str] = field(default_factory=list)


def count_files(folder: str) -> (int, int):
    """(files, bytes) in a folder and its sub-folders."""
    n = size = 0
    for root, _dirs, files in os.walk(folder):
        for f in files:
            n += 1
            try:
                size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n, size


def _free_name(path: str) -> str:
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem} ({n}){ext}"):
        n += 1
    return f"{stem} ({n}){ext}"


def move_folder_contents(src: str, dst: str, cancel: Optional[threading.Event] = None,
                         on_file: Optional[Callable[[str, str], None]] = None) -> MoveResult:
    """Moves everything inside src into dst (see the module notes). on_file(old_path, new_path) is
    called for every file that now lives somewhere else."""
    result = MoveResult()
    os.makedirs(dst, exist_ok=True)
    for name in sorted(os.listdir(src)):
        if cancel is not None and cancel.is_set():
            break
        s, d = os.path.join(src, name), os.path.join(dst, name)
        try:
            if os.path.isdir(s) and not os.path.islink(s):
                if os.path.isdir(d):
                    sub = move_folder_contents(s, d, cancel, on_file)
                    result.moved += sub.moved
                    result.duplicates += sub.duplicates
                    result.renamed += sub.renamed
                    result.errors += sub.errors
                    _remove_if_empty(s)
                    continue
                if os.path.exists(d):
                    d = _free_name(d)
                    result.renamed += 1
                files = [os.path.join(r, f) for r, _ds, fs in os.walk(s) for f in fs]
                shutil.move(s, d)
                result.moved += len(files)
                if on_file:
                    for old in files:
                        on_file(old, os.path.join(d, os.path.relpath(old, s)))
                continue
            if os.path.exists(d):
                if os.path.isfile(d) and os.path.getsize(d) == os.path.getsize(s):
                    os.remove(s)                       # the same file is already there
                    result.duplicates += 1
                    if on_file:
                        on_file(s, d)
                    continue
                d = _free_name(d)
                result.renamed += 1
            shutil.move(s, d)
            result.moved += 1
            if on_file:
                on_file(s, d)
        except OSError as e:
            result.errors.append(f"{name}: {e}")
    _remove_if_empty(src)
    return result


def _remove_if_empty(folder: str) -> None:
    try:
        if os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)
    except OSError:
        pass
