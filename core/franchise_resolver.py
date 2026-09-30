"""
Franchise Resolver Subsystem
Provides intelligent, automated franchise and series name resolution.
Features:
- Normalized dictionary lookup across English, Romaji, and colloquial acronyms.
- Automatic high-confidence typo and spelling tolerance (fuzzy string matching).
- Substring & subtitle stripping (e.g. "Sword Art Online: Alicization" -> "Sword Art Online").
- Zero-configuration online auto-discovery via AniList GraphQL with persistent local caching.
- Zero manual burden on users: new franchises and artist abbreviations are automatically learned.
"""

import os
import re
import sys
import json
import time
import difflib
import threading
import urllib.request
import urllib.error
from typing import Optional, Dict, Set, List, Tuple, Any
from core.logger import logger


_ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"

_ANILIST_QUERY = """
query ($search: String) {
  Media (search: $search, type: ANIME) {
    id
    title {
      romaji
      english
      native
    }
    synonyms
  }
}
"""

# Common stopwords/noise that should never be searched as a franchise
_IGNORE_FRANCHISE_TERMS: Set[str] = {
    "nsfw", "sfw", "pack", "pics", "4k", "8k", "hd", "extras", "preview",
    "standard", "cosplay", "collab", "special", "reward", "request", "poll",
    "survey", "update", "announcement", "original", "art", "artwork", "illustration",
    "cg", "video", "audio", "voice", "zip", "psd", "wip", "sketch", "doodle",
    "commission", "wallpaper", "uncensored", "censored", "sample", "unknown",
    "general", "other", "cat", "anime", "manga", "game", "comic"
}

# Subtitle / season pattern to clean up noisy franchise candidate strings
_SUBTITLE_CLEANER = re.compile(
    r'(?i)\s*[-—:]\s*(?:season\s*\d+|part\s*\d+|\d+(?:st|nd|rd|th)\s*season|the\s*final\s*season|movie|tv|ova|ona|cour\s*\d+).*$'
)
_SEASON_SUFFIX = re.compile(
    r'(?i)\s+(?:season\s*\d+|part\s*\d+|\d+(?:st|nd|rd|th)\s*season|s\d+|2nd\s*season|3rd\s*season|4th\s*season)\b'
)


# Built-in comprehensive seed catalog: English <-> Romaji <-> Abbreviations
_SEED_FRANCHISES: Dict[str, Dict[str, Any]] = {
    "Alya Sometimes Hides Her Feelings in Russian": {
        "aliases": [
            "roshidere", "tokidoki bosotto", "tokidoki bosotto rossiya-go de dereru tonari no alya-san",
            "alya sometimes hides her feelings"
        ]
    },
    "Classroom of the Elite": {
        "aliases": [
            "youkoso jitsuryoku", "youkoso jitsuryoku shijou shugi no kyoushitsu e",
            "cote", "youjitsu", "you-zitsu"
        ]
    },
    "Otonari no Tenshi-sama": {
        "aliases": [
            "the angel next door spoils me rotten", "the angel next door",
            "otonari no tenshi sama", "otonari no tenshi-sama ni itsu no ma ni ka dame ningen ni sareteita ken",
            "tenshi-sama"
        ]
    },
    "My Dress-Up Darling": {
        "aliases": [
            "my dress up darling", "sono bisque doll wa koi wo suru", "sono bisque doll", "bisque doll"
        ]
    },
    "Gotoubun no Hanayome": {
        "aliases": [
            "the quintessential quintuplets", "5-toubun no hanayome", "5toubun", "gotoubun",
            "5-toubun", "the quintuplets", "quintuplets"
        ]
    },
    "Kanojo Okarishimasu": {
        "aliases": [
            "rent a girlfriend", "rent-a-girlfriend", "kanokari", "kanojo, okarishimasu"
        ]
    },
    "The Eminence in Shadow": {
        "aliases": [
            "kage no jitsuryokusha ni naritakute!", "kage no jitsuryokusha", "eminence in shadow",
            "kagejitsu"
        ]
    },
    "Kaguya-sama: Love Is War": {
        "aliases": [
            "love is war", "kaguya-sama wa kokurasetai", "kaguya-sama", "kaguya"
        ]
    },
    "Amagami-san Chi no Enmusubi": {
        "aliases": [
            "tying the knot with an amagami sister", "amagami sisters", "amagami-san"
        ]
    },
    "The Apothecary Diaries": {
        "aliases": [
            "kusuriya no hitorigoto", "apothecary diaries", "kusuriya"
        ]
    },
    "Wistoria: Wand and Sword": {
        "aliases": [
            "tsue to tsurugi no wistoria", "wistoria"
        ]
    },
    "Chained Soldier": {
        "aliases": [
            "mato seihei no slave", "matoi seihei"
        ]
    },
    "Fire Force": {
        "aliases": [
            "enen no shouboutai"
        ]
    },
    "The Fragrant Flower Blooms with Dignity": {
        "aliases": [
            "kaoru hana wa rin to saku", "fragrant flower"
        ]
    },
    "The 100 Girlfriends Who Really Love You": {
        "aliases": [
            "100 kanojo", "100 girlfriends", "kimi no koto ga daidaidaidaidaisuki na 100-nin no kanojo"
        ]
    },
    "2.5 Dimensional Seduction": {
        "aliases": [
            "2.5-jigen no ririsa", "2.5-jigen no seduction", "ririsa"
        ]
    },
    "The Shiunji Family Children": {
        "aliases": [
            "the shiunji family", "shiunji-ke no kodomo-tachi", "shiunji"
        ]
    },
    "Let This Grieving Soul Retire!": {
        "aliases": [
            "let this grieving soul retire", "nageki no bourei wa intai shitai", "nageki no bourei"
        ]
    },
    "The Dangers in My Heart": {
        "aliases": [
            "boku no kokoro no yabai yatsu", "bokuyaba"
        ]
    },
    "Horimiya": {
        "aliases": [
            "hori-san to miyamura-kun"
        ]
    },
    "Mayonaka Heart Tune": {
        "aliases": [
            "tune in to the midnight heart", "mayochu"
        ]
    },
    "Class de 2-banme ni Kawaii": {
        "aliases": [
            "class de 2-banme ni kawaii onnanoko to tomodachi ni natta"
        ]
    },
    "Class no Daikirai": {
        "aliases": [
            "class no daikirai na joshi to kekkon suru koto ni natta"
        ]
    },
    "Demon Slayer": {
        "aliases": [
            "kimetsu no yaiba", "kimetsu"
        ]
    },
    "Fate": {
        "aliases": [
            "fate saga", "fate series", "fate/stay night", "fate stay night", "fate zero", "fate/zero"
        ]
    },
    "Fate/Grand Order": {
        "aliases": [
            "fate grand order", "fgo"
        ]
    },
    "Sword Art Online": {
        "aliases": [
            "sao", "sword art online ii", "sword art online progressive"
        ]
    },
    "Danmachi": {
        "aliases": [
            "is it wrong to try to pick up girls in a dungeon?",
            "dungeon ni deai wo motomeru no wa machigatteiru darou ka",
            "danmacchi"
        ]
    },
    "Genshin Impact": {
        "aliases": [
            "genshin", "原神"
        ]
    },
    "Honkai: Star Rail": {
        "aliases": [
            "honkai star rail", "hsr", "star rail"
        ]
    },
    "Zenless Zone Zero": {
        "aliases": [
            "zzz"
        ]
    },
    "Bocchi the Rock!": {
        "aliases": [
            "bocchi the rock", "bocchi"
        ]
    },
    "Oshi no Ko": {
        "aliases": [
            "【oshi no ko】", "oshinoko", "my star"
        ]
    },
    "Frieren": {
        "aliases": [
            "sousou no frieren", "frieren: beyond journey's end", "frieren beyond journey's end"
        ]
    },
    "Konosuba": {
        "aliases": [
            "kono subarashii sekai ni shukufuku wo!", "kono subarashii sekai ni shukufuku wo",
            "god's blessing on this wonderful world!"
        ]
    },
    "Mushoku Tensei": {
        "aliases": [
            "mushoku tensei: isekai ittara honki dasu", "jobless reincarnation"
        ]
    },
    "Re:Zero": {
        "aliases": [
            "re:zero kara hajimeru isekai seikatsu", "re: zero", "rezero"
        ]
    },
    "Makeine: Too Many Losing Heroines!": {
        "aliases": [
            "make heroine ga oosugiru!", "make heroine ga oosugiru", "makeine"
        ]
    },
    "Bunny Girl Senpai": {
        "aliases": [
            "seishun buta yarou wa bunny girl senpai no yume wo minai",
            "rascal does not dream of bunny girl senpai", "aobuta"
        ]
    },
    "High School DxD": {
        "aliases": [
            "high school dxd", "highschool dxd", "dxd"
        ]
    },
    "Oregairu": {
        "aliases": [
            "yahari ore no seishun love come wa machigatteiru.",
            "my teen romantic comedy snafu", "yahari ore no seishun"
        ]
    },
    "Jujutsu Kaisen": {
        "aliases": [
            "jjk"
        ]
    },
    "Chainsaw Man": {
        "aliases": [
            "csm"
        ]
    },
    "Cosmic Princess Kaguya": {
        "aliases": [
            "cosmic princess kaguya!"
        ]
    },
    "Yani Neko": {
        "aliases": [
            "chainsmoker cat"
        ]
    }
}


class FranchiseResolver:
    """
    Intelligent, self-learning Franchise & Series Resolver.
    Combines pre-seeded database, persistent local cache, fuzzy matching, and AniList auto-discovery.
    """

    def __init__(self, cache_path: Optional[str] = None):
        self._lock = threading.Lock()
        self._alias_to_canonical: Dict[str, str] = {}
        self._canonicals: Dict[str, str] = {}  # lowercase canonical -> display canonical
        self._negative_cache: Set[str] = set()
        self._last_online_query_time: float = 0.0

        if cache_path:
            self._cache_path = cache_path
        else:
            from core.path_utils import get_data_dir
            self._cache_path = os.path.join(get_data_dir(), "data", "franchise_cache.json")

        self._load()

    def _normalize(self, text: str) -> str:
        """Cleans and normalizes candidate franchise text."""
        if not text:
            return ""
        # Strip brackets, quotes, and symbols
        cleaned = re.sub(r'^[【\[][^】\]]+[】\]]\s*:?\s*', '', text)
        cleaned = re.sub(r'[【】\[\]()_|\-+=~～!！?？"\'`]', ' ', cleaned)
        # Strip subtitles like " - Season 2"
        cleaned = _SUBTITLE_CLEANER.sub('', cleaned)
        cleaned = _SEASON_SUFFIX.sub('', cleaned)
        # Collapse whitespace
        return " ".join(cleaned.lower().split())

    def _load(self):
        """Loads pre-seeded franchises and merges local persistent cache."""
        with self._lock:
            # 1. Populate seed catalog
            for canonical, info in _SEED_FRANCHISES.items():
                c_norm = self._normalize(canonical)
                self._canonicals[c_norm] = canonical
                self._alias_to_canonical[c_norm] = canonical
                for alias in info.get("aliases", []):
                    a_norm = self._normalize(alias)
                    if a_norm:
                        self._alias_to_canonical[a_norm] = canonical

            # 2. Merge local cache file if exists
            if os.path.exists(self._cache_path):
                try:
                    with open(self._cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        canonicals = data.get("canonicals", {})
                        for canonical, aliases in canonicals.items():
                            c_norm = self._normalize(canonical)
                            self._canonicals[c_norm] = canonical
                            self._alias_to_canonical[c_norm] = canonical
                            for alias in aliases:
                                a_norm = self._normalize(alias)
                                if a_norm:
                                    self._alias_to_canonical[a_norm] = canonical
                except Exception as ex:
                    logger.debug(f"Could not load franchise_cache.json: {ex}", category="known")

    def _save(self):
        """Persists learned canonicals and aliases to data/franchise_cache.json."""
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            export_data: Dict[str, List[str]] = {}
            # Group aliases by canonical display name
            for alias_norm, canonical in self._alias_to_canonical.items():
                if canonical not in export_data:
                    export_data[canonical] = []
                if alias_norm != self._normalize(canonical) and alias_norm not in export_data[canonical]:
                    export_data[canonical].append(alias_norm)

            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "canonicals": export_data}, f, indent=2, ensure_ascii=False)
        except Exception as ex:
            logger.debug(f"Could not write franchise_cache.json: {ex}", category="known")

    def register_alias(self, alias: str, canonical: str, persist: bool = True):
        """Registers a franchise alias in memory and optionally persists to disk."""
        if not alias or not canonical:
            return
        a_norm = self._normalize(alias)
        c_norm = self._normalize(canonical)
        if not a_norm or not c_norm:
            return

        with self._lock:
            self._canonicals[c_norm] = canonical
            self._alias_to_canonical[a_norm] = canonical
            if persist:
                self._save()

    def get_aliases(self, canonical_or_alias: str) -> List[str]:
        """Returns all known aliases for the given franchise or alias."""
        if not canonical_or_alias:
            return []
        resolved = self.resolve(canonical_or_alias, allow_online=False) or canonical_or_alias
        c_norm = self._normalize(resolved)
        aliases: Set[str] = set()
        with self._lock:
            target_canonical = self._canonicals.get(c_norm, resolved)
            for a_norm, can in self._alias_to_canonical.items():
                if can.lower() == target_canonical.lower() or can.lower() == resolved.lower():
                    aliases.add(a_norm)
        return sorted(aliases)

    def resolve(self, text: str, allow_online: bool = True) -> Optional[str]:
        """
        Resolves an input franchise candidate to its canonical name.
        Uses exact alias match, substring containment, fuzzy matching, and AniList auto-discovery.
        """
        if not text:
            return None

        norm = self._normalize(text)
        if not norm or len(norm) < 2 or norm in _IGNORE_FRANCHISE_TERMS or norm.isdigit():
            return None

        with self._lock:
            # 1. Exact match in alias or canonical map (O(1))
            if norm in self._alias_to_canonical:
                return self._alias_to_canonical[norm]

            # 2. Substring & Prefix match (e.g. "Classroom of the Elite Season 2" -> "Classroom of the Elite")
            for alias_norm, canonical in self._alias_to_canonical.items():
                alias_words = alias_norm.split()
                # Multi-word franchise titles can match as substring of longer title (e.g. with season suffix)
                if len(alias_words) >= 2:
                    if alias_norm in norm or (len(norm.split()) >= 2 and norm in alias_norm):
                        return canonical
                # Single-word aliases require exact match or word-boundary match
                elif alias_norm == norm:
                    return canonical

            # 3. High-Confidence Fuzzy Match (Auto-heals artist typos like "Danmacchi", "Fellings")
            best_canonical = None
            best_ratio = 0.0
            for alias_norm, canonical in self._alias_to_canonical.items():
                if len(alias_norm) >= 4 and abs(len(alias_norm) - len(norm)) <= 4:
                    ratio = difflib.SequenceMatcher(None, norm, alias_norm).ratio()
                    if ratio > best_ratio and ratio >= 0.85:
                        best_ratio = ratio
                        best_canonical = canonical

            if best_canonical:
                # Register the typo variant so next time is O(1)
                self._alias_to_canonical[norm] = best_canonical
                return best_canonical

        # 4. Online Auto-Discovery via AniList GraphQL
        is_single_short_word = len(norm.split()) == 1 and len(norm) < 5
        if allow_online and norm not in self._negative_cache and len(norm) >= 4 and not is_single_short_word:
            discovered = self._query_anilist(text)
            if discovered:
                return discovered
            else:
                self._negative_cache.add(norm)

        return None

    def _query_anilist(self, search_term: str) -> Optional[str]:
        """
        Queries AniList GraphQL API to automatically resolve unknown anime titles,
        Romaji variants, and community abbreviations with zero user intervention.
        """
        # Rate limit: minimum 0.5s between consecutive online requests
        now = time.time()
        elapsed = now - self._last_online_query_time
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_online_query_time = time.time()

        clean_search = re.sub(r'^[【\[][^】\]]+[】\]]\s*:?\s*', '', search_term)
        clean_search = re.sub(r'[\U00010000-\U0010ffff]', '', clean_search).strip("【】[]() _|-+=~～")
        if not clean_search or len(clean_search) < 3 or clean_search.lower() in _IGNORE_FRANCHISE_TERMS:
            return None

        try:
            req = urllib.request.Request(
                _ANILIST_GRAPHQL_URL,
                data=json.dumps({"query": _ANILIST_QUERY, "variables": {"search": clean_search}}).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "PawchiveDownloader/1.2 (Anime Franchise Resolver)"
                }
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                media = data.get("data", {}).get("Media")
                if not media:
                    return None

                titles = []
                eng = media.get("title", {}).get("english")
                rom = media.get("title", {}).get("romaji")
                native = media.get("title", {}).get("native")
                synonyms = media.get("synonyms", [])

                if eng:
                    titles.append(eng)
                if rom:
                    titles.append(rom)
                if native:
                    titles.append(native)
                titles.extend(synonyms)

                # Quality gate: verify returned anime actually corresponds to query
                st_lower = clean_search.lower()
                st_norm = self._normalize(clean_search)
                best_ratio = max((difflib.SequenceMatcher(None, st_norm, self._normalize(t)).ratio() for t in titles if t), default=0.0)
                contains = any(st_lower in t.lower() or t.lower() in st_lower for t in titles if t and len(t) >= 4)

                if best_ratio < 0.70 and not contains:
                    return None

                # Canonical preference: English title if present and standard, otherwise Romaji
                canonical = eng or rom
                if not canonical:
                    return None

                # Register discovered aliases
                with self._lock:
                    c_norm = self._normalize(canonical)
                    self._canonicals[c_norm] = canonical
                    self._alias_to_canonical[st_norm] = canonical
                    for t in titles:
                        if t:
                            t_norm = self._normalize(t)
                            if t_norm:
                                self._alias_to_canonical[t_norm] = canonical
                    self._save()

                logger.info(
                    f"✨ Auto-discovered anime franchise: '{clean_search}' -> '{canonical}' (via AniList)",
                    category="known"
                )
                return canonical

        except Exception as ex:
            logger.debug(f"AniList auto-discovery skipped for '{search_term}': {ex}", category="known")
            return None
