"""
Application Bridge Subsystem
Binds the PySide6/Qt Core engine with the QML User Interface, providing
reactive properties, slots, session persistence, telemetry signals, and async orchestration.
"""

import os
import time
import subprocess
import threading
from typing import Optional, Dict, Any, List
from PySide6.QtCore import QObject, Signal, Property, Slot, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog, QApplication

from core.logger import logger
from core.parser import KemonoURLParser, URLParseResult
from core.filter_engine import FilterEngine, FilterOptions
from core.api_client import KemonoApiClient
from core.downloader import KemonoDownloader, DownloadTask
from core.session_manager import SessionManager
from core.known_manager import KnownManager
from bridge.log_model import LogModel
from bridge.queue_model import QueueModel
from bridge.known_model import KnownModel
from services.batch_loader import BatchLoader
from services.link_extractor import LinkExtractor
from services.text_exporter import TextExporter
from services.bunkr_client import fetch_bunkr_album
from services.erome_client import fetch_erome_album
from services.nhentai_client import fetch_nhentai_gallery
from services.cloud_downloader import (
    download_mega_link,
    download_gdrive_link,
    download_dropbox_link,
    download_gofile_link
)


class AppBridge(QObject):
    # Signals for properties
    currentUrlChanged = Signal()
    pageStartChanged = Signal()
    pageEndChanged = Signal()
    downloadDirChanged = Signal()
    filterCharactersChanged = Signal()
    characterScopeChanged = Signal()
    skipWordsChanged = Signal()
    skipScopeChanged = Signal()
    removeWordsChanged = Signal()
    filterTypeChanged = Signal()
    skipArchivesChanged = Signal()
    downloadThumbnailsOnlyChanged = Signal()
    scanContentImagesChanged = Signal()
    compressWebpChanged = Signal()
    keepDuplicatesChanged = Signal()
    favoriteModeChanged = Signal()
    subfolderPerPostChanged = Signal()
    datePrefixChanged = Signal()
    separateFoldersByKnownChanged = Signal()
    downloadRevisionsChanged = Signal()
    adaptiveThreadingChanged = Signal()
    autoRetryAtEndChanged = Signal()
    mangaModeChanged = Signal()
    filenameStyleChanged = Signal()
    proxyUrlChanged = Signal()
    threadsCountChanged = Signal()
    maxCpuThreadsChanged = Signal()
    cookieStringChanged = Signal()
    userAgentChanged = Signal()
    isDownloadingChanged = Signal()
    statusTextChanged = Signal()
    overallProgressChanged = Signal()
    currentSpeedChanged = Signal()
    etaTextChanged = Signal()
    savedBytesTextChanged = Signal()
    hasSavedSessionChanged = Signal()
    hasErrorChanged = Signal()
    lastErrorMessageChanged = Signal()
    creatorNameChanged = Signal()
    downloadHistoryChanged = Signal()
    adaptiveStatusTextChanged = Signal()
    adaptiveStateChanged = Signal()
    elapsedTimeTextChanged = Signal()
    downloadDelayChanged = Signal()
    savePostMetadataChanged = Signal()
    downloadEmbedsChanged = Signal()
    openFolderOnCompleteChanged = Signal()
    playCompletionSoundChanged = Signal()
    filesCountTextChanged = Signal()
    harvestedLinksChanged = Signal()
    consoleWidthChanged = Signal()

    _progressSignal  = Signal(dict)    # carries progress info dict
    _taskSignal      = Signal(object)  # carries a DownloadTask object
    _finishedSignal  = Signal(bool, str)
    _throttledSignal = Signal(int)     # carries new worker concurrency count
    _creatorSignal   = Signal(str)     # carries resolved creator name
    _setTasksSignal  = Signal(list)    # safely sends new task list to GUI thread

    def __init__(self, parent=None):
        super().__init__(parent)

        # Core systems
        self.known_manager = KnownManager()
        self.session_manager = SessionManager()
        self.downloader = KemonoDownloader(
            known_manager=self.known_manager,
            session_manager=self.session_manager,
            max_workers=4
        )
        self.api_client = KemonoApiClient()

        # Models
        self._log_model = LogModel(self)
        self._queue_model = QueueModel(self)
        self._known_model = KnownModel(self.known_manager, self)

        # Settings defaults
        saved_settings = self.session_manager.load_settings()
        self._current_url = ""
        self._page_start = int(saved_settings.get("page_start", 1))
        self._page_end = int(saved_settings.get("page_end", 999))
        self._download_dir = saved_settings.get("download_dir", os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads"))
        self._filter_characters = ""
        self._character_scope = saved_settings.get("character_scope", "title")
        self._skip_words = ""
        self._skip_scope = saved_settings.get("skip_scope", "posts")
        self._remove_words = ""
        self._filter_type = "all"
        self._skip_archives = False
        self._download_thumbnails_only = False
        self._scan_content_images = saved_settings.get("scan_content_images", True)
        self._compress_webp = saved_settings.get("compress_webp", False)
        self._keep_duplicates = saved_settings.get("keep_duplicates", False)
        self._favorite_mode = False
        self._subfolder_per_post = saved_settings.get("subfolder_per_post", True)
        self._date_prefix = saved_settings.get("date_prefix", True)
        self._separate_folders_by_known = saved_settings.get("separate_by_known", False)
        self._download_revisions = saved_settings.get("download_revisions", False)
        self._adaptive_threading = saved_settings.get("adaptive_threading", False)
        self._auto_retry_at_end = saved_settings.get("auto_retry_at_end", False)
        self._manga_mode = saved_settings.get("manga_mode", False)
        self._filename_style = saved_settings.get("filename_style", "post_title")
        self._proxy_url = saved_settings.get("proxy_url", "")
        self._max_cpu_threads = max(4, os.cpu_count() or 16)
        self._threads_count = int(saved_settings.get("threads", min(8, self._max_cpu_threads)))
        self.downloader.max_workers = self._threads_count
        self._cookie_string = saved_settings.get("cookie", "")
        self._user_agent = saved_settings.get("user_agent", "")
        self._download_delay = float(saved_settings.get("download_delay", 2.0))
        self._save_post_metadata = bool(saved_settings.get("save_post_metadata", True))
        self._download_embeds = bool(saved_settings.get("download_embeds", True))
        self._open_folder_on_complete = bool(saved_settings.get("open_folder_on_complete", False))
        self._play_completion_sound = bool(saved_settings.get("play_completion_sound", False))
        self._console_width = int(saved_settings.get("console_width", 620))
        self._creator_name = ""

        # Scan & Cloud cancellation state
        self._scan_cancel_event = threading.Event()
        self._cloud_cancel_event = threading.Event()
        self._cloud_pause_event = threading.Event()
        self._is_cloud_downloading = False

        # Trigger background auto-check / update for standalone dependencies/yt-dlp.exe
        self.downloader.ytdlp_manager.check_for_updates_async()

        # Status & In-depth Telemetry
        self._is_downloading = False
        self._status_text = "Progress: Idle"
        self._overall_progress = 0
        self._current_speed = "0 KB/s"
        self._eta_text = "--"
        self._saved_bytes_text = "0 MB"
        self._adaptive_status_text = ""
        self._adaptive_state = "optimal"
        self._elapsed_time_text = "0s"
        self._files_count_text = ""
        self._has_error = False
        self._last_error_message = ""

        # Check saved session
        saved_sess = self.session_manager.get_saved_session()
        self._has_saved_session = bool(saved_sess)

        # Hook downloader callbacks — they emit our private signals (thread-safe)
        self.downloader.on_progress_update        = lambda info: self._progressSignal.emit(info)
        self.downloader.on_task_status_changed    = lambda task: self._taskSignal.emit(task)
        self.downloader.on_download_finished      = lambda ok, msg: self._finishedSignal.emit(ok, msg)
        self.downloader.on_concurrency_throttled  = lambda count: self._throttledSignal.emit(count)

        # Connect private signals to main-thread handlers with QueuedConnection
        self._progressSignal.connect(self._handle_progress,    Qt.QueuedConnection)
        self._taskSignal.connect(self._handle_task_status,     Qt.QueuedConnection)
        self._finishedSignal.connect(self._handle_finished,    Qt.QueuedConnection)
        self._throttledSignal.connect(self._handle_throttled,  Qt.QueuedConnection)
        self._creatorSignal.connect(self._handle_creator_resolved, Qt.QueuedConnection)
        self._setTasksSignal.connect(self._handle_set_tasks,       Qt.QueuedConnection)

        # Hook queue model retry signals
        self._queue_model.retryRequested.connect(self.retryFailed)
        self._queue_model.singleRetryRequested.connect(self.retrySingleTask)
        self._queue_model.retrySelectedRequested.connect(self.retrySelectedTasks)

        # Apply initial client config
        if self._cookie_string:
            self.api_client.set_cookie(self._cookie_string)
        if self._user_agent:
            self.api_client.set_user_agent(self._user_agent)

        logger.info(f"filename style loaded: 'post_title'", category="system")
        logger.info(f"Skip words scope loaded: '{self._skip_scope}'", category="system")
        logger.info(f"Character filter scope set to default: '{self._character_scope}'", category="system")
        if self._has_saved_session:
            logger.warning("Incomplete download session found. UI updated for restore.", category="session")

    # Property Getters / Setters
    @Property(str, notify=currentUrlChanged)
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
                        args=(parsed,),
                        daemon=True
                    ).start()
                else:
                    self._creator_name = ""
                    self.creatorNameChanged.emit()
            else:
                self._creator_name = ""
                self.creatorNameChanged.emit()

    @Property(int, notify=pageStartChanged)
    def pageStart(self) -> int:
        return self._page_start

    @pageStart.setter
    def pageStart(self, val: int):
        if self._page_start != val:
            self._page_start = max(1, val)
            self.pageStartChanged.emit()

    @Property(int, notify=pageEndChanged)
    def pageEnd(self) -> int:
        return self._page_end

    @pageEnd.setter
    def pageEnd(self, val: int):
        if self._page_end != val:
            self._page_end = max(1, val)
            self.pageEndChanged.emit()

    @Property(str, notify=downloadDirChanged)
    def downloadDir(self) -> str:
        return self._download_dir

    @downloadDir.setter
    def downloadDir(self, val: str):
        if self._download_dir != val:
            self._download_dir = val
            self.downloadDirChanged.emit()

    @Property(str, notify=filterCharactersChanged)
    def filterCharacters(self) -> str:
        return self._filter_characters

    @filterCharacters.setter
    def filterCharacters(self, val: str):
        if self._filter_characters != val:
            self._filter_characters = val
            self.filterCharactersChanged.emit()

    @Property(str, notify=characterScopeChanged)
    def characterScope(self) -> str:
        return self._character_scope

    @characterScope.setter
    def characterScope(self, val: str):
        if self._character_scope != val:
            self._character_scope = val
            self.characterScopeChanged.emit()

    @Property(str, notify=skipWordsChanged)
    def skipWords(self) -> str:
        return self._skip_words

    @skipWords.setter
    def skipWords(self, val: str):
        if self._skip_words != val:
            self._skip_words = val
            self.skipWordsChanged.emit()

    @Property(str, notify=skipScopeChanged)
    def skipScope(self) -> str:
        return self._skip_scope

    @skipScope.setter
    def skipScope(self, val: str):
        if self._skip_scope != val:
            self._skip_scope = val
            self.skipScopeChanged.emit()

    @Property(str, notify=removeWordsChanged)
    def removeWords(self) -> str:
        return self._remove_words

    @removeWords.setter
    def removeWords(self, val: str):
        if self._remove_words != val:
            self._remove_words = val
            self.removeWordsChanged.emit()

    @Property(str, notify=filterTypeChanged)
    def filterType(self) -> str:
        return self._filter_type

    @filterType.setter
    def filterType(self, val: str):
        if self._filter_type != val:
            self._filter_type = val
            self.filterTypeChanged.emit()

    @Property(bool, notify=skipArchivesChanged)
    def skipArchives(self) -> bool:
        return self._skip_archives

    @skipArchives.setter
    def skipArchives(self, val: bool):
        if self._skip_archives != val:
            self._skip_archives = val
            self.skipArchivesChanged.emit()

    @Property(bool, notify=downloadThumbnailsOnlyChanged)
    def downloadThumbnailsOnly(self) -> bool:
        return self._download_thumbnails_only

    @downloadThumbnailsOnly.setter
    def downloadThumbnailsOnly(self, val: bool):
        if self._download_thumbnails_only != val:
            self._download_thumbnails_only = val
            self.downloadThumbnailsOnlyChanged.emit()

    @Property(bool, notify=scanContentImagesChanged)
    def scanContentImages(self) -> bool:
        return self._scan_content_images

    @scanContentImages.setter
    def scanContentImages(self, val: bool):
        if self._scan_content_images != val:
            self._scan_content_images = val
            self.scanContentImagesChanged.emit()

    @Property(bool, notify=compressWebpChanged)
    def compressWebp(self) -> bool:
        return self._compress_webp

    @compressWebp.setter
    def compressWebp(self, val: bool):
        if self._compress_webp != val:
            self._compress_webp = val
            self.compressWebpChanged.emit()

    @Property(bool, notify=keepDuplicatesChanged)
    def keepDuplicates(self) -> bool:
        return self._keep_duplicates

    @keepDuplicates.setter
    def keepDuplicates(self, val: bool):
        if self._keep_duplicates != val:
            self._keep_duplicates = val
            self.keepDuplicatesChanged.emit()

    @Property(bool, notify=favoriteModeChanged)
    def favoriteMode(self) -> bool:
        return self._favorite_mode

    @favoriteMode.setter
    def favoriteMode(self, val: bool):
        if self._favorite_mode != val:
            self._favorite_mode = val
            self.favoriteModeChanged.emit()

    @Property(bool, notify=subfolderPerPostChanged)
    def subfolderPerPost(self) -> bool:
        return self._subfolder_per_post

    @subfolderPerPost.setter
    def subfolderPerPost(self, val: bool):
        if self._subfolder_per_post != val:
            self._subfolder_per_post = val
            self.subfolderPerPostChanged.emit()

    @Property(bool, notify=datePrefixChanged)
    def datePrefix(self) -> bool:
        return self._date_prefix

    @datePrefix.setter
    def datePrefix(self, val: bool):
        if self._date_prefix != val:
            self._date_prefix = val
            self.datePrefixChanged.emit()

    @Property(bool, notify=separateFoldersByKnownChanged)
    def separateFoldersByKnown(self) -> bool:
        return self._separate_folders_by_known

    @separateFoldersByKnown.setter
    def separateFoldersByKnown(self, val: bool):
        if self._separate_folders_by_known != val:
            self._separate_folders_by_known = val
            self.separateFoldersByKnownChanged.emit()

    @Property(bool, notify=downloadRevisionsChanged)
    def downloadRevisions(self) -> bool:
        return self._download_revisions

    @downloadRevisions.setter
    def downloadRevisions(self, val: bool):
        if self._download_revisions != val:
            self._download_revisions = val
            self.downloadRevisionsChanged.emit()

    @Property(bool, notify=adaptiveThreadingChanged)
    def adaptiveThreading(self) -> bool:
        return self._adaptive_threading

    @adaptiveThreading.setter
    def adaptiveThreading(self, val: bool):
        if self._adaptive_threading != val:
            self._adaptive_threading = val
            self.adaptiveThreadingChanged.emit()
            self.saveSettings()

    @Property(bool, notify=autoRetryAtEndChanged)
    def autoRetryAtEnd(self) -> bool:
        return self._auto_retry_at_end

    @autoRetryAtEnd.setter
    def autoRetryAtEnd(self, val: bool):
        if self._auto_retry_at_end != val:
            self._auto_retry_at_end = val
            self.autoRetryAtEndChanged.emit()

    @Property(bool, notify=mangaModeChanged)
    def mangaMode(self) -> bool:
        return self._manga_mode

    @mangaMode.setter
    def mangaMode(self, val: bool):
        if self._manga_mode != val:
            self._manga_mode = val
            self.mangaModeChanged.emit()

    @Property(str, notify=filenameStyleChanged)
    def filenameStyle(self) -> str:
        return self._filename_style

    @filenameStyle.setter
    def filenameStyle(self, val: str):
        if self._filename_style != val:
            self._filename_style = val
            self.filenameStyleChanged.emit()

    @Property(str, notify=proxyUrlChanged)
    def proxyUrl(self) -> str:
        return self._proxy_url

    @proxyUrl.setter
    def proxyUrl(self, val: str):
        if self._proxy_url != val:
            self._proxy_url = val
            self.api_client.set_proxy(val)
            self.proxyUrlChanged.emit()
            self.saveSettings()

    @Property(int, notify=threadsCountChanged)
    def threadsCount(self) -> int:
        return self._threads_count

    @threadsCount.setter
    def threadsCount(self, val: int):
        if self._threads_count != val:
            self._threads_count = max(1, min(self._max_cpu_threads, val))
            self.downloader.max_workers = self._threads_count
            self.threadsCountChanged.emit()

    @Property(int, notify=maxCpuThreadsChanged)
    def maxCpuThreads(self) -> int:
        return self._max_cpu_threads

    @Property(str, notify=etaTextChanged)
    def etaText(self) -> str:
        return self._eta_text

    @Property(str, notify=savedBytesTextChanged)
    def savedBytesText(self) -> str:
        return self._saved_bytes_text

    @Property(str, notify=adaptiveStatusTextChanged)
    def adaptiveStatusText(self) -> str:
        return self._adaptive_status_text

    @Property(str, notify=adaptiveStateChanged)
    def adaptiveState(self) -> str:
        return self._adaptive_state

    @Property(str, notify=elapsedTimeTextChanged)
    def elapsedTimeText(self) -> str:
        return self._elapsed_time_text

    @Property(str, notify=filesCountTextChanged)
    def filesCountText(self) -> str:
        return self._files_count_text

    @Property(str, notify=cookieStringChanged)
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
            self.cookieStringChanged.emit()

    @Property(str, notify=userAgentChanged)
    def userAgent(self) -> str:
        return self._user_agent

    @userAgent.setter
    def userAgent(self, val: str):
        if self._user_agent != val:
            self._user_agent = val
            self.api_client.set_user_agent(val)
            self.userAgentChanged.emit()

    @Property(bool, notify=isDownloadingChanged)
    def isDownloading(self) -> bool:
        return self._is_downloading

    @Property(str, notify=statusTextChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(int, notify=overallProgressChanged)
    def overallProgress(self) -> int:
        return self._overall_progress

    @Property(str, notify=currentSpeedChanged)
    def currentSpeed(self) -> str:
        return self._current_speed

    @Property(bool, notify=hasSavedSessionChanged)
    def hasSavedSession(self) -> bool:
        return self._has_saved_session

    @Property(bool, notify=hasErrorChanged)
    def hasError(self) -> bool:
        return self._has_error

    @Property(str, notify=lastErrorMessageChanged)
    def lastErrorMessage(self) -> str:
        return self._last_error_message

    @Property(str, notify=creatorNameChanged)
    def creatorName(self) -> str:
        return self._creator_name

    @Property(float, notify=downloadDelayChanged)
    def downloadDelay(self) -> float:
        return self._download_delay

    @downloadDelay.setter
    def downloadDelay(self, val: float):
        val = round(float(val), 2)
        if self._download_delay != val:
            self._download_delay = val
            self.downloadDelayChanged.emit()
            self.saveSettings()

    @Property(bool, notify=savePostMetadataChanged)
    def savePostMetadata(self) -> bool:
        return self._save_post_metadata

    @savePostMetadata.setter
    def savePostMetadata(self, val: bool):
        if self._save_post_metadata != val:
            self._save_post_metadata = val
            self.savePostMetadataChanged.emit()
            self.saveSettings()

    @Property(bool, notify=downloadEmbedsChanged)
    def downloadEmbeds(self) -> bool:
        return self._download_embeds

    @downloadEmbeds.setter
    def downloadEmbeds(self, val: bool):
        if self._download_embeds != val:
            self._download_embeds = val
            self.downloadEmbedsChanged.emit()
            self.saveSettings()

    @Property(bool, notify=openFolderOnCompleteChanged)
    def openFolderOnComplete(self) -> bool:
        return self._open_folder_on_complete

    @openFolderOnComplete.setter
    def openFolderOnComplete(self, val: bool):
        if self._open_folder_on_complete != val:
            self._open_folder_on_complete = val
            self.openFolderOnCompleteChanged.emit()
            self.saveSettings()

    @Property(bool, notify=playCompletionSoundChanged)
    def playCompletionSound(self) -> bool:
        return self._play_completion_sound

    @playCompletionSound.setter
    def playCompletionSound(self, val: bool):
        if self._play_completion_sound != val:
            self._play_completion_sound = val
            self.playCompletionSoundChanged.emit()
            self.saveSettings()

    @Property(int, notify=consoleWidthChanged)
    def consoleWidth(self) -> int:
        return self._console_width

    @consoleWidth.setter
    def consoleWidth(self, val: int):
        val = max(280, min(1400, int(val)))
        if self._console_width != val:
            self._console_width = val
            self.consoleWidthChanged.emit()
            self.saveSettings()

    # Model Properties
    @Property(QObject, constant=True)
    def logModel(self) -> LogModel:
        return self._log_model

    @Property(QObject, constant=True)
    def queueModel(self) -> QueueModel:
        return self._queue_model

    @Property(QObject, constant=True)
    def knownModel(self) -> KnownModel:
        return self._known_model

    @Property(bool, notify=harvestedLinksChanged)
    def hasHarvestedLinks(self) -> bool:
        return bool(self.downloader.harvested_links_records)

    @Property(int, notify=harvestedLinksChanged)
    def harvestedLinksCount(self) -> int:
        return len(self.downloader.harvested_links_records)

    @Property(list, notify=harvestedLinksChanged)
    def harvestedLinks(self) -> list:
        return self.downloader.harvested_links_records

    @Property(bool, notify=isDownloadingChanged)
    def isCloudDownloading(self) -> bool:
        return self._is_cloud_downloading

    @Slot(result="QVariantList")
    def getHarvestedLinks(self):
        return self.downloader.harvested_links_records

    @Slot(result="QVariantList")
    def getDownloadHistory(self):
        """Return download history as a list of dicts for the History tab."""
        return self.session_manager.get_download_history()

    def _get_filter_options(self) -> FilterOptions:
        return FilterOptions(
            characters=self._filter_characters,
            character_scope=self._character_scope,
            skip_words=self._skip_words,
            skip_scope=self._skip_scope,
            remove_words=self._remove_words,
            file_type=self._filter_type,
            skip_archives=self._skip_archives,
            download_thumbnails_only=self._download_thumbnails_only,
            scan_content_images=self._scan_content_images,
            compress_to_webp=self._compress_webp,
            keep_duplicates=self._keep_duplicates,
            favorite_mode=self._favorite_mode,
            subfolder_per_post=self._subfolder_per_post,
            date_prefix=self._date_prefix,
            separate_by_known=self._separate_folders_by_known,
            download_revisions=self._download_revisions,
            adaptive_threading=self._adaptive_threading,
            auto_retry_at_end=self._auto_retry_at_end,
            manga_mode=self._manga_mode,
            filename_style=self._filename_style,
            proxy_url=self._proxy_url,
            page_start=self._page_start,
            page_end=self._page_end,
            download_delay=self._download_delay,
            save_post_metadata=self._save_post_metadata,
            download_embeds=self._download_embeds
        )

    # Actions / Slots
    @Slot()
    def startDownload(self):
        """
        Parses URL, fetches posts from API or external providers, builds download queue, and starts downloading.
        """
        if self._is_downloading:
            logger.warning("Download process is already running!", category="system")
            return

        parsed = KemonoURLParser.parse(self._current_url)
        if not parsed.is_valid:
            self._has_error = True
            self._last_error_message = parsed.error_msg
            self.hasErrorChanged.emit()
            self.lastErrorMessageChanged.emit()
            logger.error(f"Invalid URL: {parsed.error_msg}", category="parser")
            return

        self._scan_cancel_event.clear()
        self._has_error = False
        self.hasErrorChanged.emit()
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self._status_text = "Fetching metadata..."
        self.statusTextChanged.emit()

        threading.Thread(
            target=self._async_fetch_and_start,
            args=(parsed, True),
            daemon=True
        ).start()

    @Slot()
    def addToQueue(self):
        """
        Parses URL, fetches posts, and appends to the queue without immediate download.
        """
        parsed = KemonoURLParser.parse(self._current_url)
        if not parsed.is_valid:
            logger.error(f"Invalid URL: {parsed.error_msg}", category="parser")
            return

        self._scan_cancel_event.clear()
        threading.Thread(
            target=self._async_fetch_and_start,
            args=(parsed, False),
            daemon=True
        ).start()

    def _async_fetch_and_start(self, parsed: URLParseResult, auto_start: bool):
        try:
            if self._scan_cancel_event.is_set():
                self._is_downloading = False
                self._status_text = "Progress: Cancelled"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                return

            options = self._get_filter_options()

            # ── Handle Integrated Third-Party Providers ───────────────────────
            if parsed.is_external_provider:
                creator_name = parsed.domain
                tasks = []

                if parsed.provider == "bunkr":
                    album_title, files = fetch_bunkr_album(parsed.raw_url)
                    creator_name = album_title or "Bunkr Album"
                    folder = os.path.join(self._download_dir, f"Bunkr - {creator_name}")
                    for f in files:
                        t = DownloadTask(
                            url=f["url"],
                            target_path=os.path.join(folder, f["filename"]),
                            post_title=creator_name,
                            creator_name="Bunkr",
                            service="bunkr",
                            post_id=parsed.post_id or "bunkr",
                            file_id=f["url"]
                        )
                        tasks.append(t)

                elif parsed.provider == "erome":
                    album_title, files = fetch_erome_album(parsed.raw_url)
                    creator_name = album_title or "Erome Album"
                    folder = os.path.join(self._download_dir, creator_name)
                    for f in files:
                        t = DownloadTask(
                            url=f["url"],
                            target_path=os.path.join(folder, f["filename"]),
                            post_title=creator_name,
                            creator_name="Erome",
                            service="erome",
                            post_id=parsed.post_id or "erome",
                            file_id=f["url"]
                        )
                        tasks.append(t)

                elif parsed.provider == "nhentai":
                    gallery_title, files = fetch_nhentai_gallery(parsed.post_id or parsed.raw_url)
                    creator_name = gallery_title or f"Gallery {parsed.post_id}"
                    folder = os.path.join(self._download_dir, f"nHentai - {creator_name}")
                    for f in files:
                        t = DownloadTask(
                            url=f["url"],
                            target_path=os.path.join(folder, f["filename"]),
                            post_title=creator_name,
                            creator_name="nHentai",
                            service="nhentai",
                            post_id=parsed.post_id or "nhentai",
                            file_id=f["url"]
                        )
                        tasks.append(t)

                self._creator_name = creator_name
                self.creatorNameChanged.emit()

            else:
                # ── Standard Kemono / Coomer / Pawchive Provider ───────────────
                # 1. Fetch profile
                profile = self.api_client.fetch_creator_profile(parsed)
                creator_name = profile.get("name", parsed.user_id) or parsed.user_id
                self._creator_name = creator_name
                self.creatorNameChanged.emit()

                if self._scan_cancel_event.is_set():
                    self._is_downloading = False
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                # 2. Fetch posts
                if parsed.is_single_post:
                    single = self.api_client.fetch_single_post(parsed)
                    posts = [single] if single else []
                else:
                    posts = self.api_client.fetch_user_posts(
                        parsed=parsed,
                        page_start=self._page_start,
                        page_end=self._page_end,
                        cancel_event=self._scan_cancel_event
                    )

                if self._scan_cancel_event.is_set():
                    self._is_downloading = False
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                if not posts:
                    logger.warning(f"No posts found for {creator_name} ({parsed.service}).", category="api")
                    self._is_downloading = False
                    self._status_text = "Progress: Idle (0 posts found)"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                # If character filter uses comments scope, attach comments to post dictionaries
                if options.character_scope in ("comments", "all"):
                    for p in posts:
                        if self._scan_cancel_event.is_set():
                            break
                        pid = str(p.get("id", ""))
                        if pid:
                            comms = self.api_client.fetch_post_comments(parsed.domain, parsed.service, parsed.user_id, pid)
                            p["comments_text"] = "\n".join(c.get("content", "") for c in comms if isinstance(c, dict))

                if self._scan_cancel_event.is_set():
                    self._is_downloading = False
                    self._status_text = "Progress: Cancelled"
                    self.isDownloadingChanged.emit()
                    self.statusTextChanged.emit()
                    return

                # 3. Build tasks
                tasks = self.downloader.build_tasks_from_posts(
                    posts=posts,
                    creator_name=creator_name,
                    service=parsed.service,
                    domain=parsed.domain,
                    base_dir=self._download_dir,
                    options=options
                )

            if self._scan_cancel_event.is_set():
                self._is_downloading = False
                self._status_text = "Progress: Cancelled"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                return

            if options.file_type == "links":
                h_count = len(self.downloader.harvested_links_records)
                self._is_downloading = False
                self._status_text = f"Links extraction complete ({h_count} links found). Ready to download or export."
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                self.harvestedLinksChanged.emit()
                return

            if not tasks:
                logger.warning("No files matched filtering criteria.", category="downloader")
                self._is_downloading = False
                self._status_text = "Progress: Idle (All files filtered out)"
                self.isDownloadingChanged.emit()
                self.statusTextChanged.emit()
                return

            # Add to queue model safely on GUI main thread
            self._setTasksSignal.emit(tasks)

            # Record to history for History tab
            self.session_manager.record_download_session(
                creator_name=creator_name,
                url=self._current_url,
                service=parsed.service,
                file_count=len(tasks)
            )
            self.downloadHistoryChanged.emit()

            # Save session for restore capability
            self.session_manager.save_session({
                "url": self._current_url,
                "creator": creator_name,
                "service": parsed.service,
                "total_tasks": len(tasks),
                "options": vars(options)
            })
            self._has_saved_session = True
            self.hasSavedSessionChanged.emit()

            if auto_start:
                self.downloader.start_download_queue(
                    tasks=tasks,
                    options=options,
                    cookie_str=self._cookie_string
                )
            else:
                self._status_text = f"Queued {len(tasks)} files."
                self.statusTextChanged.emit()

        except Exception as e:
            logger.error(f"Error during task initialization: {e}", category="downloader")
            self._is_downloading = False
            self._has_error = True
            self._last_error_message = str(e)
            self.isDownloadingChanged.emit()
            self.hasErrorChanged.emit()
            self.lastErrorMessageChanged.emit()

    @Slot()
    def restoreDownload(self):
        saved = self.session_manager.get_saved_session()
        if not saved:
            logger.warning("No saved download session found.", category="session")
            return

        logger.info(f"Restoring session for {saved.get('creator')} ({saved.get('url')})...", category="session")
        self._current_url = saved.get("url", self._current_url)
        self.currentUrlChanged.emit()
        self.startDownload()

    @Slot()
    def discardSession(self):
        # Discard cancels active download automatically as requested
        if self._is_downloading:
            self.cancelDownload()
        self._queue_model.clear()
        self.session_manager.discard_session()
        self._has_saved_session = False
        self.hasSavedSessionChanged.emit()
        logger.info("Active download stopped and session discarded.", category="session")

    @Slot()
    def onAppClosing(self):
        """Called when user closes the window — preserves active session and stops threads cleanly."""
        if self._is_downloading:
            logger.info("Application closing: saving active session and stopping threads...", category="system")
            # Save session for restore upon next launch
            if self._queue_model.rowCount() > 0:
                self.session_manager.save_session({
                    "url": self._current_url,
                    "creator": self._creator_name,
                    "service": "fanbox",
                    "total_tasks": self._queue_model.rowCount(),
                    "options": vars(self._get_filter_options())
                })
            self.downloader.cancel()

    @Slot()
    def retryFailed(self):
        """Retries all failed tasks in the queue."""
        options = self._get_filter_options()
        self._is_downloading = True
        self.isDownloadingChanged.emit()

        count = self.downloader.retry_failed_tasks(options, self._cookie_string)
        if count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._status_text = "Progress: Idle (no failed tasks)"
            self.statusTextChanged.emit()
        elif count > 0:
            logger.info(f"Retrying {count} failed tasks with {self._threads_count} worker threads...", category="downloader")

    @Slot("QVariantList")
    def retrySelectedTasks(self, selected_ids: list):
        """Retries only selected failed tasks."""
        options = self._get_filter_options()
        self._is_downloading = True
        self.isDownloadingChanged.emit()

        count = self.downloader.retry_selected_tasks(selected_ids, options, self._cookie_string)
        if count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._status_text = "Progress: Idle (no selected tasks to retry)"
            self.statusTextChanged.emit()
        elif count > 0:
            logger.info(f"Retrying {count} selected tasks...", category="downloader")

    @Slot(str)
    def retrySingleTask(self, file_id: str):
        """Retries only a single specific failed task."""
        if not file_id:
            return
        options = self._get_filter_options()
        self._is_downloading = True
        self.isDownloadingChanged.emit()

        count = self.downloader.retry_selected_tasks([file_id], options, self._cookie_string)
        if count == 0 and not self.downloader.is_running:
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._status_text = "Progress: Idle"
            self.statusTextChanged.emit()
        elif count > 0:
            logger.info(f"Retrying single task: {file_id}", category="downloader")

    @Slot()
    def cancelDownload(self):
        self.downloader.cancel()
        self.cancelCloudDownloads()
        self._is_downloading = False
        self.isDownloadingChanged.emit()
        self._status_text = "Progress: Cancelled"
        self.statusTextChanged.emit()

    @Slot()
    def pauseDownload(self):
        self.downloader.pause()
        self._cloud_pause_event.set()
        self._status_text = "Progress: Paused"
        self.statusTextChanged.emit()

    @Slot()
    def resumeDownload(self):
        self.downloader.resume()
        self._cloud_pause_event.clear()
        self._status_text = "Progress: Resumed"
        self.statusTextChanged.emit()

    @Slot()
    def selectDownloadDirectory(self):
        folder = QFileDialog.getExistingDirectory(
            None,
            "Select Download Directory",
            self._download_dir
        )
        if folder:
            self.downloadDir = folder
            self.saveSettings()

    @Slot()
    def exportAllLinks(self):
        # In links-only mode, export the harvested external cloud links
        harvested = self.downloader.harvested_links
        if harvested:
            save_path, _ = QFileDialog.getSaveFileName(
                None,
                "Export Harvested Links",
                os.path.join(self._download_dir, "harvested_links.txt"),
                "Text Files (*.txt);;All Files (*)"
            )
            if not save_path:
                return

            lines = [
                f"Kemono Downloader — Harvested External Links",
                f"Exported: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 60,
                "",
            ]
            total = 0
            for platform, urls in sorted(harvested.items()):
                lines.append(f"[{platform.upper()}]  ({len(urls)} link(s))")
                for u in urls:
                    lines.append(f"  {u}")
                    total += 1
                lines.append("")
            lines.append(f"Total: {total} unique link(s)")

            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                logger.success(f"🔗 Exported {total} harvested link(s) to: {save_path}", category="session")
            except Exception as e:
                logger.error(f"Failed to export harvested links: {e}", category="session")
            return

        # Fallback: export raw download task URLs from the queue
        tasks = self._queue_model.getTasks()
        if not tasks:
            logger.warning("No harvested links or queued tasks to export.", category="session")
            return

        links = [t.url for t in tasks]
        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export Links",
            os.path.join(self._download_dir, "links_export.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        if save_path:
            self.session_manager.export_links_to_file(links, save_path)

    @Slot("QVariantList", str)
    def startCloudDownloads(self, selected_links: list, dest_folder: str = ""):
        """Downloads selected harvested cloud links (Mega, Drive, Dropbox, GoFile) with live progress telemetry."""
        if self._is_cloud_downloading or self._is_downloading:
            logger.warning("Download process is already running!", category="system")
            return

        if not selected_links:
            logger.warning("No links selected for cloud download.", category="downloader")
            return

        target_dir = dest_folder.strip() or self._download_dir
        os.makedirs(target_dir, exist_ok=True)

        self._is_cloud_downloading = True
        self._is_downloading = True
        self.isDownloadingChanged.emit()
        self._cloud_cancel_event.clear()
        self._cloud_pause_event.clear()

        def _worker():
            total = len(selected_links)
            concurrency = min(total, max(1, self._threads_count))
            logger.info(f"☁️ Starting concurrent cloud downloads for {total} link(s) ({concurrency} parallel streams) to: {target_dir}", category="downloader")
            self._status_text = f"Cloud Download: 0/{total} completed"
            self.statusTextChanged.emit()

            success_count = 0
            start_time = time.time()
            total_downloaded_bytes = 0
            progress_lock = threading.Lock()
            last_calc_time = time.time()
            last_calc_bytes = 0
            link_progress_map = {}

            def _process_link(idx, item):
                nonlocal success_count, total_downloaded_bytes, last_calc_time, last_calc_bytes
                if self._cloud_cancel_event.is_set():
                    return False

                url = item.get("url", "") if isinstance(item, dict) else str(item)
                title = item.get("title", "File") if isinstance(item, dict) else "Cloud File"
                platform = item.get("platform", "other").lower() if isinstance(item, dict) else "other"

                if "mega.nz" in url or "mega.co.nz" in url:
                    platform = "mega"
                elif "drive.google.com" in url or "docs.google.com" in url:
                    platform = "gdrive"
                elif "dropbox.com" in url:
                    platform = "dropbox"
                elif "gofile.io" in url:
                    platform = "gofile"

                logger.info(f"☁️ [{platform.upper()}] Starting ({idx}/{total}): {url}", category="downloader")

                def _prog(fname, dl, tot, file_idx=1, file_tot=1):
                    nonlocal last_calc_time, last_calc_bytes
                    with progress_lock:
                        link_progress_map[idx] = {
                            "fname": fname,
                            "dl": dl,
                            "tot": tot,
                            "file_idx": file_idx,
                            "file_tot": file_tot,
                            "platform": platform
                        }
                        now = time.time()
                        dt = now - last_calc_time
                        current_total_dl = sum(p["dl"] for p in link_progress_map.values()) + total_downloaded_bytes

                        speed_str = ""
                        eta_str = "--"
                        if dt >= 0.5:
                            d_bytes = max(0, current_total_dl - last_calc_bytes)
                            speed = d_bytes / dt if dt > 0 else 0
                            last_calc_time = now
                            last_calc_bytes = current_total_dl
                            if speed > 1024 * 1024:
                                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                            elif speed > 1024:
                                speed_str = f"{speed / 1024:.0f} KB/s"
                            else:
                                speed_str = f"{speed:.0f} B/s"

                        # Calculate aggregated progress across all links
                        sum_fraction = 0.0
                        for l_idx in range(1, total + 1):
                            if l_idx in link_progress_map:
                                p = link_progress_map[l_idx]
                                f_tot = p["file_tot"]
                                f_idx = p["file_idx"]
                                f_dl = p["dl"]
                                f_t = p["tot"]
                                f_frac = (f_idx - 1 + (f_dl / f_t if f_t > 0 else 0)) / f_tot if f_tot > 0 else 0
                                sum_fraction += f_frac
                            elif l_idx < idx:
                                sum_fraction += 1.0

                        pct = int((sum_fraction / total) * 100) if total > 0 else 0
                        elapsed_sec = int(now - start_time)
                        elapsed_str = f"{elapsed_sec}s" if elapsed_sec < 60 else f"{elapsed_sec // 60}m {elapsed_sec % 60}s"
                        saved_mb = current_total_dl / (1024 * 1024)
                        saved_str = f"{saved_mb:.1f} MB" if saved_mb < 1024 else f"{saved_mb / 1024:.2f} GB"

                        if total == 1:
                            files_badge = f"{file_idx}/{file_tot}" if file_tot > 1 else "1/1"
                        else:
                            files_badge = f"{success_count}/{total} links"

                        status_msg = f"[{platform.upper()}] {fname}"
                        if tot > 0:
                            status_msg += f" ({dl // 1024 // 1024}MB / {tot // 1024 // 1024}MB)"

                        self._progressSignal.emit({
                            "percent": max(0, min(100, pct)),
                            "speed_str": speed_str or self._current_speed,
                            "eta_str": eta_str,
                            "saved_str": saved_str,
                            "elapsed_str": elapsed_str,
                            "files_count_text": files_badge,
                            "status_text": status_msg
                        })

                workers_per_link = max(1, min(self._threads_count, 8))
                ok = False
                try:
                    if platform == "mega":
                        ok = download_mega_link(url, target_dir, log_func=lambda msg: logger.info(msg, category="downloader"), progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, max_workers=workers_per_link)
                    elif platform in ("gdrive", "google drive"):
                        ok = download_gdrive_link(url, target_dir, log_func=lambda msg: logger.info(msg, category="downloader"), cancel_event=self._cloud_cancel_event)
                    elif platform == "dropbox":
                        ok = download_dropbox_link(url, target_dir, log_func=lambda msg: logger.info(msg, category="downloader"), progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event)
                    elif platform == "gofile":
                        ok = download_gofile_link(url, target_dir, log_func=lambda msg: logger.info(msg, category="downloader"), progress_callback=_prog, cancel_event=self._cloud_cancel_event, pause_event=self._cloud_pause_event, max_workers=workers_per_link)
                    else:
                        logger.warning(f"Platform '{platform}' cannot be directly auto-downloaded (URL: {url}).", category="downloader")
                except Exception as ex:
                    logger.error(f"Error downloading {url}: {ex}", category="downloader")

                with progress_lock:
                    if ok:
                        success_count += 1
                        if idx in link_progress_map:
                            total_downloaded_bytes += link_progress_map[idx].get("tot", 0)

                return ok

            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=concurrency) as link_executor:
                futures = [link_executor.submit(_process_link, idx, item) for idx, item in enumerate(selected_links, 1)]
                for future in as_completed(futures):
                    if self._cloud_cancel_event.is_set():
                        for f in futures:
                            f.cancel()
                        break
                    try:
                        future.result()
                    except Exception:
                        pass

            self._is_cloud_downloading = False
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            self._overall_progress = 100 if success_count == total else int((success_count / total) * 100)
            self.overallProgressChanged.emit()
            self._status_text = f"Cloud Download completed: {success_count}/{total} succeeded."
            self.statusTextChanged.emit()
            logger.success(f"☁️ Cloud downloads finished: {success_count}/{total} succeeded.", category="downloader")

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def cancelCloudDownloads(self):
        if self._is_cloud_downloading:
            self._cloud_cancel_event.set()
            self._is_cloud_downloading = False
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            logger.warning("Cloud downloads cancellation requested.", category="downloader")

    @Slot()
    def cancelDownload(self):
        self._scan_cancel_event.set()
        self.downloader.cancel()
        self.cancelCloudDownloads()
        self._is_downloading = False
        self.isDownloadingChanged.emit()
        self._status_text = "Progress: Cancelled"
        self.statusTextChanged.emit()

    @Slot()
    def pauseDownload(self):
        self.downloader.pause()
        self._cloud_pause_event.set()
        self._status_text = "Progress: Paused"
        self.statusTextChanged.emit()

    @Slot()
    def resumeDownload(self):
        self.downloader.resume()
        self._cloud_pause_event.clear()
        self._status_text = "Progress: Resumed"
        self.statusTextChanged.emit()

    @Slot()
    def selectDownloadDirectory(self):
        folder = QFileDialog.getExistingDirectory(
            None,
            "Select Download Directory",
            self._download_dir
        )
        if folder:
            self.downloadDir = folder
            self.saveSettings()

    @Slot()
    def exportAllLinks(self):
        # In links-only mode, export the harvested external cloud links
        harvested = self.downloader.harvested_links
        if harvested:
            save_path, _ = QFileDialog.getSaveFileName(
                None,
                "Export Harvested Links",
                os.path.join(self._download_dir, "harvested_links.txt"),
                "Text Files (*.txt);;All Files (*)"
            )
            if not save_path:
                return

            lines = [
                f"Kemono Downloader — Harvested External Links",
                f"Exported: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 60,
                "",
            ]
            total = 0
            for platform, urls in sorted(harvested.items()):
                lines.append(f"[{platform.upper()}]  ({len(urls)} link(s))")
                for u in urls:
                    lines.append(f"  {u}")
                    total += 1
                lines.append("")
            lines.append(f"Total: {total} unique link(s)")

            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                logger.success(f"🔗 Exported {total} harvested link(s) to: {save_path}", category="session")
            except Exception as e:
                logger.error(f"Failed to export harvested links: {e}", category="session")
            return

    @Slot()
    def exportLogs(self):
        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export Console Logs",
            os.path.join(self._download_dir, "kemono_console.log"),
            "Log Files (*.log *.txt);;All Files (*)"
        )
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(self._log_model.get_all_text())
                logger.success(f"Console logs exported to: {save_path}", category="logger")
            except Exception as e:
                logger.error(f"Failed to export console logs: {e}", category="logger")

    @Slot()
    def clearLogs(self):
        self._log_model.clearLogs()

    @Slot()
    def openDownloadFolder(self):
        os.makedirs(self._download_dir, exist_ok=True)
        if os.name == "nt":
            os.startfile(self._download_dir)
        else:
            subprocess.Popen(["xdg-open", self._download_dir])

    @Slot()
    def openKnownTxt(self):
        path = self.known_manager.file_path
        if not os.path.exists(path):
            self.known_manager.save()
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])

    @Slot(str)
    def addKnownCharacter(self, name: str):
        if self._known_model.addEntry(name):
            logger.success(f"Added '{name}' to Known list.", category="known")

    @Slot(int)
    def removeKnownCharacter(self, index: int):
        self._known_model.removeIndex(index)

    @Slot(str)
    def applyCharacterToFilter(self, name: str):
        if not self._filter_characters:
            self.filterCharacters = name
        else:
            parts = [p.strip() for p in self._filter_characters.split(",") if p.strip()]
            if name not in parts:
                parts.append(name)
                self.filterCharacters = ", ".join(parts)
        logger.info(f"Added '{name}' to character filter.", category="filter")

    @Slot(str, result=int)
    def batchLoadUrls(self, input_text_or_path: str) -> int:
        """
        Parses multiple URLs from a file path or pasted multi-line text and queues them.
        """
        if os.path.exists(input_text_or_path):
            urls, err = BatchLoader.load_urls_from_file(input_text_or_path)
            if err:
                logger.error(err, category="batch")
                return 0
        else:
            urls = BatchLoader.parse_urls_from_text(input_text_or_path)

        if not urls:
            logger.warning("No valid URLs found in batch input.", category="batch")
            return 0

        logger.info(f"Loaded {len(urls)} URLs for batch processing.", category="batch")
        for u in urls:
            parsed = KemonoURLParser.parse(u)
            if parsed.is_valid:
                threading.Thread(
                    target=self._async_fetch_and_start,
                    args=(parsed, False),
                    daemon=True
                ).start()
            else:
                logger.warning(f"Skipped invalid URL in batch: {u}", category="batch")
        return len(urls)

    @Slot(result=str)
    def exportExtractedLinks(self) -> str:
        """
        Exports extracted external links to a user-chosen text file.
        """
        tasks = self._queue_model.tasks
        if not tasks:
            return ""

        all_text = ""
        for t in tasks:
            if t.url:
                all_text += f"{t.url}\n"

        save_path, _ = QFileDialog.getSaveFileName(
            None,
            "Export External Links",
            os.path.join(self._download_dir, "extracted_links.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(all_text)
                logger.success(f"Links exported to: {save_path}", category="file")
                return save_path
            except Exception as e:
                logger.error(f"Failed to export links: {e}", category="file")
        return ""

    @Slot()
    def saveSettings(self):
        settings_dict = {
            "download_dir": self._download_dir,
            "threads": self._threads_count,
            "cookie": self._cookie_string,
            "user_agent": self._user_agent,
            "page_start": self._page_start,
            "page_end": self._page_end,
            "character_scope": self._character_scope,
            "skip_scope": self._skip_scope,
            "subfolder_per_post": self._subfolder_per_post,
            "date_prefix": self._date_prefix,
            "separate_by_known": self._separate_folders_by_known,
            "download_revisions": self._download_revisions,
            "adaptive_threading": self._adaptive_threading,
            "auto_retry_at_end": self._auto_retry_at_end,
            "manga_mode": self._manga_mode,
            "filename_style": self._filename_style,
            "proxy_url": self._proxy_url,
            "compress_webp": self._compress_webp,
            "keep_duplicates": self._keep_duplicates,
            "scan_content_images": self._scan_content_images,
            "download_delay": self._download_delay,
            "save_post_metadata": self._save_post_metadata,
            "download_embeds": self._download_embeds,
            "open_folder_on_complete": self._open_folder_on_complete,
            "play_completion_sound": self._play_completion_sound,
            "console_width": self._console_width
        }
        self.session_manager.save_settings(settings_dict, silent=True)

    # ── Thread-safe downloader event handlers ─────────────────────────────────
    # These slots run on the MAIN thread (via QueuedConnection) so it is safe
    # to read/write Qt properties and update models here.

    @Slot(dict)
    def _handle_progress(self, info: Dict[str, Any]):
        completed = info.get("completed", 0)
        total     = info.get("total", 0)
        failed    = info.get("failed", 0)
        self._overall_progress   = info.get("percent", info.get("progress", 0))
        self._current_speed      = info.get("speed_str", "0 KB/s")
        self._eta_text           = info.get("eta_str", "--")
        self._saved_bytes_text   = info.get("saved_str", "0 MB")
        self._status_text        = info.get("status_text", f"Downloading… {completed}/{total}")
        self._files_count_text   = info.get("files_count_text") if info.get("files_count_text") else (f"{completed}/{total}" if total > 0 else "")
        self._adaptive_state     = info.get("adaptive_state", "optimal")
        self._adaptive_status_text = info.get("adaptive_status_text", "")
        self._elapsed_time_text  = info.get("elapsed_str", "0s")

        self.overallProgressChanged.emit()
        self.currentSpeedChanged.emit()
        self.etaTextChanged.emit()
        self.savedBytesTextChanged.emit()
        self.statusTextChanged.emit()
        self.filesCountTextChanged.emit()
        self.adaptiveStateChanged.emit()
        self.adaptiveStatusTextChanged.emit()
        self.elapsedTimeTextChanged.emit()

    @Slot(object)
    def _handle_task_status(self, task: DownloadTask):
        self._queue_model.updateTask(task)

    @Slot(int)
    def _handle_throttled(self, new_count: int):
        self._threads_count = new_count
        self.threadsCountChanged.emit()
        logger.info(f"UI concurrency slider auto-throttled to {new_count} threads due to rate limiting.", category="system")

    @Slot(list)
    def _handle_set_tasks(self, tasks: list):
        self._queue_model.setTasks(tasks)

    @Slot(bool, str)
    def _handle_finished(self, success: bool, message: str):
        self._is_downloading = False
        
        # Calculate actual completed percentage
        tasks = self._queue_model.getTasks()
        if tasks:
            completed_c = sum(1 for t in tasks if t.status == "completed")
            failed_c = sum(1 for t in tasks if t.status == "failed")
            self._overall_progress = int(completed_c / len(tasks) * 100)
            if failed_c > 0:
                self._status_text = f"Finished with {failed_c} error(s) ({completed_c}/{len(tasks)} completed)"
            else:
                self._overall_progress = 100
                self._status_text = f"Completed ({completed_c}/{len(tasks)} files)"
        else:
            self._overall_progress = 100 if success else self._overall_progress
            self._status_text = f"Progress: {message}"

        self.isDownloadingChanged.emit()
        self.overallProgressChanged.emit()
        self.statusTextChanged.emit()
        if not success:
            self._has_error = True
            self._last_error_message = message
            self.hasErrorChanged.emit()
            self.lastErrorMessageChanged.emit()
        else:
            self.session_manager.discard_session()
            self._has_saved_session = False
            self.hasSavedSessionChanged.emit()
            # Post-completion actions
            if self._open_folder_on_complete and self._download_dir:
                try:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(self._download_dir))
                except Exception:
                    pass

    def _async_resolve_creator_name(self, parsed: URLParseResult):
        try:
            if parsed.is_external_provider:
                if parsed.provider == "bunkr":
                    album_title, _ = fetch_bunkr_album(parsed.raw_url)
                    if album_title:
                        self._creatorSignal.emit(f"Bunkr: {album_title}")
                elif parsed.provider == "erome":
                    album_title, _ = fetch_erome_album(parsed.raw_url)
                    if album_title:
                        self._creatorSignal.emit(f"Erome: {album_title}")
                elif parsed.provider == "nhentai":
                    gallery_title, _ = fetch_nhentai_gallery(parsed.post_id or parsed.raw_url)
                    if gallery_title:
                        self._creatorSignal.emit(f"nHentai: {gallery_title}")
                elif parsed.provider == "saint2":
                    self._creatorSignal.emit(f"Saint2: {parsed.user_id}")
            else:
                profile = self.api_client.fetch_creator_profile(parsed)
                name = profile.get("displayName") or profile.get("name") or profile.get("user") or profile.get("username") or parsed.user_id
                if name:
                    self._creatorSignal.emit(str(name))
        except Exception:
            pass

    @Slot(str)
    def _handle_creator_resolved(self, name: str):
        if name and self._creator_name != name:
            self._creator_name = name
            self.creatorNameChanged.emit()
