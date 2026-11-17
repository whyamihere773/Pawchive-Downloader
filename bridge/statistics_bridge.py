"""
QML Bridge for the Statistics & Raw Telemetry View (`StatisticsBridge`).
Exposes live network bandwidth (up/down), persistent lifetime counters, and
asynchronous disk/archive/database storage breakdowns to `qml/views/StatisticsView.qml`.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Property, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog

from core.statistics_manager import (
    StatisticsManager,
    format_bytes,
    statistics_manager,
)


def _empty_storage_snapshot() -> Dict[str, Any]:
    return {
        "scanned_at": "",
        "scan_duration_ms": 0,
        "cancelled": False,
        "total_artists": 0,
        "disk_total_files": 0,
        "disk_total_folders": 0,
        "disk_artist_folders": 0,
        "disk_total_bytes": 0,
        "disk_total_str": "0 B",
        "disk_part_files": 0,
        "disk_part_bytes": 0,
        "disk_part_str": "0 B",
        "archive_files": 0,
        "archive_creators": 0,
        "archive_posts": 0,
        "archive_verified_files": 0,
        "archive_missing_files": 0,
        "archive_unverified_files": 0,
        "archive_recorded_bytes": 0,
        "archive_recorded_str": "0 B",
        "archive_db_bytes": 0,
        "archive_db_str": "0 B",
        "history_sessions": 0,
        "history_files": 0,
        "history_db_bytes": 0,
        "history_db_str": "0 B",
        "watchlist_creators": 0,
        "storage_roots_count": 0,
        "drives": [],
        "categories": [],
        "extensions": [],
        "services": [],
        "artists": [],
    }


class StatisticsBridge(QObject):
    """QML bridge connecting `StatisticsManager` telemetry to `StatisticsView.qml`."""

    liveStatsChanged = Signal()
    storageStatsChanged = Signal()
    isScanningChanged = Signal()
    artistsFilterChanged = Signal()
    toastRequested = Signal(str, str)
    _scanCompletedInternal = Signal(int, object)

    def __init__(
        self,
        app_bridge: Any = None,
        stats_manager: Optional[StatisticsManager] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._app_bridge = app_bridge
        self._stats_manager = stats_manager or statistics_manager
        self._storage_snapshot: Dict[str, Any] = (
            self._stats_manager.get_cached_storage_snapshot() or _empty_storage_snapshot()
        )
        self._has_scanned = bool(self._storage_snapshot.get("scanned_at"))
        self._is_scanning = False
        self._scan_gen = 0
        self._scan_cancel_event: Optional[threading.Event] = None
        self._scan_lock = threading.Lock()

        self._artist_search = ""
        self._artist_service_filter = "all"
        self._artist_sort_by = "size_desc"

        self._scanCompletedInternal.connect(self._on_scan_completed, Qt.ConnectionType.QueuedConnection)

    # ── Live Telemetry ───────────────────────────────────────────────────────

    @Property("QVariantMap", notify=liveStatsChanged)
    def liveSnapshot(self) -> Dict[str, Any]:
        return self._stats_manager.get_live_snapshot()

    @Slot()
    def refreshLive(self) -> None:
        self.liveStatsChanged.emit()

    # ── Disk & Database Storage Snapshot ─────────────────────────────────────

    @Property("QVariantMap", notify=storageStatsChanged)
    def storageSnapshot(self) -> Dict[str, Any]:
        return dict(self._storage_snapshot)

    @Property(bool, notify=isScanningChanged)
    def isScanning(self) -> bool:
        return self._is_scanning

    @Property(bool, notify=storageStatsChanged)
    def hasScanned(self) -> bool:
        return self._has_scanned

    @Slot()
    @Slot(bool)
    def refreshStorage(self, force: bool = True) -> None:
        """Start an asynchronous disk, archive, and database scan (non-blocking)."""
        if not force and self._has_scanned and not self._is_scanning:
            self.storageStatsChanged.emit()
            self.artistsFilterChanged.emit()
            return

        with self._scan_lock:
            if self._scan_cancel_event is not None:
                self._scan_cancel_event.set()
            self._scan_gen += 1
            gen = self._scan_gen
            cancel_ev = threading.Event()
            self._scan_cancel_event = cancel_ev
            if not self._is_scanning:
                self._is_scanning = True
                self.isScanningChanged.emit()

        primary_dir, overflow_dirs, library_roots, archive_mgr, history_store, watchlist_mgr = (
            self._collect_dependencies()
        )

        def _worker() -> None:
            try:
                snap = self._stats_manager.collect_full_snapshot(
                    primary_dir=primary_dir,
                    overflow_dirs=overflow_dirs,
                    local_library_roots=library_roots,
                    archive_manager=archive_mgr,
                    history_store=history_store,
                    watchlist_manager=watchlist_mgr,
                    cancel_event=cancel_ev,
                )
            except Exception:
                snap = _empty_storage_snapshot()
            self._scanCompletedInternal.emit(gen, snap)

        t = threading.Thread(target=_worker, name=f"StatsDiskScan-{gen}", daemon=True)
        t.start()

    def _collect_dependencies(self):
        ab = self._app_bridge
        primary_dir = str(getattr(ab, "_download_dir", "") or "") if ab else ""
        library_roots = list(getattr(ab, "_local_library_roots", []) or []) if ab else []
        archive_mgr = getattr(ab, "archive_manager", None) if ab else None
        session_mgr = getattr(ab, "session_manager", None) if ab else None
        history_store = getattr(session_mgr, "history_store", None) if session_mgr else None
        watchlist_mgr = getattr(ab, "_watchlist_manager", None) if ab else None
        overflow_dirs: List[str] = []
        try:
            from core.storage_pool_manager import storage_pool_manager
            if not primary_dir:
                primary_dir = str(getattr(storage_pool_manager, "primary_dir", "") or "")
            if storage_pool_manager.enabled and storage_pool_manager.overflow_dirs:
                overflow_dirs = list(storage_pool_manager.overflow_dirs)
        except Exception:
            pass
        return primary_dir, overflow_dirs, library_roots, archive_mgr, history_store, watchlist_mgr

    @Slot(int, object)
    def _on_scan_completed(self, gen: int, snap: Any) -> None:
        with self._scan_lock:
            if gen != self._scan_gen:
                return
            self._is_scanning = False
        self.isScanningChanged.emit()
        if isinstance(snap, dict) and not snap.get("cancelled"):
            self._storage_snapshot = snap
            self._has_scanned = True
            self.storageStatsChanged.emit()
            self.artistsFilterChanged.emit()

    # ── Artists Table Search, Service Filter & Sort ──────────────────────────

    @Property(str, notify=artistsFilterChanged)
    def artistSearch(self) -> str:
        return self._artist_search

    @artistSearch.setter
    def artistSearch(self, value: str) -> None:
        clean = str(value or "")
        if clean != self._artist_search:
            self._artist_search = clean
            self.artistsFilterChanged.emit()

    @Property(str, notify=artistsFilterChanged)
    def artistServiceFilter(self) -> str:
        return self._artist_service_filter

    @artistServiceFilter.setter
    def artistServiceFilter(self, value: str) -> None:
        clean = str(value or "all").strip().lower() or "all"
        if clean != self._artist_service_filter:
            self._artist_service_filter = clean
            self.artistsFilterChanged.emit()

    @Property(str, notify=artistsFilterChanged)
    def artistSortBy(self) -> str:
        return self._artist_sort_by

    @artistSortBy.setter
    def artistSortBy(self, value: str) -> None:
        clean = str(value or "size_desc").strip() or "size_desc"
        if clean != self._artist_sort_by:
            self._artist_sort_by = clean
            self.artistsFilterChanged.emit()

    @Property("QVariantList", notify=storageStatsChanged)
    def availableServices(self) -> List[Dict[str, str]]:
        opts = [{"text": "All Services", "value": "all"}]
        for s in self._storage_snapshot.get("services") or []:
            svc = str(s.get("service") or "").strip()
            if svc:
                opts.append({"text": svc, "value": svc.lower()})
        return opts

    @Property("QVariantList", notify=artistsFilterChanged)
    def filteredArtists(self) -> List[Dict[str, Any]]:
        rows = list(self._storage_snapshot.get("artists") or [])
        q = self._artist_search.strip().lower()
        svc_filter = self._artist_service_filter

        if svc_filter and svc_filter != "all":
            rows = [r for r in rows if str(r.get("service") or "").lower() == svc_filter]
        if q:
            rows = [
                r for r in rows
                if q in str(r.get("artist_name") or "").lower()
                or q in str(r.get("service") or "").lower()
                or q in str(r.get("creator_id") or "").lower()
                or q in str(r.get("drives") or "").lower()
            ]

        sort_key = self._artist_sort_by
        if sort_key == "files_desc":
            rows.sort(key=lambda r: (int(r.get("files") or 0), int(r.get("size_bytes") or 0)), reverse=True)
        elif sort_key == "folders_desc":
            rows.sort(key=lambda r: (int(r.get("folders") or 0), int(r.get("files") or 0)), reverse=True)
        elif sort_key == "posts_desc":
            rows.sort(key=lambda r: (int(r.get("posts") or 0), int(r.get("files") or 0)), reverse=True)
        elif sort_key == "name_asc":
            rows.sort(key=lambda r: str(r.get("artist_name") or "").lower())
        else:  # size_desc
            rows.sort(key=lambda r: (int(r.get("size_bytes") or 0), int(r.get("files") or 0)), reverse=True)
        return rows

    # ── Utility Actions ──────────────────────────────────────────────────────

    @Slot(result=bool)
    def resetNetworkStats(self) -> bool:
        """Reset tracked session and lifetime network/engine counters."""
        self._stats_manager.reset_network_counters()
        self.liveStatsChanged.emit()
        self.toastRequested.emit("Network & session telemetry counters reset.", "info")
        return True

    @Slot(str)
    def openFolder(self, folder_path: str) -> None:
        clean = str(folder_path or "").strip()
        if clean and os.path.isdir(clean):
            QDesktopServices.openUrl(QUrl.fromLocalFile(clean))

    @Slot(str, result=bool)
    def exportReport(self, format_type: str = "json") -> bool:
        """Prompt user to save a raw JSON or CSV telemetry report."""
        fmt = "csv" if str(format_type or "").strip().lower() == "csv" else "json"
        default_name = f"pawchive_statistics.{fmt}"
        filter_str = "CSV Table (*.csv)" if fmt == "csv" else "JSON Report (*.json)"
        target_path, _ = QFileDialog.getSaveFileName(None, "Export Statistics Report", default_name, filter_str)
        if not target_path:
            return False
        payload = {
            "live_and_lifetime": self._stats_manager.get_live_snapshot(),
            **self._storage_snapshot,
        }
        ok = self._stats_manager.export_report(target_path, payload)
        if ok:
            self.toastRequested.emit(f"Exported statistics report to {os.path.basename(target_path)}", "success")
        else:
            self.toastRequested.emit("Failed to export statistics report.", "error")
        return ok

    @Slot(result=bool)
    def copyRawSummary(self) -> bool:
        """Copy a plain-text raw telemetry summary to the system clipboard."""
        live = self._stats_manager.get_live_snapshot()
        st = self._storage_snapshot
        lines = [
            "Pawchive Downloader — Raw Statistics",
            f"Bandwidth Down (Session / Lifetime): {live['session_down_str']} ({live['session_down_bytes']:,} B) / {live['lifetime_down_str']} ({live['lifetime_down_bytes']:,} B)",
            f"Bandwidth Up (Session / Lifetime):   {live['session_up_str']} ({live['session_up_bytes']:,} B) / {live['lifetime_up_str']} ({live['lifetime_up_bytes']:,} B)",
            f"Live Speed Down / Up:                {live['live_down_str']} / {live['live_up_str']}",
            f"Peak Speed Down / Up (Lifetime):     {live['lifetime_peak_down_str']} / {live['lifetime_peak_up_str']}",
            f"Downloaded Artists:                  {st.get('total_artists', 0):,}",
            f"Disk Files / Folders:                {st.get('disk_total_files', 0):,} files / {st.get('disk_total_folders', 0):,} folders ({st.get('disk_artist_folders', 0):,} artist roots)",
            f"Disk Total Size:                     {st.get('disk_total_str', '0 B')} ({st.get('disk_total_bytes', 0):,} B)",
            f"Archive DB Records / Posts:          {st.get('archive_files', 0):,} files / {st.get('archive_posts', 0):,} posts ({st.get('archive_db_str', '0 B')})",
            f"Compression Saved (Lifetime):        {live['lifetime_compressed_saved_str']} ({live['lifetime_compressed_files']:,} files)",
            f"HTTP Requests / Errors / 429s:       {live['lifetime_http_requests']:,} / {live['lifetime_http_errors']:,} / {live['lifetime_http_429']:,}",
        ]
        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.setText("\n".join(lines))
            self.toastRequested.emit("Copied raw statistics summary to clipboard.", "success")
            return True
        return False

    @Slot("qulonglong", result=str)
    @Slot(float, result=str)
    def formatBytes(self, num_bytes: Any) -> str:
        try:
            return format_bytes(int(num_bytes or 0))
        except Exception:
            return "0 B"
