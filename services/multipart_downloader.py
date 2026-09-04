import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable, Dict, Any, Tuple
import requests

CHUNK_BUFFER_SIZE = 64 * 1024  # 64 KB read buffer
MIN_MULTIPART_SIZE = 20 * 1024 * 1024  # Only use multipart for files >= 20 MB

def download_multipart_file(
    url: str,
    target_path: str,
    headers: Optional[Dict[str, str]] = None,
    num_chunks: int = 4,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    pause_event: Optional[threading.Event] = None,
    timeout: int = 30,
    session: Optional[requests.Session] = None
) -> Tuple[bool, str]:
    """
    Downloads a large file using parallel HTTP Range requests (multipart chunking).
    If the remote server does not support byte ranges, it seamlessly falls back
    to standard single-stream downloading.

    Returns:
        (success: bool, error_message: str)
    """
    req_headers = dict(headers or {})
    req_session = session or requests.Session()
    
    # 1. Probe the file size and range capabilities
    try:
        probe_resp = req_session.head(url, headers=req_headers, timeout=timeout, allow_redirects=True)
        # If HEAD is disallowed (e.g. 405), try a 1-byte GET
        if probe_resp.status_code in (405, 403, 400):
            probe_headers = dict(req_headers)
            probe_headers["Range"] = "bytes=0-0"
            probe_resp = req_session.get(url, headers=probe_headers, timeout=timeout, stream=True)
    except Exception as e:
        return _fallback_single_download(
            url, target_path, req_headers, progress_callback, cancel_event, pause_event, timeout, req_session
        )

    content_length_str = probe_resp.headers.get("Content-Length")
    accept_ranges = probe_resp.headers.get("Accept-Ranges", "").lower()
    is_partial_capable = (
        probe_resp.status_code == 206
        or "bytes" in accept_ranges
        or probe_resp.headers.get("Content-Range") is not None
    )

    total_size = int(content_length_str) if content_length_str and content_length_str.isdigit() else 0

    # Fallback to single stream if file is small, size unknown, or server lacks Range support
    if total_size < MIN_MULTIPART_SIZE or not is_partial_capable or num_chunks <= 1:
        return _fallback_single_download(
            url, target_path, req_headers, progress_callback, cancel_event, pause_event, timeout, req_session
        )

    # 2. Divide into chunk ranges
    chunk_size = total_size // num_chunks
    ranges = []
    for i in range(num_chunks):
        start_byte = i * chunk_size
        end_byte = (start_byte + chunk_size - 1) if i < num_chunks - 1 else (total_size - 1)
        ranges.append((i, start_byte, end_byte))

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    part_files = [f"{target_path}.part{i}" for i in range(num_chunks)]
    downloaded_bytes_per_chunk = [0] * num_chunks
    lock = threading.Lock()

    def _update_global_progress():
        if progress_callback:
            with lock:
                curr_total = sum(downloaded_bytes_per_chunk)
            progress_callback(curr_total, total_size)

    def _download_chunk(chunk_idx: int, start: int, end: int) -> Tuple[bool, str]:
        part_path = part_files[chunk_idx]
        chunk_headers = dict(req_headers)
        chunk_headers["Range"] = f"bytes={start}-{end}"
        expected_len = end - start + 1

        for attempt in range(3):
            if cancel_event and cancel_event.is_set():
                return False, "Cancelled"

            try:
                with req_session.get(url, headers=chunk_headers, timeout=timeout, stream=True) as resp:
                    if resp.status_code not in (200, 206):
                        time.sleep(1.0)
                        continue

                    written = 0
                    with open(part_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=CHUNK_BUFFER_SIZE):
                            if cancel_event and cancel_event.is_set():
                                return False, "Cancelled"
                            while pause_event and pause_event.is_set():
                                if cancel_event and cancel_event.is_set():
                                    return False, "Cancelled"
                                time.sleep(0.5)

                            if chunk:
                                f.write(chunk)
                                written += len(chunk)
                                with lock:
                                    downloaded_bytes_per_chunk[chunk_idx] = written
                                _update_global_progress()

                    if written >= expected_len:
                        return True, ""
            except Exception as e:
                if attempt == 2:
                    return False, f"Chunk {chunk_idx} failed: {e}"
                time.sleep(1.5 * (attempt + 1))

        return False, f"Chunk {chunk_idx} failed after 3 attempts"

    # 3. Download chunks concurrently
    with ThreadPoolExecutor(max_workers=num_chunks) as executor:
        futures = [
            executor.submit(_download_chunk, idx, start, end)
            for idx, start, end in ranges
        ]
        results = [f.result() for f in futures]

    # Check for failures
    for success, err in results:
        if not success:
            _cleanup_parts(part_files)
            if cancel_event and cancel_event.is_set():
                return False, "Download cancelled"
            # Fallback to single stream if multipart fails
            return _fallback_single_download(
                url, target_path, req_headers, progress_callback, cancel_event, pause_event, timeout, req_session
            )

    # 4. Stitch chunks together
    try:
        temp_final = f"{target_path}.tmp"
        with open(temp_final, "wb") as outfile:
            for p in part_files:
                with open(p, "rb") as infile:
                    while True:
                        buf = infile.read(1024 * 1024)
                        if not buf:
                            break
                        outfile.write(buf)
        
        _cleanup_parts(part_files)
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass
        os.replace(temp_final, target_path)
        return True, ""
    except Exception as e:
        _cleanup_parts(part_files)
        return False, f"Error stitching chunks: {e}"


def _fallback_single_download(
    url: str,
    target_path: str,
    headers: Dict[str, str],
    progress_callback: Optional[Callable[[int, int], None]],
    cancel_event: Optional[threading.Event],
    pause_event: Optional[threading.Event],
    timeout: int,
    session: requests.Session
) -> Tuple[bool, str]:
    """Single stream standard download fallback."""
    temp_target = f"{target_path}.tmp"
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    try:
        resp = session.get(url, headers=headers, timeout=timeout, stream=True)
        if resp.status_code == 403:
            # Fallback to browser navigation headers to bypass bot protection / CDN block
            browser_headers = {
                "User-Agent": headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
                "Referer": headers.get("Referer", "https://pawchive.pw/"),
                "Accept": "*/*",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
            try:
                resp.close()
            except Exception:
                pass
            resp = session.get(url, headers=browser_headers, timeout=timeout, stream=True)

        resp.raise_for_status()
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0

        with open(temp_target, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_BUFFER_SIZE):
                if cancel_event and cancel_event.is_set():
                    if os.path.exists(temp_target):
                        os.remove(temp_target)
                    return False, "Download cancelled"

                while pause_event and pause_event.is_set():
                    if cancel_event and cancel_event.is_set():
                        if os.path.exists(temp_target):
                            os.remove(temp_target)
                        return False, "Download cancelled"
                    time.sleep(0.5)

                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

        if total_size > 0 and downloaded == 0:
            if os.path.exists(temp_target):
                os.remove(temp_target)
            return False, "Downloaded file is empty (0 bytes received)"

        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass
        os.replace(temp_target, target_path)
        return True, ""
    except Exception as e:
        if os.path.exists(temp_target):
            try:
                os.remove(temp_target)
            except OSError:
                pass
        return False, str(e)


def _cleanup_parts(part_files: list):
    for p in part_files:
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
