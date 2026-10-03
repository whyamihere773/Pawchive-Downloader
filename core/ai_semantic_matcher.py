"""
AI Semantic Matcher Subsystem (Tier 1)
Provides fast, GPU-accelerated multilingual vector embedding matching against
Known.txt and master character databases using ONNX Runtime.
"""

import os
import re
import sys
import threading
import time
import unicodedata
from typing import Optional, List, Dict, Any, Tuple
import numpy as np

from core.logger import logger
from core.hardware_detector import HardwareDetector
from services.model_manager import ModelManager

# A loaded model is unloaded after this long without being used (it reloads on its next use).
IDLE_UNLOAD_SECONDS = 300


class WordPieceTokenizer:
    """Lightweight, pure-Python WordPiece tokenizer for multilingual BERT/MiniLM models."""

    def __init__(self, vocab_file: str):
        self.vocab: Dict[str, int] = {}
        self.inv_vocab: Dict[int, str] = {}
        if os.path.exists(vocab_file):
            with open(vocab_file, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f):
                    token = line.rstrip("\r\n")
                    self.vocab[token] = idx
                    self.inv_vocab[idx] = token
        self.unk_token = "[UNK]"
        self.unk_id = self.vocab.get(self.unk_token, 100)
        self.cls_token = "[CLS]"
        self.cls_id = self.vocab.get(self.cls_token, 101)
        self.sep_token = "[SEP]"
        self.sep_id = self.vocab.get(self.sep_token, 102)

    @staticmethod
    def _is_cjk_char(cp: int) -> bool:
        """Determines if a codepoint is an East Asian CJK character."""
        return (
            (0x4E00 <= cp <= 0x9FFF)
            or (0x3400 <= cp <= 0x4DBF)
            or (0x20000 <= cp <= 0x2A6DF)
            or (0x2A700 <= cp <= 0x2B73F)
            or (0x2B740 <= cp <= 0x2B81F)
            or (0x2B820 <= cp <= 0x2CEAF)
            or (0xF900 <= cp <= 0xFAFF)
            or (0x2F800 <= cp <= 0x2FA1F)
            or (0x3040 <= cp <= 0x309F)   # Hiragana
            or (0x30A0 <= cp <= 0x30FF)   # Katakana
            or (0xAC00 <= cp <= 0xD7AF)   # Hangul Syllables
        )

    def _tokenize_text(self, text: str) -> List[str]:
        """Pre-tokenizes text with CJK single-char isolation and punctuation splitting."""
        text = unicodedata.normalize("NFC", text).strip().lower()
        output_tokens = []
        chars = []

        # Add spaces around CJK characters so they are treated as separate tokens
        for ch in text:
            cp = ord(ch)
            if self._is_cjk_char(cp):
                chars.extend([" ", ch, " "])
            else:
                chars.append(ch)

        spaced_text = "".join(chars)
        raw_words = re.findall(r"\w+|[^\w\s]", spaced_text, re.UNICODE)

        for word in raw_words:
            if not word:
                continue
            if word in self.vocab:
                output_tokens.append(word)
                continue

            # WordPiece subword breakdown
            is_bad = False
            start = 0
            sub_tokens = []
            while start < len(word):
                end = len(word)
                cur_substr = None
                while start < end:
                    substr = word[start:end]
                    if start > 0:
                        substr = "##" + substr
                    if substr in self.vocab:
                        cur_substr = substr
                        break
                    end -= 1
                if cur_substr is None:
                    is_bad = True
                    break
                sub_tokens.append(cur_substr)
                start = end

            if is_bad:
                output_tokens.append(self.unk_token)
            else:
                output_tokens.extend(sub_tokens)

        return output_tokens

    def encode(self, text: str, max_length: int = 64) -> Tuple[List[int], List[int]]:
        """Encodes text into (input_ids, attention_mask) with max length padding/truncation."""
        tokens = self._tokenize_text(text)
        # Bounded length for potato CPU performance
        tokens = tokens[: max_length - 2]
        token_ids = [self.cls_id] + [self.vocab.get(t, self.unk_id) for t in tokens] + [self.sep_id]
        attention_mask = [1] * len(token_ids)

        return token_ids, attention_mask


class SemanticMatcher:
    """Manages the ONNX embedding session, cached vectors for Known.txt, and similarity search."""

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.session = None
        self.tokenizer: Optional[WordPieceTokenizer] = None
        self.hardware_name = "Uninitialized"
        self._lock = threading.RLock()        # held while the model is used, so it's never unloaded mid-use
        self._last_used = 0.0

        # Cached index: list of (canonical_entry, franchise, character) and corresponding matrix
        self._cached_items: List[Tuple[str, str, str]] = []
        self._cached_vectors: Optional[np.ndarray] = None
        self._last_index_time: float = 0.0

    def is_available(self) -> bool:
        """Returns True if the fast_semantic model is fully downloaded and ready."""
        return self.model_manager.is_model_ready("fast_semantic")

    def initialize(self) -> bool:
        """Loads ONNX runtime session with GPU/DirectML/CPU execution providers."""
        with self._lock:
            return self._initialize_locked()

    def _initialize_locked(self) -> bool:
        if not self.is_available():
            return False
        if self.session is not None and (self.tokenizer is not None or getattr(self, "hf_tokenizer", None) is not None):
            return True

        try:
            import onnxruntime as ort

            model_path = self.model_manager.get_model_file_path("fast_semantic", "multilingual_minilm_l12_int8.onnx")
            tok_path = self.model_manager.get_model_file_path("fast_semantic", "tokenizer.json")
            if not tok_path:
                tok_path = self.model_manager.get_model_file_path("fast_semantic", "vocab.txt")

            if not model_path or not tok_path:
                return False

            self.hf_tokenizer = None
            try:
                from tokenizers import Tokenizer
                self.hf_tokenizer = Tokenizer.from_file(tok_path)
            except Exception as e:
                logger.debug(f"HF fast tokenizer fallback: {e}", category="ai")
                self.tokenizer = WordPieceTokenizer(tok_path)

            providers, self.hardware_name = HardwareDetector.get_best_onnx_providers()
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            logger.info(f"Initializing SemanticMatcher ONNX session on: {self.hardware_name}", category="ai")
            self.session = ort.InferenceSession(model_path, sess_options=sess_options, providers=providers)
            return True

        except Exception as e:
            logger.error(f"Failed to initialize SemanticMatcher session: {e}", category="ai")
            return False

    def is_loaded(self) -> bool:
        return self.session is not None

    def unload(self) -> bool:
        """Free the model's memory (it loads again on its next use). The Known index is kept."""
        with self._lock:
            if self.session is None:
                return False
            self.session = None
            self.tokenizer = None
            self.hf_tokenizer = None
            logger.debug("Semantic matcher model unloaded.", category="ai")
            return True

    def unload_if_idle(self, idle_seconds: float = IDLE_UNLOAD_SECONDS) -> bool:
        """Unload when unused for idle_seconds. Never waits for, or interrupts, a lookup in progress."""
        if self.session is None or time.monotonic() - self._last_used < idle_seconds:
            return False
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if self.session is None or time.monotonic() - self._last_used < idle_seconds:
                return False
            return self.unload()
        finally:
            self._lock.release()

    def embed_text(self, text: str) -> Optional[np.ndarray]:
        """Calculates normalized 384-dimensional embedding vector for a given text."""
        with self._lock:
            self._last_used = time.monotonic()
            try:
                return self._embed_text_locked(text)
            finally:
                self._last_used = time.monotonic()

    def _embed_text_locked(self, text: str) -> Optional[np.ndarray]:
        if not self.initialize() or self.session is None:
            return None

        clean_text = text.strip()
        if not clean_text:
            return None

        if getattr(self, "hf_tokenizer", None) is not None:
            enc = self.hf_tokenizer.encode(clean_text)
            input_ids = enc.ids[:64]
            attention_mask = enc.attention_mask[:64]
        elif self.tokenizer is not None:
            input_ids, attention_mask = self.tokenizer.encode(clean_text, max_length=64)
        else:
            return None

        input_ids_arr = np.array([input_ids], dtype=np.int64)
        attention_mask_arr = np.array([attention_mask], dtype=np.int64)


        # Build feed dict matching ONNX input names
        feed = {}
        for inp in self.session.get_inputs():
            if "input_ids" in inp.name:
                feed[inp.name] = input_ids_arr
            elif "attention_mask" in inp.name:
                feed[inp.name] = attention_mask_arr
            elif "token_type_ids" in inp.name:
                feed[inp.name] = np.zeros_like(input_ids_arr, dtype=np.int64)

        outputs = self.session.run(None, feed)
        last_hidden_state = outputs[0]  # shape (1, seq_len, 384)

        # Mean pooling over attention mask
        mask_expanded = np.expand_dims(attention_mask_arr, -1)  # (1, seq_len, 1)
        sum_embeddings = np.sum(last_hidden_state * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        mean_pooled = sum_embeddings / sum_mask  # (1, 384)

        # L2 Normalization
        norm = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
        normalized = mean_pooled / np.clip(norm, a_min=1e-9, a_max=None)

        return normalized[0]

    def build_known_index(self, known_manager: Any) -> int:
        """
        Computes and caches vector embeddings for all entries in KnownManager.
        Runs in ~0.5s–1.5s on GPU/CPU for typical lists.
        """
        if not self.initialize():
            return 0

        items_to_embed: List[Tuple[str, str, str]] = []  # (text, franchise, character)

        # 1. Custom Known.txt characters from franchise sections
        franchise_aliases = getattr(known_manager, "franchise_aliases", {})
        for franchise, chars in getattr(known_manager, "franchise_sections", {}).items():
            fr_variants = [franchise] + list(franchise_aliases.get(franchise, []))
            for f_var in fr_variants:
                items_to_embed.append((f_var, franchise, ""))

            for ch in chars:
                canon = known_manager._canonical_entry(ch) if hasattr(known_manager, "_canonical_entry") else ch
                aliases = known_manager._entry_aliases(ch) if hasattr(known_manager, "_entry_aliases") else [canon]

                for al in aliases:
                    # Index standalone name/alias
                    items_to_embed.append((al, franchise, canon))
                    # Index name + franchise variants for contextual queries
                    for f_var in fr_variants:
                        items_to_embed.append((f"{f_var} {al}", franchise, canon))

        # 2. Standalone entries
        for st in getattr(known_manager, "standalone_entries", []):
            canon = known_manager._canonical_entry(st) if hasattr(known_manager, "_canonical_entry") else st
            items_to_embed.append((canon, canon, ""))

        # De-duplicate items
        unique_items = []
        seen = set()
        for text, fr, ch in items_to_embed:
            key = (text.lower().strip(), fr.lower().strip(), ch.lower().strip())
            if key not in seen and text.strip():
                seen.add(key)
                unique_items.append((text, fr, ch))

        if not unique_items:
            self._cached_items = []
            self._cached_vectors = None
            return 0

        vectors = []
        valid_items = []
        for text, fr, ch in unique_items:
            vec = self.embed_text(text)
            if vec is not None:
                vectors.append(vec)
                valid_items.append((text, fr, ch))

        if vectors:
            self._cached_items = valid_items
            self._cached_vectors = np.array(vectors, dtype=np.float32)  # shape (N, 384)
            self._last_index_time = time.time()
            logger.info(f"Built semantic index with {len(valid_items)} entries.", category="ai")
            return len(valid_items)

        return 0

    def find_match(
        self,
        query: str,
        threshold: float = 0.65
    ) -> Optional[Tuple[str, str, float]]:
        """
        Performs fast cosine similarity search against cached Known.txt vectors.
        Returns (franchise, character, similarity_score) if score >= threshold.
        """
        if self._cached_vectors is None or not self._cached_items:
            return None

        query_vec = self.embed_text(query)
        if query_vec is None:
            return None

        # Dot product of normalized vectors equals cosine similarity
        similarities = np.dot(self._cached_vectors, query_vec)
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= threshold:
            _, franchise, character = self._cached_items[best_idx]
            return franchise, character, best_score

        return None
