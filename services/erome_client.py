import re
import html
import urllib.parse
from typing import Tuple, List, Dict, Any, Optional
import time
import requests

def fetch_erome_album(url: str, headers: Optional[dict] = None, timeout: int = 25) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Parses an Erome album URL (e.g. https://www.erome.com/a/albumId) and extracts direct media links.
    Returns: (album_title, list_of_file_dicts)
    """
    album_id_match = re.search(r"/a/(\w+)", url)
    if not album_id_match:
        return None, []

    album_id = album_id_match.group(1)
    session = requests.Session()
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.erome.com/",
    }
    if headers:
        req_headers.update(headers)

    content = None
    for attempt in range(3):
        try:
            resp = session.get(url, headers=req_headers, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            content = resp.text
            break
        except Exception:
            if attempt == 2:
                return None, []
            time.sleep(1.5 * (attempt + 1))

    if not content:
        return None, []

    try:
        title_match = re.search(r'property="og:title"\s+content="([^"]+)"', content)
        title = html.unescape(title_match.group(1)) if title_match else f"Album_{album_id}"
        sanitized_title = re.sub(r'[\\/*?:"<>|]', '_', title).strip()

        urls = []
        # Find video sources
        for m in re.finditer(r'<source\s+src="([^"]+)"', content):
            urls.append(m.group(1))
        # Find images
        for m in re.finditer(r'<img[^>]+(?:data-src|src)="([^"]+)"[^>]+class="[^"]*img-front[^"]*"', content):
            urls.append(m.group(1))
        # Also generic media matches on erome cdn
        for m in re.finditer(r'https?://(?:s\d+\.)?erome\.com/[^\s"\'<>]+\.(?:mp4|webm|jpg|jpeg|png|webp)', content, re.IGNORECASE):
            if m.group(0) not in urls:
                urls.append(m.group(0))

        # Deduplicate
        seen = set()
        deduped_urls = []
        for u in urls:
            if u not in seen and not u.endswith("thumbnail.jpg"):
                seen.add(u)
                deduped_urls.append(u)

        file_list = []
        for idx, media_url in enumerate(deduped_urls, 1):
            ext = media_url.split("?")[0].split(".")[-1] or "mp4"
            fname = f"{album_id}_{idx:03d}.{ext}"
            file_list.append({
                "url": media_url,
                "filename": fname,
                "headers": {"Referer": url}
            })

        folder_name = f"Erome - {sanitized_title} [{album_id}]"
        return folder_name, file_list
    except Exception:
        return None, []
