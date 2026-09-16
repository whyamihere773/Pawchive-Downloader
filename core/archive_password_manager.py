"""
Archive Password Manager
Provides persistent local storage for Decompressor passwords,
smart candidate password discovery across post metadata, Link Vault, and heuristics,
and atomic persistence to config/decompressor_passwords.json.
"""

import os
import re
import json
import threading
from typing import List, Dict, Any, Optional, Set

from core.logger import logger


class ArchivePasswordManager:
    """Manages remembered passwords and resolves candidate passwords for archives."""

    def __init__(self, config_dir: Optional[str] = None):
        if not config_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_dir = os.path.join(base_dir, "config")
        self.config_dir = config_dir
        self.passwords_file = os.path.join(self.config_dir, "decompressor_passwords.json")
        self.archive_map_file = os.path.join(self.config_dir, "archive_password_map.json")
        self._lock = threading.Lock()

        self._passwords: List[str] = []
        self._creator_passwords: Dict[str, List[str]] = {}  # creator -> [passwords]
        self._archive_map: Dict[str, str] = {}  # normcase(abs_path) -> password
        self._load()

    def _rebuild_flat_passwords_unlocked(self):
        """Rebuilds flat deduplicated _passwords list from _creator_passwords."""
        all_pws = []
        seen = set()
        # Creator-specific first, then Global
        for c, pws in self._creator_passwords.items():
            if c != "Global":
                for p in pws:
                    if p not in seen:
                        seen.add(p)
                        all_pws.append(p)
        for p in self._creator_passwords.get("Global", []):
            if p not in seen:
                seen.add(p)
                all_pws.append(p)
        self._passwords = all_pws

    def _load(self):
        """Loads saved passwords and archive map from disk with backwards compatibility."""
        with self._lock:
            if os.path.exists(self.passwords_file):
                try:
                    with open(self.passwords_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            # Legacy format: flat list of strings
                            pws = [str(p).strip() for p in data if str(p).strip()]
                            self._creator_passwords = {"Global": pws} if pws else {}
                        elif isinstance(data, dict):
                            # V2 format: {"global": [...], "creators": {...}}
                            loaded: Dict[str, List[str]] = {}
                            creators_dict = data.get("creators", {})
                            if isinstance(creators_dict, dict):
                                for c, pws in creators_dict.items():
                                    if isinstance(pws, list):
                                        clean = [str(p).strip() for p in pws if str(p).strip()]
                                        if clean:
                                            loaded[c] = clean
                            global_list = data.get("global", [])
                            if isinstance(global_list, list):
                                clean_g = [str(p).strip() for p in global_list if str(p).strip()]
                                if clean_g:
                                    loaded["Global"] = clean_g
                            self._creator_passwords = loaded
                        else:
                            self._creator_passwords = {}
                except Exception as e:
                    logger.warning(f"Could not load decompressor_passwords.json: {e}", category="decompressor")
                    self._creator_passwords = {}
            else:
                self._creator_passwords = {}

            self._rebuild_flat_passwords_unlocked()

            if os.path.exists(self.archive_map_file):
                try:
                    with open(self.archive_map_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            self._archive_map = data
                except Exception as e:
                    logger.debug(f"Could not load archive_password_map.json: {e}", category="decompressor")
                    self._archive_map = {}
            else:
                self._archive_map = {}

    def _save_passwords(self):
        """Atomically saves passwords dictionary in V2 format."""
        os.makedirs(self.config_dir, exist_ok=True)
        tmp_file = f"{self.passwords_file}.tmp"
        payload = {
            "version": 2,
            "global": self._creator_passwords.get("Global", []),
            "creators": {k: v for k, v in self._creator_passwords.items() if k != "Global" and v}
        }
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            if os.path.exists(self.passwords_file):
                os.replace(tmp_file, self.passwords_file)
            else:
                os.rename(tmp_file, self.passwords_file)
        except Exception as e:
            logger.error(f"Failed to save decompressor_passwords.json: {e}", category="decompressor")
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass

    def _save_archive_map(self):
        """Atomically saves archive map."""
        os.makedirs(self.config_dir, exist_ok=True)
        tmp_file = f"{self.archive_map_file}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self._archive_map, f, indent=2, ensure_ascii=False)
            if os.path.exists(self.archive_map_file):
                os.replace(tmp_file, self.archive_map_file)
            else:
                os.rename(tmp_file, self.archive_map_file)
        except Exception as e:
            logger.debug(f"Failed to save archive_password_map.json: {e}", category="decompressor")
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass

    def get_passwords(self) -> List[str]:
        """Returns a flat copy of all saved passwords across all creators."""
        with self._lock:
            return list(self._passwords)

    def get_passwords_by_creator(self) -> Dict[str, List[str]]:
        """Returns a copy of passwords grouped by creator name."""
        with self._lock:
            return {k: list(v) for k, v in self._creator_passwords.items() if v}

    def add_password(self, password: str, creator: str = "Global") -> bool:
        """Adds a password under a specific creator (or 'Global') if non-empty and unique."""
        p = str(password or "").strip()
        c = str(creator or "Global").strip() or "Global"
        if not p:
            return False
        with self._lock:
            if c not in self._creator_passwords:
                self._creator_passwords[c] = []
            if p not in self._creator_passwords[c]:
                self._creator_passwords[c].append(p)
                self._rebuild_flat_passwords_unlocked()
                self._save_passwords()
                logger.info(f"Added password to Decompressor Password Bank [{c}]: {p}", category="decompressor")
                return True
        return False

    def add_passwords(self, passwords: List[str], creator: str = "Global") -> int:
        """Adds multiple passwords to a creator, deduplicating."""
        added = 0
        c = str(creator or "Global").strip() or "Global"
        with self._lock:
            if c not in self._creator_passwords:
                self._creator_passwords[c] = []
            for item in passwords:
                p = str(item or "").strip()
                if p and p not in self._creator_passwords[c]:
                    self._creator_passwords[c].append(p)
                    added += 1
            if added > 0:
                self._rebuild_flat_passwords_unlocked()
                self._save_passwords()
                logger.info(f"Added {added} password(s) to Decompressor Password Bank [{c}].", category="decompressor")
        return added

    def remove_password(self, password: str, creator: str = "") -> bool:
        """Removes a password from a specific creator (or all groups if creator is blank)."""
        p = str(password or "").strip()
        c = str(creator or "").strip()
        with self._lock:
            removed = False
            if c:
                if c in self._creator_passwords and p in self._creator_passwords[c]:
                    self._creator_passwords[c].remove(p)
                    if not self._creator_passwords[c] and c != "Global":
                        del self._creator_passwords[c]
                    removed = True
            else:
                for grp_name in list(self._creator_passwords.keys()):
                    if p in self._creator_passwords[grp_name]:
                        self._creator_passwords[grp_name].remove(p)
                        if not self._creator_passwords[grp_name] and grp_name != "Global":
                            del self._creator_passwords[grp_name]
                        removed = True

            # Also purge from archive mapping
            to_del = [k for k, v in self._archive_map.items() if v == p]
            for k in to_del:
                del self._archive_map[k]
                removed = True

            if removed:
                self._rebuild_flat_passwords_unlocked()
                self._save_passwords()
                self._save_archive_map()
                logger.info(f"Removed password from Decompressor Password Bank: {p}", category="decompressor")
                return True
        return False

    def clear_passwords(self) -> bool:
        """Wipes all saved passwords and archive mappings."""
        with self._lock:
            self._passwords.clear()
            self._creator_passwords.clear()
            self._archive_map.clear()
            self._save_passwords()
            self._save_archive_map()
            logger.info("Cleared Decompressor Password Bank.", category="decompressor")
            return True

    def record_archive_password(self, archive_path: str, password: str, creator: str = ""):
        """Associates a specific archive file path with a confirmed password and creator."""
        if not archive_path or not password:
            return
        norm = os.path.normcase(os.path.abspath(archive_path))
        p = str(password).strip()
        with self._lock:
            self._archive_map[norm] = p
            self._save_archive_map()
        # Ensure it's in the bank under the creator (or Global if unspecified)
        self.add_password(p, creator=creator or "Global")

    def get_archive_password(self, archive_path: str) -> Optional[str]:
        """Retrieves a specifically paired password for an archive path, if recorded."""
        if not archive_path:
            return None
        norm = os.path.normcase(os.path.abspath(archive_path))
        with self._lock:
            return self._archive_map.get(norm)

    def sync_from_link_vault(self) -> int:
        """Imports all detected passwords from Link Vault, mapped to their respective creators."""
        try:
            from core.link_vault_manager import link_vault_manager
            added = 0
            with self._lock:
                # 1. Gather creator-specific passwords from posts
                for post in link_vault_manager.data.get("posts", {}).values():
                    c_name = str(post.get("creator_name") or "").strip() or "Global"
                    for p in post.get("passwords", []):
                        val = str(p or "").strip()
                        if not val:
                            continue
                        if c_name not in self._creator_passwords:
                            self._creator_passwords[c_name] = []
                        if val not in self._creator_passwords[c_name]:
                            self._creator_passwords[c_name].append(val)
                            added += 1

                # 2. Also import any global passwords
                for p in link_vault_manager.get_all_passwords():
                    val = str(p or "").strip()
                    if val and val not in self._passwords:
                        if "Global" not in self._creator_passwords:
                            self._creator_passwords["Global"] = []
                        if val not in self._creator_passwords["Global"]:
                            self._creator_passwords["Global"].append(val)
                            added += 1

                if added > 0:
                    self._rebuild_flat_passwords_unlocked()
                    self._save_passwords()
                    logger.info(f"Synced {added} password(s) from Link Vault into creator Password Bank.", category="decompressor")
            return added
        except Exception as e:
            logger.warning(f"Failed to sync passwords from Link Vault: {e}", category="decompressor")
            return 0

    def parse_folder_info_passwords(self, folder_path: str) -> List[str]:
        """
        Inspects directory for info.txt, post_info.txt, or *.txt and extracts any
        passwords listed under '--- Detected Password(s) ---' or via smart extraction.
        """
        found_passwords: List[str] = []
        if not folder_path or not os.path.exists(folder_path):
            return found_passwords

        candidate_files = ["info.txt", "post_info.txt"]
        try:
            all_txt = [f for f in os.listdir(folder_path) if f.lower().endswith(".txt")]
            for cf in candidate_files:
                if cf in all_txt:
                    all_txt.remove(cf)
                    all_txt.insert(0, cf)
        except OSError:
            all_txt = candidate_files

        for txt_name in all_txt[:3]:
            txt_path = os.path.join(folder_path, txt_name)
            if not os.path.exists(txt_path):
                continue
            try:
                with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(32768)

                if "--- Detected Password(s) ---" in content:
                    lines = content.split("--- Detected Password(s) ---", 1)[1].split("\n---", 1)[0].splitlines()
                    for line in lines:
                        pw = line.strip()
                        if pw and pw not in found_passwords:
                            found_passwords.append(pw)

                from services.link_extractor import LinkExtractor
                extracted = LinkExtractor.extract_passwords(content)
                for pw in extracted:
                    if pw and pw not in found_passwords:
                        found_passwords.append(pw)
            except Exception as e:
                logger.debug(f"Could not read passwords from {txt_path}: {e}", category="decompressor")

        return found_passwords

    def find_candidate_passwords(self, archive_path: str, creator: str = "") -> List[str]:
        """
        Aggregates candidate passwords for an archive in priority order:
        1. Explicitly mapped password for this exact archive file path.
        2. Passwords found in the same folder's info.txt / post_info.txt.
        3. Creator-specific passwords from Link Vault.
        4. Saved Decompressor Password Bank.
        5. Global passwords in Link Vault.
        6. Context heuristics (creator name, folder name tokens).
        """
        candidates: List[str] = []
        seen: Set[str] = set()

        def _add(cand: Optional[str]):
            if not cand:
                return
            c = str(cand).strip()
            if c and c not in seen:
                seen.add(c)
                candidates.append(c)

        # 1. Exact archive mapping
        direct_pw = self.get_archive_password(archive_path)
        if direct_pw:
            _add(direct_pw)

        # 2. Local folder info.txt / post_info.txt
        if archive_path:
            archive_dir = os.path.dirname(os.path.abspath(archive_path))
            for p in self.parse_folder_info_passwords(archive_dir):
                _add(p)
            parent_dir = os.path.dirname(archive_dir)
            if parent_dir and parent_dir != archive_dir:
                for p in self.parse_folder_info_passwords(parent_dir):
                    _add(p)

        # 3. Creator-specific passwords from Link Vault
        if creator:
            try:
                from core.link_vault_manager import link_vault_manager
                creator_clean = creator.strip().lower()
                for c_key, c_data in link_vault_manager.data.get("creators", {}).items():
                    if creator_clean in str(c_key).lower() or creator_clean in str(c_data.get("name", "")).lower():
                        for post in link_vault_manager.data.get("posts", {}).values():
                            if post.get("creator_id") == c_key or str(post.get("creator_name", "")).lower() == creator_clean:
                                for p in post.get("passwords", []):
                                    _add(p)
            except Exception as e:
                logger.debug(f"Could not fetch creator passwords from Link Vault: {e}", category="decompressor")

        # 4. Creator-specific passwords from Password Bank
        if creator:
            with self._lock:
                c_clean = creator.strip().lower()
                for c_name, pws in self._creator_passwords.items():
                    if c_name.strip().lower() == c_clean:
                        for p in pws:
                            _add(p)

        # 5. Saved Global / All Decompressor Password Bank
        for p in self.get_passwords():
            _add(p)

        # 5. Global passwords in Link Vault
        try:
            from core.link_vault_manager import link_vault_manager
            for p in link_vault_manager.get_all_passwords():
                _add(p)
        except Exception:
            pass

        # 6. Context heuristics (creator name)
        if creator:
            c_clean = creator.strip()
            _add(c_clean)
            _add(c_clean.lower())

        return candidates


# Singleton instance
archive_password_manager = ArchivePasswordManager()
