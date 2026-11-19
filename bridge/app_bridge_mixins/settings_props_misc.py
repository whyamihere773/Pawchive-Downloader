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



class SettingsPropsMiscMixin(AppBridgeSignalsMixin):
    @Property("QVariantList", notify=AppBridgeSignalsMixin.disabledTabsChanged)
    def disabledTabs(self) -> list:
        return list(self._disabled_tabs)

    @Slot(str, result=bool)
    def isTabDisabled(self, tab_key: str) -> bool:
        clean = (tab_key or "").strip().lower()
        if clean in ("downloader", "settings"):
            return False
        return clean in self._disabled_tabs

    @Slot(str, bool)
    def setTabDisabled(self, tab_key: str, disabled: bool) -> None:
        clean = (tab_key or "").strip().lower()
        if not clean or clean in ("downloader", "settings"):
            return
        changed = False
        if disabled and clean not in self._disabled_tabs:
            self._disabled_tabs.append(clean)
            changed = True
        elif not disabled and clean in self._disabled_tabs:
            self._disabled_tabs = [t for t in self._disabled_tabs if t != clean]
            changed = True
        if changed:
            self.disabledTabsChanged.emit()
            self.scheduleSaveSettings()

    @Slot()
    def resetDisabledTabs(self) -> None:
        if self._disabled_tabs:
            self._disabled_tabs = []
            self.disabledTabsChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.privacyModeActiveChanged)
    def privacyModeActive(self) -> bool:
        return self._privacy_mode_active

    @privacyModeActive.setter
    def privacyModeActive(self, val: bool):
        val = bool(val)
        if self._privacy_mode_active != val:
            self._privacy_mode_active = val
            self.privacyModeActiveChanged.emit()

    @Property(bool, notify=AppBridgeSignalsMixin.privacyPinConfiguredChanged)
    def privacyPinConfigured(self) -> bool:
        return bool(self._privacy_pin)

    @Property(int, notify=AppBridgeSignalsMixin.privacyFailedAttemptsChanged)
    def privacyFailedAttempts(self) -> int:
        return self._failed_pin_attempts

    @Property(bool, notify=AppBridgeSignalsMixin.privacyLockoutActiveChanged)
    def privacyLockoutActive(self) -> bool:
        return self._privacy_lockout_active

    @Property(bool, notify=AppBridgeSignalsMixin.safeModeActiveChanged)
    def safeModeActive(self) -> bool:
        return self._safe_mode_active

    @Property(int, notify=AppBridgeSignalsMixin.privacyIdleMinutesChanged)
    def privacyIdleMinutes(self) -> int:
        return self._privacy_idle_minutes

    @Slot(result=bool)
    def togglePrivacyMode(self) -> bool:
        if not self._privacy_mode_active:
            self.privacyModeActive = True
            return True
        else:
            if not self._privacy_pin:
                self.privacyModeActive = False
                return False
            return True

    @Slot(str, result=bool)
    def unlockPrivacyMode(self, pin: str = "") -> bool:
        if self._privacy_lockout_active:
            return False
        entered = str(pin or "").strip()
        if not self._privacy_pin:
            self._failed_pin_attempts = 0
            self.privacyFailedAttemptsChanged.emit()
            self.privacyModeActive = False
            return True
        if entered == self._privacy_pin:
            self._failed_pin_attempts = 0
            self.privacyFailedAttemptsChanged.emit()
            self.privacyModeActive = False
            return True
        else:
            self._failed_pin_attempts += 1
            self.privacyFailedAttemptsChanged.emit()
            if self._failed_pin_attempts >= 5:
                self._privacy_lockout_active = True
                self._pending_pin_reset = True
                self.saveSettings()
                self.privacyLockoutActiveChanged.emit()
                logger.warning("Privacy PIN failed 5 times; session locked out until restart.", category="session")
            return False

    @Slot()
    def requestPinReset(self):
        """User clicked 'Forgot PIN' or requested reset from locked state."""
        self._pending_pin_reset = True
        self._privacy_lockout_active = True
        self.saveSettings()
        self.privacyLockoutActiveChanged.emit()
        logger.info("Privacy PIN reset requested. Application locked until restart.", category="session")

    @Slot(str)
    def completePinReset(self, new_pin: str = ""):
        """Called when user sets a new PIN (or clears it) in Safe Mode after restart."""
        cleaned = str(new_pin or "").strip()
        self._privacy_pin = cleaned
        self._pending_pin_reset = False
        self._safe_mode_active = False
        self._failed_pin_attempts = 0
        self._privacy_lockout_active = False
        self.saveSettings()
        self.privacyPinConfiguredChanged.emit()
        self.privacyFailedAttemptsChanged.emit()
        self.privacyLockoutActiveChanged.emit()
        self.safeModeActiveChanged.emit()
        self.privacyModeActive = False
        logger.info(f"Safe Mode resolved. PIN set: {bool(cleaned)}. All tabs restored.", category="session")

    @Slot(str)
    def setPrivacyPin(self, new_pin: str):
        cleaned = str(new_pin or "").strip()
        self._privacy_pin = cleaned
        self._failed_pin_attempts = 0
        self._privacy_lockout_active = False
        self._pending_pin_reset = False
        self.saveSettings()
        self.privacyPinConfiguredChanged.emit()
        self.privacyFailedAttemptsChanged.emit()
        self.privacyLockoutActiveChanged.emit()
        logger.info("Privacy PIN updated successfully.", category="session")

    @Slot()
    def resetPrivacyPin(self):
        self._privacy_pin = ""
        self._failed_pin_attempts = 0
        self._privacy_lockout_active = False
        self._pending_pin_reset = False
        self.saveSettings()
        self.privacyPinConfiguredChanged.emit()
        self.privacyFailedAttemptsChanged.emit()
        self.privacyLockoutActiveChanged.emit()
        self.privacyModeActive = False
        logger.info("Privacy PIN removed.", category="session")

    @Slot(int)
    def setPrivacyIdleMinutes(self, minutes: int):
        m = max(0, min(60, int(minutes)))
        if self._privacy_idle_minutes != m:
            self._privacy_idle_minutes = m
            self.privacyIdleMinutesChanged.emit()
            self.saveSettings()
            logger.info(f"Privacy idle timeout set to {m} minutes.", category="session")

    @Property(int, notify=AppBridgeSignalsMixin.consoleWidthChanged)
    def consoleWidth(self) -> int:
        return self._console_width

    @consoleWidth.setter
    def consoleWidth(self, val: int):
        val = max(280, min(1400, int(val)))
        if self._console_width != val:
            self._console_width = val
            self.consoleWidthChanged.emit()
            self.scheduleSaveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.postDownloadActionChanged)
    def postDownloadAction(self) -> str:
        return self._post_download_action

    @postDownloadAction.setter
    def postDownloadAction(self, val: str):
        allowed = {"none", "close_app", "sleep", "hibernate", "shutdown", "restart"}
        if val not in allowed:
            val = "none"
        if self._post_download_action != val:
            self._post_download_action = val
            self.postDownloadActionChanged.emit()

    @Property(QObject, constant=True)
    def logModel(self) -> LogModel:
        return self._log_model

    @Property(QObject, constant=True)
    def queueModel(self) -> QueueModel:
        return self._queue_model

    @Property(QObject, constant=True)
    def activeQueueModel(self) -> QueueModel:
        return self._active_queue_model

    @Property(QObject, constant=True)
    def knownModel(self) -> KnownModel:
        return self._known_model

    @Property(QObject, constant=True)
    def watchlistModel(self) -> WatchlistModel:
        return self._watchlist_model

    @Property(QObject, constant=True)
    def linkVaultCreatorsModel(self) -> RecordListModel:
        """The Link Vault's creators (filled by linkVaultTreeJsonAsync)."""
        return self._vault_creators_model

    @Property(QObject, constant=True)
    def archiveCreatorsModel(self) -> ArchiveCreatorsModel:
        """The Archive tab's creators (filled by getArchiveDataAsync)."""
        return self._archive_creators_model

    @Property(bool, notify=AppBridgeSignalsMixin.watchlistApplyGlobalSettingsChanged)
    def watchlistApplyGlobalSettings(self) -> bool:
        return self._watchlist_apply_global_settings

    @watchlistApplyGlobalSettings.setter
    def watchlistApplyGlobalSettings(self, val: bool):
        b_val = bool(val)
        if self._watchlist_apply_global_settings != b_val:
            self._watchlist_apply_global_settings = b_val
            self.watchlistApplyGlobalSettingsChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.watchlistCheckOnStartupChanged)
    def watchlistCheckOnStartup(self) -> bool:
        return self._watchlist_check_on_startup

    @watchlistCheckOnStartup.setter
    def watchlistCheckOnStartup(self, val: bool):
        b_val = bool(val)
        if self._watchlist_check_on_startup != b_val:
            self._watchlist_check_on_startup = b_val
            self.watchlistCheckOnStartupChanged.emit()
            self.saveSettings()

    @Property(QObject, constant=True)
    def decompressorBridge(self) -> DecompressorBridge:
        return self._decompressor_bridge

    @Property(QObject, constant=True)
    def telegramBridge(self) -> TelegramBridge:
        return self._telegram_bridge

    @Property(bool, notify=AppBridgeSignalsMixin.tagFolderModeChanged)
    def tagFolderMode(self) -> bool:
        return self._tag_folder_mode

    @tagFolderMode.setter
    def tagFolderMode(self, val: bool):
        if self._tag_folder_mode != val:
            self._tag_folder_mode = val
            self.tagFolderModeChanged.emit()
            self.scheduleSaveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.groupFileTypeChanged)
    def groupFileType(self) -> str:
        return self._group_file_type

    @groupFileType.setter
    def groupFileType(self, val: str):
        val = str(val or "none").lower()
        if val not in ("none", "post", "creator"):
            val = "none"
        if self._group_file_type != val:
            self._group_file_type = val
            self.groupFileTypeChanged.emit()
            self.scheduleSaveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.fileOrderChanged)
    def fileOrder(self) -> str:
        """Order of the files inside a post: "posted", "reversed" or "name"."""
        return self._file_order

    @fileOrder.setter
    def fileOrder(self, val: str):
        val = normalize_file_order(val)
        if self._file_order != val:
            self._file_order = val
            self.fileOrderChanged.emit()
            self._settings_save_timer.start()

    @Slot("QVariantList", result="QVariantList")
    def orderPostFiles(self, files):
        """A post's files in the order they'll be numbered (for the Post Selection window).

        Each file remembers its place on the site ("postedIndex"), so switching the order back and
        forth always starts from the posted order.
        """
        items = [dict(f) for f in (files or []) if isinstance(f, dict)]
        for i, f in enumerate(items):
            f.setdefault("postedIndex", i)
        items.sort(key=lambda f: int(f.get("postedIndex") or 0))
        return order_files(items, self._file_order, lambda f: str(f.get("name") or ""))

    @Property(bool, notify=AppBridgeSignalsMixin.harvestedLinksChanged)
    def hasHarvestedLinks(self) -> bool:
        return bool(self.downloader.harvested_links_records)

    @Property(int, notify=AppBridgeSignalsMixin.harvestedLinksChanged)
    def harvestedLinksCount(self) -> int:
        return len(self.downloader.harvested_links_records)

    @Property(list, notify=AppBridgeSignalsMixin.harvestedLinksChanged)
    def harvestedLinks(self) -> list:
        return self.downloader.harvested_links_records

    @Property(bool, notify=AppBridgeSignalsMixin.isDownloadingChanged)
    def isCloudDownloading(self) -> bool:
        return self._is_cloud_downloading

    def _vault_tree(self) -> list:
        """The Link Vault's tree for the current search / platform. Built once per vault change and
        filter: it was rebuilt (the whole vault) on every read."""
        from core.link_vault_manager import link_vault_manager
        key = (getattr(link_vault_manager, "revision", 0), len(link_vault_manager.data.get("links", [])),
               self._vault_search, self._vault_platform)
        cached = self.__dict__.get("_vault_tree_cache")
        if cached and cached[0] == key:
            return cached[1]
        tree = link_vault_manager.get_tree_model(self._vault_search, self._vault_platform)
        self._vault_tree_cache = (key, tree)
        return tree

    @Property(str, notify=AppBridgeSignalsMixin.linkVaultChanged)
    def linkVaultTreeJson(self) -> str:
        return json.dumps(self._vault_tree(), ensure_ascii=False)

    @Slot(str)
    def linkVaultTreeJsonAsync(self, request_id: str):
        """The Link Vault's creators, built in the background into linkVaultCreatorsModel (the view
        shows them with applyPending()); asyncResultReady answers with their number. Sending the
        whole tree as one JSON text to parse on the window thread froze big vaults."""
        def _job():
            try:
                tree = self._vault_tree()
            except Exception as e:
                logger.error(f"Background task failed: {e}", category="system")
                tree = []

            def _deliver():
                self._vault_creators_model.set_pending(tree)
                self.asyncResultReady.emit(request_id, {"count": len(tree)})
            try:
                self._callOnGui.emit(_deliver)
            except RuntimeError:
                pass      # the app is closing
        threading.Thread(target=_job, daemon=True, name=f"async:{request_id[:24]}").start()

    @Property(int, notify=AppBridgeSignalsMixin.linkVaultChanged)
    def linkVaultTotalLinks(self) -> int:
        from core.link_vault_manager import link_vault_manager
        return len(link_vault_manager.data.get("links", []))

    @Property(int, notify=AppBridgeSignalsMixin.linkVaultChanged)
    def linkVaultTotalCreators(self) -> int:
        from core.link_vault_manager import link_vault_manager
        return len(link_vault_manager.data.get("creators", {}))

    @Property(bool, notify=AppBridgeSignalsMixin.linkVaultChanged)
    def linkVaultProbingActive(self) -> bool:
        from core.link_vault_manager import link_vault_manager
        return link_vault_manager._probing_active

    @Property(bool, notify=AppBridgeSignalsMixin.linkVaultChanged)
    def linkVaultHarvestingActive(self) -> bool:
        return self._vault_harvesting

    @Property(str, notify=AppBridgeSignalsMixin.linkVaultChanged)
    def linkVaultHarvestingStatus(self) -> str:
        return self._vault_harvest_status

    @Property(bool, notify=AppBridgeSignalsMixin.storagePoolChanged)
    def storagePoolEnabled(self) -> bool:
        from core.storage_pool_manager import storage_pool_manager
        return storage_pool_manager.enabled

    @Property(float, notify=AppBridgeSignalsMixin.storagePoolChanged)
    def storagePoolMarginGB(self) -> float:
        from core.storage_pool_manager import storage_pool_manager
        return storage_pool_manager.safety_margin_gb

    @Property(str, notify=AppBridgeSignalsMixin.storagePoolChanged)
    def storagePoolStatusJson(self) -> str:
        from core.storage_pool_manager import storage_pool_manager
        return json.dumps(storage_pool_manager.get_pool_status(), ensure_ascii=False)

    @Property(str, notify=AppBridgeSignalsMixin.cookieWatchdogChanged)
    def cookieWatchdogStatus(self) -> str:
        from services.cookie_importer import browser_cookie_importer
        info = browser_cookie_importer.calculate_expiration_info(self._cookie_string)
        return info.get("status", "missing")

    @Property(str, notify=AppBridgeSignalsMixin.cookieWatchdogChanged)
    def cookieWatchdogText(self) -> str:
        from services.cookie_importer import browser_cookie_importer
        info = browser_cookie_importer.calculate_expiration_info(self._cookie_string)
        return info.get("status_text", "")

    @Property(str, notify=AppBridgeSignalsMixin.cookieWatchdogChanged)
    def cookieWatchdogColor(self) -> str:
        from services.cookie_importer import browser_cookie_importer
        info = browser_cookie_importer.calculate_expiration_info(self._cookie_string)
        return info.get("color", "#94A3B8")

    @Property('QVariant', notify=AppBridgeSignalsMixin.cookieWatchdogChanged)
    def detectedBrowsersList(self):
        from services.cookie_importer import browser_cookie_importer
        return browser_cookie_importer.get_supported_browsers()

    @Property(bool, notify=AppBridgeSignalsMixin.schedulerChanged)
    def schedulerEnabled(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.enabled

    @Property(bool, notify=AppBridgeSignalsMixin.schedulerChanged)
    def schedulerLockThreadsDelay(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.lock_threads_delay

    @Property(bool, notify=AppBridgeSignalsMixin.schedulerChanged)
    def schedulerNightOwlEnabled(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.night_owl_enabled

    @Property(str, notify=AppBridgeSignalsMixin.schedulerChanged)
    def schedulerNightOwlStart(self) -> str:
        from core.task_scheduler import task_scheduler
        return task_scheduler.night_owl_start

    @Property(str, notify=AppBridgeSignalsMixin.schedulerChanged)
    def schedulerNightOwlEnd(self) -> str:
        from core.task_scheduler import task_scheduler
        return task_scheduler.night_owl_end

    @Property(bool, notify=AppBridgeSignalsMixin.schedulerChanged)
    def schedulerPreventSleep(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.prevent_sleep

    @Property(bool, notify=AppBridgeSignalsMixin.schedulerChanged)
    def schedulerSweepRetry(self) -> bool:
        from core.task_scheduler import task_scheduler
        return task_scheduler.sweep_retry

    @Property(str, notify=AppBridgeSignalsMixin.schedulerChanged)
    def schedulerSchedulesJson(self) -> str:
        from core.task_scheduler import task_scheduler
        return json.dumps(task_scheduler.schedules, ensure_ascii=False)

    @Slot(result="QVariantList")
    def getHarvestedLinks(self):
        return self.downloader.harvested_links_records

    @Slot(result="QVariantList")
    def getDownloadHistory(self):
        """Return download history as a list of dicts for the History tab."""
        return self.session_manager.get_download_history()

    @Property(bool, notify=AppBridgeSignalsMixin.telegramSafetyAcknowledgedChanged)
    def telegramSafetyAcknowledged(self) -> bool:
        return self._telegram_safety_acknowledged

    @telegramSafetyAcknowledged.setter
    def telegramSafetyAcknowledged(self, val: bool):
        if self._telegram_safety_acknowledged != val:
            self._telegram_safety_acknowledged = val
            self.telegramSafetyAcknowledgedChanged.emit()
            self.scheduleSaveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.telegramLiabilityAcknowledgedChanged)
    def telegramLiabilityAcknowledged(self) -> bool:
        return self._telegram_liability_acknowledged

    @telegramLiabilityAcknowledged.setter
    def telegramLiabilityAcknowledged(self, val: bool):
        if self._telegram_liability_acknowledged != val:
            self._telegram_liability_acknowledged = val
            self.telegramLiabilityAcknowledgedChanged.emit()
            self.scheduleSaveSettings()

    @Slot(bool)
    def setTelegramSafetyAcknowledged(self, val: bool):
        self.telegramSafetyAcknowledged = val

    @Slot(bool)
    def setTelegramLiabilityAcknowledged(self, val: bool):
        self.telegramLiabilityAcknowledged = val

    @Slot()
    def resetTelegramWarnings(self):
        self._telegram_safety_acknowledged = False
        self._telegram_liability_acknowledged = False
        self.telegramSafetyAcknowledgedChanged.emit()
        self.telegramLiabilityAcknowledgedChanged.emit()
        self.scheduleSaveSettings()
        logger.info("Telegram warning modals reset.", category="telegram")
