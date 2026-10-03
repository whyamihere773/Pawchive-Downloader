"""
On-Demand Model Manager Subsystem
Handles automated zero-handholding downloading, verification, caching, and lifecycle
management of on-demand AI models for character recognition and semantic matching.
"""

import os
import time
import threading
import requests
from typing import Optional, Dict, Any, Callable, List
from core.logger import logger
from core.hardware_detector import HardwareDetector


# Model catalog definitions with multi-mirror redundancy
MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    "fast_semantic": {
        "name": "Fast Multilingual Semantic Matcher",
        "description": "GPU/CPU vector embedding model for cross-lingual character and series matching.",
        "size_bytes": 127 * 1024 * 1024,  # ~127 MB (model + tokenizer)
        "files": [
            {
                "filename": "multilingual_minilm_l12_int8.onnx",
                "mirrors": [
                    "https://github.com/whyamihere773/Pawchive-Downloader/releases/download/v1.2.0-ai-models/multilingual_minilm_l12_int8.onnx",
                    "https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/resolve/main/onnx/model_int8.onnx",
                ],
                "expected_min_bytes": 60 * 1024 * 1024,
            },
            {
                "filename": "tokenizer.json",
                "mirrors": [
                    "https://github.com/whyamihere773/Pawchive-Downloader/releases/download/v1.2.0-ai-models/tokenizer.json",
                    "https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/resolve/main/tokenizer.json",
                ],
                "expected_min_bytes": 5 * 1024 * 1024,
            },
        ],
    },
    "deep_reasoner_light": {
        "name": "Deep Context Reasoner (Light • Qwen 0.5B)",
        "description": "Potato-friendly 0.5B reasoning model. Low memory (~450 MB RAM), ideal for older PCs and laptops.",
        "size_bytes": 490 * 1024 * 1024,  # ~490 MB
        "files": [
            {
                "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
                "mirrors": [
                    "https://github.com/whyamihere773/Pawchive-Downloader/releases/download/v1.2.0-ai-models/qwen2.5-0.5b-instruct-q4_k_m.gguf",
                    "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
                ],
                "expected_min_bytes": 400 * 1024 * 1024,
            }
        ],
    },
    "deep_reasoner_heavy": {
        "name": "Deep Context Reasoner (Smart • Qwen 1.5B)",
        "description": "High-intelligence 1.5B model with deep anime & pop culture knowledge. Ideal for modern CPUs & GPUs.",
        "size_bytes": 1117 * 1024 * 1024,  # ~1.04 GB
        "files": [
            {
                "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
                "mirrors": [
                    "https://github.com/whyamihere773/Pawchive-Downloader/releases/download/v1.2.0-ai-models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
                    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
                ],
                "expected_min_bytes": 950 * 1024 * 1024,
            }
        ],
    },
}

# Alias deep_reasoner default to light model
MODEL_CATALOG["deep_reasoner"] = MODEL_CATALOG["deep_reasoner_light"]



class ModelManager:
    """Manages AI model files on disk, background streaming downloads, and verification."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = base_dir
            self.models_dir = os.path.join(self.base_dir, "dependencies", "models")
        else:
            from core.path_utils import get_dependencies_dir, get_base_dir
            self.base_dir = get_base_dir()
            self.models_dir = os.path.join(get_dependencies_dir(), "models")

        os.makedirs(self.models_dir, exist_ok=True)

        self._lock = threading.Lock()
        self._active_downloads: Dict[str, threading.Event] = {}
        self._progress_data: Dict[str, Dict[str, Any]] = {}
        self._callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def get_models_dir(self) -> str:
        """Returns the directory where model artifacts reside."""
        os.makedirs(self.models_dir, exist_ok=True)
        return self.models_dir

    def is_model_ready(self, model_key: str) -> bool:
        """Checks if all required files for a model are present and non-empty on disk."""
        if model_key not in MODEL_CATALOG:
            return False

        spec = MODEL_CATALOG[model_key]
        for item in spec["files"]:
            target_path = os.path.join(self.models_dir, item["filename"])
            if not os.path.exists(target_path):
                return False
            min_size = item.get("expected_min_bytes", 1024)
            if os.path.getsize(target_path) < min_size:
                return False
        return True

    def get_model_file_path(self, model_key: str, filename: Optional[str] = None) -> Optional[str]:
        """Returns the absolute file path for a model artifact if ready."""
        if not self.is_model_ready(model_key):
            return None
        spec = MODEL_CATALOG[model_key]
        target_name = filename or spec["files"][0]["filename"]
        target_path = os.path.join(self.models_dir, target_name)
        return target_path if os.path.exists(target_path) else None

    def get_status(self, model_key: str) -> Dict[str, Any]:
        """Returns detailed status information for the model."""
        if model_key not in MODEL_CATALOG:
            return {"status": "unknown", "error": f"Invalid model key: {model_key}"}

        spec = MODEL_CATALOG[model_key]
        with self._lock:
            prog = self._progress_data.get(model_key)
            if prog and prog.get("status") in ("downloading", "error"):
                return dict(prog)

        ready = self.is_model_ready(model_key)
        # Never detect here: Settings asks for this while opening, and detecting starts PowerShell
        # and loads ONNX Runtime (the page froze for up to a few seconds). It runs in the background.
        hw_info = HardwareDetector.cached_info()
        if hw_info is None:
            HardwareDetector.probe_async()
            hw_info = {"provider_name": "Detecting hardware…", "has_gpu": False}

        return {
            "model_key": model_key,
            "name": spec["name"],
            "description": spec["description"],
            "size_bytes": spec["size_bytes"],
            "status": "ready" if ready else "not_downloaded",
            "is_ready": ready,
            "hardware": hw_info["provider_name"],
            "has_gpu": hw_info["has_gpu"],
            "percent": 100.0 if ready else 0.0,
            "speed_mbps": 0.0,
            "error": "",
        }

    def register_callback(self, model_key: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a progress callback for a model download."""
        with self._lock:
            if model_key not in self._callbacks:
                self._callbacks[model_key] = []
            self._callbacks[model_key].append(callback)

    def _notify_progress(self, model_key: str, data: Dict[str, Any]) -> None:
        """Notify all registered listeners about download progress."""
        with self._lock:
            self._progress_data[model_key] = dict(data)
            listeners = list(self._callbacks.get(model_key, []))
        for cb in listeners:
            try:
                cb(data)
            except Exception as e:
                logger.debug(f"Progress callback error for {model_key}: {e}", category="ai")

    def start_download(
        self,
        model_key: str,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> bool:
        """Initiates a background download of the specified model across mirrors."""
        if model_key not in MODEL_CATALOG:
            logger.error(f"Cannot download unknown model: {model_key}", category="ai")
            return False

        if self.is_model_ready(model_key):
            self._notify_progress(model_key, self.get_status(model_key))
            return True

        with self._lock:
            if model_key in self._active_downloads:
                # Already in progress
                if on_progress:
                    self.register_callback(model_key, on_progress)
                return True

            cancel_event = threading.Event()
            self._active_downloads[model_key] = cancel_event
            if on_progress:
                self.register_callback(model_key, on_progress)

        thread = threading.Thread(
            target=self._download_worker,
            args=(model_key, cancel_event),
            daemon=True,
            name=f"ModelDownload-{model_key}"
        )
        thread.start()
        return True

    def cancel_download(self, model_key: str) -> None:
        """Signals active download to cancel and clean up temporary partial files."""
        with self._lock:
            cancel_event = self._active_downloads.get(model_key)
            if cancel_event:
                cancel_event.set()
                logger.info(f"Cancellation requested for {model_key} download.", category="ai")

    def delete_model(self, model_key: str) -> bool:
        """Deletes downloaded model files to reclaim disk space."""
        self.cancel_download(model_key)
        if model_key not in MODEL_CATALOG:
            return False

        spec = MODEL_CATALOG[model_key]
        success = True
        for item in spec["files"]:
            target_path = os.path.join(self.models_dir, item["filename"])
            part_path = f"{target_path}.part"
            for p in [target_path, part_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception as e:
                        logger.error(f"Failed to delete {p}: {e}", category="ai")
                        success = False

        self._notify_progress(model_key, {
            "model_key": model_key,
            "status": "not_downloaded",
            "percent": 0.0,
            "is_ready": False,
            "error": ""
        })
        return success

    def _download_worker(self, model_key: str, cancel_event: threading.Event) -> None:
        """Background worker thread performing streaming downloads with mirror fallback."""
        spec = MODEL_CATALOG[model_key]
        total_model_bytes = spec["size_bytes"]
        downloaded_so_far = 0

        logger.info(f"Starting download of AI model '{spec['name']}'...", category="ai")

        self._notify_progress(model_key, {
            "model_key": model_key,
            "status": "downloading",
            "percent": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": total_model_bytes,
            "speed_mbps": 0.0,
            "is_ready": False,
            "error": ""
        })

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pawchive/1.2.0 (AI Assistant)",
            "Accept": "*/*"
        }

        for file_spec in spec["files"]:
            filename = file_spec["filename"]
            target_path = os.path.join(self.models_dir, filename)
            part_path = f"{target_path}.part"
            mirrors = file_spec["mirrors"]
            min_bytes = file_spec.get("expected_min_bytes", 1024)

            # If file already exists and is valid on disk, skip downloading it!
            if os.path.exists(target_path) and os.path.getsize(target_path) >= min_bytes:
                downloaded_so_far += os.path.getsize(target_path)
                logger.info(f"File {filename} is already present and verified ({os.path.getsize(target_path)} bytes).", category="ai")
                continue

            file_success = False

            # Try each mirror in sequence
            for mirror_url in mirrors:
                if cancel_event.is_set():
                    break

                try:
                    logger.debug(f"Attempting download of {filename} from: {mirror_url}", category="ai")
                    with requests.get(mirror_url, headers=headers, stream=True, timeout=30) as resp:
                        if resp.status_code != 200:
                            logger.debug(f"Mirror returned HTTP {resp.status_code}, trying next mirror...", category="ai")
                            continue

                        content_len = int(resp.headers.get("content-length", 0))
                        file_downloaded = 0
                        start_time = time.time()
                        last_update_time = start_time

                        with open(part_path, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=128 * 1024):
                                if cancel_event.is_set():
                                    break
                                if chunk:
                                    f.write(chunk)
                                    file_downloaded += len(chunk)
                                    downloaded_so_far += len(chunk)

                                    now = time.time()
                                    if now - last_update_time >= 0.2:
                                        elapsed = max(now - start_time, 0.001)
                                        speed_mbps = (file_downloaded / (1024 * 1024)) / elapsed
                                        pct = min(99.0, (downloaded_so_far / total_model_bytes) * 100.0)

                                        self._notify_progress(model_key, {
                                            "model_key": model_key,
                                            "status": "downloading",
                                            "percent": round(pct, 1),
                                            "downloaded_bytes": downloaded_so_far,
                                            "total_bytes": total_model_bytes,
                                            "speed_mbps": round(speed_mbps, 2),
                                            "is_ready": False,
                                            "error": ""
                                        })
                                        last_update_time = now

                        if cancel_event.is_set():
                            break

                        # Validate the size: the whole file as announced by the server (a dropped
                        # connection used to leave a cut-off model marked "ready" that then failed
                        # to load), and at least the expected minimum
                        min_bytes = file_spec.get("expected_min_bytes", 1024)
                        got = os.path.getsize(part_path) if os.path.exists(part_path) else 0
                        encoded = "content-encoding" in {k.lower() for k in resp.headers}
                        if content_len and not encoded and got != content_len:
                            logger.warning(f"{filename}: download incomplete ({got} of {content_len} bytes), trying again...",
                                           category="ai")
                            os.remove(part_path)
                            continue
                        if got >= min_bytes:
                            os.replace(part_path, target_path)
                            file_success = True
                            logger.info(f"Successfully downloaded {filename} ({os.path.getsize(target_path)} bytes)", category="ai")
                            break
                        else:
                            if os.path.exists(part_path):
                                os.remove(part_path)

                except Exception as ex:
                    logger.debug(f"Download attempt failed from {mirror_url}: {ex}", category="ai")
                    if os.path.exists(part_path):
                        try:
                            os.remove(part_path)
                        except Exception:
                            pass

            if cancel_event.is_set():
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass
                logger.info(f"Download of {model_key} was cancelled by user.", category="ai")
                self._notify_progress(model_key, {
                    "model_key": model_key,
                    "status": "not_downloaded",
                    "percent": 0.0,
                    "is_ready": False,
                    "error": "Cancelled"
                })
                with self._lock:
                    self._active_downloads.pop(model_key, None)
                return

            if not file_success:
                logger.error(f"All mirrors exhausted for {filename}.", category="ai")
                self._notify_progress(model_key, {
                    "model_key": model_key,
                    "status": "error",
                    "percent": 0.0,
                    "is_ready": False,
                    "error": f"Failed to download {filename} from all mirrors."
                })
                with self._lock:
                    self._active_downloads.pop(model_key, None)
                return

        # Finished all files successfully
        with self._lock:
            self._active_downloads.pop(model_key, None)

        hw_info = HardwareDetector.get_hardware_info()
        logger.success(f"AI model '{spec['name']}' is ready! Running on: {hw_info['provider_name']}", category="ai")

        self._notify_progress(model_key, {
            "model_key": model_key,
            "status": "ready",
            "percent": 100.0,
            "downloaded_bytes": total_model_bytes,
            "total_bytes": total_model_bytes,
            "speed_mbps": 0.0,
            "is_ready": True,
            "hardware": hw_info["provider_name"],
            "has_gpu": hw_info["has_gpu"],
            "error": ""
        })
