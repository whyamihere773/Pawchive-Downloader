"""
Watchlist Qt Model
Exposes the WatchlistManager's entries as a QAbstractListModel so QML
ListView and Repeater can bind to them reactively.

Built for big watchlists (100k creators): the counts are worked out once per rebuild, each cell read
returns only the field asked for, big lists are filtered and sorted in the background, a rebuild that
keeps the order updates the rows in place (no reset: the list keeps its scroll position), and one
creator's check result updates just its row.
"""

import threading
from operator import itemgetter

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot, Property, QThread, QTimer


def _file_count(p: dict) -> int:
    f = p.get("file")
    n = 1 if (f and isinstance(f, dict) and (f.get("path") or f.get("storageKey"))) else 0
    return n + len([a for a in (p.get("attachments") or []) if isinstance(a, dict) and (a.get("path") or a.get("storageKey"))])


def _posts_for_qml(e) -> list:
    return [
        {
            "id": str(p.get("id", "")),
            "title": (p.get("title") or "Untitled").strip(),
            "published": str(p.get("published") or p.get("added") or "")[:10],
            "fileCount": _file_count(p),
        }
        for p in getattr(e, "cached_new_posts", None) or []
    ]


def _download_dirs(e) -> list:
    d_dirs = list(getattr(e, "download_dirs", []) or [])
    if e.download_dir and e.download_dir not in d_dirs:
        d_dirs.insert(0, e.download_dir)
    return d_dirs


class WatchlistModel(QAbstractListModel):
    # Custom roles
    UrlRole          = Qt.UserRole + 1
    CreatorNameRole  = Qt.UserRole + 2
    ServiceRole      = Qt.UserRole + 3
    DomainRole       = Qt.UserRole + 4
    UserIdRole       = Qt.UserRole + 5
    LastPostDateRole = Qt.UserRole + 6
    LastPostIdRole   = Qt.UserRole + 7
    AddedAtRole      = Qt.UserRole + 8
    AutoCheckRole    = Qt.UserRole + 9
    NewPostCountRole = Qt.UserRole + 10
    DownloadDirRole  = Qt.UserRole + 11
    IgnoredCountRole = Qt.UserRole + 12
    CachedPostsRole  = Qt.UserRole + 13
    DownloadDirsRole = Qt.UserRole + 14

    # Above this many creators the list is filtered and sorted in the background
    BACKGROUND_REBUILD_AT = 20000

    _ROLE_GETTERS = {
        UrlRole:          lambda e: e.url,
        CreatorNameRole:  lambda e: e.creator_name,
        ServiceRole:      lambda e: e.service,
        DomainRole:       lambda e: e.domain,
        UserIdRole:       lambda e: e.user_id,
        LastPostDateRole: lambda e: e.last_post_date,
        LastPostIdRole:   lambda e: e.last_post_id,
        AddedAtRole:      lambda e: e.added_at,
        AutoCheckRole:    lambda e: e.auto_check,
        NewPostCountRole: lambda e: e.new_post_count,
        DownloadDirRole:  lambda e: e.download_dir,
        DownloadDirsRole: _download_dirs,
        IgnoredCountRole: lambda e: len(getattr(e, "ignored_post_ids", None) or []),
        CachedPostsRole:  _posts_for_qml,
        Qt.DisplayRole:   lambda e: e.creator_name,
    }

    countChanged = Signal()
    _refreshRequested = Signal()
    _flushRequested = Signal()
    _rebuilt = Signal(int, object)

    FLUSH_BATCH = 500        # changed creators applied per event-loop turn

    def __init__(self, watchlist_manager, parent=None):
        super().__init__(parent)
        self._refreshRequested.connect(self.refresh, Qt.QueuedConnection)
        self._flushRequested.connect(self._flush_changes, Qt.QueuedConnection)
        self._pending_changes = {}           # id(entry) -> entry, waiting for _flush_changes
        self._pending_lock = threading.Lock()
        self._flush_scheduled = False
        self._rebuilt.connect(self._apply_rebuild, Qt.QueuedConnection)
        self._manager = watchlist_manager
        self._search_text: str = ""
        self._service_filter: str = "all"
        self._display_entries = []
        self._row_of = {}                    # id(entry) -> row
        self._n_of = {}                      # id(entry) -> new post count when last counted
        self._total = 0
        self._updated = 0
        self._new_posts = 0
        self._gen = 0
        self._rebuilding = False
        self._again = False
        self._count_timer = QTimer(self)
        self._count_timer.setSingleShot(True)
        self._count_timer.setInterval(200)
        self._count_timer.timeout.connect(self.countChanged.emit)
        self._apply(self._compute(self._snapshot()), reset=False)

    # ── Building the list ──────────────────────────────────────────────────────

    def _snapshot(self):
        lock = getattr(self._manager, "_lock", None)
        if lock is not None:
            with lock:
                return list(self._manager.entries), self._search_text, self._service_filter
        return list(self._manager.entries), self._search_text, self._service_filter

    @staticmethod
    def _compute(snapshot):
        """
        Filters and sorts entries:
        1. Filters by search_text (creator_name or user_id)
        2. Filters by service_filter ("all", "updates", or specific service)
        3. Creators with new_post_count > 0 at the top, sorted alphabetically by creator name.
        4. Remaining creators below, sorted alphabetically by creator name.
        """
        entries, search_text, service_filter = snapshot
        st = (search_text or "").strip().lower()
        sf = (service_filter or "all").strip().lower()
        updated = new_posts = 0
        n_of = {}
        keyed = []
        for e in entries:
            n = getattr(e, "new_post_count", 0) or 0
            n_of[id(e)] = n
            if n > 0:
                updated += 1
                new_posts += n
            name = getattr(e, "creator_name", "") or ""
            uid = getattr(e, "user_id", "") or ""
            if st and st not in name.lower() and st not in uid.lower():
                continue
            if sf == "updates":
                if n <= 0:
                    continue
            elif sf and sf != "all" and (getattr(e, "service", "") or "").lower() != sf:
                continue
            keyed.append((0 if n > 0 else 1, (name or uid).lower(), e))
        keyed.sort(key=itemgetter(0, 1))
        display = [k[2] for k in keyed]
        return display, n_of, (len(entries), updated, new_posts)

    def _apply(self, built, reset=True):
        display, n_of, (total, updated, new_posts) = built
        old = self._display_entries
        same_rows = len(old) == len(display) and all(a is b for a, b in zip(old, display))
        if reset and not same_rows:
            self.beginResetModel()
        self._display_entries = display
        self._row_of = {id(e): i for i, e in enumerate(display)}
        self._n_of = n_of
        self._total, self._updated, self._new_posts = total, updated, new_posts
        if reset:
            if same_rows:
                if display:      # same creators in the same order: refresh the rows in place
                    self.dataChanged.emit(self.index(0, 0), self.index(len(display) - 1, 0))
            else:
                self.endResetModel()
            self.countChanged.emit()

    @Slot(int, object)
    def _apply_rebuild(self, gen, built):
        self._rebuilding = False
        if gen == self._gen:
            self._apply(built)
        if self._again:
            self._again = False
            self.refresh()

    @Slot(str, str)
    def setFilter(self, search_text: str, service_filter: str):
        """Live search & category filter update from QML."""
        self._search_text = search_text or ""
        self._service_filter = (service_filter or "all").lower()
        self.refresh()

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._display_entries)

    @Property(int, notify=countChanged)
    def totalCount(self) -> int:
        """Total unfiltered count of tracked artists."""
        return self._total

    @Property(int, notify=countChanged)
    def updatedCount(self) -> int:
        """Number of tracked artists that have new posts found since last download."""
        return self._updated

    @Property(int, notify=countChanged)
    def totalNewPosts(self) -> int:
        """Total count of new posts across all tracked artists."""
        return self._new_posts

    @Slot(int, result="QVariantMap")
    def get(self, index: int) -> dict:
        if 0 <= index < len(self._display_entries):
            e = self._display_entries[index]
            return {
                "url": e.url,
                "creatorName": e.creator_name,
                "service": e.service,
                "domain": e.domain,
                "userId": e.user_id,
                "lastPostDate": e.last_post_date,
                "lastPostId": e.last_post_id,
                "addedAt": e.added_at,
                "autoCheck": e.auto_check,
                "newPostCount": e.new_post_count,
                "downloadDir": e.download_dir,
                "downloadDirs": _download_dirs(e),
                "ignoredCount": len(getattr(e, "ignored_post_ids", None) or []),
                "cachedNewPosts": _posts_for_qml(e),
            }
        return {}

    # ── QAbstractListModel interface ───────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._display_entries)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._display_entries):
            return None
        getter = self._ROLE_GETTERS.get(role)
        return getter(self._display_entries[index.row()]) if getter else None

    def roleNames(self):
        return {
            self.UrlRole:          b"url",
            self.CreatorNameRole:  b"creatorName",
            self.ServiceRole:      b"service",
            self.DomainRole:       b"domain",
            self.UserIdRole:       b"userId",
            self.LastPostDateRole: b"lastPostDate",
            self.LastPostIdRole:   b"lastPostId",
            self.AddedAtRole:      b"addedAt",
            self.AutoCheckRole:    b"autoCheck",
            self.NewPostCountRole: b"newPostCount",
            self.DownloadDirRole:  b"downloadDir",
            self.DownloadDirsRole: b"downloadDirs",
            self.IgnoredCountRole: b"ignoredCount",
            self.CachedPostsRole:  b"cachedNewPosts",
            Qt.DisplayRole:        b"display",
        }

    # ── Refresh helpers ────────────────────────────────────────────────────────

    @Slot()
    def refresh(self):
        """Rebuilds the filtered, sorted list (in the background for big watchlists).

        Watchlist checks and downloads call this from background threads; changing a model outside
        the GUI thread can crash the app, so those calls are passed to the GUI thread.
        """
        if QThread.currentThread() is not self.thread():
            self._refreshRequested.emit()
            return
        if self._rebuilding:
            self._again = True            # once the running rebuild is in
            return
        snapshot = self._snapshot()
        self._gen += 1
        if len(snapshot[0]) < self.BACKGROUND_REBUILD_AT:
            self._apply(self._compute(snapshot))
            return
        self._rebuilding = True
        gen = self._gen

        def _work():
            try:
                built = self._compute(snapshot)
            except Exception:
                built = None
            if built is None:
                built = (list(self._display_entries), dict(self._n_of), (self._total, self._updated, self._new_posts))
            self._rebuilt.emit(gen, built)
        threading.Thread(target=_work, name="WatchlistRebuild", daemon=True).start()

    def update_new_counts(self):
        """Re-sort and refresh when new counts are updated."""
        self.refresh()

    def entry_changed(self, entry):
        """One creator changed (e.g. its check finished): its row and the counts are updated without
        rebuilding the list; its place in the order is updated by the next refresh(). Can be called
        from any thread. Changes are collected and applied in batches: a check of a big watchlist
        reports thousands of creators a second, and one queued call per creator piled up into
        long pauses of the window."""
        with self._pending_lock:
            self._pending_changes[id(entry)] = entry
            if self._flush_scheduled:
                return
            self._flush_scheduled = True
        self._flushRequested.emit()

    @Slot()
    def _flush_changes(self):
        with self._pending_lock:
            keys = list(self._pending_changes)[:self.FLUSH_BATCH]
            batch = [self._pending_changes.pop(k) for k in keys]
            more = bool(self._pending_changes)
            if not more:
                self._flush_scheduled = False
        lo = hi = None
        counts_changed = False
        n_display = len(self._display_entries)
        for entry in batch:
            key = id(entry)
            if key in self._n_of:
                old = self._n_of[key]
                new = getattr(entry, "new_post_count", 0) or 0
                if old != new:
                    self._n_of[key] = new
                    self._updated += (new > 0) - (old > 0)
                    self._new_posts += max(new, 0) - max(old, 0)
                    counts_changed = True
            row = self._row_of.get(key)
            if row is not None and row < n_display and self._display_entries[row] is entry:
                lo = row if lo is None else min(lo, row)
                hi = row if hi is None else max(hi, row)
        if lo is not None:
            self.dataChanged.emit(self.index(lo, 0), self.index(hi, 0))
        if counts_changed and not self._count_timer.isActive():
            self._count_timer.start()
        if more:
            self._flushRequested.emit()     # the rest on the next turn: other events go first
