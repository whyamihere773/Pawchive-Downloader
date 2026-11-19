"""
Persistent Selection Cart (`BrowserMarkManager`) for Pawchive Dual-Mode Browser.
Decomposed from bridge/browser_bridge.py to keep modules cohesive and under 1,000 lines.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from core.atomic_io import atomic_write_json
from core.logger import logger
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
