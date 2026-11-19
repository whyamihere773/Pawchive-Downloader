"""
Download Queue Batch Lifecycle, Retry & Failed-Task Operations Mixin
Decomposed from bridge/queue_model.py to keep modules cohesive and under 1,000 lines.
"""

import threading
import time
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QModelIndex, Slot

from core.downloader import DownloadTask, is_task_non_retryable
from core.logger import logger


class QueueModelOpsMixin:
    """Batch pause/resume/cancel/remove/replace, live task updates, and retry operations."""

    @Slot(str)
    def removeBatch(self, batch_id: str):
        if not batch_id:
            return
        self._paused_batch_ids.discard(batch_id)
        if self._groups_model:
            self._groups_model.resume_batch(batch_id)
        self.beginResetModel()
        self._counts_timer.stop()
        self._tasks = [t for t in self._tasks if (getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")) != batch_id or t.status == "downloading"]
        self._signatures_dirty = True
        self._recalculate_counts()
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        if self._selected_batch_id == batch_id:
            self._selected_batch_id = ""
            self.selectedBatchIdChanged.emit()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.remove_batch(batch_id)
            self.groupsChanged.emit()
        self.batchRemoveRequested.emit(batch_id)

    def replace_batches(self, batch_ids: Set[str], replacement_tasks: List[DownloadTask]) -> None:
        """Atomically replaces all tasks belonging to `batch_ids` on the GUI thread."""
        target_bids = {str(b) for b in (batch_ids or ()) if b}
        if not target_bids:
            return
        rep_list = list(replacement_tasks or [])
        if self._off_gui_thread(lambda: self.replace_batches(target_bids, rep_list)):
            return

        def _bid(t: DownloadTask) -> str:
            return getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")

        self._paused_batch_ids.difference_update(target_bids)
        if self._groups_model:
            for bid in target_bids:
                self._groups_model.resume_batch(bid)

        rep_by_batch: Dict[str, List[DownloadTask]] = {}
        for t in rep_list:
            rep_by_batch.setdefault(_bid(t), []).append(t)

        self.beginResetModel()
        self._counts_timer.stop()
        self._removal_timer.stop()
        self._pending_removals = set()

        new_tasks: List[DownloadTask] = []
        emitted_batches: Set[str] = set()
        for t in self._tasks:
            b = _bid(t)
            if b in target_bids:
                if b not in emitted_batches:
                    emitted_batches.add(b)
                    new_tasks.extend(rep_by_batch.get(b, []))
            else:
                new_tasks.append(t)
        for b in target_bids:
            if b not in emitted_batches:
                emitted_batches.add(b)
                new_tasks.extend(rep_by_batch.get(b, []))

        self._tasks = new_tasks
        self._task_last_emit.clear()
        self._task_last_status = {id(t): t.status for t in new_tasks}
        self._signatures_dirty = True
        self._recalculate_counts()
        self._last_counts = (
            self._pending_count,
            self._downloading_count,
            self._completed_count,
            self._skipped_count,
            self._failed_count,
        )
        if self._selected_batch_id in target_bids and not rep_by_batch.get(self._selected_batch_id):
            self._selected_batch_id = ""
            self.selectedBatchIdChanged.emit()
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.rebuild(self._tasks, background=True)
            self.groupsChanged.emit()

    @Slot()
    def cancel_all_pending(self):
        """Cancels all pending, downloading, and retrying tasks in a single fast batch operation."""
        self.beginResetModel()
        self._counts_timer.stop()
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
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.rebuild(self._tasks)
            self.groupsChanged.emit()

    @Slot(str)
    def cancelBatch(self, batch_id: str):
        if not batch_id:
            return
        self._paused_batch_ids.discard(batch_id)
        if self._groups_model:
            self._groups_model.resume_batch(batch_id)
        self.beginResetModel()
        self._counts_timer.stop()
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if bid == batch_id and t.status in ("pending", "downloading", "retrying", "paused"):
                t.status = "cancelled"
                t.error_msg = "Download cancelled by user"
                t.progress_pct = 0
                t.speed_bps = 0
                t.speed_str = "0 KB/s"
                t.eta_str = "--"
                self._task_last_status[id(t)] = "cancelled"
        self._recalculate_counts()
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.rebuild(self._tasks)
            self.groupsChanged.emit()
        self.batchCancelRequested.emit(batch_id)

    @Slot(str)
    def pauseBatch(self, batch_id: str):
        if not batch_id:
            return
        self._paused_batch_ids.add(batch_id)
        if self._groups_model:
            self._groups_model.pause_batch(batch_id)
        self.beginResetModel()
        self._counts_timer.stop()
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if bid == batch_id and t.status in ("pending", "downloading", "retrying"):
                t.status = "paused"
                t.speed_bps = 0
                t.speed_str = "0 KB/s"
                t.eta_str = "--"
                self._task_last_status[id(t)] = "paused"
        self._recalculate_counts()
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        if self._groups_model:
            self._groups_model.rebuild(self._tasks)
            self.groupsChanged.emit()
        self.batchPauseRequested.emit(batch_id)

    @Slot(str)
    def resumeBatch(self, batch_id: str):
        if not batch_id:
            return
        self._paused_batch_ids.discard(batch_id)
        if self._groups_model:
            self._groups_model.resume_batch(batch_id)
        self.beginResetModel()
        self._counts_timer.stop()
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if bid == batch_id and t.status == "paused":
                t.status = "pending"
                t.error_msg = ""
                self._task_last_status[id(t)] = "pending"
        self._recalculate_counts()
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        if self._groups_model:
            self._groups_model.rebuild(self._tasks)
            self.groupsChanged.emit()
        self.batchResumeRequested.emit(batch_id)

    @Slot(str, result=bool)
    def isBatchPaused(self, batch_id: str) -> bool:
        if not batch_id:
            return False
        return batch_id in self._paused_batch_ids

    @Slot(str)
    def toggleBatchPause(self, batch_id: str):
        if self.isBatchPaused(batch_id):
            self.resumeBatch(batch_id)
        else:
            self.pauseBatch(batch_id)

    @Slot(str)
    def retryBatch(self, batch_id: str):
        if not batch_id:
            return
        self._paused_batch_ids.discard(batch_id)
        if self._groups_model:
            self._groups_model.resume_batch(batch_id)
        p = self.parent()
        skip_404 = bool(getattr(p, "skipRetry404", False)) if p else False
        changed = 0
        self.beginResetModel()
        self._counts_timer.stop()
        for t in self._tasks:
            bid = getattr(t, "batch_id", "") or f"{t.service}_{t.creator_name}_{t.post_id}".strip("_")
            if bid == batch_id and (t.status in ("failed", "cancelled") or t.status == "pending"):
                if is_task_non_retryable(t):
                    continue
                if skip_404 and self._is_404(t):
                    continue
                t.status = "pending"
                t.error_msg = ""
                t.retry_count = getattr(t, "retry_count", 0) + 1
                self._task_last_status[id(t)] = "pending"
                changed += 1
        self._recalculate_counts()
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.rebuild(self._tasks)
            self.groupsChanged.emit()
        if changed > 0:
            self.batchRetryRequested.emit(batch_id)

    def updateTask(self, task: DownloadTask):
        try:
            task_id = id(task)
            row = self._visible_task_row.get(task_id)
            is_visible = (row is not None)
            matches = self._matches_filter(task)
            old_status = self._task_last_status.get(task_id)
            new_status = getattr(task, "status", "")

            # If this model does not track groups (e.g. active downloads panel) and the task
            # is not visible and does not match the active filter, skip work immediately.
            if not self._enable_groups and not is_visible and not matches:
                return

            # Throttle progress updates if the task's status hasn't changed
            now = time.time()
            last_emit = self._task_last_emit.get(task_id, 0.0)
            status_changed = (old_status != new_status)
            if not status_changed and (now - last_emit < 0.08):
                return
            self._task_last_emit[task_id] = now

            if is_visible:
                if matches:
                    self._pending_removals.discard(task_id)     # back in the filter before it was removed
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
                elif len(self._visible_tasks) <= self.IMMEDIATE_REMOVAL_ROWS:
                    # Short lists: the row goes at once
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._visible_tasks.pop(row)
                    self._visible_task_row.remove(task_id)
                    if self._visible_task_row.needs_compacting():
                        self._visible_task_row.reset(self._visible_tasks)
                    self.endRemoveRows()
                    self.countChanged.emit()
                else:
                    self._pending_removals.add(task_id)
                    if not self._removal_timer.isActive():
                        self._removal_timer.start()
            else:
                if matches and task_id in self._pending_removals:
                    self._pending_removals.discard(task_id)      # back in the filter before it left
                elif matches:
                    row = len(self._visible_tasks)
                    self.beginInsertRows(QModelIndex(), row, row)
                    self._visible_tasks.append(task)
                    self._visible_task_row.append(task)
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
                    self._failed_404.pop(task_id, None)
                elif old_status in ("pending", "paused"):
                    self._pending_count = max(0, self._pending_count - 1)

                if new_status in ("downloading", "retrying"):
                    self._downloading_count += 1
                elif new_status == "completed":
                    self._completed_count += 1
                elif new_status == "skipped":
                    self._skipped_count += 1
                elif new_status in ("failed", "cancelled"):
                    self._failed_count += 1
                    if self._is_404(task):
                        self._failed_404[task_id] = True
                elif new_status in ("pending", "paused"):
                    self._pending_count += 1

                curr_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
                if self._last_counts != curr_counts:
                    if not self._counts_timer.isActive():
                        self._counts_timer.start()

            if self._groups_model:
                self._groups_model.update_task(task)
        except (ValueError, RuntimeError):
            pass

    @Slot()
    def clear(self):
        if self._off_gui_thread(self.clear):
            return
        self._paused_batch_ids.clear()
        self.beginResetModel()
        self._counts_timer.stop()
        self._tasks.clear()
        self._visible_tasks.clear()
        self._visible_task_row.reset(())
        self._task_last_status.clear()
        self._task_last_emit.clear()
        self._last_counts = (0, 0, 0, 0, 0)
        self._pending_count = 0
        self._downloading_count = 0
        self._completed_count = 0
        self._skipped_count = 0
        self._failed_count = 0
        self._failed_404 = {}
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.clear()
            self.groupsChanged.emit()
        self.cleared.emit()

    @Slot()
    @Slot("QVariantList")
    def clearFailedTasks(self, selected_file_ids: Optional[List[str]] = None):
        """Removes failed and cancelled tasks from the queue (all if selected_file_ids is empty/None)."""
        selected_set = set(selected_file_ids) if selected_file_ids else None

        self.beginResetModel()
        self._counts_timer.stop()
        if selected_set:
            self._tasks = [
                t for t in self._tasks
                if not (t.status in ("failed", "cancelled") and ((t.file_id or t.url or t.filename) in selected_set))
            ]
        else:
            self._tasks = [t for t in self._tasks if t.status not in ("failed", "cancelled")]

        self._signatures_dirty = True
        self._recalculate_counts()
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        self._rebuild_visible()
        self.endResetModel()

        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.rebuild(self._tasks)
            self.groupsChanged.emit()

    @Slot()
    def retryFailed(self):
        """Flags all retryable failed and cancelled tasks as pending and emits retryRequested."""
        p = self.parent()
        skip_404 = bool(getattr(p, "skipRetry404", False)) if p else False
        failed = [
            t for t in self._tasks
            if (t.status in ("failed", "cancelled")
                or (t.status == "pending" and (getattr(t, "retry_count", 0) > 0 or getattr(t, "error_msg", ""))))
            and not is_task_non_retryable(t)
            and not (skip_404 and self._is_404(t))
        ]
        if not failed:
            return
        self.beginResetModel()
        self._counts_timer.stop()
        for t in failed:
            t.retry_count = getattr(t, "retry_count", 0) + 1
            t.retry_capped = False
            t.status = "pending"
            t.error_msg = ""
            t.progress_pct = 0
            self._task_last_status[id(t)] = "pending"
        self._recalculate_counts()
        self._last_counts = (self._pending_count, self._downloading_count, self._completed_count, self._skipped_count, self._failed_count)
        self._rebuild_visible()
        self.endResetModel()
        self.countChanged.emit()
        self.countsChanged.emit()
        self.failedCountChanged.emit()
        if self._groups_model:
            self._groups_model.rebuild(self._tasks)
            self.groupsChanged.emit()

        self.retryRequested.emit()

    @Slot(int)
    def retryTaskAt(self, visible_index: int):
        """Flags a single retryable task at visible_index as pending and triggers single retry."""
        if 0 <= visible_index < len(self._visible_tasks):
            t = self._visible_tasks[visible_index]
            if is_task_non_retryable(t):
                return
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
        return self._build_failed_list(list(self._tasks), skip_404, p)

    @Slot(str)
    def prepareFailedTasksAsync(self, request_id: str):
        """Builds the Retry dialog's list in the background (it stalled the window with big queues and
        failed lists); failedListReady(request_id, count) follows, then the dialog takes it a page at a
        time with getFailedTasksPage."""
        p = self.parent()
        skip_404 = bool(getattr(p, "skipRetry404", False)) if p else False
        tasks = list(self._tasks)
        self._active_failed_request = request_id

        def _job(req_id, req_tasks, req_skip):
            try:
                rows = self._build_failed_list(req_tasks, req_skip, p)
            except Exception as e:
                logger.debug(f"Couldn't list the failed files: {e}", category="queue")
                rows = []
            if getattr(self, "_active_failed_request", None) != req_id:
                return
            self._failed_rows = rows
            try:
                self.failedListReady.emit(req_id, len(rows))
            except RuntimeError:
                pass
        threading.Thread(target=_job, args=(request_id, tasks, skip_404), name="FailedList", daemon=True).start()

    @Slot(int, int, result="QVariantList")
    def getFailedTasksPage(self, offset: int, limit: int):
        rows = getattr(self, "_failed_rows", []) or []
        return rows[max(0, offset):max(0, offset) + max(0, limit)]

    def _build_failed_list(self, tasks, skip_404: bool, p):
        """The Retry dialog's rows: failed / cancelled tasks of the queue, else the saved failed files."""
        failed = []
        has_failed_in_queue = False
        for t in tasks:
            if t.status in ("failed", "cancelled") or (t.status == "pending" and (getattr(t, "retry_count", 0) > 0 or getattr(t, "error_msg", ""))):
                has_failed_in_queue = True
                unimp = is_task_non_retryable(t)
                err_msg = t.error_msg or ("Download cancelled by user" if t.status == "cancelled" else "Download failed")
                if skip_404 and not unimp and ("404" in str(err_msg).lower() or getattr(t, "http_status", 0) == 404):
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
                    "retryCapped": getattr(t, "retry_capped", False) or getattr(t, "retry_count", 0) >= 5,
                    "isUnimported": unimp,
                })

        if not has_failed_in_queue:
            try:
                if p and hasattr(p, "recovery_manager"):
                    spilled = p.recovery_manager.load_retries()
                    if spilled:
                        for item in spilled:
                            d = item.to_dict() if hasattr(item, "to_dict") else (item if isinstance(item, dict) else vars(item))
                            unimp = is_task_non_retryable(d)
                            err_msg = d.get("error_msg") or "Download failed"
                            if skip_404 and not unimp and ("404" in str(err_msg).lower() or d.get("http_status") == 404):
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
                                "retryCapped": d.get("retry_capped", False) or d.get("retry_count", 0) >= 5,
                                "isUnimported": unimp,
                            })
            except Exception as e:
                logger.debug(f"Error loading retries from recovery_manager in getFailedTasksList: {e}")

        return failed

    @Slot("QVariantList")
    def retrySelected(self, selected_file_ids: List[str]):
        """Flags only the user-selected retryable failed/cancelled tasks for retry."""
        p = self.parent()
        skip_404 = bool(getattr(p, "skipRetry404", False)) if p else False
        selected_set = set(selected_file_ids or [])
        blocked_keys = set()
        for t in self._tasks:
            key = t.file_id or t.url or t.filename
            if is_task_non_retryable(t):
                blocked_keys.add(key)
                if t.file_id:
                    blocked_keys.add(t.file_id)
                continue
            if (t.status in ("failed", "cancelled") or t.status == "pending") and (key in selected_set):
                if skip_404 and self._is_404(t):
                    blocked_keys.add(key)
                    continue
                t.retry_count = getattr(t, "retry_count", 0) + 1
                t.retry_capped = False
                t.status = "pending"
                t.error_msg = ""
                t.progress_pct = 0
                self.updateTask(t)

        retryable_ids = [i for i in (selected_file_ids or []) if i not in blocked_keys]
        if retryable_ids:
            self.retrySelectedRequested.emit(retryable_ids)

    def getTasks(self) -> List[DownloadTask]:
        return list(self._tasks)

    @property
    def tasks(self) -> List[DownloadTask]:
        return list(self._tasks)
