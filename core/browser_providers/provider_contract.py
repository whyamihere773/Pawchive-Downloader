"""
Abstract BaseBrowserProvider Contract
Decomposed from core/browser_providers/base.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from core.browser_providers.dto import BrowserPageResult, ProviderCapabilities
from core.providers import cookie_for_url, is_disabled


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
