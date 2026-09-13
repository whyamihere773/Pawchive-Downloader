"""
Text formatting and cleaning utilities.
Handles mojibake repair, invisible unicode stripping, HTML entity unescaping,
and filesystem name sanitization across Kemono, Coomer, Bunkr, and third-party providers.
"""
import html
import re
from typing import Optional

INVISIBLE_CHARS_PATTERN = re.compile(
    r'[\ufeff\u200b-\u200f\u2028-\u202f\u2060-\u206f\u00ad\ufffd]'
)
MOJIBAKE_MARKERS = ('ï»¿', 'ðŸ', 'â€™', 'â€œ', 'â€”', 'Ã©', 'Ã', 'ð')


def clean_text(text: Optional[str]) -> str:
    """
    Cleans, repairs and formats raw display text:
    1. Unescapes HTML entities (e.g. &amp;, &#39;, &quot;)
    2. Repairs mojibake (e.g. UTF-8 erroneously decoded as Latin-1 or CP1252)
    3. Strips zero-width, invisible formatting, and BOM characters (e.g. \\ufeff, \\u200b)
    4. Normalizes whitespace and trims
    """
    if not text:
        return ""

    # 1. Unescape HTML entities
    s = html.unescape(str(text))

    # 2. Repair mojibake if UTF-8 was decoded as Latin-1 / CP1252
    if any(m in s for m in MOJIBAKE_MARKERS):
        for enc in ('latin1', 'cp1252'):
            try:
                fixed = s.encode(enc).decode('utf-8')
                s = fixed
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass

    # 3. Strip zero-width / invisible / BOM formatting
    s = INVISIBLE_CHARS_PATTERN.sub('', s)
    s = s.replace('ï»¿', '')

    # 4. Collapse consecutive whitespace
    s = re.sub(r'[ \t\r\n]+', ' ', s).strip()
    return s


def sanitize_filesystem_name(name: Optional[str], fallback: str = "item", max_len: int = 180) -> str:
    """
    Sanitizes text for safe use as a directory or file name on Windows / Unix:
    - Cleans mojibake and invisible characters via clean_text
    - Replaces forbidden filesystem characters (\\ / : * ? \" < > |) with underscores
    - Trims trailing periods, spaces, and limits length
    """
    cleaned = clean_text(name)
    if not cleaned:
        return fallback

    # Replace forbidden filesystem characters
    safe = re.sub(r'[\\/*?:"<>|]', '_', cleaned)
    safe = re.sub(r'_+', '_', safe).strip(" ._\t\r\n")

    if max_len and len(safe) > max_len:
        safe = safe[:max_len].strip(" ._")

    return safe or fallback


def strip_html_tags(html_str: Optional[str]) -> str:
    """
    Converts HTML markup into clean readable plaintext:
    - Converts <br>, <p>, <div>, <li> to proper linebreaks
    - Strips remaining HTML tags (<[^>]+>)
    - Unescapes HTML entities (&#x27;, &quot;, &amp;, etc.)
    - Removes invisible unicode and repairs mojibake
    - Collapses excessive blank lines
    """
    if not html_str:
        return ""
    text = str(html_str)
    # Replace line breaks and structural tags
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p\s*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li\s*>', '\n• ', text, flags=re.IGNORECASE)
    # Strip any remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Unescape HTML entities
    text = html.unescape(text)
    # Strip invisible formatting characters
    text = INVISIBLE_CHARS_PATTERN.sub('', text)
    text = text.replace('ï»¿', '')
    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
