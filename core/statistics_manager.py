"""
Statistics & Telemetry Manager
Tracks live and persistent lifetime network bandwidth (up/down), HTTP telemetry,
pipeline/engine counters, and deep on-disk / archive storage statistics.
"""

from collections import deque
import json
import os
import threading
import time
from typing import Any, Deque, Dict, Optional, Tuple

from core.atomic_io import atomic_write_json
from core.logger import logger
from core.path_utils import get_config_dir
from core.statistics_http_hook import (
    _EXT_CATEGORY_MAP,
    _FALLBACK_CATEGORIES,
    _HTTP_HOOK_INSTALLED,
    _HTTP_HOOK_LOCK,
    _build_body_length,
    _estimate_request_wire_bytes,
    _estimate_response_header_bytes,
    _get_ext_category_map,
    _normalize_path_key,
    _utc_now_iso,
    classify_ext,
    format_bytes,
    format_duration,
    format_speed,
    install_http_instrumentation,
)
from core.statistics_scanner import StatisticsScannerMixin, _CANCEL_POLL_INTERVAL

_STATISTICS_FILENAME = "statistics.json"
_STATISTICS_VERSION = 1
_RATE_WINDOW_SEC = 3.0
_PERSIST_DEBOUNCE_SEC = 5.0


class StatisticsManager(StatisticsScannerMixin):
    """
    Thread-safe telemetry aggregator and disk/archive analyzer.
    Combines live socket/HTTP I/O accounting with persisted lifetime counters and
    background filesystem + SQLite storage scans.
    """

    _LIFETIME_INT_KEYS = (
        "lifetime_down_bytes",
        "lifetime_up_bytes",
        "lifetime_down_media_bytes",
        "lifetime_down_api_bytes",
        "lifetime_http_requests",
        "lifetime_http_errors",
        "lifetime_http_429",
        "lifetime_files_completed",
        "lifetime_files_skipped",
        "lifetime_files_failed",
        "lifetime_retries",
        "lifetime_batches_completed",
        "lifetime_compressed_files",
        "lifetime_compressed_before_bytes",
        "lifetime_compressed_after_bytes",
        "lifetime_extracted_archives",
        "lifetime_extracted_files",
    )

    def __init__(self, config_dir: Optional[str] = None):
        self._lock = threading.RLock()
        self._explicit_config_dir = config_dir
        self._stats_path = os.path.join(get_config_dir(config_dir), _STATISTICS_FILENAME)

        now_mono = time.monotonic()
        self._session_start_mono = now_mono
        self._session_started_at = _utc_now_iso()

        # Rolling window samples for live up/down speed: (mono_ts, down_bytes, up_bytes)
        self._rate_samples: Deque[Tuple[float, int, int]] = deque()
        self._session_peak_down_bps: float = 0.0
        self._session_peak_up_bps: float = 0.0

        # Active download timing tracking
        self._active_download_running: bool = False
        self._active_download_since_mono: float = 0.0
        self._session_active_download_seconds: float = 0.0
        self._lifetime_active_download_seconds: float = 0.0

        # Session counters
        self._session: Dict[str, int] = {
            "down_bytes": 0,
            "up_bytes": 0,
            "down_media_bytes": 0,
            "down_api_bytes": 0,
            "http_requests": 0,
            "http_errors": 0,
            "http_429": 0,
            "files_completed": 0,
            "files_skipped": 0,
            "files_failed": 0,
            "retries": 0,
            "batches_completed": 0,
            "compressed_files": 0,
            "compressed_before_bytes": 0,
            "compressed_after_bytes": 0,
            "extracted_archives": 0,
            "extracted_files": 0,
        }

        # Persisted lifetime counters
        self._lifetime: Dict[str, Any] = {k: 0 for k in self._LIFETIME_INT_KEYS}
        self._lifetime["lifetime_peak_down_bps"] = 0.0
        self._lifetime["lifetime_peak_up_bps"] = 0.0
        self._lifetime["lifetime_active_download_seconds"] = 0.0
        self._lifetime["first_recorded_at"] = _utc_now_iso()
        self._lifetime["last_updated_at"] = ""

        self._dirty = False
        self._save_timer: Optional[threading.Timer] = None
        self._cached_storage_snapshot: Optional[Dict[str, Any]] = None

        self._load_persisted()

    def _resolve_stats_path(self) -> str:
        return os.path.join(get_config_dir(self._explicit_config_dir), _STATISTICS_FILENAME)

    def _load_persisted(self) -> None:
        path = self._resolve_stats_path()
        self._stats_path = path
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return
            with self._lock:
                for k in self._LIFETIME_INT_KEYS:
                    try:
                        self._lifetime[k] = max(0, int(raw.get(k, 0) or 0))
                    except (TypeError, ValueError):
                        pass
                self._lifetime["lifetime_peak_down_bps"] = max(
                    0.0, float(raw.get("lifetime_peak_down_bps", 0.0) or 0.0)
                )
                self._lifetime["lifetime_peak_up_bps"] = max(
                    0.0, float(raw.get("lifetime_peak_up_bps", 0.0) or 0.0)
                )
                self._lifetime_active_download_seconds = max(
                    0.0, float(raw.get("lifetime_active_download_seconds", 0.0) or 0.0)
                )
                self._lifetime["lifetime_active_download_seconds"] = self._lifetime_active_download_seconds
                first_at = str(raw.get("first_recorded_at") or "").strip()
                if first_at:
                    self._lifetime["first_recorded_at"] = first_at
                last_at = str(raw.get("last_updated_at") or "").strip()
                if last_at:
                    self._lifetime["last_updated_at"] = last_at
        except Exception as e:
            logger.debug(f"Could not read persisted statistics ({path}): {e}", category="system")

    def _schedule_save_locked(self) -> None:
        self._dirty = True
        if self._save_timer is not None:
            return
        timer = threading.Timer(_PERSIST_DEBOUNCE_SEC, self._save_worker)
        timer.daemon = True
        self._save_timer = timer
        timer.start()

    def _save_worker(self) -> None:
        with self._lock:
            self._save_timer = None
        self.flush()

    def flush(self) -> None:
        """Immediately persist any pending lifetime statistics to disk."""
        with self._lock:
            timer, self._save_timer = self._save_timer, None
            if timer is not None:
                try:
                    timer.cancel()
                except Exception:
                    pass
            # Roll any active download timer into persisted total before writing
            if self._active_download_running:
                now = time.monotonic()
                dt = max(0.0, now - self._active_download_since_mono)
                self._active_download_since_mono = now
                self._session_active_download_seconds += dt
                self._lifetime_active_download_seconds += dt
                self._dirty = True
            if not self._dirty and os.path.isfile(self._stats_path):
                return
            payload = dict(self._lifetime)
            payload["version"] = _STATISTICS_VERSION
            payload["lifetime_active_download_seconds"] = round(self._lifetime_active_download_seconds, 2)
            payload["last_updated_at"] = _utc_now_iso()
            self._lifetime["last_updated_at"] = payload["last_updated_at"]
            self._dirty = False
            path = self._resolve_stats_path()
            self._stats_path = path

        try:
            atomic_write_json(path, payload, indent=2)
        except Exception as e:
            logger.debug(f"Could not persist statistics: {e}", category="system")

    def _prune_samples_locked(self, now_mono: float) -> Tuple[float, float]:
        cutoff = now_mono - _RATE_WINDOW_SEC
        while self._rate_samples and self._rate_samples[0][0] < cutoff:
            self._rate_samples.popleft()
        if not self._rate_samples:
            return 0.0, 0.0
        sum_down = sum(s[1] for s in self._rate_samples)
        sum_up = sum(s[2] for s in self._rate_samples)
        # Divide over at least 1s so an initial burst doesn't spike artificially infinite speeds
        span = max(1.0, min(_RATE_WINDOW_SEC, now_mono - self._rate_samples[0][0] + 0.25))
        return sum_down / span, sum_up / span

    def _append_sample_locked(self, down_bytes: int, up_bytes: int) -> None:
        now = time.monotonic()
        if self._rate_samples and now - self._rate_samples[-1][0] < 0.15:
            ts, prev_d, prev_u = self._rate_samples[-1]
            self._rate_samples[-1] = (ts, prev_d + down_bytes, prev_u + up_bytes)
        else:
            self._rate_samples.append((now, down_bytes, up_bytes))
        live_down, live_up = self._prune_samples_locked(now)
        if live_down > self._session_peak_down_bps:
            self._session_peak_down_bps = live_down
        if live_up > self._session_peak_up_bps:
            self._session_peak_up_bps = live_up
        if live_down > self._lifetime["lifetime_peak_down_bps"]:
            self._lifetime["lifetime_peak_down_bps"] = live_down
        if live_up > self._lifetime["lifetime_peak_up_bps"]:
            self._lifetime["lifetime_peak_up_bps"] = live_up

    # ── Live Recording Hooks ─────────────────────────────────────────────────

    def set_download_active(self, active: bool) -> None:
        """Track active download duration (only counts wall time while downloads run)."""
        with self._lock:
            now = time.monotonic()
            if active and not self._active_download_running:
                self._active_download_running = True
                self._active_download_since_mono = now
            elif not active and self._active_download_running:
                dt = max(0.0, now - self._active_download_since_mono)
                self._active_download_running = False
                self._session_active_download_seconds += dt
                self._lifetime_active_download_seconds += dt
                self._schedule_save_locked()

    def record_download(self, num_bytes: int, category: str = "media") -> None:
        """Record received network bytes ('media' for streamed payloads, 'api' for metadata/HTTP)."""
        amount = int(num_bytes or 0)
        if amount <= 0:
            return
        with self._lock:
            self._session["down_bytes"] += amount
            self._lifetime["lifetime_down_bytes"] += amount
            if category == "api":
                self._session["down_api_bytes"] += amount
                self._lifetime["lifetime_down_api_bytes"] += amount
            else:
                self._session["down_media_bytes"] += amount
                self._lifetime["lifetime_down_media_bytes"] += amount
            self._append_sample_locked(amount, 0)
            self._schedule_save_locked()

    def record_upload(self, num_bytes: int) -> None:
        """Record transmitted network bytes (outgoing HTTP requests, headers, API payloads)."""
        amount = int(num_bytes or 0)
        if amount <= 0:
            return
        with self._lock:
            self._session["up_bytes"] += amount
            self._lifetime["lifetime_up_bytes"] += amount
            self._append_sample_locked(0, amount)
            self._schedule_save_locked()

    def record_http_request(self, status_code: int = 0) -> None:
        """Record an outgoing HTTP request and optional HTTP status code outcome."""
        code = int(status_code or 0)
        with self._lock:
            self._session["http_requests"] += 1
            self._lifetime["lifetime_http_requests"] += 1
            if code >= 400:
                self._session["http_errors"] += 1
                self._lifetime["lifetime_http_errors"] += 1
            if code == 429:
                self._session["http_429"] += 1
                self._lifetime["lifetime_http_429"] += 1
            self._schedule_save_locked()

    def record_file_result(self, outcome: str) -> None:
        """Record a task terminal outcome ('completed', 'skipped', or 'failed')."""
        clean = str(outcome or "").strip().lower()
        key_map = {
            "completed": ("files_completed", "lifetime_files_completed"),
            "skipped": ("files_skipped", "lifetime_files_skipped"),
            "failed": ("files_failed", "lifetime_files_failed"),
        }
        pair = key_map.get(clean)
        if not pair:
            return
        with self._lock:
            self._session[pair[0]] += 1
            self._lifetime[pair[1]] += 1
            self._schedule_save_locked()

    def record_retry(self) -> None:
        """Record a download retry attempt."""
        with self._lock:
            self._session["retries"] += 1
            self._lifetime["lifetime_retries"] += 1
            self._schedule_save_locked()

    def record_batch_completed(self) -> None:
        """Record completion of a download batch."""
        with self._lock:
            self._session["batches_completed"] += 1
            self._lifetime["lifetime_batches_completed"] += 1
            self._schedule_save_locked()

    def record_compression(self, before_bytes: int, after_bytes: int) -> None:
        """Record a media compression conversion that reduced file size."""
        before = max(0, int(before_bytes or 0))
        after = max(0, int(after_bytes or 0))
        if before <= 0:
            return
        with self._lock:
            self._session["compressed_files"] += 1
            self._session["compressed_before_bytes"] += before
            self._session["compressed_after_bytes"] += after
            self._lifetime["lifetime_compressed_files"] += 1
            self._lifetime["lifetime_compressed_before_bytes"] += before
            self._lifetime["lifetime_compressed_after_bytes"] += after
            self._schedule_save_locked()

    def record_extraction(self, extracted_files: int = 0) -> None:
        """Record an extracted archive and number of extracted entries."""
        files_n = max(0, int(extracted_files or 0))
        with self._lock:
            self._session["extracted_archives"] += 1
            self._session["extracted_files"] += files_n
            self._lifetime["lifetime_extracted_archives"] += 1
            self._lifetime["lifetime_extracted_files"] += files_n
            self._schedule_save_locked()

    def reset_network_counters(self) -> None:
        """Reset tracked session + lifetime network and engine counters (does not touch files)."""
        with self._lock:
            self._rate_samples.clear()
            self._session_peak_down_bps = 0.0
            self._session_peak_up_bps = 0.0
            self._session_active_download_seconds = 0.0
            self._lifetime_active_download_seconds = 0.0
            self._active_download_since_mono = time.monotonic()
            for k in list(self._session.keys()):
                self._session[k] = 0
            for k in self._LIFETIME_INT_KEYS:
                self._lifetime[k] = 0
            self._lifetime["lifetime_peak_down_bps"] = 0.0
            self._lifetime["lifetime_peak_up_bps"] = 0.0
            self._lifetime["lifetime_active_download_seconds"] = 0.0
            self._lifetime["first_recorded_at"] = _utc_now_iso()
            self._dirty = True
        self.flush()

    def get_live_snapshot(self) -> Dict[str, Any]:
        """Return a fast, thread-safe snapshot of live speeds, session totals, and lifetime totals."""
        with self._lock:
            now = time.monotonic()
            live_down_bps, live_up_bps = self._prune_samples_locked(now)
            active_delta = max(0.0, now - self._active_download_since_mono) if self._active_download_running else 0.0
            session_active_sec = self._session_active_download_seconds + active_delta
            lifetime_active_sec = self._lifetime_active_download_seconds + active_delta
            uptime_sec = max(0.0, now - self._session_start_mono)

            s_comp_saved = max(0, self._session["compressed_before_bytes"] - self._session["compressed_after_bytes"])
            l_comp_saved = max(
                0,
                int(self._lifetime["lifetime_compressed_before_bytes"])
                - int(self._lifetime["lifetime_compressed_after_bytes"]),
            )
            stats_path = self._resolve_stats_path()
            stats_size = os.path.getsize(stats_path) if os.path.isfile(stats_path) else 0

            return {
                "live_down_bps": live_down_bps,
                "live_up_bps": live_up_bps,
                "live_down_str": format_speed(live_down_bps),
                "live_up_str": format_speed(live_up_bps),
                "session_peak_down_bps": self._session_peak_down_bps,
                "session_peak_up_bps": self._session_peak_up_bps,
                "session_peak_down_str": format_speed(self._session_peak_down_bps),
                "session_peak_up_str": format_speed(self._session_peak_up_bps),
                "lifetime_peak_down_bps": float(self._lifetime["lifetime_peak_down_bps"]),
                "lifetime_peak_up_bps": float(self._lifetime["lifetime_peak_up_bps"]),
                "lifetime_peak_down_str": format_speed(float(self._lifetime["lifetime_peak_down_bps"])),
                "lifetime_peak_up_str": format_speed(float(self._lifetime["lifetime_peak_up_bps"])),
                "session_down_bytes": self._session["down_bytes"],
                "session_up_bytes": self._session["up_bytes"],
                "session_down_str": format_bytes(self._session["down_bytes"]),
                "session_up_str": format_bytes(self._session["up_bytes"]),
                "session_down_media_bytes": self._session["down_media_bytes"],
                "session_down_api_bytes": self._session["down_api_bytes"],
                "session_down_media_str": format_bytes(self._session["down_media_bytes"]),
                "session_down_api_str": format_bytes(self._session["down_api_bytes"]),
                "session_http_requests": self._session["http_requests"],
                "session_http_errors": self._session["http_errors"],
                "session_http_429": self._session["http_429"],
                "session_files_completed": self._session["files_completed"],
                "session_files_skipped": self._session["files_skipped"],
                "session_files_failed": self._session["files_failed"],
                "session_retries": self._session["retries"],
                "session_batches_completed": self._session["batches_completed"],
                "session_compressed_files": self._session["compressed_files"],
                "session_compressed_saved_bytes": s_comp_saved,
                "session_compressed_saved_str": format_bytes(s_comp_saved),
                "session_extracted_archives": self._session["extracted_archives"],
                "session_extracted_files": self._session["extracted_files"],
                "session_uptime_seconds": uptime_sec,
                "session_uptime_str": format_duration(uptime_sec),
                "session_active_download_seconds": session_active_sec,
                "session_active_download_str": format_duration(session_active_sec),
                "session_started_at": self._session_started_at,
                "lifetime_down_bytes": int(self._lifetime["lifetime_down_bytes"]),
                "lifetime_up_bytes": int(self._lifetime["lifetime_up_bytes"]),
                "lifetime_down_str": format_bytes(int(self._lifetime["lifetime_down_bytes"])),
                "lifetime_up_str": format_bytes(int(self._lifetime["lifetime_up_bytes"])),
                "lifetime_down_media_bytes": int(self._lifetime["lifetime_down_media_bytes"]),
                "lifetime_down_api_bytes": int(self._lifetime["lifetime_down_api_bytes"]),
                "lifetime_down_media_str": format_bytes(int(self._lifetime["lifetime_down_media_bytes"])),
                "lifetime_down_api_str": format_bytes(int(self._lifetime["lifetime_down_api_bytes"])),
                "lifetime_http_requests": int(self._lifetime["lifetime_http_requests"]),
                "lifetime_http_errors": int(self._lifetime["lifetime_http_errors"]),
                "lifetime_http_429": int(self._lifetime["lifetime_http_429"]),
                "lifetime_files_completed": int(self._lifetime["lifetime_files_completed"]),
                "lifetime_files_skipped": int(self._lifetime["lifetime_files_skipped"]),
                "lifetime_files_failed": int(self._lifetime["lifetime_files_failed"]),
                "lifetime_retries": int(self._lifetime["lifetime_retries"]),
                "lifetime_batches_completed": int(self._lifetime["lifetime_batches_completed"]),
                "lifetime_compressed_files": int(self._lifetime["lifetime_compressed_files"]),
                "lifetime_compressed_before_bytes": int(self._lifetime["lifetime_compressed_before_bytes"]),
                "lifetime_compressed_after_bytes": int(self._lifetime["lifetime_compressed_after_bytes"]),
                "lifetime_compressed_saved_bytes": l_comp_saved,
                "lifetime_compressed_saved_str": format_bytes(l_comp_saved),
                "lifetime_extracted_archives": int(self._lifetime["lifetime_extracted_archives"]),
                "lifetime_extracted_files": int(self._lifetime["lifetime_extracted_files"]),
                "lifetime_active_download_seconds": lifetime_active_sec,
                "lifetime_active_download_str": format_duration(lifetime_active_sec),
                "first_recorded_at": self._lifetime["first_recorded_at"],
                "last_updated_at": self._lifetime["last_updated_at"] or _utc_now_iso(),
                "stats_file_bytes": stats_size,
                "stats_file_str": format_bytes(stats_size),
            }

    def get_cached_storage_snapshot(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._cached_storage_snapshot) if self._cached_storage_snapshot else None

    # ── Deep Disk, Archive & Database Scanner ────────────────────────────────



# Global shared singleton instance
statistics_manager = StatisticsManager()
install_http_instrumentation(statistics_manager)
