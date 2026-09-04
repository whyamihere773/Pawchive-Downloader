"""
Localization & Translation Manager Subsystem
Loads locale dictionaries from isolated JSON files in the locales/ directory.
Exposes reactive translation properties and helper methods to QML and Python.
"""

import os
import sys
import json
import re
from typing import Dict, Any, List
from PySide6.QtCore import QObject, Signal, Property, Slot, QLocale
from core.logger import logger


class TranslationManager(QObject):
    languageChanged = Signal()

    SUPPORTED_LANGUAGES = [
        {"code": "auto", "name": "System Default", "native": "System Default (Auto)"},
        {"code": "en", "name": "English", "native": "English"},
        {"code": "zh_CN", "name": "Chinese Simplified", "native": "简体中文"},
        {"code": "zh_TW", "name": "Chinese Traditional", "native": "繁體中文"},
        {"code": "ja", "name": "Japanese", "native": "日本語"},
        {"code": "ko", "name": "Korean", "native": "한국어"},
        {"code": "es", "name": "Spanish", "native": "Español"},
        {"code": "pt", "name": "Portuguese", "native": "Português"},
        {"code": "fr", "name": "French", "native": "Français"},
        {"code": "de", "name": "German", "native": "Deutsch"},
        {"code": "ru", "name": "Russian", "native": "Русский"},
        {"code": "th", "name": "Thai", "native": "ไทย"},
        {"code": "vi", "name": "Vietnamese", "native": "Tiếng Việt"},
        {"code": "id", "name": "Indonesian", "native": "Bahasa Indonesia"},
        {"code": "tr", "name": "Turkish", "native": "Türkçe"},
    ]

    def __init__(self, locales_dir: str = None, parent: QObject = None):
        super().__init__(parent)

        if not locales_dir:
            if getattr(sys, "frozen", False):
                if hasattr(sys, "_MEIPASS") and os.path.exists(os.path.join(sys._MEIPASS, "locales")):
                    base_dir = sys._MEIPASS
                else:
                    cand = os.path.join(os.path.dirname(sys.executable), "_internal")
                    base_dir = cand if os.path.exists(cand) else os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self._locales_dir = os.path.join(base_dir, "locales")
        else:
            self._locales_dir = locales_dir

        self._selected_code: str = "auto"
        self._active_code: str = "en"
        self._translations: Dict[str, str] = {}
        self._fallback_en: Dict[str, str] = {}

        self._load_fallback()
        self.setLanguage("auto")

    def _load_fallback(self):
        en_path = os.path.join(self._locales_dir, "en.json")
        if os.path.exists(en_path):
            try:
                with open(en_path, "r", encoding="utf-8") as f:
                    self._fallback_en = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load fallback en.json: {e}", category="i18n")

    def _detect_system_locale(self) -> str:
        try:
            sys_name = QLocale.system().name()  # e.g. "zh_CN", "ja_JP", "fr_FR", "ru_RU"
            lang = sys_name.split("_")[0].lower()
            
            # Direct matches
            if sys_name.lower() in ("zh_cn", "zh_hans", "zh_sg"):
                return "zh_CN"
            if sys_name.lower() in ("zh_tw", "zh_hant", "zh_hk", "zh_mo"):
                return "zh_TW"
            
            # Match 2-letter language prefix
            prefix_map = {
                "zh": "zh_CN",
                "ja": "ja",
                "ko": "ko",
                "es": "es",
                "pt": "pt",
                "fr": "fr",
                "de": "de",
                "ru": "ru",
                "th": "th",
                "vi": "vi",
                "id": "id",
                "in": "id",  # older Indonesian code
                "tr": "tr",
            }
            if lang in prefix_map:
                return prefix_map[lang]
        except Exception as e:
            logger.warning(f"Could not detect system locale: {e}", category="i18n")
        return "en"

    def _load_language(self, code: str):
        target_code = self._detect_system_locale() if code == "auto" else code
        file_path = os.path.join(self._locales_dir, f"{target_code}.json")

        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self._translations = json.load(f)
                self._active_code = target_code
                return
            except Exception as e:
                logger.error(f"Failed to load locale {target_code}: {e}", category="i18n")

        # Fallback to English if file not found or load failed
        self._translations = dict(self._fallback_en)
        self._active_code = "en"

    @Property(str, notify=languageChanged)
    def currentLanguage(self) -> str:
        return self._selected_code

    @currentLanguage.setter
    def currentLanguage(self, code: str):
        self.setLanguage(code)

    @Property(str, notify=languageChanged)
    def activeLanguage(self) -> str:
        return self._active_code

    @Property(list, notify=languageChanged)
    def availableLanguages(self) -> List[Dict[str, str]]:
        return self.SUPPORTED_LANGUAGES

    @Property('QVariantMap', notify=languageChanged)
    def strings(self) -> Dict[str, str]:
        merged = dict(self._fallback_en)
        merged.update(self._translations)
        return merged


    @Slot(str)
    def setLanguage(self, code: str):
        if not code or code not in [l["code"] for l in self.SUPPORTED_LANGUAGES]:
            code = "auto"
        self._selected_code = code
        self._load_language(code)
        logger.info(f"Language set to: '{code}' (Active: '{self._active_code}')", category="i18n")
        self.languageChanged.emit()

    @Slot(str, result=str)
    def t(self, key: str) -> str:
        """Translates a key into the active locale, falling back to English or the key itself."""
        if not key:
            return ""
        if key in self._translations:
            return self._translations[key]
        if key in self._fallback_en:
            return self._fallback_en[key]
        return key

    # Pre-compiled regex patterns for common application log messages
    LOG_PATTERNS = [
        ("log_ytdlp_up_to_date", re.compile(r"^yt-dlp is already up to date\.$")),
        ("log_checking_ytdlp", re.compile(r"^Checking for yt-dlp updates\.\.\.$")),
        ("log_ytdlp_updated", re.compile(r"^yt-dlp successfully updated to latest version!$")),
        ("log_init_suite", re.compile(r"^Initializing Kemono & Pawchive Desktop Suite\.\.\.$")),
        ("log_app_initialized", re.compile(r"^Application interface initialized successfully\.$")),
        ("log_download_paused", re.compile(r"^Download paused\.$")),
        ("log_download_resumed", re.compile(r"^Download resumed\.$")),
        ("log_download_cancel_req", re.compile(r"^Download cancellation requested\.$")),
        ("log_active_stopped_session_discarded", re.compile(r"^Active download stopped and session discarded\.$")),
        ("log_saved_session_discarded", re.compile(r"^Saved session discarded\.$")),
        ("log_session_saved", re.compile(r"^Current download session state saved\.$")),
        ("log_settings_saved", re.compile(r"^Application settings saved\.$")),
        ("log_manga_mode_active", re.compile(r"^Manga Mode active: Sorting posts chronologically \(oldest first\)\.\.\.$")),
        ("log_session_cookie_loaded", re.compile(r"^Session cookie loaded into HTTP client\.$")),
        ("log_queue_cleared", re.compile(r"^Queue cleared\.$")),
        ("log_history_cleared", re.compile(r"^History cleared\.$")),
        ("log_rate_limit_encountered", re.compile(r"^⚡ \[Rate Limit Cooldown\] HTTP 429 encountered! Threads locked at (\d+) \(cooldown (\d+)s\)\.\.\.$")),
        ("log_ytdlp_downloading", re.compile(r"^Downloading latest yt-dlp\.exe from GitHub to (.+?)\.\.\.$")),
        ("log_ytdlp_installed", re.compile(r"^yt-dlp\.exe successfully installed \((.+?)\)$")),
        ("log_loading_qml", re.compile(r"^Loading QML interface from: (.+)$")),
        ("log_char_filter_scope_default", re.compile(r"^Character filter scope set to default: '(.+?)'$")),
        ("log_filename_style_loaded", re.compile(r"^filename style loaded: '(.+?)'$")),
        ("log_skip_scope_loaded", re.compile(r"^Skip words scope loaded: '(.+?)'$")),
        ("log_known_mode_set", re.compile(r"^Known character recognition mode set to: '(.+?)'$")),
        ("log_exported_links", re.compile(r"^Exported (\d+) links to: (.+)$")),
        ("log_links_exported_to", re.compile(r"^Links exported to: (.+)$")),
        ("log_loaded_history", re.compile(r"^Loaded (\d+) last downloaded files and (\d+) processed posts from history\.$")),
        ("log_loaded_master_db", re.compile(r"^Loaded Master Database \(fast binary cache\): (\d+) characters across (\d+) franchises\.$")),
        ("log_loaded_known_txt", re.compile(r"^Loaded (\d+) known characters/series from Known\.txt \((\d+) franchises\)$")),
        ("log_saved_known_txt", re.compile(r"^Saved (\d+) entries to Known\.txt$")),
        ("log_created_known_txt", re.compile(r"^Created default structured Known\.txt at: (.+)$")),
        ("log_structuring_plan", re.compile(r"^Structuring download plan for (\d+) posts\.\.\.$")),
        ("log_prepared_tasks", re.compile(r"^Prepared (\d+) file download tasks\.$")),
        ("log_flagged_retry", re.compile(r"^Flagged (\d+) failed tasks for retry\.$")),
        ("log_flagged_selected_retry", re.compile(r"^Flagged (\d+) selected tasks for retry\.$")),
        ("log_all_failed_requeued", re.compile(r"^All (\d+) failed tasks re-queued\.$")),
        ("log_post_action_queued", re.compile(r"^Post-download action '(.+?)' queued — showing 15s countdown modal\.$")),
        ("log_post_action_exec", re.compile(r"^Executing post-download action: (.+)$")),
        ("log_post_action_cancelled", re.compile(r"^Post-download action '(.+?)' cancelled by user\.$")),
        ("log_throttled_threads", re.compile(r"^UI concurrency slider auto-throttled to (\d+) threads due to rate limiting\.$")),
        ("log_links_scan_complete", re.compile(r"^Links scan complete: found (\d+) external links\.$")),
        ("log_skipped_invalid_url", re.compile(r"^Skipped invalid URL in batch: (.+)$")),
        ("log_skipped_post", re.compile(r"^Skipped post \[(\d+)\] '(.+?)': (.+)$")),
        ("log_skipped_file", re.compile(r"^Skipped file '(.+?)': (.+)$")),
        ("log_completed_files", re.compile(r"^Completed \((\d+) files\)$")),
        ("log_finished_errors", re.compile(r"^Finished with (\d+) error\(s\) \((\d+)/(\d+) completed\)$")),
        ("log_starting_download", re.compile(r"^Starting download for (.+?)\.\.\.$")),
        ("log_fetched_posts", re.compile(r"^Fetched (\d+) posts\.\.\.$")),
        ("log_language_set", re.compile(r"^Language set to: '(.+?)' \(Active: '(.+?)'\)$")),
        ("log_already_downloaded", re.compile(r"^Already downloaded \(history\): (.+)$")),
        # Adaptive Threading
        ("log_adaptive_active", re.compile(r"^⚡ \[Adaptive Threading\] Active: Starting with (\d+) worker threads \(Max CPU limit: (\d+) threads\)\.\.\.$")),
        ("log_adaptive_scaling_up", re.compile(r"^⚡ \[Adaptive Threading\] Connection stable\. Scaling up concurrency to (\d+)/(\d+) threads \(ceiling: (\d+)\)\.\.\.$")),
        ("log_adaptive_longterm", re.compile(r"^⚡ \[Adaptive Threading\] Long-term stability verified \(50\+ clean files\)\. Probing higher concurrency \(\+1 to (\d+) threads\)\.\.\.$")),
        ("log_adaptive_fast_scale", re.compile(r"^⚡ \[Adaptive Threading\] Fast-scaling concurrency to (\d+)/(\d+) threads\.\.\.$")),
        # Download pool
        ("log_pool_start", re.compile(r"^Starting download pool with (\d+) worker threads\.\.\.$")),
        ("log_pool_start_locked", re.compile(r"^Starting download pool with (\d+) worker threads \(Locked\)\.\.\.$")),
        # Chunked / multipart download
        ("log_chunked_download", re.compile(r"^\s*⚡\s*Activating 4-part parallel chunked download for (.+?) \((.+?)\)$")),
        ("log_multipart_fallback", re.compile(r"^\s*↪\s*Multipart fallback: (.+?) — switching to standard single stream download\.\.\.$")),
        # File events
        ("log_skip_existing", re.compile(r"^⏳ Skipping existing file: '(.+?)' \(already present on disk\)$")),
        ("log_skip_existing2", re.compile(r"^⏳ Skipping existing file: '(.+?)' \(already complete on disk\)$")),
        ("log_ytdlp_dl_media", re.compile(r"^▶ \[yt-dlp\] Downloading embedded player media: (.+)$")),
        ("log_auto_retry", re.compile(r"^🔄 Auto-retry triggered for (\d+) failed files\.\.\.$")),
        ("log_auto_learned", re.compile(r"^✨ Auto-learned (\d+) character\(s\) into Known list: (.+)$")),
        ("log_download_complete", re.compile(r"^Download completed in ([\d.]+)s! \((\d+) successful, (\d+) errors\)$")),
        ("log_download_cancelled", re.compile(r"^Download cancelled\. Completed: (\d+), Failed/Cancelled: (\d+)$")),
        # Concurrency & Downloader state
        ("log_downloader_already_active", re.compile(r"^Downloader is already active\.$")),
        ("log_download_process_running", re.compile(r"^Download process is already running!$")),
        ("log_no_failed_tasks", re.compile(r"^No failed tasks to retry\.$")),
        ("log_no_tasks_selected", re.compile(r"^No tasks selected for retry\.$")),
        ("log_no_matching_failed", re.compile(r"^No matching failed tasks found to retry\.$")),
        ("log_no_files_matched_filter", re.compile(r"^No files matched filtering criteria\.$")),
        ("log_no_saved_session", re.compile(r"^No saved download session found\.$")),
        ("log_incomplete_session_found", re.compile(r"^Incomplete download session found\. UI updated for restore\.$")),
        ("log_auto_retry_starting", re.compile(r"^Auto-Retry enabled with failed tasks present — starting retry queue\.\.\.$")),
        ("log_auto_retry_activated", re.compile(r"^Auto-Retry activated for failed tasks\.\.\.$")),
        ("log_app_closing_stopping_threads", re.compile(r"^Application closing: saving active session and stopping threads\.\.\.$")),
        ("log_no_harvested_links_export", re.compile(r"^No harvested links or queued tasks to export\.$")),
        ("log_no_links_cloud_download", re.compile(r"^No links selected for cloud download\.$")),
        ("log_cloud_download_cancel_req", re.compile(r"^Cloud downloads cancellation requested\.$")),
        ("log_no_valid_urls_batch", re.compile(r"^No valid URLs found in batch input\.$")),
        ("log_closing_app_after_download", re.compile(r"^Closing application as requested after download\.$")),
    ]

    @Slot(str, str, result=str)
    def translateLog(self, message: str, level: str = "") -> str:
        """
        Translates a log message into the active language, skipping errors.
        Extracts dynamic variables and formats them into the translated template.
        """
        if not message:
            return ""
        # Do not translate errors (as requested: 'beside errors')
        if level and str(level).strip().upper() in ("ERROR", "ERR"):
            return message
        if self._active_code == "en":
            return message

        for key, pattern in self.LOG_PATTERNS:
            match = pattern.match(message)
            if match:
                template = self.t(key)
                if template and template != key:
                    for idx, group_val in enumerate(match.groups()):
                        template = template.replace(f"{{{idx}}}", group_val).replace(f"%{idx+1}", group_val)
                    return template
                break

        return message

