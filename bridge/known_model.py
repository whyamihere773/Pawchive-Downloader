"""
Known Characters & Series List Model
Provides an observable list model with search filtering for the Known Series tab.
"""

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot, QThread
from typing import List
from core.known_manager import KnownManager


class KnownModel(QAbstractListModel):
    NameRole = Qt.UserRole + 1

    countChanged = Signal()
    _guiCall = Signal(object)

    def __init__(self, known_manager: KnownManager, parent=None):
        super().__init__(parent)
        self._guiCall.connect(self._run_gui_call, Qt.QueuedConnection)
        self.known_manager = known_manager
        self.known_manager.on_entries_changed = self.refresh
        self._filtered_entries: List[str] = list(self.known_manager.entries)
        self._search_query: str = ""

    def rowCount(self, parent=QModelIndex()):
        return len(self._filtered_entries)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._filtered_entries):
            return None

        name = self._filtered_entries[index.row()]
        if role == self.NameRole or role == Qt.DisplayRole:
            return name
        return None

    def roleNames(self):
        return {
            self.NameRole: b"name",
            Qt.DisplayRole: b"display"
        }

    @Slot(str)
    def setSearchQuery(self, query: str):
        self._search_query = query.strip()
        self.refresh()

    @Slot(str)
    def addEntry(self, name: str) -> bool:
        success = self.known_manager.add_entry(name)
        if success:
            self.refresh()
        return success

    @Slot(int)
    def removeIndex(self, index: int) -> bool:
        if 0 <= index < len(self._filtered_entries):
            name = self._filtered_entries[index]
            success = self.known_manager.remove_entry(name)
            if success:
                self.refresh()
            return success
        return False

    @Slot(object)
    def _run_gui_call(self, fn):
        fn()

    def _off_gui_thread(self, fn) -> bool:
        """Models may only change on the GUI thread (a reset from a worker thread can crash the
        app). Called from another thread, fn is queued for the GUI thread and True is returned."""
        if QThread.currentThread() is not self.thread():
            self._guiCall.emit(fn)
            return True
        return False

    @Slot()
    def refresh(self):
        if self._off_gui_thread(self.refresh):
            return
        self.beginResetModel()
        self._filtered_entries = self.known_manager.search(self._search_query)
        self.endResetModel()
        self.countChanged.emit()
