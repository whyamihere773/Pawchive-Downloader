"""
API Client — Single Post, Post Pagination, DMs, Comments & Creator Tags Fetcher Mixin
Decomposed from core/api_client.py to keep modules cohesive and under 1,000 lines.
"""

import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from core.logger import logger
from core.parser import URLParseResult


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


class ApiContentFetcherMixin:
    """Fetches single posts/DMs, paginated creator posts, DMs, comments, and creator tags."""

    def fetch_single_post(self, parsed: URLParseResult) -> Optional[Dict[str, Any]]:
        """Fetch a single post (or DM) by ID."""
        if getattr(parsed, "domain", "") == "coomerfans.com" or getattr(parsed, "provider", "") == "coomerfans":
            from services.coomerfans_client import fetch_single_post as fetch_cf_post
            return fetch_cf_post(parsed)

        if not parsed.post_id:
            return None

        # Check if URL was a DM or Post
        endpoint_type = "dm" if "/dm/" in parsed.raw_url.lower() else "post"
        url = f"https://{parsed.domain}/api/v1/{parsed.service}/user/{parsed.user_id}/{endpoint_type}/{parsed.post_id}"
        logger.info(f"Fetching single {endpoint_type}: {parsed.post_id}", category="api")

        resp = self._get_with_log(url, timeout=15)
        if resp is None or resp.status_code != 200:
            if endpoint_type == "dm" and "pawchive" in (parsed.domain or "").lower():
                for dm_item in self.fetch_user_dms(parsed):
                    if str(dm_item.get("id") or "") == str(parsed.post_id):
                        return dm_item
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

            if post_obj and isinstance(post_obj, dict):
                if endpoint_type == "dm":
                    post_obj = dict(post_obj)
                    post_obj["user"] = post_obj.get("user") or parsed.user_id
                    post_obj["service"] = post_obj.get("service") or parsed.service
                    post_obj["domain"] = parsed.domain
                    post_obj["is_dm"] = True
                    post_obj["is_dms"] = True
                    cap = str(
                        post_obj.get("captionText")
                        or post_obj.get("contentText")
                        or post_obj.get("caption")
                        or ""
                    ).strip()
                    if cap:
                        post_obj["captionText"] = cap
                    post_obj["content"] = post_obj.get("content") or post_obj.get("captionHtml") or cap
                    first_line = cap.split("\n")[0][:80].strip() if cap else ""
                    post_obj["title"] = post_obj.get("title") or first_line or f"DM {parsed.post_id}"
                if "pawchive" in (parsed.domain or "") or "pawchive" in str(post_obj.get("origin", "")):
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
        if getattr(parsed, "domain", "") == "coomerfans.com" or getattr(parsed, "provider", "") == "coomerfans":
            from services.coomerfans_client import fetch_user_posts as fetch_cf_posts
            return fetch_cf_posts(
                parsed=parsed,
                page_start=page_start,
                page_end=page_end,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                date_after=date_after,
                date_before=date_before,
            )

        all_posts: List[Dict[str, Any]] = []
        self._fetch_state.failed = False        # set when the list stops early because of an error
        current_page = page_start
        offset = (page_start - 1) * page_size
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 3
        rate_limited = 0
        MAX_RATE_LIMITED = 6
        largest_page = 0
        pages_fetched = 0
        cancelled = False
        known_total: Optional[int] = None

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

            if progress_callback and current_page == page_start and len(all_posts) == 0:
                try:
                    progress_callback(current_page, 0, known_total)
                except TypeError:
                    progress_callback(current_page, 0)

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
                    self._fetch_state.failed = True
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
                    self._fetch_state.failed = True
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
                self._fetch_state.failed = True
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
                    self._fetch_state.failed = True
                    logger.warning(f"Page {current_page}: unexpected HTTP {resp.status_code}, stopping.", category="api")
                break

            try:
                raw_data = resp.json()
            except Exception as e:
                self._fetch_state.failed = True
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

            if isinstance(raw_data, dict):
                raw_tot = raw_data.get("total")
                if isinstance(raw_tot, int) and raw_tot > 0:
                    known_total = raw_tot
                elif isinstance(raw_tot, str) and raw_tot.strip().isdigit():
                    known_total = int(raw_tot.strip())

            if progress_callback:
                try:
                    progress_callback(current_page, len(all_posts), known_total)
                except TypeError:
                    progress_callback(current_page, len(all_posts))

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

    def fetch_user_dms(
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
        Paginates through creator direct messages (DMs).
        Supported on cum.st (via REST API) and Pawchive (via HTML scraping).
        Emits progress and handles cancellation, backoff, and date filters.
        """
        all_dms: List[Dict[str, Any]] = []
        domain_lower = (parsed.domain or "").lower()
        if "cum.st" not in domain_lower and "pawchive" not in domain_lower:
            logger.info(f"Direct messages (DMs) are not supported on {parsed.domain}.", category="api")
            return []

        logger.info(
            f"DM enumeration started — {parsed.service}/{parsed.user_id} on {parsed.domain}",
            category="api"
        )

        current_page = page_start
        offset = (page_start - 1) * page_size
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 3
        rate_limited = 0
        MAX_RATE_LIMITED = 6
        pages_fetched = 0
        cancelled = False
        known_total: Optional[int] = None
        seen_ids: Set[str] = set()

        norm_after = date_after.strip() if date_after else ""
        norm_before = date_before.strip() if date_before else ""

        while current_page <= page_end:
            if cancel_event and cancel_event.is_set():
                logger.warning("DM enumeration cancelled by user.", category="api")
                cancelled = True
                break

            if "cum.st" in domain_lower:
                url = (
                    f"https://cum.st/api/v1/{parsed.service}"
                    f"/user/{parsed.user_id}/dms?o={offset}&n={page_size}"
                )
            else:  # pawchive
                url = f"https://pawchive.pw/{parsed.service}/user/{parsed.user_id}/dms?o={offset}"

            if progress_callback and current_page == page_start and len(all_dms) == 0:
                try:
                    progress_callback(current_page, 0, known_total)
                except TypeError:
                    progress_callback(current_page, 0)

            resp = self._get_with_log(url, timeout=25)

            if cancel_event and cancel_event.is_set():
                logger.warning("DM enumeration cancelled by user.", category="api")
                cancelled = True
                break

            if resp is None:
                consecutive_errors += 1
                logger.warning(
                    f"DM Page {current_page} request failed "
                    f"({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS} consecutive errors)",
                    category="api"
                )
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        f"Stopping DM enumeration after {MAX_CONSECUTIVE_ERRORS} consecutive failures.",
                        category="api"
                    )
                    break
                time.sleep(2.0)
                continue

            consecutive_errors = 0

            if resp.status_code == 429:
                rate_limited += 1
                if rate_limited > MAX_RATE_LIMITED:
                    logger.error(f"DM Page {current_page}: rate limited after {MAX_RATE_LIMITED} waits; stopping.", category="api")
                    break
                wait_sec = _retry_after_seconds(resp.headers.get("Retry-After"), default=5.0 * rate_limited)
                logger.warning(f"DM Page {current_page}: Rate limited (429). Pausing {wait_sec:.0f}s...", category="api")
                waited = 0.0
                while waited < wait_sec:
                    if cancel_event and cancel_event.is_set():
                        break
                    time.sleep(min(0.5, wait_sec - waited))
                    waited += 0.5
                continue
            rate_limited = 0

            if resp.status_code in (400, 404):
                logger.info(f"DM Page {current_page}: no more DMs (HTTP {resp.status_code}).", category="api")
                break
            elif resp.status_code != 200:
                logger.warning(f"DM Page {current_page}: unexpected HTTP {resp.status_code}, stopping.", category="api")
                break

            page_dms: List[Dict[str, Any]] = []
            has_next_page = True

            if "cum.st" in domain_lower:
                try:
                    raw_data = resp.json()
                except Exception as e:
                    logger.error(f"DM Page {current_page}: JSON parse error — {e}", category="api")
                    break

                raw_items = raw_data.get("dms") if isinstance(raw_data, dict) else (raw_data if isinstance(raw_data, list) else [])
                if isinstance(raw_data, dict):
                    raw_tot = raw_data.get("total")
                    if isinstance(raw_tot, (int, str)) and str(raw_tot).isdigit():
                        known_total = int(raw_tot)

                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    p = dict(item)
                    p["user"] = p.get("user") or parsed.user_id
                    p["service"] = p.get("service") or parsed.service
                    p["domain"] = "cum.st"
                    p["is_dm"] = True
                    p["is_dms"] = True
                    cap = str(
                        p.get("captionText")
                        or p.get("contentText")
                        or p.get("caption")
                        or ""
                    ).strip()
                    p["captionText"] = cap
                    p["content"] = p.get("content") or p.get("captionHtml") or cap
                    first_line = cap.split("\n")[0][:80].strip() if cap else ""
                    p["title"] = p.get("title") or first_line or "Direct Message"
                    p["published"] = p.get("published") or p.get("added") or ""
                    page_dms.append(p)

            else:  # Pawchive HTML parsing (shared parser)
                if BeautifulSoup is None:
                    logger.error("BeautifulSoup4 is required to parse Pawchive DMs.", category="api")
                    break
                try:
                    from core.browser_providers.base import KemonoStyleCatalogProvider
                    page_dms, html_total, has_next_page = KemonoStyleCatalogProvider.parse_dms_html_cards(
                        resp.text,
                        base_domain="pawchive.pw",
                        service=parsed.service,
                        creator_id=parsed.user_id,
                        current_offset=offset,
                    )
                    if known_total is None and html_total is not None:
                        known_total = html_total
                except Exception as e:
                    logger.error(f"DM Page {current_page}: HTML parse error — {e}", category="api")
                    break

            if not page_dms:
                logger.info(
                    f"DM Page {current_page} returned 0 DMs — enumeration complete at offset {offset}.",
                    category="api"
                )
                break

            unique_page_dms: List[Dict[str, Any]] = []
            for dm_obj in page_dms:
                d_id = dm_obj.get("id")
                if d_id:
                    if d_id in seen_ids:
                        continue
                    seen_ids.add(d_id)
                unique_page_dms.append(dm_obj)

            if not unique_page_dms:
                logger.info(
                    f"DM Page {current_page}: no new DMs found (all {len(page_dms)} cards were already seen) — pagination complete.",
                    category="api"
                )
                break

            batch = len(unique_page_dms)
            all_dms.extend(unique_page_dms)
            pages_fetched += 1
            logger.info(
                f"DM Page {current_page:3d}  offset {offset:5d}  +{batch} DMs  "
                f"(running total: {len(all_dms)})",
                category="api"
            )

            if progress_callback:
                try:
                    progress_callback(current_page, len(all_dms), known_total)
                except TypeError:
                    progress_callback(current_page, len(all_dms))

            # If total reached, stop
            if known_total and len(all_dms) >= known_total:
                logger.info(f"Reached known total of {known_total} DMs.", category="api")
                break

            # If pawchive returned less than page_size cards or has no subsequent page links, stop
            if "pawchive" in domain_lower:
                if not has_next_page:
                    logger.info(
                        f"Last Pawchive DMs page reached ({batch} cards, no subsequent pagination links).",
                        category="api"
                    )
                    break
                if batch < 50:
                    logger.info(f"Last Pawchive DMs page reached ({batch} cards).", category="api")
                    break

            offset += len(page_dms)
            current_page += 1
            page_delay = random.uniform(0.35, 0.55) if ("pawchive" in domain_lower) else 0.15
            time.sleep(page_delay)

        page_word = "page" if pages_fetched == 1 else "pages"
        if cancelled:
            logger.info(
                f"DM enumeration stopped: {len(all_dms)} DMs collected from {pages_fetched} {page_word} before cancelling.",
                category="api"
            )
        else:
            logger.success(
                f"DM enumeration done: {len(all_dms)} DMs collected across {pages_fetched} {page_word}.",
                category="api"
            )
        return all_dms

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
