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



class SettingsPropsExtendedMixin(AppBridgeSignalsMixin):
    @Property(bool, notify=AppBridgeSignalsMixin.subfolderPerPostChanged)
    def subfolderPerPost(self) -> bool:
        return self._subfolder_per_post

    @subfolderPerPost.setter
    def subfolderPerPost(self, val: bool):
        if self._subfolder_per_post != val:
            self._subfolder_per_post = val
            self.subfolderPerPostChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=AppBridgeSignalsMixin.datePrefixChanged)
    def datePrefix(self) -> bool:
        return self._date_prefix

    @datePrefix.setter
    def datePrefix(self, val: bool):
        if self._date_prefix != val:
            self._date_prefix = val
            self.datePrefixChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.siteInFolderNameChanged)
    def siteInFolderName(self) -> bool:
        """Creator folders named "Artist [onlyfans]" (True) or "Artist" (False)."""
        return folder_naming.include_service

    @siteInFolderName.setter
    def siteInFolderName(self, val: bool):
        if folder_naming.include_service != bool(val):
            folder_naming.include_service = bool(val)
            self.siteInFolderNameChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.fileIndexPrefixChanged)
    def fileIndexPrefix(self) -> bool:
        return self._file_index_prefix

    @fileIndexPrefix.setter
    def fileIndexPrefix(self, val: bool):
        if self._file_index_prefix != val:
            self._file_index_prefix = val
            self.fileIndexPrefixChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.separateFoldersByKnownChanged)
    def separateFoldersByKnown(self) -> bool:
        return self._separate_folders_by_known

    @separateFoldersByKnown.setter
    def separateFoldersByKnown(self, val: bool):
        if self._separate_folders_by_known != val:
            self._separate_folders_by_known = val
            self.separateFoldersByKnownChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=AppBridgeSignalsMixin.downloadRevisionsChanged)
    def downloadRevisions(self) -> bool:
        return self._download_revisions

    @downloadRevisions.setter
    def downloadRevisions(self, val: bool):
        if self._download_revisions != val:
            self._download_revisions = val
            self.downloadRevisionsChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=AppBridgeSignalsMixin.adaptiveThreadingChanged)
    def adaptiveThreading(self) -> bool:
        return self._adaptive_threading

    @adaptiveThreading.setter
    def adaptiveThreading(self, val: bool):
        # Cannot enable adaptive threading if threads are locked
        if self._threads_locked and val:
            return
        if self._adaptive_threading != val:
            self._adaptive_threading = val
            self.adaptiveThreadingChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.threadsLockedChanged)
    def threadsLocked(self) -> bool:
        return self._threads_locked

    @threadsLocked.setter
    def threadsLocked(self, val: bool):
        val = bool(val)
        if self._threads_locked != val:
            self._threads_locked = val
            self.threadsLockedChanged.emit()
            if val:
                # Lock applied -> disable adaptive threading
                self.adaptiveThreading = False
            if hasattr(self.downloader, "current_options") and self.downloader.current_options:
                self.downloader.current_options.threads_locked = val
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.autoRetryAtEndChanged)
    def autoRetryAtEnd(self) -> bool:
        return self._auto_retry_at_end

    @autoRetryAtEnd.setter
    def autoRetryAtEnd(self, val: bool):
        if self._auto_retry_at_end != val:
            self._auto_retry_at_end = val
            self.autoRetryAtEndChanged.emit()
            self.scheduleSaveSettings()
            if hasattr(self.downloader, "current_options") and self.downloader.current_options:
                self.downloader.current_options.auto_retry_at_end = val
            if val and not self._is_downloading and self._has_failed_tasks():
                logger.info("Auto-Retry enabled with failed tasks present — starting retry queue...", category="downloader")
                self._retry_failed(include_cancelled=False)

    @Slot()
    def toggleAutoRetry(self):
        """Toggles auto-retry; if turning on (or if already on with failed tasks idle), immediately retries failed tasks."""
        if not self._auto_retry_at_end:
            self.autoRetryAtEnd = True
        else:
            if not self._is_downloading and self._has_failed_tasks():
                logger.info("Auto-Retry activated for failed tasks...", category="downloader")
                self._retry_failed(include_cancelled=False)
            else:
                self.autoRetryAtEnd = False

    @Property(bool, notify=AppBridgeSignalsMixin.skipRetry404Changed)
    def skipRetry404(self) -> bool:
        return self._skip_retry_404

    @skipRetry404.setter
    def skipRetry404(self, val: bool):
        val = bool(val)
        if self._skip_retry_404 != val:
            self._skip_retry_404 = val
            self.skipRetry404Changed.emit()
            self.scheduleSaveSettings()
            if hasattr(self.downloader, "current_options") and self.downloader.current_options:
                self.downloader.current_options.skip_retry_404 = val
            if val:
                tasks_to_update = []
                if hasattr(self, "_queue_model") and self._queue_model:
                    for t in self._queue_model.getTasks():
                        if t.status == "pending" and ("404" in str(getattr(t, "error_msg", "")).lower() or getattr(t, "http_status", 0) == 404):
                            t.status = "failed"
                            tasks_to_update.append(t)
                    for t in tasks_to_update:
                        self._queue_model.updateTask(t)
                if hasattr(self, "downloader") and self.downloader:
                    for t in self.downloader.tasks:
                        if t.status == "pending" and ("404" in str(getattr(t, "error_msg", "")).lower() or getattr(t, "http_status", 0) == 404):
                            t.status = "failed"
            if hasattr(self, "_queue_model") and self._queue_model:
                self._queue_model.failedCountChanged.emit()

    @Property(bool, notify=AppBridgeSignalsMixin.mangaModeChanged)
    def mangaMode(self) -> bool:
        return self._manga_mode

    @mangaMode.setter
    def mangaMode(self, val: bool):
        if self._manga_mode != val:
            self._manga_mode = val
            self.mangaModeChanged.emit()
            self._settings_save_timer.start()

    @Property(str, notify=AppBridgeSignalsMixin.filenameStyleChanged)
    def filenameStyle(self) -> str:
        return self._filename_style

    @filenameStyle.setter
    def filenameStyle(self, val: str):
        if self._filename_style != val:
            self._filename_style = val
            self.filenameStyleChanged.emit()
            self.scheduleSaveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.filenameTemplateChanged)
    def filenameTemplate(self) -> str:
        return self._filename_template

    @filenameTemplate.setter
    def filenameTemplate(self, val: str):
        if self._filename_template != val:
            self._filename_template = val
            self.filenameTemplateChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.postSelectionLoadingChanged)
    def postSelectionLoading(self) -> bool:
        return self._is_post_selection_loading

    @Property(int, notify=AppBridgeSignalsMixin.postSelectionProgressPageChanged)
    def postSelectionProgressPage(self) -> int:
        return self._post_selection_progress_page

    @Property(int, notify=AppBridgeSignalsMixin.postSelectionProgressCountChanged)
    def postSelectionProgressCount(self) -> int:
        return self._post_selection_progress_count

    @Property(int, notify=AppBridgeSignalsMixin.postSelectionProgressTotalChanged)
    def postSelectionProgressTotal(self) -> int:
        return self._post_selection_progress_total

    @Property(str, notify=AppBridgeSignalsMixin.postSelectionProgressStatusChanged)
    def postSelectionProgressStatus(self) -> str:
        return self._post_selection_progress_status

    def _emit_post_selection_progress(self, page: int, count: int, total: int = 0, status: str = ""):
        # Never reset an already known total back to 0 during an active scan
        prev_total = getattr(self, "_post_selection_progress_total", 0)
        new_total = total if (total > 0 or count == 0) else prev_total

        page_changed = (getattr(self, "_post_selection_progress_page", -1) != page)
        count_changed = (getattr(self, "_post_selection_progress_count", -1) != count)
        total_changed = (prev_total != new_total)
        status_changed = (getattr(self, "_post_selection_progress_status", None) != status)

        self._post_selection_progress_page = page
        self._post_selection_progress_count = count
        self._post_selection_progress_total = new_total
        self._post_selection_progress_status = status

        try:
            if page_changed:
                self.postSelectionProgressPageChanged.emit()
            if count_changed:
                self.postSelectionProgressCountChanged.emit()
            if total_changed:
                self.postSelectionProgressTotalChanged.emit()
            if status_changed:
                self.postSelectionProgressStatusChanged.emit()
            self.postSelectionProgress.emit(page, count, new_total, status)
        except RuntimeError:
            pass

    @Property(str, notify=AppBridgeSignalsMixin.proxyUrlChanged)
    def proxyUrl(self) -> str:
        return self._proxy_url

    @proxyUrl.setter
    def proxyUrl(self, val: str):
        if self._proxy_url != val:
            self._proxy_url = val
            self.api_client.set_proxy(val)
            from services import update_service as us
            us.apply_proxy(val)
            self.proxyUrlChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.bandwidthLimitEnabledChanged)
    def bandwidthLimitEnabled(self) -> bool:
        return self._bandwidth_limit_enabled

    @bandwidthLimitEnabled.setter
    def bandwidthLimitEnabled(self, val: bool):
        val = bool(val)
        if self._bandwidth_limit_enabled != val:
            self._bandwidth_limit_enabled = val
            bandwidth_limiter.update(self._bandwidth_limit_enabled, self._bandwidth_limit_value, self._bandwidth_limit_unit)
            self.bandwidthLimitEnabledChanged.emit()
            self.bandwidthLimitSummaryChanged.emit()
            self.scheduleSaveSettings()

    @Property(float, notify=AppBridgeSignalsMixin.bandwidthLimitValueChanged)
    def bandwidthLimitValue(self) -> float:
        return self._bandwidth_limit_value

    @bandwidthLimitValue.setter
    def bandwidthLimitValue(self, val: float):
        try:
            val_f = max(0.1, round(float(val), 2))
        except (ValueError, TypeError):
            val_f = 10.0
        if self._bandwidth_limit_value != val_f:
            self._bandwidth_limit_value = val_f
            bandwidth_limiter.update(self._bandwidth_limit_enabled, self._bandwidth_limit_value, self._bandwidth_limit_unit)
            self.bandwidthLimitValueChanged.emit()
            self.bandwidthLimitSummaryChanged.emit()
            self.scheduleSaveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.bandwidthLimitUnitChanged)
    def bandwidthLimitUnit(self) -> str:
        return self._bandwidth_limit_unit

    @bandwidthLimitUnit.setter
    def bandwidthLimitUnit(self, val: str):
        unit = "mbps" if "mbps" in str(val).lower() else "MB/s"
        if self._bandwidth_limit_unit != unit:
            self._bandwidth_limit_unit = unit
            bandwidth_limiter.update(self._bandwidth_limit_enabled, self._bandwidth_limit_value, self._bandwidth_limit_unit)
            self.bandwidthLimitUnitChanged.emit()
            self.bandwidthLimitSummaryChanged.emit()
            self.scheduleSaveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.bandwidthLimitSummaryChanged)
    def bandwidthLimitSummary(self) -> str:
        return bandwidth_limiter.get_summary()

    @Slot(bool, float, str)
    def setBandwidthLimit(self, enabled: bool, value: float, unit: str):
        self._bandwidth_limit_enabled = bool(enabled)
        try:
            self._bandwidth_limit_value = max(0.1, round(float(value), 2))
        except (ValueError, TypeError):
            self._bandwidth_limit_value = 10.0
        self._bandwidth_limit_unit = "mbps" if "mbps" in str(unit).lower() else "MB/s"
        bandwidth_limiter.update(self._bandwidth_limit_enabled, self._bandwidth_limit_value, self._bandwidth_limit_unit)
        self.bandwidthLimitEnabledChanged.emit()
        self.bandwidthLimitValueChanged.emit()
        self.bandwidthLimitUnitChanged.emit()
        self.bandwidthLimitSummaryChanged.emit()
        self.scheduleSaveSettings()

    @Property(int, notify=AppBridgeSignalsMixin.threadsCountChanged)
    def threadsCount(self) -> int:
        return self._threads_count

    @threadsCount.setter
    def threadsCount(self, val: int):
        from core.filter_options import safe_int
        val_i = safe_int(val, self._threads_count)
        # Strict Telegram ceiling: Under any circumstance, clamp to max 2 threads for Telegram
        is_pure_tg = False
        if hasattr(self, "downloader") and self.downloader.tasks:
            is_pure_tg = all(
                getattr(t, "is_telegram", False) or getattr(t, "service", "") == "telegram" or (t.url and t.url.startswith("tg://"))
                for t in self.downloader.tasks
            )
        if is_pure_tg:
            val_i = min(val_i, 2)

        clamped = max(1, min(self._max_cpu_threads, val_i))
        if self._threads_count != clamped:
            self._threads_count = clamped
            self.downloader.max_workers = self._threads_count
            self.threadsCountChanged.emit()
            self._settings_save_timer.start()

    @Property(int, notify=AppBridgeSignalsMixin.maxCpuThreadsChanged)
    def maxCpuThreads(self) -> int:
        return self._max_cpu_threads

    @Property(str, notify=AppBridgeSignalsMixin.etaTextChanged)
    def etaText(self) -> str:
        return self._eta_text

    @Property(str, notify=AppBridgeSignalsMixin.savedBytesTextChanged)
    def savedBytesText(self) -> str:
        return self._saved_bytes_text

    @Property(str, notify=AppBridgeSignalsMixin.adaptiveStatusTextChanged)
    def adaptiveStatusText(self) -> str:
        return self._adaptive_status_text

    @Property(str, notify=AppBridgeSignalsMixin.adaptiveStateChanged)
    def adaptiveState(self) -> str:
        return self._adaptive_state

    @Property(str, notify=AppBridgeSignalsMixin.elapsedTimeTextChanged)
    def elapsedTimeText(self) -> str:
        return self._elapsed_time_text

    @Property(str, notify=AppBridgeSignalsMixin.filesCountTextChanged)
    def filesCountText(self) -> str:
        return self._files_count_text

    @Property(str, notify=AppBridgeSignalsMixin.cookieStringChanged)
    def cookieString(self) -> str:
        return self._cookie_string

    @cookieString.setter
    def cookieString(self, val: str):
        val = val.strip()
        if val and val.startswith("eyJ") and "session=" not in val:
            val = f"session={val}"
        elif val and "=" not in val:
            val = f"session={val}"
        if self._cookie_string != val:
            self._cookie_string = val
            self.api_client.set_cookie(val)
            self._cookie_save_timer.start()      # saved once typing stops
            self.cookieStringChanged.emit()

    @Slot()
    def _persist_cookie(self):
        try:
            from core.auth_manager import auth_manager
            # The general cookie is kept in the vault's "kemono" slot (never in settings.json)
            auth_manager.set_credential("kemono", {"cookie": self._cookie_string})
            self.providersChanged.emit()
        except Exception as e:
            logger.debug(f"Could not save the cookie: {e}", category="auth")

    @Property(str, notify=AppBridgeSignalsMixin.userAgentChanged)
    def userAgent(self) -> str:
        return self._user_agent

    @userAgent.setter
    def userAgent(self, val: str):
        if self._user_agent != val:
            self._user_agent = val
            self.api_client.set_user_agent(val)
            self.userAgentChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=AppBridgeSignalsMixin.isDownloadingChanged)
    def isDownloading(self) -> bool:
        return self._is_downloading

    @Property(bool, notify=AppBridgeSignalsMixin.isPausedChanged)
    def isPaused(self) -> bool:
        return self.downloader.is_paused or self._cloud_pause_event.is_set() or ("Paused" in self._status_text)

    @Property(str, notify=AppBridgeSignalsMixin.statusTextChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(int, notify=AppBridgeSignalsMixin.overallProgressChanged)
    def overallProgress(self) -> int:
        return self._overall_progress

    @Property(str, notify=AppBridgeSignalsMixin.currentSpeedChanged)
    def currentSpeed(self) -> str:
        return self._current_speed

    @Property(str, notify=AppBridgeSignalsMixin.currentSpeedChanged)
    def speedText(self) -> str:
        return self._current_speed

    @Property(bool, notify=AppBridgeSignalsMixin.hasSavedSessionChanged)
    def hasSavedSession(self) -> bool:
        return self._has_saved_session

    @Property(bool, notify=AppBridgeSignalsMixin.hasRecoverySessionChanged)
    def hasRecoverySession(self) -> bool:
        return self._has_recovery_session

    @Property('QVariant', notify=AppBridgeSignalsMixin.hasRecoverySessionChanged)
    def recoverySummary(self) -> dict:
        return self._recovery_summary or {}

    @Property(bool, notify=AppBridgeSignalsMixin.hasErrorChanged)
    def hasError(self) -> bool:
        return self._has_error

    @hasError.setter
    def hasError(self, val: bool):
        val = bool(val)
        if self._has_error != val:
            self._has_error = val
            self.hasErrorChanged.emit()

    @Property(str, notify=AppBridgeSignalsMixin.lastErrorMessageChanged)
    def lastErrorMessage(self) -> str:
        return self._last_error_message

    @lastErrorMessage.setter
    def lastErrorMessage(self, val: str):
        val = str(val or "")
        if self._last_error_message != val:
            self._last_error_message = val
            self.lastErrorMessageChanged.emit()

    @Property(str, notify=AppBridgeSignalsMixin.creatorNameChanged)
    def creatorName(self) -> str:
        return self._creator_name

    @Property(str, notify=AppBridgeSignalsMixin.languageChanged)
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, val: str):
        if self._language != val:
            self._language = val
            self.languageChanged.emit()
            self.scheduleSaveSettings()

    @Property(float, notify=AppBridgeSignalsMixin.uiScaleChanged)
    def uiScale(self) -> float:
        return self._ui_scale

    @uiScale.setter
    def uiScale(self, val: float):
        try:
            val_f = float(val)
            if val_f > 10.0:
                val_f = val_f / 100.0
            val_f = max(0.5, min(3.5, round(val_f, 2)))
        except Exception:
            val_f = 1.0
        if abs(self._ui_scale - val_f) >= 0.005:
            self._ui_scale = val_f
            self.uiScaleChanged.emit()
            self.saveSettings()

    @Property(float, constant=True)
    def activeUiScale(self) -> float:
        return self._active_ui_scale

    @Property(bool, notify=AppBridgeSignalsMixin.uiScaleChanged)
    def uiScaleRestartNeeded(self) -> bool:
        return abs(self._ui_scale - self._active_ui_scale) >= 0.04

    @Slot()
    def restartApplication(self):
        """Save settings and restart Pawchive Downloader to apply changes (e.g. UI scale)."""
        self.saveSettings()
        try:
            from services.update_service import detached_popen_kwargs
            if getattr(sys, "frozen", False):
                cmd = [sys.executable]
                cwd = os.path.dirname(sys.executable)
            else:
                main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
                cmd = [sys.executable, main_py]
                cwd = os.path.dirname(main_py)
            env = clean_subprocess_env(os.environ)
            if abs(self._ui_scale - 1.0) >= 0.01:
                env["QT_SCALE_FACTOR"] = f"{self._ui_scale:.2f}".rstrip("0").rstrip(".")
            else:
                env.pop("QT_SCALE_FACTOR", None)
            subprocess.Popen(cmd, cwd=cwd, env=env, **detached_popen_kwargs())
            logger.info(f"Relaunching application (UI scale: {self._ui_scale:.2f}x)...", category="system")
        except Exception as e:
            logger.error(f"Failed to restart application: {e}", category="system")
        QTimer.singleShot(150, QCoreApplication.quit)

    @Property(bool, notify=AppBridgeSignalsMixin.autoSyncKnownChanged)
    def autoSyncKnown(self) -> bool:
        return bool(getattr(self, "_auto_sync_known", True))

    @autoSyncKnown.setter
    def autoSyncKnown(self, val: bool):
        b = bool(val)
        if getattr(self, "_auto_sync_known", True) != b:
            self._auto_sync_known = b
            self.autoSyncKnownChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.showConsoleLinksChanged)
    def showConsoleLinks(self) -> bool:
        return bool(getattr(self, "_show_console_links", True))

    @showConsoleLinks.setter
    def showConsoleLinks(self, val: bool):
        b = bool(val)
        if getattr(self, "_show_console_links", True) != b:
            self._show_console_links = b
            self.showConsoleLinksChanged.emit()
            self.scheduleSaveSettings()

    @Property(float, notify=AppBridgeSignalsMixin.downloadDelayChanged)
    def downloadDelay(self) -> float:
        return self._download_delay

    @downloadDelay.setter
    def downloadDelay(self, val: float):
        from core.filter_options import safe_float
        val_f = max(0.0, round(safe_float(val, self._download_delay), 2))
        if self._download_delay != val_f:
            self._download_delay = val_f
            self.downloadDelayChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.savePostMetadataChanged)
    def savePostMetadata(self) -> bool:
        return self._save_post_metadata

    @savePostMetadata.setter
    def savePostMetadata(self, val: bool):
        if self._save_post_metadata != val:
            self._save_post_metadata = val
            self.savePostMetadataChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.writeSidecarsChanged)
    def writeSidecars(self) -> bool:
        return self._write_sidecars

    @writeSidecars.setter
    def writeSidecars(self, val: bool):
        val = bool(val)
        if self._write_sidecars != val:
            self._write_sidecars = val
            self.writeSidecarsChanged.emit()
            self.scheduleSaveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.sidecarFormatChanged)
    def sidecarFormat(self) -> str:
        return self._sidecar_format

    @sidecarFormat.setter
    def sidecarFormat(self, val: str):
        val = str(val or "json").lower()
        if self._sidecar_format != val:
            self._sidecar_format = val
            self.sidecarFormatChanged.emit()
            self.scheduleSaveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.sidecarScopeChanged)
    def sidecarScope(self) -> str:
        return self._sidecar_scope

    @sidecarScope.setter
    def sidecarScope(self, val: str):
        val = str(val or "per_file").lower()
        if self._sidecar_scope != val:
            self._sidecar_scope = val
            self.sidecarScopeChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.downloadEmbedsChanged)
    def downloadEmbeds(self) -> bool:
        return self._download_embeds

    @downloadEmbeds.setter
    def downloadEmbeds(self, val: bool):
        if self._download_embeds != val:
            self._download_embeds = val
            self.downloadEmbedsChanged.emit()
            self.scheduleSaveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.embedCookiesBrowserChanged)
    def embedCookiesBrowser(self) -> str:
        return self._embed_cookies_browser

    @embedCookiesBrowser.setter
    def embedCookiesBrowser(self, val: str):
        val = str(val or "").lower()
        if self._embed_cookies_browser != val:
            self._embed_cookies_browser = val
            self.downloader.ytdlp_manager.set_cookies_browser(val)
            self.embedCookiesBrowserChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.openFolderOnCompleteChanged)
    def openFolderOnComplete(self) -> bool:
        return self._open_folder_on_complete

    @openFolderOnComplete.setter
    def openFolderOnComplete(self, val: bool):
        if self._open_folder_on_complete != val:
            self._open_folder_on_complete = val
            self.openFolderOnCompleteChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.playCompletionSoundChanged)
    def playCompletionSound(self) -> bool:
        return self._play_completion_sound

    @playCompletionSound.setter
    def playCompletionSound(self, val: bool):
        if self._play_completion_sound != val:
            self._play_completion_sound = val
            self.playCompletionSoundChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.generateDesktopReportChanged)
    def generateDesktopReport(self) -> bool:
        return self._generate_desktop_report

    @generateDesktopReport.setter
    def generateDesktopReport(self, val: bool):
        if self._generate_desktop_report != val:
            self._generate_desktop_report = val
            self.generateDesktopReportChanged.emit()
            self.saveDesktopReportChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.saveDesktopReportChanged)
    def saveDesktopReport(self) -> bool:
        return self._generate_desktop_report

    @saveDesktopReport.setter
    def saveDesktopReport(self, val: bool):
        self.generateDesktopReport = val

    @Property(bool, notify=AppBridgeSignalsMixin.enableDownloadArchiveChanged)
    def enableDownloadArchive(self) -> bool:
        return self._enable_download_archive

    @enableDownloadArchive.setter
    def enableDownloadArchive(self, val: bool):
        val = bool(val)
        if self._enable_download_archive != val:
            self._enable_download_archive = val
            self.archive_manager.set_enabled(val)
            self.enableDownloadArchiveChanged.emit()
            self.archiveRecordCountChanged.emit()
            self.scheduleSaveSettings()

    @Property(int, notify=AppBridgeSignalsMixin.archiveRecordCountChanged)
    def archiveRecordCount(self) -> int:
        return self.archive_manager.get_total_count()
