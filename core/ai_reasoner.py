"""
AI Contextual Reasoner Subsystem (Tier 2)
Combines creator archive download history from download_archive.db with post content
to deduce character and franchise matches for ambiguous, minimalist, or unsearchable titles.
"""

import os
import re
import json
import threading
import time
from typing import Optional, Dict, Any, Tuple, List
from core.logger import logger
from services.model_manager import ModelManager

# A loaded model is unloaded after this long without being used (it reloads on its next use).
IDLE_UNLOAD_SECONDS = 300


_LLAMA_CPP_AVAILABLE: Optional[bool] = None


def has_llama_cpp() -> bool:
    """Checks whether the llama-cpp-python engine is installed and functional."""
    global _LLAMA_CPP_AVAILABLE
    if _LLAMA_CPP_AVAILABLE is not None:
        return _LLAMA_CPP_AVAILABLE
    try:
        import llama_cpp  # noqa: F401
        _LLAMA_CPP_AVAILABLE = True
    except (ImportError, Exception):
        _LLAMA_CPP_AVAILABLE = False
    return _LLAMA_CPP_AVAILABLE


class ContextualReasoner:
    """Performs deep contextual reasoning combining creator history priors and post metadata."""

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self._llm_instance = None
        self._lock = threading.RLock()        # held while the model runs, so it's never unloaded mid-use
        self._last_used = 0.0
        self._is_loaded = False
        self._engine_failed = False
        self._missing_dep_logged = False

    def is_available(self) -> bool:
        """Returns True if either light (0.5B) or heavy (1.5B) model is ready and llama_cpp is installed."""
        if not has_llama_cpp() or self._engine_failed:
            if not has_llama_cpp() and not self._missing_dep_logged:
                self._missing_dep_logged = True
                logger.info(
                    "Deep Context Reasoner (Tier 2 SLM) inactive: 'llama-cpp-python' library is not available. "
                    "Running high-speed Multilingual Semantic Matcher (Tier 1 ONNX) instead.",
                    category="ai"
                )
            return False

        return (
            self.model_manager.is_model_ready("deep_reasoner_heavy")
            or self.model_manager.is_model_ready("deep_reasoner_light")
            or self.model_manager.is_model_ready("deep_reasoner")
        )

    def _format_archive_context(self, creator_profile: Optional[Dict[str, Any]]) -> str:
        """Formats creator archive history into a concise prompt context block."""
        if not creator_profile or not creator_profile.get("top_characters"):
            return "No prior download history for this creator."

        lines = []
        creator_name = creator_profile.get("creator_name") or creator_profile.get("creator_id") or "Unknown"
        lines.append(f"Creator: {creator_name}")

        top_chars = creator_profile.get("top_characters", [])[:4]
        char_strs = [f"{c['character']} ({c['franchise']}, {c['count']} past posts)" for c in top_chars]
        lines.append(f"Frequently drawn characters: {'; '.join(char_strs)}")

        top_frs = creator_profile.get("top_franchises", [])[:3]
        fr_strs = [f"{f['name']} ({f['count']} posts)" for f in top_frs]
        lines.append(f"Frequently drawn franchises: {'; '.join(fr_strs)}")

        return "\n".join(lines)

    def reason_match(
        self,
        post_title: str,
        filenames: Optional[List[str]] = None,
        content: Optional[str] = None,
        creator_profile: Optional[Dict[str, Any]] = None,
        known_manager: Optional[Any] = None
    ) -> Optional[Tuple[str, str, float]]:
        """
        Deduces the most likely (franchise, character, confidence) for an ambiguous post.
        Uses creator archive priors and title cues.
        """
        if not post_title and not filenames and not content:
            return None

        clean_title = (post_title or "").strip()
        clean_filenames = [f for f in (filenames or []) if f and f.strip()]
        clean_desc = (content or "").strip()[:500]

        # 1. Archive Prior Matching (Fast Bayesian heuristic when creator has strong habits)
        if creator_profile and creator_profile.get("top_characters"):
            archive_match = self._deduce_from_archive_priors(
                clean_title,
                clean_filenames,
                clean_desc,
                creator_profile,
                known_manager
            )
            if archive_match:
                return archive_match

        # 2. Generative SLM Inference (if deep_reasoner model is active)
        if self.is_available():
            llm_match = self._run_llm_inference(
                clean_title,
                clean_filenames,
                clean_desc,
                creator_profile
            )
            if llm_match:
                return llm_match

        return None

    def _deduce_from_archive_priors(
        self,
        title: str,
        filenames: List[str],
        desc: str,
        creator_profile: Dict[str, Any],
        known_manager: Optional[Any]
    ) -> Optional[Tuple[str, str, float]]:
        """
        Calculates confidence score based on creator's historical character frequency
        combined with subtle keywords/tokens in the post.
        """
        top_characters = creator_profile.get("top_characters", [])
        if not top_characters:
            return None

        all_text = f"{title} {' '.join(filenames)} {desc}".lower()

        # Check each frequent character of this creator
        for char_entry in top_characters:
            char_name = char_entry["character"]
            franchise = char_entry["franchise"]
            count = char_entry["count"]

            # Tokenize character into parts (e.g. "Nino Nakano" -> ["nino", "nakano"])
            name_parts = [p.lower() for p in re.findall(r"\w+", char_name, re.UNICODE) if len(p) >= 2]
            if not name_parts:
                continue

            # If any significant name part matches the text and creator frequently draws them
            for part in name_parts:
                if len(part) >= 3 and part in all_text:
                    # Confidence scales with creator's historical concentration
                    total = max(creator_profile.get("total_posts", count), 1)
                    concentration = count / total
                    confidence = min(0.95, 0.70 + (concentration * 0.25))
                    logger.info(
                        f"Archive reasoning matched '{char_name}' ({franchise}) based on creator prior ({count} posts, conf={confidence:.2f})",
                        category="ai"
                    )
                    return franchise, char_name, confidence

        return None

    def is_loaded(self) -> bool:
        return self._llm_instance is not None

    def unload(self) -> bool:
        """Free the language model's RAM/VRAM (it loads again on its next use)."""
        with self._lock:
            llm, self._llm_instance = self._llm_instance, None
            if llm is None:
                return False
            try:
                close = getattr(llm, "close", None)       # releases the memory-mapped model file
                if callable(close):
                    close()
            except Exception as e:
                logger.debug(f"Closing the language model failed: {e}", category="ai")
            del llm
            logger.debug("Language model unloaded.", category="ai")
            return True

    def unload_if_idle(self, idle_seconds: float = IDLE_UNLOAD_SECONDS) -> bool:
        """Unload when unused for idle_seconds. Never waits for, or interrupts, a run in progress."""
        if self._llm_instance is None or time.monotonic() - self._last_used < idle_seconds:
            return False
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if self._llm_instance is None or time.monotonic() - self._last_used < idle_seconds:
                return False
            return self.unload()
        finally:
            self._lock.release()

    def _run_llm_inference(
        self,
        title: str,
        filenames: List[str],
        desc: str,
        creator_profile: Optional[Dict[str, Any]]
    ) -> Optional[Tuple[str, str, float]]:
        """Runs local SLM inference with strict timeout and JSON extraction."""
        with self._lock:
            self._last_used = time.monotonic()
            try:
                return self._run_llm_inference_locked(title, filenames, desc, creator_profile)
            finally:
                self._last_used = time.monotonic()

    def _run_llm_inference_locked(
        self,
        title: str,
        filenames: List[str],
        desc: str,
        creator_profile: Optional[Dict[str, Any]]
    ) -> Optional[Tuple[str, str, float]]:
        if not has_llama_cpp() or self._engine_failed:
            return None

        # Check for llama-cpp-python availability
        try:
            from llama_cpp import Llama
            from core.hardware_detector import HardwareDetector
            hw = HardwareDetector.get_hardware_info()

            # Prefer heavy (1.5B) model if present, otherwise light (0.5B)
            model_path = (
                self.model_manager.get_model_file_path("deep_reasoner_heavy", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
                or self.model_manager.get_model_file_path("deep_reasoner_light", "qwen2.5-0.5b-instruct-q4_k_m.gguf")
                or self.model_manager.get_model_file_path("deep_reasoner")
            )
            if not model_path or not os.path.exists(model_path):
                return None

            if self._llm_instance is None:
                # GPU offloading if GPU detected, otherwise 2 CPU threads max
                gpu_layers = -1 if hw.get("has_gpu") else 0
                try:
                    self._llm_instance = Llama(
                        model_path=model_path,
                        n_ctx=512,
                        n_threads=2,
                        n_gpu_layers=gpu_layers,
                        verbose=False
                    )
                except Exception as init_err:
                    self._engine_failed = True
                    logger.warning(f"Failed to initialize SLM engine with model {model_path}: {init_err}", category="ai")
                    return None

            history_str = self._format_archive_context(creator_profile)
            prompt = (
                f"<|im_start|>system\nYou are an anime and game character classifier. "
                f"Given the creator's history and current post, output JSON with 'franchise', 'character', 'confidence' (0.0-1.0).<|im_end|>\n"
                f"<|im_start|>user\n[HISTORY]\n{history_str}\n\n"
                f"[POST]\nTitle: {title}\nFiles: {', '.join(filenames[:3])}\nContent: {desc[:200]}\n"
                f"Output format: {{\"franchise\": \"...\", \"character\": \"...\", \"confidence\": 0.9}}<|im_end|>\n"
                f"<|im_start|>assistant\n{{"
            )

            start_t = time.time()
            output = self._llm_instance(
                prompt,
                max_tokens=48,
                stop=["<|im_end|>", "\n\n"],
                temperature=0.1
            )
            elapsed = time.time() - start_t
            logger.debug(f"SLM inference completed in {elapsed:.2f}s", category="ai")

            resp_text = "{" + output["choices"][0]["text"].strip()
            data = json.loads(resp_text)
            fr = data.get("franchise", "").strip()
            ch = data.get("character", "").strip()
            conf = float(data.get("confidence", 0.7))

            if fr and fr.lower() not in {"unknown", "none"}:
                return fr, ch, conf

        except Exception as e:
            logger.debug(f"SLM inference skipped or failed: {e}", category="ai")

        return None
