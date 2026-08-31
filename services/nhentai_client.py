import re
from typing import Tuple, List, Dict, Any, Optional
import time
import requests

def fetch_nhentai_gallery(gallery_id_or_url: str, headers: Optional[dict] = None, timeout: int = 25) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Fetches gallery metadata and page image URLs for nHentai.
    Accepts an ID (e.g. '123456') or URL ('https://nhentai.net/g/123456/').
    Returns: (gallery_title, list_of_page_dicts)
    """
    gid_match = re.search(r'(\d+)', str(gallery_id_or_url))
    if not gid_match:
        return None, []

    gallery_id = gid_match.group(1)
    api_url = f"https://nhentai.net/api/v2/galleries/{gallery_id}"
    
    session = requests.Session()
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*"
    }
    if headers:
        req_headers.update(headers)

    data = None
    for attempt in range(3):
        try:
            resp = session.get(api_url, headers=req_headers, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            if resp.status_code != 200:
                return None, []
            data = resp.json()
            break
        except Exception:
            if attempt == 2:
                return None, []
            time.sleep(1.5 * (attempt + 1))

    if not data:
        return None, []

    try:
        title_obj = data.get("title", {})
        title = title_obj.get("pretty") or title_obj.get("english") or f"Gallery_{gallery_id}"
        sanitized_title = re.sub(r'[\\/*?:"<>|]', '_', title).strip()

        media_id = data.get("media_id")
        pages = data.get("pages", [])
        if not media_id or not pages:
            return None, []

        # Extension map from nhentai format letters
        ext_map = {"j": "jpg", "p": "png", "w": "webp", "g": "gif"}
        
        file_list = []
        for idx, page_info in enumerate(pages, 1):
            t = page_info.get("t", "j")
            ext = ext_map.get(t, "jpg")
            page_url = f"https://i.nhentai.net/galleries/{media_id}/{idx}.{ext}"
            file_list.append({
                "url": page_url,
                "filename": f"{idx:03d}.{ext}",
                "headers": {"Referer": f"https://nhentai.net/g/{gallery_id}/"}
            })

        folder_name = f"[{gallery_id}] {sanitized_title}"
        return folder_name, file_list
    except Exception:
        return None, []
