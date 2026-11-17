"""
In-App Browser Media Cache & Range Streaming Proxy (`BrowserMediaService`).

Enables native, reliable in-app viewing of remote pictures, animated GIFs/WebPs/AVIFs,
videos, and audio in `BrowserView` / `MediaLightboxModal` without launching any external browser:

1. Pictures & Animated Images -> Async LRU disk preview cache (`<temp>/pawchive_browser_media_<pid>`)
   with automatic Pawchive `n1`–`n4` node failover, provider `Referer`/`User-Agent`/`Cookie`
   headers, and magic-byte extension detection so `AnimatedImage` + `FullImageProvider` +
   `AnimatedMedia` decode every format cleanly offline/online.
2. Videos & Audio -> Lazily started loopback `127.0.0.1` HTTP Range-capable proxy so Qt
   `MediaPlayer` (FFmpeg backend) seeks/scrubs smoothly over upstream CDNs with full header,
   cookie, and node-fallback support.
"""

from __future__ import annotations

import atexit
import hashlib
import os
import re
import shutil
import tempfile
import threading
import time
import urllib.parse
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, List, Optional, Tuple

import requests

from core.logger import logger
from core.providers import cookie_for_url

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_PAWCHIVE_UA = "PawchiveDownloader/1.3.5 (https://github.com/whyamihere773/Pawchive-Downloader)"
_CONTACT_HEADERS = {
    "X-Contact": "https://github.com/whyamihere773/Pawchive-Downloader",
    "X-Client-Notice": (
        "Pawchive Downloader user here! Love your site. If my client is ever causing server strain, "
        "please open an issue on GitHub instead of a hard ban and I'll fix my request pacing immediately."
    ),
}

_MAX_IMAGE_BYTES = 100 * 1024 * 1024  # 100 MB cap for in-app lightbox image/GIF prefetch
_CACHE_MAX_BYTES = 350 * 1024 * 1024  # 350 MB rolling LRU preview budget
_CACHE_MAX_ITEMS = 120

_CTYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/apng": ".apng",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/flac": ".flac",
}


def _detect_magic_ext(head: bytes) -> str:
    if not head:
        return ""
    if head.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head.startswith(b"BM"):
        return ".bmp"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"avif", b"avis"):
            return ".avif"
        if brand in (b"heic", b"heix", b"mif1"):
            return ".heic"
    return ""


def _url_hint_ext(url: str) -> str:
    clean = (url or "").split("#", 1)[0]
    path_ext = os.path.splitext(clean.split("?", 1)[0])[1].lower()
    if path_ext and len(path_ext) <= 6:
        return path_ext
    if "?" in clean:
        try:
            qs = urllib.parse.parse_qs(clean.split("?", 1)[1])
            for k in ("f", "filename", "file", "name"):
                vals = qs.get(k)
                if vals and vals[0]:
                    qext = os.path.splitext(vals[0])[1].lower()
                    if qext and len(qext) <= 6:
                        return qext
        except Exception:
            pass
    return ""


def candidate_urls(url: str) -> List[str]:
    """Produces ordered failover candidates (e.g., Pawchive n1..n4 node rotation)."""
    u = (url or "").strip()
    if not u:
        return []
    u = u.replace("e1.cum.st", "cdn.cum.st")
    candidates = [u]
    m = re.match(r"^(https?://)n(\d+)\.(pawchive\.pw)(/.*)$", u, re.IGNORECASE)
    if m:
        scheme, cur_node, domain, rest = m.groups()
        for alt in ("1", "2", "3", "4"):
            if alt != cur_node:
                candidates.append(f"{scheme}n{alt}.{domain}{rest}")
    return candidates


def build_request_headers(url: str, provider_id: str = "") -> Dict[str, str]:
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    low = (url or "").lower()
    pid = (provider_id or "").lower()
    if "coomerfans" in low or pid == "coomerfans":
        headers["Referer"] = "https://coomerfans.com/"
        headers["Origin"] = "https://coomerfans.com"
    elif "pawchive" in low or pid == "pawchive":
        # Pawchive CDN (n1-n4/t1-t4) blocks spoofed bare Chrome UAs with 403 and expects
        # our identifiable downloader User-Agent + contact headers.
        headers["User-Agent"] = _PAWCHIVE_UA
        headers["Referer"] = "https://pawchive.pw/"
        headers.update(_CONTACT_HEADERS)
    elif "cum.st" in low or pid == "cumst":
        headers["Referer"] = "https://cum.st/"

    cookie = cookie_for_url(url)
    if cookie:
        headers["Cookie"] = cookie
    return headers


_candidate_urls = candidate_urls
_build_request_headers = build_request_headers


class BrowserMediaService:
    """
    Shared media fetcher + LRU preview cache + localhost Range streaming proxy
    used by `BrowserBridge`. Thread-safe and cleaned up automatically on exit.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._cache_dir = os.path.join(tempfile.gettempdir(), f"pawchive_browser_media_{os.getpid()}")
        self._lru: OrderedDict[str, Tuple[str, int]] = OrderedDict()  # orig_url -> (local_path, size_bytes)
        self._lru_total_bytes: int = 0
        self._inflight: Dict[str, List[Callable[[str, str, str], None]]] = {}

        # Proxy state (started lazily only on first video/audio stream request)
        self._stream_map: Dict[str, Tuple[str, str]] = {}  # token -> (orig_url, provider_id)
        self._url_to_token: Dict[str, str] = {}
        self._server: Optional[ThreadingHTTPServer] = None
        self._server_port: int = 0
        self._closed: bool = False

        self._session = requests.Session()
        atexit.register(self.shutdown)

    def _ensure_cache_dir(self) -> None:
        os.makedirs(self._cache_dir, exist_ok=True)

    def get_cached_path(self, url: str) -> str:
        clean = (url or "").strip()
        if not clean:
            return ""
        with self._lock:
            entry = self._lru.get(clean)
            if entry:
                fpath, _ = entry
                if os.path.isfile(fpath) and os.path.getsize(fpath) > 0:
                    self._lru.move_to_end(clean)
                    return fpath
                # Stale record
                self._remove_lru_locked(clean)
        return ""

    def _remove_lru_locked(self, key: str) -> None:
        entry = self._lru.pop(key, None)
        if not entry:
            return
        fpath, sz = entry
        self._lru_total_bytes = max(0, self._lru_total_bytes - sz)
        try:
            if fpath and os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass

    def _record_lru(self, key: str, local_path: str, size_bytes: int) -> None:
        with self._lock:
            if key in self._lru:
                self._remove_lru_locked(key)
            self._lru[key] = (local_path, size_bytes)
            self._lru_total_bytes += size_bytes
            while (len(self._lru) > _CACHE_MAX_ITEMS or self._lru_total_bytes > _CACHE_MAX_BYTES) and len(self._lru) > 1:
                oldest_key, _ = next(iter(self._lru.items()))
                if oldest_key == key:
                    break
                self._remove_lru_locked(oldest_key)

    def fetch_image_async(
        self,
        url: str,
        provider_id: str,
        callback: Callable[[str, str, str], None],
    ) -> Optional[str]:
        """
        Returns cached local path synchronously if already present; otherwise schedules an
        async background download and calls `callback(orig_url, local_path, error_str)`.
        """
        clean = (url or "").strip()
        if not clean:
            return None
        cached = self.get_cached_path(clean)
        if cached:
            return cached

        should_spawn = False
        with self._lock:
            if clean in self._inflight:
                self._inflight[clean].append(callback)
            else:
                self._inflight[clean] = [callback]
                should_spawn = True

        if not should_spawn:
            return None

        def _worker():
            local_path, err = self._download_to_cache(clean, provider_id)
            with self._lock:
                cbs = self._inflight.pop(clean, [])
            for cb in cbs:
                try:
                    cb(clean, local_path, err)
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True, name="BrowserImageCacheWorker").start()
        return None

    def _download_to_cache(self, url: str, provider_id: str) -> Tuple[str, str]:
        self._ensure_cache_dir()
        candidates = _candidate_urls(url)
        digest = hashlib.sha256(url.encode("utf-8", errors="ignore")).hexdigest()[:24]
        last_err = "Failed to load media"

        for cand in candidates:
            if self._closed:
                return "", "Cancelled"
            tmp_path = os.path.join(self._cache_dir, f"{digest}_{threading.get_ident()}.part")
            try:
                resp = self._session.get(
                    cand,
                    headers=_build_request_headers(cand, provider_id),
                    stream=True,
                    timeout=(10, 25),
                )
                if resp.status_code >= 400:
                    last_err = f"HTTP {resp.status_code}"
                    resp.close()
                    continue

                ctype = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                if ctype.startswith("text/html"):
                    last_err = "Upstream returned HTML instead of media"
                    resp.close()
                    continue

                first_chunk = b""
                total_written = 0
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if self._closed:
                            raise RuntimeError("Service shutting down")
                        if not chunk:
                            continue
                        if not first_chunk:
                            first_chunk = bytes(chunk[:32])
                        total_written += len(chunk)
                        if total_written > _MAX_IMAGE_BYTES:
                            raise RuntimeError("Preview image exceeds 100 MB limit")
                        f.write(chunk)
                resp.close()

                if total_written <= 0:
                    last_err = "Empty response"
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    continue

                ext = _detect_magic_ext(first_chunk) or _CTYPE_TO_EXT.get(ctype, "") or _url_hint_ext(cand) or ".bin"
                final_path = os.path.join(self._cache_dir, f"{digest}{ext}")
                os.replace(tmp_path, final_path)
                self._record_lru(url, final_path, total_written)
                return final_path, ""
            except Exception as e:
                last_err = str(e)
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass

        logger.debug(f"[BrowserMediaService] Image prefetch failed for {url}: {last_err}", category="network")
        return "", last_err

    # ── Loopback Range Streaming Proxy (Video & Audio) ──────────────────────

    def _ensure_proxy_running(self) -> int:
        with self._lock:
            if self._server is not None and self._server_port > 0:
                return self._server_port

            service = self

            class _StreamHandler(BaseHTTPRequestHandler):
                protocol_version = "HTTP/1.1"

                def log_message(self, format, *args):
                    # Silence noisy HTTP access logs on stdout
                    return

                def do_HEAD(self):
                    self._handle_proxy(head_only=True)

                def do_GET(self):
                    self._handle_proxy(head_only=False)

                def _handle_proxy(self, head_only: bool):
                    token = urllib.parse.urlparse(self.path).path.rsplit("/", 1)[-1]
                    token_clean = os.path.splitext(token)[0]
                    entry = service.lookup_stream(token_clean)
                    if not entry:
                        self.send_error(404, "Stream token not found")
                        return
                    orig_url, prov_id = entry
                    req_range = self.headers.get("Range")
                    candidates = _candidate_urls(orig_url)
                    upstream_resp = None
                    last_status = 502

                    for cand in candidates:
                        try:
                            hdrs = _build_request_headers(cand, prov_id)
                            if req_range:
                                hdrs["Range"] = req_range
                            r = service._session.request(
                                "HEAD" if head_only else "GET",
                                cand,
                                headers=hdrs,
                                stream=not head_only,
                                timeout=(10, 30),
                                allow_redirects=True,
                            )
                            if r.status_code in (200, 206):
                                upstream_resp = r
                                break
                            last_status = r.status_code
                            r.close()
                        except Exception:
                            continue

                    if upstream_resp is None:
                        self.send_error(last_status, "Upstream stream unavailable")
                        return

                    try:
                        self.send_response(upstream_resp.status_code)
                        for h_name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "ETag"):
                            h_val = upstream_resp.headers.get(h_name)
                            if h_val:
                                self.send_header(h_name, h_val)
                        if "Accept-Ranges" not in upstream_resp.headers:
                            self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Connection", "close")
                        self.end_headers()

                        if not head_only:
                            for chunk in upstream_resp.iter_content(chunk_size=65536):
                                if service._closed:
                                    break
                                if chunk:
                                    self.wfile.write(chunk)
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
                        # Normal when Qt MediaPlayer seeks or closes mid-stream
                        pass
                    finally:
                        try:
                            upstream_resp.close()
                        except Exception:
                            pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), _StreamHandler)
            server.daemon_threads = True
            self._server = server
            self._server_port = int(server.server_address[1])
            threading.Thread(target=server.serve_forever, daemon=True, name="BrowserMediaProxy").start()
            return self._server_port

    def lookup_stream(self, token: str) -> Optional[Tuple[str, str]]:
        with self._lock:
            return self._stream_map.get(token)

    def register_stream(self, url: str, provider_id: str = "", suggested_ext: str = "") -> str:
        clean = (url or "").strip()
        if not clean:
            return ""
        if not clean.lower().startswith(("http://", "https://")):
            return clean
        ext = (suggested_ext or _url_hint_ext(clean) or ".mp4").lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        # HLS playlists rely on relative segment resolution against their CDN base URL; stream directly
        if ext == ".m3u8":
            return clean

        port = self._ensure_proxy_running()
        key = f"{provider_id}:{clean}"
        with self._lock:
            token = self._url_to_token.get(key)
            if not token:
                token = hashlib.sha256(key.encode("utf-8", errors="ignore")).hexdigest()[:24]
                self._url_to_token[key] = token
                self._stream_map[token] = (clean, provider_id or "")
        return f"http://127.0.0.1:{port}/stream/{token}{ext}"

    def shutdown(self) -> None:
        self._closed = True
        srv = None
        with self._lock:
            srv = self._server
            self._server = None
            self._server_port = 0
            self._lru.clear()
            self._lru_total_bytes = 0
        if srv is not None:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass
        if os.path.isdir(self._cache_dir):
            try:
                shutil.rmtree(self._cache_dir, ignore_errors=True)
            except Exception:
                pass
