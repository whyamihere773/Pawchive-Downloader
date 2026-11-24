"""
Modular Dual-Mode Browser QML Bridge (`BrowserBridge`) & Persistent Mark Cart (`BrowserMarkManager`).

Connects the capability-driven `BrowserProviderRegistry` (Online Mode) and
`LocalLibraryService` (Multi-Drive Local Disk Mode) to `qml/views/BrowserView.qml`.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Qt, Slot

from bridge.archive_creators_model import RecordListModel
from bridge.browser_bridge_mixins import (
    BrowserAuthFavoritesMixin,
    BrowserCartDispatchMixin,
    BrowserFetchPostsMixin,
    BrowserLinksRelocateMixin,
    BrowserLocalNewPostsMixin,
    BrowserPropsFiltersMixin,
)
from bridge.browser_mark_manager import BrowserMarkManager
from core.atomic_io import atomic_write_json
from core.browser_media_service import BrowserMediaService
from core.browser_providers import browser_registry
from core.local_library import LocalLibraryService
from core.logger import logger
from core.path_utils import get_config_dir


class BrowserBridge(
    QObject,
    BrowserPropsFiltersMixin,
    BrowserFetchPostsMixin,
    BrowserCartDispatchMixin,
    BrowserAuthFavoritesMixin,
    BrowserLocalNewPostsMixin,
    BrowserLinksRelocateMixin,
):
    """
    QML Bridge for the Top-Level Native Browser Tab (`BrowserView.qml`).
    Supports both Online Mode (via `browser_registry`) and Multi-Drive Local Mode (via `LocalLibraryService`).
    """

    def __init__(self, app_bridge=None, config_dir: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._callOnGui.connect(self._run_on_gui, Qt.QueuedConnection)
        self._app_bridge = app_bridge
        if app_bridge is not None:
            try:
                app_bridge._browser_bridge = self
            except Exception:
                pass

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
