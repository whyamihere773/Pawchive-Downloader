"""
Decompressor Bridge
Exposes BulkDecompressorEngine to QML with reactive properties,
async worker threads, live progress parsing, and ETA calculations.
"""

import os
import sys
import json
import time
import shutil
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtWidgets import QFileDialog

from services.bulk_decompressor import (
    BulkDecompressorEngine,
    ArchiveItem,
    DiskCheckResult,
    get_7za_path
)
from core.archive_password_manager import archive_password_manager
from core.logger import logger


def _format_bytes(b: int) -> str:
    if not b or b <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} PB"


class DecompressorBridge(QObject):
    # ── Signals ────────────────────────────────────────────────────────────────
    scanStarted = Signal()
    scanFinished = Signal(int, "qint64")  # count, total_bytes (64-bit to prevent 32-bit overflow)
    scanError = Signal(str)

    itemsChanged = Signal()
    isBusyChanged = Signal()
    isScanningChanged = Signal()
    isExtractingChanged = Signal()
    selectedStatsChanged = Signal()
    settingsChanged = Signal()
    locationsChanged = Signal()

    diskCheckCompleted = Signal(str)  # JSON string of List[DiskCheckResult]

    extractionStarted = Signal()
    extractionProgress = Signal(float, str, float, str, str)  # overall%, cur_name, cur_pct, eta_str, speed_str
    itemUpdated = Signal(str, str, float, str)  # id, status, progress, error_message
    extractionFinished = Signal(int, int)  # success_count, error_count

    # Redecompress confirmation
    redecompressConfirmRequested = Signal(int, int)  # already_done_count, total_selected_count

    # Password management & manual prompt signals
    passwordPromptRequested = Signal(str, str, str, str, str, "qint64")  # itemId, filename, creator, directory, errorMsg, size
    passwordPromptDismissed = Signal(str)  # itemId
    passwordWrong = Signal(str)           # itemId — wrong password entered
    passwordBankChanged = Signal()

    def __init__(self, watchlist_manager, app_bridge=None, parent=None):
        super().__init__(parent)
        self._watchlist_manager = watchlist_manager
        self._app_bridge = app_bridge
        self.engine = BulkDecompressorEngine()

        self._items: List[ArchiveItem] = []
        self._items_lock = threading.RLock()  # Must be re-entrant: signal handlers may read itemsJson (which acquires the lock) while we already hold it
        self._custom_locations: List[Dict[str, str]] = []  # [{"path": ..., "creator": ...}]

        # State flags
        self._is_scanning = False
        self._is_extracting = False
        self._scan_cancel_event = threading.Event()
        self._extract_cancel_event = threading.Event()

        # Password prompt coordination
        self._auto_prompt_passwords = True
        self._skip_all_password_prompts = False
        self._prompt_events: Dict[str, threading.Event] = {}
        self._prompt_responses: Dict[str, Dict[str, Any]] = {}
        self._prompt_lock = threading.Lock()
        # Semaphore: ensures only one password prompt is shown at a time.
        # Parallel workers block here until the current prompt is dismissed.
        self._prompt_serial_sem = threading.Semaphore(1)

        # Configurable Settings
        self._max_parallel = 2
        self._threads_per_archive = 2
        self._delete_after = False

        # Metrics for extraction
        self._total_bytes_to_extract = 0
        self._extracted_bytes_done = 0
        self._start_time = 0.0

        # Reactive password bank binding: selection changes update matched status
        self.selectedStatsChanged.connect(self.passwordBankChanged)
        self.isExtractingChanged.connect(self.passwordBankChanged)

    # ── Properties ─────────────────────────────────────────────────────────────

    @Property(bool, notify=isBusyChanged)
    def isBusy(self) -> bool:
        return self._is_scanning or self._is_extracting

    @Property(bool, notify=isScanningChanged)
    def isScanning(self) -> bool:
        return self._is_scanning

    @Property(bool, notify=isExtractingChanged)
    def isExtracting(self) -> bool:
        return self._is_extracting

    @Property(int, notify=itemsChanged)
    def totalCount(self) -> int:
        with self._items_lock:
            return len(self._items)

    @Property(int, notify=selectedStatsChanged)
    def selectedCount(self) -> int:
        with self._items_lock:
            return sum(1 for i in self._items if i.selected)

    @Property("qint64", notify=itemsChanged)
    def totalBytes(self) -> int:
        with self._items_lock:
            return sum(i.size for i in self._items)

    @Property("qint64", notify=selectedStatsChanged)
    def selectedBytes(self) -> int:
        with self._items_lock:
            return sum(i.size for i in self._items if i.selected)

    @Property(int, notify=settingsChanged)
    def maxParallel(self) -> int:
        return self._max_parallel

    @maxParallel.setter
    def maxParallel(self, val: int):
        v = max(1, min(8, int(val)))
        if self._max_parallel != v:
            self._max_parallel = v
            self.settingsChanged.emit()

    @Property(int, notify=settingsChanged)
    def threadsPerArchive(self) -> int:
        return self._threads_per_archive

    @threadsPerArchive.setter
    def threadsPerArchive(self, val: int):
        v = max(1, min(16, int(val)))
        if self._threads_per_archive != v:
            self._threads_per_archive = v
            self.settingsChanged.emit()

    @Property(bool, notify=settingsChanged)
    def deleteAfter(self) -> bool:
        return self._delete_after

    @deleteAfter.setter
    def deleteAfter(self, val: bool):
        if self._delete_after != bool(val):
            self._delete_after = bool(val)
            self.settingsChanged.emit()

    @Property(bool, notify=settingsChanged)
    def autoPromptPasswords(self) -> bool:
        return self._auto_prompt_passwords

    @autoPromptPasswords.setter
    def autoPromptPasswords(self, val: bool):
        if self._auto_prompt_passwords != bool(val):
            self._auto_prompt_passwords = bool(val)
            self.settingsChanged.emit()

    @Property('QVariant', notify=passwordBankChanged)
    def savedPasswords(self) -> List[str]:
        return archive_password_manager.get_passwords()

    @Property(int, notify=passwordBankChanged)
    def savedPasswordsCount(self) -> int:
        return len(archive_password_manager.get_passwords())

    @Property(str, notify=passwordBankChanged)
    def passwordBankTreeJson(self) -> str:
        """Returns JSON tree of creators and their passwords, with isMatched flags."""
        with self._items_lock:
            if self._is_extracting:
                active_items = [it for it in self._items if it.status in ("extracting", "pending", "password_required")]
                if not active_items:
                    active_items = [it for it in self._items if it.selected]
            else:
                active_items = [it for it in self._items if it.selected]

            active_creators = {it.creator.strip().lower() for it in active_items if it.creator}
            active_passwords = set()
            for it in active_items:
                if it.password:
                    active_passwords.add(it.password.strip())
                mapped = archive_password_manager.get_archive_password(it.path)
                if mapped:
                    active_passwords.add(mapped.strip())

        creator_groups = archive_password_manager.get_passwords_by_creator()
        groups = []
        for creator_name, pws in creator_groups.items():
            is_global = (creator_name == "Global")
            creator_clean = creator_name.strip().lower()
            group_matched = (not is_global and creator_clean in active_creators) or any(p in active_passwords for p in pws)
            pw_list = []
            for p in pws:
                pw_matched = (p in active_passwords) or (not is_global and creator_clean in active_creators)
                pw_list.append({
                    "password": p,
                    "isMatched": pw_matched
                })
            groups.append({
                "creator": creator_name,
                "isGlobal": is_global,
                "isMatched": group_matched,
                "passwords": pw_list,
                "count": len(pw_list)
            })

        # Sort: matched first, then creators A-Z, Global last unless matched
        groups.sort(key=lambda g: (not g["isMatched"], g["isGlobal"], g["creator"].lower()))
        return json.dumps(groups, ensure_ascii=False)

    @Property('QVariant', notify=passwordBankChanged)
    def bankCreatorNames(self) -> List[str]:
        """Returns list of all available creator names for password assignment, sorted alphabetically."""
        creators = set()
        with self._items_lock:
            for it in self._items:
                if it.creator and it.creator.strip():
                    creators.add(it.creator.strip())
        from_bank = archive_password_manager.get_passwords_by_creator().keys()
        for c in from_bank:
            if c and c.strip() and c.strip() != "Global":
                creators.add(c.strip())
        try:
            from core.watchlist_manager import watchlist_manager
            for w in watchlist_manager.get_entries():
                if w.creator and w.creator.strip():
                    creators.add(w.creator.strip())
        except Exception:
            pass
        try:
            from core.link_vault_manager import link_vault_manager
            with link_vault_manager._lock:
                for c_key, c_val in link_vault_manager._data.get("creators", {}).items():
                    c_name = c_val.get("creator_name") or c_key
                    if c_name and c_name.strip() and c_name.strip() != "Global":
                        creators.add(c_name.strip())
        except Exception:
            pass

        # Sort alphabetically A-Z (case-insensitive)
        clean_creators = [c for c in creators if c and c.lower() != "global"]
        sorted_creators = sorted(clean_creators, key=lambda s: s.lower())
        return ["Global"] + sorted_creators

    @Property(str, notify=itemsChanged)
    def itemsJson(self) -> str:
        with self._items_lock:
            data = [i.to_dict() for i in self._items]
        return json.dumps(data, ensure_ascii=False)

    @Property(str, notify=itemsChanged)
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

    @Property(str, notify=locationsChanged)
    def locationsJson(self) -> str:
        locs = self._get_all_target_locations()
        return json.dumps(locs, ensure_ascii=False)

    @Property(bool, constant=True)
    def has7za(self) -> bool:
        return self.engine.has_7za

    # ── Internal Helpers ───────────────────────────────────────────────────────

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

    # ── Scanning Slots ─────────────────────────────────────────────────────────

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

    # ── Selection Slots ────────────────────────────────────────────────────────

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

    # ── Pre-flight Disk Check ──────────────────────────────────────────────────

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

    # ── Extraction Slots ───────────────────────────────────────────────────────

    @Slot()
    def startDecompression(self):
        """Start parallel decompression of all selected archives."""
        if self._is_extracting or self._is_scanning:
            return

        with self._items_lock:
            all_selected = [i for i in self._items if i.selected]
            already_done = [i for i in all_selected if i.status == "done" or i.extracted_present]
            pending = [i for i in all_selected if i.status != "done" and not i.extracted_present]

        if not all_selected:
            return

        # If every selected item is already extracted, ask the user before overwriting
        if not pending and already_done:
            self.redecompressConfirmRequested.emit(len(already_done), len(all_selected))
            return

        self._run_decompression(pending)

    @Slot()
    def confirmRedecompress(self):
        """Called by QML when user confirms re-decompression of already-extracted archives."""
        if self._is_extracting or self._is_scanning:
            return
        with self._items_lock:
            # Reset 'done' status on selected-and-extracted items so they are picked up again
            for item in self._items:
                if item.selected and (item.status == "done" or item.extracted_present):
                    item.status = "pending"
                    item.progress = 0.0
                    item.error_message = ""
            selected_items = [i for i in self._items if i.selected]
        self._run_decompression(selected_items)

    def _run_decompression(self, selected_items):
        """Internal: kick off extraction worker for the given items list."""
        if not selected_items:
            return

        # Reset the prompt semaphore to ensure a clean state for this run
        # (guards against a previous cancelled run leaving the semaphore at 0)
        self._prompt_serial_sem = threading.Semaphore(1)

        self._is_extracting = True
        self._extract_cancel_event.clear()
        self._skip_all_password_prompts = False
        self.isExtractingChanged.emit()
        self.isBusyChanged.emit()
        self.extractionStarted.emit()

        # Metrics setup
        self._total_bytes_to_extract = sum(i.size for i in selected_items)
        self._extracted_bytes_done = 0
        self._start_time = time.time()

        max_workers = self._max_parallel
        threads = self._threads_per_archive
        delete_after = self._delete_after

        logger.info(
            f"Starting bulk extraction: {len(selected_items)} archive(s) ({_format_bytes(self._total_bytes_to_extract)}) | "
            f"Workers: {max_workers}, Threads/archive: {threads}, Delete after: {delete_after}",
            category="decompressor"
        )

        def _worker():
            success_count = 0
            error_count = 0

            # Thread-safe tracker for active jobs
            active_items: Dict[str, ArchiveItem] = {}
            active_lock = threading.Lock()

            def _update_progress(item: ArchiveItem, pct: float):
                item.progress = pct
                self.itemUpdated.emit(item.item_id, item.status, pct, item.error_message)

                # Compute overall progress
                with self._items_lock:
                    done_b = sum(
                        (i.size if i.status == "done" else (i.size * (i.progress / 100.0) if i.status == "extracting" else 0))
                        for i in selected_items
                    )
                total_b = max(1, self._total_bytes_to_extract)
                overall_pct = min(100.0, (done_b / total_b) * 100.0)

                # Speed and ETA
                elapsed = max(0.1, time.time() - self._start_time)
                speed = done_b / elapsed
                rem_b = max(0, total_b - done_b)
                eta_sec = (rem_b / speed) if speed > 0 else 0

                speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed >= 1024*1024 else f"{speed / 1024:.0f} KB/s"
                if eta_sec > 3600:
                    eta_str = f"{int(eta_sec//3600)}h {int((eta_sec%3600)//60)}m"
                elif eta_sec > 60:
                    eta_str = f"{int(eta_sec//60)}m {int(eta_sec%60)}s"
                else:
                    eta_str = f"{int(eta_sec)}s"

                self.extractionProgress.emit(
                    overall_pct,
                    item.filename,
                    pct,
                    eta_str,
                    speed_str
                )

            def _process_one(item: ArchiveItem):
                if self._extract_cancel_event.is_set():
                    item.status = "skipped"
                    self.itemUpdated.emit(item.item_id, item.status, 0.0, "Cancelled")
                    return False

                item.status = "extracting"
                item.progress = 0.0
                self.itemUpdated.emit(item.item_id, item.status, 0.0, "")
                logger.info(f"Extracting [{item.creator}] {item.filename}...", category="decompressor")

                def _cb(pct: float):
                    _update_progress(item, pct)

                # 1. First attempt: with pre-assigned password or without password
                initial_pw = item.password or None
                ok, err = self.engine.extract_single_archive(
                    item=item,
                    password=initial_pw,
                    threads_per_archive=threads,
                    delete_after=delete_after,
                    progress_callback=_cb,
                    cancel_event=self._extract_cancel_event
                )

                # 2. If password error, test candidate passwords automatically
                if not ok and self.engine.is_password_error(err) and not self._extract_cancel_event.is_set():
                    logger.info(f"Encrypted archive detected: [{item.creator}] {item.filename}. Testing candidate passwords...", category="decompressor")
                    candidates = archive_password_manager.find_candidate_passwords(item.path, item.creator)
                    matched_pw = None
                    for cand in candidates:
                        if self._extract_cancel_event.is_set():
                            break
                        if self.engine.test_password(item.path, cand, cancel_event=self._extract_cancel_event):
                            matched_pw = cand
                            logger.success(f"✓ Found matching password for [{item.creator}] {item.filename}: '{cand}'", category="decompressor")
                            break

                    if matched_pw:
                        ok, err = self.engine.extract_single_archive(
                            item=item,
                            password=matched_pw,
                            threads_per_archive=threads,
                            delete_after=delete_after,
                            progress_callback=_cb,
                            cancel_event=self._extract_cancel_event
                        )
                        if ok:
                            item.password = matched_pw
                            archive_password_manager.record_archive_password(item.path, matched_pw)
                            self.passwordBankChanged.emit()

                # 3. If still encrypted and uncracked: prompt user if enabled
                if not ok and self.engine.is_password_error(err) and not self._extract_cancel_event.is_set():
                    if self._auto_prompt_passwords and not self._skip_all_password_prompts:
                        # Acquire the serial semaphore — blocks until any other in-flight
                        # password prompt is dismissed, ensuring only one modal is shown at a time.
                        acquired = self._prompt_serial_sem.acquire(timeout=310)
                        if not acquired or self._extract_cancel_event.is_set() or self._skip_all_password_prompts:
                            if acquired:
                                self._prompt_serial_sem.release()
                        else:
                            try:
                                ev = threading.Event()
                                with self._prompt_lock:
                                    self._prompt_events[item.item_id] = ev
                                    self._prompt_responses.pop(item.item_id, None)

                                self.passwordPromptRequested.emit(
                                    item.item_id, item.filename, item.creator, item.directory, err, item.size
                                )

                                # Wait for user input (up to 300s)
                                ev.wait(timeout=300)

                                with self._prompt_lock:
                                    resp = self._prompt_responses.pop(item.item_id, None)
                                    self._prompt_events.pop(item.item_id, None)
                            finally:
                                # Always release so the next waiting archive can show its prompt
                                self._prompt_serial_sem.release()

                            if resp and resp.get("action") == "submit":
                                supplied_pw = resp.get("password", "")
                                remember = resp.get("remember", True)
                                if supplied_pw:
                                    ok, err = self.engine.extract_single_archive(
                                        item=item,
                                        password=supplied_pw,
                                        threads_per_archive=threads,
                                        delete_after=delete_after,
                                        progress_callback=_cb,
                                        cancel_event=self._extract_cancel_event
                                    )
                                    if ok:
                                        item.password = supplied_pw
                                        if remember:
                                            archive_password_manager.record_archive_password(item.path, supplied_pw, creator=item.creator)
                                            self.passwordBankChanged.emit()

                if ok:
                    item.status = "done"
                    item.progress = 100.0
                    item.error_message = ""
                    self.itemUpdated.emit(item.item_id, item.status, 100.0, "")
                    logger.success(f"✓ Extracted [{item.creator}] {item.filename} -> {item.target_dir}", category="decompressor")
                    return True
                else:
                    if self.engine.is_password_error(err):
                        item.status = "password_required"
                        item.error_message = "Password required (encrypted archive)"
                        self.itemUpdated.emit(item.item_id, item.status, 0.0, item.error_message)
                        logger.warning(f"🔒 Password required for [{item.creator}] {item.filename}", category="decompressor")
                    else:
                        item.status = "error"
                        item.error_message = err
                        self.itemUpdated.emit(item.item_id, item.status, item.progress, err)
                        logger.error(f"✗ Error extracting [{item.creator}] {item.filename}: {err}", category="decompressor")
                    return False

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_process_one, it): it for it in selected_items}
                for f in as_completed(futures):
                    it = futures[f]
                    try:
                        res = f.result()
                        if res:
                            success_count += 1
                        else:
                            error_count += 1
                    except Exception as exc:
                        error_count += 1
                        it.status = "error"
                        it.error_message = str(exc)
                        self.itemUpdated.emit(it.item_id, it.status, it.progress, str(exc))
                        logger.error(f"✗ Exception in [{it.creator}] {it.filename}: {exc}", category="decompressor")

            self._is_extracting = False
            self.isExtractingChanged.emit()
            self.isBusyChanged.emit()
            self.itemsChanged.emit()
            self.selectedStatsChanged.emit()
            self.extractionFinished.emit(success_count, error_count)
            logger.success(
                f"Bulk decompression complete: {success_count} succeeded, {error_count} failed.",
                category="decompressor"
            )

        threading.Thread(target=_worker, daemon=True).start()

    # ── Password Bank & Prompt Slots ───────────────────────────────────────────

    @Slot(result='QVariant')
    def getSavedPasswords(self) -> List[str]:
        return archive_password_manager.get_passwords()

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def addPassword(self, password: str, creator: str = "Global") -> bool:
        ok = archive_password_manager.add_password(password, creator)
        if ok:
            self.passwordBankChanged.emit()
        return ok

    @Slot(str, result=int)
    def addMultiplePasswords(self, text: str) -> int:
        if not text:
            return 0
        lines = [l.strip() for l in text.replace(",", "\n").splitlines() if l.strip()]
        count = archive_password_manager.add_passwords(lines)
        if count > 0:
            self.passwordBankChanged.emit()
        return count

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def removePassword(self, password: str, creator: str = "") -> bool:
        ok = archive_password_manager.remove_password(password, creator)
        if ok:
            self.passwordBankChanged.emit()
        return ok

    @Slot(result=bool)
    def clearSavedPasswords(self) -> bool:
        ok = archive_password_manager.clear_passwords()
        if ok:
            self.passwordBankChanged.emit()
        return ok

    @Slot(result=int)
    def syncFromLinkVault(self) -> int:
        count = archive_password_manager.sync_from_link_vault()
        if count > 0:
            self.passwordBankChanged.emit()
        return count

    @Slot(str, str)
    def setItemPassword(self, itemId: str, password: str):
        with self._items_lock:
            for item in self._items:
                if item.item_id == itemId:
                    item.password = str(password or "").strip()
                    if item.status == "password_required":
                        item.status = "pending"
                        item.error_message = ""
                    break
        self.itemsChanged.emit()

    @Slot(str, str, result=bool)
    def testItemPassword(self, itemId: str, password: str) -> bool:
        target_item = None
        with self._items_lock:
            for it in self._items:
                if it.item_id == itemId:
                    target_item = it
                    break
        if not target_item or not os.path.exists(target_item.path):
            return False
        return self.engine.test_password(target_item.path, str(password or "").strip())

    @Slot(str, str, bool)
    def submitPromptPassword(self, itemId: str, password: str, remember: bool = True):
        with self._prompt_lock:
            self._prompt_responses[itemId] = {
                "action": "submit",
                "password": str(password or "").strip(),
                "remember": remember
            }
            ev = self._prompt_events.get(itemId)
            if ev:
                ev.set()
        self.passwordPromptDismissed.emit(itemId)

    @Slot(str)
    def skipPasswordPrompt(self, itemId: str):
        with self._prompt_lock:
            self._prompt_responses[itemId] = {"action": "skip"}
            ev = self._prompt_events.get(itemId)
            if ev:
                ev.set()
        self.passwordPromptDismissed.emit(itemId)

    @Slot()
    def skipAllPasswordPrompts(self):
        self._skip_all_password_prompts = True
        with self._prompt_lock:
            for it_id, ev in list(self._prompt_events.items()):
                self._prompt_responses[it_id] = {"action": "skip"}
                ev.set()
                self.passwordPromptDismissed.emit(it_id)
        self.passwordPromptDismissed.emit("mock_locked_archive")
        # Release the semaphore in case a worker is queued waiting to show its prompt.
        # We release up to once — if no one holds it this is a no-op (try/except).
        try:
            self._prompt_serial_sem.release()
        except ValueError:
            pass  # semaphore was already at max value (no one was waiting)


    @Slot()
    def triggerTestPasswordPrompt(self):
        """Creates a mock encrypted archive item and requests the password prompt modal for UI testing."""
        mock_id = "mock_locked_archive"
        mock_filename = "exclusive_art_pack.zip"
        mock_creator = "CloZzY"
        mock_directory = "C:/Downloads/CloZzY [fanbox]"
        mock_error = "ERROR: Can not open encrypted archive. Wrong password?"
        mock_size = 15400000

        with self._items_lock:
            found = False
            for it in self._items:
                if it.item_id == mock_id:
                    it.status = "password_required"
                    it.error_message = mock_error
                    found = True
                    break
            if not found:
                self._items.insert(0, ArchiveItem(
                    item_id=mock_id,
                    path=os.path.join(mock_directory, mock_filename),
                    filename=mock_filename,
                    directory=mock_directory,
                    size=mock_size,
                    creator=mock_creator,
                    status="password_required",
                    error_message=mock_error
                ))
        self.itemsChanged.emit()
        self.passwordPromptRequested.emit(
            mock_id, mock_filename, mock_creator, mock_directory, mock_error, mock_size
        )

    @Slot(str, str, bool, result=bool)
    def retryItemWithPassword(self, itemId: str, password: str, remember: bool = True) -> bool:
        p = str(password or "").strip()

        with self._prompt_lock:
            waiting_ev = self._prompt_events.get(itemId)

        # Locate target item
        target_item = None
        with self._items_lock:
            for it in self._items:
                if it.item_id == itemId:
                    target_item = it
                    break

        # ── Mock item special handling ────────────────────────────────────────
        if itemId == "mock_locked_archive":
            target_path = target_item.path if (target_item and target_item.path) else r"C:\Downloads\CloZzY [fanbox]\exclusive_art_pack.zip"
            if os.path.exists(target_path):
                is_valid = self.engine.test_password(target_path, p)
            else:
                is_valid = p.lower() in ("test123", "pawchive", "secret", "password")

            if not is_valid:
                self.passwordWrong.emit(itemId)
                return False

            if remember:
                self.addPassword(p)

            # If waiting in bulk extraction flow, wake up the worker
            if waiting_ev:
                with self._prompt_lock:
                    self._prompt_responses[itemId] = {
                        "action": "submit",
                        "password": p,
                        "remember": remember
                    }
                    waiting_ev.set()
                self.passwordPromptDismissed.emit(itemId)
                return True

            # Standalone mock extraction: if real file exists, extract it in background
            if target_item and os.path.exists(target_item.path):
                def _mock_worker():
                    target_item.password = p
                    target_item.status = "extracting"
                    target_item.progress = 0.0
                    target_item.error_message = ""
                    self.itemUpdated.emit(target_item.item_id, target_item.status, 0.0, "")
                    self.passwordPromptDismissed.emit(itemId)

                    def _cb(pct: float):
                        target_item.progress = pct
                        self.itemUpdated.emit(target_item.item_id, target_item.status, pct, "")

                    ok, err = self.engine.extract_single_archive(
                        item=target_item,
                        password=p,
                        threads_per_archive=self._threads_per_archive,
                        delete_after=False,
                        progress_callback=_cb
                    )
                    if ok:
                        target_item.status = "done"
                        target_item.progress = 100.0
                        target_item.error_message = ""
                        self.itemUpdated.emit(target_item.item_id, target_item.status, 100.0, "")
                        logger.success(f"✓ Extracted [{target_item.creator}] {target_item.filename} with password", category="decompressor")
                    else:
                        target_item.status = "error"
                        target_item.error_message = err
                        self.itemUpdated.emit(target_item.item_id, target_item.status, target_item.progress, err)
                    self.itemsChanged.emit()

                threading.Thread(target=_mock_worker, daemon=True).start()
                return True

            # Fallback if no file on disk
            with self._items_lock:
                for it in self._items:
                    if it.item_id == itemId:
                        it.status = "done"
                        it.progress = 100.0
                        it.password = p
                        it.error_message = ""
                        break
            self.itemUpdated.emit(itemId, "done", 100.0, "")
            self.itemsChanged.emit()
            self.passwordPromptDismissed.emit(itemId)
            return True

        # ── Real archive path ─────────────────────────────────────────────────
        if not target_item or not os.path.exists(target_item.path):
            return False

        # If waiting in bulk extraction flow, validate password and wake up worker
        if waiting_ev:
            if not self.engine.test_password(target_item.path, p):
                logger.debug(f"Wrong password for {target_item.filename}", category="decompressor")
                self.passwordWrong.emit(itemId)
                return False

            target_item.password = p
            if remember:
                archive_password_manager.record_archive_password(target_item.path, p)
                self.passwordBankChanged.emit()

            with self._prompt_lock:
                self._prompt_responses[itemId] = {
                    "action": "submit",
                    "password": p,
                    "remember": remember
                }
                waiting_ev.set()
            self.passwordPromptDismissed.emit(itemId)
            return True

        # Standalone retry (e.g. from an individual item row)
        def _single_worker():
            if not self.engine.test_password(target_item.path, p):
                logger.debug(f"Wrong password for {target_item.filename}", category="decompressor")
                self.passwordWrong.emit(itemId)
                return

            target_item.password = p
            if remember:
                archive_password_manager.record_archive_password(target_item.path, p)
                self.passwordBankChanged.emit()

            target_item.status = "extracting"
            target_item.progress = 0.0
            target_item.error_message = ""
            self.itemUpdated.emit(target_item.item_id, target_item.status, 0.0, "")
            self.passwordPromptDismissed.emit(itemId)

            def _cb(pct: float):
                target_item.progress = pct
                self.itemUpdated.emit(target_item.item_id, target_item.status, pct, "")

            ok, err = self.engine.extract_single_archive(
                item=target_item,
                password=p,
                threads_per_archive=self._threads_per_archive,
                delete_after=self._delete_after,
                progress_callback=_cb
            )
            if ok:
                target_item.status = "done"
                target_item.progress = 100.0
                target_item.error_message = ""
                self.itemUpdated.emit(target_item.item_id, target_item.status, 100.0, "")
                logger.success(f"✓ Extracted [{target_item.creator}] {target_item.filename} with password", category="decompressor")
            else:
                target_item.status = "error"
                target_item.error_message = err
                self.itemUpdated.emit(target_item.item_id, target_item.status, target_item.progress, err)
            self.itemsChanged.emit()

        threading.Thread(target=_single_worker, daemon=True).start()
        return True

    @Slot()
    def cancelDecompression(self):
        """Cancel ongoing extraction jobs immediately."""
        logger.warning("Bulk decompression cancelled by user.", category="decompressor")
        self._extract_cancel_event.set()
        self.engine.cancel_all()
        # Wake any worker that is blocked waiting to show a password prompt
        with self._prompt_lock:
            for it_id, ev in list(self._prompt_events.items()):
                self._prompt_responses[it_id] = {"action": "skip"}
                ev.set()

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
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
