"""
Hang detector: notices when the window stops responding and writes what it was doing to the log.

A timer on the window thread ticks every 25 ms; a watchdog thread checks the ticks. When they stop for
longer than the threshold, the watchdog takes the window thread's Python stack at that moment (the code
that is blocking it) and, once the window responds again, logs how long it was stuck with that stack.
A stack that only shows the Qt event loop means the time went into Qt / QML itself (building items,
layout, a big model reset) rather than into Python.

Threshold: 1 s in release builds, 100 ms in beta builds; PAWCHIVE_HANG_MS overrides it (the tests use it).
"""

import json
import os
import sys
import threading
import time
import traceback
from typing import Callable, List, Optional, Tuple

from core.logger import logger


def _default_threshold_ms() -> int:
    env = os.environ.get("PAWCHIVE_HANG_MS", "").strip()
    if env.isdigit() and int(env) > 0:
        return int(env)
    try:
        from core.path_utils import get_app_root
        for root in (get_app_root(), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
            path = os.path.join(root, "version.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    if str(json.load(f).get("channel", "release")).lower() != "release":
                        return 100
                break
    except Exception:
        pass
    return 1000


class HangDetector:
    TICK_MS = 25
    LONG_S = 5.0

    def __init__(self, threshold_ms: Optional[int] = None):
        self.threshold_ms = int(threshold_ms or _default_threshold_ms())
        self._last_tick = time.perf_counter()
        self._window_thread = threading.main_thread().ident
        self._stop = threading.Event()
        self._timer = None
        self._thread: Optional[threading.Thread] = None
        self.stalls: List[Tuple[float, str, float]] = []   # (milliseconds, stack, when the stack was taken)
        self.on_stall: Optional[Callable[[float, str], None]] = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, parent=None) -> None:
        """Call on the window thread once the Qt application exists."""
        if self.running:
            return
        from PySide6.QtCore import QTimer
        self._window_thread = threading.get_ident()
        self._last_tick = time.perf_counter()
        self._timer = QTimer(parent)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._stop.clear()
        self._thread = threading.Thread(target=self._watch, name="HangDetector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._timer is not None:
            try:
                self._timer.stop()
            except RuntimeError:
                pass

    def _tick(self) -> None:
        self._last_tick = time.perf_counter()

    def _stack(self) -> str:
        frame = sys._current_frames().get(self._window_thread)
        if frame is None:
            return ""
        lines = traceback.format_stack(frame)
        # The innermost frames say what's blocking; the outer ones are always main() / exec()
        return "".join(lines[-14:])

    def _watch(self) -> None:
        threshold = self.threshold_ms / 1000.0
        while not self._stop.wait(0.02):
            started = self._last_tick
            if time.perf_counter() - started < threshold:
                continue
            stack = self._stack()
            caught = time.perf_counter()
            reported_long = False
            while not self._stop.is_set() and self._last_tick == started:
                time.sleep(0.02)
                if not reported_long and time.perf_counter() - started > self.LONG_S:
                    # A freeze that may never end is logged while it's happening
                    reported_long = True
                    logger.warning(f"⏳ The window hasn't responded for {self.LONG_S:.0f} s; it's busy with:",
                                   category="system", details=self._stack() or stack)
            ms = (time.perf_counter() - started) * 1000.0 - self.TICK_MS
            if self._stop.is_set() or ms < self.threshold_ms:
                continue
            self.stalls.append((ms, stack, caught))
            in_qt = (not stack.strip()) or ("exec" in stack.strip().splitlines()[-1] if stack.strip() else True)
            where = "inside Qt / QML (building or laying out items)" if in_qt else "in the code below"
            logger.warning(f"⏳ The window stopped responding for {ms:.0f} ms ({where}).",
                           category="system", details=stack)
            if self.on_stall:
                try:
                    self.on_stall(ms, stack)
                except Exception:
                    pass


hang_detector = HangDetector()
