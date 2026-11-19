"""
Mega.nz Cloud Storage Provider
Provides AES-CTR streaming decryption and parallel folder traversal for Mega links.
"""

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import struct
import sys
from threading import Event, Lock
import time
from typing import Any, Callable, Dict, List, Optional, Union

import requests

from core.bandwidth_limiter import bandwidth_limiter
from services.cloud_providers.base import (
    CloudProvider,
    _active_cloud_lock,
    _active_cloud_resps,
    _inside,
    _safe_name,
    should_skip_cloud_file,
)

try:
    from Crypto.Cipher import AES
    PYCRYPTODOME_AVAILABLE = True
except ImportError:
    AES = None
    PYCRYPTODOME_AVAILABLE = False

MEGA_API_URL = "https://g.api.mega.co.nz"


def _urlb64_to_b64(s: str) -> str:
    s += '=' * (-len(s) % 4)
    return s.replace('-', '+').replace('_', '/')


def _b64_to_bytes(s: str) -> bytes:
    return base64.b64decode(_urlb64_to_b64(s))


def _decrypt_mega_attribute(encrypted_attr_b64: str, key_bytes: bytes) -> Dict[str, Any]:
    _facade = sys.modules.get('services.cloud_downloader')
    _crypto_ok = getattr(_facade, 'PYCRYPTODOME_AVAILABLE', PYCRYPTODOME_AVAILABLE) if _facade else PYCRYPTODOME_AVAILABLE
    _req = getattr(_facade, 'requests', requests) if _facade else requests
    _proc_folder = getattr(_facade, '_process_mega_folder', _process_mega_folder) if _facade else _process_mega_folder
    _dl_file = getattr(_facade, 'download_and_decrypt_mega_file', download_and_decrypt_mega_file) if _facade else download_and_decrypt_mega_file
    if not _crypto_ok:
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
    _facade = sys.modules.get('services.cloud_downloader')
    _crypto_ok = getattr(_facade, 'PYCRYPTODOME_AVAILABLE', PYCRYPTODOME_AVAILABLE) if _facade else PYCRYPTODOME_AVAILABLE
    _req = getattr(_facade, 'requests', requests) if _facade else requests
    _proc_folder = getattr(_facade, '_process_mega_folder', _process_mega_folder) if _facade else _process_mega_folder
    _dl_file = getattr(_facade, 'download_and_decrypt_mega_file', download_and_decrypt_mega_file) if _facade else download_and_decrypt_mega_file
    if not _crypto_ok:
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
            name = _safe_name(attrs.get('n'), f"node_{node['h']}")
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
    file_name = _safe_name(file_name, "mega_file")
    final_path = os.path.join(download_dir, file_name)
    tmp_path = final_path + ".part"
    if not _inside(download_dir, final_path):
        log_func(f"   [Mega] ⚠️ Skipping '{file_name}': unsafe file name")
        return False

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
        with _active_cloud_lock:
            _active_cloud_resps.add(r)
        try:
            r.raise_for_status()
            mode = 'ab' if initial_bytes > 0 else 'wb'
            with open(tmp_path, mode) as f:
                for chunk in r.iter_content(chunk_size=16384):
                    if cancel_event and cancel_event.is_set():
                        log_func(f"   [Mega] Download cancelled for '{file_name}'.")
                        if os.path.exists(tmp_path):
                            try:
                                os.remove(tmp_path)
                            except OSError:
                                pass
                        return
                    while pause_event and pause_event.is_set():
                        time.sleep(0.5)
                        if cancel_event and cancel_event.is_set():
                            if os.path.exists(tmp_path):
                                try:
                                    os.remove(tmp_path)
                                except OSError:
                                    pass
                            return

                    if not bandwidth_limiter.wait_for(len(chunk), cancel_event, pause_event):
                        log_func(f"   [Mega] Download cancelled for '{file_name}'.")
                        if os.path.exists(tmp_path):
                            try:
                                os.remove(tmp_path)
                            except OSError:
                                pass
                        return

                    decrypted = cipher.decrypt(chunk)
                    f.write(decrypted)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_log_time >= 1.0:
                        if progress_callback:
                            progress_callback(file_name, downloaded, file_size, file_index, total_files)
                        last_log_time = now
        finally:
            with _active_cloud_lock:
                _active_cloud_resps.discard(r)

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
    max_workers: int = 6,
    skip_words: Optional[Union[str, List[str]]] = None,
    options: Optional[Any] = None
):
    _facade = sys.modules.get('services.cloud_downloader')
    _crypto_ok = getattr(_facade, 'PYCRYPTODOME_AVAILABLE', PYCRYPTODOME_AVAILABLE) if _facade else PYCRYPTODOME_AVAILABLE
    _req = getattr(_facade, 'requests', requests) if _facade else requests
    _proc_folder = getattr(_facade, '_process_mega_folder', _process_mega_folder) if _facade else _process_mega_folder
    _dl_file = getattr(_facade, 'download_and_decrypt_mega_file', download_and_decrypt_mega_file) if _facade else download_and_decrypt_mega_file
    if not _crypto_ok:
        log_func("❌ Mega download failed: 'pycryptodome' library is not available.")
        return False

    session = _req.Session()
    session.headers.update({'User-Agent': 'Kemono-Downloader/1.0'})

    folder_match = re.search(r'mega(?:\.co)?\.nz/folder/([a-zA-Z0-9]+)#([a-zA-Z0-9_.-]+)', url)
    file_match = re.search(r'mega(?:\.co)?\.nz/(?:file/|#!)?([a-zA-Z0-9]+)(?:#|!)([a-zA-Z0-9_.-]+)', url)

    if folder_match:
        folder_id, folder_key = folder_match.groups()
        log_func(f"   [Mega] Folder detected ({folder_id}). Crawling structure...")
        root_name, files = _proc_folder(folder_id, folder_key, session, log_func)
        if not files:
            log_func(f"   [Mega] No files found in folder {folder_id}.")
            return False

        if skip_words or options:
            filtered_files = []
            for f in files:
                rel = f.get('relative_path', '')
                fsize = f.get('s', 0)
                skip, reason = should_skip_cloud_file(rel, skip_words=skip_words, file_size=fsize, options=options)
                if skip:
                    log_func(f"   [Mega] ⏭️ Skipping '{rel}': {reason}")
                else:
                    filtered_files.append(f)
            files = filtered_files
            if not files:
                log_func(f"   [Mega] All files in folder '{root_name}' matched skip filters.")
                return True

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
                if save_dir != folder_path and not _inside(folder_path, save_dir):
                    log_func(f"   [Mega Worker] ⚠️ Skipping '{file_data['relative_path']}': unsafe folder name")
                    return

                _dl_file(
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

        if skip_words or options:
            skip, reason = should_skip_cloud_file(file_name, skip_words=skip_words, file_size=file_size, options=options)
            if skip:
                log_func(f"   [Mega] ⏭️ Skipping '{file_name}': {reason}")
                return True

        file_info = {
            'file_name': file_name,
            'file_size': file_size,
            'dl_url': dl_url,
            'file_key': file_key
        }
        _dl_file(
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


class MegaCloudProvider(CloudProvider):
    """Plug-and-play provider for Mega.nz file and folder links."""

    name = "mega"

    def can_handle(self, url: str) -> bool:
        return bool(re.search(r"mega(?:\.co)?\.nz/", url or "", re.IGNORECASE))

    def download(
        self,
        url: str,
        target_folder: str,
        log_func: Callable[[str], None] = print,
        progress_callback: Optional[Callable[..., None]] = None,
        cancel_event: Optional[Event] = None,
        pause_event: Optional[Event] = None,
        **kwargs: Any,
    ) -> bool:
        return bool(
            download_mega_link(
                url,
                target_folder,
                log_func=log_func,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
                pause_event=pause_event,
                max_workers=kwargs.get("max_workers", 6),
                skip_words=kwargs.get("skip_words"),
                options=kwargs.get("options"),
            )
        )
