"""
Download Queue Qt Model
Exposes an observable QAbstractListModel for active, pending, completed, and failed tasks.
"""

import time
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot, Property, QObject, QTimer, QThread
from typing import List, Dict, Any, Optional
from core.downloader import DownloadTask
from core.logger import logger


class QueueGroupsModel(QAbstractListModel):
    BatchIdRole = Qt.UserRole + 1
    CreatorNameRole = Qt.UserRole + 2
    PostTitleRole = Qt.UserRole + 3
    ServiceRole = Qt.UserRole + 4
    PostIdRole = Qt.UserRole + 5
    TotalFilesRole = Qt.UserRole + 6
    CompletedFilesRole = Qt.UserRole + 7
    FailedFilesRole = Qt.UserRole + 8
    DownloadingFilesRole = Qt.UserRole + 9
    PendingFilesRole = Qt.UserRole + 10
    SkippedFilesRole = Qt.UserRole + 11
    TotalBytesRole = Qt.UserRole + 12
    DownloadedBytesRole = Qt.UserRole + 13
    TotalBytesStrRole = Qt.UserRole + 14
    DownloadedBytesStrRole = Qt.UserRole + 15
    StatusRole = Qt.UserRole + 16
    TotalProgressRole = Qt.UserRole + 17
    ProgressRole = Qt.UserRole + 18
    ActiveFileNameRole = Qt.UserRole + 19
    ActiveFileProgressPctRole = Qt.UserRole + 20
    ActiveFileSpeedRole = Qt.UserRole + 21

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: List[Dict[str, Any]] = []
        self._row_by_id: Dict[str, int] = {}
        self._tasks_by_id: Dict[str, List[DownloadTask]] = {}
        self._task_ids_by_group: Dict[str, set] = {}
        self._task_last_group_status: Dict[int, str] = {}
        self._last_progress_time: Dict[str, float] = {}
        self._last_emitted_stats: Dict[str, tuple] = {}
        # Groups whose numbers changed since the last refresh (refreshed together, a few times a second)
        self._dirty_groups: set = set()
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(120)
        self._flush_timer.timeout.connect(self._flush_dirty_groups)

    def rowCount(self, parent=QModelIndex()):
        return len(self._groups)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._groups):
            return None
        g = self._groups[index.row()]
        role_map = {
            self.BatchIdRole: "batchId",
            self.CreatorNameRole: "creatorName",
            self.PostTitleRole: "postTitle",
            self.ServiceRole: "service",
            self.PostIdRole: "postId",
            self.TotalFilesRole: "totalFiles",
            self.CompletedFilesRole: "completedFiles",
            self.SkippedFilesRole: "skippedFiles",
            self.FailedFilesRole: "failedFiles",
            self.DownloadingFilesRole: "downloadingFiles",
            self.PendingFilesRole: "pendingFiles",
            self.TotalBytesRole: "totalBytes",
            self.DownloadedBytesRole: "downloadedBytes",
            self.TotalBytesStrRole: "totalBytesStr",
            self.DownloadedBytesStrRole: "downloadedBytesStr",
            self.StatusRole: "status",
            self.TotalProgressRole: "totalProgress",
            self.ProgressRole: "progress",
            self.ActiveFileNameRole: "activeFileName",
            self.ActiveFileProgressPctRole: "activeFileProgressPct",
            self.ActiveFileSpeedRole: "activeFileSpeed",
        }
        key = role_map.get(role)
        if key:
            return g.get(key)
        return None

    def roleNames(self):
        return {
            self.BatchIdRole: b"batchId",
            self.CreatorNameRole: b"creatorName",
            self.PostTitleRole: b"postTitle",
            self.ServiceRole: b"service",
            self.PostIdRole: b"postId",
            self.TotalFilesRole: b"totalFiles",
            self.CompletedFilesRole: b"completedFiles",
            self.SkippedFilesRole: b"skippedFiles",
            self.FailedFilesRole: b"failedFiles",
            self.DownloadingFilesRole: b"downloadingFiles",
            self.PendingFilesRole: b"pendingFiles",
            self.TotalBytesRole: b"totalBytes",
            self.DownloadedBytesRole: b"downloadedBytes",
            self.TotalBytesStrRole: b"totalBytesStr",
            self.DownloadedBytesStrRole: b"downloadedBytesStr",
            self.StatusRole: b"status",
            self.TotalProgressRole: b"totalProgress",
            self.ProgressRole: b"progress",
            self.ActiveFileNameRole: b"activeFileName",
            self.ActiveFileProgressPctRole: b"activeFileProgressPct",
            self.ActiveFileSpeedRole: b"activeFileSpeed",
        }

    @staticmethod
    def _format_size(b: int) -> str:
        if b <= 0:
            return "-"
        if b >= 1024 * 1024 * 1024:
            return f"{b / (1024 * 1024 * 1024):.2f} GB"
        elif b >= 1024 * 1024:
            return f"{b / (1024 * 1024):.1f} MB"
        elif b >= 1024:
            return f"{b / 1024:.1f} KB"
        return f"{b} B"

    def _calc_group_stats(self, g: Dict[str, Any], tasks: List[DownloadTask]):
        completed_files = 0
        skipped_files = 0
        failed_files = 0
        downloading_files = 0
        pending_files = 0
        total_files = len(tasks)
        total_bytes = 0
        downloaded_bytes = 0
        active_task = None

        for t in tasks:
            eff_size = max(t.file_size, t.downloaded_bytes)
            total_bytes += eff_size
            downloaded_bytes += t.downloaded_bytes
            if t.status == "completed":
                completed_files += 1
            elif t.status == "skipped":
                skipped_files += 1
            elif t.status == "failed":
                failed_files += 1
            elif t.status in ("downloading", "retrying"):
                downloading_files += 1
                if active_task is None:
                    active_task = t
            elif t.status == "cancelled":
                pass
            else:
                pending_files += 1

        if (completed_files + skipped_files) == total_files and total_files > 0:
            status = "skipped" if (completed_files == 0 and skipped_files > 0) else "completed"
        elif downloading_files > 0:
            status = "downloading"
        elif failed_files > 0 and (completed_files + skipped_files + failed_files == total_files):
            status = "failed"
        elif completed_files > 0:
            status = "partial"
        elif skipped_files > 0 and (skipped_files + pending_files == total_files):
            status = "skipped"
        elif pending_files > 0:
            status = "pending"
        else:
            status = "cancelled"

        total_progress = ((completed_files + skipped_files) / total_files) if total_files > 0 else (1.0 if status in ("completed", "skipped") else 0.0)
        progress = (downloaded_bytes / total_bytes) if total_bytes > 0 else (1.0 if status in ("completed", "skipped") else 0.0)

        g["totalFiles"] = total_files
        g["completedFiles"] = completed_files
        g["skippedFiles"] = skipped_files
        g["failedFiles"] = failed_files
        g["downloadingFiles"] = downloading_files
        g["pendingFiles"] = pending_files
        g["totalBytes"] = total_bytes
        g["downloadedBytes"] = downloaded_bytes
        g["totalBytesStr"] = self._format_size(total_bytes)
        g["downloadedBytesStr"] = self._format_size(downloaded_bytes)
        g["status"] = status
        g["totalProgress"] = total_progress
        g["progress"] = progress

        if active_task:
            g["activeFileName"] = getattr(active_task, "filename", "") or ""
            g["activeFileProgressPct"] = getattr(active_task, "progress_pct", 0)
            g["activeFileSpeed"] = getattr(active_task, "speed_str", "0 KB/s") or "0 KB/s"
        else:
            g["activeFileName"] = ""
            g["activeFileProgressPct"] = 0
            g["activeFileSpeed"] = ""

    def rebuild(self, all_tasks: List[DownloadTask]):
        self.beginResetModel()
        self._groups = []
        self._row_by_id = {}
        self._tasks_by_id = {}
        self._task_ids_by_group = {}
        self._task_last_group_status.clear()
        self._last_progress_time.clear()
        self._last_emitted_stats.clear()

        for t in all_tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if not bid:
                bid = "batch_default"
            if bid not in self._tasks_by_id:
                self._tasks_by_id[bid] = []
                self._task_ids_by_group[bid] = set()
                post_title = t.post_title or "Media Collection"
                if bid.startswith("artist_") or bid.startswith("creator_"):
                    post_title = "All Works / Posts"
                g = {
                    "batchId": bid,
                    "creatorName": t.creator_name or "Unknown Creator",
                    "postTitle": post_title,
                    "service": t.service or "kemono",
                    "postId": t.post_id or "",
                }
                self._row_by_id[bid] = len(self._groups)
                self._groups.append(g)
            self._tasks_by_id[bid].append(t)
            self._task_ids_by_group[bid].add(id(t))
            self._task_last_group_status[id(t)] = getattr(t, "status", "")

        for g in self._groups:
            bid = g["batchId"]
            self._calc_group_stats(g, self._tasks_by_id[bid])
            self._last_emitted_stats[bid] = (
                g["totalFiles"], g["completedFiles"], g["failedFiles"],
                g["downloadingFiles"], g["pendingFiles"], g["status"]
            )

        self.endResetModel()

    def update_task(self, task: DownloadTask):
        bid = getattr(task, "batch_id", "") or f"{task.service}_{task.creator_name}_{task.post_id}".strip("_")
        if not bid:
            bid = "batch_default"

        tid = id(task)
        new_status = getattr(task, "status", "")

        if bid not in self._row_by_id:
            row = len(self._groups)
            self.beginInsertRows(QModelIndex(), row, row)
            self._tasks_by_id[bid] = [task]
            self._task_ids_by_group[bid] = {tid}
            self._task_last_group_status[tid] = new_status
            self._row_by_id[bid] = row
            post_title = task.post_title or "Media Collection"
            if bid.startswith("artist_") or bid.startswith("creator_"):
                post_title = "All Works / Posts"
            g = {
                "batchId": bid,
                "creatorName": task.creator_name or "Unknown Creator",
                "postTitle": post_title,
                "service": task.service or "kemono",
                "postId": task.post_id or "",
            }
            self._calc_group_stats(g, self._tasks_by_id[bid])
            self._groups.append(g)
            self._last_emitted_stats[bid] = (
                g["totalFiles"], g["completedFiles"], g["skippedFiles"], g["failedFiles"],
                g["downloadingFiles"], g["pendingFiles"], g["status"]
            )
            self.endInsertRows()
        else:
            row = self._row_by_id[bid]
            g = self._groups[row]
            tasks = self._tasks_by_id.get(bid, [])
            group_task_ids = self._task_ids_by_group.setdefault(bid, set())

            is_new_task = (tid not in group_task_ids)
            if is_new_task:
                group_task_ids.add(tid)
                tasks.append(task)

            self._task_last_group_status[tid] = new_status

            # Recalculate this group with the next batched refresh instead of right now
            self._dirty_groups.add(bid)
            if not self._flush_timer.isActive():
                self._flush_timer.start()

    def _flush_dirty_groups(self):
        """Recalculate every group that changed since the last refresh, once each."""
        dirty, self._dirty_groups = self._dirty_groups, set()
        for bid in dirty:
            row = self._row_by_id.get(bid)
            if row is None or row >= len(self._groups):
                continue
            g = self._groups[row]
            self._calc_group_stats(g, self._tasks_by_id.get(bid, []))
            old_stats = self._last_emitted_stats.get(bid)
            new_stats = (
                g["totalFiles"], g["completedFiles"], g["skippedFiles"], g["failedFiles"],
                g["downloadingFiles"], g["pendingFiles"], g["status"]
            )
            idx = self.index(row, 0)
            # If structural stats (counts, status) changed, emit full dataChanged
            if old_stats != new_stats:
                self._last_emitted_stats[bid] = new_stats
                self.dataChanged.emit(idx, idx)
            else:
                self.dataChanged.emit(idx, idx, [
                    self.ProgressRole,
                    self.TotalProgressRole,
                    self.DownloadedBytesRole,
                    self.DownloadedBytesStrRole,
                    self.ActiveFileNameRole,
                    self.ActiveFileProgressPctRole,
                    self.ActiveFileSpeedRole
                ])

    def remove_batch(self, batch_id: str):
        if batch_id in self._row_by_id:
            row = self._row_by_id[batch_id]
            self.beginRemoveRows(QModelIndex(), row, row)
            self._groups.pop(row)
            if batch_id in self._tasks_by_id:
                for t in self._tasks_by_id[batch_id]:
                    self._task_last_group_status.pop(id(t), None)
                del self._tasks_by_id[batch_id]
            if batch_id in self._task_ids_by_group:
                del self._task_ids_by_group[batch_id]
            if batch_id in self._last_progress_time:
                del self._last_progress_time[batch_id]
            if batch_id in self._last_emitted_stats:
                del self._last_emitted_stats[batch_id]
            self._row_by_id = {g["batchId"]: i for i, g in enumerate(self._groups)}
            self.endRemoveRows()

    def clear(self):
        self.beginResetModel()
        self._groups.clear()
        self._row_by_id.clear()
        self._tasks_by_id.clear()
        self._task_ids_by_group.clear()
        self._task_last_group_status.clear()
        self._last_progress_time.clear()
        self._last_emitted_stats.clear()
        self.endResetModel()

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return list(self._groups)


class QueueModel(QAbstractListModel):
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

    countChanged = Signal()
    filterStatusChanged = Signal()
    minFileSizeChanged = Signal()
    countsChanged = Signal()
    failedCountChanged = Signal()
    groupsChanged = Signal()
    selectedBatchIdChanged = Signal()
    viewModeChanged = Signal()
    retryRequested = Signal()
    singleRetryRequested = Signal(str)
    retrySelectedRequested = Signal(list)
    batchRetryRequested = Signal(str)
    batchCancelRequested = Signal(str)
    batchRemoveRequested = Signal(str)
    cleared = Signal()
    _guiCall = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._guiCall.connect(self._run_gui_call, Qt.QueuedConnection)
        self._tasks: List[DownloadTask] = []
        self._filter_status: str = "all" # "all", "downloading", "completed", "failed", "pending"
        self._min_file_size: int = 0
        self._selected_batch_id: str = ""
        self._view_mode: str = "grouped" # "grouped" or "flat"
        self._visible_tasks: List[DownloadTask] = []
        self._visible_task_row: Dict[int, int] = {}
        self._groups_model = QueueGroupsModel(self)
        self._last_counts: Optional[tuple] = None
        self._pending_count: int = 0
        self._downloading_count: int = 0
        self._completed_count: int = 0
        self._skipped_count: int = 0
        self._failed_count: int = 0
        self._task_last_status: Dict[int, str] = {}
        self._task_last_emit: Dict[int, float] = {}

    def _recalculate_counts(self):
        pending = 0
        downloading = 0
        completed = 0
        skipped = 0
        failed = 0
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
            elif st == "pending":
                pending += 1
        self._pending_count = pending
        self._downloading_count = downloading
        self._completed_count = completed
        self._skipped_count = skipped
        self._failed_count = failed

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
            return task.status == "pending"
        return True

    def _rebuild_visible(self):
        self._visible_tasks = [t for t in self._tasks if self._matches_filter(t)]
        self._visible_task_row = {id(t): i for i, t in enumerate(self._visible_tasks)}

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

        if skip_404:
            count = sum(1 for t in self._tasks if t.status in ("failed", "cancelled") and not ("404" in str(getattr(t, "error_msg", "") or "").lower() or getattr(t, "http_status", 0) == 404))
            if count > 0:
                return count
            try:
                if p and hasattr(p, "recovery_manager"):
                    spilled = p.recovery_manager.load_retries()
                    if spilled:
                        return sum(1 for item in spilled if not ("404" in str((item.get("error_msg") if isinstance(item, dict) else getattr(item, "error_msg", "")) or "").lower()))
            except Exception:
                pass
            return count

        if self._failed_count > 0:
            return self._failed_count
        try:
            if p and hasattr(p, "recovery_manager"):
                spilled = p.recovery_manager.load_retries()
                if spilled:
                    return len(spilled)
        except Exception:
            pass
        return self._failed_count

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
            try:
                return self._tasks.index(task)
            except ValueError:
                return index.row()
        elif role == self.FileIdRole:
            return task.file_id
        elif role == self.RetryCountRole:
            return getattr(task, "retry_count", 0)
        elif role == self.BatchIdRole:
            return getattr(task, "batch_id", "") or f"{task.service}_{task.creator_name}_{task.post_id}"
        elif role == self.TargetPathRole:
            return getattr(task, "target_path", "") or ""

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
            self.TargetPathRole: b"targetPath"
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
    def groupsModel(self) -> QAbstractListModel:
        return self._groups_model

    @Property(int, notify=groupsChanged)
    def groupsCount(self) -> int:
        return self._groups_model.rowCount()

    @Property("QVariantList", notify=groupsChanged)
    def groups(self) -> List[Dict[str, Any]]:
        return self._groups_model.to_dict_list()

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
        self._tasks = list(tasks)
        self._task_last_status.clear()
        self._task_last_emit.clear()
        for t in self._tasks:
            self._task_last_status[id(t)] = getattr(t, "status", "")
        self._recalculate_counts()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self._groups_model.rebuild(self._tasks)
        self.groupsChanged.emit()

    def appendTasks(self, tasks: List[DownloadTask]) -> int:
        if not tasks:
            return 0
        tasks = list(tasks)
        if self._off_gui_thread(lambda: self.appendTasks(tasks)):
            return len(tasks)
        existing_signatures = set()
        for t in self._tasks:
            existing_signatures.add((t.url, t.target_path))
            if t.file_id:
                existing_signatures.add(t.file_id)

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

        self.beginResetModel()
        self._tasks.extend(deduped)
        for t in deduped:
            self._task_last_status[id(t)] = getattr(t, "status", "")
        self._recalculate_counts()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self._groups_model.rebuild(self._tasks)
        self.groupsChanged.emit()
        return len(deduped)

    def addTasks(self, tasks: List[DownloadTask]):
        self.appendTasks(tasks)

    def add_tasks(self, tasks: List[DownloadTask]):
        return self.appendTasks(tasks)

    @Slot(str)
    def removeBatch(self, batch_id: str):
        if not batch_id:
            return
        self.beginResetModel()
        self._tasks = [t for t in self._tasks if (getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")) != batch_id or t.status == "downloading"]
        self._recalculate_counts()
        if self._selected_batch_id == batch_id:
            self._selected_batch_id = ""
            self.selectedBatchIdChanged.emit()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self._groups_model.remove_batch(batch_id)
        self.groupsChanged.emit()
        self.batchRemoveRequested.emit(batch_id)

    @Slot()
    def cancel_all_pending(self):
        """Cancels all pending, downloading, and retrying tasks in a single fast batch operation."""
        self.beginResetModel()
        for t in self._tasks:
            if t.status in ("pending", "downloading", "retrying"):
                t.status = "cancelled"
                t.error_msg = "Download cancelled by user"
                t.progress_pct = 0
                t.speed_bps = 0
                t.speed_str = "0 KB/s"
                t.eta_str = "--"
                self._task_last_status[id(t)] = "cancelled"
        self._recalculate_counts()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self._groups_model.rebuild(self._tasks)
        self.groupsChanged.emit()

    @Slot(str)
    def cancelBatch(self, batch_id: str):
        if not batch_id:
            return
        self.beginResetModel()
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if bid == batch_id and t.status in ("pending", "downloading", "retrying"):
                t.status = "cancelled"
                t.error_msg = "Download cancelled by user"
                t.progress_pct = 0
                t.speed_bps = 0
                t.speed_str = "0 KB/s"
                t.eta_str = "--"
                self._task_last_status[id(t)] = "cancelled"
        self._recalculate_counts()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self._groups_model.rebuild(self._tasks)
        self.groupsChanged.emit()
        self.batchCancelRequested.emit(batch_id)

    @Slot(str)
    def retryBatch(self, batch_id: str):
        if not batch_id:
            return
        self.beginResetModel()
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if bid == batch_id and t.status in ("failed", "cancelled"):
                t.status = "pending"
                t.error_msg = ""
                t.retry_count = getattr(t, "retry_count", 0) + 1
                self._task_last_status[id(t)] = "pending"
        self._recalculate_counts()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self._groups_model.rebuild(self._tasks)
        self.groupsChanged.emit()

    def updateTask(self, task: DownloadTask):
        try:
            task_id = id(task)
            row = self._visible_task_row.get(task_id)
            is_visible = (row is not None)
            matches = self._matches_filter(task)
            old_status = self._task_last_status.get(task_id)
            new_status = getattr(task, "status", "")

            # Throttle dataChanged ONLY if the task is ALREADY visible and its status hasn't changed
            now = time.time()
            last_emit = self._task_last_emit.get(task_id, 0.0)
            status_changed = (old_status != new_status)
            if is_visible and not status_changed and (now - last_emit < 0.08):
                return
            self._task_last_emit[task_id] = now

            if is_visible:
                if matches:
                    idx = self.index(row, 0)
                    self.dataChanged.emit(idx, idx, [
                        self.ProgressRole,
                        self.PercentageRole,
                        self.DownloadedBytesRole,
                        self.SpeedRole,
                        self.EtaRole,
                        self.StatusRole,
                        self.ErrorMsgRole
                    ])
                else:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._visible_tasks.pop(row)
                    del self._visible_task_row[task_id]
                    for r in range(row, len(self._visible_tasks)):
                        self._visible_task_row[id(self._visible_tasks[r])] = r
                    self.endRemoveRows()
                    self.countChanged.emit()
            else:
                if matches:
                    row = len(self._visible_tasks)
                    self.beginInsertRows(QModelIndex(), row, row)
                    self._visible_tasks.append(task)
                    self._visible_task_row[task_id] = row
                    self.endInsertRows()
                    self.countChanged.emit()

            if status_changed:
                self._task_last_status[task_id] = new_status
                # O(1) incremental counter delta updates
                if old_status in ("downloading", "retrying"):
                    self._downloading_count = max(0, self._downloading_count - 1)
                elif old_status == "completed":
                    self._completed_count = max(0, self._completed_count - 1)
                elif old_status == "skipped":
                    self._skipped_count = max(0, self._skipped_count - 1)
                elif old_status in ("failed", "cancelled"):
                    self._failed_count = max(0, self._failed_count - 1)
                elif old_status == "pending":
                    self._pending_count = max(0, self._pending_count - 1)

                if new_status in ("downloading", "retrying"):
                    self._downloading_count += 1
                elif new_status == "completed":
                    self._completed_count += 1
                elif new_status == "skipped":
                    self._skipped_count += 1
                elif new_status in ("failed", "cancelled"):
                    self._failed_count += 1
                elif new_status == "pending":
                    self._pending_count += 1

                curr_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
                if self._last_counts != curr_counts:
                    prev_failed = self._last_counts[4] if (self._last_counts and len(self._last_counts) > 4) else None
                    self._last_counts = curr_counts
                    self.countsChanged.emit()
                    if prev_failed is None or prev_failed != curr_counts[4]:
                        self.failedCountChanged.emit()

            self._groups_model.update_task(task)
        except (ValueError, RuntimeError):
            pass

    @Slot()
    def clear(self):
        if self._off_gui_thread(self.clear):
            return
        self.beginResetModel()
        self._tasks.clear()
        self._visible_tasks.clear()
        self._visible_task_row.clear()
        self._task_last_status.clear()
        self._task_last_emit.clear()
        self._last_counts = None
        self._pending_count = 0
        self._downloading_count = 0
        self._completed_count = 0
        self._failed_count = 0
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self._groups_model.clear()
        self.groupsChanged.emit()
        self.cleared.emit()

    @Slot()
    @Slot("QVariantList")
    def clearFailedTasks(self, selected_file_ids: Optional[List[str]] = None):
        """Removes failed and cancelled tasks from the queue (all if selected_file_ids is empty/None)."""
        selected_set = set(selected_file_ids) if selected_file_ids else None

        self.beginResetModel()
        if selected_set:
            self._tasks = [
                t for t in self._tasks
                if not (t.status in ("failed", "cancelled") and (t.file_id in selected_set or t.url in selected_set or t.filename in selected_set))
            ]
        else:
            self._tasks = [t for t in self._tasks if t.status not in ("failed", "cancelled")]

        self._recalculate_counts()
        self._rebuild_visible()
        self.endResetModel()

        self._last_counts = None
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self._groups_model.rebuild(self._tasks)
        self.groupsChanged.emit()

    @Slot()
    def retryFailed(self):
        """Flags all failed and cancelled tasks as pending and emits retryRequested."""
        failed = [t for t in self._tasks if t.status in ("failed", "cancelled")]
        if not failed:
            return
        self.beginResetModel()
        for t in failed:
            t.retry_count = getattr(t, "retry_count", 0) + 1
            t.retry_capped = False
            t.status = "pending"
            t.error_msg = ""
            t.progress_pct = 0
            self._task_last_status[id(t)] = "pending"
        self._recalculate_counts()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self._groups_model.rebuild(self._tasks)
        self.groupsChanged.emit()

        self.retryRequested.emit()

    @Slot(int)
    def retryTaskAt(self, visible_index: int):
        """Flags a single task at visible_index as pending and triggers single retry."""
        if 0 <= visible_index < len(self._visible_tasks):
            t = self._visible_tasks[visible_index]
            t.retry_count = getattr(t, "retry_count", 0) + 1
            t.retry_capped = False
            t.status = "pending"
            t.error_msg = ""
            t.progress_pct = 0
            self.updateTask(t)
            self.singleRetryRequested.emit(t.file_id)

    @Slot(result="QVariantList")
    def getFailedTasksList(self):
        """Returns detailed failed and cancelled task metadata for the Retry Modal dialog."""
        p = self.parent()
        skip_404 = bool(getattr(p, "skipRetry404", False)) if p else False

        failed = []
        for t in self._tasks:
            if t.status in ("failed", "cancelled"):
                err_msg = t.error_msg or ("Download cancelled by user" if t.status == "cancelled" else "Download failed")
                if skip_404 and ("404" in str(err_msg).lower() or getattr(t, "http_status", 0) == 404):
                    continue

                p_url = getattr(t, "post_url", "") or ""
                if not p_url and t.service and t.post_id:
                    p_url = f"https://pawchive.pw/{t.service}/user/{t.creator_name}/post/{t.post_id}"

                failed.append({
                    "fileId": t.file_id,
                    "filename": t.filename,
                    "postTitle": t.post_title,
                    "creatorName": t.creator_name,
                    "service": t.service,
                    "postId": t.post_id,
                    "postUrl": p_url,
                    "url": t.url,
                    "errorMsg": err_msg,
                    "fileSize": self._format_size(t.file_size),
                    "retryCount": getattr(t, "retry_count", 0),
                    "retryCapped": getattr(t, "retry_capped", False) or getattr(t, "retry_count", 0) >= 5
                })

        if not failed:
            try:
                if p and hasattr(p, "recovery_manager"):
                    spilled = p.recovery_manager.load_retries()
                    if spilled:
                        for item in spilled:
                            d = item.to_dict() if hasattr(item, "to_dict") else (item if isinstance(item, dict) else vars(item))
                            err_msg = d.get("error_msg") or "Download failed"
                            if skip_404 and ("404" in str(err_msg).lower() or d.get("http_status") == 404):
                                continue

                            p_url = d.get("post_url") or ""
                            if not p_url and d.get("service") and d.get("post_id"):
                                p_url = f"https://pawchive.pw/{d.get('service')}/user/{d.get('creator_name')}/post/{d.get('post_id')}"
                            failed.append({
                                "fileId": d.get("file_id", ""),
                                "filename": d.get("filename", ""),
                                "postTitle": d.get("post_title", ""),
                                "creatorName": d.get("creator_name", ""),
                                "service": d.get("service", ""),
                                "postId": d.get("post_id", ""),
                                "postUrl": p_url,
                                "url": d.get("url", ""),
                                "errorMsg": err_msg,
                                "fileSize": self._format_size(d.get("file_size", 0)),
                                "retryCount": d.get("retry_count", 0),
                                "retryCapped": d.get("retry_capped", False) or d.get("retry_count", 0) >= 5
                            })
            except Exception as e:
                logger.debug(f"Error loading retries from recovery_manager in getFailedTasksList: {e}")

        return failed

    @Slot("QVariantList")
    def retrySelected(self, selected_file_ids: List[str]):
        """Flags only the user-selected failed/cancelled tasks for retry."""
        selected_set = set(selected_file_ids)
        for t in self._tasks:
            if t.status in ("failed", "cancelled") and (t.file_id in selected_set or t.url in selected_set or t.filename in selected_set):
                t.retry_count = getattr(t, "retry_count", 0) + 1
                t.retry_capped = False
                t.status = "pending"
                t.error_msg = ""
                t.progress_pct = 0
                self.updateTask(t)

        self.retrySelectedRequested.emit(selected_file_ids)

    def getTasks(self) -> List[DownloadTask]:
        return list(self._tasks)

    @property
    def tasks(self) -> List[DownloadTask]:
        return list(self._tasks)
