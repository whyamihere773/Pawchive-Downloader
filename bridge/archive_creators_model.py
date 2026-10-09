"""
Long lists of records (dicts) for QML, as list models: the Archive tab's creators and the Link Vault's.

They used to be JavaScript arrays of every creator, converted on the window thread at each refresh
(a few hundred ms at 20,000 creators, seconds at 100,000; the Link Vault's came as one big JSON text,
post texts included). Here the list stays in Python and a card reads its own record when it's built
("modelData", the model's only role).
"""

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Property, Signal, Slot


class RecordListModel(QAbstractListModel):
    RecordRole = Qt.UserRole + 1
    CreatorRole = RecordRole

    countChanged = Signal()

    def __init__(self, parent=None, key_field: str = "key"):
        super().__init__(parent)
        self._key_field = key_field
        self._creators = []
        self._row_of_key = {}
        self._pending = None
        self._pending_keys = None

    def _keys(self, records) -> list:
        k = self._key_field
        return [r.get(k) for r in records]

    def set_creators(self, creators) -> None:
        creators = list(creators or [])
        if creators and len(creators) == len(self._creators) and self._keys(creators) == self._keys(self._creators):
            # Same records in the same order (a refresh): the rows that changed are updated in place;
            # a reset of a long list made the window wait
            old, self._creators = self._creators, creators
            changed = [i for i, (a, b) in enumerate(zip(old, creators)) if a != b]
            # (one signal per run of neighbouring rows: a signal for every row of a long list kept
            # the window busy even when nothing had changed)
            start = prev = None
            for i in changed + [None]:
                if start is not None and (i is None or i != prev + 1):
                    self.dataChanged.emit(self.index(start, 0), self.index(prev, 0))
                    start = None
                if i is not None and start is None:
                    start = i
                prev = i
            return
        self.beginResetModel()
        self._creators = creators
        self._row_of_key = {k: i for i, k in enumerate(self._keys(creators))}
        self.endResetModel()
        self.countChanged.emit()

    def set_pending(self, creators) -> None:
        """A new list read in the background; the view shows it with applyPending() (it keeps its
        scroll position around that)."""
        self._pending = list(creators or [])
        self._pending_keys = set(self._keys(self._pending))

    @Slot()
    def applyPending(self) -> None:
        if self._pending is not None:
            creators, self._pending, self._pending_keys = self._pending, None, None
            self.set_creators(creators)

    @Slot(str, result=bool)
    def pendingHasKey(self, key: str) -> bool:
        """The list about to be shown has this record (or the current one, without a new list)."""
        keys = self._pending_keys if self._pending_keys is not None else self._row_of_key
        return key in keys

    # ── QAbstractListModel ─────────────────────────────────────────────────────
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._creators)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._creators):
            return None
        if role in (self.RecordRole, Qt.DisplayRole):
            return self._creators[index.row()]
        return None

    def roleNames(self):
        return {self.RecordRole: b"creator"}       # the only role: cards read it as modelData

    # ── For the view ───────────────────────────────────────────────────────────
    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._creators)

    @Slot(int, result="QVariantMap")
    def get(self, row: int) -> dict:
        return self._creators[row] if 0 <= row < len(self._creators) else {}

    @Slot(str, result=bool)
    def hasKey(self, key: str) -> bool:
        return key in self._row_of_key

    @Slot(result="QVariantMap")
    def allNamesMap(self) -> dict:
        """{creator name: true} for every creator in the list ("Expand All"; with a list waiting to
        be shown: that one)."""
        src = self._pending if self._pending is not None else self._creators
        return {c.get("creator_name", ""): True for c in src}

    @Slot("QVariantMap", result=bool)
    def allIn(self, names) -> bool:
        """Every creator in the list is in `names` (an {name: true} map)."""
        if not self._creators or not names or len(names) < len(self._creators):
            return False
        return all(names.get(c.get("creator_name", "")) for c in self._creators)


class ArchiveCreatorsModel(RecordListModel):
    """The Archive tab's creators (records keyed by "key")."""
