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

            # 2. Primary drive below safety margin -> select overflow drive
            primary_free_gb = round(primary_free / (1024 ** 3), 2)
            logger.warning(
                f"Storage Pool: Primary drive low on space ({primary_free_gb} GB free < {self.safety_margin_gb} GB margin). "
                f"Evaluating overflow drives for '{filename}'...",
                category="storage"
            )

            for o_dir in self.overflow_dirs:
                try:
                    o_drive = o_dir if os.path.exists(o_dir) else os.path.splitdrive(o_dir)[0] or o_dir
                    if os.path.exists(o_drive):
                        o_usage = shutil.disk_usage(o_drive)
                        o_free = getattr(o_usage, "free", o_usage[2] if len(o_usage) > 2 else 0)
                        if o_free >= required_bytes:
                            target_dir = os.path.join(o_dir, subfolder)
                            os.makedirs(target_dir, exist_ok=True)
                            overflow_free_gb = round(o_free / (1024 ** 3), 2)
                            logger.info(
                                f"Storage Pool: Overflowing to {o_dir} ({overflow_free_gb} GB free).",
                                category="storage"
                            )
                            return os.path.join(target_dir, filename), True
                except Exception as e:
                    logger.debug(f"Error checking overflow drive {o_dir}: {e}", category="storage")

            # If all overflow drives also fail, fallback to primary drive
            logger.error(
                "Storage Pool: ALL drives (primary & overflow) are below safety margin! Continuing on primary.",
                category="storage"
            )
            return os.path.join(self.primary_dir, subfolder, filename), False


# Global Singleton
storage_pool_manager = StoragePoolManager()
