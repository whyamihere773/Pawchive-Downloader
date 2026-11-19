"""
BrowserBridge Catalog Refresh, Creator Profile, Post Detail & Media Streaming Mixin
Decomposed from bridge/browser_bridge.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import inspect
import threading
from typing import Any, Dict, List

from PySide6.QtCore import Slot

from bridge.browser_bridge_mixins.signals_mixin import BrowserSignalsMixin
from core.browser_providers import browser_registry
from core.local_library import LocalLibraryService
from core.logger import logger


class BrowserFetchPostsMixin(BrowserSignalsMixin):
    """Handles async catalog fetching, creator profiles, post details, and remote media proxying."""

    def _annotate_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Annotates creator/post dicts with `is_marked` and `is_on_disk` status."""
        out = []
        for it in items:
            copy = dict(it)
            copy["is_marked"] = self._mark_manager.has_key(copy.get("key", ""))
            if self._browser_mode == "online" and copy.get("item_type") == "creator":
                on_disk, local_posts, drives = self._local_library.is_creator_on_disk(
                    copy.get("service", ""),
                    copy.get("creator_id", ""),
                    copy.get("name", ""),
                )
                copy["is_on_disk"] = on_disk
                if on_disk:
                    copy["local_post_count"] = local_posts
                    copy["local_drives"] = drives
            out.append(copy)
        return out

    @Slot(bool)
    @Slot()
    def refresh(self, force_disk_rescan: bool = False) -> None:
        self._cancel_event.set()
        self._cancel_event = threading.Event()
        cancel = self._cancel_event

        self._req_gen += 1
        gen = self._req_gen

        self._is_loading = True
        self._error_message = ""
        self._auth_required = False
        self._status_text = "Scanning local drives…" if self._browser_mode == "local" else "Loading…"
        self.loadingStateChanged.emit()

        mode = self._browser_mode
        prov_id = self._active_provider
        svc = self._active_service
        sort_by = self._active_sort
        tag = self._active_tag
        drv = self._active_drive
        q = self._search_query
        target = self._search_target
        offset = self._offset

        def _worker():
            try:
                if mode == "local":
                    items, total = self._local_library.list_local_creators(
                        query=q,
                        service=svc,
                        drive_filter=drv,
                        sort=sort_by,
                        offset=offset,
                        limit=50,
                        force_refresh=force_disk_rescan,
                    )
                    annotated = self._annotate_items(items)
                    page_sz = 50
                    has_more = (offset + len(annotated)) < total
                    err = ""
                    auth_req = False
                else:
                    prov = browser_registry.get_provider(prov_id)
                    if not prov:
                        annotated, total, page_sz, has_more = [], 0, 50, False
                        err, auth_req = f"Provider '{prov_id}' is not available.", False
                    else:
                        page_sz = prov.capabilities().page_size
                        if target == "posts" and prov.capabilities().supports_global_post_search:
                            res = prov.search_global_posts(
                                query=q, service=svc, tag=tag, offset=offset, limit=page_sz, cancel_event=cancel
                            )
                        else:
                            res = prov.list_creators(
                                query=q, service=svc, tag=tag, sort=sort_by, offset=offset, limit=page_sz, cancel_event=cancel
                            )
                        annotated = self._annotate_items(res.items)
                        total = res.total
                        has_more = res.has_more
                        err = res.error
                        auth_req = res.auth_required
            except Exception as e:
                annotated, total, page_sz, has_more = [], 0, 50, False
                err, auth_req = str(e), False

            def _deliver():
                if gen != self._req_gen:
                    return
                self._page_size = page_sz
                self._total_count = total
                self._has_more = has_more
                self._error_message = err
                self._auth_required = auth_req
                self._is_loading = False
                if mode == "online" and target == "posts":
                    self._posts_model.set_creators(annotated)
                else:
                    self._creators_model.set_creators(annotated)
                self._status_text = err if err else f"Showing {len(annotated)} of {total:,} result(s)"
                self.paginationChanged.emit()
                self.loadingStateChanged.emit()
                if mode == "local":
                    self.localDrivesChanged.emit()
                else:
                    if getattr(self, "_last_auth_prov", None) != self._active_provider:
                        self._last_auth_prov = self._active_provider
                        self.activeProviderAuthChanged.emit()
                    if auth_req:
                        self.activeProviderAuthChanged.emit()
                        if self._active_service == "favorites":
                            self.loginPromptRequested.emit(self._active_provider, "favorites")

            self._callOnGui.emit(_deliver)

        threading.Thread(target=_worker, daemon=True, name="BrowserRefreshWorker").start()

    @Slot("QVariantMap")
    def openCreator(self, creator_map: Dict[str, Any]) -> None:
        if not creator_map or not isinstance(creator_map, dict):
            return
        self._selected_creator = dict(creator_map)
        self._creator_section = "posts"
        self._selected_post = {}
        self._creator_posts_offset = 0
        self._creator_posts_query = ""
        self._reset_new_posts_state()
        self.filterStateChanged.emit()
        self.selectedCreatorChanged.emit()
        self.selectedPostChanged.emit()
        self.loadCreatorPosts(0, "")

    @Slot(str)
    def setCreatorSection(self, section: str) -> None:
        clean = "dms" if (section or "").strip().lower() == "dms" else "posts"
        if self._creator_section == clean:
            return
        self._creator_section = clean
        self._selected_post = {}
        self._creator_posts_offset = 0
        self.filterStateChanged.emit()
        self.selectedPostChanged.emit()
        if self._selected_creator:
            self.loadCreatorPosts(0, self._creator_posts_query)

    @Slot()
    def queueAllCreatorDms(self) -> None:
        if not self._selected_creator:
            return
        prov, svc, cid = self._resolve_online_provider(self._selected_creator, self._get_creator_links())
        if not prov or not svc or svc == "local" or not cid:
            self.toastRequested.emit("No linked online creator available for DM download.", "warning")
            return
        dms_url = prov.build_dms_url(svc, cid)
        if not dms_url:
            self.toastRequested.emit(f"{prov.display_name} does not provide a DMs archive endpoint.", "warning")
            return
        if not self._app_bridge:
            self.toastRequested.emit("Downloader bridge is not connected.", "warning")
            return
        if hasattr(self._app_bridge, "enqueueBatchUrls"):
            self._app_bridge.enqueueBatchUrls([dms_url], True)
        else:
            self._app_bridge.currentUrl = dms_url
            self._app_bridge.startDownload()
        cname = str(self._selected_creator.get("name") or cid).strip()
        self.toastRequested.emit(f"Queued all DMs for '{cname}' in Downloader.", "success")

    @Slot()
    def closeCreator(self) -> None:
        self._req_gen += 1
        self._is_loading = False
        self._selected_creator = {}
        self._selected_post = {}
        self._reset_new_posts_state()
        self.selectedCreatorChanged.emit()
        self.selectedPostChanged.emit()
        self.loadingStateChanged.emit()
        if self._browser_mode == "online":
            first = self._creators_model.get(0) if self._creators_model.count > 0 else {}
            if not first or (first.get("provider_id") and first.get("provider_id") != self._active_provider):
                self.refresh(False)

    def _find_local_creator(self, service: str, creator_id: str, creator_name: str) -> Optional[Dict[str, Any]]:
        svc = (service or "").lower()
        cid = (creator_id or "").lower()
        cname = (creator_name or "").lower()
        items, _ = self._local_library.list_local_creators(force_refresh=False, limit=0)
        for c in items:
            if (cid and str(c.get("creator_id", "")).lower() == cid) or (cname and str(c.get("name", "")).lower() == cname):
                if not svc or str(c.get("service", "")).lower() in (svc, "local"):
                    return dict(c)
        return None

    @Slot("QVariantMap")
    def openCreatorInLocalMode(self, creator_map: Dict[str, Any]) -> None:
        """Switches to Local Mode and opens the matching on-disk creator immediately."""
        if not creator_map:
            return
        svc = str(creator_map.get("service") or "").lower()
        cid = str(creator_map.get("creator_id") or "").lower()
        cname = str(creator_map.get("name") or creator_map.get("creator_name") or "").lower()
        self._browser_mode = "local"
        self.browserModeChanged.emit()
        matched = self._find_local_creator(svc, cid, cname)
        if matched:
            self.openCreator(matched)
            return
        self.refresh(False)

    @Slot(int, str)
    @Slot(int)
    def loadCreatorPosts(self, offset: int = 0, query: str = "") -> None:
        if not self._selected_creator:
            return
        creator = dict(self._selected_creator)
        self._creator_posts_offset = max(0, int(offset or 0))
        self._creator_posts_query = (query or "").strip()

        self._req_gen += 1
        gen = self._req_gen
        fav_gen = self._fav_toggle_gen
        self._is_loading = True
        self._error_message = ""
        self._status_text = f"Loading posts for {creator.get('name', 'creator')}…"
        self.loadingStateChanged.emit()

        mode = self._browser_mode
        section = self._creator_section
        drv = self._active_drive
        off = self._creator_posts_offset
        q = self._creator_posts_query

        def _worker():
            try:
                fav_keys = None
                disk_summary = None
                if mode == "local":
                    posts, total = self._local_library.list_local_creator_posts(
                        creator_key=str(creator.get("key") or ""),
                        query=q,
                        drive_filter=drv,
                        offset=off,
                        limit=50,
                    )
                    annotated = self._annotate_items(posts)
                    has_more = (off + len(annotated)) < total
                    err = ""
                else:
                    prov = browser_registry.get_provider(str(creator.get("provider_id") or self._active_provider))
                    if not prov:
                        annotated, total, has_more, err = [], 0, False, "Provider not found"
                    else:
                        page_sz = prov.capabilities().page_size
                        if section == "dms":
                            res = prov.list_creator_dms(
                                service=str(creator.get("service") or ""),
                                creator_id=str(creator.get("creator_id") or ""),
                                creator_name=str(creator.get("name") or ""),
                                query=q,
                                offset=off,
                                limit=page_sz,
                            )
                        else:
                            res = prov.list_creator_posts(
                                service=str(creator.get("service") or ""),
                                creator_id=str(creator.get("creator_id") or ""),
                                creator_name=str(creator.get("name") or ""),
                                query=q,
                                offset=off,
                                limit=page_sz,
                            )
                        if off == 0 and getattr(prov.capabilities(), "supports_favorites", False):
                            try:
                                fav_keys = prov.get_favorite_creator_keys()
                            except Exception:
                                fav_keys = None
                        annotated = self._annotate_items(res.items)
                        # Online Mode: when the creator exists on disk, annotate each post as
                        # "complete" (green), "partial" (yellow), or "none" (not on disk)
                        disk_index = None
                        disk_summary = None
                        try:
                            disk_index = self._local_library.get_creator_post_disk_index(
                                str(creator.get("service") or ""),
                                str(creator.get("creator_id") or ""),
                                str(creator.get("name") or ""),
                            )
                        except Exception as dex:
                            logger.debug(f"[BrowserBridge] Post disk status scan skipped: {dex}", category="archive")
                        if disk_index and disk_index.get("creator_on_disk"):
                            cnt_complete = 0
                            cnt_partial = 0
                            cnt_missing = 0
                            for p_item in annotated:
                                info = LocalLibraryService.evaluate_online_post_disk_status(p_item, disk_index)
                                p_item.update(info)
                                st = info.get("disk_status")
                                if st == "complete":
                                    cnt_complete += 1
                                elif st == "partial":
                                    cnt_partial += 1
                                else:
                                    cnt_missing += 1
                            disk_summary = {
                                "is_on_disk": True,
                                "local_drives": list(disk_index.get("local_drives") or []),
                                "page_disk_complete": cnt_complete,
                                "page_disk_partial": cnt_partial,
                                "page_disk_missing": cnt_missing,
                            }
                        total = res.total
                        has_more = res.has_more
                        err = res.error
            except Exception as e:
                annotated, total, has_more, err, fav_keys, disk_summary = [], 0, False, str(e), None, None

            def _deliver():
                if gen != self._req_gen:
                    return
                if self._selected_creator:
                    sel_key = str(self._selected_creator.get("key") or "")
                    if sel_key and sel_key == str(creator.get("key") or ""):
                        updates = {}
                        if fav_keys is not None and fav_gen == self._fav_toggle_gen:
                            svc_k = str(self._selected_creator.get("service") or "").strip().lower()
                            cid_k = str(self._selected_creator.get("creator_id") or "").strip()
                            updates["is_favorited"] = (svc_k, cid_k) in fav_keys
                        if mode != "local":
                            if disk_summary is not None:
                                updates.update(disk_summary)
                            else:
                                updates["page_disk_complete"] = 0
                                updates["page_disk_partial"] = 0
                                updates["page_disk_missing"] = 0
                        if updates:
                            self._selected_creator = {**self._selected_creator, **updates}
                self._posts_model.set_creators(annotated)
                self._creator_posts_total = total
                self._creator_posts_has_more = has_more
                self._error_message = err
                self._is_loading = False
                unit = "DM(s)" if (mode != "local" and section == "dms") else "post(s)"
                self._status_text = err if err else f"Loaded {len(annotated)} of {total:,} {unit}"
                self.selectedCreatorChanged.emit()
                self.loadingStateChanged.emit()

            self._callOnGui.emit(_deliver)

        threading.Thread(target=_worker, daemon=True, name="BrowserCreatorPostsWorker").start()

    @Slot("QVariantMap")
    def openPostDetail(self, post_map: Dict[str, Any]) -> None:
        if not post_map or not isinstance(post_map, dict):
            return
        self._selected_post = dict(post_map)
        self.selectedPostChanged.emit()

        if self._browser_mode == "online" and not self._selected_post.get("content_full"):
            prov = browser_registry.get_provider(str(post_map.get("provider_id") or self._active_provider))
            if prov:
                svc = str(post_map.get("service") or "")
                cid = str(post_map.get("creator_id") or "")
                pid = str(post_map.get("post_id") or "")
                cname = str(post_map.get("creator_name") or "")
                key = str(post_map.get("key") or "")
                is_dm_item = bool(post_map.get("is_dm"))

                def _fetch_detail():
                    try:
                        sig = inspect.signature(prov.get_post_detail)
                        if "is_dm" in sig.parameters:
                            detail = prov.get_post_detail(svc, cid, pid, cname, is_dm=is_dm_item)
                        else:
                            detail = prov.get_post_detail(svc, cid, pid, cname)
                    except TypeError:
                        detail = prov.get_post_detail(svc, cid, pid, cname)
                    if not detail:
                        return

                    def _apply():
                        if self._selected_post.get("key") == key:
                            detail["is_marked"] = self._mark_manager.has_key(key)
                            # Preserve / refine local disk status when full attachments arrive
                            prev_status = str(self._selected_post.get("disk_status") or "none")
                            prev_local = int(self._selected_post.get("local_file_count") or 0)
                            if prev_status in ("complete", "partial"):
                                full_expected = max(len(detail.get("attachments") or []), int(detail.get("file_count") or 0))
                                if full_expected > 0:
                                    refined = "complete" if prev_local >= full_expected else ("partial" if prev_local > 0 else "none")
                                else:
                                    refined = prev_status
                                detail["disk_status"] = refined
                                detail["is_on_disk"] = refined in ("complete", "partial")
                                detail["local_file_count"] = prev_local
                                detail["expected_file_count"] = full_expected
                                detail["local_folder"] = self._selected_post.get("local_folder", "")
                                detail["local_drives"] = list(self._selected_post.get("local_drives") or [])
                            self._selected_post = detail
                            self.selectedPostChanged.emit()

                    self._callOnGui.emit(_apply)

                threading.Thread(target=_fetch_detail, daemon=True, name="BrowserPostDetailWorker").start()

    @Slot()
    def closePostDetail(self) -> None:
        self._selected_post = {}
        self.selectedPostChanged.emit()

    @Slot(str, str, result=str)
    @Slot(str, result=str)
    def prepareRemoteMedia(self, url: str, provider_id: str = "") -> str:
        """
        Ensures a remote picture/GIF/WebP is downloaded into the bounded local preview
        LRU cache with provider headers and Pawchive n1-n4 failover.
        Returns local path synchronously if already cached; otherwise returns "" and emits
        `remoteMediaReady(url, localPath, error)` on completion.
        """
        clean = (url or "").strip()
        if not clean:
            return ""
        if not clean.lower().startswith(("http://", "https://")):
            return clean
        prov = (provider_id or self._active_provider or "").strip()

        def _on_done(orig_u: str, local_p: str, err: str) -> None:
            self._callOnGui.emit(lambda: self.remoteMediaReady.emit(orig_u, local_p, err))

        cached = self._media_service.fetch_image_async(clean, prov, _on_done)
        return cached or ""

    @Slot(str, str, str, result=str)
    @Slot(str, str, result=str)
    @Slot(str, result=str)
    def getStreamUrl(self, url: str, provider_id: str = "", ext: str = "") -> str:
        """
        Returns a local HTTP Range-streaming proxy URL for remote video/audio items so Qt
        `MediaPlayer` seeks smoothly with provider cookies/Referer and n1-n4 failover.
        """
        clean = (url or "").strip()
        if not clean:
            return ""
        if not clean.lower().startswith(("http://", "https://")):
            return clean
        prov = (provider_id or self._active_provider or "").strip()
        return self._media_service.register_stream(clean, prov, suggested_ext=ext)

    @Slot(str)
    def fetchTagsAutocomplete(self, query: str = "") -> None:
        prov = browser_registry.get_provider(self._active_provider)
        if not prov or not prov.capabilities().supports_tag_filter:
            self.tagsListReady.emit([])
            return

        def _worker():
            tags = prov.list_tags(query=query, limit=30)
            self._callOnGui.emit(lambda: self.tagsListReady.emit(tags))

        threading.Thread(target=_worker, daemon=True, name="BrowserTagsWorker").start()
