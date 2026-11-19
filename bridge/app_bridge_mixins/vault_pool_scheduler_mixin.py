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



class VaultPoolSchedulerMixin(AppBridgeSignalsMixin):
    @Slot(str, str)
    def refreshLinkVault(self, search: str = "", platform: str = ""):
        self._vault_search = search
        self._vault_platform = platform
        self.linkVaultChanged.emit()

    @Slot(str, result=bool)
    def deleteVaultLink(self, linkId: str) -> bool:
        from core.link_vault_manager import link_vault_manager
        res = link_vault_manager.delete_link(linkId)
        if res:
            self.linkVaultChanged.emit()
        return res

    @Slot(str, 'QVariant', result=bool)
    def updateVaultLinkPasswords(self, linkId: str, passwords) -> bool:
        from core.link_vault_manager import link_vault_manager
        pw_list = []
        if isinstance(passwords, str):
            pw_list = [p.strip() for p in passwords.split(",") if p.strip()]
        elif isinstance(passwords, (list, tuple)):
            pw_list = [str(p).strip() for p in passwords if str(p).strip()]
        res = link_vault_manager.update_link_passwords(linkId, pw_list)
        if res:
            self.linkVaultChanged.emit()
        return res

    @Slot(str, result=bool)
    def deleteVaultPost(self, postId: str) -> bool:
        from core.link_vault_manager import link_vault_manager
        res = link_vault_manager.delete_post(postId)
        if res:
            self.linkVaultChanged.emit()
        return res

    @Slot(str, result=bool)
    def deleteVaultCreator(self, creatorKey: str) -> bool:
        from core.link_vault_manager import link_vault_manager
        res = link_vault_manager.delete_creator(creatorKey)
        if res:
            self.linkVaultChanged.emit()
        return res

    @Slot(result=int)
    def cleanDeadVaultLinks(self) -> int:
        from core.link_vault_manager import link_vault_manager
        count = link_vault_manager.clean_dead_links()
        self.linkVaultChanged.emit()
        return count

    @Slot(str, result=int)
    @Slot(result=int)
    def copyVaultLinks(self, creatorKey: str = "") -> int:
        from core.link_vault_manager import link_vault_manager
        urls = link_vault_manager.get_all_link_urls(creatorKey)
        if urls:
            self.copyToClipboard("\n".join(urls))
        return len(urls)

    @Slot(str, result=int)
    def exportVaultToFolder(self, folderPath: str) -> int:
        from core.link_vault_manager import link_vault_manager
        clean_path = folderPath or ""
        if clean_path.startswith("file:"):
            clean_path = QUrl(clean_path).toLocalFile()
        clean_path = os.path.normpath(clean_path)
        return link_vault_manager.export_all_to_folder(clean_path)

    @Slot()
    def probeVaultHealth(self):
        from core.link_vault_manager import link_vault_manager
        self.linkVaultProbingStarted.emit()
        def _on_done(done, total, url):
            self.linkVaultChanged.emit()
        def _on_complete():
            self.linkVaultChanged.emit()
            self.linkVaultProbingFinished.emit()
        link_vault_manager.probe_all_links_async(
            progress_callback=_on_done,
            completion_callback=_on_complete
        )

    @Slot(str, bool, int, int)
    def harvestArtistToVault(self, url: str, probeHealth: bool = True, pageStart: int = 1, pageEnd: int = 999999):
        clean_url = (url or "").strip()
        if not clean_url:
            self.vaultHarvestFinished.emit(False, "", 0, 0)
            return
        if self._vault_harvesting:
            logger.warning("Artist harvesting to Link Vault is already running.", category="vault")
            return

        def _worker():
            self._vault_harvesting = True
            self._vault_harvest_cancel.clear()
            self._vault_harvest_status = "Connecting..."
            self.linkVaultChanged.emit()

            try:
                parsed = KemonoURLParser.parse(clean_url)
                if not parsed.is_valid:
                    logger.error(f"Link Vault Harvest: Invalid artist URL '{clean_url}'", category="vault")
                    self.vaultHarvestFinished.emit(False, "Invalid URL", 0, 0)
                    return
                if self._refuse_if_disabled(clean_url):
                    self.vaultHarvestFinished.emit(False, "Site turned off", 0, 0)
                    return

                # Fetch artist profile
                profile = self.api_client.fetch_creator_profile(parsed)
                creator_name = clean_text(profile.get("name", parsed.user_id) or parsed.user_id)
                creator_key = f"{parsed.service}:{parsed.user_id}".lower()

                self._vault_harvest_status = f"Scanning posts for {creator_name}..."
                self.linkVaultChanged.emit()
                self.vaultHarvestStarted.emit(creator_name)

                # Fetch all posts in range
                if parsed.is_single_post:
                    single = self.api_client.fetch_single_post(parsed)
                    posts = [single] if single else []
                else:
                    if parsed.is_dms:
                        posts = self.api_client.fetch_user_dms(
                            parsed=parsed,
                            page_start=pageStart,
                            page_end=pageEnd,
                            cancel_event=self._vault_harvest_cancel
                        )
                    else:
                        posts = self.api_client.fetch_user_posts(
                            parsed=parsed,
                            page_start=pageStart,
                            page_end=pageEnd,
                            cancel_event=self._vault_harvest_cancel
                        )

                if self._vault_harvest_cancel.is_set():
                    logger.warning(f"Link Vault Harvest: Cancelled during post fetch for {creator_name}.", category="vault")
                    self.vaultHarvestFinished.emit(False, creator_name, 0, len(posts))
                    return

                if not posts:
                    logger.info(f"Link Vault Harvest: No posts found for {creator_name}.", category="vault")
                    self.vaultHarvestFinished.emit(True, creator_name, 0, 0)
                    return

                # Process posts into vault records
                harvested_posts = []
                total_links_found = 0
                for idx, p in enumerate(posts):
                    if self._vault_harvest_cancel.is_set():
                        break

                    rec = LinkExtractor.extract_post_vault_record(
                        post=p,
                        api_client=self.api_client,
                        domain=parsed.domain,
                        service=parsed.service,
                        user_id=parsed.user_id
                    )
                    if rec and rec.get("links"):
                        harvested_posts.append(rec)
                        total_links_found += len(rec["links"])

                    if (idx + 1) % 10 == 0 or idx == len(posts) - 1:
                        status_msg = f"Processed {idx + 1}/{len(posts)} posts ({total_links_found} links found)"
                        self._vault_harvest_status = status_msg
                        self.linkVaultChanged.emit()
                        self.vaultHarvestProgress.emit(status_msg, idx + 1, total_links_found)

                if self._vault_harvest_cancel.is_set():
                    logger.warning(f"Link Vault Harvest: Cancelled during link extraction for {creator_name}.", category="vault")
                    self.vaultHarvestFinished.emit(False, creator_name, 0, len(posts))
                    return

                # Store harvested posts into Link Vault
                from core.link_vault_manager import link_vault_manager
                new_links_count = link_vault_manager.add_harvested_data(
                    creator_name=creator_name,
                    service=parsed.service,
                    user_id=parsed.user_id,
                    harvested_posts=harvested_posts
                )
                self.linkVaultChanged.emit()

                # Optionally probe links health
                if probeHealth and new_links_count > 0 and not self._vault_harvest_cancel.is_set():
                    self._vault_harvest_status = f"Probing links for {creator_name}..."
                    self.linkVaultChanged.emit()
                    self.linkVaultProbingStarted.emit()
                    def _on_probe_progress(done, tot, u):
                        self.linkVaultChanged.emit()
                    def _on_probe_complete():
                        self.linkVaultChanged.emit()
                        self.linkVaultProbingFinished.emit()
                    link_vault_manager.probe_all_links_async(
                        progress_callback=_on_probe_progress,
                        cancel_event=self._vault_harvest_cancel,
                        creator_key=creator_key,
                        completion_callback=_on_probe_complete
                    )

                logger.success(
                    f"Link Vault: Finished harvesting {creator_name} ({new_links_count} new links saved from {len(posts)} posts).",
                    category="vault"
                )
                self.vaultHarvestFinished.emit(True, creator_name, new_links_count, len(posts))

            except Exception as e:
                logger.error(f"Link Vault Harvest failed: {e}", category="vault")
                self.vaultHarvestFinished.emit(False, str(e), 0, 0)
            finally:
                self._vault_harvesting = False
                self._vault_harvest_status = ""
                self.linkVaultChanged.emit()

        t = threading.Thread(target=_worker, daemon=True, name="VaultArtistHarvester")
        t.start()

    @Slot()
    def cancelVaultHarvest(self):
        self._vault_harvest_cancel.set()
        self._vault_harvesting = False
        self._vault_harvest_status = "Cancelled"
        self.linkVaultChanged.emit()

    @Slot(result=int)
    def copyPasswordsToDecompressor(self) -> int:
        from core.link_vault_manager import link_vault_manager
        pws = link_vault_manager.get_all_passwords()
        count = len(pws)
        if hasattr(self, "_decompressor_bridge") and self._decompressor_bridge:
            for pw in pws:
                if pw and hasattr(self._decompressor_bridge, "addPassword"):
                    self._decompressor_bridge.addPassword(pw)
        logger.success(f"Copied {count} password(s) from Link Vault to Bulk Decompressor.", category="vault")
        return count

    @Slot(bool)
    def setStoragePoolEnabled(self, enabled: bool):
        from core.storage_pool_manager import storage_pool_manager
        storage_pool_manager.set_enabled(enabled)
        self.storagePoolChanged.emit()

    @Slot(float)
    def setStoragePoolMargin(self, marginGB: float):
        from core.storage_pool_manager import storage_pool_manager
        storage_pool_manager.set_safety_margin(marginGB)
        self.storagePoolChanged.emit()

    @Slot(str, result=bool)
    def addStoragePoolDrive(self, path: str) -> bool:
        from core.storage_pool_manager import storage_pool_manager
        res = storage_pool_manager.add_overflow_dir(path)
        if res:
            self.storagePoolChanged.emit()
        return res

    @Slot(str, result=bool)
    def removeStoragePoolDrive(self, path: str) -> bool:
        from core.storage_pool_manager import storage_pool_manager
        res = storage_pool_manager.remove_overflow_dir(path)
        if res:
            self.storagePoolChanged.emit()
        return res

    @Slot(result=str)
    def selectStoragePoolDirectory(self) -> str:
        folder = _app_bridge_mod().QFileDialog.getExistingDirectory(
            None,
            "Select Storage Overflow Directory",
            ""
        )
        if folder:
            self.addStoragePoolDrive(folder)
            return folder
        return ""

    @Slot()
    def refreshStoragePools(self):
        self.storagePoolChanged.emit()

    @Slot(result=bool)
    @Slot(str, result=bool)
    def importBrowserCookies(self, browserId: str = "") -> bool:
        from services.cookie_importer import browser_cookie_importer
        try:
            res = browser_cookie_importer.import_auto_detect(preferred_browser=browserId or None)
            c_str = res.get("cookie_string", "")
            if c_str:
                self.cookieString = c_str
                self.saveSettings()
                self.cookieWatchdogChanged.emit()
                self.cookieImportCompleted.emit(True, res.get("browser_name", "Browser"))
                return True
        except Exception as e:
            logger.error(f"Browser cookie import failed: {e}", category="cookie")
            self.cookieImportCompleted.emit(False, str(e))
        return False

    @Slot()
    def refreshCookieWatchdog(self):
        self.cookieWatchdogChanged.emit()

    @Slot(result=list)
    def getProvidersList(self) -> list:
        from core.auth_manager import auth_manager
        return auth_manager.get_all_providers_summary()

    @Slot(str, str, result=bool)
    def saveProviderCredential(self, providerId: str, credVal: str) -> bool:
        from core.auth_manager import auth_manager, SUPPORTED_PROVIDERS
        meta = SUPPORTED_PROVIDERS.get(providerId, {})
        auth_type = meta.get("auth_type", "cookie")
        key = "cookie" if auth_type == "cookie" else ("token" if auth_type == "token" else ("api_key" if auth_type == "api_key" else "cookie"))

        ok = auth_manager.set_credential(providerId, {key: credVal.strip()})
        if providerId == "kemono":
            self.cookieString = credVal.strip()
            self.saveSettings()
            self.cookieWatchdogChanged.emit()
        self.providersChanged.emit()
        return ok

    @Slot(str, result=bool)
    def clearProviderCredential(self, providerId: str) -> bool:
        from core.auth_manager import auth_manager
        ok = auth_manager.clear_credential(providerId)
        if providerId == "kemono":
            self.cookieString = ""
            self.saveSettings()
            self.cookieWatchdogChanged.emit()
        self.providersChanged.emit()
        return ok

    @Slot(str)
    def validateProviderSession(self, providerId: str):
        def _val_worker():
            from core.auth_manager import auth_manager
            ok, msg, _ = auth_manager.validate_session(providerId)
            self.providerValidationFinished.emit(providerId, ok, msg)
            self.providersChanged.emit()

        threading.Thread(target=_val_worker, daemon=True, name=f"ValWorker_{providerId}").start()

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def importBrowserCookiesToProvider(self, providerId: str, browserId: str = "") -> bool:
        from services.cookie_importer import browser_cookie_importer
        from core.auth_manager import auth_manager
        try:
            res = browser_cookie_importer.import_auto_detect(preferred_browser=browserId or None)
            c_str = res.get("cookie_string", "")
            if c_str:
                auth_manager.set_credential(providerId, {"cookie": c_str})
                if providerId == "kemono":
                    self.cookieString = c_str
                    self.saveSettings()
                self.providersChanged.emit()
                self.cookieWatchdogChanged.emit()
                self.cookieImportCompleted.emit(True, res.get("browser_name", "Browser"))
                return True
        except Exception as e:
            logger.error(f"Browser cookie import to {providerId} failed: {e}", category="cookie")
            self.cookieImportCompleted.emit(False, str(e))
        return False

    @Slot(str, str, str)
    def loginProviderWithCredentials(self, providerId: str, username: str, password: str):
        def _worker():
            from core.auth_manager import auth_manager
            ok, msg, details = auth_manager.login_with_credentials(providerId, username, password)
            self.providerLoginFinished.emit(providerId, ok, msg)
            if ok:
                if providerId == "kemono":
                    c = auth_manager.get_credential("kemono", "cookie")
                    if c:
                        self.cookieString = c
                        self.saveSettings()
                self.providersChanged.emit()

        threading.Thread(target=_worker, daemon=True, name=f"Login_{providerId}").start()

    @Slot(str, str, str, str, int, str, result=str)
    def addSchedulerTask(self, name: str, targetType: str, targetUrl: str, triggerType: str, intervalHours: int, timeOfDay: str) -> str:
        from core.task_scheduler import task_scheduler
        sid = task_scheduler.add_schedule(name, targetType, targetUrl, triggerType, intervalHours, timeOfDay)
        self.schedulerChanged.emit()
        return sid

    @Slot(str, result=bool)
    def deleteSchedulerTask(self, schedId: str) -> bool:
        from core.task_scheduler import task_scheduler
        res = task_scheduler.delete_schedule(schedId)
        if res:
            self.schedulerChanged.emit()
        return res

    @Slot(str, bool, result=bool)
    def toggleSchedulerTask(self, schedId: str, enabled: bool) -> bool:
        from core.task_scheduler import task_scheduler
        res = task_scheduler.toggle_schedule(schedId, enabled)
        if res:
            self.schedulerChanged.emit()
        return res

    @Slot(str, str, str, str, str, int, str, result=bool)
    def updateSchedulerTask(self, schedId: str, name: str, targetType: str, targetUrl: str, triggerType: str, intervalHours: int, timeOfDay: str) -> bool:
        from core.task_scheduler import task_scheduler
        res = task_scheduler.update_schedule(schedId, name, targetType, targetUrl, triggerType, intervalHours, timeOfDay)
        if res:
            self.schedulerChanged.emit()
        return res

    @Slot(bool, bool, bool, str, str, bool, bool)
    def setSchedulerSettings(self, enabled: bool, lockThreads: bool, nightOwl: bool, start: str, end: str, preventSleep: bool, sweepRetry: bool):
        from core.task_scheduler import task_scheduler
        task_scheduler.enabled = enabled
        task_scheduler.lock_threads_delay = lockThreads
        self.threadsLocked = lockThreads
        task_scheduler.night_owl_enabled = nightOwl
        task_scheduler.night_owl_start = start
        task_scheduler.night_owl_end = end
        task_scheduler.prevent_sleep = preventSleep
        task_scheduler.sweep_retry = sweepRetry
        task_scheduler.save()
        self._update_sleep_prevention()
        self.schedulerChanged.emit()

    @Slot()
    def _update_sleep_prevention(self):
        try:
            from core.task_scheduler import task_scheduler
            from core.power import sleep_inhibitor
            sleep_inhibitor.set_active(bool(self._is_downloading and task_scheduler.prevent_sleep))
        except Exception as e:
            logger.debug(f"Sleep prevention update failed: {e}", category="system")

    def _run_scheduled_watchlist_sync(self):
        """Called by the TaskScheduler (in its background thread) when a Watchlist Sync schedule
        triggers: checks every watchlist artist, then downloads their new posts. (It used to only
        count new posts, so nothing was ever downloaded automatically.)"""
        from core.task_scheduler import task_scheduler
        from core.providers import is_disabled
        logger.info("Scheduler: Watchlist Sync — checking all watchlist artists for new posts...", category="scheduler")
        self._async_watchlist_check(wait_if_running=True)    # runs right here, in the scheduler's thread
        updated = [e for e in list(self._watchlist_manager.entries)
                   if (getattr(e, "new_post_count", 0) or 0) > 0 and not is_disabled(e.domain)]
        if not updated:
            logger.info("Scheduler: Watchlist Sync — nothing new to download.", category="scheduler")
            return
        self._scheduled_sweep_retry = bool(task_scheduler.sweep_retry)
        logger.info(f"Scheduler: Watchlist Sync — downloading new posts for {len(updated)} artist(s)...", category="scheduler")
        for e in updated:
            try:
                self._process_watchlist_entry_download(e)
            except Exception as err:
                logger.error(f"Scheduler: could not download updates for {e.creator_name!r}: {err}", category="scheduler")

    def _run_scheduled_creator_sync(self, url: str):
        """Called by the TaskScheduler (background thread) when a Creator schedule triggers.
        The download is started on the GUI thread."""
        if url:
            self._scheduledCreatorSyncSignal.emit(url)

    @Slot(str)
    def _handle_scheduled_creator_sync(self, url: str):
        from core.task_scheduler import task_scheduler
        self._scheduled_sweep_retry = bool(task_scheduler.sweep_retry)
        self.currentUrl = url
        if self._is_downloading:
            # A download is already running: add this creator to it instead of skipping the schedule
            logger.info(f"Scheduler: a download is running — adding '{url}' to the queue.", category="scheduler")
            self.addToQueue()
        else:
            logger.info(f"Scheduler: Initiating automated Creator Sync for '{url}'...", category="scheduler")
            self.startDownload()
