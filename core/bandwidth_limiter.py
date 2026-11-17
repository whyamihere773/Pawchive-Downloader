"""
Global Bandwidth Limiter / Download Speed Throttle
Enforces process-wide download speed limits across all worker threads, multipart connections,
and external downloaders.
"""

import time
import threading
from typing import Optional

from core.statistics_manager import statistics_manager


class BandwidthLimiter:
    """
    Global Token-Bucket / Virtual-Clock Bandwidth Limiter.
    Paces downloaded bytes across any number of concurrent threads to guarantee
    aggregate throughput never exceeds the specified speed limit.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._enabled: bool = False
        self._rate_value: float = 10.0
        self._rate_unit: str = "MB/s"  # "MB/s" or "mbps"
        self._bytes_per_sec: float = 0.0
        self._next_allowed_time: float = time.monotonic()

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def rate_value(self) -> float:
        with self._lock:
            return self._rate_value

    @property
    def rate_unit(self) -> str:
        with self._lock:
            return self._rate_unit

    @property
    def bytes_per_sec(self) -> float:
        with self._lock:
            return self._bytes_per_sec if self._enabled else 0.0

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled and self._bytes_per_sec > 0

    def get_rate_bps(self) -> float:
        with self._lock:
            return self._bytes_per_sec if self._enabled else 0.0

    @staticmethod
    def calculate_bytes_per_sec(value: float, unit: str) -> float:
        """
        Converts a numeric value and unit ("MB/s" or "mbps") to bytes per second.
        - MB/s: Binary megabytes per second (1024 * 1024 bytes/sec = 1,048,576 B/s)
        - mbps / Mbps: Decimal megabits per second (1,000,000 / 8 bytes/sec = 125,000 B/s)
        """
        try:
            val = float(value)
        except (ValueError, TypeError):
            val = 0.0
        if val <= 0:
            return 0.0

        u = str(unit or "").strip().lower()
        if "mbps" in u or "mbit" in u or (u == "mb/s" and False):
            # Megabits per second (network standard)
            return (val * 1_000_000.0) / 8.0
        else:
            # Megabytes per second (binary 1024*1024)
            return val * 1024.0 * 1024.0

    def update(self, enabled: bool, value: float, unit: str) -> None:
        """
        Updates the bandwidth limit settings. Thread-safe and takes effect immediately.
        """
        with self._lock:
            self._enabled = bool(enabled)
            try:
                self._rate_value = max(0.1, float(value))
            except (ValueError, TypeError):
                self._rate_value = 10.0

            u_clean = str(unit or "").strip()
            if "mbps" in u_clean.lower() or "mbit" in u_clean.lower():
                self._rate_unit = "mbps"
            else:
                self._rate_unit = "MB/s"

            if self._enabled and self._rate_value > 0:
                self._bytes_per_sec = self.calculate_bytes_per_sec(self._rate_value, self._rate_unit)
            else:
                self._bytes_per_sec = 0.0

            # Reset virtual clock to current time so old backlog or setting changes don't stall new downloads
            self._next_allowed_time = time.monotonic()

    def get_summary(self) -> str:
        """
        Returns a friendly formatted string of the current limit,
        including equivalent conversion (e.g. '10.0 MB/s (≈ 83.9 Mbps)').
        """
        with self._lock:
            if not self._enabled or self._bytes_per_sec <= 0:
                return "Unlimited"
            if self._rate_unit == "mbps":
                mb_s = self._bytes_per_sec / (1024.0 * 1024.0)
                return f"{self._rate_value:.1f} Mbps (≈ {mb_s:.2f} MB/s)"
            else:
                mbps = (self._bytes_per_sec * 8.0) / 1_000_000.0
                return f"{self._rate_value:.1f} MB/s (≈ {mbps:.1f} Mbps)"

    def wait_for(
        self,
        num_bytes: int,
        cancel_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None
    ) -> bool:
        """
        Paces data transfer. Call this when `num_bytes` have been received.
        If aggregate bandwidth exceeds the limit, sleeps the calling thread just enough
        to maintain the target rate across all threads.

        Returns:
            True if allowed to proceed.
            False if cancelled.
        """
        if num_bytes <= 0:
            return True

        statistics_manager.record_download(num_bytes, category="media")

        with self._lock:
            if not self._enabled or self._bytes_per_sec <= 0:
                return True

            rate = self._bytes_per_sec
            now = time.monotonic()

            # Bound burst allowance: max 0.05 seconds of data (or 32KB)
            # This ensures that when starting or after an idle period, speed never spikes above the cap.
            burst_seconds = min(0.05, max(0.01, 32768.0 / rate))
            earliest_start = now - burst_seconds
            start_time = max(self._next_allowed_time, earliest_start)

            duration = num_bytes / rate
            target_time = start_time + duration

            # Bound queue horizon to 3.0 seconds into the future
            if target_time - now > 3.0:
                target_time = now + 3.0

            self._next_allowed_time = target_time

        sleep_needed = target_time - time.monotonic()
        if sleep_needed <= 0.001:
            return True

        deadline = time.monotonic() + sleep_needed
        while True:
            if cancel_event and cancel_event.is_set():
                return False

            if pause_event and pause_event.is_set():
                while pause_event and pause_event.is_set():
                    if cancel_event and cancel_event.is_set():
                        return False
                    time.sleep(0.1)
                # After pausing, reset schedule so resuming doesn't burst
                with self._lock:
                    self._next_allowed_time = time.monotonic()
                return True

            rem = deadline - time.monotonic()
            if rem <= 0.001:
                break

            step = min(rem, 0.05)
            if cancel_event:
                if cancel_event.wait(timeout=step):
                    return False
            else:
                time.sleep(step)

        return True


# Global shared singleton instance
bandwidth_limiter = BandwidthLimiter()
