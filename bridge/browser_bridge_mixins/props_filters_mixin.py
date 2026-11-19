"""
BrowserBridge QML Properties & Filter/Pagination Controls Mixin
Decomposed from bridge/browser_bridge.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Set

from PySide6.QtCore import Property, QObject, Slot

from bridge.browser_bridge_mixins.signals_mixin import BrowserSignalsMixin
from core.browser_providers import browser_registry


class BrowserPropsFiltersMixin(BrowserSignalsMixin):
    """Exposes BrowserBridge QML properties and filter/pagination control slots."""

    @Property(QObject, constant=True)
    def creatorsModel(self) -> RecordListModel:
        return self._creators_model

    @Property(QObject, constant=True)
    def postsModel(self) -> RecordListModel:
        return self._posts_model

    @Property(QObject, constant=True)
    def markedItemsModel(self) -> RecordListModel:
        return self._marked_model

    @Property("QVariantList", notify=BrowserSignalsMixin.providersManifestChanged)
    def providersManifest(self) -> List[Dict[str, Any]]:
        return browser_registry.get_ui_manifest()

    @Property(str, notify=BrowserSignalsMixin.browserModeChanged)
    def browserMode(self) -> str:
        return self._browser_mode

    @Property(str, notify=BrowserSignalsMixin.activeProviderChanged)
    def activeProvider(self) -> str:
        return self._active_provider

    @Property("QVariantMap", notify=BrowserSignalsMixin.activeProviderChanged)
    def activeProviderManifest(self) -> Dict[str, Any]:
        prov = browser_registry.get_provider(self._active_provider)
        if prov:
            return prov.get_manifest_entry()
        active = browser_registry.get_active_providers()
        return active[0].get_manifest_entry() if active else {}

    @Property(str, notify=BrowserSignalsMixin.filterStateChanged)
    def activeService(self) -> str:
        return self._active_service

    @Property(str, notify=BrowserSignalsMixin.filterStateChanged)
    def activeSort(self) -> str:
        return self._active_sort

    @Property(str, notify=BrowserSignalsMixin.filterStateChanged)
    def activeTag(self) -> str:
        return self._active_tag

    @Property(str, notify=BrowserSignalsMixin.filterStateChanged)
    def activeDriveFilter(self) -> str:
        return self._active_drive

    @Property(str, notify=BrowserSignalsMixin.filterStateChanged)
    def searchQuery(self) -> str:
        return self._search_query

    @Property(str, notify=BrowserSignalsMixin.filterStateChanged)
    def searchTarget(self) -> str:
        return self._search_target

    @Property(int, notify=BrowserSignalsMixin.paginationChanged)
    def currentOffset(self) -> int:
        return self._offset

    @Property(int, notify=BrowserSignalsMixin.paginationChanged)
    def pageSize(self) -> int:
        return self._page_size

    @Property(int, notify=BrowserSignalsMixin.paginationChanged)
    def totalCount(self) -> int:
        return self._total_count

    @Property(int, notify=BrowserSignalsMixin.paginationChanged)
    def currentPage(self) -> int:
        return (self._offset // max(1, self._page_size)) + 1

    @Property(int, notify=BrowserSignalsMixin.paginationChanged)
    def totalPages(self) -> int:
        if self._total_count <= 0:
            return 1
        return max(1, (self._total_count + self._page_size - 1) // max(1, self._page_size))

    @Property(bool, notify=BrowserSignalsMixin.paginationChanged)
    def hasMore(self) -> bool:
        return self._has_more

    @Property(bool, notify=BrowserSignalsMixin.loadingStateChanged)
    def isLoading(self) -> bool:
        return self._is_loading

    @Property(str, notify=BrowserSignalsMixin.loadingStateChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=BrowserSignalsMixin.loadingStateChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(bool, notify=BrowserSignalsMixin.loadingStateChanged)
    def authRequired(self) -> bool:
        return self._auth_required

    @Property(bool, notify=BrowserSignalsMixin.activeProviderAuthChanged)
    def activeProviderLoggedIn(self) -> bool:
        from core.auth_manager import auth_manager
        return auth_manager.is_logged_in(self._active_provider)

    @Property(str, notify=BrowserSignalsMixin.activeProviderAuthChanged)
    def activeProviderUsername(self) -> str:
        from core.auth_manager import auth_manager
        summary = auth_manager.get_provider_summary(self._active_provider)
        return str(summary.get("username") or "")

    @Property(bool, notify=BrowserSignalsMixin.activeProviderAuthChanged)
    def isLoggingInProvider(self) -> bool:
        return bool(getattr(self, "_is_logging_in_provider", False))

    @Property("QVariantMap", notify=BrowserSignalsMixin.selectedCreatorChanged)
    def selectedCreator(self) -> Dict[str, Any]:
        return self._selected_creator

    @Property(bool, notify=BrowserSignalsMixin.selectedCreatorChanged)
    def hasSelectedCreator(self) -> bool:
        return bool(self._selected_creator and self._selected_creator.get("key"))

    @Property(str, notify=BrowserSignalsMixin.filterStateChanged)
    def creatorSection(self) -> str:
        return self._creator_section

    @Property(bool, notify=BrowserSignalsMixin.selectedCreatorChanged)
    def creatorSupportsDms(self) -> bool:
        if not self._selected_creator or self._browser_mode == "local":
            return False
        prov, svc, cid = self._resolve_online_provider(self._selected_creator, self._get_creator_links())
        return bool(prov and svc and svc != "local" and cid and getattr(prov.capabilities(), "supports_dms", False))

    @Property(int, notify=BrowserSignalsMixin.selectedCreatorChanged)
    def creatorPostsTotal(self) -> int:
        return self._creator_posts_total

    @Property(int, notify=BrowserSignalsMixin.selectedCreatorChanged)
    def creatorPostsOffset(self) -> int:
        return self._creator_posts_offset

    @Property(bool, notify=BrowserSignalsMixin.selectedCreatorChanged)
    def creatorPostsHasMore(self) -> bool:
        return self._creator_posts_has_more

    @Property("QVariantMap", notify=BrowserSignalsMixin.selectedPostChanged)
    def selectedPost(self) -> Dict[str, Any]:
        return self._selected_post

    @Property(bool, notify=BrowserSignalsMixin.selectedPostChanged)
    def hasSelectedPost(self) -> bool:
        return bool(self._selected_post and self._selected_post.get("key"))

    @Property(int, notify=BrowserSignalsMixin.marksChanged)
    def markedCount(self) -> int:
        return len(self._mark_manager.all_items())

    @Property(int, notify=BrowserSignalsMixin.marksChanged)
    def markedCreatorsCount(self) -> int:
        return sum(1 for it in self._mark_manager.all_items() if it.get("item_type") == "creator")

    @Property(int, notify=BrowserSignalsMixin.marksChanged)
    def markedPostsCount(self) -> int:
        return sum(1 for it in self._mark_manager.all_items() if it.get("item_type") != "creator")

    @Property("QVariantList", notify=BrowserSignalsMixin.localDrivesChanged)
    def localDrives(self) -> List[Dict[str, Any]]:
        return self._local_library.get_available_drives_summary()

    @Property("QVariantList", notify=BrowserSignalsMixin.localDrivesChanged)
    def relocateTargetDrives(self) -> List[Dict[str, Any]]:
        return self._local_library.get_available_drives_summary(include_excluded=True)

    @Property("QVariantList", notify=BrowserSignalsMixin.localDrivesChanged)
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

    @Property("QVariantList", notify=BrowserSignalsMixin.localDrivesChanged)
    def localLibraryRoots(self) -> List[str]:
        return self._local_library.get_all_library_roots()

    @Property(bool, notify=BrowserSignalsMixin.newPostsStateChanged)
    def isCheckingNewPosts(self) -> bool:
        return self._is_checking_new_posts

    @Property("QVariantList", notify=BrowserSignalsMixin.newPostsStateChanged)
    def newPostsList(self) -> List[Dict[str, Any]]:
        return self._new_posts_list

    @Property(int, notify=BrowserSignalsMixin.newPostsStateChanged)
    def newPostsCount(self) -> int:
        return len(self._new_posts_list)

    @Property("QVariantList", notify=BrowserSignalsMixin.newPostsStateChanged)
    def creatorSearchMatches(self) -> List[Dict[str, Any]]:
        return self._creator_search_matches

    @Property(int, notify=BrowserSignalsMixin.newPostsStateChanged)
    def creatorSearchMatchCount(self) -> int:
        return len(self._creator_search_matches)

    @Property(str, notify=BrowserSignalsMixin.newPostsStateChanged)
    def newPostsCreatorKey(self) -> str:
        return self._new_posts_creator_key

    @Property(str, notify=BrowserSignalsMixin.newPostsStateChanged)
    def newPostsStatusText(self) -> str:
        return self._new_posts_status_text

    @Property(str, notify=BrowserSignalsMixin.lastDownloadDirChanged)
    def lastDownloadDir(self) -> str:
        if self._app_bridge and hasattr(self._app_bridge, "browserLastDownloadDir"):
            val = str(self._app_bridge.browserLastDownloadDir or "").strip()
            if val:
                return val
        return str(self._read_settings().get("browser_last_download_dir") or "").strip()

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
