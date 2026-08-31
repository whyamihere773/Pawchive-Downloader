"""
Central Logging Subsystem
Provides thread-safe multi-level logging with console formatting and Qt UI event dispatching.
"""

import sys
import os
import datetime
from typing import Callable, Optional

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class LogLevel:
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogEntry:
    def __init__(self, message: str, level: str = LogLevel.INFO, category: str = "general"):
        self.timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.message = str(message)
        self.level = level
        self.category = category

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "message": self.message,
            "level": self.level,
            "category": self.category
        }

    def __str__(self):
        return f"[{self.timestamp}] [{self.level.upper()}] {self.message}"


class AppLogger:
    _instance = None

    def __init__(self):
        self._listeners = []
        self._history = []
        self._max_history = 1000

    @classmethod
    def instance(cls) -> "AppLogger":
        if cls._instance is None:
            cls._instance = AppLogger()
        return cls._instance

    def add_listener(self, callback: Callable[[LogEntry], None]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[LogEntry], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def log(self, message: str, level: str = LogLevel.INFO, category: str = "general"):
        entry = LogEntry(message, level, category)
        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        try:
            print(str(entry), flush=True)
        except Exception:
            try:
                safe_str = str(entry).encode("ascii", errors="replace").decode("ascii")
                print(safe_str, flush=True)
            except Exception:
                pass

        for listener in list(self._listeners):
            try:
                listener(entry)
            except Exception as e:
                try:
                    print(f"[Logger Error] Failed to invoke listener: {e}", file=sys.stderr)
                except Exception:
                    pass

    def debug(self, msg: str, category: str = "debug"):
        self.log(msg, LogLevel.DEBUG, category)

    def info(self, msg: str, category: str = "info"):
        self.log(msg, LogLevel.INFO, category)

    def success(self, msg: str, category: str = "success"):
        self.log(msg, LogLevel.SUCCESS, category)

    def warning(self, msg: str, category: str = "warning"):
        self.log(msg, LogLevel.WARNING, category)

    def error(self, msg: str, category: str = "error"):
        self.log(msg, LogLevel.ERROR, category)

    def get_history(self):
        return list(self._history)

    def clear(self):
        self._history.clear()


logger = AppLogger.instance()
