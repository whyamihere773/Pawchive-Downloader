"""
CoomerFans Client
Parses creator profiles, paginated post feeds, and individual post media from coomerfans.com.
Supports direct image and video extraction with signed expiration tokens.
"""

import html
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import unquote

import requests

from core.logger import logger
from core.text_utils import clean_text

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://coomerfans.com/",
}


class CoomerFansClient:
    """Client for querying coomerfans.com creator profiles and posts."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)

    def _fetch_html(self, url: str, timeout: Optional[int] = None) -> str:
        t = timeout or self.timeout
        for attempt in range(3):
            try:
                resp = self._session.get(url, timeout=t)
                if resp.status_code == 429:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if resp.status_code == 404:
                    return ""
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                if attempt == 2:
                    logger.debug(f"Failed to fetch {url} after 3 attempts: {e}", category="api")
                    return ""
                time.sleep(1.0 * (attempt + 1))
        return ""

    def fetch_creator_profile(self, parsed: Any) -> Dict[str, Any]:
        """
        Fetches creator profile metadata (name, service, id, avatar).
        Supports creator profile URLs, single post URLs, and discovers creator slugs.
        """
        service = str(getattr(parsed, "service", "") or "onlyfans").lower()
        user_id = str(getattr(parsed, "user_id", "") or "")
        post_id = str(getattr(parsed, "post_id", "") or "")
        slug = ""
        if hasattr(parsed, "extra_data") and isinstance(parsed.extra_data, dict):
            slug = parsed.extra_data.get("username", "")

        content = ""
        # 1. If username slug is known, fetch creator profile directly
        if slug:
            url = f"https://coomerfans.com/u/{service}/{user_id}/{slug}".rstrip("/")
            content = self._fetch_html(url)

        # 2. If it's a single post URL (or slug was missing/failed), fetch the post page to discover creator info
        if not content and post_id:
            post_url = f"https://coomerfans.com/p/{post_id}/{user_id}/{service}"
            post_content = self._fetch_html(post_url)
            if post_content:
                content = post_content
                # Discover slug from author link e.g. /u/onlyfans/322768/alienspxxxres
                slug_m = re.search(rf'/u/{service}/{user_id}/([^"/\s>]+)', post_content, re.IGNORECASE)
                if not slug_m:
                    slug_m = re.search(r'/u/[^/]+/[^/]+/([^"/\s>]+)', post_content, re.IGNORECASE)
                if slug_m:
                    slug = clean_text(slug_m.group(1).strip())
                    if hasattr(parsed, "extra_data") and isinstance(parsed.extra_data, dict):
                        parsed.extra_data["username"] = slug

        # 3. Fallback: try bare user URL if still no content
        if not content:
            url = f"https://coomerfans.com/u/{service}/{user_id}".rstrip("/")
            content = self._fetch_html(url)

        name = slug
        if content:
            name_m = re.search(r'<span class="model-name">([^<]+)</span>', content)
            alt_m = re.search(
                r'<img[^>]+src="[^"]*istorage/' + re.escape(user_id) + r'\.jpg"[^>]+alt="([^"]+)"',
                content
            )
            title_profile_m = re.search(r'<title>([^<]+)\s+posts</title>', content, re.IGNORECASE)
            title_post_m = re.search(r'<title>([^<]+?)\s*[/|-]', content)

            if name_m:
                name = clean_text(name_m.group(1).strip())
            elif alt_m:
                name = clean_text(alt_m.group(1).strip())
            elif title_profile_m:
                name = clean_text(title_profile_m.group(1).strip())
            elif title_post_m:
                name = clean_text(title_post_m.group(1).strip())

        if not name:
            name = f"{service}_{user_id}"

        profile_url = f"https://coomerfans.com/u/{service}/{user_id}/{slug}".rstrip("/") if slug else f"https://coomerfans.com/u/{service}/{user_id}"
        avatar_url = f"https://coomerfans.com/istorage/{user_id}.jpg"
        return {
            "id": user_id,
            "name": name,
            "service": service,
            "avatar": avatar_url,
            "url": profile_url,
        }

    def fetch_single_post(self, parsed: Any) -> Optional[Dict[str, Any]]:
        """
        Fetches a single post page and extracts all images, videos, title, and date.
        """
        service = str(getattr(parsed, "service", "") or "onlyfans").lower()
        user_id = str(getattr(parsed, "user_id", "") or "")
        post_id = str(getattr(parsed, "post_id", "") or "")
        if not post_id or not user_id:
            return None

        url = f"https://coomerfans.com/p/{post_id}/{user_id}/{service}"
        content = self._fetch_html(url)
        if not content:
            return None

        return self.parse_post_html(content, post_id=post_id, user_id=user_id, service=service)

    def parse_post_html(
        self, content: str, post_id: str, user_id: str, service: str
    ) -> Dict[str, Any]:
        """Parses the HTML of an individual post page into a normalized post dictionary."""
        title_m = re.search(r'<div class="post-wrap">\s*<h1>(.*?)</h1>', content, re.DOTALL)
        title = html.unescape(title_m.group(1).strip()) if title_m else f"Post {post_id}"

        date_m = re.search(r'<span class="post-date">(?:Added\s+)?(.*?)</span>', content)
        raw_date = html.unescape(date_m.group(1).strip()) if date_m else ""
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}:\d{2}))?', raw_date)
        if date_match:
            iso_date = f"{date_match.group(1)}T{date_match.group(2)}" if date_match.group(2) else date_match.group(1)
        else:
            iso_date = raw_date[:10] if raw_date else ""

        body_m = re.search(r'<div class="post-body">(.*?)</div>\s*</div>', content, re.DOTALL)
        media_items: List[Dict[str, Any]] = []

        if body_m:
            body = body_m.group(1)
            # 1. Images
            for img in re.findall(r'<img[^>]+src="([^"]+)"', body):
                clean_u = html.unescape(img).strip()
                if not clean_u:
                    continue
                path_part = clean_u.split("?")[0].split("#")[0].rstrip("/").rsplit("/", 1)[-1]
                fn = unquote(path_part)
                media_items.append(
                    {
                        "name": fn,
                        "path": clean_u,
                        "mimeType": "image/jpeg",
                        "is_temporary": False,
                    }
                )

            # 2. Videos (HTML5 video tags with expiration tokens)
            for vid in re.findall(r'<source[^>]+src="([^"]+)"', body):
                clean_u = html.unescape(vid).strip()
                if not clean_u:
                    continue
                path_part = clean_u.split("?")[0].split("#")[0].rstrip("/").rsplit("/", 1)[-1]
                fn = unquote(path_part)
                ext = os.path.splitext(fn)[1].lstrip(".").lower() or "mp4"
                media_items.append(
                    {
                        "name": fn,
                        "path": clean_u,
                        "mimeType": f"video/{ext}",
                        "is_temporary": True,  # Tells downloader to preserve signed query parameters
                    }
                )

        content_m = re.search(r'<div class="post-wrap">.*?<p>(.*?)</p>', content, re.DOTALL)
        post_content = html.unescape(content_m.group(1).strip()) if content_m else ""

        name_m = re.search(r'<span class="model-name">([^<]+)</span>', content)
        slug_m = re.search(rf'/u/{service}/{user_id}/([^"/\s>]+)', content, re.IGNORECASE)
        if not slug_m:
            slug_m = re.search(r'/u/[^/]+/[^/]+/([^"/\s>]+)', content, re.IGNORECASE)
        alt_m = re.search(
            r'<img[^>]+src="[^"]*istorage/' + re.escape(user_id) + r'\.jpg"[^>]+alt="([^"]+)"',
            content
        )
        title_post_m = re.search(r'<title>([^<]+?)\s*[/|-]', content)

        c_name = ""
        if name_m:
            c_name = clean_text(name_m.group(1).strip())
        elif alt_m:
            c_name = clean_text(alt_m.group(1).strip())
        elif title_post_m:
            c_name = clean_text(title_post_m.group(1).strip())

        slug = clean_text(slug_m.group(1).strip()) if slug_m else (c_name or "")

        primary_file = media_items[0] if media_items else None
        attachments = media_items[1:] if len(media_items) > 1 else []

        return {
            "id": str(post_id),
            "user": str(user_id),
            "username": slug or c_name,
            "creator_name": c_name or slug,
            "artist_name": c_name or slug,
            "service": str(service),
            "title": title,
            "content": post_content,
            "published": iso_date,
            "file": primary_file,
            "attachments": attachments,
            "tags": [],
            "_needs_coomerfans_media": False,
        }

    def fetch_user_posts(
        self,
        parsed: Any,
        page_start: int = 1,
        page_end: int = 999999,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[Callable] = None,
        date_after: str = "",
        date_before: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Paginates through a creator's posts, extracting title, post ID, thumbnail, and date.
        Post media can then be resolved either in batch or on-demand before downloading.
        """
        service = str(getattr(parsed, "service", "") or "onlyfans").lower()
        user_id = str(getattr(parsed, "user_id", "") or "")
        slug = ""
        if hasattr(parsed, "extra_data") and isinstance(parsed.extra_data, dict):
            slug = parsed.extra_data.get("username", "")

        all_posts: List[Dict[str, Any]] = []
        page = max(1, page_start)

        while page <= page_end:
            if cancel_event and cancel_event.is_set():
                logger.info("CoomerFans post scanning cancelled.", category="api")
                break

            url = f"https://coomerfans.com/u/{service}/{user_id}/{slug}".rstrip("/")
            if page > 1:
                url += f"?page={page}"

            if progress_callback:
                progress_callback(page, len(all_posts), None)

            content = self._fetch_html(url)
            if not content:
                break

            post_blocks = re.findall(
                r'<div class="post">\s*<h3><a href="/p/(\d+)/([^/]+)/([^"]+)">(.*?)</a></h3>(.*?)</div>\s*(?=<div class="post">|<div class="pagination|$)',
                content,
                re.DOTALL,
            )

            if not post_blocks:
                break

            early_stop_date = False
            for pid, uid, svc, raw_title, rest in post_blocks:
                if cancel_event and cancel_event.is_set():
                    break

                title = html.unescape(raw_title.strip())
                date_m = re.search(r'<span class="post-date">(.*?)</span>', rest)
                pub_date = html.unescape(date_m.group(1).strip()) if date_m else ""
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}:\d{2}))?', pub_date)
                if date_match:
                    iso_date = f"{date_match.group(1)}T{date_match.group(2)}" if date_match.group(2) else date_match.group(1)
                    short_date = date_match.group(1)
                else:
                    iso_date = pub_date[:10] if pub_date else ""
                    short_date = iso_date

                # Date Filtering
                if date_after and short_date and short_date < date_after:
                    early_stop_date = True
                    break
                if date_before and short_date and short_date > date_before:
                    continue

                thumb_m = re.search(
                    r'<div class="post-thumbs">\s*<figure>\s*<img[^>]+src="([^"]+)"', rest
                )
                thumb_url = html.unescape(thumb_m.group(1).strip()) if thumb_m else ""

                content_m = re.search(r'<p>(.*?)</p>', rest, re.DOTALL)
                post_text = html.unescape(content_m.group(1).strip()) if content_m else ""

                f_obj = None
                if thumb_url:
                    path_part = thumb_url.split("?")[0].rsplit("/", 1)[-1]
                    f_obj = {
                        "name": unquote(path_part),
                        "path": thumb_url,
                        "mimeType": "image/jpeg",
                        "is_temporary": False,
                    }

                all_posts.append(
                    {
                        "id": str(pid),
                        "user": str(uid),
                        "username": slug,
                        "creator_name": slug,
                        "artist_name": slug,
                        "service": str(svc).lower(),
                        "title": title or f"Post {pid}",
                        "content": post_text,
                        "published": iso_date,
                        "thumbnail": thumb_url,
                        "file": f_obj,
                        "attachments": [],
                        "tags": [],
                        "_needs_coomerfans_media": True,
                    }
                )

            if early_stop_date:
                logger.info(
                    f"CoomerFans: Passed cutoff date ({date_after}) on page {page} — stopping crawl.",
                    category="api",
                )
                break

            has_next = bool(re.search(r'<a class="next"\s+href="[^"]+">Next</a>', content, re.IGNORECASE))
            if not has_next:
                break

            page += 1

        if progress_callback:
            progress_callback(page, len(all_posts), len(all_posts))

        logger.info(
            f"CoomerFans: Discovered {len(all_posts)} posts for {service}/{user_id} across {page - page_start + 1} page(s).",
            category="api",
        )
        return all_posts

    def resolve_posts_media(
        self,
        posts: List[Dict[str, Any]],
        cancel_event: Optional[threading.Event] = None,
        max_workers: int = 10,
    ) -> None:
        """
        Resolves full media (images and videos) for posts that still have `_needs_coomerfans_media`.
        Runs requests in parallel using a thread pool.
        """
        unresolved = [p for p in posts if p.get("_needs_coomerfans_media")]
        if not unresolved:
            return

        logger.info(
            f"Resolving full media for {len(unresolved)} CoomerFans post(s) in parallel...",
            category="api",
        )

        def _resolve_one(post: Dict[str, Any]) -> None:
            if cancel_event and cancel_event.is_set():
                return
            pid = post.get("id")
            uid = post.get("user")
            svc = post.get("service")
            if not pid or not uid or not svc:
                return

            url = f"https://coomerfans.com/p/{pid}/{uid}/{svc}"
            content = self._fetch_html(url)
            if not content:
                post["_needs_coomerfans_media"] = False
                return

            full_data = self.parse_post_html(content, post_id=pid, user_id=uid, service=svc)
            if full_data:
                if full_data.get("file"):
                    post["file"] = full_data["file"]
                if full_data.get("attachments"):
                    post["attachments"] = full_data["attachments"]
                if full_data.get("title") and full_data["title"] != f"Post {pid}":
                    post["title"] = full_data["title"]
                if full_data.get("content"):
                    post["content"] = full_data["content"]
            post["_needs_coomerfans_media"] = False

        workers = min(max_workers, len(unresolved))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_resolve_one, p) for p in unresolved]
            for fut in as_completed(futures):
                if cancel_event and cancel_event.is_set():
                    break
                try:
                    fut.result()
                except Exception as ex:
                    logger.debug(f"Error resolving post media: {ex}", category="api")


# Singleton instance and module-level helpers
_coomerfans_client = CoomerFansClient()


def fetch_creator_profile(parsed: Any) -> Dict[str, Any]:
    return _coomerfans_client.fetch_creator_profile(parsed)


def fetch_single_post(parsed: Any) -> Optional[Dict[str, Any]]:
    return _coomerfans_client.fetch_single_post(parsed)


def fetch_user_posts(
    parsed: Any,
    page_start: int = 1,
    page_end: int = 999999,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable] = None,
    date_after: str = "",
    date_before: str = "",
) -> List[Dict[str, Any]]:
    return _coomerfans_client.fetch_user_posts(
        parsed=parsed,
        page_start=page_start,
        page_end=page_end,
        cancel_event=cancel_event,
        progress_callback=progress_callback,
        date_after=date_after,
        date_before=date_before,
    )


def resolve_posts_media(
    posts: List[Dict[str, Any]],
    cancel_event: Optional[threading.Event] = None,
    max_workers: int = 10,
) -> None:
    return _coomerfans_client.resolve_posts_media(
        posts=posts, cancel_event=cancel_event, max_workers=max_workers
    )
