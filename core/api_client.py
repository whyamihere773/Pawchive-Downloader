"""
API Client & Network Engine
Handles communication with Kemono, Pawchive, Coomer, and Cum.st REST endpoints
with exponential backoff, rate limiting recovery, and diagnostic logging.
"""

import json
import os
import sys
import time
import random
import threading
import requests
import re
import hashlib
from urllib.parse import unquote, urljoin
from typing import Dict, Any, List, Optional, Callable, Tuple, Set
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger
from core.parser import URLParseResult
from core.text_utils import clean_text
from core.providers import cookie_for_url, is_disabled, disabled_message, provider_for_host
from core.api_listings_profile import ApiListingsProfileMixin
from core.api_content_fetcher import ApiContentFetcherMixin

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


class KemonoApiClient(ApiListingsProfileMixin, ApiContentFetcherMixin):
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

    @staticmethod
    def _parse_cumst_bookmarks(json_data: dict, fav_type: str = "artist") -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """
        Parses SvelteKit devalue serialized JSON from:
        - https://cum.st/account/bookmarks/creators/__data.json
        - https://cum.st/account/bookmarks/posts/__data.json
        """
        results: List[Dict[str, Any]] = []
        total_count: Optional[int] = None
        try:
            if isinstance(json_data, list):
                return json_data, None
            if not isinstance(json_data, dict):
                return results, total_count
            nodes = json_data.get("nodes", [])
            if len(nodes) < 3:
                return results, total_count
            node_data = nodes[2].get("data", [])
            if not node_data or not isinstance(node_data, list):
                return results, total_count

            def resolve(val):
                if isinstance(val, int) and 0 <= val < len(node_data):
                    return node_data[val]
                return val

            root = node_data[0]
            if not isinstance(root, dict):
                return results, total_count

            tot = root.get("total")
            if tot is not None:
                tot_val = resolve(tot)
                if isinstance(tot_val, int):
                    total_count = tot_val

            if fav_type == "artist":
                creators_ref = root.get("creators")
                if creators_ref is None:
                    return results, total_count
                creators_indices = resolve(creators_ref)
                if not isinstance(creators_indices, list):
                    return results, total_count

                for c_idx in creators_indices:
                    c_dict = resolve(c_idx)
                    if not isinstance(c_dict, dict):
                        continue
                    resolved = {k: resolve(v) for k, v in c_dict.items()}
                    uid = str(resolved.get("id") or "").strip()
                    svc = str(resolved.get("service") or "").strip().lower()
                    name = resolved.get("displayName") or resolved.get("name") or uid
                    avatar = f"https://img.cum.st/creator/{svc}/{uid}/avatar.webp"
                    if uid and svc:
                        results.append({
                            "id": uid,
                            "service": svc,
                            "name": name,
                            "avatar": avatar,
                            "domain": "cum.st",
                            "postCount": resolved.get("postCount", 0),
                            "imageCount": resolved.get("imageCount", 0),
                            "videoCount": resolved.get("videoCount", 0),
                        })
            else:
                items_ref = root.get("items")
                if items_ref is None:
                    return results, total_count
                items_indices = resolve(items_ref)
                if not isinstance(items_indices, list):
                    return results, total_count

                for it_idx in items_indices:
                    it_dict = resolve(it_idx)
                    if not isinstance(it_dict, dict):
                        continue
                    resolved = {k: resolve(v) for k, v in it_dict.items()}
                    pid = str(resolved.get("id") or "").strip()
                    usr = str(resolved.get("user") or resolved.get("creatorId") or "").strip()
                    svc = str(resolved.get("service") or "").strip().lower()
                    title = resolved.get("title") or resolved.get("captionHtml") or f"Post {pid}"
                    if pid:
                        entry = {
                            "id": pid,
                            "user": usr,
                            "service": svc,
                            "title": title,
                            "domain": "cum.st",
                        }
                        for k, v in resolved.items():
                            if k not in entry:
                                entry[k] = v
                        results.append(entry)
        except Exception as ex:
            logger.error(f"Error parsing cum.st bookmarks: {ex}", category="api")
        return results, total_count

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
        Fetches authenticated user favorites (posts or artists) from Kemono/Coomer/Pawchive/cum.st favorites API.
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
        is_cumst = "cum.st" in domain.lower() or "cumst" in domain.lower()

        while current_page <= page_end:
            if cancel_event and cancel_event.is_set():
                logger.warning("Favorites enumeration cancelled by user.", category="api")
                break

            if is_cumst:
                endpoint = "creators" if fav_type == "artist" else "posts"
                url = f"https://cum.st/account/bookmarks/{endpoint}/__data.json?page={current_page}"
            elif is_pawchive:
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
            cumst_total: Optional[int] = None

            # cum.st SvelteKit JSON parsing
            if is_cumst:
                try:
                    raw_data = resp.json()
                    items, cumst_total = self._parse_cumst_bookmarks(raw_data, fav_type=fav_type)
                except Exception as e:
                    logger.error(f"cum.st favorites parse error: {e}", category="api")
                    break
            # Pawchive HTML parsing
            elif is_pawchive:
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
                            cimg_el = u_card.find("img")
                            cavatar = cimg_el.get("src", "") if cimg_el else ""
                            if cavatar and not cavatar.startswith("http"):
                                cavatar = f"https://{domain}{cavatar}"
                            if cid and csvc:
                                items.append({"id": str(cid), "service": str(csvc), "name": cname, "avatar": cavatar})
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

            if is_cumst and cumst_total is not None and len(all_items) >= cumst_total:
                logger.info(f"Page {current_page}: reached cum.st total ({len(all_items)}/{cumst_total}) — enumeration complete.", category="api")
                break

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
