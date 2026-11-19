"""
Normalized Browser Provider DTOs, Capabilities & Kemono Media URL Resolvers
Decomposed from core/browser_providers/base.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import html as html_lib
import os
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.filter_engine import FilterEngine


SERVICE_DISPLAY_NAMES: Dict[str, str] = {
    "all": "All Services",
    "onlyfans": "OnlyFans",
    "fansly": "Fansly",
    "candfans": "CandFans",
    "patreon": "Patreon",
    "fanbox": "Pixiv Fanbox",
    "fantia": "Fantia",
    "boosty": "Boosty",
    "gumroad": "Gumroad",
    "subscribestar": "SubscribeStar",
    "dlsite": "DLsite",
    "afdian": "Afdian",
}


def format_service_label(service: str) -> str:
    clean = (service or "").strip().lower()
    if not clean:
        return "Creator"
    return SERVICE_DISPLAY_NAMES.get(clean, clean.capitalize())


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declarative capability manifest for a browser provider."""
    supports_creator_search: bool = True
    supports_global_post_search: bool = True
    supports_creator_post_search: bool = True
    supports_tag_filter: bool = False
    supports_service_filter: bool = True
    supports_dms: bool = False
    supports_favorites: bool = False
    requires_cookie_auth: bool = False
    page_size: int = 50
    services: Tuple[Tuple[str, str], ...] = (("all", "All Services"),)
    sort_options: Tuple[Tuple[str, str], ...] = (
        ("popular", "Popular"),
        ("updated", "Recently Updated"),
        ("indexed", "Newly Indexed"),
        ("name", "Name (A–Z)"),
    )
    accent_color: str = "#38BDF8"
    badge_icon: str = "🌐"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "supportsCreatorSearch": self.supports_creator_search,
            "supportsGlobalPostSearch": self.supports_global_post_search,
            "supportsCreatorPostSearch": self.supports_creator_post_search,
            "supportsTagFilter": self.supports_tag_filter,
            "supportsServiceFilter": self.supports_service_filter,
            "supportsDms": self.supports_dms,
            "supportsFavorites": self.supports_favorites,
            "requiresCookieAuth": self.requires_cookie_auth,
            "pageSize": self.page_size,
            "services": [{"id": k, "label": v} for k, v in self.services],
            "sortOptions": [{"id": k, "label": v} for k, v in self.sort_options],
            "accentColor": self.accent_color,
            "badgeIcon": self.badge_icon,
        }


@dataclass
class BrowserPageResult:
    """Normalized page response from any provider."""
    items: List[Dict[str, Any]] = field(default_factory=list)
    total: int = 0
    offset: int = 0
    page_size: int = 50
    has_more: bool = False
    error: str = ""
    auth_required: bool = False


def build_creator_card_dto(
    *,
    provider_id: str,
    service: str,
    creator_id: str,
    name: str,
    url: str,
    avatar_url: str = "",
    banner_url: str = "",
    post_count: int = 0,
    video_count: int = 0,
    image_count: int = 0,
    dm_count: int = 0,
    favorited_count: int = 0,
    updated_at: str = "",
    tags: Optional[List[str]] = None,
    is_on_disk: bool = False,
    local_post_count: int = 0,
    local_file_count: int = 0,
    local_size_bytes: int = 0,
    local_drives: Optional[List[str]] = None,
    local_dirs: Optional[List[str]] = None,
    is_marked: bool = False,
    is_unimported: bool = False,
    is_favorited: bool = False,
) -> Dict[str, Any]:
    """Produces the normalized Creator dictionary consumed by RecordListModel and QML cards."""
    svc = (service or "unknown").strip().lower()
    cid = str(creator_id or "").strip()
    clean_name = (name or cid or "Unknown Creator").strip()
    key = f"{provider_id}:{svc}:{cid}"
    return {
        "key": key,
        "item_type": "creator",
        "provider_id": provider_id,
        "service": svc,
        "service_label": format_service_label(svc),
        "creator_id": cid,
        "creator_name": clean_name,
        "name": clean_name,
        "url": url,
        "avatar_url": avatar_url or "",
        "banner_url": banner_url or "",
        "post_count": int(post_count or 0),
        "video_count": int(video_count or 0),
        "image_count": int(image_count or 0),
        "dm_count": int(dm_count or 0),
        "favorited_count": int(favorited_count or 0),
        "updated_at": str(updated_at or "")[:10],
        "tags": FilterEngine.normalize_tags(tags),
        "is_on_disk": bool(is_on_disk),
        "local_post_count": int(local_post_count or 0),
        "local_file_count": int(local_file_count or 0),
        "local_size_bytes": int(local_size_bytes or 0),
        "local_drives": list(local_drives or []),
        "local_dirs": list(local_dirs or []),
        "is_marked": bool(is_marked),
        "is_unimported": bool(is_unimported),
        "is_favorited": bool(is_favorited),
    }


_VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".flv", ".wmv", ".m3u8", ".ts")
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".heic", ".heif", ".apng", ".svg")
_AUDIO_EXTS = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma")
_ARCHIVE_EXTS = (".zip", ".rar", ".7z", ".tar", ".gz", ".cbz", ".cbr", ".pdf", ".psd")


def html_to_readable_text(raw_html: str) -> str:
    """Converts HTML post body fragments into clean readable plain text with preserved paragraphs."""
    text = str(raw_html or "")
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:p|div|li|h[1-6]|blockquote|tr)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.splitlines()]
    cleaned: List[str] = []
    prev_blank = True
    for ln in lines:
        if not ln:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(ln)
            prev_blank = False
    return "\n".join(cleaned).strip()


def _infer_url_extension(name: str, url: str) -> str:
    ext = os.path.splitext((name or "").split("?", 1)[0].split("#", 1)[0])[1].lower()
    if ext:
        return ext
    clean_url = (url or "").split("#", 1)[0]
    ext = os.path.splitext(clean_url.split("?", 1)[0])[1].lower()
    if ext:
        return ext
    if "?" in clean_url:
        try:
            qs = urllib.parse.parse_qs(clean_url.split("?", 1)[1])
            for key in ("f", "filename", "file", "name"):
                vals = qs.get(key)
                if vals and vals[0]:
                    qext = os.path.splitext(vals[0])[1].lower()
                    if qext:
                        return qext
        except Exception:
            pass
    return ""


def build_media_attachment_dto(
    *,
    name: str,
    url: str,
    thumbnail_url: str = "",
    local_path: str = "",
    file_size: int = 0,
    media_type: str = "",
    is_loop: bool = False,
    modified_at: float = 0.0,
) -> Dict[str, Any]:
    ext = _infer_url_extension(name, url)
    # Check actual stream container extension when upstream serves GIF loops as MP4/WebM
    url_ext = _infer_url_extension("", url)
    resolved_type = (media_type or "").strip().lower()
    if url_ext in _VIDEO_EXTS:
        resolved_type = "video"
        if not ext:
            ext = url_ext
    elif not resolved_type:
        if ext in _VIDEO_EXTS:
            resolved_type = "video"
        elif ext in _IMAGE_EXTS:
            resolved_type = "image"
        elif ext in _AUDIO_EXTS:
            resolved_type = "audio"
        elif ext in _ARCHIVE_EXTS:
            resolved_type = "archive"
        else:
            resolved_type = "file"
    safe_thumb = thumbnail_url or ""
    if not safe_thumb and resolved_type == "image":
        safe_thumb = url
    elif safe_thumb and _infer_url_extension("", safe_thumb) in _VIDEO_EXTS:
        safe_thumb = ""
    return {
        "name": name or os.path.basename((url or "").split("?", 1)[0]) or "attachment",
        "url": url,
        "thumbnail_url": safe_thumb,
        "local_path": local_path,
        "file_size": int(file_size or 0),
        "ext": ext,
        "media_type": resolved_type,
        "is_loop": bool(is_loop or ext == ".gif" or (resolved_type == "video" and _infer_url_extension(name, "") == ".gif")),
        "modified_at": float(modified_at or 0.0),
    }


def resolve_kemono_media_urls(
    fobj: Dict[str, Any],
    base_domain: str = "pawchive.pw",
    post_raw: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[str, str, str]]:
    """
    Resolves (filename, full_url, thumbnail_url) for a Kemono/Pawchive/Coomer file or attachment dict.
    Respects `server` (`https://n1..n4.pawchive.pw`), `node` number, `?f=<filename>`, and
    temporary signed `t1..t4.pawchive.pw` URLs.
    """
    if not isinstance(fobj, dict):
        return None
    temp_dl = str(fobj.get("temp_download_url") or "").strip()
    temp_u = str(fobj.get("temp_url") or "").strip()
    raw_p = str(fobj.get("path") or "").strip()
    if temp_dl:
        raw_p = temp_dl
    elif temp_u and not temp_u.split("?")[0].lower().endswith(".m3u8"):
        raw_p = temp_u
    if not raw_p:
        return None

    clean_domain = (base_domain or "pawchive.pw").strip().lower()
    fname = str(fobj.get("name") or os.path.basename(raw_p.split("?")[0])).strip().rstrip(".,;!?")
    srv = str(
        fobj.get("server")
        or (post_raw.get("server") if isinstance(post_raw, dict) else "")
        or ""
    ).strip().rstrip("/")
    node = fobj.get("node") if fobj.get("node") is not None else (
        post_raw.get("node") if isinstance(post_raw, dict) else None
    )
    if not srv and node is not None:
        srv = f"https://n{node}.{clean_domain}"
    if srv and not srv.startswith(("http://", "https://")):
        srv = f"https://{srv}"

    url_ext = _infer_url_extension("", raw_p)
    media_ext = _infer_url_extension(fname, raw_p)
    thumb_ext = url_ext or media_ext
    # Only image attachments have /thumbnail/data/ previews on Pawchive/Kemono; archives/audio/video 404
    has_img_thumb = (thumb_ext in _IMAGE_EXTS) if thumb_ext else True

    if raw_p.startswith(("http://", "https://")):
        full_url = raw_p
        if re.match(r"^https?://pawchive\.pw/data/", full_url, re.IGNORECASE):
            target_host = srv or "https://n1.pawchive.pw"
            full_url = re.sub(r"^https?://pawchive\.pw", target_host, full_url, count=1, flags=re.IGNORECASE)
        if fname and "?f=" not in full_url and "&f=" not in full_url and "/data/" in full_url:
            sep = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{sep}f={urllib.parse.quote(fname, safe='')}"
        is_temp_host = bool(re.search(r"\bt\d+\.pawchive\.pw\b", full_url, re.IGNORECASE))
        if is_temp_host or not has_img_thumb:
            thumb_url = ""
        elif "/data/" in full_url and "/thumbnail/" not in full_url:
            m_rel = re.search(r"/data(/[0-9a-f]{2,3}/[0-9a-f]{2}/[^\s?#]+)", full_url, re.IGNORECASE)
            thumb_url = (
                f"https://img.{clean_domain}/thumbnail/data{m_rel.group(1)}"
                if m_rel
                else full_url
            )
        else:
            thumb_url = full_url
        return fname or "file", full_url, thumb_url

    clean_p = raw_p if raw_p.startswith("/") else f"/{raw_p}"
    if clean_p.startswith("/data/"):
        clean_p = clean_p[5:]
    if not clean_p.startswith("/"):
        clean_p = f"/{clean_p}"

    thumb_url = f"https://img.{clean_domain}/thumbnail/data{clean_p}" if has_img_thumb else ""
    if bool(fobj.get("preview_only")) and not srv and has_img_thumb:
        full_url = thumb_url
    else:
        target_srv = srv or (f"https://n1.{clean_domain}" if "pawchive" in clean_domain else f"https://{clean_domain}")
        full_url = f"{target_srv}/data{clean_p}"
        if fname:
            full_url = f"{full_url}?f={urllib.parse.quote(fname, safe='')}"

    return fname or os.path.basename(clean_p), full_url, thumb_url


def build_post_card_dto(
    *,
    provider_id: str,
    service: str,
    creator_id: str,
    post_id: str,
    title: str,
    url: str,
    creator_name: str = "",
    published_at: str = "",
    content_snippet: str = "",
    thumbnail_url: str = "",
    attachments: Optional[List[Dict[str, Any]]] = None,
    tags: Optional[List[str]] = None,
    is_on_disk: bool = False,
    disk_status: str = "",
    local_file_count: int = 0,
    expected_file_count: int = 0,
    local_folder: str = "",
    local_drives: Optional[List[str]] = None,
    is_marked: bool = False,
    is_dm: bool = False,
    is_unimported: bool = False,
) -> Dict[str, Any]:
    """Produces the normalized Post dictionary consumed by RecordListModel and QML post cards."""
    svc = (service or "unknown").strip().lower()
    cid = str(creator_id or "").strip()
    pid = str(post_id or "").strip()
    atts = list(attachments or [])
    img_count = sum(1 for a in atts if a.get("media_type") == "image")
    vid_count = sum(1 for a in atts if a.get("media_type") == "video")
    thumb = thumbnail_url
    if not thumb and atts:
        for a in atts:
            if a.get("thumbnail_url"):
                thumb = a["thumbnail_url"]
                break
    clean_title = (title or "").strip() or (f"DM #{pid}" if is_dm and pid else (f"Post #{pid}" if pid else "Untitled Post"))
    key_prefix = f"{provider_id}:{svc}:{cid}"
    key = f"{key_prefix}:dm:{pid}" if is_dm else f"{key_prefix}:{pid}"
    resolved_disk_status = (disk_status or ("complete" if is_on_disk else "none")).strip().lower()
    return {
        "key": key,
        "item_type": "post",
        "provider_id": provider_id,
        "service": svc,
        "service_label": format_service_label(svc),
        "creator_id": cid,
        "creator_name": (creator_name or cid or "Unknown Creator").strip(),
        "post_id": pid,
        "title": clean_title,
        "url": url,
        "published_at": str(published_at or "")[:10],
        "content_snippet": (content_snippet or "").strip(),
        "thumbnail_url": thumb or "",
        "file_count": len(atts),
        "image_count": img_count,
        "video_count": vid_count,
        "attachments": atts,
        "tags": FilterEngine.normalize_tags(tags),
        "is_on_disk": bool(is_on_disk or resolved_disk_status in ("complete", "partial")),
        "disk_status": resolved_disk_status,
        "local_file_count": int(local_file_count or (len(atts) if is_on_disk else 0)),
        "expected_file_count": int(expected_file_count or len(atts)),
        "local_folder": local_folder or "",
        "local_drives": list(local_drives or []),
        "is_marked": bool(is_marked),
        "is_dm": bool(is_dm),
        "is_unimported": bool(is_unimported),
    }


