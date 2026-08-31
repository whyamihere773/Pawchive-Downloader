import re
import html
import urllib.parse
from typing import Tuple, List, Dict, Any, Optional
import time
import requests

def fetch_bunkr_album(url: str, headers: Optional[dict] = None, timeout: int = 25) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Parses a Bunkr album URL (e.g. https://bunkr.is/a/albumId) and extracts direct media links.
    Returns: (album_title, list_of_file_dicts)
    """
    session = requests.Session()
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": url,
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
        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
        title = title_match.group(1).split("|")[0].strip() if title_match else "Bunkr Album"
        title = re.sub(r'[\\/*?:"<>|]', '_', title).strip()

        # Find media URLs / download links
        media_urls = set()
        for m in re.finditer(r'href=["\']((?:https?://[^"\']+|/(?:v|d|i)/[^"\']+))["\']', content):
            raw_link = m.group(1)
            if not raw_link.startswith("http"):
                raw_link = urllib.parse.urljoin(url, raw_link)
            if any(ext in raw_link.lower() for ext in ['.mp4', '.mkv', '.webm', '.jpg', '.png', '.jpeg', '.zip', '.rar', '.7z']):
                media_urls.add(raw_link)

        file_list = []
        for idx, media_url in enumerate(sorted(list(media_urls)), 1):
            fname = media_url.split("?")[0].split("/")[-1]
            if not fname:
                fname = f"bunkr_file_{idx:03d}"
            file_list.append({
                "url": media_url,
                "filename": fname,
                "headers": {"Referer": url}
            })

        return title, file_list
    except Exception:
        return None, []
