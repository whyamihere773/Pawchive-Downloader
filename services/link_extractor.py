"""
External Link Harvesting Engine
Detects, extracts, and categorizes cloud links (Mega, Drive, Dropbox, GoFile, etc.),
hyperlinked anchor tags (<a href="...">blue clickable words</a>), markdown links,
and streaming media embeds from post bodies, descriptions, and comments.
"""

import html
import re
from typing import List, Dict, Any, Set, Optional
from urllib.parse import urlparse, parse_qs, unquote

LINK_PATTERNS = {
    "mega": re.compile(r'https?://(?:www\.)?mega\.(?:nz|co\.nz|io)/(?:file/|folder/|embed/|#|#!|#F!|[a-zA-Z0-9_\-#])[^\s"\'<>]+', re.IGNORECASE),
    "gdrive": re.compile(r'https?://(?:drive|docs)\.google\.com/(?:file/d/|open\?id=|drive/(?:u/\d+/)?folders/|uc\?id=|document/d/|spreadsheets/d/|[a-zA-Z0-9_\-/])[^\s"\'<>]+', re.IGNORECASE),
    "dropbox": re.compile(r'https?://(?:www\.)?dropbox\.com/(?:s/|scl/|sh/|browse/|[a-zA-Z0-9_\-/])[^\s"\'<>]+', re.IGNORECASE),
    "pixeldrain": re.compile(r'https?://(?:www\.)?pixeldrain\.com/(?:u/|l/|api/file/)[a-zA-Z0-9_\-]+', re.IGNORECASE),
    "catbox": re.compile(r'https?://(?:files\.)?catbox\.moe/[a-zA-Z0-9\.\-_]+', re.IGNORECASE),
    "mediafire": re.compile(r'https?://(?:www\.)?mediafire\.com/(?:file/|folder/|download/|view/|\?|[a-zA-Z0-9_\-/])[^\s"\'<>]+', re.IGNORECASE),
    "gofile": re.compile(r'https?://(?:www\.)?gofile\.io/(?:d/|#[a-zA-Z0-9_\-]+)[a-zA-Z0-9_\-]+', re.IGNORECASE),
    "1fichier": re.compile(r'https?://(?:www\.)?(?:1fichier\.com|\w+\.1fichier\.com)/[^\s"\'<>]+', re.IGNORECASE),
    "terabox": re.compile(r'https?://(?:www\.)?(?:terabox\.com|teraboxapp\.com|1024tera\.com)/(?:s/|sharing/|[a-zA-Z0-9_\-/])[^\s"\'<>]+', re.IGNORECASE),
    "workupload": re.compile(r'https?://(?:www\.)?workupload\.com/(?:file/|archive/)[^\s"\'<>]+', re.IGNORECASE),
    "qiwi": re.compile(r'https?://(?:www\.)?qiwi\.gg/[^\s"\'<>]+', re.IGNORECASE),
    "bunkr": re.compile(r'https?://(?:www\.)?(?:bunkr|bunkrr)\.(?:is|si|cr|ru|black|media|site|ac|su|la)/(?:a|v|d)/[^\s"\'<>]+', re.IGNORECASE),
    "erome": re.compile(r'https?://(?:www\.)?erome\.com/a/[a-zA-Z0-9]+', re.IGNORECASE),
    "nhentai": re.compile(r'https?://(?:www\.)?nhentai\.net/g/\d+/?', re.IGNORECASE),
    "saint2": re.compile(r'https?://(?:www\.)?saint2\.su/[^\s"\'<>]+', re.IGNORECASE),
    "simpcity": re.compile(r'https?://simpcity\.(?:su|cr|is)/[^\s"\'<>]+', re.IGNORECASE),
}

GENERIC_URL_PATTERN = re.compile(r'https?://[^\s"\'<>()]+', re.IGNORECASE)

# Regex patterns for popular embedded media platforms supported by yt-dlp
YTDLP_MEDIA_PATTERNS = [
    re.compile(r'https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|shorts/|v/)|youtu\.be/)[a-zA-Z0-9_\-]+', re.IGNORECASE),
    re.compile(r'https?://(?:www\.)?(?:player\.)?vimeo\.com/(?:video/)?\d+(?:\?[^\s"\'<>]*)?', re.IGNORECASE),
    re.compile(r'https?://(?:www\.)?streamable\.com/(?:e/)?[a-zA-Z0-9]+', re.IGNORECASE),
    re.compile(r'https?://(?:www\.)?redgifs\.com/(?:watch/|ifr/)?[a-zA-Z0-9\-]+', re.IGNORECASE),
    re.compile(r'https?://(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+/status/\d+', re.IGNORECASE),
    re.compile(r'https?://(?:www\.)?soundcloud\.com/[^\s"\'<>]+/[^\s"\'<>]+', re.IGNORECASE),
    re.compile(r'https?://(?:www\.)?bilibili\.com/video/[a-zA-Z0-9]+', re.IGNORECASE),
    re.compile(r'https?://(?:www\.)?dailymotion\.com/video/[a-zA-Z0-9]+', re.IGNORECASE),
]


class LinkExtractor:
    """
    Extracts, categorizes, and formats external links from post descriptions,
    comments, HTML bodies (including blue clickable hyperlinks), and post metadata.
    """

    @staticmethod
    def clean_and_normalize_url(raw: str) -> Optional[str]:
        """
        Cleans, unescapes, and normalizes a candidate URL string.
        Resolves entity-encoded links (&amp; -> &), removes surrounding quotes/brackets,
        and trims sentence punctuation without breaking Mega folder fragments.
        """
        if not raw or not isinstance(raw, str):
            return None

        # 1. Unescape HTML entities (&amp; -> &, &#x2F; -> /, &quot; -> ", etc.)
        u = html.unescape(raw.strip())

        # 2. Strip surrounding wrapper characters (quotes, parens, brackets, angles)
        u = u.strip("\"'<>{}[]()")

        # 3. Clean scheme-relative URLs (//mega.nz/... -> https://mega.nz/...)
        if u.startswith("//"):
            u = f"https:{u}"
        elif re.match(r'^(?:mega\.(?:nz|co\.nz|io)|drive\.google\.com|docs\.google\.com|dropbox\.com|pixeldrain\.com|mediafire\.com|gofile\.io|1fichier\.com|terabox\.com|teraboxapp\.com|1024tera\.com|workupload\.com|qiwi\.gg|bunkr\.[a-z]+|erome\.com)/', u, re.IGNORECASE):
            u = f"https://{u}"

        # 4. Strip trailing sentence punctuation, but preserve valid URL characters
        while u and u[-1] in ".,;:!?)>]}'\"":
            # Don't strip exclamation mark if part of a Mega fragment like #!key!abc or #F!key
            if u[-1] == "!" and ("mega.nz" in u or "mega.io" in u or "mega.co.nz" in u) and "#" in u:
                break
            u = u[:-1]

        # 5. Must start with http:// or https://
        if not (u.startswith("http://") or u.startswith("https://")):
            return None

        # 6. Parse and validate domain
        try:
            parsed = urlparse(u)
            domain = parsed.netloc.lower()
            if not domain or "." not in domain:
                return None
        except Exception:
            return None

        # 7. Ignore internal Kemono / Pawchive / Coomer platform domains
        internal_domains = [
            "kemono.su", "kemono.party", "coomer.su", "coomer.party",
            "pawchive.pw", "cum.st", "localhost", "127.0.0.1"
        ]
        if any(domain == d or domain.endswith("." + d) for d in internal_domains):
            # Check if this is an external redirect link like /external/?url=...
            if "/external" in parsed.path or "url=" in parsed.query:
                qs = parse_qs(parsed.query)
                target = qs.get("url") or qs.get("target") or qs.get("link")
                if target and target[0]:
                    return LinkExtractor.clean_and_normalize_url(unquote(target[0]))
            return None

        # 8. Skip obvious static site assets (scripts, stylesheets, favicons)
        if any(u.lower().endswith(ext) for ext in (".svg", ".ico", ".css", ".js")):
            return None

        return u

    @classmethod
    def categorize_url(cls, url: str) -> str:
        """Categorizes a cleaned URL by platform/host."""
        url_lower = url.lower()
        if "mega.nz" in url_lower or "mega.co.nz" in url_lower or "mega.io" in url_lower:
            return "mega"
        if "drive.google.com" in url_lower or "docs.google.com" in url_lower:
            return "gdrive"
        if "dropbox.com" in url_lower:
            return "dropbox"
        if "pixeldrain.com" in url_lower:
            return "pixeldrain"
        if "gofile.io" in url_lower:
            return "gofile"
        if "mediafire.com" in url_lower:
            return "mediafire"
        if "1fichier.com" in url_lower:
            return "1fichier"
        if "terabox.com" in url_lower or "teraboxapp.com" in url_lower or "1024tera.com" in url_lower:
            return "terabox"
        if "workupload.com" in url_lower:
            return "workupload"
        if "qiwi.gg" in url_lower:
            return "qiwi"
        if "catbox.moe" in url_lower:
            return "catbox"
        if "bunkr" in url_lower:
            return "bunkr"
        if "erome.com" in url_lower:
            return "erome"
        if "nhentai.net" in url_lower:
            return "nhentai"
        if "saint2.su" in url_lower:
            return "saint2"
        if "simpcity." in url_lower:
            return "simpcity"
        return "other"

    @classmethod
    def extract_embed_urls(cls, post: Dict[str, Any]) -> List[str]:
        """
        Extracts embedded media player URLs (Vimeo, YouTube, Streamable, RedGifs, etc.)
        from post.embed object and post HTML content for downloading via yt-dlp.
        """
        found_urls = set()

        # 1. Check post.embed object (Kemono / Coomer / Pawchive API)
        embed_obj = post.get("embed")
        if isinstance(embed_obj, dict):
            embed_url = embed_obj.get("url") or embed_obj.get("src")
            if embed_url and isinstance(embed_url, str):
                cleaned = cls.clean_and_normalize_url(embed_url)
                if cleaned:
                    found_urls.add(cleaned)

        # 2. Check HTML content / caption for iframes, anchors, and embedded video links
        html_text = f"{post.get('content', '') or ''}\n{post.get('captionHtml', '') or ''}\n{post.get('caption', '') or ''}"
        if html_text.strip():
            # Check iframe src
            iframe_matches = re.findall(r'<iframe\s+[^>]*?src=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
            for m in iframe_matches:
                cleaned = cls.clean_and_normalize_url(m)
                if cleaned:
                    found_urls.add(cleaned)

            # Check known yt-dlp media patterns
            for pat in YTDLP_MEDIA_PATTERNS:
                for match in pat.findall(html_text):
                    cleaned = cls.clean_and_normalize_url(match)
                    if cleaned:
                        found_urls.add(cleaned)

        return sorted(list(found_urls))

    @classmethod
    def extract_links_from_text(cls, text: str) -> Dict[str, List[str]]:
        """
        Scans text/HTML for all cloud storage, external hosts, and media links.
        Accurately extracts:
        - Blue clickable hyperlinked words (<a href="...">word</a>)
        - Embedded iframes (<iframe src="...">)
        - Markdown hyperlinks ([anchor](url))
        - Raw plain URLs (https://...)
        - Bare domain URLs without http:// (mega.nz/..., drive.google.com/...)
        Returns a dictionary mapping platform name -> list of unique URLs.
        """
        if not text:
            return {}

        candidates: List[str] = []

        # 1. Extract from HTML <a> tags: <a ... href="..." ...>blue clickable word</a>
        # Handles single quotes, double quotes, unquoted hrefs
        candidates.extend(re.findall(r'<a\s+[^>]*?href\s*=\s*["\']([^"\']+)["\']', text, re.IGNORECASE))
        candidates.extend(re.findall(r'<a\s+[^>]*?href\s*=\s*([^\s>"\']+)', text, re.IGNORECASE))

        # 2. Extract from <iframe> tags
        candidates.extend(re.findall(r'<iframe\s+[^>]*?src\s*=\s*["\']([^"\']+)["\']', text, re.IGNORECASE))

        # 3. Extract from Markdown links: [anchor](url)
        candidates.extend(re.findall(r'\[(?:[^\]]*)\]\(([^)\s]+)\)', text))

        # 4. Extract raw http/https URLs
        candidates.extend(re.findall(r'https?://[^\s"\'<>]+', text, re.IGNORECASE))

        # 5. Extract scheme-relative URLs: //...
        candidates.extend(re.findall(r'(?:^|[\s"\'<>(])(//[^\s"\'<>]+)', text, re.IGNORECASE))

        # 6. Extract bare cloud domains without http:// (e.g., mega.nz/..., drive.google.com/...)
        candidates.extend(re.findall(
            r'(?:^|[\s"\'<>(])((?:mega\.(?:nz|co\.nz|io)|drive\.google\.com|docs\.google\.com|dropbox\.com|pixeldrain\.com|mediafire\.com|gofile\.io|1fichier\.com|terabox\.com|teraboxapp\.com|1024tera\.com|workupload\.com|qiwi\.gg|bunkr\.[a-z]+|erome\.com)/[^\s"\'<>]+)',
            text, re.IGNORECASE
        ))

        # Clean, normalize, and deduplicate all candidates
        unique_urls: Set[str] = set()
        for raw in candidates:
            cleaned = cls.clean_and_normalize_url(raw)
            if cleaned:
                unique_urls.add(cleaned)

        # Categorize into platforms
        results: Dict[str, Set[str]] = {}
        for url in unique_urls:
            platform = cls.categorize_url(url)
            results.setdefault(platform, set()).add(url)

        # Convert sets to sorted lists, remove empty categories
        return {k: sorted(list(v)) for k, v in results.items() if v}

    @classmethod
    def extract_links_from_post(cls, post: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Comprehensive extractor: inspects ALL available post fields:
        - title
        - content (HTML body with embedded clickable links)
        - captionHtml & caption
        - description
        - embed object (url, src, description)
        - comments & comments_text
        - attachments & file objects
        """
        if not isinstance(post, dict):
            return {}

        text_pieces: List[str] = []

        # Title
        if post.get("title"):
            text_pieces.append(str(post["title"]))

        # HTML body and captions (contains the blue clickable hyperlinks)
        for field in ("content", "captionHtml", "caption", "description", "body", "text"):
            val = post.get(field)
            if val and isinstance(val, str):
                text_pieces.append(val)

        # Embeds
        embed = post.get("embed")
        if isinstance(embed, dict):
            for k in ("url", "src", "description", "title"):
                val = embed.get(k)
                if val and isinstance(val, str):
                    text_pieces.append(val)
        elif isinstance(embed, str):
            text_pieces.append(embed)

        # Comments
        if post.get("comments_text"):
            text_pieces.append(str(post["comments_text"]))
        comms = post.get("comments")
        if isinstance(comms, list):
            for c in comms:
                if isinstance(c, dict):
                    for k in ("content", "message", "text", "comment"):
                        val = c.get(k)
                        if val and isinstance(val, str):
                            text_pieces.append(val)
                elif isinstance(c, str):
                    text_pieces.append(c)

        # Attachments & Files (if pointing to external services)
        attachments = post.get("attachments")
        if isinstance(attachments, list):
            for a in attachments:
                if isinstance(a, dict):
                    for k in ("path", "name"):
                        val = a.get(k)
                        if val and isinstance(val, str) and ("://" in val or val.startswith("//")):
                            text_pieces.append(val)
        file_obj = post.get("file")
        if isinstance(file_obj, dict):
            for k in ("path", "name"):
                val = file_obj.get(k)
                if val and isinstance(val, str) and ("://" in val or val.startswith("//")):
                    text_pieces.append(val)

        combined_text = "\n".join(text_pieces)
        return cls.extract_links_from_text(combined_text)

    @classmethod
    def extract_all_flat(cls, text: str) -> List[str]:
        """Returns a flat list of all unique external URLs from text/HTML."""
        categorized = cls.extract_links_from_text(text)
        flat = []
        for urls in categorized.values():
            flat.extend(urls)
        return sorted(list(set(flat)))

    @classmethod
    def format_export_text(cls, post_title: str, creator_name: str, links_dict: Dict[str, List[str]]) -> str:
        """Formats extracted links into a clean, human-readable text document."""
        if not links_dict:
            return ""

        lines = [
            f"=== {post_title} (Creator: {creator_name}) ===",
            ""
        ]
        for platform, urls in links_dict.items():
            lines.append(f"[{platform.upper()} - {len(urls)} link(s)]")
            for u in urls:
                lines.append(f"  • {u}")
            lines.append("")
        lines.append("-" * 50)
        lines.append("")
        return "\n".join(lines)

