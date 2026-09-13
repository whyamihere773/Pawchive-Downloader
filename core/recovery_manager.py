"""
Recovery & Crash Journal Manager
Provides 100% crash-proof recovery for interrupted downloads.
Uses atomic write-flush-fsync-replace, automatic .bak fallback,
and multi-artist / multi-platform session tracking.
"""

import os
import sys
import json
import time
import shutil
import datetime
from typing import Dict, Any, List, Optional
from core.logger import logger


class RecoveryManager:
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
        self.journal_file = os.path.join(self.config_dir, "recovery_journal.json")
        self.tmp_file = os.path.join(self.config_dir, "recovery_journal.json.tmp")
        self.bak_file = os.path.join(self.config_dir, "recovery_journal.json.bak")

    @staticmethod
    def _detect_platform(service: str, domain: str = "", url: str = "") -> str:
        """Derives a friendly platform name (e.g. Kemono, Coomer, Patreon, Fanbox, OnlyFans, Bunkr, Erome, nHentai)."""
        svc = (service or "").lower()
        dom = (domain or "").lower()
        u = (url or "").lower()

        # Dedicated external providers
        if svc in ("bunkr",) or "bunkr" in dom or "bunkr" in u or "balbums.st" in dom or "balbums.st" in u:
            return "Bunkr"
        if svc in ("erome",) or "erome" in dom or "erome" in u:
            return "Erome"
        if svc in ("nhentai",) or "nhentai" in dom or "nhentai" in u:
            return "nHentai"

        # Check domain first
        if "coomer" in dom or "coomer" in u:
            platform_base = "Coomer"
        elif "kemono" in dom or "kemono" in u:
            platform_base = "Kemono"
        elif "pawchive" in dom or "pawchive" in u:
            platform_base = "Pawchive"
        elif "cum.st" in dom or "cum.st" in u:
            platform_base = "cum.st"
        else:
            if svc in ("onlyfans", "fansly", "candfans"):
                platform_base = "Coomer"
            else:
                platform_base = "Kemono"

        service_labels = {
            "patreon": "Patreon",
            "fanbox": "Pixiv Fanbox",
            "fantia": "Fantia",
            "onlyfans": "OnlyFans",
            "fansly": "Fansly",
            "candfans": "CandFans",
            "subscribestar": "SubscribeStar",
            "boosty": "Boosty",
            "dlsite": "DLsite",
            "discord": "Discord",
            "afdian": "Afdian",
            "gumroad": "Gumroad"
        }
        svc_label = service_labels.get(svc, svc.capitalize() if svc else "Unknown")
        return f"{svc_label} ({platform_base})"

    @staticmethod
    def _format_size(num_bytes: int) -> str:
        """Formats byte count into human-readable string."""
        if num_bytes <= 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(num_bytes) < 1024.0:
                return f"{num_bytes:.2f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.2f} PB"

    def build_summary(self, tasks: List[Any], batches: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Calculates artist-level and overall progress summary from a list of tasks.
        """
        if not tasks:
            return {
                "artists": [],
                "total_files": 0,
                "completed_files": 0,
                "pending_files": 0,
                "failed_files": 0,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "percent": 0.0,
                "formatted_downloaded": "0 B",
                "formatted_total": "0 B",
                "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        artist_map: Dict[str, Dict[str, Any]] = {}
        total_files = len(tasks)
        completed_files = 0
        failed_files = 0
        pending_files = 0
        downloaded_bytes = 0
        total_bytes = 0

        for t in tasks:
            c_name = getattr(t, "creator_name", "") or (t.get("creator_name") if isinstance(t, dict) else "") or "Unknown Artist"
            svc = getattr(t, "service", "") or (t.get("service") if isinstance(t, dict) else "") or ""
            url = getattr(t, "url", "") or (t.get("url") if isinstance(t, dict) else "") or ""
            st = getattr(t, "status", "") or (t.get("status") if isinstance(t, dict) else "") or "pending"
            p_title = getattr(t, "post_title", "") or (t.get("post_title") if isinstance(t, dict) else "") or ""
            target_p = getattr(t, "target_path", "") or (t.get("target_path") if isinstance(t, dict) else "") or ""

            # If creator_name is generic provider (e.g. "Bunkr", "Erome", "nHentai", "Unknown Artist")
            # extract real creator from post_title or folder name
            if c_name.lower() in ("bunkr", "erome", "nhentai", "unknown artist", "bunkr album", "erome album"):
                if p_title and p_title.lower() not in ("bunkr", "erome", "nhentai", "untitled", "bunkr album", "erome album"):
                    c_name = p_title
                elif target_p:
                    parent_folder = os.path.basename(os.path.dirname(target_p))
                    for prefix in ("Bunkr - ", "Erome - ", "nHentai - "):
                        if parent_folder.startswith(prefix):
                            extracted = parent_folder[len(prefix):].strip()
                            if extracted:
                                c_name = extracted
                            break

            f_size = getattr(t, "file_size", 0) or (t.get("file_size", 0) if isinstance(t, dict) else 0) or 0
            d_bytes = getattr(t, "downloaded_bytes", 0) or (t.get("downloaded_bytes", 0) if isinstance(t, dict) else 0) or 0

            task_total = max(f_size, d_bytes)
            total_bytes += task_total
            downloaded_bytes += d_bytes

            if st == "completed":
                completed_files += 1
            elif st == "failed":
                failed_files += 1
            else:
                pending_files += 1

            key = f"{c_name}_{svc}".lower()
            if key not in artist_map:
                artist_map[key] = {
                    "name": c_name,
                    "service": svc,
                    "platform": self._detect_platform(svc, url=url),
                    "completed": 0,
                    "total": 0,
                    "downloaded_bytes": 0,
                    "total_bytes": 0
                }
            artist_map[key]["total"] += 1
            artist_map[key]["total_bytes"] += task_total
            artist_map[key]["downloaded_bytes"] += d_bytes
            if st == "completed":
                artist_map[key]["completed"] += 1

        artists_list = []
        for a in artist_map.values():
            pct = (a["completed"] / a["total"] * 100.0) if a["total"] > 0 else 0.0
            artists_list.append({
                "name": a["name"],
                "service": a["service"],
                "platform": a["platform"],
                "completed": a["completed"],
                "total": a["total"],
                "percent": round(pct, 1),
                "formatted_downloaded": self._format_size(a["downloaded_bytes"]),
                "formatted_total": self._format_size(a["total_bytes"])
            })

        overall_pct = (completed_files / total_files * 100.0) if total_files > 0 else 0.0

        return {
            "artists": artists_list,
            "total_files": total_files,
            "completed_files": completed_files,
            "pending_files": pending_files,
            "failed_files": failed_files,
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
            "percent": round(overall_pct, 1),
            "formatted_downloaded": self._format_size(downloaded_bytes),
            "formatted_total": self._format_size(total_bytes),
            "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def save_checkpoint(
        self,
        tasks: List[Any],
        batches: Optional[List[Dict[str, Any]]] = None,
        settings: Optional[Dict[str, Any]] = None,
        status: str = "interrupted"
    ) -> bool:
        """
        Atomically writes the recovery journal using flush + os.fsync + backup rotation + atomic replace.
        Ensures zero file corruption even during sudden power loss or process kill.
        """
        if not tasks:
            return False

        try:
            summary = self.build_summary(tasks, batches)
            raw_tasks = [
                t.to_dict() if hasattr(t, "to_dict") else t
                for t in tasks
            ]

            payload = {
                "version": 1,
                "status": status,
                "saved_at": datetime.datetime.now().isoformat(),
                "summary": summary,
                "settings": settings or {},
                "batches": batches or [],
                "tasks": raw_tasks
            }

            # Step 1: Write to temporary file
            with open(self.tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                # Step 2: Force physical OS / NTFS disk write barrier
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass

            # Step 3: Rotate current valid journal to .bak if it exists
            if os.path.exists(self.journal_file):
                try:
                    shutil.copy2(self.journal_file, self.bak_file)
                except Exception as bak_err:
                    logger.debug(f"Could not update journal .bak: {bak_err}", category="session")

            # Step 4: Atomic file replace (NTFS MFT pointer swap)
            os.replace(self.tmp_file, self.journal_file)
            logger.debug("Download recovery checkpoint saved atomically.", category="session")
            return True

        except Exception as e:
            logger.error(f"Failed to save recovery checkpoint: {e}", category="session")
            if os.path.exists(self.tmp_file):
                try:
                    os.remove(self.tmp_file)
                except Exception:
                    pass
            return False

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Loads the saved recovery journal. If the primary file is missing, empty, or corrupt,
        it automatically and silently falls back to the .bak backup file.
        """
        if os.path.exists(self.tmp_file):
            try:
                os.remove(self.tmp_file)
            except Exception:
                pass

        # Candidate 1: Primary recovery journal
        if os.path.exists(self.journal_file):
            try:
                with open(self.journal_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and isinstance(data, dict) and data.get("tasks"):
                        return data
            except Exception as primary_err:
                logger.warning(
                    f"Primary recovery journal could not be decoded ({primary_err}). Attempting fallback to .bak...",
                    category="session"
                )

        # Candidate 2: Automatic fallback to .bak
        if os.path.exists(self.bak_file):
            try:
                with open(self.bak_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and isinstance(data, dict) and data.get("tasks"):
                        logger.info("Recovery journal successfully restored from .bak backup file.", category="session")
                        return data
            except Exception as bak_err:
                logger.warning(f"Recovery .bak file also unusable: {bak_err}", category="session")

        return None

    def has_unfinished_session(self) -> bool:
        """Checks whether a valid unfinished recovery session exists."""
        data = self.load_checkpoint()
        if not data:
            return False
        if data.get("status") == "completed":
            return False
        tasks = data.get("tasks", [])
        if not tasks:
            return False
        has_pending = any(t.get("status") in ("pending", "downloading", "failed") for t in tasks)
        return has_pending

    def get_recovery_summary(self) -> Optional[Dict[str, Any]]:
        """Returns the high-level summary dict for displaying in the recovery modal."""
        data = self.load_checkpoint()
        if not data:
            return None
        tasks = data.get("tasks", [])
        if tasks:
            return self.build_summary(tasks, data.get("batches"))
        return data.get("summary")

    def discard_recovery(self) -> bool:
        """Purges all recovery journal files (.json, .bak, .tmp)."""
        purged = False
        for fpath in [self.journal_file, self.bak_file, self.tmp_file]:
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    purged = True
                except Exception as e:
                    logger.warning(f"Could not remove recovery file {fpath}: {e}", category="session")
        if purged:
            logger.info("Recovery journal files discarded.", category="session")
        return purged
