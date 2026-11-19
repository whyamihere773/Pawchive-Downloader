"""
Modular Dual-Mode Browser QML Bridge (`BrowserBridge`) & Persistent Mark Cart (`BrowserMarkManager`).

Connects the capability-driven `BrowserProviderRegistry` (Online Mode) and
`LocalLibraryService` (Multi-Drive Local Disk Mode) to `qml/views/BrowserView.qml`.
"""

from __future__ import annotations

import os
import re
import json
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QObject, Property, Qt, QUrl, Signal, Slot

from bridge.archive_creators_model import RecordListModel
from core.atomic_io import atomic_write_json
from core.browser_media_service import BrowserMediaService
from core.browser_providers import browser_registry
from core.browser_providers.base import build_creator_card_dto, build_post_card_dto
from core.local_library import LocalLibraryService
from core.logger import logger
from core.parser import normalize_archive_url
from core.path_utils import get_config_dir


class BrowserMarkManager:
    """
    Persistent Selection Cart ("Marked for Download" Tray) stored in `config/browser_marks.json`.
    Allows users to mark multiple creators and posts across different searches, pages, and providers.
    """

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = get_config_dir(config_dir)
        os.makedirs(self.config_dir, exist_ok=True)
        self.marks_file = os.path.join(self.config_dir, "browser_marks.json")
        self._lock = threading.RLock()
        self._items: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        with self._lock:
            if not os.path.exists(self.marks_file):
                self._items = {}
                return
            try:
                with open(self.marks_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._items = {str(it["key"]): it for it in data if isinstance(it, dict) and it.get("key")}
                elif isinstance(data, dict) and isinstance(data.get("items"), list):
                    self._items = {str(it["key"]): it for it in data["items"] if isinstance(it, dict) and it.get("key")}
            except Exception as e:
                logger.warning(f"[BrowserMarks] Could not load browser_marks.json: {e}", category="session")
                self._items = {}

    def save(self) -> None:
        with self._lock:
            payload = {"items": list(self._items.values())}
            try:
                atomic_write_json(self.marks_file, payload, indent=2)
            except Exception as e:
                logger.warning(f"[BrowserMarks] Failed to save browser_marks.json: {e}", category="session")

    def has_key(self, key: str) -> bool:
        with self._lock:
            return str(key or "") in self._items

    def is_marked(self, key: str) -> bool:
        return self.has_key(key)

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def all_items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._items.values())

    def get_download_urls(self) -> List[str]:
        with self._lock:
            urls = []
            seen = set()
            for it in self._items.values():
                u = str(it.get("url") or "").strip()
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)
            return urls

    def toggle_mark(self, item: Dict[str, Any]) -> bool:
        return self.toggle_item(item)

    @staticmethod
    def _build_entry(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(item, dict):
            return None
        key = str(item.get("key") or "").strip()
        if not key:
            return None
        return {
            "key": key,
            "item_type": str(item.get("item_type") or ("post" if item.get("post_id") else "creator")),
            "provider_id": str(item.get("provider_id") or "cumst"),
            "service": str(item.get("service") or ""),
            "service_label": str(item.get("service_label") or item.get("service") or ""),
            "creator_id": str(item.get("creator_id") or ""),
            "creator_name": str(item.get("creator_name") or item.get("name") or ""),
            "post_id": str(item.get("post_id") or ""),
            "title": str(item.get("title") or item.get("name") or item.get("creator_name") or ""),
            "url": str(item.get("url") or ""),
            "avatar_url": str(item.get("avatar_url") or item.get("thumbnail_url") or ""),
            "file_count": int(item.get("file_count") or item.get("post_count") or 0),
            "is_local": bool(item.get("is_local") or (not item.get("url") and bool(item.get("is_on_disk")))),
        }

    def toggle_item(self, item: Dict[str, Any]) -> bool:
        """Toggles a creator or post in the mark cart. Returns True if now marked, False if removed."""
        entry = self._build_entry(item)
        if not entry:
            return False
        key = entry["key"]
        with self._lock:
            if key in self._items:
                self._items.pop(key, None)
                self.save()
                return False
            self._items[key] = entry
            self.save()
            return True

    def set_items_marked(self, items: List[Dict[str, Any]], mark_state: bool) -> int:
        """Mark or unmark multiple items with one atomic save. Returns count changed."""
        changed = 0
        with self._lock:
            for item in items:
                entry = self._build_entry(item)
                if not entry:
                    continue
                key = entry["key"]
                if mark_state:
                    if key not in self._items:
                        self._items[key] = entry
                        changed += 1
                elif key in self._items:
                    self._items.pop(key, None)
                    changed += 1
            if changed:
                self.save()
        return changed

    def remove_key(self, key: str) -> bool:
        with self._lock:
            if key in self._items:
                self._items.pop(key, None)
                self.save()
                return True
        return False

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.save()


class BrowserBridge(QObject):
    """
    QML Bridge for the Top-Level Native Browser Tab (`BrowserView.qml`).
    Supports both Online Mode (via `browser_registry`) and Multi-Drive Local Mode (via `LocalLibraryService`).
    """

    providersManifestChanged = Signal()
    browserModeChanged = Signal()
    activeProviderChanged = Signal()
    filterStateChanged = Signal()
    loadingStateChanged = Signal()
    paginationChanged = Signal()
    selectedCreatorChanged = Signal()
    selectedPostChanged = Signal()
    marksChanged = Signal()
    localDrivesChanged = Signal()
    newPostsStateChanged = Signal()
    tagsListReady = Signal("QVariantList")
    relocationProgress = Signal(str, int, int, str)   # creatorKey, done, total, currentFile
    relocationFinished = Signal(str, bool, str)       # creatorKey, ok, message
    toastRequested = Signal(str, str)                 # message, kind ("info"|"success"|"warning"|"error")
    navigateToTabRequested = Signal(int)              # tab index in main.qml
    remoteMediaReady = Signal(str, str, str)          # sourceUrl, localPath, error
    activeProviderAuthChanged = Signal()
    loginPromptRequested = Signal(str, str)           # providerId, reason
    providerLoginFinished = Signal(str, bool, str)    # providerId, ok, message
    lastDownloadDirChanged = Signal()

    _callOnGui = Signal(object)

    def __init__(self, app_bridge=None, config_dir: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._callOnGui.connect(self._run_on_gui, Qt.QueuedConnection)
        self._app_bridge = app_bridge

        self._creators_model = RecordListModel(self, key_field="key")
        self._posts_model = RecordListModel(self, key_field="key")
        self._marked_model = RecordListModel(self, key_field="key")

        self._mark_manager = BrowserMarkManager(config_dir=config_dir)
        self._marked_model.set_creators(self._mark_manager.all_items())
        self._media_service = BrowserMediaService()

        self._config_dir = config_dir
        self._mem_settings: Dict[str, Any] = {
            "local_library_roots": [],
            "excluded_local_drives": [],
            "excluded_local_roots": [],
            "local_creator_links": {},
            "browser_last_download_dir": "",
        }

        from core.storage_pool_manager import StoragePoolManager
        pool_mgr = getattr(app_bridge, "storage_pool_manager", None) if app_bridge else StoragePoolManager(config_dir=config_dir)
        self._local_library = LocalLibraryService(
            archive_manager=getattr(app_bridge, "archive_manager", None) if app_bridge else None,
            watchlist_manager=getattr(app_bridge, "_watchlist_manager", None) if app_bridge else None,
            storage_pool_manager=pool_mgr,
            get_primary_dir=(lambda: getattr(app_bridge, "downloadDir", "")) if app_bridge else (lambda: ""),
            get_extra_roots=self._get_extra_library_roots,
            get_excluded_drives=self._get_excluded_drives,
            get_excluded_roots=self._get_excluded_roots,
            get_creator_links=self._get_creator_links,
        )

        active_provs = browser_registry.get_active_providers()
        self._browser_mode: str = "online"            # "online" | "local"
        self._active_provider: str = active_provs[0].provider_id if active_provs else "cumst"
        self._active_service: str = "all"
        self._active_sort: str = "popular"
        self._active_tag: str = ""
        self._active_drive: str = "all"
        self._search_query: str = ""
        self._search_target: str = "creators"         # "creators" | "posts"

        self._offset: int = 0
        self._page_size: int = 50
        self._total_count: int = 0
        self._has_more: bool = False
        self._is_loading: bool = False
        self._status_text: str = "Ready"
        self._error_message: str = ""
        self._auth_required: bool = False

        self._selected_creator: Dict[str, Any] = {}
        self._creator_section: str = "posts"            # "posts" | "dms"
        self._creator_posts_offset: int = 0
        self._creator_posts_total: int = 0
        self._creator_posts_has_more: bool = False
        self._creator_posts_query: str = ""
        self._selected_post: Dict[str, Any] = {}

        self._req_gen: int = 0
        self._fav_toggle_gen: int = 0
        self._new_posts_gen: int = 0
        self._is_checking_new_posts: bool = False
        self._new_posts_list: List[Dict[str, Any]] = []
        self._creator_search_matches: List[Dict[str, Any]] = []
        self._new_posts_creator_key: str = ""
        self._new_posts_status_text: str = ""
        self._cancel_event = threading.Event()
        self._relocate_cancel = threading.Event()

    @Slot(object)
    def _run_on_gui(self, fn):
        try:
            fn()
        except Exception as e:
            logger.debug(f"[BrowserBridge] GUI callback error: {e}", category="system")

    def _read_settings(self) -> Dict[str, Any]:
        if self._app_bridge and hasattr(self._app_bridge, "session_manager"):
            return self._app_bridge.session_manager.load_settings()
        return dict(self._mem_settings)

    def _write_settings(self, settings: Dict[str, Any]) -> None:
        if self._app_bridge and hasattr(self._app_bridge, "session_manager"):
            self._app_bridge.session_manager.save_settings(settings)
        else:
            self._mem_settings = dict(settings)

    def _get_extra_library_roots(self) -> List[str]:
        return list(self._read_settings().get("local_library_roots") or [])

    def _get_excluded_drives(self) -> List[str]:
        return list(self._read_settings().get("excluded_local_drives") or [])

    def _get_excluded_roots(self) -> List[str]:
        return list(self._read_settings().get("excluded_local_roots") or [])

    def _get_creator_links(self) -> Dict[str, Any]:
        raw = self._read_settings().get("local_creator_links")
        return dict(raw) if isinstance(raw, dict) else {}

    # ── Properties Exposed to QML ──────────────────────────────────────────────

    @Property(QObject, constant=True)
    def creatorsModel(self) -> RecordListModel:
        return self._creators_model

    @Property(QObject, constant=True)
    def postsModel(self) -> RecordListModel:
        return self._posts_model

    @Property(QObject, constant=True)
    def markedItemsModel(self) -> RecordListModel:
        return self._marked_model

    @Property("QVariantList", notify=providersManifestChanged)
    def providersManifest(self) -> List[Dict[str, Any]]:
        return browser_registry.get_ui_manifest()

    @Property(str, notify=browserModeChanged)
    def browserMode(self) -> str:
        return self._browser_mode

    @Property(str, notify=activeProviderChanged)
    def activeProvider(self) -> str:
        return self._active_provider

    @Property("QVariantMap", notify=activeProviderChanged)
    def activeProviderManifest(self) -> Dict[str, Any]:
        prov = browser_registry.get_provider(self._active_provider)
        if prov:
            return prov.get_manifest_entry()
        active = browser_registry.get_active_providers()
        return active[0].get_manifest_entry() if active else {}

    @Property(str, notify=filterStateChanged)
    def activeService(self) -> str:
        return self._active_service

    @Property(str, notify=filterStateChanged)
    def activeSort(self) -> str:
        return self._active_sort

    @Property(str, notify=filterStateChanged)
    def activeTag(self) -> str:
        return self._active_tag

    @Property(str, notify=filterStateChanged)
    def activeDriveFilter(self) -> str:
        return self._active_drive

    @Property(str, notify=filterStateChanged)
    def searchQuery(self) -> str:
        return self._search_query

    @Property(str, notify=filterStateChanged)
    def searchTarget(self) -> str:
        return self._search_target

    @Property(int, notify=paginationChanged)
    def currentOffset(self) -> int:
        return self._offset

    @Property(int, notify=paginationChanged)
    def pageSize(self) -> int:
        return self._page_size

    @Property(int, notify=paginationChanged)
    def totalCount(self) -> int:
        return self._total_count

    @Property(int, notify=paginationChanged)
    def currentPage(self) -> int:
        return (self._offset // max(1, self._page_size)) + 1

    @Property(int, notify=paginationChanged)
    def totalPages(self) -> int:
        if self._total_count <= 0:
            return 1
        return max(1, (self._total_count + self._page_size - 1) // max(1, self._page_size))

    @Property(bool, notify=paginationChanged)
    def hasMore(self) -> bool:
        return self._has_more

    @Property(bool, notify=loadingStateChanged)
    def isLoading(self) -> bool:
        return self._is_loading

    @Property(str, notify=loadingStateChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=loadingStateChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(bool, notify=loadingStateChanged)
    def authRequired(self) -> bool:
        return self._auth_required

    @Property(bool, notify=activeProviderAuthChanged)
    def activeProviderLoggedIn(self) -> bool:
        from core.auth_manager import auth_manager
        return auth_manager.is_logged_in(self._active_provider)

    @Property(str, notify=activeProviderAuthChanged)
    def activeProviderUsername(self) -> str:
        from core.auth_manager import auth_manager
        summary = auth_manager.get_provider_summary(self._active_provider)
        return str(summary.get("username") or "")

    @Property(bool, notify=activeProviderAuthChanged)
    def isLoggingInProvider(self) -> bool:
        return bool(getattr(self, "_is_logging_in_provider", False))

    @Property("QVariantMap", notify=selectedCreatorChanged)
    def selectedCreator(self) -> Dict[str, Any]:
        return self._selected_creator

    @Property(bool, notify=selectedCreatorChanged)
    def hasSelectedCreator(self) -> bool:
        return bool(self._selected_creator and self._selected_creator.get("key"))

    @Property(str, notify=filterStateChanged)
    def creatorSection(self) -> str:
        return self._creator_section

    @Property(bool, notify=selectedCreatorChanged)
    def creatorSupportsDms(self) -> bool:
        if not self._selected_creator or self._browser_mode == "local":
            return False
        prov, svc, cid = self._resolve_online_provider(self._selected_creator, self._get_creator_links())
        return bool(prov and svc and svc != "local" and cid and getattr(prov.capabilities(), "supports_dms", False))

    @Property(int, notify=selectedCreatorChanged)
    def creatorPostsTotal(self) -> int:
        return self._creator_posts_total

    @Property(int, notify=selectedCreatorChanged)
    def creatorPostsOffset(self) -> int:
        return self._creator_posts_offset

    @Property(bool, notify=selectedCreatorChanged)
    def creatorPostsHasMore(self) -> bool:
        return self._creator_posts_has_more

    @Property("QVariantMap", notify=selectedPostChanged)
    def selectedPost(self) -> Dict[str, Any]:
        return self._selected_post

    @Property(bool, notify=selectedPostChanged)
    def hasSelectedPost(self) -> bool:
        return bool(self._selected_post and self._selected_post.get("key"))

    @Property(int, notify=marksChanged)
    def markedCount(self) -> int:
        return len(self._mark_manager.all_items())

    @Property(int, notify=marksChanged)
    def markedCreatorsCount(self) -> int:
        return sum(1 for it in self._mark_manager.all_items() if it.get("item_type") == "creator")

    @Property(int, notify=marksChanged)
    def markedPostsCount(self) -> int:
        return sum(1 for it in self._mark_manager.all_items() if it.get("item_type") != "creator")

    @Property("QVariantList", notify=localDrivesChanged)
    def localDrives(self) -> List[Dict[str, Any]]:
        return self._local_library.get_available_drives_summary()

    @Property("QVariantList", notify=localDrivesChanged)
    def relocateTargetDrives(self) -> List[Dict[str, Any]]:
        return self._local_library.get_available_drives_summary(include_excluded=True)

    @Property("QVariantList", notify=localDrivesChanged)
    def excludedLocalDrives(self) -> List[str]:
        out: List[str] = []
        seen: Set[str] = set()
        for item in [*(self._get_excluded_drives() or []), *(self._get_excluded_roots() or [])]:
            s = str(item or "").strip()
            if not s:
                continue
            k = s.lower()
            if k not in seen:
                seen.add(k)
                out.append(s)
        return out

    @Property("QVariantList", notify=localDrivesChanged)
    def localLibraryRoots(self) -> List[str]:
        return self._local_library.get_all_library_roots()

    @Property(bool, notify=newPostsStateChanged)
    def isCheckingNewPosts(self) -> bool:
        return self._is_checking_new_posts

    @Property("QVariantList", notify=newPostsStateChanged)
    def newPostsList(self) -> List[Dict[str, Any]]:
        return self._new_posts_list

    @Property(int, notify=newPostsStateChanged)
    def newPostsCount(self) -> int:
        return len(self._new_posts_list)

    @Property("QVariantList", notify=newPostsStateChanged)
    def creatorSearchMatches(self) -> List[Dict[str, Any]]:
        return self._creator_search_matches

    @Property(int, notify=newPostsStateChanged)
    def creatorSearchMatchCount(self) -> int:
        return len(self._creator_search_matches)

    @Property(str, notify=newPostsStateChanged)
    def newPostsCreatorKey(self) -> str:
        return self._new_posts_creator_key

    @Property(str, notify=newPostsStateChanged)
    def newPostsStatusText(self) -> str:
        return self._new_posts_status_text

    # ── Mode, Provider & Filter Slots ──────────────────────────────────────────

    @Slot(str)
    def setBrowserMode(self, mode: str) -> None:
        clean = "local" if (mode or "").strip().lower() == "local" else "online"
        if self._browser_mode != clean:
            self._browser_mode = clean
            self._selected_creator = {}
            self._selected_post = {}
            self._offset = 0
            self._reset_new_posts_state()
            self.browserModeChanged.emit()
            self.selectedCreatorChanged.emit()
            self.selectedPostChanged.emit()
            if clean == "local":
                self.localDrivesChanged.emit()
            self.refresh(True)

    @Slot(str)
    def setActiveProvider(self, provider_id: str) -> None:
        clean = (provider_id or "").strip().lower()
        prov = browser_registry.get_provider(clean)
        if not prov:
            return
        if self._active_provider != clean:
            self._active_provider = clean
            self._active_service = "all"
            self._active_tag = ""
            self._offset = 0
            self._selected_creator = {}
            self._selected_post = {}
            self.activeProviderChanged.emit()
            self.filterStateChanged.emit()
            self.selectedCreatorChanged.emit()
            self.selectedPostChanged.emit()
            if self._browser_mode == "online":
                self.refresh(False)

    @Slot(str)
    def setServiceFilter(self, service: str) -> None:
        clean = (service or "all").strip().lower()
        changed = self._active_service != clean
        if clean == "favorites" and self._browser_mode == "online":
            from core.auth_manager import auth_manager
            prov_id = self._active_provider
            if self._search_target == "posts":
                self._search_target = "creators"
            if changed:
                self._active_service = clean
                self._offset = 0
            self.filterStateChanged.emit()
            if not auth_manager.is_logged_in(prov_id):
                self._req_gen += 1
                self._creators_model.set_creators([])
                self._total_count = 0
                self._has_more = False
                self._auth_required = True
                self._is_loading = False
                self._error_message = f"Log in to {prov_id} to view your favorited creators."
                self._status_text = self._error_message
                self.paginationChanged.emit()
                self.loadingStateChanged.emit()
                self.loginPromptRequested.emit(prov_id, "favorites")
                return
            self.refresh(False)
            return

        if changed:
            self._active_service = clean
            self._offset = 0
            self.filterStateChanged.emit()
            self.refresh(False)

    @Slot(str)
    def setSortOrder(self, sort_key: str) -> None:
        clean = (sort_key or "popular").strip().lower()
        if self._active_sort != clean:
            self._active_sort = clean
            self._offset = 0
            self.filterStateChanged.emit()
            self.refresh(False)

    @Slot(str)
    def setTagFilter(self, tag: str) -> None:
        clean = (tag or "").strip().lstrip("#")
        if self._active_tag != clean:
            self._active_tag = clean
            self._offset = 0
            self.filterStateChanged.emit()
            self.refresh(False)

    @Slot(str)
    def setDriveFilter(self, drive: str) -> None:
        clean = (drive or "all").strip()
        if self._active_drive != clean:
            self._active_drive = clean
            self._offset = 0
            self.filterStateChanged.emit()
            if self._selected_creator:
                self.loadCreatorPosts(0, self._creator_posts_query)
            else:
                self.refresh(False)

    @Slot(str)
    def setSearchTarget(self, target: str) -> None:
        clean = "posts" if (target or "").strip().lower() == "posts" else "creators"
        if self._search_target != clean:
            self._search_target = clean
            self._offset = 0
            self.filterStateChanged.emit()
            self.refresh(False)

    @Slot(str)
    def search(self, query: str) -> None:
        clean = (query or "").strip()
        self._search_query = clean
        self._offset = 0
        self.filterStateChanged.emit()
        self.refresh(False)

    @Slot(int)
    def goToPage(self, page_num: int) -> None:
        target_page = max(1, int(page_num or 1))
        self._offset = (target_page - 1) * self._page_size
        self.paginationChanged.emit()
        self.refresh(False)

    @Slot()
    def nextPage(self) -> None:
        if self._has_more and not self._is_loading:
            self._offset += self._page_size
            self.paginationChanged.emit()
            self.refresh(False)

    @Slot()
    def prevPage(self) -> None:
        if self._offset > 0 and not self._is_loading:
            self._offset = max(0, self._offset - self._page_size)
            self.paginationChanged.emit()
            self.refresh(False)

    # ── Core Data Fetching (Online & Local) ────────────────────────────────────

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

    # ── Creator Profile & Post Feed ────────────────────────────────────────────

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

    # ── Persistent Mark Tray (Selection Cart) & Normal Downloader Integration ─

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

    # ── Browser Download Destination & Modal Dispatch ──────────────────────

    @Property(str, notify=lastDownloadDirChanged)
    def lastDownloadDir(self) -> str:
        if self._app_bridge and hasattr(self._app_bridge, "browserLastDownloadDir"):
            val = str(self._app_bridge.browserLastDownloadDir or "").strip()
            if val:
                return val
        return str(self._read_settings().get("browser_last_download_dir") or "").strip()

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

    # ── Account Auth & Creator Favorites ───────────────────────────────────

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

    # ── Multi-Drive Management & Artist Relocation ─────────────────────────────

    @Slot(str)
    def addLocalLibraryRoot(self, folder_path: str) -> None:
        clean = (folder_path or "").replace("file:///", "").replace("file://", "").strip()
        if not clean:
            return
        norm = os.path.normpath(clean)
        if not os.path.isdir(norm):
            self.toastRequested.emit(f"Folder does not exist: {norm}", "error")
            return
        settings = self._read_settings()
        roots = list(settings.get("local_library_roots") or [])
        if not any(os.path.normcase(r) == os.path.normcase(norm) for r in roots):
            roots.append(norm)
        settings["local_library_roots"] = roots

        # Re-adding a folder explicitly un-excludes its drive / root path
        drv_key = LocalLibraryService.normalize_drive_key(norm)
        if drv_key:
            settings["excluded_local_drives"] = [
                d for d in (settings.get("excluded_local_drives") or [])
                if LocalLibraryService.normalize_drive_key(d) != drv_key
            ]
        settings["excluded_local_roots"] = [
            r for r in (settings.get("excluded_local_roots") or [])
            if os.path.normcase(os.path.normpath(r)) != os.path.normcase(norm)
        ]
        self._write_settings(settings)
        self.localDrivesChanged.emit()
        if self._browser_mode == "local":
            self.refresh(True)
        self.toastRequested.emit(f"Added local library folder: {norm}", "success")

    @Slot(str)
    def removeLocalLibraryRoot(self, folder_path: str) -> None:
        norm = os.path.normpath((folder_path or "").strip())
        if not norm:
            return
        settings = self._read_settings()
        roots = [
            r for r in (settings.get("local_library_roots") or [])
            if os.path.normcase(os.path.normpath(r)) != os.path.normcase(norm)
        ]
        settings["local_library_roots"] = roots
        # If it still exists as a default/primary/overflow root, track it in excluded_local_roots
        excl_roots = list(settings.get("excluded_local_roots") or [])
        if not any(os.path.normcase(os.path.normpath(r)) == os.path.normcase(norm) for r in excl_roots):
            excl_roots.append(norm)
        settings["excluded_local_roots"] = excl_roots
        self._write_settings(settings)
        self.localDrivesChanged.emit()
        if self._browser_mode == "local":
            self.refresh(True)

    @Slot(str, str)
    @Slot(str)
    def removeLocalDrive(self, drive_label: str, root_path: str = "") -> None:
        drv_key = LocalLibraryService.normalize_drive_key(drive_label or root_path)
        norm_root = os.path.normpath((root_path or "").strip()) if (root_path or "").strip() else ""
        if not drv_key and not norm_root:
            return
        settings = self._read_settings()
        if os.name == "nt" and drv_key and len(drv_key) == 2 and drv_key[1] == ":":
            excl_drvs = list(settings.get("excluded_local_drives") or [])
            if not any(LocalLibraryService.normalize_drive_key(d) == drv_key for d in excl_drvs):
                excl_drvs.append(drv_key)
            settings["excluded_local_drives"] = excl_drvs
        else:
            target = norm_root or drv_key
            excl_roots = list(settings.get("excluded_local_roots") or [])
            if not any(os.path.normcase(os.path.normpath(r)) == os.path.normcase(target) for r in excl_roots):
                excl_roots.append(target)
            settings["excluded_local_roots"] = excl_roots
            settings["local_library_roots"] = [
                r for r in (settings.get("local_library_roots") or [])
                if os.path.normcase(os.path.normpath(r)) != os.path.normcase(target)
            ]
        self._write_settings(settings)

        if drv_key and (self._active_drive or "").strip().upper() == drv_key.upper():
            self._active_drive = "all"
            self.filterStateChanged.emit()

        self.localDrivesChanged.emit()
        if self._browser_mode == "local":
            self.refresh(True)
        else:
            self._local_library.refresh_catalog(heal_moved_paths=False)
        shown = drv_key or norm_root
        self.toastRequested.emit(f"Removed drive {shown} from Local Browser. You can restore it anytime.", "info")

    @Slot()
    def restoreDefaultLocalDrives(self) -> None:
        settings = self._read_settings()
        settings["excluded_local_drives"] = []
        settings["excluded_local_roots"] = []
        self._write_settings(settings)
        self.localDrivesChanged.emit()
        if self._browser_mode == "local":
            self.refresh(True)
        else:
            self._local_library.refresh_catalog(heal_moved_paths=False)
        self.toastRequested.emit("Restored all default & system drives in Local Browser.", "success")

    # ── Newer Posts Check & Post Redownload ────────────────────────────────────

    def _reset_new_posts_state(self, emit: bool = True) -> None:
        self._new_posts_gen += 1
        changed = (
            self._is_checking_new_posts
            or bool(self._new_posts_list)
            or bool(self._creator_search_matches)
            or bool(self._new_posts_creator_key)
            or bool(self._new_posts_status_text)
        )
        self._is_checking_new_posts = False
        self._new_posts_list = []
        self._creator_search_matches = []
        self._new_posts_creator_key = ""
        self._new_posts_status_text = ""
        if emit and changed:
            self.newPostsStateChanged.emit()

    @Slot()
    def clearNewPosts(self) -> None:
        self._reset_new_posts_state(emit=True)

    @staticmethod
    def _normalize_match_token(text: str) -> str:
        s = (text or "").strip().lower()
        s = re.sub(r"\s*\(@[^)]+\)$", "", s)
        s = re.sub(r"\s*[\(\[][a-z0-9_.-]+[\)\]]$", "", s)
        return re.sub(r"[^a-z0-9]", "", s)

    def _save_local_creator_link(self, creator: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
        settings = self._read_settings()
        links = dict(settings.get("local_creator_links") or {})
        prov_id = str(candidate.get("provider_id") or "").strip().lower()
        svc = str(candidate.get("service") or "").strip().lower()
        cid = str(candidate.get("creator_id") or "").strip()
        url = str(candidate.get("url") or "").strip()
        cname = str(candidate.get("name") or creator.get("name") or cid).strip()
        if not prov_id or not svc or svc == "local" or not cid:
            return dict(creator)

        link_payload = {
            "provider_id": prov_id,
            "service": svc,
            "creator_id": cid,
            "name": cname,
            "url": url,
            "post_count": int(candidate.get("post_count") or 0),
            "dm_count": int(candidate.get("dm_count") or 0),
        }
        orig_name = str(creator.get("name") or "").strip().lower()
        orig_key = str(creator.get("key") or "").strip()
        for k in {
            orig_key,
            orig_name,
            f"local:{orig_name}" if orig_name else "",
            cname.lower(),
        }:
            if k:
                links[k] = link_payload
        for d in (creator.get("local_dirs") or []):
            bname = os.path.basename(str(d)).strip().lower()
            if bname:
                links[bname] = link_payload

        settings["local_creator_links"] = links
        self._write_settings(settings)

        updated = dict(creator)
        updated["provider_id"] = prov_id
        updated["service"] = svc
        updated["service_label"] = candidate.get("service_label") or svc.capitalize()
        updated["creator_id"] = cid
        if url:
            updated["url"] = url
        if int(candidate.get("dm_count") or 0) > 0:
            updated["dm_count"] = int(candidate.get("dm_count") or 0)
        return updated

    @staticmethod
    def _resolve_online_provider(
        creator_map: Dict[str, Any],
        creator_links: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, str, str]:
        prov_id = str(creator_map.get("provider_id") or "").strip().lower()
        svc = str(creator_map.get("service") or "").strip().lower()
        cid = str(creator_map.get("creator_id") or "").strip()
        raw_url = str(creator_map.get("url") or "").strip()

        if (not svc or svc == "local" or not cid or not raw_url) and isinstance(creator_links, dict) and creator_links:
            cname_low = str(creator_map.get("name") or "").strip().lower()
            ckey = str(creator_map.get("key") or "").strip()
            saved = (
                creator_links.get(ckey)
                or creator_links.get(f"local:{cname_low}")
                or creator_links.get(cname_low)
            )
            if not saved:
                for d in (creator_map.get("local_dirs") or []):
                    bname = os.path.basename(str(d)).strip().lower()
                    if bname and isinstance(creator_links.get(bname), dict):
                        saved = creator_links[bname]
                        break
            if isinstance(saved, dict):
                prov_id = str(saved.get("provider_id") or prov_id or "").strip().lower()
                svc = str(saved.get("service") or svc or "").strip().lower()
                cid = str(saved.get("creator_id") or cid or "").strip()
                raw_url = str(saved.get("url") or raw_url or "").strip()

        if raw_url:
            try:
                from core.parser import KemonoURLParser
                parsed = KemonoURLParser.parse_url(raw_url)
                if parsed and getattr(parsed, "is_valid", False) and not getattr(parsed, "is_external_provider", False):
                    if not svc or svc == "local":
                        svc = str(parsed.service or "").strip().lower()
                    if not cid:
                        cid = str(parsed.user_id or "").strip()
                    dom = str(parsed.domain or "").lower()
                    if not prov_id:
                        if "coomerfans" in dom:
                            prov_id = "coomerfans"
                        elif "cum.st" in dom:
                            prov_id = "cumst"
                        else:
                            prov_id = "pawchive"
            except Exception:
                pass

        prov = browser_registry.get_provider(prov_id) if prov_id else None
        if prov is None or (svc and svc != "local" and getattr(prov.capabilities, "supported_services", None) and svc not in prov.capabilities.supported_services and prov_id == "pawchive" and svc in ("onlyfans", "fansly", "candfans", "coomerfans")):
            if svc == "coomerfans":
                prov = browser_registry.get_provider("coomerfans")
            elif svc in ("onlyfans", "fansly", "candfans"):
                prov = browser_registry.get_provider("cumst")
            else:
                prov = browser_registry.get_provider(prov_id or "pawchive") or browser_registry.get_provider("pawchive")
        return prov, svc, cid

    def _collect_known_post_signatures(
        self, creator: Dict[str, Any], svc: str, cid: str, cname: str
    ) -> Tuple[Set[str], Set[Tuple[str, str]], Set[str]]:
        known_ids: Set[str] = set()
        known_title_dates: Set[Tuple[str, str]] = set()
        known_filenames: Set[str] = set()

        def _record_filename(fn: str) -> None:
            clean = os.path.basename(str(fn or "").strip()).lower()
            if not clean:
                return
            known_filenames.add(clean)
            stripped = re.sub(r"^\d+_", "", clean)
            if stripped:
                known_filenames.add(stripped)

        def _record_post(p: Dict[str, Any]):
            pid = str(p.get("post_id") or "").strip()
            if pid and pid != "root_files" and not pid.startswith("local_"):
                known_ids.add(pid.lower())
            title = str(p.get("title") or "").strip().lower()
            pub = str(p.get("published_at") or p.get("downloaded_at") or "").strip()[:10]
            if title and pub:
                known_title_dates.add((title, pub))
            for att in (p.get("attachments") or []):
                if isinstance(att, dict):
                    _record_filename(att.get("name") or att.get("local_path") or "")

        creator_key = str(creator.get("key") or "").strip()
        if creator_key:
            lposts, _ = self._local_library.list_local_creator_posts(creator_key, drive_filter="all", limit=0)
            for p in lposts:
                _record_post(p)

        if not known_ids or not known_filenames:
            local_match = self._find_local_creator(svc, cid, cname)
            if local_match and str(local_match.get("key") or "") != creator_key:
                lposts2, _ = self._local_library.list_local_creator_posts(str(local_match.get("key") or ""), drive_filter="all", limit=0)
                for p in lposts2:
                    _record_post(p)

        arch_mgr = getattr(self._app_bridge, "archive_manager", None) if self._app_bridge else None
        if arch_mgr:
            try:
                arch_key = str(creator.get("archive_key") or "").strip()
                if not arch_key:
                    for sm in (arch_mgr.get_creator_summaries() or []):
                        s_svc = str(sm.get("service") or "").strip().lower()
                        s_cid = str(sm.get("creator_id") or "").strip()
                        s_name = str(sm.get("creator_name") or "").strip().lower()
                        if (not svc or s_svc == svc) and ((cid and s_cid.lower() == cid.lower()) or (cname and s_name == cname.lower())):
                            arch_key = str(sm.get("key") or "").strip()
                            break
                if arch_key:
                    for ap in (arch_mgr.get_creator_posts(arch_key) or []):
                        ap_pid = str(ap.get("post_id") or "").strip()
                        if ap_pid:
                            known_ids.add(ap_pid.lower())
                        ap_t = str(ap.get("post_title") or "").strip().lower()
                        ap_d = str(ap.get("downloaded_at") or "").strip()[:10]
                        if ap_t and ap_d:
                            known_title_dates.add((ap_t, ap_d))
            except Exception:
                pass

        return known_ids, known_title_dates, known_filenames

    def _search_creator_across_sites(self, query_name: str, preferred_service: str = "") -> List[Dict[str, Any]]:
        clean_raw = (query_name or "").strip()
        if not clean_raw:
            return []
        stripped = re.sub(r"\s*\(@[^)]+\)$", "", clean_raw).strip()
        stripped = re.sub(r"\s*[\(\[][a-zA-Z0-9_.-]+[\)\]]$", "", stripped).strip()
        queries: List[str] = [stripped or clean_raw]
        alt_space = re.sub(r"[_\-]+", " ", queries[0]).strip()
        if alt_space and alt_space.lower() != queries[0].lower():
            queries.append(alt_space)

        q_norm = self._normalize_match_token(queries[0])
        pref_svc = (preferred_service or "").strip().lower()
        if pref_svc == "local":
            pref_svc = ""

        providers = [p for p in browser_registry.get_active_providers() if p.capabilities().supports_creator_search]
        if not providers:
            return []

        def _probe_provider(prov):
            caps = prov.capabilities()
            manifest = prov.get_manifest_entry()
            found_items: List[Dict[str, Any]] = []
            for q in queries:
                try:
                    svc_arg = pref_svc if (pref_svc and any(k == pref_svc for k, _ in caps.services)) else "all"
                    res = prov.list_creators(query=q, service=svc_arg, offset=0, limit=25)
                    if (not res.items or res.error) and svc_arg != "all":
                        res = prov.list_creators(query=q, service="all", offset=0, limit=25)
                    if not res.error and res.items:
                        for it in res.items:
                            item = dict(it)
                            item["provider_name"] = manifest.get("name") or prov.display_name
                            item["provider_icon"] = manifest.get("icon") or caps.badge_icon
                            item["provider_accent"] = manifest.get("accentColor") or caps.accent_color
                            found_items.append(item)
                        break
                except Exception:
                    continue
            return found_items

        raw_candidates: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(4, len(providers))) as pool:
            futs = [pool.submit(_probe_provider, p) for p in providers]
            for fut in as_completed(futs):
                try:
                    raw_candidates.extend(fut.result() or [])
                except Exception:
                    pass

        scored: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple[str, str, str]] = set()
        for item in raw_candidates:
            pid = str(item.get("provider_id") or "").lower()
            svc = str(item.get("service") or "").lower()
            cid = str(item.get("creator_id") or "")
            uniq = (pid, svc, cid.lower())
            if uniq in seen_keys or not cid:
                continue

            name_raw = str(item.get("name") or "")
            handle_m = re.search(r"\(@([^)]+)\)", name_raw)
            bare_name = re.sub(r"\s*\(@[^)]+\)$", "", name_raw).strip()
            candidates_str = [
                bare_name.lower(),
                (handle_m.group(1).lower() if handle_m else ""),
                cid.lower(),
            ]
            cand_norms = [self._normalize_match_token(s) for s in candidates_str if s]

            score = 0
            if any(c == queries[0].lower() for c in candidates_str if c) or (q_norm and q_norm in cand_norms):
                score = 100
            elif any(c.startswith(queries[0].lower()) for c in candidates_str if c) or (q_norm and any(cn.startswith(q_norm) for cn in cand_norms)):
                score = 85
            elif len(q_norm) >= 3 and (
                any(q_norm in cn for cn in cand_norms) or any(cn in q_norm and len(cn) >= 3 for cn in cand_norms)
            ):
                score = 65

            if score == 0:
                continue

            if pref_svc and svc == pref_svc:
                score += 12
            seen_keys.add(uniq)
            item["match_score"] = score
            item["is_exact_match"] = score >= 100
            item["post_activity"] = int(item.get("post_count") or 0) + int(item.get("favorited_count") or 0) // 100
            scored.append(item)

        scored.sort(key=lambda c: (c.get("match_score", 0), c.get("post_activity", 0), c.get("post_count", 0)), reverse=True)
        return scored[:12]

    def _run_new_posts_check_for_target(
        self,
        creator: Dict[str, Any],
        prov: Any,
        svc: str,
        cid: str,
        cname: str,
        status_prefix: str = "",
    ) -> None:
        known_ids, known_title_dates, known_filenames = self._collect_known_post_signatures(creator, svc, cid, cname)
        self._new_posts_gen += 1
        gen = self._new_posts_gen
        creator_key = str(creator.get("key") or "").strip()

        self._is_checking_new_posts = True
        self._new_posts_list = []
        self._new_posts_creator_key = creator_key
        self._new_posts_status_text = status_prefix or f"Checking '{cname}' online on {prov.display_name} for newer posts…"
        self.newPostsStateChanged.emit()

        def _worker():
            fetched: List[Dict[str, Any]] = []
            err_msg = ""
            try:
                res = prov.list_creator_posts(service=svc, creator_id=cid, creator_name=cname, offset=0, limit=50)
                if res.error:
                    err_msg = res.error
                else:
                    fetched.extend(res.items or [])
                    if res.has_more and known_ids and not any(str(it.get("post_id") or "").strip().lower() in known_ids for it in fetched):
                        res2 = prov.list_creator_posts(service=svc, creator_id=cid, creator_name=cname, offset=50, limit=50)
                        if not res2.error and res2.items:
                            fetched.extend(res2.items)
                if not err_msg and getattr(prov.capabilities(), "supports_dms", False) and (int(creator.get("dm_count") or 0) > 0 or self._creator_section == "dms"):
                    dm_res = prov.list_creator_dms(service=svc, creator_id=cid, creator_name=cname, offset=0, limit=50)
                    if not dm_res.error and dm_res.items:
                        fetched.extend(dm_res.items)
            except Exception as e:
                err_msg = str(e)

            missing: List[Dict[str, Any]] = []
            seen_pids: Set[Tuple[bool, str]] = set()
            for item in fetched:
                p = dict(item)
                pid = str(p.get("post_id") or "").strip()
                pid_low = pid.lower()
                is_dm = bool(p.get("is_dm"))
                if pid_low:
                    dedup_k = (is_dm, pid_low)
                    if dedup_k in seen_pids:
                        continue
                    seen_pids.add(dedup_k)
                    if pid_low in known_ids:
                        continue
                title_low = str(p.get("title") or "").strip().lower()
                pub = str(p.get("published_at") or "").strip()[:10]
                if title_low and pub and (title_low, pub) in known_title_dates:
                    continue
                if known_filenames:
                    att_names = [
                        os.path.basename(str(a.get("name") or "")).strip().lower()
                        for a in (p.get("attachments") or [])
                        if isinstance(a, dict) and a.get("name")
                    ]
                    if att_names and all(an in known_filenames for an in att_names):
                        continue
                p["is_on_disk"] = False
                missing.append(p)

            def _apply():
                if gen != self._new_posts_gen:
                    return
                self._is_checking_new_posts = False
                if err_msg:
                    self._new_posts_list = []
                    self._new_posts_status_text = f"Update check failed: {err_msg}"
                    self.newPostsStateChanged.emit()
                    self.toastRequested.emit(f"Could not check newer posts for '{cname}': {err_msg}", "warning")
                    return
                self._new_posts_list = missing
                if missing:
                    self._new_posts_status_text = f"Found {len(missing)} newer/missing item(s) for '{cname}' ({prov.display_name})."
                    self.newPostsStateChanged.emit()
                    self.toastRequested.emit(self._new_posts_status_text, "success")
                else:
                    self._new_posts_status_text = f"'{cname}' is up to date on {prov.display_name} — no missing recent posts."
                    self.newPostsStateChanged.emit()
                    self.toastRequested.emit(self._new_posts_status_text, "info")

            self._callOnGui.emit(_apply)

        threading.Thread(target=_worker, daemon=True, name="BrowserCheckNewPosts").start()

    @Slot("QVariantMap")
    def searchCreatorAcrossSites(self, creator_map: Dict[str, Any]) -> None:
        creator = dict(creator_map) if (creator_map and isinstance(creator_map, dict)) else dict(self._selected_creator)
        if not creator:
            self.toastRequested.emit("Select a creator first to search across sites.", "warning")
            return
        cname = str(creator.get("name") or creator.get("creator_id") or "creator").strip()
        pref_svc = str(creator.get("service") or "").strip().lower()
        self._new_posts_gen += 1
        gen = self._new_posts_gen
        self._is_checking_new_posts = True
        self._new_posts_list = []
        self._creator_search_matches = []
        self._new_posts_creator_key = str(creator.get("key") or "").strip()
        self._new_posts_status_text = f"Searching cum.st, Pawchive, and CoomerFans for '{cname}'…"
        self.newPostsStateChanged.emit()

        def _worker():
            matches = self._search_creator_across_sites(cname, pref_svc)

            def _apply():
                if gen != self._new_posts_gen:
                    return
                self._creator_search_matches = matches
                if not matches:
                    self._is_checking_new_posts = False
                    self._new_posts_status_text = f"Could not find '{cname}' on cum.st, Pawchive, or CoomerFans."
                    self.newPostsStateChanged.emit()
                    self.toastRequested.emit(self._new_posts_status_text, "warning")
                elif len(matches) == 1:
                    best = matches[0]
                    updated = self._save_local_creator_link(creator, best)
                    if self._selected_creator.get("key") == creator.get("key"):
                        self._selected_creator = updated
                        self.selectedCreatorChanged.emit()
                    prov = browser_registry.get_provider(str(best.get("provider_id") or ""))
                    b_svc = str(best.get("service") or "")
                    b_cid = str(best.get("creator_id") or "")
                    b_name = str(best.get("name") or cname)
                    if prov and b_svc and b_cid:
                        self._run_new_posts_check_for_target(
                            updated,
                            prov,
                            b_svc,
                            b_cid,
                            b_name,
                            status_prefix=f"Matched '{cname}' → {b_name} ({best.get('service_label', b_svc)} · {best.get('provider_name', prov.display_name)}) — checking posts…",
                        )
                    else:
                        self._is_checking_new_posts = False
                        self._new_posts_status_text = f"Found 1 match for '{cname}'."
                        self.newPostsStateChanged.emit()
                else:
                    self._is_checking_new_posts = False
                    self._new_posts_status_text = f"Found {len(matches)} match(es) across sites for '{cname}' — pick a profile to check for newer posts:"
                    self.newPostsStateChanged.emit()

            self._callOnGui.emit(_apply)

        threading.Thread(target=_worker, daemon=True, name="BrowserCrossSiteCreatorSearch").start()

    @Slot("QVariantMap")
    def selectCreatorMatchAndCheck(self, candidate_map: Dict[str, Any]) -> None:
        if not candidate_map or not isinstance(candidate_map, dict):
            return
        creator = dict(self._selected_creator or {})
        updated = self._save_local_creator_link(creator, candidate_map)
        if creator and self._selected_creator.get("key") == creator.get("key"):
            self._selected_creator = updated
            self.selectedCreatorChanged.emit()
        prov = browser_registry.get_provider(str(candidate_map.get("provider_id") or ""))
        svc = str(candidate_map.get("service") or "").strip().lower()
        cid = str(candidate_map.get("creator_id") or "").strip()
        cname = str(candidate_map.get("name") or updated.get("name") or cid).strip()
        if not prov or not svc or not cid:
            self.toastRequested.emit("Selected match is missing provider details.", "warning")
            return
        if self._browser_mode == "local":
            threading.Thread(
                target=lambda: self._local_library.refresh_catalog(heal_moved_paths=False),
                daemon=True,
            ).start()
        self._run_new_posts_check_for_target(
            updated,
            prov,
            svc,
            cid,
            cname,
            status_prefix=f"Checking {cname} ({candidate_map.get('service_label', svc)} · {prov.display_name}) for newer posts…",
        )

    @Slot("QVariantMap")
    def checkCreatorNewPosts(self, creator_map: Dict[str, Any]) -> None:
        creator = dict(creator_map) if (creator_map and isinstance(creator_map, dict)) else dict(self._selected_creator)
        if not creator:
            self.toastRequested.emit("Select a creator first to check for newer posts.", "warning")
            return

        prov, svc, cid = self._resolve_online_provider(creator, self._get_creator_links())
        cname = str(creator.get("name") or cid or "creator").strip()
        if not prov or not svc or svc == "local" or not cid:
            self.searchCreatorAcrossSites(creator)
            return

        self._creator_search_matches = []
        self._run_new_posts_check_for_target(creator, prov, svc, cid, cname)

    @Slot("QVariantList", bool)
    @Slot("QVariantList")
    def downloadNewPosts(self, urls: Optional[List[str]] = None, auto_start: bool = True) -> int:
        clean_urls = [str(u or "").strip() for u in (urls or []) if str(u or "").strip()]
        if not clean_urls:
            clean_urls = [str(p.get("url") or "").strip() for p in self._new_posts_list if str(p.get("url") or "").strip()]
        if not clean_urls:
            self.toastRequested.emit("No newer post URLs available to download.", "warning")
            return 0
        if not self._app_bridge:
            self.toastRequested.emit("Downloader bridge is not connected.", "warning")
            return 0
        if hasattr(self._app_bridge, "enqueueBatchUrls"):
            self._app_bridge.enqueueBatchUrls(clean_urls, auto_start)
        else:
            self._app_bridge.currentUrl = "\n".join(clean_urls)
            self._app_bridge.startDownload() if auto_start else self._app_bridge.addToQueue()

        url_set = set(clean_urls)
        self._new_posts_list = [p for p in self._new_posts_list if str(p.get("url") or "").strip() not in url_set]
        self._new_posts_status_text = f"Queued {len(clean_urls)} newer post(s) in Downloader."
        self.newPostsStateChanged.emit()
        self.toastRequested.emit(self._new_posts_status_text, "success")
        return len(clean_urls)

    def _resolve_creator_url(self, creator_map: Optional[Dict[str, Any]] = None) -> str:
        creator = dict(creator_map) if (creator_map and isinstance(creator_map, dict)) else dict(self._selected_creator or {})
        if not creator:
            return ""
        raw_url = str(creator.get("url") or "").strip()
        if raw_url.startswith(("http://", "https://")):
            return normalize_archive_url(raw_url)
        prov, svc, cid = self._resolve_online_provider(creator, self._get_creator_links())
        if prov and svc and svc != "local" and cid:
            built = str(prov.build_creator_url(svc, cid) or "").strip()
            if built:
                return normalize_archive_url(built)
        if raw_url:
            return raw_url
        for d in (creator.get("local_dirs") or []):
            d_str = str(d or "").strip()
            if d_str:
                return QUrl.fromLocalFile(d_str).toString()
        return ""

    def _resolve_post_online_context(
        self, post_map: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], str, str, str, str, str]:
        post = dict(post_map) if (post_map and isinstance(post_map, dict)) else dict(self._selected_post or {})
        if not post:
            return {}, "", "", "", "", ""
        svc = str(post.get("service") or "").strip().lower()
        cid = str(post.get("creator_id") or "").strip()
        pid = str(post.get("post_id") or "").strip()
        prov_id = str(post.get("provider_id") or "").strip().lower()
        is_dm = bool(post.get("is_dm"))
        url = str(post.get("url") or "").strip()

        if svc in ("", "local") or not cid or not prov_id:
            source_creator = dict(self._selected_creator or {})
            if not source_creator:
                source_creator = {
                    "provider_id": prov_id,
                    "service": svc,
                    "creator_id": cid,
                    "name": post.get("creator_name") or "",
                    "key": f"{prov_id}:{svc}:{cid}" if (prov_id and svc and cid) else "",
                }
            r_prov, r_svc, r_cid = self._resolve_online_provider(source_creator, self._get_creator_links())
            if r_prov and r_svc and r_cid:
                prov_id = r_prov.provider_id
                svc = r_svc
                cid = r_cid

        if not url:
            url = LocalLibraryService._build_post_online_url(prov_id, svc, cid, pid, is_dm=is_dm)
        if not url and prov_id and svc and svc != "local" and cid and pid and pid != "root_files":
            prov = browser_registry.get_provider(prov_id)
            if prov:
                url = prov.build_dm_url(svc, cid, pid) if is_dm else prov.build_post_url(svc, cid, pid)
        return post, prov_id, svc, cid, pid, normalize_archive_url(str(url or "").strip())

    def _resolve_post_url(self, post_map: Optional[Dict[str, Any]] = None) -> str:
        post, _prov_id, _svc, _cid, _pid, url = self._resolve_post_online_context(post_map)
        if url:
            return url
        if not post:
            return ""
        folder = str(post.get("local_folder") or "").strip()
        if folder:
            return QUrl.fromLocalFile(folder).toString()
        for att in post.get("attachments") or []:
            if isinstance(att, dict):
                lp = str(att.get("local_path") or "").strip()
                if lp:
                    return QUrl.fromLocalFile(os.path.dirname(lp)).toString()
        return ""

    def _resolve_attachment_url(
        self,
        att_map: Optional[Dict[str, Any]] = None,
        _post_map: Optional[Dict[str, Any]] = None,
    ) -> str:
        att = dict(att_map) if (att_map and isinstance(att_map, dict)) else {}
        if not att:
            return ""
        for key in ("url", "source_url", "sourceUrl"):
            val = str(att.get(key) or "").strip()
            if val:
                return val
        local_path = str(att.get("local_path") or att.get("localPath") or "").strip()
        if local_path:
            return QUrl.fromLocalFile(local_path).toString()
        thumb = str(att.get("thumbnail_url") or att.get("thumbnailUrl") or "").strip()
        return thumb

    def _copy_text(self, text: str, label: str = "Link") -> bool:
        clean = str(text or "").strip()
        if not clean:
            self.toastRequested.emit(f"No {label.lower()} available to copy.", "warning")
            return False
        try:
            if self._app_bridge and hasattr(self._app_bridge, "copyToClipboard"):
                self._app_bridge.copyToClipboard(clean)
            else:
                from PySide6.QtGui import QGuiApplication
                cb = QGuiApplication.clipboard()
                if cb:
                    cb.setText(clean)
            self.toastRequested.emit(f"{label} copied to clipboard.", "success")
            return True
        except Exception as e:
            logger.debug(f"[BrowserBridge] Failed to copy {label.lower()}: {e}", category="system")
            self.toastRequested.emit(f"Could not copy {label.lower()}.", "error")
            return False

    @Slot("QVariantMap", result=str)
    def resolveCreatorUrl(self, creator_map: Dict[str, Any]) -> str:
        return self._resolve_creator_url(creator_map)

    @Slot("QVariantMap", result=str)
    def resolvePostUrl(self, post_map: Dict[str, Any]) -> str:
        return self._resolve_post_url(post_map)

    @Slot("QVariantMap", "QVariantMap", result=str)
    def resolveAttachmentUrl(self, att_map: Dict[str, Any], post_map: Dict[str, Any]) -> str:
        return self._resolve_attachment_url(att_map, post_map)

    @Slot(str, result=bool)
    def copyLink(self, url: str) -> bool:
        return self._copy_text(url, "Link")

    @Slot(str, str, result=bool)
    def copyLabeledLink(self, url: str, label: str) -> bool:
        return self._copy_text(url, label or "Link")

    @Slot("QVariantMap", result=bool)
    def copyCreatorLink(self, creator_map: Dict[str, Any]) -> bool:
        return self._copy_text(self._resolve_creator_url(creator_map), "Creator link")

    @Slot("QVariantMap", result=bool)
    def copyPostLink(self, post_map: Dict[str, Any]) -> bool:
        return self._copy_text(self._resolve_post_url(post_map), "Post link")

    @Slot("QVariantMap", "QVariantMap", result=bool)
    def copyAttachmentLink(self, att_map: Dict[str, Any], post_map: Dict[str, Any]) -> bool:
        return self._copy_text(self._resolve_attachment_url(att_map, post_map), "File link")

    @Slot("QVariantMap", result=bool)
    def redownloadPost(self, post_map: Dict[str, Any]) -> bool:
        post, _prov_id, svc, _cid, pid, url = self._resolve_post_online_context(post_map)
        if not post:
            self.toastRequested.emit("Select a post first to redownload it.", "warning")
            return False

        if not url:
            self.toastRequested.emit("This local post folder doesn't have an online source URL to redownload.", "warning")
            return False
        if not self._app_bridge:
            self.toastRequested.emit("Downloader bridge is not connected.", "warning")
            return False

        arch_mgr = getattr(self._app_bridge, "archive_manager", None)
        if arch_mgr and svc and pid:
            try:
                arch_mgr.delete_by_post(svc, pid)
            except Exception as e:
                logger.debug(f"[BrowserBridge] Could not clear archive entry for post {svc}:{pid}: {e}", category="archive")

        if hasattr(self._app_bridge, "enqueueBatchUrls"):
            self._app_bridge.enqueueBatchUrls([url], True, True)
        else:
            self._app_bridge.currentUrl = url
            self._app_bridge.startDownload()

        title = str(post.get("title") or pid or "post").strip()
        self.toastRequested.emit(f"Queued '{title}' for fresh redownload (overwriting existing files).", "success")
        return True

    @Slot(str, str)
    def moveCreatorToDrive(self, creator_key: str, target_root_dir: str) -> None:
        """
        Relocates an artist's on-disk folder(s) to another drive/folder in a background thread,
        emitting live progress for the Newtonian progress bar and syncing ArchiveManager + Watchlist.
        """
        clean_target = (target_root_dir or "").replace("file:///", "").replace("file://", "").strip()
        if not creator_key or not clean_target:
            return
        self._relocate_cancel.clear()

        def _on_prog(done: int, total: int, fname: str):
            self._callOnGui.emit(lambda: self.relocationProgress.emit(creator_key, done, total, fname))

        def _worker():
            res = self._local_library.relocate_creator_to_drive(
                creator_key=creator_key,
                target_root_dir=clean_target,
                cancel_event=self._relocate_cancel,
                progress_cb=_on_prog,
            )

            def _done():
                ok = bool(res.get("ok"))
                if ok:
                    msg = f"Moved {res.get('moved', 0)} file(s) to {res.get('dest_dir', clean_target)} ({res.get('relocated_records', 0)} archive records updated)."
                    self.toastRequested.emit(msg, "success")
                else:
                    msg = str(res.get("error") or (res.get("errors") or ["Move failed"])[0])
                    self.toastRequested.emit(msg, "error")
                self.relocationFinished.emit(creator_key, ok, msg)
                self.localDrivesChanged.emit()
                self.refresh(False)

            self._callOnGui.emit(_done)

        threading.Thread(target=_worker, daemon=True, name="BrowserDriveMoveWorker").start()

    @Slot()
    def cancelMoveCreator(self) -> None:
        self._relocate_cancel.set()
