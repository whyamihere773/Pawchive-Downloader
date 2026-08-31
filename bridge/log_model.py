"""
Console Log Model
Thread-safe Qt model streaming application and network logs into the QML console interface.
"""

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot, QObject
from typing import List
from core.logger import LogEntry, LogLevel, logger


class _ThreadSafeLogDispatcher(QObject):
    """
    Bridges background-thread logger calls to the main Qt thread via signal emission.
    Signal.emit() is thread-safe in Qt; the connected slot will be invoked on the
    receiver's thread via an automatically queued connection.
    """
    entryReceived = Signal(object)   # carries a LogEntry instance

    def push(self, entry: LogEntry):
        """Called from any thread — safely queues the entry to the main thread."""
        self.entryReceived.emit(entry)


# Module-level singleton dispatcher — created once on the main thread
_dispatcher = _ThreadSafeLogDispatcher()


class LogModel(QAbstractListModel):
    TimestampRole = Qt.UserRole + 1
    MessageRole   = Qt.UserRole + 2
    LevelRole     = Qt.UserRole + 3
    CategoryRole  = Qt.UserRole + 4
    LevelColorRole = Qt.UserRole + 5
    IconRole      = Qt.UserRole + 6

    countChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_entries: List[LogEntry] = []
        self._filtered_entries: List[LogEntry] = []
        self._filter_level: str = "ALL"
        self._search_query: str = ""
        self._status_only: bool = False

        # Register ourselves with the global dispatcher (main thread connection)
        _dispatcher.entryReceived.connect(self._on_new_log, Qt.QueuedConnection)

        # Register dispatcher.push as the logger listener (safe to call from any thread)
        logger.add_listener(_dispatcher.push)

    def rowCount(self, parent=QModelIndex()):
        return len(self._filtered_entries)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._filtered_entries):
            return None
        entry = self._filtered_entries[index.row()]
        if role == self.TimestampRole:    return entry.timestamp
        if role == self.MessageRole:      return entry.message
        if role == self.LevelRole:        return entry.level
        if role == self.CategoryRole:     return entry.category
        if role == self.LevelColorRole:   return self._level_color(entry)
        if role == self.IconRole:         return self._level_icon(entry)
        return None

    def roleNames(self):
        return {
            self.TimestampRole:  b"timestamp",
            self.MessageRole:    b"message",
            self.LevelRole:      b"level",
            self.CategoryRole:   b"category",
            self.LevelColorRole: b"levelColor",
            self.IconRole:       b"icon",
        }

    def _level_color(self, entry: LogEntry) -> str:
        msg_lower = entry.message.lower()
        cat_lower = entry.category.lower() if entry.category else ""
        if cat_lower == "adaptive" or "adaptive threading" in msg_lower or "[adaptive" in msg_lower or "⚡ adaptive" in msg_lower:
            return "#C084FC"  # Vibrant Neon Purple / Violet for Adaptive Threading
        # Link scan results get a distinct warm amber/teal so they pop in the log
        if "🔗" in entry.message and ("link" in msg_lower or "extract" in msg_lower):
            return "#F59E0B"  # Warm amber-gold for all link-related messages
        if "links scan complete" in msg_lower or "harvested" in msg_lower:
            return "#F59E0B"
        return {
            LogLevel.DEBUG:   "#7A889B",
            LogLevel.INFO:    "#38BDF8",
            LogLevel.SUCCESS: "#34D399",
            LogLevel.WARNING: "#FBBF24",
            LogLevel.ERROR:   "#F87171",
        }.get(entry.level, "#CBD5E1")

    def _level_icon(self, entry: LogEntry) -> str:
        msg_lower = entry.message.lower()
        cat_lower = entry.category.lower() if entry.category else ""
        if cat_lower == "adaptive" or "adaptive threading" in msg_lower or "[adaptive" in msg_lower or "⚡ adaptive" in msg_lower:
            return "⚡"
        # Link scan messages get a chain-link icon
        if "🔗" in entry.message and ("link" in msg_lower or "extract" in msg_lower):
            return "🔗"
        if "links scan complete" in msg_lower or "harvested" in msg_lower:
            return "🔗"
        return {
            LogLevel.DEBUG:   "🔍",
            LogLevel.INFO:    "ℹ",
            LogLevel.SUCCESS: "✔",
            LogLevel.WARNING: "⚠",
            LogLevel.ERROR:   "✖",
        }.get(entry.level, "•")

    # ── Slot runs on the main thread ──────────────────────────────────────────
    def _on_new_log(self, entry: LogEntry):
        self._all_entries.append(entry)
        if self._matches_filter(entry):
            pos = len(self._filtered_entries)
            self.beginInsertRows(QModelIndex(), pos, pos)
            self._filtered_entries.append(entry)
            self.endInsertRows()
            self.countChanged.emit()

    def _matches_filter(self, entry: LogEntry) -> bool:
        if self._filter_level != "ALL" and entry.level != self._filter_level:
            return False
        if self._search_query:
            q = self._search_query.lower()
            if q not in entry.message.lower() and q not in entry.category.lower():
                return False
        if self._status_only:
            # Hide individual file transfer and per-file logging, showing high-level status only
            msg = entry.message
            if entry.category in ("file", "chunk", "transfer"):
                return False
            if msg.startswith("Downloaded '") or msg.startswith("Skipped already downloaded") or msg.startswith("Skipped file '"):
                return False
            if "← https://" in msg or "← http://" in msg or "HTTP 200" in msg or "HTTP 206" in msg:
                return False
        return True

    @Slot(str)
    def setFilterLevel(self, level: str):
        self._filter_level = level.upper()
        self._reapply_filter()

    @Slot(str)
    def setSearchQuery(self, query: str):
        self._search_query = query.strip()
        self._reapply_filter()

    @Slot(bool)
    def setStatusOnly(self, enabled: bool):
        self._status_only = enabled
        self._reapply_filter()

    def _reapply_filter(self):
        self.beginResetModel()
        self._filtered_entries = [e for e in self._all_entries if self._matches_filter(e)]
        self.endResetModel()
        self.countChanged.emit()

    @Slot()
    def clearLogs(self):
        self.beginResetModel()
        self._all_entries.clear()
        self._filtered_entries.clear()
        self.endResetModel()
        self.countChanged.emit()

    def get_all_text(self) -> str:
        return "\n".join(
            f"[{e.timestamp}] [{e.level}] [{e.category}] {e.message}"
            for e in self._all_entries
        )
