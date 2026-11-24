"""
Downloader HTTP Mirror Negotiation & Request Headers Mixin
Decomposed from core/downloader_transfer_http.py for proactive modularity.
"""

import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.downloader_models import DownloadTask, _CONTACT_HEADERS
from core.filter_engine import FilterOptions
from core.logger import logger
from core.providers import cookie_for_url, provider_for_host

_CACHED_PAWCHIVE_UA: Optional[str] = None


def _pawchive_user_agent() -> str:
    global _CACHED_PAWCHIVE_UA
    if _CACHED_PAWCHIVE_UA is None:
        ver = "1.4.4"
        try:
            from services.update_service import get_local_version_info
            v = str((get_local_version_info() or {}).get("version") or "").strip().lstrip("v")
            if v:
                ver = v
        except Exception:
            pass
        _CACHED_PAWCHIVE_UA = f"PawchiveDownloader/{ver} (https://github.com/whyamihere773/Pawchive-Downloader)"
    return _CACHED_PAWCHIVE_UA


class DownloaderHttpNegotiatorMixin:
    """Builds host-specific headers and negotiates HTTP responses across mirrors."""

    def _new_cookieless_session(self) -> requests.Session:
        """Create a fresh cookieless session that still honors self._proxy_url."""
        sess = requests.Session()
        proxy_url = getattr(self, "_proxy_url", "") or ""
        if proxy_url:
            sess.proxies = {"http": proxy_url, "https": proxy_url}
        return sess

    def _build_request_headers(
        self,
        task: DownloadTask,
        attempt_url: str,
        range_headers: Dict[str, str],
    ) -> Dict[str, str]:
        """Construct provider-specific request headers and per-site cookies for an HTTP GET."""
        req_headers = dict(range_headers)
        u_low = attempt_url.lower()
        if "bunkr" in u_low or "cdn.cr" in u_low or "scdn.st" in u_low or (hasattr(task, "service") and task.service == "bunkr"):
            req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            req_headers["Referer"] = "https://bunkr.cr/"
            req_headers["Origin"] = "https://bunkr.cr"
            req_headers["Accept"] = "*/*"
        elif "erome" in u_low:
            req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            req_headers["Referer"] = "https://www.erome.com/"
            req_headers["Accept"] = "*/*"
        elif "nhentai" in u_low:
            req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            req_headers["Referer"] = "https://nhentai.net/"
            req_headers["Accept"] = "*/*"
        elif "coomerfans" in u_low:
            req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            req_headers["Referer"] = "https://coomerfans.com/"
            req_headers["Accept"] = "*/*"
        elif "coomer" in u_low:
            req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            req_headers["Referer"] = "https://coomer.st/"
            req_headers["Accept"] = "*/*"
        elif "pawchive" in u_low:
            req_headers["User-Agent"] = _pawchive_user_agent()
            req_headers["Referer"] = "https://pawchive.pw/"
            req_headers["Accept"] = "*/*"
        elif "cum.st" in u_low:
            req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            req_headers["Referer"] = "https://cum.st/"
            req_headers["Accept"] = "*/*"
        else:
            req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            req_headers["Referer"] = "https://kemono.cr/"
            req_headers["Accept"] = "*/*"

        # The login cookie only goes to the archive site it belongs to
        _mod = sys.modules.get("core.downloader")
        _pfh = getattr(_mod, "provider_for_host", provider_for_host) if _mod is not None else provider_for_host
        if _pfh(attempt_url):
            site_cookie = cookie_for_url(attempt_url, self._clean_cookie)
            if site_cookie:
                req_headers["Cookie"] = site_cookie
            else:
                req_headers.update(_CONTACT_HEADERS)

        return req_headers

    def _acquire_http_response(
        self,
        *,
        task: DownloadTask,
        session: requests.Session,
        options: Optional[FilterOptions],
        full_urls: List[str],
        preview_urls: List[str],
        allow_thumb_fallback: bool,
        range_headers: Dict[str, str],
        mode: str,
        existing_size: int,
    ) -> Tuple[Any, str, int, Dict[str, str], Optional[Tuple[bool, str]]]:
        """Negotiate an open HTTP response across full-size mirrors and optional thumbnail fallback.

        Returns (resp, mode, existing_size, winning_req_headers, early_return_or_none).
        """
        resp = None
        req_headers: Dict[str, str] = dict(range_headers)
        # Two passes across full-size mirrors; small preview copy ONLY if fallback_to_thumbnails is enabled
        # and ONLY when full-size mirrors were missing/unavailable (never on temporary 429 rate-limits).
        is_pawchive_task = any("pawchive" in u.lower() for u in full_urls)
        pass1_urls = full_urls[:1] if (is_pawchive_task and len(full_urls) > 1) else full_urls
        pass_lists = [full_urls, pass1_urls] + ([preview_urls] if (preview_urls and allow_thumb_fallback) else [])
        saw_429 = False
        saw_404 = False
        saw_403 = False
        last_error_status = 0
        last_retry_after = ""

        for pass_idx, urls_to_try in enumerate(pass_lists):
            # Never downgrade a temporarily rate-limited full-size file to a thumbnail preview
            if pass_idx == 2 and saw_429:
                break
            if pass_idx == 1:
                time.sleep(1.5)  # Brief jittered pause before second pass if all mirrors were busy

            for attempt_url in urls_to_try:
                if self._cancel_event.is_set():
                    return None, mode, existing_size, req_headers, (False, "Cancelled")
                if attempt_url not in task._tried_urls:
                    task._tried_urls.append(attempt_url)

                req_headers = self._build_request_headers(task, attempt_url, range_headers)
                u_low = attempt_url.lower()

                stream_timeout = (25, 60)
                if not self._wait_pawchive_pace_slot(task, attempt_url, respect_cooldown=not (pass_idx > 0 and saw_429)):
                    if self._cancel_event.is_set() or self.is_batch_cancelled(task):
                        return None, mode, existing_size, req_headers, (False, "Cancelled")
                    return None, mode, existing_size, req_headers, (False, "Batch paused by user")
                try:
                    resp = session.get(attempt_url, stream=True, timeout=stream_timeout, headers=req_headers)
                    if resp.status_code in (200, 206, 416):
                        task.url = attempt_url
                        break
                    elif resp.status_code in (403, 404) and re.search(r"\bt\d+\.pawchive\.pw\b", attempt_url):
                        # Pawchive temporary oversized download URLs are signed (?e=...&s=...) and expire over time.
                        # Re-resolve the post page to get a fresh signed URL if available.
                        last_error_status = resp.status_code
                        if resp.status_code == 404:
                            saw_404 = True
                        else:
                            saw_403 = True
                        fresh_url = self._refresh_pawchive_temp_url(task)
                        if fresh_url and fresh_url != attempt_url:
                            logger.info(f"✨ Refreshed expired temporary download URL for {task.filename}", category="downloader")
                            task.url = fresh_url
                            attempt_url = fresh_url
                            resp.close()
                            try:
                                retry_resp = session.get(fresh_url, stream=True, timeout=stream_timeout, headers=req_headers)
                                if retry_resp.status_code in (200, 206, 416):
                                    resp = retry_resp
                                    break
                                else:
                                    retry_resp.close()
                            except Exception:
                                pass
                        if resp and resp.status_code not in (200, 206, 416):
                            resp.close()
                            resp = None
                            continue
                    elif resp.status_code == 404:
                        saw_404 = True
                        last_error_status = 404
                        if pass_idx < len(pass_lists) - 1:
                            logger.debug(f"  ↪ Mirror 404 on {attempt_url} (pass {pass_idx + 1}/{len(pass_lists)}) — will retry on next pass...", category="file")
                            resp.close()
                            resp = None
                            continue
                        elif len(urls_to_try) > 1:
                            logger.debug(f"  ↪ Mirror 404 on {attempt_url} — trying next mirror...", category="file")
                            resp.close()
                            resp = None
                            continue
                        else:
                            # Final pass on single-mirror host — definitive 404 verified after retry
                            task.http_status = 404
                            if "pawchive" in u_low:
                                msg = (
                                    "Not available on Pawchive (HTTP 404) — this file isn't physically hosted "
                                    "on Pawchive's servers (the post may not have been imported yet, or the file was removed)"
                                )
                            else:
                                msg = "404 Not Found — file does not exist on server"
                            logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                            resp.close()
                            resp = None
                            return None, mode, existing_size, req_headers, (False, msg)
                    elif resp.status_code == 403:
                        saw_403 = True
                        last_error_status = 403
                        # If we sent a Range header, the CDN might be rejecting range requests with 403.
                        # Retry from byte 0 without Range and without cookies.
                        if "Range" in req_headers:
                            no_range_headers = {k: v for k, v in req_headers.items() if k.lower() != "range"}
                            try:
                                fresh_resp = session.get(attempt_url, stream=True, timeout=stream_timeout, headers=no_range_headers)
                                if fresh_resp.status_code in (200, 206):
                                    resp.close()
                                    resp = fresh_resp
                                    task.url = attempt_url
                                    mode = "wb"
                                    existing_size = 0
                                    break
                                else:
                                    fresh_resp.close()
                            except Exception:
                                pass

                        # Try without cookie and with full headers (identifiable UA for Pawchive, browser headers for others)
                        try:
                            if "pawchive" in attempt_url.lower():
                                clean_headers = {
                                    "User-Agent": _pawchive_user_agent(),
                                    "Referer": "https://pawchive.pw/",
                                    "Accept": "*/*",
                                    "X-Contact": "https://github.com/whyamihere773/Pawchive-Downloader",
                                }
                            else:
                                clean_headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                                    "Sec-Fetch-Dest": "document",
                                    "Sec-Fetch-Mode": "navigate",
                                    "Sec-Fetch-Site": "none",
                                    "Sec-Fetch-User": "?1",
                                    "Upgrade-Insecure-Requests": "1",
                                }
                            clean_sess = self._new_cookieless_session()
                            try:
                                clean_resp = clean_sess.get(attempt_url, stream=True, timeout=stream_timeout, headers=clean_headers)
                                if clean_resp.status_code in (200, 206):
                                    resp.close()
                                    resp = clean_resp
                                    task.url = attempt_url
                                    mode = "wb"
                                    existing_size = 0
                                    break
                                elif clean_resp.status_code == 403 and len(urls_to_try) == 1:
                                    # Single-mirror CDN transient burst 403 — progressive pause & retry
                                    clean_resp.close()
                                    for delay in (1.5, 3.0):
                                        time.sleep(delay)
                                        if self._cancel_event.is_set():
                                            break
                                        retry_resp = clean_sess.get(attempt_url, stream=True, timeout=stream_timeout, headers=clean_headers)
                                        if retry_resp.status_code in (200, 206):
                                            resp.close()
                                            resp = retry_resp
                                            task.url = attempt_url
                                            mode = "wb"
                                            existing_size = 0
                                            break
                                        else:
                                            retry_resp.close()
                                else:
                                    clean_resp.close()
                            finally:
                                if resp is None or resp.status_code not in (200, 206):
                                    clean_sess.close()
                            if resp and resp.status_code in (200, 206):
                                break
                        except Exception:
                            pass

                        # Still 403 — rotate to next mirror or pass
                        logger.debug(f"  ↪ Mirror 403 on {attempt_url} — trying next mirror...", category="file")
                        if resp:
                            resp.close()
                            resp = None
                        continue
                    elif resp.status_code == 429:
                        saw_429 = True
                        last_error_status = 429
                        task.http_status = 429
                        retry_after = str(resp.headers.get("Retry-After") or "").strip()
                        last_retry_after = retry_after if retry_after.isdigit() else ("10" if "pawchive" in u_low else "15")
                        delay = min(max(float(last_retry_after), 1.0), 10.0)
                        logger.warning(
                            f"  ⚠ {task.filename}: HTTP 429 Too Many Requests on {attempt_url} (Retry-After: {last_retry_after}s)",
                            category="file"
                        )
                        resp.close()
                        resp = None
                        # Immediately step down Adaptive Threading & pause sibling workers even on a
                        # first-pass 429 so concurrency doesn't stay stuck at its ceiling if pass 1 succeeds.
                        is_locked_now = bool(getattr(self.current_options or options, "threads_locked", False))
                        self._trigger_rate_limit_backoff(threads_locked=is_locked_now)
                        with self._pawchive_pace_lock:
                            self._pawchive_next_req_time = max(self._pawchive_next_req_time, time.time() + delay)
                        if pass_idx == 0 and ("pawchive" in u_low or len(urls_to_try) == 1):
                            # Respect Retry-After once before a single verification retry on pass 1;
                            # break out of the inner mirror loop so shared-bucket mirrors aren't hammered.
                            time.sleep(delay)
                            if self._cancel_event.is_set():
                                return None, mode, existing_size, req_headers, (False, "Cancelled")
                            break
                        if "pawchive" in u_low or len(urls_to_try) == 1:
                            # Persistent 429 after Retry-After: propagate 429_RATE_LIMIT immediately
                            # so global adaptive backoff and auto-retry engage cleanly.
                            return None, mode, existing_size, req_headers, (False, f"429_RATE_LIMIT (Retry-After: {last_retry_after}s)")
                        continue
                    else:
                        last_error_status = int(resp.status_code or 0)
                        resp.close()
                        resp = None
                except Exception as ex:
                    if resp:
                        try:
                            resp.close()
                        except Exception:
                            pass
                        resp = None
                    logger.debug(f"  ↪ Mirror connect error on {attempt_url}: {ex}", category="file")
                    continue

            if resp and resp.status_code in (200, 206, 416):
                break

        if resp is None:
            if saw_429:
                task.http_status = 429
                return None, mode, existing_size, req_headers, (False, f"429_RATE_LIMIT (Retry-After: {last_retry_after or '15'}s)")
            if saw_403 and not saw_404:
                task.http_status = 403
                msg = "403 Forbidden — content locked (membership tier access required)"
                logger.error(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return None, mode, existing_size, req_headers, (False, msg)
            if saw_404:
                task.http_status = 404
                if is_pawchive_task or "pawchive" in (task.url or "").lower():
                    msg = (
                        "Not available on Pawchive (HTTP 404) — this file isn't physically hosted "
                        "on Pawchive's servers (the post may not have been imported yet, or the file was removed)"
                    )
                else:
                    msg = "404 Not Found — file does not exist on any server mirror"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return None, mode, existing_size, req_headers, (False, msg)
            if last_error_status:
                task.http_status = last_error_status
                msg = f"HTTP {last_error_status}"
                logger.warning(f"  ✖ {task.filename}: {msg}", category="file", details=self._task_context(task))
                return None, mode, existing_size, req_headers, (False, msg)
            return None, mode, existing_size, req_headers, (False, "Failed to connect to any file server")

        return resp, mode, existing_size, req_headers, None
