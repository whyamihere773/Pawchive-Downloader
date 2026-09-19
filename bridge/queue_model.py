"""
Download Queue Qt Model
Exposes an observable QAbstractListModel for active, pending, completed, and failed tasks.
"""

import time
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot, Property, QObject
from typing import List, Dict, Any, Optional
from core.downloader import DownloadTask


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
    TotalBytesRole = Qt.UserRole + 11
    DownloadedBytesRole = Qt.UserRole + 12
    TotalBytesStrRole = Qt.UserRole + 13
    DownloadedBytesStrRole = Qt.UserRole + 14
    StatusRole = Qt.UserRole + 15
    TotalProgressRole = Qt.UserRole + 16
    ProgressRole = Qt.UserRole + 17
    ActiveFileNameRole = Qt.UserRole + 18
    ActiveFileProgressPctRole = Qt.UserRole + 19
    ActiveFileSpeedRole = Qt.UserRole + 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: List[Dict[str, Any]] = []
        self._row_by_id: Dict[str, int] = {}
        self._tasks_by_id: Dict[str, List[DownloadTask]] = {}
        self._last_progress_time: Dict[str, float] = {}
        self._last_emitted_stats: Dict[str, tuple] = {}

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
        total_files = len(tasks)
        completed_files = 0
        failed_files = 0
        downloading_files = 0
        pending_files = 0
        total_bytes = 0
        downloaded_bytes = 0
        active_task = None

        for t in tasks:
            eff_size = max(t.file_size, t.downloaded_bytes)
            total_bytes += eff_size
            downloaded_bytes += t.downloaded_bytes
            if t.status == "completed":
                completed_files += 1
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

        if completed_files == total_files and total_files > 0:
            status = "completed"
        elif downloading_files > 0:
            status = "downloading"
        elif failed_files > 0 and (completed_files + failed_files == total_files):
            status = "failed"
        elif completed_files > 0:
            status = "partial"
        elif pending_files > 0:
            status = "pending"
        else:
            status = "cancelled"

        total_progress = (completed_files / total_files) if total_files > 0 else (1.0 if status == "completed" else 0.0)
        progress = (downloaded_bytes / total_bytes) if total_bytes > 0 else (1.0 if status == "completed" else 0.0)

        g["totalFiles"] = total_files
        g["completedFiles"] = completed_files
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
        self._last_progress_time.clear()
        self._last_emitted_stats.clear()

        for t in all_tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if not bid:
                bid = "batch_default"
            if bid not in self._tasks_by_id:
                self._tasks_by_id[bid] = []
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

        if bid not in self._row_by_id:
            row = len(self._groups)
            self.beginInsertRows(QModelIndex(), row, row)
            self._tasks_by_id[bid] = [task]
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
                g["totalFiles"], g["completedFiles"], g["failedFiles"],
                g["downloadingFiles"], g["pendingFiles"], g["status"]
            )
            self.endInsertRows()
        else:
            row = self._row_by_id[bid]
            g = self._groups[row]
            tasks = self._tasks_by_id.get(bid, [])
            if task not in tasks:
                tasks.append(task)
            self._calc_group_stats(g, tasks)

            old_stats = self._last_emitted_stats.get(bid)
            new_stats = (
                g["totalFiles"], g["completedFiles"], g["failedFiles"],
                g["downloadingFiles"], g["pendingFiles"], g["status"]
            )
            idx = self.index(row, 0)

            # If structural stats (counts, status) changed, emit full dataChanged
            if old_stats != new_stats:
                self._last_emitted_stats[bid] = new_stats
                self.dataChanged.emit(idx, idx)
            else:
                # Only byte progress or speed changed: throttle to ~80ms and emit ONLY progress roles
                # so structural UI bindings (buttons, visibility, layout) do not jitter or drop hover
                now = time.time()
                if now - self._last_progress_time.get(bid, 0.0) < 0.08:
                    return
                self._last_progress_time[bid] = now
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
                del self._tasks_by_id[batch_id]
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: List[DownloadTask] = []
        self._filter_status: str = "all" # "all", "downloading", "completed", "failed", "pending"
        self._min_file_size: int = 0
        self._selected_batch_id: str = ""
        self._view_mode: str = "grouped" # "grouped" or "flat"
        self._visible_tasks: List[DownloadTask] = []
        self._groups_model = QueueGroupsModel(self)
        self._last_counts: Optional[tuple] = None
        self._pending_count: int = 0
        self._downloading_count: int = 0
        self._completed_count: int = 0
        self._failed_count: int = 0
        self._task_last_status: Dict[int, str] = {}
        self._task_last_emit: Dict[int, float] = {}

    def _recalculate_counts(self):
        pending = 0
        downloading = 0
        completed = 0
        failed = 0
        for t in self._tasks:
            st = getattr(t, "status", "")
            if st in ("downloading", "retrying"):
                downloading += 1
            elif st == "completed":
                completed += 1
            elif st == "failed":
                failed += 1
            elif st == "pending":
                pending += 1
        self._pending_count = pending
        self._downloading_count = downloading
        self._completed_count = completed
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
        elif self._filter_status == "failed":
            return task.status == "failed"
        elif self._filter_status == "pending":
            return task.status == "pending"
        return True

    def _rebuild_visible(self):
        self._visible_tasks = [t for t in self._tasks if self._matches_filter(t)]

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

    @Property(int, notify=failedCountChanged)
    def failedCount(self) -> int:
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
            return 1.0 if task.status == "completed" else 0.0
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
            self.BatchIdRole: b"batchId"
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

    def setTasks(self, tasks: List[DownloadTask]):
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

    @Slot(str)
    def cancelBatch(self, batch_id: str):
        if not batch_id:
            return
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if bid == batch_id and t.status in ("pending", "downloading"):
                t.status = "cancelled"
                self.updateTask(t)
        self._groups_model.rebuild(self._tasks)
        self.groupsChanged.emit()
        self.batchCancelRequested.emit(batch_id)

    @Slot(str)
    def retryBatch(self, batch_id: str):
        if not batch_id:
            return
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if bid == batch_id and t.status in ("failed", "cancelled"):
                t.status = "pending"
                t.error_msg = ""
                t.retry_count = getattr(t, "retry_count", 0) + 1
                self.updateTask(t)
        self._groups_model.rebuild(self._tasks)
        self.groupsChanged.emit()
        self.failedCountChanged.emit()

    def updateTask(self, task: DownloadTask):
        try:
            matches = self._matches_filter(task)
            is_visible = task in self._visible_tasks
            old_status = self._task_last_status.get(id(task))
            new_status = getattr(task, "status", "")

            # Throttle dataChanged ONLY if the task is ALREADY visible and its status hasn't changed
            now = time.time()
            last_emit = self._task_last_emit.get(id(task), 0.0)
            status_changed = (old_status != new_status)
            if is_visible and not status_changed and (now - last_emit < 0.08):
                return
            self._task_last_emit[id(task)] = now

            if is_visible:
                if matches:
                    row = self._visible_tasks.index(task)
                    idx = self.index(row, 0)
                    self.dataChanged.emit(idx, idx, [
                        self.ProgressRole,
                        self.PercentageRole,
                        self.DownloadedBytesRole,
                        self.SpeedRole,
                        self.EtaRole,
                        self.StatusRole
                    ])
                else:
                    row = self._visible_tasks.index(task)
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._visible_tasks.pop(row)
                    self.endRemoveRows()
                    self.countChanged.emit()
            else:
                if matches:
                    row = len(self._visible_tasks)
                    self.beginInsertRows(QModelIndex(), row, row)
                    self._visible_tasks.append(task)
                    self.endInsertRows()
                    self.countChanged.emit()

            if status_changed:
                self._task_last_status[id(task)] = new_status
                self._recalculate_counts()
                curr_counts = (self._pending_count, self._downloading_count, self._completed_count, self._failed_count)
                if self._last_counts != curr_counts:
                    prev_failed = self._last_counts[3] if self._last_counts else None
                    self._last_counts = curr_counts
                    self.countsChanged.emit()
                    if prev_failed is None or prev_failed != curr_counts[3]:
                        self.failedCountChanged.emit()

            self._groups_model.update_task(task)
        except (ValueError, RuntimeError):
            pass

    @Slot()
    def clear(self):
        self.beginResetModel()
        self._tasks.clear()
        self._visible_tasks.clear()
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
        """Removes failed tasks from the queue (all failed tasks if selected_file_ids is empty/None)."""
        selected_set = set(selected_file_ids) if selected_file_ids else None

        self.beginResetModel()
        if selected_set:
            self._tasks = [
                t for t in self._tasks
                if not (t.status == "failed" and (t.file_id in selected_set or t.url in selected_set or t.filename in selected_set))
            ]
        else:
            self._tasks = [t for t in self._tasks if t.status != "failed"]

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
        """Flags all failed tasks as pending and emits retryRequested."""
        failed = [t for t in self._tasks if t.status == "failed"]
        for t in failed:
            t.retry_count = getattr(t, "retry_count", 0) + 1
            t.status = "pending"
            t.error_msg = ""
            t.progress_pct = 0
            self.updateTask(t)

        self.retryRequested.emit()

    @Slot(int)
    def retryTaskAt(self, visible_index: int):
        """Flags a single task at visible_index as pending and triggers single retry."""
        if 0 <= visible_index < len(self._visible_tasks):
            t = self._visible_tasks[visible_index]
            t.retry_count = getattr(t, "retry_count", 0) + 1
            t.status = "pending"
            t.error_msg = ""
            t.progress_pct = 0
            self.updateTask(t)
            self.singleRetryRequested.emit(t.file_id)

    @Slot(result="QVariantList")
    def getFailedTasksList(self):
        """Returns detailed failed task metadata for the Retry Modal dialog."""
        failed = []
        for t in self._tasks:
            if t.status == "failed":
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
                    "errorMsg": t.error_msg or "Download failed",
                    "fileSize": self._format_size(t.file_size),
                    "retryCount": getattr(t, "retry_count", 0),
                    "retryCapped": getattr(t, "retry_capped", False) or getattr(t, "retry_count", 0) >= 5
                })
        return failed

    @Slot("QVariantList")
    def retrySelected(self, selected_file_ids: List[str]):
        """Flags only the user-selected failed tasks for retry."""
        selected_set = set(selected_file_ids)
        for t in self._tasks:
            if t.status == "failed" and (t.file_id in selected_set or t.url in selected_set or t.filename in selected_set):
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
