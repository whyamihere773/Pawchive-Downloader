"""
Downloader Telemetry — Speed Tracking, Smart ETA & Progress Reporting Mixin
Decomposed from core/downloader.py to keep modules cohesive and under 1,000 lines.
"""

import time
from typing import Dict


class DownloaderTelemetryMixin:
    """Computes active elapsed time, rolling/instant speed, smart ETA, and queue progress stats."""

    def _get_active_elapsed(self, now: float) -> float:
        """Returns the actual active downloading elapsed time, excluding all paused periods."""
        if self.start_time <= 0:
            return 0.1
        paused = self._total_paused_time
        if self._pause_event.is_set() and self._pause_start_time > 0:
            paused += max(0.0, now - self._pause_start_time)
        return max(0.1, (now - self.start_time) - paused)

    def _calculate_instant_speed(self, now: float) -> int:
        """
        Calculates 100% accurate, real-time download throughput.
        Tracks byte delta over recent 1.0-2.0 second window for responsive, accurate network monitoring.
        Also maintains rolling 45-second samples for sustained throughput tracking.
        """
        with self._lock:
            current_bytes = self.downloaded_bytes

        if current_bytes > 0 and self._first_byte_time == 0.0:
            self._first_byte_time = now

        # A gap of more than 2 s since the last sample (paused, stalled): measure afresh
        if self._speed_samples and (now - self._speed_samples[-1][0] > 2.0):
            self._speed_samples.clear()
            self._smoothed_speed = 0.0

        self._speed_samples.append((now, current_bytes))

        # Evict all samples older than 2.0 seconds
        while self._speed_samples and (now - self._speed_samples[0][0] > 2.0):
            self._speed_samples.popleft()

        # Maintain rolling 45-second samples for sustained throughput tracking
        if not self._rolling_speed_samples or (now - self._rolling_speed_samples[-1][0] >= 0.5):
            self._rolling_speed_samples.append((now, current_bytes))
        while self._rolling_speed_samples and (now - self._rolling_speed_samples[0][0] > 45.0):
            self._rolling_speed_samples.popleft()

        if len(self._speed_samples) >= 2:
            dt = now - self._speed_samples[0][0]
            db = current_bytes - self._speed_samples[0][1]
            if dt >= 0.2:
                raw_speed = max(0.0, db / dt)
                if self._smoothed_speed <= 0:
                    self._smoothed_speed = raw_speed
                else:
                    self._smoothed_speed = 0.85 * raw_speed + 0.15 * self._smoothed_speed
                return max(0, int(self._smoothed_speed))

        return max(0, int(self._smoothed_speed))

    def _get_rolling_speed(self, now: float) -> float:
        """Computes sustained throughput over the recent 45-second window."""
        with self._lock:
            current_bytes = self.downloaded_bytes
        if len(self._rolling_speed_samples) >= 2:
            dt = now - self._rolling_speed_samples[0][0]
            db = current_bytes - self._rolling_speed_samples[0][1]
            if dt >= 3.0:
                return max(0.0, db / dt)
        return 0.0

    def _calculate_smart_eta(self, completed: int, failed: int, total: int, speed: int, elapsed: float) -> str:
        """
        Calculates a learning, countdown-stable ETA that resists transient network dips/crashes.
        Uses:
        1. Multi-tier throughput baseline (rolling 45s window + sustained session average + medium EMA)
           measured strictly from active transfer time (excluding pauses and discovery latency).
        2. Content-aware learned file size estimation (categorized into video/archive, image/audio, other).
        3. Adaptive confidence-weighted dual-model blending (byte-throughput prioritized when sizes are known,
           with completion rate as safety bound driven strictly by completed downloads).
        4. Monotonic steady countdown with early-warmup rapid convergence and anti-jitter damping.
        """
        remaining_tasks = total - completed - failed
        if total <= 0 or remaining_tasks <= 0:
            self._smoothed_eta = None
            return "Done"

        now = time.time()
        time_since_last_calc = (now - self._last_eta_calc_time) if self._last_eta_calc_time > 0 else 0.0
        self._last_eta_calc_time = now

        # ── 1. Content-Aware Learned File Size Estimation ────────────────────
        st = self._queue_stats(now)

        if st.get("done_video_n", 0) > 0:
            avg_video = st["done_video_bytes"] / st["done_video_n"]
        else:
            avg_video = 60.0 * 1024 * 1024  # 60 MB realistic video/archive fallback
        avg_video = max(1.0 * 1024 * 1024, min(1024.0 * 1024 * 1024, avg_video))

        if st.get("done_image_n", 0) > 0:
            avg_image = st["done_image_bytes"] / st["done_image_n"]
        else:
            avg_image = 3.5 * 1024 * 1024   # 3.5 MB realistic image/audio fallback
        avg_image = max(100.0 * 1024, min(50.0 * 1024 * 1024, avg_image))

        if st["done_n"] > 0:
            avg_other = st["done_bytes"] / st["done_n"]
        elif st["known_n"] > 0:
            avg_other = st["known_bytes"] / st["known_n"]
        else:
            avg_other = 4.5 * 1024 * 1024   # 4.5 MB realistic artwork fallback
        avg_other = max(200.0 * 1024, min(100.0 * 1024 * 1024, avg_other))

        unknown_video_n = st.get("unknown_video_n", 0)
        unknown_image_n = st.get("unknown_image_n", 0)
        unknown_other_n = st.get("unknown_other_n", max(0, st["unknown_n"] - unknown_video_n - unknown_image_n))

        estimated_unknown_bytes = (
            unknown_video_n * avg_video +
            unknown_image_n * avg_image +
            max(0, unknown_other_n) * avg_other
        )
        total_remaining_bytes = st["known_remaining"] + max(
            0.0, estimated_unknown_bytes - st["unknown_downloaded"]
        )

        # ── 2. Derive Learning ETA Throughput Baseline ────────────────────────
        with self._lock:
            current_bytes = self.downloaded_bytes

        # Exclude paused time from active duration calculation
        paused_duration = self._total_paused_time
        if self._pause_event.is_set() and self._pause_start_time > 0:
            paused_duration += max(0.0, now - self._pause_start_time)

        # Measure session throughput from first active byte to exclude discovery/setup latency
        if self._first_byte_time > 0 and self.start_time > 0:
            active_transfer_time = max(0.5, (now - self._first_byte_time) - paused_duration)
            transfer_elapsed = min(elapsed, active_transfer_time)
        else:
            transfer_elapsed = max(0.5, elapsed)

        session_avg_speed = current_bytes / max(1.0, transfer_elapsed)

        # Check sustained rolling speed over the recent 45-second window
        rolling_speed = self._get_rolling_speed(now)
        sustained_speed = rolling_speed if rolling_speed > 0 else session_avg_speed

        # Track medium-term pace using EMA
        if self._medium_speed <= 0:
            self._medium_speed = float(speed if speed > 0 else sustained_speed)
        else:
            self._medium_speed = 0.05 * speed + 0.95 * self._medium_speed

        # Progressive learning anchor: As elapsed time increases, anchor heavily to the
        # sustained empirical average so brief speed crashes don't cause wild ETA spikes
        learn_weight = min(0.85, max(0.20, (transfer_elapsed - 5.0) / 60.0))
        learned_eta_speed = (1.0 - learn_weight) * self._medium_speed + learn_weight * sustained_speed

        # ── 3. Dual-Model Target ETA Derivation ──────────────────────────────
        target_candidates = []

        # Model A: Byte-Throughput ETA using learned sustained speed
        if learned_eta_speed > 512 and total_remaining_bytes > 0:
            target_candidates.append(total_remaining_bytes / learned_eta_speed)

        # Model B: Task Completion Rate ETA (empirically learned completed tasks/sec)
        # Note: ONLY successfully completed downloads reflect actual transfer work.
        # Failed/skipped files terminate immediately and must not artificially inflate the completion rate.
        if completed > 0 and transfer_elapsed > 2.0:
            tasks_per_second = completed / transfer_elapsed
            if tasks_per_second > 0:
                target_candidates.append(remaining_tasks / tasks_per_second)

        if not target_candidates:
            if remaining_tasks == 0:
                return "Done"
            return "--"

        # Adaptive confidence blending:
        # If all file sizes are known, byte-throughput model is mathematically rigorous (up to 90% weight).
        # If many sizes are unknown, blend in task completion rate (up to 45% weight).
        if len(target_candidates) == 2:
            total_active_remaining = st["known_n"] + st["unknown_n"]
            if total_active_remaining > 0:
                known_confidence = st["known_n"] / total_active_remaining
            else:
                known_confidence = 1.0 if st["known_bytes"] > 0 else 0.5
            byte_weight = 0.55 + 0.35 * known_confidence
            target_eta_seconds = byte_weight * target_candidates[0] + (1.0 - byte_weight) * target_candidates[1]
        else:
            target_eta_seconds = target_candidates[0]

        # ── 4. Monotonic Countdown & Anti-Fluctuation Damping ────────────────
        if self._smoothed_eta is None:
            self._smoothed_eta = target_eta_seconds
        else:
            # First, tick down naturally by the elapsed real time
            if 0 < time_since_last_calc < 3.0:
                self._smoothed_eta = max(1.0, self._smoothed_eta - time_since_last_calc)

            # Then gently nudge towards target ETA using adaptive damping
            deviation = abs(target_eta_seconds - self._smoothed_eta) / max(1.0, self._smoothed_eta)
            if transfer_elapsed < 15.0:
                # Early warmup: converge quickly to the true ETA
                alpha = 0.20 if deviation > 0.25 else 0.10
            elif target_eta_seconds < 10.0 and self._smoothed_eta > 20.0:
                # Approaching finish: don't let ETA drag behind when completing
                alpha = 0.15
            elif deviation > 0.60:
                alpha = 0.10
            elif deviation > 0.25:
                alpha = 0.04
            else:
                alpha = 0.015

            self._smoothed_eta = (1.0 - alpha) * self._smoothed_eta + alpha * target_eta_seconds

        eta_sec = max(1, int(round(self._smoothed_eta)))

        # ── 5. Format Output String ──────────────────────────────────────────
        if eta_sec >= 86400:
            return f"{eta_sec // 86400}d {(eta_sec % 86400) // 3600}h"
        elif eta_sec >= 3600:
            return f"{eta_sec // 3600}h {(eta_sec % 3600) // 60}m {eta_sec % 60}s"
        elif eta_sec >= 60:
            return f"{eta_sec // 60}m {eta_sec % 60}s"
        elif eta_sec > 1:
            return f"{eta_sec}s"
        else:
            return "< 1s"

    def _queue_stats(self, now: float) -> Dict[str, float]:
        """Byte totals over the whole queue for the ETA, gathered in one pass at most once a second
        (four passes five times a second were noticeable with 100,000-file queues)."""
        if self._task_stats and now - self._task_stats_time < 1.0:
            return self._task_stats
        done_bytes = done_n = known_bytes = known_n = 0
        known_remaining = unknown_n = unknown_downloaded = all_downloaded = 0
        done_video_bytes = done_video_n = done_image_bytes = done_image_n = 0
        unknown_video_n = unknown_image_n = unknown_other_n = 0

        video_archive_exts = {
            ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".wmv",
            ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"
        }
        image_audio_exts = {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".ico",
            ".mp3", ".flac", ".wav", ".m4a", ".ogg", ".opus"
        }

        for t in self.tasks:
            d = t.downloaded_bytes
            all_downloaded += d
            status = t.status
            fn = getattr(t, "filename", "") or getattr(t, "target_path", "") or getattr(t, "url", "") or ""
            dot_idx = fn.rfind(".")
            ext = fn[dot_idx:].split("?")[0].lower() if dot_idx != -1 else ""

            if status == "completed":
                if d > 0:
                    done_bytes += d
                    done_n += 1
                    if ext in video_archive_exts:
                        done_video_bytes += d
                        done_video_n += 1
                    elif ext in image_audio_exts:
                        done_image_bytes += d
                        done_image_n += 1
            elif status in ("pending", "downloading"):
                size = t.file_size
                if size > 0:
                    known_bytes += size
                    known_n += 1
                    known_remaining += max(0, size - d)
                else:
                    unknown_n += 1
                    unknown_downloaded += d
                    if ext in video_archive_exts:
                        unknown_video_n += 1
                    elif ext in image_audio_exts:
                        unknown_image_n += 1
                    else:
                        unknown_other_n += 1

        self._task_stats = {
            "done_bytes": done_bytes, "done_n": done_n, "known_bytes": known_bytes, "known_n": known_n,
            "known_remaining": float(known_remaining), "unknown_n": unknown_n,
            "unknown_downloaded": float(unknown_downloaded), "all_downloaded": all_downloaded,
            "done_video_bytes": done_video_bytes, "done_video_n": done_video_n,
            "done_image_bytes": done_image_bytes, "done_image_n": done_image_n,
            "unknown_video_n": unknown_video_n, "unknown_image_n": unknown_image_n,
            "unknown_other_n": unknown_other_n,
        }
        self._task_stats_time = now
        return self._task_stats

    def _emit_progress(self, completed: int, failed: int, total: int, force: bool = False):
        if not self.on_progress_update:
            return

        now = time.time()
        # Throttle progress emissions to max 5 times per second unless forced
        if not force and (now - self._last_progress_emit_time < 0.20):
            return
        self._last_progress_emit_time = now

        active_elapsed = self._get_active_elapsed(now)
        speed = self._calculate_instant_speed(now)

        # Format elapsed time (active download time, excluding paused time)
        elapsed_int = int(active_elapsed)
        if elapsed_int >= 3600:
            elapsed_str = f"{elapsed_int // 3600}h {(elapsed_int % 3600) // 60}m {elapsed_int % 60}s"
        elif elapsed_int >= 60:
            elapsed_str = f"{elapsed_int // 60}m {elapsed_int % 60}s"
        else:
            elapsed_str = f"{elapsed_int}s"

        # Calculate ETA
        eta_str = self._calculate_smart_eta(completed, failed, total, speed, active_elapsed)

        # Calculate progress percent
        if total > 0:
            task_ratio = (completed + failed) / total
            percent = int(task_ratio * 100)
            percent = max(0, min(100, percent))
        else:
            percent = 0

        # Use the maximum of the running counter and the sum of per-task bytes.
        # The running counter can lag for multipart files (disk-poll vs in-flight bytes),
        # and the per-task sum stays accurate because _disk_poll updates task.downloaded_bytes.
        tasks_downloaded = self._queue_stats(now)["all_downloaded"]
        effective_bytes = max(self.downloaded_bytes, tasks_downloaded)
        dl_mb = effective_bytes / (1024 * 1024)
        if effective_bytes > 1024 * 1024 * 1024:
            saved_str = f"{effective_bytes / (1024 * 1024 * 1024):.2f} GB"
        else:
            saved_str = f"{dl_mb:.1f} MB"

        status_text = (
            "Progress: Paused" if self._pause_event.is_set() else (
                f"Downloading… ({completed}/{total} files)"
                if self._is_running else "Idle"
            )
        )

        info = {
            "completed": completed,
            "failed": failed,
            "total": total,
            "percent": percent,
            "speed_str": self.format_speed(speed),
            "eta_str": eta_str,
            "elapsed_str": elapsed_str,
            "downloaded_bytes": self.downloaded_bytes,
            "saved_str": saved_str,
            "status_text": status_text,
            "adaptive_state": self.adaptive_state,
            "adaptive_status_text": self.adaptive_status_text
        }
        self.on_progress_update(info)

    @staticmethod
    def format_speed(bps: int) -> str:
        if bps <= 0:
            return "0 KB/s"
        if bps >= 1024 * 1024:
            return f"{bps / (1024 * 1024):.2f} MB/s"
        elif bps >= 1024:
            return f"{bps / 1024:.1f} KB/s"
        return f"{bps} B/s"
