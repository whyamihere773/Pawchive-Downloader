"""
Order of the files inside a post (the "File order in posts" setting).

  posted    the order the site lists them (default, unchanged behaviour)
  reversed  the opposite, for creators who upload the newest version first
  name      natural file-name order, the way a person would sort them:
              "Mya2" < "Mya2v2" < "Mya2v10", "page 9" < "page_10" < "page-11",
              "一枚目" < "二枚目" < "十枚目", "Ａ２" == "A2", "étude" next to "etude"

The order decides which file of a post gets #1 (index prefix, numbered filename styles) and is
also how the Post Selection window lists the files, so both always agree.

Name order works for any script:
  * numbers: any Unicode digits (Arabic-Indic, Devanagari, Thai, full-width, ...), circled and
    superscript numbers (via NFKC), and Chinese / Japanese numerals (一 二 十 百 千 万 億, 壱 弐 参);
  * case and width are ignored (casefold + NFKC: "Ａ" == "a", half-width katakana == katakana);
  * accents are ignored first for Latin, Greek, Cyrillic, Arabic and Hebrew ("é" sorts with "e"),
    but Cyrillic "й" stays its own letter; Thai / Devanagari / other vowel signs are kept because
    they change the word;
  * hiragana and katakana sort together;
  * Thai and Lao vowels written before their consonant are sorted by the consonant;
  * spaces, "_", "-", ".", "~" and other dashes all count as the same separator.
Files whose names compare equal keep their posted order; files without a name go last.
"""

import unicodedata
from typing import Callable, List, Sequence, Tuple, TypeVar

T = TypeVar("T")

POSTED, REVERSED, BY_NAME = "posted", "reversed", "name"
FILE_ORDERS = (POSTED, REVERSED, BY_NAME)


def normalize_file_order(value) -> str:
    v = str(value or "").strip().lower()
    return v if v in FILE_ORDERS else POSTED


# ── Chinese / Japanese numerals ──────────────────────────────────────────────
_CJK_DIGITS = {
    "〇": 0, "零": 0, "一": 1, "壱": 1, "壹": 1, "二": 2, "弐": 2, "貳": 2, "两": 2, "兩": 2,
    "三": 3, "参": 3, "參": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
_CJK_UNITS = {"十": 10, "拾": 10, "百": 100, "千": 1000}
_CJK_BIG = {"万": 10_000, "萬": 10_000, "億": 100_000_000}
_CJK_NUMERAL_CHARS = set(_CJK_DIGITS) | set(_CJK_UNITS) | set(_CJK_BIG)


def _cjk_value(run: str) -> int:
    if not any(c in _CJK_UNITS or c in _CJK_BIG for c in run):
        # Written digit by digit, like "二〇二四" (2024)
        return int("".join(str(_CJK_DIGITS[c]) for c in run))
    total = section = num = 0
    for c in run:
        if c in _CJK_DIGITS:
            num = _CJK_DIGITS[c]
        elif c in _CJK_UNITS:
            section += (num or 1) * _CJK_UNITS[c]     # "十一" = 11, "二十" = 20
            num = 0
        else:
            total += ((section + num) or 1) * _CJK_BIG[c]  # "一万五千" = 15000
            section = num = 0
    return total + section + num


# ── Text folding ─────────────────────────────────────────────────────────────
_SEPARATORS = set(".·・~,")


def _is_separator(ch: str) -> bool:
    return ch.isspace() or ch in _SEPARATORS or unicodedata.category(ch) in ("Pd", "Pc")


def _strips_marks(base: str) -> bool:
    """Scripts whose accents/vowel points are ignored when sorting (the letters stay)."""
    cp = ord(base)
    return (cp < 0x0250 or 0x1E00 <= cp <= 0x1EFF     # Latin (incl. Vietnamese)
            or 0x0370 <= cp <= 0x03FF or 0x1F00 <= cp <= 0x1FFF   # Greek
            or 0x0400 <= cp <= 0x04FF                  # Cyrillic
            or 0x0590 <= cp <= 0x05FF                  # Hebrew points
            or 0x0600 <= cp <= 0x06FF)                 # Arabic harakat


def _strip_accents(text: str) -> str:
    out = []
    base = ""
    for ch in unicodedata.normalize("NFD", text):
        if unicodedata.combining(ch):
            # "й" (и + breve) is a separate letter in Russian, Ukrainian, Belarusian...
            keep = not base or not _strips_marks(base) or (ch == "̆" and "Ѐ" <= base <= "ӿ")
            if keep:
                out.append(ch)
            continue
        base = ch
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _strip_accents(text)
    chars = []
    for ch in text:
        cp = ord(ch)
        if 0x30A1 <= cp <= 0x30F6:          # katakana -> hiragana
            ch = chr(cp - 0x60)
        chars.append(ch)
    # Thai (เ แ โ ใ ไ) and Lao (ເ ແ ໂ ໃ ໄ) vowels are written before the consonant they follow
    i = 0
    while i < len(chars) - 1:
        a, b = chars[i], chars[i + 1]
        if (("เ" <= a <= "ไ" and "ก" <= b <= "ฮ")
                or ("ເ" <= a <= "ໄ" and "ກ" <= b <= "ຮ")):
            chars[i], chars[i + 1] = b, a
            i += 2                          # the vowel moved past its consonant only
        else:
            i += 1
    return "".join(chars)


def _tokens(text: str) -> Tuple:
    """Separators < numbers < text, so "a 1" < "a1" < "a b" and "file" < "file 2"."""
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if _is_separator(ch):
            while i < n and _is_separator(text[i]):
                i += 1
            out.append((0, 0, ""))
        elif ch.isdecimal():
            j = i
            while j < n and text[j].isdecimal():
                j += 1
            out.append((1, int(text[i:j]), ""))
            i = j
        elif ch in _CJK_NUMERAL_CHARS:
            j = i
            while j < n and text[j] in _CJK_NUMERAL_CHARS:
                j += 1
            out.append((1, _cjk_value(text[i:j]), ""))
            i = j
        else:
            j = i
            while j < n and not (_is_separator(text[j]) or text[j].isdecimal() or text[j] in _CJK_NUMERAL_CHARS):
                j += 1
            out.append((2, 0, text[i:j]))
            i = j
    # A trailing separator doesn't make a name sort later ("cover_" next to "cover")
    while out and out[-1][0] == 0:
        out.pop()
    return tuple(out)


def _split_ext(name: str) -> Tuple[str, str]:
    dot = name.rfind(".")
    if dot <= 0 or dot == len(name) - 1 or len(name) - dot > 12 or " " in name[dot:]:
        return name, ""        # no extension, a dot-file, or a dot inside the name ("Vol. 2")
    return name[:dot], name[dot + 1:]


def name_sort_key(name) -> Tuple:
    """Natural sort key for a file name (see the module notes)."""
    raw = str(name or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not raw:
        return (1,)            # nameless files go after the named ones
    stem, ext = _split_ext(raw)
    folded_stem, folded_ext = _fold(stem), _fold(ext)
    exact = unicodedata.normalize("NFKC", raw).casefold()
    return (0, _tokens(folded_stem), _tokens(folded_ext), folded_stem, exact)


def order_files(items: Sequence[T], order: str, name_of: Callable[[T], str]) -> List[T]:
    """The items in the chosen order; ties keep their posted order."""
    order = normalize_file_order(order)
    items = list(items)
    if order == REVERSED:
        return items[::-1]
    if order == BY_NAME:
        return sorted(items, key=lambda it: name_sort_key(name_of(it)))
    return items
