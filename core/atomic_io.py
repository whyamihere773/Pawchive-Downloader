"""
Crash-safe file writes.

A file is written to a temporary file in the same folder, flushed to disk, and then swapped into
place with os.replace. A crash or power cut mid-write therefore leaves either the old file or the
new one — never an empty or half-written file (which used to reset settings to defaults).
"""

import json
import os
import tempfile
import time
from typing import Any


def _replace(src: str, dst: str) -> None:
    # On Windows the target can be briefly locked (antivirus, indexer, a reader); retry shortly
    for attempt in range(8):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.05 * (attempt + 1))


def atomic_write_text(path: str, text: str, encoding: str = "utf-8") -> None:
    folder = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        _replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path: str, data: Any, **dump_kwargs) -> None:
    dump_kwargs.setdefault("ensure_ascii", False)
    atomic_write_text(path, json.dumps(data, **dump_kwargs))


# Public name for renaming a finished file over its destination (with the Windows lock retries)
replace_file = _replace
