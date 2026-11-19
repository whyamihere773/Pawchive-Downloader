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



class AiKnownMixin(AppBridgeSignalsMixin):
    @Property(str, notify=AppBridgeSignalsMixin.knownRecognitionModeChanged)
    def knownRecognitionMode(self) -> str:
        return self._known_recognition_mode

    @knownRecognitionMode.setter
    def knownRecognitionMode(self, val: str):
        allowed = {"hybrid", "database_only", "learning_only"}
        if val not in allowed:
            val = "hybrid"
        if self._known_recognition_mode != val:
            self._known_recognition_mode = val
            self.known_manager.set_mode(val)
            self.knownRecognitionModeChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.aiRecognitionEnabledChanged)
    def aiRecognitionEnabled(self) -> bool:
        return self._ai_recognition_enabled

    @aiRecognitionEnabled.setter
    def aiRecognitionEnabled(self, val: bool):
        val = bool(val)
        if self._ai_recognition_enabled != val:
            self._ai_recognition_enabled = val
            self.known_manager.enable_ai(val, model_manager=self.model_manager)
            self.aiRecognitionEnabledChanged.emit()
            self.saveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.aiEngineModeChanged)
    def aiEngineMode(self) -> str:
        return self._ai_engine_mode

    @aiEngineMode.setter
    def aiEngineMode(self, val: str):
        allowed = {"semantic_only", "hybrid"}
        if val in allowed and self._ai_engine_mode != val:
            self._ai_engine_mode = val
            self.known_manager.set_ai_engine_mode(val)
            self.aiEngineModeChanged.emit()
            self.saveSettings()

    @Property(str, notify=AppBridgeSignalsMixin.aiHardwareInfoChanged)
    def aiHardwareBadge(self) -> str:
        info = HardwareDetector.cached_info()
        if info is None:
            # Detected in the background; the badge updates when it's known
            HardwareDetector.probe_async(lambda: self.aiHardwareInfoChanged.emit())
            return "Detecting hardware…"
        return str(info.get("provider_name", "CPU Mode"))

    @Property(bool, notify=AppBridgeSignalsMixin.aiRecognitionEnabledChanged)
    def aiFastSemanticReady(self) -> bool:
        return self.model_manager.is_model_ready("fast_semantic")

    @Property(bool, notify=AppBridgeSignalsMixin.aiRecognitionEnabledChanged)
    def aiDeepReasonerReady(self) -> bool:
        from core.ai_reasoner import has_llama_cpp
        if not has_llama_cpp():
            return False
        return (
            self.model_manager.is_model_ready("deep_reasoner_heavy")
            or self.model_manager.is_model_ready("deep_reasoner_light")
            or self.model_manager.is_model_ready("deep_reasoner")
        )

    @Property(str, notify=AppBridgeSignalsMixin.aiRecognitionEnabledChanged)
    def aiDeepReasonerVariant(self) -> str:
        return self._ai_deep_reasoner_variant

    @aiDeepReasonerVariant.setter
    def aiDeepReasonerVariant(self, val: str):
        allowed = {"light", "heavy"}
        if val in allowed and self._ai_deep_reasoner_variant != val:
            self._ai_deep_reasoner_variant = val
            self.aiRecognitionEnabledChanged.emit()
            self.saveSettings()

    @Property(bool, notify=AppBridgeSignalsMixin.aiRecognitionEnabledChanged)
    def aiDeepReasonerLightReady(self) -> bool:
        return self.model_manager.is_model_ready("deep_reasoner_light")

    @Property(bool, notify=AppBridgeSignalsMixin.aiRecognitionEnabledChanged)
    def aiDeepReasonerHeavyReady(self) -> bool:
        return self.model_manager.is_model_ready("deep_reasoner_heavy")

    @Slot(str, result="QVariant")
    def getAiModelStatus(self, model_key: str):
        if HardwareDetector.cached_info() is None:
            # Hardware is detected in the background; the AI section refreshes when it's known
            HardwareDetector.probe_async(lambda: self.aiHardwareInfoChanged.emit())
        return self.model_manager.get_status(model_key)

    @Slot(str)
    def startAiModelDownload(self, model_key: str):
        self.model_manager.start_download(model_key)

    @Slot(str)
    def cancelAiModelDownload(self, model_key: str):
        self.model_manager.cancel_download(model_key)

    @Slot(str, result=bool)
    def deleteAiModel(self, model_key: str) -> bool:
        # A loaded model keeps its files open (Windows won't delete them), so unload it first
        km = getattr(self, "known_manager", None)
        for engine in (getattr(km, "semantic_matcher", None), getattr(km, "contextual_reasoner", None)):
            if engine is not None and hasattr(engine, "unload"):
                try:
                    engine.unload()
                except Exception:
                    logger.exception("Couldn't unload an AI model before deleting it", category="ai")
        res = self.model_manager.delete_model(model_key)
        self.aiRecognitionEnabledChanged.emit()
        return res

    @Slot(str, result="QVariant")
    def testAiRecognition(self, test_title: str):
        """Runs test inference across Tier 0, Tier 1, and Tier 2 for interactive sandbox."""
        clean_t = (test_title or "").strip()
        if not clean_t:
            return {"error": "Empty test title"}

        # Tier 0 (Fast heuristic)
        t0_res = self.known_manager._find_matching_hierarchy_fast(clean_t, [], [])
        t0_str = f"{t0_res[1]} ({t0_res[0]})" if (t0_res and t0_res[1]) else (t0_res[0] if t0_res else "None")

        # Tier 1 (Semantic matcher)
        t1_str = "Not available (model not downloaded)"
        if self.model_manager.is_model_ready("fast_semantic"):
            if self.known_manager.semantic_matcher:
                if self.known_manager.semantic_matcher._cached_vectors is None:
                    self.known_manager.semantic_matcher.build_known_index(self.known_manager)
                m = self.known_manager.semantic_matcher.find_match(clean_t, threshold=0.70)
                if m:
                    t1_str = f"{m[1]} ({m[0]}) [score={m[2]:.2f}]"
                else:
                    t1_str = "No match above threshold"

        # Final resolved hierarchy using standard engine
        final = self.known_manager.find_matching_hierarchy(clean_t)
        final_str = f"{final[1]} ({final[0]})" if (final and final[1]) else (final[0] if final else "Uncategorized")

        return {
            "title": clean_t,
            "tier0": t0_str,
            "tier1": t1_str,
            "final": final_str,
            "hardware": (HardwareDetector.cached_info() or {}).get("provider_name", "Detecting hardware…")
        }

    @Slot()
    def clearLogs(self):
        self._log_model.clearLogs()

    @Slot(str)
    def logsUsageAsync(self, request_id: str):
        """logsUsage in the background (answer: asyncResultReady). Sizing thousands of log files
        held up the Settings page while it opened."""
        self._run_async(request_id, self.logsUsage)

    @Slot(result="QVariant")
    def logsUsage(self) -> dict:
        """How many log files there are and how much space they take (Settings → Logs)."""
        u = logger.logs_usage()
        return {
            "files": u["files"],
            "bytes": u["bytes"],
            "text": f"{u['files']:,} file{'s' if u['files'] != 1 else ''} · {FilterEngine.format_size_str(u['bytes'])}",
            "folder": logger.get_logs_dir(),
        }

    @Slot(result="QVariant")
    def deleteAllLogs(self) -> dict:
        """Delete every log file except the one this session is writing. Only runs when the user asks."""
        r = logger.delete_all_logs()
        text = f"Deleted {r['deleted']:,} log file(s), freed {FilterEngine.format_size_str(r['freed'])}."
        if r["failed"]:
            text += f" {r['failed']} file(s) couldn't be deleted (in use or read-only)."
        logger.info(text + " (Requested from Settings.)", category="logger")
        return {"deleted": r["deleted"], "failed": r["failed"], "text": text}

    @Slot()
    def openLogsFolder(self):
        logs_dir = logger.get_logs_dir()
        os.makedirs(logs_dir, exist_ok=True)
        if os.name == "nt":
            os.startfile(logs_dir)
        else:
            subprocess.Popen(["xdg-open", logs_dir], **subprocess_env_kwargs())

    @Slot(str)
    def copyToClipboard(self, text: str):
        """Copies given text to the system clipboard in a thread-safe manner."""
        try:
            from PySide6.QtGui import QGuiApplication
            cb = QGuiApplication.clipboard()
            if cb:
                cb.setText(str(text))
        except Exception as e:
            logger.debug(f"Failed to copy to clipboard: {e}", category="system")

    @Slot()
    def openDownloadFolder(self):
        os.makedirs(self._download_dir, exist_ok=True)
        if os.name == "nt":
            os.startfile(self._download_dir)
        else:
            subprocess.Popen(["xdg-open", self._download_dir], **subprocess_env_kwargs())

    @Slot()
    def openKnownTxt(self):
        path = self.known_manager.file_path
        if not os.path.exists(path):
            self.known_manager.save()
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path], **subprocess_env_kwargs())

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
