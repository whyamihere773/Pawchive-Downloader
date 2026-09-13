"""
Task Scheduler & Automation Hub
Background execution engine for automated Watchlist sync, interval & time triggers,
Night Owl off-peak windows, user-locked concurrency settings, and Windows sleep prevention.
"""

import os
import sys
import json
import time
import uuid
import shutil
import datetime
import threading
import ctypes
from typing import Dict, Any, List, Optional, Callable

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger

# Windows kernel power management constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040


class TaskScheduler:
    """
    Manages automated periodic triggers, Night Owl windows, and unattended download queues.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if not config_dir:
            config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)

        self.schedules_file = os.path.join(self.config_dir, "schedules.json")
        self.bak_file = os.path.join(self.config_dir, "schedules.json.bak")
        self._lock = threading.RLock()

        # Global automation settings
        self.enabled: bool = False
        self.lock_threads_delay: bool = True  # User-locked threads/delay mode (User Request 4.2)
        self.night_owl_enabled: bool = False
        self.night_owl_start: str = "01:00"
        self.night_owl_end: str = "07:00"
        self.prevent_sleep: bool = True
        self.sweep_retry: bool = True

        self.schedules: List[Dict[str, Any]] = []

        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sleep_lock_active: bool = False

        # Callbacks
        self.on_trigger_watchlist_sync: Optional[Callable[[], None]] = None
        self.on_trigger_creator_sync: Optional[Callable[[str], None]] = None

        self._load()

    def _load(self):
        """Loads schedules from disk with .bak fallback."""
        with self._lock:
            if os.path.exists(self.schedules_file):
                try:
                    with open(self.schedules_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._apply_dict(data)
                        return
                except Exception as e:
                    logger.warning(f"Could not load schedules.json: {e}; checking backup...", category="scheduler")

            if os.path.exists(self.bak_file):
                try:
                    with open(self.bak_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._apply_dict(data)
                        logger.success("Recovered schedules from .bak backup.", category="scheduler")
                        return
                except Exception as e:
                    logger.error(f"Backup schedules.json.bak also failed: {e}", category="scheduler")

    def _apply_dict(self, data: Dict[str, Any]):
        self.enabled = bool(data.get("enabled", False))
        self.lock_threads_delay = bool(data.get("lock_threads_delay", True))
        self.night_owl_enabled = bool(data.get("night_owl_enabled", False))
        self.night_owl_start = str(data.get("night_owl_start", "01:00"))
        self.night_owl_end = str(data.get("night_owl_end", "07:00"))
        self.prevent_sleep = bool(data.get("prevent_sleep", True))
        self.sweep_retry = bool(data.get("sweep_retry", True))
        self.schedules = list(data.get("schedules", []))

    def save(self):
        """Persists schedule configuration atomically."""
        with self._lock:
            self._save_unlocked()

    def _save_unlocked(self):
        payload = {
            "enabled": self.enabled,
            "lock_threads_delay": self.lock_threads_delay,
            "night_owl_enabled": self.night_owl_enabled,
            "night_owl_start": self.night_owl_start,
            "night_owl_end": self.night_owl_end,
            "prevent_sleep": self.prevent_sleep,
            "sweep_retry": self.sweep_retry,
            "schedules": self.schedules
        }
        tmp_path = f"{self.schedules_file}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass

            if os.path.exists(self.schedules_file):
                try:
                    shutil.copy2(self.schedules_file, self.bak_file)
                except Exception as e:
                    logger.debug(f"Could not rotate schedules .bak: {e}", category="scheduler")

            os.replace(tmp_path, self.schedules_file)
            if not os.path.exists(self.bak_file):
                try:
                    shutil.copy2(self.schedules_file, self.bak_file)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to persist schedules: {e}", category="scheduler")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def add_schedule(
        self,
        name: str,
        target_type: str = "watchlist",
        target_url: str = "",
        trigger_type: str = "interval",
        interval_hours: int = 6,
        time_of_day: str = "03:00"
    ) -> str:
        """Adds a new automated schedule task."""
        sched_id = str(uuid.uuid4())
        now = datetime.datetime.now()

        next_run = self._compute_next_run(now, trigger_type, interval_hours, time_of_day)

        entry = {
            "id": sched_id,
            "name": name.strip() or "Automated Download",
            "target_type": target_type,  # "watchlist" or "creator"
            "target_url": target_url.strip(),
            "trigger_type": trigger_type,  # "interval" or "time_of_day"
            "interval_hours": max(1, int(interval_hours)),
            "time_of_day": time_of_day,
            "enabled": True,
            "last_run": None,
            "next_run": next_run.isoformat(),
            "status": "idle"
        }

        with self._lock:
            self.schedules.append(entry)
            self._save_unlocked()
            logger.info(f"Created automated schedule '{entry['name']}' (Next run: {next_run.strftime('%Y-%m-%d %H:%M')}).", category="scheduler")

        return sched_id

    def update_schedule(
        self,
        sched_id: str,
        name: str,
        target_type: str = "watchlist",
        target_url: str = "",
        trigger_type: str = "interval",
        interval_hours: int = 6,
        time_of_day: str = "03:00"
    ) -> bool:
        """Updates an existing schedule task and recalculates next run."""
        with self._lock:
            for s in self.schedules:
                if s.get("id") == sched_id:
                    s["name"] = name.strip() or ("Watchlist Delta Sync" if target_type == "watchlist" else "Creator Download")
                    s["target_type"] = target_type
                    s["target_url"] = target_url.strip()
                    s["trigger_type"] = trigger_type
                    s["interval_hours"] = max(1, int(interval_hours))
                    s["time_of_day"] = time_of_day
                    now = datetime.datetime.now()
                    s["next_run"] = self._compute_next_run(now, trigger_type, interval_hours, time_of_day).isoformat()
                    self._save_unlocked()
                    logger.info(f"Updated automated schedule '{s['name']}' ({sched_id}).", category="scheduler")
                    return True
        return False


    def delete_schedule(self, sched_id: str) -> bool:
        """Deletes a schedule by ID."""
        with self._lock:
            before_len = len(self.schedules)
            self.schedules = [s for s in self.schedules if s.get("id") != sched_id]
            if len(self.schedules) < before_len:
                self._save_unlocked()
                logger.info(f"Deleted schedule {sched_id}.", category="scheduler")
                return True
        return False

    def toggle_schedule(self, sched_id: str, enabled: bool) -> bool:
        """Enables or disables an individual schedule."""
        with self._lock:
            for s in self.schedules:
                if s.get("id") == sched_id:
                    s["enabled"] = bool(enabled)
                    if enabled and not s.get("next_run"):
                        now = datetime.datetime.now()
                        s["next_run"] = self._compute_next_run(
                            now, s.get("trigger_type", "interval"),
                            s.get("interval_hours", 6), s.get("time_of_day", "03:00")
                        ).isoformat()
                    self._save_unlocked()
                    return True
        return False

    @staticmethod
    def _compute_next_run(
        from_time: datetime.datetime,
        trigger_type: str,
        interval_hours: int,
        time_of_day: str
    ) -> datetime.datetime:
        """Calculates next run datetime based on trigger type."""
        if trigger_type == "time_of_day":
            try:
                parts = time_of_day.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                target = from_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= from_time:
                    target += datetime.timedelta(days=1)
                return target
            except Exception:
                return from_time + datetime.timedelta(hours=6)
        else:  # interval
            return from_time + datetime.timedelta(hours=max(1, interval_hours))

    def is_in_night_owl_window(self, check_time: Optional[datetime.time] = None) -> bool:
        """
        Evaluates whether the current time is within the configured Night Owl window.
        Correctly handles windows that cross midnight (e.g., 23:00 to 06:00).
        """
        if not self.night_owl_enabled:
            return True

        if not check_time:
            check_time = datetime.datetime.now().time()

        try:
            s_h, s_m = [int(p) for p in self.night_owl_start.split(":")]
            e_h, e_m = [int(p) for p in self.night_owl_end.split(":")]
            start = datetime.time(s_h, s_m)
            end = datetime.time(e_h, e_m)

            if start <= end:
                return start <= check_time <= end
            else:  # Crosses midnight (e.g. 23:00 -> 06:00)
                return check_time >= start or check_time <= end
        except Exception as e:
            logger.debug(f"Error evaluating Night Owl window: {e}", category="scheduler")
            return True

    def acquire_sleep_lock(self):
        """Prevents Windows system sleep and standby while downloads are active."""
        if not self.prevent_sleep:
            return

        if sys.platform == "win32" and not self._sleep_lock_active:
            try:
                flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
                ctypes.windll.kernel32.SetThreadExecutionState(flags)
                self._sleep_lock_active = True
                logger.debug("Windows Sleep Prevention activated (Away Mode ON).", category="scheduler")
            except Exception as e:
                logger.debug(f"Could not set execution state: {e}", category="scheduler")

    def release_sleep_lock(self):
        """Releases sleep prevention lock, restoring default power management."""
        if sys.platform == "win32" and self._sleep_lock_active:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                self._sleep_lock_active = False
                logger.debug("Windows Sleep Prevention released.", category="scheduler")
            except Exception as e:
                logger.debug(f"Could not reset execution state: {e}", category="scheduler")

    def start(self):
        """Starts the background scheduler thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="TaskSchedulerLoop")
        self._thread.start()
        logger.info("Task Scheduler background engine started.", category="scheduler")

    def stop(self):
        """Stops the scheduler loop and releases power locks."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.release_sleep_lock()
        logger.info("Task Scheduler stopped.", category="scheduler")

    def _scheduler_loop(self):
        """Periodic background evaluation loop."""
        while not self._stop_event.is_set():
            now = datetime.datetime.now()

            if self.enabled:
                with self._lock:
                    schedules_copy = list(self.schedules)

                for sched in schedules_copy:
                    if self._stop_event.is_set():
                        break
                    if not sched.get("enabled", True):
                        continue

                    next_run_str = sched.get("next_run")
                    if not next_run_str:
                        continue

                    try:
                        next_run_dt = datetime.datetime.fromisoformat(next_run_str)
                    except Exception:
                        continue

                    if now >= next_run_dt:
                        # Time to trigger! Check Night Owl window
                        if self.night_owl_enabled and not self.is_in_night_owl_window(now.time()):
                            logger.info(
                                f"Schedule '{sched['name']}' trigger reached, but currently outside Night Owl window ({self.night_owl_start}–{self.night_owl_end}). Waiting...",
                                category="scheduler"
                            )
                            continue

                        # Execute schedule
                        self._execute_schedule(sched)

            # Check every 10 seconds
            self._stop_event.wait(10.0)

    def _execute_schedule(self, sched: Dict[str, Any]):
        """Executes the action for a triggered schedule."""
        sched_name = sched.get("name", "Task")
        target_type = sched.get("target_type", "watchlist")
        logger.info(f"⏰ [SCHEDULER] Triggering schedule '{sched_name}' ({target_type})...", category="scheduler")

        self.acquire_sleep_lock()
        try:
            sched["status"] = "running"
            now = datetime.datetime.now()
            sched["last_run"] = now.isoformat()

            # Compute next run
            sched["next_run"] = self._compute_next_run(
                now, sched.get("trigger_type", "interval"),
                sched.get("interval_hours", 6), sched.get("time_of_day", "03:00")
            ).isoformat()
            self.save()

            if target_type == "watchlist" and self.on_trigger_watchlist_sync:
                self.on_trigger_watchlist_sync()
            elif target_type == "creator" and self.on_trigger_creator_sync:
                self.on_trigger_creator_sync(sched.get("target_url", ""))

            sched["status"] = "idle"
            self.save()
            logger.success(f"✔ [SCHEDULER] Schedule '{sched_name}' finished.", category="scheduler")
        except Exception as e:
            sched["status"] = f"error: {e}"
            self.save()
            logger.error(f"✖ [SCHEDULER] Error executing '{sched_name}': {e}", category="scheduler")
        finally:
            self.release_sleep_lock()


# Global Singleton
task_scheduler = TaskScheduler()
