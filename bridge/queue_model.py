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

    countChanged = Signal()
    filterStatusChanged = Signal()
    countsChanged = Signal()
    failedCountChanged = Signal()
    retryRequested = Signal()
    singleRetryRequested = Signal(str)
    retrySelectedRequested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: List[DownloadTask] = []
        self._filter_status: str = "all" # "all", "downloading", "completed", "failed", "pending"
        self._visible_tasks: List[DownloadTask] = []

    def _matches_filter(self, task: DownloadTask) -> bool:
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
            self.RetryCountRole: b"retryCount"
        }

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

    def addTasks(self, tasks: List[DownloadTask]):
        if not tasks:
            return
        self.beginResetModel()
        self._tasks.extend(tasks)
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
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
                    # Task no longer belongs in this filtered view (e.g. completed)
                    row = self._visible_tasks.index(task)
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._visible_tasks.pop(row)
                    self.endRemoveRows()
                    self.countChanged.emit()
            else:
                if matches:
                    # Task now belongs in this filtered view (e.g. started downloading)
                    row = len(self._visible_tasks)
                    self.beginInsertRows(QModelIndex(), row, row)
                    self._visible_tasks.append(task)
                    self.endInsertRows()
                    self.countChanged.emit()

            self.countsChanged.emit()
            self.failedCountChanged.emit()
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
                failed.append({
                    "fileId": t.file_id,
                    "filename": t.filename,
                    "postTitle": t.post_title,
                    "creatorName": t.creator_name,
                    "service": t.service,
                    "url": t.url,
                    "errorMsg": t.error_msg or "Download failed",
                    "fileSize": self._format_size(t.file_size),
                    "retryCount": getattr(t, "retry_count", 0)
                })
        return failed

    @Slot("QVariantList")
    def retrySelected(self, selected_file_ids: List[str]):
        """Flags only the user-selected failed tasks for retry."""
        selected_set = set(selected_file_ids)
        for t in self._tasks:
            if t.status == "failed" and (t.file_id in selected_set or t.url in selected_set or t.filename in selected_set):
                t.retry_count = getattr(t, "retry_count", 0) + 1
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
