"""
Cum.st Modular Browser Provider Adapter (`CumstBrowserProvider`).

Uses cum.st's native server-side paginated REST API (`/api/v1/creators`, `/api/v1/posts`,
`/api/v1/tags`, `/api/v1/{service}/user/{id}/posts`) and WebP CDN avatars (`img.cum.st`).
"""

from __future__ import annotations

import os
import re
import time
import threading
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

from core.browser_providers.base import (
    BaseBrowserProvider,
    BrowserPageResult,
    ProviderCapabilities,
    build_creator_card_dto,
    build_media_attachment_dto,
    build_post_card_dto,
    html_to_readable_text,
)
from core.browser_providers.registry import register_browser_provider
from core.parser import canonical_site_url
from core.providers import CUMST


def _ext_from_mime(mime: str) -> str:
    m = (mime or "").lower()
    if "mp4" in m or "quicktime" in m:
        return ".mp4"
    if "webm" in m:
        return ".webm"
    if "png" in m:
        return ".png"
    if "webp" in m:
        return ".webp"
    if "gif" in m:
        return ".gif"
    if "jpeg" in m or "jpg" in m:
        return ".jpg"
    return ""


def resolve_cumst_media_dto(fobj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolves a cum.st file/media dict (`storageKey`, `variants`, `path`) into a normalized media DTO."""
    if not isinstance(fobj, dict):
        return None
    path = str(fobj.get("path") or fobj.get("url") or "").strip()
    skey = str(fobj.get("storageKey") or "").strip()
    variants = [v for v in (fobj.get("variants") or []) if isinstance(v, dict) and v.get("name")]
    mime_raw = str(fobj.get("mimeType") or fobj.get("mime") or "").strip().lower()
    chosen_bytes = int(fobj.get("bytes") or fobj.get("size") or fobj.get("fileSize") or 0)
    thumb = str(fobj.get("thumbnailUrl") or fobj.get("previewUrl") or fobj.get("poster") or "").strip()

    chosen_v = None
    thumb_v = None
    for v in variants:
        vn = str(v.get("name") or "").lower()
        if "original" in vn:
            chosen_v = v
        elif any(tok in vn for tok in ("thumb", "preview", "poster", "small")) and vn.endswith((".jpg", ".jpeg", ".png", ".webp")):
            thumb_v = v
    if chosen_v is None and variants:
        chosen_v = variants[0]

    if not path and skey:
        if chosen_v is not None:
            vname = str(chosen_v.get("name"))
            chosen_bytes = chosen_bytes or int(chosen_v.get("bytes") or chosen_v.get("size") or 0)
            path = f"https://cdn.cum.st/media/{skey}/{vname}"
        else:
            orig_name = str(
                fobj.get("originalFilename") or fobj.get("name") or fobj.get("filename") or ""
            ).strip()
            orig_ext = os.path.splitext(orig_name.split("?", 1)[0])[1].lower()
            if orig_ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".mov"):
                orig_ext = ""
            fallback_ext = _ext_from_mime(mime_raw) or orig_ext or ".jpg"
            path = f"https://cdn.cum.st/media/{skey}/original{fallback_ext}"
    elif path and not path.startswith("http"):
        path = f"https://cdn.cum.st/{path.lstrip('/')}"
    else:
        path = path.replace("e1.cum.st", "cdn.cum.st")

    if not thumb and thumb_v is not None and skey:
        thumb = f"https://cdn.cum.st/media/{skey}/{thumb_v['name']}"

    if not path:
        return None
    if not thumb and path.split("?", 1)[0].lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        thumb = path

    name = str(fobj.get("originalFilename") or fobj.get("name") or fobj.get("filename") or os.path.basename(path.split("?")[0]) or "media")
    kind = str(fobj.get("kind") or "").strip().lower()
    mtype = str(fobj.get("type") or fobj.get("mediaType") or mime_raw or "").lower()
    is_loop = (kind == "gif") or ("image/gif" in mime_raw)
    if "video" in mtype or kind == "video":
        mtype = "video"
    elif "audio" in mtype or kind == "audio":
        mtype = "audio"
    elif "image" in mtype or "photo" in mtype or kind in ("image", "gif"):
        mtype = "image"
    else:
        mtype = ""
    return build_media_attachment_dto(
        name=name,
        url=path,
        thumbnail_url=thumb,
        file_size=chosen_bytes,
        media_type=mtype,
        is_loop=is_loop,
    )


@register_browser_provider
class CumstBrowserProvider(BaseBrowserProvider):
    provider_id = CUMST
    display_name = "cum.st"
    base_domain = "cum.st"
    order = 10

    def __init__(self):
        super().__init__()
        self._cached_tags: List[Dict[str, Any]] = []
        self._tags_fetched_at: float = 0.0
        self._tags_lock = threading.Lock()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_creator_search=True,
            supports_global_post_search=True,
            supports_creator_post_search=True,
            supports_tag_filter=True,
            supports_service_filter=True,
            supports_dms=True,
            supports_favorites=True,
            requires_cookie_auth=False,
            page_size=50,
            services=(
                ("all", "All Services"),
                ("favorites", "⭐ Favorites"),
                ("onlyfans", "OnlyFans"),
                ("patreon", "Patreon"),
                ("fansly", "Fansly"),
            ),
            sort_options=(
                ("popular", "Popular"),
                ("updated", "Recently Updated"),
                ("indexed", "Newly Indexed"),
                ("name", "Name (A–Z)"),
            ),
            accent_color="#38BDF8",
            badge_icon="💦",
        )

    def build_creator_url(self, service: str, creator_id: str) -> str:
        return canonical_site_url("cum.st", service, creator_id)

    def build_post_url(self, service: str, creator_id: str, post_id: str) -> str:
        return canonical_site_url("cum.st", service, creator_id, "post", post_id)

    def build_dms_url(self, service: str, creator_id: str) -> str:
        return canonical_site_url("cum.st", service, creator_id, "dms")

    def build_dm_url(self, service: str, creator_id: str, dm_id: str) -> str:
        return canonical_site_url("cum.st", service, creator_id, "dm", dm_id)

    @staticmethod
    def _format_cumst_date(val: Any) -> str:
        if val is None or val == "":
            return ""
        if isinstance(val, (int, float)):
            ts = float(val)
            if ts > 1e12:
                ts /= 1000.0
            try:
                return time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
            except Exception:
                return ""
        s = str(val).strip()
        if s.isdigit() and 9 <= len(s) <= 13:
            ts = int(s)
            if ts > 1e12:
                ts //= 1000
            try:
                return time.strftime("%Y-%m-%d", time.gmtime(ts))
            except Exception:
                return ""
        return s[:10]

    @staticmethod
    def resolve_avatar_url(service: str, creator_id: str) -> str:
        return f"https://img.cum.st/creator/{service}/{creator_id}/avatar.webp"

    @staticmethod
    def resolve_banner_url(service: str, creator_id: str) -> str:
        return f"https://img.cum.st/creator/{service}/{creator_id}/header.webp"

    def _parse_cumst_creator(
        self,
        raw: Dict[str, Any],
        fav_keys: Optional[Set[Tuple[str, str]]] = None,
        force_favorited: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(raw, dict):
            return None
        cid = str(raw.get("id") or "").strip()
        svc = str(raw.get("service") or "").strip().lower()
        if not cid or not svc:
            return None
        disp = str(raw.get("displayName") or raw.get("name") or cid).strip()
        handle = str(raw.get("name") or "").strip()
        full_name = f"{disp} (@{handle})" if (handle and disp.lower() != handle.lower()) else disp
        upd = self._format_cumst_date(raw.get("contentUpdated") or raw.get("updated") or raw.get("indexed"))
        raw_tags = raw.get("creatorTags") or []
        tag_names = []
        for t in raw_tags:
            if isinstance(t, dict) and t.get("name"):
                tag_names.append(str(t["name"]))
            elif isinstance(t, str):
                tag_names.append(t)
        is_fav = bool(force_favorited or (fav_keys is not None and (svc, cid) in fav_keys))
        return build_creator_card_dto(
            provider_id=self.provider_id,
            service=svc,
            creator_id=cid,
            name=full_name,
            url=self.build_creator_url(svc, cid),
            avatar_url=self.resolve_avatar_url(svc, cid),
            banner_url=self.resolve_banner_url(svc, cid),
            post_count=int(raw.get("postCount") or 0),
            video_count=int(raw.get("videoCount") or 0),
            image_count=int(raw.get("imageCount") or 0),
            dm_count=int(raw.get("dmCount") or 0),
            favorited_count=int(raw.get("bookmarked") or raw.get("favorited") or 0),
            updated_at=upd,
            tags=tag_names[:8],
            is_favorited=is_fav,
        )

    def get_favorite_creator_keys(self, force_refresh: bool = False) -> Optional[Set[Tuple[str, str]]]:
        def _load(cookie: str) -> Optional[Set[Tuple[str, str]]]:
            url = f"https://{self.base_domain}/api/v1/bookmarks?keys=1"
            headers = {
                **self._request_headers(url),
                "Cookie": cookie,
                "Accept": "application/json, text/plain, */*",
            }
            try:
                resp = self._session.get(url, headers=headers, timeout=12)
                if resp.status_code != 200:
                    return None
                payload = resp.json()
                raw_keys = payload.get("keys") if isinstance(payload, dict) else []
                parsed: Set[Tuple[str, str]] = set()
                for entry in raw_keys or []:
                    s = str(entry or "").strip()
                    if ":" in s:
                        svc, cid = s.split(":", 1)
                        if svc.strip() and cid.strip():
                            parsed.add((svc.strip().lower(), cid.strip()))
                return parsed
            except Exception:
                return None

        return self._get_cached_fav_keys(_load, force_refresh=force_refresh)

    def set_creator_favorite(self, service: str, creator_id: str, favorite: bool) -> Dict[str, Any]:
        svc = (service or "").strip().lower()
        cid = str(creator_id or "").strip()
        if not svc or not cid:
            return {"ok": False, "is_favorited": not bool(favorite), "auth_required": False, "error": "Invalid creator identifier."}
        cookie = self._current_auth_cookie()
        if not cookie:
            return {
                "ok": False,
                "is_favorited": not bool(favorite),
                "auth_required": True,
                "error": "Log in to cum.st to save bookmarked creators to your account.",
            }
        url = f"https://{self.base_domain}/api/v1/{urllib.parse.quote(svc, safe='')}/user/{urllib.parse.quote(cid, safe='')}/bookmark"
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
                    "error": f"Session expired or unauthorized (HTTP {resp.status_code}). Please log in to cum.st.",
                }
            if not resp.ok:
                return {
                    "ok": False,
                    "is_favorited": not bool(favorite),
                    "auth_required": False,
                    "error": f"HTTP {resp.status_code}",
                }
            now_fav = bool(favorite)
            try:
                data = resp.json()
                if isinstance(data, dict) and "bookmarked" in data:
                    now_fav = bool(data["bookmarked"])
            except Exception:
                pass
            self._update_cached_fav_key(svc, cid, now_fav, cookie=cookie)
            return {"ok": True, "is_favorited": now_fav, "auth_required": False, "error": ""}
        except Exception as e:
            return {
                "ok": False,
                "is_favorited": not bool(favorite),
                "auth_required": False,
                "error": str(e),
            }

    def _list_favorite_creators_svelte_fallback(
        self, cookie: str, query: str, offset: int, page_limit: int
    ) -> BrowserPageResult:
        page_num = max(1, (max(0, int(offset or 0)) // page_limit) + 1)
        url = f"https://{self.base_domain}/account/bookmarks/creators/__data.json?page={page_num}"
        headers = {
            **self._request_headers(url),
            "Cookie": cookie,
            "Accept": "application/json, text/plain, */*",
        }
        try:
            resp = self._session.get(url, headers=headers, timeout=20)
            if resp.status_code in (401, 403):
                return BrowserPageResult(error="Authentication required. Please log in to cum.st.", auth_required=True)
            if resp.status_code != 200:
                return BrowserPageResult(error=f"HTTP {resp.status_code}")
            raw_json = resp.json()
            if isinstance(raw_json, dict) and raw_json.get("type") == "redirect":
                return BrowserPageResult(error="Log in to cum.st to view your favorited creators.", auth_required=True)
            from core.api_client import KemonoAPIClient
            parsed_raw, parsed_total = KemonoAPIClient._parse_cumst_bookmarks(raw_json, fav_type="artist")
            clean_q = (query or "").strip().lower()
            items = []
            for raw in parsed_raw:
                dto = self._parse_cumst_creator(raw, force_favorited=True)
                if not dto:
                    continue
                if clean_q and clean_q not in dto["name"].lower() and clean_q not in dto["creator_id"].lower():
                    continue
                items.append(dto)
            total = int(parsed_total) if parsed_total is not None else len(items)
            return BrowserPageResult(
                items=items,
                total=total,
                offset=offset,
                page_size=page_limit,
                has_more=(offset + len(items)) < total,
            )
        except Exception as e:
            return BrowserPageResult(error=str(e))

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
        clean_svc = (service or "all").strip().lower()
        is_favorites = clean_svc == "favorites"
        page_limit = min(50, max(1, int(limit or 50)))

        auth_cookie = self._current_auth_cookie()
        if is_favorites and not auth_cookie:
            return BrowserPageResult(
                error="Log in to cum.st to view your favorited creators.",
                auth_required=True,
            )

        params: Dict[str, Any] = {
            "o": max(0, int(offset or 0)),
            "n": page_limit,
        }
        if is_favorites:
            params["scope"] = "bookmarks"
        elif clean_svc and clean_svc != "all":
            params["service"] = clean_svc
        if query and query.strip():
            params["q"] = query.strip()
        if tag and tag.strip():
            params["tag"] = tag.strip().lstrip("#")
        if sort and sort.strip():
            params["sort"] = sort.strip().lower()

        url = f"https://{self.base_domain}/api/v1/creators"
        headers = self._request_headers(url)
        if auth_cookie:
            headers["Cookie"] = auth_cookie
        try:
            resp = self._session.get(url, params=params, headers=headers, timeout=20)
            if resp.status_code in (401, 403):
                self.invalidate_favorite_cache()
                return BrowserPageResult(error="Session expired or unauthorized. Please log in to cum.st.", auth_required=True)
            if is_favorites and resp.status_code in (400, 404):
                return self._list_favorite_creators_svelte_fallback(auth_cookie, query, offset, page_limit)
            if resp.status_code != 200:
                return BrowserPageResult(error=f"HTTP {resp.status_code}")

            payload = resp.json()
            raw_list = payload.get("creators") if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
            total = int(payload.get("total") or len(raw_list)) if isinstance(payload, dict) else len(raw_list)

            fav_keys: Optional[Set[Tuple[str, str]]] = None
            if not is_favorites and auth_cookie:
                fav_keys = self.get_favorite_creator_keys()

            items: List[Dict[str, Any]] = []
            for raw in raw_list or []:
                if cancel_event and cancel_event.is_set():
                    break
                dto = self._parse_cumst_creator(raw, fav_keys=fav_keys, force_favorited=is_favorites)
                if dto:
                    items.append(dto)

            return BrowserPageResult(
                items=items,
                total=total,
                offset=offset,
                page_size=page_limit,
                has_more=(offset + len(items)) < total,
            )
        except Exception as e:
            return BrowserPageResult(error=str(e))

    def _parse_cumst_post(
        self,
        raw: Dict[str, Any],
        fallback_service: str = "",
        fallback_creator_id: str = "",
        fallback_creator_name: str = "",
        is_dm: bool = False,
    ) -> Dict[str, Any]:
        svc = str(raw.get("service") or fallback_service or "").strip().lower()
        cid = str(raw.get("user") or raw.get("creatorId") or raw.get("creator_id") or fallback_creator_id or "").strip()
        cname = str(raw.get("creatorName") or raw.get("displayName") or fallback_creator_name or cid).strip()
        pid = str(raw.get("id") or raw.get("postId") or "").strip()
        raw_title = str(raw.get("title") or raw.get("captionText") or raw.get("contentText") or raw.get("caption") or "").strip()
        clean_body = html_to_readable_text(
            str(
                raw.get("content")
                or raw.get("captionHtml")
                or raw.get("contentText")
                or raw.get("captionText")
                or raw.get("caption")
                or raw.get("substring")
                or ""
            )
        )
        default_label = f"DM #{pid}" if is_dm else f"Post #{pid}"
        title = raw_title.splitlines()[0][:110] if raw_title else (clean_body.splitlines()[0][:110] if clean_body else default_label)
        published = self._format_cumst_date(raw.get("published") or raw.get("added") or raw.get("createdAt"))

        atts: List[Dict[str, Any]] = []
        seen_urls = set()

        def _add_file_obj(fobj: Dict[str, Any]):
            dto = resolve_cumst_media_dto(fobj)
            if not dto or dto["url"] in seen_urls:
                return
            seen_urls.add(dto["url"])
            atts.append(dto)

        if isinstance(raw.get("file"), dict):
            _add_file_obj(raw["file"])
        for a in raw.get("attachments") or raw.get("media") or []:
            if isinstance(a, dict):
                _add_file_obj(a)

        tags = raw.get("tags") or []

        return build_post_card_dto(
            provider_id=self.provider_id,
            service=svc,
            creator_id=cid,
            creator_name=cname,
            post_id=pid,
            title=title,
            url=self.build_dm_url(svc, cid, pid) if is_dm else self.build_post_url(svc, cid, pid),
            published_at=published,
            content_snippet=clean_body[:280],
            attachments=atts,
            tags=tags,
            is_dm=is_dm,
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
        page_limit = min(50, max(1, int(limit or 50)))
        params: Dict[str, Any] = {"o": max(0, int(offset or 0)), "n": page_limit}
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
            raw_posts = payload.get("posts") if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
            total = int(payload.get("total") or payload.get("count") or len(raw_posts)) if isinstance(payload, dict) else len(raw_posts)
            items = [
                self._parse_cumst_post(p, service, creator_id, creator_name)
                for p in (raw_posts or [])
                if isinstance(p, dict)
            ]
            has_more = (offset + len(items)) < total if total > len(items) else (len(items) >= page_limit)
            return BrowserPageResult(
                items=items,
                total=max(total, offset + len(items)),
                offset=offset,
                page_size=page_limit,
                has_more=has_more,
            )
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
        page_limit = min(50, max(1, int(limit or 50)))
        params: Dict[str, Any] = {"o": max(0, int(offset or 0)), "n": page_limit}
        if query and query.strip():
            params["q"] = query.strip()
        if service and service.strip().lower() not in ("all", "favorites"):
            params["service"] = service.strip().lower()
        if tag and tag.strip():
            params["tag"] = tag.strip().lstrip("#")

        url = f"https://{self.base_domain}/api/v1/posts"
        try:
            resp = self._session.get(url, params=params, headers=self._request_headers(url), timeout=20)
            if resp.status_code != 200:
                return BrowserPageResult(error=f"HTTP {resp.status_code}")
            payload = resp.json()
            raw_posts = payload.get("posts") if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
            total = int(payload.get("total") or payload.get("count") or len(raw_posts)) if isinstance(payload, dict) else len(raw_posts)
            items = [self._parse_cumst_post(p) for p in (raw_posts or []) if isinstance(p, dict)]
            has_more = (offset + len(items)) < total if total > len(items) else (len(items) >= page_limit)
            return BrowserPageResult(
                items=items,
                total=max(total, offset + len(items)),
                offset=offset,
                page_size=page_limit,
                has_more=has_more,
            )
        except Exception as e:
            return BrowserPageResult(error=str(e))

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
        page_limit = min(50, max(1, int(limit or 50)))
        params: Dict[str, Any] = {"o": max(0, int(offset or 0)), "n": page_limit}
        clean_q = (query or "").strip().lower()
        url = f"https://{self.base_domain}/api/v1/{service}/user/{creator_id}/dms"
        try:
            resp = self._session.get(url, params=params, headers=self._request_headers(url), timeout=20)
            if resp.status_code in (401, 403):
                return BrowserPageResult(error=f"Authentication required (HTTP {resp.status_code})", auth_required=True)
            if resp.status_code == 404:
                return BrowserPageResult(items=[], total=0, offset=offset, page_size=page_limit, has_more=False)
            if resp.status_code != 200:
                return BrowserPageResult(error=f"HTTP {resp.status_code}")

            payload = resp.json()
            raw_dms = payload.get("dms") if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
            total = int(payload.get("total") or payload.get("count") or len(raw_dms)) if isinstance(payload, dict) else len(raw_dms)
            items = []
            for d in raw_dms or []:
                if not isinstance(d, dict):
                    continue
                dto = self._parse_cumst_post(d, service, creator_id, creator_name, is_dm=True)
                if clean_q:
                    hay = f"{dto.get('title', '')} {dto.get('content_snippet', '')}".lower()
                    if clean_q not in hay:
                        continue
                items.append(dto)
            has_more = (offset + len(raw_dms)) < total if total > len(raw_dms) else (len(raw_dms) >= page_limit)
            return BrowserPageResult(
                items=items,
                total=len(items) if clean_q else max(total, offset + len(items)),
                offset=offset,
                page_size=page_limit,
                has_more=has_more,
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
        endpoints = ["dm", "post"] if is_dm else ["post", "dm"]
        for ep in endpoints:
            url = f"https://{self.base_domain}/api/v1/{service}/user/{creator_id}/{ep}/{post_id}"
            try:
                resp = self._session.get(url, headers=self._request_headers(url), timeout=20)
                if resp.status_code != 200:
                    continue
                payload = resp.json()
                post_obj = (
                    payload.get(ep)
                    if isinstance(payload, dict) and isinstance(payload.get(ep), dict)
                    else payload
                )
                if not isinstance(post_obj, dict):
                    continue
                used_dm = (ep == "dm") or is_dm
                dto = self._parse_cumst_post(post_obj, service, creator_id, creator_name, is_dm=used_dm)
                full_html = str(
                    post_obj.get("content")
                    or post_obj.get("captionHtml")
                    or post_obj.get("contentText")
                    or post_obj.get("captionText")
                    or post_obj.get("caption")
                    or ""
                )
                dto["content_full"] = html_to_readable_text(full_html)
                return dto
            except Exception:
                continue
        return None

    def list_tags(self, query: str = "", limit: int = 40) -> List[Dict[str, Any]]:
        now = time.time()
        with self._tags_lock:
            if not self._cached_tags or (now - self._tags_fetched_at) > 3600 * 6:
                try:
                    url = f"https://{self.base_domain}/api/v1/tags"
                    resp = self._session.get(url, headers=self._request_headers(url), timeout=12)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_tags = data.get("tags") if isinstance(data, dict) else (data if isinstance(data, list) else [])
                        parsed_tags = []
                        for t in raw_tags or []:
                            if isinstance(t, dict) and t.get("name"):
                                parsed_tags.append({
                                    "name": str(t["name"]),
                                    "count": int(t.get("count") or t.get("creatorCount") or 0),
                                })
                            elif isinstance(t, str):
                                parsed_tags.append({"name": t, "count": 0})
                        self._cached_tags = parsed_tags
                        self._tags_fetched_at = now
                except Exception:
                    pass
            tags_snapshot = list(self._cached_tags)

        clean_q = (query or "").strip().lower().lstrip("#")
        if clean_q:
            tags_snapshot = [t for t in tags_snapshot if clean_q in t["name"].lower()]
        return tags_snapshot[: max(1, int(limit or 40))]
