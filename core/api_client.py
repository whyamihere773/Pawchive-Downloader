"""
API Client & Network Engine
Handles communication with Kemono, Pawchive, Coomer, and Cum.st REST endpoints
with exponential backoff, rate limiting recovery, and diagnostic logging.
"""

import os
import sys
import time
import requests
from urllib.parse import urljoin
from typing import Dict, Any, List, Optional, Callable
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger
from core.parser import URLParseResult

HTTP_STATUS_HINTS = {
    400: "Bad Request — malformed URL or invalid query parameters",
    401: "Unauthorized — session expired or invalid cookie",
    403: "Forbidden — content locked (Cloudflare block might help to use cookies)",
    404: "Not Found — creator or post does not exist on this server",
    408: "Request Timeout — server closed idle connection",
    410: "Gone — resource was permanently removed",
    416: "Range Not Satisfiable — byte range exceeds file size (already complete)",
    429: "Rate Limited — too many requests (429 backoff active)",
    451: "Unavailable For Legal Reasons — DMCA or regional restriction",
    500: "Internal Server Error — server-side crash or backend issue",
    502: "Bad Gateway — upstream server temporarily unreachable",
    503: "Service Unavailable — server overloaded or undergoing maintenance",
    504: "Gateway Timeout — upstream proxy timed out",
    520: "Web Server Returned Unknown Error (Cloudflare 520)",
    521: "Web Server Is Down (Cloudflare 521)",
    522: "Connection Timed Out (Cloudflare 522)",
    523: "Origin Is Unreachable (Cloudflare 523)",
    524: "A Timeout Occurred (Cloudflare 524)",
    525: "SSL Handshake Failed (Cloudflare 525)",
    526: "Invalid SSL Certificate (Cloudflare 526)",
    530: "Cloudflare DNS / Origin Error (Cloudflare 530)",
}


class KemonoApiClient:
    """
    HTTP REST Client for Kemono / Pawchive / Coomer APIs.
    Features: automatic retries with exponential backoff, rate-limiting,
    Cloudflare-aware headers, cookie injection, and rich diagnostic logging.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 KemonoSuite/2.0"
    )

    def __init__(self, cookie_string: str = "", custom_user_agent: str = "", proxy_url: str = ""):
        self.session = requests.Session()
        self.cookie_string = cookie_string
        self.user_agent = custom_user_agent or self.DEFAULT_USER_AGENT
        self.proxy_url = proxy_url.strip()
        self._request_count = 0
        self._total_bytes_received = 0

        # Retry strategy: 4 retries, 1.5× exponential backoff on 429/5xx
        retry_strategy = Retry(
            total=4,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._update_headers()
        self._update_proxies()

        logger.debug("API client initialized (UA: Chromium/124, retries: 4×1.5s backoff)", category="api")

    def set_proxy(self, proxy_url: str):
        self.proxy_url = proxy_url.strip()
        self._update_proxies()
        if self.proxy_url:
            logger.info(f"Proxy configured: {self.proxy_url}", category="api")

    def _update_proxies(self):
        if self.proxy_url:
            self.session.proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url
            }
        else:
            self.session.proxies = {}

    def set_cookie(self, cookie_string: str):
        self.cookie_string = cookie_string.strip()
        self._update_headers()
        if cookie_string:
            logger.info("Session cookie loaded into HTTP client.", category="api")

    def set_user_agent(self, user_agent: str):
        self.user_agent = user_agent.strip() or self.DEFAULT_USER_AGENT
        self._update_headers()
        logger.debug(f"User-Agent updated: {self.user_agent[:60]}", category="api")

    def _update_headers(self):
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://pawchive.pw/",
        }
        if self.cookie_string:
            headers["Cookie"] = self.cookie_string
        self.session.headers.update(headers)

    def _get_with_log(self, url: str, timeout: int = 20, extra_headers: dict = None) -> Optional[requests.Response]:
        """
        Performs a GET request with full logging of status, latency, and errors.
        Returns the Response on HTTP 200/206/416, None on failure.
        """
        self._request_count += 1
        req_headers = {}
        if extra_headers:
            req_headers.update(extra_headers)

        t0 = time.time()
        try:
            resp = self.session.get(url, timeout=timeout, headers=req_headers, stream=False)
            elapsed = (time.time() - t0) * 1000  # ms
            status = resp.status_code

            # Log response line
            hint = HTTP_STATUS_HINTS.get(status, "")
            content_len = int(resp.headers.get("content-length", 0))
            content_type = resp.headers.get("content-type", "?")[:40]

            if status in (200, 206):
                logger.debug(
                    f"HTTP {status}  {elapsed:6.0f}ms  {content_len//1024:>5}KB  "
                    f"{content_type}  ← {url}",
                    category="http"
                )
            elif status == 416:
                logger.debug(f"HTTP 416 (Already complete)  ← {url}", category="http")
            elif status == 403:
                logger.warning(
                    f"HTTP 403 Forbidden — {hint}. Add a session cookie in Settings.",
                    category="http"
                )
            elif status == 429:
                retry_after = resp.headers.get("Retry-After", "?")
                logger.warning(
                    f"HTTP 429 Rate-limited (Retry-After: {retry_after}s) — backing off…",
                    category="http"
                )
            else:
                logger.warning(
                    f"HTTP {status}  {elapsed:6.0f}ms  {hint or 'Unexpected status'}  ← {url}",
                    category="http"
                )

            return resp

        except requests.exceptions.SSLError as e:
            logger.error(f"SSL error connecting to server: {e}", category="http")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection failed (server unreachable?): {e}", category="http")
        except requests.exceptions.Timeout:
            elapsed = (time.time() - t0) * 1000
            logger.error(f"Request timed out after {elapsed:.0f}ms — {url}", category="http")
        except Exception as e:
            logger.error(f"Unexpected HTTP error: {type(e).__name__}: {e}", category="http")

        return None

    # ── API Methods ───────────────────────────────────────────────────────────

    def fetch_creator_profile(self, parsed: URLParseResult) -> Dict[str, Any]:
        """Fetch creator profile, trying profile endpoints, cross-domain mirrors, and first post fallback."""
        logger.info(f"Fetching creator profile: {parsed.service}/{parsed.user_id}", category="api")

        candidate_urls = [
            f"https://{parsed.domain}/api/v1/{parsed.service}/user/{parsed.user_id}/profile",
            f"https://{parsed.domain}/api/v1/{parsed.service}/user/{parsed.user_id}",
        ]

        # Cross-mirror fallbacks for Kemono / Pawchive / Coomer network
        for alt_domain in ("pawchive.pw", "kemono.su", "coomer.su", "cum.st"):
            if alt_domain != parsed.domain:
                candidate_urls.append(f"https://{alt_domain}/api/v1/{parsed.service}/user/{parsed.user_id}/profile")
                candidate_urls.append(f"https://{alt_domain}/api/v1/{parsed.service}/user/{parsed.user_id}")

        for url in candidate_urls:
            resp = self._get_with_log(url, timeout=10)
            if resp is None:
                continue
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict):
                        name = data.get("displayName") or data.get("name") or data.get("user") or data.get("username")
                        if name and name != parsed.user_id:
                            logger.success(f"Creator: {name!r}  service={parsed.service}  id={parsed.user_id}", category="api")
                            return data
                    elif isinstance(data, list) and data:
                        first_item = data[0]
                        if isinstance(first_item, dict):
                            name = first_item.get("user") or first_item.get("username") or first_item.get("name")
                            if name:
                                logger.success(f"Creator: {name!r}  service={parsed.service}  id={parsed.user_id}", category="api")
                                return {"id": parsed.user_id, "name": name, "service": parsed.service}
                except Exception as e:
                    logger.debug(f"Failed to parse profile JSON: {e}", category="api")

        # Fallback: Query first post to extract creator name from post author metadata
        try:
            posts_url = f"https://{parsed.domain}/api/v1/{parsed.service}/user/{parsed.user_id}?o=0"
            resp = self._get_with_log(posts_url, timeout=10)
            if resp and resp.status_code == 200:
                posts_data = resp.json()
                items = posts_data.get("posts", []) if isinstance(posts_data, dict) else (posts_data if isinstance(posts_data, list) else [])
                if items and isinstance(items[0], dict):
                    name = items[0].get("user") or items[0].get("username")
                    if name:
                        logger.success(f"Creator: {name!r} (from post metadata)  service={parsed.service}", category="api")
                        return {"id": parsed.user_id, "name": name, "service": parsed.service}
        except Exception:
            pass

        logger.warning(f"Could not retrieve profile for {parsed.user_id}; using ID as name.", category="api")
        return {"id": parsed.user_id, "name": parsed.user_id, "service": parsed.service}

    def fetch_single_post(self, parsed: URLParseResult) -> Optional[Dict[str, Any]]:
        """Fetch a single post (or DM) by ID."""
        if not parsed.post_id:
            return None

        # Check if URL was a DM or Post
        endpoint_type = "dm" if "/dm/" in parsed.raw_url.lower() else "post"
        url = f"https://{parsed.domain}/api/v1/{parsed.service}/user/{parsed.user_id}/{endpoint_type}/{parsed.post_id}"
        logger.info(f"Fetching single {endpoint_type}: {parsed.post_id}", category="api")

        resp = self._get_with_log(url, timeout=15)
        if resp is None or resp.status_code != 200:
            return None

        try:
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0]
            if isinstance(data, dict):
                if "post" in data and isinstance(data["post"], dict):
                    return data["post"]
                if "dm" in data and isinstance(data["dm"], dict):
                    return data["dm"]
                return data
        except Exception as e:
            logger.error(f"Failed to parse post/dm JSON: {e}", category="api")
        return None

    def fetch_post_comments(self, domain: str, service: str, user_id: str, post_id: str) -> List[Dict[str, Any]]:
        """
        Fetches all comments for a post from /api/v1/{service}/user/{user_id}/post/{post_id}/comments
        """
        url = f"https://{domain}/api/v1/{service}/user/{user_id}/post/{post_id}/comments"
        resp = self._get_with_log(url, timeout=15)
        if resp is None or resp.status_code != 200:
            return []

        try:
            comments = resp.json()
            if isinstance(comments, list):
                return comments
            if isinstance(comments, dict) and "comments" in comments:
                return comments["comments"]
        except Exception as e:
            logger.debug(f"Failed to parse comments JSON for post {post_id}: {e}", category="api")
        return []

    def fetch_user_posts(
        self,
        parsed: URLParseResult,
        page_start: int = 1,
        page_end: int = 999999,
        page_size: int = 50,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> List[Dict[str, Any]]:
        """
        Paginates through user posts from page_start to page_end.
        Emits detailed per-page console logs including post counts, offsets, and timing.
        """
        all_posts: List[Dict[str, Any]] = []
        current_page = page_start
        offset = (page_start - 1) * page_size
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 3

        logger.info(
            f"Post enumeration started — {parsed.service}/{parsed.user_id}  "
            f"pages {page_start}–{page_end}  (page size: {page_size})",
            category="api"
        )

        while current_page <= page_end:
            if cancel_event and cancel_event.is_set():
                logger.warning("Post enumeration cancelled by user.", category="api")
                break

            if parsed.domain == "cum.st":
                url = (
                    f"https://cum.st/api/v1/{parsed.service}"
                    f"/user/{parsed.user_id}/posts?o={offset}&n={page_size}"
                )
            else:
                url = (
                    f"https://{parsed.domain}/api/v1/{parsed.service}"
                    f"/user/{parsed.user_id}?o={offset}"
                )

            if progress_callback:
                progress_callback(current_page, len(all_posts))

            resp = self._get_with_log(url, timeout=25)

            if cancel_event and cancel_event.is_set():
                logger.warning("Post enumeration cancelled by user.", category="api")
                break

            if resp is None:
                consecutive_errors += 1
                logger.warning(
                    f"Page {current_page} request failed "
                    f"({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS} consecutive errors)",
                    category="api"
                )
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        f"Stopping enumeration after {MAX_CONSECUTIVE_ERRORS} consecutive failures.",
                        category="api"
                    )
                    break
                time.sleep(2.0)
                continue

            consecutive_errors = 0  # reset on success

            if resp.status_code == 429:
                wait_sec = int(resp.headers.get("Retry-After", 5))
                logger.warning(f"Page {current_page}: Rate limited (429). Pausing {wait_sec}s before retry...", category="api")
                time.sleep(wait_sec)
                continue

            if resp.status_code == 403:
                logger.error(
                    "403 Forbidden — posts are paywalled or cookie is missing/expired. "
                    "Add your session cookie in Settings → Network.",
                    category="api"
                )
                break

            if resp.status_code != 200:
                logger.warning(f"Page {current_page}: unexpected HTTP {resp.status_code}, stopping.", category="api")
                break

            try:
                raw_data = resp.json()
            except Exception as e:
                logger.error(f"Page {current_page}: JSON parse error — {e}", category="api")
                break

            # Handle both list responses and dict responses (cum.st returns {"total": N, "posts": [...]})
            if isinstance(raw_data, dict):
                posts = raw_data.get("posts") or raw_data.get("dms") or []
            elif isinstance(raw_data, list):
                posts = raw_data
            else:
                posts = []

            if not isinstance(posts, list) or len(posts) == 0:
                logger.info(
                    f"Page {current_page} returned 0 posts — enumeration complete at offset {offset}.",
                    category="api"
                )
                break

            batch = len(posts)
            all_posts.extend(posts)
            logger.info(
                f"Page {current_page:3d}  offset {offset:5d}  +{batch} posts  "
                f"(running total: {len(all_posts)})",
                category="api"
            )

            if batch < page_size:
                logger.info(f"Partial page ({batch}<{page_size}) — reached last page.", category="api")
                break

            offset += batch
            current_page += 1
            time.sleep(0.15)  # polite throttle

        logger.success(
            f"Enumeration done: {len(all_posts)} posts collected "
            f"across {current_page - page_start + 1} page(s).",
            category="api"
        )
        return all_posts
