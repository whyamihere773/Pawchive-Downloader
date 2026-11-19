"""
Known Series & Character Manager — Persistence, Master DB & Entry Editing Mixin
Decomposed from core/known_manager.py to keep modules cohesive and under 1,000 lines.
"""

import json
import os
import pickle
import re
import sys
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from core.atomic_io import atomic_write_text
from core.known_constants import (
    GENERIC_TITLE_WORDS,
    IGNORED_TAGS,
    _CREATURE_PATTERN,
    _FRANCHISE_BLOCKLIST,
    _LEAD_JUNK,
    _NOISE_TAGS,
    _STOP_CHAR_WORDS,
    _TRAIL_JUNK,
    _is_invalid_franchise,
)
from core.logger import logger


class KnownStorageMixin:
    """Master character DB loading, Known.txt I/O, index building, and entry edits."""

    def enable_ai(self, enabled: bool = True, model_manager: Optional[Any] = None) -> None:
        """Enables or disables AI-assisted character recognition (Tier 1 & Tier 2)."""
        self._ai_enabled = bool(enabled)
        if self._ai_enabled:
            # Without these packages the engine never starts; say so instead of failing silently
            import importlib.util
            missing = [m for m in ("numpy", "onnxruntime", "tokenizers") if importlib.util.find_spec(m) is None]
            if missing:
                logger.warning(
                    "AI character recognition needs these Python packages, which aren't installed: "
                    f"{', '.join(missing)}. Install them with: pip install -r requirements-ai.txt",
                    category="ai")
            if not self.model_manager:
                try:
                    from services.model_manager import ModelManager
                    from core.ai_semantic_matcher import SemanticMatcher
                    from core.ai_reasoner import ContextualReasoner
                    self.model_manager = model_manager or ModelManager()
                    self.semantic_matcher = SemanticMatcher(self.model_manager)
                    self.contextual_reasoner = ContextualReasoner(self.model_manager)
                    logger.info("AI-assisted character recognition engine activated.", category="known")
                except Exception as e:
                    logger.warning(f"AI character recognition couldn't start: {e}", category="ai")
        self._lru_cache.clear()

    def set_ai_engine_mode(self, mode: str) -> None:
        """Sets the AI engine mode ('semantic_only' or 'hybrid')."""
        if mode in ("semantic_only", "hybrid"):
            self._ai_engine_mode = mode
            self._lru_cache.clear()

    def _load_master_db(self):
        """Loads the pre-compiled master game and anime characters database using fast binary caching."""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        master_path = os.path.join(base_dir, "data", "master_characters.json")
        bin_path = os.path.join(base_dir, "data", "master_characters.bin")

        # 1. Fast binary load if cache is fresh and valid
        if os.path.exists(bin_path) and os.path.exists(master_path):
            if os.path.getmtime(bin_path) >= os.path.getmtime(master_path):
                try:
                    with open(bin_path, "rb") as f:
                        cached_data = pickle.load(f)
                        if cached_data.get("version") == 2:
                            self.master_characters = cached_data["characters"]
                            self.master_franchises = cached_data["franchises"]
                            self._master_char_map = cached_data["char_map"]
                            self._master_franchise_map = cached_data["franchise_map"]
                            logger.info(
                                f"Loaded Master Database (fast binary cache): {len(self.master_characters)} characters across {len(self.master_franchises)} franchises.",
                                category="known"
                            )
                            return
                except Exception as e:
                    logger.debug(f"Could not load master_characters.bin: {e}, falling back to json")

        # 2. Parse JSON and build compiled token indexes
        if os.path.exists(master_path):
            try:
                with open(master_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    chars = data.get("characters", {})
                    raw_franchises = data.get("franchises", [])
                    
                    self.master_characters = {k: v for k, v in chars.items() if not _is_invalid_franchise(k)}
                    self.master_franchises = [f for f in raw_franchises if not _is_invalid_franchise(f)]

                    self._master_char_map = {}
                    for k, info in self.master_characters.items():
                        c_name = info.get("name", k.strip())
                        fr = info.get("franchise", "General")
                        if _is_invalid_franchise(fr):
                            fr = "General"
                        toks = tuple(self._tokenize(k))
                        if toks:
                            if len(toks) == 1 and toks[0] in _STOP_CHAR_WORDS:
                                continue
                            if toks not in self._master_char_map or (self._master_char_map[toks][0] in ("General", "Other") and fr not in ("General", "Other")):
                                self._master_char_map[toks] = (fr, c_name)
                            if len(toks) == 2:
                                rev_toks = (toks[1], toks[0])
                                if rev_toks not in self._master_char_map:
                                    self._master_char_map[rev_toks] = (fr, c_name)

                    self._master_franchise_map = {}
                    for f in self.master_franchises:
                        f_toks = tuple(self._tokenize(f))
                        if f_toks:
                            self._master_franchise_map[f_toks] = f

                # Write pre-compiled binary cache (version 2)
                try:
                    with open(bin_path, "wb") as bf:
                        pickle.dump({
                            "version": 2,
                            "characters": self.master_characters,
                            "franchises": self.master_franchises,
                            "char_map": self._master_char_map,
                            "franchise_map": self._master_franchise_map
                        }, bf, protocol=pickle.HIGHEST_PROTOCOL)
                except Exception as ex:
                    logger.debug(f"Could not write master_characters.bin: {ex}")

                logger.info(
                    f"Loaded Master Characters Database: {len(self.master_characters)} characters across {len(self.master_franchises)} franchises.",
                    category="known"
                )
            except Exception as e:
                logger.warning(f"Could not load master_characters.json: {e}", category="known")

    def set_mode(self, mode: str):
        allowed = {"hybrid", "database_only", "learning_only"}
        if mode in allowed:
            self.mode = mode
            self._lru_cache.clear()
            logger.info(f"Known character recognition mode set to: '{mode}'", category="known")

    def load(self, log: bool = True):
        # Everything is built aside and swapped in at the end: a download being planned at the same
        # time used to see an empty or half-built list while Known.txt was reloaded
        entries: List[str] = []
        entry_franchise_map: Dict[str, str] = {}
        franchise_sections: Dict[str, List[str]] = {}
        standalone_entries: List[str] = []
        franchise_aliases: Dict[str, List[str]] = {}
        custom_cjk_names: Set[str] = set()
        custom_cjk_franchises: Set[str] = set()

        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            default_content = """# Pawchive Downloader - Known Series & Characters
# Format: [Franchise Name] followed by character names, or standalone characters.

[Final Fantasy VII]
Tifa Lockhart
Aerith Gainsborough

[The Witcher]
Ciri
Yennefer
Triss Merigold

[Overwatch]
D.Va
Mercy
Widowmaker

[Genshin Impact]
Raiden Shogun
Yelan

[Honkai Star Rail]
Kafka
Firefly

[Warhammer]
Alarielle
Morathi
Katarin
"""
            try:
                atomic_write_text(self.file_path, default_content.strip() + "\n")
                logger.info(f"Created default structured Known.txt at: {self.file_path}", category="known")
            except Exception as e:
                logger.error(f"Failed to create Known.txt: {e}", category="known")

        try:
            current_franchise: Optional[str] = None
            # (sets for the "already listed" checks: searching the lists made a 10,000-line Known.txt take
            # ~0.5 s, on the window thread at each add / remove)
            seen_entries: Set[str] = set()
            seen_standalone: Set[str] = set()
            seen_in_section: Dict[str, Set[str]] = {}
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    cleaned = line.strip()
                    if not cleaned or cleaned.startswith("#"):
                        continue
                    # Check for section header [Franchise Name | Alias1 | Alias2]
                    section_match = re.match(r'^\[([^\]]+)\]$', cleaned)
                    if section_match:
                        raw_header = section_match.group(1).strip()
                        parts = [p.strip() for p in raw_header.split("|") if p.strip()]
                        primary_fr = parts[0] if parts else raw_header
                        current_franchise = primary_fr
                        franchise_sections.setdefault(current_franchise, [])
                        if current_franchise not in franchise_aliases:
                            franchise_aliases[current_franchise] = []
                        for al in parts[1:]:
                            if al not in franchise_aliases[current_franchise]:
                                franchise_aliases[current_franchise].append(al)
                            self.franchise_resolver.register_alias(al, current_franchise, persist=False)
                        continue

                    if cleaned not in seen_entries:
                        seen_entries.add(cleaned)
                        entries.append(cleaned)

                    if current_franchise:
                        entry_franchise_map[cleaned.lower()] = current_franchise
                        canon = self._canonical_entry(cleaned)
                        entry_franchise_map[canon.lower()] = current_franchise
                        for al in self._entry_aliases(cleaned):
                            entry_franchise_map[al.lower()] = current_franchise
                        in_section = seen_in_section.setdefault(current_franchise, set())
                        if cleaned not in in_section:
                            in_section.add(cleaned)
                            franchise_sections[current_franchise].append(cleaned)
                    else:
                        if cleaned not in seen_standalone:
                            seen_standalone.add(cleaned)
                            standalone_entries.append(cleaned)

            # Build custom phone book index for O(1) matching
            custom_exact_map = {}
            custom_first_token_map = {}
            custom_last_token_map = {}
            custom_single_names = []
            custom_indexed = []
            custom_words: Set[str] = set()

            for entry in entries:
                canonical = self._canonical_entry(entry)
                if not canonical:
                    continue
                fr = entry_franchise_map.get(canonical.lower()) or canonical
                for alias in self._entry_aliases(entry):
                    ntoks = tuple(self._tokenize(alias))
                    if not ntoks:
                        continue
                    custom_exact_map[ntoks] = (fr, canonical)
                    custom_indexed.append((canonical, ntoks))
                    for tok in ntoks:
                        custom_words.add(tok)

                    if len(ntoks) == 1:
                        custom_single_names.append(canonical)
                    else:
                        first, last = ntoks[0], ntoks[-1]
                        if len(first) >= 3 and first not in _NOISE_TAGS and first not in GENERIC_TITLE_WORDS:
                            custom_first_token_map.setdefault(first, []).append((canonical, ntoks))
                        if last != first and len(last) >= 3 and last not in _NOISE_TAGS and last not in GENERIC_TITLE_WORDS:
                            custom_last_token_map.setdefault(last, []).append((canonical, ntoks))

            # Build custom franchise map with auto-generated and explicit aliases
            custom_franchise_map = {}

            # Built-in multi-lingual franchise synonyms across supported tutorial languages (ZH, JA, KO, RU, EN)
            MULTILINGUAL_FRANCHISE_MAP = {
                "genshin": ["原神", "げんしん", "원신", "геншин", "геншин импакт"],
                "quintuplet": [
                    "五等分的新娘", "五等分", "五等分の花嫁", "ごとうぶんのはなよめ",
                    "ごとうぶん", "5등분의 신부", "5등분", "5toubun", "gotoubun"
                ],
                "star rail": [
                    "崩坏：星穹铁道", "崩坏星穹铁道", "星穹铁道", "星铁", "崩壊：スターレイル",
                    "スターレイル", "붕괴: 스타레일", "스타레일", "хонкай стар рейл", "стар рейл"
                ],
                "fate": [
                    "命运-冠位指定", "命运冠位指定", "フェイト・グランドオーダー",
                    "フェイト", "페이트 그랜드 오더", "페그오", "fgo"
                ],
                "final fantasy": [
                    "最终幻想", "最终幻想7", "ファイナルファンタジー", "파이널 판타지", "финалка"
                ],
                "witcher": [
                    "巫师", "巫师3", "ウィッチャー", "위쳐", "ведьмак"
                ],
                "overwatch": [
                    "守望先锋", "守望先锋2", "オーバーウォッチ", "오버워치", "овервотч", "ow", "ow2"
                ],
                "blue archive": [
                    "碧蓝档案", "蔚蓝档案", "ブルーアーカイブ", "ブルアカ", "블루 아카이브", "블아"
                ],
                "zenless": [
                    "绝区零", "ゼンレスゾーンゼロ", "ゼンゼロ", "젠레스 존 제로", "젠존제"
                ],
                "azur lane": [
                    "碧蓝航线", "アズールレーン", "アズレン", "벽람항로"
                ],
                "arknights": [
                    "明日方舟", "アークナイツ", "명일방주"
                ]
            }

            for fr in franchise_sections:
                fr_toks = tuple(self._tokenize(fr))
                if fr_toks:
                    custom_franchise_map[fr_toks] = fr
                for al in franchise_aliases.get(fr, []):
                    al_toks = tuple(self._tokenize(al))
                    if al_toks:
                        custom_franchise_map[al_toks] = fr

                # 1. Stripping "The "
                if fr.lower().startswith("the "):
                    stripped_toks = tuple(self._tokenize(fr[4:]))
                    if stripped_toks:
                        custom_franchise_map[stripped_toks] = fr

                # 2. Acronyms for >= 3 words (e.g. Fate Grand Order -> FGO)
                words = fr.split()
                if len(words) >= 3:
                    acro = "".join(w[0] for w in words if w.lower() not in {"the", "of", "and", "in", "no", "to"}).lower()
                    if len(acro) >= 2:
                        custom_franchise_map[(acro,)] = fr

                # 3. Roman numerals <-> numbers (e.g. VII <-> 7)
                roman_map = {
                    "vii": "7", "viii": "8", "ix": "9", "iv": "4", "vi": "6",
                    "iii": "3", "ii": "2", "x": "10", "v": "5"
                }
                for r_tok, d_tok in roman_map.items():
                    if r_tok in fr_toks:
                        sub_toks = tuple(d_tok if t == r_tok else t for t in fr_toks)
                        custom_franchise_map[sub_toks] = fr
                        if len(fr_toks) >= 2:
                            ff_acro = f"{fr_toks[0][0]}{fr_toks[1][0]}{d_tok}"
                            custom_franchise_map[(ff_acro,)] = fr
                            custom_franchise_map[(f"{fr_toks[0][0]}{fr_toks[1][0]}{r_tok}",)] = fr

                # 4. Distinctive single-word franchise keywords (len >= 6)
                for w in fr_toks:
                    if len(w) >= 6 and w not in _NOISE_TAGS and w not in GENERIC_TITLE_WORDS and w not in IGNORED_TAGS:
                        if (w,) not in custom_franchise_map:
                            custom_franchise_map[(w,)] = fr

                # 5. Multi-lingual franchise aliases (ZH, JA, KO, RU, EN)
                fr_lower = fr.lower()
                for key, trans_list in MULTILINGUAL_FRANCHISE_MAP.items():
                    if key in fr_lower or any(t.lower() in fr_lower for t in trans_list):
                        for trans in trans_list:
                            t_toks = tuple(self._tokenize(trans))
                            if t_toks and t_toks not in custom_franchise_map:
                                custom_franchise_map[t_toks] = fr

                # 6. Automated Franchise Resolver Aliases (Seed catalog + persistent learned cache)
                if hasattr(self, "franchise_resolver") and self.franchise_resolver:
                    for r_al in self.franchise_resolver.get_aliases(fr):
                        r_toks = tuple(self._tokenize(r_al))
                        if r_toks and r_toks not in custom_franchise_map:
                            custom_franchise_map[r_toks] = fr

            # Track CJK character names and franchise names for unspaced Asian title scanning
            for entry in entries:
                if self._has_cjk(entry):
                    custom_cjk_names.add(entry.strip())
                for alias in self._entry_aliases(entry):
                    if self._has_cjk(alias):
                        custom_cjk_names.add(alias.strip())

            for fr in franchise_sections:
                if self._has_cjk(fr):
                    custom_cjk_franchises.add(fr.strip())
                for al in franchise_aliases.get(fr, []):
                    if self._has_cjk(al):
                        custom_cjk_franchises.add(al.strip())

            for t_toks, mapped_fr in custom_franchise_map.items():
                phrase = "".join(t_toks)
                if self._has_cjk(phrase) and len(phrase) >= 2:
                    custom_cjk_franchises.add(phrase)

            with self._lock:
                self.entries = entries
                self.entry_franchise_map = entry_franchise_map
                self.franchise_sections = franchise_sections
                self.standalone_entries = standalone_entries
                self.franchise_aliases = franchise_aliases
                self._custom_exact_map = custom_exact_map
                self._custom_first_token_map = custom_first_token_map
                self._custom_last_token_map = custom_last_token_map
                self._custom_single_names = custom_single_names
                self._custom_indexed = custom_indexed
                self._custom_words = custom_words
                self._custom_franchise_map = custom_franchise_map
                self._custom_cjk_names = custom_cjk_names
                self._custom_cjk_franchises = custom_cjk_franchises
                self._lru_cache.clear()
            if log:
                logger.info(f"Loaded {len(entries)} known characters/series from Known.txt ({len(franchise_sections)} franchises)", category="known")
        except Exception as e:
            logger.error(f"Failed to read Known.txt: {e}", category="known")

    def save(self, notify: bool = True):
        """Write standalone entries and franchise sections to Known.txt.

        Only those two structures are written, so every edit must update them
        (not just self.entries) or it is lost on restart.
        """
        try:
            with self._lock:
                parts = ["# Pawchive Downloader - Known Series & Characters\n# Format: [Franchise Name] followed by character names\n\n"]
                if self.standalone_entries:
                    for entry in self.standalone_entries:
                        parts.append(f"{entry}\n")
                    parts.append("\n")

                for franchise, chars in self.franchise_sections.items():
                    if chars or franchise in self.franchise_aliases:
                        aliases = self.franchise_aliases.get(franchise, [])
                        header_str = f"[{franchise} | {' | '.join(aliases)}]" if aliases else f"[{franchise}]"
                        parts.append(f"{header_str}\n")
                        for c in chars:
                            parts.append(f"{c}\n")
                        parts.append("\n")
                # Crash-safe: a cut-off write used to leave Known.txt empty or half-written
                atomic_write_text(self.file_path, "".join(parts))

            if notify and self.on_entries_changed:
                try:
                    self.on_entries_changed()
                except Exception:
                    pass
            written = len(self.standalone_entries) + sum(len(c) for c in self.franchise_sections.values())
            logger.success(f"Saved {written} entries to Known.txt", category="known")
            return True
        except Exception as e:
            logger.error(f"Failed to save Known.txt: {e}", category="known")
            return False

    def _entries_as_saved(self) -> List[str]:
        """The list the next reload builds from the saved file (standalone characters first, then each
        franchise's), so the list shown at once doesn't change order when the background reload ends."""
        seen: Set[str] = set()
        out: List[str] = []
        for e in self.standalone_entries + [c for chars in self.franchise_sections.values() for c in chars]:
            if e not in seen:
                seen.add(e)
                out.append(e)
        return out

    def _notify_changed(self):
        if self.on_entries_changed:
            try:
                self.on_entries_changed()
            except Exception:
                pass

    def _commit(self):
        """Save, then reload so the matching indexes (built in load) include the change."""
        if not self.save(notify=False):
            self._notify_changed()
            return
        if not self.background_reload:
            self.load(log=False)
            self._notify_changed()
            return
        self._notify_changed()                         # the list itself is already up to date

        def _rebuild():
            with self._edit_lock:
                self.load(log=False)
            self._notify_changed()
        threading.Thread(target=_rebuild, name="KnownReload", daemon=True).start()

    def add_entry(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        with self._edit_lock:
            # Case-insensitive duplicate check
            if name.lower() in {e.lower() for e in self.entries}:
                return False
            self.standalone_entries.append(name)
            self.entries = self._entries_as_saved()
        self._commit()
        return True

    def add_entries(self, names: List[str]) -> List[str]:
        """Adds the plausible names from a list of candidates as standalone entries."""
        with self._edit_lock:
            added = self.filter_candidates(names)
            if added:
                self.standalone_entries.extend(added)
                self.entries = self._entries_as_saved()
        if added:
            self._commit()
        return added

    def filter_candidates(self, names: List[str]) -> List[str]:
        """Clean up candidate names and drop junk and anything already known (case-insensitive)."""
        added: List[str] = []
        existing_lower = {e.lower() for e in self.entries}

        # Substrings that disqualify any candidate regardless of position
        _BAD_SUBSTRINGS = {"whore", "slut", "bbc", "proudwhore", "proudw"}

        # Words that should never appear as the last word in a learned name
        _BAD_SUFFIXES = {
            "cowboy", "outfit", "bbc", "whore", "slut", "shorts", "short", "body",
            "small", "random", "normal", "personal", "ashtray", "tattoos", "horn",
            "helmet", "rework", "remake", "add", "test", "concept", "practice",
            "start", "fin", "final", "version", "upgrade", "mod", "mods", "method",
            "fix", "face", "hair", "hairs", "type", "types", "attacks", "attack",
            "si", "ory", "ideo", "oufit",
        }

        for n in names:
            # Normalize underscores to spaces
            n_clean = n.replace("_", " ").strip(" \t\r\n.,;:!?'\"-–—[](){}【】《》")
            # Reject any name containing an explicit bad substring
            n_lower = n_clean.lower()
            if any(bs in n_lower for bs in _BAD_SUBSTRINGS):
                continue
            if not n_clean or len(n_clean) < 2 or len(n_clean) > 50:
                continue

            # Split combined names (e.g., "Fay&Shadowheart" → ["Fay", "Shadowheart"])
            split_names = re.split(r'[&+]', n_clean)
            processed_names = []

            for split_n in split_names:
                split_n = split_n.strip()
                if not split_n:
                    continue

                while True:
                    nxt = _LEAD_JUNK.sub("", split_n).strip()
                    nxt = _TRAIL_JUNK.sub("", nxt).strip()
                    if nxt == split_n:
                        break
                    split_n = nxt

                if not split_n or len(split_n) < 2 or len(split_n) > 50:
                    continue

                split_n_lower = split_n.lower()
                if split_n_lower in existing_lower or split_n_lower in IGNORED_TAGS or split_n_lower in _NOISE_TAGS:
                    continue
                if split_n_lower in _FRANCHISE_BLOCKLIST:
                    continue
                words_chk = split_n.split()
                if any(w.lower() in _NOISE_TAGS or w.lower() in GENERIC_TITLE_WORDS for w in words_chk):
                    continue
                if words_chk[-1].isdigit():
                    continue
                # Reject "Adjective + Generic Creature" patterns
                if _CREATURE_PATTERN.match(split_n):
                    continue
                # Filter out purely numeric or date patterns
                if re.match(r'^[\d\s\-_/.:]+$', split_n):
                    continue
                # Filter out common resolutions / generic words
                if re.match(r'^(4k|8k|hd|psd|mp4|zip|rar|vol\s*\d+|part\s*\d+|set\s*\d+)$', split_n, re.IGNORECASE):
                    continue
                # Reject names with possessive 's (e.g., "Next month's")
                if re.search(r"'\s", split_n):
                    continue
                # Reject if the last word is a known noise suffix
                last_word = split_n.split()[-1].lower()
                if last_word in _BAD_SUFFIXES:
                    continue
                # Skip short single words that are already contained in a longer existing entry
                # e.g. skip "Miao" if "Miao ying" is already present
                if len(split_n.split()) == 1:
                    is_prefix_of_existing = any(
                        split_n_lower in existing_el and split_n_lower != existing_el
                        for existing_el in existing_lower
                    )
                    if is_prefix_of_existing:
                        continue

                processed_names.append(split_n)

            for processed in processed_names:
                existing_lower.add(processed.lower())
                added.append(processed)

        return added

    def remove_entry(self, name: str) -> bool:
        target = (name or "").strip().lower()
        if not target:
            return False
        with self._edit_lock:
            removed = False
            before = len(self.standalone_entries)
            self.standalone_entries = [e for e in self.standalone_entries if e.lower() != target]
            removed = removed or len(self.standalone_entries) != before
            for franchise, chars in self.franchise_sections.items():
                kept = [c for c in chars if c.lower() != target]
                if len(kept) != len(chars):
                    self.franchise_sections[franchise] = kept
                    removed = True
            if removed:
                self.entries = self._entries_as_saved()
        if removed:
            self._commit()
        return removed

    def remove_at_index(self, index: int) -> bool:
        if 0 <= index < len(self.entries):
            return self.remove_entry(self.entries[index])
        return False

    def search(self, query: str) -> List[str]:
        if not query:
            return list(self.entries)
        q = query.lower()
        return [item for item in self.entries if q in item.lower()]
