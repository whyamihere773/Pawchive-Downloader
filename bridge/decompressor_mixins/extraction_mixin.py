"""
DecompressorBridge Parallel Extraction & Post-Extract Compression Mixin
Decomposed from bridge/decompressor_bridge.py to keep modules cohesive and under 1,000 lines.
"""

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict

from PySide6.QtCore import Slot

from bridge.decompressor_mixins.compression_mixin import _format_bytes
from bridge.decompressor_mixins.signals_mixin import DecompressorSignalsMixin
from core.archive_password_manager import archive_password_manager as _default_apm
from core.logger import logger
from services.bulk_decompressor import ArchiveItem
from services.media_compressor import CompressResult, compress_folder


def _apm():
    """Resolve archive_password_manager via bridge.decompressor_bridge so test patches work."""
    mod = sys.modules.get("bridge.decompressor_bridge")
    if mod is not None and hasattr(mod, "archive_password_manager"):
        return mod.archive_password_manager
    return _default_apm


class DecompressorExtractionMixin(DecompressorSignalsMixin):
    """Runs parallel bulk archive decompression, auto-password probing, and optional compression."""

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
        self._prompt_serial_sem = threading.BoundedSemaphore(1)

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
        compress = self._compress_settings()
        compressed_total = CompressResult()
        compressed_lock = threading.Lock()

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
            last_progress_emit = [0.0]

            def _update_progress(item: ArchiveItem, pct: float):
                item.progress = pct
                now = time.time()
                if pct < 100.0 and (now - last_progress_emit[0] < 0.2):
                    return
                last_progress_emit[0] = now

                self.itemUpdated.emit(item.item_id, item.status, pct, item.error_message)

                # Compute overall progress
                with self._items_lock:
                    done_b = sum(
                        (i.size if i.status in ("done", "compressing")
                         else (i.size * (i.progress / 100.0) if i.status == "extracting" else 0))
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
                    return None                     # stopped, not failed

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
                    candidates = _apm().find_candidate_passwords(item.path, item.creator)
                    matched_pw = None
                    for cand in candidates:
                        if self._extract_cancel_event.is_set():
                            break
                        if self.engine.test_password(item.path, cand, cancel_event=self._extract_cancel_event):
                            matched_pw = cand
                            logger.success(f"✓ Found matching password for [{item.creator}] {item.filename} (from the Password Bank)", category="decompressor")
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
                            _apm().record_archive_password(item.path, matched_pw, creator=item.creator)
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
                                            _apm().record_archive_password(item.path, supplied_pw, creator=item.creator)
                                            self.passwordBankChanged.emit()

                if ok:
                    logger.success(f"✓ Extracted [{item.creator}] {item.filename} -> {item.target_dir}", category="decompressor")
                    if compress and item.target_dir and os.path.isdir(item.target_dir) \
                            and not self._extract_cancel_event.is_set():
                        item.status = "compressing"
                        item.progress = 0.0
                        self.itemUpdated.emit(item.item_id, item.status, 0.0, "")
                        r = compress_folder(item.target_dir, compress, cancel=self._extract_cancel_event,
                                            on_progress=lambda pct: _update_progress(item, pct),
                                            procs=self._compress_procs)
                        with compressed_lock:
                            compressed_total.merge(r)
                            if r.compressed:
                                self._pending_source = "decompressor"
                        if r.compressed or r.failed:
                            logger.info(f"🗜 [{item.creator}] {item.filename}: {len(r.compressed)} file(s) compressed, "
                                        f"{_format_bytes(r.bytes_before)} → {_format_bytes(r.bytes_after)}"
                                        + (f", {len(r.failed)} couldn't be" if r.failed else ""),
                                        category="decompressor",
                                        details="\n".join(r.failed[:50]) if r.failed else "")
                    item.status = "done"
                    item.progress = 100.0
                    item.error_message = ""
                    self.itemUpdated.emit(item.item_id, item.status, 100.0, "")
                    return True
                else:
                    if self._extract_cancel_event.is_set() and "Cancelled" in (err or ""):
                        item.status = "skipped"
                        item.error_message = "Cancelled"
                        self.itemUpdated.emit(item.item_id, item.status, 0.0, item.error_message)
                        return None
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
                        elif res is not None:
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
            if compressed_total.compressed:
                # The originals stay until the user decides (asked once, for the whole run)
                self._pending_originals = list(compressed_total.compressed)
                logger.success(
                    f"🗜 Compressed {len(compressed_total.compressed)} file(s): "
                    f"{_format_bytes(compressed_total.bytes_before)} → {_format_bytes(compressed_total.bytes_after)}.",
                    category="decompressor")
                self.compressionReviewRequested.emit(len(compressed_total.compressed), compressed_total.bytes_before,
                                                     compressed_total.bytes_after, len(compressed_total.failed))

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def cancelDecompression(self):
        """Cancel ongoing extraction jobs immediately."""
        logger.warning("Bulk decompression cancelled by user.", category="decompressor")
        self._extract_cancel_event.set()
        self.engine.cancel_all()
        for proc in list(self._compress_procs):        # ffmpeg compressing a video
            try:
                proc.kill()
            except Exception:
                pass
        # Wake any worker that is blocked waiting to show a password prompt
        with self._prompt_lock:
            for it_id, ev in list(self._prompt_events.items()):
                self._prompt_responses[it_id] = {"action": "skip"}
                ev.set()
