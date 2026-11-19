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



class SettingsPropsCoreMixin(AppBridgeSignalsMixin):
    @Property(bool, notify=AppBridgeSignalsMixin.isScanningChanged)
    def isScanning(self) -> bool:
        return self._is_scanning

    @Property(str, notify=AppBridgeSignalsMixin.scanProgressChanged)
    def scanPhaseText(self) -> str:
        return self._scan_phase_text

    @Property(int, notify=AppBridgeSignalsMixin.scanProgressChanged)
    def scanProgressCurrent(self) -> int:
        return self._scan_progress_current

    @Property(int, notify=AppBridgeSignalsMixin.scanProgressChanged)
    def scanProgressTotal(self) -> int:
        return self._scan_progress_total

    @Property(bool, notify=AppBridgeSignalsMixin.hasPendingDownloadSettingsChangesChanged)
    def hasPendingDownloadSettingsChanges(self) -> bool:
        return self._has_pending_download_settings_changes

    @Property(str, notify=AppBridgeSignalsMixin.pendingSettingsDiffSummaryChanged)
    def pendingSettingsDiffSummary(self) -> str:
        return self._pending_settings_diff_summary

    @Property(bool, notify=AppBridgeSignalsMixin.isApplyingMidDownloadSettingsChanged)
    def isApplyingMidDownloadSettings(self) -> bool:
        return self._is_applying_mid_download

    @Property(str, notify=AppBridgeSignalsMixin.midDownloadApplyStatusTextChanged)
    def midDownloadApplyStatusText(self) -> str:
        return self._mid_download_apply_status_text

    def _update_scan_progress(
        self,
        phase_text: str,
        current: int = 0,
        total: int = 0,
        force: bool = False,
        gen: Optional[int] = None,
        active: Optional[bool] = None,
        update_status_text: bool = True,
    ) -> None:
        """Updates throttled scan phase & progress safely from any worker thread."""
        if gen is not None and gen != self._scan_ui_gen:
            return
        now = time.monotonic()
        if not force and active is None and (now - self._last_scan_ui_emit) < 0.25:
            return
        self._last_scan_ui_emit = now

        def _apply():
            if gen is not None and gen != self._scan_ui_gen:
                return
            if active is not None and self._is_scanning != bool(active):
                self._is_scanning = bool(active)
                self.isScanningChanged.emit()
            c_int = max(0, int(current or 0))
            t_int = max(0, int(total or 0))
            if (
                self._scan_phase_text != phase_text
                or self._scan_progress_current != c_int
                or self._scan_progress_total != t_int
            ):
                self._scan_phase_text = phase_text
                self._scan_progress_current = c_int
                self._scan_progress_total = t_int
                self.scanProgressChanged.emit()
            if update_status_text and phase_text and self._status_text != phase_text:
                self._status_text = phase_text
                self.statusTextChanged.emit()

        if QThread.currentThread() is self.thread():
            _apply()
        else:
            self._callOnGui.emit(_apply)

    @Slot()
    def cancelScan(self):
        """Cancels any active creator metadata/post scan without affecting other completed items."""
        self._scan_cancel_event.set()
        self._scan_ui_gen += 1
        self._update_scan_progress("", 0, 0, force=True, active=False, update_status_text=False)
        if not self.downloader.is_running:
            self._status_text = "Progress: Scan cancelled"
            self.statusTextChanged.emit()

    @Property(str, notify=AppBridgeSignalsMixin.currentUrlChanged)
    def currentUrl(self) -> str:
        return self._current_url

    @currentUrl.setter
    def currentUrl(self, val: str):
        if self._current_url != val:
            self._current_url = val
            self.currentUrlChanged.emit()

            val_clean = val.strip()
            if val_clean:
                parsed = KemonoURLParser.parse(val_clean)
                if parsed.is_valid:
                    initial_name = parsed.user_id if parsed.user_id not in ("bunkr_user", "erome_user") else parsed.domain
                    self._creator_name = initial_name
                    self.creatorNameChanged.emit()
                    threading.Thread(
                        target=self._async_resolve_creator_name,
                        args=(parsed, val_clean),
                        daemon=True
                    ).start()
                    if self._favorite_mode:
                        self.checkFavoriteModeAuth()
                else:
                    self._creator_name = ""
                    self.creatorNameChanged.emit()
            else:
                self._creator_name = ""
                self.creatorNameChanged.emit()

    @Property(bool, notify=AppBridgeSignalsMixin.currentUrlChanged)
    def isTelegramUrl(self) -> bool:
        url = (self._current_url or "").strip()
        if url:
            if re.search(r'(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:me|dog)|telegram\.org)/', url, re.I) or url.startswith("tg://"):
                return True
            parsed = KemonoURLParser.parse(url)
            if parsed.is_valid and parsed.provider == "telegram":
                return True
        if hasattr(self, "downloader") and self.downloader.tasks:
            return any(
                getattr(t, "is_telegram", False) or getattr(t, "service", "") == "telegram" or (t.url and t.url.startswith("tg://"))
                for t in self.downloader.tasks
                if t.status in ("pending", "downloading")
            )
        return False

    @Property(int, notify=AppBridgeSignalsMixin.pageStartChanged)
    def pageStart(self) -> int:
        return self._page_start

    @pageStart.setter
    def pageStart(self, val: int):
        if self._page_start != val:
            self._page_start = max(1, val)
            self.pageStartChanged.emit()

    @Property(int, notify=AppBridgeSignalsMixin.pageEndChanged)
    def pageEnd(self) -> int:
        return self._page_end

    @pageEnd.setter
    def pageEnd(self, val: int):
        if self._page_end != val:
            self._page_end = max(1, val)
            self.pageEndChanged.emit()

    @Property(str, notify=AppBridgeSignalsMixin.downloadDirChanged)
    def downloadDir(self) -> str:
        return self._download_dir

    @downloadDir.setter
    def downloadDir(self, val: str):
        if self._download_dir != val:
            self._download_dir = val
            self.downloadDirChanged.emit()
            self._settings_save_timer.start()
            try:
                from core.storage_pool_manager import storage_pool_manager
                storage_pool_manager.set_primary_dir(val)
                self.storagePoolChanged.emit()
            except Exception:
                pass

    @Property(str, notify=AppBridgeSignalsMixin.filterCharactersChanged)
    def filterCharacters(self) -> str:
        return self._filter_characters

    @filterCharacters.setter
    def filterCharacters(self, val: str):
        if self._filter_characters != val:
            self._filter_characters = val
            self.filterCharactersChanged.emit()

    @Property(str, notify=AppBridgeSignalsMixin.characterScopeChanged)
    def characterScope(self) -> str:
        return self._character_scope

    @characterScope.setter
    def characterScope(self, val: str):
        if self._character_scope != val:
            self._character_scope = val
            self.characterScopeChanged.emit()
            self._settings_save_timer.start()

    @Property(str, notify=AppBridgeSignalsMixin.skipWordsChanged)
    def skipWords(self) -> str:
        return self._skip_words

    @skipWords.setter
    def skipWords(self, val: str):
        if self._skip_words != val:
            self._skip_words = val
            self.skipWordsChanged.emit()
            matched = FilterEngine.match_filter_profile(val)
            if self._filter_profile != matched:
                self._filter_profile = matched
                self.filterProfileChanged.emit()
            self._settings_save_timer.start()

    @Property(str, notify=AppBridgeSignalsMixin.filterProfileChanged)
    def filterProfile(self) -> str:
        return self._filter_profile

    @filterProfile.setter
    def filterProfile(self, val: str):
        if self._filter_profile != val:
            self.applyFilterProfile(val)

    @Slot(str)
    def applyFilterProfile(self, profile_key: str):
        """Applies a preset filter profile or clears keywords."""
        if profile_key == "clear":
            self._filter_profile = "clear"
            self.filterProfileChanged.emit()
            self.skipWords = ""
        elif profile_key in FILTER_PROFILES:
            self._filter_profile = profile_key
            self.filterProfileChanged.emit()
            self.skipWords = FILTER_PROFILES[profile_key]["keywords"]
        elif profile_key == "custom":
            self._filter_profile = "custom"
            self.filterProfileChanged.emit()
            self._settings_save_timer.start()

    @Slot(str)
    def appendKeywordsToSkip(self, keywords: str):
        """Appends comma-separated keywords to skipWords without duplicates."""
        if not keywords:
            return
        current_tokens = [t.strip() for t in self._skip_words.split(",") if t.strip()]
        current_lower = {t.lower() for t in current_tokens}
        new_tokens = [t.strip() for t in keywords.split(",") if t.strip()]
        added = False
        for token in new_tokens:
            if token.lower() not in current_lower:
                current_tokens.append(token)
                current_lower.add(token.lower())
                added = True
        if added:
            self.skipWords = ", ".join(current_tokens)

    @Property(str, notify=AppBridgeSignalsMixin.skipScopeChanged)
    def skipScope(self) -> str:
        return self._skip_scope

    @skipScope.setter
    def skipScope(self, val: str):
        if self._skip_scope != val:
            self._skip_scope = val
            self.skipScopeChanged.emit()
            self._settings_save_timer.start()

    @Property(str, notify=AppBridgeSignalsMixin.removeWordsChanged)
    def removeWords(self) -> str:
        return self._remove_words

    @removeWords.setter
    def removeWords(self, val: str):
        if self._remove_words != val:
            self._remove_words = val
            self.removeWordsChanged.emit()
            matched = FilterEngine.match_remove_words_profile(val)
            if self._remove_words_profile != matched:
                self._remove_words_profile = matched
                self.removeWordsProfileChanged.emit()
            self._settings_save_timer.start()

    @Property(str, notify=AppBridgeSignalsMixin.removeWordsProfileChanged)
    def removeWordsProfile(self) -> str:
        return self._remove_words_profile

    @removeWordsProfile.setter
    def removeWordsProfile(self, val: str):
        if self._remove_words_profile != val:
            self.applyRemoveWordsProfile(val)

    @Slot(str)
    def applyRemoveWordsProfile(self, profile_key: str):
        """Applies a preset remove words profile or clears keywords."""
        if profile_key == "clear":
            self._remove_words_profile = "clear"
            self.removeWordsProfileChanged.emit()
            self.removeWords = ""
        elif profile_key in REMOVE_WORDS_PROFILES:
            self._remove_words_profile = profile_key
            self.removeWordsProfileChanged.emit()
            self.removeWords = REMOVE_WORDS_PROFILES[profile_key]["keywords"]
        elif profile_key == "custom":
            self._remove_words_profile = "custom"
            self.removeWordsProfileChanged.emit()
            self._settings_save_timer.start()

    @Slot(str)
    def appendKeywordsToRemove(self, keywords: str):
        """Appends comma-separated keywords to removeWords without duplicates."""
        if not keywords:
            return
        current_tokens = [t.strip() for t in self._remove_words.split(",") if t.strip()]
        current_lower = {t.lower() for t in current_tokens}
        new_tokens = [t.strip() for t in keywords.split(",") if t.strip()]
        added = False
        for token in new_tokens:
            if token.lower() not in current_lower:
                current_tokens.append(token)
                current_lower.add(token.lower())
                added = True
        if added:
            self.removeWords = ", ".join(current_tokens)

    @Property(str, notify=AppBridgeSignalsMixin.dateAfterChanged)
    def dateAfter(self) -> str:
        return self._date_after

    @dateAfter.setter
    def dateAfter(self, val: str):
        if self._date_after != val:
            self._date_after = val
            self.dateAfterChanged.emit()

    @Property(str, notify=AppBridgeSignalsMixin.dateBeforeChanged)
    def dateBefore(self) -> str:
        return self._date_before

    @dateBefore.setter
    def dateBefore(self, val: str):
        if self._date_before != val:
            self._date_before = val
            self.dateBeforeChanged.emit()

    @Property(bool, notify=AppBridgeSignalsMixin.dateAutoScanPagesChanged)
    def dateAutoScanPages(self) -> bool:
        return self._date_auto_scan_pages

    @dateAutoScanPages.setter
    def dateAutoScanPages(self, val: bool):
        if self._date_auto_scan_pages != val:
            self._date_auto_scan_pages = val
            self.dateAutoScanPagesChanged.emit()
            self.saveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.minFileSizeChanged)
    def minFileSize(self) -> str:
        return self._min_file_size

    @minFileSize.setter
    def minFileSize(self, val: str):
        if self._min_file_size != val:
            self._min_file_size = val
            self.minFileSizeChanged.emit()
            self.saveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.maxFileSizeChanged)
    def maxFileSize(self) -> str:
        return self._max_file_size

    @maxFileSize.setter
    def maxFileSize(self, val: str):
        if self._max_file_size != val:
            self._max_file_size = val
            self.maxFileSizeChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.videoDurationFilterEnabledChanged)
    def videoDurationFilterEnabled(self) -> bool:
        return self._video_duration_filter_enabled

    @videoDurationFilterEnabled.setter
    def videoDurationFilterEnabled(self, val: bool):
        if self._video_duration_filter_enabled != bool(val):
            self._video_duration_filter_enabled = bool(val)
            self.videoDurationFilterEnabledChanged.emit()
            self.videoDurationSummaryChanged.emit()
            self.saveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.minVideoDurationChanged)
    def minVideoDuration(self) -> str:
        return self._min_video_duration

    @minVideoDuration.setter
    def minVideoDuration(self, val: str):
        if self._min_video_duration != val:
            self._min_video_duration = val
            self.minVideoDurationChanged.emit()
            self.videoDurationSummaryChanged.emit()
            self.saveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.maxVideoDurationChanged)
    def maxVideoDuration(self) -> str:
        return self._max_video_duration

    @maxVideoDuration.setter
    def maxVideoDuration(self, val: str):
        if self._max_video_duration != val:
            self._max_video_duration = val
            self.maxVideoDurationChanged.emit()
            self.videoDurationSummaryChanged.emit()
            self.saveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.videoDurationSummaryChanged)
    def videoDurationSummary(self) -> str:
        if not self._video_duration_filter_enabled:
            return "Off"
        min_sec = FilterEngine.parse_duration_seconds(self._min_video_duration)
        max_sec = FilterEngine.parse_duration_seconds(self._max_video_duration)
        min_s = FilterEngine.format_duration_str(min_sec) if min_sec is not None else ""
        max_s = FilterEngine.format_duration_str(max_sec) if max_sec is not None else ""
        if min_s and max_s:
            return f"{min_s} – {max_s}"
        elif min_s:
            return f"≥ {min_s}"
        elif max_s:
            return f"≤ {max_s}"
        return "Active (No limits)"

    @Property(int, notify=AppBridgeSignalsMixin.currentFpsChanged)
    def currentFps(self) -> int:
        return self._current_fps

    @Slot(int)
    def setCurrentFps(self, val: int):
        if self._current_fps != val:
            self._current_fps = val
            self.currentFpsChanged.emit()

    @Property(int, notify=AppBridgeSignalsMixin.screenHzChanged)
    def screenHz(self) -> int:
        return self._screen_hz

    @Slot(int)
    def setScreenHz(self, val: int):
        if self._screen_hz != val:
            self._screen_hz = val
            self.screenHzChanged.emit()

    @Property(str, notify=AppBridgeSignalsMixin.filterTypeChanged)
    def filterType(self) -> str:
        return self._filter_type

    @filterType.setter
    def filterType(self, val: str):
        if self._filter_type != val:
            self._filter_type = val
            self.filterTypeChanged.emit()

    @Property(str, notify=AppBridgeSignalsMixin.exactExtensionsChanged)
    def exactExtensions(self) -> str:
        return self._exact_extensions

    @exactExtensions.setter
    def exactExtensions(self, val: str):
        val_clean = str(val or "").strip()
        if self._exact_extensions != val_clean:
            self._exact_extensions = val_clean
            self.exactExtensionsChanged.emit()
            self.saveSettings()

    @Slot(str)
    def toggleExactExtension(self, ext: str):
        """Toggles an extension (e.g. '.zip' or 'zip' or '*.zip') in the active comma-separated list."""
        ext = ext.strip().lower().lstrip("*")
        if not ext.startswith("."):
            ext = "." + ext
        tokens = [t.strip().lower().lstrip("*") for t in re.split(r'[,;\s]+', self._exact_extensions) if t.strip()]
        norm_tokens = [(t if t.startswith(".") else "." + t) for t in tokens if t]
        unique_tokens = []
        for t in norm_tokens:
            if t not in unique_tokens:
                unique_tokens.append(t)
        if ext in unique_tokens:
            unique_tokens = [t for t in unique_tokens if t != ext]
        else:
            unique_tokens.append(ext)
        self.exactExtensions = ", ".join(unique_tokens)

    @Slot(str, result=bool)
    def isExactExtensionActive(self, ext: str) -> bool:
        """Returns True if the specified extension is in the current exact extensions list."""
        if not self._exact_extensions:
            return False
        ext = ext.strip().lower()
        if not ext.startswith("."):
            ext = "." + ext
        allowed = FilterEngine.parse_extensions_list(self._exact_extensions)
        return ext in allowed

    @Slot()
    def clearExactExtensions(self):
        """Clears all exact extension filters."""
        self.exactExtensions = ""

    @Property('QVariantList', notify=AppBridgeSignalsMixin.exactExtensionsChanged)
    def activeExtensionsList(self) -> list:
        """Returns the list of currently active extensions in sorted order."""
        if not self._exact_extensions:
            return []
        parsed = FilterEngine.parse_extensions_list(self._exact_extensions)
        return sorted(list(parsed))

    @Property('QVariantList', notify=AppBridgeSignalsMixin.savedCustomExtensionsChanged)
    def savedCustomExtensions(self) -> list:
        """Returns the list of saved custom extensions."""
        return self._saved_custom_extensions

    @Slot(str)
    def addSavedCustomExtension(self, ext: str):
        """Adds one or more custom extensions (comma/space separated) to the permanent saved list and activates them."""
        if not ext:
            return
        tokens = FilterEngine.parse_extensions_list(ext)
        if not tokens:
            return
        changed = False
        for t in sorted(tokens):
            if t not in self._saved_custom_extensions:
                self._saved_custom_extensions.append(t)
                changed = True
            if not self.isExactExtensionActive(t):
                self.toggleExactExtension(t)
        if changed:
            self.savedCustomExtensionsChanged.emit()
            self.saveSettings()

    @Slot(str)
    def removeSavedCustomExtension(self, ext: str):
        """Removes a custom extension from the permanent saved list."""
        if not ext:
            return
        ext = ext.strip().lower().lstrip("*")
        if not ext.startswith("."):
            ext = "." + ext
        if ext in self._saved_custom_extensions:
            self._saved_custom_extensions.remove(ext)
            self.savedCustomExtensionsChanged.emit()
            self.saveSettings()
        if self.isExactExtensionActive(ext):
            self.toggleExactExtension(ext)

    @Property(bool, notify=AppBridgeSignalsMixin.skipArchivesChanged)
    def skipArchives(self) -> bool:
        return self._skip_archives

    @skipArchives.setter
    def skipArchives(self, val: bool):
        if self._skip_archives != val:
            self._skip_archives = val
            self.skipArchivesChanged.emit()

    @Property(bool, notify=AppBridgeSignalsMixin.downloadThumbnailsOnlyChanged)
    def downloadThumbnailsOnly(self) -> bool:
        return self._download_thumbnails_only

    @downloadThumbnailsOnly.setter
    def downloadThumbnailsOnly(self, val: bool):
        if self._download_thumbnails_only != val:
            self._download_thumbnails_only = val
            self.downloadThumbnailsOnlyChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.fallbackToThumbnailsChanged)
    def fallbackToThumbnails(self) -> bool:
        return self._fallback_to_thumbnails

    @fallbackToThumbnails.setter
    def fallbackToThumbnails(self, val: bool):
        if self._fallback_to_thumbnails != val:
            self._fallback_to_thumbnails = val
            self.fallbackToThumbnailsChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.hideUnimportedNoticeChanged)
    def hideUnimportedNotice(self) -> bool:
        return self._hide_unimported_notice

    @hideUnimportedNotice.setter
    def hideUnimportedNotice(self, val: bool):
        val_b = bool(val)
        if self._hide_unimported_notice != val_b:
            self._hide_unimported_notice = val_b
            self.hideUnimportedNoticeChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.redownloadSmallFilesChanged)
    def redownloadSmallFiles(self) -> bool:
        return self._redownload_small_files

    @redownloadSmallFiles.setter
    def redownloadSmallFiles(self, val: bool):
        if self._redownload_small_files != val:
            self._redownload_small_files = val
            self.redownloadSmallFilesChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.skipPostCoversChanged)
    def skipPostCovers(self) -> bool:
        return self._skip_post_covers

    @skipPostCovers.setter
    def skipPostCovers(self, val: bool):
        if self._skip_post_covers != val:
            self._skip_post_covers = val
            self.skipPostCoversChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.scanContentImagesChanged)
    def scanContentImages(self) -> bool:
        return self._scan_content_images

    @scanContentImages.setter
    def scanContentImages(self, val: bool):
        if self._scan_content_images != val:
            self._scan_content_images = val
            self.scanContentImagesChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=AppBridgeSignalsMixin.downloadDmsChanged)
    def downloadDms(self) -> bool:
        return self._download_dms

    @downloadDms.setter
    def downloadDms(self, val: bool):
        if self._download_dms != val:
            self._download_dms = val
            self.downloadDmsChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=AppBridgeSignalsMixin.downloadPawchiveTemporaryFilesChanged)
    def downloadPawchiveTemporaryFiles(self) -> bool:
        return self._download_pawchive_temporary_files

    @downloadPawchiveTemporaryFiles.setter
    def downloadPawchiveTemporaryFiles(self, val: bool):
        if self._download_pawchive_temporary_files != val:
            self._download_pawchive_temporary_files = val
            self.downloadPawchiveTemporaryFilesChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.compressWebpChanged)
    def compressWebp(self) -> bool:
        return self._compress_webp

    @compressWebp.setter
    def compressWebp(self, val: bool):
        if self._compress_webp != val:
            self._compress_webp = val
            self.compressWebpChanged.emit()
            self._settings_save_timer.start()

    @Property(str, notify=AppBridgeSignalsMixin.webpQualityChanged)
    def webpQuality(self) -> str:
        """How strongly "Compress to WebP" compresses: lossless / high / balanced / small / smallest."""
        return self._webp_quality

    @webpQuality.setter
    def webpQuality(self, val: str):
        from core.filter_engine import WEBP_QUALITY_LEVELS
        val = str(val or "").lower()
        if val not in WEBP_QUALITY_LEVELS:
            val = "balanced"
        if self._webp_quality != val:
            self._webp_quality = val
            self.webpQualityChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=AppBridgeSignalsMixin.writeAudioMetadataChanged)
    def writeAudioMetadata(self) -> bool:
        return self._write_audio_metadata

    @writeAudioMetadata.setter
    def writeAudioMetadata(self, val: bool):
        if self._write_audio_metadata != val:
            self._write_audio_metadata = val
            self.writeAudioMetadataChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.keepDuplicatesChanged)
    def keepDuplicates(self) -> bool:
        return self._keep_duplicates

    @keepDuplicates.setter
    def keepDuplicates(self, val: bool):
        if self._keep_duplicates != val:
            self._keep_duplicates = val
            self.keepDuplicatesChanged.emit()
            self._settings_save_timer.start()

    @Property(bool, notify=AppBridgeSignalsMixin.favoriteModeChanged)
    def favoriteMode(self) -> bool:
        return self._favorite_mode

    @favoriteMode.setter
    def favoriteMode(self, val: bool):
        if val:
            if not self.checkFavoriteModeAuth():
                return
        if self._favorite_mode != val:
            self._favorite_mode = val
            self.favoriteModeChanged.emit()

    @Property(bool, notify=AppBridgeSignalsMixin.favoriteArtistsLoadingChanged)
    def favoriteArtistsLoading(self) -> bool:
        return getattr(self, "_is_favorite_artists_loading", False)

    def get_provider_for_domain(self, domain_or_url: str) -> str:
        d = (domain_or_url or "").lower()
        if "coomer" in d:
            return "coomer"
        if "pawchive" in d:
            return "pawchive"
        if "cum.st" in d or "cumst" in d:
            return "cumst"
        return "pawchive"

    @Slot(result=bool)
    def checkFavoriteModeAuth(self) -> bool:
        """
        Validates whether the user has a valid Pawchive or cum.st account connected for Favorite Mode.
        Favorite Mode requires a connected Pawchive or cum.st account.
        If not authenticated, emits favoriteAuthRequired("Pawchive or cum.st") and returns False.
        """
        from core.auth_manager import auth_manager
        pawchive_logged_in = auth_manager.is_logged_in("pawchive")
        cumst_logged_in = auth_manager.is_logged_in("cumst")
        if not pawchive_logged_in and not cumst_logged_in:
            logger.warning("⭐ Favorite Mode requires a connected Pawchive or cum.st account.", category="auth")
            self.favoriteAuthRequired.emit("Pawchive")
            if self._favorite_mode:
                self._favorite_mode = False
                self.favoriteModeChanged.emit()
            return False

        return True
