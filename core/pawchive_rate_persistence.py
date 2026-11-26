"""
Configuration, Disk Persistence & UI Snapshot Mixin for `PawchiveRateGovernor`.
Decomposed from `core/pawchive_rate_governor.py` to keep every module cohesive and well under 1,000 lines.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

from core.atomic_io import atomic_write_json
from core.logger import logger

RATE_GUARD_MODES = ("smart", "cautious", "manual")
RATE_GUARD_FOOTER_STYLES = ("full", "micro", "minimal", "tiny", "hidden")


def normalize_rate_guard_mode(val: Any) -> str:
    v = str(val or "smart").strip().lower()
    if v in ("smart", "auto", "balanced", "default"):
        return "smart"
    if v in ("cautious", "paranoid", "ban_safe", "safe", "stealth"):
        return "cautious"
    if v in ("manual", "custom"):
        return "manual"
    return "smart"


def normalize_rate_guard_footer_style(val: Any) -> str:
    v = str(val or "micro").strip().lower()
    if v in ("full", "full_length", "expanded", "detailed"):
        return "full"
    if v in ("micro", "compact", "unified", "default"):
        return "micro"
    if v in ("minimal", "mini", "short"):
        return "minimal"
    if v in ("tiny", "nano", "dot"):
        return "tiny"
    if v in ("hidden", "off", "none"):
        return "hidden"
    return "micro"


class PawchiveRatePersistenceMixin:
    """Handles runtime configuration, `pawchive_rate_profile.json` persistence, and UI snapshots."""

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
            self._quota_cruise_active = False
            self._domain_cooldown_until = 0.0
            self._cooldown_id = 0
            self._probe_claimed_id = 0
            self._wave = 0
            self._wave_ts_60m.clear()
            self._consecutive_failed_probes = 0
            self._recovery_clean_files = 0
            self._hot_node_until.clear()
            self._global_sched_ts.clear()
            self._node_sched_ts.clear()
            self._global_next_slot = 0.0
            self._node_next_slot.clear()
            if self._mode != "manual":
                self._clamp_target_unlocked()
                self._clamp_streams_unlocked()
        self._notify()

    def recalibrate(self) -> Dict[str, Any]:
        """Clear learned 429 danger ceilings & penalties and begin a fresh smooth calibration."""
        with self._lock:
            preset = self._PRESETS.get(self._mode, self._PRESETS["smart"])
            self._danger_global_rpm = None
            self._danger_streams = None
            self._quota_cruise_active = False
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
            self._wave_ts_60m.clear()
            self._consecutive_failed_probes = 0
            self._recovery_clean_files = 0
            self._cruise_clean_files = 0
            self._self_heal_clean_files = 0
            self._global_sent_1m.clear()
            self._global_sent_5m.clear()
            self._global_sent_60m.clear()
            self._sent_1m_weight = 0.0
            self._sent_5m_weight = 0.0
            self._sent_60m_weight = 0.0
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
                    d_val: Optional[float] = float(saved_danger)
                    if hours_since_429 >= 48.0:
                        d_val = None
                    elif hours_since_429 >= 2.0 and d_val is not None:
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

                # Restore rolling 60m / 5m / 1m request history and 429 wave history
                self._global_sent_1m.clear()
                self._global_sent_5m.clear()
                self._global_sent_60m.clear()
                self._sent_1m_weight = 0.0
                self._sent_5m_weight = 0.0
                self._sent_60m_weight = 0.0
                raw_sent = data.get("sent_ts_60m")
                if isinstance(raw_sent, list):
                    c_60m = now - 3600.0
                    c_5m = now - 300.0
                    c_1m = now - 60.0
                    for pair in raw_sent:
                        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                            continue
                        try:
                            t_s = float(pair[0])
                            w_s = float(pair[1])
                        except (TypeError, ValueError):
                            continue
                        if c_60m < t_s <= now + 5.0 and w_s > 0.0:
                            tup = (t_s, w_s)
                            self._global_sent_60m.append(tup)
                            self._sent_60m_weight += w_s
                            if t_s > c_5m:
                                self._global_sent_5m.append(tup)
                                self._sent_5m_weight += w_s
                            if t_s > c_1m:
                                self._global_sent_1m.append(tup)
                                self._sent_1m_weight += w_s

                self._wave_ts_60m.clear()
                raw_waves = data.get("wave_ts_60m")
                if isinstance(raw_waves, list):
                    c_60m = now - 3600.0
                    for wt in raw_waves:
                        try:
                            wt_f = float(wt)
                            if c_60m < wt_f <= now + 5.0:
                                self._wave_ts_60m.append(wt_f)
                        except (TypeError, ValueError):
                            pass

                raw_hot = data.get("hot_node_until")
                if isinstance(raw_hot, dict):
                    for hk, hv in raw_hot.items():
                        try:
                            hv_f = float(hv)
                            if now < hv_f <= now + 900.0:
                                self._hot_node_until[str(hk).lower()] = hv_f
                        except (TypeError, ValueError):
                            pass

                raw_n429 = data.get("node_last_429_ts")
                if isinstance(raw_n429, dict):
                    for hk, hv in raw_n429.items():
                        try:
                            hv_f = float(hv)
                            if (now - hv_f) < 3600.0 and hv_f <= now + 5.0:
                                self._node_last_429_ts[str(hk).lower()] = hv_f
                        except (TypeError, ValueError):
                            pass

                # Restore Quota Cruise across restarts for the full 60-minute rolling window
                saved_qc = data.get("quota_cruise_active")
                if saved_qc is not None:
                    self._quota_cruise_active = bool(saved_qc and self._mode != "manual" and hours_since_429 < 1.0)
                else:
                    self._quota_cruise_active = bool(
                        self._mode != "manual" and hours_since_429 < 1.0 and saved_target < preset["floor_rpm"]
                    )

                self._target_global_rpm = saved_target
                self._target_streams = saved_streams
                self._clamp_target_unlocked()
                self._clamp_streams_unlocked()

                # Restore active cooldown, probing, or recovery state
                saved_cd_until = float(data.get("domain_cooldown_until") or 0.0)
                saved_state = str(data.get("state") or "cruise")
                if now < saved_cd_until <= (now + 600.0):
                    self._domain_cooldown_until = saved_cd_until
                    self._global_next_slot = saved_cd_until
                    self._cooldown_id = 1
                    self._state = "paused_shield" if saved_state == "paused_shield" else "cooldown"
                elif (saved_cd_until > 0.0 or saved_state in ("cooldown", "probing")) and hours_since_429 < 0.25:
                    self._state = "probing"
                    self._cooldown_id = 1
                elif saved_state == "recovering" and hours_since_429 < 0.5:
                    self._state = "recovering"
                    self._recovery_clean_files = max(0, min(14, int(data.get("recovery_clean_files") or 0)))
                    self._recovery_started_at = min(now, float(data.get("recovery_started_at") or now))

                if hours_since_429 * 3600.0 < 300.0 or self._wave_ts_60m:
                    self._wave = max(0, int(data.get("wave") or 0))
                    self._consecutive_failed_probes = max(0, min(3, int(data.get("consecutive_failed_probes") or 0)))
                self._last_probe_up_ts = min(now, max(0.0, float(data.get("last_probe_up_ts") or 0.0)))

                raw_nodes = data.get("node_rpm")
                if isinstance(raw_nodes, dict) and hours_since_429 < 24.0:
                    node_floor = 4.0 if self._quota_cruise_active else 8.0
                    for hk, hv in raw_nodes.items():
                        try:
                            self._node_rpm[str(hk).lower()] = max(node_floor, min(30.0, float(hv)))
                        except (TypeError, ValueError):
                            pass
        except Exception as ex:
            logger.debug(f"[PawchiveRateGovernor] Profile load skipped: {ex}", category="downloader")

    def _build_persist_payload_unlocked(self, now: float) -> Dict[str, Any]:
        return {
            "version": 2,
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
            "state": self._state,
            "quota_cruise_active": bool(self._quota_cruise_active),
            "domain_cooldown_until": round(self._domain_cooldown_until, 2) if self._domain_cooldown_until > now else 0.0,
            "wave": int(self._wave),
            "consecutive_failed_probes": int(self._consecutive_failed_probes),
            "recovery_started_at": round(self._recovery_started_at, 2),
            "recovery_clean_files": int(self._recovery_clean_files),
            "last_probe_up_ts": round(self._last_probe_up_ts, 2),
            "hot_node_until": {k: round(v, 2) for k, v in self._hot_node_until.items() if v > now},
            "node_last_429_ts": {k: round(v, 2) for k, v in self._node_last_429_ts.items() if (now - v) < 3600.0},
            "wave_ts_60m": [round(t, 2) for t in self._wave_ts_60m if (now - t) < 3600.0],
            "sent_ts_60m": [[round(t, 2), round(w, 2)] for t, w in self._global_sent_60m if (now - t) < 3600.0],
        }

    def flush_to_disk(self) -> None:
        """Synchronously persist full Rate Guard state (called on clean application shutdown)."""
        if not self._persist_path:
            return
        now = time.time()
        with self._lock:
            payload = self._build_persist_payload_unlocked(now)
            self._last_save_ts = now
            path = self._persist_path
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            atomic_write_json(path, payload)
        except Exception as ex:
            logger.debug(f"[PawchiveRateGovernor] Profile flush skipped: {ex}", category="downloader")

    def _save_async(self, force: bool = False) -> None:
        if not self._persist_path:
            return
        now = time.time()
        with self._lock:
            if not force and (now - self._last_save_ts < 15.0 or self._save_pending):
                return
            self._save_pending = True
            self._last_save_ts = now
            payload = self._build_persist_payload_unlocked(now)
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

    def snapshot(self, now: Optional[float] = None) -> Dict[str, Any]:
        ts = time.time() if now is None else now
        with self._lock:
            self._prune_telemetry_unlocked(ts)
            if self._state == "cooldown" and ts >= self._domain_cooldown_until:
                self._state = "probing"
            cd_rem = max(0.0, self._domain_cooldown_until - ts)
            eff = round(self._effective_rpm_unlocked(ts), 1)
            live = round(self._sent_1m_weight, 1)
            waves_5m, waves_60m = self._wave_counts_unlocked(ts)
            danger = round(self._danger_global_rpm, 1) if self._danger_global_rpm is not None else 0.0
            danger_s = int(self._danger_streams) if self._danger_streams is not None else 0
            tot_s, node_s = self.max_concurrent_streams(ts)

            if cd_rem > 0.0:
                status = f"Quiet Cooldown: {int(round(cd_rem))}s (0 conn • wave {max(1, self._wave)})"
            elif self._state == "paused_shield":
                status = "Ban-Shield Paused (3× 429 probes — wait a few min & Resume)"
            elif self._state == "probing":
                status = f"Probing (1 test conn • {eff:.1f} req/min)"
            elif self._state == "recovering":
                status = f"Recovering ({self._recovery_clean_files}/15 clean • {tot_s} conn • {eff:.1f} req/min)"
            elif self._quota_cruise_active:
                status = f"Quota Cruise ({live:.0f} req/min • {tot_s} conn • Steady {eff:.1f}/min)"
            else:
                ceil_part = f" • Safe Cap {eff:.0f}/min" if danger > 0 else f" • Pace {eff:.0f}/min"
                status = f"Cruise ({live:.0f} req/min • {tot_s} conn{ceil_part})"

            return {
                "mode": self._mode,
                "state": self._state if cd_rem <= 0 else "cooldown",
                "quota_cruise": self._quota_cruise_active,
                "cooldown_remaining": round(cd_rem, 1),
                "wave": int(self._wave),
                "recovery_clean_files": int(self._recovery_clean_files),
                "live_rpm": live,
                "effective_rpm": eff,
                "target_rpm": round(self._target_global_rpm, 1),
                "danger_rpm": danger,
                "target_streams": self._target_streams,
                "danger_streams": danger_s,
                "waves_5m": waves_5m,
                "waves_60m": waves_60m,
                "sent_5m": round(self._sent_5m_weight, 1),
                "sent_60m": round(self._sent_60m_weight, 1),
                "manual_rpm": round(self._manual_rpm, 1),
                "manual_max_streams": self._manual_max_streams,
                "manual_cooldown_s": self._manual_cooldown_s,
                "max_streams": tot_s,
                "node_streams": node_s,
                "status_text": status,
            }
