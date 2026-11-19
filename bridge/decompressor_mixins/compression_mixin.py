"""
DecompressorBridge Compression Settings, FFmpeg Download & Gallery Media Compression Mixin
Decomposed from bridge/decompressor_bridge.py to keep modules cohesive and under 1,000 lines.
"""

import os
import threading
import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Property, Slot

from bridge.decompressor_mixins.signals_mixin import DecompressorSignalsMixin
from core.logger import logger
from core.path_translation import localize_path
from services.media_compressor import (
    CompressResult,
    CompressSettings,
    classify,
    compress_paths,
    media_in,
    validate_ffmpeg_settings,
)


def _format_bytes(b: int) -> str:
    if not b or b <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} PB"


class DecompressorCompressionMixin(DecompressorSignalsMixin):
    """Compression settings properties, FFmpeg installer, and Gallery file/folder compression."""

    def settings_dict(self) -> Dict[str, Any]:
        return {
            "max_parallel": self._max_parallel,
            "threads_per_archive": self._threads_per_archive,
            "delete_after": self._delete_after,
            "auto_prompt_passwords": self._auto_prompt_passwords,
            "custom_locations": [{"path": c["path"], "creator": c.get("creator", "Custom")}
                                 for c in self._custom_locations],
            "compress_after": self._compress_after,
            "image_format": self._image_format,
            "image_quality": self._image_quality,
            "video_format": self._video_format,
            "video_quality": self._video_quality,
            "video_hwaccel": self._video_hwaccel,
            "video_preset": self._video_preset,
            "audio_codec": self._audio_codec,
            "custom_video_args": self._custom_video_args,
            "animated_format": self._animated_format,
            "animated_quality": self._animated_quality,
            "header_collapsed": self._header_collapsed,
        }

    def load_settings(self, d: Dict[str, Any]) -> None:
        """Settings from settings.json (they reset at every start before)."""
        if not isinstance(d, dict):
            return
        self._loading_settings = True
        try:
            self.maxParallel = d.get("max_parallel", self._max_parallel)
            self.threadsPerArchive = d.get("threads_per_archive", self._threads_per_archive)
            self.deleteAfter = bool(d.get("delete_after", self._delete_after))
            self.autoPromptPasswords = bool(d.get("auto_prompt_passwords", self._auto_prompt_passwords))
            self._custom_locations = [
                {"path": localize_path(c["path"]), "creator": c.get("creator", "Custom"), "source": "custom"}
                for c in d.get("custom_locations") or [] if isinstance(c, dict) and c.get("path")]
            self.compressAfter = bool(d.get("compress_after", False))
            self.imageFormat = d.get("image_format", self._image_format)
            self.imageQuality = d.get("image_quality", self._image_quality)
            self.videoFormat = d.get("video_format", self._video_format)
            self.videoQuality = d.get("video_quality", self._video_quality)
            self.videoHwAccel = d.get("video_hwaccel", self._video_hwaccel)
            self.videoPreset = d.get("video_preset", self._video_preset)
            self.audioCodec = d.get("audio_codec", self._audio_codec)
            self.customVideoArgs = d.get("custom_video_args", self._custom_video_args)
            self.animatedFormat = d.get("animated_format", self._animated_format)
            self.animatedQuality = d.get("animated_quality", self._animated_quality)
            self.headerCollapsed = bool(d.get("header_collapsed", False))
            self.locationsChanged.emit()
        except (TypeError, ValueError) as e:
            logger.debug(f"Decompressor settings partly ignored: {e}", category="decompressor")
        finally:
            self._loading_settings = False

    def _save_settings(self) -> None:
        if self._loading_settings or not self._app_bridge or not hasattr(self._app_bridge, "saveSettings"):
            return
        try:
            if hasattr(type(self._app_bridge), "scheduleSaveSettings"):
                self._app_bridge.scheduleSaveSettings()
            else:
                self._app_bridge.saveSettings()
        except Exception as e:
            logger.debug(f"Couldn't save the Decompressor settings: {e}", category="decompressor")

    @Property(bool, notify=DecompressorSignalsMixin.settingsChanged)
    def compressAfter(self) -> bool:
        return self._compress_after

    @compressAfter.setter
    def compressAfter(self, val: bool):
        if self._compress_after != bool(val):
            self._compress_after = bool(val)
            self.settingsChanged.emit()

    @Property(str, notify=DecompressorSignalsMixin.settingsChanged)
    def imageFormat(self) -> str:
        return self._image_format

    @imageFormat.setter
    def imageFormat(self, val: str):
        v = str(val or "").lower()
        if v in ("jpg", "png", "webp", "avif", "keep") and v != self._image_format:
            self._image_format = v
            self.settingsChanged.emit()

    @Property(int, notify=DecompressorSignalsMixin.settingsChanged)
    def imageQuality(self) -> int:
        return self._image_quality

    @imageQuality.setter
    def imageQuality(self, val: int):
        v = max(1, min(100, int(val)))
        if v != self._image_quality:
            self._image_quality = v
            self.settingsChanged.emit()

    @Property(str, notify=DecompressorSignalsMixin.settingsChanged)
    def videoFormat(self) -> str:
        return self._video_format

    @videoFormat.setter
    def videoFormat(self, val: str):
        v = str(val or "").lower()
        if v in ("h265", "h264", "mkv", "av1", "keep") and v != self._video_format:
            self._video_format = v
            self.settingsChanged.emit()

    @Property(int, notify=DecompressorSignalsMixin.settingsChanged)
    def videoQuality(self) -> int:
        return self._video_quality

    @videoQuality.setter
    def videoQuality(self, val: int):
        v = max(1, min(100, int(val)))
        if v != self._video_quality:
            self._video_quality = v
            self.settingsChanged.emit()

    @Property(str, notify=DecompressorSignalsMixin.settingsChanged)
    def videoHwAccel(self) -> str:
        return self._video_hwaccel

    @videoHwAccel.setter
    def videoHwAccel(self, val: str):
        v = str(val or "").lower()
        if v in ("auto", "nvenc", "qsv", "amf", "cpu") and v != self._video_hwaccel:
            self._video_hwaccel = v
            self.settingsChanged.emit()

    @Property(str, notify=DecompressorSignalsMixin.ffmpegChanged)
    def detectedHwAccel(self) -> str:
        """Name of the detected hardware encoder (e.g. 'nvenc', 'qsv', 'amf'), or ''."""
        self._ensure_hwaccel_probed()
        return self._detected_hwaccel

    @Property("QVariantList", notify=DecompressorSignalsMixin.ffmpegChanged)
    def availableHwAccels(self) -> List[str]:
        """List of detected hardware acceleration options on this system."""
        self._ensure_hwaccel_probed()
        return self._available_hwaccels

    @Property(str, notify=DecompressorSignalsMixin.settingsChanged)
    def videoPreset(self) -> str:
        return self._video_preset

    @videoPreset.setter
    def videoPreset(self, val: str):
        v = str(val or "auto").strip()
        if v != self._video_preset:
            self._video_preset = v
            self.settingsChanged.emit()

    @Property(str, notify=DecompressorSignalsMixin.settingsChanged)
    def audioCodec(self) -> str:
        return self._audio_codec

    @audioCodec.setter
    def audioCodec(self, val: str):
        v = str(val or "auto").strip().lower()
        if v in ("auto", "copy", "aac", "opus") and v != self._audio_codec:
            self._audio_codec = v
            self.settingsChanged.emit()

    @Property(str, notify=DecompressorSignalsMixin.settingsChanged)
    def customVideoArgs(self) -> str:
        return self._custom_video_args

    @customVideoArgs.setter
    def customVideoArgs(self, val: str):
        v = str(val or "").strip()
        if v != self._custom_video_args:
            self._custom_video_args = v
            self.settingsChanged.emit()

    @Slot(result="QVariantMap")
    def testCompressionPreset(self) -> Dict[str, Any]:
        """Validates current encoder, preset, audio codec, and parameters on a mini test video frame."""
        s = self._media_settings()
        if not s.ffmpeg:
            return {"success": False, "message": "FFmpeg is not installed or detected."}
        ok, msg = validate_ffmpeg_settings(s.ffmpeg, s)
        return {"success": ok, "message": msg}

    @Slot()
    def testCompressionPresetAsync(self) -> None:
        """Non-blocking companion to testCompressionPreset (answer: presetTestFinished(dict))."""
        def _worker():
            try:
                res = self.testCompressionPreset()
            except Exception as e:
                res = {"success": False, "message": f"Validation error: {e}"}
            self._guiCall.emit(lambda: self.presetTestFinished.emit(res))
        threading.Thread(target=_worker, daemon=True, name="DecompressorPresetTest").start()

    @Property(str, notify=DecompressorSignalsMixin.settingsChanged)
    def animatedFormat(self) -> str:
        """Animated pictures: "same" (each keeps its format), gif / png / webp / avif, or "keep"."""
        return self._animated_format

    @animatedFormat.setter
    def animatedFormat(self, val: str):
        v = str(val or "").lower()
        if v in ("same", "gif", "png", "webp", "avif", "keep") and v != self._animated_format:
            self._animated_format = v
            self.settingsChanged.emit()

    @Property(int, notify=DecompressorSignalsMixin.settingsChanged)
    def animatedQuality(self) -> int:
        return self._animated_quality

    @animatedQuality.setter
    def animatedQuality(self, val: int):
        v = max(1, min(100, int(val)))
        if v != self._animated_quality:
            self._animated_quality = v
            self.settingsChanged.emit()

    @Property(bool, notify=DecompressorSignalsMixin.settingsChanged)
    def headerCollapsed(self) -> bool:
        """The top card's options folded away (remembered)."""
        return self._header_collapsed

    @headerCollapsed.setter
    def headerCollapsed(self, val: bool):
        if self._header_collapsed != bool(val):
            self._header_collapsed = bool(val)
            self.settingsChanged.emit()

    @Property(bool, notify=DecompressorSignalsMixin.ffmpegChanged)
    def ffmpegAvailable(self) -> bool:
        return bool(self._ffmpeg_path) and os.path.isfile(self._ffmpeg_path)

    @Property(bool, notify=DecompressorSignalsMixin.ffmpegChanged)
    def ffmpegDownloading(self) -> bool:
        return self._ffmpeg_downloading

    @Property(float, notify=DecompressorSignalsMixin.ffmpegChanged)
    def ffmpegProgress(self) -> float:
        return self._ffmpeg_progress

    @Property(str, notify=DecompressorSignalsMixin.ffmpegChanged)
    def ffmpegMessage(self) -> str:
        return self._ffmpeg_message

    @Slot()
    def downloadFfmpeg(self):
        """Downloads FFmpeg (needed for videos) in the background."""
        if self._ffmpeg_downloading:
            return
        self._ffmpeg_downloading = True
        self._ffmpeg_progress = 0.0
        self._ffmpeg_message = ""
        self.ffmpegChanged.emit()
        last = [0.0]

        def _progress(done, total):
            now = time.time()
            if total and now - last[0] > 0.2:
                last[0] = now
                self._ffmpeg_progress = done / total * 100
                self.ffmpegChanged.emit()

        def _worker():
            ok, msg = self._ffmpeg_downloader.download(_progress)
            if ok:
                self._ffmpeg_path = msg
                self._ffmpeg_message = ""
                self._hwaccel_probed_path = ""
                self._detected_hwaccel = ""
                self._available_hwaccels = []
            else:
                self._ffmpeg_message = "" if msg == "Cancelled" else msg
                if msg != "Cancelled":
                    logger.warning(msg, category="ffmpeg")
            self._ffmpeg_downloading = False
            self.ffmpegChanged.emit()
        threading.Thread(target=_worker, daemon=True, name="FfmpegDownload").start()

    @Slot()
    def cancelFfmpegDownload(self):
        self._ffmpeg_downloader.cancel_event.set()

    def _media_settings(self) -> CompressSettings:
        """The formats and qualities chosen (shared by the Decompressor and the Gallery)."""
        return CompressSettings(image_format=self._image_format, image_quality=self._image_quality,
                                video_format=self._video_format, video_quality=self._video_quality,
                                video_hwaccel=self._video_hwaccel,
                                video_preset=self._video_preset, audio_codec=self._audio_codec,
                                custom_video_args=self._custom_video_args,
                                animated_format=self._animated_format, animated_quality=self._animated_quality,
                                ffmpeg=self._ffmpeg_path if self.ffmpegAvailable else "")

    def _compress_settings(self) -> Optional[CompressSettings]:
        if not self._compress_after:
            return None
        s = self._media_settings()
        if s.video_format != "keep" and not s.ffmpeg:
            logger.warning("Videos aren't compressed: FFmpeg isn't installed (Decompressor → Compress after "
                           "extracting → Download FFmpeg).", category="decompressor")
        return s if (s.images_on or s.videos_on or s.animated_on) else None

    @Property(bool, notify=DecompressorSignalsMixin.compressingPathsChanged)
    def compressingPaths(self) -> bool:
        return self._compressing_paths

    @Slot("QVariantList", result="QVariantList")
    def compressibleFiles(self, paths):
        """The files among `paths` that can be compressed at all: still pictures (JPG, PNG, BMP, TIFF), animated
        ones (GIF, animated PNG / WebP / AVIF) and videos. Folders and other files aren't. The Gallery offers
        "Compress pictures & videos…" only when there's one."""
        any_format = CompressSettings(image_format="webp", video_format="h265", animated_format="same", ffmpeg="ffmpeg")
        out = []
        for p in list(paths or [])[:20000]:
            p = str(p or "")
            if p and os.path.isfile(p) and classify(p, any_format):
                out.append(p)
        return out

    @Slot("QVariantList")
    def countMediaPaths(self, paths):
        """How many pictures / videos / animated pictures the chosen items hold (in the background: a
        folder can hold a lot). Answers with mediaCountReady; a newer question replaces an older one."""
        self._count_gen += 1
        gen = self._count_gen
        settings = self._media_settings()
        paths = [str(p) for p in (paths or []) if p]

        def _worker():
            stop = threading.Event()
            images, videos, animated = media_in(paths, settings, stop)
            if gen != self._count_gen:
                return
            total = 0
            for p in images + videos + animated:
                try:
                    total += os.path.getsize(p)
                except OSError:
                    pass
            self.mediaCountReady.emit(len(images), len(videos), len(animated), total)
        threading.Thread(target=_worker, daemon=True, name="MediaCount").start()

    @Slot("QVariantList")
    def compressPaths(self, paths):
        """Compresses the pictures and videos among the chosen files and folders with the chosen formats.
        The originals are kept until the user answers (removeCompressedOriginals / keepCompressedOriginals)."""
        if self._compressing_paths:
            return
        paths = [str(p) for p in (paths or []) if p]
        settings = self._media_settings()
        self._paths_cancel.clear()
        self._compressing_paths = True
        self.compressingPathsChanged.emit()
        last = [0.0]

        def _progress(pct, name=""):
            now = time.time()
            if now - last[0] >= 0.1 or pct >= 100:
                last[0] = now
                self.compressPathsProgress.emit(float(pct), name)

        def _worker():
            r = CompressResult()
            try:
                found = media_in(paths, settings, self._paths_cancel)
                r = compress_paths(paths, settings, cancel=self._paths_cancel, on_progress=_progress,
                                   procs=self._compress_procs, found=found)
                if r.compressed:
                    self._pending_originals = list(r.compressed)
                    self._pending_source = "gallery"
                logger.info(f"🗜 Gallery: {len(r.compressed)} file(s) compressed, {_format_bytes(r.bytes_before)} → "
                            f"{_format_bytes(r.bytes_after)}" + (f", {len(r.failed)} couldn't be" if r.failed else ""),
                            category="decompressor", details="\n".join(r.failed[:50]) if r.failed else "")
            except Exception as e:
                logger.exception("Gallery compression failed", category="decompressor")
                r.failed.append(str(e))
            finally:
                self._compressing_paths = False
                self.compressingPathsChanged.emit()
                self.compressPathsFinished.emit(len(r.compressed), r.bytes_before, r.bytes_after, len(r.failed),
                                                r.skipped, self._paths_cancel.is_set())
        threading.Thread(target=_worker, daemon=True, name="GalleryCompress").start()

    @Slot()
    def cancelCompressPaths(self):
        self._paths_cancel.set()
        for proc in list(self._compress_procs):
            try:
                proc.kill()
            except Exception:
                pass

    @Slot()
    def removeCompressedOriginals(self):
        """The user's answer at the end: the originals of the compressed files go to the Recycle Bin."""
        pairs, self._pending_originals = self._pending_originals, []
        source = self._pending_source
        if not pairs:
            return

        def _worker():
            from PySide6.QtCore import QFile
            moved, freed, kept = 0, 0, 0
            for orig, new in pairs:
                try:
                    if not (os.path.exists(orig) and os.path.exists(new)):
                        kept += 1
                        continue
                    size = os.path.getsize(orig)
                    if not QFile.moveToTrash(orig):
                        kept += 1
                        continue
                    moved += 1
                    freed += size - os.path.getsize(new)
                    # "clip (compressed).mp4" takes the original's name once it's gone
                    if os.path.normcase(os.path.splitext(new)[0]) == os.path.normcase(os.path.splitext(orig)[0] + " (compressed)") \
                            and os.path.splitext(new)[1].lower() == os.path.splitext(orig)[1].lower() and not os.path.exists(orig):
                        os.replace(new, orig)
                except OSError as e:
                    kept += 1
                    logger.debug(f"Couldn't move {orig} to the Recycle Bin: {e}", category="decompressor")
            msg = f"Moved {moved} original(s) to the Recycle Bin, {_format_bytes(max(0, freed))} saved."
            if kept:
                msg += f" {kept} couldn't be moved and were kept."
            logger.success(msg, category="decompressor")
            (self.galleryOriginalsHandled if source == "gallery" else self.originalsHandled).emit(msg)
        threading.Thread(target=_worker, daemon=True, name="CompressOriginals").start()

    @Slot()
    def keepCompressedOriginals(self):
        n = len(self._pending_originals)
        self._pending_originals = []
        if n:
            logger.info(f"Kept the {n} original(s) next to their compressed copies.", category="decompressor")
            (self.galleryOriginalsHandled if self._pending_source == "gallery" else self.originalsHandled).emit("")
