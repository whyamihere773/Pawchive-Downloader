"""
Modular Browser Provider Base Contracts, Normalized DTOs, and Reusable Catalog Engine.

Every online archive site (and future provider added down the line) implements `BaseBrowserProvider`
or subclasses `KemonoStyleCatalogProvider`. The QML Browser UI reads `ProviderCapabilities`
and normalized DTOs, requiring zero UI changes when new sites are registered.
"""

from __future__ import annotations

import os
import re
import time
import json
import hashlib
import html as html_lib
import sqlite3
import threading
import urllib.parse
import requests
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from core.logger import logger
from core.filter_engine import FilterEngine
from core.providers import cookie_for_url, is_disabled


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


class BaseBrowserProvider(ABC):
    """
    Abstract base contract for any site integrated into the Native Browser tab.
    New sites only need to implement this class and decorate with `@register_browser_provider`.
    """

    provider_id: str = ""
    display_name: str = ""
    base_domain: str = ""
    order: int = 100
    _fav_keys_ttl: float = 60.0

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
            "Accept": "text/css,*/*;q=0.1,application/json",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self._fav_lock = threading.RLock()
        self._fav_keys_cache: Optional[Set[Tuple[str, str]]] = None
        self._fav_keys_cookie: str = ""
        self._fav_keys_ts: float = 0.0

    def is_enabled(self) -> bool:
        return bool(self.provider_id) and not is_disabled(self.provider_id)

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        ...

    def get_manifest_entry(self) -> Dict[str, Any]:
        caps = self.capabilities()
        return {
            "id": self.provider_id,
            "name": self.display_name,
            "domain": self.base_domain,
            "icon": caps.badge_icon,
            "accentColor": caps.accent_color,
            "capabilities": caps.to_dict(),
        }

    def _request_headers(self, url: str) -> Dict[str, str]:
        headers = {
            "Referer": f"https://{self.base_domain}/",
            "Accept": "text/css,*/*;q=0.1,application/json",
        }
        cookie = cookie_for_url(url)
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def build_creator_url(self, service: str, creator_id: str) -> str:
        return f"https://{self.base_domain}/{service}/user/{creator_id}"

    def build_post_url(self, service: str, creator_id: str, post_id: str) -> str:
        return f"https://{self.base_domain}/{service}/user/{creator_id}/post/{post_id}"

    def build_dms_url(self, service: str, creator_id: str) -> str:
        return ""

    def build_dm_url(self, service: str, creator_id: str, dm_id: str) -> str:
        return ""

    @abstractmethod
    def list_creators(
        self,
        query: str = "",
        service: str = "all",
        tag: str = "",
        sort: str = "popular",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        ...

    @abstractmethod
    def list_creator_posts(
        self,
        service: str,
        creator_id: str,
        creator_name: str = "",
        query: str = "",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        ...

    def search_global_posts(
        self,
        query: str = "",
        service: str = "all",
        tag: str = "",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        return BrowserPageResult(items=[], total=0, offset=offset, page_size=limit, has_more=False)

    def get_post_detail(
        self,
        service: str,
        creator_id: str,
        post_id: str,
        creator_name: str = "",
        cancel_event: Optional[threading.Event] = None,
    ) -> Optional[Dict[str, Any]]:
        return None

    def list_tags(self, query: str = "", limit: int = 40) -> List[Dict[str, Any]]:
        return []

    def list_creator_dms(
        self,
        service: str,
        creator_id: str,
        creator_name: str = "",
        query: str = "",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        return BrowserPageResult(items=[], total=0, offset=offset, page_size=limit, has_more=False)

    def _current_auth_cookie(self) -> str:
        if not self.base_domain:
            return ""
        return cookie_for_url(f"https://{self.base_domain}/")

    def invalidate_favorite_cache(self) -> None:
        with self._fav_lock:
            self._fav_keys_cache = None
            self._fav_keys_cookie = ""
            self._fav_keys_ts = 0.0

    def _set_cached_fav_keys(self, keys: Set[Tuple[str, str]], cookie: str) -> None:
        with self._fav_lock:
            self._fav_keys_cache = set(keys)
            self._fav_keys_cookie = cookie
            self._fav_keys_ts = time.monotonic()

    def _update_cached_fav_key(
        self, service: str, creator_id: str, favorite: bool, cookie: Optional[str] = None
    ) -> None:
        svc = (service or "").strip().lower()
        cid = str(creator_id or "").strip()
        if not svc or not cid:
            return
        with self._fav_lock:
            if cookie and self._fav_keys_cookie != cookie:
                self._fav_keys_cache = set()
                self._fav_keys_cookie = cookie
            if self._fav_keys_cache is None:
                return
            if favorite:
                self._fav_keys_cache.add((svc, cid))
            else:
                self._fav_keys_cache.discard((svc, cid))
            self._fav_keys_ts = time.monotonic()

    def _get_cached_fav_keys(self, loader_fn, force_refresh: bool = False) -> Optional[Set[Tuple[str, str]]]:
        cookie = self._current_auth_cookie()
        if not cookie:
            self.invalidate_favorite_cache()
            return None
        with self._fav_lock:
            if (
                not force_refresh
                and self._fav_keys_cache is not None
                and self._fav_keys_cookie == cookie
                and (time.monotonic() - self._fav_keys_ts) < self._fav_keys_ttl
            ):
                return set(self._fav_keys_cache)
        loaded = loader_fn(cookie)
        if loaded is None:
            self.invalidate_favorite_cache()
            return None
        self._set_cached_fav_keys(loaded, cookie)
        return set(loaded)

    def get_favorite_creator_keys(self, force_refresh: bool = False) -> Optional[Set[Tuple[str, str]]]:
        """Returns set of (service, creator_id) favorited in the user's account, or None if not logged in."""
        return None

    def set_creator_favorite(self, service: str, creator_id: str, favorite: bool) -> Dict[str, Any]:
        """Adds or removes a creator in the user's site account favorites."""
        return {
            "ok": False,
            "is_favorited": not bool(favorite),
            "auth_required": False,
            "error": f"{self.display_name or self.provider_id} does not support account favorites.",
        }


class KemonoStyleCatalogProvider(BaseBrowserProvider):
    """
    Reusable base provider for any site using the Kemono-compatible `/api/v1/creators`
    and `/api/v1/{service}/user/{id}/posts` REST structure (such as Pawchive and future mirrors).

    Automatically caches `/api/v1/creators` into a local SQLite database (`browser_cache.db`)
    so searching, filtering by service, and sorting 100k+ creators takes <5ms locally.
    """

    catalog_ttl_seconds: int = 3600 * 6  # Refresh creator catalog every 6 hours
    default_services: Tuple[Tuple[str, str], ...] = (
        ("all", "All Services"),
        ("patreon", "Patreon"),
        ("fanbox", "Pixiv Fanbox"),
        ("fantia", "Fantia"),
        ("boosty", "Boosty"),
        ("gumroad", "Gumroad"),
        ("subscribestar", "SubscribeStar"),
        ("dlsite", "DLsite"),
    )
    default_accent_color: str = "#A78BFA"
    default_badge_icon: str = "🐾"
    default_supports_favorites: bool = False

    def __init__(self, cache_db_path: Optional[str] = None):
        super().__init__()
        if not cache_db_path:
            from core.path_utils import get_config_dir
            cache_db_path = os.path.join(get_config_dir(), "browser_cache.db")
        self.cache_db_path = cache_db_path
        self._db_lock = threading.RLock()
        self._sync_lock = threading.Lock()
        self._ensure_tables()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_creator_search=True,
            supports_global_post_search=True,
            supports_creator_post_search=True,
            supports_tag_filter=False,
            supports_service_filter=True,
            supports_dms=True,
            supports_favorites=self.default_supports_favorites,
            requires_cookie_auth=False,
            page_size=50,
            services=self.default_services,
            sort_options=(
                ("popular", "Most Favorited"),
                ("updated", "Recently Updated"),
                ("indexed", "Newly Indexed"),
                ("name", "Name (A–Z)"),
            ),
            accent_color=self.default_accent_color,
            badge_icon=self.default_badge_icon,
        )

    @contextmanager
    def _conn(self):
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path, timeout=15.0)
        try:
            conn.execute("PRAGMA synchronous=NORMAL;")
            yield conn
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_tables(self):
        try:
            with self._db_lock, self._conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS catalog_creators (
                        provider_id TEXT NOT NULL,
                        service TEXT NOT NULL,
                        creator_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        name_lower TEXT NOT NULL,
                        favorited INTEGER DEFAULT 0,
                        indexed INTEGER DEFAULT 0,
                        updated INTEGER DEFAULT 0,
                        ever_imported INTEGER DEFAULT 1,
                        PRIMARY KEY (provider_id, service, creator_id)
                    );
                    """
                )
                cols = {r[1] for r in conn.execute("PRAGMA table_info(catalog_creators);").fetchall()}
                migrated_ever_imported = "ever_imported" not in cols
                if migrated_ever_imported:
                    conn.execute("ALTER TABLE catalog_creators ADD COLUMN ever_imported INTEGER DEFAULT 1;")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cat_prov_svc ON catalog_creators(provider_id, service);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cat_prov_fav ON catalog_creators(provider_id, favorited DESC);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cat_prov_upd ON catalog_creators(provider_id, updated DESC);"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS catalog_meta (
                        provider_id TEXT PRIMARY KEY,
                        synced_at REAL DEFAULT 0,
                        total_count INTEGER DEFAULT 0
                    );
                    """
                )
                if migrated_ever_imported:
                    conn.execute("UPDATE catalog_meta SET synced_at = 0;")
        except Exception as e:
            logger.debug(f"[BrowserCatalog] Table init warning: {e}", category="api")

    def _needs_catalog_sync(self) -> bool:
        try:
            with self._db_lock, self._conn() as conn:
                row = conn.execute(
                    "SELECT synced_at, total_count FROM catalog_meta WHERE provider_id = ?;",
                    (self.provider_id,),
                ).fetchone()
                if not row or int(row[1] or 0) == 0:
                    return True
                return (time.time() - float(row[0] or 0)) > self.catalog_ttl_seconds
        except Exception:
            return True

    def ensure_catalog_synced(self, force: bool = False, cancel_event: Optional[threading.Event] = None) -> bool:
        if not force and not self._needs_catalog_sync():
            return True
        if not self._sync_lock.acquire(blocking=True, timeout=30.0):
            return False
        try:
            if not force and not self._needs_catalog_sync():
                return True
            url = f"https://{self.base_domain}/api/v1/creators"
            resp = self._session.get(url, headers=self._request_headers(url), timeout=25)
            if resp.status_code != 200:
                logger.warning(f"[{self.display_name}] Catalog fetch returned HTTP {resp.status_code}", category="api")
                return False
            data = resp.json()
            if not isinstance(data, list):
                return False
            rows = []
            for item in data:
                if cancel_event and cancel_event.is_set():
                    return False
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("id") or "").strip()
                svc = str(item.get("service") or "").strip().lower()
                name = str(item.get("name") or cid).strip()
                if not cid or not svc:
                    continue
                fav = int(item.get("favorited") or 0)
                idx = int(item.get("indexed") or 0)
                upd = int(item.get("updated") or 0)
                ever_imp = 0 if (item.get("ever_imported") is False) else 1
                rows.append((self.provider_id, svc, cid, name, name.lower(), fav, idx, upd, ever_imp))

            with self._db_lock, self._conn() as conn:
                conn.execute("DELETE FROM catalog_creators WHERE provider_id = ?;", (self.provider_id,))
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO catalog_creators
                    (provider_id, service, creator_id, name, name_lower, favorited, indexed, updated, ever_imported)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    rows,
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO catalog_meta (provider_id, synced_at, total_count)
                    VALUES (?, ?, ?);
                    """,
                    (self.provider_id, time.time(), len(rows)),
                )
            logger.info(f"[{self.display_name}] Indexed {len(rows)} creators into local catalog cache.", category="api")
            return True
        except Exception as e:
            logger.warning(f"[{self.display_name}] Catalog sync failed: {e}", category="api")
            return False
        finally:
            self._sync_lock.release()

    def resolve_avatar_url(self, service: str, creator_id: str) -> str:
        return f"https://{self.base_domain}/icons/{service}/{creator_id}"

    def resolve_banner_url(self, service: str, creator_id: str) -> str:
        return f"https://{self.base_domain}/banners/{service}/{creator_id}"

    def is_creator_unimported_cached(self, service: str, creator_id: str) -> bool:
        """Returns True if the cached catalog explicitly flags this creator as never imported."""
        svc = (service or "").strip().lower()
        cid = str(creator_id or "").strip()
        if not svc or not cid or not os.path.isfile(self.cache_db_path):
            return False
        try:
            with self._db_lock, self._conn() as conn:
                row = conn.execute(
                    """
                    SELECT COALESCE(ever_imported, 1)
                    FROM catalog_creators
                    WHERE provider_id = ? AND service = ? AND creator_id = ?;
                    """,
                    (self.provider_id, svc, cid),
                ).fetchone()
                return bool(row is not None and int(row[0] if row[0] is not None else 1) == 0)
        except Exception:
            return False

    @staticmethod
    def _parse_ts_sort_and_date(val: Any) -> Tuple[float, str]:
        if val is None or val == "":
            return 0.0, ""
        if isinstance(val, (int, float)):
            ts = float(val)
            if ts > 1e12:
                ts /= 1000.0
            if ts > 0:
                try:
                    return ts, time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
                except Exception:
                    return ts, ""
            return 0.0, ""
        s = str(val).strip()
        if s.isdigit() and 9 <= len(s) <= 13:
            ts = float(int(s))
            if ts > 1e12:
                ts /= 1000.0
            try:
                return ts, time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
            except Exception:
                return ts, ""
        return 0.0, s[:10]

    def _fetch_account_favorite_creators(
        self, cookie: Optional[str] = None, timeout: int = 20
    ) -> Tuple[Optional[List[Dict[str, Any]]], bool, str]:
        """Fetches raw favorited creator dicts from `/api/v1/account/favorites?type=artist`."""
        auth_cookie = cookie if cookie is not None else self._current_auth_cookie()
        if not auth_cookie:
            return None, True, f"Log in to {self.display_name} to view your favorited creators."
        url = f"https://{self.base_domain}/api/v1/account/favorites?type=artist"
        headers = {
            **self._request_headers(url),
            "Cookie": auth_cookie,
            "Accept": "application/json, text/css, */*;q=0.1",
        }
        try:
            resp = self._session.get(url, headers=headers, timeout=timeout)
            if resp.status_code in (401, 403):
                return None, True, f"Session expired or unauthorized. Please log in to {self.display_name}."
            if resp.status_code != 200:
                return None, False, f"HTTP {resp.status_code}"
            payload = resp.json()
            if isinstance(payload, list):
                raw_list = payload
            elif isinstance(payload, dict):
                raw_list = payload.get("artists") or payload.get("favorites") or payload.get("creators") or []
            else:
                raw_list = []
            items = [it for it in (raw_list or []) if isinstance(it, dict)]
            keys = {
                (str(it.get("service") or "").strip().lower(), str(it.get("id") or it.get("creator_id") or "").strip())
                for it in items
                if (it.get("service") and (it.get("id") or it.get("creator_id")))
            }
            self._set_cached_fav_keys(keys, auth_cookie)
            return items, False, ""
        except Exception as e:
            return None, False, str(e)

    def get_favorite_creator_keys(self, force_refresh: bool = False) -> Optional[Set[Tuple[str, str]]]:
        if not self.default_supports_favorites:
            return None

        def _load(cookie: str) -> Optional[Set[Tuple[str, str]]]:
            items, auth_req, _err = self._fetch_account_favorite_creators(cookie=cookie, timeout=12)
            if items is None:
                return None
            return {
                (str(it.get("service") or "").strip().lower(), str(it.get("id") or it.get("creator_id") or "").strip())
                for it in items
                if (it.get("service") and (it.get("id") or it.get("creator_id")))
            }

        return self._get_cached_fav_keys(_load, force_refresh=force_refresh)

    def set_creator_favorite(self, service: str, creator_id: str, favorite: bool) -> Dict[str, Any]:
        svc = (service or "").strip().lower()
        cid = str(creator_id or "").strip()
        if not self.default_supports_favorites:
            return super().set_creator_favorite(svc, cid, favorite)
        if not svc or not cid:
            return {"ok": False, "is_favorited": not bool(favorite), "auth_required": False, "error": "Invalid creator identifier."}
        cookie = self._current_auth_cookie()
        if not cookie:
            return {
                "ok": False,
                "is_favorited": not bool(favorite),
                "auth_required": True,
                "error": f"Log in to {self.display_name} to save favorite creators to your account.",
            }
        url = f"https://{self.base_domain}/api/v1/favorites/creator/{urllib.parse.quote(svc, safe='')}/{urllib.parse.quote(cid, safe='')}"
        method = "POST" if favorite else "DELETE"
        headers = {
            **self._request_headers(url),
            "Cookie": cookie,
            "Origin": f"https://{self.base_domain}",
            "Referer": self.build_creator_url(svc, cid),
            "Accept": "application/json, text/plain, */*",
        }
        try:
            resp = self._session.request(method, url, headers=headers, timeout=15)
            if resp.status_code in (401, 403):
                self.invalidate_favorite_cache()
                return {
                    "ok": False,
                    "is_favorited": not bool(favorite),
                    "auth_required": True,
                    "error": f"Session expired or unauthorized (HTTP {resp.status_code}). Please log in to {self.display_name}.",
                }
            if not resp.ok:
                return {
                    "ok": False,
                    "is_favorited": not bool(favorite),
                    "auth_required": False,
                    "error": f"HTTP {resp.status_code}",
                }
            self._update_cached_fav_key(svc, cid, bool(favorite), cookie=cookie)
            delta = 1 if favorite else -1
            try:
                with self._db_lock, self._conn() as conn:
                    conn.execute(
                        """
                        UPDATE catalog_creators
                        SET favorited = MAX(0, COALESCE(favorited, 0) + ?)
                        WHERE provider_id = ? AND service = ? AND creator_id = ?;
                        """,
                        (delta, self.provider_id, svc, cid),
                    )
            except Exception:
                pass
            return {"ok": True, "is_favorited": bool(favorite), "auth_required": False, "error": ""}
        except Exception as e:
            return {
                "ok": False,
                "is_favorited": not bool(favorite),
                "auth_required": False,
                "error": str(e),
            }

    def _list_favorite_creators(
        self,
        query: str = "",
        sort: str = "popular",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        raw_items, auth_req, err = self._fetch_account_favorite_creators(timeout=20)
        if auth_req:
            self.invalidate_favorite_cache()
            return BrowserPageResult(error=err, auth_required=True)
        if raw_items is None:
            return BrowserPageResult(error=err or f"Could not load favorited creators from {self.display_name}.")

        # Enrich missing fields from local catalog cache by primary key
        catalog_meta_by_key: Dict[Tuple[str, str], Tuple[str, int, int, int, int]] = {}
        try:
            with self._db_lock, self._conn() as conn:
                for it in raw_items:
                    svc = str(it.get("service") or "").strip().lower()
                    cid = str(it.get("id") or it.get("creator_id") or "").strip()
                    if not svc or not cid:
                        continue
                    row = conn.execute(
                        """
                        SELECT name, favorited, indexed, updated, COALESCE(ever_imported, 1)
                        FROM catalog_creators
                        WHERE provider_id = ? AND service = ? AND creator_id = ?;
                        """,
                        (self.provider_id, svc, cid),
                    ).fetchone()
                    if row:
                        catalog_meta_by_key[(svc, cid)] = row
        except Exception:
            pass

        clean_q = (query or "").strip().lower()
        enriched = []
        for it in raw_items:
            if cancel_event and cancel_event.is_set():
                break
            svc = str(it.get("service") or "").strip().lower()
            cid = str(it.get("id") or it.get("creator_id") or "").strip()
            if not svc or not cid:
                continue
            cached_row = catalog_meta_by_key.get((svc, cid))
            name = str(it.get("name") or (cached_row[0] if cached_row else "") or cid).strip()
            fav_cnt = int(it.get("favorited") if it.get("favorited") is not None else (cached_row[1] if cached_row else 0))
            idx_val = it.get("indexed") if it.get("indexed") is not None else (cached_row[2] if cached_row else 0)
            upd_val = it.get("updated") if it.get("updated") is not None else (cached_row[3] if cached_row else 0)
            if "ever_imported" in it:
                is_unimp = it.get("ever_imported") is False
            elif cached_row is not None:
                is_unimp = int(cached_row[4] if cached_row[4] is not None else 1) == 0
            else:
                is_unimp = False

            if clean_q and clean_q not in name.lower() and clean_q not in cid.lower() and clean_q not in svc:
                continue

            upd_ts, upd_str = self._parse_ts_sort_and_date(upd_val)
            idx_ts, _ = self._parse_ts_sort_and_date(idx_val)
            dto = build_creator_card_dto(
                provider_id=self.provider_id,
                service=svc,
                creator_id=cid,
                name=name,
                url=self.build_creator_url(svc, cid),
                avatar_url=self.resolve_avatar_url(svc, cid),
                banner_url=self.resolve_banner_url(svc, cid),
                favorited_count=fav_cnt,
                updated_at=upd_str,
                is_unimported=is_unimp,
                is_favorited=True,
            )
            enriched.append((fav_cnt, upd_ts, idx_ts, name.lower(), dto))

        if sort == "updated":
            enriched.sort(key=lambda r: (r[1], r[0]), reverse=True)
        elif sort == "indexed":
            enriched.sort(key=lambda r: (r[2], r[0]), reverse=True)
        elif sort == "name":
            enriched.sort(key=lambda r: r[3])
        else:
            enriched.sort(key=lambda r: (r[0], r[1]), reverse=True)

        total = len(enriched)
        start = max(0, int(offset or 0))
        end = start + max(1, int(limit or 50))
        items = [r[4] for r in enriched[start:end]]
        return BrowserPageResult(
            items=items,
            total=total,
            offset=start,
            page_size=limit,
            has_more=(start + len(items)) < total,
        )

    def list_creators(
        self,
        query: str = "",
        service: str = "all",
        tag: str = "",
        sort: str = "popular",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        clean_q = (query or "").strip().lower()
        clean_svc = (service or "all").strip().lower()
        if clean_svc == "favorites":
            return self._list_favorite_creators(
                query=clean_q, sort=sort, offset=offset, limit=limit, cancel_event=cancel_event
            )
        self.ensure_catalog_synced(force=False, cancel_event=cancel_event)

        where_clauses = ["provider_id = ?"]
        params: List[Any] = [self.provider_id]
        if clean_svc and clean_svc != "all":
            where_clauses.append("service = ?")
            params.append(clean_svc)
        if clean_q:
            where_clauses.append("(name_lower LIKE ? OR LOWER(creator_id) LIKE ?)")
            like_q = f"%{clean_q}%"
            params.extend([like_q, like_q])

        order_sql = "favorited DESC, updated DESC"
        if sort == "updated":
            order_sql = "updated DESC, favorited DESC"
        elif sort == "indexed":
            order_sql = "indexed DESC, favorited DESC"
        elif sort == "name":
            order_sql = "name_lower ASC"

        where_str = " AND ".join(where_clauses)
        try:
            with self._db_lock, self._conn() as conn:
                total_row = conn.execute(
                    f"SELECT COUNT(*) FROM catalog_creators WHERE {where_str};",
                    params,
                ).fetchone()
                total = int(total_row[0] or 0) if total_row else 0
                rows = conn.execute(
                    f"""
                    SELECT service, creator_id, name, favorited, indexed, updated, COALESCE(ever_imported, 1)
                    FROM catalog_creators
                    WHERE {where_str}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?;
                    """,
                    params + [int(limit), int(offset)],
                ).fetchall()

            fav_keys: Set[Tuple[str, str]] = set()
            if self.default_supports_favorites and self._current_auth_cookie():
                fav_keys = self.get_favorite_creator_keys() or set()

            items = []
            for svc, cid, name, fav, idx, upd, ever_imp in rows:
                _, upd_str = self._parse_ts_sort_and_date(upd)
                items.append(
                    build_creator_card_dto(
                        provider_id=self.provider_id,
                        service=svc,
                        creator_id=cid,
                        name=name,
                        url=self.build_creator_url(svc, cid),
                        avatar_url=self.resolve_avatar_url(svc, cid),
                        banner_url=self.resolve_banner_url(svc, cid),
                        favorited_count=int(fav or 0),
                        updated_at=upd_str,
                        is_unimported=(int(ever_imp if ever_imp is not None else 1) == 0),
                        is_favorited=((str(svc or "").strip().lower(), str(cid or "").strip()) in fav_keys),
                    )
                )
            return BrowserPageResult(
                items=items,
                total=total,
                offset=offset,
                page_size=limit,
                has_more=(offset + len(items)) < total,
            )
        except Exception as e:
            return BrowserPageResult(error=str(e))

    def _build_kemono_media_urls(
        self,
        fobj: Dict[str, Any],
        post_raw: Optional[Dict[str, Any]] = None,
    ) -> Optional[Tuple[str, str, str]]:
        return resolve_kemono_media_urls(fobj, base_domain=self.base_domain, post_raw=post_raw)

    def _parse_kemono_post(self, raw: Dict[str, Any], fallback_service: str = "", fallback_creator_id: str = "", fallback_creator_name: str = "") -> Dict[str, Any]:
        svc = str(raw.get("service") or fallback_service or "").strip().lower()
        cid = str(raw.get("user") or raw.get("creator_id") or fallback_creator_id or "").strip()
        pid = str(raw.get("id") or "").strip()
        title = html_lib.unescape(str(raw.get("title") or "").strip())
        content = html_to_readable_text(str(raw.get("content") or raw.get("substring") or ""))
        published = str(raw.get("published") or raw.get("added") or "")[:10]

        atts: List[Dict[str, Any]] = []
        seen_paths = set()

        def _norm_dedup(p_str: str) -> str:
            m = re.search(r"/(?:data|thumbnail/data)?/[0-9a-f]?([0-9a-f]{2}/[0-9a-f]{2}/[^\s?#]+)", p_str, re.IGNORECASE)
            return m.group(1).lower() if m else p_str.split("?")[0].lower()

        main_file = raw.get("file")
        if isinstance(main_file, dict):
            resolved = self._build_kemono_media_urls(main_file, raw)
            if resolved:
                fname, full_url, thumb_url = resolved
                seen_paths.add(_norm_dedup(str(main_file.get("path") or full_url)))
                atts.append(
                    build_media_attachment_dto(
                        name=fname,
                        url=full_url,
                        thumbnail_url=thumb_url,
                    )
                )
        for att in raw.get("attachments") or []:
            if not isinstance(att, dict):
                continue
            resolved = self._build_kemono_media_urls(att, raw)
            if not resolved:
                continue
            fname, full_url, thumb_url = resolved
            dedup_k = _norm_dedup(str(att.get("path") or full_url))
            if dedup_k in seen_paths:
                continue
            seen_paths.add(dedup_k)
            atts.append(
                build_media_attachment_dto(
                    name=fname,
                    url=full_url,
                    thumbnail_url=thumb_url,
                )
            )

        tags = FilterEngine.normalize_tags(raw.get("tags"))
        is_unimported = (raw.get("has_full") is False) or bool(raw.get("is_unimported"))
        return build_post_card_dto(
            provider_id=self.provider_id,
            service=svc,
            creator_id=cid,
            creator_name=fallback_creator_name or cid,
            post_id=pid,
            title=title,
            url=self.build_post_url(svc, cid, pid),
            published_at=published,
            content_snippet=content[:280],
            attachments=atts,
            tags=tags,
            is_unimported=is_unimported,
        )

    def list_creator_posts(
        self,
        service: str,
        creator_id: str,
        creator_name: str = "",
        query: str = "",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        params: Dict[str, Any] = {"o": int(offset)}
        if query and query.strip():
            params["q"] = query.strip()
        url = f"https://{self.base_domain}/api/v1/{service}/user/{creator_id}/posts"
        try:
            resp = self._session.get(url, params=params, headers=self._request_headers(url), timeout=20)
            if resp.status_code in (401, 403):
                return BrowserPageResult(error=f"Authentication required (HTTP {resp.status_code})", auth_required=True)
            if resp.status_code != 200:
                return BrowserPageResult(error=f"HTTP {resp.status_code}")
            payload = resp.json()
            raw_posts = payload if isinstance(payload, list) else (payload.get("posts") or payload.get("results") or [])
            items = [
                self._parse_kemono_post(p, service, creator_id, creator_name)
                for p in raw_posts
                if isinstance(p, dict)
            ]
            has_more = len(items) >= 50
            total = (offset + len(items) + (50 if has_more else 0))
            return BrowserPageResult(items=items, total=total, offset=offset, page_size=50, has_more=has_more)
        except Exception as e:
            return BrowserPageResult(error=str(e))

    def search_global_posts(
        self,
        query: str = "",
        service: str = "all",
        tag: str = "",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        params: Dict[str, Any] = {"o": int(offset)}
        if query and query.strip():
            params["q"] = query.strip()
        url = f"https://{self.base_domain}/api/v1/posts"
        try:
            resp = self._session.get(url, params=params, headers=self._request_headers(url), timeout=20)
            if resp.status_code != 200:
                return BrowserPageResult(error=f"HTTP {resp.status_code}")
            payload = resp.json()
            raw_posts = payload if isinstance(payload, list) else (payload.get("posts") or [])
            total = int(payload.get("count") or payload.get("true_count") or len(raw_posts)) if isinstance(payload, dict) else len(raw_posts)
            items = []
            for p in raw_posts:
                if not isinstance(p, dict):
                    continue
                if service and service != "all" and str(p.get("service", "")).lower() != service.lower():
                    continue
                items.append(self._parse_kemono_post(p))
            return BrowserPageResult(
                items=items,
                total=max(total, offset + len(items)),
                offset=offset,
                page_size=50,
                has_more=len(raw_posts) >= 50,
            )
        except Exception as e:
            return BrowserPageResult(error=str(e))

    def build_dms_url(self, service: str, creator_id: str) -> str:
        return f"https://{self.base_domain}/{service}/user/{creator_id}/dms"

    def build_dm_url(self, service: str, creator_id: str, dm_id: str) -> str:
        return f"https://{self.base_domain}/{service}/user/{creator_id}/dm/{dm_id}"

    @staticmethod
    def parse_dms_html_cards(
        html_text: str,
        base_domain: str,
        service: str,
        creator_id: str,
        current_offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], Optional[int], bool]:
        """Parses Kemono/Pawchive `<article class='dm-card'>` HTML into normalized raw DM records."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return [], None, False

        soup = BeautifulSoup(html_text or "", "html.parser")
        articles = soup.find_all("article", class_="dm-card")

        known_total: Optional[int] = None
        m_tot = re.search(r"DMs\s*\(([0-9,]+)\)", html_text or "")
        if m_tot:
            try:
                known_total = int(m_tot.group(1).replace(",", ""))
            except (ValueError, TypeError):
                pass

        has_next_page = False
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if (f"/user/{creator_id}/dms" in href or href.startswith(("?o=", "&o="))) and re.search(r"[?&]o=\d+", href):
                m_o = re.search(r"[?&]o=(\d+)", href)
                if m_o and int(m_o.group(1)) > current_offset:
                    has_next_page = True
                    break

        parsed_items: List[Dict[str, Any]] = []
        for art in articles:
            content_div = art.find(class_="dm-card__content")
            content_html = content_div.decode_contents().strip() if content_div else ""
            content_text = content_div.get_text(separator="\n", strip=True) if content_div else ""

            added_div = art.find(class_="dm-card__added")
            added_str = ""
            if added_div:
                m_dt = re.search(r"Added:\s*([0-9-]+)", added_div.get_text())
                if m_dt:
                    added_str = m_dt.group(1)

            attachments: List[Dict[str, Any]] = []
            seen_att = set()
            for img in art.find_all("img"):
                src = img.get("src")
                if src and not src.endswith("logo.png") and not src.endswith("favicon.png"):
                    fname = src.split("/")[-1].split("?")[0] or "image.jpg"
                    if src.startswith(("http://", "https://")):
                        img_path = src
                    elif src.startswith("//"):
                        img_path = f"https:{src}"
                    elif src.startswith("/"):
                        img_path = src
                    else:
                        img_path = f"/{src}"
                    if img_path not in seen_att:
                        seen_att.add(img_path)
                        attachments.append({"name": fname, "path": img_path, "originalFilename": fname})
            for a in art.find_all("a"):
                href = a.get("href")
                if href and any(ext in href.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".zip", ".rar", "/data/")):
                    fname = href.split("/")[-1].split("?")[0] or "file.bin"
                    if href.startswith(("http://", "https://")):
                        link_path = href
                    elif href.startswith("//"):
                        link_path = f"https:{href}"
                    elif href.startswith("/"):
                        link_path = href
                    else:
                        link_path = f"/{href}"
                    if link_path not in seen_att:
                        seen_att.add(link_path)
                        attachments.append({"name": fname, "path": link_path, "originalFilename": fname})

            dm_id = art.get("id") or art.get("data-id")
            if not dm_id:
                att_str = ",".join(a.get("path", "") for a in attachments)
                fingerprint = f"{service}:{creator_id}:{added_str}:{content_text}:{att_str}"
                dm_id = f"dm_{hashlib.sha256(fingerprint.encode('utf-8', errors='ignore')).hexdigest()[:16]}"

            first_line = content_text.split("\n")[0][:80].strip() if content_text else ""
            parsed_items.append({
                "id": str(dm_id),
                "user": str(creator_id),
                "service": str(service),
                "domain": base_domain,
                "is_dm": True,
                "is_dms": True,
                "title": first_line or "Direct Message",
                "captionText": content_text,
                "content": content_html,
                "published": added_str,
                "attachments": attachments,
            })

        return parsed_items, known_total, has_next_page

    def list_creator_dms(
        self,
        service: str,
        creator_id: str,
        creator_name: str = "",
        query: str = "",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        url = f"https://{self.base_domain}/{service}/user/{creator_id}/dms?o={max(0, int(offset or 0))}"
        clean_q = (query or "").strip().lower()
        try:
            resp = self._session.get(url, headers=self._request_headers(url), timeout=20)
            if resp.status_code in (401, 403):
                return BrowserPageResult(error=f"Authentication required (HTTP {resp.status_code})", auth_required=True)
            if resp.status_code == 404:
                return BrowserPageResult(items=[], total=0, offset=offset, page_size=50, has_more=False)
            if resp.status_code != 200:
                return BrowserPageResult(error=f"HTTP {resp.status_code}")

            raw_items, known_total, has_next = self.parse_dms_html_cards(
                resp.text or "",
                base_domain=self.base_domain,
                service=service,
                creator_id=creator_id,
                current_offset=max(0, int(offset or 0)),
            )
            dtos: List[Dict[str, Any]] = []
            for raw_dm in raw_items:
                if clean_q:
                    hay = f"{raw_dm.get('title', '')} {raw_dm.get('captionText', '')}".lower()
                    if clean_q not in hay:
                        continue
                dto = self._parse_kemono_post(raw_dm, service, creator_id, creator_name)
                dto["is_dm"] = True
                dto["key"] = f"{self.provider_id}:{service}:{creator_id}:dm:{raw_dm['id']}"
                dto["url"] = self.build_dm_url(service, creator_id, raw_dm["id"])
                dto["content_full"] = raw_dm.get("captionText") or html_to_readable_text(raw_dm.get("content") or "")
                dtos.append(dto)

            total = known_total if (known_total is not None and not clean_q) else (offset + len(dtos) + (50 if has_next else 0))
            return BrowserPageResult(
                items=dtos,
                total=max(total, offset + len(dtos)),
                offset=offset,
                page_size=50,
                has_more=has_next,
            )
        except Exception as e:
            return BrowserPageResult(error=str(e))

    def get_post_detail(
        self,
        service: str,
        creator_id: str,
        post_id: str,
        creator_name: str = "",
        cancel_event: Optional[threading.Event] = None,
        is_dm: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if is_dm:
            dm_url = f"https://{self.base_domain}/api/v1/{service}/user/{creator_id}/dm/{post_id}"
            try:
                resp = self._session.get(dm_url, headers=self._request_headers(dm_url), timeout=15)
                if resp.status_code == 200:
                    payload = resp.json()
                    dm_obj = payload.get("dm") if isinstance(payload, dict) and isinstance(payload.get("dm"), dict) else payload
                    if isinstance(dm_obj, dict):
                        dto = self._parse_kemono_post(dm_obj, service, creator_id, creator_name)
                        dto["is_dm"] = True
                        dto["url"] = self.build_dm_url(service, creator_id, post_id)
                        dto["content_full"] = html_to_readable_text(str(dm_obj.get("content") or dm_obj.get("captionHtml") or dm_obj.get("captionText") or ""))
                        return dto
            except Exception:
                pass
            return None
        url = f"https://{self.base_domain}/api/v1/{service}/user/{creator_id}/post/{post_id}"
        try:
            resp = self._session.get(url, headers=self._request_headers(url), timeout=20)
            if resp.status_code != 200:
                return None
            payload = resp.json()
            post_obj = payload.get("post") if isinstance(payload, dict) and isinstance(payload.get("post"), dict) else payload
            if not isinstance(post_obj, dict):
                return None
            dto = self._parse_kemono_post(post_obj, service, creator_id, creator_name)
            full_html = str(post_obj.get("content") or post_obj.get("substring") or "")
            dto["content_full"] = html_to_readable_text(full_html)
            return dto
        except Exception:
            return None
