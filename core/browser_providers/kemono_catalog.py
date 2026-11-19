"""
Reusable SQLite-Cached Kemono-Style Catalog Provider (`KemonoStyleCatalogProvider`)
Decomposed from core/browser_providers/base.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
import sqlite3
import threading
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

from core.browser_providers.dto import (
    BrowserPageResult,
    ProviderCapabilities,
    build_creator_card_dto,
)
from core.browser_providers.kemono_posts_mixin import KemonoCatalogPostsMixin
from core.browser_providers.provider_contract import BaseBrowserProvider
from core.logger import logger


class KemonoStyleCatalogProvider(KemonoCatalogPostsMixin, BaseBrowserProvider):
    """
    Reusable base provider for any site using the Kemono-compatible `/api/v1/creators`
    and `/api/v1/{service}/user/{id}/posts` REST structure (such as Pawchive and future mirrors).

    Automatically caches `/api/v1/creators` into a local SQLite database (`browser_cache.db`)
    so searching, filtering by service, and sorting 100k+ creators takes <5ms locally.
    """

    catalog_ttl_seconds: int = 3600 * 6  # Refresh creator catalog every 6 hours
    default_services: Tuple[Tuple[str, str], ...] = (
        ("all", "All Services"),
        ("patreon", "Patreon"),
        ("fanbox", "Pixiv Fanbox"),
        ("fantia", "Fantia"),
        ("boosty", "Boosty"),
        ("gumroad", "Gumroad"),
        ("subscribestar", "SubscribeStar"),
        ("dlsite", "DLsite"),
    )
    default_accent_color: str = "#A78BFA"
    default_badge_icon: str = "🐾"
    default_supports_favorites: bool = False

    def __init__(self, cache_db_path: Optional[str] = None):
        super().__init__()
        if not cache_db_path:
            from core.path_utils import get_config_dir
            cache_db_path = os.path.join(get_config_dir(), "browser_cache.db")
        self.cache_db_path = cache_db_path
        self._db_lock = threading.RLock()
        self._sync_lock = threading.Lock()
        self._ensure_tables()

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_creator_search=True,
            supports_global_post_search=True,
            supports_creator_post_search=True,
            supports_tag_filter=False,
            supports_service_filter=True,
            supports_dms=True,
            supports_favorites=self.default_supports_favorites,
            requires_cookie_auth=False,
            page_size=50,
            services=self.default_services,
            sort_options=(
                ("popular", "Most Favorited"),
                ("updated", "Recently Updated"),
                ("indexed", "Newly Indexed"),
                ("name", "Name (A–Z)"),
            ),
            accent_color=self.default_accent_color,
            badge_icon=self.default_badge_icon,
        )

    @contextmanager
    def _conn(self):
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path, timeout=15.0)
        try:
            conn.execute("PRAGMA synchronous=NORMAL;")
            yield conn
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_tables(self):
        try:
            with self._db_lock, self._conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS catalog_creators (
                        provider_id TEXT NOT NULL,
                        service TEXT NOT NULL,
                        creator_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        name_lower TEXT NOT NULL,
                        favorited INTEGER DEFAULT 0,
                        indexed INTEGER DEFAULT 0,
                        updated INTEGER DEFAULT 0,
                        ever_imported INTEGER DEFAULT 1,
                        PRIMARY KEY (provider_id, service, creator_id)
                    );
                    """
                )
                cols = {r[1] for r in conn.execute("PRAGMA table_info(catalog_creators);").fetchall()}
                migrated_ever_imported = "ever_imported" not in cols
                if migrated_ever_imported:
                    conn.execute("ALTER TABLE catalog_creators ADD COLUMN ever_imported INTEGER DEFAULT 1;")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cat_prov_svc ON catalog_creators(provider_id, service);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cat_prov_fav ON catalog_creators(provider_id, favorited DESC);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cat_prov_upd ON catalog_creators(provider_id, updated DESC);"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS catalog_meta (
                        provider_id TEXT PRIMARY KEY,
                        synced_at REAL DEFAULT 0,
                        total_count INTEGER DEFAULT 0
                    );
                    """
                )
                if migrated_ever_imported:
                    conn.execute("UPDATE catalog_meta SET synced_at = 0;")
        except Exception as e:
            logger.debug(f"[BrowserCatalog] Table init warning: {e}", category="api")

    def _needs_catalog_sync(self) -> bool:
        try:
            with self._db_lock, self._conn() as conn:
                row = conn.execute(
                    "SELECT synced_at, total_count FROM catalog_meta WHERE provider_id = ?;",
                    (self.provider_id,),
                ).fetchone()
                if not row or int(row[1] or 0) == 0:
                    return True
                return (time.time() - float(row[0] or 0)) > self.catalog_ttl_seconds
        except Exception:
            return True

    def ensure_catalog_synced(self, force: bool = False, cancel_event: Optional[threading.Event] = None) -> bool:
        if not force and not self._needs_catalog_sync():
            return True
        if not self._sync_lock.acquire(blocking=True, timeout=30.0):
            return False
        try:
            if not force and not self._needs_catalog_sync():
                return True
            url = f"https://{self.base_domain}/api/v1/creators"
            resp = self._session.get(url, headers=self._request_headers(url), timeout=25)
            if resp.status_code != 200:
                logger.warning(f"[{self.display_name}] Catalog fetch returned HTTP {resp.status_code}", category="api")
                return False
            data = resp.json()
            if not isinstance(data, list):
                return False
            rows = []
            for item in data:
                if cancel_event and cancel_event.is_set():
                    return False
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("id") or "").strip()
                svc = str(item.get("service") or "").strip().lower()
                name = str(item.get("name") or cid).strip()
                if not cid or not svc:
                    continue
                fav = int(item.get("favorited") or 0)
                idx = int(item.get("indexed") or 0)
                upd = int(item.get("updated") or 0)
                ever_imp = 0 if (item.get("ever_imported") is False) else 1
                rows.append((self.provider_id, svc, cid, name, name.lower(), fav, idx, upd, ever_imp))

            with self._db_lock, self._conn() as conn:
                conn.execute("DELETE FROM catalog_creators WHERE provider_id = ?;", (self.provider_id,))
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO catalog_creators
                    (provider_id, service, creator_id, name, name_lower, favorited, indexed, updated, ever_imported)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    rows,
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO catalog_meta (provider_id, synced_at, total_count)
                    VALUES (?, ?, ?);
                    """,
                    (self.provider_id, time.time(), len(rows)),
                )
            logger.info(f"[{self.display_name}] Indexed {len(rows)} creators into local catalog cache.", category="api")
            return True
        except Exception as e:
            logger.warning(f"[{self.display_name}] Catalog sync failed: {e}", category="api")
            return False
        finally:
            self._sync_lock.release()

    def resolve_avatar_url(self, service: str, creator_id: str) -> str:
        return f"https://{self.base_domain}/icons/{service}/{creator_id}"

    def resolve_banner_url(self, service: str, creator_id: str) -> str:
        return f"https://{self.base_domain}/banners/{service}/{creator_id}"

    def is_creator_unimported_cached(self, service: str, creator_id: str) -> bool:
        """Returns True if the cached catalog explicitly flags this creator as never imported."""
        svc = (service or "").strip().lower()
        cid = str(creator_id or "").strip()
        if not svc or not cid or not os.path.isfile(self.cache_db_path):
            return False
        try:
            with self._db_lock, self._conn() as conn:
                row = conn.execute(
                    """
                    SELECT COALESCE(ever_imported, 1)
                    FROM catalog_creators
                    WHERE provider_id = ? AND service = ? AND creator_id = ?;
                    """,
                    (self.provider_id, svc, cid),
                ).fetchone()
                return bool(row is not None and int(row[0] if row[0] is not None else 1) == 0)
        except Exception:
            return False

    @staticmethod
    def _parse_ts_sort_and_date(val: Any) -> Tuple[float, str]:
        if val is None or val == "":
            return 0.0, ""
        if isinstance(val, (int, float)):
            ts = float(val)
            if ts > 1e12:
                ts /= 1000.0
            if ts > 0:
                try:
                    return ts, time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
                except Exception:
                    return ts, ""
            return 0.0, ""
        s = str(val).strip()
        if s.isdigit() and 9 <= len(s) <= 13:
            ts = float(int(s))
            if ts > 1e12:
                ts /= 1000.0
            try:
                return ts, time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
            except Exception:
                return ts, ""
        return 0.0, s[:10]

    def _fetch_account_favorite_creators(
        self, cookie: Optional[str] = None, timeout: int = 20
    ) -> Tuple[Optional[List[Dict[str, Any]]], bool, str]:
        """Fetches raw favorited creator dicts from `/api/v1/account/favorites?type=artist`."""
        auth_cookie = cookie if cookie is not None else self._current_auth_cookie()
        if not auth_cookie:
            return None, True, f"Log in to {self.display_name} to view your favorited creators."
        url = f"https://{self.base_domain}/api/v1/account/favorites?type=artist"
        headers = {
            **self._request_headers(url),
            "Cookie": auth_cookie,
            "Accept": "application/json, text/css, */*;q=0.1",
        }
        try:
            resp = self._session.get(url, headers=headers, timeout=timeout)
            if resp.status_code in (401, 403):
                return None, True, f"Session expired or unauthorized. Please log in to {self.display_name}."
            if resp.status_code != 200:
                return None, False, f"HTTP {resp.status_code}"
            payload = resp.json()
            if isinstance(payload, list):
                raw_list = payload
            elif isinstance(payload, dict):
                raw_list = payload.get("artists") or payload.get("favorites") or payload.get("creators") or []
            else:
                raw_list = []
            items = [it for it in (raw_list or []) if isinstance(it, dict)]
            keys = {
                (str(it.get("service") or "").strip().lower(), str(it.get("id") or it.get("creator_id") or "").strip())
                for it in items
                if (it.get("service") and (it.get("id") or it.get("creator_id")))
            }
            self._set_cached_fav_keys(keys, auth_cookie)
            return items, False, ""
        except Exception as e:
            return None, False, str(e)

    def get_favorite_creator_keys(self, force_refresh: bool = False) -> Optional[Set[Tuple[str, str]]]:
        if not self.default_supports_favorites:
            return None

        def _load(cookie: str) -> Optional[Set[Tuple[str, str]]]:
            items, auth_req, _err = self._fetch_account_favorite_creators(cookie=cookie, timeout=12)
            if items is None:
                return None
            return {
                (str(it.get("service") or "").strip().lower(), str(it.get("id") or it.get("creator_id") or "").strip())
                for it in items
                if (it.get("service") and (it.get("id") or it.get("creator_id")))
            }

        return self._get_cached_fav_keys(_load, force_refresh=force_refresh)

    def set_creator_favorite(self, service: str, creator_id: str, favorite: bool) -> Dict[str, Any]:
        svc = (service or "").strip().lower()
        cid = str(creator_id or "").strip()
        if not self.default_supports_favorites:
            return super().set_creator_favorite(svc, cid, favorite)
        if not svc or not cid:
            return {"ok": False, "is_favorited": not bool(favorite), "auth_required": False, "error": "Invalid creator identifier."}
        cookie = self._current_auth_cookie()
        if not cookie:
            return {
                "ok": False,
                "is_favorited": not bool(favorite),
                "auth_required": True,
                "error": f"Log in to {self.display_name} to save favorite creators to your account.",
            }
        url = f"https://{self.base_domain}/api/v1/favorites/creator/{urllib.parse.quote(svc, safe='')}/{urllib.parse.quote(cid, safe='')}"
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
                    "error": f"Session expired or unauthorized (HTTP {resp.status_code}). Please log in to {self.display_name}.",
                }
            if not resp.ok:
                return {
                    "ok": False,
                    "is_favorited": not bool(favorite),
                    "auth_required": False,
                    "error": f"HTTP {resp.status_code}",
                }
            self._update_cached_fav_key(svc, cid, bool(favorite), cookie=cookie)
            delta = 1 if favorite else -1
            try:
                with self._db_lock, self._conn() as conn:
                    conn.execute(
                        """
                        UPDATE catalog_creators
                        SET favorited = MAX(0, COALESCE(favorited, 0) + ?)
                        WHERE provider_id = ? AND service = ? AND creator_id = ?;
                        """,
                        (delta, self.provider_id, svc, cid),
                    )
            except Exception:
                pass
            return {"ok": True, "is_favorited": bool(favorite), "auth_required": False, "error": ""}
        except Exception as e:
            return {
                "ok": False,
                "is_favorited": not bool(favorite),
                "auth_required": False,
                "error": str(e),
            }

    def _list_favorite_creators(
        self,
        query: str = "",
        sort: str = "popular",
        offset: int = 0,
        limit: int = 50,
        cancel_event: Optional[threading.Event] = None,
    ) -> BrowserPageResult:
        raw_items, auth_req, err = self._fetch_account_favorite_creators(timeout=20)
        if auth_req:
            self.invalidate_favorite_cache()
            return BrowserPageResult(error=err, auth_required=True)
        if raw_items is None:
            return BrowserPageResult(error=err or f"Could not load favorited creators from {self.display_name}.")

        # Enrich missing fields from local catalog cache by primary key
        catalog_meta_by_key: Dict[Tuple[str, str], Tuple[str, int, int, int, int]] = {}
        try:
            with self._db_lock, self._conn() as conn:
                for it in raw_items:
                    svc = str(it.get("service") or "").strip().lower()
                    cid = str(it.get("id") or it.get("creator_id") or "").strip()
                    if not svc or not cid:
                        continue
                    row = conn.execute(
                        """
                        SELECT name, favorited, indexed, updated, COALESCE(ever_imported, 1)
                        FROM catalog_creators
                        WHERE provider_id = ? AND service = ? AND creator_id = ?;
                        """,
                        (self.provider_id, svc, cid),
                    ).fetchone()
                    if row:
                        catalog_meta_by_key[(svc, cid)] = row
        except Exception:
            pass

        clean_q = (query or "").strip().lower()
        enriched = []
        for it in raw_items:
            if cancel_event and cancel_event.is_set():
                break
            svc = str(it.get("service") or "").strip().lower()
            cid = str(it.get("id") or it.get("creator_id") or "").strip()
            if not svc or not cid:
                continue
            cached_row = catalog_meta_by_key.get((svc, cid))
            name = str(it.get("name") or (cached_row[0] if cached_row else "") or cid).strip()
            fav_cnt = int(it.get("favorited") if it.get("favorited") is not None else (cached_row[1] if cached_row else 0))
            idx_val = it.get("indexed") if it.get("indexed") is not None else (cached_row[2] if cached_row else 0)
            upd_val = it.get("updated") if it.get("updated") is not None else (cached_row[3] if cached_row else 0)
            if "ever_imported" in it:
                is_unimp = it.get("ever_imported") is False
            elif cached_row is not None:
                is_unimp = int(cached_row[4] if cached_row[4] is not None else 1) == 0
            else:
                is_unimp = False

            if clean_q and clean_q not in name.lower() and clean_q not in cid.lower() and clean_q not in svc:
                continue

            upd_ts, upd_str = self._parse_ts_sort_and_date(upd_val)
            idx_ts, _ = self._parse_ts_sort_and_date(idx_val)
            dto = build_creator_card_dto(
                provider_id=self.provider_id,
                service=svc,
                creator_id=cid,
                name=name,
                url=self.build_creator_url(svc, cid),
                avatar_url=self.resolve_avatar_url(svc, cid),
                banner_url=self.resolve_banner_url(svc, cid),
                favorited_count=fav_cnt,
                updated_at=upd_str,
                is_unimported=is_unimp,
                is_favorited=True,
            )
            enriched.append((fav_cnt, upd_ts, idx_ts, name.lower(), dto))

        if sort == "updated":
            enriched.sort(key=lambda r: (r[1], r[0]), reverse=True)
        elif sort == "indexed":
            enriched.sort(key=lambda r: (r[2], r[0]), reverse=True)
        elif sort == "name":
            enriched.sort(key=lambda r: r[3])
        else:
            enriched.sort(key=lambda r: (r[0], r[1]), reverse=True)

        total = len(enriched)
        start = max(0, int(offset or 0))
        end = start + max(1, int(limit or 50))
        items = [r[4] for r in enriched[start:end]]
        return BrowserPageResult(
            items=items,
            total=total,
            offset=start,
            page_size=limit,
            has_more=(start + len(items)) < total,
        )

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
        clean_q = (query or "").strip().lower()
        clean_svc = (service or "all").strip().lower()
        if clean_svc == "favorites":
            return self._list_favorite_creators(
                query=clean_q, sort=sort, offset=offset, limit=limit, cancel_event=cancel_event
            )
        self.ensure_catalog_synced(force=False, cancel_event=cancel_event)

        where_clauses = ["provider_id = ?"]
        params: List[Any] = [self.provider_id]
        if clean_svc and clean_svc != "all":
            where_clauses.append("service = ?")
            params.append(clean_svc)
        if clean_q:
            where_clauses.append("(name_lower LIKE ? OR LOWER(creator_id) LIKE ?)")
            like_q = f"%{clean_q}%"
            params.extend([like_q, like_q])

        order_sql = "favorited DESC, updated DESC"
        if sort == "updated":
            order_sql = "updated DESC, favorited DESC"
        elif sort == "indexed":
            order_sql = "indexed DESC, favorited DESC"
        elif sort == "name":
            order_sql = "name_lower ASC"

        where_str = " AND ".join(where_clauses)
        try:
            with self._db_lock, self._conn() as conn:
                total_row = conn.execute(
                    f"SELECT COUNT(*) FROM catalog_creators WHERE {where_str};",
                    params,
                ).fetchone()
                total = int(total_row[0] or 0) if total_row else 0
                rows = conn.execute(
                    f"""
                    SELECT service, creator_id, name, favorited, indexed, updated, COALESCE(ever_imported, 1)
                    FROM catalog_creators
                    WHERE {where_str}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?;
                    """,
                    params + [int(limit), int(offset)],
                ).fetchall()

            fav_keys: Set[Tuple[str, str]] = set()
            if self.default_supports_favorites and self._current_auth_cookie():
                fav_keys = self.get_favorite_creator_keys() or set()

            items = []
            for svc, cid, name, fav, idx, upd, ever_imp in rows:
                _, upd_str = self._parse_ts_sort_and_date(upd)
                items.append(
                    build_creator_card_dto(
                        provider_id=self.provider_id,
                        service=svc,
                        creator_id=cid,
                        name=name,
                        url=self.build_creator_url(svc, cid),
                        avatar_url=self.resolve_avatar_url(svc, cid),
                        banner_url=self.resolve_banner_url(svc, cid),
                        favorited_count=int(fav or 0),
                        updated_at=upd_str,
                        is_unimported=(int(ever_imp if ever_imp is not None else 1) == 0),
                        is_favorited=((str(svc or "").strip().lower(), str(cid or "").strip()) in fav_keys),
                    )
                )
            return BrowserPageResult(
                items=items,
                total=total,
                offset=offset,
                page_size=limit,
                has_more=(offset + len(items)) < total,
            )
        except Exception as e:
            return BrowserPageResult(error=str(e))

