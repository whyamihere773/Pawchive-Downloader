"""
Known Series & Character Manager — Constants, Blocklists & Regex Patterns
Decomposed from core/known_manager.py to keep modules cohesive and under 1,000 lines.
"""

import re
from typing import Set

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

# Generic tags to strip from segments
_GENERIC_SEGMENT_TAGS: Set[str] = {
    "nsfw", "sfw", "nsfw 🔞", "sfw pack", "nsfw pack", "pack", "pics", "4k", "8k", "hd",
    "extras", "preview", "standar pack", "standard pack", "cosplay", "collab", "special",
    "bunny special", "christmas special", "valentine special", "halloween special", "spooky special",
    "summer special", "pussy spreading", "pussy", "nude", "lewd", "leaks", "raw"
}

# Single words that should never match as standalone character names
_STOP_CHAR_WORDS: Set[str] = {
    "change", "feedback", "poll", "survey", "sunday", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "post", "eden", "help",
    "style", "waifu", "collab", "catalog", "winner", "reward", "request",
    "announcement", "special", "preview", "extras", "sfw", "nsfw", "pack"
}




_BLOCKED_FRANCHISES: Set[str] = {
    "landscape", "scenery", "background", "wallpaper", "female", "male",
    "solo", "pair", "group", "comic", "manga", "anime", "game", "random",
    "art", "artwork", "render", "illustration", "photo", "cosplay", "leak",
    "dl", "sample", "preview", "news", "poll", "general", "other", "unknown",
    "untitled", "test", "wip", "pack", "set", "reward", "rewards", "bundle",
    "complete", "video", "audio", "original", "3d", "2d", "cg", "r18", "nsfw",
    "artist", "character", "style", "help!!!", "help", "cat", "seal", "slime",
    "marshbreeze", "yuki anno", "yukinosora1126", "unkrk55", "morbidlycutecrunch",
    "iskra", "wffl", "panalee", "sirbrownbear", "solopipb", "pcrx7327", "godbardtsubasa",
    "roughplus", "remanedur", "innocentenough", "silveredge", "denyfake", "neoneet",
    "snowweaver", "kayla-na", "khimera", "hnumkt", "hokawazu", "anzu15", "kame 3",
    "fii-tan the figure", "green patio", "gym pals", "hardtones", "harukanaru 5",
    "idolomantises", "legion beast", "pklucario", "puppy in space", "rikka331",
    "woadedfox", "yatogami fuma", "zanamaoria"
}

def _is_invalid_franchise(f: str) -> bool:
    if not f or len(f) < 2:
        return True
    fl = f.lower().strip()
    if fl in _BLOCKED_FRANCHISES:
        return True
    if fl.isdigit():
        return True
    if any(fl.endswith(ext) for ext in ('.log', '.png', '.jpg', '.jpeg', '.txt', '.zip', '.rar', '.7z', '.psd', '.mp4')):
        return True
    if fl.startswith((')', ']', '}', '"', "'")) or fl.endswith(('(', '[', '{')):
        return True
    if fl.count('(') != fl.count(')'):
        return True
    if ')' in fl and '(' in fl and fl.find(')') < fl.find('('):
        return True
    return False

# Regex: reject "Adjective + Generic Creature" patterns (e.g., "Corrupted Dryad", "Fallen Angel")
_CREATURE_PATTERN = re.compile(
    r'^(?:corrupted|fallen|dark|light|shadow|blood|bone|fire|ice|frost|death|undead|ancient|elder|young)\s+(?:dryad|elf|demon|angel|spirit|dragon|beast|goddess|god|deity)$',
    re.IGNORECASE
)

