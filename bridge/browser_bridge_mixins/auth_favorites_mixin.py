"""
BrowserBridge Provider Authentication, Favorites & Watchlist Actions Mixin
Decomposed from bridge/browser_bridge.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Slot

from bridge.browser_bridge_mixins.signals_mixin import BrowserSignalsMixin
from core.browser_providers import browser_registry
from core.logger import logger


class BrowserAuthFavoritesMixin(BrowserSignalsMixin):
    """Handles per-provider login/cookies, favorite artist sync/toggle, and watchlist additions."""

    @Slot(result=bool)
    @Slot(str, result=bool)
    def isProviderLoggedIn(self, provider_id: str = "") -> bool:
        from core.auth_manager import auth_manager
        pid = (provider_id or self._active_provider or "").strip().lower()
        return auth_manager.is_logged_in(pid)

    @Slot()
    @Slot(str)
    def notifyProviderAuthChanged(self, provider_id: str = "") -> None:
        from core.auth_manager import auth_manager
        pid = (provider_id or self._active_provider or "").strip().lower()
        prov = browser_registry.get_provider(pid)
        if prov and hasattr(prov, "invalidate_favorite_cache"):
            prov.invalidate_favorite_cache()
        self.activeProviderAuthChanged.emit()
        if self._browser_mode == "online" and pid == self._active_provider:
            if auth_manager.is_logged_in(pid):
                self._auth_required = False
                self.loadingStateChanged.emit()
                if self._active_service == "favorites":
                    self.refresh(False)
                elif prov:
                    self._refresh_visible_favorite_badges(prov, pid)
            elif self._active_service == "favorites":
                self._creators_model.set_creators([])
                self._total_count = 0
                self._has_more = False
                self._auth_required = True
                self.paginationChanged.emit()
                self.loadingStateChanged.emit()

    def _sync_favorite_state(
        self,
        creator_key: str,
        provider_id: str,
        service: str,
        creator_id: str,
        is_favorited: bool,
    ) -> None:
        """Updates visible models and selectedCreator after a favorite toggle."""
        def _matches(item: Dict[str, Any]) -> bool:
            if creator_key and str(item.get("key") or "") == creator_key:
                return True
            return (
                str(item.get("provider_id") or "").lower() == provider_id
                and str(item.get("service") or "").lower() == service
                and str(item.get("creator_id") or "") == creator_id
            )

        recs = self._creators_model.items_list()
        if (
            not is_favorited
            and self._browser_mode == "online"
            and self._active_provider == provider_id
            and self._active_service == "favorites"
        ):
            filtered = [dict(it) for it in recs if not _matches(it)]
            if len(filtered) != len(recs):
                self._creators_model.set_creators(filtered)
                self._total_count = max(0, self._total_count - 1)
                self.paginationChanged.emit()
        else:
            changed = False
            updated: List[Dict[str, Any]] = []
            for it in recs:
                row = dict(it)
                if _matches(row):
                    prev = bool(row.get("is_favorited"))
                    if prev != is_favorited:
                        row["is_favorited"] = is_favorited
                        fav_cnt = row.get("favorited_count")
                        if isinstance(fav_cnt, int):
                            row["favorited_count"] = max(0, fav_cnt + (1 if is_favorited else -1))
                        changed = True
                updated.append(row)
            if changed:
                self._creators_model.set_creators(updated)

        if self._selected_creator and _matches(self._selected_creator):
            sel = dict(self._selected_creator)
            prev = bool(sel.get("is_favorited"))
            sel["is_favorited"] = is_favorited
            fav_cnt = sel.get("favorited_count")
            if isinstance(fav_cnt, int) and prev != is_favorited:
                sel["favorited_count"] = max(0, fav_cnt + (1 if is_favorited else -1))
            self._selected_creator = sel
            self.selectedCreatorChanged.emit()

    def _refresh_visible_favorite_badges(self, prov, pid: str) -> None:
        """Refreshes is_favorited badges on the currently loaded page without scrolling."""
        if not prov or not getattr(prov.capabilities(), "supports_favorites", False):
            return

        def _worker():
            try:
                fav_keys = prov.get_favorite_creator_keys()
            except Exception:
                fav_keys = None
            if fav_keys is None:
                return

            def _apply():
                recs = self._creators_model.items_list()
                changed = False
                updated: List[Dict[str, Any]] = []
                for it in recs:
                    row = dict(it)
                    if str(row.get("provider_id") or "").lower() == pid:
                        comp = (
                            str(row.get("service") or "").strip().lower(),
                            str(row.get("creator_id") or "").strip(),
                        )
                        val = comp in fav_keys
                        if bool(row.get("is_favorited")) != val:
                            row["is_favorited"] = val
                            changed = True
                    updated.append(row)
                if changed:
                    self._creators_model.set_creators(updated)
                if (
                    self._selected_creator
                    and str(self._selected_creator.get("provider_id") or "").lower() == pid
                ):
                    sel = dict(self._selected_creator)
                    comp = (
                        str(sel.get("service") or "").strip().lower(),
                        str(sel.get("creator_id") or "").strip(),
                    )
                    val = comp in fav_keys
                    if bool(sel.get("is_favorited")) != val:
                        sel["is_favorited"] = val
                        self._selected_creator = sel
                        self.selectedCreatorChanged.emit()

            self._callOnGui.emit(_apply)

        threading.Thread(target=_worker, daemon=True, name="BrowserFavSyncWorker").start()

    def _execute_favorite_toggle(
        self,
        prov,
        prov_id: str,
        service: str,
        creator_id: str,
        creator_key: str,
        creator_name: str,
        desired: bool,
        creator_map: Dict[str, Any],
        on_success=None,
    ) -> None:
        self._fav_toggle_gen += 1

        def _worker():
            res = prov.set_creator_favorite(service, creator_id, desired)
            if isinstance(res, dict):
                ok = bool(res.get("ok"))
                new_state = bool(res.get("is_favorited", desired))
                auth_req = bool(res.get("auth_required"))
                err = str(res.get("error") or "")
            else:
                ok, new_state, auth_req, err = res

            def _apply():
                if auth_req:
                    self._pending_favorite = dict(creator_map)
                    self.activeProviderAuthChanged.emit()
                    self.loginPromptRequested.emit(prov_id, "favorite_creator")
                    return
                if not ok:
                    self.toastRequested.emit(err or f"Could not update favorite for {creator_name}.", "error")
                    return
                self._sync_favorite_state(creator_key, prov_id, service, creator_id, new_state)
                site = prov.manifest.display_name
                if new_state:
                    self.toastRequested.emit(f"Added {creator_name} to {site} favorites.", "success")
                else:
                    self.toastRequested.emit(f"Removed {creator_name} from {site} favorites.", "info")
                if on_success:
                    on_success()

            self._callOnGui.emit(_apply)

        threading.Thread(target=_worker, daemon=True, name="BrowserFavoriteWorker").start()

    @Slot("QVariantMap")
    def toggleFavoriteCreator(self, creator_map: Dict[str, Any]) -> None:
        """Toggles a creator's account favorite/bookmark state on Pawchive or Cum.st."""
        if not creator_map or not isinstance(creator_map, dict):
            return
        if self._browser_mode == "local":
            self.toastRequested.emit("Favorites sync applies to online creators.", "info")
            return

        prov_id = str(creator_map.get("provider_id") or self._active_provider or "").strip().lower()
        service = str(creator_map.get("service") or "").strip().lower()
        creator_id = str(creator_map.get("creator_id") or creator_map.get("id") or "").strip()
        creator_name = str(creator_map.get("name") or creator_id or "Creator").strip()
        creator_key = str(creator_map.get("key") or f"{prov_id}:{service}:{creator_id}")

        prov = browser_registry.get_provider(prov_id)
        if not prov or not getattr(prov.capabilities(), "supports_favorites", False):
            self.toastRequested.emit("Account favorites are not supported on this site.", "info")
            return
        if not service or service == "all" or not creator_id:
            self.toastRequested.emit("Missing creator service or ID.", "warning")
            return

        desired = not bool(creator_map.get("is_favorited"))

        from core.auth_manager import auth_manager
        if not auth_manager.is_logged_in(prov_id):
            self._pending_favorite = dict(creator_map) if desired else None
            self.loginPromptRequested.emit(prov_id, "favorite_creator")
            return

        self._execute_favorite_toggle(
            prov, prov_id, service, creator_id, creator_key, creator_name, desired, dict(creator_map)
        )

    def _finish_provider_login(self, pid: str, ok: bool, msg: str) -> None:
        self._is_logging_in_provider = False
        prov = browser_registry.get_provider(pid)
        if ok and prov and hasattr(prov, "invalidate_favorite_cache"):
            prov.invalidate_favorite_cache()
        self.activeProviderAuthChanged.emit()
        self.providerLoginFinished.emit(pid, ok, msg)
        if not ok:
            self.toastRequested.emit(msg or f"Login failed for {pid}.", "error")
            return

        if pid == self._active_provider:
            self._auth_required = False
            self.loadingStateChanged.emit()

        self.toastRequested.emit(msg or f"Logged in to {pid}.", "success")

        pending = getattr(self, "_pending_favorite", None)
        self._pending_favorite = None
        if pending and str(pending.get("provider_id") or self._active_provider).strip().lower() == pid:
            svc = str(pending.get("service") or "").strip().lower()
            cid = str(pending.get("creator_id") or pending.get("id") or "").strip()
            cname = str(pending.get("name") or cid or "Creator").strip()
            ckey = str(pending.get("key") or f"{pid}:{svc}:{cid}")
            if prov and svc and cid:
                def _after_fav():
                    if self._browser_mode == "online" and self._active_provider == pid:
                        if self._active_service == "favorites":
                            self.refresh(False)
                        else:
                            self._refresh_visible_favorite_badges(prov, pid)

                self._execute_favorite_toggle(
                    prov, pid, svc, cid, ckey, cname, True, pending, on_success=_after_fav
                )
                return

        if self._browser_mode == "online" and self._active_provider == pid:
            if self._active_service == "favorites":
                self.refresh(False)
            elif prov:
                self._refresh_visible_favorite_badges(prov, pid)

    @Slot(str, str, str)
    def loginProvider(self, provider_id: str, username: str, password: str) -> None:
        """Logs into a provider using account username and password."""
        pid = (provider_id or self._active_provider or "").strip().lower()
        user = (username or "").strip()
        pw = password or ""
        if not pid or not user or not pw:
            self.providerLoginFinished.emit(pid, False, "Please enter both username and password.")
            self.toastRequested.emit("Please enter both username and password.", "warning")
            return

        self._is_logging_in_provider = True
        self.activeProviderAuthChanged.emit()

        def _worker():
            from core.auth_manager import auth_manager
            try:
                ok, msg, _ = auth_manager.login_with_credentials(pid, user, pw)
            except Exception as e:
                ok, msg = False, str(e)
            self._callOnGui.emit(lambda: self._finish_provider_login(pid, bool(ok), str(msg or "")))

        threading.Thread(target=_worker, daemon=True, name="BrowserLoginWorker").start()

    def _apply_and_validate_cookie(self, pid: str, cookie_str: str, source_name: str = "") -> None:
        """Applies a candidate cookie string, validates the session, and rolls back on failure."""
        from core.auth_manager import auth_manager

        prev_cookie = auth_manager.get_credential(pid, "cookie")
        prev_user = auth_manager.get_credential(pid, "username")
        try:
            auth_manager.set_credential(pid, {"cookie": cookie_str})
            ok, msg, _ = auth_manager.validate_session(pid)
            if not ok:
                if prev_cookie:
                    restore = {"cookie": prev_cookie}
                    if prev_user:
                        restore["username"] = prev_user
                    auth_manager.set_credential(pid, restore)
                else:
                    auth_manager.clear_credential(pid)
                err_msg = msg or f"Session cookie is not logged in on {pid}."
                self._callOnGui.emit(lambda: self._finish_provider_login(pid, False, err_msg))
                return
            default_ok = f"Imported active session from {source_name}." if source_name else f"Session verified for {pid}."
            ok_msg = msg or default_ok
            self._callOnGui.emit(lambda: self._finish_provider_login(pid, True, ok_msg))
        except Exception as e:
            err_s = str(e)
            self._callOnGui.emit(lambda: self._finish_provider_login(pid, False, err_s))

    @Slot(str)
    @Slot(str, str)
    def importProviderCookies(self, provider_id: str, browser_id: str = "") -> None:
        """Imports browser session cookies for the given provider and validates the session."""
        pid = (provider_id or self._active_provider or "").strip().lower()
        if not pid:
            return
        self._is_logging_in_provider = True
        self.activeProviderAuthChanged.emit()

        def _worker():
            from services.cookie_importer import browser_cookie_importer

            try:
                res = browser_cookie_importer.import_auto_detect(
                    preferred_browser=(browser_id or "").strip() or None
                )
                cookie_str = str(res.get("cookie_string") or "").strip()
                if not cookie_str:
                    self._callOnGui.emit(
                        lambda: self._finish_provider_login(pid, False, "No active session cookies found in browser.")
                    )
                    return
                bname = str(res.get("browser_name") or "browser")
                self._apply_and_validate_cookie(pid, cookie_str, source_name=bname)
            except Exception as e:
                err_s = str(e)
                self._callOnGui.emit(lambda: self._finish_provider_login(pid, False, err_s))

        threading.Thread(target=_worker, daemon=True, name="BrowserCookieImportWorker").start()

    @Slot(str, str)
    def saveProviderCookie(self, provider_id: str, cookie_str: str) -> None:
        """Saves a manually pasted Cookie header for the provider and validates the session."""
        pid = (provider_id or self._active_provider or "").strip().lower()
        raw = (cookie_str or "").strip()
        if raw.lower().startswith("cookie:"):
            raw = raw[7:].strip()
        if not pid or not raw:
            self.providerLoginFinished.emit(pid, False, "Please paste a valid cookie string.")
            self.toastRequested.emit("Please paste a valid cookie string.", "warning")
            return

        self._is_logging_in_provider = True
        self.activeProviderAuthChanged.emit()

        def _worker():
            self._apply_and_validate_cookie(pid, raw)

        threading.Thread(target=_worker, daemon=True, name="BrowserSaveCookieWorker").start()

    @Slot(str)
    @Slot()
    def logoutProvider(self, provider_id: str = "") -> None:
        """Clears stored credentials for the provider and resets its favorite indicators."""
        from core.auth_manager import auth_manager

        pid = (provider_id or self._active_provider or "").strip().lower()
        if not pid:
            return
        auth_manager.clear_credential(pid)
        prov = browser_registry.get_provider(pid)
        if prov and hasattr(prov, "invalidate_favorite_cache"):
            prov.invalidate_favorite_cache()

        pending = getattr(self, "_pending_favorite", None)
        if pending and str(pending.get("provider_id") or "").lower() == pid:
            self._pending_favorite = None

        if self._browser_mode == "online" and self._active_provider == pid and self._active_service == "favorites":
            self._creators_model.set_creators([])
            self._total_count = 0
            self._has_more = False
            self._auth_required = True
            self._error_message = f"Log in to {pid} to view your favorited creators."
            self._status_text = self._error_message
            self.paginationChanged.emit()
            self.loadingStateChanged.emit()
        else:
            recs = self._creators_model.items_list()
            changed = False
            updated: List[Dict[str, Any]] = []
            for it in recs:
                row = dict(it)
                if str(row.get("provider_id") or "").lower() == pid and row.get("is_favorited"):
                    row["is_favorited"] = False
                    changed = True
                updated.append(row)
            if changed:
                self._creators_model.set_creators(updated)

        if self._selected_creator and str(self._selected_creator.get("provider_id") or "").lower() == pid:
            sel = dict(self._selected_creator)
            if sel.get("is_favorited"):
                sel["is_favorited"] = False
                self._selected_creator = sel
                self.selectedCreatorChanged.emit()

        self.activeProviderAuthChanged.emit()
        self.toastRequested.emit(f"Signed out of {pid}.", "info")

    @Slot(result=int)
    def addMarkedCreatorsToWatchlist(self) -> int:
        """Adds all marked creators (or the parent creators of marked posts) to WatchlistManager."""
        if not self._app_bridge or not getattr(self._app_bridge, "_watchlist_manager", None):
            return 0
        wm = self._app_bridge._watchlist_manager
        added = 0
        for it in self._mark_manager.all_items():
            svc = str(it.get("service") or "").strip().lower()
            cid = str(it.get("creator_id") or "").strip()
            cname = str(it.get("creator_name") or cid).strip()
            prov_id = str(it.get("provider_id") or "cumst")
            prov = browser_registry.get_provider(prov_id)
            domain = prov.base_domain if prov else ("cum.st" if prov_id == "cumst" else "pawchive.pw")
            url = prov.build_creator_url(svc, cid) if prov else str(it.get("url") or "")
            if svc and cid:
                wm.add_entry(
                    url=url,
                    creator_name=cname,
                    user_id=cid,
                    service=svc,
                    domain=domain,
                    download_dir="",
                )
                added += 1
        if added > 0:
            if getattr(self._app_bridge, "_watchlist_model", None):
                self._app_bridge._watchlist_model.refresh()
            self._app_bridge.watchlistChanged.emit()
            self.toastRequested.emit(f"Added {added} creator(s) to Watchlist.", "success")
        return added
