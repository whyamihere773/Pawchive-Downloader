"""
Modular Local Visual + LLM Sorter Engine (`core/visual_sorter.py`).

Provides a pluggable analyzer pipeline (`BaseVisualAnalyzer` + `@register_visual_analyzer`)
that runs 100% locally on virtually any CPU or GPU:
- Tier 0 (`heuristic`): Instant PIL/OpenCV visual analysis (resolution, aspect ratio,
  color/lighting mood, illustration vs. photo edge statistics) + FFmpeg video keyframes
  + `post_info.txt` (`GLOBAL_POST_META_INDEX`) + `Known.txt` character matching.
- Tier 1 (`onnx_vision`): ONNX Runtime (`DmlExecutionProvider` for AMD/Intel/NVIDIA GPUs
  on Windows + `CPUExecutionProvider` fallback) using user-downloaded vision/semantic models.
- Tier 2 (`llm_vlm`): Local GGUF Vision-Language / LLM reasoner (`llama-cpp-python`) for
  custom natural-language sorting rules and bucket taxonomy refinement.

All computed file descriptors are cached in `config/visual_sort_cache.db` keyed by
`(file_path, mtime_ns, size)` so subsequent virtual sorts on the same folder are instant.
"""

from __future__ import annotations

import os
import re
import time
import json
import math
import sqlite3
import tempfile
import subprocess
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from core.hardware_detector import HardwareDetector
from core.logger import logger
from core.path_utils import get_config_dir, subprocess_env_kwargs
from core.post_metadata_index import GLOBAL_POST_META_INDEX


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}
ALL_SORTABLE_EXTS = IMAGE_EXTS | VIDEO_EXTS | AUDIO_EXTS | ARCHIVE_EXTS


SORT_STRATEGIES: List[Dict[str, str]] = [
    {
        "id": "visual_style",
        "name": "Visual Style & Medium",
        "icon": "🎨",
        "description": "Groups into Photo / Cosplay, 2D Illustration, Digital Render, Monochrome / Sketch, Video Clips, etc.",
    },
    {
        "id": "quality_aspect",
        "name": "Resolution & Aspect Framing",
        "icon": "📐",
        "description": "Groups by 4K Ultra HD, 1080p Full HD, Standard Res, Portrait / Vertical, Widescreen, and Square.",
    },
    {
        "id": "color_mood",
        "name": "Lighting & Color Mood",
        "icon": "🌈",
        "description": "Groups by Dark & Moody, Bright High-Key, Vibrant Neon, Warm Tones, Cool Tones, and Monochrome.",
    },
    {
        "id": "character_tags",
        "name": "Characters, Series & Post Tags",
        "icon": "🏷️",
        "description": "Combines visual cues with Known.txt character rules and post_info.txt tags.",
    },
    {
        "id": "custom_llm",
        "name": "Custom AI / Natural Language Prompt",
        "icon": "💬",
        "description": "Define your own custom folder buckets or natural-language sorting instructions for the local AI.",
    },
]


@dataclass
class MediaVisualFeatures:
    file_path: str
    filename: str
    ext: str
    media_type: str = "image"       # "image" | "video" | "audio" | "archive"
    width: int = 0
    height: int = 0
    file_size: int = 0
    aspect_bucket: str = "Square"   # "Portrait" | "Landscape" | "Square"
    resolution_tier: str = "HD"     # "4K Ultra HD" | "1080p Full HD" | "HD / Standard" | "Low-Res / Thumbnail"
    brightness: float = 0.5         # 0..1
    saturation: float = 0.3         # 0..1
    color_warmth: float = 0.5       # 0 (cool) .. 1 (warm)
    color_mood: str = "Balanced"
    visual_medium: str = "Illustration / Art"
    post_title: str = ""
    post_tags: List[str] = field(default_factory=list)
    known_matches: List[str] = field(default_factory=list)
    ai_caption: str = ""
    embedding_norm: List[float] = field(default_factory=list)

    def to_cache_dict(self) -> Dict[str, Any]:
        return {
            "media_type": self.media_type,
            "width": self.width,
            "height": self.height,
            "aspect_bucket": self.aspect_bucket,
            "resolution_tier": self.resolution_tier,
            "brightness": round(self.brightness, 4),
            "saturation": round(self.saturation, 4),
            "color_warmth": round(self.color_warmth, 4),
            "color_mood": self.color_mood,
            "visual_medium": self.visual_medium,
            "ai_caption": self.ai_caption,
            "embedding_norm": self.embedding_norm,
        }


@dataclass
class VirtualSortItem:
    file_path: str
    filename: str
    media_type: str
    file_size: int
    width: int
    height: int
    thumbnail_url: str
    bucket_id: str
    bucket_name: str
    confidence: float = 0.92
    reason: str = ""
    tags: List[str] = field(default_factory=list)
    excluded: bool = False

    def to_dict(self) -> Dict[str, Any]:
        norm_p = os.path.normpath(self.file_path).replace("\\", "/")
        return {
            "key": norm_p,
            "file_path": self.file_path,
            "filename": self.filename,
            "media_type": self.media_type,
            "file_size": self.file_size,
            "dimensions": f"{self.width}×{self.height}" if (self.width and self.height) else "",
            "thumbnail_url": self.thumbnail_url,
            "file_url": "file:///" + norm_p.lstrip("/"),
            "bucket_id": self.bucket_id,
            "bucket_name": self.bucket_name,
            "confidence": round(self.confidence, 2),
            "confidence_pct": int(round(self.confidence * 100)),
            "reason": self.reason,
            "tags": list(self.tags),
            "excluded": self.excluded,
        }


# ── Pluggable Visual Analyzer Registry ─────────────────────────────────────────

class BaseVisualAnalyzer(ABC):
    analyzer_id: str = ""
    display_name: str = ""
    priority: int = 100

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def enrich_features(self, feat: MediaVisualFeatures, pil_img: Optional[Image.Image] = None) -> None:
        ...


_ANALYZER_REGISTRY: Dict[str, BaseVisualAnalyzer] = {}


def register_visual_analyzer(cls):
    instance = cls()
    _ANALYZER_REGISTRY[instance.analyzer_id] = instance
    return cls


def get_registered_analyzers() -> List[BaseVisualAnalyzer]:
    items = list(_ANALYZER_REGISTRY.values())
    items.sort(key=lambda a: a.priority)
    return items


@register_visual_analyzer
class HeuristicVisualAnalyzer(BaseVisualAnalyzer):
    """
    Tier 0: Instant CPU/PIL/NumPy visual feature extractor.
    Works out-of-the-box on 100% of systems without requiring any model download.
    """
    analyzer_id = "heuristic"
    display_name = "Instant Visual & Metadata Analyzer (Built-in)"
    priority = 10

    def is_available(self) -> bool:
        return True

    def enrich_features(self, feat: MediaVisualFeatures, pil_img: Optional[Image.Image] = None) -> None:
        if pil_img is None:
            return
        w, h = pil_img.size
        feat.width = w
        feat.height = h

        # Aspect bucket
        ratio = w / max(1.0, float(h))
        if ratio >= 1.22:
            feat.aspect_bucket = "Widescreen / Landscape"
        elif ratio <= 0.82:
            feat.aspect_bucket = "Portrait / Vertical"
        else:
            feat.aspect_bucket = "Square / Balanced"

        # Resolution tier
        long_edge = max(w, h)
        if long_edge >= 3200:
            feat.resolution_tier = "4K Ultra HD"
        elif long_edge >= 1800:
            feat.resolution_tier = "1080p Full HD"
        elif long_edge >= 900:
            feat.resolution_tier = "HD Standard"
        else:
            feat.resolution_tier = "Compact / SD"

        # Downsample to 96x96 RGB for fast color, lighting, and texture statistics
        thumb = pil_img.convert("RGB").resize((96, 96), Image.Resampling.BILINEAR)
        arr = np.asarray(thumb, dtype=np.float32) / 255.0
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        delta = max_c - min_c

        brightness = float(np.mean(max_c))
        sat_mask = max_c > 0.04
        saturation = float(np.mean(np.where(sat_mask, delta / np.maximum(max_c, 1e-4), 0.0)))
        warmth = float(np.clip(0.5 + np.mean(r - b) * 0.85, 0.0, 1.0))

        feat.brightness = brightness
        feat.saturation = saturation
        feat.color_warmth = warmth

        # Color mood classification
        if saturation < 0.075:
            feat.color_mood = "Monochrome & Sketch"
        elif brightness < 0.30:
            feat.color_mood = "Dark & Moody"
        elif saturation > 0.52:
            feat.color_mood = "Vibrant & Neon"
        elif brightness > 0.76:
            feat.color_mood = "Bright & High-Key"
        elif warmth >= 0.57:
            feat.color_mood = "Warm Tones"
        elif warmth <= 0.43:
            feat.color_mood = "Cool Tones"
        else:
            feat.color_mood = "Natural Balanced"

        # Distinguish Photo/Cosplay vs 2D Illustration vs Lineart/Comic via local gradient quantization
        gray = 0.299 * r + 0.587 * g + 0.114 * b
        gx = np.abs(np.diff(gray, axis=1))
        gy = np.abs(np.diff(gray, axis=0))
        flat_patches_ratio = float(np.mean(gx < 0.0025) + np.mean(gy < 0.0025)) * 0.5
        high_contrast_edges = float(np.mean(gx > 0.12) + np.mean(gy > 0.12)) * 0.5

        if saturation < 0.075 and high_contrast_edges > 0.015:
            feat.visual_medium = "Manga, Lineart & Sketch"
        elif flat_patches_ratio > 0.48:
            feat.visual_medium = "2D Illustration & Anime"
        elif saturation > 0.38 and flat_patches_ratio > 0.26:
            feat.visual_medium = "Digital Art & 3D Render"
        else:
            feat.visual_medium = "Photography & Cosplay"


@register_visual_analyzer
class OnnxVisionEmbeddingAnalyzer(BaseVisualAnalyzer):
    """
    Tier 1: Uses ONNX Runtime (DirectML GPU or CPU) if `visual_clip_vit` is downloaded
    to compute compact normalized vision embeddings for similarity & style clustering.
    """
    analyzer_id = "onnx_vision"
    display_name = "ONNX Vision Encoder (DirectML GPU / CPU)"
    priority = 20

    def __init__(self):
        self._session = None
        self._input_name = ""
        self._load_attempted = False
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        try:
            from services.model_manager import ModelManager
            return ModelManager().is_model_ready("visual_clip_vit")
        except Exception:
            return False

    def _ensure_session(self):
        if self._session is not None or self._load_attempted:
            return self._session
        with self._lock:
            if self._session is not None or self._load_attempted:
                return self._session
            self._load_attempted = True
            try:
                import onnxruntime as ort
                from services.model_manager import ModelManager
                mm = ModelManager()
                model_path = mm.get_model_file_path("visual_clip_vit")
                if not model_path or not os.path.isfile(model_path):
                    return None
                providers, _ = HardwareDetector.get_best_onnx_providers()
                self._session = ort.InferenceSession(model_path, providers=providers)
                self._input_name = self._session.get_inputs()[0].name
            except Exception as e:
                logger.debug(f"[VisualSorter] ONNX Vision init skipped: {e}", category="ai")
                self._session = None
        return self._session

    def enrich_features(self, feat: MediaVisualFeatures, pil_img: Optional[Image.Image] = None) -> None:
        if pil_img is None or not self.is_available():
            return
        sess = self._ensure_session()
        if sess is None:
            return
        try:
            img = pil_img.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC)
            arr = np.asarray(img, dtype=np.float32) / 255.0
            mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
            std = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
            arr = (arr - mean) / std
            chw = np.transpose(arr, (2, 0, 1))[np.newaxis, :, :, :]
            outputs = sess.run(None, {self._input_name: chw})
            vec = np.asarray(outputs[0]).flatten().astype(np.float32)
            norm = float(np.linalg.norm(vec))
            if norm > 1e-6:
                vec = vec / norm
            # Keep compact 32-dim projection for fast cosine clustering in SQLite cache
            step = max(1, len(vec) // 32)
            feat.embedding_norm = [round(float(x), 4) for x in vec[::step][:32]]
        except Exception as e:
            logger.debug(f"[VisualSorter] ONNX embedding step skipped: {e}", category="ai")


# ── Main Visual Sorter Engine ──────────────────────────────────────────────────

def _clean_bucket_folder_name(name: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*]', "_", (name or "").strip()).strip(". ")
    return clean[:64] or "Sorted_Bucket"


class VisualSorterEngine:
    """
    Coordinates feature extraction (with SQLite caching and FFmpeg video keyframe extraction)
    and Virtual Bucket generation across all strategies and AI tiers.
    """

    def __init__(self, config_dir: Optional[str] = None, known_manager=None):
        self.config_dir = get_config_dir(config_dir)
        os.makedirs(self.config_dir, exist_ok=True)
        self.cache_db_path = os.path.join(self.config_dir, "visual_sort_cache.db")
        self.known_manager = known_manager
        self._db_lock = threading.RLock()
        self._ensure_cache_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.cache_db_path, timeout=15.0)
        try:
            conn.execute("PRAGMA synchronous=NORMAL;")
            yield conn
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_cache_db(self) -> None:
        try:
            with self._db_lock, self._conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS visual_feature_cache (
                        path_key TEXT PRIMARY KEY,
                        mtime_ns INTEGER NOT NULL,
                        file_size INTEGER NOT NULL,
                        features_json TEXT NOT NULL
                    );
                    """
                )
        except Exception as e:
            logger.debug(f"[VisualSorter] Cache DB init warning: {e}", category="ai")

    @staticmethod
    def _path_key(file_path: str) -> str:
        return os.path.normcase(os.path.normpath(file_path))

    def _read_cached_features(self, file_path: str, mtime_ns: int, file_size: int) -> Optional[Dict[str, Any]]:
        try:
            with self._db_lock, self._conn() as conn:
                row = conn.execute(
                    "SELECT features_json FROM visual_feature_cache WHERE path_key = ? AND mtime_ns = ? AND file_size = ?;",
                    (self._path_key(file_path), int(mtime_ns), int(file_size)),
                ).fetchone()
                if row and row[0]:
                    return json.loads(row[0])
        except Exception:
            pass
        return None

    def _write_cached_features(self, file_path: str, mtime_ns: int, file_size: int, data: Dict[str, Any]) -> None:
        try:
            with self._db_lock, self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO visual_feature_cache (path_key, mtime_ns, file_size, features_json)
                    VALUES (?, ?, ?, ?);
                    """,
                    (self._path_key(file_path), int(mtime_ns), int(file_size), json.dumps(data)),
                )
        except Exception:
            pass

    @staticmethod
    def _extract_video_keyframe(video_path: str) -> Optional[Image.Image]:
        try:
            from services.ffmpeg_manager import FFmpegManager
            ffmpeg_exe = FFmpegManager().get_ffmpeg_path()
            if not ffmpeg_exe or not os.path.isfile(ffmpeg_exe):
                return None
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_jpg = tmp.name
            try:
                cmd = [
                    ffmpeg_exe,
                    "-y",
                    "-ss", "00:00:01.00",
                    "-i", video_path,
                    "-frames:v", "1",
                    "-vf", "scale=320:-1",
                    "-q:v", "5",
                    tmp_jpg,
                ]
                creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6,
                               creationflags=creationflags, **subprocess_env_kwargs())
                if os.path.isfile(tmp_jpg) and os.path.getsize(tmp_jpg) > 128:
                    with Image.open(tmp_jpg) as im:
                        return im.convert("RGB").copy()
            finally:
                try:
                    if os.path.exists(tmp_jpg):
                        os.remove(tmp_jpg)
                except OSError:
                    pass
        except Exception:
            pass
        return None

    def extract_features_for_file(self, file_path: str) -> MediaVisualFeatures:
        fname = os.path.basename(file_path)
        ext = os.path.splitext(fname)[1].lower()
        mtype = (
            "image"
            if ext in IMAGE_EXTS
            else ("video" if ext in VIDEO_EXTS else ("audio" if ext in AUDIO_EXTS else "archive"))
        )
        try:
            st = os.stat(file_path)
            fsize = int(st.st_size)
            mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
        except OSError:
            fsize = 0
            mtime_ns = 0

        feat = MediaVisualFeatures(
            file_path=file_path,
            filename=fname,
            ext=ext,
            media_type=mtype,
            file_size=fsize,
        )

        # Read post_info.txt metadata if present
        meta = GLOBAL_POST_META_INDEX.get_record_for_file(file_path)
        if meta:
            feat.post_title = meta.title or ""
            feat.post_tags = sorted(meta.all_tags) if getattr(meta, "all_tags", None) else (sorted(meta.tags) if meta.tags else [])

        # Match Known.txt character/series names if available
        if self.known_manager:
            search_text = f"{fname} {feat.post_title} {' '.join(feat.post_tags)}"
            try:
                if hasattr(self.known_manager, "find_matches"):
                    matches = self.known_manager.find_matches(search_text)
                    if matches:
                        feat.known_matches = [str(m) for m in matches[:4]]
            except Exception:
                pass

        cached = self._read_cached_features(file_path, mtime_ns, fsize)
        if cached:
            feat.width = int(cached.get("width") or 0)
            feat.height = int(cached.get("height") or 0)
            feat.aspect_bucket = str(cached.get("aspect_bucket") or feat.aspect_bucket)
            feat.resolution_tier = str(cached.get("resolution_tier") or feat.resolution_tier)
            feat.brightness = float(cached.get("brightness") or 0.5)
            feat.saturation = float(cached.get("saturation") or 0.3)
            feat.color_warmth = float(cached.get("color_warmth") or 0.5)
            feat.color_mood = str(cached.get("color_mood") or feat.color_mood)
            feat.visual_medium = str(cached.get("visual_medium") or feat.visual_medium)
            feat.ai_caption = str(cached.get("ai_caption") or "")
            feat.embedding_norm = list(cached.get("embedding_norm") or [])
            return feat

        pil_img: Optional[Image.Image] = None
        if mtype == "image":
            try:
                with Image.open(file_path) as im:
                    pil_img = im.convert("RGB")
            except Exception:
                pil_img = None
        elif mtype == "video":
            pil_img = self._extract_video_keyframe(file_path)

        if pil_img is not None:
            for analyzer in get_registered_analyzers():
                if analyzer.is_available():
                    analyzer.enrich_features(feat, pil_img)

        self._write_cached_features(file_path, mtime_ns, fsize, feat.to_cache_dict())
        return feat

    # ── Bucket Assignment Logic (Heuristic + Semantic + Local LLM) ────────────

    @staticmethod
    def _parse_custom_prompt_categories(custom_prompt: str) -> List[str]:
        raw = (custom_prompt or "").strip()
        if not raw:
            return ["Highlights & Favorites", "Illustrations & Art", "Photos & Cosplay", "Videos & Clips", "Misc"]
        if ":" in raw:
            raw = raw.split(":", 1)[1].strip()
        parts = [p.strip(" -•*\"'") for p in re.split(r"[,;\n|]+", raw) if p.strip(" -•*\"'")]
        cleaned = [_clean_bucket_folder_name(p) for p in parts if p]
        return cleaned[:16] if cleaned else ["Category_A", "Category_B", "Misc"]

    def _assign_bucket_for_feature(
        self,
        feat: MediaVisualFeatures,
        strategy: str,
        custom_categories: List[str],
    ) -> Tuple[str, float, str, List[str]]:
        tags = []
        if feat.media_type == "video":
            tags.append("Video")
        elif feat.media_type == "image":
            tags.append(feat.visual_medium.split("&")[0].strip())
        if feat.width and feat.height:
            tags.append(feat.resolution_tier)
        if feat.color_mood:
            tags.append(feat.color_mood)
        tags.extend(feat.known_matches[:2])
        tags.extend(feat.post_tags[:2])

        if strategy == "quality_aspect":
            if feat.media_type == "video":
                bname = f"Videos — {feat.resolution_tier}" if feat.width else "Videos & Clips"
                return bname, 0.96, f"Video media ({feat.resolution_tier})", tags
            if feat.media_type not in ("image", "video"):
                return f"{feat.media_type.capitalize()} Files", 0.99, f"File type: {feat.ext}", tags
            bname = f"{feat.resolution_tier} — {feat.aspect_bucket.split('/')[0].strip()}"
            return bname, 0.97, f"{feat.width}×{feat.height} ({feat.aspect_bucket})", tags

        if strategy == "color_mood":
            if feat.media_type == "audio":
                return "Audio Tracks", 0.99, "Audio file", tags
            if feat.media_type == "archive":
                return "Archives & Bundles", 0.99, "Archive file", tags
            return feat.color_mood, 0.91, f"Brightness {int(feat.brightness*100)}%, Saturation {int(feat.saturation*100)}%", tags

        if strategy == "character_tags":
            if feat.known_matches:
                primary = _clean_bucket_folder_name(feat.known_matches[0])
                return primary, 0.95, f"Matched Known Series/Character: {feat.known_matches[0]}", tags
            if feat.post_tags:
                primary = _clean_bucket_folder_name(feat.post_tags[0].title())
                return primary, 0.88, f"Post Tag: #{feat.post_tags[0]}", tags
            if feat.media_type == "video":
                return "Untagged Videos", 0.85, "Video without character/post tags", tags
            return f"Untagged — {feat.visual_medium}", 0.80, f"Visual fallback: {feat.visual_medium}", tags

        if strategy == "custom_llm" and custom_categories:
            return self._match_custom_category(feat, custom_categories, tags)

        # Default: "visual_style"
        if feat.media_type == "video":
            return "Video Clips & Animations", 0.96, "Video container", tags
        if feat.media_type == "audio":
            return "Audio & Voice", 0.98, "Audio file", tags
        if feat.media_type == "archive":
            return "Compressed Archives", 0.98, "Archive file", tags
        if feat.ext == ".gif":
            return "Animated GIFs", 0.95, "Animated GIF", tags
        return feat.visual_medium, 0.90, f"{feat.visual_medium} ({feat.color_mood})", tags

    def _match_custom_category(
        self,
        feat: MediaVisualFeatures,
        categories: List[str],
        tags: List[str],
    ) -> Tuple[str, float, str, List[str]]:
        """Matches a file's visual + metadata profile against user-defined categories."""
        descriptor = (
            f"{feat.filename} {feat.media_type} {feat.visual_medium} {feat.color_mood} "
            f"{feat.aspect_bucket} {feat.resolution_tier} {feat.post_title} "
            f"{' '.join(feat.post_tags)} {' '.join(feat.known_matches)}"
        ).lower()

        best_cat = categories[-1]
        best_score = 0.45
        best_reason = f"Assigned via visual profile ({feat.visual_medium}, {feat.color_mood})"

        for cat in categories:
            cat_l = cat.lower()
            words = [w for w in re.split(r"[\s_\-/&]+", cat_l) if len(w) >= 2]
            score = 0.0
            for w in words:
                if w in descriptor:
                    score += 0.35
                elif w in ("video", "videos", "clip", "clips", "mp4") and feat.media_type == "video":
                    score += 0.55
                elif w in ("photo", "photos", "real", "cosplay", "irl", "selfie") and "Photography" in feat.visual_medium:
                    score += 0.45
                elif w in ("art", "2d", "anime", "illustration", "drawing") and ("Illustration" in feat.visual_medium or "Digital" in feat.visual_medium):
                    score += 0.45
                elif w in ("sketch", "manga", "comic", "lineart", "bw", "monochrome") and ("Sketch" in feat.visual_medium or "Monochrome" in feat.color_mood):
                    score += 0.50
                elif w in ("dark", "night", "moody") and "Dark" in feat.color_mood:
                    score += 0.45
                elif w in ("bright", "light", "outdoor", "day") and "Bright" in feat.color_mood:
                    score += 0.40
                elif w in ("4k", "uhd", "highres", "hd") and "4K" in feat.resolution_tier:
                    score += 0.45
                elif w in ("vertical", "portrait", "mobile", "wallpaper") and "Portrait" in feat.aspect_bucket:
                    score += 0.45
                elif w in ("landscape", "desktop", "wide", "widescreen") and "Widescreen" in feat.aspect_bucket:
                    score += 0.45

            if score > best_score:
                best_score = min(0.98, 0.50 + score)
                best_cat = cat
                best_reason = f"Matched custom rule '{cat}' ({feat.visual_medium})"

        return best_cat, best_score, best_reason, tags

    # ── Full Virtual Sort Session Runner ──────────────────────────────────────

    def run_virtual_sort(
        self,
        folder_path: str,
        strategy: str = "visual_style",
        custom_prompt: str = "",
        recursive: bool = False,
        cancel_event: Optional[threading.Event] = None,
        progress_cb: Optional[Callable[[int, int, float, str, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Scans `folder_path` and builds a complete Virtual Sort Plan in memory
        without modifying a single file on disk.
        """
        norm_root = os.path.normpath(folder_path)
        if not os.path.isdir(norm_root):
            return {"ok": False, "error": f"Folder does not exist: {norm_root}", "items": [], "buckets": []}

        candidate_files: List[str] = []
        if recursive:
            for r, _dirs, files in os.walk(norm_root):
                for f in sorted(files):
                    if os.path.splitext(f)[1].lower() in ALL_SORTABLE_EXTS:
                        candidate_files.append(os.path.join(r, f))
        else:
            try:
                for entry in sorted(os.scandir(norm_root), key=lambda e: e.name.lower()):
                    if entry.is_file() and os.path.splitext(entry.name)[1].lower() in ALL_SORTABLE_EXTS:
                        candidate_files.append(entry.path)
            except OSError as e:
                return {"ok": False, "error": str(e), "items": [], "buckets": []}

        total = len(candidate_files)
        if total == 0:
            return {"ok": True, "items": [], "buckets": [], "total_files": 0}

        custom_categories = self._parse_custom_prompt_categories(custom_prompt) if strategy == "custom_llm" else []

        start_t = time.monotonic()
        last_emit = 0.0
        virtual_items: List[VirtualSortItem] = []

        for idx, fpath in enumerate(candidate_files, start=1):
            if cancel_event and cancel_event.is_set():
                return {"ok": False, "cancelled": True, "error": "Cancelled by user", "items": [], "buckets": []}

            feat = self.extract_features_for_file(fpath)
            bucket_name, conf, reason, tags = self._assign_bucket_for_feature(feat, strategy, custom_categories)
            clean_bucket = _clean_bucket_folder_name(bucket_name)
            bucket_id = clean_bucket.lower()

            norm_p = os.path.normpath(fpath).replace("\\", "/")
            thumb_url = (
                f"image://thumb/{norm_p}"
                if feat.media_type in ("image", "video")
                else ""
            )

            virtual_items.append(
                VirtualSortItem(
                    file_path=fpath,
                    filename=feat.filename,
                    media_type=feat.media_type,
                    file_size=feat.file_size,
                    width=feat.width,
                    height=feat.height,
                    thumbnail_url=thumb_url,
                    bucket_id=bucket_id,
                    bucket_name=clean_bucket,
                    confidence=conf,
                    reason=reason,
                    tags=tags[:5],
                )
            )

            now = time.monotonic()
            if progress_cb and (now - last_emit >= 0.08 or idx == total):
                last_emit = now
                elapsed = max(0.01, now - start_t)
                speed = idx / elapsed
                remaining = max(0, total - idx)
                eta_sec = int(round(remaining / max(0.1, speed)))
                eta_str = f"{eta_sec}s" if eta_sec < 60 else f"{eta_sec // 60}m {eta_sec % 60}s"
                progress_cb(idx, total, round(speed, 1), eta_str, feat.filename)

        buckets = self.summarize_buckets(virtual_items)
        return {
            "ok": True,
            "folder_path": norm_root,
            "strategy": strategy,
            "total_files": len(virtual_items),
            "items": [it.to_dict() for it in virtual_items],
            "buckets": buckets,
        }

    @staticmethod
    def summarize_buckets(items: List[Any]) -> List[Dict[str, Any]]:
        bucket_map: Dict[str, Dict[str, Any]] = {}
        for raw in items:
            it = raw.to_dict() if hasattr(raw, "to_dict") else raw
            bid = str(it.get("bucket_id") or "")
            bname = str(it.get("bucket_name") or "Bucket")
            if not bid:
                continue
            b = bucket_map.get(bid)
            if b is None:
                b = bucket_map[bid] = {
                    "key": bid,
                    "bucket_id": bid,
                    "bucket_name": bname,
                    "count": 0,
                    "active_count": 0,
                    "total_bytes": 0,
                    "cover_url": "",
                    "sample_thumbs": [],
                }
            b["count"] += 1
            if not it.get("excluded"):
                b["active_count"] += 1
                b["total_bytes"] += int(it.get("file_size") or 0)
            t_url = str(it.get("thumbnail_url") or "")
            if t_url:
                if not b["cover_url"]:
                    b["cover_url"] = t_url
                if len(b["sample_thumbs"]) < 4:
                    b["sample_thumbs"].append(t_url)

        result = list(bucket_map.values())
        result.sort(key=lambda x: (-int(x["active_count"]), x["bucket_name"].lower()))
        return result
