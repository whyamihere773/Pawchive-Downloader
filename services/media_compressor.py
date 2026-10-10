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


def video_command(ffmpeg: str, src: str, dst: str, fmt: str, quality: int, audio_codec: str) -> List[str]:
    crf = str(video_crf(fmt, quality))
    head = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", src]
    tail = ["-progress", "pipe:1", "-nostats"]
    x265 = ["-c:v", "libx265", "-crf", crf, "-preset", "medium", "-x265-params", "log-level=error"]
    if fmt == "mkv":
        # Matroska holds any audio, subtitles and attached fonts: all kept as they are
        return [*head, "-map", "0:v:0", "-map", "0:a?", "-map", "0:s?", "-map", "0:t?", "-map_metadata", "0",
                *x265, "-pix_fmt", "yuv420p", "-c:a", "copy", "-c:s", "copy", "-c:t", "copy", *tail,
                "-f", "matroska", dst]
    if fmt == "h264":
        video = ["-c:v", "libx264", "-crf", crf, "-preset", "slow"]
    elif fmt == "av1":
        video = ["-c:v", "libsvtav1", "-crf", crf, "-preset", "6"]
    else:
        video = [*x265, "-tag:v", "hvc1"]
    audio = ["-c:a", "copy"] if audio_codec in ("aac", "mp3") else ["-c:a", "aac", "-b:a", "192k"]
    return [*head, "-map", "0:v:0", "-map", "0:a?", "-sn", "-dn", "-map_metadata", "0", *video,
            "-pix_fmt", "yuv420p", *audio, "-movflags", "+faststart", *tail, "-f", "mp4", dst]


@_releases_names
def compress_video(ffmpeg: str, path: str, fmt: str, quality: int, result: CompressResult,
                   cancel: Optional[threading.Event] = None,
                   on_progress: Optional[Callable[[float], None]] = None,
                   procs: Optional[set] = None) -> None:
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
        compress_video(settings.ffmpeg, v, settings.video_format, settings.video_quality, result, cancel, part, procs)
        finished(v)
    return result
