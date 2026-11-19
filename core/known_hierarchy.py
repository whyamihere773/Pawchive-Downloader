"""
Known Series & Character Manager — Hierarchical Franchise/Character Resolution Mixin
Decomposed from core/known_manager.py to keep modules cohesive and under 1,000 lines.
"""

from typing import Any, Dict, List, Optional, Tuple

from core.known_constants import (
    GENERIC_TITLE_WORDS,
    _NOISE_TAGS,
    _ONLY_JUNK,
)
from core.logger import logger


class KnownHierarchyMixin:
    """Fast heuristic + AI Tier 1/2 hierarchical (Franchise, Character) resolution."""

    def find_matching_hierarchy(
        self,
        title: str,
        tags: Optional[Any] = None,
        filenames: Optional[List[str]] = None,
        content: Optional[str] = None,
        creator_profile: Optional[Dict[str, Any]] = None
    ) -> Optional[Tuple[str, str]]:
        """
        Picks the (Franchise, Character) hierarchical pair for a post.
        Returns Tuple of (franchise_name, character_name), or None if uncataloged.
        Uses Tags, Title N-Grams, Filenames (with CamelCase de-munging), Post Content,
        optional AI Semantic Matching (Tier 1), Creator Archive Reasoning (Tier 2),
        and an LRU query cache.
        Custom Known.txt entries strictly take precedence over the Master Database.
        """
        tag_list = self._parse_tags(tags)
        file_list = [str(f) for f in filenames if f] if filenames else []
        if not title and not tag_list and not file_list and not content:
            return None

        creator_key = str(creator_profile.get("creator_id") or "") if creator_profile else ""
        # Check in-memory LRU query cache
        cache_key = (
            title or "",
            tuple(tag_list),
            tuple(file_list),
            content[:200] if content else "",
            self.mode,
            creator_key,
            self._ai_enabled,
            getattr(self, "_ai_engine_mode", "hybrid")
        )
        with self._lock:
            if cache_key in self._lru_cache:
                return self._lru_cache[cache_key]

        # Ignore polls / announcement posts so they never match as anime characters
        if title:
            t_lower = title.lower()
            if any(w in t_lower for w in ("survey", "waifu poll", "feedback", "which waifu", "what character would you like", "next big collab", "character catalog", "what's coming next", "new generation style", "image style", "winner of the latest post")):
                with self._lock:
                    self._lru_cache[cache_key] = None
                return None

        # Structural delimited title parsing ("Character | Series" or "[Extras] | Character | Series")
        delim_res = self._match_delimited_title(title) if title else None
        if delim_res:
            res = delim_res
        else:
            res = self._find_matching_hierarchy_fast(title, tag_list, file_list, content)

        # Tier 1 & Tier 2 AI-assisted fallback when fast heuristics return None or missing character
        if self._ai_enabled and (not res or not res[1]):
            # Tier 1: Fast Multilingual Semantic Embeddings Matcher
            if self.semantic_matcher and self.semantic_matcher.is_available():
                try:
                    if self.semantic_matcher._cached_vectors is None:
                        self.semantic_matcher.build_known_index(self)
                    sem_match = self.semantic_matcher.find_match(title, threshold=0.82)
                    if sem_match:
                        fr, ch, score = sem_match
                        logger.info(f"AI Tier 1 Semantic Match: '{ch}' ({fr}) [similarity={score:.2f}]", category="known")
                        res = (fr, ch)
                except Exception as ex:
                    logger.debug(f"AI Tier 1 matching error: {ex}", category="known")

            # Tier 2: Creator Archive Prior Reasoning & SLM Deduction (only in hybrid mode)
            if getattr(self, "_ai_engine_mode", "hybrid") != "semantic_only" and self.contextual_reasoner and (not res or not res[1]):
                try:
                    reasoned = self.contextual_reasoner.reason_match(
                        post_title=title,
                        filenames=file_list,
                        content=content,
                        creator_profile=creator_profile,
                        known_manager=self
                    )
                    if reasoned:
                        fr, ch, conf = reasoned
                        logger.info(f"AI Tier 2 Reasoned Match: '{ch}' ({fr}) [confidence={conf:.2f}]", category="known")
                        res = (fr, ch)
                except Exception as ex:
                    logger.debug(f"AI Tier 2 reasoning error: {ex}", category="known")

        with self._lock:
            if len(self._lru_cache) > 10000:
                self._lru_cache.clear()
            self._lru_cache[cache_key] = res
        return res

    def _find_matching_hierarchy_fast(
        self,
        title: str,
        tag_list: List[str],
        filenames: Optional[List[str]] = None,
        content: Optional[str] = None
    ) -> Optional[Tuple[str, str]]:
        hay_tokens = self._tokenize(title) if title else []
        num_toks = len(hay_tokens)

        # Collect tag tokens
        tag_token_list: List[Tuple[str, ...]] = []
        all_flat_tag_tokens: List[str] = []
        for tag in tag_list:
            toks = tuple(self._tokenize(tag))
            if toks:
                tag_token_list.append(toks)
                all_flat_tag_tokens.extend(toks)

        # Collect smart filename tokens (CamelCase split & noise stripped)
        file_token_tuples: List[Tuple[str, ...]] = []
        if filenames:
            for fn in filenames:
                file_token_tuples.extend(self._extract_filename_tokens(fn))

        # Collect post content tokens if provided
        content_tokens: List[str] = []
        if content:
            clean_body = self._clean_content_text(content)
            content_tokens = self._tokenize(clean_body)

        def _is_filler_tok(tok: str) -> bool:
            return (
                tok in _NOISE_TAGS
                or tok in GENERIC_TITLE_WORDS
                or tok.isdigit()
                or bool(_ONLY_JUNK.match(tok))
            )

        # Multi-lingual honorific & affix expansion (JA, ZH, KO, EN)
        MULTILINGUAL_HONORIFIC_SUFFIXES = (
            "chan", "san", "sama", "kun", "senpai", "sensei", "tan", "dono", "chama",
            "ちゃん", "さん", "さま", "様", "くん", "君", "せんぱい", "先輩", "せんせい", "先生", "殿",
            "酱", "桑", "大人", "学姐", "学长", "前辈", "老师", "殿下", "小姐", "女士", "太太", "娘",
            "양", "군", "씨", "님", "선배", "선생님", "짱"
        )
        DIMINUTIVE_PREFIXES = ("小", "阿")
        expanded_title_tokens = list(hay_tokens)
        custom_words = getattr(self, "_custom_words", set())
        cjk_names = getattr(self, "_custom_cjk_names", set())

        for t in hay_tokens:
            for sfx in MULTILINGUAL_HONORIFIC_SUFFIXES:
                if t.endswith(sfx) and len(t) > len(sfx) + 1:
                    stem = t[:-len(sfx)]
                    if (stem in custom_words or stem in cjk_names) and stem not in expanded_title_tokens:
                        expanded_title_tokens.append(stem)
            for pfx in DIMINUTIVE_PREFIXES:
                if t.startswith(pfx) and len(t) >= 2:
                    stem = t[len(pfx):]
                    if (stem in custom_words or stem in cjk_names) and stem not in expanded_title_tokens:
                        expanded_title_tokens.append(stem)

        # CJK unspaced character substring extraction:
        raw_title_str = title or ""
        if self._has_cjk(raw_title_str):
            for c_name in cjk_names:
                if len(c_name) >= 2 and c_name in raw_title_str:
                    c_toks = tuple(self._tokenize(c_name))
                    if c_toks and c_toks[0] not in expanded_title_tokens:
                        expanded_title_tokens.append(c_toks[0])

        # ═════════════════════════════════════════════════════════════════════
        # ── CONTEXT DISAMBIGUATION & FRANCHISE BOOSTING ──────────────────────
        # ═════════════════════════════════════════════════════════════════════
        detected_franchise = self._detect_custom_franchise(
            tag_token_list, hay_tokens, file_token_tuples, content_tokens
        )

        if detected_franchise and self.mode in ("hybrid", "learning_only"):
            chars_in_franchise = self.franchise_sections.get(detected_franchise, [])
            if chars_in_franchise:
                all_context_tokens = list(expanded_title_tokens) + all_flat_tag_tokens
                for ft in file_token_tuples:
                    all_context_tokens.extend(ft)
                if content_tokens:
                    all_context_tokens.extend(content_tokens[:150])

                context_set = set(all_context_tokens)

                # 1. Match full character aliases / n-grams in context
                for c in chars_in_franchise:
                    canonical = self._canonical_entry(c)
                    for alias in self._entry_aliases(c):
                        a_toks = tuple(self._tokenize(alias))
                        if not a_toks:
                            continue
                        if a_toks in tag_token_list or a_toks in file_token_tuples:
                            return (detected_franchise, canonical)
                        if self._find_token_sequence(hay_tokens, a_toks) is not None:
                            return (detected_franchise, canonical)
                        if content_tokens and self._find_token_sequence(content_tokens[:200], a_toks) is not None:
                            return (detected_franchise, canonical)

                # 2. Match single distinctive character tokens (e.g. first or last name)
                for c in chars_in_franchise:
                    canonical = self._canonical_entry(c)
                    for alias in self._entry_aliases(c):
                        a_toks = self._tokenize(alias)
                        for tok in a_toks:
                            min_len = 2 if self._has_cjk(tok) else 3
                            if len(tok) >= min_len and tok in context_set and not _is_filler_tok(tok):
                                return (detected_franchise, canonical)

            # Franchise matched, but no specific character matched -> Series-Only Fallback!
            return (detected_franchise, "")

        # ═════════════════════════════════════════════════════════════════════
        # ── PHASE 1: Custom Known.txt Checks (Highest Priority Always) ────────
        # ═════════════════════════════════════════════════════════════════════
        if self.mode in ("hybrid", "learning_only") and self._custom_exact_map:
            # 1A. Exact tag match in Custom Known
            for t_toks in tag_token_list:
                if t_toks in self._custom_exact_map:
                    fr, canonical = self._custom_exact_map[t_toks]
                    return (fr or canonical, canonical)

            # 1B. Combined tags match in Custom Known (e.g. tag 'nakano' + tag 'nino')
            if len(all_flat_tag_tokens) >= 2:
                for k in range(min(4, len(all_flat_tag_tokens)), 1, -1):
                    for i in range(len(all_flat_tag_tokens) - k + 1):
                        ngram = tuple(all_flat_tag_tokens[i:i + k])
                        if ngram in self._custom_exact_map:
                            fr, canonical = self._custom_exact_map[ngram]
                            return (fr or canonical, canonical)

            # 1C. Title N-Gram matches in Custom Known (5-grams down to 1-gram)
            # (Matches direct and reversed name permutations like 'Nakano Nino' <-> 'Nino Nakano')
            if hay_tokens:
                for k in range(min(5, num_toks), 0, -1):
                    for i in range(num_toks - k + 1):
                        ngram = tuple(hay_tokens[i:i + k])
                        if ngram in self._custom_exact_map:
                            if k == 1 and self._custom_first_token_map:
                                first_word = ngram[0]
                                hits = self._custom_first_token_map.get(first_word)
                                if hits:
                                    rest = hay_tokens[i + 1:]
                                    if not rest or all(_is_filler_tok(t) for t in rest):
                                        pick = max(hits, key=lambda item: (len(item[1]), len(item[0])))[0]
                                        fr = self.entry_franchise_map.get(pick.lower()) or pick
                                        return (fr, pick)

                            fr, canonical = self._custom_exact_map[ngram]
                            return (fr or canonical, canonical)

            # 1C-alt: Expanded title tokens for honorific stems (e.g. Ninochan -> Nino)
            if len(expanded_title_tokens) > len(hay_tokens):
                for tok in expanded_title_tokens[num_toks:]:
                    if (tok,) in self._custom_exact_map:
                        fr, canonical = self._custom_exact_map[(tok,)]
                        return (fr or canonical, canonical)
                    if self._custom_first_token_map and tok in self._custom_first_token_map:
                        hits = self._custom_first_token_map[tok]
                        pick = max(hits, key=lambda item: (len(item[1]), len(item[0])))[0]
                        fr = self.entry_franchise_map.get(pick.lower()) or pick
                        return (fr, pick)

            # 1D. Filename exact N-Grams in Custom Known (e.g. nino.zip, NakanoNino.zip)
            for f_toks in file_token_tuples:
                if f_toks in self._custom_exact_map:
                    fr, canonical = self._custom_exact_map[f_toks]
                    return (fr or canonical, canonical)

            # 1E. High-Confidence Fuzzy Matching for Custom Known (Typo & romanization tolerance)
            fuzzy_res = self._fuzzy_match_custom(hay_tokens)
            if fuzzy_res:
                return fuzzy_res

            # 1F. Smart Token Fallback for Custom Known (Unique token hits from title, tags, files)
            candidate_tokens = list(expanded_title_tokens) + all_flat_tag_tokens
            for ft in file_token_tuples:
                candidate_tokens.extend(ft)

            if self._custom_first_token_map or self._custom_last_token_map:
                for tok in candidate_tokens:
                    if len(tok) < 3 or _is_filler_tok(tok):
                        continue
                    hits1 = self._custom_first_token_map.get(tok) or []
                    hits2 = self._custom_last_token_map.get(tok) or []
                    all_hits = list({item[0]: item for item in (hits1 + hits2)}.values())
                    if len(all_hits) == 1:
                        pick = all_hits[0][0]
                        fr = self.entry_franchise_map.get(pick.lower()) or pick
                        return (fr, pick)
                    elif len(all_hits) > 1:
                        # Try disambiguating with another token in candidates
                        for other_tok in candidate_tokens:
                            if other_tok != tok and len(other_tok) >= 3 and not _is_filler_tok(other_tok):
                                subhits = [h for h in all_hits if other_tok in h[1]]
                                if len(subhits) == 1:
                                    pick = subhits[0][0]
                                    fr = self.entry_franchise_map.get(pick.lower()) or pick
                                    return (fr, pick)

                        # If all hits belong to the exact same franchise, return that franchise!
                        shared_franchises = {self.entry_franchise_map.get(h[0].lower()) or h[0] for h in all_hits}
                        if len(shared_franchises) == 1:
                            fr = next(iter(shared_franchises))
                            return (fr, fr)

            if self._custom_single_names:
                for tok in candidate_tokens:
                    if 3 <= len(tok) <= 5:
                        p_hits = [
                            n for n in self._custom_single_names
                            if n.lower().startswith(tok) and len(n) >= 6
                        ]
                        uniq = list(dict.fromkeys(p_hits))
                        if len(uniq) == 1:
                            pick = uniq[0]
                            fr = self.entry_franchise_map.get(pick.lower()) or pick
                            return (fr, pick)

            # 1G. Post Content Scanning for Custom Known
            if content_tokens:
                c_len = len(content_tokens)
                for k in range(min(4, c_len), 0, -1):
                    for i in range(min(200, c_len - k + 1)):
                        ngram = tuple(content_tokens[i:i + k])
                        if ngram in self._custom_exact_map:
                            fr, canonical = self._custom_exact_map[ngram]
                            return (fr or canonical, canonical)

        # ═════════════════════════════════════════════════════════════════════
        # ── PHASE 2: Master Database Fallback (Only if Custom Known had no match)
        # ═════════════════════════════════════════════════════════════════════
        if self.mode in ("hybrid", "database_only") and self._master_char_map:
            # 2A. Multi-token tags in Master DB
            for t_toks in tag_token_list:
                if len(t_toks) >= 2 and t_toks in self._master_char_map:
                    fr, c_name = self._master_char_map[t_toks]
                    if fr not in ("General", "Other"):
                        return (fr, c_name)
                if len(t_toks) >= 2 and t_toks in self._master_franchise_map:
                    f = self._master_franchise_map[t_toks]
                    return (f, f)

            # 2B. Title N-Grams in Master DB
            if hay_tokens:
                for k in range(min(5, num_toks), 0, -1):
                    for i in range(num_toks - k + 1):
                        ngram = tuple(hay_tokens[i:i + k])
                        # Guard single-word entries in Master DB
                        if k == 1:
                            tok0 = ngram[0]
                            if len(tok0) < 4 or tok0 in _NOISE_TAGS or tok0 in GENERIC_TITLE_WORDS:
                                continue
                            # Crucial: if word appears in any custom Known.txt entry, don't let Master DB steal it!
                            if tok0 in custom_words:
                                continue
                        if ngram in self._master_char_map:
                            return self._master_char_map[ngram]
                        if ngram in self._master_franchise_map:
                            f = self._master_franchise_map[ngram]
                            return (f, f)

            # 2C. Single-token tags in Master DB (guarded)
            for t_toks in tag_token_list:
                if len(t_toks) == 1:
                    tok0 = t_toks[0]
                    if len(tok0) < 4 or tok0 in _NOISE_TAGS or tok0 in GENERIC_TITLE_WORDS:
                        continue
                    if tok0 in custom_words:
                        continue
                    if t_toks in self._master_char_map:
                        fr, c_name = self._master_char_map[t_toks]
                        if fr not in ("General", "Other"):
                            return (fr, c_name)
                    if t_toks in self._master_franchise_map:
                        f = self._master_franchise_map[t_toks]
                        return (f, f)

            # 2D. Filename tuples in Master DB (guarded)
            for f_toks in file_token_tuples:
                if len(f_toks) >= 2 and f_toks in self._master_char_map:
                    fr, c_name = self._master_char_map[f_toks]
                    if fr not in ("General", "Other"):
                        return (fr, c_name)

        return None

    def find_matching_category(self, title: str, tags: Optional[Any] = None) -> Optional[str]:
        """Pick the Known.txt category for a post. Returns the character or series name."""
        hierarchy = self.find_matching_hierarchy(title, tags)
        if not hierarchy:
            return None
        franchise, character = hierarchy
        return character or franchise
