"""
BrowserBridge Mark Cart & Downloader Dispatch Mixin
Decomposed from bridge/browser_bridge.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import inspect
import os
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import Slot

from bridge.browser_bridge_mixins.signals_mixin import BrowserSignalsMixin
from core.browser_providers import browser_registry
from core.browser_providers.base import build_creator_card_dto, build_post_card_dto
from core.logger import logger


class BrowserCartDispatchMixin(BrowserSignalsMixin):
    """Manages persistent mark cart selection, folder previews, and downloader queue dispatch."""

    def _sync_marks_to_models(self) -> None:
        self._marked_model.set_creators(self._mark_manager.all_items())
        # Refresh `is_marked` flags in creatorsModel and postsModel in place
        if self._creators_model.count > 0:
            updated_c = [
                {**self._creators_model.get(i), "is_marked": self._mark_manager.has_key(self._creators_model.get(i).get("key", ""))}
                for i in range(self._creators_model.count)
            ]
            self._creators_model.set_creators(updated_c)
        if self._posts_model.count > 0:
            updated_p = [
                {**self._posts_model.get(i), "is_marked": self._mark_manager.has_key(self._posts_model.get(i).get("key", ""))}
                for i in range(self._posts_model.count)
            ]
            self._posts_model.set_creators(updated_p)
        if self._selected_creator:
            self._selected_creator = {
                **self._selected_creator,
                "is_marked": self._mark_manager.has_key(self._selected_creator.get("key", "")),
            }
            self.selectedCreatorChanged.emit()
        if self._selected_post:
            self._selected_post = {
                **self._selected_post,
                "is_marked": self._mark_manager.has_key(self._selected_post.get("key", "")),
            }
            self.selectedPostChanged.emit()
        self.marksChanged.emit()

    @Slot("QVariantMap", result=bool)
    def toggleMarkItem(self, item_map: Dict[str, Any]) -> bool:
        now_marked = self._mark_manager.toggle_item(dict(item_map or {}))
        self._sync_marks_to_models()
        return now_marked

    @Slot(str, int, int, bool, result=int)
    def markRangeInModel(self, model_kind: str, start_index: int, end_index: int, mark_state: bool) -> int:
        """Mark or unmark an inclusive index range in the visible creators or posts model."""
        model = self._posts_model if model_kind == "posts" else self._creators_model
        count = model.count
        if count <= 0:
            return 0
        lo = max(0, min(int(start_index), int(end_index)))
        hi = min(count - 1, max(int(start_index), int(end_index)))
        if lo > hi:
            return 0
        items = [model.get(i) for i in range(lo, hi + 1)]
        changed = self._mark_manager.set_items_marked(items, bool(mark_state))
        if changed:
            self._sync_marks_to_models()
        return changed

    @Slot(str, result=bool)
    def isKeyMarked(self, key: str) -> bool:
        return self._mark_manager.has_key(key)

    @Slot(str)
    def removeMarkedItem(self, key: str) -> None:
        if self._mark_manager.remove_key(key):
            self._sync_marks_to_models()

    @staticmethod
    def _find_model_record(
        model: RecordListModel,
        *,
        key: str = "",
        service: str = "",
        creator_id: str = "",
        post_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        svc_l = (service or "").strip().lower()
        cid_l = (creator_id or "").strip().lower()
        pid_l = (post_id or "").strip().lower()
        for i in range(model.count):
            rec = model.get(i)
            if not isinstance(rec, dict):
                continue
            if key and rec.get("key") == key:
                return dict(rec)
            r_svc = str(rec.get("service") or "").strip().lower()
            r_cid = str(rec.get("creator_id") or "").strip().lower()
            r_pid = str(rec.get("post_id") or "").strip().lower()
            if cid_l and r_cid == cid_l and (not svc_l or r_svc == svc_l):
                if pid_l:
                    if r_pid == pid_l:
                        return dict(rec)
                elif not r_pid:
                    return dict(rec)
        return None

    def _open_marked_local(self, item_map: Dict[str, Any]) -> None:
        item_type = str(item_map.get("item_type") or ("post" if item_map.get("post_id") else "creator")).strip().lower()
        svc = str(item_map.get("service") or "")
        cid = str(item_map.get("creator_id") or "")
        cname = str(item_map.get("creator_name") or item_map.get("name") or item_map.get("title") or "")
        pid = str(item_map.get("post_id") or "")
        key = str(item_map.get("key") or "")

        if self._browser_mode != "local":
            self._browser_mode = "local"
            self.browserModeChanged.emit()
        self.localDrivesChanged.emit()

        creator_dto = self._find_local_creator(svc, cid, cname)
        if not creator_dto:
            self.toastRequested.emit("Could not find this marked item in your local folders.", "warning")
            self.refresh(False)
            return

        self.openCreator(creator_dto)
        if item_type == "post":
            posts, _ = self._local_library.list_local_creator_posts(
                creator_key=str(creator_dto.get("key") or ""), offset=0, limit=500
            )
            matched = next(
                (p for p in posts if (key and p.get("key") == key) or (pid and str(p.get("post_id") or "").lower() == pid.lower())),
                None,
            )
            if matched:
                self.openPostDetail(self._annotate_items([matched])[0])
            else:
                self.toastRequested.emit("Opened creator folder; exact post was not found on disk.", "info")

    def _open_marked_online(self, item_map: Dict[str, Any]) -> None:
        item_type = str(item_map.get("item_type") or ("post" if item_map.get("post_id") else "creator")).strip().lower()
        raw_prov = str(item_map.get("provider_id") or self._active_provider or "cumst").strip().lower()
        prov_id = raw_prov if browser_registry.get_provider(raw_prov) else self._active_provider
        svc = str(item_map.get("service") or "").strip().lower()
        cid = str(item_map.get("creator_id") or "").strip()
        cname = str(item_map.get("creator_name") or item_map.get("name") or item_map.get("title") or "").strip()
        pid = str(item_map.get("post_id") or "").strip()
        title = str(item_map.get("title") or cname).strip()
        url = str(item_map.get("url") or "").strip()
        avatar_url = str(item_map.get("avatar_url") or item_map.get("thumbnail_url") or "").strip()
        key = str(item_map.get("key") or "").strip()

        if self._browser_mode != "online":
            self._browser_mode = "online"
            self.browserModeChanged.emit()
        if prov_id and prov_id != self._active_provider:
            self._active_provider = prov_id
            self._active_service = "all"
            self._active_tag = ""
            self._offset = 0
            self.activeProviderChanged.emit()
            self.filterStateChanged.emit()

        creator_key = key if item_type == "creator" else (f"{prov_id}:{svc}:{cid}" if (svc and cid) else "")
        cur_c = self._selected_creator
        same_creator = bool(
            cur_c
            and str(cur_c.get("provider_id") or "").lower() == prov_id
            and (
                (creator_key and cur_c.get("key") == creator_key)
                or (cid and str(cur_c.get("creator_id") or "").lower() == cid.lower() and (not svc or str(cur_c.get("service") or "").lower() == svc))
            )
        )
        creator_dto = (
            dict(cur_c)
            if same_creator
            else self._find_model_record(self._creators_model, key=creator_key, service=svc, creator_id=cid)
        )
        if not creator_dto:
            creator_url = url if item_type == "creator" else re.sub(r"/posts?/[^/?#]+.*$", "", url)
            creator_dto = build_creator_card_dto(
                provider_id=prov_id,
                service=svc or "unknown",
                creator_id=cid or cname,
                name=cname or cid,
                url=creator_url,
                avatar_url=avatar_url if item_type == "creator" else "",
                is_marked=self._mark_manager.has_key(creator_key) if creator_key else False,
            )
            if creator_key:
                creator_dto["key"] = creator_key

        if item_type == "creator":
            self.openCreator(creator_dto)
            return

        if (cid or cname) and not same_creator:
            self.openCreator(creator_dto)

        post_dto = self._find_model_record(self._posts_model, key=key, service=svc, creator_id=cid, post_id=pid)
        if not post_dto:
            post_dto = build_post_card_dto(
                provider_id=prov_id,
                service=svc or "unknown",
                creator_id=cid,
                post_id=pid,
                title=title,
                url=url,
                creator_name=cname,
                thumbnail_url=avatar_url,
                is_marked=self._mark_manager.has_key(key) if key else True,
            )
            if key:
                post_dto["key"] = key
        self.openPostDetail(post_dto)

    @Slot("QVariantMap")
    def openMarkedItem(self, item_map: Dict[str, Any]) -> None:
        """Navigates directly to the clicked marked creator profile or post detail."""
        if not item_map or not isinstance(item_map, dict):
            return
        url = str(item_map.get("url") or "").strip()
        is_local = bool(item_map.get("is_local")) or (
            not url and (self._browser_mode == "local" or str(item_map.get("service") or "").lower() == "local")
        )
        if is_local:
            self._open_marked_local(item_map)
        else:
            self._open_marked_online(item_map)

    @Slot()
    def clearMarkedItems(self) -> None:
        self._mark_manager.clear()
        self._sync_marks_to_models()

    @Slot(result="QVariantList")
    def getMarkedItemsList(self) -> List[Dict[str, Any]]:
        """Returns a plain list of all marked cart item dicts for QML modals."""
        return [dict(it) for it in self._mark_manager.all_items()]

    @Slot(bool, bool)
    @Slot(bool)
    def dispatchMarkedToDownloader(self, auto_start: bool = True, switch_to_downloader_tab: bool = False) -> int:
        """
        Passes all marked creators and posts in the cart directly into the normal
        Downloader & Queue engine (`AppBridge.enqueueBatchUrls`), respecting all active
        filter, folder naming, Storage Pool, Known.txt, and Archive settings.
        """
        items = self._mark_manager.all_items()
        urls = [str(it.get("url") or "").strip() for it in items if str(it.get("url") or "").strip()]
        if not urls:
            self.toastRequested.emit("No downloadable URLs in your selection cart.", "warning")
            return 0

        if self._app_bridge and hasattr(self._app_bridge, "enqueueBatchUrls"):
            self._app_bridge.enqueueBatchUrls(urls, auto_start)
        elif self._app_bridge:
            self._app_bridge.currentUrl = "\n".join(urls)
            if auto_start:
                self._app_bridge.startDownload()
            else:
                self._app_bridge.addToQueue()

        count = len(urls)
        self._mark_manager.clear()
        self._sync_marks_to_models()

        action_label = "Started downloading" if auto_start else "Added to Queue:"
        self.toastRequested.emit(f"{action_label} {count} marked item(s) via Downloader.", "success")
        if switch_to_downloader_tab:
            self.navigateToTabRequested.emit(0)
        return count

    @Slot()
    def openDownloaderTab(self) -> None:
        """Switches the main window back to the Downloader tab."""
        self.navigateToTabRequested.emit(0)

    @Slot(str, bool)
    @Slot(str, bool, str)
    def downloadSingleUrl(self, url: str, auto_start: bool = True, label: str = "") -> None:
        """Immediately sends a single creator or post URL to the normal Downloader."""
        clean = (url or "").strip()
        if not clean:
            self.toastRequested.emit("No downloadable URL available for this item.", "warning")
            return
        if not self._app_bridge:
            self.toastRequested.emit("Downloader bridge is not connected.", "warning")
            return
        if hasattr(self._app_bridge, "enqueueBatchUrls"):
            self._app_bridge.enqueueBatchUrls([clean], auto_start)
        else:
            self._app_bridge.currentUrl = clean
            if auto_start:
                self._app_bridge.startDownload()
            else:
                self._app_bridge.addToQueue()
        clean_label = (label or "").strip()
        target_text = f"'{clean_label}'" if clean_label else "item"
        self.toastRequested.emit(
            (
                f"Download started for {target_text} — check Downloader tab."
                if auto_start
                else f"Added {target_text} to Downloader Queue."
            ),
            "success",
        )

    @Slot(result=str)
    def getEffectiveDownloadDir(self) -> str:
        """Returns remembered Browser download folder, falling back to Downloader's folder if set."""
        saved = self.lastDownloadDir
        if saved:
            return saved
        if self._app_bridge:
            dl_dir = str(getattr(self._app_bridge, "downloadDir", "") or "").strip()
            if dl_dir:
                return dl_dir
        return ""

    @Slot(str)
    def setLastDownloadDir(self, path: str) -> None:
        clean = os.path.normpath((path or "").replace("file:///", "").replace("file://", "").strip()) if (path or "").strip() else ""
        if self._app_bridge and hasattr(self._app_bridge, "browserLastDownloadDir"):
            self._app_bridge.browserLastDownloadDir = clean
        else:
            s = self._read_settings()
            s["browser_last_download_dir"] = clean
            self._write_settings(s)
        self.lastDownloadDirChanged.emit()

    @Slot(str, result=str)
    @Slot(result=str)
    def browseDownloadDir(self, current_dir: str = "") -> str:
        """Opens native folder dialog starting at current/last remembered Browser path and persists the selection."""
        initial = (current_dir or "").strip()
        if not initial or not os.path.isdir(initial):
            initial = self.lastDownloadDir
        if not initial or not os.path.isdir(initial):
            if self._app_bridge:
                cand = str(getattr(self._app_bridge, "downloadDir", "") or "").strip()
                if cand and os.path.isdir(cand):
                    initial = cand
        if not initial or not os.path.isdir(initial):
            initial = os.path.expanduser("~")

        chosen = ""
        if self._app_bridge and hasattr(self._app_bridge, "browseBrowserDownloadDir"):
            chosen = str(self._app_bridge.browseBrowserDownloadDir(initial) or "").strip()
        else:
            from PySide6.QtWidgets import QFileDialog
            raw = QFileDialog.getExistingDirectory(None, "Select Browser Download Folder", initial)
            chosen = os.path.normpath(raw) if raw else ""
            if chosen:
                self.setLastDownloadDir(chosen)

        if chosen:
            self.lastDownloadDirChanged.emit()
        return chosen

    @Slot(result=str)
    def getSelectedCreatorDmsUrl(self) -> str:
        if not self._selected_creator:
            return ""
        prov, svc, cid = self._resolve_online_provider(self._selected_creator, self._get_creator_links())
        if not prov or not svc or svc == "local" or not cid:
            return ""
        return str(prov.build_dms_url(svc, cid) or "").strip()

    @Slot(str, "QVariantList", bool, result="QVariantList")
    def previewDownloadFolders(self, target_dir: str, items: list, create_creator_folder: bool = True) -> List[str]:
        """Returns concrete resolved folder preview lines for the Browser Download modal."""
        clean_dir = os.path.normpath((target_dir or "").strip()) if (target_dir or "").strip() else ""
        if not clean_dir:
            return []

        from core.filter_engine import FilterEngine
        from core.folder_naming import pick_creator_folder, is_creator_folder

        creators: List[Tuple[str, str]] = []
        seen_creators: Set[Tuple[str, str]] = set()
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            cname = str(it.get("creator_name") or it.get("name") or it.get("title") or "").strip()
            svc = str(it.get("service") or "").strip().lower()
            cid = str(it.get("creator_id") or "").strip()
            key = (svc, (cid or cname).lower())
            if not cname:
                cname = cid or "Creator"
            if key not in seen_creators:
                seen_creators.add(key)
                creators.append((cname, svc))

        if not creators:
            return [clean_dir]

        multi = len(creators) > 1
        use_subfolder = True if multi else bool(create_creator_folder)
        if not use_subfolder:
            return [clean_dir]

        previews: List[str] = []
        base_leaf = os.path.basename(clean_dir)
        for cname, svc in creators:
            clean_c = FilterEngine.clean_filesystem_text(cname, max_len=80, fallback="creator")
            if not multi and is_creator_folder(base_leaf, clean_c, svc):
                previews.append(clean_dir)
            else:
                previews.append(pick_creator_folder(clean_dir, clean_c, svc))
        return previews

    @Slot("QVariantList", str, bool, bool, bool, bool, result=int)
    def dispatchBrowserDownload(
        self,
        urls: list,
        download_dir: str,
        auto_start: bool = True,
        create_creator_folder: bool = True,
        clear_marks: bool = False,
        force_redownload: bool = False,
    ) -> int:
        """Dispatches Browser-chosen URLs to the Downloader with an explicit destination folder & folder mode."""
        clean_urls = [str(u or "").strip() for u in (urls or []) if str(u or "").strip()]
        if not clean_urls:
            self.toastRequested.emit("No downloadable URLs selected.", "warning")
            return 0
        clean_dir = os.path.normpath((download_dir or "").replace("file:///", "").replace("file://", "").strip()) if (download_dir or "").strip() else ""
        if not clean_dir:
            self.toastRequested.emit("Please choose a destination folder before downloading.", "warning")
            return 0
        if not self._app_bridge:
            self.toastRequested.emit("Downloader bridge is not connected.", "warning")
            return 0

        # Remember this folder for the next time the Browser Download modal opens
        self.setLastDownloadDir(clean_dir)

        if hasattr(self._app_bridge, "enqueueBatchUrls"):
            try:
                sig = inspect.signature(self._app_bridge.enqueueBatchUrls)
                if len(sig.parameters) >= 5:
                    self._app_bridge.enqueueBatchUrls(
                        clean_urls,
                        bool(auto_start),
                        bool(force_redownload),
                        clean_dir,
                        bool(create_creator_folder),
                    )
                else:
                    self._app_bridge.enqueueBatchUrls(clean_urls, bool(auto_start), bool(force_redownload))
            except Exception:
                self._app_bridge.enqueueBatchUrls(clean_urls, bool(auto_start))
        else:
            self._app_bridge.downloadDir = clean_dir
            self._app_bridge.currentUrl = "\n".join(clean_urls)
            if auto_start:
                self._app_bridge.startDownload()
            else:
                self._app_bridge.addToQueue()

        if clear_marks:
            self._mark_manager.clear()
            self._sync_marks_to_models()

        url_set = set(clean_urls)
        if self._new_posts_list:
            before_np = len(self._new_posts_list)
            self._new_posts_list = [p for p in self._new_posts_list if str(p.get("url") or "").strip() not in url_set]
            if len(self._new_posts_list) != before_np:
                self._new_posts_status_text = f"Queued {len(clean_urls)} newer post(s) to {clean_dir}."
                self.newPostsStateChanged.emit()

        count = len(clean_urls)
        action_label = "Started downloading" if auto_start else "Added to Queue:"
        self.toastRequested.emit(f"{action_label} {count} item(s) → {clean_dir}", "success")
        return count
