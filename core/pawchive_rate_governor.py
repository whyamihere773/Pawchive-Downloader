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
import os
import random
import re
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from core.atomic_io import atomic_write_json
from core.logger import logger

RATE_GUARD_MODES = ("smart", "cautious", "manual")
_STORAGE_HOST_RE = re.compile(r"^(?:file|[nt]\d+)\.pawchive\.pw$", re.IGNORECASE)


def normalize_rate_guard_mode(val: Any) -> str:
    v = str(val or "smart").strip().lower()
    if v in ("smart", "auto", "balanced", "default"):
        return "smart"
    if v in ("cautious", "paranoid", "ban_safe", "safe", "stealth"):
        return "cautious"
    if v in ("manual", "custom"):
        return "manual"
    return "smart"


class PawchiveRateGovernor:
    """Thread-safe two-layer congestion controller and persistent rate calibrator for `*.pawchive.pw`."""

    # Preset parameters: fast enough to never feel sluggish, conservative enough to avoid 429s
    _PRESETS: Dict[str, Dict[str, float]] = {
        "smart": {
            "start_rpm": 26.0,       # ~1,560 files/hr baseline
            "floor_rpm": 12.0,       # anti-crawl floor (1 file / 5s worst-case)
            "max_rpm": 36.0,         # ~2,160 files/hr max auto-probe
            "safety_ratio": 0.85,    # settle comfortably at 85% of confirmed 429 ceiling
            "start_streams": 3.0,    # starts balanced at 3 simultaneous connections
            "min_streams": 2.0,      # Cruise anti-crawl floor (0 in cooldown, 1 in probe, 2+ in cruise)
            "max_streams": 6.0,      # dynamically opens up to 6 Pawchive connections when clean
            "base_cd": 35.0,
        },
        "cautious": {
            "start_rpm": 18.0,       # ~1,080 files/hr baseline
            "floor_rpm": 9.0,        # 1 file / 6.6s worst-case
            "max_rpm": 24.0,
            "safety_ratio": 0.75,    # extra 25% safety headroom below any 429 ceiling
            "start_streams": 2.0,
            "min_streams": 1.0,
            "max_streams": 2.0,
            "base_cd": 45.0,
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
        self._domain_cooldown_until: float = 0.0
        self._cooldown_id: int = 0
        self._probe_claimed_id: int = 0
        self._wave: int = 0
        self._consecutive_failed_probes: int = 0
        self._recovery_started_at: float = 0.0
        self._recovery_clean_files: int = 0
        self._cruise_clean_files: int = 0
        self._self_heal_clean_files: int = 0
        self._last_probe_up_ts: float = 0.0

        # Sliding-window telemetry (real HTTP requests sent vs next scheduled slot)
        self._global_sent_ts: deque = deque()            # (timestamp, weight) over last 300s
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

    # ── Configuration & Persistence ───────────────────────────────────────────

    def configure(
        self,
        *,
        mode: Optional[str] = None,
        manual_rpm: Optional[float] = None,
        manual_max_streams: Optional[int] = None,
        manual_cooldown_s: Optional[int] = None,
    ) -> None:
        changed = False
        with self._lock:
            if mode is not None:
                nm = normalize_rate_guard_mode(mode)
                if nm != self._mode:
                    prev_mode = self._mode
                    self._mode = nm
                    changed = True
                    if nm in self._PRESETS:
                        p = self._PRESETS[nm]
                        if prev_mode == "manual" or self._target_global_rpm <= 0:
                            self._target_global_rpm = p["start_rpm"]
                            self._target_streams = int(p["start_streams"])
                        self._clamp_target_unlocked()
                        self._clamp_streams_unlocked()
            if manual_rpm is not None:
                mr = max(8.0, min(60.0, float(manual_rpm)))
                if abs(mr - self._manual_rpm) >= 0.05:
                    self._manual_rpm = mr
                    changed = True
            if manual_max_streams is not None:
                ms = max(1, min(6, int(manual_max_streams)))
                if ms != self._manual_max_streams:
                    self._manual_max_streams = ms
                    changed = True
            if manual_cooldown_s is not None:
                mc = max(15, min(180, int(manual_cooldown_s)))
                if mc != self._manual_cooldown_s:
                    self._manual_cooldown_s = mc
                    changed = True
        if changed:
            self._save_async(force=True)
            self._notify()

    def reset_runtime(self) -> None:
        """Clear transient in-session cooldown/probing flags while preserving learned safe speeds."""
        with self._lock:
            self._state = "cruise"
            self._domain_cooldown_until = 0.0
            self._cooldown_id = 0
            self._probe_claimed_id = 0
            self._wave = 0
            self._consecutive_failed_probes = 0
            self._recovery_clean_files = 0
            self._hot_node_until.clear()
            self._global_sched_ts.clear()
            self._node_sched_ts.clear()
            self._global_next_slot = 0.0
            self._node_next_slot.clear()
        self._notify()

    def recalibrate(self) -> Dict[str, Any]:
        """Clear learned 429 danger ceilings & penalties and begin a fresh smooth calibration."""
        with self._lock:
            preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
            self._danger_global_rpm = None
            self._danger_streams = None
            self._hot_node_until.clear()
            self._node_rpm.clear()
            self._node_last_429_ts.clear()
            self._target_global_rpm = preset["start_rpm"] if self._mode != "manual" else self._manual_rpm
            self._target_streams = int(preset["start_streams"]) if self._mode != "manual" else self._manual_max_streams
            self._state = "cruise"
            self._domain_cooldown_until = 0.0
            self._cooldown_id = 0
            self._probe_claimed_id = 0
            self._wave = 0
            self._consecutive_failed_probes = 0
            self._recovery_clean_files = 0
            self._cruise_clean_files = 0
            self._self_heal_clean_files = 0
            self._global_sched_ts.clear()
            self._node_sched_ts.clear()
            self._global_next_slot = 0.0
            self._node_next_slot.clear()
            snap = self.snapshot()
        logger.info(
            f"🔄 [Pawchive Rate Guard] Recalibrated — reset learned ceilings to {snap['effective_rpm']:.1f} req/min "
            f"& {snap['max_streams']} conn ({self._mode} mode).",
            category="downloader",
        )
        self._save_async(force=True)
        self._notify()
        return snap

    def _load_from_disk(self) -> None:
        if not self._persist_path or not os.path.isfile(self._persist_path):
            return
        try:
            import json
            with open(self._persist_path, "r", encoding="utf-8") as rf:
                data = json.load(rf)
            if not isinstance(data, dict):
                return
            with self._lock:
                if "mode" in data:
                    self._mode = normalize_rate_guard_mode(data.get("mode"))
                if "manual_rpm" in data:
                    self._manual_rpm = max(8.0, min(60.0, float(data["manual_rpm"])))
                if "manual_max_streams" in data:
                    self._manual_max_streams = max(1, min(6, int(data["manual_max_streams"])))
                if "manual_cooldown_s" in data:
                    self._manual_cooldown_s = max(15, min(180, int(data["manual_cooldown_s"])))

                preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
                saved_target = float(data.get("target_global_rpm") or preset["start_rpm"])
                saved_danger = data.get("danger_global_rpm")
                saved_streams = int(data.get("target_streams") or preset["start_streams"])
                saved_danger_s = data.get("danger_streams")
                last_429 = float(data.get("last_429_wall_ts") or 0.0)
                self._last_429_wall_ts = last_429

                # Time-based decay on restart so old penalties from hours/days ago never lock speeds low
                now = time.time()
                hours_since_429 = max(0.0, (now - last_429) / 3600.0) if last_429 > 0 else 999.0
                if saved_danger is not None:
                    d_val = float(saved_danger)
                    if hours_since_429 >= 48.0:
                        d_val = None
                    elif hours_since_429 >= 2.0:
                        # Heal +12% per 6 hours away from Pawchive
                        heal_factor = 1.0 + 0.12 * (hours_since_429 / 6.0)
                        d_val = min(preset["max_rpm"] / preset["safety_ratio"], d_val * heal_factor)
                        if d_val >= preset["max_rpm"]:
                            d_val = None
                    self._danger_global_rpm = d_val

                if saved_danger_s is not None:
                    ds_val: Optional[int] = int(saved_danger_s)
                    if hours_since_429 >= 24.0:
                        ds_val = None
                    elif hours_since_429 >= 6.0 and ds_val is not None:
                        ds_val = ds_val + int(hours_since_429 // 6.0)
                        if ds_val > int(preset["max_streams"]):
                            ds_val = None
                    self._danger_streams = ds_val

                if hours_since_429 >= 6.0 and saved_target < preset["start_rpm"]:
                    saved_target = min(preset["start_rpm"], saved_target + 4.0 * (hours_since_429 / 6.0))
                if hours_since_429 >= 6.0 and saved_streams < int(preset["start_streams"]):
                    saved_streams = min(int(preset["start_streams"]), saved_streams + int(hours_since_429 // 6.0))
                self._target_global_rpm = saved_target
                self._target_streams = saved_streams
                self._clamp_target_unlocked()
                self._clamp_streams_unlocked()

                raw_nodes = data.get("node_rpm")
                if isinstance(raw_nodes, dict) and hours_since_429 < 24.0:
                    for hk, hv in raw_nodes.items():
                        try:
                            self._node_rpm[str(hk).lower()] = max(8.0, min(30.0, float(hv)))
                        except (TypeError, ValueError):
                            pass
        except Exception as ex:
            logger.debug(f"[PawchiveRateGovernor] Profile load skipped: {ex}", category="downloader")

    def _save_async(self, force: bool = False) -> None:
        if not self._persist_path:
            return
        now = time.time()
        with self._lock:
            if not force and (now - self._last_save_ts < 15.0 or self._save_pending):
                return
            self._save_pending = True
            self._last_save_ts = now
            payload = {
                "version": 1,
                "updated_at": now,
                "mode": self._mode,
                "manual_rpm": round(self._manual_rpm, 2),
                "manual_max_streams": self._manual_max_streams,
                "manual_cooldown_s": self._manual_cooldown_s,
                "target_global_rpm": round(self._target_global_rpm, 2),
                "danger_global_rpm": round(self._danger_global_rpm, 2) if self._danger_global_rpm is not None else None,
                "target_streams": int(self._target_streams),
                "danger_streams": int(self._danger_streams) if self._danger_streams is not None else None,
                "last_429_wall_ts": self._last_429_wall_ts,
                "node_rpm": {k: round(v, 2) for k, v in self._node_rpm.items()},
            }
            path = self._persist_path

        def _writer():
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                atomic_write_json(path, payload)
            except Exception as ex:
                logger.debug(f"[PawchiveRateGovernor] Profile save skipped: {ex}", category="downloader")
            finally:
                with self._lock:
                    self._save_pending = False

        threading.Thread(target=_writer, daemon=True, name="PawchiveRateProfileSave").start()

    def _notify(self) -> None:
        cb = self._on_state_changed
        if cb is not None:
            try:
                cb()
            except Exception:
                pass

    # ── Core Calculations ─────────────────────────────────────────────────────

    def _clamp_target_unlocked(self) -> None:
        preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
        floor_rpm = preset["floor_rpm"]
        ceil_rpm = preset["max_rpm"]
        if self._danger_global_rpm is not None:
            ceil_rpm = min(ceil_rpm, max(floor_rpm, self._danger_global_rpm * preset["safety_ratio"]))
        self._target_global_rpm = max(floor_rpm, min(ceil_rpm, self._target_global_rpm))

    def _clamp_streams_unlocked(self) -> None:
        preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
        min_s = int(preset["min_streams"])
        max_s = int(preset["max_streams"])
        if self._danger_streams is not None:
            max_s = min(max_s, max(min_s, self._danger_streams - 1))
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
            return max(preset["floor_rpm"], self._target_global_rpm * 0.82)
        return self._target_global_rpm

    def _prune_telemetry_unlocked(self, now: float) -> None:
        cutoff_5m = now - 300.0
        while self._global_sent_ts and self._global_sent_ts[0][0] <= cutoff_5m:
            self._global_sent_ts.popleft()
        cutoff_2m = now - 120.0
        for dq in self._node_sent_ts.values():
            while dq and dq[0] <= cutoff_2m:
                dq.popleft()
        cutoff_1m = now - 60.0
        while self._global_sched_ts and self._global_sched_ts[0] <= cutoff_1m:
            self._global_sched_ts.popleft()
        for dq in self._node_sched_ts.values():
            while dq and dq[0] <= cutoff_1m:
                dq.popleft()

    def live_rpm(self, now: Optional[float] = None) -> float:
        ts = time.time() if now is None else now
        with self._lock:
            self._prune_telemetry_unlocked(ts)
            c60 = ts - 60.0
            return round(sum(w for t, w in self._global_sent_ts if t > c60), 1)

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
            global_gap = max(0.45, 60.0 / max(8.0, eff_rpm) * 0.72)
            if in_cautious:
                global_gap = max(global_gap, 60.0 / max(8.0, eff_rpm))

            default_node_rpm = max(8.0, min(eff_rpm * 0.70, 22.0))
            node_rpm = self._node_rpm.get(h, default_node_rpm) if is_storage else eff_rpm
            node_rpm = min(node_rpm, eff_rpm)
            node_gap = max(0.55, 60.0 / max(6.0, node_rpm) * 0.80)
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
            burst_10s = max(3, min(7, int(math.ceil(eff_rpm / 4.5))))
            cap_60s = max(6, int(round(eff_rpm)))
            if len(g_dq) >= burst_10s:
                slot = max(slot, g_dq[-burst_10s] + 10.05)
            if len(g_dq) >= cap_60s:
                slot = max(slot, g_dq[-cap_60s] + 60.05)

            # 5-minute sustained window check from real sent requests
            sent_5m = sum(w for t, w in self._global_sent_ts if t > ts - 300.0)
            cap_5m = eff_rpm * 4.80
            if sent_5m >= cap_5m and self._global_sent_ts:
                slot = max(slot, self._global_sent_ts[0][0] + 300.05)

            # Per-node 60s rolling cap
            n_dq = self._node_sched_ts.setdefault(h, deque())
            node_cap_60s = max(5, int(round(node_rpm)))
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
            self._global_sent_ts.append((ts, weight))
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
                self._wave += 1
                if was_probing:
                    self._consecutive_failed_probes += 1
                elif self._consecutive_failed_probes == 0:
                    self._consecutive_failed_probes = 1

                # Measure real request rate over last 60s and last 5m
                obs_60s = sum(w for t, w in self._global_sent_ts if t > ts - 60.0)
                obs_5m_rpm = sum(w for t, w in self._global_sent_ts if t > ts - 300.0) / 5.0
                node_60s = len([t for t in self._node_sent_ts.get(h, ()) if t > ts - 60.0]) if h else 0

                cross_node_recent = any(
                    other_h != h and (ts - last_t) <= 180.0
                    for other_h, last_t in self._node_last_429_ts.items()
                )
                if h:
                    self._node_last_429_ts[h] = ts
                self._last_429_wall_ts = ts

                # Determine whether a single hot node overloaded or the shared IP bucket tripped
                node_share = (node_60s / max(1.0, obs_60s)) if (h and obs_60s >= 4.0) else 0.0
                single_node_overload = bool(
                    h and _STORAGE_HOST_RE.match(h) and node_share >= 0.75 and not cross_node_recent and obs_5m_rpm < 22.0
                )

                prev_streams = self._target_streams
                if self._mode != "manual":
                    preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
                    obs_eff = max(obs_60s, obs_5m_rpm)
                    if single_node_overload:
                        cur_n = self._node_rpm.get(h, min(self._target_global_rpm * 0.70, 20.0))
                        ref_n = max(8.0, float(node_60s)) if node_60s >= 6 else cur_n
                        self._node_rpm[h] = max(8.0, min(cur_n * 0.85, ref_n * 0.78))
                        self._hot_node_until[h] = ts + 240.0
                        self._target_global_rpm = max(preset["floor_rpm"], self._target_global_rpm * 0.90)
                        self._target_streams = max(int(preset["min_streams"]), prev_streams - 1)
                        self._clamp_streams_unlocked()
                    else:
                        trigger_rpm = obs_eff if obs_eff >= 10.0 else (self._target_global_rpm * 0.92)
                        if self._danger_global_rpm is None:
                            self._danger_global_rpm = max(preset["floor_rpm"] / preset["safety_ratio"], trigger_rpm)
                        else:
                            # Smooth EWMA / min update, bounded above floor so a post-cooldown probe doesn't crush ceiling
                            if trigger_rpm >= preset["floor_rpm"]:
                                self._danger_global_rpm = min(self._danger_global_rpm, trigger_rpm)
                        if prev_streams >= 4 or (prev_streams >= 3 and self._wave >= 2):
                            self._danger_streams = (
                                prev_streams if self._danger_streams is None else min(self._danger_streams, prev_streams)
                            )
                        step_down = 2 if prev_streams >= 4 else 1
                        self._target_global_rpm = self._target_global_rpm * 0.78
                        self._clamp_target_unlocked()
                        self._target_streams = max(int(preset["min_streams"]), prev_streams - step_down)
                        self._clamp_streams_unlocked()

                # Compute domain-wide quiet cooldown (jittered so retries never look robotic)
                if self._mode == "manual":
                    tiers = (
                        float(self._manual_cooldown_s),
                        min(180.0, self._manual_cooldown_s * 1.5),
                        min(240.0, self._manual_cooldown_s * 2.2),
                    )
                else:
                    b_cd = self._PRESETS.get(self._mode, self._PRESETS["smart"])["base_cd"]
                    tiers = (b_cd, b_cd * 1.7, b_cd * 2.5, 135.0)

                raw_cd = tiers[min(self._wave - 1, len(tiers) - 1)]
                cooldown_s = min(180.0, max(raw_cd, float(retry_after or 0.0)))
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
                logger.warning(
                    f"🛡️ [Pawchive Rate Guard] HTTP 429 ({scope_lbl}, wave {self._wave}) — "
                    f"quiet domain cooldown {int(round(cooldown_s))}s | target pace {self._effective_rpm_unlocked(ts):.1f} req/min"
                    + conn_note
                    + (f" | ceiling {self._danger_global_rpm:.1f} req/min" if self._danger_global_rpm else ""),
                    category="downloader",
                )
            else:
                cooldown_s = max(1.0, self._domain_cooldown_until - ts)
                should_auto_pause = self._state == "paused_shield"

            res = {
                "entered_cooldown": entered_cooldown,
                "cooldown_until": self._domain_cooldown_until,
                "cooldown_s": cooldown_s,
                "wave": self._wave,
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
                    self._wave = 0
                    self._consecutive_failed_probes = 0
                    self._cruise_clean_files = 0
                    self._last_probe_up_ts = ts
                    changed = True
                    cr_s, _ = self.max_concurrent_streams(ts)
                    logger.info(
                        f"⚡ [Pawchive Rate Guard] Recovery verified ({self._recovery_clean_files} clean files) — "
                        f"resuming Cruise at {cr_s} conn • {self._effective_rpm_unlocked(ts):.1f} req/min.",
                        category="downloader",
                    )
            else:
                self._state = "cruise"
                self._cruise_clean_files += 1
                self._self_heal_clean_files += 1

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

                    # Smooth upward probe every 25 clean files & >= 60s: nudge pace (+1.5 RPM) & open +1 connection
                    if self._cruise_clean_files >= 25 and (ts - self._last_probe_up_ts) >= 60.0:
                        self._cruise_clean_files = 0
                        self._last_probe_up_ts = ts
                        prev_t = self._target_global_rpm
                        prev_s = self._target_streams
                        self._target_global_rpm += 1.5
                        self._clamp_target_unlocked()
                        self._target_streams += 1
                        self._clamp_streams_unlocked()
                        for nh in list(self._node_rpm.keys()):
                            self._node_rpm[nh] = min(22.0, self._node_rpm[nh] + 1.5)
                        if abs(self._target_global_rpm - prev_t) >= 0.1 or self._target_streams != prev_s:
                            changed = True
                            logger.debug(
                                f"📈 [Pawchive Rate Guard] Clean streak — scaling up to {self._target_streams} conn "
                                f"• {self._target_global_rpm:.1f} req/min.",
                                category="downloader",
                            )

        if changed:
            self._save_async(force=False)
            self._notify()

    # ── UI Snapshot ───────────────────────────────────────────────────────────

    def snapshot(self, now: Optional[float] = None) -> Dict[str, Any]:
        ts = time.time() if now is None else now
        with self._lock:
            if self._state == "cooldown" and ts >= self._domain_cooldown_until:
                self._state = "probing"
            cd_rem = max(0.0, self._domain_cooldown_until - ts)
            eff = round(self._effective_rpm_unlocked(ts), 1)
            live = self.live_rpm(ts)
            danger = round(self._danger_global_rpm, 1) if self._danger_global_rpm is not None else 0.0
            danger_s = int(self._danger_streams) if self._danger_streams is not None else 0
            tot_s, node_s = self.max_concurrent_streams(ts)

            if cd_rem > 0.0:
                status = f"Quiet Cooldown: {int(round(cd_rem))}s (0 conn • wave {max(1, self._wave)})"
            elif self._state == "paused_shield":
                status = "Ban-Shield Paused (3× 429 probes — wait a few min & Resume)"
            elif self._state == "probing":
                status = f"Probing (1 test conn • {eff:.0f} req/min)"
            elif self._state == "recovering":
                status = f"Recovering ({self._recovery_clean_files}/15 clean • {tot_s} conn • {eff:.0f} req/min)"
            else:
                ceil_part = f" • Safe Cap {eff:.0f}/min" if danger > 0 else f" • Pace {eff:.0f}/min"
                status = f"Cruise ({live:.0f} req/min • {tot_s} conn{ceil_part})"

            return {
                "mode": self._mode,
                "state": self._state if cd_rem <= 0 else "cooldown",
                "cooldown_remaining": round(cd_rem, 1),
                "live_rpm": live,
                "effective_rpm": eff,
                "target_rpm": round(self._target_global_rpm, 1),
                "danger_rpm": danger,
                "target_streams": self._target_streams,
                "danger_streams": danger_s,
                "manual_rpm": round(self._manual_rpm, 1),
                "manual_max_streams": self._manual_max_streams,
                "manual_cooldown_s": self._manual_cooldown_s,
                "max_streams": tot_s,
                "node_streams": node_s,
                "status_text": status,
            }
