"""
Hardware Acceleration Detector for Pawchive Downloader
Detects available GPU devices (NVIDIA, AMD Radeon, Intel Arc/UHD) and determines the best
execution provider for ONNX Runtime with graceful potato-safe CPU fallbacks.
"""

import os
import sys
import platform
from typing import List, Tuple, Dict, Any, Union, Optional
from core.logger import logger


class HardwareDetector:
    """Detects graphics hardware and configures optimal ONNX execution providers."""

    _cached_device_info: Optional[Dict[str, Any]] = None

    @classmethod
    def get_hardware_info(cls) -> Dict[str, Any]:
        """Returns detected GPU hardware details and execution provider capability."""
        if cls._cached_device_info is not None:
            return cls._cached_device_info

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
                cmd = 'powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"'
                res = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
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
