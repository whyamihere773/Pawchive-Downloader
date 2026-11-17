"""
Visual + LLM Sorter QML Bridge (`VisualSorterBridge`).

Manages the two-stage Virtual-First -> Commit-to-Disk workflow for the Gallery tab:
1. Stage 1 (Virtual Sandbox): Runs `VisualSorterEngine.run_virtual_sort` in a background
   worker, streaming live progress and populating `bucketsModel` and `previewItemsModel`
   with zero modifications on disk. Supports interactive bucket renaming, item reassignment,
   and item exclusion.
2. Stage 2 (Commit to Disk + Full Ctrl+Z Undo): Moves files conflict-safely into their
   target bucket subfolders, updates `ArchiveManager.relocate_files()`, updates
   `gallery_marks.json`, and pushes a batch undo transaction onto `GalleryToolsBridge._undo`
   so `Ctrl+Z` cleanly reverts the entire sort.
"""

from __future__ import annotations

import os
import shutil
import threading
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Property, Qt, Signal, Slot

from bridge.archive_creators_model import RecordListModel
from core.hardware_detector import HardwareDetector
from core.logger import logger
from core.visual_sorter import SORT_STRATEGIES, VisualSorterEngine, _clean_bucket_folder_name
from services.model_manager import ModelManager


def _free_dest_path(dest_path: str) -> str:
    if not os.path.exists(dest_path):
        return dest_path
    stem, ext = os.path.splitext(dest_path)
    n = 2
    while os.path.exists(f"{stem} ({n}){ext}"):
        n += 1
    return f"{stem} ({n}){ext}"


class VisualSorterBridge(QObject):
    """QML Bridge for the Interactive Virtual-First Gallery Visual Sorter."""

    stateChanged = Signal()
    progressChanged = Signal()
    planChanged = Signal()
    modelsStateChanged = Signal()
    commitFinished = Signal(bool, str, int)     # ok, message, movedCount
    virtualFilterApplied = Signal(str, "QVariantList")  # bucketName, filePathsList

    _callOnGui = Signal(object)

    def __init__(
        self,
        app_bridge=None,
        gallery_tools_bridge=None,
        config_dir: Optional[str] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._callOnGui.connect(self._run_on_gui, Qt.QueuedConnection)
        self._app_bridge = app_bridge
        self._gallery_tools = gallery_tools_bridge
        known_mgr = getattr(app_bridge, "known_manager", None) if app_bridge else None
        self._engine = VisualSorterEngine(config_dir=config_dir, known_manager=known_mgr)
        self._model_manager = getattr(app_bridge, "model_manager", None) if app_bridge else ModelManager()

        self._buckets_model = RecordListModel(self, key_field="key")
        self._items_model = RecordListModel(self, key_field="key")

        self._folder_path: str = ""
        self._active_strategy: str = "visual_style"
        self._custom_prompt: str = "Photos & Cosplay, 2D Illustrations, Dark & Moody, Video Clips, Favorites"
        self._recursive: bool = False
        self._selected_bucket_id: str = "all"

        self._is_running: bool = False
        self._progress_done: int = 0
        self._progress_total: int = 0
        self._progress_speed: str = ""
        self._progress_eta: str = ""
        self._progress_file: str = ""
        self._status_text: str = "Ready for Virtual Sort"
        self._error_message: str = ""

        self._all_virtual_items: List[Dict[str, Any]] = []
        self._cancel_event = threading.Event()

    @Slot(object)
    def _run_on_gui(self, fn):
        try:
            fn()
        except Exception as e:
            logger.debug(f"[VisualSorterBridge] GUI callback error: {e}", category="ai")

    # ── QML Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def bucketsModel(self) -> RecordListModel:
        return self._buckets_model

    @Property(QObject, constant=True)
    def previewItemsModel(self) -> RecordListModel:
        return self._items_model

    @Property("QVariantList", constant=True)
    def strategiesList(self) -> List[Dict[str, str]]:
        return list(SORT_STRATEGIES)

    @Property(str, notify=stateChanged)
    def folderPath(self) -> str:
        return self._folder_path

    @Property(str, notify=stateChanged)
    def activeStrategy(self) -> str:
        return self._active_strategy

    @Property(str, notify=stateChanged)
    def customPrompt(self) -> str:
        return self._custom_prompt

    @Property(bool, notify=stateChanged)
    def recursive(self) -> bool:
        return self._recursive

    @Property(str, notify=planChanged)
    def selectedBucketId(self) -> str:
        return self._selected_bucket_id

    @Property(bool, notify=stateChanged)
    def isRunning(self) -> bool:
        return self._is_running

    @Property(int, notify=progressChanged)
    def progressDone(self) -> int:
        return self._progress_done

    @Property(int, notify=progressChanged)
    def progressTotal(self) -> int:
        return self._progress_total

    @Property(int, notify=progressChanged)
    def progressPercent(self) -> int:
        if self._progress_total <= 0:
            return 0
        return int(round((self._progress_done / max(1, self._progress_total)) * 100))

    @Property(str, notify=progressChanged)
    def progressSpeed(self) -> str:
        return self._progress_speed

    @Property(str, notify=progressChanged)
    def progressEta(self) -> str:
        return self._progress_eta

    @Property(str, notify=progressChanged)
    def progressCurrentFile(self) -> str:
        return self._progress_file

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=stateChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Property(bool, notify=planChanged)
    def hasVirtualPlan(self) -> bool:
        return len(self._all_virtual_items) > 0

    @Property(int, notify=planChanged)
    def totalPlannedFiles(self) -> int:
        return sum(1 for it in self._all_virtual_items if not it.get("excluded"))

    @Property(int, notify=planChanged)
    def totalBucketsCount(self) -> int:
        return self._buckets_model.count

    @Property(str, notify=modelsStateChanged)
    def hardwareSummary(self) -> str:
        hw = HardwareDetector.cached_info()
        if not hw:
            HardwareDetector.probe_async()
            return "Universal CPU + DirectML GPU Ready"
        return str(hw.get("provider_name") or "CPU Execution Provider")

    @Property("QVariantList", notify=modelsStateChanged)
    def visualModelsStatus(self) -> List[Dict[str, Any]]:
        keys = ["visual_clip_vit", "fast_semantic", "deep_reasoner_light", "visual_vlm_light"]
        out = []
        for k in keys:
            st = self._model_manager.get_status(k)
            out.append({
                "key": k,
                "name": st.get("name", k),
                "description": st.get("description", ""),
                "status": st.get("status", "not_downloaded"),
                "is_ready": bool(st.get("is_ready", False)),
                "percent": float(st.get("percent", 0.0)),
                "size_mb": round(int(st.get("size_bytes", 0)) / (1024 * 1024), 1),
                "speed_mbps": float(st.get("speed_mbps", 0.0)),
                "error": str(st.get("error") or ""),
            })
        return out

    # ── Configuration & Model Download Slots ──────────────────────────────────

    @Slot(str)
    def setFolderPath(self, path: str) -> None:
        clean = (path or "").replace("file:///", "").replace("file://", "").strip()
        if clean and self._folder_path != clean:
            self._folder_path = os.path.normpath(clean)
            self.stateChanged.emit()

    @Slot(str)
    def setActiveStrategy(self, strategy_id: str) -> None:
        clean = (strategy_id or "visual_style").strip()
        if self._active_strategy != clean:
            self._active_strategy = clean
            self.stateChanged.emit()

    @Slot(str)
    def setCustomPrompt(self, prompt: str) -> None:
        self._custom_prompt = prompt or ""
        self.stateChanged.emit()

    @Slot(bool)
    def setRecursive(self, rec: bool) -> None:
        if self._recursive != bool(rec):
            self._recursive = bool(rec)
            self.stateChanged.emit()

    @Slot(str)
    def downloadVisualModel(self, model_key: str) -> None:
        def _cb(_prog: Dict[str, Any]):
            self._callOnGui.emit(self.modelsStateChanged.emit)

        self._model_manager.download_model_async(model_key, progress_callback=_cb)
        self.modelsStateChanged.emit()

    @Slot(str)
    def cancelVisualModelDownload(self, model_key: str) -> None:
        self._model_manager.cancel_download(model_key)
        self.modelsStateChanged.emit()

    @Slot()
    def refreshModelsStatus(self) -> None:
        self.modelsStateChanged.emit()

    # ── Stage 1: Virtual Sort Execution & Interactive Sandbox Editing ──────────

    @Slot(str, str, str, bool)
    @Slot(str)
    @Slot()
    def startVirtualSort(
        self,
        folder_path: str = "",
        strategy: str = "",
        custom_prompt: str = "",
        recursive: bool = False,
    ) -> None:
        if folder_path:
            self._folder_path = os.path.normpath(folder_path.replace("file:///", "").replace("file://", "").strip())
        if strategy:
            self._active_strategy = strategy
        if custom_prompt:
            self._custom_prompt = custom_prompt
        self._recursive = bool(recursive)

        if not self._folder_path or not os.path.isdir(self._folder_path):
            self._error_message = "Please select a valid folder in Gallery first."
            self.stateChanged.emit()
            return

        self._cancel_event.set()
        self._cancel_event = threading.Event()
        cancel = self._cancel_event

        self._is_running = True
        self._error_message = ""
        self._progress_done = 0
        self._progress_total = 0
        self._progress_speed = ""
        self._progress_eta = "--"
        self._progress_file = ""
        self._status_text = "Scanning media & computing virtual buckets…"
        self.stateChanged.emit()
        self.progressChanged.emit()

        target_dir = self._folder_path
        strat = self._active_strategy
        prompt = self._custom_prompt
        rec = self._recursive

        def _on_prog(done: int, total: int, speed_fps: float, eta_str: str, cur_file: str):
            def _update():
                self._progress_done = done
                self._progress_total = total
                self._progress_speed = f"{speed_fps:.1f} files/s"
                self._progress_eta = eta_str
                self._progress_file = cur_file
                self._status_text = f"Analyzing ({done}/{total}) — {cur_file}"
                self.progressChanged.emit()
                self.stateChanged.emit()

            self._callOnGui.emit(_update)

        def _worker():
            res = self._engine.run_virtual_sort(
                folder_path=target_dir,
                strategy=strat,
                custom_prompt=prompt,
                recursive=rec,
                cancel_event=cancel,
                progress_cb=_on_prog,
            )

            def _deliver():
                self._is_running = False
                if not res.get("ok"):
                    self._error_message = str(res.get("error") or "Virtual sort stopped.")
                    self._status_text = self._error_message
                    self.stateChanged.emit()
                    return

                self._all_virtual_items = list(res.get("items") or [])
                buckets = list(res.get("buckets") or [])
                self._buckets_model.set_creators(buckets)
                self._selected_bucket_id = "all"
                self._refresh_preview_items_model()
                self._status_text = (
                    f"Virtual Sort Ready: {len(self._all_virtual_items)} file(s) organized into {len(buckets)} virtual bucket(s). "
                    "No files have been moved on disk yet."
                )
                self.planChanged.emit()
                self.stateChanged.emit()

            self._callOnGui.emit(_deliver)

        threading.Thread(target=_worker, daemon=True, name="VisualSorterVirtualWorker").start()

    @Slot()
    def cancelVirtualSort(self) -> None:
        self._cancel_event.set()

    def _refresh_preview_items_model(self) -> None:
        if self._selected_bucket_id in ("", "all"):
            filtered = list(self._all_virtual_items)
        else:
            filtered = [it for it in self._all_virtual_items if it.get("bucket_id") == self._selected_bucket_id]
        self._items_model.set_creators(filtered)

    def _rebuild_buckets_from_items(self) -> None:
        buckets = VisualSorterEngine.summarize_buckets(self._all_virtual_items)
        self._buckets_model.set_creators(buckets)
        self._refresh_preview_items_model()
        self.planChanged.emit()

    @Slot(str)
    def selectBucket(self, bucket_id: str) -> None:
        clean = (bucket_id or "all").strip()
        if self._selected_bucket_id != clean:
            self._selected_bucket_id = clean
            self._refresh_preview_items_model()
            self.planChanged.emit()

    @Slot(str)
    def toggleExcludeItem(self, file_path_or_key: str) -> None:
        norm_k = os.path.normpath(file_path_or_key).replace("\\", "/")
        for it in self._all_virtual_items:
            if it.get("key") == norm_k or it.get("file_path") == file_path_or_key:
                it["excluded"] = not bool(it.get("excluded"))
                break
        self._rebuild_buckets_from_items()

    @Slot("QVariantList", str)
    def moveItemsToBucket(self, item_keys: List[str], target_bucket_name: str) -> None:
        clean_name = _clean_bucket_folder_name(target_bucket_name)
        target_id = clean_name.lower()
        key_set = {os.path.normpath(str(k)).replace("\\", "/") for k in (item_keys or [])}
        for it in self._all_virtual_items:
            if it.get("key") in key_set or it.get("file_path") in (item_keys or []):
                it["bucket_id"] = target_id
                it["bucket_name"] = clean_name
                it["reason"] = f"Manually assigned to '{clean_name}'"
                it["confidence"] = 1.0
                it["confidence_pct"] = 100
        self._rebuild_buckets_from_items()

    @Slot(str, str)
    def renameBucket(self, bucket_id: str, new_folder_name: str) -> None:
        clean_name = _clean_bucket_folder_name(new_folder_name)
        new_id = clean_name.lower()
        for it in self._all_virtual_items:
            if it.get("bucket_id") == bucket_id:
                it["bucket_id"] = new_id
                it["bucket_name"] = clean_name
        if self._selected_bucket_id == bucket_id:
            self._selected_bucket_id = new_id
        self._rebuild_buckets_from_items()

    @Slot(str)
    def applyBucketAsGalleryFilter(self, bucket_id: str) -> None:
        """Lets the user filter the main Gallery grid virtually by a bucket without moving files on disk."""
        if bucket_id in ("", "all"):
            paths = [it["file_path"] for it in self._all_virtual_items if not it.get("excluded")]
            bname = "All Virtual Sorted Items"
        else:
            paths = [it["file_path"] for it in self._all_virtual_items if it.get("bucket_id") == bucket_id and not it.get("excluded")]
            bname = bucket_id
            for it in self._all_virtual_items:
                if it.get("bucket_id") == bucket_id:
                    bname = str(it.get("bucket_name") or bucket_id)
                    break
        self.virtualFilterApplied.emit(bname, paths)

    @Slot()
    def clearVirtualPlan(self) -> None:
        self._all_virtual_items = []
        self._buckets_model.set_creators([])
        self._items_model.set_creators([])
        self._selected_bucket_id = "all"
        self._status_text = "Ready for Virtual Sort"
        self.planChanged.emit()
        self.stateChanged.emit()

    # ── Stage 2: Commit Virtual Plan to Disk (With Archive Sync & Ctrl+Z Undo) ─

    def _execute_commit_moves(self, root_dir: str, active_items: List[Dict[str, Any]]) -> Tuple[List[Tuple[str, str]], List[str], List[str]]:
        moved_pairs: List[Tuple[str, str]] = []
        created_dirs: List[str] = []
        errors: List[str] = []

        for it in active_items:
            src = str(it.get("file_path") or "")
            bname = _clean_bucket_folder_name(str(it.get("bucket_name") or "Sorted"))
            if not src or not os.path.isfile(src):
                continue
            dst_dir = os.path.normpath(os.path.join(root_dir, bname))
            if os.path.normcase(os.path.dirname(src)) == os.path.normcase(dst_dir):
                continue
            try:
                if not os.path.isdir(dst_dir):
                    os.makedirs(dst_dir, exist_ok=True)
                    created_dirs.append(dst_dir)
                dst = _free_dest_path(os.path.join(dst_dir, os.path.basename(src)))
                shutil.move(src, dst)
                moved_pairs.append((src, dst))
            except OSError as e:
                errors.append(f"{os.path.basename(src)}: {e}")

        # 1. Sync ArchiveManager (`download_archive.db`)
        if moved_pairs and self._app_bridge and getattr(self._app_bridge, "archive_manager", None):
            try:
                self._app_bridge.archive_manager.relocate_files([root_dir], moved_pairs)
            except Exception as e:
                logger.debug(f"[VisualSorter] Archive relocate warning: {e}", category="archive")

        return moved_pairs, created_dirs, errors

    def _finalize_commit_on_gui(self, moved_pairs: List[Tuple[str, str]], created_dirs: List[str], errors: List[str]) -> Dict[str, Any]:
        # 2. Sync Gallery favorites/ratings & push batch Ctrl+Z Undo transaction
        if moved_pairs and self._gallery_tools:
            try:
                pairs_list = [[old_p, new_p] for (old_p, new_p) in moved_pairs]
                self._gallery_tools._remap_pairs(pairs_list)
                n = len(pairs_list)
                self._gallery_tools._push_undo({
                    "type": "move",
                    "pairs": pairs_list,
                    "created_dirs": created_dirs,
                    "label": f"Undo Visual Sort of {n} item{'s' if n != 1 else ''}",
                })
            except Exception as e:
                logger.debug(f"[VisualSorter] Undo registration warning: {e}", category="system")

        self._is_running = False
        moved_cnt = len(moved_pairs)
        if moved_cnt > 0:
            self._all_virtual_items = []
            self._buckets_model.set_creators([])
            self._items_model.set_creators([])
            msg = f"Sorted {moved_cnt} file(s) into folders on disk (Press Ctrl+Z in Gallery to undo)."
            if errors:
                msg += f" ({len(errors)} skipped)"
            self._status_text = msg
            self.planChanged.emit()
            self.stateChanged.emit()
            self.commitFinished.emit(True, msg, moved_cnt)
            return {"ok": True, "message": msg, "moved_count": moved_cnt}
        else:
            err = errors[0] if errors else "No files needed to be moved."
            self._status_text = err
            self.stateChanged.emit()
            self.commitFinished.emit(False, err, 0)
            return {"ok": False, "message": err, "moved_count": 0}

    def commit_virtual_sort_sync(self) -> Dict[str, Any]:
        """Synchronous commit entry point (useful for headless workflows and tests)."""
        active_items = [it for it in self._all_virtual_items if not it.get("excluded")]
        if not active_items or not self._folder_path:
            msg = "No active files in the virtual sort plan to commit."
            self.commitFinished.emit(False, msg, 0)
            return {"ok": False, "message": msg, "moved_count": 0}
        moved_pairs, created_dirs, errors = self._execute_commit_moves(self._folder_path, active_items)
        return self._finalize_commit_on_gui(moved_pairs, created_dirs, errors)

    @Slot()
    def commitVirtualSort(self) -> None:
        """
        Writes the virtual sort plan to disk:
        1. Creates bucket folders inside `_folder_path`.
        2. Moves all non-excluded files conflict-safely.
        3. Updates `ArchiveManager.relocate_files()` so `download_archive.db` stays in sync.
        4. Updates `gallery_marks.json` via `GalleryToolsBridge._marks_follow_move`.
        5. Pushes a batch undo entry onto `GalleryToolsBridge._undo` so `Ctrl+Z` reverses the sort.
        """
        active_items = [it for it in self._all_virtual_items if not it.get("excluded")]
        if not active_items or not self._folder_path:
            self.commitFinished.emit(False, "No active files in the virtual sort plan to commit.", 0)
            return

        root_dir = self._folder_path
        self._is_running = True
        self._status_text = f"Writing {len(active_items)} sorted file(s) to disk…"
        self.stateChanged.emit()

        def _worker():
            moved_pairs, created_dirs, errors = self._execute_commit_moves(root_dir, active_items)
            self._callOnGui.emit(lambda: self._finalize_commit_on_gui(moved_pairs, created_dirs, errors))

        threading.Thread(target=_worker, daemon=True, name="VisualSorterCommitWorker").start()
