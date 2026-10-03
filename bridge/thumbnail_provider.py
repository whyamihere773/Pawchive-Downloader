"""
Gallery thumbnail provider.

Serves ``image://thumb/<url-encoded path>?m=<mtime>`` to QML. Thumbnails are
decoded with QImageReader (scaled decoding, EXIF-aware), then cached on disk as
small JPEGs so revisiting a folder is instant. The provider is registered with
ForceAsynchronousImageLoading, so Qt calls requestImage off the UI thread.
"""

import hashlib
import os
import sys
import threading
import time
from collections import OrderedDict
import urllib.parse

from PySide6.QtCore import QSize, QStandardPaths, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter
from PySide6.QtQml import QQmlImageProviderBase
from PySide6.QtQuick import QQuickImageProvider

from core.logger import logger

# Thumbnails fit inside this box; QML crops them to the card with PreserveAspectCrop.
THUMB_BOX = 480
CACHE_MAX_BYTES = 512 * 1024 * 1024
CACHE_PRUNE_TARGET = 400 * 1024 * 1024
BACKGROUND = QColor("#131824")


# ── Pictures and animations kept in memory ──────────────────────────────────
# The image viewer and animated previews reuse decoded pictures, so reopening one is instant.
MEDIA_CACHE_MAX_ITEMS = 50                    # pictures + animations
MEDIA_CACHE_MAX_IDLE = 5 * 60                 # each one is dropped 5 minutes after it was last shown
MEDIA_CACHE_MAX_BYTES = 1536 * 1024 * 1024    # safety limit: 50 huge pictures could otherwise need 10+ GB


class MediaMemoryCache:
    """Least-recently-used cache of decoded pictures/animations with an idle timeout."""

    def __init__(self, max_items: int, max_bytes: int, max_idle: float):
        self.max_items, self.max_bytes, self.max_idle = max_items, max_bytes, max_idle
        self._items: "OrderedDict[tuple, list]" = OrderedDict()     # key -> [value, cost, last_used]
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            entry[2] = time.monotonic()
            self._items.move_to_end(key)
            return entry[0]

    def put(self, key, value, cost: int) -> None:
        if cost > self.max_bytes:          # bigger than the whole budget: don't keep it
            return
        with self._lock:
            old = self._items.pop(key, None)
            if old is not None:
                self._bytes -= old[1]
            self._items[key] = [value, cost, time.monotonic()]
            self._bytes += cost
            while self._items and (len(self._items) > self.max_items or self._bytes > self.max_bytes):
                _k, (_v, c, _t) = self._items.popitem(last=False)
                self._bytes -= c

    def expire(self) -> int:
        """Drop everything not used for max_idle seconds; returns how many were dropped."""
        cutoff = time.monotonic() - self.max_idle
        dropped = 0
        with self._lock:
            for key in [k for k, e in self._items.items() if e[2] < cutoff]:
                self._bytes -= self._items.pop(key)[1]
                dropped += 1
        return dropped

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._bytes = 0

    def usage(self) -> tuple:
        with self._lock:
            return len(self._items), self._bytes


media_cache = MediaMemoryCache(MEDIA_CACHE_MAX_ITEMS, MEDIA_CACHE_MAX_BYTES, MEDIA_CACHE_MAX_IDLE)


def _media_key(kind: str, path: str):
    """Cache key that changes when the file does (edited, rotated, replaced)."""
    try:
        st = os.stat(path)
        return (kind, os.path.normcase(os.path.abspath(path)), st.st_mtime_ns, st.st_size)
    except OSError:
        return None


VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".f4v", ".wmv", ".asf", ".mpg", ".mpeg",
    ".m2v", ".ts", ".mts", ".m2ts", ".3gp", ".3g2", ".ogv", ".vob", ".divx",
}


def _shell_thumbnail(path: str, box: int) -> QImage:
    """Ask Windows for the same thumbnail File Explorer shows (works for videos without ffmpeg).

    Uses IShellItemImageFactory through ctypes. Returns a null QImage when there is no
    thumbnail (e.g. no codec installed for the format), so callers fall back to an icon.
    """
    if sys.platform != "win32":
        return QImage()
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    class SIZE(ctypes.Structure):
        _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

    class BITMAP(ctypes.Structure):
        _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long), ("bmHeight", ctypes.c_long),
                    ("bmWidthBytes", ctypes.c_long), ("bmPlanes", ctypes.c_ushort),
                    ("bmBitsPixel", ctypes.c_ushort), ("bmBits", ctypes.c_void_p)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", ctypes.c_ushort), ("biBitCount", ctypes.c_ushort),
                    ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32),
                    ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]

    ole32 = ctypes.windll.ole32
    shell32 = ctypes.windll.shell32
    gdi32 = ctypes.windll.gdi32
    user32 = ctypes.windll.user32

    iid = GUID()
    ole32.IIDFromString(ctypes.c_wchar_p("{bcc18b79-ba16-442f-80c4-8a59c30c463b}"), ctypes.byref(iid))

    # The image loader thread may not have COM set up yet
    hr_init = ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED
    factory = ctypes.c_void_p()
    hbitmap = wintypes.HBITMAP()
    try:
        shell32.SHCreateItemFromParsingName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p,
                                                        ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        shell32.SHCreateItemFromParsingName.restype = ctypes.c_long
        if shell32.SHCreateItemFromParsingName(path, None, ctypes.byref(iid), ctypes.byref(factory)) != 0 or not factory:
            return QImage()

        vtbl = ctypes.cast(factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        get_image = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, SIZE, ctypes.c_int,
                                       ctypes.POINTER(wintypes.HBITMAP))(vtbl[3])
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
        try:
            # SIIGBF_BIGGERSIZEOK | SIIGBF_THUMBNAILONLY: a real thumbnail or nothing (no generic icon)
            if get_image(factory, SIZE(box, box), 0x1 | 0x8, ctypes.byref(hbitmap)) != 0 or not hbitmap:
                return QImage()
        finally:
            release(factory)

        bm = BITMAP()
        gdi32.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        if not gdi32.GetObjectW(hbitmap, ctypes.sizeof(bm), ctypes.byref(bm)):
            return QImage()
        w, h = bm.bmWidth, abs(bm.bmHeight)
        if w <= 0 or h <= 0:
            return QImage()

        bih = BITMAPINFOHEADER()
        bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bih.biWidth, bih.biHeight = w, -h      # negative height = top-down rows
        bih.biPlanes, bih.biBitCount, bih.biCompression = 1, 32, 0  # BI_RGB
        buf = ctypes.create_string_buffer(w * h * 4)
        hdc = user32.GetDC(None)
        try:
            gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                                        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
            rows = gdi32.GetDIBits(hdc, hbitmap, 0, h, buf, ctypes.byref(bih), 0)
        finally:
            user32.ReleaseDC(None, hdc)
        if rows != h:
            return QImage()

        raw = buf.raw
        # Many shell thumbnails leave alpha at 0 even though they are opaque
        fmt = QImage.Format.Format_ARGB32_Premultiplied if any(raw[3::4]) else QImage.Format.Format_RGB32
        return QImage(raw, w, h, w * 4, fmt).copy()
    except Exception as e:
        logger.debug(f"Shell thumbnail failed for {path}: {e}", category="gallery")
        return QImage()
    finally:
        if hbitmap:
            gdi32.DeleteObject(hbitmap)
        if hr_init in (0, 1):  # S_OK / S_FALSE must be balanced
            ole32.CoUninitialize()


def decode_with_pillow(path: str, max_box: int = 0) -> QImage:
    """Decode formats Qt can't (AVIF, files with the wrong extension, …) with Pillow."""
    try:
        from PIL import Image as PILImage, ImageOps
        with PILImage.open(path) as im:
            if max_box:
                im.draft("RGB", (max_box, max_box))   # fast downscale while decoding (JPEG)
            im = ImageOps.exif_transpose(im)
            if max_box:
                im.thumbnail((max_box, max_box))
            im = im.convert("RGBA")
            data = im.tobytes("raw", "RGBA")
            return QImage(data, im.width, im.height, im.width * 4, QImage.Format.Format_RGBA8888).copy()
    except Exception:
        return QImage()


def decode_full_image(path: str) -> QImage:
    """Full-size decode for the image viewer: Qt first, then Pillow, then the Windows thumbnail."""
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    reader.setDecideFormatFromContent(True)   # a .png that's really AVIF/JPEG is still read correctly
    img = reader.read()
    if img.isNull():
        img = decode_with_pillow(path)
    if img.isNull():
        img = _shell_thumbnail(path, 1600)
    return img


class FullImageProvider(QQuickImageProvider):
    """Serves image://full/<url-encoded path> for the image viewer (decoded off the UI thread)."""

    def __init__(self):
        super().__init__(
            QQmlImageProviderBase.ImageType.Image,
            QQmlImageProviderBase.Flag.ForceAsynchronousImageLoading,
        )

    def requestImage(self, image_id: str, size: QSize, requested_size: QSize) -> QImage:
        path = urllib.parse.unquote(image_id.split("?", 1)[0])
        key = _media_key("full", path) if os.path.isfile(path) else None
        img = media_cache.get(key) if key else None
        if img is None:
            img = decode_full_image(path) if key else QImage()
            if key and not img.isNull():
                media_cache.put(key, img, img.sizeInBytes())
        if img.isNull():
            # 1x1 transparent: the viewer shows "can't display" instead of a console error
            img = QImage(1, 1, QImage.Format.Format_ARGB32)
            img.fill(0)
        elif requested_size.isValid() and requested_size.width() > 0 and requested_size.height() > 0:
            img = img.scaled(requested_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        size.setWidth(img.width())
        size.setHeight(img.height())
        return img


# ── Animated images Qt can't play itself (APNG, animated AVIF, mis-named GIFs…) ───
# Frames are decoded once with Pillow, scaled to fit a memory budget, and kept for the
# last few animations so the viewer / hover preview can step through them smoothly.
_ANIM_BUDGET_BYTES = 256 * 1024 * 1024        # one animation's frames are scaled down to fit this
_ANIM_MAX_FRAMES = 600


def load_animation(path: str) -> dict:
    """{"frames": n, "durations": [ms…]}; n is 0 for still images or unreadable files."""
    key = _media_key("anim", path)
    a = media_cache.get(key) if key else None
    if a is not None:
        return {"frames": len(a["frames"]), "durations": a["durations"]}
    try:
        from PIL import Image as PILImage, ImageSequence
        with PILImage.open(path) as im:
            n = getattr(im, "n_frames", 1)
            if n <= 1:
                return {"frames": 0, "durations": []}
            n = min(n, _ANIM_MAX_FRAMES)
            w, h = im.size
            # Shrink frames if the whole animation wouldn't fit the memory budget
            scale = min(1.0, (_ANIM_BUDGET_BYTES / max(1, n * w * h * 4)) ** 0.5)
            target = (max(1, int(w * scale)), max(1, int(h * scale)))
            frames, durations = [], []
            for i, fr in enumerate(ImageSequence.Iterator(im)):
                if i >= n:
                    break
                durations.append(int(fr.info.get("duration", im.info.get("duration", 100)) or 100))
                rgba = fr.convert("RGBA")
                if rgba.size != target:
                    rgba = rgba.resize(target)
                data = rgba.tobytes("raw", "RGBA")
                frames.append(QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy())
    except Exception as e:
        logger.debug(f"Animation decode failed for {path}: {e}", category="gallery")
        return {"frames": 0, "durations": []}
    if len(frames) <= 1:
        return {"frames": 0, "durations": []}
    if key:
        media_cache.put(key, {"frames": frames, "durations": durations}, sum(f.sizeInBytes() for f in frames))
    return {"frames": len(frames), "durations": durations}


def animation_frame(path: str, index: int) -> QImage:
    key = _media_key("anim", path)
    a = media_cache.get(key) if key else None     # every frame shown counts as use, so playing never expires
    if not a or not a["frames"]:
        return QImage()
    return a["frames"][index % len(a["frames"])]


class FrameProvider(QQuickImageProvider):
    """image://frame/<url-encoded path>?frame=N, one decoded frame of a prepared animation.
    Synchronous on purpose: frames are already in memory, so swapping them never flickers."""

    def __init__(self):
        super().__init__(QQmlImageProviderBase.ImageType.Image)

    def requestImage(self, image_id: str, size: QSize, requested_size: QSize) -> QImage:
        path_part, _, query = image_id.partition("?")
        path = urllib.parse.unquote(path_part)
        index = 0
        for kv in query.split("&"):
            if kv.startswith("frame="):
                try:
                    index = int(kv[6:])
                except ValueError:
                    pass
        img = animation_frame(path, index)
        if img.isNull():
            img = QImage(1, 1, QImage.Format.Format_ARGB32)
            img.fill(0)
        size.setWidth(img.width())
        size.setHeight(img.height())
        return img


def _cache_dir() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".cache", "pawchive")
    path = os.path.join(base, "thumbnails")
    os.makedirs(path, exist_ok=True)
    return path


class ThumbnailProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(
            QQmlImageProviderBase.ImageType.Image,
            QQmlImageProviderBase.Flag.ForceAsynchronousImageLoading,
        )
        self._cache_dir = _cache_dir()
        self._prune_started = False
        self._prune_lock = threading.Lock()

    def requestImage(self, image_id: str, size: QSize, requested_size: QSize) -> QImage:
        self._maybe_prune()
        path = urllib.parse.unquote(image_id.split("?", 1)[0])
        try:
            st = os.stat(path)
        except OSError:
            return self._no_thumbnail(size)

        key = hashlib.sha1(
            f"{os.path.normcase(os.path.normpath(path))}|{st.st_mtime_ns}|{st.st_size}|{THUMB_BOX}".encode("utf-8")
        ).hexdigest()
        cached_path = os.path.join(self._cache_dir, key[:2], key + ".jpg")

        if os.path.exists(cached_path):
            img = QImage(cached_path)
            if not img.isNull():
                size.setWidth(img.width())
                size.setHeight(img.height())
                return img

        ext = os.path.splitext(path)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            img = _shell_thumbnail(path, THUMB_BOX)
        else:
            img = self._decode_scaled(path)
            if img.isNull():
                # Formats Qt can't read (HEIC, AVIF…) may still have a Windows thumbnail
                img = _shell_thumbnail(path, THUMB_BOX)
        if img.isNull():
            return self._no_thumbnail(size)
        if img.width() > THUMB_BOX or img.height() > THUMB_BOX:
            img = img.scaled(THUMB_BOX, THUMB_BOX, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        try:
            os.makedirs(os.path.dirname(cached_path), exist_ok=True)
            img.save(cached_path, "JPG", 85)
        except Exception as e:
            logger.debug(f"Could not cache thumbnail for {path}: {e}", category="gallery")

        size.setWidth(img.width())
        size.setHeight(img.height())
        return img

    @staticmethod
    def _no_thumbnail(size: QSize) -> QImage:
        """1x1 transparent image: QML shows the file icon instead (a null image logs a warning)."""
        img = QImage(1, 1, QImage.Format.Format_ARGB32)
        img.fill(0)
        size.setWidth(1)
        size.setHeight(1)
        return img

    @staticmethod
    def _decode_scaled(path: str) -> QImage:
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        reader.setDecideFormatFromContent(True)
        src = reader.size()
        if src.isValid() and (src.width() > THUMB_BOX or src.height() > THUMB_BOX):
            reader.setScaledSize(src.scaled(THUMB_BOX, THUMB_BOX, Qt.AspectRatioMode.KeepAspectRatio))
        img = reader.read()
        if img.isNull():
            img = decode_with_pillow(path, THUMB_BOX)
        if img.isNull():
            return QImage()

        # Readers that ignore setScaledSize (or have no size header) still need shrinking.
        if img.width() > THUMB_BOX or img.height() > THUMB_BOX:
            img = img.scaled(THUMB_BOX, THUMB_BOX, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        # Flatten transparency onto the card colour, since the cache is JPEG.
        if img.hasAlphaChannel():
            flat = QImage(img.size(), QImage.Format.Format_RGB32)
            flat.fill(BACKGROUND)
            painter = QPainter(flat)
            painter.drawImage(0, 0, img)
            painter.end()
            img = flat
        return img

    def _maybe_prune(self):
        with self._prune_lock:
            if self._prune_started:
                return
            self._prune_started = True
        threading.Thread(target=self._prune_cache, daemon=True, name="ThumbCachePrune").start()

    def _prune_cache(self):
        """Drop the least recently written thumbnails once the cache grows past its limit."""
        try:
            entries = []
            total = 0
            for dirpath, _, files in os.walk(self._cache_dir):
                for f in files:
                    fp = os.path.join(dirpath, f)
                    try:
                        st = os.stat(fp)
                    except OSError:
                        continue
                    entries.append((st.st_mtime, st.st_size, fp))
                    total += st.st_size
            if total <= CACHE_MAX_BYTES:
                return
            entries.sort()
            for _, sz, fp in entries:
                if total <= CACHE_PRUNE_TARGET:
                    break
                try:
                    os.remove(fp)
                    total -= sz
                except OSError:
                    pass
            logger.debug(f"Thumbnail cache pruned to {total / (1024 * 1024):.0f} MB.", category="gallery")
        except Exception as e:
            logger.debug(f"Thumbnail cache prune failed: {e}", category="gallery")
