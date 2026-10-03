"""
Hardware Acceleration Detector for Pawchive Downloader
Detects available GPU devices (NVIDIA, AMD Radeon, Intel Arc/UHD) and determines the best
execution provider for ONNX Runtime with graceful potato-safe CPU fallbacks.
"""

import sys
import threading
from typing import List, Tuple, Dict, Any, Optional
from core.logger import logger


class HardwareDetector:
    """Detects graphics hardware and configures optimal ONNX execution providers."""

    _cached_device_info: Optional[Dict[str, Any]] = None
    _probe_lock = threading.Lock()
    _probe_running = False
    _probe_callbacks: List[Any] = []
    _detect_lock = threading.Lock()     # one detection at a time (it starts PowerShell)

    @classmethod
    def cached_info(cls) -> Optional[Dict[str, Any]]:
        """The detection result if it's already known, else None (never blocks)."""
        return cls._cached_device_info

    @classmethod
    def probe_async(cls, on_done=None) -> None:
        """Detects the hardware in a background thread (it starts PowerShell and loads ONNX Runtime,
        which froze the Settings page for a few seconds when done on the GUI thread)."""
        with cls._probe_lock:
            if cls._cached_device_info is not None:
                pass
            else:
                if on_done:
                    cls._probe_callbacks.append(on_done)
                if not cls._probe_running:
                    cls._probe_running = True
                    threading.Thread(target=cls._probe_worker, daemon=True, name="HardwareProbe").start()
                return
        if on_done:
            on_done()

    @classmethod
    def _probe_worker(cls) -> None:
        try:
            cls.get_hardware_info()
        finally:
            with cls._probe_lock:
                cls._probe_running = False
                callbacks, cls._probe_callbacks = cls._probe_callbacks, []
            for cb in callbacks:
                try:
                    cb()
                except Exception:
                    pass

    @classmethod
    def get_hardware_info(cls) -> Dict[str, Any]:
        """Returns detected GPU hardware details and execution provider capability.

        Blocks while detecting (PowerShell + ONNX Runtime, up to a few seconds): never call it from
        the window thread before cached_info() has a result; use probe_async() there."""
        if cls._cached_device_info is not None:
            return cls._cached_device_info
        with cls._detect_lock:          # a second caller waits for the first result instead of probing again
            if cls._cached_device_info is not None:
                return cls._cached_device_info
            return cls._detect_hardware()

    @classmethod
    def _detect_hardware(cls) -> Dict[str, Any]:

        info: Dict[str, Any] = {
            "has_gpu": False,
            "gpu_name": "None",
            "provider_type": "cpu",
            "provider_name": "CPU (Multi-threaded)",
            "onnx_providers": ["CPUExecutionProvider"],
            "directml_supported": False,
            "cuda_supported": False,
        }

        # 1. Query Windows video controllers if on Windows
        if sys.platform == "win32":
            try:
                import subprocess
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)   # no console window flashing up
                )
                if res.returncode == 0 and res.stdout.strip():
                    gpus = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
                    # Filter out virtual/remote display adapters if physical GPU exists
                    physical_gpus = [
                        g for g in gpus
                        if not any(v in g.lower() for v in ["virtual", "remote", "vnc", "citrix", "basic display"])
                    ]
                    best_gpu = physical_gpus[0] if physical_gpus else (gpus[0] if gpus else "Unknown GPU")
                    info["has_gpu"] = True
                    info["gpu_name"] = best_gpu
            except Exception as e:
                logger.debug(f"Hardware GPU query failed: {e}", category="hardware")

        # 2. Check available ONNX Runtime providers
        try:
            import onnxruntime as ort
            available = ort.get_available_providers()

            # Priority 1: Native NVIDIA CUDA
            if "CUDAExecutionProvider" in available:
                info["cuda_supported"] = True
                info["provider_type"] = "cuda"
                info["provider_name"] = f"GPU (NVIDIA CUDA: {info['gpu_name']})"
                info["onnx_providers"] = [
                    ("CUDAExecutionProvider", {
                        "device_id": 0,
                        "arena_extend_strategy": "kNextPowerOfTwo",
                    }),
                    "CPUExecutionProvider"
                ]
                cls._cached_device_info = info
                return info

            # Priority 2: DirectML (DirectX 12 on Windows - works on NVIDIA, AMD, Intel)
            if "DmlExecutionProvider" in available:
                info["directml_supported"] = True
                info["provider_type"] = "directml"
                info["provider_name"] = f"GPU (DirectML: {info['gpu_name']})"
                info["onnx_providers"] = [
                    ("DmlExecutionProvider", {
                        "device_id": 0
                    }),
                    "CPUExecutionProvider"
                ]
                cls._cached_device_info = info
                return info

        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"ONNX provider resolution notice: {e}", category="hardware")

        # Priority 3: Potato-safe CPU fallback (strictly 2 threads max to preserve UI responsiveness)
        info["provider_type"] = "cpu"
        info["provider_name"] = "CPU (Potato-Safe 2-Thread)"
        info["onnx_providers"] = [
            ("CPUExecutionProvider", {
                "intra_op_num_threads": 2,
                "inter_op_num_threads": 1
            })
        ]

        cls._cached_device_info = info
        return info

    @classmethod
    def get_best_onnx_providers(cls) -> Tuple[List[Any], str]:
        """Returns tuple of (configured_providers_list, display_name)."""
        info = cls.get_hardware_info()
        return info["onnx_providers"], info["provider_name"]

    @classmethod
    def reset_cache(cls) -> None:
        """Clears hardware cache for testing or runtime re-check."""
        cls._cached_device_info = None
