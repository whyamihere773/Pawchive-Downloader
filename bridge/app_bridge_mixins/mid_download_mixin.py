"""Auto-extracted AppBridge domain mixin (see bridge/app_bridge.py)."""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import Property, QCoreApplication, QObject, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QApplication, QFileDialog

from bridge.app_bridge_mixins.signals_mixin import AppBridgeSignalsMixin
from bridge.archive_creators_model import ArchiveCreatorsModel, RecordListModel
from bridge.decompressor_bridge import DecompressorBridge
from bridge.known_model import KnownModel
from bridge.log_model import LogModel
from bridge.queue_model import QueueModel
from bridge.telegram_bridge import TelegramBridge
from bridge.thumbnail_provider import VIDEO_EXTENSIONS
from bridge.watchlist_model import WatchlistModel
from core import folder_naming
from core.api_client import KemonoApiClient
from core.archive_manager import ArchiveManager
from core.archive_rebuild_journal import ArchiveRebuildJournal
from core.archive_rebuilder import ArchiveRebuilder, ArchiveRebuildOptions
from core.bandwidth_limiter import bandwidth_limiter
from core.downloader import (
    BatchBuildContext,
    DownloadTask,
    KemonoDownloader,
    is_permanent_failure,
    is_task_non_retryable,
)
from core.file_order import normalize_file_order, order_files
from core.filter_engine import (
    FILTER_PROFILES,
    REMOVE_WORDS_PROFILES,
    FilenameStyles,
    FilterEngine,
    FilterOptions,
    classify_settings_change,
)
from core.folder_naming import is_creator_folder, pick_creator_folder
from core.hardware_detector import HardwareDetector
from core.known_manager import KnownManager
from core.logger import logger
from core.parser import KemonoURLParser, URLParseResult, canonical_site_url, normalize_archive_url
from core.path_utils import (
    clean_subprocess_env,
    post_info_files,
    post_info_for_file,
    subprocess_env_kwargs,
    unique_name_in_batch,
)
from core.post_metadata_index import parse_post_info_content
from core.session_manager import SessionManager
from core.text_utils import clean_text, safe_file_name, sanitize_filesystem_name
from core.watchlist_manager import WatchlistManager
from services.batch_loader import BatchLoader
from services.link_extractor import LinkExtractor
from services.model_manager import MODEL_CATALOG, ModelManager
from services.telegram_service import TelegramService
from services.text_exporter import TextExporter

_FOLDER_PREVIEW_IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
    ".avif", ".apng", ".tif", ".tiff", ".jfif",
}


def _app_bridge_mod():
    import bridge.app_bridge as _ab
    return _ab



class MidDownloadMixin(AppBridgeSignalsMixin):
    @Slot()
    def _on_download_setting_mutated(self):
        if self.downloader.active_unfinished_batch_ids():
            self._settings_dirty_timer.start()

    def _current_settings_signature(self) -> str:
        payload = {
            "options": self._get_filter_options().to_dict(),
            "download_dir": os.path.normpath(str(self._download_dir or "")),
            "site_in_folder_name": bool(folder_naming.include_service),
        }
        return json.dumps(payload, sort_keys=True, default=str)

    def _resolve_ctx_target_settings(self, ctx: BatchBuildContext, scope: str = "global"):
        """Returns (eff_opts, eff_base_dir, eff_artist_dir, eff_site_in_name, wl_entry)."""
        site_in_name = bool(folder_naming.include_service)
        wl = None
        if ctx.user_id and ctx.service and not (ctx.parsed and ctx.parsed.is_external_provider):
            wl = self._watchlist_manager._find(ctx.user_id, ctx.service)

        if ctx.from_watchlist and wl is not None:
            eff_opts = FilterOptions.from_dict(self._get_effective_watchlist_options(wl).to_dict())
            if getattr(wl, "custom_folder", False) and wl.download_dir:
                eff_artist_dir = os.path.normpath(wl.download_dir)
                eff_base_dir = os.path.dirname(os.path.abspath(eff_artist_dir))
            else:
                clean_c = FilterEngine.clean_filesystem_text(
                    wl.creator_name or wl.user_id, max_len=80, fallback="creator"
                )
                eff_base_dir = self._download_dir or ctx.base_dir
                eff_artist_dir = pick_creator_folder(eff_base_dir, clean_c, wl.service)
            return eff_opts, eff_base_dir, eff_artist_dir, site_in_name, wl

        eff_opts = FilterOptions.from_dict(self._get_filter_options().to_dict())
        eff_base_dir = self._download_dir or ctx.base_dir
        if ctx.parsed and ctx.parsed.is_external_provider:
            prov = (ctx.provider or ctx.service or "").lower()
            prefix_map = {"bunkr": "Bunkr", "erome": "Erome", "nhentai": "nHentai"}
            label = prefix_map.get(prov, prov.title())
            fallback = f"Gallery {ctx.post_id}" if prov == "nhentai" else f"{label} Album"
            folder_name = sanitize_filesystem_name(ctx.creator_name or fallback, fallback=fallback)
            eff_artist_dir = os.path.join(eff_base_dir, f"{label} - {folder_name}")
        else:
            eff_artist_dir = None
        return eff_opts, eff_base_dir, eff_artist_dir, site_in_name, None

    def _set_pending_settings_state(self, has_changes: bool, summary: str) -> None:
        if self._has_pending_download_settings_changes != has_changes:
            self._has_pending_download_settings_changes = has_changes
            self.hasPendingDownloadSettingsChangesChanged.emit()
        if self._pending_settings_diff_summary != summary:
            self._pending_settings_diff_summary = summary
            self.pendingSettingsDiffSummaryChanged.emit()

    def _classify_ctx_diff(
        self,
        ctx: BatchBuildContext,
        eff_opts: FilterOptions,
        eff_base_dir: str,
        eff_artist_dir: Optional[str],
        site_flag: bool,
    ) -> dict:
        old_dir = ctx.artist_dir if (ctx.from_watchlist and ctx.artist_dir) else ctx.applied_download_dir
        new_dir = eff_artist_dir if (ctx.from_watchlist and eff_artist_dir) else eff_base_dir
        return classify_settings_change(
            ctx.applied_options,
            eff_opts,
            old_dir,
            new_dir,
            ctx.applied_site_in_folder_name,
            site_flag,
            has_comments_fetched=bool(ctx.fetched_comments),
            fetched_dms=bool(ctx.fetched_dms),
            has_favs_fetched=(ctx.fetched_fav_ids is not None),
            scan_bounds={
                "page_start": ctx.scan_page_start,
                "page_end": ctx.scan_page_end,
                "date_after": ctx.scan_date_after,
                "date_before": ctx.scan_date_before,
            },
        )

    @Slot()
    def _evaluate_pending_download_settings(self) -> None:
        unfinished_bids = set(self.downloader.active_unfinished_batch_ids())
        if not unfinished_bids or not (self._is_downloading or self.downloader.is_running):
            self._settings_dismissed_baseline = None
            self._set_pending_settings_state(False, "")
            return

        contexts = [c for c in self.downloader.get_all_batch_contexts() if c.batch_id in unfinished_bids]
        if not contexts:
            self._set_pending_settings_state(False, "")
            return

        cur_sig = self._current_settings_signature()
        if self._settings_dismissed_baseline is not None:
            if self._settings_dismissed_baseline == cur_sig:
                self._set_pending_settings_state(False, "")
                return
            self._settings_dismissed_baseline = None

        labels: List[str] = []
        seen_labels: Set[str] = set()
        for ctx in contexts:
            eff_opts, eff_base_dir, eff_artist_dir, site_flag, _wl = self._resolve_ctx_target_settings(ctx)
            diff = self._classify_ctx_diff(ctx, eff_opts, eff_base_dir, eff_artist_dir, site_flag)
            if diff.get("tier", 0) > 0:
                for part in str(diff.get("summary") or "").split(","):
                    clean_p = part.strip()
                    if clean_p and clean_p not in seen_labels:
                        seen_labels.add(clean_p)
                        labels.append(clean_p)

        if labels:
            self._set_pending_settings_state(True, ", ".join(labels[:6]) + ("..." if len(labels) > 6 else ""))
        else:
            self._set_pending_settings_state(False, "")

    @Slot()
    def dismissPendingDownloadSettingsBanner(self):
        """Hides the pending settings banner until a subsequent settings edit occurs."""
        self._settings_dismissed_baseline = self._current_settings_signature()
        self._set_pending_settings_state(False, "")

    def _build_mid_download_prompt_payload(
        self, scope: str = "global", target_user_id: str = "", target_service: str = ""
    ) -> dict:
        if scope == "creator" and target_user_id:
            bids = set(self.downloader.active_batch_ids_for(target_user_id, target_service))
        else:
            bids = set(self.downloader.active_unfinished_batch_ids())
        contexts = [c for c in self.downloader.get_all_batch_contexts() if c.batch_id in bids]
        names = []
        seen_names: Set[str] = set()
        labels: List[str] = []
        seen_labels: Set[str] = set()
        requires_scan = False
        for c in contexts:
            nm = c.creator_name or c.user_id or "Download"
            if nm not in seen_names:
                seen_names.add(nm)
                names.append(nm)
            eff_opts, eff_base_dir, eff_artist_dir, site_flag, _wl = self._resolve_ctx_target_settings(c, scope=scope)
            diff = self._classify_ctx_diff(c, eff_opts, eff_base_dir, eff_artist_dir, site_flag)
            if diff.get("tier", 0) >= 4:
                requires_scan = True
            for part in str(diff.get("summary") or "").split(","):
                cp = part.strip()
                if cp and cp not in seen_labels:
                    seen_labels.add(cp)
                    labels.append(cp)

        scope_label = (
            names[0]
            if (scope == "creator" and names)
            else f"All Active Queue ({max(1, len(bids))} batch{'es' if len(bids) != 1 else ''})"
        )
        return {
            "scope": scope,
            "targetUserId": str(target_user_id or ""),
            "targetService": str(target_service or ""),
            "scopeLabel": scope_label,
            "summary": ", ".join(labels) if labels else (self._pending_settings_diff_summary or "Download settings"),
            "requiresScan": requires_scan,
        }

    @Slot()
    @Slot(str)
    @Slot(str, str, str)
    def requestMidDownloadSettingsPrompt(self, scope: str = "global", targetUserId: str = "", targetService: str = ""):
        payload = self._build_mid_download_prompt_payload(scope, targetUserId, targetService)
        self.midDownloadSettingsPromptRequested.emit(scope, payload)

    def _set_applying_mid_download_ui(self, active: bool, status_text: str = "") -> None:
        def _apply():
            if self._is_applying_mid_download != active:
                self._is_applying_mid_download = active
                self.isApplyingMidDownloadSettingsChanged.emit()
            if self._mid_download_apply_status_text != status_text:
                self._mid_download_apply_status_text = status_text
                self.midDownloadApplyStatusTextChanged.emit()
        if QThread.currentThread() is self.thread():
            _apply()
        else:
            self._callOnGui.emit(_apply)

    @Slot()
    def cancelMidDownloadApply(self):
        self._apply_cancel_event.set()
        self._settings_apply_gen += 1
        self._set_applying_mid_download_ui(self._is_applying_mid_download, "Cancelling settings update...")

    def _is_safe_delete_path(self, path: str) -> bool:
        if not path:
            return False
        abs_p = os.path.abspath(os.path.normpath(path))
        if os.path.dirname(abs_p) == abs_p:
            return False
        protected = self._protected_root_dirs()
        root_keys = {self._norm_path_key(r).rstrip("\\/") for r in protected if r}
        p_key = self._norm_path_key(abs_p).rstrip("\\/")
        if not p_key or p_key in root_keys:
            return False
        if any(self._is_ancestor_dir(abs_p, r) for r in protected):
            return False
        return True

    def _wipe_ad_hoc_batch_before_redownload(
        self, ctx: BatchBuildContext, batch_tasks: List[DownloadTask], delete_creator_archive: bool = False
    ) -> None:
        """Removes only files and archive entries belonging to an ad-hoc batch cleanly."""
        target_files: List[str] = []
        parent_dirs: Set[str] = set()
        for t in batch_tasks:
            tp = getattr(t, "target_path", "")
            if tp:
                target_files.append(tp)
                target_files.append(tp + ".part")
                parent_dirs.add(os.path.dirname(os.path.abspath(tp)))

        for fp in target_files:
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
                    self._invalidate_folder_stats(fp)
            except OSError as e:
                logger.warning(f"Could not delete '{fp}' during re-download wipe: {e}", category="downloader")

        # Prune empty subfolders created strictly by this batch without touching protected roots
        for d in sorted(parent_dirs, key=len, reverse=True):
            curr = d
            while curr and self._is_safe_delete_path(curr):
                try:
                    if os.path.isdir(curr) and not os.listdir(curr):
                        os.rmdir(curr)
                        curr = os.path.dirname(curr)
                    else:
                        break
                except OSError:
                    break

        if ctx.artist_dir and self._is_safe_delete_path(ctx.artist_dir) and os.path.isdir(ctx.artist_dir):
            base_k = self._norm_path_key(ctx.artist_dir)
            if delete_creator_archive or (ctx.parsed and ctx.parsed.is_external_provider):
                try:
                    shutil.rmtree(ctx.artist_dir, ignore_errors=True)
                    self._invalidate_folder_stats(os.path.join(ctx.artist_dir, "x"))
                except Exception:
                    pass

        if self._enable_download_archive or os.path.exists(self.archive_manager.db_path):
            if delete_creator_archive and ctx.user_id and ctx.service:
                self.archive_manager.delete_by_creator(ctx.user_id, ctx.service)
                if ctx.creator_name and ctx.creator_name != ctx.user_id:
                    self.archive_manager.delete_by_creator(ctx.creator_name, ctx.service)
            clean_files = [os.path.normpath(p) for p in target_files if not p.endswith(".part")]
            if clean_files:
                self.archive_manager.delete_under_paths(clean_files)

    def _fetch_tier4_delta(
        self,
        ctx: BatchBuildContext,
        eff_opts: FilterOptions,
        diff: Dict[str, Any],
        my_gen: int,
    ) -> Tuple[bool, List[Dict[str, Any]], Optional[Set[str]], bool, bool, int, int, str, str]:
        """Fetches only missing API scopes (DMs, comments, favorites, expanded range) before pause."""
        posts_copy = list(ctx.posts or [])
        fav_ids = set(ctx.fetched_fav_ids) if ctx.fetched_fav_ids is not None else None
        fetched_dms = bool(ctx.fetched_dms)
        fetched_comments = bool(ctx.fetched_comments)
        p_start = ctx.scan_page_start
        p_end = ctx.scan_page_end
        d_after = ctx.scan_date_after
        d_before = ctx.scan_date_before

        parsed = ctx.parsed
        if not parsed or (getattr(parsed, "is_external_provider", False)) or getattr(parsed, "is_single_post", False):
            return True, posts_copy, fav_ids, fetched_dms, fetched_comments, p_start, p_end, d_after, d_before

        def _cancelled() -> bool:
            return self._apply_cancel_event.is_set() or (my_gen != self._settings_apply_gen)

        want_window_expand = bool(diff.get("requires_window_expand")) or (len(posts_copy) == 0)
        new_p_start = int(getattr(eff_opts, "page_start", 1) or 1)
        new_p_end = int(getattr(eff_opts, "page_end", 999999) or 999999)
        if not ctx.from_watchlist and self._date_auto_scan_pages and (eff_opts.date_after or eff_opts.date_before):
            new_p_end = 999999
        new_d_after = str(getattr(eff_opts, "date_after", "") or "")
        new_d_before = str(getattr(eff_opts, "date_before", "") or "")

        if want_window_expand:
            self._set_applying_mid_download_ui(True, f"Scanning expanded post range for {ctx.creator_name}...")
            fresh = self.api_client.fetch_user_posts(
                parsed=parsed,
                page_start=new_p_start,
                page_end=new_p_end,
                date_after=new_d_after,
                date_before=new_d_before,
                cancel_event=self._apply_cancel_event,
            )
            if _cancelled():
                return False, posts_copy, fav_ids, fetched_dms, fetched_comments, p_start, p_end, d_after, d_before
            if fresh:
                existing_comments = {str(p.get("id", "")): p.get("comments_text") for p in posts_copy if "comments_text" in p}
                seen_k = {(str(p.get("id", "")), bool(p.get("_is_dm"))) for p in posts_copy}
                for p in fresh:
                    pid = str(p.get("id", ""))
                    if pid in existing_comments:
                        p["comments_text"] = existing_comments[pid]
                    pk = (pid, bool(p.get("_is_dm")))
                    if pk not in seen_k:
                        seen_k.add(pk)
                        posts_copy.append(p)
                p_start = min(p_start, new_p_start)
                p_end = max(p_end, new_p_end)
                d_after = new_d_after if not d_after else (min(d_after, new_d_after) if new_d_after else "")
                d_before = new_d_before if not d_before else (max(d_before, new_d_before) if new_d_before else "")

        if (diff.get("requires_dm_scan") or (want_window_expand and getattr(eff_opts, "download_dms", False))) and not fetched_dms:
            if "cum.st" in (ctx.domain or "").lower() or "pawchive" in (ctx.domain or "").lower():
                self._set_applying_mid_download_ui(True, f"Fetching DMs for {ctx.creator_name}...")
                dms = self.api_client.fetch_user_dms(
                    parsed=parsed,
                    page_start=new_p_start,
                    page_end=new_p_end,
                    date_after=new_d_after,
                    date_before=new_d_before,
                    cancel_event=self._apply_cancel_event,
                )
                if _cancelled():
                    return False, posts_copy, fav_ids, fetched_dms, fetched_comments, p_start, p_end, d_after, d_before
                fetched_dms = True
                if dms:
                    seen_k = {(str(p.get("id", "")), bool(p.get("_is_dm"))) for p in posts_copy}
                    for dm in dms:
                        pk = (str(dm.get("id", "")), True)
                        if pk not in seen_k:
                            seen_k.add(pk)
                            posts_copy.append(dm)

        if diff.get("requires_fav_scan") and fav_ids is None:
            from core.auth_manager import auth_manager
            prov_id = self.get_provider_for_domain(ctx.domain)
            if not auth_manager.is_logged_in(prov_id):
                meta = auth_manager.get_provider_summary(prov_id)
                self._callOnGui.emit(lambda: self.favoriteAuthRequired.emit(meta.get("name", prov_id.capitalize())))
                return False, posts_copy, fav_ids, fetched_dms, fetched_comments, p_start, p_end, d_after, d_before
            self._set_applying_mid_download_ui(True, f"Fetching favorites for {ctx.creator_name}...")
            fav_posts = self.api_client.fetch_user_favorites(domain=ctx.domain, fav_type="post", cancel_event=self._apply_cancel_event)
            if _cancelled():
                return False, posts_copy, fav_ids, fetched_dms, fetched_comments, p_start, p_end, d_after, d_before
            fav_ids = {str(f.get("id")) for f in fav_posts if f.get("id")}

        if (diff.get("requires_comments_scan") or eff_opts.character_scope in ("comments", "all")) and not fetched_comments:
            self._set_applying_mid_download_ui(True, f"Scanning post comments for {ctx.creator_name}...")
            for p in posts_copy:
                if _cancelled():
                    return False, posts_copy, fav_ids, fetched_dms, fetched_comments, p_start, p_end, d_after, d_before
                if "comments_text" in p:
                    continue
                pid = str(p.get("id", ""))
                if pid:
                    comms = self.api_client.fetch_post_comments(ctx.domain, ctx.service, ctx.user_id, pid)
                    p["comments_text"] = "\n".join(c.get("content", "") for c in comms if isinstance(c, dict))
            fetched_comments = True

        return True, posts_copy, fav_ids, fetched_dms, fetched_comments, p_start, p_end, d_after, d_before

    @Slot(str, str)
    @Slot(str, str, str, str)
    def applyMidDownloadSettings(
        self,
        mode: str,
        scope: str = "global",
        targetUserId: str = "",
        targetService: str = "",
    ):
        """Applies mid-download settings cleanly via Continue, Delete & Re-download All, or Future Only."""
        mode_clean = str(mode or "").strip().lower()
        scope_clean = str(scope or "global").strip().lower()
        if mode_clean == "future_only":
            if scope_clean == "global":
                self.dismissPendingDownloadSettingsBanner()
            self.midDownloadApplyFinished.emit(True, "New settings saved for future downloads.")
            return

        if self._is_applying_mid_download:
            logger.warning("Settings update is already in progress.", category="downloader")
            return

        self._settings_apply_gen += 1
        my_gen = self._settings_apply_gen
        self._apply_cancel_event.clear()
        self._set_applying_mid_download_ui(True, "Preparing mid-download settings update...")

        def _worker():
            ok_final = False
            msg_final = ""
            try:
                if scope_clean == "creator" and targetUserId:
                    target_bids = set(self.downloader.active_batch_ids_for(targetUserId, targetService))
                else:
                    target_bids = set(self.downloader.active_unfinished_batch_ids())

                if not target_bids:
                    ok_final = True
                    msg_final = "No active downloads required updating."
                    return

                contexts = [
                    c for c in self.downloader.get_all_batch_contexts()
                    if c.batch_id in target_bids
                ]

                # Fast path: Tier 2 runtime-only changes never pause or rebuild
                if mode_clean == "continue" and contexts and len(contexts) == len(target_bids):
                    resolved_per_ctx = {}
                    all_tier2_only = True
                    any_proxy_changed = False
                    for c in contexts:
                        eff_opts, eff_base, eff_artist, site_flag, _wl = self._resolve_ctx_target_settings(c, scope=scope_clean)
                        diff = self._classify_ctx_diff(c, eff_opts, eff_base, eff_artist, site_flag)
                        resolved_per_ctx[c.batch_id] = (c, eff_opts, eff_base, eff_artist, site_flag, diff, _wl)
                        if diff.get("tier", 0) > 2 or diff.get("dest_changed"):
                            all_tier2_only = False
                        if diff.get("proxy_changed"):
                            any_proxy_changed = True

                    if all_tier2_only:
                        primary_opts = self._get_filter_options()
                        self.downloader.update_runtime_options(
                            target_bids,
                            primary_opts,
                            proxy_changed=any_proxy_changed,
                            update_global_options=(scope_clean == "global"),
                        )
                        for _bid, (ctx_item, e_opts, _eb, _ea, _sf, _df, _wl_item) in resolved_per_ctx.items():
                            ctx_item.applied_options = FilterOptions.from_dict(e_opts.to_dict())
                        ok_final = True
                        msg_final = "Active download transport settings updated."
                        return
                else:
                    resolved_per_ctx = {}
                    for c in contexts:
                        eff_opts, eff_base, eff_artist, site_flag, _wl = self._resolve_ctx_target_settings(c, scope=scope_clean)
                        diff = self._classify_ctx_diff(c, eff_opts, eff_base, eff_artist, site_flag)
                        resolved_per_ctx[c.batch_id] = (c, eff_opts, eff_base, eff_artist, site_flag, diff, _wl)

                # Step 1: Fetch Tier 4 API deltas BEFORE pausing workers or deleting files
                updated_posts_map: Dict[str, Any] = {}
                for bid, (c, eff_opts, eff_base, eff_artist, site_flag, diff, _wl) in resolved_per_ctx.items():
                    if self._apply_cancel_event.is_set() or my_gen != self._settings_apply_gen:
                        msg_final = "Settings update cancelled."
                        return
                    need_delta = (
                        diff.get("tier", 0) >= 4
                        or (not c.posts and not (c.parsed and c.parsed.is_external_provider))
                    )
                    if need_delta:
                        ok_d, p_list, f_ids, dms_f, comm_f, p_st, p_en, d_af, d_be = self._fetch_tier4_delta(
                            c, eff_opts, diff, my_gen
                        )
                        if not ok_d:
                            msg_final = "Settings update cancelled before interrupting active downloads."
                            return
                        updated_posts_map[bid] = (p_list, f_ids, dms_f, comm_f, p_st, p_en, d_af, d_be)

                # Also ensure recovery batches without context still support redownload cleanly
                if mode_clean == "continue" and len(resolved_per_ctx) < len(target_bids):
                    missing = [b for b in target_bids if b not in resolved_per_ctx]
                    msg_final = f"Batch {', '.join(missing[:2])} lacks source post metadata; use Delete Old & Re-download All."
                    return

                # Step 2: Quiesce target batch workers cleanly
                is_redownload = (mode_clean == "redownload")
                self._set_applying_mid_download_ui(
                    True,
                    "Stopping active transfers before cleanup..." if is_redownload else "Waiting for active transfers to pause...",
                )
                q_ok, q_err = self.downloader.quiesce_batches(
                    target_bids, mode=("cancel" if is_redownload else "pause"), timeout=15.0
                )
                if not q_ok:
                    msg_final = q_err or "Active transfers did not stop in time."
                    return

                # Step 3: Destructive cleanup for Option B ONLY after workers drained
                if is_redownload:
                    self._set_applying_mid_download_ui(True, "Deleting old files & archive records...")
                    all_tasks_snapshot = list(self.downloader.tasks)
                    wiped_wl_keys: Set[Tuple[str, str]] = set()
                    for bid in target_bids:
                        pair = resolved_per_ctx.get(bid)
                        batch_tasks = [t for t in all_tasks_snapshot if self.downloader._task_batch_id(t) == bid]
                        for bt in batch_tasks:
                            p_file = getattr(bt, "target_path", "") + ".part"
                            if p_file and os.path.isfile(p_file):
                                try:
                                    os.remove(p_file)
                                except OSError:
                                    pass
                        if pair is not None:
                            c, eff_opts, eff_base, eff_artist, site_flag, _diff, wl = pair
                            if wl is not None:
                                wkey = (wl.service.lower(), wl.user_id.lower())
                                if wkey not in wiped_wl_keys:
                                    wiped_wl_keys.add(wkey)
                                    self._wipe_creator_before_redownload(wl)
                            else:
                                self._wipe_ad_hoc_batch_before_redownload(
                                    c, batch_tasks, delete_creator_archive=not (c.parsed and c.parsed.is_single_post)
                                )
                    self.archiveRecordCountChanged.emit()
                    self.archiveUpdated.emit()

                # Step 4: Build new plans and splice in-place
                self._set_applying_mid_download_ui(True, "Rebuilding download queue with new settings...")
                batch_plans: Dict[str, Dict[str, Any]] = {}
                for bid, (c, eff_opts, eff_base, eff_artist, site_flag, _diff, wl) in resolved_per_ctx.items():
                    if wl is not None and not getattr(wl, "custom_folder", False) and eff_artist:
                        try:
                            os.makedirs(eff_artist, exist_ok=True)
                        except OSError:
                            pass
                        wl.download_dir = eff_artist
                        self._watchlist_manager.save(wl)

                    p_list, f_ids, dms_f, comm_f, p_st, p_en, d_af, d_be = updated_posts_map.get(
                        bid,
                        (
                            list(c.posts or []),
                            set(c.fetched_fav_ids) if c.fetched_fav_ids is not None else None,
                            c.fetched_dms,
                            c.fetched_comments,
                            c.scan_page_start,
                            c.scan_page_end,
                            c.scan_date_after,
                            c.scan_date_before,
                        ),
                    )
                    posts_for_build = (
                        [p for p in p_list if str(p.get("id")) in f_ids]
                        if (getattr(eff_opts, "favorite_mode", False) and f_ids is not None)
                        else p_list
                    )
                    batch_plans[bid] = {
                        "options": eff_opts,
                        "posts": posts_for_build,
                        "external_files": list(c.external_files or []) if (c.parsed and c.parsed.is_external_provider) else None,
                        "provider": c.provider or (c.parsed.provider if c.parsed else ""),
                        "post_id": c.post_id or (c.parsed.post_id if c.parsed else ""),
                        "creator_name": c.creator_name,
                        "service": c.service,
                        "domain": c.domain,
                        "base_dir": eff_base,
                        "artist_dir": eff_artist,
                        "user_id": c.user_id,
                    }

                    # Persist updated snapshot back into BatchBuildContext
                    c.posts = p_list
                    c.fetched_fav_ids = f_ids
                    c.fetched_dms = dms_f
                    c.fetched_comments = comm_f
                    c.scan_page_start = p_st
                    c.scan_page_end = p_en
                    c.scan_date_after = d_af
                    c.scan_date_before = d_be
                    c.base_dir = eff_base
                    c.artist_dir = eff_artist
                    c.applied_options = FilterOptions.from_dict(eff_opts.to_dict())
                    c.applied_download_dir = str(self._download_dir or "")
                    c.applied_site_in_folder_name = site_flag
                    c.force_redownload = is_redownload

                global_opts = self._get_filter_options()
                res = self.downloader.rebuild_batches_in_place(
                    batch_plans=batch_plans,
                    new_options=global_opts,
                    cookie_str=self._cookie_string,
                    force_redownload=is_redownload,
                    clear_previous_completed=is_redownload,
                    update_global_options=(scope_clean == "global"),
                )
                if not res.get("ok"):
                    msg_final = res.get("error") or "Could not rebuild queue."
                    return

                self._replaceBatchesSignal.emit(target_bids, res.get("replacement_tasks") or [])
                ok_final = True
                if is_redownload:
                    msg_final = "Cleared previous files and restarted with new settings."
                else:
                    migrated = int(res.get("migrated_parts", 0))
                    msg_final = (
                        f"Continued with new settings ({migrated} partial resume file(s) preserved)."
                        if migrated
                        else "Continued active downloads with new settings."
                    )
            except Exception as exc:
                logger.error(f"Error applying mid-download settings: {exc}", category="downloader")
                ok_final = False
                msg_final = str(exc)
            finally:
                self._set_applying_mid_download_ui(False, "")
                self._callOnGui.emit(self._evaluate_pending_download_settings)
                self._callOnGui.emit(lambda: self.midDownloadApplyFinished.emit(ok_final, msg_final))

        threading.Thread(target=_worker, daemon=True, name="MidDownloadApply").start()
