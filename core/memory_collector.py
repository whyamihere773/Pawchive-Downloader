"""
Central Memory & Resource Collector Subsystem
Provides continuous background memory monitoring, 3-generation Python garbage collection,
working set trimming on Windows, and proactive resource leak prevention.
"""

import os
import sys
import gc
import time
import threading
import ctypes
from typing import Optional, Callable, List
from core.logger import logger

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


class MemoryCollector:
    _instance: Optional["MemoryCollector"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        interval_seconds: float = 60.0,
        working_set_threshold_mb: float = 250.0,
        log_throttle_seconds: float = 60.0
    ):
        self.interval_seconds = interval_seconds
        self.working_set_threshold_mb = working_set_threshold_mb
        self.log_throttle_seconds = log_throttle_seconds
        self._last_log_time: float = 0.0
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._custom_cleanup_hooks: List[Callable[[], None]] = []
        self._last_rss_mb: float = 0.0

    @classmethod
    def instance(
        cls,
        interval_seconds: Optional[float] = None,
        working_set_threshold_mb: Optional[float] = None,
        log_throttle_seconds: Optional[float] = None
    ) -> "MemoryCollector":
        with cls._lock:
            if cls._instance is None:
                cls._instance = MemoryCollector(
                    interval_seconds=interval_seconds if interval_seconds is not None else 60.0,
                    working_set_threshold_mb=working_set_threshold_mb if working_set_threshold_mb is not None else 250.0,
                    log_throttle_seconds=log_throttle_seconds if log_throttle_seconds is not None else 60.0
                )
            else:
                cls._instance.configure(
                    interval_seconds=interval_seconds,
                    working_set_threshold_mb=working_set_threshold_mb,
                    log_throttle_seconds=log_throttle_seconds
                )
            return cls._instance

    def configure(
        self,
        interval_seconds: Optional[float] = None,
        working_set_threshold_mb: Optional[float] = None,
        log_throttle_seconds: Optional[float] = None
    ):
        """Allows dynamic configuration updates on the singleton instance."""
        if interval_seconds is not None:
            self.interval_seconds = interval_seconds
        if working_set_threshold_mb is not None:
            self.working_set_threshold_mb = working_set_threshold_mb
        if log_throttle_seconds is not None:
            self.log_throttle_seconds = log_throttle_seconds

    def register_cleanup_hook(self, hook: Callable[[], None]):
        """Register a callback to be invoked during memory collection passes (e.g. to clear caches)."""
        if hook not in self._custom_cleanup_hooks:
            self._custom_cleanup_hooks.append(hook)

    def unregister_cleanup_hook(self, hook: Callable[[], None]):
        if hook in self._custom_cleanup_hooks:
            self._custom_cleanup_hooks.remove(hook)

    def get_memory_info(self) -> dict:
        """Returns current process memory info in MB."""
        rss_bytes = 0
        vms_bytes = 0

        if _HAS_PSUTIL:
            try:
                proc = psutil.Process()
                mem = proc.memory_info()
                rss_bytes = mem.rss
                vms_bytes = mem.vms
            except Exception as e:
                logger.debug(f"[Memory Collector] psutil memory query failed: {e}", category="system")

        if rss_bytes == 0 and sys.platform == "win32":
            # Fallback to direct Win32 GetProcessMemoryInfo via ctypes
            try:
                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ('cb', ctypes.c_ulong),
                        ('PageFaultCount', ctypes.c_ulong),
                        ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t),
                    ]
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                h_proc = ctypes.windll.kernel32.GetCurrentProcess()
                if ctypes.windll.psapi.GetProcessMemoryInfo(h_proc, ctypes.byref(counters), counters.cb):
                    rss_bytes = counters.WorkingSetSize
                    vms_bytes = counters.PagefileUsage
            except Exception as e:
                logger.debug(f"[Memory Collector] Win32 GetProcessMemoryInfo failed: {e}", category="system")

        rss_mb = rss_bytes / (1024.0 * 1024.0)
        vms_mb = vms_bytes / (1024.0 * 1024.0)
        self._last_rss_mb = rss_mb
        return {
            "rss_mb": round(rss_mb, 2),
            "vms_mb": round(vms_mb, 2),
        }

    def collect(self, force_working_set_trim: bool = False, emit_log: bool = True) -> dict:
        """
        Executes a single unified garbage collection pass across all generations.
        Optionally trims working set on Windows if explicitly requested (e.g. entering idle state).
        Emits a pink log entry if cyclic garbage was freed or memory was trimmed (rate-limited).
        """
        # 1. Run custom cache invalidation callbacks
        for hook in list(self._custom_cleanup_hooks):
            try:
                hook()
            except Exception as e:
                logger.debug(f"[Memory Collector] Cleanup hook raised exception: {e}", category="system")

        # 2. Trigger Python cyclic garbage collection (single pass sweeps all generations)
        unreachable = 0
        try:
            unreachable = gc.collect()
        except Exception as e:
            logger.debug(f"[Memory Collector] gc.collect error: {e}", category="system")

        # 3. Working set trim on Windows (explicitly commanded when idle, avoiding periodic paging)
        mem_before = self.get_memory_info()
        trimmed = False

        if sys.platform == "win32" and force_working_set_trim:
            try:
                h_proc = ctypes.windll.kernel32.GetCurrentProcess()
                # EmptyWorkingSet requests Windows to page out inactive pages
                ctypes.windll.psapi.EmptyWorkingSet(h_proc)
                trimmed = True
            except Exception as e:
                logger.debug(f"[Memory Collector] EmptyWorkingSet failed: {e}", category="system")
                try:
                    ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1)
                    trimmed = True
                except Exception as ex:
                    logger.debug(f"[Memory Collector] SetProcessWorkingSetSize fallback failed: {ex}", category="system")

        mem_after = self.get_memory_info()

        # 4. Emit pink rate-limited log message if collector did something
        now = time.time()
        if emit_log and (unreachable > 0 or trimmed):
            if now - self._last_log_time >= self.log_throttle_seconds:
                self._last_log_time = now
                if trimmed:
                    msg = (
                        f"🧹 Memory collector sweep: freed {unreachable} cyclic object(s) & "
                        f"trimmed working set ({mem_before['rss_mb']} MB → {mem_after['rss_mb']} MB)"
                    )
                elif mem_before['rss_mb'] != mem_after['rss_mb']:
                    msg = (
                        f"🧹 Memory collector sweep: freed {unreachable} cyclic object(s) "
                        f"({mem_before['rss_mb']} MB → {mem_after['rss_mb']} MB)"
                    )
                else:
                    msg = (
                        f"🧹 Memory collector sweep: freed {unreachable} cyclic object(s) "
                        f"({mem_after['rss_mb']} MB in use)"
                    )
                logger.info(msg, category="memory")

        return {
            "unreachable_collected": unreachable,
            "before_rss_mb": mem_before["rss_mb"],
            "after_rss_mb": mem_after["rss_mb"],
            "trimmed": trimmed
        }

    def start(self):
        """Starts the background monitoring daemon thread."""
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._background_sweep_loop,
                daemon=True,
                name="MemoryCollectorDaemon"
            )
            self._worker_thread.start()
            logger.debug("Memory & Resource Collector daemon active.", category="system")

    def stop(self):
        """Signals the background monitoring thread to stop."""
        self._stop_event.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None

    def _background_sweep_loop(self):
        while not self._stop_event.wait(self.interval_seconds):
            try:
                # Periodic background pass: collect cyclic garbage without forced paging/trimming
                self.collect(force_working_set_trim=False)
            except Exception as e:
                logger.debug(f"[Memory Collector] Background sweep loop error: {e}", category="system")


# Global singleton instance
memory_collector = MemoryCollector.instance()
