"""
Dropbox & GoFile Cloud Storage Providers
Handles direct Dropbox downloads (with automatic ZIP extraction) and parallel GoFile folders.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
import re
import sys
from threading import Event, Lock
import time
from typing import Any, Callable, List, Optional, Union
from urllib.parse import parse_qs, urlparse
import zipfile

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


def download_dropbox_link(
    url: str,
    target_folder: str,
    log_func: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    cancel_event: Optional[Event] = None,
    pause_event: Optional[Event] = None,
    skip_words: Optional[Union[str, List[str]]] = None,
    options: Optional[Any] = None
) -> bool:
    os.makedirs(target_folder, exist_ok=True)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    qs['dl'] = ['1']
    from urllib.parse import urlunparse, urlencode
    direct_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(qs, doseq=True), parsed.fragment))

    log_func(f"   [Dropbox] Connecting to direct stream: {direct_url}")
    try:
        _facade = sys.modules.get('services.cloud_downloader')
        _req = getattr(_facade, 'requests', requests) if _facade else requests
        with _req.get(direct_url, stream=True, allow_redirects=True, timeout=(20, 600)) as r:
            with _active_cloud_lock:
                _active_cloud_resps.add(r)
            try:
                r.raise_for_status()
                cd = r.headers.get('content-disposition', '')
                fname_match = re.findall(r'filename="?([^"]+)"?', cd)
                filename = fname_match[0].strip() if fname_match else os.path.basename(parsed.path) or "dropbox_download"
                filename = _safe_name(filename, "dropbox_download")
                if not os.path.splitext(filename)[1]:
                    filename += ".zip"

                total_size = int(r.headers.get('content-length', 0))
                if skip_words or options:
                    skip, reason = should_skip_cloud_file(filename, skip_words=skip_words, file_size=total_size, options=options)
                    if skip:
                        log_func(f"   [Dropbox] ⏭️ Skipping '{filename}': {reason}")
                        return True

                full_path = os.path.join(target_folder, filename)
                downloaded = 0
                last_log = time.time()

                with open(full_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=16384):
                        if cancel_event and cancel_event.is_set():
                            log_func("   [Dropbox] Download cancelled.")
                            if os.path.exists(full_path):
                                try:
                                    os.remove(full_path)
                                except OSError:
                                    pass
                            return False
                        while pause_event and pause_event.is_set():
                            time.sleep(0.5)
                            if cancel_event and cancel_event.is_set():
                                if os.path.exists(full_path):
                                    try:
                                        os.remove(full_path)
                                    except OSError:
                                        pass
                                return False

                        if not bandwidth_limiter.wait_for(len(chunk), cancel_event, pause_event):
                            log_func("   [Dropbox] Download cancelled.")
                            if os.path.exists(full_path):
                                try:
                                    os.remove(full_path)
                                except OSError:
                                    pass
                            return False

                        f.write(chunk)
                        downloaded += len(chunk)
                        if time.time() - last_log >= 1.0:
                            if progress_callback:
                                progress_callback(filename, downloaded, total_size, 1, 1)
                            last_log = time.time()
            finally:
                with _active_cloud_lock:
                    _active_cloud_resps.discard(r)

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
                if skip_words or options:
                    for root, _, fnames in os.walk(extract_dir, topdown=False):
                        for fn in fnames:
                            fpath = os.path.join(root, fn)
                            rel = os.path.relpath(fpath, extract_dir)
                            fsize = os.path.getsize(fpath) if os.path.exists(fpath) else 0
                            skip, reason = should_skip_cloud_file(rel, skip_words=skip_words, file_size=fsize, options=options)
                            if skip:
                                try:
                                    os.remove(fpath)
                                    log_func(f"   [Dropbox] ⏭️ Pruned extracted '{rel}': {reason}")
                                except OSError:
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
    max_workers: int = 6,
    skip_words: Optional[Union[str, List[str]]] = None,
    options: Optional[Any] = None
) -> bool:
    match = re.search(r"gofile\.io/d/([^/?#]+)", url)
    if not match:
        log_func(f"   [GoFile] ❌ Invalid GoFile URL format: {url}")
        return False

    content_id = match.group(1)
    _facade = sys.modules.get('services.cloud_downloader')
    _req = getattr(_facade, 'requests', requests) if _facade else requests
    session = _req.Session()
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

        if skip_words or options:
            filtered_files = []
            for f in files:
                fname = f.get("name", "")
                fsize = f.get("size", 0)
                skip, reason = should_skip_cloud_file(fname, skip_words=skip_words, file_size=fsize, options=options)
                if skip:
                    log_func(f"   [GoFile] ⏭️ Skipping '{fname}': {reason}")
                else:
                    filtered_files.append(f)
            files = filtered_files
            if not files:
                log_func("   [GoFile] All files in folder matched skip filters.")
                return True

        workers = max(1, min(max_workers, 16))
        folder_name = _safe_name(folder_info.get("name"), f"gofile_{content_id}")
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

            fname = _safe_name(fobj.get("name"), f"gofile_file_{fobj.get('id', '')}")
            furl = fobj["link"]
            fsize = fobj.get("size", 0)
            fpath = os.path.join(save_path, fname)
            if not _inside(save_path, fpath):
                log_func(f"   [GoFile] ⚠️ Skipping '{fname}': unsafe file name")
                return

            log_func(f"   [GoFile] 🔽 '{fname}'")

            try:
                with session.get(furl, stream=True, timeout=(30, 600)) as r:
                    with _active_cloud_lock:
                        _active_cloud_resps.add(r)
                    try:
                        r.raise_for_status()
                        downloaded = 0
                        last_t = time.time()
                        with open(fpath, "wb") as f:
                            for chunk in r.iter_content(chunk_size=16384):
                                if cancel_event and cancel_event.is_set():
                                    if os.path.exists(fpath):
                                        try:
                                            os.remove(fpath)
                                        except OSError:
                                            pass
                                    return
                                while pause_event and pause_event.is_set():
                                    time.sleep(0.5)
                                    if cancel_event and cancel_event.is_set():
                                        if os.path.exists(fpath):
                                            try:
                                                os.remove(fpath)
                                            except OSError:
                                                pass
                                        return

                                if not bandwidth_limiter.wait_for(len(chunk), cancel_event, pause_event):
                                    if os.path.exists(fpath):
                                        try:
                                            os.remove(fpath)
                                        except OSError:
                                            pass
                                    return

                                f.write(chunk)
                                downloaded += len(chunk)
                                if time.time() - last_t >= 1.0:
                                    if progress_callback:
                                        progress_callback(fname, downloaded, fsize, processed_count + 1, total_files)
                                    last_t = time.time()
                    finally:
                        with _active_cloud_lock:
                            _active_cloud_resps.discard(r)

                log_func(f"   [GoFile] ✅ Finished '{fname}'")
                if progress_callback:
                    progress_callback(fname, fsize, fsize, processed_count + 1, total_files)
            except Exception as e:
                if cancel_event and cancel_event.is_set():
                    if os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                    return
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


class DropboxCloudProvider(CloudProvider):
    """Plug-and-play provider for Dropbox share links."""

    name = "dropbox"

    def can_handle(self, url: str) -> bool:
        return "dropbox.com" in (url or "").lower()

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
            download_dropbox_link(
                url,
                target_folder,
                log_func=log_func,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
                pause_event=pause_event,
                skip_words=kwargs.get("skip_words"),
                options=kwargs.get("options"),
            )
        )


class GoFileCloudProvider(CloudProvider):
    """Plug-and-play provider for GoFile folder links."""

    name = "gofile"

    def can_handle(self, url: str) -> bool:
        return "gofile.io" in (url or "").lower()

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
            download_gofile_link(
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
