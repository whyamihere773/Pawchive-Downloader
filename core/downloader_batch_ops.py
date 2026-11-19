"""
Downloader Batch Context Management, Pause/Resume/Cancel & Live Rebuild Mixin
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import os
import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from core.downloader_models import (
    BatchBuildContext,
    DownloadTask,
    PART_SUFFIX,
    _remove_quietly,
    atomic_move_part,
    is_task_non_retryable,
)
from core.filter_engine import FilterEngine, FilterOptions, fit_path_for_windows
from core.logger import logger
from core.providers import is_disabled


class DownloaderBatchOpsMixin:
    """Per-batch lifecycle controls, quiescing, external-file queuing, and live in-place rebuilds."""

    @staticmethod
    def _task_batch_id(batch_id_or_task) -> str:
        if isinstance(batch_id_or_task, str):
            return batch_id_or_task
        t = batch_id_or_task
        return (
            getattr(t, "batch_id", "")
            or f"{getattr(t, 'service', '')}_{getattr(t, 'creator_name', '')}_{getattr(t, 'post_id', '')}".strip("_")
        )

    def _track_active_response(self, resp, batch_id: str) -> None:
        if resp is None:
            return
        with self._active_resp_lock:
            self._active_responses[resp] = batch_id or ""

    def _untrack_active_response(self, resp) -> None:
        if resp is None:
            return
        with self._active_resp_lock:
            self._active_responses.pop(resp, None)

    def _close_batch_responses(self, batch_ids: Set[str]) -> int:
        """Closes only active HTTP stream responses belonging to `batch_ids`."""
        if not batch_ids:
            return 0
        with self._active_resp_lock:
            targets = [r for r, bid in list(self._active_responses.items()) if bid in batch_ids]
        closed = 0
        for r in targets:
            try:
                r.close()
                closed += 1
            except Exception:
                pass
        return closed

    def _increment_batch_worker(self, batch_id: str) -> None:
        bid = batch_id or ""
        with self._workers_drained_cond:
            self._active_batch_workers[bid] = self._active_batch_workers.get(bid, 0) + 1

    def _decrement_batch_worker(self, batch_id: str) -> None:
        bid = batch_id or ""
        with self._workers_drained_cond:
            cur = self._active_batch_workers.get(bid, 0) - 1
            if cur <= 0:
                self._active_batch_workers.pop(bid, None)
            else:
                self._active_batch_workers[bid] = cur
            self._workers_drained_cond.notify_all()

    def is_batch_paused(self, batch_id_or_task) -> bool:
        if not self._paused_batches:
            return False
        bid = self._task_batch_id(batch_id_or_task)
        with self._paused_batches_lock:
            return bid in self._paused_batches

    def is_batch_cancelled(self, batch_id_or_task) -> bool:
        if self._cancel_event.is_set():
            return True
        if not self._cancelled_batches:
            return False
        bid = self._task_batch_id(batch_id_or_task)
        with self._paused_batches_lock:
            return bid in self._cancelled_batches

    def has_pending_rebuilds(self) -> bool:
        with self._mutation_lock:
            return bool(self._pending_rebuild_batches)

    def register_batch_context(self, ctx: BatchBuildContext) -> None:
        """Registers or merges a creator/album build snapshot for mid-download re-planning."""
        if not ctx or not ctx.batch_id:
            return
        opts_copy = FilterOptions.from_dict(ctx.applied_options.to_dict()) if ctx.applied_options else FilterOptions()
        with self._batch_contexts_lock:
            existing = self._batch_contexts.get(ctx.batch_id)
            if existing is None:
                ctx.applied_options = opts_copy
                self._batch_contexts[ctx.batch_id] = ctx
            else:
                if ctx.posts:
                    seen_keys = {(str(p.get("id", "")), bool(p.get("_is_dm"))) for p in existing.posts}
                    for p in ctx.posts:
                        pk = (str(p.get("id", "")), bool(p.get("_is_dm")))
                        if pk not in seen_keys:
                            seen_keys.add(pk)
                            existing.posts.append(p)
                if ctx.external_files and not existing.external_files:
                    existing.external_files = list(ctx.external_files)
                existing.fetched_dms = existing.fetched_dms or ctx.fetched_dms
                existing.fetched_comments = existing.fetched_comments or ctx.fetched_comments
                if ctx.fetched_fav_ids is not None:
                    existing.fetched_fav_ids = set(ctx.fetched_fav_ids)
                existing.scan_page_start = min(existing.scan_page_start, ctx.scan_page_start)
                existing.scan_page_end = max(existing.scan_page_end, ctx.scan_page_end)
                if ctx.scan_date_after and (not existing.scan_date_after or ctx.scan_date_after < existing.scan_date_after):
                    existing.scan_date_after = ctx.scan_date_after
                if ctx.scan_date_before and (not existing.scan_date_before or ctx.scan_date_before > existing.scan_date_before):
                    existing.scan_date_before = ctx.scan_date_before
                existing.applied_options = opts_copy
                if ctx.applied_download_dir:
                    existing.applied_download_dir = ctx.applied_download_dir
                existing.applied_site_in_folder_name = ctx.applied_site_in_folder_name
                if ctx.artist_dir is not None:
                    existing.artist_dir = ctx.artist_dir
                if ctx.base_dir:
                    existing.base_dir = ctx.base_dir
            self._prune_finished_batch_contexts_unlocked()

    def _prune_finished_batch_contexts_unlocked(self) -> None:
        """Drops bulky cached post payloads for finished batches so memory stays bounded."""
        active_bids: Set[str] = set()
        for t in self.tasks:
            if t.status in ("pending", "downloading", "retrying", "paused", "failed"):
                bid = self._task_batch_id(t)
                if bid:
                    active_bids.add(bid)
        active_bids.update(self._pending_rebuild_batches)
        for bid, ctx in list(self._batch_contexts.items()):
            if bid not in active_bids and (len(ctx.posts) > 500 or len(self._batch_contexts) > 32):
                ctx.posts = []
                ctx.external_files = []

    def unregister_batch_context(self, batch_id: str) -> None:
        if not batch_id:
            return
        with self._batch_contexts_lock:
            self._batch_contexts.pop(batch_id, None)

    def get_batch_context(self, batch_id: str) -> Optional[BatchBuildContext]:
        if not batch_id:
            return None
        with self._batch_contexts_lock:
            return self._batch_contexts.get(batch_id)

    def get_all_batch_contexts(self) -> List[BatchBuildContext]:
        with self._batch_contexts_lock:
            return list(self._batch_contexts.values())

    def active_unfinished_batch_ids(self) -> List[str]:
        """Returns distinct batch IDs that still have active, pending, or paused tasks."""
        seen: List[str] = []
        seen_set: Set[str] = set()
        for t in list(self.tasks):
            if t.status in ("pending", "downloading", "retrying", "paused"):
                bid = self._task_batch_id(t)
                if bid and bid not in seen_set:
                    seen_set.add(bid)
                    seen.append(bid)
        return seen

    def active_batch_ids_for(self, creator_id: str, service: str = "") -> List[str]:
        """Returns unfinished batch IDs matching a creator_id (and optional service)."""
        cid = str(creator_id or "").strip()
        svc = str(service or "").strip().lower()
        if not cid:
            return []
        matched: List[str] = []
        seen: Set[str] = set()
        for t in list(self.tasks):
            if t.status not in ("pending", "downloading", "retrying", "paused"):
                continue
            t_cid = str(getattr(t, "user_id", "") or "").strip()
            t_svc = str(getattr(t, "service", "") or "").strip().lower()
            if t_cid == cid and (not svc or t_svc == svc):
                bid = self._task_batch_id(t)
                if bid and bid not in seen:
                    seen.add(bid)
                    matched.append(bid)
        if not matched:
            with self._batch_contexts_lock:
                ctx_vals = list(self._batch_contexts.values())
            for ctx in ctx_vals:
                if str(ctx.user_id or "").strip() == cid and (not svc or str(ctx.service or "").lower() == svc):
                    bid = ctx.batch_id
                    if bid in self._pending_rebuild_batches and bid not in seen:
                        seen.add(bid)
                        matched.append(bid)
        return matched

    def has_active_tasks_for_creator(self, service: str, creator_id: str) -> bool:
        return bool(self.active_batch_ids_for(creator_id, service))

    def _clear_post_info_for_batches(self, batch_ids: Set[str], remaining_tasks: Optional[List[DownloadTask]] = None) -> None:
        if not batch_ids:
            return
        keep_tasks = remaining_tasks if remaining_tasks is not None else [
            t for t in self.tasks if self._task_batch_id(t) not in batch_ids
        ]
        live_keys = {
            (getattr(t, "post_info_path", ""), getattr(t, "post_id", ""))
            for t in keep_tasks
            if getattr(t, "post_info_path", "")
        }
        for key, owner_bid in list(self._post_info_owners.items()):
            if owner_bid in batch_ids and key not in live_keys:
                self._post_info_owners.pop(key, None)
                self._post_info_pending.pop(key, None)

    def set_batch_options(self, batch_id: str, options: FilterOptions) -> None:
        if batch_id and options:
            with self._batch_options_lock:
                self._batch_options[batch_id] = options

    def get_batch_options(self, batch_id: str) -> Optional[FilterOptions]:
        if not batch_id:
            return None
        with self._batch_options_lock:
            return self._batch_options.get(batch_id)

    def pause_batch(self, batch_id: str) -> int:
        """Pauses only tasks belonging to a specific batch without stopping other batches."""
        if not batch_id:
            return 0
        with self._paused_batches_lock:
            self._paused_batches.add(batch_id)
        paused = 0
        for t in self.tasks:
            bid = self._task_batch_id(t)
            if bid == batch_id and t.status in ("pending", "downloading", "retrying"):
                t.status = "paused"
                t.speed_bps = 0
                t.speed_str = "0 KB/s"
                t.eta_str = "--"
                paused += 1
                if self.on_task_status_changed:
                    self.on_task_status_changed(t)
        logger.info(f"Batch paused: {batch_id} ({paused} tasks paused)", category="downloader")
        return paused

    def resume_batch(self, batch_id: str, options: Optional[FilterOptions] = None, cookie_str: str = "") -> int:
        """Resumes a paused batch and wakes/starts the download loop if necessary."""
        if not batch_id:
            return 0
        with self._paused_batches_lock:
            self._paused_batches.discard(batch_id)
            self._cancelled_batches.discard(batch_id)
        self._dispatch_cursor = 0
        self._last_full_scan = 0.0

        resumed_tasks = []
        for t in self.tasks:
            bid = self._task_batch_id(t)
            if bid == batch_id and t.status == "paused":
                t.status = "pending"
                t.error_msg = ""
                resumed_tasks.append(t)
                if self.on_task_status_changed:
                    self.on_task_status_changed(t)

        logger.info(f"Batch resumed: {batch_id} ({len(resumed_tasks)} tasks restored to pending)", category="downloader")

        if not self._is_running and resumed_tasks:
            opts = options or self.current_options or FilterOptions()
            cookie = cookie_str or self._clean_cookie
            self.start_download_queue(self.tasks, opts, cookie)

        return len(resumed_tasks)

    def cancel_batch(self, batch_id: str, notify: bool = False) -> int:
        """Cancels all pending and downloading tasks belonging to a specific batch_id."""
        with self._paused_batches_lock:
            self._paused_batches.discard(batch_id)
            if batch_id:
                self._cancelled_batches.add(batch_id)
        self._close_batch_responses({batch_id})
        cancelled = 0
        for t in self.tasks:
            if self._task_batch_id(t) == batch_id and t.status in ("pending", "downloading", "retrying", "paused"):
                t.status = "cancelled"
                t.error_msg = "Download cancelled by user"
                t.progress_pct = 0
                t.speed_bps = 0
                t.speed_str = "0 KB/s"
                t.eta_str = "--"
                cancelled += 1
                if notify and self.on_task_status_changed:
                    self.on_task_status_changed(t)
        self.unregister_batch_context(batch_id)
        return cancelled

    def retry_batch_failed(self, batch_id: str, options: Optional[FilterOptions] = None, cookie_str: str = "") -> int:
        """Resets failed/cancelled tasks in a specific batch to pending and resumes download."""
        with self._paused_batches_lock:
            self._paused_batches.discard(batch_id)
            self._cancelled_batches.discard(batch_id)
        failed = []
        for t in self.tasks:
            t_bid = self._task_batch_id(t)
            if t_bid == batch_id:
                if is_task_non_retryable(t):
                    continue
                if t.status in ("failed", "cancelled") or (not self._is_running and t.status in ("pending", "paused")):
                    failed.append(t)

        for t in failed:
            t.status = "pending"
            t.error_msg = ""
            t.downloaded_bytes = 0
            t.progress_pct = 0
            t.retry_count = getattr(t, "retry_count", 0) + 1
            if self.on_task_status_changed:
                self.on_task_status_changed(t)
        if failed and not self._is_running and options:
            self.start_download_queue(self.tasks, options, cookie_str)
        return len(failed)

    def remove_batch(self, batch_id: str) -> int:
        """Removes non-active tasks belonging to a batch from the queue."""
        with self._paused_batches_lock:
            self._paused_batches.discard(batch_id)
            self._cancelled_batches.discard(batch_id)
        with self._mutation_lock:
            self._pending_rebuild_batches.discard(batch_id)
        initial_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if self._task_batch_id(t) != batch_id or t.status == "downloading"]
        if not any(self._task_batch_id(t) == batch_id for t in self.tasks):
            self.unregister_batch_context(batch_id)
            self._clear_post_info_for_batches({batch_id}, self.tasks)
        return initial_count - len(self.tasks)

    def quiesce_batches(self, batch_ids: Set[str], mode: str = "pause", timeout: float = 15.0) -> Tuple[bool, str]:
        """Safely pauses or cancels `batch_ids` and waits until zero active workers remain for them.

        Must never be called from the Qt main thread.
        """
        target_bids = {b for b in (batch_ids or set()) if b}
        if not target_bids:
            return True, ""

        try:
            from PySide6.QtCore import QCoreApplication, QThread
            app = QCoreApplication.instance()
            if app is not None and QThread.currentThread() == app.thread():
                raise RuntimeError("quiesce_batches must not be called on the Qt main thread")
        except ImportError:
            pass

        with self._mutation_lock:
            self._pending_rebuild_batches.update(target_bids)
            with self._paused_batches_lock:
                if mode == "cancel":
                    self._cancelled_batches.update(target_bids)
                    self._paused_batches.difference_update(target_bids)
                else:
                    self._paused_batches.update(target_bids)

            changed_tasks: List[DownloadTask] = []
            for t in self.tasks:
                if self._task_batch_id(t) not in target_bids:
                    continue
                if mode == "cancel":
                    if t.status in ("pending", "paused", "retrying"):
                        t.status = "cancelled"
                        t.error_msg = "Download cancelled by user"
                        t.speed_bps = 0
                        t.speed_str = "0 KB/s"
                        t.eta_str = "--"
                        changed_tasks.append(t)
                else:
                    if t.status in ("pending", "retrying"):
                        t.status = "paused"
                        t.speed_bps = 0
                        t.speed_str = "0 KB/s"
                        t.eta_str = "--"
                        changed_tasks.append(t)

        if changed_tasks:
            self._notify_many(changed_tasks)

        if mode == "cancel":
            self._close_batch_responses(target_bids)

        def _all_drained() -> bool:
            return all(self._active_batch_workers.get(b, 0) == 0 for b in target_bids)

        deadline = time.monotonic() + max(0.2, float(timeout))
        initial_wait = min(1.5, max(0.1, deadline - time.monotonic()))
        with self._workers_drained_cond:
            drained = self._workers_drained_cond.wait_for(_all_drained, timeout=initial_wait)

        if not drained:
            # Close active sockets even on pause mode after 1.5s so stalled transfers don't hang rebuild
            self._close_batch_responses(target_bids)
            remaining = max(0.1, deadline - time.monotonic())
            with self._workers_drained_cond:
                drained = self._workers_drained_cond.wait_for(_all_drained, timeout=remaining)

        if not drained:
            with self._mutation_lock:
                self._pending_rebuild_batches.difference_update(target_bids)
            return False, "Active file transfer is still winding down; please try again in a moment."

        # Workers have fully exited for target_bids; normalize any straggling 'downloading' state
        stragglers: List[DownloadTask] = []
        with self._mutation_lock:
            for t in self.tasks:
                if self._task_batch_id(t) in target_bids and t.status == "downloading":
                    t.status = "cancelled" if mode == "cancel" else "paused"
                    t.speed_bps = 0
                    t.speed_str = "0 KB/s"
                    t.eta_str = "--"
                    if mode == "cancel" and not t.error_msg:
                        t.error_msg = "Download cancelled by user"
                    stragglers.append(t)
        if stragglers:
            self._notify_many(stragglers)

        return True, ""

    def update_runtime_options(
        self,
        batch_ids: Set[str],
        new_options: FilterOptions,
        proxy_changed: bool = False,
        update_global_options: bool = True,
    ) -> None:
        """Applies Tier 2 runtime/transport settings in-place without pausing or rebuilding tasks."""
        if not new_options:
            return
        if update_global_options:
            self.current_options = FilterOptions.from_dict(new_options.to_dict())
            self.max_workers = max(1, int(getattr(new_options, "threads", self.max_workers) or self.max_workers))
        for bid in batch_ids:
            opts_copy = FilterOptions.from_dict(new_options.to_dict())
            self.set_batch_options(bid, opts_copy)
            with self._batch_contexts_lock:
                ctx = self._batch_contexts.get(bid)
                if ctx is not None:
                    ctx.applied_options = FilterOptions.from_dict(new_options.to_dict())
            for t in list(self.tasks):
                if self._task_batch_id(t) == bid and t.status in ("pending", "downloading", "retrying", "paused"):
                    t.options = opts_copy
        if proxy_changed:
            self.bump_worker_session_epoch(getattr(new_options, "proxy_url", ""))

    def build_tasks_from_external_files(
        self,
        files: List[Dict[str, Any]],
        provider: str,
        creator_name: str,
        base_dir: str,
        options: FilterOptions,
        batch_id: str,
        post_id: str = "",
        artist_dir: Optional[str] = None,
        user_id: str = "",
    ) -> List[DownloadTask]:
        """Builds filtered DownloadTask objects for Bunkr/Erome/nHentai external album batches."""
        from core.text_utils import sanitize_filesystem_name
        from core.path_utils import unique_name_in_batch

        prefix_map = {"bunkr": "Bunkr", "erome": "Erome", "nhentai": "nHentai"}
        label_prefix = prefix_map.get((provider or "").lower(), (provider or "Album").title())
        fallback_name = f"Gallery {post_id}" if (provider or "").lower() == "nhentai" else f"{label_prefix} Album"
        folder_name = sanitize_filesystem_name(creator_name or fallback_name, fallback=fallback_name)
        folder = artist_dir or os.path.join(base_dir, f"{label_prefix} - {folder_name}")
        taken: Set[str] = set()
        tasks: List[DownloadTask] = []
        force_redownload = bool(getattr(options, "force_redownload", False))
        svc = (provider or "").lower()
        pid = post_id or svc

        for f in files:
            url = f.get("url", "")
            fname = f.get("filename", "") or "file"
            fsize = int(f.get("size", 0) or 0)
            if not url:
                continue
            keep, _ = FilterEngine.should_keep_file(fname, options, file_size=fsize)
            if not keep:
                continue
            if not force_redownload and self.archive_manager and self.archive_manager.is_enabled:
                if self.archive_manager.is_archived(service=svc, post_id=pid, file_id=url):
                    continue
            target_path = fit_path_for_windows(unique_name_in_batch(folder, fname, taken))
            t = DownloadTask(
                url=url,
                target_path=target_path,
                post_title=creator_name or fallback_name,
                creator_name=creator_name or fallback_name,
                service=svc,
                post_id=pid,
                file_id=url,
                file_size=fsize,
                batch_id=batch_id,
                user_id=user_id,
            )
            t.options = options
            tasks.append(t)
        return tasks

    def rebuild_batches_in_place(
        self,
        batch_plans: Dict[str, Dict[str, Any]],
        new_options: FilterOptions,
        cookie_str: str = "",
        force_redownload: bool = False,
        clear_previous_completed: bool = False,
        update_global_options: bool = True,
    ) -> Dict[str, Any]:
        """Rebuilds queued/paused/failed tasks for `batch_plans` using new settings cleanly.

        Callers must invoke `quiesce_batches(...)` beforehand so zero active workers remain.
        """
        batch_ids = {b for b in (batch_plans or {}).keys() if b}
        if not batch_ids:
            return {"ok": True, "rebuilt_batch_ids": [], "replacement_tasks": []}

        with self._workers_drained_cond:
            busy = [b for b in batch_ids if self._active_batch_workers.get(b, 0) > 0]
        if busy:
            with self._mutation_lock:
                self._pending_rebuild_batches.difference_update(batch_ids)
            return {"ok": False, "error": f"Workers still active for batches: {', '.join(busy)}"}

        build_session = self._session_id
        migrated_parts = 0
        cleaned_parts = 0
        kept_completed_count = 0
        new_pending_count = 0

        try:
            with self._mutation_lock:
                self._pending_rebuild_batches.update(batch_ids)
                existing_tasks = list(self.tasks)

            by_batch_existing: Dict[str, List[DownloadTask]] = defaultdict(list)
            other_tasks: List[DownloadTask] = []
            for t in existing_tasks:
                bid = self._task_batch_id(t)
                if bid in batch_ids:
                    by_batch_existing[bid].append(t)
                else:
                    other_tasks.append(t)

            self._clear_post_info_for_batches(batch_ids, other_tasks)

            rebuilt_map: Dict[str, List[DownloadTask]] = {}
            all_new_candidates: List[DownloadTask] = []

            for bid, plan in batch_plans.items():
                plan_opts = plan.get("options") or new_options
                fresh_options = FilterOptions.from_dict(plan_opts.to_dict())
                fresh_options.force_redownload = bool(force_redownload)

                existing_for_bid = by_batch_existing.get(bid, [])
                completed_tasks = (
                    []
                    if clear_previous_completed
                    else [t for t in existing_for_bid if t.status == "completed"]
                )
                old_interrupted = (
                    existing_for_bid
                    if clear_previous_completed
                    else [t for t in existing_for_bid if t.status in ("pending", "paused", "retrying", "failed")]
                )

                old_by_url: Dict[str, List[Tuple[str, bool, str]]] = defaultdict(list)
                ctx = self.get_batch_context(bid)
                old_thumb_flag = bool(
                    getattr(ctx.applied_options, "download_thumbnails_only", False)
                    if ctx and ctx.applied_options
                    else False
                )
                for ot in old_interrupted:
                    ot_thumb = (
                        bool(getattr(ot.options, "download_thumbnails_only", False))
                        if getattr(ot, "options", None) is not None
                        else old_thumb_flag
                    )
                    old_by_url[ot.url].append((ot.target_path, ot_thumb, ot.target_path + PART_SUFFIX))

                if "tasks" in plan and plan["tasks"] is not None:
                    candidates = list(plan["tasks"])
                elif plan.get("external_files"):
                    candidates = self.build_tasks_from_external_files(
                        files=plan["external_files"],
                        provider=plan.get("provider") or plan.get("service", ""),
                        creator_name=plan.get("creator_name", ""),
                        base_dir=plan.get("base_dir", ""),
                        options=fresh_options,
                        batch_id=bid,
                        post_id=plan.get("post_id", ""),
                        artist_dir=plan.get("artist_dir"),
                        user_id=plan.get("user_id", ""),
                    )
                else:
                    candidates = self.build_tasks_from_posts(
                        posts=plan.get("posts") or [],
                        creator_name=plan.get("creator_name", "creator"),
                        service=plan.get("service", ""),
                        domain=plan.get("domain", ""),
                        base_dir=plan.get("base_dir", ""),
                        options=fresh_options,
                        batch_id=bid,
                        artist_dir=plan.get("artist_dir"),
                        user_id=plan.get("user_id", ""),
                        progress_callback=plan.get("progress_callback"),
                    )

                if self.last_build_cancelled or (self._cancel_event.is_set() and build_session != self._session_id):
                    return {"ok": False, "cancelled": True, "error": "Rebuild cancelled"}

                thumb_changed = old_thumb_flag != bool(getattr(fresh_options, "download_thumbnails_only", False))
                filtered_candidates: List[DownloadTask] = []
                if not clear_previous_completed and completed_tasks and not thumb_changed:
                    done_identities = {
                        (str(t.service).lower(), str(t.post_id), str(t.file_id))
                        for t in completed_tasks
                        if getattr(t, "file_id", "")
                    }
                    done_urls = {t.url for t in completed_tasks if getattr(t, "url", "")}
                    for c in candidates:
                        c_id = (str(c.service).lower(), str(c.post_id), str(c.file_id))
                        if (c.file_id and c_id in done_identities) or (c.url and c.url in done_urls):
                            continue
                        filtered_candidates.append(c)
                else:
                    filtered_candidates = list(candidates)

                # Reserve collision-free paths against other batches, kept completed tasks, and earlier rebuilt batches
                self._keep_paths_apart(filtered_candidates, other_tasks + completed_tasks + all_new_candidates)

                new_thumb_flag = bool(getattr(fresh_options, "download_thumbnails_only", False))
                migrated_part_paths: Set[str] = set()
                for c in filtered_candidates:
                    c.batch_id = bid
                    c.options = fresh_options
                    c.target_path = fit_path_for_windows(c.target_path)
                    if not clear_previous_completed and c.url in old_by_url and old_by_url[c.url]:
                        old_target, ot_thumb, old_part = old_by_url[c.url].pop(0)
                        if ot_thumb == new_thumb_flag and os.path.isfile(old_part):
                            try:
                                if os.path.getsize(old_part) > 0:
                                    dst_part = c.target_path + PART_SUFFIX
                                    if os.path.abspath(old_part) == os.path.abspath(dst_part) or atomic_move_part(old_part, dst_part):
                                        migrated_part_paths.add(os.path.abspath(old_part))
                                        migrated_parts += 1
                                        try:
                                            c.downloaded_bytes = os.path.getsize(dst_part)
                                        except OSError:
                                            pass
                            except OSError:
                                pass

                if not clear_previous_completed:
                    for ot in old_interrupted:
                        old_part = ot.target_path + PART_SUFFIX
                        if os.path.abspath(old_part) not in migrated_part_paths and os.path.isfile(old_part):
                            _remove_quietly(old_part)
                            cleaned_parts += 1

                kept_completed_count += len(completed_tasks)
                new_pending_count += len(filtered_candidates)
                all_new_candidates.extend(filtered_candidates)
                rebuilt_map[bid] = completed_tasks + filtered_candidates
                self.set_batch_options(bid, fresh_options)

            with self._mutation_lock:
                if build_session != self._session_id:
                    return {"ok": False, "cancelled": True, "error": "Session superseded"}

                new_task_list: List[DownloadTask] = []
                emitted_batches: Set[str] = set()
                for t in existing_tasks:
                    bid = self._task_batch_id(t)
                    if bid in batch_ids:
                        if bid not in emitted_batches:
                            emitted_batches.add(bid)
                            new_task_list.extend(rebuilt_map.get(bid, []))
                    else:
                        new_task_list.append(t)
                for bid in batch_ids:
                    if bid not in emitted_batches:
                        emitted_batches.add(bid)
                        new_task_list.extend(rebuilt_map.get(bid, []))

                self.tasks = new_task_list
                self._counter_sig = None
                self._dispatch_cursor = 0
                self._last_full_scan = 0.0
                if update_global_options:
                    self.current_options = FilterOptions.from_dict(new_options.to_dict())

                with self._lock:
                    self.total_bytes = sum(t.file_size for t in self.tasks if getattr(t, "file_size", 0) > 0)

                with self._paused_batches_lock:
                    self._paused_batches.difference_update(batch_ids)
                    self._cancelled_batches.difference_update(batch_ids)

                eff_opts = FilterOptions.from_dict(new_options.to_dict())
                self._save_recovery_checkpoint(eff_opts, async_write=False, force_full=True)

            replacement_flat: List[DownloadTask] = []
            for bid in batch_ids:
                replacement_flat.extend(rebuilt_map.get(bid, []))

            if replacement_flat:
                self._notify_many(replacement_flat)

            has_pending = any(t.status == "pending" for t in self.tasks)
            if has_pending and not self._is_running:
                self.start_download_queue(
                    self.tasks,
                    FilterOptions.from_dict(new_options.to_dict()),
                    cookie_str or self._clean_cookie,
                )

            return {
                "ok": True,
                "rebuilt_batch_ids": list(batch_ids),
                "replacement_tasks": replacement_flat,
                "migrated_parts": migrated_parts,
                "cleaned_parts": cleaned_parts,
                "kept_completed": kept_completed_count,
                "new_pending": new_pending_count,
            }
        finally:
            with self._mutation_lock:
                self._pending_rebuild_batches.difference_update(batch_ids)
