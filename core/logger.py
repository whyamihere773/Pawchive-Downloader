"""
Central Logging Subsystem
Thread-safe multi-level logging to the console panel, the terminal and a per-session log file.

Log files live next to the app, one folder per app version:

    logs/v1.2.1/2026-10-02_10-00-00.log      one file per app session
    logs/updater/...                          the updater's own runs (written by the updater)
    logs/older/...                            logs from before this layout (moved, never deleted)

Nothing is written to disk until the app calls start_session(), so scripts and tests that import
the logger don't leave empty log files behind. Log files are never deleted automatically; only the
user's "Clear logs" button removes them.
"""

import sys
import os
import datetime
import threading
import time
import traceback
from typing import Callable, List, Optional

from core.log_utils import redact, system_summary

try:
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SESSION_END_MARKER = "=== Session ended"
_MAX_PENDING_LINES = 5000


class LogLevel:
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogEntry:
    def __init__(self, message: str, level: str = LogLevel.INFO, category: str = "general", details: str = ""):
        self.created = datetime.datetime.now()
        self.timestamp = self.created.strftime("%H:%M:%S")
        self.message = str(message)
        self.level = level
        self.category = category
        self.details = details          # extra lines for the log file only (tracebacks, URLs, lists)

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "message": self.message,
            "level": self.level,
            "category": self.category
        }

    def __str__(self):
        return f"[{self.timestamp}] [{self.level.upper()}] {self.message}"


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")


class AppLogger:
    _instance = None

    def __init__(self):
        self._listeners = []
        self._history = []
        self._max_history = 1000
        self._file_lock = threading.RLock()
        self._pending: List[str] = []          # lines logged before the session file exists
        self._session_start_time = datetime.datetime.now()
        self._logs_dir = ""
        self._session_dir = ""
        self._current_log_path = ""
        self._crash_path = ""
        self._crash_file = None
        self._ended = False
        self._version_label = ""
        # Lines are written to the file by a background writer a few times a second (warnings and
        # errors at once): opening the file for every line cost milliseconds on Windows (antivirus
        # checks on close), paid by whichever thread logged, the window's too
        self._file_queue: List[str] = []
        self._write_wanted = threading.Event()
        self._writer: Optional[threading.Thread] = None

    @classmethod
    def instance(cls) -> "AppLogger":
        if cls._instance is None:
            cls._instance = AppLogger()
        return cls._instance

    # ── Locations ─────────────────────────────────────────────────────────────
    def get_logs_dir(self) -> str:
        """The root logs folder (next to the app)."""
        if not self._logs_dir:
            try:
                from core.path_utils import get_logs_dir
                self._logs_dir = get_logs_dir()
            except Exception:
                self._logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        return self._logs_dir

    def get_session_dir(self) -> str:
        return self._session_dir

    def get_current_log_file(self) -> str:
        return self._current_log_path

    def get_current_crash_file(self) -> str:
        return self._crash_path

    def _get_log_file_path(self) -> str:
        return self._current_log_path

    # ── Session ───────────────────────────────────────────────────────────────
    def start_session(self) -> str:
        """Create this session's log file (logs/v<version>/<date_time>.log) and write the header.
        Called once by the app at startup; lines logged before that are written into it too."""
        with self._file_lock:
            if self._current_log_path:
                return self._current_log_path
            info = self._version_info()
            self._version_label = f"v{info.get('version') or '0.0.0'}"
            root = self.get_logs_dir()
            session_dir = os.path.join(root, self._version_label)
            stamp = self._session_start_time.strftime("%Y-%m-%d_%H-%M-%S")
            try:
                os.makedirs(session_dir, exist_ok=True)
            except OSError:
                session_dir = root
            path = os.path.join(session_dir, f"{stamp}.log")
            n = 2
            while os.path.exists(path):                       # two sessions in the same second
                path = os.path.join(session_dir, f"{stamp}_{n}.log")
                n += 1
            previous_note = self._previous_session_note(root)
            self._session_dir = session_dir
            self._current_log_path = path
            self._append_raw(self._header(info, previous_note))
            if self._pending:
                self._append_raw("".join(self._pending))
                self._pending.clear()
            self._remember_session(root, path)
        self._enable_fault_dump()
        # Runs after Python has waited for background threads, i.e. at the very end of a normal exit
        import atexit
        atexit.register(self.end_session, "normally")
        threading.Thread(target=self._move_legacy_logs, daemon=True, name="LogMigration").start()
        return path

    def end_session(self, reason: str = "normally") -> None:
        """Write the closing line, so a missing one means the app crashed or was killed."""
        with self._file_lock:
            if self._ended or not self._current_log_path:
                return
            self._ended = True
            self.flush()
            now = datetime.datetime.now()
            ran = _format_duration((now - self._session_start_time).total_seconds())
            self._append_raw(f"{SESSION_END_MARKER} {reason} at {now:%Y-%m-%d %H:%M:%S} (ran {ran}) ===\n")
        self._close_fault_dump(keep=reason != "normally")

    def _version_info(self) -> dict:
        try:
            from services.update_service import get_local_version_info
            return get_local_version_info()
        except Exception:
            return {"version": "0.0.0", "display": "unknown version", "edition_label": ""}

    def _header(self, info: dict, previous_note: str) -> str:
        try:
            import PySide6
            from PySide6.QtCore import qVersion
            qt = f"PySide6 {PySide6.__version__} (Qt {qVersion()})"
        except Exception:
            qt = "PySide6 not available"
        start = self._session_start_time
        offset = start.astimezone().strftime("%z")
        offset = f"UTC{offset[:3]}:{offset[3:]}" if offset else ""
        edition = info.get("edition_label") or ""
        branch = info.get("branch") or ""
        lines = [
            "=" * 72,
            f"Pawchive Downloader {info.get('display', '')}"
            + (f" · {edition}" if edition else "") + (f" · branch {branch}" if branch else ""),
            f"Session started {start:%Y-%m-%d %H:%M:%S} {offset}".rstrip(),
            f"System: {system_summary()}",
            f"Python {sys.version.split()[0]} · {qt}",
            f"App folder: {redact(os.path.dirname(self.get_logs_dir()))}",
        ]
        if previous_note:
            lines.append(previous_note)
        lines.append("=" * 72)
        return "\n".join(lines) + "\n"

    def _previous_session_note(self, root: str) -> str:
        """If the last session's log has no closing line, say so (it crashed or was killed)."""
        try:
            with open(os.path.join(root, ".last_session"), "r", encoding="utf-8") as f:
                last = f.read().strip()
            if not last or not os.path.isfile(last):
                return ""
            crash = last[:-4] + ".crash.log"
            if os.path.isfile(crash) and os.path.getsize(crash) == 0:
                os.remove(crash)        # the unused placeholder of a session that didn't crash hard
            with open(last, "rb") as f:
                f.seek(max(0, os.path.getsize(last) - 4096))
                tail = f.read().decode("utf-8", "replace")
            if SESSION_END_MARKER in tail:
                return ""
            note = f"⚠ The previous session ({os.path.basename(os.path.dirname(last))}/{os.path.basename(last)}) didn't close normally: it crashed, was force-closed, or the PC shut down."
            if os.path.isfile(crash) and os.path.getsize(crash) > 0:
                note += f" Crash details: {os.path.basename(crash)}"
            return note
        except (OSError, ValueError):
            return ""

    def _remember_session(self, root: str, path: str) -> None:
        try:
            with open(os.path.join(root, ".last_session"), "w", encoding="utf-8") as f:
                f.write(path)
        except OSError:
            pass

    # ── Hard crashes (Python/Qt dying in native code) ───────────────────────
    def _enable_fault_dump(self) -> None:
        """A hard crash (segfault, abort) can't run Python code, so faulthandler writes the stack of
        every thread straight into <session>.crash.log. The file is removed again after a normal exit."""
        try:
            import faulthandler
            self._crash_path = self._current_log_path[:-4] + ".crash.log"
            self._crash_file = open(self._crash_path, "w", encoding="utf-8")
            faulthandler.enable(file=self._crash_file, all_threads=True)
        except Exception:
            self._crash_path, self._crash_file = "", None

    def _close_fault_dump(self, keep: bool) -> None:
        if not self._crash_file:
            return
        try:
            import faulthandler
            faulthandler.disable()
            self._crash_file.close()
            # Only an empty file, or noise from errors the app survived, is removed after a clean exit
            if not keep and os.path.exists(self._crash_path):
                os.remove(self._crash_path)
        except Exception:
            pass
        self._crash_file = None

    # ── Errors nobody caught ────────────────────────────────────────────────
    def install_crash_handlers(self) -> None:
        """Log every error nobody caught (main thread, background threads, Qt slots, __del__)
        with its full traceback. Release builds have no console, so without this they vanish."""
        def _excepthook(exc_type, exc, tb):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc, tb)
                return
            self.log(f"Unexpected error: {exc_type.__name__}: {exc}", LogLevel.ERROR, "crash",
                     details="".join(traceback.format_exception(exc_type, exc, tb)))

        def _thread_hook(args):
            if args.exc_type is SystemExit:
                return
            name = args.thread.name if args.thread else "background task"
            self.log(f"Unexpected error in '{name}': {args.exc_type.__name__}: {args.exc_value}", LogLevel.ERROR, "crash",
                     details="".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

        def _unraisable_hook(u):
            where = f" in {u.object!r}" if u.object is not None else ""
            self.log(f"Ignored error{where}: {u.exc_type.__name__}: {u.exc_value}", LogLevel.WARNING, "crash",
                     details="".join(traceback.format_exception(u.exc_type, u.exc_value, u.exc_traceback)))

        sys.excepthook = _excepthook
        threading.excepthook = _thread_hook
        sys.unraisablehook = _unraisable_hook
        self._bridge_std_logging()

    def _bridge_std_logging(self) -> None:
        """Libraries (Telethon, gdown, urllib3…) report problems through Python's `logging` module."""
        import logging
        app_logger = self

        class _Bridge(logging.Handler):
            def emit(self, record):
                try:
                    if record.levelno >= logging.ERROR:
                        level = LogLevel.ERROR
                    elif record.levelno >= logging.WARNING:
                        level = LogLevel.WARNING
                    elif record.levelno >= logging.INFO:
                        level = LogLevel.INFO
                    else:
                        level = LogLevel.DEBUG
                    details = self.formatter.formatException(record.exc_info) if record.exc_info else ""
                    app_logger.log(record.getMessage(), level, record.name.split(".")[0] or "lib", details=details)
                except Exception:
                    pass

        root = logging.getLogger()
        if not any(isinstance(h, _Bridge) or getattr(h, "_pawchive", False) for h in root.handlers):
            handler = _Bridge()
            handler._pawchive = True
            handler.setFormatter(logging.Formatter())
            root.addHandler(handler)
        root.setLevel(logging.WARNING)                     # libraries: warnings and errors only
        logging.getLogger("pawchive").setLevel(logging.INFO)

    # ── Moving logs written by older versions ────────────────────────────────
    def _move_legacy_logs(self) -> None:
        """Older versions wrote every log flat into logs/ (Windows builds: _internal/logs, Linux builds:
        ~/.local/share/pawchive/logs). Move them into logs/older and logs/updater; nothing is deleted."""
        import shutil
        root = self.get_logs_dir()
        try:
            from core.path_utils import get_legacy_logs_dirs
            sources = [root] + [d for d in get_legacy_logs_dirs() if os.path.normcase(os.path.abspath(d)) != os.path.normcase(os.path.abspath(root))]
        except Exception:
            sources = [root]
        moved = 0
        for src in sources:
            try:
                names = [n for n in os.listdir(src) if n.lower().endswith(".log") and os.path.isfile(os.path.join(src, n))]
            except OSError:
                continue
            for name in names:
                if name.lower() == "updater.log":
                    dest_dir, dest_name = os.path.join(root, "updater"), "updater (older versions).log"
                else:
                    dest_dir, dest_name = os.path.join(root, "older"), name
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                    dest = os.path.join(dest_dir, dest_name)
                    base, ext = os.path.splitext(dest)
                    n = 2
                    while os.path.exists(dest):
                        dest = f"{base} ({n}){ext}"
                        n += 1
                    shutil.move(os.path.join(src, name), dest)
                    moved += 1
                except OSError:
                    continue
            if src != root:
                try:
                    os.rmdir(src)                     # only succeeds when nothing is left in it
                except OSError:
                    pass
        if moved:
            self.info(f"Moved {moved} log file(s) from older versions into the 'older' and 'updater' folders.", category="logger")

    # ── Writing ───────────────────────────────────────────────────────────────
    def _append_raw(self, text: str):
        try:
            with self._file_lock:
                with open(self._current_log_path, "a", encoding="utf-8", errors="replace") as f:
                    f.write(text)
        except Exception:
            pass

    def _append_to_file(self, text: str, urgent: bool = False):
        with self._file_lock:
            if not self._current_log_path:
                self._pending.append(text)
                if len(self._pending) > _MAX_PENDING_LINES:
                    del self._pending[: len(self._pending) - _MAX_PENDING_LINES]
                return
            self._file_queue.append(text)
            if self._ended:
                urgent = True                     # (no writer after the closing line)
            elif self._writer is None or not self._writer.is_alive():
                self._writer = threading.Thread(target=self._writer_loop, name="LogWriter", daemon=True)
                self._writer.start()
        if urgent:
            self.flush()
        else:
            self._write_wanted.set()

    def _writer_loop(self):
        while True:
            self._write_wanted.wait()
            time.sleep(0.3)                       # lines logged together are written together
            self._write_wanted.clear()
            self.flush()

    def flush(self) -> None:
        """Writes the lines still waiting for the background writer."""
        with self._file_lock:
            if not self._file_queue:
                return
            text, self._file_queue = "".join(self._file_queue), []
            self._append_raw(text)

    def add_listener(self, callback: Callable[[LogEntry], None]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[LogEntry], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def log(self, message: str, level: str = LogLevel.INFO, category: str = "general", details: str = ""):
        entry = LogEntry(redact(str(message)), level, category, redact(details) if details else "")
        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        log_line = f"[{entry.created:%Y-%m-%d %H:%M:%S}.{entry.created.microsecond // 1000:03d}] [{entry.level.upper():<7}] [{entry.category}] {entry.message}\n"
        if entry.details:
            log_line += "".join(f"    | {ln}\n" for ln in entry.details.rstrip("\n").split("\n"))
        self._append_to_file(log_line, urgent=entry.level in (LogLevel.WARNING, LogLevel.ERROR))

        try:
            if sys.stdout is not None:
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

    def debug(self, msg: str, category: str = "debug", details: str = ""):
        self.log(msg, LogLevel.DEBUG, category, details)

    def info(self, msg: str, category: str = "info", details: str = ""):
        self.log(msg, LogLevel.INFO, category, details)

    def success(self, msg: str, category: str = "success", details: str = ""):
        self.log(msg, LogLevel.SUCCESS, category, details)

    def warning(self, msg: str, category: str = "warning", details: str = ""):
        self.log(msg, LogLevel.WARNING, category, details)

    def error(self, msg: str, category: str = "error", details: str = ""):
        self.log(msg, LogLevel.ERROR, category, details)

    def exception(self, msg: str, category: str = "error", level: str = LogLevel.ERROR):
        """Log an error together with the traceback of the exception being handled."""
        exc_type, exc, _tb = sys.exc_info()
        if exc is not None and str(exc) and str(exc) not in msg:
            msg = f"{msg}: {type(exc).__name__}: {exc}"
        self.log(msg, level, category, details=traceback.format_exc() if exc is not None else "")

    def get_history(self):
        return list(self._history)

    def clear(self):
        self._history.clear()

    # ── Size / clearing (Settings → Clear logs) ───────────────────────────────
    def logs_usage(self) -> dict:
        """{'files': n, 'bytes': n} for everything in the logs folder."""
        files = size = 0
        for root, _dirs, names in os.walk(self.get_logs_dir()):
            for n in names:
                if n.startswith("."):
                    continue
                try:
                    size += os.path.getsize(os.path.join(root, n))
                    files += 1
                except OSError:
                    pass
        return {"files": files, "bytes": size}

    def delete_all_logs(self) -> dict:
        """Delete every log file except the running session's. Only ever called by the user."""
        keep = {os.path.normcase(os.path.abspath(p)) for p in (self._current_log_path, self._crash_path) if p}
        deleted = failed = freed = 0
        root = self.get_logs_dir()
        for folder, dirs, names in os.walk(root, topdown=False):
            for n in names:
                p = os.path.join(folder, n)
                if os.path.normcase(os.path.abspath(p)) in keep or n == ".last_session":
                    continue
                try:
                    size = os.path.getsize(p)
                    os.remove(p)
                    deleted += 1
                    freed += size
                except OSError:
                    failed += 1
            if folder != root:
                try:
                    os.rmdir(folder)          # empty folders only; the running session's stays
                except OSError:
                    pass
        return {"deleted": deleted, "failed": failed, "freed": freed}


logger = AppLogger.instance()
