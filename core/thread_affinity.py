"""
Main GUI Thread P-Core Affinity & Priority Allocation (AGENTS.md Rule 2).

Dedicates the GUI/QML main thread to Performance Cores (P-Cores) on hybrid
CPUs (Intel 12th+ gen, heterogeneous ARM/AMD topologies) and elevates main
thread priority slightly above normal so background download/hash/AI workers
cannot starve the UI event loop or frame pacing.

Never raises on restricted/virtualized environments; always returns a
structured diagnostic summary for startup logging.
"""

from __future__ import annotations

import ctypes
import os
import sys
from typing import Any, Dict, List, Set


def _load_win32_kernel32():
    """Return a private kernel32 handle with explicit 64-bit-safe prototypes."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentThread.argtypes = []
    kernel32.GetCurrentThread.restype = ctypes.c_void_p
    kernel32.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
    kernel32.SetThreadPriority.restype = ctypes.c_int
    if hasattr(kernel32, "GetSystemCpuSetInformation"):
        kernel32.GetSystemCpuSetInformation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        kernel32.GetSystemCpuSetInformation.restype = ctypes.c_int
    if hasattr(kernel32, "SetThreadSelectedCpuSets"):
        kernel32.SetThreadSelectedCpuSets.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_ulong,
        ]
        kernel32.SetThreadSelectedCpuSets.restype = ctypes.c_int
    return kernel32


def _detect_windows_pcore_cpu_sets(kernel32=None) -> Dict[str, Any]:
    """Query Windows GetSystemCpuSetInformation to locate highest EfficiencyClass CPU sets."""
    if kernel32 is None:
        kernel32 = _load_win32_kernel32()
    if not hasattr(kernel32, "GetSystemCpuSetInformation"):
        return {"pcore_ids": [], "total_logical": os.cpu_count() or 1, "hybrid": False}
    buf_len = ctypes.c_ulong(0)
    # First call queries required buffer size (returns False with ERROR_INSUFFICIENT_BUFFER)
    kernel32.GetSystemCpuSetInformation(None, 0, ctypes.byref(buf_len), None, 0)
    size = int(buf_len.value)
    if size <= 0 or size > 4 * 1024 * 1024:
        return {"pcore_ids": [], "total_logical": os.cpu_count() or 1, "hybrid": False}

    raw = (ctypes.c_ubyte * size)()
    ok = kernel32.GetSystemCpuSetInformation(ctypes.byref(raw), size, ctypes.byref(buf_len), None, 0)
    if not ok:
        return {"pcore_ids": [], "total_logical": os.cpu_count() or 1, "hybrid": False}

    # SYSTEM_CPU_SET_INFORMATION header layout (Windows 10/11 SDK winnt.h):
    #   offset 0: DWORD Size
    #   offset 4: CPU_SET_INFORMATION_TYPE Type (0 = CpuSetInformation)
    #   offset 8: DWORD Id
    #   offset 12: WORD Group
    #   offset 14: BYTE LogicalProcessorIndex
    #   offset 15: BYTE CoreIndex
    #   offset 16: BYTE LastLevelCacheIndex
    #   offset 17: BYTE NumaNodeIndex
    #   offset 18: BYTE EfficiencyClass (higher value = higher performance P-Core)
    import struct

    entries = []
    offset = 0
    actual_size = int(buf_len.value)
    while offset + 20 <= actual_size:
        entry_size, entry_type = struct.unpack_from("<II", raw, offset)
        if entry_size < 20 or offset + entry_size > actual_size:
            break
        if entry_type == 0:  # CpuSetInformation
            cpu_set_id, _group, _lpi, _core, _llc, _numa, eff_class = struct.unpack_from("<IHBBBBB", raw, offset + 8)
            entries.append((cpu_set_id, eff_class))
        offset += entry_size

    if not entries:
        return {"pcore_ids": [], "total_logical": os.cpu_count() or 1, "hybrid": False}

    eff_classes = {eff for _, eff in entries}
    max_eff = max(eff_classes)
    pcore_ids = [cid for cid, eff in entries if eff == max_eff]
    return {
        "pcore_ids": pcore_ids,
        "total_logical": len(entries),
        "hybrid": len(eff_classes) > 1,
        "max_efficiency_class": max_eff,
    }


def _apply_windows_pcore_affinity() -> Dict[str, Any]:
    kernel32 = _load_win32_kernel32()
    thread_handle = kernel32.GetCurrentThread()

    # Elevate GUI main thread priority one step above normal (THREAD_PRIORITY_ABOVE_NORMAL = 1)
    prio_ok = bool(kernel32.SetThreadPriority(thread_handle, 1))
    prio_label = "ABOVE_NORMAL" if prio_ok else "NORMAL"

    topo = _detect_windows_pcore_cpu_sets(kernel32)
    pcore_ids: List[int] = topo.get("pcore_ids", [])
    total_logical = int(topo.get("total_logical") or (os.cpu_count() or 1))
    hybrid = bool(topo.get("hybrid"))

    if hybrid and pcore_ids and hasattr(kernel32, "SetThreadSelectedCpuSets"):
        arr_type = ctypes.c_ulong * len(pcore_ids)
        arr = arr_type(*pcore_ids)
        pin_ok = bool(kernel32.SetThreadSelectedCpuSets(thread_handle, arr, len(pcore_ids)))
        return {
            "applied": pin_ok or prio_ok,
            "pinned": pin_ok,
            "platform": "win32",
            "hybrid": True,
            "pcore_count": len(pcore_ids),
            "total_logical": total_logical,
            "priority": prio_label,
            "detail": (
                f"Main GUI thread pinned to {len(pcore_ids)}/{total_logical} P-Core logical threads "
                f"(priority={prio_label})"
                if pin_ok
                else f"Main GUI thread priority={prio_label} (CPU set pinning declined by OS)"
            ),
        }

    return {
        "applied": prio_ok,
        "pinned": False,
        "platform": "win32",
        "hybrid": False,
        "pcore_count": total_logical,
        "total_logical": total_logical,
        "priority": prio_label,
        "detail": f"Uniform CPU topology ({total_logical} logical threads); main GUI thread priority={prio_label}",
    }


def _detect_linux_pcore_cpus() -> Set[int]:
    """Identify highest-max-frequency logical CPUs on Linux hybrid CPUs via sysfs."""
    cpu_freqs: Dict[int, int] = {}
    sys_cpu = "/sys/devices/system/cpu"
    try:
        for name in os.listdir(sys_cpu):
            if not name.startswith("cpu") or not name[3:].isdigit():
                continue
            cid = int(name[3:])
            freq_path = os.path.join(sys_cpu, name, "cpufreq", "cpuinfo_max_freq")
            if os.path.isfile(freq_path):
                with open(freq_path, "r", encoding="utf-8") as f:
                    val = int(f.read().strip())
                if val > 0:
                    cpu_freqs[cid] = val
    except OSError:
        return set()

    if len(cpu_freqs) < 2:
        return set()
    max_freq = max(cpu_freqs.values())
    min_freq = min(cpu_freqs.values())
    # Only treat as hybrid if top tier is clearly faster (>5% gap) than lowest tier
    if max_freq <= min_freq * 1.05:
        return set()
    threshold = int(max_freq * 0.95)
    return {cid for cid, freq in cpu_freqs.items() if freq >= threshold}


def _apply_linux_pcore_affinity() -> Dict[str, Any]:
    total_logical = os.cpu_count() or 1
    pcores = _detect_linux_pcore_cpus()
    if pcores and hasattr(os, "sched_setaffinity"):
        try:
            allowed = os.sched_getaffinity(0)
            target = pcores & allowed
            if target and target != allowed:
                os.sched_setaffinity(0, target)
                return {
                    "applied": True,
                    "pinned": True,
                    "platform": "linux",
                    "hybrid": True,
                    "pcore_count": len(target),
                    "total_logical": total_logical,
                    "priority": "NORMAL",
                    "detail": f"Main GUI thread pinned to {len(target)}/{total_logical} high-frequency P-Core threads",
                }
        except OSError as e:
            return {
                "applied": False,
                "pinned": False,
                "platform": "linux",
                "hybrid": True,
                "pcore_count": len(pcores),
                "total_logical": total_logical,
                "priority": "NORMAL",
                "detail": f"Linux P-Core affinity skipped ({e})",
            }
    return {
        "applied": False,
        "pinned": False,
        "platform": "linux",
        "hybrid": False,
        "pcore_count": total_logical,
        "total_logical": total_logical,
        "priority": "NORMAL",
        "detail": f"Uniform Linux CPU topology ({total_logical} logical threads)",
    }


def prioritize_main_thread_pcore() -> Dict[str, Any]:
    """Allocate the current (main GUI) thread to Performance Cores and elevate scheduling priority."""
    try:
        if sys.platform == "win32":
            return _apply_windows_pcore_affinity()
        if sys.platform.startswith("linux"):
            return _apply_linux_pcore_affinity()
    except Exception as e:
        return {
            "applied": False,
            "pinned": False,
            "platform": sys.platform,
            "hybrid": False,
            "pcore_count": os.cpu_count() or 1,
            "total_logical": os.cpu_count() or 1,
            "priority": "NORMAL",
            "detail": f"Thread affinity skipped: {e}",
        }
    total = os.cpu_count() or 1
    return {
        "applied": False,
        "pinned": False,
        "platform": sys.platform,
        "hybrid": False,
        "pcore_count": total,
        "total_logical": total,
        "priority": "NORMAL",
        "detail": f"Default scheduler affinity on {sys.platform}",
    }
