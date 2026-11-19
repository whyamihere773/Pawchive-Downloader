"""
Download Queue Qt Model
Exposes an observable QAbstractListModel for active, pending, completed, and failed tasks.
"""

import threading
import time
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, QThread, QTimer, Signal, Slot

from bridge.queue_groups_model import QueueGroupsModel, _RowIndex
from bridge.queue_model_ops import QueueModelOpsMixin
from core.downloader import DownloadTask, is_task_non_retryable
from core.logger import logger


class QueueModel(QAbstractListModel, QueueModelOpsMixin):
    FilenameRole = Qt.UserRole + 1
    PostTitleRole = Qt.UserRole + 2
    CreatorNameRole = Qt.UserRole + 3
    ServiceRole = Qt.UserRole + 4
    StatusRole = Qt.UserRole + 5
    ProgressRole = Qt.UserRole + 6
    FileSizeRole = Qt.UserRole + 7
    DownloadedBytesRole = Qt.UserRole + 8
    ErrorMsgRole = Qt.UserRole + 9
    UrlRole = Qt.UserRole + 10
    SpeedRole = Qt.UserRole + 11
    EtaRole = Qt.UserRole + 12
    PercentageRole = Qt.UserRole + 13
    OriginalIndexRole = Qt.UserRole + 14
    FileIdRole = Qt.UserRole + 15
    RetryCountRole = Qt.UserRole + 16
    BatchIdRole = Qt.UserRole + 17
    TargetPathRole = Qt.UserRole + 18
    IsUnimportedRole = Qt.UserRole + 19

    countChanged = Signal()
    filterStatusChanged = Signal()
    minFileSizeChanged = Signal()
    countsChanged = Signal()
    failedCountChanged = Signal()
    failedListReady = Signal(str, int)
    groupsChanged = Signal()
    selectedBatchIdChanged = Signal()
    viewModeChanged = Signal()
    retryRequested = Signal()
    singleRetryRequested = Signal(str)
    retrySelectedRequested = Signal(list)
    batchRetryRequested = Signal(str)
    batchCancelRequested = Signal(str)
    batchRemoveRequested = Signal(str)
    batchPauseRequested = Signal(str)
    batchResumeRequested = Signal(str)
    cleared = Signal()
    _guiCall = Signal(object)
    IMMEDIATE_REMOVAL_ROWS = 2000
    RESET_AFTER_RUNS = 150         # more separate runs of rows leaving the filter: the list is rebuilt   # above this, rows leaving the filter are removed in batches

    def __init__(self, parent=None, enable_groups: bool = True):
        super().__init__(parent)
        self._enable_groups = enable_groups
        self._guiCall.connect(self._run_gui_call, Qt.QueuedConnection)
        self._tasks: List[DownloadTask] = []
        self._filter_status: str = "all" # "all", "downloading", "completed", "failed", "pending"
        self._min_file_size: int = 0
        self._selected_batch_id: str = ""
        self._view_mode: str = "grouped" # "grouped" or "flat"
        self._visible_tasks: List[DownloadTask] = []
        self._visible_task_row = _RowIndex()
        self._groups_model = QueueGroupsModel(self) if enable_groups else None
        self._last_counts: Optional[tuple] = None
        self._pending_count: int = 0
        self._downloading_count: int = 0
        self._completed_count: int = 0
        self._skipped_count: int = 0
        self._failed_count: int = 0
        self._paused_batch_ids: set = set()
        self._task_last_status: Dict[int, str] = {}
        self._task_last_emit: Dict[int, float] = {}
        self._failed_404: dict = {}      # id(task) of failed tasks whose error is a 404
        # (url, path) and file ids already in the queue, kept between appends (rebuilding them from
        # the whole queue on every append made adding to a big queue slow)
        self._signatures: set = set()
        self._signatures_dirty = False
        self._task_index_by_id: Dict[int, int] = {}
        self._task_index_dirty = False
        # Rows that left the current filter, removed together a few times a second (removing one
        # renumbered every row below it: with a big filtered list, every status change stalled)
        self._pending_removals: set = set()
        self._removal_timer = QTimer(self)
        self._removal_timer.setSingleShot(True)
        self._removal_timer.setInterval(250)
        self._removal_timer.timeout.connect(self._flush_removals)
        self._counts_timer = QTimer(self)
        self._counts_timer.setSingleShot(True)
        self._counts_timer.setInterval(60)
        self._counts_timer.timeout.connect(self._flush_counts_changed)

    def _flush_counts_changed(self):
        curr_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        if self._last_counts != curr_counts:
            prev_failed = self._last_counts[4] if (self._last_counts and len(self._last_counts) > 4) else None
            self._last_counts = curr_counts
            self.countsChanged.emit()
            if prev_failed is None or prev_failed != curr_counts[4]:
                self.failedCountChanged.emit()

    def _recalculate_counts(self):
        pending = 0
        downloading = 0
        completed = 0
        skipped = 0
        failed = 0
        failed_404 = {}
        for t in self._tasks:
            st = getattr(t, "status", "")
            if st in ("downloading", "retrying"):
                downloading += 1
            elif st == "completed":
                completed += 1
            elif st == "skipped":
                skipped += 1
            elif st in ("failed", "cancelled"):
                failed += 1
                if self._is_404(t):
                    failed_404[id(t)] = True
            elif st in ("pending", "paused"):
                pending += 1
        self._pending_count = pending
        self._downloading_count = downloading
        self._completed_count = completed
        self._skipped_count = skipped
        self._failed_count = failed
        self._failed_404 = failed_404

    @staticmethod
    def _is_404(t) -> bool:
        # Unimported Pawchive placeholders stay visible in Failed / Retry Modal even when
        # "Skip 404s" is active, so users always see which files aren't hosted on Pawchive yet.
        if is_task_non_retryable(t):
            return False
        return "404" in str(getattr(t, "error_msg", "") or "").lower() or getattr(t, "http_status", 0) == 404

    @staticmethod
    def _format_size(b: int) -> str:
        return QueueGroupsModel._format_size(b)

    def _matches_filter(self, task: DownloadTask) -> bool:
        if self._selected_batch_id:
            task_batch = getattr(task, "batch_id", "") or f"{task.service}_{task.creator_name}_{task.post_id}"
            if task_batch != self._selected_batch_id:
                return False

        if self._min_file_size > 0:
            effective_size = max(task.file_size, task.downloaded_bytes)
            if effective_size < self._min_file_size:
                return False

        if self._filter_status == "all":
            return True
        elif self._filter_status == "downloading":
            return task.status in ("downloading", "retrying")
        elif self._filter_status == "completed":
            return task.status == "completed"
        elif self._filter_status == "skipped":
            return task.status == "skipped"
        elif self._filter_status == "failed":
            return task.status in ("failed", "cancelled")
        elif self._filter_status == "pending":
            return task.status in ("pending", "paused")
        return True

    def _flush_removals(self):
        """Removes the rows that left the filter: each run of neighbouring rows in one step (the
        rows below don't need renumbering, see _RowIndex)."""
        gone = self._pending_removals
        self._pending_removals = set()
        rows = sorted((self._visible_task_row[tid] for tid in gone if tid in self._visible_task_row), reverse=True)
        if not rows:
            return
        runs = 1 + sum(1 for a, b in zip(rows, rows[1:]) if a - b != 1)
        if runs > self.RESET_AFTER_RUNS or self._visible_task_row.needs_compacting():
            # Thousands of scattered rows (files skipped quickly): each removal moved the whole rest
            # of the list (20,000 of them took 9 s on a 300,000-row list). The list is rebuilt once.
            self.beginResetModel()
            self._visible_tasks = [t for t in self._visible_tasks if id(t) not in gone]
            self._visible_task_row.reset(self._visible_tasks)
            self.endResetModel()
            self.countChanged.emit()
            return
        i = 0
        while i < len(rows):
            hi = rows[i]
            lo = hi
            while i + 1 < len(rows) and rows[i + 1] == lo - 1:
                i += 1
                lo = rows[i]
            self.beginRemoveRows(QModelIndex(), lo, hi)
            del self._visible_tasks[lo:hi + 1]
            self.endRemoveRows()
            i += 1
        self._visible_task_row.remove_many(gone)
        self.countChanged.emit()

    _STATUS_FILTERS = {"downloading": ("downloading", "retrying"), "completed": ("completed",),
                       "skipped": ("skipped",), "failed": ("failed", "cancelled"), "pending": ("pending", "paused")}

    def _rebuild_visible(self):
        self._pending_removals = set()
        wanted = self._STATUS_FILTERS.get(self._filter_status)
        if self._selected_batch_id or self._min_file_size > 0 or (wanted is None and self._filter_status != "all"):
            self._visible_tasks = [t for t in self._tasks if self._matches_filter(t)]
        elif wanted is None:
            self._visible_tasks = list(self._tasks)          # everything: no check per task (big queues)
        else:
            self._visible_tasks = [t for t in self._tasks if t.status in wanted]
        self._visible_task_row.reset(self._visible_tasks)

    # ── Properties ────────────────────────────────────────────────────────────
    @Property(int, notify=minFileSizeChanged)
    def minFileSize(self) -> int:
        return self._min_file_size

    @minFileSize.setter
    def minFileSize(self, val: int):
        val = max(0, int(val))
        if self._min_file_size != val:
            self.beginResetModel()
            self._min_file_size = val
            self._rebuild_visible()
            self.endResetModel()
            self.minFileSizeChanged.emit()
            self.countChanged.emit()
    @Property(str, notify=filterStatusChanged)
    def filterStatus(self) -> str:
        return self._filter_status

    @filterStatus.setter
    def filterStatus(self, val: str):
        if self._filter_status != val:
            self.beginResetModel()
            self._filter_status = val
            self._rebuild_visible()
            self.endResetModel()
            self.filterStatusChanged.emit()
            self.countChanged.emit()

    @Property(int, notify=countsChanged)
    def totalCount(self) -> int:
        return len(self._tasks)

    @Property(int, notify=countsChanged)
    def downloadingCount(self) -> int:
        return self._downloading_count

    @Property(int, notify=countsChanged)
    def completedCount(self) -> int:
        return self._completed_count

    @Property(int, notify=countsChanged)
    def skippedCount(self) -> int:
        return self._skipped_count

    @Property(int, notify=failedCountChanged)
    def failedCount(self) -> int:
        p = self.parent()
        skip_404 = bool(getattr(p, "skipRetry404", False)) if p else False

        # Counted as tasks change, and the saved failed files come from memory: this is read every
        # time the button redraws, so it must never loop over the queue or read the file (it stalled
        # the window with big queues / failed lists)
        if self._failed_count > 0:
            return max(0, self._failed_count - len(self._failed_404)) if skip_404 else self._failed_count

        rm = getattr(p, "recovery_manager", None) if p else None
        if rm is not None and hasattr(rm, "retry_counts"):
            try:
                counts = rm.retry_counts(wait=False) or rm.retry_counts_cached()
                return counts[1] if skip_404 else counts[0]
            except Exception:
                pass
        return 0

    @Property(int, notify=countsChanged)
    def pendingCount(self) -> int:
        return self._pending_count

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._visible_tasks)

    # ── QAbstractListModel methods ────────────────────────────────────────────
    def rowCount(self, parent=QModelIndex()):
        return len(self._visible_tasks)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._visible_tasks):
            return None

        task = self._visible_tasks[index.row()]

        if role == self.FilenameRole:
            return task.filename
        elif role == self.PostTitleRole:
            return task.post_title
        elif role == self.CreatorNameRole:
            return task.creator_name
        elif role == self.ServiceRole:
            return task.service
        elif role == self.StatusRole:
            return task.status
        elif role == self.ProgressRole:
            if task.file_size > 0:
                return min(1.0, max(0.0, task.downloaded_bytes / task.file_size))
            return 1.0 if task.status in ("completed", "skipped") else 0.0
        elif role == self.FileSizeRole:
            return self._format_size(task.file_size)
        elif role == self.DownloadedBytesRole:
            return self._format_size(task.downloaded_bytes)
        elif role == self.ErrorMsgRole:
            return task.error_msg
        elif role == self.UrlRole:
            return task.url
        elif role == self.SpeedRole:
            return task.speed_str
        elif role == self.EtaRole:
            return task.eta_str
        elif role == self.PercentageRole:
            return task.progress_pct
        elif role == self.OriginalIndexRole:
            if self._task_index_dirty:
                self._task_index_by_id = {id(t): i for i, t in enumerate(self._tasks)}
                self._task_index_dirty = False
            return self._task_index_by_id.get(id(task), index.row())
        elif role == self.FileIdRole:
            return task.file_id
        elif role == self.RetryCountRole:
            return getattr(task, "retry_count", 0)
        elif role == self.BatchIdRole:
            return getattr(task, "batch_id", "") or f"{task.service}_{task.creator_name}_{task.post_id}"
        elif role == self.TargetPathRole:
            return getattr(task, "target_path", "") or ""
        elif role == self.IsUnimportedRole:
            return is_task_non_retryable(task)

        return None

    def roleNames(self):
        return {
            self.FilenameRole: b"filename",
            self.PostTitleRole: b"postTitle",
            self.CreatorNameRole: b"creatorName",
            self.ServiceRole: b"service",
            self.StatusRole: b"status",
            self.ProgressRole: b"progress",
            self.FileSizeRole: b"fileSize",
            self.DownloadedBytesRole: b"downloadedBytes",
            self.ErrorMsgRole: b"errorMsg",
            self.UrlRole: b"url",
            self.SpeedRole: b"speed",
            self.EtaRole: b"eta",
            self.PercentageRole: b"percentage",
            self.OriginalIndexRole: b"originalIndex",
            self.FileIdRole: b"fileId",
            self.RetryCountRole: b"retryCount",
            self.BatchIdRole: b"batchId",
            self.TargetPathRole: b"targetPath",
            self.IsUnimportedRole: b"isUnimported"
        }

    # ── Grouping & Batch View Properties ──────────────────────────────────────
    @Property(str, notify=selectedBatchIdChanged)
    def selectedBatchId(self) -> str:
        return self._selected_batch_id

    @selectedBatchId.setter
    def selectedBatchId(self, val: str):
        if self._selected_batch_id != val:
            self.beginResetModel()
            self._selected_batch_id = val
            self._rebuild_visible()
            self.endResetModel()
            self.selectedBatchIdChanged.emit()
            self.countChanged.emit()

    @Property(str, notify=viewModeChanged)
    def viewMode(self) -> str:
        return self._view_mode

    @viewMode.setter
    def viewMode(self, val: str):
        if self._view_mode != val:
            self._view_mode = val
            self.viewModeChanged.emit()

    @Property(QObject, constant=True)
    def groupsModel(self) -> Optional[QAbstractListModel]:
        return self._groups_model

    @Property(int, notify=groupsChanged)
    def groupsCount(self) -> int:
        return self._groups_model.rowCount() if self._groups_model else 0

    @Property("QVariantList", notify=groupsChanged)
    def groups(self) -> List[Dict[str, Any]]:
        return self._groups_model.to_dict_list() if self._groups_model else []

    @groups.setter
    def groups(self, val):
        pass


    @Slot(object)
    def _run_gui_call(self, fn):
        fn()

    def _off_gui_thread(self, fn) -> bool:
        """Models may only change on the GUI thread (a reset from a worker thread can crash the
        app). Called from another thread, fn is queued for the GUI thread and True is returned."""
        if QThread.currentThread() is not self.thread():
            self._guiCall.emit(fn)
            return True
        return False

    def setTasks(self, tasks: List[DownloadTask]):
        tasks = list(tasks)
        if self._off_gui_thread(lambda: self.setTasks(tasks)):
            return
        self.beginResetModel()
        self._counts_timer.stop()
        self._removal_timer.stop()
        self._pending_removals = set()
        self._tasks = tasks
        self._task_index_dirty = True
        self._task_last_emit.clear()
        self._task_last_status = {id(t): t.status for t in tasks}
        self._recalculate_counts()
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        self._rebuild_visible()
        self._signatures_dirty = True
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.rebuild(self._tasks, background=True)
            self.groupsChanged.emit()

    def _ensure_signatures(self):
        if self._signatures_dirty:
            sigs = set()
            for t in self._tasks:
                sigs.add((t.url, t.target_path))
                if t.file_id:
                    sigs.add(t.file_id)
            self._signatures = sigs
            self._signatures_dirty = False

    def appendTasks(self, tasks: List[DownloadTask]) -> int:
        if not tasks:
            return 0
        tasks = list(tasks)
        if self._off_gui_thread(lambda: self.appendTasks(tasks)):
            return len(tasks)
        self._ensure_signatures()
        existing_signatures = self._signatures

        deduped = []
        for t in tasks:
            sig1 = (t.url, t.target_path)
            sig2 = t.file_id
            if sig1 in existing_signatures or (sig2 and sig2 in existing_signatures):
                continue
            existing_signatures.add(sig1)
            if sig2:
                existing_signatures.add(sig2)
            t._last_model_status = getattr(t, "status", "")
            deduped.append(t)

        if not deduped:
            return 0

        # Counted and shown incrementally: only the new tasks are looked at
        base_idx = len(self._tasks)
        self._tasks.extend(deduped)
        if not self._task_index_dirty:
            for offset, t in enumerate(deduped):
                self._task_index_by_id[id(t)] = base_idx + offset
        for t in deduped:
            st = t.status
            self._task_last_status[id(t)] = st
            if st in ("downloading", "retrying"):
                self._downloading_count += 1
            elif st == "completed":
                self._completed_count += 1
            elif st == "skipped":
                self._skipped_count += 1
            elif st in ("failed", "cancelled"):
                self._failed_count += 1
                if self._is_404(t):
                    self._failed_404[id(t)] = True
            elif st in ("pending", "paused"):
                self._pending_count += 1
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        shown = [t for t in deduped if self._matches_filter(t)]
        if shown:
            first = len(self._visible_tasks)
            self.beginInsertRows(QModelIndex(), first, first + len(shown) - 1)
            for t in shown:
                self._visible_task_row.append(t)
            self._visible_tasks.extend(shown)
            self.endInsertRows()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.add_tasks_batch(deduped)
            self.groupsChanged.emit()
        return len(deduped)

    def addTasks(self, tasks: List[DownloadTask]):
        self.appendTasks(tasks)

    def add_tasks(self, tasks: List[DownloadTask]):
        return self.appendTasks(tasks)

    @Slot()
    def refreshActiveRows(self):
        """Emit targeted dataChanged only for currently active visible rows (avoids O(N) full-model invalidation)."""
        if self._off_gui_thread(self.refreshActiveRows):
            return
        active_statuses = ("downloading", "retrying", "converting", "extracting", "waiting")
        roles = [self.ProgressRole, self.SpeedRole, self.EtaRole, self.PercentageRole, self.DownloadedBytesRole]
        run_start = -1
        for row, task in enumerate(self._visible_tasks):
            if getattr(task, "status", "") in active_statuses:
                if run_start < 0:
                    run_start = row
            elif run_start >= 0:
                self.dataChanged.emit(self.index(run_start, 0), self.index(row - 1, 0), roles)
                run_start = -1
        if run_start >= 0:
            self.dataChanged.emit(self.index(run_start, 0), self.index(len(self._visible_tasks) - 1, 0), roles)

