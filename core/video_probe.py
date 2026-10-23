"""
Video Duration Prober
Probes and extracts video durations using:
1. Fast in-memory LRU caching
2. Lightweight HTTP Range requests + pure Python MP4/MOV container atom parsing (takes ~50-150ms, <128KB)
3. FFmpeg header probing fallback for WebM/MKV or end-of-file moov atoms
4. yt-dlp metadata extraction for embedded video players
"""

import io
import re
import struct
import subprocess
import threading
import requests
from typing import Optional, Dict
from core.logger import logger
from services.ffmpeg_manager import find_ffmpeg

# Thread-safe in-memory cache: URL/path -> duration in seconds
_CACHE_LOCK = threading.Lock()
_DURATION_CACHE: Dict[str, Optional[float]] = {}
_MAX_CACHE_SIZE = 5000


def _parse_duration_from_ffmpeg_output(output: str) -> Optional[float]:
    """Extracts duration in seconds from ffmpeg text output (e.g. Duration: 00:02:15.30)."""
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    if not m:
        return None
    hours, minutes, seconds = m.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def extract_mp4_duration(data: bytes) -> Optional[float]:
    """
    Parses MP4/MOV container bytes (e.g. first 128KB via HTTP Range request)
    and extracts video duration in seconds from the mvhd FullBox.
    """
    if not data or len(data) < 16:
        return None

    # Fast scan for b"mvhd" inside data
    idx = data.find(b"mvhd")
    if idx != -1 and len(data) >= idx + 24:
        payload = data[idx + 4:]
        if len(payload) >= 20:
            v_flags = struct.unpack(">I", payload[:4])[0]
            v = (v_flags >> 24) & 0xFF
            if v == 0 and len(payload) >= 20:
                timescale, duration = struct.unpack(">II", payload[12:20])
                if timescale > 0:
                    return duration / timescale
            elif v == 1 and len(payload) >= 32:
                timescale, duration = struct.unpack(">IQ", payload[20:32])
                if timescale > 0:
                    return duration / timescale

    # Fallback box tree traversal
    stream = io.BytesIO(data)
    try:
        while True:
            header = stream.read(8)
            if len(header) < 8:
                break
            size, btype = struct.unpack(">I4s", header)
            if size == 1:
                ext = stream.read(8)
                if len(ext) < 8:
                    break
                size = struct.unpack(">Q", ext)[0]
                payload_len = size - 16
            elif size == 0:
                payload_len = -1
            else:
                payload_len = size - 8

            if btype == b"moov":
                sub_data = stream.read(payload_len) if payload_len > 0 else stream.read()
                sub_stream = io.BytesIO(sub_data)
                while True:
                    sh = sub_stream.read(8)
                    if len(sh) < 8:
                        break
                    ssz, sbt = struct.unpack(">I4s", sh)
                    if sbt == b"mvhd":
                        p = sub_stream.read(ssz - 8)
                        v_flags = struct.unpack(">I", p[:4])[0]
                        v = (v_flags >> 24) & 0xFF
                        if v == 0 and len(p) >= 20:
                            timescale, duration = struct.unpack(">II", p[12:20])
                            if timescale > 0:
                                return duration / timescale
                        elif v == 1 and len(p) >= 32:
                            timescale, duration = struct.unpack(">IQ", p[20:32])
                            if timescale > 0:
                                return duration / timescale
                    else:
                        sub_stream.seek(ssz - 8, io.SEEK_CUR)
            else:
                if payload_len > 0:
                    stream.seek(payload_len, io.SEEK_CUR)
                else:
                    break
    except Exception:
        pass

    return None


class VideoProbe:
    """Thread-safe prober for direct video files and streams."""

    @classmethod
    def get_cached_duration(cls, key: str) -> Optional[float]:
        with _CACHE_LOCK:
            return _DURATION_CACHE.get(key)

    @classmethod
    def set_cached_duration(cls, key: str, duration: Optional[float]):
        with _CACHE_LOCK:
            if len(_DURATION_CACHE) >= _MAX_CACHE_SIZE:
                _DURATION_CACHE.clear()
            _DURATION_CACHE[key] = duration

    @classmethod
    def probe_http_range(cls, url: str, session: Optional[requests.Session] = None,
                         headers: Optional[dict] = None, timeout: float = 6.0) -> Optional[float]:
        """
        Requests the first 128KB of a video URL using HTTP Range and parses the MP4/MOV header.
        """
        sess = session or requests
        req_headers = dict(headers or {})
        req_headers["Range"] = "bytes=0-131071"  # 128 KB
        try:
            resp = sess.get(url, headers=req_headers, timeout=timeout, stream=True)
            if resp.status_code in (200, 206):
                chunk = resp.raw.read(131072)
                return extract_mp4_duration(chunk)
        except Exception as e:
            logger.debug(f"HTTP Range probe failed for {url}: {e}", category="video_probe")
        return None

    @classmethod
    def probe_ffmpeg(cls, target: str, timeout: float = 5.0) -> Optional[float]:
        """Probes a local file or remote URL using ffmpeg."""
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            return None
        try:
            cmd = [ffmpeg, "-hide_banner", "-i", target]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, errors="replace", timeout=timeout)
            return _parse_duration_from_ffmpeg_output(proc.stderr)
        except Exception as e:
            logger.debug(f"FFmpeg probe failed for {target}: {e}", category="video_probe")
            return None

    @classmethod
    def probe_ytdlp(cls, url: str, timeout: float = 8.0) -> Optional[float]:
        """Probes an embedded video player (YouTube, Vimeo, Streamable, etc.) using yt-dlp."""
        import json
        import shutil
        from core.path_utils import resolve_bundled_ytdlp
        ytdlp_bin = resolve_bundled_ytdlp() or shutil.which("yt-dlp")
        if not ytdlp_bin:
            return None
        try:
            cmd = [ytdlp_bin, "--dump-json", "--skip-download", "--no-warnings", url]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, errors="replace", timeout=timeout)
            if proc.returncode == 0 and proc.stdout:
                data = json.loads(proc.stdout)
                dur = data.get("duration")
                if dur is not None and isinstance(dur, (int, float)) and dur > 0:
                    return float(dur)
        except Exception as e:
            logger.debug(f"yt-dlp probe failed for {url}: {e}", category="video_probe")
        return None

    @classmethod
    def get_video_duration(cls, url_or_path: str, session: Optional[requests.Session] = None,
                           headers: Optional[dict] = None, timeout: float = 6.0) -> Optional[float]:
        """
        Unified duration prober. Checks cache first, then attempts range probe, ffmpeg, or yt-dlp.
        Returns duration in seconds, or None if undetermined.
        """
        if not url_or_path:
            return None

        # Clean key
        cache_key = url_or_path.split("?")[0]
        with _CACHE_LOCK:
            if cache_key in _DURATION_CACHE:
                return _DURATION_CACHE[cache_key]

        duration = None

        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            # 1. Fast HTTP Range header probe
            duration = cls.probe_http_range(url_or_path, session=session, headers=headers, timeout=timeout)

            # 2. Fallback to FFmpeg if range probe didn't find mvhd atom
            if duration is None:
                duration = cls.probe_ffmpeg(url_or_path, timeout=timeout)

            # 3. If still None and looks like an embed, try yt-dlp
            if duration is None and any(d in url_or_path.lower() for d in ("youtube.com", "youtu.be", "vimeo.com", "streamable.com", "redgifs.com")):
                duration = cls.probe_ytdlp(url_or_path, timeout=timeout + 2.0)
        else:
            # Local file
            import os
            if os.path.exists(url_or_path):
                try:
                    with open(url_or_path, "rb") as f:
                        header = f.read(131072)
                        duration = extract_mp4_duration(header)
                except Exception:
                    pass
                if duration is None:
                    duration = cls.probe_ffmpeg(url_or_path, timeout=timeout)

        cls.set_cached_duration(cache_key, duration)
        return duration
