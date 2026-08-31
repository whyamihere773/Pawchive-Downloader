"""
Known Series and Character Manager
Handles persistent storage, categorization matching, and synchronization of Known.txt.
"""

import sys
import os
import re
from typing import List, Optional
from core.logger import logger


class KnownManager:
    def __init__(self, file_path: Optional[str] = None):
        if file_path:
            self.file_path = file_path
        else:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.file_path = os.path.join(base_dir, "config", "Known.txt")

        self.entries: List[str] = []
        self.load()

    def load(self):
        self.entries.clear()
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            default_entries = [
                "Final Fantasy",
                "Tifa",
                "Aerith",
                "Genshin Impact",
                "Raiden Shogun",
                "Yelan",
                "Honkai Star Rail",
                "Firefly",
                "Kafka",
                "Original",
                "Fate Grand Order",
                "Artoria",
                "Morgan"
            ]
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    for entry in default_entries:
                        f.write(f"{entry}\n")
                self.entries = list(default_entries)
                logger.info(f"Created default Known.txt at: {self.file_path}", category="known")
            except Exception as e:
                logger.error(f"Failed to create Known.txt: {e}", category="known")
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith("#"):
                        if cleaned not in self.entries:
                            self.entries.append(cleaned)
            logger.info(f"Loaded {len(self.entries)} known characters/series from Known.txt", category="known")
        except Exception as e:
            logger.error(f"Failed to read Known.txt: {e}", category="known")

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                for entry in self.entries:
                    f.write(f"{entry}\n")
            logger.success(f"Saved {len(self.entries)} entries to Known.txt", category="known")
        except Exception as e:
            logger.error(f"Failed to save Known.txt: {e}", category="known")

    def add_entry(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        if name not in self.entries:
            self.entries.append(name)
            self.save()
            return True
        return False

    def remove_entry(self, name: str) -> bool:
        if name in self.entries:
            self.entries.remove(name)
            self.save()
            return True
        return False

    def remove_at_index(self, index: int) -> bool:
        if 0 <= index < len(self.entries):
            self.entries.pop(index)
            self.save()
            return True
        return False

    def search(self, query: str) -> List[str]:
        if not query:
            return list(self.entries)
        q = query.lower()
        return [item for item in self.entries if q in item.lower()]

    def find_matching_category(self, title: str) -> Optional[str]:
        if not title:
            return None

        for item in self.entries:
            if re.search(r"\b" + re.escape(item) + r"\b", title, re.IGNORECASE):
                return item
        return None
