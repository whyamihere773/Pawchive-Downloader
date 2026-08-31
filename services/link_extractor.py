"""
External Link Harvesting Engine
Detects, extracts, and categorizes cloud links (Mega, Drive, Dropbox, GoFile)
and streaming media embeds from post descriptions and comments.
"""

import re
from typing import List, Dict, Any, Set
from urllib.parse import urlparse

LINK_PATTERNS = {
    "mega": re.compile(r'https?://(?:www\.)?mega\.(?:nz|co\.nz)/(?:file|folder|#)[^\s"\'<>]+', re.IGNORECASE),
    "gdrive": re.compile(r'https?://(?:drive|docs)\.google\.com/(?:file/d/|open\?id=|drive/folders/)[^\s"\'<>]+', re.IGNORECASE),
    "dropbox": re.compile(r'https?://(?:www\.)?dropbox\.com/(?:s|scl|sh)/[^\s"\'<>]+', re.IGNORECASE),
    "pixeldrain": re.compile(r'https?://pixeldrain\.com/(?:u|l)/[a-zA-Z0-9]+', re.IGNORECASE),
    "catbox": re.compile(r'https?://files\.catbox\.moe/[a-zA-Z0-9\.\-_]+', re.IGNORECASE),
    "mediafire": re.compile(r'https?://(?:www\.)?mediafire\.com/(?:file|folder)/[^\s"\'<>]+', re.IGNORECASE),
    "gofile": re.compile(r'https?://(?:www\.)?gofile\.io/d/[a-zA-Z0-9]+', re.IGNORECASE),
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
    comments, and HTML bodies.
    """

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
                cleaned = embed_url.rstrip(".,;!?'\")>]}").strip()
                if cleaned.startswith("http"):
                    found_urls.add(cleaned)

        # 2. Check HTML content / caption for iframes and embedded video links
        html_text = f"{post.get('content', '') or ''}\n{post.get('captionHtml', '') or ''}\n{post.get('caption', '') or ''}"
        if html_text.strip():
            # Check iframe src
            iframe_matches = re.findall(r'<iframe\s+[^>]*src=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
            for m in iframe_matches:
                m_clean = m.strip()
                if m_clean.startswith("//"):
                    m_clean = f"https:{m_clean}"
                if m_clean.startswith("http"):
                    found_urls.add(m_clean)

            # Check known yt-dlp media patterns
            for pat in YTDLP_MEDIA_PATTERNS:
                for match in pat.findall(html_text):
                    cleaned = match.rstrip(".,;!?'\")>]}").strip()
                    if cleaned:
                        found_urls.add(cleaned)

        return sorted(list(found_urls))

    @classmethod
    def extract_links_from_text(cls, text: str) -> Dict[str, List[str]]:
        """
        Scans text/HTML for cloud storage, external hosts, and media links.
        Returns a dictionary mapping platform name -> list of unique URLs.
        """
        if not text:
            return {}

        results: Dict[str, Set[str]] = {k: set() for k in LINK_PATTERNS.keys()}
        results["other"] = set()

        # Check specific platform patterns
        matched_urls = set()
        for platform, regex in LINK_PATTERNS.items():
            matches = regex.findall(text)
            for m in matches:
                cleaned = m.rstrip(".,;!?'\")>]}").strip()
                if cleaned:
                    results[platform].add(cleaned)
                    matched_urls.add(cleaned)

        # Catch remaining valid HTTP/HTTPS URLs (excluding internal Kemono/Pawchive URLs)
        all_urls = GENERIC_URL_PATTERN.findall(text)
        for u in all_urls:
            cleaned = u.rstrip(".,;!?'\")>]}").strip()
            if cleaned not in matched_urls:
                domain = urlparse(cleaned).netloc.lower()
                if not any(d in domain for d in ["kemono", "coomer", "pawchive", "localhost"]):
                    results["other"].add(cleaned)

        # Convert sets to sorted lists, remove empty categories
        return {k: sorted(list(v)) for k, v in results.items() if v}

    @classmethod
    def extract_all_flat(cls, text: str) -> List[str]:
        """Returns a flat list of all unique external URLs."""
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

