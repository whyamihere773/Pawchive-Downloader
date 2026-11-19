"""
Download Queue Groups Model & O(log N) Row Index
Decomposed from bridge/queue_model.py to keep modules cohesive and under 1,000 lines.
"""

from bisect import bisect_left, insort
import threading
from typing import Any, Dict, List

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QTimer, Signal, Slot

from core.downloader import DownloadTask, is_task_non_retryable
from core.logger import logger


class _RowIndex:
    """The row of each visible task, without renumbering the rows below a removed one (that cost
    0.1 s per 300,000 rows for every batch of finished files).

    Every task gets a slot number when it's added to the end of the list; slots never change. The
    slots of removed tasks are kept in a sorted list, so a task's row is its slot minus the removed
    slots before it (one binary search). The slots are numbered again from 0 once many are removed."""

    COMPACT_AT = 50_000

    def __init__(self, tasks=()):
        self.reset(tasks)

    def reset(self, tasks) -> None:
        self._slot = {id(t): i for i, t in enumerate(tasks)}
        self._next = len(self._slot)
        self._dead: List[int] = []

    def append(self, task) -> None:
        self._slot[id(task)] = self._next
        self._next += 1

    def get(self, task_id, default=None):
        s = self._slot.get(task_id)
        return default if s is None else s - bisect_left(self._dead, s)

    def __getitem__(self, task_id) -> int:
        s = self._slot[task_id]
        return s - bisect_left(self._dead, s)

    def __contains__(self, task_id) -> bool:
        return task_id in self._slot

    def __len__(self) -> int:
        return len(self._slot)

    def remove(self, task_id) -> None:
        s = self._slot.pop(task_id, None)
        if s is not None:
            insort(self._dead, s)

    def remove_many(self, task_ids) -> None:
        gone = [s for s in (self._slot.pop(t, None) for t in task_ids) if s is not None]
        if len(gone) > 8:
            self._dead = sorted(self._dead + gone)
        else:
            for s in gone:
                insort(self._dead, s)

    def needs_compacting(self) -> bool:
        return len(self._dead) > self.COMPACT_AT


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
    IsPausedRole = Qt.UserRole + 22
    PausedFilesRole = Qt.UserRole + 23
    UnimportedFilesRole = Qt.UserRole + 24
    RetryableFailedFilesRole = Qt.UserRole + 25

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: List[Dict[str, Any]] = []
        self._row_by_id: Dict[str, int] = {}
        self._tasks_by_id: Dict[str, List[DownloadTask]] = {}
        self._task_ids_by_group: Dict[str, set] = {}
        self._task_last_group_status: Dict[int, str] = {}
        self._last_progress_time: Dict[str, float] = {}
        self._last_emitted_stats: Dict[str, tuple] = {}
        self._paused_batch_ids: set = set()
        # Groups whose numbers changed since the last refresh (refreshed together, a few times a second)
        self._dirty_groups: set = set()
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(120)
        self._flush_timer.timeout.connect(self._flush_dirty_groups)
        # Big queues: the groups are worked out on a background thread (seconds for hundreds of
        # thousands of files) and swapped in; changes arriving meanwhile are replayed afterwards
        self._rebuild_gen = 0
        self._rebuilding = False
        self._queued_adds: List[DownloadTask] = []
        self._queued_updates: Dict[int, DownloadTask] = {}
        self._rebuilt.connect(self._apply_rebuild, Qt.QueuedConnection)

    _rebuilt = Signal(int, object)
    BACKGROUND_REBUILD_AT = 20000

    def pause_batch(self, batch_id: str):
        if batch_id:
            self._paused_batch_ids.add(batch_id)
            if batch_id in self._row_by_id:
                row = self._row_by_id[batch_id]
                g = self._groups[row]
                self._calc_group_stats(g, self._tasks_by_id.get(batch_id, []))
                idx = self.index(row, 0)
                self.dataChanged.emit(idx, idx)

    def resume_batch(self, batch_id: str):
        if batch_id:
            self._paused_batch_ids.discard(batch_id)
            if batch_id in self._row_by_id:
                row = self._row_by_id[batch_id]
                g = self._groups[row]
                self._calc_group_stats(g, self._tasks_by_id.get(batch_id, []))
                idx = self.index(row, 0)
                self.dataChanged.emit(idx, idx)

    def is_batch_paused(self, batch_id: str) -> bool:
        return batch_id in self._paused_batch_ids

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
            self.IsPausedRole: "isPaused",
            self.PausedFilesRole: "pausedFiles",
            self.UnimportedFilesRole: "unimportedFiles",
            self.RetryableFailedFilesRole: "retryableFailedFiles",
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
            self.IsPausedRole: b"isPaused",
            self.PausedFilesRole: b"pausedFiles",
            self.UnimportedFilesRole: b"unimportedFiles",
            self.RetryableFailedFilesRole: b"retryableFailedFiles",
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
        unimported_files = 0
        downloading_files = 0
        pending_files = 0
        paused_files = 0
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
                if is_task_non_retryable(t):
                    unimported_files += 1
            elif t.status in ("downloading", "retrying"):
                downloading_files += 1
                if active_task is None:
                    active_task = t
            elif t.status == "cancelled":
                pass
            elif t.status == "paused":
                paused_files += 1
            else:
                pending_files += 1

        retryable_failed_files = max(0, failed_files - unimported_files)
        batch_id = g.get("batchId", "")
        is_paused = (batch_id in self._paused_batch_ids) or (paused_files > 0 and downloading_files == 0)

        if (completed_files + skipped_files) == total_files and total_files > 0:
            status = "skipped" if (completed_files == 0 and skipped_files > 0) else "completed"
        elif is_paused:
            status = "paused"
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
        g["unimportedFiles"] = unimported_files
        g["retryableFailedFiles"] = retryable_failed_files
        g["downloadingFiles"] = downloading_files
        g["pendingFiles"] = pending_files
        g["pausedFiles"] = paused_files
        g["isPaused"] = is_paused
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

    def _compute_groups(self, all_tasks: List[DownloadTask]) -> Dict[str, Any]:
        """The groups of a task list (no model changes: safe on a background thread)."""
        groups: List[Dict[str, Any]] = []
        row_by_id: Dict[str, int] = {}
        tasks_by_id: Dict[str, List[DownloadTask]] = {}
        ids_by_group: Dict[str, set] = {}
        last_status: Dict[int, str] = {}
        for t in all_tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if not bid:
                bid = "batch_default"
            lst = tasks_by_id.get(bid)
            if lst is None:
                lst = tasks_by_id[bid] = []
                ids_by_group[bid] = set()
                post_title = t.post_title or "Media Collection"
                if bid.startswith("artist_") or bid.startswith("creator_"):
                    post_title = "All Works / Posts"
                row_by_id[bid] = len(groups)
                groups.append({
                    "batchId": bid,
                    "creatorName": t.creator_name or "Unknown Creator",
                    "postTitle": post_title,
                    "service": t.service or "kemono",
                    "postId": t.post_id or "",
                })
            lst.append(t)
            ids_by_group[bid].add(id(t))
            last_status[id(t)] = t.status
        emitted: Dict[str, tuple] = {}
        for g in groups:
            bid = g["batchId"]
            self._calc_group_stats(g, tasks_by_id[bid])
            emitted[bid] = (g["totalFiles"], g["completedFiles"], g["failedFiles"],
                            g["downloadingFiles"], g["pendingFiles"], g["status"])
        return {"groups": groups, "row_by_id": row_by_id, "tasks_by_id": tasks_by_id,
                "ids_by_group": ids_by_group, "last_status": last_status, "emitted": emitted}

    def rebuild(self, all_tasks: List[DownloadTask], background: bool = False):
        self._rebuild_gen += 1
        gen = self._rebuild_gen
        self._queued_adds = []
        self._queued_updates = {}
        tasks = list(all_tasks)
        if background and len(tasks) >= self.BACKGROUND_REBUILD_AT:
            self._rebuilding = True

            def _job():
                try:
                    built = self._compute_groups(tasks)
                except Exception as e:
                    logger.debug(f"Couldn't group the queue: {e}", category="queue")
                    built = self._compute_groups([])
                try:
                    self._rebuilt.emit(gen, built)
                except RuntimeError:
                    pass
            threading.Thread(target=_job, name="QueueGroups", daemon=True).start()
            return
        self._rebuilding = False
        self._apply_rebuild(gen, self._compute_groups(tasks))

    @Slot(int, object)
    def _apply_rebuild(self, gen: int, built: Dict[str, Any]):
        if gen != self._rebuild_gen:
            return                    # a newer rebuild started meanwhile
        self.beginResetModel()
        self._groups = built["groups"]
        self._row_by_id = built["row_by_id"]
        self._tasks_by_id = built["tasks_by_id"]
        self._task_ids_by_group = built["ids_by_group"]
        self._task_last_group_status = built["last_status"]
        self._last_progress_time.clear()
        self._last_emitted_stats = built["emitted"]
        self._dirty_groups = set()
        self.endResetModel()
        if self._rebuilding:
            self._rebuilding = False
            adds, updates = self._queued_adds, self._queued_updates
            self._queued_adds, self._queued_updates = [], {}
            if adds:
                self.add_tasks_batch(adds)
            for t in updates.values():
                self.update_task(t)

    def add_tasks_batch(self, new_tasks: List[DownloadTask]):
        """Fast incremental batch insertion of newly queued tasks without wiping all existing groups."""
        if not new_tasks:
            return
        if self._rebuilding:
            self._queued_adds.extend(new_tasks)
            return
        if not self._groups:
            self.rebuild(new_tasks)
            return

        tasks_by_batch: Dict[str, List[DownloadTask]] = {}
        for t in new_tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_") or "batch_default"
            tasks_by_batch.setdefault(bid, []).append(t)

        new_groups_to_insert = []
        for bid, b_tasks in tasks_by_batch.items():
            if bid not in self._row_by_id:
                sample_t = b_tasks[0]
                post_title = sample_t.post_title or "Media Collection"
                if bid.startswith("artist_") or bid.startswith("creator_"):
                    post_title = "All Works / Posts"
                g = {
                    "batchId": bid,
                    "creatorName": sample_t.creator_name or "Unknown Creator",
                    "postTitle": post_title,
                    "service": sample_t.service or "kemono",
                    "postId": sample_t.post_id or "",
                }
                new_groups_to_insert.append((bid, g, b_tasks))
            else:
                group_task_ids = self._task_ids_by_group.setdefault(bid, set())
                t_list = self._tasks_by_id.setdefault(bid, [])
                for t in b_tasks:
                    tid = id(t)
                    if tid not in group_task_ids:
                        group_task_ids.add(tid)
                        t_list.append(t)
                    self._task_last_group_status[tid] = getattr(t, "status", "")
                self._dirty_groups.add(bid)

        if new_groups_to_insert:
            start_row = len(self._groups)
            end_row = start_row + len(new_groups_to_insert) - 1
            self.beginInsertRows(QModelIndex(), start_row, end_row)
            for idx, (bid, g, b_tasks) in enumerate(new_groups_to_insert):
                row = start_row + idx
                self._row_by_id[bid] = row
                self._tasks_by_id[bid] = list(b_tasks)
                self._task_ids_by_group[bid] = {id(t) for t in b_tasks}
                for t in b_tasks:
                    self._task_last_group_status[id(t)] = getattr(t, "status", "")
                self._calc_group_stats(g, b_tasks)
                self._groups.append(g)
                self._last_emitted_stats[bid] = (
                    g["totalFiles"], g["completedFiles"], g["skippedFiles"], g["failedFiles"],
                    g["downloadingFiles"], g["pendingFiles"], g["status"], g.get("isPaused", False)
                )
            self.endInsertRows()

        if self._dirty_groups and not self._flush_timer.isActive():
            self._flush_timer.start()

    def update_task(self, task: DownloadTask):
        if self._rebuilding:
            self._queued_updates[id(task)] = task
            return
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
                g["downloadingFiles"], g["pendingFiles"], g["status"], g.get("isPaused", False)
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
                g.get("unimportedFiles", 0), g["downloadingFiles"], g["pendingFiles"],
                g["status"], g.get("isPaused", False)
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
            self._paused_batch_ids.discard(batch_id)
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
        self._paused_batch_ids.clear()
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
