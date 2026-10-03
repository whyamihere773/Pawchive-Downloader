"""
Keeps the computer from going to sleep while downloads are running.

Windows: SetThreadExecutionState, called from one long-lived helper thread (the request belongs to
the thread that makes it, so calling it from short-lived threads did nothing once they ended).
Linux: systemd-inhibit. macOS: caffeinate. When none is available, nothing happens.
"""

import atexit
import os
import shutil
import subprocess
import sys
import threading
from typing import Optional

from core.logger import logger

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


class SleepInhibitor:
    def __init__(self):
        self._lock = threading.Lock()
        self._active = False
        self._proc: Optional[subprocess.Popen] = None
        self._win_want = False
        self._win_wake = threading.Event()
        self._win_thread: Optional[threading.Thread] = None

    @property
    def active(self) -> bool:
        return self._active

    def set_active(self, active: bool, reason: str = "Downloading files") -> None:
        with self._lock:
            if active == self._active:
                return
            self._active = active
            try:
                if sys.platform == "win32":
                    self._set_windows(active)
                else:
                    self._set_posix(active, reason)
                logger.debug("Sleep prevention " + ("on while downloading." if active else "off."), category="system")
            except Exception as e:
                logger.debug(f"Sleep prevention unavailable: {e}", category="system")

    # Windows ------------------------------------------------------------------
    def _set_windows(self, active: bool) -> None:
        self._win_want = active
        if self._win_thread is None:
            self._win_thread = threading.Thread(target=self._windows_loop, daemon=True, name="SleepInhibitor")
            self._win_thread.start()
        self._win_wake.set()

    def _windows_loop(self) -> None:
        import ctypes
        set_state = ctypes.windll.kernel32.SetThreadExecutionState
        while True:
            self._win_wake.wait()
            self._win_wake.clear()
            set_state(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED if self._win_want else _ES_CONTINUOUS)

    # Linux / macOS -------------------------------------------------------------
    def _set_posix(self, active: bool, reason: str) -> None:
        if not active:
            if self._proc is not None:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=3)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
                self._proc = None
            return
        # The helper ends by itself when this app's process ends (even after a crash)
        pid = str(os.getpid())
        if sys.platform == "darwin" and shutil.which("caffeinate"):
            cmd = ["caffeinate", "-i", "-w", pid]
        elif shutil.which("systemd-inhibit") and shutil.which("tail"):
            cmd = ["systemd-inhibit", "--what=idle:sleep", "--who=Pawchive Downloader",
                   f"--why={reason}", "--mode=block", "tail", f"--pid={pid}", "-f", "/dev/null"]
        else:
            return
        self._proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)


sleep_inhibitor = SleepInhibitor()
atexit.register(lambda: sleep_inhibitor.set_active(False))
