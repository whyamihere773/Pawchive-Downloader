"""
Download Queue Qt Model
Exposes an observable QAbstractListModel for active, pending, completed, and failed tasks.
"""

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot, Property
from typing import List, Dict, Any, Optional
from core.downloader import DownloadTask


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
        return sum(1 for t in self._tasks if t.status in ("downloading", "retrying"))

    @Property(int, notify=countsChanged)
    def completedCount(self) -> int:
        return sum(1 for t in self._tasks if t.status == "completed")

    @Property(int, notify=failedCountChanged)
    def failedCount(self) -> int:
        return sum(1 for t in self._tasks if t.status == "failed")

    @Property(int, notify=countsChanged)
    def pendingCount(self) -> int:
        return sum(1 for t in self._tasks if t.status == "pending")

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

    @Property(int, notify=groupsChanged)
    def groupsCount(self) -> int:
        return len(self.groups)

    @Property("QVariantList", notify=groupsChanged)
    def groups(self) -> List[Dict[str, Any]]:
        groups_dict: Dict[str, Dict[str, Any]] = {}
        # Also track the active (first downloading) task per group
        active_task_dict: Dict[str, Any] = {}
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if not bid:
                bid = "batch_default"
            if bid not in groups_dict:
                post_title = t.post_title or "Media Collection"
                if bid.startswith("artist_") or bid.startswith("creator_"):
                    post_title = "All Works / Posts"
                groups_dict[bid] = {
                    "batchId": bid,
                    "creatorName": t.creator_name or "Unknown Creator",
                    "postTitle": post_title,
                    "service": t.service or "kemono",
                    "postId": t.post_id or "",
                    "totalFiles": 0,
                    "completedFiles": 0,
                    "failedFiles": 0,
                    "downloadingFiles": 0,
                    "pendingFiles": 0,
                    "totalBytes": 0,
                    "downloadedBytes": 0,
                    "status": "pending"
                }
            g = groups_dict[bid]
            g["totalFiles"] += 1
            eff_size = max(t.file_size, t.downloaded_bytes)
            g["totalBytes"] += eff_size
            g["downloadedBytes"] += t.downloaded_bytes
            if t.status == "completed":
                g["completedFiles"] += 1
            elif t.status == "failed":
                g["failedFiles"] += 1
            elif t.status in ("downloading", "retrying"):
                g["downloadingFiles"] += 1
                # Record first downloading task per group for active-file info
                if bid not in active_task_dict:
                    active_task_dict[bid] = t
            else:
                g["pendingFiles"] += 1

        result = []
        for g in groups_dict.values():
            bid = g["batchId"]
            if g["completedFiles"] == g["totalFiles"] and g["totalFiles"] > 0:
                g["status"] = "completed"
            elif g["downloadingFiles"] > 0:
                g["status"] = "downloading"
            elif g["failedFiles"] > 0 and (g["completedFiles"] + g["failedFiles"] == g["totalFiles"]):
                g["status"] = "failed"
            elif g["completedFiles"] > 0:
                g["status"] = "partial"
            else:
                g["status"] = "pending"

            # Total progress: strictly file-counter-based (completedFiles / totalFiles)
            total = g["totalFiles"]
            completed = g["completedFiles"]
            if total > 0:
                g["totalProgress"] = completed / total
            else:
                g["totalProgress"] = 1.0 if g["status"] == "completed" else 0.0

            # Active file progress: from the currently downloading task
            at = active_task_dict.get(bid)
            if at:
                g["activeFileName"] = getattr(at, "filename", "") or ""
                g["activeFileProgressPct"] = getattr(at, "progress_pct", 0)
                g["activeFileSpeed"] = getattr(at, "speed_str", "0 KB/s") or "0 KB/s"
            else:
                g["activeFileName"] = ""
                g["activeFileProgressPct"] = 0
                g["activeFileSpeed"] = ""

            g["progress"] = (g["downloadedBytes"] / g["totalBytes"]) if g["totalBytes"] > 0 else (1.0 if g["status"] == "completed" else 0.0)
            g["totalBytesStr"] = self._format_size(g["totalBytes"])
            g["downloadedBytesStr"] = self._format_size(g["downloadedBytes"])
            result.append(g)
        return result

    def _format_size(self, b: int) -> str:
        if b <= 0:
            return "-"
        if b >= 1024 * 1024 * 1024:
            return f"{b / (1024 * 1024 * 1024):.2f} GB"
        elif b >= 1024 * 1024:
            return f"{b / (1024 * 1024):.1f} MB"
        elif b >= 1024:
            return f"{b / 1024:.1f} KB"
        return f"{b} B"

    def setTasks(self, tasks: List[DownloadTask]):
        self.beginResetModel()
        self._tasks = list(tasks)
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
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
            deduped.append(t)

        if not deduped:
            return 0

        self.beginResetModel()
        self._tasks.extend(deduped)
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
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
        if self._selected_batch_id == batch_id:
            self._selected_batch_id = ""
            self.selectedBatchIdChanged.emit()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self.groupsChanged.emit()
        self.batchRemoveRequested.emit(batch_id)

    @Slot(str)
    def cancelBatch(self, batch_id: str):
        if not batch_id:
            return
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if bid == batch_id and t.status == "pending":
                t.status = "cancelled"
                self.updateTask(t)
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
        self.groupsChanged.emit()
        self.failedCountChanged.emit()

    def updateTask(self, task: DownloadTask):
        try:
            matches = self._matches_filter(task)
            is_visible = task in self._visible_tasks

            if is_visible:
                if matches:
                    row = self._visible_tasks.index(task)
                    idx = self.index(row, 0)
                    self.dataChanged.emit(idx, idx)
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

            self.countsChanged.emit()
            self.failedCountChanged.emit()
            self.groupsChanged.emit()
        except (ValueError, RuntimeError):
            pass

    @Slot()
    def clear(self):
        self.beginResetModel()
        self._tasks.clear()
        self._visible_tasks.clear()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        self.groupsChanged.emit()
        self.cleared.emit()

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
