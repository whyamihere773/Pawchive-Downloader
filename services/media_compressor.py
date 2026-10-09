"""
Compressing extracted pictures and videos (Decompressor → "Compress after extracting", off by default).

Each file is written next to the original in the chosen format ("art.png" → "art.webp") and checked; it's
kept only when it's noticeably smaller, otherwise it's thrown away and the original stays as it was.
Originals are never touched here: once everything is done the user is asked whether to move them to the
Recycle Bin.

- Pictures (Pillow): WebP, AVIF or JPG at a quality from 1 to 100. Colour profiles and photo info are
  kept; animated pictures, and transparent ones when the format can't hold transparency, are skipped.
- Videos (ffmpeg): H.265, H.264 or AV1 in an .mp4, at a quality from 1 to 100 (mapped to each codec's CRF).
  A video already in the chosen codec is skipped (it would only lose quality).
"""

import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from core.logger import logger

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".m4v", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".webm"}
IMAGE_FORMATS = {"webp": ".webp", "avif": ".avif", "jpg": ".jpg"}
VIDEO_FORMATS = {"h265": "hevc", "h264": "h264", "av1": "av1"}      # choice -> codec name ffmpeg reports
MIN_SAVING = 0.05            # the new file must be at least 5% smaller to be kept

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class CompressResult:
    compressed: List[Tuple[str, str]] = field(default_factory=list)    # (original, new file)
    bytes_before: int = 0             # of the compressed files' originals
    bytes_after: int = 0
    skipped: int = 0                  # not smaller, already in that format, animated…
    failed: List[str] = field(default_factory=list)

    def merge(self, other: "CompressResult") -> None:
        self.compressed += other.compressed
        self.bytes_before += other.bytes_before
        self.bytes_after += other.bytes_after
        self.skipped += other.skipped
        self.failed += other.failed


@dataclass
class CompressSettings:
    image_format: str = "webp"        # webp | avif | jpg | keep
    image_quality: int = 82
    video_format: str = "h265"        # h265 | h264 | av1 | keep
    video_quality: int = 75
    ffmpeg: str = ""

    @property
    def images_on(self) -> bool:
        return self.image_format in IMAGE_FORMATS

    @property
    def videos_on(self) -> bool:
        return self.video_format in VIDEO_FORMATS and bool(self.ffmpeg)


def video_crf(fmt: str, quality: int) -> int:
    """Quality 1–100 → CRF (lower = better). 75 gives x265 25, x264 22, SVT-AV1 31: hard to tell apart from
    the original at a fraction of the size."""
    q = max(1, min(100, int(quality)))
    if fmt == "h264":
        return round(36 - q * 0.18)       # 100 → 18, 50 → 27
    if fmt == "av1":
        return round(50 - q * 0.25)       # 100 → 25, 50 → 38
    return round(40 - q * 0.2)            # h265: 100 → 20, 50 → 30


def _free_name(folder: str, stem: str, ext: str, original: str) -> str:
    """"art.webp", or "art (2).webp" when that name is taken by another file."""
    cand = os.path.join(folder, stem + ext)
    n = 2
    while os.path.exists(cand) and os.path.normcase(cand) != os.path.normcase(original):
        cand = os.path.join(folder, f"{stem} ({n}){ext}")
        n += 1
    return cand


def _keep_if_smaller(original: str, tmp: str, final: str, result: CompressResult) -> None:
    before, after = os.path.getsize(original), os.path.getsize(tmp)
    if after <= 0 or after > before * (1 - MIN_SAVING):
        os.remove(tmp)
        result.skipped += 1
        return
    os.replace(tmp, final)
    result.compressed.append((original, final))
    result.bytes_before += before
    result.bytes_after += after


# ── Pictures ─────────────────────────────────────────────────────────────────

def compress_image(path: str, fmt: str, quality: int, result: CompressResult) -> None:
    from PIL import Image
    ext = IMAGE_FORMATS[fmt]
    src_ext = os.path.splitext(path)[1].lower()
    if src_ext == ext or (fmt == "jpg" and src_ext == ".jpeg"):
        result.skipped += 1
        return
    folder, name = os.path.split(path)
    final = _free_name(folder, os.path.splitext(name)[0], ext, path)
    tmp = final + ".pawtmp"
    q = max(1, min(100, int(quality)))
    try:
        with Image.open(path) as im:
            if getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1:
                result.skipped += 1
                return
            info = {k: im.info[k] for k in ("icc_profile", "exif") if im.info.get(k)}
            size = im.size
            has_alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
            if fmt == "jpg":
                if has_alpha:
                    result.skipped += 1           # JPG can't keep transparency
                    return
                im = im.convert("RGB") if im.mode != "RGB" else im
                im.save(tmp, "JPEG", quality=q, optimize=True, progressive=True,
                        subsampling=0 if q >= 90 else 2, **info)
            else:
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA" if has_alpha else "RGB")
                if fmt == "webp":
                    im.save(tmp, "WEBP", quality=q, method=6, lossless=q >= 100, **info)
                else:
                    im.save(tmp, "AVIF", quality=q, speed=6, **info)
        with Image.open(tmp) as check:                 # it opens, whole, at the same size
            check.load()
            if check.size != size:
                raise ValueError(f"size changed {size} -> {check.size}")
        _keep_if_smaller(path, tmp, final, result)
    except Exception as e:
        result.failed.append(f"{name}: {e}")
        logger.debug(f"Couldn't compress {path}: {e}", category="decompressor")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ── Videos ───────────────────────────────────────────────────────────────────

def probe_video(ffmpeg: str, path: str) -> Tuple[float, str, str]:
    """(duration in seconds, video codec, audio codec) from ffmpeg's description of the file."""
    try:
        p = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, creationflags=_CREATE_NO_WINDOW)
        text = p.stderr
    except Exception:
        return 0.0, "", ""
    dur = 0.0
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    v = re.search(r"Stream #\S+.*?: Video: (\w+)", text)
    a = re.search(r"Stream #\S+.*?: Audio: (\w+)", text)
    return dur, (v.group(1) if v else ""), (a.group(1) if a else "")


def video_command(ffmpeg: str, src: str, dst: str, fmt: str, quality: int, audio_codec: str) -> List[str]:
    crf = str(video_crf(fmt, quality))
    if fmt == "h264":
        video = ["-c:v", "libx264", "-crf", crf, "-preset", "slow"]
    elif fmt == "av1":
        video = ["-c:v", "libsvtav1", "-crf", crf, "-preset", "6"]
    else:
        video = ["-c:v", "libx265", "-crf", crf, "-preset", "medium", "-tag:v", "hvc1", "-x265-params", "log-level=error"]
    audio = ["-c:a", "copy"] if audio_codec in ("aac", "mp3") else ["-c:a", "aac", "-b:a", "192k"]
    return [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a?", "-sn", "-dn",
            "-map_metadata", "0", *video, "-pix_fmt", "yuv420p", *audio, "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", "-f", "mp4", dst]


def compress_video(ffmpeg: str, path: str, fmt: str, quality: int, result: CompressResult,
                   cancel: Optional[threading.Event] = None,
                   on_progress: Optional[Callable[[float], None]] = None,
                   procs: Optional[set] = None) -> None:
    duration, vcodec, acodec = probe_video(ffmpeg, path)
    if not vcodec or vcodec == VIDEO_FORMATS[fmt]:
        result.skipped += 1                    # not a video ffmpeg can read, or already in that codec
        return
    folder, name = os.path.split(path)
    final = _free_name(folder, os.path.splitext(name)[0], ".mp4", path)
    if os.path.normcase(final) == os.path.normcase(path):
        final = _free_name(folder, os.path.splitext(name)[0] + " (compressed)", ".mp4", path)
    tmp = final + ".pawtmp"
    try:
        proc = subprocess.Popen(video_command(ffmpeg, path, tmp, fmt, quality, acodec), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                errors="replace", creationflags=_CREATE_NO_WINDOW)
    except OSError as e:
        result.failed.append(f"{name}: {e}")
        return
    if procs is not None:
        procs.add(proc)
    err_tail: List[str] = []
    t = threading.Thread(target=lambda: err_tail.extend(proc.stderr.read().splitlines()[-5:]), daemon=True)
    t.start()
    try:
        for line in proc.stdout:
            if cancel is not None and cancel.is_set():
                proc.kill()
                break
            if line.startswith("out_time_us=") and duration > 0 and on_progress:
                try:
                    on_progress(min(99.0, int(line.split("=", 1)[1]) / 1e6 / duration * 100))
                except ValueError:
                    pass
        proc.wait()
        t.join(5)
    finally:
        if procs is not None:
            procs.discard(proc)
    if (cancel is not None and cancel.is_set()) or proc.returncode != 0 or not os.path.exists(tmp):
        if os.path.exists(tmp):
            os.remove(tmp)
        if not (cancel is not None and cancel.is_set()):
            result.failed.append(f"{name}: {' '.join(err_tail)[-200:] or f'ffmpeg exited with {proc.returncode}'}")
        return
    new_dur, new_codec, _ = probe_video(ffmpeg, tmp)
    if not new_codec or (duration > 0 and abs(new_dur - duration) > max(1.0, duration * 0.02)):
        os.remove(tmp)                              # incomplete: never keep a cut-off video
        result.failed.append(f"{name}: the compressed video came out incomplete")
        return
    _keep_if_smaller(path, tmp, final, result)


# ── A folder ─────────────────────────────────────────────────────────────────

def media_files(folder: str, settings: CompressSettings) -> Tuple[List[str], List[str]]:
    images, videos = [], []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if settings.images_on and ext in IMAGE_EXTS:
                images.append(os.path.join(root, f))
            elif settings.videos_on and ext in VIDEO_EXTS:
                videos.append(os.path.join(root, f))
    return images, videos


def compress_folder(folder: str, settings: CompressSettings, cancel: Optional[threading.Event] = None,
                    on_progress: Optional[Callable[[float], None]] = None, workers: int = 0,
                    procs: Optional[set] = None) -> CompressResult:
    """Compresses the pictures and videos in a folder (and its sub-folders). on_progress: 0–100, weighted by
    file size. Pictures are compressed a few at a time; videos one at a time (ffmpeg uses every core)."""
    from concurrent.futures import ThreadPoolExecutor
    result = CompressResult()
    images, videos = media_files(folder, settings)
    sizes = {p: max(1, os.path.getsize(p)) for p in images + videos}
    total = sum(sizes.values()) or 1
    done = [0]
    lock = threading.Lock()

    def finished(p):
        with lock:
            done[0] += sizes[p]
            if on_progress:
                on_progress(done[0] / total * 100)

    def one_image(p):
        if cancel is not None and cancel.is_set():
            return CompressResult()
        r = CompressResult()
        compress_image(p, settings.image_format, settings.image_quality, r)
        finished(p)
        return r

    n = workers or max(1, min(4, (os.cpu_count() or 2) // 2))
    with ThreadPoolExecutor(max_workers=n) as pool:
        for r in pool.map(one_image, images):
            result.merge(r)
    for v in videos:
        if cancel is not None and cancel.is_set():
            break
        base = done[0]

        def part(pct, base=base, v=v):
            if on_progress:
                on_progress((base + sizes[v] * pct / 100) / total * 100)
        compress_video(settings.ffmpeg, v, settings.video_format, settings.video_quality, result, cancel, part, procs)
        finished(v)
    return result
