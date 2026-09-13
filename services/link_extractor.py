"""
External Link Harvesting Engine
Detects, extracts, and categorizes cloud links (Mega, Drive, Dropbox, GoFile, etc.),
hyperlinked anchor tags (<a href="...">blue clickable words</a>), markdown links,
and streaming media embeds from post bodies, descriptions, and comments.
"""

import html
import re
import base64
from typing import List, Dict, Any, Set, Optional, Tuple
from urllib.parse import urlparse, parse_qs, unquote

LINK_PATTERNS = {
    "mega": re.compile(r'https?://(?:www\.)?mega\.(?:nz|co\.nz|io)/(?:file/|folder/|embed/|#|#!|#F!|[a-zA-Z0-9_\-#])[^\s"\'<>]+', re.IGNORECASE),
    "gdrive": re.compile(r'https?://(?:(?:drive|docs|drive\.usercontent)\.google\.com)/(?:file/d/|open\?id=|drive/(?:u/\d+/)?folders/|uc\?id=|document/d/|spreadsheets/d/|download\?id=|[a-zA-Z0-9_\-/])[^\s"\'<>]+', re.IGNORECASE),
    "dropbox": re.compile(r'https?://(?:www\.)?dropbox\.com/(?:s/|scl/|sh/|browse/|[a-zA-Z0-9_\-/])[^\s"\'<>]+', re.IGNORECASE),
    "pixeldrain": re.compile(r'https?://(?:www\.)?pixeldrain\.com/(?:u/|l/|api/file/)[a-zA-Z0-9_\-]+', re.IGNORECASE),
    "catbox": re.compile(r'https?://(?:files\.)?catbox\.moe/[a-zA-Z0-9\.\-_]+', re.IGNORECASE),
    "mediafire": re.compile(r'https?://(?:www\.)?mediafire\.com/(?:file/|folder/|download/|view/|\?|[a-zA-Z0-9_\-/])[^\s"\'<>]+', re.IGNORECASE),
    "gofile": re.compile(r'https?://(?:www\.)?gofile\.io/(?:d/|#[a-zA-Z0-9_\-]+)[a-zA-Z0-9_\-]+', re.IGNORECASE),
    "1fichier": re.compile(r'https?://(?:www\.)?(?:1fichier\.com|\w+\.1fichier\.com)/[^\s"\'<>]+', re.IGNORECASE),
    "terabox": re.compile(r'https?://(?:www\.)?(?:terabox\.com|teraboxapp\.com|1024tera\.com)/(?:s/|sharing/|[a-zA-Z0-9_\-/])[^\s"\'<>]+', re.IGNORECASE),
    "workupload": re.compile(r'https?://(?:www\.)?workupload\.com/(?:file/|archive/)[^\s"\'<>]+', re.IGNORECASE),
    "qiwi": re.compile(r'https?://(?:www\.)?qiwi\.gg/[^\s"\'<>]+', re.IGNORECASE),
    "bunkr": re.compile(r'https?://(?:[a-zA-Z0-9_-]+\.)?(?:(?:bunkr|bunkrr|bunk)\.[a-z0-9]+|balbums\.st)/(?:a|v|d|f|i|file)/[^\s"\'<>]+', re.IGNORECASE),
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
        elif re.match(r'^(?:mega\.(?:nz|co\.nz|io)|drive\.google\.com|docs\.google\.com|dropbox\.com|pixeldrain\.com|mediafire\.com|gofile\.io|1fichier\.com|terabox\.com|teraboxapp\.com|1024tera\.com|workupload\.com|qiwi\.gg|(?:bunkr|bunkrr|bunk)\.[a-z0-9]+|balbums\.st|erome\.com)/', u, re.IGNORECASE):
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
        if "drive.google.com" in url_lower or "docs.google.com" in url_lower or "drive.usercontent.google.com" in url_lower:
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
        if "bunkr" in url_lower or "balbums.st" in url_lower or "cdn.cr" in url_lower or "scdn.st" in url_lower:
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
            r'(?:^|[\s"\'<>(])((?:mega\.(?:nz|co\.nz|io)|drive\.google\.com|docs\.google\.com|dropbox\.com|pixeldrain\.com|mediafire\.com|gofile\.io|1fichier\.com|terabox\.com|teraboxapp\.com|1024tera\.com|workupload\.com|qiwi\.gg|(?:bunkr|bunkrr|bunk)\.[a-z0-9]+|balbums\.st|erome\.com)/[^\s"\'<>]+)',
            text, re.IGNORECASE
        ))

        # 7. Rescue defanged / obfuscated and Base64 encoded cloud URLs
        candidates.extend(cls.rescue_obfuscated_and_base64(text))

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
    def extract_all_flat(cls, text: str) -> List[str]:
        """Returns a flat, deduplicated list of all extracted URLs across all categories."""
        by_cat = cls.extract_links_from_text(text)
        seen: Set[str] = set()
        flat: List[str] = []
        for urls in by_cat.values():
            for u in urls:
                if u not in seen:
                    seen.add(u)
                    flat.append(u)
        return flat

    @classmethod
    def format_export_text(cls, post_title: str, artist_name: str, extracted: Dict[str, List[str]]) -> str:
        """Formats extracted links into a human-readable export block."""
        lines = [f"=== {post_title} (Creator: {artist_name}) ==="]
        for platform, urls in extracted.items():
            lines.append(f"[{platform.upper()}]")
            for u in urls:
                lines.append(f"  - {u}")
        return "\n".join(lines)

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
    def rescue_obfuscated_and_base64(cls, text: str) -> List[str]:
        """
        Detects and decodes:
        1. Base64 strings encoding cloud links (e.g., aHR0cHM6Ly9tZWdhLm56...)
        2. Defanged / broken URLs (e.g., h**ps://, hxxps://, [.] or (dot))
        """
        if not text:
            return []

        rescued: List[str] = []

        # 1. Defanged URLs (h**ps:// or hxxps:// and [.] / (dot))
        defanged = re.sub(r'h[\*_x]{2,4}ps?://', 'https://', text, flags=re.IGNORECASE)
        defanged = re.sub(r'\[\.\]|\(dot\)', '.', defanged, flags=re.IGNORECASE)
        if defanged != text:
            for pat in (r'https?://[^\s"\'<>]+', r'(?:mega\.(?:nz|io)|drive\.google\.com|pixeldrain\.com)/[^\s"\'<>]+'):
                for m in re.findall(pat, defanged, re.IGNORECASE):
                    rescued.append(m)

        # 2. Base64 encoded strings
        # Look for base64-like blocks of length 16 to 600
        b64_matches = re.findall(r'(?:[A-Za-z0-9+/]{4}){4,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?', text)
        for b64 in b64_matches:
            if len(b64) < 16 or len(b64) > 600:
                continue
            try:
                decoded_bytes = base64.b64decode(b64, validate=True)
                decoded_str = decoded_bytes.decode('utf-8', errors='ignore').strip()
                if any(domain in decoded_str.lower() for domain in (
                    "http://", "https://", "mega.nz", "mega.io", "drive.google.com",
                    "dropbox.com", "pixeldrain.com", "gofile.io", "mediafire.com",
                    "1fichier.com", "bunkr", "erome.com"
                )):
                    # Check if plain URL or multiple URLs
                    for u in re.findall(r'https?://[^\s"\'<>]+', decoded_str, re.IGNORECASE):
                        rescued.append(u)
                    if not rescued and ("mega." in decoded_str or "drive.google" in decoded_str):
                        rescued.append(decoded_str)
            except Exception:
                pass

        return rescued

    @classmethod
    def extract_passwords_with_positions(cls, text: str) -> List[Dict[str, Any]]:
        """
        Finds passwords in text along with character start/end positions and matching labels.
        Supports multilingual labels: English, Japanese, Chinese, Russian, Korean, French, German.
        """
        if not text:
            return []

        # Plain text conversion for HTML entities
        unescaped = html.unescape(text)
        candidates: List[Dict[str, Any]] = []

        patterns = [
            # English standard: password: VALUE / pw: VALUE / pass: VALUE
            (r'(?i)(?:password|passwords|psswd|pswd|passwd|pass|pw|pwd|pd|passcode|zip pass|rar pass|encryption key)\s*[:=\-–—]\s*([^\s<>"\n,;|]{2,64})', "english"),
            # English is: password is VALUE
            (r'(?i)(?:password|pwd|pw)\s+is\s+([^\s<>"\n,;|]{2,64})', "english_phrase"),
            # English brackets: [PW: VALUE] or (password=VALUE)
            (r'(?i)[\[(](?:password|pass|pw|pwd|pd)\s*[:=]?\s*([^\])\s]+)[\])]', "bracketed"),
            # Japanese: パスワード / パス / 解凍パス / 解凍PW
            (r'(?:パスワード|パス|解凍パス|解凍PW|解凍pass)\s*[:：=–—]?\s*([^\s<>"\n,;|]{2,64})', "japanese"),
            # Japanese brackets: 【パス: VALUE】
            (r'【(?:パスワード|パス|解凍パス|PW|解压密码|密码)\s*[:：=]?\s*([^】\s]+)】', "cjk_bracket"),
            # Simplified / Traditional Chinese: 解压密码 / 密码 / 解壓密碼 / 提取码
            (r'(?:解压密码|解壓密碼|密码|密碼|提取码|提取碼)\s*[:：=–—]?\s*([^\s<>"\n,;|]{2,64})', "chinese"),
            # Russian: пароль / пасс
            (r'(?i)(?:пароль|пасс)\s*[:=\-–—]?\s*([^\s<>"\n,;|]{2,64})', "russian"),
            # Korean: 비밀번호 / 비번
            (r'(?:비밀번호|비번)\s*[:：=–—]?\s*([^\s<>"\n,;|]{2,64})', "korean"),
            # French: mot de passe / mdp
            (r'(?i)(?:mot de passe|mdp)\s*[:=\-–—]\s*([^\s<>"\n,;|]{2,64})', "french"),
            # German: passwort / kennwort
            (r'(?i)(?:passwort|kennwort)\s*[:=\-–—]\s*([^\s<>"\n,;|]{2,64})', "german"),
        ]

        seen_values = set()
        for pat, lang in patterns:
            for m in re.finditer(pat, unescaped):
                val = m.group(1).strip().strip('"\'“”‘’')
                # Clean trailing punctuation
                while val and val[-1] in ".,;:!?)>]}":
                    val = val[:-1]
                if len(val) >= 2 and val not in seen_values and not val.lower().startswith("http"):
                    seen_values.add(val)
                    candidates.append({
                        "password": val,
                        "start": m.start(1),
                        "end": m.end(1),
                        "language": lang
                    })

        return candidates

    @classmethod
    def extract_links_with_details(cls, text: str) -> List[Dict[str, Any]]:
        """
        Extracts all cloud links, finds nearby passwords using proximity weighting,
        and returns detailed link objects ready for Link Vault ingestion.
        """
        if not text:
            return []

        # 1. Extract all candidate passwords with positions
        pw_candidates = cls.extract_passwords_with_positions(text)
        all_post_passwords = [p["password"] for p in pw_candidates]

        # 2. Extract links and find their character offsets in text
        categorized = cls.extract_links_from_text(text)
        flat_urls = []
        for urls in categorized.values():
            flat_urls.extend(urls)
        flat_urls = sorted(list(set(flat_urls)))

        results = []
        for u in flat_urls:
            platform = cls.categorize_url(u)

            # Find closest password in text
            u_pos = text.find(u)
            if u_pos == -1:
                # Try finding without scheme
                bare = re.sub(r'^https?://', '', u)
                u_pos = text.find(bare)

            assigned_passwords = []
            source = "post"

            if u_pos != -1 and pw_candidates:
                # Interval distance between [u_pos, u_end] and [pw_start, pw_end]
                u_end = u_pos + len(u)
                closest_dist = float("inf")
                closest_pw = None
                for pw in pw_candidates:
                    pw_start = pw["start"]
                    pw_end = pw["end"]
                    if pw_start >= u_end:
                        dist = pw_start - u_end
                    elif pw_end <= u_pos:
                        dist = u_pos - pw_end
                    else:
                        dist = 0

                    if dist < closest_dist and dist <= 350:
                        closest_dist = dist
                        closest_pw = pw["password"]

                if closest_pw:
                    assigned_passwords.append(closest_pw)
                    source = "proximity"

            if not assigned_passwords and all_post_passwords:
                assigned_passwords = list(all_post_passwords)
                source = "post"

            results.append({
                "url": u,
                "platform": platform,
                "passwords": assigned_passwords,
                "all_post_passwords": all_post_passwords,
                "password_source": source
            })

        return results

    @classmethod
    def resolve_cross_post_links_and_passwords(
        cls,
        post: Dict[str, Any],
        api_client,
        visited_posts: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        1-Hop Cross-Post Resolver:
        If a post body contains references or links to another post (e.g. pinned master post,
        rules post, or cross-post on Patreon, Fanbox, Fantia, Boosty, Kemono, Pawchive):
        Fetches the target post text and comments from OP, and harvests additional credentials.
        """
        if not isinstance(post, dict) or not api_client:
            return []

        if visited_posts is None:
            visited_posts = set()

        current_post_id = str(post.get("id") or post.get("post_id") or "")
        if current_post_id:
            visited_posts.add(current_post_id)

        # Search for post URLs in content, caption, and description
        text_to_scan = f"{post.get('content', '') or ''}\n{post.get('description', '') or ''}\n{post.get('caption', '') or ''}"

        # Import parser safely
        from core.parser import KemonoURLParser

        # Find all URLs mentioned in post text
        urls = re.findall(r'https?://[^\s"\'<>]+', text_to_scan, re.IGNORECASE)
        target_results: List[Dict[str, Any]] = []

        for raw_u in urls:
            parsed = KemonoURLParser.parse(raw_u)
            if not parsed.is_valid:
                continue

            target_post_id = parsed.post_id
            if not target_post_id or target_post_id in visited_posts:
                continue

            # If user_id is empty (e.g. native patreon link /posts/123), inherit from parent post
            if not parsed.user_id and post.get("user"):
                parsed.user_id = str(post.get("user"))
            elif not parsed.user_id and post.get("user_id"):
                parsed.user_id = str(post.get("user_id"))

            visited_posts.add(target_post_id)

            try:
                # 1-Hop query: Fetch target post
                target_post = api_client.fetch_single_post(parsed)
                if not target_post:
                    continue

                target_text = f"{target_post.get('title', '')}\n{target_post.get('content', '')}\n{target_post.get('description', '')}"

                # Also fetch OP comments for target post
                op_user = str(target_post.get("user") or target_post.get("user_id") or parsed.user_id)
                comments = api_client.fetch_post_comments(parsed.domain, parsed.service, op_user, target_post_id)
                if comments:
                    for c in comments:
                        if isinstance(c, dict):
                            c_author = str(c.get("commenter") or c.get("user") or "")
                            if c_author == op_user or not op_user:
                                target_text += f"\n{c.get('content', '') or ''}"

                # Extract links and passwords from target post
                extracted = cls.extract_links_with_details(target_text)
                for item in extracted:
                    item["password_source"] = "cross_post"
                    target_results.append(item)

                logger.info(
                    f"Cross-post resolved: Fetched post {target_post_id} (+{len(extracted)} link/pw items).",
                    category="extractor"
                )
            except Exception as e:
                logger.debug(f"Could not resolve cross-post {target_post_id}: {e}", category="extractor")

        return target_results

    @classmethod
    def extract_post_vault_record(
        cls,
        post: Dict[str, Any],
        api_client=None,
        domain: str = "",
        service: str = "",
        user_id: str = ""
    ) -> Dict[str, Any]:
        """
        Extracts and prepares a comprehensive Link Vault post record from an API post object.
        Harvests:
        - Post metadata (id, title, published date, canonical url)
        - Embedded clickable hyperlinks & markdown links
        - Proximity-associated passwords and post-level passwords
        - Embedded media player URLs (Vimeo, YouTube, Streamable, RedGifs)
        - Optional 1-hop cross-post links and master post credentials
        """
        if not isinstance(post, dict):
            return {}

        pid = str(post.get("id") or post.get("post_id") or "")
        title = str(post.get("title") or "Untitled Post").strip()
        published = str(post.get("published") or post.get("added") or post.get("edited") or post.get("date") or "")

        # 1. Gather all text fields
        text_pieces: List[str] = []
        if post.get("title"):
            text_pieces.append(str(post["title"]))

        for field in ("content", "captionHtml", "caption", "description", "body", "text"):
            val = post.get(field)
            if val and isinstance(val, str):
                text_pieces.append(val)

        embed = post.get("embed")
        if isinstance(embed, dict):
            for k in ("url", "src", "description", "title"):
                val = embed.get(k)
                if val and isinstance(val, str):
                    text_pieces.append(val)
        elif isinstance(embed, str):
            text_pieces.append(embed)

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

        attachments = post.get("attachments")
        if isinstance(attachments, list):
            for a in attachments:
                if isinstance(a, dict):
                    for k in ("path", "name"):
                        val = a.get(k)
                        if val and isinstance(val, str) and ("://" in val or val.startswith("//")):
                            text_pieces.append(val)

        combined_text = "\n".join(text_pieces)

        # 2. Extract links with proximity password pairing
        link_items = cls.extract_links_with_details(combined_text)
        seen_urls = {cls.clean_and_normalize_url(item["url"]) for item in link_items if item.get("url")}

        # 3. Extract media embeds (Vimeo, YouTube, Streamable, etc.)
        embed_urls = cls.extract_embed_urls(post)
        for eu in embed_urls:
            norm_eu = cls.clean_and_normalize_url(eu)
            if norm_eu and norm_eu not in seen_urls:
                seen_urls.add(norm_eu)
                link_items.append({
                    "url": norm_eu,
                    "platform": cls.categorize_url(norm_eu),
                    "passwords": [],
                    "all_post_passwords": [],
                    "password_source": "embed"
                })

        # 4. Extract post passwords
        pw_candidates = cls.extract_passwords_with_positions(combined_text)
        post_passwords = sorted(list({p["password"] for p in pw_candidates if p.get("password")}))

        # 5. Cross-post resolution if API client provided
        if api_client:
            try:
                cross_items = cls.resolve_cross_post_links_and_passwords(post, api_client)
                for ci in cross_items:
                    ci_url = cls.clean_and_normalize_url(ci.get("url", ""))
                    if ci_url and ci_url not in seen_urls:
                        seen_urls.add(ci_url)
                        link_items.append(ci)
                        for pw in ci.get("passwords", []):
                            if pw and pw not in post_passwords:
                                post_passwords.append(pw)
            except Exception:
                pass

        # 6. Canonical post URL
        post_url = ""
        if domain and service and user_id and pid:
            post_url = f"https://{domain}/{service}/user/{user_id}/post/{pid}"
        elif post.get("post_url") or post.get("url"):
            post_url = str(post.get("post_url") or post.get("url"))

        from core.text_utils import strip_html_tags
        clean_body = strip_html_tags(combined_text)

        return {
            "post_id": pid,
            "title": title,
            "published": published,
            "full_text": clean_body,
            "post_url": post_url,
            "passwords": post_passwords,
            "links": link_items
        }



