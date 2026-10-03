"""
Session & History Persistence Manager
Handles queue persistence, history records, application settings, and link file exports.
"""

import json
import os
import time
import datetime
import threading
from typing import Dict, Any, List, Optional
from core.logger import logger
from core.recovery_manager import RecoveryManager
from core.atomic_io import atomic_write_json

# Settings that must never be written to settings.json (the login cookie lives in the encrypted vault)
_NEVER_SAVED_SETTINGS = ("cookie",)


from core.path_utils import get_config_dir


class SessionManager:
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = get_config_dir(config_dir)

        os.makedirs(self.config_dir, exist_ok=True)
        self.recovery_manager = RecoveryManager(self.config_dir)
        self.session_file = os.path.join(self.config_dir, "session.json")
        self.history_file = os.path.join(self.config_dir, "history.json")
        self.settings_file = os.path.join(self.config_dir, "settings.json")

        self.history: Dict[str, Any] = {"downloaded_files": [], "processed_posts": []}
        self._downloaded_files_set: set = set()
        # The download loop and the window both record history; one lock keeps history.json whole,
        # and a second one keeps saves in order (an older snapshot never overwrites a newer one)
        self._history_lock = threading.RLock()
        self._history_write_lock = threading.Lock()
        self._history_save_timer: Optional[threading.Timer] = None
        self._settings_lock = threading.Lock()
        self.load_history()

    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
                self._downloaded_files_set = set(self.history.get("downloaded_files", []))
                logger.info(
                    f"Loaded {len(self.history.get('downloaded_files', []))} last downloaded files and "
                    f"{len(self.history.get('processed_posts', []))} processed posts from history.",
                    category="session"
                )
            except Exception as e:
                logger.warning(f"Could not load download history: {e}", category="session")

    def save_history(self):
        """Writes history.json now (crash-safe: a cut-off write never leaves a broken file)."""
        with self._history_write_lock:
            with self._history_lock:
                timer, self._history_save_timer = self._history_save_timer, None
                try:
                    payload = json.dumps(self.history, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Failed to save download history: {e}", category="session")
                    return
            if timer is not None:
                timer.cancel()
            try:
                from core.atomic_io import atomic_write_text
                atomic_write_text(self.history_file, payload)
            except Exception as e:
                logger.error(f"Failed to save download history: {e}", category="session")

    def _schedule_history_save(self, delay: float = 3.0):
        """Saves history a few seconds after the latest change, in the background (writing up to
        50,000 entries from the download loop every 3 s stalled downloads on slow drives)."""
        with self._history_lock:
            if self._history_save_timer is not None:
                return
            timer = threading.Timer(delay, self.save_history)
            timer.daemon = True
            self._history_save_timer = timer
        timer.start()

    def flush_history(self):
        """Writes a pending history save right away (call before the app closes)."""
        with self._history_lock:
            pending = self._history_save_timer is not None
        if pending:
            self.save_history()

    def record_downloaded_file(self, file_id_or_path: str):
        with self._history_lock:
            if "downloaded_files" not in self.history:
                self.history["downloaded_files"] = []
            if file_id_or_path in self._downloaded_files_set:
                return
            self._downloaded_files_set.add(file_id_or_path)
            self.history["downloaded_files"].append(file_id_or_path)
            if len(self.history["downloaded_files"]) > 50000:
                removed = self.history["downloaded_files"][:-50000]
                self.history["downloaded_files"] = self.history["downloaded_files"][-50000:]
                self._downloaded_files_set.difference_update(removed)
        self._schedule_history_save()

    def is_file_downloaded(self, file_id_or_path: str) -> bool:
        return file_id_or_path in self._downloaded_files_set

    def record_download_session(self, creator_name: str, url: str, service: str, file_count: int):
        with self._history_lock:
            if "download_history" not in self.history:
                self.history["download_history"] = []
        entry = {
            "creator": creator_name,
            "url": url,
            "service": service,
            "files": file_count,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        with self._history_lock:
            self.history["download_history"].insert(0, entry)
            if len(self.history["download_history"]) > 500:
                self.history["download_history"] = self.history["download_history"][:500]
        self._schedule_history_save(delay=0.5)

    def get_download_history(self):
        return self.history.get("download_history", [])

    def save_session(self, session_data: Dict[str, Any]):
        try:
            session_data["saved_at"] = datetime.datetime.now().isoformat()
            tmp_path = f"{self.session_file}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp_path, self.session_file)
            logger.info("Current download session state saved.", category="session")
        except Exception as e:
            logger.error(f"Failed to save session state: {e}", category="session")

    def get_saved_session(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.session_file):
            return None
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and (data.get("queue") or data.get("url")):
                    return data
        except Exception as e:
            logger.warning(f"Failed to read session file: {e}", category="session")
        return None

    def discard_session(self) -> bool:
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
                logger.info("Saved session discarded.", category="session")
                return True
            except Exception as e:
                logger.error(f"Could not discard session: {e}", category="session")
        return False

    def load_settings(self) -> Dict[str, Any]:
        default_settings = {
            "download_dir": os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads"),
            "threads": 4,
            "cookie": "",
            "user_agent": "",
            "page_start": 1,
            "page_end": 999999,
            "filename_style": "post_title",
            "character_scope": "title",
            "skip_scope": "posts",
            "subfolder_per_post": True,
            "date_prefix": True,
            "file_index_prefix": False,
            "group_file_type": "none",
            "separate_by_known": False,
            "download_revisions": False,
            "compress_webp": False,
            "keep_duplicates": False,
            "scan_content_images": True,
            "fallback_to_thumbnails": False,
            "redownload_small_files": False,
            "dark_theme": True,
            "auto_sync_known": True,
            "open_folder_on_complete": False,
            "play_completion_sound": False,
            "post_download_action": "none",
            "known_recognition_mode": "hybrid",
            "language": "auto",
            "tag_folder_mode": False,
            "storage_pool_enabled": False,
            "storage_pool_margin_gb": 10.0,
            "storage_pool_drives": [],
            "scheduler_enabled": False,
            "scheduler_lock_threads_delay": True,
            "scheduler_night_owl_enabled": False,
            "scheduler_night_owl_start": "01:00",
            "scheduler_night_owl_end": "07:00",
            "scheduler_prevent_sleep": True,
            "scheduler_sweep_retry": True,
            "cookie_watchdog_enabled": True,
            "exact_extensions": "",
            "saved_custom_extensions": [],
            "gallery_bookmarks": []
        }

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    default_settings.update(saved)
            except Exception as e:
                logger.warning(f"Failed to load settings.json: {e}", category="session")
                # Keep the unreadable file for inspection instead of overwriting it on the next save
                try:
                    import shutil
                    shutil.copy2(self.settings_file, f"{self.settings_file}.unreadable-{int(time.time())}")
                except Exception:
                    pass

        return default_settings

    def save_settings(self, settings_data: Dict[str, Any], silent: bool = False):
        """Writes settings.json crash-safely (a crash mid-write used to reset all settings).
        The login cookie is never written here: it is kept in the encrypted credentials vault."""
        data = {k: v for k, v in settings_data.items() if k not in _NEVER_SAVED_SETTINGS}
        try:
            with self._settings_lock:
                atomic_write_json(self.settings_file, data, indent=2)
            if not silent:
                logger.info("Application settings saved.", category="session")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}", category="session")

    def export_links_to_file(self, links: List[str], file_path: str) -> bool:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for link in links:
                    f.write(f"{link}\n")
            logger.success(f"Exported {len(links)} links to: {file_path}", category="session")
            return True
        except Exception as e:
            logger.error(f"Failed to export links: {e}", category="session")
            return False
