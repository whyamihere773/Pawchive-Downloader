"""
DecompressorBridge Archive List, Virtualized Groups, Scanning & Selection Mixin
Decomposed from bridge/decompressor_bridge.py to keep modules cohesive and under 1,000 lines.
"""

import json
import os
import sys
import threading
from typing import Any, Dict, List

from PySide6.QtCore import Property, QObject, Slot
from PySide6.QtWidgets import QFileDialog

from bridge.archive_creators_model import RecordListModel
from bridge.decompressor_mixins.compression_mixin import _format_bytes
from bridge.decompressor_mixins.signals_mixin import DecompressorSignalsMixin
from core.logger import logger
from core.path_utils import subprocess_env_kwargs


class DecompressorItemsGroupsMixin(DecompressorSignalsMixin):
    """Archive scanning, custom folders, selection controls, disk checks, and virtualized groups."""

    @Property(bool, notify=DecompressorSignalsMixin.isBusyChanged)
    def isBusy(self) -> bool:
        return self._is_scanning or self._is_extracting

    @Property(bool, notify=DecompressorSignalsMixin.isScanningChanged)
    def isScanning(self) -> bool:
        return self._is_scanning

    @Property(bool, notify=DecompressorSignalsMixin.isExtractingChanged)
    def isExtracting(self) -> bool:
        return self._is_extracting

    @Property(int, notify=DecompressorSignalsMixin.itemsChanged)
    def totalCount(self) -> int:
        with self._items_lock:
            return len(self._items)

    @Property(int, notify=DecompressorSignalsMixin.selectedStatsChanged)
    def selectedCount(self) -> int:
        with self._items_lock:
            return sum(1 for i in self._items if i.selected)

    @Property("qint64", notify=DecompressorSignalsMixin.itemsChanged)
    def totalBytes(self) -> int:
        with self._items_lock:
            return sum(i.size for i in self._items)

    @Property("qint64", notify=DecompressorSignalsMixin.selectedStatsChanged)
    def selectedBytes(self) -> int:
        with self._items_lock:
            return sum(i.size for i in self._items if i.selected)

    @Property(int, notify=DecompressorSignalsMixin.settingsChanged)
    def maxParallel(self) -> int:
        return self._max_parallel

    @maxParallel.setter
    def maxParallel(self, val: int):
        v = max(1, min(8, int(val)))
        if self._max_parallel != v:
            self._max_parallel = v
            self.settingsChanged.emit()

    @Property(int, notify=DecompressorSignalsMixin.settingsChanged)
    def threadsPerArchive(self) -> int:
        return self._threads_per_archive

    @threadsPerArchive.setter
    def threadsPerArchive(self, val: int):
        v = max(1, min(16, int(val)))
        if self._threads_per_archive != v:
            self._threads_per_archive = v
            self.settingsChanged.emit()

    @Property(bool, notify=DecompressorSignalsMixin.settingsChanged)
    def deleteAfter(self) -> bool:
        return self._delete_after

    @deleteAfter.setter
    def deleteAfter(self, val: bool):
        if self._delete_after != bool(val):
            self._delete_after = bool(val)
            self.settingsChanged.emit()

    @Property(bool, notify=DecompressorSignalsMixin.settingsChanged)
    def autoPromptPasswords(self) -> bool:
        return self._auto_prompt_passwords

    @autoPromptPasswords.setter
    def autoPromptPasswords(self, val: bool):
        if self._auto_prompt_passwords != bool(val):
            self._auto_prompt_passwords = bool(val)
            self.settingsChanged.emit()

    @Property(str, notify=DecompressorSignalsMixin.itemsChanged)
    def itemsJson(self) -> str:
        with self._items_lock:
            data = [i.to_dict() for i in self._items]
        return json.dumps(data, ensure_ascii=False)

    @Property(QObject, constant=True)
    def groupsModel(self) -> RecordListModel:
        return self._groups_model

    @Slot(str)
    def setSearch(self, text: str):
        self._search = str(text or "").strip().lower()
        self._refresh_groups()

    @Property(int, notify=DecompressorSignalsMixin.groupCountChanged)
    def groupCount(self) -> int:
        """Groups (creator + folder) shown."""
        return self._group_count

    @Property(bool, notify=DecompressorSignalsMixin.groupCountChanged)
    def anyCollapsed(self) -> bool:
        """Some group shown is folded ("Expand All" instead of "Collapse All")."""
        return self._any_collapsed

    @Slot(str)
    def toggleGroupCollapsed(self, key: str):
        self._collapsed.symmetric_difference_update({key})
        self._refresh_groups()

    @Slot(bool)
    def setAllCollapsed(self, collapsed: bool):
        if collapsed:
            self._collapsed = {g["groupKey"] for g in self._build_groups()}
        else:
            self._collapsed = set()
        self._refresh_groups()

    def _groups_soon(self, *args):
        self._groups_timer.start(0)

    def _groups_later(self, *args):
        if not self._groups_timer.isActive():
            self._groups_timer.start(400)

    def _build_groups(self) -> List[Dict[str, Any]]:
        q = self._search
        with self._items_lock:
            groups: Dict[tuple, Dict[str, Any]] = {}
            for item in self._items:
                c = item.creator or "Unknown"
                if q and q not in c.lower() and q not in item.filename.lower() and q not in item.directory.lower():
                    continue
                raw_root = item.scan_root or item.directory
                key = (c, os.path.normcase(os.path.normpath(raw_root)) if raw_root else "")
                g = groups.get(key)
                if g is None:
                    g = groups[key] = {"creator": c, "directory": raw_root, "groupKey": f"{c}|{raw_root}",
                                       "items": [], "totalCount": 0, "selectedCount": 0, "totalBytes": 0,
                                       "selectedBytes": 0}
                g["items"].append(item.to_dict())
                g["totalCount"] += 1
                g["totalBytes"] += item.size
                if item.selected:
                    g["selectedCount"] += 1
                    g["selectedBytes"] += item.size
        out = list(groups.values())
        for g in out:
            g["allSelected"] = g["totalCount"] > 0 and g["selectedCount"] == g["totalCount"]
            g["someSelected"] = 0 < g["selectedCount"] < g["totalCount"]
        return out

    def _build_rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        groups = self._build_groups()
        for g in groups:
            key = g["groupKey"]
            collapsed = key in self._collapsed
            items = g.pop("items")
            g.update(kind="group", rowKey="g|" + key, collapsed=collapsed)
            rows.append(g)
            if not collapsed:
                for it in items:
                    it.update(kind="item", rowKey="i|" + it["id"], groupKey=key)
                    rows.append(it)
        any_collapsed = any(r.get("collapsed") for r in rows if r["kind"] == "group")
        if self._group_count != len(groups) or self._any_collapsed != any_collapsed:
            self._group_count = len(groups)
            self._any_collapsed = any_collapsed
            self.groupCountChanged.emit()
        return rows

    def _refresh_groups(self):
        self._groups_timer.stop()
        self._groups_model.set_creators(self._build_rows())

    @Property(str, notify=DecompressorSignalsMixin.itemsChanged)
    def groupedItemsJson(self) -> str:
        """Returns archives grouped hierarchically by (creator, scan_root) so that
        the same creator with multiple watched download folders appears as separate groups."""
        with self._items_lock:
            # Key: (creator_name, norm_scan_root) — unique per watched folder, stable across subdirs
            groups_dict: Dict[tuple, Dict[str, Any]] = {}
            for item in self._items:
                c = item.creator or "Unknown"
                raw_root = item.scan_root or item.directory
                norm_root = os.path.normcase(os.path.normpath(raw_root)) if raw_root else ""
                key = (c, norm_root)
                if key not in groups_dict:
                    groups_dict[key] = {
                        "creator": c,
                        "directory": item.scan_root or item.directory,
                        "items": [],
                        "totalCount": 0,
                        "selectedCount": 0,
                        "totalBytes": 0,
                        "selectedBytes": 0,
                    }
                g = groups_dict[key]
                g["items"].append(item.to_dict())
                g["totalCount"] += 1
                g["totalBytes"] += item.size
                if item.selected:
                    g["selectedCount"] += 1
                    g["selectedBytes"] += item.size

            groups_list = list(groups_dict.values())
            for g in groups_list:
                g["allSelected"] = (g["totalCount"] > 0 and g["selectedCount"] == g["totalCount"])
                g["someSelected"] = (g["selectedCount"] > 0 and g["selectedCount"] < g["totalCount"])

        return json.dumps(groups_list, ensure_ascii=False)

    @Property(str, notify=DecompressorSignalsMixin.locationsChanged)
    def locationsJson(self) -> str:
        locs = self._get_all_target_locations()
        return json.dumps(locs, ensure_ascii=False)

    @Property(bool, constant=True)
    def has7za(self) -> bool:
        return self.engine.has_7za

    def _get_all_target_locations(self) -> List[Dict[str, str]]:
        """Combine watchlist locations with any user-added custom folder locations."""
        locations = []
        # 1. Watchlist entries
        if self._watchlist_manager:
            for e in self._watchlist_manager.entries:
                p = e.download_dir.strip() if e.download_dir else ""
                # If download_dir not set on entry, check default download folder with creator subfolder
                if not p and self._app_bridge:
                    default_base = getattr(self._app_bridge, "downloadDir", "")
                    if default_base and os.path.exists(default_base):
                        cand = os.path.join(default_base, f"{e.creator_name} [{e.service}]")
                        if os.path.exists(cand):
                            p = cand
                        else:
                            p = default_base
                if p and os.path.exists(p):
                    # If p is a parent directory, check if a dedicated creator subfolder exists inside it
                    if os.path.isdir(p) and e.creator_name:
                        expected = [
                            f"{e.creator_name} [{e.service}]".lower() if e.service else "",
                            e.creator_name.lower()
                        ]
                        try:
                            for sub in os.listdir(p):
                                sub_lower = sub.lower()
                                if any(sub_lower == exp for exp in expected if exp) or (
                                    e.service and sub_lower.startswith(f"{e.creator_name.lower()} [")
                                ):
                                    cand = os.path.join(p, sub)
                                    if os.path.isdir(cand):
                                        p = cand
                                        break
                        except OSError:
                            pass

                    locations.append({
                        "path": p,
                        "creator": e.creator_name or e.user_id,
                        "source": "watchlist"
                    })

        # 2. Custom manually added locations
        for c in self._custom_locations:
            locations.append({
                "path": c["path"],
                "creator": c.get("creator", "Custom"),
                "source": "custom"
            })

        # Deduplicate paths
        unique = []
        seen = set()
        for loc in locations:
            norm = os.path.normcase(os.path.normpath(loc["path"]))
            if norm not in seen:
                seen.add(norm)
                unique.append(loc)
        return unique

    @Slot()
    def scanLocations(self):
        """Asynchronously scan all configured locations (watchlist + custom) for archives."""
        if self._is_scanning or self._is_extracting:
            return

        self._is_scanning = True
        self._scan_cancel_event.clear()
        self.isScanningChanged.emit()
        self.isBusyChanged.emit()
        self.scanStarted.emit()

        targets = [(loc["path"], loc["creator"]) for loc in self._get_all_target_locations()]
        logger.info(f"Scanning {len(targets)} location(s) for archives...", category="decompressor")

        def _worker():
            try:
                scanned = self.engine.scan_locations(targets, self._scan_cancel_event)
                with self._items_lock:
                    self._items = scanned
                total_sz = sum(i.size for i in scanned)
                self._is_scanning = False
                self.isScanningChanged.emit()
                self.isBusyChanged.emit()
                self.itemsChanged.emit()
                self.selectedStatsChanged.emit()
                self.scanFinished.emit(len(scanned), total_sz)
                logger.info(
                    f"Scan complete: found {len(scanned)} archive(s) ({_format_bytes(total_sz)}).",
                    category="decompressor"
                )
            except Exception as e:
                logger.error(f"Scan error: {e}", category="decompressor")
                self._is_scanning = False
                self.isScanningChanged.emit()
                self.isBusyChanged.emit()
                self.scanError.emit(str(e))

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def browseCustomFolder(self):
        """Open folder dialog to add a custom folder and re-scan."""
        start_dir = getattr(self._app_bridge, "downloadDir", "") if self._app_bridge else ""
        folder = QFileDialog.getExistingDirectory(
            None,
            "Select Folder to Scan for Archives",
            start_dir
        )
        if folder:
            norm = os.path.normcase(os.path.normpath(folder))
            if not any(os.path.normcase(os.path.normpath(c["path"])) == norm for c in self._custom_locations):
                self._custom_locations.append({
                    "path": folder,
                    "creator": os.path.basename(folder) or "Custom",
                    "source": "custom"
                })
                logger.info(f"Added custom folder to decompressor: {folder}", category="decompressor")
                self.locationsChanged.emit()
            self.scanLocations()

    @Slot(int)
    def removeCustomLocation(self, index: int):
        """Remove a custom folder at index."""
        if 0 <= index < len(self._custom_locations):
            self._custom_locations.pop(index)
            self.locationsChanged.emit()

    @Slot(bool)
    def selectAll(self, selected: bool):
        with self._items_lock:
            for item in self._items:
                item.selected = selected
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str, bool)
    def selectCreator(self, creatorName: str, selected: bool):
        with self._items_lock:
            for item in self._items:
                if item.creator == creatorName:
                    item.selected = selected
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str, str, bool)
    def selectCreatorByScanRoot(self, creatorName: str, scanRoot: str, selected: bool):
        """Select/deselect all archives for a specific creator+folder pair."""
        norm = os.path.normcase(os.path.normpath(scanRoot)) if scanRoot else ""
        with self._items_lock:
            for item in self._items:
                item_root = os.path.normcase(os.path.normpath(item.scan_root or item.directory))
                if item.creator == creatorName and item_root == norm:
                    item.selected = selected
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str)
    def toggleCreator(self, creatorName: str):
        """Toggle selection for all archives of a specific creator."""
        with self._items_lock:
            creator_items = [i for i in self._items if i.creator == creatorName]
            all_sel = all(i.selected for i in creator_items) if creator_items else False
            new_val = not all_sel
            for item in creator_items:
                item.selected = new_val
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str, str)
    def toggleCreatorByScanRoot(self, creatorName: str, scanRoot: str):
        """Toggle selection for all archives of a specific creator+folder pair."""
        norm = os.path.normcase(os.path.normpath(scanRoot)) if scanRoot else ""
        with self._items_lock:
            creator_items = [i for i in self._items
                             if i.creator == creatorName and os.path.normcase(os.path.normpath(i.scan_root or i.directory)) == norm]
            all_sel = all(i.selected for i in creator_items) if creator_items else False
            new_val = not all_sel
            for item in creator_items:
                item.selected = new_val
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str)
    def toggleItem(self, itemId: str):
        with self._items_lock:
            for item in self._items:
                if item.item_id == itemId:
                    item.selected = not item.selected
                    break
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(result=str)
    def checkDiskSpace(self) -> str:
        """Run disk space check and return JSON results."""
        with self._items_lock:
            items_copy = list(self._items)
        results = self.engine.check_disk_space(items_copy, delete_after=self._delete_after)
        data = [r.to_dict() for r in results]
        res_json = json.dumps(data, ensure_ascii=False)
        self.diskCheckCompleted.emit(res_json)
        return res_json

    @Slot()
    def clearFinished(self):
        """Remove completed entries from the list."""
        with self._items_lock:
            self._items = [i for i in self._items if i.status != "done"]
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str)
    def openFolder(self, path: str):
        """Open the enclosing folder in the OS file manager."""
        if not path:
            return
        target = path if os.path.isdir(path) else os.path.dirname(path)
        if os.path.exists(target):
            import subprocess
            if sys.platform == "win32":
                subprocess.Popen(["explorer", os.path.normpath(target)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target], **subprocess_env_kwargs())
            else:
                subprocess.Popen(["xdg-open", target], **subprocess_env_kwargs())
