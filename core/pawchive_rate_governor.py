"""
Two-Layer Ban-Averse Rate Governor & Persistent Calibration Engine for Pawchive (`*.pawchive.pw`).

Combines:
1. Master domain-wide `*.pawchive.pw` IP pacing (10s burst + 60s RPM + 5m sustained rolling window)
   to prevent shared Cloudflare / front-proxy IP rate-limit penalties.
2. Per-shard (`n1`-`n4`, `t1`-`t4`, `file`) speedometers & concurrency caps to prevent overloading
   an individual storage server when a creator's posts live on a single node.
3. Domain-wide quiet cooldowns on any 429 (all Pawchive nodes pause together so shared IP timeout
   timers drain cleanly on the first cooldown instead of cascading across n1 -> n4 -> n2).
4. Anti-crawl recovery & self-healing ceilings: practical minimum RPM floor, 15-file/75s recovery
   verification (eliminating 1-file amnesia), smooth upward probing, and automatic decay of stale
   danger ceilings so temporary hiccups never trap downloads at crawling speeds.
5. Ban-Shield circuit breaker: auto-pauses the queue after 3 consecutive failed post-cooldown probes
   to protect the user's IP from automated bans.
6. Cross-session persistence (`pawchive_rate_profile.json`) + user presets (`smart`, `cautious`, `manual`)
   and 1-click `recalibrate()`.
"""

from __future__ import annotations

from collections import deque
import math
import random
import re
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from core.logger import logger
from core.pawchive_rate_persistence import (
    PawchiveRatePersistenceMixin,
    RATE_GUARD_MODES,
    normalize_rate_guard_mode,
)

_STORAGE_HOST_RE = re.compile(r"^(?:file|[nt]\d+)\.pawchive\.pw$", re.IGNORECASE)


def slow_probe_ts_needed(slow_probe_mode: bool) -> bool:
    return bool(slow_probe_mode)


class PawchiveRateGovernor(PawchiveRatePersistenceMixin):
    """Thread-safe two-layer congestion controller and persistent rate calibrator for `*.pawchive.pw`."""

    # Preset parameters: fast enough to never feel sluggish, conservative enough to avoid 429s
    _PRESETS: Dict[str, Dict[str, float]] = {
        "smart": {
            "start_rpm": 26.0,       # ~1,560 files/hr baseline
            "floor_rpm": 12.0,       # normal Cruise floor (1 file / 5s) when hourly quota is healthy
            "quota_floor_rpm": 4.0,  # steady Quota Cruise floor unlocked only when hourly refill tightens
            "max_rpm": 30.0,         # ~1,800 files/hr max auto-probe (tapers automatically over 60m)
            "safety_ratio": 0.85,    # settle comfortably at 85% of confirmed 429 ceiling
            "start_streams": 3.0,    # starts balanced at 3 simultaneous connections
            "min_streams": 2.0,      # normal Cruise floor (drops to 1 in Quota Cruise < 10 RPM)
            "max_streams": 5.0,      # dynamically opens up to 5 Pawchive connections when clean
            "base_cd": 20.0,         # short 20s first-bump cooldown
        },
        "cautious": {
            "start_rpm": 18.0,       # ~1,080 files/hr baseline
            "floor_rpm": 9.0,        # 1 file / 6.6s normal floor
            "quota_floor_rpm": 4.0,  # steady Quota Cruise floor under sustained hourly throttling
            "max_rpm": 24.0,
            "safety_ratio": 0.75,    # extra 25% safety headroom below any 429 ceiling
            "start_streams": 2.0,
            "min_streams": 1.0,
            "max_streams": 2.0,
            "base_cd": 30.0,
        },
    }

    def __init__(
        self,
        persist_path: Optional[str] = None,
        mode: str = "smart",
        manual_rpm: float = 24.0,
        manual_max_streams: int = 3,
        manual_cooldown_s: int = 40,
        on_state_changed: Optional[Callable[[], None]] = None,
    ):
        self._lock = threading.RLock()
        self._persist_path = str(persist_path or "").strip() or None
        self._on_state_changed = on_state_changed

        self._mode: str = normalize_rate_guard_mode(mode)
        self._manual_rpm: float = max(8.0, min(60.0, float(manual_rpm or 24.0)))
        self._manual_max_streams: int = max(1, min(6, int(manual_max_streams or 3)))
        self._manual_cooldown_s: int = max(15, min(180, int(manual_cooldown_s or 40)))

        # Learned / adaptive state (RPM + dynamic concurrent connection count)
        preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
        self._target_global_rpm: float = preset["start_rpm"]
        self._danger_global_rpm: Optional[float] = None
        self._target_streams: int = int(preset["start_streams"])
        self._danger_streams: Optional[int] = None
        self._hot_node_until: Dict[str, float] = {}
        self._last_429_wall_ts: float = 0.0
        self._node_rpm: Dict[str, float] = {}
        self._node_last_429_ts: Dict[str, float] = {}

        # Runtime state machine: "cruise" | "cooldown" | "probing" | "recovering" | "paused_shield"
        self._state: str = "cruise"
        self._quota_cruise_active: bool = False
        self._domain_cooldown_until: float = 0.0
        self._cooldown_id: int = 0
        self._probe_claimed_id: int = 0
        self._wave: int = 0
        self._wave_ts_60m: deque = deque()               # timestamps of 429 waves over last 3600s
        self._consecutive_failed_probes: int = 0
        self._recovery_started_at: float = 0.0
        self._recovery_clean_files: int = 0
        self._cruise_clean_files: int = 0
        self._self_heal_clean_files: int = 0
        self._last_probe_up_ts: float = 0.0

        # O(1) sliding-window telemetry (1m live RPM, 5m burst/sustained, 60m rolling hourly self-pacing)
        self._global_sent_1m: deque = deque()
        self._global_sent_5m: deque = deque()
        self._global_sent_60m: deque = deque()
        self._global_sent_ts: deque = self._global_sent_5m
        self._sent_1m_weight: float = 0.0
        self._sent_5m_weight: float = 0.0
        self._sent_60m_weight: float = 0.0
        self._node_sent_ts: Dict[str, deque] = {}        # host -> deque[timestamp] over last 120s
        self._global_sched_ts: deque = deque()           # scheduled storage slots over last 60s
        self._node_sched_ts: Dict[str, deque] = {}       # scheduled per-node slots over last 60s
        self._global_next_slot: float = 0.0
        self._node_next_slot: Dict[str, float] = {}
        self._node_slow_ttfb_until: Dict[str, float] = {}

        self._last_save_ts: float = 0.0
        self._save_pending: bool = False

        if self._persist_path:
            self._load_from_disk()

    # ── Core Calculations ─────────────────────────────────────────────────────

    def _hourly_budget_cap_unlocked(self) -> Tuple[float, int]:
        """Smoothly taper Smart Auto ceiling over rolling 60m volume so marathon queues glide
        underneath Pawchive's ~2,200–2,500 req/hr threshold before hitting a wall."""
        preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
        if self._mode != "smart":
            return preset["max_rpm"], int(preset["max_streams"])
        s60 = self._sent_60m_weight
        if s60 < 1400.0:
            return preset["max_rpm"], int(preset["max_streams"])
        if s60 < 1800.0:
            frac = (s60 - 1400.0) / 400.0
            return preset["max_rpm"] - 8.0 * frac, 4
        frac = min(1.0, (s60 - 1800.0) / 350.0)
        return 22.0 - 6.0 * frac, 3

    def _wave_counts_unlocked(self, now: float) -> Tuple[int, int]:
        cutoff_60m = now - 3600.0
        while self._wave_ts_60m and self._wave_ts_60m[0] <= cutoff_60m:
            self._wave_ts_60m.popleft()
        cutoff_5m = now - 300.0
        w5 = sum(1 for t in self._wave_ts_60m if t > cutoff_5m)
        return w5, len(self._wave_ts_60m)

    def _clamp_target_unlocked(self) -> None:
        preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
        floor_rpm = preset["quota_floor_rpm"] if self._quota_cruise_active else preset["floor_rpm"]
        hr_rpm, _ = self._hourly_budget_cap_unlocked()
        ceil_rpm = min(preset["max_rpm"], hr_rpm)
        if self._danger_global_rpm is not None:
            ceil_rpm = min(ceil_rpm, max(preset["floor_rpm"], self._danger_global_rpm * preset["safety_ratio"]))
        self._target_global_rpm = max(floor_rpm, min(ceil_rpm, self._target_global_rpm))

    def _clamp_streams_unlocked(self) -> None:
        preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
        low_quota = self._quota_cruise_active and self._target_global_rpm < 10.5
        min_s = 1 if low_quota else int(preset["min_streams"])
        _, hr_s = self._hourly_budget_cap_unlocked()
        max_s = min(int(preset["max_streams"]), hr_s)
        if self._danger_streams is not None:
            max_s = min(max_s, max(min_s, self._danger_streams - 1))
        if low_quota:
            max_s = 1
        else:
            rpm_cap = max(min_s, min(int(preset["max_streams"]), int(self._target_global_rpm // 5.5)))
            max_s = min(max_s, rpm_cap)
        self._target_streams = max(min_s, min(max_s, int(self._target_streams)))

    def _effective_rpm_unlocked(self, now: float) -> float:
        if self._mode == "manual":
            base = self._manual_rpm
            if self._state in ("probing", "recovering"):
                return max(8.0, base * 0.80)
            return base
        self._clamp_target_unlocked()
        preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
        if self._state in ("probing", "recovering"):
            if self._quota_cruise_active:
                return max(preset["quota_floor_rpm"], self._target_global_rpm * 0.90)
            return max(preset["floor_rpm"], self._target_global_rpm * 0.82)
        return self._target_global_rpm

    def _prune_telemetry_unlocked(self, now: float) -> None:
        cutoff_1m = now - 60.0
        while self._global_sent_1m and self._global_sent_1m[0][0] <= cutoff_1m:
            _, w = self._global_sent_1m.popleft()
            self._sent_1m_weight = max(0.0, self._sent_1m_weight - w)
        if not self._global_sent_1m:
            self._sent_1m_weight = 0.0

        cutoff_5m = now - 300.0
        while self._global_sent_5m and self._global_sent_5m[0][0] <= cutoff_5m:
            _, w = self._global_sent_5m.popleft()
            self._sent_5m_weight = max(0.0, self._sent_5m_weight - w)
        if not self._global_sent_5m:
            self._sent_5m_weight = 0.0

        cutoff_60m = now - 3600.0
        while self._global_sent_60m and self._global_sent_60m[0][0] <= cutoff_60m:
            _, w = self._global_sent_60m.popleft()
            self._sent_60m_weight = max(0.0, self._sent_60m_weight - w)
        if not self._global_sent_60m:
            self._sent_60m_weight = 0.0

        while self._wave_ts_60m and self._wave_ts_60m[0] <= cutoff_60m:
            self._wave_ts_60m.popleft()

        cutoff_2m = now - 120.0
        for dq in self._node_sent_ts.values():
            while dq and dq[0] <= cutoff_2m:
                dq.popleft()
        while self._global_sched_ts and self._global_sched_ts[0] <= cutoff_1m:
            self._global_sched_ts.popleft()
        for dq in self._node_sched_ts.values():
            while dq and dq[0] <= cutoff_1m:
                dq.popleft()

    def live_rpm(self, now: Optional[float] = None) -> float:
        ts = time.time() if now is None else now
        with self._lock:
            self._prune_telemetry_unlocked(ts)
            return round(self._sent_1m_weight, 1)

    def is_node_hot(self, host: str, now: Optional[float] = None) -> bool:
        """True when `host` recently returned HTTP 429 and should yield priority to cool shards."""
        ts = time.time() if now is None else now
        h = (host or "").strip().lower()
        with self._lock:
            return bool(h and ts < self._hot_node_until.get(h, 0.0))

    def max_concurrent_streams(self, now: Optional[float] = None) -> Tuple[int, int]:
        """Return `(max_total_pawchive_streams, max_per_storage_node_streams)` right now.
        Dynamically closes down to (0, 0) on cooldown, (1, 1) on probe, (2, 1) on recovery,
        and scales up to (6, 3) in Smart mode as clean streaks accumulate."""
        ts = time.time() if now is None else now
        with self._lock:
            if ts < self._domain_cooldown_until:
                return 0, 0
            if self._state in ("probing", "paused_shield"):
                return 1, 1
            if self._mode == "manual":
                tot = self._manual_max_streams
                if self._state == "recovering":
                    return min(2, tot), 1
                return tot, min(3, max(1, (tot + 1) // 2))
            self._clamp_streams_unlocked()
            tot = self._target_streams
            if self._state == "recovering":
                return min(2, tot), 1
            per_node = 1 if tot <= 2 else (2 if tot <= 4 else 3)
            return tot, per_node

    def max_streams_for_node(self, host: str, now: Optional[float] = None) -> int:
        """Per-node stream limit, tightening to 1 if that specific shard recently overloaded."""
        ts = time.time() if now is None else now
        h = (host or "").strip().lower()
        with self._lock:
            tot, per_node = self.max_concurrent_streams(ts)
            if tot <= 0:
                return 0
            if h and ts < self._hot_node_until.get(h, 0.0):
                return 1
            return per_node

    def get_cooldown_until(self, now: Optional[float] = None) -> float:
        ts = time.time() if now is None else now
        with self._lock:
            if self._domain_cooldown_until > 0 and ts >= self._domain_cooldown_until and self._state == "cooldown":
                self._state = "probing"
            return self._domain_cooldown_until

    def is_cooling_down(self, now: Optional[float] = None) -> bool:
        ts = time.time() if now is None else now
        return ts < self.get_cooldown_until(ts)

    def is_probing(self) -> bool:
        now = time.time()
        with self._lock:
            if self._state == "cooldown" and now >= self._domain_cooldown_until:
                self._state = "probing"
            return self._state == "probing" or (self._state == "paused_shield" and now >= self._domain_cooldown_until)

    # ── Pacing Slot Reservation & Request Telemetry ───────────────────────────

    def reserve_pace_slot(self, host: str, respect_cooldown: bool = True, now: Optional[float] = None) -> float:
        """Reserve the next polite request timestamp for `host` across both per-node and global budgets.
        Returns `wait_seconds >= 0.0`."""
        h = (host or "").strip().lower()
        if "pawchive.pw" not in h:
            return 0.0

        ts = time.time() if now is None else now
        is_thumb = "img.pawchive.pw" in h
        is_storage = bool(_STORAGE_HOST_RE.match(h))

        with self._lock:
            if self._state == "cooldown" and ts >= self._domain_cooldown_until:
                self._state = "probing"
            self._prune_telemetry_unlocked(ts)

            eff_rpm = self._effective_rpm_unlocked(ts)
            slow_ttfb = ts < self._node_slow_ttfb_until.get(h, 0.0)
            in_cautious = self._state in ("probing", "recovering")

            if is_thumb:
                # Thumbnails are lightweight CDN hits: gentle spacing without starving main RPM
                min_node_gap = 0.30 if in_cautious else (0.22 if slow_ttfb else 0.14)
                min_global_gap = 0.10
                cd_floor = self._domain_cooldown_until if respect_cooldown else ts
                slot = max(ts, cd_floor, self._node_next_slot.get(h, 0.0), self._global_next_slot)
                self._node_next_slot[h] = slot + min_node_gap
                self._global_next_slot = max(self._global_next_slot, slot + min_global_gap)
                return max(0.0, slot - ts)

            # Storage / API request: apply Two-Layer (Per-Node + Global IP) pacing
            in_quota_low = eff_rpm < 12.0
            if in_quota_low:
                # Quota Cruise (< 12 req/min): smooth even spacing (7.5s–15s apart) with zero bursts
                global_gap = 60.0 / max(3.0, eff_rpm) * (1.0 if in_cautious else 0.94)
                default_node_rpm = eff_rpm
            else:
                global_gap = max(0.45, 60.0 / max(8.0, eff_rpm) * 0.72)
                if in_cautious:
                    global_gap = max(global_gap, 60.0 / max(8.0, eff_rpm))
                default_node_rpm = max(8.0, min(eff_rpm * 0.70, 22.0))

            node_rpm = self._node_rpm.get(h, default_node_rpm) if is_storage else eff_rpm
            node_rpm = min(node_rpm, eff_rpm)
            node_gap = max(0.55, 60.0 / max(3.0, node_rpm) * (0.94 if node_rpm < 12.0 else 0.80))
            if slow_ttfb:
                node_gap = max(node_gap, 1.10)
            if in_cautious:
                node_gap = max(node_gap, 1.25)

            cd_floor = self._domain_cooldown_until if respect_cooldown else ts
            node_next = self._node_next_slot.get(h, 0.0)
            if respect_cooldown:
                slot = max(ts, cd_floor, self._global_next_slot, node_next)
            else:
                slot = max(ts, self._global_next_slot, min(node_next, ts + node_gap))

            # Global 10s burst guard + 60s RPM cap + 5m sustained leaky-bucket guard
            g_dq = self._global_sched_ts
            if in_quota_low:
                burst_10s = 1 if eff_rpm <= 6.5 else 2
            else:
                burst_10s = max(3, min(7, int(math.ceil(eff_rpm / 4.5))))
            cap_60s = max(3, int(round(eff_rpm)))
            if len(g_dq) >= burst_10s:
                slot = max(slot, g_dq[-burst_10s] + 10.05)
            if len(g_dq) >= cap_60s:
                slot = max(slot, g_dq[-cap_60s] + 60.05)

            # 5-minute sustained window check from real sent requests
            sent_5m = self._sent_5m_weight
            cap_5m = eff_rpm * 4.80
            if sent_5m >= cap_5m and self._global_sent_5m:
                slot = max(slot, self._global_sent_5m[0][0] + 300.05)

            # Per-node 60s rolling cap
            n_dq = self._node_sched_ts.setdefault(h, deque())
            node_cap_60s = max(3, int(round(node_rpm)))
            if len(n_dq) >= node_cap_60s:
                slot = max(slot, n_dq[-node_cap_60s] + 60.05)

            g_dq.append(slot)
            n_dq.append(slot)
            self._global_next_slot = max(self._global_next_slot, slot + global_gap)
            self._node_next_slot[h] = max(node_next, slot + node_gap)
            return max(0.0, slot - ts)

    def record_request_sent(self, host: str, now: Optional[float] = None) -> None:
        """Record an actual outbound HTTP GET to `*.pawchive.pw`."""
        h = (host or "").strip().lower()
        if "pawchive.pw" not in h:
            return
        ts = time.time() if now is None else now
        weight = 0.35 if "img.pawchive.pw" in h else 1.0
        with self._lock:
            self._prune_telemetry_unlocked(ts)
            item = (ts, weight)
            self._global_sent_1m.append(item)
            self._sent_1m_weight += weight
            self._global_sent_5m.append(item)
            self._sent_5m_weight += weight
            self._global_sent_60m.append(item)
            self._sent_60m_weight += weight
            if weight >= 1.0:
                self._node_sent_ts.setdefault(h, deque()).append(ts)

    def note_ttfb(self, host: str, ttfb_s: float) -> None:
        h = (host or "").strip().lower()
        if h and "pawchive.pw" in h and ttfb_s >= 2.5:
            with self._lock:
                self._node_slow_ttfb_until[h] = max(self._node_slow_ttfb_until.get(h, 0.0), time.time() + 30.0)

    def claim_probe_slot(self) -> bool:
        """Ensure at most ONE worker runs an inline Pass-1 probe per domain cooldown window."""
        with self._lock:
            if self._cooldown_id > self._probe_claimed_id:
                self._probe_claimed_id = self._cooldown_id
                return True
            return False

    # ── 429 Event & Clean Completion State Machine ────────────────────────────

    def on_429(self, host: str = "", retry_after: float = 0.0, now: Optional[float] = None) -> Dict[str, Any]:
        """Handle an HTTP 429 from `host`: engage domain-wide quiet cooldown, close down active
        stream targets, apply smart attribution, and trip Ban-Shield after 3 failed probes."""
        h = (host or "").strip().lower()
        ts = time.time() if now is None else now
        notify_needed = False
        entered_cooldown = False

        with self._lock:
            self._prune_telemetry_unlocked(ts)
            already_cooling = ts < self._domain_cooldown_until

            if not already_cooling:
                entered_cooldown = True
                self._cooldown_id += 1
                was_probing = self._state == "probing"
                prev_last_429 = self._last_429_wall_ts
                self._wave_ts_60m.append(ts)
                waves_5m, waves_60m = self._wave_counts_unlocked(ts)
                if prev_last_429 > 0.0 and (ts - prev_last_429) >= 300.0 and waves_5m <= 1 and waves_60m <= 2:
                    self._wave = 0
                self._wave += 1
                if was_probing:
                    self._consecutive_failed_probes += 1
                elif self._consecutive_failed_probes == 0:
                    self._consecutive_failed_probes = 1

                # Measure real request rate over last 60s and last 5m
                obs_60s = self._sent_1m_weight
                obs_5m_rpm = self._sent_5m_weight / 5.0
                node_60s = len([t for t in self._node_sent_ts.get(h, ()) if t > ts - 60.0]) if h else 0

                cross_node_recent = any(
                    other_h != h and (ts - last_t) <= 180.0
                    for other_h, last_t in self._node_last_429_ts.items()
                )
                if h:
                    self._node_last_429_ts[h] = ts
                    if _STORAGE_HOST_RE.match(h):
                        # Always mark the offending storage shard hot so cool shards take priority
                        self._hot_node_until[h] = max(self._hot_node_until.get(h, 0.0), ts + 240.0)
                self._last_429_wall_ts = ts

                # Determine whether a single hot node overloaded or the shared IP bucket tripped
                node_share = (node_60s / max(1.0, obs_60s)) if (h and obs_60s >= 4.0) else 0.0
                single_node_overload = bool(
                    h and _STORAGE_HOST_RE.match(h) and node_share >= 0.75 and not cross_node_recent and obs_5m_rpm < 22.0
                )

                prev_streams = self._target_streams
                hard_brake = False
                if self._mode == "manual":
                    tiers = (
                        float(self._manual_cooldown_s),
                        min(180.0, self._manual_cooldown_s * 1.5),
                        min(240.0, self._manual_cooldown_s * 2.2),
                    )
                    raw_cd = tiers[min(self._wave - 1, len(tiers) - 1)]
                else:
                    preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
                    obs_eff = max(obs_60s, obs_5m_rpm)
                    near_floor = self._target_global_rpm <= (preset["floor_rpm"] + 1.5)
                    hard_brake = (waves_5m >= 3) or (waves_60m >= 5)
                    enter_quota_cruise = hard_brake or (waves_5m >= 2) or (waves_60m >= 3) or near_floor or self._quota_cruise_active

                    if hard_brake:
                        # 3rd+ 429 in 5m or 5th+ in 60m -> 4-minute Quiet Quota Breather + drop to 4–5 req/min
                        self._quota_cruise_active = True
                        q_floor = preset["quota_floor_rpm"]
                        self._target_global_rpm = max(q_floor, min(self._target_global_rpm * 0.65, 5.0))
                        self._target_streams = 1
                        if h and _STORAGE_HOST_RE.match(h):
                            self._node_rpm[h] = max(q_floor, min(self._node_rpm.get(h, self._target_global_rpm), self._target_global_rpm))
                            self._hot_node_until[h] = max(self._hot_node_until.get(h, 0.0), ts + 420.0)
                        self._clamp_target_unlocked()
                        self._clamp_streams_unlocked()
                        raw_cd = 245.0
                    elif enter_quota_cruise:
                        # 2nd 429 in 5m / near floor -> unlock Quota Cruise (< 12 RPM, 1 conn) below server refill rate
                        self._quota_cruise_active = True
                        q_floor = preset["quota_floor_rpm"]
                        ref_rpm = min(self._target_global_rpm, max(q_floor, obs_eff)) if obs_eff >= q_floor else self._target_global_rpm
                        self._target_global_rpm = max(
                            q_floor,
                            min(self._target_global_rpm * 0.68, ref_rpm * 0.76, preset["floor_rpm"] - 2.5),
                        )
                        if h and _STORAGE_HOST_RE.match(h):
                            self._node_rpm[h] = max(q_floor, min(self._node_rpm.get(h, self._target_global_rpm), self._target_global_rpm))
                            self._hot_node_until[h] = max(self._hot_node_until.get(h, 0.0), ts + 360.0)
                        self._target_streams = 1 if self._target_global_rpm < 10.5 else min(2, prev_streams)
                        self._clamp_target_unlocked()
                        self._clamp_streams_unlocked()
                        raw_cd = 60.0 if self._mode == "smart" else 72.0
                    else:
                        # 1st transient 429 in 5m -> short 20s speed bump, preserve >= 12 RPM floor
                        if single_node_overload:
                            cur_n = self._node_rpm.get(h, min(self._target_global_rpm * 0.70, 20.0))
                            ref_n = max(8.0, float(node_60s)) if node_60s >= 6 else cur_n
                            self._node_rpm[h] = max(8.0, min(cur_n * 0.85, ref_n * 0.78))
                            self._target_global_rpm = max(preset["floor_rpm"], self._target_global_rpm * 0.90)
                            self._target_streams = max(int(preset["min_streams"]), prev_streams - 1)
                            self._clamp_streams_unlocked()
                        else:
                            trigger_rpm = obs_eff if obs_eff >= 10.0 else (self._target_global_rpm * 0.92)
                            min_danger = preset["floor_rpm"] / preset["safety_ratio"]
                            if self._danger_global_rpm is None:
                                self._danger_global_rpm = max(min_danger, trigger_rpm)
                            elif trigger_rpm >= preset["floor_rpm"]:
                                self._danger_global_rpm = min(self._danger_global_rpm, max(min_danger, trigger_rpm))
                            if prev_streams >= 4 or (prev_streams >= 3 and self._wave >= 2):
                                self._danger_streams = (
                                    prev_streams if self._danger_streams is None else min(self._danger_streams, prev_streams)
                                )
                            step_down = 2 if prev_streams >= 4 else 1
                            self._target_global_rpm = self._target_global_rpm * 0.80
                            self._clamp_target_unlocked()
                            self._target_streams = max(int(preset["min_streams"]), prev_streams - step_down)
                            self._clamp_streams_unlocked()
                        raw_cd = 38.0 if was_probing else preset["base_cd"]

                max_cd_cap = 300.0 if hard_brake else 180.0
                cooldown_s = min(max_cd_cap, max(raw_cd, float(retry_after or 0.0)))
                # Small deterministic-safe positive jitter (0% to +8%)
                cooldown_s = round(cooldown_s * random.uniform(1.0, 1.08), 1)

                self._domain_cooldown_until = ts + cooldown_s
                self._global_next_slot = max(self._global_next_slot, self._domain_cooldown_until)
                if h:
                    self._node_next_slot[h] = max(self._node_next_slot.get(h, 0.0), self._domain_cooldown_until)

                # Clear future scheduled slots that were queued before the 429
                while self._global_sched_ts and self._global_sched_ts[-1] > ts:
                    self._global_sched_ts.pop()
                for dq in self._node_sched_ts.values():
                    while dq and dq[-1] > ts:
                        dq.pop()

                self._recovery_clean_files = 0
                self._cruise_clean_files = 0
                self._self_heal_clean_files = 0

                should_auto_pause = self._consecutive_failed_probes >= 3
                self._state = "paused_shield" if should_auto_pause else "cooldown"
                notify_needed = True

                scope_lbl = f"node {h}" if single_node_overload else "shared *.pawchive.pw IP bucket"
                conn_note = f" | connections {prev_streams}→0 (cooldown)→{self._target_streams}" if self._mode != "manual" else ""
                mode_note = " | Quota Cruise unlocked" if self._quota_cruise_active else ""
                logger.warning(
                    f"🛡️ [Pawchive Rate Guard] HTTP 429 ({scope_lbl}, wave {self._wave}, {waves_5m}/5m • {waves_60m}/60m) — "
                    f"quiet domain cooldown {int(round(cooldown_s))}s | target pace {self._effective_rpm_unlocked(ts):.1f} req/min"
                    + conn_note
                    + mode_note
                    + (f" | ceiling {self._danger_global_rpm:.1f} req/min" if self._danger_global_rpm else ""),
                    category="downloader",
                )
            else:
                waves_5m, waves_60m = self._wave_counts_unlocked(ts)
                cooldown_s = max(1.0, self._domain_cooldown_until - ts)
                should_auto_pause = self._state == "paused_shield"

            res = {
                "entered_cooldown": entered_cooldown,
                "cooldown_until": self._domain_cooldown_until,
                "cooldown_s": cooldown_s,
                "wave": self._wave,
                "waves_5m": waves_5m,
                "waves_60m": waves_60m,
                "quota_cruise": self._quota_cruise_active,
                "target_rpm": round(self._target_global_rpm, 1),
                "danger_rpm": round(self._danger_global_rpm, 1) if self._danger_global_rpm else None,
                "target_streams": self._target_streams,
                "danger_streams": self._danger_streams,
                "should_auto_pause": should_auto_pause,
                "state": self._state,
            }

        if notify_needed:
            self._save_async(force=True)
            self._notify()
        return res

    def on_request_succeeded(self, host: str = "", now: Optional[float] = None) -> None:
        """Record a clean HTTP 200/206/416 from Pawchive. Requires sustained clean traffic before
        exiting recovery (no 1-file amnesia), then smoothly ramps pace & connections back up."""
        h = (host or "").strip().lower()
        if h and "pawchive.pw" not in h:
            return
        if "img.pawchive.pw" in h:
            return

        ts = time.time() if now is None else now
        changed = False
        with self._lock:
            if self._state in ("cooldown", "paused_shield") and ts >= self._domain_cooldown_until:
                self._state = "probing"

            if self._state == "probing":
                # First clean probe after quiet cooldown -> enter cautious recovery (<=2 streams, 82% RPM)
                self._state = "recovering"
                self._recovery_started_at = ts
                self._recovery_clean_files = 1
                self._consecutive_failed_probes = 0
                changed = True
                rec_s, _ = self.max_concurrent_streams(ts)
                logger.info(
                    f"🟢 [Pawchive Rate Guard] Post-cooldown probe succeeded — entering smooth recovery "
                    f"({rec_s} conn • {self._effective_rpm_unlocked(ts):.1f} req/min for 15 clean files)...",
                    category="downloader",
                )
            elif self._state == "recovering":
                self._recovery_clean_files += 1
                elapsed_rec = ts - self._recovery_started_at
                if self._recovery_clean_files >= 15 and elapsed_rec >= 75.0:
                    self._state = "cruise"
                    waves_5m, waves_60m = self._wave_counts_unlocked(ts)
                    # Only reset wave counter if >= 5 full clean minutes have elapsed without a 429
                    if (self._last_429_wall_ts <= 0.0 or (ts - self._last_429_wall_ts) >= 300.0) and waves_5m == 0 and not self._quota_cruise_active:
                        self._wave = 0
                    self._consecutive_failed_probes = 0
                    self._cruise_clean_files = 0
                    self._last_probe_up_ts = ts
                    changed = True
                    cr_s, _ = self.max_concurrent_streams(ts)
                    mode_lbl = "Quota Cruise" if self._quota_cruise_active else "Cruise"
                    logger.info(
                        f"⚡ [Pawchive Rate Guard] Recovery verified ({self._recovery_clean_files} clean files) — "
                        f"resuming {mode_lbl} at {cr_s} conn • {self._effective_rpm_unlocked(ts):.1f} req/min.",
                        category="downloader",
                    )
            else:
                self._state = "cruise"
                self._cruise_clean_files += 1
                self._self_heal_clean_files += 1
                waves_5m, waves_60m = self._wave_counts_unlocked(ts)
                if self._wave > 0 and (ts - self._last_429_wall_ts) >= 300.0 and waves_5m == 0:
                    self._wave = 0

                if self._mode != "manual":
                    preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
                    # Self-heal old danger ceilings after 120 clean files & >= 10 min so a fluke 429 never locks speeds down
                    if (
                        (self._danger_global_rpm is not None or self._danger_streams is not None)
                        and self._self_heal_clean_files >= 120
                        and (ts - self._last_429_wall_ts) >= 600.0
                    ):
                        self._self_heal_clean_files = 0
                        if self._danger_global_rpm is not None:
                            new_d = self._danger_global_rpm * 1.08
                            if new_d >= preset["max_rpm"] / preset["safety_ratio"]:
                                self._danger_global_rpm = None
                            else:
                                self._danger_global_rpm = new_d
                        if self._danger_streams is not None:
                            if self._danger_streams + 1 > int(preset["max_streams"]):
                                self._danger_streams = None
                            else:
                                self._danger_streams += 1
                        changed = True

                    # Upward probe cadence:
                    # - In Quota Cruise or elevated hourly waves (>= 3 in 60m): probe gently every 12 minutes (720s)
                    #   so we generate <= 3–4 test bumps/hour while hourly windows drain, then graduate smoothly.
                    # - In normal healthy Cruise: probe every 25 clean files & >= 60s.
                    slow_probe_mode = self._quota_cruise_active or waves_60m >= 3
                    ref_probe_ts = max(self._last_probe_up_ts, self._last_429_wall_ts) if slow_probe_ts_needed(slow_probe_mode) else self._last_probe_up_ts
                    min_probe_files = 20 if slow_probe_mode else 25
                    min_probe_interval = 720.0 if slow_probe_mode else 60.0
                    if self._cruise_clean_files >= min_probe_files and (ts - ref_probe_ts) >= min_probe_interval:
                        self._cruise_clean_files = 0
                        self._last_probe_up_ts = ts
                        prev_t = self._target_global_rpm
                        prev_s = self._target_streams
                        prev_qc = self._quota_cruise_active
                        step_rpm = 2.0 if self._quota_cruise_active else 1.5
                        self._target_global_rpm += step_rpm
                        if self._quota_cruise_active and self._target_global_rpm >= preset["floor_rpm"] and waves_5m == 0:
                            self._quota_cruise_active = False
                        self._clamp_target_unlocked()
                        if not self._quota_cruise_active or self._target_global_rpm >= 10.5:
                            self._target_streams += 1
                        self._clamp_streams_unlocked()
                        for nh in list(self._node_rpm.keys()):
                            self._node_rpm[nh] = min(22.0, self._node_rpm[nh] + step_rpm)
                        if abs(self._target_global_rpm - prev_t) >= 0.1 or self._target_streams != prev_s or prev_qc != self._quota_cruise_active:
                            changed = True
                            logger.debug(
                                f"📈 [Pawchive Rate Guard] Clean streak — scaling up to {self._target_streams} conn "
                                f"• {self._target_global_rpm:.1f} req/min"
                                + (" (exited Quota Cruise)." if (prev_qc and not self._quota_cruise_active) else "."),
                                category="downloader",
                            )

        if changed:
            self._save_async(force=False)
            self._notify()
