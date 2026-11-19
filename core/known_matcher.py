"""
Known Series & Character Manager — Tokenization, Fuzzy & Delimited Title Matcher Mixin
Decomposed from core/known_manager.py to keep modules cohesive and under 1,000 lines.
"""

import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.known_constants import (
    GENERIC_TITLE_WORDS,
    IGNORED_TAGS,
    _GENERIC_SEGMENT_TAGS,
    _NOISE_TAGS,
    _ONLY_JUNK,
    _is_invalid_franchise,
)


class KnownMatcherMixin:
    """Tokenization, filename parsing, fuzzy matching, franchise resolution, and delimited title parsing."""

    # Underscores/hyphens are word chars for \b, so "katarin_story" never matched "Katarin".
    # Tokenize the same way Danbooru/gallery-dl treat tags: separators are equivalent to spaces.
    _TOKEN_SPLIT = re.compile(
        r"[\s_\-,;:|/\\~～+&'’\"“”‘`()\[\]{}<>【】《》「」『』（）〔〕〈〉［］〖〗〘〙〚〛«»!?·・•、。，；：]+"
    )

    @staticmethod
    def _has_cjk(s: str) -> bool:
        if not s:
            return False
        return bool(re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uac00-\ud7af]', s))

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        if not text:
            return []
        return [t for t in cls._TOKEN_SPLIT.split(text.lower()) if t]

    @staticmethod
    def _parse_tags(tags: Optional[Any]) -> List[str]:
        if not tags:
            return []
        try:
            from core.filter_engine import FilterEngine
            return FilterEngine.normalize_tags(tags)
        except Exception:
            if isinstance(tags, str):
                return [t.strip().strip("{}'\"") for t in tags.split(",") if t.strip().strip("{}'\"")]
            return [str(t).strip().strip("{}'\"") for t in tags if t]

    @staticmethod
    def _canonical_entry(entry: str) -> str:
        # Known.txt aliases: "Katarin | Katarin Bokha | Ice Court"
        return entry.split("|", 1)[0].strip() or entry.strip()

    @staticmethod
    def _entry_aliases(entry: str) -> List[str]:
        parts = [p.strip() for p in entry.split("|") if p.strip()]
        aliases = list(parts) if parts else [entry.strip()]
        # Automatically generate reversed name permutations for 2-word names (e.g. "Nino Nakano" <-> "Nakano Nino")
        extra_permutations = []
        for a in aliases:
            words = a.split()
            if len(words) == 2:
                reversed_name = f"{words[1]} {words[0]}"
                if reversed_name.lower() != a.lower() and reversed_name not in aliases:
                    extra_permutations.append(reversed_name)
        return aliases + extra_permutations

    def _find_token_sequence(self, hay_tokens: List[str], needle: Tuple[str, ...]) -> Optional[int]:
        n = len(needle)
        if n == 0 or n > len(hay_tokens):
            return None
        for i in range(len(hay_tokens) - n + 1):
            if tuple(hay_tokens[i:i + n]) == needle:
                return i
        return None

    def _match_entries_pool(self, pool_entries: List[str], hay_tokens: List[str], tag_keys: Set[str], is_custom_pool: bool = False) -> Optional[str]:
        """Internal token-sequence matcher across a list of entries."""
        indexed: List[Tuple[str, Tuple[str, ...]]] = []
        first_token_map: Dict[str, List[str]] = {}
        last_token_map: Dict[str, List[str]] = {}
        single_names: List[str] = []

        for entry in pool_entries:
            canonical = self._canonical_entry(entry)
            if not canonical:
                continue
            for alias in self._entry_aliases(entry):
                ntoks = tuple(self._tokenize(alias))
                if not ntoks:
                    continue
                # In master DB, reject single-word names that are generic dictionary words
                if not is_custom_pool and len(ntoks) == 1:
                    tok0 = ntoks[0]
                    if len(tok0) < 4 or tok0 in _NOISE_TAGS or tok0 in GENERIC_TITLE_WORDS:
                        continue
                indexed.append((canonical, ntoks))
                if len(ntoks) == 1:
                    single_names.append(canonical)
                else:
                    first, last = ntoks[0], ntoks[-1]
                    if len(first) >= 4 and first not in _NOISE_TAGS and first not in GENERIC_TITLE_WORDS:
                        first_token_map.setdefault(first, [])
                        if canonical not in first_token_map[first]:
                            first_token_map[first].append(canonical)
                    if (
                        last != first
                        and len(last) >= 4
                        and last not in _NOISE_TAGS
                        and last not in GENERIC_TITLE_WORDS
                    ):
                        last_token_map.setdefault(last, [])
                        if canonical not in last_token_map[last]:
                            last_token_map[last].append(canonical)

        def consider(name: str, score: int, pos: int):
            nonlocal best_name, best_score, best_pos
            if score > best_score or (score == best_score and pos < best_pos):
                best_name = name
                best_score = score
                best_pos = pos

        best_name: Optional[str] = None
        best_score = -1
        best_pos = 10**9

        def _is_filler(tok: str) -> bool:
            return (
                tok in _NOISE_TAGS
                or tok in GENERIC_TITLE_WORDS
                or tok.isdigit()
                or bool(_ONLY_JUNK.match(tok))
            )

        for canonical, ntoks in indexed:
            pos = self._find_token_sequence(hay_tokens, ntoks)
            if pos is None:
                continue
            if any(_is_filler(t) for t in ntoks):
                continue
            tag_bonus = 1000 if " ".join(ntoks) in tag_keys else 0
            consider(canonical, tag_bonus + len(ntoks) * 100 + sum(len(t) for t in ntoks), pos)

        # Short / first-name forms (only for user custom Known.txt entries): "Miao story" → "Miao Ying", "kat video" → "Katarin"
        if is_custom_pool:
            for pos, tok in enumerate(hay_tokens):
                rest = hay_tokens[pos + 1:]
                rest_ok = not rest or all(_is_filler(t) for t in rest)
                for cmap, bonus in ((first_token_map, 45), (last_token_map, 40)):
                    hits = cmap.get(tok) or []
                    if not hits:
                        continue
                    if len(hits) == 1:
                        pick = hits[0]
                    else:
                        pick = max(hits, key=lambda n: (len(self._tokenize(n)), len(n)))
                    extra = 80 if rest and rest_ok and best_name and self._tokenize(best_name) == [tok] else 0
                    consider(pick, bonus + extra + len(tok), pos)

                if 3 <= len(tok) <= 5:
                    prefix_hits = [
                        n for n in single_names
                        if n.lower().startswith(tok) and len(n) >= 6
                    ]
                    uniq = list(dict.fromkeys(prefix_hits))
                    if len(uniq) == 1:
                        consider(uniq[0], 30 + len(tok), pos)

        return best_name

    @classmethod
    def _split_camel_case(cls, s: str) -> str:
        s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
        s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
        return s

    @classmethod
    def _extract_filename_tokens(cls, filename: str) -> List[Tuple[str, ...]]:
        if not filename:
            return []
        base = os.path.basename(filename.split("?")[0])
        stem, _ = os.path.splitext(base)
        stem = cls._split_camel_case(stem)
        raw_tokens = cls._tokenize(stem)
        if not raw_tokens:
            return []

        clean_tokens = [
            t for t in raw_tokens
            if t not in _NOISE_TAGS
            and t not in GENERIC_TITLE_WORDS
            and t not in IGNORED_TAGS
            and not t.isdigit()
            and not _ONLY_JUNK.match(t)
        ]

        res: List[Tuple[str, ...]] = []
        if clean_tokens:
            res.append(tuple(clean_tokens))
            c_len = len(clean_tokens)
            for k in range(min(4, c_len), 0, -1):
                for i in range(c_len - k + 1):
                    ngram = tuple(clean_tokens[i:i + k])
                    if ngram not in res:
                        res.append(ngram)

        r_len = len(raw_tokens)
        for k in range(min(4, r_len), 0, -1):
            for i in range(r_len - k + 1):
                ngram = tuple(raw_tokens[i:i + k])
                if ngram not in res:
                    res.append(ngram)

        return res

    @classmethod
    def _clean_content_text(cls, content: Optional[str]) -> str:
        if not content or not isinstance(content, str):
            return ""
        snippet = content[:1500]
        snippet = re.sub(r'<[^>]+>', ' ', snippet)
        snippet = snippet.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
        return snippet

    def _fuzzy_match_custom(self, query_tokens: List[str]) -> Optional[Tuple[str, str]]:
        """
        High-confidence typo and romanization tolerance for custom characters.
        Guarded: only compares candidate phrases with length >= 5.
        Uses similarity ratio >= 0.88.
        """
        import difflib

        candidates: List[str] = []
        n = len(query_tokens)
        for k in range(min(3, n), 0, -1):
            for i in range(n - k + 1):
                phrase = " ".join(query_tokens[i:i + k])
                if len(phrase) >= 5 and phrase not in _NOISE_TAGS and phrase not in GENERIC_TITLE_WORDS and phrase not in IGNORED_TAGS:
                    candidates.append(phrase)

        if not candidates:
            return None

        for cand in candidates:
            for entry_tokens, (fr, canonical) in self._custom_exact_map.items():
                entry_phrase = " ".join(entry_tokens)
                if abs(len(cand) - len(entry_phrase)) > 2:
                    continue
                if len(entry_phrase) < 5:
                    continue
                ratio = difflib.SequenceMatcher(None, cand, entry_phrase).quick_ratio()
                if ratio >= 0.88:
                    ratio = difflib.SequenceMatcher(None, cand, entry_phrase).ratio()
                    if ratio >= 0.88:
                        return (fr, canonical)

        return None

    def _detect_custom_franchise(
        self,
        tag_tokens: List[Tuple[str, ...]],
        title_tokens: List[str],
        file_tokens: List[Tuple[str, ...]],
        content_tokens: Optional[List[str]] = None
    ) -> Optional[str]:
        if not self._custom_franchise_map:
            return None

        # 1. Tags
        for t_toks in tag_tokens:
            if t_toks in self._custom_franchise_map:
                return self._custom_franchise_map[t_toks]

        # 2. Title N-grams (from 4-grams down to 1-gram)
        t_len = len(title_tokens)
        for k in range(min(4, t_len), 0, -1):
            for i in range(t_len - k + 1):
                ngram = tuple(title_tokens[i:i + k])
                if ngram in self._custom_franchise_map:
                    return self._custom_franchise_map[ngram]

        # 3. Filename tokens
        for f_toks in file_tokens:
            if f_toks in self._custom_franchise_map:
                return self._custom_franchise_map[f_toks]

        # 4. Content tokens
        if content_tokens:
            c_len = len(content_tokens)
            for k in range(min(4, c_len), 0, -1):
                for i in range(c_len - k + 1):
                    ngram = tuple(content_tokens[i:i + k])
                    if ngram in self._custom_franchise_map:
                        return self._custom_franchise_map[ngram]

        # 5. Unspaced CJK franchise substring search in title/tags
        combined_text = " ".join(title_tokens)
        if self._has_cjk(combined_text):
            for cf in getattr(self, "_custom_cjk_franchises", set()):
                if len(cf) >= 2 and cf in combined_text:
                    cf_toks = tuple(self._tokenize(cf))
                    if cf_toks in self._custom_franchise_map:
                        return self._custom_franchise_map[cf_toks]

        return None

    def get_franchise_for_character(self, char_name: str) -> Optional[str]:
        """Returns known franchise for character by inverting custom and master database mappings."""
        if not char_name or len(char_name) < 2:
            return None
        c_low = char_name.strip().lower()

        # 1. Custom Known.txt mapping
        canon = self._canonical_entry(char_name).lower()
        if canon in self.entry_franchise_map:
            fr = self.entry_franchise_map[canon]
            if not _is_invalid_franchise(fr):
                return fr
        if c_low in self.entry_franchise_map:
            fr = self.entry_franchise_map[c_low]
            if not _is_invalid_franchise(fr):
                return fr

        # 2. Master DB exact mapping
        toks = tuple(self._tokenize(char_name))
        if hasattr(self, "_master_char_map") and toks in self._master_char_map:
            fr, _ = self._master_char_map[toks]
            if not _is_invalid_franchise(fr):
                return fr

        # 3. Two-word reverse tokens (Western <-> Eastern order)
        if len(toks) == 2:
            rev_toks = (toks[1], toks[0])
            if hasattr(self, "_master_char_map") and rev_toks in self._master_char_map:
                fr, _ = self._master_char_map[rev_toks]
                if not _is_invalid_franchise(fr):
                    return fr

        return None

    def _resolve_franchise_text(self, text: str, allow_online: bool = False) -> Optional[str]:
        if not text:
            return None
        cleaned = text.strip("【】[]() _|-").strip()
        if not cleaned:
            return None

        # 1. Custom franchise map from Known.txt
        toks = tuple(self._tokenize(cleaned))
        if hasattr(self, "_custom_franchise_map") and toks in self._custom_franchise_map:
            return self._custom_franchise_map[toks]

        # 2. Automated FranchiseResolver (Seed catalog, Local cache, Substring, Fuzzy matching)
        if hasattr(self, "franchise_resolver") and self.franchise_resolver:
            resolved = self.franchise_resolver.resolve(cleaned, allow_online=allow_online)
            if resolved:
                return resolved

        # 3. Master database franchise map
        if hasattr(self, "_master_franchise_map") and toks in self._master_franchise_map:
            if len(toks) == 1:
                tok0 = toks[0]
                if (tok0 in getattr(self, "_custom_words", set()) 
                    or toks in getattr(self, "_custom_exact_map", {})
                    or (hasattr(self, "_master_char_map") and toks in self._master_char_map)):
                    return None
            f = self._master_franchise_map[toks]
            if not _is_invalid_franchise(f):
                return f

        return None

    def _match_delimited_title(self, title: str) -> Optional[Tuple[str, str]]:
        if not title:
            return None

        # Only process titles containing structural delimiters |, _ , or —
        if not re.search(r'\s*[|]\s*|\s+_\s+|\s+[—–]\s+', title):
            return None

        clean_t = re.sub(r'^[【\[][^】\]]+[】\]]\s*:?\s*', '', title)
        clean_t = re.sub(r'^(?:Request|Commission)\s*[-—:]\s*', '', clean_t, flags=re.I)

        raw_segs = [s.strip() for s in re.split(r'\s*[|]\s*|\s+_\s+|\s+[—–]\s+', clean_t) if s.strip()]
        if not raw_segs:
            return None

        segs = []
        for s in raw_segs:
            cs = re.sub(r'[\U00010000-\U0010ffff]', '', s)
            cs = re.sub(r'^[\[(]?\d{4}[-/.]\d{2}[-/.]\d{2}[\])]?\s*', '', cs)
            cs = cs.strip("【】[]() _|-+=~～?!¿¡\"\'`").strip()
            cs = re.sub(r'^(?:Request|Commission|Preview|Extras|SFW|NSFW)\s*[-—:]\s*', '', cs, flags=re.I)
            cs = cs.strip("【】[]() _|-+=~～?!¿¡\"\'`").strip()
            if (cs and 
                cs.lower() not in _GENERIC_SEGMENT_TAGS and 
                not re.match(r'^(?:Request|Commission|Preview|Extras|SFW|NSFW|\d+\s*pics?|\d+k|standar|standard)$', cs, flags=re.I)):
                segs.append(cs)

        if not segs:
            return None

        def _canonicalize_char(fr: str, ch: str) -> str:
            if not ch:
                return ""
            chars = self.franchise_sections.get(fr, [])
            if chars:
                toks = set(self._tokenize(ch))
                for c in chars:
                    canon = self._canonical_entry(c)
                    for alias in self._entry_aliases(c):
                        a_toks = set(self._tokenize(alias))
                        if a_toks and (toks.issubset(a_toks) or a_toks.issubset(toks)):
                            return canon
            c_toks = tuple(self._tokenize(ch))
            if hasattr(self, "_master_char_map") and c_toks in self._master_char_map:
                m_fr, m_char = self._master_char_map[c_toks]
                if m_fr.lower() == fr.lower() or m_fr in ("General", "Other"):
                    return m_char
            return ch

        # If exactly 1 meaningful segment remains (e.g. "Classroom of the Elite _ NSFW" -> ["Classroom of the Elite"])
        if len(segs) == 1:
            matched_fr = self._resolve_franchise_text(segs[0])
            if matched_fr:
                return (matched_fr, "")
            known_fr = self.get_franchise_for_character(segs[0])
            if known_fr:
                return (known_fr, _canonicalize_char(known_fr, segs[0]))
            return None

        # If 2 or more segments: evaluate every candidate pair (franchise, character)
        candidates = []
        for i in range(len(segs)):
            fr_cand_raw = segs[i]
            other_segs = [segs[j] for j in range(len(segs)) if j != i]
            ch_cand_raw = other_segs[0] if len(other_segs) == 1 else " ".join(other_segs)
            fr_is_right = (i == len(segs) - 1)

            cand_fr_clean = fr_cand_raw.strip("【】[]() _|-+=~～?!¿¡\"\'`").strip()
            fr_toks = tuple(self._tokenize(cand_fr_clean))
            resolved_fr = None
            fr_score = 0

            # 1A. Custom franchise map from Known.txt section or alias
            if hasattr(self, "_custom_franchise_map") and fr_toks in self._custom_franchise_map:
                resolved_fr = self._custom_franchise_map[fr_toks]
                fr_score = 10000
            # 1B. Automated FranchiseResolver (Seed catalog + persistent cache + fuzzy typo healing)
            elif hasattr(self, "franchise_resolver") and self.franchise_resolver:
                res = self.franchise_resolver.resolve(cand_fr_clean, allow_online=False)
                if res:
                    c_norm = self.franchise_resolver._normalize(res)
                    matched_custom_sec = None
                    for sec in self.franchise_sections:
                        if self.franchise_resolver._normalize(sec) == c_norm:
                            matched_custom_sec = sec
                            break
                    resolved_fr = matched_custom_sec or res
                    fr_score = 8000 if matched_custom_sec else 5000

            # 1C. Master database franchise map
            if not resolved_fr and hasattr(self, "_master_franchise_map") and fr_toks in self._master_franchise_map:
                f = self._master_franchise_map[fr_toks]
                if not _is_invalid_franchise(f):
                    if len(fr_toks) >= 2:
                        resolved_fr = f
                        fr_score = 2000
                    else:
                        is_known_char = (
                            cand_fr_clean.lower() in self.entry_franchise_map
                            or fr_toks[0] in getattr(self, "_custom_words", set())
                            or (hasattr(self, "_master_char_map") and fr_toks in self._master_char_map)
                        )
                        if not is_known_char:
                            resolved_fr = f
                            fr_score = 300

            if not resolved_fr:
                inverted_fr = self.get_franchise_for_character(cand_fr_clean)
                if inverted_fr:
                    candidates.append((-10000, None, ""))
                    continue
                candidates.append((-1000, None, ""))
                continue

            # 2. Score candidate character
            ch_score = 0
            clean_ch = re.sub(r'\s*\([^)]*\)|\s*\[[^\]]*\]', '', ch_cand_raw).strip()
            clean_ch = re.sub(r'(?i)\b(nsfw|sfw|pack|pics|standar|standard|extra|preview|request|commission)\b', '', clean_ch).strip(" |_-")
            ch_toks = tuple(self._tokenize(clean_ch))

            if hasattr(self, "_custom_franchise_map") and ch_toks in self._custom_franchise_map:
                ch_score -= 5000

            chars_in_sec = self.franchise_sections.get(resolved_fr, [])
            if chars_in_sec and ch_toks:
                for c in chars_in_sec:
                    c_entry_toks = set(self._tokenize(c))
                    cand_tok_set = set(ch_toks)
                    if cand_tok_set.issubset(c_entry_toks) or c_entry_toks.issubset(cand_tok_set):
                        ch_score += 20000
                        break

            if hasattr(self, "_master_char_map") and ch_toks in self._master_char_map:
                m_fr, m_char = self._master_char_map[ch_toks]
                if m_fr.lower() == resolved_fr.lower():
                    ch_score += 15000
                else:
                    ch_score += 1000
            elif clean_ch.lower() in self.entry_franchise_map:
                ch_score += 2000

            if len(ch_toks) >= 2:
                ch_score += 500
            elif len(clean_ch) >= 3:
                ch_score += 100

            pos_bonus = 50 if fr_is_right else 0
            total_score = fr_score + ch_score + pos_bonus
            canon_ch = _canonicalize_char(resolved_fr, clean_ch)
            candidates.append((total_score, resolved_fr, canon_ch))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_candidate = candidates[0]
            if best_candidate[0] > 0 and best_candidate[1]:
                return (best_candidate[1], best_candidate[2])

        # Inversion: check if any segment is a known character whose franchise can be inverted
        for s in segs:
            cs = re.sub(r'^[【\[][^】\]]+[】\]]\s*:?\s*', '', s)
            cs = re.sub(r'^(?:Request|Commission|Preview|Extras|SFW|NSFW)\s*[-—:]\s*', '', cs, flags=re.I).strip("【】[]() _|-")
            cs = re.sub(r'(?i)\b(nsfw|sfw|pack|pics|standar|standard|extra|preview|request|commission)\b', '', cs).strip(" |_-")
            clean_cand = re.sub(r'\s*\([^)]*\)|\s*\[[^\]]*\]', '', cs).strip()
            if clean_cand and len(clean_cand) >= 3 and clean_cand.lower() not in _GENERIC_SEGMENT_TAGS:
                known_fr = self.get_franchise_for_character(clean_cand)
                if known_fr:
                    return (known_fr, _canonicalize_char(known_fr, clean_cand))

        # Fallback for 2 segments where right segment looks like a franchise
        right_seg = segs[-1]
        left_seg = segs[0]
        if (len(right_seg) >= 3 and 
            not _is_invalid_franchise(right_seg) and 
            right_seg.lower() not in _GENERIC_SEGMENT_TAGS):
            
            clean_char = re.sub(r'\s*\([^)]*\)|\s*\[[^\]]*\]', '', left_seg).strip()
            clean_char = re.sub(r'(?i)\b(nsfw|sfw|pack|pics|standar|standard|extra|preview)\b', '', clean_char).strip(" |_-")
            if clean_char:
                return (right_seg, clean_char)

        return None
