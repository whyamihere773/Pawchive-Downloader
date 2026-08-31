"""
Cloud Storage Downloader Subsystem
Provides hardware-accelerated AES-CTR decryption, parallel folder traversal,
and multi-threaded streaming for Mega.nz, Google Drive, Dropbox, and GoFile.
"""

import os
import re
import json
import base64
import time
import zipfile
import struct
import hashlib
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urlparse, parse_qs
from threading import Lock, Event
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

try:
    from Crypto.Cipher import AES
    PYCRYPTODOME_AVAILABLE = True
except ImportError:
    PYCRYPTODOME_AVAILABLE = False

try:
    import gdown
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False

from core.logger import logger

MEGA_API_URL = "https://g.api.mega.co.nz"


def _urlb64_to_b64(s: str) -> str:
    s += '=' * (-len(s) % 4)
    return s.replace('-', '+').replace('_', '/')


def _b64_to_bytes(s: str) -> bytes:
    return base64.b64decode(_urlb64_to_b64(s))


def _decrypt_mega_attribute(encrypted_attr_b64: str, key_bytes: bytes) -> Dict[str, Any]:
    if not PYCRYPTODOME_AVAILABLE:
        return {}
    try:
        attr_bytes = _b64_to_bytes(encrypted_attr_b64)
        padded_len = (len(attr_bytes) + 15) & ~15
        padded_attr_bytes = attr_bytes.ljust(padded_len, b'\0')
        iv = b'\0' * 16
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
        decrypted_attr = cipher.decrypt(padded_attr_bytes)
        json_str = decrypted_attr.strip(b'\0').decode('utf-8')
        if json_str.startswith('MEGA'):
            return json.loads(json_str[4:])
        return json.loads(json_str)
    except Exception:
        return {}


def _decrypt_mega_key(encrypted_key_b64: str, master_key_bytes: bytes) -> bytes:
    if not PYCRYPTODOME_AVAILABLE:
        raise RuntimeError("pycryptodome is required for Mega download")
    key_bytes = _b64_to_bytes(encrypted_key_b64)
    cipher = AES.new(master_key_bytes, AES.MODE_ECB)
    return cipher.decrypt(key_bytes)


def _parse_mega_key(key_b64: str):
    key_bytes = _b64_to_bytes(key_b64)
    key_parts = struct.unpack('>' + 'I' * (len(key_bytes) // 4), key_bytes)
    if len(key_parts) == 8:
        final_key = (
            key_parts[0] ^ key_parts[4],
            key_parts[1] ^ key_parts[5],
            key_parts[2] ^ key_parts[6],
            key_parts[3] ^ key_parts[7]
        )
        iv = (key_parts[4], key_parts[5], 0, 0)
        key_bytes = struct.pack('>' + 'I' * 4, *final_key)
        iv_bytes = struct.pack('>' + 'I' * 4, *iv)
        return key_bytes, iv_bytes, None
    elif len(key_parts) == 4:
        return key_bytes, None, None
    raise ValueError("Invalid Mega key length")


def _process_file_key(file_key_bytes: bytes) -> bytes:
    key_parts = struct.unpack('>' + 'I' * 8, file_key_bytes)
    final_key_parts = (
        key_parts[0] ^ key_parts[4],
        key_parts[1] ^ key_parts[5],
        key_parts[2] ^ key_parts[6],
        key_parts[3] ^ key_parts[7]
    )
    return struct.pack('>' + 'I' * 4, *final_key_parts)


def _process_mega_folder(folder_id: str, folder_key: str, session: requests.Session, log_func: Callable[[str], None]):
    master_key_bytes, _, _ = _parse_mega_key(folder_key)
    params = {'n': folder_id}
    payload = [{"a": "f", "c": 1, "r": 1}]

    response = session.post(f"{MEGA_API_URL}/cs", params=params, json=payload, timeout=25)
    response.raise_for_status()
    res_json = response.json()

    if isinstance(res_json, int) or (isinstance(res_json, list) and res_json and isinstance(res_json[0], int)):
        error_code = res_json if isinstance(res_json, int) else res_json[0]
        log_func(f"❌ Mega API returned error code {error_code}")
        return None, None

    if not isinstance(res_json, list) or not res_json or 'f' not in res_json[0]:
        log_func("❌ Invalid Mega folder response format")
        return None, None

    nodes = res_json[0]['f']
    decrypted_nodes = {}

    for node in nodes:
        try:
            k_str = node.get('k')
            if not k_str:
                continue
            encrypted_key_b64 = k_str.split(':')[-1]
            decrypted_key_raw = _decrypt_mega_key(encrypted_key_b64, master_key_bytes)
            attr_key = _process_file_key(decrypted_key_raw) if node.get('t') == 0 else decrypted_key_raw
            attrs = _decrypt_mega_attribute(node.get('a', ''), attr_key)
            name = re.sub(r'[<>:"/\\|?*]', '_', attrs.get('n', f"node_{node['h']}"))
            raw_key_b64 = base64.b64encode(decrypted_key_raw).decode('utf-8')
            decrypted_nodes[node['h']] = {
                "name": name,
                "parent": node.get('p'),
                "type": node.get('t'),
                "size": node.get('s', 0),
                "key": raw_key_b64
            }
        except Exception:
            continue

    root_name = decrypted_nodes.get(folder_id, {}).get("name", f"mega_folder_{folder_id}")
    files_to_download = []

    for handle, node_info in decrypted_nodes.items():
        if node_info.get("type") == 0:
            path_parts = [node_info['name']]
            current_parent_id = node_info.get('parent')
            while current_parent_id in decrypted_nodes:
                parent_node = decrypted_nodes[current_parent_id]
                if current_parent_id == folder_id:
                    break
                path_parts.insert(0, parent_node['name'])
                current_parent_id = parent_node.get('parent')

            files_to_download.append({
                'h': handle,
                's': node_info['size'],
                'key': node_info['key'],
                'relative_path': os.path.join(*path_parts) if path_parts else node_info['name']
            })

    return root_name, files_to_download


def download_and_decrypt_mega_file(
    info: Dict[str, Any],
    download_dir: str,
    log_func: Callable[[str], None],
    progress_callback: Optional[Callable[[str, int, int, int, int], None]] = None,
    cancel_event: Optional[Event] = None,
    pause_event: Optional[Event] = None,
    file_index: int = 1,
    total_files: int = 1
):
    file_name = info['file_name']
    file_size = info.get('file_size', 0)
    dl_url = info['dl_url']
    final_path = os.path.join(download_dir, file_name)
    tmp_path = final_path + ".part"

    os.makedirs(download_dir, exist_ok=True)

    if os.path.exists(final_path) and os.path.getsize(final_path) == file_size and file_size > 0:
        log_func(f"   [Mega] ℹ️ File '{file_name}' already exists. Skipping.")
        if progress_callback:
            progress_callback(file_name, file_size, file_size, file_index, total_files)
        return

    key, iv, _ = _parse_mega_key(_urlb64_to_b64(info['file_key']))
    if iv is None:
        iv = b'\0' * 16
    nonce = iv[:8]
    initial_bytes = 0

    if os.path.exists(tmp_path):
        initial_bytes = os.path.getsize(tmp_path)

    headers = {}
    if initial_bytes > 0:
        headers['Range'] = f"bytes={initial_bytes}-"
        log_func(f"   [Mega] Resuming '{file_name}' from {initial_bytes // 1024 // 1024} MB...")
    else:
        log_func(f"   [Mega] 🔽 Downloading '{file_name}' ({file_size // 1024 // 1024} MB)...")

    counter = initial_bytes // 16
    cipher = AES.new(key, AES.MODE_CTR, nonce=nonce, initial_value=counter)

    downloaded = initial_bytes
    last_log_time = time.time()

    with requests.get(dl_url, headers=headers, stream=True, timeout=(15, 300)) as r:
        r.raise_for_status()
        mode = 'ab' if initial_bytes > 0 else 'wb'
        with open(tmp_path, mode) as f:
            for chunk in r.iter_content(chunk_size=16384):
                if cancel_event and cancel_event.is_set():
                    log_func(f"   [Mega] Download cancelled for '{file_name}'.")
                    return
                while pause_event and pause_event.is_set():
                    time.sleep(0.5)
                    if cancel_event and cancel_event.is_set():
                        return

                decrypted = cipher.decrypt(chunk)
                f.write(decrypted)
                downloaded += len(chunk)

                now = time.time()
                if now - last_log_time >= 1.0:
                    if progress_callback:
                        progress_callback(file_name, downloaded, file_size, file_index, total_files)
                    last_log_time = now

    if os.path.exists(tmp_path):
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(tmp_path, final_path)
        log_func(f"   [Mega] ✅ Completed: '{file_name}'")
        if progress_callback:
            progress_callback(file_name, file_size, file_size, file_index, total_files)


def download_mega_link(
    url: str,
    target_folder: str,
    log_func: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[str, int, int, int, int], None]] = None,
    cancel_event: Optional[Event] = None,
    pause_event: Optional[Event] = None,
    max_workers: int = 6
):
    if not PYCRYPTODOME_AVAILABLE:
        log_func("❌ Mega download failed: 'pycryptodome' library is not available.")
        return False

    session = requests.Session()
    session.headers.update({'User-Agent': 'Kemono-Downloader/1.0'})

    folder_match = re.search(r'mega(?:\.co)?\.nz/folder/([a-zA-Z0-9]+)#([a-zA-Z0-9_.-]+)', url)
    file_match = re.search(r'mega(?:\.co)?\.nz/(?:file/|#!)?([a-zA-Z0-9]+)(?:#|!)([a-zA-Z0-9_.-]+)', url)

    if folder_match:
        folder_id, folder_key = folder_match.groups()
        log_func(f"   [Mega] Folder detected ({folder_id}). Crawling structure...")
        root_name, files = _process_mega_folder(folder_id, folder_key, session, log_func)
        if not files:
            log_func(f"   [Mega] No files found in folder {folder_id}.")
            return False

        workers = max(1, min(max_workers, 16))
        log_func(f"   [Mega] Found {len(files)} file(s) in folder '{root_name}'. Starting parallel downloads ({workers} threads)...")
        folder_path = os.path.join(target_folder, root_name)
        os.makedirs(folder_path, exist_ok=True)

        progress_lock = Lock()
        processed_count = 0
        total_files = len(files)

        def _mega_worker(file_data):
            nonlocal processed_count
            if cancel_event and cancel_event.is_set():
                return
            try:
                params = {'n': folder_id}
                payload = [{"a": "g", "g": 1, "n": file_data['h']}]
                resp = session.post(f"{MEGA_API_URL}/cs", params=params, json=payload, timeout=20)
                resp.raise_for_status()
                res_json = resp.json()

                if isinstance(res_json, int) or (isinstance(res_json, list) and res_json and isinstance(res_json[0], int)):
                    log_func(f"   [Mega Worker] ⚠️ Skipping file '{file_data['relative_path']}' (API error)")
                    return

                dl_temp_url = res_json[0]['g']
                file_info = {
                    'file_name': os.path.basename(file_data['relative_path']),
                    'file_size': file_data['s'],
                    'dl_url': dl_temp_url,
                    'file_key': file_data['key']
                }
                sub_dir = os.path.dirname(file_data['relative_path'])
                save_dir = os.path.join(folder_path, sub_dir) if sub_dir else folder_path

                download_and_decrypt_mega_file(
                    file_info,
                    save_dir,
                    log_func,
                    progress_callback,
                    cancel_event,
                    pause_event,
                    file_index=processed_count + 1,
                    total_files=total_files
                )
            except Exception as e:
                if not (cancel_event and cancel_event.is_set()):
                    log_func(f"   [Mega Worker] ❌ Error on '{file_data['relative_path']}': {e}")
            finally:
                with progress_lock:
                    processed_count += 1

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_mega_worker, f) for f in files]
            for future in as_completed(futures):
                if cancel_event and cancel_event.is_set():
                    for f in futures:
                        f.cancel()
                    break
                try:
                    future.result()
                except Exception:
                    pass
        return True

    elif file_match:
        file_id, file_key = file_match.groups()
        payload = [{"a": "g", "g": 1, "p": file_id}]
        resp = session.post(f"{MEGA_API_URL}/cs", json=payload, timeout=20)
        resp.raise_for_status()
        res_json = resp.json()

        if isinstance(res_json, int) or (isinstance(res_json, list) and res_json and isinstance(res_json[0], int)):
            log_func(f"❌ Mega API returned error code for file {file_id}")
            return False

        data = res_json[0]
        dl_url = data['g']
        file_size = data.get('s', 0)
        attrs_key, _, _ = _parse_mega_key(_urlb64_to_b64(file_key))
        file_attrs = _decrypt_mega_attribute(data['at'], attrs_key)
        file_name = file_attrs.get('n', f"mega_{file_id}.bin")

        file_info = {
            'file_name': file_name,
            'file_size': file_size,
            'dl_url': dl_url,
            'file_key': file_key
        }
        download_and_decrypt_mega_file(
            file_info,
            target_folder,
            log_func,
            progress_callback,
            cancel_event,
            pause_event,
            file_index=1,
            total_files=1
        )
        return True

    log_func(f"⚠️ Unrecognized Mega URL format: {url}")
    return False


def download_gdrive_link(
    url: str,
    target_folder: str,
    log_func: Callable[[str], None] = print,
    cancel_event: Optional[Event] = None
) -> bool:
    if not GDRIVE_AVAILABLE:
        log_func("❌ Google Drive download failed: 'gdown' is not installed.")
        return False

    os.makedirs(target_folder, exist_ok=True)
    log_func(f"   [Google Drive] Initializing download for: {url}")

    try:
        if "drive/folders/" in url or "open?id=" in url and "folders" in url:
            gdown.download_folder(url=url, output=target_folder, quiet=False, use_cookies=False)
        else:
            gdown.download(url=url, output=target_folder, quiet=False, fuzzy=True)
        log_func(f"   [Google Drive] ✅ Download complete to: {target_folder}")
        return True
    except Exception as e:
        log_func(f"   [Google Drive] ❌ Download error: {e}")
        return False


def download_dropbox_link(
    url: str,
    target_folder: str,
    log_func: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    cancel_event: Optional[Event] = None,
    pause_event: Optional[Event] = None
) -> bool:
    os.makedirs(target_folder, exist_ok=True)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    qs['dl'] = ['1']
    from urllib.parse import urlunparse, urlencode
    direct_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(qs, doseq=True), parsed.fragment))

    log_func(f"   [Dropbox] Connecting to direct stream: {direct_url}")
    try:
        with requests.get(direct_url, stream=True, allow_redirects=True, timeout=(20, 600)) as r:
            r.raise_for_status()
            cd = r.headers.get('content-disposition', '')
            fname_match = re.findall(r'filename="?([^"]+)"?', cd)
            filename = fname_match[0].strip() if fname_match else os.path.basename(parsed.path) or "dropbox_download"
            if not os.path.splitext(filename)[1]:
                filename += ".zip"

            full_path = os.path.join(target_folder, filename)
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0
            last_log = time.time()

            with open(full_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=16384):
                    if cancel_event and cancel_event.is_set():
                        log_func("   [Dropbox] Download cancelled.")
                        return False
                    while pause_event and pause_event.is_set():
                        time.sleep(0.5)
                        if cancel_event and cancel_event.is_set():
                            return False

                    f.write(chunk)
                    downloaded += len(chunk)
                    if time.time() - last_log >= 1.0:
                        if progress_callback:
                            progress_callback(filename, downloaded, total_size, 1, 1)
                        last_log = time.time()

            log_func(f"   [Dropbox] ✅ Downloaded '{filename}'")

            if zipfile.is_zipfile(full_path):
                log_func(f"   [Dropbox] 📦 Extracting zip archive: '{filename}'...")
                extract_dir = os.path.join(target_folder, os.path.splitext(filename)[0])
                os.makedirs(extract_dir, exist_ok=True)
                with zipfile.ZipFile(full_path, 'r') as z:
                    z.extractall(extract_dir)
                log_func(f"   [Dropbox] ✅ Extracted to '{extract_dir}'")
                try:
                    os.remove(full_path)
                except Exception:
                    pass
        return True
    except Exception as e:
        log_func(f"   [Dropbox] ❌ Download error: {e}")
        return False


def download_gofile_link(
    url: str,
    target_folder: str,
    log_func: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[str, int, int, int, int], None]] = None,
    cancel_event: Optional[Event] = None,
    pause_event: Optional[Event] = None,
    max_workers: int = 6
) -> bool:
    match = re.search(r"gofile\.io/d/([^/?#]+)", url)
    if not match:
        log_func(f"   [GoFile] ❌ Invalid GoFile URL format: {url}")
        return False

    content_id = match.group(1)
    session = requests.Session()
    session.headers.update({
        "Accept-Encoding": "gzip",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    })

    try:
        log_func("   [GoFile] Requesting guest token...")
        resp = session.post("https://api.gofile.io/accounts", timeout=20)
        resp.raise_for_status()
        token_data = resp.json()
        if token_data.get("status") != "ok":
            log_func("   [GoFile] ❌ Failed to get guest token.")
            return False

        token = token_data["data"]["token"]
        session.headers.update({"Authorization": f"Bearer {token}"})

        user_agent = session.headers.get('User-Agent', 'Mozilla/5.0')
        lang = "en-US"
        raw_sig = f"{user_agent}::{lang}::{token}::{int(time.time() / 14400)}::5d4f7g8sd45fsd"
        wt_token = hashlib.sha256(raw_sig.encode()).hexdigest()

        api_url = f"https://api.gofile.io/contents/{content_id}?cache=true&sortField=createTime&sortDirection=1"
        res = session.get(api_url, headers={"X-Website-Token": wt_token, "X-BL": lang}, timeout=30)
        res.raise_for_status()
        data = res.json()

        if data.get("status") != "ok":
            log_func(f"   [GoFile] ❌ API error: {data.get('status')}")
            return False

        folder_info = data["data"]
        files = [c for c in folder_info.get("children", {}).values() if c.get("type") == "file"]

        if not files:
            log_func("   [GoFile] ℹ️ No files in folder.")
            return False

        workers = max(1, min(max_workers, 16))
        folder_name = folder_info.get("name", f"gofile_{content_id}")
        save_path = os.path.join(target_folder, folder_name)
        os.makedirs(save_path, exist_ok=True)

        log_func(f"   [GoFile] Found {len(files)} file(s). Starting parallel downloads ({workers} threads)...")

        progress_lock = Lock()
        processed_count = 0
        total_files = len(files)

        def _gofile_worker(fobj):
            nonlocal processed_count
            if cancel_event and cancel_event.is_set():
                return

            fname = fobj["name"]
            furl = fobj["link"]
            fsize = fobj.get("size", 0)
            fpath = os.path.join(save_path, fname)

            log_func(f"   [GoFile] 🔽 '{fname}'")

            try:
                with session.get(furl, stream=True, timeout=(30, 600)) as r:
                    r.raise_for_status()
                    downloaded = 0
                    last_t = time.time()
                    with open(fpath, "wb") as f:
                        for chunk in r.iter_content(chunk_size=16384):
                            if cancel_event and cancel_event.is_set():
                                return
                            while pause_event and pause_event.is_set():
                                time.sleep(0.5)
                                if cancel_event and cancel_event.is_set():
                                    return

                            f.write(chunk)
                            downloaded += len(chunk)
                            if time.time() - last_t >= 1.0:
                                if progress_callback:
                                    progress_callback(fname, downloaded, fsize, processed_count + 1, total_files)
                                last_t = time.time()

                log_func(f"   [GoFile] ✅ Finished '{fname}'")
                if progress_callback:
                    progress_callback(fname, fsize, fsize, processed_count + 1, total_files)
            except Exception as e:
                if not (cancel_event and cancel_event.is_set()):
                    log_func(f"   [GoFile] ❌ Error on '{fname}': {e}")
            finally:
                with progress_lock:
                    processed_count += 1

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_gofile_worker, f) for f in files]
            for future in as_completed(futures):
                if cancel_event and cancel_event.is_set():
                    for f in futures:
                        f.cancel()
                    break
                try:
                    future.result()
                except Exception:
                    pass
        return True
    except Exception as e:
        log_func(f"   [GoFile] ❌ GoFile error: {e}")
        return False
