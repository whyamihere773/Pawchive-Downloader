"""
Decompressor Bridge
Exposes BulkDecompressorEngine to QML with reactive properties,
async worker threads, live progress parsing, and ETA calculations.
"""

import os
import threading
from typing import Any, Dict, List, Tuple

from PySide6.QtCore import QObject, Qt, QTimer, Slot

from bridge.archive_creators_model import RecordListModel
from bridge.decompressor_mixins import (
    DecompressorCompressionMixin,
    DecompressorExtractionMixin,
    DecompressorItemsGroupsMixin,
    DecompressorPasswordsMixin,
    _format_bytes,
)
from core.archive_password_manager import archive_password_manager
from core.logger import logger
from services.bulk_decompressor import (
    ArchiveItem,
    BulkDecompressorEngine,
    DiskCheckResult,
    get_7za_path,
)
from services.ffmpeg_manager import FfmpegDownloader, find_ffmpeg
from services.media_compressor import (
    CompressResult,
    CompressSettings,
    classify,
    compress_folder,
    compress_paths,
    detect_available_hwaccels,
    get_primary_hwaccel,
    media_in,
    validate_ffmpeg_settings,
)


class DecompressorBridge(
    QObject,
    DecompressorCompressionMixin,
    DecompressorItemsGroupsMixin,
    DecompressorExtractionMixin,
    DecompressorPasswordsMixin,
):
    """QML Bridge for bulk archive extraction, password bank management, and media compression."""

    def __init__(self, watchlist_manager, app_bridge=None, parent=None):
        super().__init__(parent)
        self._watchlist_manager = watchlist_manager
        self._app_bridge = app_bridge
        self.engine = BulkDecompressorEngine()

        self._items: List[ArchiveItem] = []
        self._items_lock = threading.RLock()  # Must be re-entrant: signal handlers may read itemsJson (which acquires the lock) while we already hold it
        self._custom_locations: List[Dict[str, str]] = []  # [{"path": ..., "creator": ...}]

        # State flags
        self._is_scanning = False
        self._is_extracting = False
        self._scan_cancel_event = threading.Event()
        self._extract_cancel_event = threading.Event()

        # Password prompt coordination
        self._auto_prompt_passwords = True
        self._skip_all_password_prompts = False
        self._prompt_events: Dict[str, threading.Event] = {}
        self._prompt_responses: Dict[str, Dict[str, Any]] = {}
        self._prompt_lock = threading.Lock()
        # Semaphore: ensures only one password prompt is shown at a time.
        # Parallel workers block here until the current prompt is dismissed.
        self._prompt_serial_sem = threading.BoundedSemaphore(1)
        self._guiCall.connect(self._run_gui_call, Qt.QueuedConnection)

        # Configurable Settings
        self._max_parallel = 2
        self._threads_per_archive = 2
        self._delete_after = False

        # Metrics for extraction
        self._total_bytes_to_extract = 0
        self._extracted_bytes_done = 0
        self._start_time = 0.0

        # Compress after extracting
        self._compress_after = False
        self._image_format = "webp"
        self._image_quality = 82
        self._video_format = "h265"
        self._video_quality = 75
        self._video_hwaccel = "auto"
        self._video_preset = "auto"
        self._audio_codec = "auto"
        self._custom_video_args = ""
        self._animated_format = "same"
        self._animated_quality = 82
        self._header_collapsed = False
        self._ffmpeg_path = find_ffmpeg()
        self._detected_hwaccel = ""
        self._available_hwaccels: List[str] = []
        self._probing_hwaccel = False
        self._hwaccel_probed_path = ""
        self._ffmpeg_downloader = FfmpegDownloader()
        self._ffmpeg_downloading = False
        self._ffmpeg_progress = 0.0
        self._ffmpeg_message = ""
        self._compress_procs: set = set()
        self._pending_originals: List[Tuple[str, str]] = []     # (original, compressed) awaiting the answer
        self._pending_source = "decompressor"                   # who asked: "decompressor" | "gallery"
        self._paths_cancel = threading.Event()
        self._compressing_paths = False
        self._count_gen = 0
        self._loading_settings = False
        self.settingsChanged.connect(self._save_settings)
        self.locationsChanged.connect(self._save_settings)

        # The list the view shows, kept in Python: a header row per (creator, folder) group followed by its
        # archives' rows (none while the group is folded). It was the whole list as JSON, rebuilt on the
        # window thread at every change, with every archive of a group built at once: 5,000 archives took
        # ~0.5 s to show, ~0.25 s per selection change, and 2–5 s when a creator had 500 archives. As one
        # flat list only the rows on screen exist; changes are gathered and applied together (on the next
        # turn of the event loop; progress ticks at most every 0.2 s) and only changed rows are redrawn.
        self._groups_model = RecordListModel(self, key_field="rowKey")
        self._group_count = 0
        self._any_collapsed = False
        self._collapsed: set = set()
        self._search = ""
        self._groups_timer = QTimer(self)
        self._groups_timer.setSingleShot(True)
        self._groups_timer.timeout.connect(self._refresh_groups)
        self.itemsChanged.connect(self._groups_soon, Qt.QueuedConnection)
        self.itemUpdated.connect(self._groups_later, Qt.QueuedConnection)
        self.passwordBankChanged.connect(self._groups_soon, Qt.QueuedConnection)

        # Reactive password bank binding: selection changes update matched status
        self.selectedStatsChanged.connect(self.passwordBankChanged)
        self.isExtractingChanged.connect(self.passwordBankChanged)

    @Slot(object)
    def _run_gui_call(self, fn) -> None:
        """Executes callables marshaled from background workers on the Qt GUI thread."""
        if callable(fn):
            fn()

    def _ensure_hwaccel_probed(self) -> None:
        ffmpeg_path = self._ffmpeg_path
        if (
            not ffmpeg_path
            or self._hwaccel_probed_path == ffmpeg_path
            or getattr(self, "_probing_hwaccel", False)
            or not self.ffmpegAvailable
        ):
            return
        self._start_async_hwaccel_probe()

    def _start_async_hwaccel_probe(self):
        ffmpeg_path = self._ffmpeg_path
        if (
            getattr(self, "_probing_hwaccel", False)
            or not ffmpeg_path
            or self._hwaccel_probed_path == ffmpeg_path
        ):
            return
        self._probing_hwaccel = True

        def _worker():
            changed = False
            try:
                accels = detect_available_hwaccels(ffmpeg_path)
                primary = accels[0] if accels else ""
                if self._ffmpeg_path == ffmpeg_path:
                    changed = (accels != self._available_hwaccels) or (primary != self._detected_hwaccel)
                    self._available_hwaccels = accels
                    self._detected_hwaccel = primary
                    self._hwaccel_probed_path = ffmpeg_path
            except Exception as e:
                if self._ffmpeg_path == ffmpeg_path:
                    self._hwaccel_probed_path = ffmpeg_path
                logger.debug(f"Hardware probe error: {e}", category="decompressor")
            finally:
                self._probing_hwaccel = False
            if changed:
                self.ffmpegChanged.emit()

        threading.Thread(target=_worker, daemon=True, name="HwAccelProbe").start()
