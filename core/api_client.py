"""
API Client & Network Engine
Handles communication with Kemono, Pawchive, Coomer, and Cum.st REST endpoints
with exponential backoff, rate limiting recovery, and diagnostic logging.
"""

import os
import sys
import time
import random
import threading
import requests
import re
from urllib.parse import unquote
from typing import Dict, Any, List, Optional, Callable
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger
from core.parser import URLParseResult
from core.text_utils import clean_text
from core.providers import cookie_for_url, is_disabled, disabled_message, provider_for_host

# Only advertise Brotli when it can actually be decoded: Pawchive answers with Brotli when asked,
# and without the brotli package requests hands back undecodable bytes (every API call failed).
try:
    import brotli  # noqa: F401
    _ACCEPT_ENCODING = "gzip, deflate, br"
except ImportError:
    try:
        import brotlicffi  # noqa: F401
        _ACCEPT_ENCODING = "gzip, deflate, br"
    except ImportError:
        _ACCEPT_ENCODING = "gzip, deflate"

# Services that live on Coomer / cum.st rather than Kemono / Pawchive
_COOMER_FAMILY_SERVICES = {"onlyfans", "fansly", "candfans"}


def _retry_after_seconds(value, default: float = 5.0, cap: float = 120.0) -> float:
    """Retry-After is either a number of seconds or an HTTP date."""
    if value is None:
        return default
    try:
        return max(0.0, min(cap, float(str(value).strip())))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        import datetime as _dt
        when = parsedate_to_datetime(str(value))
        if when.tzinfo is None:
            when = when.replace(tzinfo=_dt.timezone.utc)
        return max(0.0, min(cap, (when - _dt.datetime.now(_dt.timezone.utc)).total_seconds()))
    except Exception:
        return default

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

        # Retry strategy: 4 retries, 1.5× exponential backoff on 429/5xx, at most 8 s per wait.
        # The server's Retry-After isn't followed here: these waits can't be interrupted, and a
        # "Retry-After: 60" made Cancel hang for up to 4 minutes. The post scan handles 429 itself,
        # with waits that stop as soon as you cancel.
        retry_strategy = Retry(
            total=4,
            backoff_factor=1.5,
            backoff_max=8,
            respect_retry_after_header=False,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        # Name / profile lookups try several URLs; retrying each with backoff took minutes in outages
        self._quick_session = requests.Session()
        quick_adapter = HTTPAdapter(max_retries=0)
        self._quick_session.mount("https://", quick_adapter)
        self._quick_session.mount("http://", quick_adapter)
        self._update_headers()
        self._update_proxies()

        logger.debug("API client initialized (UA: Chromium/124, retries: 4×1.5s backoff)", category="api")

    def set_proxy(self, proxy_url: str):
        self.proxy_url = proxy_url.strip()
        self._update_proxies()
        if self.proxy_url:
            logger.info(f"Proxy configured: {self.proxy_url}", category="api")

    def _update_proxies(self):
        proxies = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else {}
        self.session.proxies = dict(proxies)
        if hasattr(self, "_quick_session"):
            self._quick_session.proxies = dict(proxies)

    def set_cookie(self, cookie_string: str):
        """The general cookie from Settings. It's attached per request, only to the archive sites."""
        changed = cookie_string.strip() != self.cookie_string
        self.cookie_string = cookie_string.strip()
        self._update_headers()
        if cookie_string and changed:
            logger.debug("Session cookie updated.", category="api")

    def set_user_agent(self, user_agent: str):
        self.user_agent = user_agent.strip() or self.DEFAULT_USER_AGENT
        self._update_headers()
        logger.debug(f"User-Agent updated: {self.user_agent[:60]}", category="api")

    def _update_headers(self):
        # No Cookie here: cookies are added per request for the site they belong to (_get_with_log)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": _ACCEPT_ENCODING,
            "Connection": "keep-alive",
            "X-Contact": "https://github.com/whyamihere773/Pawchive-Downloader",
            "X-Client-Notice": (
                "Pawchive Downloader user here! Love your site. If my client is ever causing server strain, "
                "please open an issue on GitHub instead of a hard ban and I'll fix my request pacing immediately."
            ),
        }
        for sess in (self.session, getattr(self, "_quick_session", None)):
            if sess is None:
                continue
            sess.headers.pop("Cookie", None)
            sess.headers.update(headers)

    @staticmethod
    def is_kemono_family(domain_or_url: str) -> bool:
        """Kemono / Coomer run the same software (new API path rules and the text/css header)."""
        d = (domain_or_url or "").lower()
        return "kemono." in d or "coomer." in d

    @classmethod
    def posts_list_url(cls, domain: str, service: str, user_id: str, offset: int) -> str:
        """A creator's post list. Kemono / Coomer moved it to /posts (the old path answers 404)."""
        if cls.is_kemono_family(domain):
            return f"https://{domain}/api/v1/{service}/user/{user_id}/posts?o={offset}"
        return f"https://{domain}/api/v1/{service}/user/{user_id}?o={offset}"

    def _get_with_log(self, url: str, timeout: int = 20, extra_headers: dict = None,
                      quick: bool = False) -> Optional[requests.Response]:
        """
        Performs a GET request with full logging of status, latency, and errors.
        Returns the Response for any HTTP status, or None when there was no answer (or the site is
        switched off). quick=True skips the automatic retries (for lookups that try several URLs).
        """
        host = url.split("://")[-1].split("/")[0]
        if is_disabled(host):
            logger.debug(f"Skipped {host}: {disabled_message(host)}", category="http")
            return None
        self._request_count += 1
        req_headers = {"Referer": f"https://{host}/"} if provider_for_host(host) else {}
        cookie = cookie_for_url(url, self.cookie_string)
        if cookie:
            req_headers["Cookie"] = cookie
        # Kemono / Coomer refuse API calls (HTTP 403) unless they ask for "text/css"
        if "/api/" in url and self.is_kemono_family(url.split("://")[-1].split("/")[0]):
            req_headers["Accept"] = "text/css"
        if extra_headers:
            req_headers.update(extra_headers)

        t0 = time.time()
        try:
            sess = self._quick_session if quick else self.session
            resp = sess.get(url, timeout=timeout, headers=req_headers, stream=False)
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

    def _extract_creator_from_html(self, html_text: str, user_id: str) -> Optional[str]:
        """Extract creator display name from Kemono/Pawchive/Coomer HTML page metadata."""
        if not html_text:
            return None
        import re
        uid_str = str(user_id).strip()

        # 1. itemprop="name"
        m = re.search(r'itemprop=["\']name["\'][^>]*>(.*?)<', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str:
                return name

        # 2. user-header__name
        m = re.search(r'class=["\'][^"\']*user-header__name[^"\']*["\'][^>]*>(.*?)<', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str:
                return name

        # 3. title regex: Posts of (.*?) from ...
        m = re.search(r'<title>\s*Posts of (.*?) from', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str:
                return name

        # 4. title regex: (.*?)'s posts | ...
        m = re.search(r'<title>\s*(.*?)\'s posts', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str:
                return name

        # 5. og:title
        m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html_text, re.I)
        if m:
            name = clean_text(m.group(1))
            if name and name != uid_str and not name.lower().startswith("posts of"):
                return name

        return None

    def resolve_creator_name(self, parsed: URLParseResult) -> Optional[str]:
        """Convenience helper to resolve and return just the clean creator display name."""
        if not parsed or not parsed.is_valid:
            return None
        profile = self.fetch_creator_profile(parsed)
        if profile and isinstance(profile, dict):
            name = profile.get("displayName") or profile.get("name") or profile.get("username")
            if name and str(name).strip() != str(parsed.user_id).strip():
                return clean_text(str(name))
        return None

    def fetch_creator_profile(self, parsed: URLParseResult) -> Dict[str, Any]:
        """Fetch creator profile, trying profile endpoints, cross-domain mirrors, HTML page scraping, and post fallback."""
        logger.info(f"Fetching creator profile: {parsed.service}/{parsed.user_id}", category="api")
        uid_str = str(parsed.user_id).strip()

        # Phase 1: Try dedicated JSON profile endpoints on the link's site + the mirror that carries
        # the same creators (Pawchive/Kemono, or cum.st/Coomer). Switched-off sites are skipped.
        family = ("coomer.st", "cum.st") if str(parsed.service).lower() in _COOMER_FAMILY_SERVICES else ("pawchive.pw", "kemono.cr")
        profile_domains = [d for d in [parsed.domain, *family] if d and not is_disabled(d)]
        profile_domains = list(dict.fromkeys(profile_domains))

        for domain in profile_domains:
            url = f"https://{domain}/api/v1/{parsed.service}/user/{parsed.user_id}/profile"
            resp = self._get_with_log(url, timeout=10, quick=True)
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict):
                        raw_name = data.get("displayName") or data.get("name") or data.get("username")
                        name = clean_text(raw_name) if raw_name else None
                        if name and name != uid_str:
                            data["name"] = name
                            logger.success(f"Creator: {name!r}  service={parsed.service}  id={parsed.user_id}", category="api")
                            return data
                except Exception as e:
                    logger.debug(f"Failed to parse profile JSON from {url}: {e}", category="api")

        # Phase 2: HTML Page metadata scraping (extremely resilient against API rate limits & 429/403)
        for domain in profile_domains:
            html_url = f"https://{domain}/{parsed.service}/user/{parsed.user_id}"
            resp = self._get_with_log(html_url, timeout=10, quick=True)
            if resp and resp.status_code == 200:
                name = self._extract_creator_from_html(resp.text, uid_str)
                if name:
                    logger.success(f"Creator: {name!r} (from HTML page {domain})  service={parsed.service}  id={parsed.user_id}", category="api")
                    return {"id": parsed.user_id, "name": name, "service": parsed.service}

        # Phase 3: Try posts endpoints ONLY if they contain a distinct creator name (NEVER accept raw_name == user_id)
        for domain in profile_domains:
            posts_url = self.posts_list_url(domain, parsed.service, parsed.user_id, 0)
            resp = self._get_with_log(posts_url, timeout=10, quick=True)
            if resp and resp.status_code == 200:
                try:
                    posts_data = resp.json()
                    items = posts_data.get("posts", []) if isinstance(posts_data, dict) else (posts_data if isinstance(posts_data, list) else [])
                    if items and isinstance(items[0], dict):
                        # ONLY check username or name — NEVER accept user field which is always the user_id
                        raw_name = items[0].get("username") or items[0].get("name")
                        name = clean_text(raw_name) if raw_name else None
                        if name and name != uid_str:
                            logger.success(f"Creator: {name!r} (from post metadata)  service={parsed.service}", category="api")
                            return {"id": parsed.user_id, "name": name, "service": parsed.service}
                except Exception:
                    pass

        logger.warning(f"Could not retrieve profile for {parsed.user_id}; using ID as name.", category="api")
        return {"id": parsed.user_id, "name": parsed.user_id, "service": parsed.service}

    @staticmethod
    def extract_pawchive_temporary_attachments(html_text: str) -> Dict[str, str]:
        """
        Parses Pawchive post HTML and returns a mapping of:
        clean_filename -> signed temporary download URL (https://t1.pawchive.pw/f/...).
        """
        if not html_text:
            return {}
        matches = re.findall(r'(?:href|src)=["\'](https://t1\.pawchive\.pw/f/[^"\']+)["\']', html_text)
        mapping: Dict[str, str] = {}
        for raw_u in matches:
            u = raw_u.replace("&amp;", "&")
            path_part = u.split("?")[0].split("/")[-1]
            name = unquote(path_part)
            if name and name not in mapping:
                mapping[name] = u
        return mapping

    def resolve_pawchive_deferred_attachments(self, post: Dict[str, Any], domain: str = "pawchive.pw") -> int:
        """
        Detects any attachments marked with 'deferred: True' (oversized temporary storage on Pawchive).
        Fetches the post HTML page, extracts signed t1.pawchive.pw temporary download URLs,
        and assigns them to the attachments' 'path' and 'is_temporary'.
        Returns the number of resolved attachments.
        """
        if not isinstance(post, dict):
            return 0

        attachments = post.get("attachments", [])
        if not isinstance(attachments, list):
            return 0

        deferred_items = [
            a for a in attachments
            if isinstance(a, dict) and a.get("deferred") and not a.get("path")
        ]
        if not deferred_items:
            return 0

        post_id = str(post.get("id") or "")
        service = post.get("service") or ""
        user_id = str(post.get("user") or "")

        if not post_id or not service or not user_id:
            return 0

        eff_domain = domain if "pawchive" in (domain or "") else "pawchive.pw"
        page_url = f"https://{eff_domain}/{service}/user/{user_id}/post/{post_id}"
        logger.debug(f"Fetching post HTML to resolve {len(deferred_items)} temporary file(s): {page_url}", category="api")

        resp = self._get_with_log(page_url, timeout=20)
        if not resp or resp.status_code != 200 or not resp.text:
            logger.warning(f"Could not fetch HTML for post {post_id} to resolve temporary files", category="api")
            return 0

        temp_map = self.extract_pawchive_temporary_attachments(resp.text)
        if not temp_map:
            logger.info(f"Post {post_id} has {len(deferred_items)} deferred attachment(s), but temporary links are expired or unavailable", category="api")
            return 0

        resolved_count = 0
        lower_map = {k.lower(): v for k, v in temp_map.items()}
        for att in deferred_items:
            att_name = att.get("name") or ""
            matched_url = temp_map.get(att_name) or lower_map.get(att_name.lower())
            if matched_url:
                att["path"] = matched_url
                att["is_temporary"] = True
                resolved_count += 1

        if resolved_count > 0:
            logger.info(f"✨ Resolved {resolved_count}/{len(deferred_items)} temporary oversized file(s) from t1.pawchive.pw for post {post_id}", category="api")

        return resolved_count

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
            post_obj = None
            if isinstance(data, list) and data:
                post_obj = data[0]
            elif isinstance(data, dict):
                if "post" in data and isinstance(data["post"], dict):
                    post_obj = data["post"]
                elif "dm" in data and isinstance(data["dm"], dict):
                    post_obj = data["dm"]
                else:
                    post_obj = data

            if post_obj and isinstance(post_obj, dict) and ("pawchive" in (parsed.domain or "") or "pawchive" in str(post_obj.get("origin", ""))):
                self.resolve_pawchive_deferred_attachments(post_obj, domain=parsed.domain)

            return post_obj
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
        date_after: str = "",
        date_before: str = "",
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
        rate_limited = 0
        MAX_RATE_LIMITED = 6
        largest_page = 0
        pages_fetched = 0
        cancelled = False

        logger.info(
            f"Post enumeration started — {parsed.service}/{parsed.user_id}  "
            f"pages {page_start}–{page_end}  (page size: {page_size})",
            category="api"
        )

        while current_page <= page_end:
            if cancel_event and cancel_event.is_set():
                logger.warning("Post enumeration cancelled by user.", category="api")
                cancelled = True
                break

            if parsed.domain == "cum.st":
                url = (
                    f"https://cum.st/api/v1/{parsed.service}"
                    f"/user/{parsed.user_id}/posts?o={offset}&n={page_size}"
                )
            else:
                url = self.posts_list_url(parsed.domain, parsed.service, parsed.user_id, offset)

            if progress_callback:
                progress_callback(current_page, len(all_posts))

            resp = self._get_with_log(url, timeout=25)

            if cancel_event and cancel_event.is_set():
                logger.warning("Post enumeration cancelled by user.", category="api")
                cancelled = True
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
                rate_limited += 1
                if rate_limited > MAX_RATE_LIMITED:
                    logger.error(f"Page {current_page}: still rate limited after {MAX_RATE_LIMITED} waits; stopping here.", category="api")
                    break
                wait_sec = _retry_after_seconds(resp.headers.get("Retry-After"), default=5.0 * rate_limited)
                logger.warning(f"Page {current_page}: Rate limited (429). Pausing {wait_sec:.0f}s before retry...", category="api")
                waited = 0.0
                while waited < wait_sec:
                    if cancel_event and cancel_event.is_set():
                        break
                    time.sleep(min(0.5, wait_sec - waited))
                    waited += 0.5
                continue
            rate_limited = 0

            if resp.status_code == 403:
                logger.error(
                    "403 Forbidden — posts are paywalled or cookie is missing/expired. "
                    "Add your session cookie in Settings → Network.",
                    category="api"
                )
                break

            if resp.status_code != 200:
                if resp.status_code in (400, 404) and pages_fetched > 0:
                    logger.info(f"Page {current_page}: no more posts (HTTP {resp.status_code}).", category="api")
                else:
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
            pages_fetched += 1
            logger.info(
                f"Page {current_page:3d}  offset {offset:5d}  +{batch} posts  "
                f"(running total: {len(all_posts)})",
                category="api"
            )

            # A page smaller than the biggest one seen is the last one. (Comparing with our own
            # page_size assumed every site serves 50 posts per page.)
            largest_page = max(largest_page, batch)
            if batch < largest_page:
                logger.info(f"Partial page ({batch}<{largest_page}) — reached last page.", category="api")
                break

            # Early-stop: if date_after is set and ALL posts on this page are
            # older than it, there is nothing useful on subsequent pages.
            if date_after:
                from core.filter_engine import FilterEngine as _FE
                norm_after = _FE.expand_date_start(date_after)
                norm_before_val = _FE.expand_date_end(date_before) if date_before else ""
                # Auto-correct inverted range (same as FilterEngine)
                if norm_after and norm_before_val and norm_after > norm_before_val:
                    norm_after, norm_before_val = norm_before_val, norm_after
                if norm_after:
                    oldest = ""
                    for p in posts:
                        pub = p.get("published") or p.get("added") or ""
                        if isinstance(pub, (int, float)):
                            try:
                                import datetime as _dt
                                d = _dt.datetime.fromtimestamp(pub).strftime("%Y-%m-%d")
                            except Exception:
                                d = ""
                        else:
                            pub_str = str(pub).strip()
                            d = pub_str.split("T")[0] if "T" in pub_str else pub_str[:10]
                        if d and (not oldest or d < oldest):
                            oldest = d
                    if oldest and oldest < norm_after:
                        logger.info(
                            f"Date early-stop: oldest post on page {current_page} ({oldest}) "
                            f"is before date range start ({norm_after}) — no need to scan further.",
                            category="api"
                        )
                        break

            offset += batch
            current_page += 1
            # Polite API pagination delay (prevents database load spikes on Pawchive)
            domain_lower = (parsed.domain or "").lower()
            page_delay = random.uniform(0.35, 0.55) if ("pawchive" in domain_lower) else 0.15
            time.sleep(page_delay)

        page_word = "page" if pages_fetched == 1 else "pages"
        if cancelled:
            logger.info(
                f"Enumeration stopped: {len(all_posts)} posts collected from {pages_fetched} {page_word} before cancelling.",
                category="api"
            )
        else:
            logger.success(
                f"Enumeration done: {len(all_posts)} posts collected across {pages_fetched} {page_word}.",
                category="api"
            )
        return all_posts

    def fetch_creator_tags(self, parsed) -> List[str]:
        """
        Fetch the tag list for a creator from Pawchive or cum.st.
        Returns a list of tag name strings sorted by post-count descending.
        Returns an empty list for unsupported providers or on error.

        Pawchive response: [ { "tag": str, "post_count": int }, ... ]
        cum.st response:   { "tags": [ { "slug": str, "label": str, "count": int }, ... ] }
        """
        domain = (parsed.domain or "").lower()
        supported = "pawchive" in domain or "cum.st" in domain

        if not supported:
            logger.debug(
                f"fetch_creator_tags: domain {domain!r} not supported (Pawchive/cum.st only).",
                category="api"
            )
            return []

        url = f"https://{parsed.domain}/api/v1/{parsed.service}/user/{parsed.user_id}/tags"
        logger.info(f"Fetching creator tags: {url}", category="api")

        resp = self._get_with_log(url, timeout=10)
        if resp is None or resp.status_code != 200:
            logger.warning(
                f"Failed to fetch tags for {parsed.user_id} ({parsed.service}): "
                f"HTTP {resp.status_code if resp is not None else 'no response'}",
                category="api"
            )
            return []

        try:
            data = resp.json()
        except Exception as e:
            logger.debug(f"Tag JSON parse error: {e}", category="api")
            return []

        tags: List[str] = []

        if "cum.st" in domain:
            # cum.st: { "tags": [ { "slug": str, "label": str, "count": int } ] }
            raw_tags = data.get("tags", []) if isinstance(data, dict) else []
            for item in raw_tags:
                if isinstance(item, dict):
                    label = item.get("label") or item.get("slug") or ""
                    if label:
                        tags.append((label, int(item.get("count", 0))))
        else:
            # Pawchive: [ { "tag": str, "post_count": int }, ... ]
            raw_tags = data if isinstance(data, list) else []
            for item in raw_tags:
                if isinstance(item, dict):
                    tag_name = item.get("tag") or ""
                    if tag_name:
                        tags.append((tag_name, int(item.get("post_count", 0))))

        # Sort by count descending, return just the names
        tags.sort(key=lambda x: x[1], reverse=True)
        result = [t[0] for t in tags]
        logger.info(f"Fetched {len(result)} tag(s) for {parsed.user_id} [{parsed.service}]", category="api")
        return result

    def fetch_user_favorites(
        self,
        domain: str = "kemono.cr",
        fav_type: str = "post",
        page_start: int = 1,
        page_end: int = 999999,
        page_size: int = 50,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches authenticated user favorites (posts or artists) from Kemono/Coomer favorites API.
        Endpoint: https://{domain}/api/v1/favorites?type={fav_type}&o={offset}
        """
        # The account cookie for this site is attached per request (core.providers.cookie_for_url)

        all_items: List[Dict[str, Any]] = []
        current_page = page_start
        offset = (page_start - 1) * page_size
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 3
        seen_keys = set()
        largest_page = 0

        logger.info(
            f"Favorites enumeration started — domain={domain} type={fav_type} pages {page_start}–{page_end}",
            category="api"
        )

        is_pawchive = "pawchive" in domain.lower()

        while current_page <= page_end:
            if cancel_event and cancel_event.is_set():
                logger.warning("Favorites enumeration cancelled by user.", category="api")
                break

            if is_pawchive:
                url = f"https://{domain}/favorites?type={fav_type}&o={offset}"
            else:
                url = f"https://{domain}/api/v1/favorites?type={fav_type}&o={offset}"

            if progress_callback:
                progress_callback(current_page, len(all_items))

            resp = self._get_with_log(url, timeout=25)

            if cancel_event and cancel_event.is_set():
                break

            if resp is None:
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(f"Stopping favorites enumeration after {MAX_CONSECUTIVE_ERRORS} consecutive failures.", category="api")
                    break
                time.sleep(2.0)
                continue

            consecutive_errors = 0

            if resp.status_code in (401, 403):
                logger.error(
                    f"HTTP {resp.status_code} Unauthorized when fetching favorites from {domain}. "
                    f"Please log in or add your session cookie in Settings → Accounts & Logins.",
                    category="api"
                )
                break

            if resp.status_code != 200:
                logger.warning(f"Favorites returned HTTP {resp.status_code}, stopping.", category="api")
                break

            items: List[Dict[str, Any]] = []

            # Pawchive HTML parsing
            if is_pawchive:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    if fav_type == "post":
                        for a in soup.find_all("article", class_=re.compile(r"post-card")):
                            pid = a.get("data-id")
                            svc = a.get("data-service")
                            usr = a.get("data-user")
                            if pid and svc and usr:
                                # Fetch full post metadata via API
                                p_url = f"https://{domain}/api/v1/{svc}/user/{usr}/post/{pid}"
                                p_resp = self._get_with_log(p_url, timeout=15)
                                if p_resp and p_resp.status_code == 200:
                                    try:
                                        p_json = p_resp.json()
                                        if isinstance(p_json, dict):
                                            items.append(p_json)
                                            continue
                                    except Exception:
                                        pass
                                # Fallback minimal post representation
                                title_el = a.find(class_=re.compile(r"post-card__title"))
                                title = title_el.get_text(strip=True) if title_el else f"Post {pid}"
                                items.append({
                                    "id": str(pid),
                                    "user": str(usr),
                                    "service": str(svc),
                                    "title": title
                                })
                    else:
                        for u_card in soup.find_all("a", class_=re.compile(r"user-card")):
                            cid = u_card.get("data-id")
                            csvc = u_card.get("data-service")
                            cname_el = u_card.find(class_=re.compile(r"user-card__name"))
                            cname = cname_el.get_text(strip=True) if cname_el else ""
                            if cid and csvc:
                                items.append({"id": str(cid), "service": str(csvc), "name": cname})
                except Exception as e:
                    logger.error(f"Pawchive favorites HTML parse error: {e}", category="api")
                    break
            else:
                try:
                    raw_data = resp.json()
                except Exception as e:
                    logger.error(f"Favorites JSON parse error: {e}", category="api")
                    break

                if isinstance(raw_data, list):
                    items = raw_data
                elif isinstance(raw_data, dict):
                    items = raw_data.get("posts") or raw_data.get("favorites") or raw_data.get("artists") or []
                else:
                    items = []

            if not items:
                logger.info(f"Page {current_page}: 0 favorites returned — enumeration complete.", category="api")
                break

            # A site that ignores the page offset returns the same list again: stop when a page
            # brings nothing new (that used to repeat the list until page_end)
            fresh = []
            for it in items:
                key = (str(it.get("service", "")), str(it.get("user", "")), str(it.get("id", ""))) if isinstance(it, dict) else (str(it),)
                if key not in seen_keys:
                    seen_keys.add(key)
                    fresh.append(it)
            if not fresh:
                logger.info(f"Page {current_page}: nothing new — reached end of favorites.", category="api")
                break

            batch = len(items)
            all_items.extend(fresh)
            logger.info(f"Page {current_page:3d}  offset {offset:5d}  +{len(fresh)} favorite {fav_type}(s) (total: {len(all_items)})", category="api")

            # A page smaller than the biggest one seen is the last one (the page size isn't fixed:
            # assuming 50 stopped after the first page on a site that shows fewer)
            largest_page = max(largest_page, batch)
            if batch < largest_page:
                logger.info(f"Partial page ({batch}<{largest_page}) — reached end of favorites.", category="api")
                break

            offset += batch
            current_page += 1
            time.sleep(0.2)

        logger.success(f"Favorites enumeration done: {len(all_items)} {fav_type}(s) collected.", category="api")
        return all_items


