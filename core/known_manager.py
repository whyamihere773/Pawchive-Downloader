"""
Known Series and Character Manager
Handles persistent storage, categorization matching, smart character extraction, and auto-learning.
"""

import sys
import os
import re
import json
import pickle
from typing import List, Optional, Set, Dict, Any, Callable, Tuple
from core.logger import logger

IGNORED_TAGS: Set[str] = {
    "r-18", "r18", "nsfw", "sfw", "4k", "8k", "patreon", "fanbox", "fantia",
    "subscribestar", "art", "illustration", "cg", "set", "pack", "reward",
    "voice", "audio", "video", "mp4", "zip", "psd", "wip", "sketch", "doodle",
    "commission", "wallpaper", "original", "uncensored", "censored", "sample",
    "preview", "gumroad", "boosty", "dlsite", "dls", "pixiv", "ai", "aiart",
    "cosplay", "photo", "leak", "dl", "highres", "jpg", "png", "webp", "gif",
    "blend", "fbx", "obj", "unity", "unreal", "blender", "ko-fi", "kofi",
    "tier", "monthly", "bonus", "poll", "update", "announcement", "release",
    "news", "free", "public", "locked", "request", "variant", "alt", "diff",
    "comic", "manga", "anime", "game", "fanart", "3d", "2d", "render",
    "embedded", "vimeo", "halloween", "amputee"
}

GENERIC_TITLE_WORDS: Set[str] = {
    "pack", "set", "reward", "rewards", "bundle", "complete", "wip", "sketch",
    "wallpaper", "illustration", "preview", "commission", "render", "animation",
    "audio", "voice", "variant", "variants", "bonus", "fanart", "version",
    "daily", "weekly", "monthly",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "vol", "volume", "part",
    "update", "release", "full", "hd", "4k", "8k", "nsfw", "sfw", "r18",
    # Multi-lingual title generic words
    "イラスト", "壁紙", "差分", "まとめ", "セット", "パック", "特典", "支援", "先行公開",
    "插画", "插图", "壁纸", "差分", "合集", "图集", "套图", "整合", "特典", "赞助", "画集", "全彩",
    "일러스트", "배경화면", "월페이퍼", "차분", "세트", "특전", "후원",
    "иллюстрация", "обои", "набор", "пак", "скетч", "бонус",
    "hintergrundbild", "fond d'écran", "fondo de pantalla", "papel de parede",
    "hình nền", "duvar kağıdı", "วอลเปเปอร์",
}

# Tags that look like character names but are workflow/meta noise
_NOISE_TAGS: Set[str] = {
    "works", "work", "story", "stories", "shorts", "short", "outfit", "outfits",
    "mod", "mods", "rework", "remake", "reworked", "test", "tests", "concept",
    "practice", "fin", "ver", "video", "translation", "upgrade", "problem",
    "method", "body", "types", "type", "tattoos", "hairs", "hair", "face", "fix",
    "ashtray", "toy", "horn", "models", "model", "addition", "additions", "personal",
    "small", "normal", "standalone", "remaster", "bundle", "pack", "set", "fanart",
    "random", "dlc", "finished", "open", "image", "several", "previous", "future",
    "working", "other", "new", "some", "added", "regarding", "about",
    "wh", "wh works", "r6", "ff7", "gits", "dc", "lis", "bg3", "mk", "wow", "re", "ts", "st",
    "bbc", "ma", "merry", "mas", "x-mas", "xmas", "dragons", "beastmans", "slut",
    "whore", "text", "non", "hammer", "orthodox", "orthodo", "character", "characters",
    "art", "artwork", "aniamation", "shotstory", "sudden", "attack",
    "ory", "fi", "oufit", "final", "polling", "results", "voting", "helmet",
    "embedded", "vimeo", "halloween", "amputee", "happy", "month", "next", "broken",
    # Japanese honorifics & titles
    "chan", "san", "sama", "kun", "senpai", "sensei", "tan", "dono", "chama",
    "ちゃん", "さん", "さま", "様", "くん", "君", "せんぱい", "先輩", "せんせい", "先生", "殿",
    # Outfits, variants & styles (English & European)
    "swimsuit", "bikini", "bunny", "maid", "nurse", "bride", "wedding", "casual",
    "kimono", "yukata", "cheerleader", "gym", "schoolgirl", "uniform", "lingerie",
    "underwear", "undies", "costume", "cosplay", "alter", "dress", "latex", "goth",
    "armor", "armour",
    "badeanzug", "maillot", "bañador", "conejita", "sirvienta", "novia", "boda",
    "maiô", "coelhinha", "empregada", "noiva", "casamento",
    "áo tắm", "hầu gái", "cô dâu", "đồng phục",
    "baju renang", "pelayan", "pengantin", "seragam",
    "hizmetçi", "gelin", "üniforma", "ชุดว่ายน้ำ", "บิกินี่", "เมด", "เจ้าสาว", "เครื่องแบบ",
    # Chinese (zh) outfits, variants & honorifics
    "泳装", "泳衣", "比基尼", "兔女郎", "女仆", "护士", "花嫁", "婚纱", "新娘",
    "便服", "私服", "旗袍", "制服", "水手服", "校服", "内衣", "情趣", "黑丝", "白丝", "同人", "同人志",
    "草稿", "涂鸦", "高清", "原画", "立绘", "表情包", "模型", "渲染", "无修", "无遮", "步兵", "骑兵", "汉化", "翻译",
    "酱", "桑", "大人", "君", "学姐", "学长", "前辈", "老师", "殿下", "小姐", "女士", "太太", "娘",
    # Japanese (ja) outfits & terms
    "水着", "ビキニ", "バニー", "バニーガール", "メイド", "ナース", "花嫁", "ウェディング",
    "私服", "セーラー服", "制服", "下着", "ランジェリー", "コスプレ", "着物", "浴衣",
    "落書き", "ラクガキ", "ファンアート", "高画質", "原画", "立ち絵", "同人",
    # Korean (ko) outfits, variants & honorifics
    "수영복", "비키니", "바니걸", "메이드", "간호사", "웨딩", "신부", "사복", "교복", "제복",
    "속옷", "코스프레", "스케치", "낙서", "팬아트", "고화질", "원화",
    "양", "군", "씨", "님", "선배", "선생님", "짱",
    # Russian (ru) outfits & terms
    "купальник", "бикини", "зайка", "кролик", "горничная", "медсестра", "невеста", "свадьба",
    "форма", "косплей", "набор", "скетч", "фанарт", "рендер", "версия", "вариант", "арт",
    # Seasons & events
    "summer", "winter", "spring", "autumn", "fall", "christmas", "valentine",
    # Media formats & platforms
    "4k", "8k", "hd", "psd", "clip", "patreon", "fanbox", "fantia", "subscribestar",
    "gumroad", "discord", "mesh", "blend", "fbx", "obj", "render",
    "v1", "v2", "v3", "ver1", "ver2", "part1", "part2", "pt1", "pt2",
    # Generic entities (but keep races like elf, demon, dragon as valid)
    "monster", "creature", "entity", "slaanesh", "khorne", "nurgle", "tzeentch",
}

# Franchise/game names that should never be extracted as character names
_FRANCHISE_BLOCKLIST: Set[str] = {
    "final fantasy", "genshin impact", "honkai star rail", "fate grand order",
    "rainbowsixsiege", "rainbow six", "wh fantasy", "warhammer fantasy",
    "overwatch", "the witcher", "witcher", "tomb raider", "fallout",
    "world of warcraft", "warcraft", "warhammer", "baldur's gate", "baldursgate", "ghostintheshell",
    "mk11", "final fantasy 7", "final fantasy vii",
}

# Artist chapter titles: "Alarielle Story 01 01~06", "Miao_Kat st 01", "Lara Croft Stroy 01"
_WORKFLOW_TOKEN = (
    r"(?:story|stroy|shotstory|chapter|ch|ep|st|vol|ver|remake|rework|"
    r"outfit|outfits|mod|mods|works?|dressing|helmet|corrupted|"
    r"update|updated|test|final|fix|video|stage|stages)"
)
_CHAPTER_HEAD = re.compile(
    rf"(?ix)^\s*(?:(?:\[[^\]]+\]|\([^)]+\))\s*)*"
    rf"(?P<name>[A-Za-z][A-Za-z0-9.'’&_ ]{{0,40}}?)"
    rf"(?:['’]s)?"
    rf"\s+{_WORKFLOW_TOKEN}\b"
)
_INLINE_NAME_WORKFLOW = re.compile(
    rf"(?ix)\b(?P<name>[A-Z][A-Za-z.]+(?:\s+[A-Z][A-Za-z.]+){{0,2}})['’]?s?\s+{_WORKFLOW_TOKEN}\b"
)
_AND_PAIR = re.compile(
    r"(?ix)\b([A-Za-z][A-Za-z.]{2,})\s+and\s+([A-Za-z][A-Za-z.]{2,})\b"
)
_RANGE_PATTERN = re.compile(r'\d+\s*[~～\-]\s*\d+|\d{2,}_\d{2,}')
_ONLY_JUNK = re.compile(r'^[\d\s\-_~～\.,:;]+$')
_TRAIL_JUNK = re.compile(
    r"(?i)\s+(update|updated?|fix|fixed|rework|remake|version|ver\.?\d*|final|"
    r"outfit|mod|mods|works?)$"
)
_LEAD_JUNK = re.compile(r"(?i)^(broken|updated?|fixed|new|old|the)\s+")

# Regex: reject "Adjective + Generic Creature" patterns (e.g., "Corrupted Dryad", "Fallen Angel")
_CREATURE_PATTERN = re.compile(
    r'^(?:corrupted|fallen|dark|light|shadow|blood|bone|fire|ice|frost|death|undead|ancient|elder|young)\s+(?:dryad|elf|demon|angel|spirit|dragon|beast|goddess|god|deity)$',
    re.IGNORECASE
)

class KnownManager:
    def __init__(self, file_path: Optional[str] = None):
        if file_path:
            self.file_path = file_path
        else:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.file_path = os.path.join(base_dir, "config", "Known.txt")

        # Recognition mode: "hybrid", "database_only", "learning_only"
        self.mode: str = "hybrid"

        self.entries: List[str] = []
        self.entry_franchise_map: Dict[str, str] = {}
        self.franchise_sections: Dict[str, List[str]] = {}
        self.standalone_entries: List[str] = []

        # Master comprehensive database (Danbooru Cat 3 & 4 game & anime characters)
        self.master_characters: Dict[str, Dict[str, str]] = {}
        self.master_franchises: List[str] = []
        self._master_char_map: Dict[Tuple[str, ...], Tuple[str, str]] = {}
        self._master_franchise_map: Dict[Tuple[str, ...], str] = {}

        # Custom Known.txt fast lookup indexes
        self.franchise_aliases: Dict[str, List[str]] = {}
        self._custom_franchise_map: Dict[Tuple[str, ...], str] = {}
        self._custom_cjk_names: Set[str] = set()
        self._custom_cjk_franchises: Set[str] = set()
        self._custom_exact_map: Dict[Tuple[str, ...], Tuple[str, str]] = {}
        self._custom_first_token_map: Dict[str, List[Tuple[str, Tuple[str, ...]]]] = {}
        self._custom_last_token_map: Dict[str, List[Tuple[str, Tuple[str, ...]]]] = {}
        self._custom_single_names: List[str] = []
        self._custom_indexed: List[Tuple[str, Tuple[str, ...]]] = []

        # In-memory query cache for instant hits
        self._lru_cache: Dict[Tuple[str, Tuple[str, ...], Tuple[str, ...], str, str], Optional[Tuple[str, str]]] = {}

        # AI-assisted recognition subsystem (Tier 1 Embeddings & Tier 2 Reasoner)
        self.model_manager: Optional[Any] = None
        self.semantic_matcher: Optional[Any] = None
        self.contextual_reasoner: Optional[Any] = None
        self._ai_enabled: bool = False
        self._ai_engine_mode: str = "hybrid"

        self._load_master_db()

        self.on_entries_changed: Optional[Callable[[], None]] = None
        self.load()

    def enable_ai(self, enabled: bool = True, model_manager: Optional[Any] = None) -> None:
        """Enables or disables AI-assisted character recognition (Tier 1 & Tier 2)."""
        self._ai_enabled = bool(enabled)
        if self._ai_enabled:
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
                    logger.debug(f"AI engine initialization notice: {e}", category="known")
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

        # 1. Fast binary load if cache is fresh
        if os.path.exists(bin_path) and os.path.exists(master_path):
            if os.path.getmtime(bin_path) >= os.path.getmtime(master_path):
                try:
                    with open(bin_path, "rb") as f:
                        cached_data = pickle.load(f)
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
                    
                    blocked_f = {
                        "landscape", "scenery", "background", "wallpaper", "female", "male",
                        "solo", "pair", "group", "comic", "manga", "anime", "game", "random",
                        "art", "artwork", "render", "illustration", "photo", "cosplay", "leak",
                        "dl", "sample", "preview", "news", "poll", "general", "other", "unknown",
                        "untitled", "test", "wip", "pack", "set", "reward", "rewards", "bundle",
                        "complete", "video", "audio", "original", "3d", "2d", "cg", "r18", "nsfw"
                    }
                    self.master_characters = {k: v for k, v in chars.items() if k not in blocked_f}
                    self.master_franchises = [f for f in raw_franchises if f.lower() not in blocked_f and len(f) >= 3]

                    self._master_char_map = {}
                    for k, info in self.master_characters.items():
                        c_name = info.get("name", k.strip())
                        fr = info.get("franchise", "General")
                        toks = tuple(self._tokenize(k))
                        if toks:
                            if toks not in self._master_char_map or (self._master_char_map[toks][0] in ("General", "Other") and fr not in ("General", "Other")):
                                self._master_char_map[toks] = (fr, c_name)


                    self._master_franchise_map = {}
                    for f in self.master_franchises:
                        f_toks = tuple(self._tokenize(f))
                        if f_toks:
                            self._master_franchise_map[f_toks] = f

                # Write pre-compiled binary cache
                try:
                    with open(bin_path, "wb") as bf:
                        pickle.dump({
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

    def load(self):
        self.entries.clear()
        self.entry_franchise_map.clear()
        self.franchise_sections.clear()
        self.standalone_entries.clear()
        self.franchise_aliases.clear()

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
                with open(self.file_path, "w", encoding="utf-8") as f:
                    f.write(default_content.strip() + "\n")
                logger.info(f"Created default structured Known.txt at: {self.file_path}", category="known")
            except Exception as e:
                logger.error(f"Failed to create Known.txt: {e}", category="known")

        try:
            current_franchise: Optional[str] = None
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
                        self.franchise_sections.setdefault(current_franchise, [])
                        if current_franchise not in self.franchise_aliases:
                            self.franchise_aliases[current_franchise] = []
                        for al in parts[1:]:
                            if al not in self.franchise_aliases[current_franchise]:
                                self.franchise_aliases[current_franchise].append(al)
                        continue

                    if cleaned not in self.entries:
                        self.entries.append(cleaned)
                    
                    if current_franchise:
                        self.entry_franchise_map[cleaned.lower()] = current_franchise
                        canon = self._canonical_entry(cleaned)
                        self.entry_franchise_map[canon.lower()] = current_franchise
                        for al in self._entry_aliases(cleaned):
                            self.entry_franchise_map[al.lower()] = current_franchise
                        if cleaned not in self.franchise_sections[current_franchise]:
                            self.franchise_sections[current_franchise].append(cleaned)
                    else:
                        if cleaned not in self.standalone_entries:
                            self.standalone_entries.append(cleaned)

            # Build custom phone book index for O(1) matching
            self._custom_exact_map = {}
            self._custom_first_token_map = {}
            self._custom_last_token_map = {}
            self._custom_single_names = []
            self._custom_indexed = []
            self._custom_words: Set[str] = set()

            for entry in self.entries:
                canonical = self._canonical_entry(entry)
                if not canonical:
                    continue
                fr = self.entry_franchise_map.get(canonical.lower()) or canonical
                for alias in self._entry_aliases(entry):
                    ntoks = tuple(self._tokenize(alias))
                    if not ntoks:
                        continue
                    self._custom_exact_map[ntoks] = (fr, canonical)
                    self._custom_indexed.append((canonical, ntoks))
                    for tok in ntoks:
                        self._custom_words.add(tok)

                    if len(ntoks) == 1:
                        self._custom_single_names.append(canonical)
                    else:
                        first, last = ntoks[0], ntoks[-1]
                        if len(first) >= 3 and first not in _NOISE_TAGS and first not in GENERIC_TITLE_WORDS:
                            self._custom_first_token_map.setdefault(first, []).append((canonical, ntoks))
                        if last != first and len(last) >= 3 and last not in _NOISE_TAGS and last not in GENERIC_TITLE_WORDS:
                            self._custom_last_token_map.setdefault(last, []).append((canonical, ntoks))

            # Build custom franchise map with auto-generated and explicit aliases
            self._custom_franchise_map = {}

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

            for fr in self.franchise_sections:
                fr_toks = tuple(self._tokenize(fr))
                if fr_toks:
                    self._custom_franchise_map[fr_toks] = fr
                for al in self.franchise_aliases.get(fr, []):
                    al_toks = tuple(self._tokenize(al))
                    if al_toks:
                        self._custom_franchise_map[al_toks] = fr

                # 1. Stripping "The "
                if fr.lower().startswith("the "):
                    stripped_toks = tuple(self._tokenize(fr[4:]))
                    if stripped_toks:
                        self._custom_franchise_map[stripped_toks] = fr

                # 2. Acronyms for >= 3 words (e.g. Fate Grand Order -> FGO)
                words = fr.split()
                if len(words) >= 3:
                    acro = "".join(w[0] for w in words if w.lower() not in {"the", "of", "and", "in", "no", "to"}).lower()
                    if len(acro) >= 2:
                        self._custom_franchise_map[(acro,)] = fr

                # 3. Roman numerals <-> numbers (e.g. VII <-> 7)
                roman_map = {
                    "vii": "7", "viii": "8", "ix": "9", "iv": "4", "vi": "6",
                    "iii": "3", "ii": "2", "x": "10", "v": "5"
                }
                for r_tok, d_tok in roman_map.items():
                    if r_tok in fr_toks:
                        sub_toks = tuple(d_tok if t == r_tok else t for t in fr_toks)
                        self._custom_franchise_map[sub_toks] = fr
                        if len(fr_toks) >= 2:
                            ff_acro = f"{fr_toks[0][0]}{fr_toks[1][0]}{d_tok}"
                            self._custom_franchise_map[(ff_acro,)] = fr
                            self._custom_franchise_map[(f"{fr_toks[0][0]}{fr_toks[1][0]}{r_tok}",)] = fr

                # 4. Distinctive single-word franchise keywords (len >= 6)
                for w in fr_toks:
                    if len(w) >= 6 and w not in _NOISE_TAGS and w not in GENERIC_TITLE_WORDS and w not in IGNORED_TAGS:
                        if (w,) not in self._custom_franchise_map:
                            self._custom_franchise_map[(w,)] = fr

                # 5. Multi-lingual franchise aliases (ZH, JA, KO, RU, EN)
                fr_lower = fr.lower()
                for key, trans_list in MULTILINGUAL_FRANCHISE_MAP.items():
                    if key in fr_lower or any(t.lower() in fr_lower for t in trans_list):
                        for trans in trans_list:
                            t_toks = tuple(self._tokenize(trans))
                            if t_toks and t_toks not in self._custom_franchise_map:
                                self._custom_franchise_map[t_toks] = fr

            # Track CJK character names and franchise names for unspaced Asian title scanning
            self._custom_cjk_names.clear()
            self._custom_cjk_franchises.clear()
            for entry in self.entries:
                if self._has_cjk(entry):
                    self._custom_cjk_names.add(entry.strip())
                for alias in self._entry_aliases(entry):
                    if self._has_cjk(alias):
                        self._custom_cjk_names.add(alias.strip())

            for fr in self.franchise_sections:
                if self._has_cjk(fr):
                    self._custom_cjk_franchises.add(fr.strip())
                for al in self.franchise_aliases.get(fr, []):
                    if self._has_cjk(al):
                        self._custom_cjk_franchises.add(al.strip())

            for t_toks, mapped_fr in self._custom_franchise_map.items():
                phrase = "".join(t_toks)
                if self._has_cjk(phrase) and len(phrase) >= 2:
                    self._custom_cjk_franchises.add(phrase)

            self._lru_cache.clear()
            logger.info(f"Loaded {len(self.entries)} known characters/series from Known.txt ({len(self.franchise_sections)} franchises)", category="known")
        except Exception as e:
            logger.error(f"Failed to read Known.txt: {e}", category="known")

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("# Pawchive Downloader - Known Series & Characters\n# Format: [Franchise Name] followed by character names\n\n")
                if self.standalone_entries:
                    for entry in self.standalone_entries:
                        f.write(f"{entry}\n")
                    f.write("\n")

                for franchise, chars in self.franchise_sections.items():
                    if chars or franchise in self.franchise_aliases:
                        aliases = self.franchise_aliases.get(franchise, [])
                        header_str = f"[{franchise} | {' | '.join(aliases)}]" if aliases else f"[{franchise}]"
                        f.write(f"{header_str}\n")
                        for c in chars:
                            f.write(f"{c}\n")
                        f.write("\n")

            if self.on_entries_changed:
                try:
                    self.on_entries_changed()
                except Exception:
                    pass
            logger.success(f"Saved {len(self.entries)} entries to Known.txt", category="known")
        except Exception as e:
            logger.error(f"Failed to save Known.txt: {e}", category="known")

    def add_entry(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        # Case-insensitive duplicate check
        existing_lower = [e.lower() for e in self.entries]
        if name.lower() not in existing_lower:
            self.entries.append(name)
            self.save()
            return True
        return False

    def add_entries(self, names: List[str]) -> List[str]:
        """Adds a list of candidate names, skipping existing items (case-insensitive)."""
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

            # Add all processed names
            for processed in processed_names:
                self.entries.append(processed)
                existing_lower.add(processed.lower())
                added.append(processed)

        if added:
            self.save()
        return added


    def remove_entry(self, name: str) -> bool:
        for idx, entry in enumerate(self.entries):
            if entry.lower() == name.lower().strip():
                self.entries.pop(idx)
                self.save()
                return True
        return False

    def remove_at_index(self, index: int) -> bool:
        if 0 <= index < len(self.entries):
            self.entries.pop(index)
            self.save()
            return True
        return False

    def search(self, query: str) -> List[str]:
        if not query:
            return list(self.entries)
        q = query.lower()
        return [item for item in self.entries if q in item.lower()]

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
        if isinstance(tags, str):
            return [t.strip() for t in tags.split(",") if t.strip()]
        return [str(t).strip() for t in tags if t]

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
        if cache_key in self._lru_cache:
            return self._lru_cache[cache_key]

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
            "酱", "桑", "大人", "君", "学姐", "学长", "前辈", "老师", "殿下", "小姐", "女士", "太太", "娘",
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
        tags = post.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

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

    def add_candidates_from_posts(self, posts: List[Dict[str, Any]]) -> List[str]:
        """Scans a batch of posts and auto-learns all discovered character/series names."""
        if self.mode == "database_only":
            return []
        all_candidates: List[str] = []
        for p in posts:
            all_candidates.extend(self.extract_character_candidates(p))
        return self.add_entries(all_candidates)

