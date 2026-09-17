"""
Multi-Drive Storage Pool Manager
Monitors disk capacity across primary and secondary storage drives,
preventing disk-full crashes (Errno 28) by automatically spanning large
download queues across available drives with a configurable safety margin.
"""

import os
import sys
import json
import shutil
import threading
from typing import Dict, Any, List, Optional, Tuple

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger


class StoragePoolManager:
    """
    Manages drive pools, free space monitoring, and seamless auto-spanning
    of downloads across multiple physical drives or network mounts.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if not config_dir:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)

        self.pool_file = os.path.join(self.config_dir, "storage_pools.json")
        self.bak_file = os.path.join(self.config_dir, "storage_pools.json.bak")
        self._lock = threading.RLock()

        self.enabled: bool = False
        self.safety_margin_gb: float = 10.0
        self.primary_dir: str = ""
        self.overflow_dirs: List[str] = []

        self._load()

    def _load(self):
        """Loads pool configuration with .bak fallback."""
        with self._lock:
            # Primary config
            if os.path.exists(self.pool_file):
                try:
                    with open(self.pool_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._apply_dict(data)
                        return
                except Exception as e:
                    logger.warning(f"Could not load storage_pools.json: {e}; checking backup...", category="storage")

            # Backup config
            if os.path.exists(self.bak_file):
                try:
                    with open(self.bak_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._apply_dict(data)
                        logger.success("Recovered storage pool settings from .bak", category="storage")
                        return
                except Exception as e:
                    logger.error(f"Backup storage_pools.json.bak also failed: {e}", category="storage")

    def _apply_dict(self, data: Dict[str, Any]):
        self.enabled = bool(data.get("enabled", False))
        self.safety_margin_gb = float(data.get("safety_margin_gb", 10.0))
        self.primary_dir = str(data.get("primary_dir", ""))
        self.overflow_dirs = [str(d) for d in data.get("overflow_dirs", []) if str(d).strip()]

    def save(self):
        """Persists storage pool settings atomically."""
        with self._lock:
            self._save_unlocked()

    def _save_unlocked(self):
        payload = {
            "enabled": self.enabled,
            "safety_margin_gb": self.safety_margin_gb,
            "primary_dir": self.primary_dir,
            "overflow_dirs": self.overflow_dirs
        }
        tmp_path = f"{self.pool_file}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass

            if os.path.exists(self.pool_file):
                try:
                    shutil.copy2(self.pool_file, self.bak_file)
                except Exception as e:
                    logger.debug(f"Could not rotate storage pool .bak: {e}", category="storage")

            os.replace(tmp_path, self.pool_file)
            if not os.path.exists(self.bak_file):
                try:
                    shutil.copy2(self.pool_file, self.bak_file)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to persist storage pools: {e}", category="storage")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def add_overflow_dir(self, dir_path: str) -> bool:
        """Adds a new secondary drive / directory to the pool."""
        norm = os.path.normpath(dir_path.strip())
        if not norm:
            return False
        with self._lock:
            if norm not in self.overflow_dirs:
                self.overflow_dirs.append(norm)
                self.save()
                logger.info(f"Added overflow storage directory: {norm}", category="storage")
                return True
        return False

    def remove_overflow_dir(self, dir_path: str) -> bool:
        """Removes a secondary drive / directory from the pool."""
        norm = os.path.normpath(dir_path.strip())
        with self._lock:
            if norm in self.overflow_dirs:
                self.overflow_dirs.remove(norm)
                self.save()
                logger.info(f"Removed overflow storage directory: {norm}", category="storage")
                return True
        return False

    def set_primary_dir(self, dir_path: str):
        """Sets the primary download directory."""
        norm = os.path.normpath(dir_path.strip())
        with self._lock:
            if self.primary_dir != norm:
                self.primary_dir = norm
                self.save()

    def set_safety_margin(self, margin_gb: float):
        """Sets minimum free space safety threshold in gigabytes."""
        with self._lock:
            self.safety_margin_gb = max(1.0, float(margin_gb))
            self.save()

    def set_enabled(self, enabled: bool):
        """Toggles multi-drive auto-spanning."""
        with self._lock:
            self.enabled = bool(enabled)
            self.save()

    @staticmethod
    def get_drive_stats(path: str) -> Dict[str, Any]:
        """Returns disk capacity statistics for a given path."""
        if not path or not os.path.exists(path):
            drive = os.path.splitdrive(path)[0] or path
            if not os.path.exists(drive):
                return {
                    "path": path,
                    "exists": False,
                    "total_gb": 0.0,
                    "used_gb": 0.0,
                    "free_gb": 0.0,
                    "percent_used": 0.0
                }
            path = drive

        try:
            usage = shutil.disk_usage(path)
            total = getattr(usage, "total", usage[0])
            used = getattr(usage, "used", usage[1])
            free = getattr(usage, "free", usage[2])

            total_gb = round(total / (1024 ** 3), 2)
            used_gb = round(used / (1024 ** 3), 2)
            free_gb = round(free / (1024 ** 3), 2)
            pct = round((used / total) * 100, 1) if total > 0 else 0.0
            return {
                "path": path,
                "exists": True,
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "percent_used": pct
            }
        except Exception as e:
            logger.debug(f"Could not get disk usage for {path}: {e}", category="storage")
            return {
                "path": path,
                "exists": False,
                "total_gb": 0.0,
                "used_gb": 0.0,
                "free_gb": 0.0,
                "percent_used": 0.0
            }

    def get_pool_status(self) -> Dict[str, Any]:
        """Returns complete pool status for UI rendering."""
        with self._lock:
            primary_stats = self.get_drive_stats(self.primary_dir) if self.primary_dir else None
            overflow_stats = [self.get_drive_stats(d) for d in self.overflow_dirs]

            drives = []
            if primary_stats:
                p_copy = dict(primary_stats)
                p_copy["is_primary"] = True
                p_copy["is_low"] = p_copy.get("free_gb", 0) < self.safety_margin_gb
                p_copy["used_percent"] = p_copy.get("percent_used", 0.0)
                drives.append(p_copy)
            for o in overflow_stats:
                o_copy = dict(o)
                o_copy["is_primary"] = False
                o_copy["is_low"] = o_copy.get("free_gb", 0) < self.safety_margin_gb
                o_copy["used_percent"] = o_copy.get("percent_used", 0.0)
                drives.append(o_copy)

            return {
                "enabled": self.enabled,
                "safety_margin_gb": self.safety_margin_gb,
                "primary_dir": self.primary_dir,
                "overflow_dirs": list(self.overflow_dirs),
                "primary": primary_stats,
                "overflow": overflow_stats,
                "drives": drives
            }

    def get_destination_target(
        self,
        subfolder: str,
        filename: str,
        estimated_bytes: int = 0
    ) -> Tuple[str, bool]:
        """
        Determines the optimal destination file path.
        If the primary drive is below the safety margin (or estimated_bytes exceeds it),
        seamlessly spans to the first healthy overflow drive with sufficient space.

        Returns: (full_file_path, was_overflowed)
        """
        subfolder = subfolder.strip().lstrip("/\\")
        filename = filename.strip()

        with self._lock:
            if not self.enabled or not self.primary_dir or not self.overflow_dirs:
                # Disabled or no overflow configured -> use primary
                base = self.primary_dir or os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads")
                return os.path.join(base, subfolder, filename), False

            margin_bytes = int(self.safety_margin_gb * (1024 ** 3))
            required_bytes = estimated_bytes + margin_bytes

            # 1. Test primary drive
            primary_free = 0
            try:
                p_drive = self.primary_dir if os.path.exists(self.primary_dir) else os.path.splitdrive(self.primary_dir)[0] or self.primary_dir
                if os.path.exists(p_drive):
                    usage = shutil.disk_usage(p_drive)
                    primary_free = getattr(usage, "free", usage[2] if len(usage) > 2 else 0)
            except Exception:
                primary_free = 0

            if primary_free >= required_bytes:
                # Primary drive is safe!
                return os.path.join(self.primary_dir, subfolder, filename), False

            # 2. Primary drive below safety margin -> select overflow drive with the MOST free space
            primary_free_gb = round(primary_free / (1024 ** 3), 2)
            logger.warning(
                f"Storage Pool: Primary drive low on space ({primary_free_gb} GB free < {self.safety_margin_gb} GB margin). "
                f"Evaluating overflow drives for '{filename}'...",
                category="storage"
            )

            # Evaluate and rank overflow drives by available free space descending
            candidates = []
            for o_dir in self.overflow_dirs:
                try:
                    o_drive = o_dir if os.path.exists(o_dir) else os.path.splitdrive(o_dir)[0] or o_dir
                    if os.path.exists(o_drive):
                        o_usage = shutil.disk_usage(o_drive)
                        o_free = getattr(o_usage, "free", o_usage[2] if len(o_usage) > 2 else 0)
                        if o_free >= required_bytes:
                            candidates.append((o_free, o_dir))
                except Exception as e:
                    logger.debug(f"Error checking overflow drive {o_dir}: {e}", category="storage")

            if candidates:
                # Pick the overflow drive with the greatest amount of free space
                candidates.sort(key=lambda c: c[0], reverse=True)
                best_free, best_dir = candidates[0]
                target_dir = os.path.join(best_dir, subfolder)
                os.makedirs(target_dir, exist_ok=True)
                overflow_free_gb = round(best_free / (1024 ** 3), 2)
                logger.info(
                    f"Storage Pool: Overflowing to most-free drive {best_dir} ({overflow_free_gb} GB free).",
                    category="storage"
                )
                return os.path.join(target_dir, filename), True

            # If all overflow drives also fail, fallback to primary drive
            logger.error(
                "Storage Pool: ALL drives (primary & overflow) are below safety margin! Continuing on primary.",
                category="storage"
            )
            return os.path.join(self.primary_dir, subfolder, filename), False

    def get_most_free_drive(self, candidate_dirs: Optional[List[str]] = None) -> Tuple[str, int]:
        """
        Returns (best_drive_path, free_bytes) from candidate drives (or primary + all overflow dirs),
        ranking strictly by maximum available free bytes on disk.
        """
        with self._lock:
            if candidate_dirs is not None:
                dirs = [d for d in candidate_dirs if d and str(d).strip()]
            elif self.enabled and self.overflow_dirs:
                dirs = ([self.primary_dir] if self.primary_dir else []) + list(self.overflow_dirs)
            else:
                dirs = [self.primary_dir] if self.primary_dir else []

            if not dirs:
                default_base = os.path.join(os.path.expanduser("~"), "Downloads", "KemonoDownloads")
                return default_base, 0

            ranked = []
            margin_bytes = int(self.safety_margin_gb * (1024 ** 3))

            for d in dirs:
                norm = os.path.normpath(d)
                try:
                    drive_root = norm if os.path.exists(norm) else os.path.splitdrive(norm)[0] or norm
                    if os.path.exists(drive_root):
                        usage = shutil.disk_usage(drive_root)
                        free_b = getattr(usage, "free", usage[2] if len(usage) > 2 else 0)
                        ranked.append((free_b, norm))
                except Exception as e:
                    logger.debug(f"get_most_free_drive error for {norm}: {e}", category="storage")

            if not ranked:
                return dirs[0], 0

            ranked.sort(key=lambda r: r[0], reverse=True)

            # Prefer drives above safety margin if available
            safe_drives = [r for r in ranked if r[0] >= margin_bytes]
            if safe_drives:
                return safe_drives[0][1], safe_drives[0][0]

            # Otherwise return the one with the most free space overall
            return ranked[0][1], ranked[0][0]

    def find_artist_locations(
        self,
        creator_name: str,
        service: str = "",
        additional_paths: Optional[List[str]] = None
    ) -> List[str]:
        """
        Discovers all existing filesystem directories for an artist across:
        1. Configured primary download directory.
        2. All configured overflow storage pool drives.
        3. Any explicitly registered/additional paths.
        Returns a sorted, deduplicated list of verified existing directory paths.
        """
        from core.filter_engine import FilterEngine

        clean_c = FilterEngine.clean_filesystem_text(creator_name or "creator", max_len=80, fallback="creator")
        svc = (service or "").lower().strip()
        expected_folder = f"{clean_c} [{svc}]" if svc else clean_c

        with self._lock:
            search_roots = []
            if self.primary_dir and os.path.exists(self.primary_dir):
                search_roots.append(os.path.normpath(self.primary_dir))
            for o in self.overflow_dirs:
                if o and os.path.exists(o):
                    search_roots.append(os.path.normpath(o))

        discovered = []
        seen = set()

        def _check_and_add(p: str):
            if not p:
                return
            norm = os.path.normpath(p)
            norm_key = norm.lower()
            if norm_key not in seen and os.path.isdir(norm):
                seen.add(norm_key)
                discovered.append(norm)

        # 1. Search across storage roots for creator subfolders
        for root_dir in search_roots:
            # Candidate 1: Root / Creator [service]
            _check_and_add(os.path.join(root_dir, expected_folder))
            # Candidate 2: Root / Creator
            _check_and_add(os.path.join(root_dir, clean_c))
            # Candidate 3: Root / service / Creator [service]
            if svc:
                _check_and_add(os.path.join(root_dir, svc, expected_folder))
                _check_and_add(os.path.join(root_dir, svc, clean_c))
                _check_and_add(os.path.join(root_dir, svc.capitalize(), expected_folder))
                _check_and_add(os.path.join(root_dir, svc.capitalize(), clean_c))

        # 2. Check additional explicit paths (e.g. from WatchlistEntry.download_dirs)
        if additional_paths:
            for p in additional_paths:
                if not p:
                    continue
                norm = os.path.normpath(p)
                if os.path.isdir(norm):
                    _check_and_add(norm)
                else:
                    # Maybe it's a parent folder where the artist folder lives
                    _check_and_add(os.path.join(norm, expected_folder))
                    _check_and_add(os.path.join(norm, clean_c))

        return discovered


# Global Singleton
storage_pool_manager = StoragePoolManager()

