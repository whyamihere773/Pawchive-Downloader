"""
CoomerFans.com Modular Browser Provider Adapter (`CoomerFansBrowserProvider`).

Wraps `services/coomerfans_client.py` (`CoomerFansClient`) under the standard
`BaseBrowserProvider` contract so CoomerFans participates in the Browser tab
with zero special-casing in QML.
"""

from __future__ import annotations

import html as html_lib
import re
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from core.browser_providers.base import (
    BaseBrowserProvider,
    BrowserPageResult,
    ProviderCapabilities,
    build_creator_card_dto,
    build_media_attachment_dto,
    build_post_card_dto,
)
from core.browser_providers.registry import register_browser_provider
from core.parser import KemonoURLParser
from core.providers import COOMERFANS, cookie_for_url
from core.text_utils import clean_text
from services.coomerfans_client import CoomerFansClient, DEFAULT_HEADERS


@register_browser_provider
class CoomerFansBrowserProvider(BaseBrowserProvider):
    provider_id = COOMERFANS
    display_name = "CoomerFans"
    base_domain = "coomerfans.com"
    order = 30

    def __init__(self):
        super().__init__()
        self._session.headers.update(DEFAULT_HEADERS)

    def _request_headers(self, url: str) -> Dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        cookie = cookie_for_url(url)
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_creator_search=True,
            supports_global_post_search=False,
            supports_creator_post_search=True,
            supports_tag_filter=False,
            supports_service_filter=True,
            requires_cookie_auth=False,
            page_size=30,
            services=(
                ("all", "All Services"),
                ("onlyfans", "OnlyFans"),
                ("fansly", "Fansly"),
                ("candfans", "CandFans"),
            ),
            sort_options=(
                ("popular", "Popular Models"),
                ("favorited", "Favorited Creators"),
            ),
            accent_color="#F472B6",
            badge_icon="🔥",
        )

    def _client(self) -> CoomerFansClient:
        cookie = cookie_for_url(f"https://{self.base_domain}/")
        client = CoomerFansClient(cookie=cookie)
        # Share session cookies (e.g. bg_trk) acquired during browsing
        client._session.cookies.update(self._session.cookies)
        return client

    @staticmethod
    def _split_creator_id(creator_id: str, fallback_slug: str = "") -> tuple[str, str]:
        raw = str(creator_id or "").strip()
        if "|" in raw:
            uid, slug = raw.split("|", 1)
            return uid.strip(), (slug.strip() or fallback_slug.strip() or uid.strip())
        if "/" in raw:
            parts = [p for p in raw.split("/") if p]
            if len(parts) >= 2:
                return parts[-2].strip(), parts[-1].strip()
        return raw, (fallback_slug.strip() or raw)

    def build_creator_url(self, service: str, creator_id: str) -> str:
        svc = (service or "onlyfans").strip().lower()
        if svc in ("all", "coomerfans", ""):
            svc = "onlyfans"
        uid, slug = self._split_creator_id(creator_id)
        if slug and slug != uid:
            return f"https://coomerfans.com/u/{svc}/{uid}/{slug}"
        return f"https://coomerfans.com/u/{svc}/{uid}"

    def build_post_url(self, service: str, creator_id: str, post_id: str) -> str:
        svc = (service or "onlyfans").strip().lower()
        if svc in ("all", "coomerfans", ""):
            svc = "onlyfans"
        uid, _ = self._split_creator_id(creator_id)
        return f"https://coomerfans.com/p/{post_id}/{uid}/{svc}"

    def list_creators(
        self,
        query: str = "",
        service: str = "all",
        tag: str = "",
        sort: str = "popular",
        offset: int = 0,
        limit: int = 30,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        page_sz = max(1, int(limit or 30))
        page = max(1, (int(offset or 0) // page_sz) + 1)
        clean_q = (query or "").strip()
        clean_svc = (service or "all").strip().lower()

        # If the user pasted a direct CoomerFans creator URL into search, resolve it immediately
        if "coomerfans.com/u/" in clean_q.lower():
            parsed = KemonoURLParser.parse(clean_q)
            if parsed.is_valid and parsed.user_id:
                slug = (parsed.extra_data or {}).get("username") or parsed.user_id
                svc = (parsed.service or "onlyfans").lower()
                comp_id = f"{parsed.user_id}|{slug}"
                dto = build_creator_card_dto(
                    provider_id=self.provider_id,
                    service=svc,
                    creator_id=comp_id,
                    name=slug,
                    url=self.build_creator_url(svc, comp_id),
                    avatar_url=f"https://coomerfans.com/istorage/{parsed.user_id}.jpg",
                )
                return BrowserPageResult(items=[dto], total=1, offset=0, page_size=page_sz, has_more=False)

        if clean_q:
            url = f"https://{self.base_domain}/?q={quote_plus(clean_q)}"
            if page > 1:
                url += f"&page={page}"
        elif sort == "favorited":
            url = f"https://{self.base_domain}/favorited"
            if page > 1:
                url += f"?page={page}"
        else:
            url = f"https://{self.base_domain}/"
            if page > 1:
                url += f"?page={page}"

        try:
            resp = self._session.get(url, headers=self._request_headers(url), timeout=20)
            if resp.status_code in (403, 503) or "Checking your browser" in (resp.text or "") or "Verifying you are human" in (resp.text or ""):
                return BrowserPageResult(
                    error="CoomerFans is temporarily requesting browser verification. Wait a moment and click Refresh, or import your browser cookies in Settings → Accounts.",
                    auth_required=True,
                )
            if resp.status_code != 200:
                return BrowserPageResult(error=f"HTTP {resp.status_code}")

            html = resp.text or ""

            # When CoomerFans finds 0 search matches it renders similar/random models below the banner
            if clean_q and (
                "nothing was found for your request" in html.lower()
                or re.search(r"<h2[^>]*>[^<]*\bTotal\s+0\b", html, re.IGNORECASE)
            ):
                return BrowserPageResult(items=[], total=0, offset=offset, page_size=page_sz, has_more=False)

            # Extract total models count from `<h2>Names of Models... Total 221113</h2>`
            total_m = re.search(r"Total\s+(\d+)", html, re.IGNORECASE)
            reported_total = int(total_m.group(1)) if total_m else 0

            # Match `/u/<service>/<user_id>/<slug>` inside `<div class="thumb">` cards
            card_pattern = re.compile(
                r'<div\s+class=["\']thumb["\']>\s*<a\s+href=["\'](?:https?://(?:www\.)?coomerfans\.com)?/u/([^/"\'?#\s]+)/([^/"\'?#\s]+)/([^/"\'?#\s>]+)["\'][^>]*>(.*?)</a>\s*(?:<a\s+class=["\']th-tag["\']>([^<]*)</a>)?',
                re.IGNORECASE | re.DOTALL,
            )

            seen = set()
            items: List[Dict[str, Any]] = []

            for m in card_pattern.finditer(html):
                svc = m.group(1).strip().lower()
                uid = m.group(2).strip()
                slug = m.group(3).strip()
                inner_html = m.group(4) or ""
                tag_svc = (m.group(5) or "").strip().lower()
                if tag_svc:
                    svc = tag_svc

                if clean_svc not in ("all", "") and svc != clean_svc:
                    continue

                comp_id = f"{uid}|{slug}"
                if comp_id in seen:
                    continue
                seen.add(comp_id)

                p_m = re.search(r"<p>([^<]+)</p>", inner_html, re.IGNORECASE)
                disp_name = clean_text(html_lib.unescape(p_m.group(1).strip())) if p_m else slug

                img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', inner_html, re.IGNORECASE)
                avatar_url = html_lib.unescape(img_m.group(1).strip()) if img_m else f"https://coomerfans.com/istorage/{uid}.jpg"
                if avatar_url.startswith("/"):
                    avatar_url = f"https://{self.base_domain}{avatar_url}"

                items.append(
                    build_creator_card_dto(
                        provider_id=self.provider_id,
                        service=svc,
                        creator_id=comp_id,
                        name=disp_name or slug,
                        url=self.build_creator_url(svc, comp_id),
                        avatar_url=avatar_url,
                    )
                )

            # Fallback link scan if HTML layout varies
            if not items:
                fallback_pattern = re.compile(
                    r'href=["\'](?:https?://(?:www\.)?coomerfans\.com)?/u/([^/"\'?#\s]+)/([^/"\'?#\s]+)/([^/"\'?#\s>]+)["\']',
                    re.IGNORECASE,
                )
                for m in fallback_pattern.finditer(html):
                    svc, uid, slug = m.group(1).strip().lower(), m.group(2).strip(), m.group(3).strip()
                    if clean_svc not in ("all", "") and svc != clean_svc:
                        continue
                    comp_id = f"{uid}|{slug}"
                    if comp_id in seen:
                        continue
                    seen.add(comp_id)
                    items.append(
                        build_creator_card_dto(
                            provider_id=self.provider_id,
                            service=svc,
                            creator_id=comp_id,
                            name=clean_text(slug),
                            url=self.build_creator_url(svc, comp_id),
                            avatar_url=f"https://coomerfans.com/istorage/{uid}.jpg",
                        )
                    )

            has_next = bool(re.search(r'<a[^>]+class=["\'][^"\']*next[^"\']*["\']', html, re.IGNORECASE)) or len(items) >= 20
            total = reported_total if (reported_total > 0 and clean_svc in ("all", "")) else (offset + len(items) + (page_sz if has_next else 0))

            return BrowserPageResult(
                items=items,
                total=max(total, offset + len(items)),
                offset=offset,
                page_size=page_sz,
                has_more=has_next,
            )
        except Exception as e:
            return BrowserPageResult(error=str(e))

    def list_creator_posts(
        self,
        service: str,
        creator_id: str,
        creator_name: str = "",
        query: str = "",
        offset: int = 0,
        limit: int = 20,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        svc = (service or "onlyfans").strip().lower()
        if svc in ("all", "coomerfans", ""):
            svc = "onlyfans"
        uid, slug = self._split_creator_id(creator_id, creator_name)
        page_sz = max(1, int(limit or 20))
        page = max(1, (int(offset or 0) // page_sz) + 1)
        clean_q = (query or "").strip().lower()

        try:
            creator_url = self.build_creator_url(svc, f"{uid}|{slug}")
            parsed = KemonoURLParser.parse(creator_url)
            client = self._client()
            raw_posts = client.fetch_user_posts(
                parsed=parsed,
                page_start=page,
                page_end=page,
                cancel_event=cancel_event,
            )
            items: List[Dict[str, Any]] = []
            for p in raw_posts or []:
                if not isinstance(p, dict):
                    continue
                pid = str(p.get("id") or "").strip()
                if not pid:
                    continue
                post_svc = str(p.get("service") or svc).strip().lower()
                title = str(p.get("title") or f"Post #{pid}").strip()
                content = str(p.get("content") or "").strip()
                if clean_q and clean_q not in title.lower() and clean_q not in content.lower():
                    continue

                thumb_url = str(p.get("thumbnail") or "").strip()
                atts: List[Dict[str, Any]] = []
                if isinstance(p.get("file"), dict) and p["file"].get("path"):
                    fpath = str(p["file"]["path"])
                    f_is_img = fpath.split("?", 1)[0].lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"))
                    atts.append(
                        build_media_attachment_dto(
                            name=str(p["file"].get("name") or "media"),
                            url=fpath,
                            thumbnail_url=thumb_url or (fpath if f_is_img else ""),
                        )
                    )
                for a in p.get("attachments") or []:
                    if isinstance(a, dict) and a.get("path"):
                        apath = str(a["path"])
                        a_is_img = apath.split("?", 1)[0].lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"))
                        atts.append(
                            build_media_attachment_dto(
                                name=str(a.get("name") or "media"),
                                url=apath,
                                thumbnail_url=apath if a_is_img else "",
                            )
                        )

                items.append(
                    build_post_card_dto(
                        provider_id=self.provider_id,
                        service=post_svc,
                        creator_id=f"{uid}|{slug}",
                        creator_name=creator_name or slug,
                        post_id=pid,
                        title=title,
                        url=self.build_post_url(post_svc, f"{uid}|{slug}", pid),
                        published_at=str(p.get("published") or "")[:10],
                        content_snippet=content[:260],
                        thumbnail_url=thumb_url,
                        attachments=atts,
                    )
                )

            has_more = len(raw_posts or []) >= 10
            return BrowserPageResult(
                items=items,
                total=offset + len(items) + (page_sz if has_more else 0),
                offset=offset,
                page_size=page_sz,
                has_more=has_more,
            )
        except Exception as e:
            err_msg = str(e)
            auth_req = "503" in err_msg or "403" in err_msg or "Checking your browser" in err_msg
            return BrowserPageResult(error=err_msg, auth_required=auth_req)

    def get_post_detail(
        self,
        service: str,
        creator_id: str,
        post_id: str,
        creator_name: str = "",
        cancel_event: Optional[threading.Event] = None,
    ) -> Optional[Dict[str, Any]]:
        svc = (service or "onlyfans").strip().lower()
        if svc in ("all", "coomerfans", ""):
            svc = "onlyfans"
        uid, slug = self._split_creator_id(creator_id, creator_name)
        pid = str(post_id or "").strip()
        if not uid or not pid:
            return None

        try:
            post_url = self.build_post_url(svc, f"{uid}|{slug}", pid)
            parsed = KemonoURLParser.parse(post_url)
            client = self._client()
            full_post = client.fetch_single_post(parsed)
            if not full_post or not isinstance(full_post, dict):
                return None

            atts: List[Dict[str, Any]] = []
            if isinstance(full_post.get("file"), dict) and full_post["file"].get("path"):
                fobj = full_post["file"]
                fpath = str(fobj["path"])
                mtype = "video" if "video" in str(fobj.get("mimeType") or "").lower() else "image"
                atts.append(
                    build_media_attachment_dto(
                        name=str(fobj.get("name") or "media"),
                        url=fpath,
                        thumbnail_url=fpath if mtype == "image" else "",
                        media_type=mtype,
                    )
                )
            for a in full_post.get("attachments") or []:
                if isinstance(a, dict) and a.get("path"):
                    apath = str(a["path"])
                    mtype = "video" if "video" in str(a.get("mimeType") or "").lower() else "image"
                    atts.append(
                        build_media_attachment_dto(
                            name=str(a.get("name") or "media"),
                            url=apath,
                            thumbnail_url=apath if mtype == "image" else "",
                            media_type=mtype,
                        )
                    )

            title = str(full_post.get("title") or f"Post #{pid}").strip()
            body = str(full_post.get("content") or "").strip()
            cname = str(full_post.get("creator_name") or creator_name or slug).strip()
            dto = build_post_card_dto(
                provider_id=self.provider_id,
                service=svc,
                creator_id=f"{uid}|{slug}",
                creator_name=cname,
                post_id=pid,
                title=title,
                url=post_url,
                published_at=str(full_post.get("published") or "")[:10],
                content_snippet=body[:260],
                attachments=atts,
            )
            dto["content_full"] = body
            return dto
        except Exception:
            return None
