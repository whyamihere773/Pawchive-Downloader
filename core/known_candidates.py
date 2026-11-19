"""
Known Series & Character Manager — Post Title & Tag Candidate Discovery Mixin
Decomposed from core/known_manager.py to keep modules cohesive and under 1,000 lines.
"""

import re
from typing import Any, Dict, List, Set

from core.known_constants import (
    GENERIC_TITLE_WORDS,
    IGNORED_TAGS,
    _AND_PAIR,
    _CHAPTER_HEAD,
    _CREATURE_PATTERN,
    _FRANCHISE_BLOCKLIST,
    _INLINE_NAME_WORKFLOW,
    _LEAD_JUNK,
    _NOISE_TAGS,
    _RANGE_PATTERN,
    _TRAIL_JUNK,
)


class KnownCandidatesMixin:
    """Extracts candidate character/franchise names from post tags and titles."""

    @classmethod
    def _is_valid_name_token(cls, token: str) -> bool:
        """Returns True if token looks like part of a real character/franchise name."""
        t_low = token.lower()
        # Must be at least 2 chars, not just numbers/symbols
        if len(token) < 2:
            return False
        if "_" in token:
            return False
        if re.match(r'^[\d\s\-_~\.,:;]+$', token):
            return False
        # Reject known noise tokens
        if t_low in _NOISE_TAGS or t_low in IGNORED_TAGS or t_low in GENERIC_TITLE_WORDS:
            return False
        # Reject fragments ending in common noise suffixes
        if re.search(r'(?i)(ory|rmal|ideo|oufit|sgate|nch|aracter)$', token):
            return False
        return True

    @classmethod
    def _blob_to_name_candidates(cls, blob: str) -> List[str]:
        """Split 'Miao_Kat', 'Fay&Shadowheart', 'Lara Croft' into name strings."""
        if not blob:
            return []
        if "_" in blob:
            names: List[str] = []
            for part in blob.split("_"):
                names.extend(cls._blob_to_name_candidates(part))
            return names
        blob = blob.strip(" \t\r\n.,;:!?'\"-–—[](){}【】《》")
        blob = _LEAD_JUNK.sub("", blob).strip()
        names = []
        for piece in re.split(r"[&+]|,\s*|\s+and\s+", blob, flags=re.IGNORECASE):
            piece = piece.strip()
            if not piece:
                continue
            while True:
                nxt = _TRAIL_JUNK.sub("", piece).strip()
                if nxt == piece:
                    break
                piece = nxt
            if not piece:
                continue
            words = piece.split()
            if len(words) > 2:
                piece = " ".join(words[:2])
                words = words[:2]
            if not words or len(piece) < 3 or len(piece) > 45:
                continue
            if len(words) == 1 and len(words[0]) < 3:
                continue
            if any(not cls._is_valid_name_token(w) for w in words):
                continue
            if piece.lower() in _FRANCHISE_BLOCKLIST or piece.lower() in _NOISE_TAGS:
                continue
            if _CREATURE_PATTERN.match(piece):
                continue
            names.append(piece)
        return names

    @classmethod
    def _candidates_from_title_text(cls, title: str) -> List[str]:
        found: List[str] = []
        spaced = title.replace("_", " ")
        for src in (title, spaced):
            m = _CHAPTER_HEAD.match(src)
            if m:
                found.extend(cls._blob_to_name_candidates(m.group("name")))
        for m in _INLINE_NAME_WORKFLOW.finditer(title):
            found.extend(cls._blob_to_name_candidates(m.group("name")))
        for src in (title, spaced):
            for m in _AND_PAIR.finditer(src):
                found.extend(cls._blob_to_name_candidates(m.group(1)))
                found.extend(cls._blob_to_name_candidates(m.group(2)))
        for m in re.finditer(r"\b([A-Z][a-zA-Z]{2,})['’]s\b", title):
            found.extend(cls._blob_to_name_candidates(m.group(1)))
        return found

    @classmethod
    def extract_character_candidates(cls, post: Dict[str, Any]) -> List[str]:
        """
        Extracts character/franchise names from a post.

        Strategy:
        - Post tags: trusted directly (after noise filtering). These are the highest quality source.
        - Post title: only bracketed segments like [Genshin Impact] or (Tifa Lockhart) are extracted.
          Free-form title segments are too noisy (page numbers, story chapters, etc.) to be reliable.
        """
        candidates: List[str] = []

        # ── 1. Tags (high-confidence source) ─────────────────────────────────
        try:
            from core.filter_engine import FilterEngine
            tags = FilterEngine.normalize_tags(post.get("tags"))
        except Exception:
            tags = post.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip().strip("{}'\"") for t in tags.split(",") if t.strip().strip("{}'\"")]


        for tag in tags:
            if not isinstance(tag, str):
                continue
            t_clean = tag.strip(" #@\t\r\n.,;:!?'\"-–—[](){}【】《》")
            if not t_clean or len(t_clean) < 2 or len(t_clean) > 45:
                continue
            if t_clean.lower() in IGNORED_TAGS or t_clean.lower() in _NOISE_TAGS:
                continue
            if t_clean.lower() in _FRANCHISE_BLOCKLIST:
                continue
            if _CREATURE_PATTERN.match(t_clean):
                continue
            if re.match(r'^[\d\s\-_/.:]+$', t_clean):
                continue
            # Multi-word tags: reject if any word is pure noise (but allow 2-word proper names)
            words = t_clean.split()
            if len(words) > 3:
                continue
            if not all(cls._is_valid_name_token(w) for w in words):
                continue
            candidates.append(t_clean)

        # ── 2. Title: chapter heads, "Name Story", "X and Y", then brackets ─
        title = post.get("title", "") or ""
        if title:
            candidates.extend(cls._candidates_from_title_text(title))

            # Comma-split remaining free-form titles ("Tifa, Kerillian Works")
            if not _RANGE_PATTERN.search(title):
                comma_parts = re.split(r'[,]', title)
                for part in comma_parts:
                    part = part.strip()
                    part_clean = re.sub(
                        r'(?i)\s+(?:works?|story|stories|shorts?|outfits?|mods?|reworks?|remakes?|tests?|concepts?|practices?|vids?|videos?|sfw|nsfw|dlc|personal|small|normal|random|artwork?s?)$',
                        '', part
                    ).strip()
                    if not part_clean:
                        continue

                    split_parts = re.split(r'[&+]', part_clean)
                    for split_part in split_parts:
                        split_part = split_part.strip()
                        if not split_part:
                            continue

                        split_part = _LEAD_JUNK.sub("", split_part).strip()
                        while True:
                            nxt = _TRAIL_JUNK.sub("", split_part).strip()
                            if nxt == split_part:
                                break
                            split_part = nxt

                        if not split_part:
                            continue
                        words = split_part.split()
                        if 1 <= len(words) <= 2:
                            if all(cls._is_valid_name_token(w) for w in words):
                                if re.match(r'^[A-Za-z][a-zA-Z]|^[A-Z]{2}|^[0-9][A-Z]|^D\.', split_part):
                                    if split_part.lower() not in _FRANCHISE_BLOCKLIST:
                                        if not _CREATURE_PATTERN.match(split_part):
                                            candidates.append(split_part)

            # Always parse bracketed content — very reliable
            bracket_matches = re.findall(
                r'[\[\(\{【《「]([^\(\)\[\]\{\}【】《》「」]+)[\]\)\}】》」]', title
            )
            for bm in bracket_matches:
                bm_clean = bm.strip(" \t\r\n.,;:!?'\"-–—")
                if not bm_clean or len(bm_clean) < 2 or len(bm_clean) > 45:
                    continue
                if bm_clean.lower() in IGNORED_TAGS or bm_clean.lower() in _NOISE_TAGS:
                    continue
                if bm_clean.lower() in _FRANCHISE_BLOCKLIST:
                    continue
                if re.match(r'^[\d\s\-_/.:]+$', bm_clean):
                    continue

                # Split combined names (e.g., "Fay&Shadowheart" → ["Fay", "Shadowheart"])
                split_brackets = re.split(r'[&+]', bm_clean)
                for split_bm in split_brackets:
                    split_bm = split_bm.strip()
                    if not split_bm or len(split_bm) < 2 or len(split_bm) > 45:
                        continue

                    # Strip noise words from beginning/end
                    split_bm = re.sub(r'^(broken|updated?|fixed|new|old)\s+', '', split_bm, flags=re.IGNORECASE).strip()
                    split_bm = re.sub(r'\s+(update|updated?|fix|fixed|rework|remake|version|ver\.?\d*)$', '', split_bm, flags=re.IGNORECASE).strip()

                    if not split_bm or len(split_bm) < 2 or len(split_bm) > 45:
                        continue
                    if split_bm.lower() in IGNORED_TAGS or split_bm.lower() in _NOISE_TAGS:
                        continue
                    if split_bm.lower() in _FRANCHISE_BLOCKLIST:
                        continue
                    if _CREATURE_PATTERN.match(split_bm):
                        continue
                    if re.match(r'^[\d\s\-_/.:]+$', split_bm):
                        continue

                    words = split_bm.split()
                    if len(words) > 4:
                        continue
                    if all(cls._is_valid_name_token(w) for w in words):
                        candidates.append(split_bm)

            # CJK names anywhere in title (博麗霊夢, ティファ, etc.)
            cjk_matches = re.findall(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]{2,8}', title)
            candidates.extend(cjk_matches)

        # ── Deduplicate (case-insensitive, preserve original casing) ─────────
        seen: Set[str] = set()
        unique: List[str] = []
        for c in candidates:
            cl = c.lower()
            if cl not in seen and cl not in IGNORED_TAGS and cl not in _NOISE_TAGS and cl not in _FRANCHISE_BLOCKLIST:
                seen.add(cl)
                unique.append(c)

        return unique

    def find_candidates_in_posts(self, posts: List[Dict[str, Any]]) -> List[str]:
        """Scan posts for possible character/series names that aren't in the Known list yet.

        Nothing is added: title words are too noisy ("Soon", "comics", ...) to go into the
        list automatically, so callers only report what was found.
        """
        if self.mode == "database_only":
            return []
        all_candidates: List[str] = []
        for p in posts:
            all_candidates.extend(self.extract_character_candidates(p))
        return self.filter_candidates(all_candidates)
