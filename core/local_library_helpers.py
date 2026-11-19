"""
Local Library Pure Path, Drive & Folder-Name Helpers
Decomposed from core/local_library.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import os
import re
from typing import Tuple


_KNOWN_SERVICES = {
    "onlyfans", "fansly", "candfans", "patreon", "fanbox",
    "fantia", "boosty", "gumroad", "subscribestar", "dlsite",
    "afdian", "coomerfans", "telegram",
}

_MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif",
    ".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi",
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac",
    ".zip", ".rar", ".7z",
}

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
_POST_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})?[_\-\s]*(?:post[_\-\s]*)?([0-9a-zA-Z]{4,24})[_\-\s]+(.+)$")
_TYPE_SUBFOLDERS = {
    "images", "image", "videos", "video", "audio",
    "archives", "archive", "other", "files", "documents",
}


def _normalize_post_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def _extract_drive_label(path: str) -> str:
    if not path:
        return ""
    norm = os.path.normpath(path)
    drive, _ = os.path.splitdrive(norm)
    if drive:
        return drive.upper()
    parts = [p for p in norm.split(os.sep) if p]
    if len(parts) >= 2 and parts[0] in ("mnt", "media", "volumes"):
        return f"/{parts[0]}/{parts[1]}"
    return "/"


def _to_thumb_url(local_path: str) -> str:
    if not local_path:
        return ""
    norm = os.path.normpath(local_path).replace("\\", "/")
    return f"image://thumb/{norm}"


def _infer_service_and_name(folder_name: str) -> Tuple[str, str]:
    """Parses 'CreatorName (patreon)' or 'CreatorName [onlyfans]' or plain 'CreatorName'."""
    raw = (folder_name or "").strip()
    m = re.match(r"^(.+?)\s*[\(\[]([a-zA-Z0-9_.-]+)[\)\]]$", raw)
    if m:
        name_part, svc_part = m.group(1).strip(), m.group(2).strip().lower()
        if svc_part in _KNOWN_SERVICES:
            return svc_part, name_part
    for svc in _KNOWN_SERVICES:
        suffix = f"_{svc}"
        if raw.lower().endswith(suffix) and len(raw) > len(suffix):
            return svc, raw[: -len(suffix)].strip()
    return "local", raw


