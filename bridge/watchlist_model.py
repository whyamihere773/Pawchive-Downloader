"""
Watchlist Qt Model
Exposes the WatchlistManager's entries as a QAbstractListModel so QML
ListView and Repeater can bind to them reactively.
"""

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot, Property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.watchlist_manager import WatchlistManager


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

    countChanged = Signal()

    def __init__(self, watchlist_manager, parent=None):
        super().__init__(parent)
        self._manager = watchlist_manager
        self._search_text: str = ""
        self._service_filter: str = "all"
        self._display_entries = []
        self._rebuild_display_entries()

    def _rebuild_display_entries(self):
        """
        Filters and sorts entries:
        1. Filters by search_text (creator_name or user_id)
        2. Filters by service_filter ("all", "updates", or specific service)
        3. Creators with new_post_count > 0 at the top, sorted alphabetically by creator name.
        4. Remaining creators below, sorted alphabetically by creator name.
        """
        entries = list(self._manager.entries)

        # Apply search filter
        if self._search_text:
            st = self._search_text.strip().lower()
            entries = [
                e for e in entries
                if st in (getattr(e, "creator_name", "") or "").lower()
                or st in (getattr(e, "user_id", "") or "").lower()
            ]

        # Apply category / service filter
        if self._service_filter == "updates":
            entries = [e for e in entries if (getattr(e, "new_post_count", 0) or 0) > 0]
        elif self._service_filter and self._service_filter != "all":
            sf = self._service_filter.strip().lower()
            entries = [e for e in entries if (getattr(e, "service", "") or "").lower() == sf]

        self._display_entries = sorted(
            entries,
            key=lambda e: (
                0 if (getattr(e, "new_post_count", 0) or 0) > 0 else 1,
                (getattr(e, "creator_name", "") or getattr(e, "user_id", "") or "").lower()
            )
        )

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
        return len(self._manager.entries)

    @Property(int, notify=countChanged)
    def updatedCount(self) -> int:
        """Number of tracked artists that have new posts found since last download."""
        return sum(1 for e in self._manager.entries if (getattr(e, "new_post_count", 0) or 0) > 0)

    @Property(int, notify=countChanged)
    def totalNewPosts(self) -> int:
        """Total count of new posts across all tracked artists."""
        return sum((getattr(e, "new_post_count", 0) or 0) for e in self._manager.entries if (getattr(e, "new_post_count", 0) or 0) > 0)

    @Slot(int, result="QVariantMap")
    def get(self, index: int) -> dict:
        if 0 <= index < len(self._display_entries):
            e = self._display_entries[index]
            d_dirs = list(getattr(e, "download_dirs", []) or [])
            if e.download_dir and e.download_dir not in d_dirs:
                d_dirs.insert(0, e.download_dir)
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
                "downloadDirs": d_dirs,
                "ignoredCount": len(getattr(e, "ignored_post_ids", [])),
                "cachedNewPosts": [
                    {
                        "id": str(p.get("id", "")),
                        "title": (p.get("title") or "Untitled").strip(),
                        "published": str(p.get("published") or p.get("added") or "")[:10],
                        "fileCount": (1 if (p.get("file") and isinstance(p.get("file"), dict) and (p.get("file").get("path") or p.get("file").get("storageKey"))) else 0) + len([a for a in (p.get("attachments") or []) if isinstance(a, dict) and (a.get("path") or a.get("storageKey"))]),
                    }
                    for p in getattr(e, "cached_new_posts", [])
                ],
            }
        return {}

    # ── QAbstractListModel interface ───────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._display_entries)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._display_entries):
            return None
        entry = self._display_entries[index.row()]
        d_dirs = list(getattr(entry, "download_dirs", []) or [])
        if entry.download_dir and entry.download_dir not in d_dirs:
            d_dirs.insert(0, entry.download_dir)
        return {
            self.UrlRole:          entry.url,
            self.CreatorNameRole:  entry.creator_name,
            self.ServiceRole:      entry.service,
            self.DomainRole:       entry.domain,
            self.UserIdRole:       entry.user_id,
            self.LastPostDateRole: entry.last_post_date,
            self.LastPostIdRole:   entry.last_post_id,
            self.AddedAtRole:      entry.added_at,
            self.AutoCheckRole:    entry.auto_check,
            self.NewPostCountRole: entry.new_post_count,
            self.DownloadDirRole:  entry.download_dir,
            self.DownloadDirsRole: d_dirs,
            self.IgnoredCountRole: len(getattr(entry, "ignored_post_ids", [])),
            self.CachedPostsRole:  [
                {
                    "id": str(p.get("id", "")),
                    "title": (p.get("title") or "Untitled").strip(),
                    "published": str(p.get("published") or p.get("added") or "")[:10],
                    "fileCount": (1 if (p.get("file") and isinstance(p.get("file"), dict) and (p.get("file").get("path") or p.get("file").get("storageKey"))) else 0) + len([a for a in (p.get("attachments") or []) if isinstance(a, dict) and (a.get("path") or a.get("storageKey"))]),
                }
                for p in getattr(entry, "cached_new_posts", [])
            ],
            Qt.DisplayRole:        entry.creator_name,
        }.get(role)

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
        """Full model reset — rebuilds sorted display list and notifies QML."""
        self.beginResetModel()
        self._rebuild_display_entries()
        self.endResetModel()
        self.countChanged.emit()

    def update_new_counts(self):
        """Re-sort and refresh when new counts are updated."""
        self.refresh()

