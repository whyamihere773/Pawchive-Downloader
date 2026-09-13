import re
import html
import urllib.parse
from typing import Tuple, List, Dict, Any, Optional
import time
from concurrent.futures import ThreadPoolExecutor
import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Origin": "https://bunkr.cr",
    "Referer": "https://bunkr.cr/",
}

from core.text_utils import clean_text, sanitize_filesystem_name

SIGN_ENDPOINT_DEFAULT = "https://glb-apisign.cdn.cr/sign"
METADATA_ENDPOINT_DEFAULT = "https://dl.bunkr.cr/api/_001_v2"


def _sanitize_name(name: str) -> str:
    """Removes invalid filename characters, repairs mojibake, strips invisible characters and trims."""
    return sanitize_filesystem_name(name, fallback="bunkr_file")


def _get_response_text(resp) -> str:
    """Safely extracts UTF-8 text from response, handling both live requests (bytes) and test mocks."""
    if resp is None:
        return ""
    try:
        raw = getattr(resp, "content", None)
        if isinstance(raw, (bytes, bytearray)):
            return raw.decode("utf-8", errors="replace")
    except Exception:
        pass
    text = getattr(resp, "text", "")
    return str(text) if text is not None else ""


def sign_bunkr_path(
    path: str,
    sign_url: str = SIGN_ENDPOINT_DEFAULT,
    session: Optional[requests.Session] = None,
    headers: Optional[dict] = None,
    timeout: int = 15
) -> Optional[Dict[str, Any]]:
    """
    Calls the Bunkr token signing microservice for a given storage path.
    Returns: {"token": "...", "ex": ...} or None.
    """
    s = session or requests.Session()
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)

    encoded_path = urllib.parse.quote(path)
    url = f"{sign_url}?path={encoded_path}"

    for attempt in range(3):
        try:
            resp = s.get(url, headers=req_headers, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(1.0 * (attempt + 1))
                continue
            if resp.status_code == 200:
                data = resp.json()
                if "token" in data and "ex" in data:
                    return data
        except Exception:
            time.sleep(0.8 * (attempt + 1))

    return None


def fetch_bunkr_file_by_id(
    file_id: str,
    original_name: Optional[str] = None,
    session: Optional[requests.Session] = None,
    headers: Optional[dict] = None,
    timeout: int = 20
) -> Optional[Dict[str, Any]]:
    """
    Resolves file metadata via Bunkr's metadata API (/api/_001_v2) and signs the storage path.
    Returns a file dictionary: {"url": ..., "filename": ..., "size": ..., "headers": ...}
    """
    s = session or requests.Session()
    req_headers = dict(DEFAULT_HEADERS)
    req_headers.update({
        "Content-Type": "application/json",
        "Origin": "https://dl.bunkr.cr",
        "Referer": f"https://dl.bunkr.cr/file/{file_id}"
    })
    if headers:
        req_headers.update(headers)

    meta_data = None
    for attempt in range(3):
        try:
            resp = s.post(
                METADATA_ENDPOINT_DEFAULT,
                headers=req_headers,
                json={"id": str(file_id)},
                timeout=timeout
            )
            if resp.status_code == 429:
                time.sleep(1.2 * (attempt + 1))
                continue
            if resp.status_code == 200:
                meta_data = resp.json()
                break
        except Exception:
            time.sleep(0.8 * (attempt + 1))

    if not meta_data or not isinstance(meta_data, dict):
        return None

    mediafiles = meta_data.get("mediafiles")
    path = meta_data.get("path")
    fname = meta_data.get("original") or original_name or "video.mp4"
    fname = _sanitize_name(fname)

    if not mediafiles or not path:
        return None

    sig = sign_bunkr_path(path, session=s, headers=headers, timeout=timeout)
    if not sig:
        return None

    token = sig.get("token")
    ex = sig.get("ex")
    raw_url = f"{mediafiles}{path}"
    dl_url = f"{raw_url}?n={urllib.parse.quote(fname)}&token={token}&ex={ex}"

    return {
        "url": dl_url,
        "filename": fname,
        "size": 0,
        "headers": {"Referer": "https://bunkr.cr/"}
    }


def resolve_bunkr_file_page(
    page_url: str,
    session: Optional[requests.Session] = None,
    headers: Optional[dict] = None,
    timeout: int = 20
) -> Optional[Dict[str, Any]]:
    """
    Resolves a single file page (e.g. https://bunkr.cr/f/<slug>).
    Extracts filename, jsCDN, signUrl, or dl link, and mints a signed download URL.
    """
    s = session or requests.Session()
    req_headers = dict(DEFAULT_HEADERS)
    req_headers["Referer"] = page_url
    if headers:
        req_headers.update(headers)

    content = None
    for attempt in range(3):
        try:
            resp = s.get(page_url, headers=req_headers, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(1.2 * (attempt + 1))
                continue
            resp.raise_for_status()
            content = _get_response_text(resp)
            break
        except Exception:
            time.sleep(0.8 * (attempt + 1))

    if not content:
        return None

    # 1. Extract filename
    title_m = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
    og_m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', content, re.IGNORECASE)
    ogname_m = re.search(r'var\s+ogname\s*=\s*["\'](.*?)["\']', content)

    raw_name = ""
    if ogname_m:
        raw_name = ogname_m.group(1)
    elif og_m:
        raw_name = og_m.group(1)
    elif title_m:
        raw_name = title_m.group(1).split("|")[0].strip()

    fname = _sanitize_name(raw_name or "video.mp4")

    # 2. Check for jsCDN & signUrl in script
    cdn_m = re.search(r'var\s+jsCDN\s*=\s*["\']([^"\']+)["\']', content)
    sign_m = re.search(r'var\s+signUrl\s*=\s*["\']([^"\']+)["\']', content)
    sign_service_m = re.search(r'SIGN_SERVICE_URL\s*=\s*["\']([^"\']+)["\']', content)

    if cdn_m:
        raw_cdn = cdn_m.group(1).replace(r'\/', '/')
        sign_url = sign_m.group(1) if sign_m else (sign_service_m.group(1) if sign_service_m else SIGN_ENDPOINT_DEFAULT)
        parsed_path = urllib.parse.urlparse(raw_cdn).path
        sig = sign_bunkr_path(parsed_path, sign_url=sign_url, session=s, headers=headers, timeout=timeout)
        if sig:
            dl_url = f"{raw_cdn}?n={urllib.parse.quote(fname)}&token={sig['token']}&ex={sig['ex']}"
            return {
                "url": dl_url,
                "filename": fname,
                "size": 0,
                "headers": {"Referer": "https://bunkr.cr/"}
            }

    # 3. Check for dl.bunkr.cr/file/<id> or download button data-id
    dl_btn_m = re.search(r'id=["\']download-btn["\'][^>]*data-id=["\'](\d+)["\']', content)
    dl_link_m = re.search(r'href=["\']https?://(?:[a-zA-Z0-9_-]+\.)?bunkr\.[a-z0-9]+/file/(\d+)["\']', content)
    f_id = dl_btn_m.group(1) if dl_btn_m else (dl_link_m.group(1) if dl_link_m else None)

    if f_id:
        file_res = fetch_bunkr_file_by_id(f_id, original_name=fname, session=s, headers=headers, timeout=timeout)
        if file_res:
            return file_res

    # 4. Fallback: check for direct media links in tags
    media_m = re.search(r'(?:src|href)=["\'](https?://[^"\']+\.(?:mp4|mkv|webm|mov|avi|zip|rar|7z|jpg|png|jpeg|webp))["\']', content, re.IGNORECASE)
    if media_m:
        direct_url = media_m.group(1)
        return {
            "url": direct_url,
            "filename": fname,
            "size": 0,
            "headers": {"Referer": page_url}
        }

    return None


def fetch_bunkr_album(
    url: str,
    headers: Optional[dict] = None,
    timeout: int = 25,
    resolve_files: bool = True
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Parses a Bunkr album, folder, or file URL and extracts direct media links.
    Supports modern 2026 Bunkr domains (bunkr.cr, bunkr.si, bunkr.pk, balbums.st, etc.)
    and handles:
      - Albums/folders: https://bunkr.cr/a/<album_id> or https://balbums.st/a/<album_id>
      - File pages: https://bunkr.cr/f/<slug> (or /v/, /d/, /i/)
      - Direct download links: https://dl.bunkr.cr/file/<file_id>
      - Pre-signed CDN URLs: https://...cdn.cr/storage/media/...

    Returns: (album_or_file_title, list_of_file_dicts)
    """
    session = requests.Session()
    clean_url = url.strip()

    # ── 1. Direct CDN link with token ──────────────────────────────────────────
    if ("cdn.cr" in clean_url or "scdn.st" in clean_url) and "/storage/media/" in clean_url:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(clean_url).query)
        fname = qs.get("n", [""])[0] or clean_url.split("?")[0].split("/")[-1]
        fname = _sanitize_name(urllib.parse.unquote(fname))
        return fname, [{
            "url": clean_url,
            "filename": fname,
            "size": 0,
            "headers": {"Referer": "https://bunkr.cr/"}
        }]

    # ── 2. Direct Download Link (e.g. dl.bunkr.cr/file/<id>) ─────────────────
    file_id_match = re.search(r'/(?:file)/(\d+)', clean_url)
    if file_id_match:
        file_id = file_id_match.group(1)
        res = fetch_bunkr_file_by_id(file_id, session=session, headers=headers, timeout=timeout)
        if res:
            return res["filename"], [res]

    # ── 3. Single File Page (e.g. bunkr.cr/f/<slug> or /v/<slug>) ────────────
    single_file_match = re.search(r'/(?:f|v|d|i)/([a-zA-Z0-9_-]+)', clean_url)
    is_album = "/a/" in clean_url
    if single_file_match and not is_album:
        res = resolve_bunkr_file_page(clean_url, session=session, headers=headers, timeout=timeout)
        if res:
            return res["filename"], [res]

    # ── 4. Album / Folder Processing (/a/<album_id>) ──────────────────────────
    # Normalize balbums.st domain to bunkr.cr
    fetch_url = clean_url
    if "balbums.st" in fetch_url:
        album_id_m = re.search(r'/a/([a-zA-Z0-9_-]+)', fetch_url)
        if album_id_m:
            fetch_url = f"https://bunkr.cr/a/{album_id_m.group(1)}"

    # Append advanced=1 to trigger Bunkr's structured albumFiles catalog
    parsed_u = urllib.parse.urlparse(fetch_url)
    q = urllib.parse.parse_qs(parsed_u.query)
    q["advanced"] = ["1"]
    advanced_url = urllib.parse.urlunparse(parsed_u._replace(query=urllib.parse.urlencode(q, doseq=True)))

    req_headers = dict(DEFAULT_HEADERS)
    req_headers["Referer"] = fetch_url
    if headers:
        req_headers.update(headers)

    content = None
    for attempt in range(3):
        try:
            resp = session.get(advanced_url, headers=req_headers, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            resp.raise_for_status()
            content = _get_response_text(resp)
            break
        except Exception:
            if attempt == 2:
                # If advanced=1 failed, fallback to standard URL
                try:
                    fallback_resp = session.get(fetch_url, headers=req_headers, timeout=timeout)
                    if fallback_resp.status_code == 200:
                        content = _get_response_text(fallback_resp)
                except Exception:
                    pass
            time.sleep(1.0 * (attempt + 1))

    if not content:
        return None, []

    # Extract album title
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
    raw_title = title_match.group(1).split("|")[0].strip() if title_match else "Bunkr Album"
    title = clean_text(raw_title) or "Bunkr Album"

    # If only title resolution was requested, return early
    if not resolve_files:
        return title, []

    # ── Check for direct legacy media URLs (backwards-compatibility) ──────────
    legacy_media_urls = set()
    for m in re.finditer(r'href=["\']((?:https?://[^"\']+|/(?:v|d|i)/[^"\']+))["\']', content):
        raw_link = m.group(1)
        if not raw_link.startswith("http"):
            raw_link = urllib.parse.urljoin(fetch_url, raw_link)
        if any(ext in raw_link.lower() for ext in ['.mp4', '.mkv', '.webm', '.jpg', '.png', '.jpeg', '.zip', '.rar', '.7z']):
            legacy_media_urls.add(raw_link)

    # ── 4A. Parse window.albumFiles structured array ─────────────────────────
    catalog_entries = []
    album_files_match = re.search(r'window\.albumFiles\s*=\s*\[(.*?)\];', content, re.DOTALL)
    if album_files_match:
        obj_matches = re.findall(r'\{([^}]+)\}', album_files_match.group(1), re.DOTALL)
        for obj_str in obj_matches:
            id_m = re.search(r'id:\s*(\d+)', obj_str)
            orig_m = re.search(r'original:\s*["\']([^"\']+)["\']', obj_str)
            name_m = re.search(r'name:\s*["\']([^"\']+)["\']', obj_str)
            slug_m = re.search(r'slug:\s*["\']([^"\']+)["\']', obj_str)
            size_m = re.search(r'size:\s*(\d+)', obj_str)

            file_id = id_m.group(1) if id_m else None
            original = orig_m.group(1) if orig_m else (name_m.group(1) if name_m else None)
            slug = slug_m.group(1) if slug_m else None
            size_bytes = int(size_m.group(1)) if size_m else 0

            if file_id or slug:
                catalog_entries.append({
                    "id": file_id,
                    "original": original,
                    "slug": slug,
                    "size": size_bytes
                })

    # ── 4B. Fallback: Parse HTML cards (.theItem) or links ───────────────────
    if not catalog_entries and not legacy_media_urls:
        card_matches = re.findall(r'<div[^>]*class=["\'][^"\']*theItem[^"\']*["\'][^>]*>(.*?)</div>\s*</div>', content, re.DOTALL)
        for card in card_matches:
            link_m = re.search(r'href=["\'](/f/[a-zA-Z0-9_-]+)["\']', card)
            title_attr_m = re.search(r'title=["\']([^"\']+)["\']', card)
            name_p_m = re.search(r'class=["\'][^"\']*theName[^"\']*["\'][^>]*>([^<]+)</p>', card)
            orig_name = name_p_m.group(1).strip() if name_p_m else (title_attr_m.group(1).strip() if title_attr_m else None)
            if link_m:
                slug = link_m.group(1).split("/")[-1]
                catalog_entries.append({
                    "id": None,
                    "original": orig_name,
                    "slug": slug,
                    "size": 0
                })

        if not catalog_entries:
            for l in re.findall(r'href=["\']((?:https?://[^"\']+|/)(?:f|v)/[a-zA-Z0-9_-]+)["\']', content):
                slug = l.rstrip("/").split("/")[-1]
                catalog_entries.append({
                    "id": None,
                    "original": None,
                    "slug": slug,
                    "size": 0
                })

    # ── 4C. Resolve entries concurrently ─────────────────────────────────────
    resolved_files = []

    def _resolve_entry(entry: dict) -> Optional[Dict[str, Any]]:
        # If numeric ID is present, try fast metadata endpoint
        f_id = entry.get("id")
        orig = entry.get("original")
        size = entry.get("size", 0)
        slug = entry.get("slug")

        if f_id:
            res = fetch_bunkr_file_by_id(f_id, original_name=orig, session=session, headers=headers, timeout=timeout)
            if res:
                if size:
                    res["size"] = size
                return res

        # Fallback to resolving via file page
        if slug:
            page_u = f"https://bunkr.cr/f/{slug}"
            res = resolve_bunkr_file_page(page_u, session=session, headers=headers, timeout=timeout)
            if res:
                if orig and not res.get("filename"):
                    res["filename"] = _sanitize_name(orig)
                if size:
                    res["size"] = size
                return res

        return None

    if catalog_entries:
        max_workers = min(6, len(catalog_entries))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            resolved_files = [r for r in executor.map(_resolve_entry, catalog_entries) if r]

    # If catalog resolution produced results, return them
    if resolved_files:
        return title, resolved_files

    # ── 4D. If only legacy links were found (e.g. in unit tests or older pages)
    if legacy_media_urls:
        legacy_list = []
        for idx, media_url in enumerate(sorted(list(legacy_media_urls)), 1):
            fname = media_url.split("?")[0].split("/")[-1]
            if not fname:
                fname = f"bunkr_file_{idx:03d}"
            legacy_list.append({
                "url": media_url,
                "filename": fname,
                "size": 0,
                "headers": {"Referer": fetch_url}
            })
        return title, legacy_list

    return title, []
