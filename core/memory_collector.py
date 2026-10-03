"""
Central Memory & Resource Collector Subsystem

- A light check every minute: runs the registered cleanup hooks (pictures kept in memory expire,
  AI models that sat unused get unloaded), reads the memory in use, tracks the peak and warns when
  it gets high. It does NOT run a full garbage collection: with the app's ~300k long-lived objects
  that pauses all Python code (gallery, thumbnails, lists) for 50-100 ms each time.
- A full collection runs only when it's free for the user: after a download finishes and when the
  window is minimized.
- freeze_startup_objects() moves everything loaded at startup (character database, settings…) out
  of the collector's scans for the rest of the session.
"""

import sys
import gc
import time
import threading
import ctypes
from typing import Optional, Callable, Dict, List
from core.logger import logger

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

HIGH_MEMORY_WARNING_MB = 1536        # warn above this (once; again only after dropping well below)
SUMMARY_EVERY_SECONDS = 3600         # one INFO line per hour with the current and peak memory


def _fmt_mb(mb: float) -> str:
    return f"{mb / 1024:.2f} GB" if mb >= 1024 else f"{mb:.0f} MB"


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
        self.high_memory_mb = HIGH_MEMORY_WARNING_MB
        self.log_throttle_seconds = log_throttle_seconds
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._custom_cleanup_hooks: List[Callable[[], None]] = []
        self._reporters: Dict[str, Callable[[], str]] = {}
        self._last_rss_mb: float = 0.0
        self._peak_mb: float = 0.0
        self._hour_peak_mb: float = 0.0
        self._last_summary = time.monotonic()
        self._warned_high = False
        self._frozen = False
        self._collect_lock = threading.Lock()

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
                    log_throttle_seconds=log_throttle_seconds if log_throttle_seconds is not None else 60.0
                )
            else:
                cls._instance.configure(interval_seconds=interval_seconds, log_throttle_seconds=log_throttle_seconds)
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
        if log_throttle_seconds is not None:
            self.log_throttle_seconds = log_throttle_seconds

    # ── What other parts of the app plug in ──────────────────────────────────
    def register_cleanup_hook(self, hook: Callable[[], None]):
        """Called on every check (e.g. to expire cached pictures or unload idle AI models)."""
        if hook not in self._custom_cleanup_hooks:
            self._custom_cleanup_hooks.append(hook)

    def unregister_cleanup_hook(self, hook: Callable[[], None]):
        if hook in self._custom_cleanup_hooks:
            self._custom_cleanup_hooks.remove(hook)

    def register_reporter(self, name: str, reporter: Callable[[], str]):
        """reporter() describes what this part holds in memory (shown in high-memory warnings)."""
        self._reporters[name] = reporter

    def describe_holders(self) -> str:
        parts = []
        for name, reporter in list(self._reporters.items()):
            try:
                text = reporter()
            except Exception as e:
                text = f"? ({e})"
            if text:
                parts.append(f"{name}: {text}")
        return "; ".join(parts)

    # ── Measuring ─────────────────────────────────────────────────────────────
    def get_memory_info(self) -> dict:
        """Current process memory in MB: rss (physical memory in use) and vms (committed / virtual)."""
        rss_bytes = 0
        vms_bytes = 0

        if _HAS_PSUTIL:
            try:
                mem = psutil.Process().memory_info()
                rss_bytes, vms_bytes = mem.rss, mem.vms
            except Exception as e:
                logger.debug(f"[Memory Collector] psutil memory query failed: {e}", category="system")

        if rss_bytes == 0 and sys.platform == "win32":
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

        if rss_bytes == 0 and sys.platform.startswith("linux"):
            # Without psutil: /proc/self/status has the resident and virtual size in kB
            try:
                with open("/proc/self/status", "r", encoding="ascii", errors="replace") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            rss_bytes = int(line.split()[1]) * 1024
                        elif line.startswith("VmSize:"):
                            vms_bytes = int(line.split()[1]) * 1024
            except (OSError, ValueError, IndexError) as e:
                logger.debug(f"[Memory Collector] /proc/self/status read failed: {e}", category="system")

        rss_mb = rss_bytes / (1024.0 * 1024.0)
        vms_mb = vms_bytes / (1024.0 * 1024.0)
        self._last_rss_mb = rss_mb
        if rss_mb > self._peak_mb:
            self._peak_mb = rss_mb
        if rss_mb > self._hour_peak_mb:
            self._hour_peak_mb = rss_mb
        return {"rss_mb": round(rss_mb, 2), "vms_mb": round(vms_mb, 2)}

    # ── Work ──────────────────────────────────────────────────────────────────
    def _run_hooks(self):
        for hook in list(self._custom_cleanup_hooks):
            try:
                hook()
            except Exception:
                logger.exception("[Memory Collector] A cleanup step failed", category="memory", level="DEBUG")

    def check(self) -> dict:
        """The light periodic pass: cleanup hooks, memory reading, peak tracking, warnings."""
        self._run_hooks()
        mem = self.get_memory_info()
        rss = mem["rss_mb"]
        if rss >= self.high_memory_mb and not self._warned_high:
            self._warned_high = True
            holders = self.describe_holders()
            logger.warning(
                f"Pawchive is using a lot of memory: {_fmt_mb(rss)}.",
                category="memory",
                details=f"peak this session: {_fmt_mb(self._peak_mb)}" + (f"\n{holders}" if holders else ""),
            )
        elif rss < self.high_memory_mb * 0.8:
            self._warned_high = False       # warn again if it climbs back up
        now = time.monotonic()
        if now - self._last_summary >= SUMMARY_EVERY_SECONDS and rss > 0:
            self._last_summary = now
            holders = self.describe_holders()
            logger.info(
                f"Memory: {_fmt_mb(rss)} in use, peak {_fmt_mb(self._hour_peak_mb)} in the last hour "
                f"({_fmt_mb(self._peak_mb)} this session).",
                category="memory",
                details=holders,
            )
            self._hour_peak_mb = rss
        return mem

    def collect(self, force_working_set_trim: bool = False, emit_log: bool = True, reason: str = "") -> dict:
        """
        A full garbage collection (all generations). Only run where a short pause doesn't matter:
        after a download finishes or while the window is minimized.
        `force_working_set_trim` is accepted for compatibility and ignored: forcing Windows to page
        memory out only makes Task Manager's number smaller and costs page faults afterwards.
        """
        if not self._collect_lock.acquire(blocking=False):
            return {}                                  # one is already running
        try:
            self._run_hooks()
            mem_before = self.get_memory_info()
            t0 = time.perf_counter()
            unreachable = 0
            try:
                unreachable = gc.collect()
            except Exception as e:
                logger.debug(f"[Memory Collector] gc.collect error: {e}", category="system")
            took_ms = (time.perf_counter() - t0) * 1000
            mem_after = self.get_memory_info()
            if emit_log:
                logger.debug(
                    f"🧹 Memory cleanup{f' ({reason})' if reason else ''}: {unreachable} unused object(s) freed in "
                    f"{took_ms:.0f} ms ({_fmt_mb(mem_before['rss_mb'])} → {_fmt_mb(mem_after['rss_mb'])})",
                    category="memory",
                )
            return {
                "unreachable_collected": unreachable,
                "before_rss_mb": mem_before["rss_mb"],
                "after_rss_mb": mem_after["rss_mb"],
                "took_ms": round(took_ms, 1),
                "trimmed": False,
            }
        finally:
            self._collect_lock.release()

    def collect_in_background(self, reason: str = "") -> None:
        threading.Thread(target=self.collect, kwargs={"reason": reason}, daemon=True, name="MemoryCleanup").start()

    def freeze_startup_objects(self) -> None:
        """After startup: collect once, then move everything still alive (character database, settings,
        loaded modules…) out of future collections, so they only scan what changes."""
        if self._frozen or not hasattr(gc, "freeze"):
            return
        self._frozen = True
        t0 = time.perf_counter()
        gc.collect()
        gc.freeze()
        logger.debug(
            f"Memory: {gc.get_freeze_count():,} startup objects excluded from future cleanups "
            f"(took {(time.perf_counter() - t0) * 1000:.0f} ms).",
            category="memory",
        )

    # ── Background loop ───────────────────────────────────────────────────────
    def start(self):
        """Starts the background monitoring daemon thread."""
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._background_loop,
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

    def _background_loop(self):
        while not self._stop_event.wait(self.interval_seconds):
            try:
                self.check()
            except Exception:
                logger.exception("[Memory Collector] Background check failed", category="memory", level="DEBUG")


# Global singleton instance
memory_collector = MemoryCollector.instance()
