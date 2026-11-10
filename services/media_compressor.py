"""
Compressing extracted pictures and videos (Decompressor → "Compress after extracting", off by default).

Each file is written next to the original in the chosen format ("art.png" → "art.webp") and checked; it's
kept only when it's noticeably smaller, otherwise it's thrown away and the original stays as it was.
Originals are never touched here: once everything is done the user is asked whether to move them to the
Recycle Bin.

- Pictures (Pillow): JPG, PNG, WebP or AVIF at a quality from 1 to 100 (PNG: lossless from 90, fewer
  colours below). Colour profiles and photo info are kept; transparent pictures are skipped for JPG.
- Animated pictures (their own setting): GIF, APNG, animated WebP and AVIF stay animated, in their own format
  or as another animated one. Every frame, the timing and transparency are checked before a copy is kept.
- Videos (ffmpeg): H.265, H.264 or AV1 in an .mp4, or H.265 in an .mkv (keeps every audio track, subtitles
  and attached fonts), at a quality from 1 to 100 (mapped to each codec's CRF). A video already in the
  chosen codec is skipped (it would only lose quality).
"""

import os
import re
import shlex
import tempfile
import time
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from core.logger import logger

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
GIF_EXTS = {".gif"}
# Animated pictures (their own setting): GIF, animated PNG (APNG), animated WebP, animated AVIF. An animation is
# never turned into a still picture: it stays in its format or becomes another animated one.
ANIMATED_EXTS = {".gif", ".png", ".apng", ".webp", ".avif"}
ANIMATED_FORMATS = {"gif": ".gif", "png": ".png", "webp": ".webp", "avif": ".avif"}   # + "same" / "keep"
ANIMATION_MEMORY_LIMIT = 1_200_000_000   # frames x width x height x 4 bytes: bigger ones are left alone
VIDEO_EXTS = {".mp4", ".m4v", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".webm"}
IMAGE_FORMATS = {"jpg": ".jpg", "png": ".png", "webp": ".webp", "avif": ".avif"}
VIDEO_FORMATS = {"h265": "hevc", "h264": "h264", "mkv": "hevc", "av1": "av1"}   # choice -> codec ffmpeg reports
VIDEO_EXTS_OUT = {"h265": ".mp4", "h264": ".mp4", "mkv": ".mkv", "av1": ".mp4"}
MIN_SAVING = 0.05            # the new file must be at least 5% smaller to be kept

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_BELOW_NORMAL_PRIORITY = 0x00004000 if sys.platform == "win32" else 0


def get_safe_encoder_threads() -> int:
    """Number of CPU threads to allocate for software encoding so that at least
    1-2 logical cores remain completely free for Qt UI and the OS."""
    c = os.cpu_count() or 4
    if c <= 2:
        return 1
    elif c <= 4:
        return max(1, c - 1)
    else:
        return max(2, min(c - 2, 16))


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
    video_format: str = "h265"        # h265 | h264 | mkv | av1 | keep
    video_quality: int = 75
    video_hwaccel: str = "auto"       # auto | nvenc | qsv | amf | cpu
    video_preset: str = "auto"        # auto | fast | balanced | quality | custom
    audio_codec: str = "auto"         # auto | copy | aac | opus
    custom_video_args: str = ""       # extra user-supplied ffmpeg parameters
    animated_format: str = "same"     # same | gif | png | webp | avif | keep
    animated_quality: int = 82
    ffmpeg: str = ""

    @property
    def images_on(self) -> bool:
        return self.image_format in IMAGE_FORMATS

    @property
    def animated_on(self) -> bool:
        return self.animated_format == "same" or self.animated_format in ANIMATED_FORMATS

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


_reserved: set = set()                 # names being written right now (pictures are compressed in parallel)
_reserved_lock = threading.Lock()
_calls = threading.local()             # names reserved by the compress call running on this thread


def _releases_names(fn):
    """The names a compress call reserved are released when it ends, however it ends."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        outer = getattr(_calls, "names", None)
        _calls.names = []
        try:
            return fn(*args, **kwargs)
        finally:
            for name in _calls.names:
                _release(name)
            _calls.names = outer
    return wrapper


def _free_name(folder: str, stem: str, ext: str, original: str) -> str:
    """"art.webp", or "art (2).webp" when that name is taken by another file, or is being written for another
    file at this moment ("art.gif" and "art.avif" both becoming "art.png"). Release it with _release()."""
    with _reserved_lock:
        cand = os.path.join(folder, stem + ext)
        n = 2
        while (os.path.exists(cand) and os.path.normcase(cand) != os.path.normcase(original))                 or os.path.normcase(cand) in _reserved:
            cand = os.path.join(folder, f"{stem} ({n}){ext}")
            n += 1
        _reserved.add(os.path.normcase(cand))
    if getattr(_calls, "names", None) is not None:
        _calls.names.append(cand)
    return cand


def _release(name: str) -> None:
    with _reserved_lock:
        _reserved.discard(os.path.normcase(name))


def frame_durations(im) -> List[int]:
    """Each frame's display time in ms. Every frame is decoded first: WebP and AVIF only set a frame's time when
    it's decoded, and until then still show the previous frame's."""
    out = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        im.load()
        out.append(max(10, int(round(float(im.info.get("duration") or 100)))))
    im.seek(0)
    return out


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

def _png_palette(im, q: int):
    """Below quality 90 a PNG keeps fewer colours (like pngquant): far smaller for drawings."""
    from PIL import Image
    colors = 256 if q >= 60 else (128 if q >= 40 else 64)
    rgba = im.convert("RGBA")
    return rgba.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)


def _gif_frame(frame, colors: int):
    """A frame with fewer colours that keeps its transparent pixels (their own palette entry)."""
    from PIL import Image
    rgba = frame.convert("RGBA")
    alpha = rgba.getchannel("A")
    dither = Image.Dither.FLOYDSTEINBERG
    if alpha.getextrema()[0] >= 128:
        return rgba.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=dither)
    q = rgba.convert("RGB").quantize(colors=colors - 1, method=Image.Quantize.MEDIANCUT, dither=dither)
    pal = (q.getpalette() or [])[: (colors - 1) * 3]
    pal += [0] * ((colors - 1) * 3 - len(pal)) + [0, 0, 0]
    q.putpalette(pal)
    q.paste(colors - 1, mask=alpha.point(lambda v: 255 if v < 128 else 0))
    q.info["transparency"] = colors - 1
    return q


def _shared_palette_frames(frames, colors: int):
    """Frames with fewer colours that all use ONE palette (animated PNG allows only one), built from a sample
    of frames across the animation; transparent pixels get their own palette entry. Not dithered: dither noise
    differs in every frame, which made animations several times bigger."""
    from PIL import Image
    rgba = [f.convert("RGBA") for f in frames]
    has_alpha = any(f.getchannel("A").getextrema()[0] < 128 for f in rgba)
    n_col = colors - 1 if has_alpha else colors
    sample = rgba[:: max(1, len(rgba) // 16)][:16]
    w = min(256, sample[0].width)
    thumbs = [f.convert("RGB").resize((w, max(1, round(f.height * w / f.width)))) for f in sample]
    montage = Image.new("RGB", (w, sum(t.height for t in thumbs)))
    y = 0
    for t in thumbs:
        montage.paste(t, (0, y))
        y += t.height
    palette = montage.quantize(colors=n_col, method=Image.Quantize.MEDIANCUT)
    pal = (palette.getpalette() or [])[: n_col * 3]
    pal += [0] * (n_col * 3 - len(pal))
    out = []
    for f in rgba:
        q = f.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
        if has_alpha:
            q.putpalette(pal + [0, 0, 0])
            q.paste(n_col, mask=f.getchannel("A").point(lambda v: 255 if v < 128 else 0))
            q.info["transparency"] = n_col
        out.append(q)
    return out


def _same_transparency(a, b, n: int) -> bool:
    """The transparent areas of the first, middle and last frame match (within 0.5% of the pixels)."""
    from PIL import ImageChops
    for idx in sorted({0, n // 2, n - 1}):
        a.seek(idx)
        b.seek(idx)
        aa, bb = a.convert("RGBA").getchannel("A"), b.convert("RGBA").getchannel("A")
        off = ImageChops.difference(aa, bb).point(lambda v: 255 if v > 128 else 0).histogram()[255]
        if off > aa.size[0] * aa.size[1] * 0.005:
            return False
    return True


@_releases_names
def compress_gif(path: str, quality: int, result: CompressResult) -> None:
    """A GIF stays a GIF (still or animated): every frame, its timing, the looping and transparency are kept.
    From quality 90 it's re-saved without loss; below, the frames use fewer colours."""
    from PIL import Image, ImageSequence
    folder, name = os.path.split(path)
    final = _free_name(folder, os.path.splitext(name)[0] + " (compressed)", ".gif", path)
    tmp = final + ".pawtmp"
    q = max(1, min(100, int(quality)))
    try:
        with Image.open(path) as im:
            size = im.size
            n = getattr(im, "n_frames", 1)
            loop = im.info.get("loop")
            durations = frame_durations(im)
            extra = {"loop": loop} if loop is not None else {}
            if n > 1:
                extra["duration"] = durations
            if q >= 90:
                im.save(tmp, "GIF", save_all=n > 1, optimize=True, **extra)
            else:
                colors = 128 if q >= 60 else (64 if q >= 40 else 32)
                frames = [_gif_frame(f, colors) for f in ImageSequence.Iterator(im)]
                frames[0].save(tmp, "GIF", save_all=n > 1, append_images=frames[1:], optimize=True,
                               disposal=2, **extra)
        with Image.open(tmp) as check, Image.open(path) as orig:
            if check.size != size or getattr(check, "n_frames", 1) != n:
                raise ValueError("the GIF came out with a different size or number of frames")
            if not _same_transparency(orig, check, n):
                raise ValueError("the GIF's transparent areas changed")
        _keep_if_smaller(path, tmp, final, result)
    except Exception as e:
        result.failed.append(f"{name}: {e}")
        logger.debug(f"Couldn't compress {path}: {e}", category="decompressor")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def is_animated_file(path: str) -> bool:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return bool(getattr(im, "is_animated", False)) and getattr(im, "n_frames", 1) > 1
    except Exception:
        return False


@_releases_names
def compress_animated(path: str, target: str, quality: int, result: CompressResult) -> None:
    """An animated picture (or any GIF), kept animated: in its own format ("same") or as an animated GIF, PNG
    (APNG), WebP or AVIF. Every frame, the frame timing and transparency are checked before it's kept."""
    from PIL import Image, ImageSequence
    src_ext = os.path.splitext(path)[1].lower()
    src_kind = ".png" if src_ext == ".apng" else src_ext
    out_ext = src_kind if target == "same" else ANIMATED_FORMATS[target]
    if out_ext == ".gif" and src_ext == ".gif":
        compress_gif(path, quality, result)          # GIF → GIF (also still GIFs: a GIF stays a GIF)
        return
    folder, name = os.path.split(path)
    same = out_ext == src_kind
    final = _free_name(folder, os.path.splitext(name)[0] + (" (compressed)" if same else ""), out_ext, path)
    tmp = final + ".pawtmp"
    q = max(1, min(100, int(quality)))
    try:
        with Image.open(path) as im:
            n = getattr(im, "n_frames", 1)
            if not getattr(im, "is_animated", False) or n < 2:
                result.skipped += 1                  # a still picture: the Pictures setting's job
                return
            size = im.size
            if n * size[0] * size[1] * 4 > ANIMATION_MEMORY_LIMIT:
                result.skipped += 1
                logger.debug(f"{name}: {n} frames at {size[0]}x{size[1]} is too big to compress safely; left alone.",
                             category="decompressor")
                return
            durations = frame_durations(im)
            loop = int(im.info.get("loop", 0) or 0)
            if out_ext == ".gif":
                colors = 256 if q >= 90 else (128 if q >= 60 else (64 if q >= 40 else 32))
                frames = [_gif_frame(f, colors) for f in ImageSequence.Iterator(im)]
                frames[0].save(tmp, "GIF", save_all=True, append_images=frames[1:], duration=durations, loop=loop,
                               optimize=True, disposal=2)
            elif out_ext == ".png":
                # Lossless first (without the alpha channel when nothing is transparent); below quality 90 a
                # version with fewer colours is tried too, and the smaller one is kept
                frames = [f.convert("RGBA") for f in ImageSequence.Iterator(im)]
                opaque = all(f.getchannel("A").getextrema()[0] == 255 for f in frames)
                full = [f.convert("RGB") for f in frames] if opaque else frames
                full[0].save(tmp, "PNG", save_all=True, append_images=full[1:], duration=durations, loop=loop,
                             optimize=True)
                if q < 90:
                    alt = tmp + "2"
                    pal = _shared_palette_frames(frames, 256 if q >= 60 else (128 if q >= 40 else 64))
                    pal[0].save(alt, "PNG", save_all=True, append_images=pal[1:], duration=durations, loop=loop,
                                optimize=True)
                    if os.path.getsize(alt) < os.path.getsize(tmp):
                        os.replace(alt, tmp)
                    else:
                        os.remove(alt)
            elif out_ext == ".webp":
                frames = [f.convert("RGBA") for f in ImageSequence.Iterator(im)]
                frames[0].save(tmp, "WEBP", save_all=True, append_images=frames[1:], duration=durations, loop=loop,
                               quality=q, method=4, lossless=q >= 100)
            else:
                frames = [f.convert("RGBA") for f in ImageSequence.Iterator(im)]
                frames[0].save(tmp, "AVIF", save_all=True, append_images=frames[1:], duration=durations,
                               quality=q, speed=6)
            frames = None
        with Image.open(tmp) as check, Image.open(path) as orig:
            got = getattr(check, "n_frames", 1)
            if check.size != size or got != n:
                raise ValueError(f"came out as {got} frame(s) at {check.size} instead of {n} at {size}")
            new = frame_durations(check)
            # every frame keeps its time (GIF stores 1/100 s, so up to 10 ms off)
            if any(abs(a - b) > 10 for a, b in zip(durations, new)):
                raise ValueError(f"the frame timing changed ({durations[:6]}… ms -> {new[:6]}… ms)")
            if not _same_transparency(orig, check, n):
                raise ValueError("the transparent areas changed")
        _keep_if_smaller(path, tmp, final, result)
    except Exception as e:
        result.failed.append(f"{name}: {e}")
        logger.debug(f"Couldn't compress {path}: {e}", category="decompressor")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


@_releases_names
def compress_image(path: str, fmt: str, quality: int, result: CompressResult) -> None:
    from PIL import Image
    src_ext = os.path.splitext(path)[1].lower()
    if src_ext == ".gif":
        compress_gif(path, quality, result)    # GIFs stay GIFs (an animation can't become a still picture)
        return
    ext = IMAGE_FORMATS[fmt]
    same = src_ext == ext or (fmt == "jpg" and src_ext == ".jpeg")
    if same and fmt != "png":
        result.skipped += 1                    # lossy again would only lose quality
        return
    folder, name = os.path.split(path)
    stem = os.path.splitext(name)[0] + (" (compressed)" if same else "")
    final = _free_name(folder, stem, ext, path)
    tmp = final + ".pawtmp"
    q = max(1, min(100, int(quality)))
    try:
        with Image.open(path) as im:
            frames = getattr(im, "n_frames", 1) if getattr(im, "is_animated", False) else 1
            info = {k: im.info[k] for k in ("icc_profile", "exif") if im.info.get(k)}
            size = im.size
            has_alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
            if frames > 1:
                # An animated picture is only re-saved in its own format (animated PNG → PNG, losslessly)
                if not (fmt == "png" and same):
                    result.skipped += 1
                    return
                im.save(tmp, "PNG", optimize=True, save_all=True)
            elif fmt == "jpg":
                if has_alpha:
                    result.skipped += 1           # JPG can't keep transparency
                    return
                im = im.convert("RGB") if im.mode != "RGB" else im
                im.save(tmp, "JPEG", quality=q, optimize=True, progressive=True,
                        subsampling=0 if q >= 90 else 2, **info)
            elif fmt == "png":
                out = im if q >= 90 else _png_palette(im, q)
                if q >= 90 and out.mode not in ("1", "L", "LA", "P", "RGB", "RGBA", "I", "I;16"):
                    out = out.convert("RGBA" if has_alpha else "RGB")
                out.save(tmp, "PNG", optimize=True, **info)
            else:
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA" if has_alpha else "RGB")
                if fmt == "webp":
                    im.save(tmp, "WEBP", quality=q, method=6, lossless=q >= 100, **info)
                else:
                    im.save(tmp, "AVIF", quality=q, speed=6, **info)
        with Image.open(tmp) as check:                 # it opens, whole, at the same size and length
            check.load()
            if check.size != size:
                raise ValueError(f"size changed {size} -> {check.size}")
            if frames > 1 and getattr(check, "n_frames", 1) != frames:
                raise ValueError(f"{frames} frames became {getattr(check, 'n_frames', 1)}")
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


_PROBED_ENCODERS: dict = {}
_PROBE_LOCK = threading.Lock()


def is_encoder_supported(ffmpeg: str, encoder: str) -> bool:
    """Checks whether the specified FFmpeg encoder works on this system (cached)."""
    if not ffmpeg or not encoder:
        return False
    cache_key = f"{ffmpeg}:{encoder}"
    with _PROBE_LOCK:
        if cache_key in _PROBED_ENCODERS:
            return _PROBED_ENCODERS[cache_key]

    if encoder in ("libopus", "opus", "aac", "libmp3lame", "flac"):
        cmd = [
            ffmpeg, "-hide_banner", "-f", "lavfi", "-i", "sine=frequency=1000:duration=0.04",
            "-c:a", encoder, "-f", "null", "-"
        ]
    else:
        # Use 256x256 test pattern: hardware encoders (specifically NVIDIA NVENC) enforce
        # a minimum resolution (usually >= 144x144) and will reject small sizes like 64x64.
        cmd = [
            ffmpeg, "-hide_banner", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.04",
            "-c:v", encoder, "-f", "null", "-"
        ]
    try:
        flags = _CREATE_NO_WINDOW | _BELOW_NORMAL_PRIORITY
        res = subprocess.run(cmd, capture_output=True, timeout=8, creationflags=flags)
        supported = (res.returncode == 0)
    except Exception:
        supported = False

    with _PROBE_LOCK:
        _PROBED_ENCODERS[cache_key] = supported
    return supported


def detect_available_hwaccels(ffmpeg: str) -> List[str]:
    """List of hardware acceleration frameworks available on this machine (e.g. ['nvenc', 'amf', 'qsv']).
    Discrete GPUs (NVIDIA NVENC, AMD AMF) are prioritized ahead of integrated graphics (Intel QSV)."""
    if not ffmpeg:
        return []
    available = []
    # Dedicated discrete GPUs (NVIDIA NVENC, AMD AMF) prioritized over integrated (Intel QSV)
    if (is_encoder_supported(ffmpeg, "hevc_nvenc") or
            is_encoder_supported(ffmpeg, "h264_nvenc") or
            is_encoder_supported(ffmpeg, "av1_nvenc")):
        available.append("nvenc")
    if (is_encoder_supported(ffmpeg, "hevc_amf") or
            is_encoder_supported(ffmpeg, "h264_amf") or
            is_encoder_supported(ffmpeg, "av1_amf")):
        available.append("amf")
    if (is_encoder_supported(ffmpeg, "hevc_qsv") or
            is_encoder_supported(ffmpeg, "h264_qsv") or
            is_encoder_supported(ffmpeg, "av1_qsv")):
        available.append("qsv")
    return available


def get_primary_hwaccel(ffmpeg: str) -> str:
    """Best detected hardware accelerator ('nvenc', 'amf', 'qsv', or '')."""
    accels = detect_available_hwaccels(ffmpeg)
    return accels[0] if accels else ""


def _hw_encoder_for(fmt: str, accel: str) -> Optional[str]:
    """Maps video format and hardware framework to encoder name."""
    if fmt in ("h265", "mkv"):
        if accel == "nvenc":
            return "hevc_nvenc"
        if accel == "amf":
            return "hevc_amf"
        if accel == "qsv":
            return "hevc_qsv"
    elif fmt == "h264":
        if accel == "nvenc":
            return "h264_nvenc"
        if accel == "amf":
            return "h264_amf"
        if accel == "qsv":
            return "h264_qsv"
    elif fmt == "av1":
        if accel == "nvenc":
            return "av1_nvenc"
        if accel == "amf":
            return "av1_amf"
        if accel == "qsv":
            return "av1_qsv"
    return None


def select_video_encoder(ffmpeg: str, fmt: str, quality: int,
                         hw_accel: str = "auto",
                         preset: str = "auto") -> Tuple[str, List[str], str, List[str]]:
    """Returns (active_encoder_name, active_encoder_args, cpu_encoder_name, cpu_encoder_args).
    Compatible with NVIDIA NVENC, AMD AMF, and Intel Quick Sync (QSV), falling back to software."""
    crf = str(video_crf(fmt, quality))
    threads = get_safe_encoder_threads()

    # CPU baseline configurations
    if fmt in ("h265", "mkv"):
        cpu_name = "libx265"
        p = "fast" if preset == "fast" else ("slow" if preset == "quality" else (preset if preset not in ("auto", "balanced", "") else "medium"))
        cpu_args = ["-c:v", "libx265", "-crf", crf, "-preset", p,
                    "-threads", str(threads),
                    "-x265-params", f"log-level=error:pools=none:frame-threads={threads}"]
    elif fmt == "h264":
        cpu_name = "libx264"
        p = "fast" if preset == "fast" else ("slower" if preset == "quality" else (preset if preset not in ("auto", "balanced", "") else "slow"))
        cpu_args = ["-c:v", "libx264", "-crf", crf, "-preset", p, "-threads", str(threads)]
    else:  # av1
        cpu_name = "libsvtav1"
        p = "8" if preset == "fast" else ("4" if preset == "quality" else (str(preset) if str(preset).isdigit() else "6"))
        cpu_args = ["-c:v", "libsvtav1", "-crf", crf, "-preset", p,
                    "-threads", str(threads),
                    "-svtav1-params", f"lp={threads}"]

    if hw_accel == "cpu" or not ffmpeg:
        return cpu_name, cpu_args, cpu_name, cpu_args

    candidates = ["nvenc", "amf", "qsv"] if hw_accel == "auto" else [hw_accel]
    for accel in candidates:
        enc = _hw_encoder_for(fmt, accel)
        if enc and is_encoder_supported(ffmpeg, enc):
            if accel == "nvenc":
                p_nv = "p3" if preset == "fast" else ("p6" if preset == "quality" else "p5")
                args = ["-c:v", enc, "-rc:v", "vbr", "-cq:v", crf, "-b:v", "0", "-preset", p_nv]
            elif accel == "qsv":
                p_qsv = "faster" if preset == "fast" else ("veryslow" if preset == "quality" else "medium")
                args = ["-c:v", enc, "-global_quality", crf, "-preset", p_qsv]
            elif accel == "amf":
                p_amf = "speed" if preset == "fast" else "quality"
                args = ["-c:v", enc, "-rc", "cqp", "-qp_i", crf, "-qp_p", crf, "-quality", p_amf]
            else:
                continue
            return enc, args, cpu_name, cpu_args

    return cpu_name, cpu_args, cpu_name, cpu_args


def video_command(ffmpeg: str, src: str, dst: str, fmt: str, quality: int, audio_codec: str,
                  video_args: Optional[List[str]] = None,
                  audio_setting: str = "auto",
                  custom_video_args: Optional[List[str]] = None,
                  preset: str = "auto",
                  hw_accel: str = "auto") -> List[str]:
    head = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", src]
    tail = ["-progress", "pipe:1", "-nostats"]
    if video_args is None:
        _, video_args, _, _ = select_video_encoder(ffmpeg, fmt, quality, hw_accel=hw_accel, preset=preset)

    extra_args = list(custom_video_args or [])

    if audio_setting == "opus" and is_encoder_supported(ffmpeg, "libopus"):
        audio = ["-c:a", "libopus", "-b:a", "64k", "-vbr", "on"]
    elif audio_setting == "aac":
        audio = ["-c:a", "aac", "-b:a", "128k"]
    elif audio_setting == "copy":
        audio = ["-c:a", "copy"]
    else:  # "auto"
        audio = ["-c:a", "copy"] if audio_codec in ("aac", "mp3") else ["-c:a", "aac", "-b:a", "192k"]

    pix_fmt = [] if any(a in extra_args for a in ("-pix_fmt", "-pix_fmts")) else ["-pix_fmt", "yuv420p"]
    if any(a in extra_args for a in ("-c:a", "-codec:a")):
        audio = []

    if fmt == "mkv":
        mkv_audio = audio if audio_setting in ("opus", "aac") else ["-c:a", "copy"]
        return [*head, "-map", "0:v:0", "-map", "0:a?", "-map", "0:s?", "-map", "0:t?", "-map_metadata", "0",
                *video_args, *extra_args, *pix_fmt, *mkv_audio, "-c:s", "copy", "-c:t", "copy", *tail,
                "-f", "matroska", dst]

    tag = ["-tag:v", "hvc1"] if fmt in ("h265", "mkv") else []
    return [*head, "-map", "0:v:0", "-map", "0:a?", "-sn", "-dn", "-map_metadata", "0", *video_args,
            *extra_args, *tag, *pix_fmt, *audio, "-movflags", "+faststart", *tail, "-f", "mp4", dst]


def _run_ffmpeg_encode(cmd: List[str], tmp: str, duration: float,
                       cancel: Optional[threading.Event],
                       on_progress: Optional[Callable[[float], None]],
                       procs: Optional[set]) -> Tuple[int, List[str]]:
    """Runs FFmpeg process and monitors progress lines. Returns (returncode, err_tail)."""
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = _CREATE_NO_WINDOW | _BELOW_NORMAL_PRIORITY
    elif hasattr(os, "nice"):
        kwargs["preexec_fn"] = lambda: os.nice(10)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                errors="replace", **kwargs)
    except OSError as e:
        return -1, [str(e)]
    if procs is not None:
        procs.add(proc)
    err_tail: List[str] = []
    t = threading.Thread(target=lambda: err_tail.extend(proc.stderr.read().splitlines()[-5:]), daemon=True)
    t.start()
    last_emit = 0.0
    try:
        for line in proc.stdout:
            if cancel is not None and cancel.is_set():
                proc.kill()
                break
            if line.startswith("out_time_us=") and duration > 0 and on_progress:
                try:
                    now = time.monotonic()
                    pct = min(99.0, int(line.split("=", 1)[1]) / 1e6 / duration * 100)
                    if now - last_emit >= 0.15 or pct >= 99.0:
                        last_emit = now
                        on_progress(pct)
                except ValueError:
                    pass
        proc.wait()
        t.join(5)
    finally:
        if procs is not None:
            procs.discard(proc)
    return proc.returncode, err_tail


@_releases_names
def compress_video(ffmpeg: str, path: str, fmt: str, quality: int, result: CompressResult,
                   cancel: Optional[threading.Event] = None,
                   on_progress: Optional[Callable[[float], None]] = None,
                   procs: Optional[set] = None,
                   hw_accel: str = "auto",
                   preset: str = "auto",
                   audio_setting: str = "auto",
                   custom_video_args: str = "") -> None:
    duration, vcodec, acodec = probe_video(ffmpeg, path)
    if not vcodec or vcodec == VIDEO_FORMATS[fmt]:
        result.skipped += 1                    # not a video ffmpeg can read, or already in that codec
        return
    folder, name = os.path.split(path)
    out_ext = VIDEO_EXTS_OUT[fmt]
    final = _free_name(folder, os.path.splitext(name)[0], out_ext, path)
    if os.path.normcase(final) == os.path.normcase(path):
        final = _free_name(folder, os.path.splitext(name)[0] + " (compressed)", out_ext, path)
    tmp = final + ".pawtmp"

    enc_name, enc_args, cpu_name, cpu_args = select_video_encoder(
        ffmpeg, fmt, quality, hw_accel=hw_accel, preset=preset
    )
    extra_args = shlex.split(custom_video_args) if custom_video_args else []
    cmd = video_command(
        ffmpeg, path, tmp, fmt, quality, acodec, enc_args,
        audio_setting=audio_setting, custom_video_args=extra_args,
        preset=preset, hw_accel=hw_accel
    )
    returncode, err_tail = _run_ffmpeg_encode(cmd, tmp, duration, cancel, on_progress, procs)

    # If hardware encoding fails at runtime, automatically fallback to software CPU encoder
    if returncode != 0 and enc_name != cpu_name and not (cancel is not None and cancel.is_set()):
        logger.warning(f"Hardware encode ({enc_name}) failed for {name}; retrying with CPU ({cpu_name})",
                       category="decompressor")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        cmd_cpu = video_command(
            ffmpeg, path, tmp, fmt, quality, acodec, cpu_args,
            audio_setting=audio_setting, custom_video_args=extra_args,
            preset=preset, hw_accel="cpu"
        )
        returncode, err_tail = _run_ffmpeg_encode(cmd_cpu, tmp, duration, cancel, on_progress, procs)

    if (cancel is not None and cancel.is_set()) or returncode != 0 or not os.path.exists(tmp):
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        if not (cancel is not None and cancel.is_set()):
            result.failed.append(f"{name}: {' '.join(err_tail)[-200:] or f'ffmpeg exited with {returncode}'}")
        return
    new_dur, new_codec, _ = probe_video(ffmpeg, tmp)
    if not new_codec or (duration > 0 and abs(new_dur - duration) > max(1.0, duration * 0.02)):
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        result.failed.append(f"{name}: the compressed video came out incomplete")
        return
    _keep_if_smaller(path, tmp, final, result)




def validate_ffmpeg_settings(ffmpeg: str, settings: CompressSettings) -> Tuple[bool, str]:
    """Validates that FFmpeg can execute an encoding task with the configured video encoder,
    preset, audio codec, and custom parameters on a test pattern."""
    if not ffmpeg or not os.path.isfile(ffmpeg):
        return False, "FFmpeg binary not found or not installed."

    enc_name, enc_args, _, _ = select_video_encoder(
        ffmpeg, settings.video_format, settings.video_quality,
        hw_accel=settings.video_hwaccel, preset=settings.video_preset
    )
    extra_args = shlex.split(settings.custom_video_args) if settings.custom_video_args else []

    with tempfile.NamedTemporaryFile(suffix=VIDEO_EXTS_OUT.get(settings.video_format, ".mp4"), delete=False) as f:
        tmp_out = f.name
    try:
        cmd = video_command(
            ffmpeg=ffmpeg,
            src="color=c=black:s=256x256:d=0.08",
            dst=tmp_out,
            fmt=settings.video_format,
            quality=settings.video_quality,
            audio_codec="aac",
            video_args=enc_args,
            audio_setting=settings.audio_codec,
            custom_video_args=extra_args,
            preset=settings.video_preset,
            hw_accel=settings.video_hwaccel
        )
        new_cmd = []
        i = 0
        while i < len(cmd):
            if cmd[i] == "-i" and i + 1 < len(cmd) and cmd[i+1].startswith("color="):
                new_cmd.extend(["-f", "lavfi", "-i", cmd[i+1], "-f", "lavfi", "-i", "sine=frequency=1000:duration=0.08"])
                i += 2
            else:
                new_cmd.append(cmd[i])
                i += 1

        flags = _CREATE_NO_WINDOW | _BELOW_NORMAL_PRIORITY
        res = subprocess.run(new_cmd, capture_output=True, text=True, timeout=10, creationflags=flags)
        if res.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0:
            return True, f"Verified: {enc_name} ({settings.video_format}) + {settings.audio_codec} working cleanly."
        else:
            err = res.stderr.splitlines()[-3:] if res.stderr else ["Unknown error"]
            return False, f"Validation failed ({enc_name}): {' '.join(err)}"
    except subprocess.TimeoutExpired:
        return False, "Validation timed out after 10 seconds."
    except Exception as e:
        return False, f"Validation error: {e}"
    finally:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except OSError:
                pass

# ── A folder ─────────────────────────────────────────────────────────────────

def classify(path: str, settings: CompressSettings) -> Optional[str]:
    """"image", "video" or "animated" when the settings compress this file, else None. GIFs always count as
    animated pictures (a GIF stays a GIF); a PNG, WebP or AVIF is looked at to see whether it's animated."""
    ext = os.path.splitext(path)[1].lower()
    if ext in GIF_EXTS:
        return "animated" if settings.animated_on else None
    if ext in ANIMATED_EXTS and (settings.animated_on or (settings.images_on and ext in IMAGE_EXTS)):
        if is_animated_file(path):
            return "animated" if settings.animated_on else None
        return "image" if settings.images_on and ext in IMAGE_EXTS else None
    if settings.images_on and ext in IMAGE_EXTS:
        return "image"
    if settings.videos_on and ext in VIDEO_EXTS:
        return "video"
    return None


def media_in(paths: List[str], settings: CompressSettings,
             cancel: Optional[threading.Event] = None) -> Tuple[List[str], List[str], List[str]]:
    """(still pictures, videos, animated pictures) among files and folders (folders with their sub-folders)."""
    lists = {"image": [], "video": [], "animated": []}
    seen = set()

    def add(p):
        key = os.path.normcase(os.path.abspath(p))
        if key in seen:
            return
        seen.add(key)
        kind = classify(p, settings)
        if kind:
            lists[kind].append(p)
    for path in paths:
        if cancel is not None and cancel.is_set():
            break
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                if cancel is not None and cancel.is_set():
                    break
                for f in files:
                    if not f.endswith(".pawtmp"):
                        add(os.path.join(root, f))
        elif os.path.isfile(path):
            add(path)
    return lists["image"], lists["video"], lists["animated"]


def media_files(folder: str, settings: CompressSettings) -> Tuple[List[str], List[str], List[str]]:
    """(still pictures, videos, animated pictures) in a folder and its sub-folders."""
    return media_in([folder], settings)


def compress_folder(folder: str, settings: CompressSettings, cancel: Optional[threading.Event] = None,
                    on_progress: Optional[Callable[[float], None]] = None, workers: int = 0,
                    procs: Optional[set] = None) -> CompressResult:
    """Compresses the pictures and videos in a folder (and its sub-folders)."""
    return compress_paths([folder], settings, cancel, on_progress, workers, procs)


def compress_paths(paths: List[str], settings: CompressSettings, cancel: Optional[threading.Event] = None,
                   on_progress: Optional[Callable[..., None]] = None, workers: int = 0,
                   procs: Optional[set] = None, found=None) -> CompressResult:
    """Compresses the pictures and videos among files and folders. on_progress(percent[, file name]): 0–100,
    weighted by file size. Pictures are compressed a few at a time; videos one at a time (ffmpeg uses every
    core). found: the (pictures, videos, animated) lists when they were already looked up."""
    from concurrent.futures import ThreadPoolExecutor
    result = CompressResult()
    images, videos, animated = found if found is not None else media_in(paths, settings, cancel)
    sizes = {}
    for p in images + videos + animated:
        try:
            sizes[p] = max(1, os.path.getsize(p))
        except OSError:
            sizes[p] = 1
    total = sum(sizes.values()) or 1
    done = [0]
    lock = threading.Lock()

    def report(pct, name):
        if on_progress:
            try:
                on_progress(pct, name)
            except TypeError:
                on_progress(pct)

    def finished(p):
        with lock:
            done[0] += sizes[p]
            report(done[0] / total * 100, os.path.basename(p))

    def one_image(p):
        if cancel is not None and cancel.is_set():
            return CompressResult()
        r = CompressResult()
        if p in animated_set:
            compress_animated(p, settings.animated_format, settings.animated_quality, r)
        else:
            compress_image(p, settings.image_format, settings.image_quality, r)
        finished(p)
        return r

    animated_set = set(animated)
    n = workers or max(1, min(4, (os.cpu_count() or 2) // 2))
    with ThreadPoolExecutor(max_workers=n) as pool:
        for r in pool.map(one_image, images + animated):
            result.merge(r)
    for v in videos:
        if cancel is not None and cancel.is_set():
            break
        base = done[0]

        def part(pct, base=base, v=v):
            report((base + sizes[v] * pct / 100) / total * 100, os.path.basename(v))
        compress_video(
            settings.ffmpeg, v, settings.video_format, settings.video_quality, result,
            cancel, part, procs, settings.video_hwaccel,
            preset=settings.video_preset,
            audio_setting=settings.audio_codec,
            custom_video_args=settings.custom_video_args
        )
        finished(v)
    return result
