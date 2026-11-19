"""
Kemono-Style Provider Post/DM Parsing, Global Search & Detail Mixin
Decomposed from core/browser_providers/base.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from core.browser_providers.dto import (
    BrowserPageResult,
    build_media_attachment_dto,
    build_post_card_dto,
    html_to_readable_text,
    resolve_kemono_media_urls,
)
from core.filter_engine import FilterEngine


class KemonoCatalogPostsMixin:
    """Post/DM parsing, creator post listing, global search, DMs HTML parser, and post detail."""

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
                        dto["key"] = f"{self.provider_id}:{service}:{creator_id}:dm:{post_id}"
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
