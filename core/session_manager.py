"""
Session & History Persistence Manager
Handles queue persistence, history records, application settings, and link file exports.
"""

import sys
import json
import os
import datetime
from typing import Dict, Any, List, Optional
from core.logger import logger


class SessionManager:
    def __init__(self, config_dir: Optional[str] = None):
        if not config_dir:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_dir = os.path.join(base_dir, "config")
        else:
            self.config_dir = config_dir

        os.makedirs(self.config_dir, exist_ok=True)
        self.session_file = os.path.join(self.config_dir, "session.json")
        self.history_file = os.path.join(self.config_dir, "history.json")
        self.settings_file = os.path.join(self.config_dir, "settings.json")

        self.history: Dict[str, Any] = {"downloaded_files": [], "processed_posts": []}
        self.load_history()

    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
                logger.info(
                    f"Loaded {len(self.history.get('downloaded_files', []))} last downloaded files and "
                    f"{len(self.history.get('processed_posts', []))} processed posts from history.",
                    category="session"
                )
            except Exception as e:
                logger.warning(f"Could not load download history: {e}", category="session")

    def save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save download history: {e}", category="session")

    def record_downloaded_file(self, file_id_or_path: str):
        if "downloaded_files" not in self.history:
            self.history["downloaded_files"] = []
        if file_id_or_path not in self.history["downloaded_files"]:
            self.history["downloaded_files"].append(file_id_or_path)
            if len(self.history["downloaded_files"]) > 50000:
                self.history["downloaded_files"] = self.history["downloaded_files"][-50000:]
            self.save_history()

    def is_file_downloaded(self, file_id_or_path: str) -> bool:
        return file_id_or_path in self.history.get("downloaded_files", [])

    def record_download_session(self, creator_name: str, url: str, service: str, file_count: int):
        if "download_history" not in self.history:
            self.history["download_history"] = []
        entry = {
            "creator": creator_name,
            "url": url,
            "service": service,
            "files": file_count,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        self.history["download_history"].insert(0, entry)
        if len(self.history["download_history"]) > 500:
            self.history["download_history"] = self.history["download_history"][:500]
        self.save_history()

    def get_download_history(self):
        return self.history.get("download_history", [])

    def save_session(self, session_data: Dict[str, Any]):
        try:
            session_data["saved_at"] = datetime.datetime.now().isoformat()
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
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
            "page_end": 999,
            "filename_style": "post_title",
            "character_scope": "title",
            "skip_scope": "posts",
            "subfolder_per_post": True,
            "date_prefix": True,
            "separate_by_known": False,
            "download_revisions": False,
            "compress_webp": False,
            "keep_duplicates": False,
            "scan_content_images": True,
            "dark_theme": True,
            "auto_sync_known": True,
            "open_folder_on_complete": False,
            "play_completion_sound": False,
            "post_download_action": "none",
            "known_recognition_mode": "hybrid",
            "language": "auto"
        }

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    default_settings.update(saved)
            except Exception as e:
                logger.warning(f"Failed to load settings.json: {e}", category="session")

        return default_settings

    def save_settings(self, settings_data: Dict[str, Any], silent: bool = False):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, indent=2, ensure_ascii=False)
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
