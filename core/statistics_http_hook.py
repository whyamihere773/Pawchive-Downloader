"""
Statistics Formatting Helpers, Extension Classification & HTTP Telemetry Hook
Decomposed from core/statistics_manager.py to keep modules cohesive and under 1,000 lines.
"""

import datetime
import os
import sys
import threading
from typing import Any, Dict, Optional, Set

import requests


_FALLBACK_CATEGORIES: Dict[str, Set[str]] = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp", ".tiff", ".tif", ".ico", ".svg", ".heic", ".heif", ".jxl", ".psd", ".raw"},
    "videos": {".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv", ".flv", ".m4v", ".ts", ".mpg", ".mpeg", ".3gp", ".ogv"},
    "audio": {".mp3", ".wav", ".flac", ".ogg", ".opus", ".aac", ".m4a", ".wma", ".aiff", ".alac"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", ".cbz", ".cbr", ".iso"},
    "links": {".txt", ".url", ".webloc", ".html", ".htm", ".json", ".md", ".pdf", ".csv"},
}
_EXT_CATEGORY_MAP: Dict[str, str] = {}

_HTTP_HOOK_LOCK = threading.Lock()
_HTTP_HOOK_INSTALLED = False


def _get_ext_category_map() -> Dict[str, str]:
    global _EXT_CATEGORY_MAP
    if _EXT_CATEGORY_MAP:
        return _EXT_CATEGORY_MAP
    try:
        from core.archive_manager import FILE_TYPE_CATEGORIES
        cats = FILE_TYPE_CATEGORIES
    except Exception:
        cats = _FALLBACK_CATEGORIES
    _EXT_CATEGORY_MAP = {
        ext: cat
        for cat, exts in cats.items()
        if cat != "other"
        for ext in exts
    }
    return _EXT_CATEGORY_MAP


def classify_ext(ext: str) -> str:
    """Classify a file extension (with or without leading dot) into a media category."""
    clean = str(ext or "").strip().lower()
    if clean and not clean.startswith("."):
        clean = f".{clean}"
    return _get_ext_category_map().get(clean, "other")


def format_bytes(num_bytes: int, binary: bool = True) -> str:
    """Format an exact byte integer into a readable size string."""
    val = float(max(0, int(num_bytes or 0)))
    step = 1024.0 if binary else 1000.0
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"] if binary else ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while val >= step and idx < len(units) - 1:
        val /= step
        idx += 1
    if idx == 0:
        return f"{int(val):,} B"
    return f"{val:.2f} {units[idx]}"


def format_speed(bps: float) -> str:
    """Format a bytes-per-second throughput rate into a readable speed string."""
    rate = float(max(0.0, bps or 0.0))
    if rate >= 1024.0 * 1024.0 * 1024.0:
        return f"{rate / (1024.0 ** 3):.2f} GiB/s"
    if rate >= 1024.0 * 1024.0:
        return f"{rate / (1024.0 ** 2):.2f} MiB/s"
    if rate >= 1024.0:
        return f"{rate / 1024.0:.1f} KiB/s"
    return f"{int(rate)} B/s"


def format_duration(seconds: float) -> str:
    """Format elapsed seconds into a compact human-readable duration."""
    total = int(max(0, seconds or 0))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _normalize_path_key(path: str) -> str:
    norm = os.path.abspath(os.path.normpath(path))
    return norm.lower() if os.name == "nt" else norm


def _build_body_length(request: requests.PreparedRequest) -> int:
    body = getattr(request, "body", None)
    if body is None:
        return 0
    if isinstance(body, (bytes, bytearray)):
        return len(body)
    if isinstance(body, str):
        return len(body.encode("utf-8", errors="replace"))
    try:
        return len(body)  # file-like or sized sequences
    except Exception:
        pass
    try:
        headers = getattr(request, "headers", None) or {}
        cl = headers.get("Content-Length") or headers.get("content-length")
        if cl is not None:
            return max(0, int(cl))
    except Exception:
        pass
    return 0


def _estimate_request_wire_bytes(request: requests.PreparedRequest) -> int:
    """Estimate outgoing HTTP request wire size (request line + headers + body)."""
    try:
        method = str(getattr(request, "method", "GET") or "GET")
        path_url = str(getattr(request, "path_url", "") or getattr(request, "url", "") or "/")
        base = len(method.encode("latin-1", errors="replace")) + len(path_url.encode("utf-8", errors="replace")) + 12
        headers = getattr(request, "headers", None) or {}
        hdr_bytes = 2
        for k, v in headers.items():
            hdr_bytes += len(str(k).encode("latin-1", errors="replace")) + len(str(v).encode("latin-1", errors="replace")) + 4
        return base + hdr_bytes + _build_body_length(request)
    except Exception:
        return 0


def _estimate_response_header_bytes(resp: requests.Response) -> int:
    """Estimate incoming HTTP status line and response headers size."""
    try:
        hdr_bytes = 18
        headers = getattr(resp, "headers", None) or {}
        for k, v in headers.items():
            hdr_bytes += len(str(k).encode("latin-1", errors="replace")) + len(str(v).encode("latin-1", errors="replace")) + 4
        return hdr_bytes
    except Exception:
        return 0




def install_http_instrumentation(manager: Optional[Any] = None) -> bool:
    """
    Wrap `requests.Session.send` once (idempotently) to measure exact HTTP upload bytes,
    non-streamed response bytes, and HTTP status counters.
    Streamed response payloads are measured chunk-by-chunk in `bandwidth_limiter.wait_for`.
    """
    global _HTTP_HOOK_INSTALLED
    if manager is not None:
        target_mgr = manager
    else:
        _mod = sys.modules.get('core.statistics_manager')
        target_mgr = getattr(_mod, 'statistics_manager', None)
    if target_mgr is None:
        return False
    with _HTTP_HOOK_LOCK:
        if _HTTP_HOOK_INSTALLED or getattr(requests.Session.send, "_pawchive_stats_wrapped", False):
            return False

        orig_send = requests.Session.send

        def _instrumented_send(self, request, **kwargs):
            req_bytes = _estimate_request_wire_bytes(request)
            if req_bytes > 0:
                target_mgr.record_upload(req_bytes)

            resp = orig_send(self, request, **kwargs)
            try:
                status = int(getattr(resp, "status_code", 0) or 0)
                target_mgr.record_http_request(status)
                hdr_bytes = _estimate_response_header_bytes(resp)
                is_stream = bool(kwargs.get("stream", False))
                body_bytes = 0
                if not is_stream:
                    cl_raw = None
                    try:
                        cl_raw = resp.headers.get("Content-Length") or resp.headers.get("content-length")
                    except Exception:
                        cl_raw = None
                    if cl_raw is not None:
                        try:
                            body_bytes = max(0, int(cl_raw))
                        except (TypeError, ValueError):
                            body_bytes = 0
                    if body_bytes <= 0:
                        raw_content = getattr(resp, "_content", None)
                        if isinstance(raw_content, (bytes, bytearray)):
                            body_bytes = len(raw_content)
                total_down = hdr_bytes + body_bytes
                if total_down > 0:
                    target_mgr.record_download(total_down, category="api")
            except Exception:
                pass
            return resp

        _instrumented_send._pawchive_stats_wrapped = True
        requests.Session.send = _instrumented_send
        _HTTP_HOOK_INSTALLED = True
        return True
