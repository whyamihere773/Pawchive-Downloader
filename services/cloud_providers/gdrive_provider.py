"""
Google Drive Cloud Storage Provider
Handles file/folder resolution, quota detection, and gdown-backed streaming downloads.
"""

import os
import re
import sys
from threading import Event
from typing import Any, Callable, List, Optional, Union
from urllib.parse import parse_qs, urlparse

import requests

from services.cloud_providers.base import _safe_name, CloudProvider, should_skip_cloud_file

try:
    import gdown
    GDRIVE_AVAILABLE = True
except ImportError:
    gdown = None
    GDRIVE_AVAILABLE = False


class _DevNull:
    """A no-op file-like object used to silence gdown when sys.stdout is None."""
    def write(self, *args, **kwargs): pass
    def flush(self, *args, **kwargs): pass
    def isatty(self): return False


class _suppress_gdown_output:
    """Context manager that patches sys.stdout/stderr to /dev/null when they
    are None (e.g. PyInstaller --windowed builds).  gdown internally uses
    tqdm which writes to sys.stdout; if that is None the whole download
    crashes with AttributeError: 'NoneType' object has no attribute 'write'.
    """
    def __enter__(self):
        import sys
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        if sys.stdout is None:
            sys.stdout = _DevNull()
        if sys.stderr is None:
            sys.stderr = _DevNull()
        return self

    def __exit__(self, *_):
        import sys
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr


def _gdrive_resolve_filename(file_id: str, fallback: str = "gdrive_file") -> str:
    """Try to resolve a Google Drive file's real name via a HEAD/GET request
    without downloading the full file body.  Falls back to *fallback* on any
    error so the download still proceeds.
    """
    try:
        r = requests.get(
            f"https://drive.google.com/uc?export=download&id={file_id}",
            allow_redirects=True,
            stream=True,
            timeout=10,
        )
        r.close()
        cd = r.headers.get("Content-Disposition", "")
        m = re.search(r'filename\*?=(?:UTF-8\'\'\')?"?([^"\n;]+)', cd, re.IGNORECASE)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    except Exception:
        pass
    return fallback


def _is_quota_error_file(path: str) -> bool:
    """Return True if the downloaded file is actually an HTML quota-error page."""
    try:
        if os.path.getsize(path) > 65536:
            return False
        with open(path, "rb") as f:
            head = f.read(2048)
        return (
            b"<title>Google Drive - Quota exceeded</title>" in head
            or b"uc-error-subcaption" in head
            or b"Too many users have viewed" in head
        )
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public Google Drive downloader
# ---------------------------------------------------------------------------

def download_gdrive_link(
    url: str,
    target_folder: str,
    log_func: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[str, int, int, int, int], None]] = None,
    cancel_event: Optional[Event] = None,
    pause_event: Optional[Event] = None,
    skip_words: Optional[Union[str, List[str]]] = None,
    options: Optional[Any] = None
) -> bool:
    _facade = sys.modules.get('services.cloud_downloader')
    _gd_ok = getattr(_facade, 'GDRIVE_AVAILABLE', GDRIVE_AVAILABLE) if _facade else GDRIVE_AVAILABLE
    _gdown = getattr(_facade, 'gdown', gdown) if _facade else gdown
    _req = getattr(_facade, 'requests', requests) if _facade else requests
    if not _gd_ok:
        log_func("❌ Google Drive download failed: 'gdown' is not installed.")
        return False

    os.makedirs(target_folder, exist_ok=True)
    log_func(f"   [Google Drive] Initializing download for: {url}")

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    # ------------------------------------------------------------------
    # Detect whether this is a folder or a single file, and extract ID
    # ------------------------------------------------------------------
    folder_m = re.search(r'/folders/([a-zA-Z0-9_-]+)', parsed.path)
    if folder_m:
        kind, item_id = 'folder', folder_m.group(1)
    elif 'folderview' in parsed.path or 'folders' in parsed.query:
        kind, item_id = 'folder', qs.get('id', [None])[0]
    elif m := re.search(r'/file/(?:u/\d+/)?d/([a-zA-Z0-9_-]+)', parsed.path):
        kind, item_id = 'file', m.group(1)
    elif m := re.search(r'/(?:document|presentation|spreadsheets)/d/([a-zA-Z0-9_-]+)', parsed.path):
        kind, item_id = 'file', m.group(1)
    elif 'id' in qs:
        item_id = qs['id'][0]
        if 'open' in parsed.path:
            try:
                r = _req.get(
                    f"https://drive.google.com/open?id={item_id}",
                    allow_redirects=False, timeout=8
                )
                loc = r.headers.get("Location", "")
                kind = "folder" if ("/folders/" in loc or "folderview" in loc) else "file"
            except Exception:
                kind = "file"
        else:
            kind = "file"
    else:
        kind, item_id = 'unknown', None

    # ------------------------------------------------------------------
    # Folder download
    # ------------------------------------------------------------------
    if kind == 'folder' and item_id:
        log_func(f"   [Google Drive] 📁 Detected folder ID: {item_id}. Downloading folder...")
        try:
            with _suppress_gdown_output():
                res_list = _gdown.download_folder(
                    id=item_id,
                    output=target_folder,
                    quiet=True,
                )
            if res_list:
                # Filter out any quota-error HTML pages or files matching skip filters
                good = []
                skipped_by_filter = 0
                for p in res_list:
                    if isinstance(p, str) and os.path.isfile(p):
                        if _is_quota_error_file(p):
                            os.remove(p)
                            log_func("   [Google Drive] ⚠️ Quota exceeded for one file in folder.")
                        else:
                            rel_p = os.path.relpath(p, target_folder)
                            fsize = os.path.getsize(p) if os.path.exists(p) else 0
                            skip, reason = should_skip_cloud_file(rel_p, skip_words=skip_words, file_size=fsize, options=options)
                            if skip:
                                skipped_by_filter += 1
                                try:
                                    os.remove(p)
                                except OSError:
                                    pass
                                log_func(f"   [Google Drive] ⏭️ Skipped '{rel_p}': {reason}")
                            else:
                                good.append(p)
                log_func(
                    f"   [Google Drive] ✅ Folder download finished: "
                    f"{len(good)} file(s) saved to {target_folder}"
                )
                return len(good) > 0 or skipped_by_filter > 0
            else:
                log_func("   [Google Drive] ⚠️ Folder appears empty or has restricted permissions.")
                return False
        except Exception as e:
            err_str = str(e)
            if "Too many users" in err_str or "Quota" in err_str:
                log_func(
                    "   [Google Drive] ⚠️ Bandwidth Quota Exceeded on folder. "
                    "Please try again later."
                )
            elif "Cancelled" in err_str:
                log_func("   [Google Drive] ℹ️ Download cancelled.")
            else:
                log_func(f"   [Google Drive] ❌ Folder download error: {e}")
            return False

    # ------------------------------------------------------------------
    # Single file download
    # ------------------------------------------------------------------
    try:
        # Use gdown's skip_download to resolve the real filename first.
        # gdown 6.x returns a GoogleDriveFileToDownload object with .path
        resolved_name = None
        try:
            with _suppress_gdown_output():
                if item_id:
                    meta = _gdown.download(id=item_id, output=target_folder + os.sep, quiet=True, skip_download=True)
                else:
                    meta = _gdown.download(url=url, output=target_folder + os.sep, quiet=True, skip_download=True)
            # gdown 6.x returns GoogleDriveFileToDownload with .path
            if meta and hasattr(meta, 'path'):
                resolved_name = os.path.basename(meta.path)
            elif isinstance(meta, str):
                resolved_name = os.path.basename(meta)
        except Exception:
            pass  # Fall through to manual resolution

        # Fallback: try manual HEAD request or use generic name
        if not resolved_name:
            if item_id:
                resolved_name = _gdrive_resolve_filename(item_id, fallback=f"gdrive_{item_id}")
            else:
                resolved_name = os.path.basename(parsed.path) or "gdrive_file"

        # Sanitise the resolved filename
        resolved_name = _safe_name(resolved_name, f"gdrive_{item_id or 'file'}")

        output_path = os.path.join(target_folder, resolved_name)

        if skip_words or options:
            skip, reason = should_skip_cloud_file(resolved_name, skip_words=skip_words, options=options)
            if skip:
                log_func(f"   [Google Drive] ⏭️ Skipping '{resolved_name}': {reason}")
                return True

        log_func(f"   [Google Drive] 🔽 Downloading as '{resolved_name}'...")

        # Build progress wrapper if caller provided a callback
        _progress_fn = None
        if progress_callback:
            def _progress_fn(current_bytes, total_bytes):
                if cancel_event and cancel_event.is_set():
                    raise InterruptedError("Cancelled by user")
                progress_callback(resolved_name, current_bytes, total_bytes or 0, 1, 1)

        with _suppress_gdown_output():
            dl_kwargs = {
                "output": output_path,
                "quiet": True,
                "resume": True,
            }
            if _progress_fn:
                dl_kwargs["progress"] = _progress_fn
            if item_id:
                dl_kwargs["id"] = item_id
            else:
                dl_kwargs["url"] = url
            result = _gdown.download(**dl_kwargs)

        # gdown 6.x may return a GoogleDriveFileToDownload object or a str
        if hasattr(result, 'path'):
            result = result.path

        # gdown returns None or False on failure
        if result is None or result is False:
            log_func(
                "   [Google Drive] ❌ Download returned no file "
                "(file may be restricted, deleted, or quota-limited)."
            )
            return False

        # Make sure the returned path actually exists (gdown may rename it)
        if not isinstance(result, str) or not os.path.isfile(result):
            log_func(f"   [Google Drive] ❌ Downloaded file not found at expected path: {result}")
            return False

        # Check for disguised quota-error HTML pages
        if _is_quota_error_file(result):
            os.remove(result)
            log_func(
                "   [Google Drive] ⚠️ Bandwidth Quota Exceeded: Google has temporarily "
                "locked public downloads for this file ('Too many users have viewed or "
                "downloaded this file recently'). Google imposes a 24-hour cooldown on "
                "heavily accessed files. Please try again later or open in a browser "
                "while logged in."
            )
            return False

        log_func(f"   [Google Drive] ✅ Download complete to: {result}")
        return True

    except Exception as e:
        err_str = str(e)
        if "Too many users have viewed or downloaded this file recently" in err_str or "Quota exceeded" in err_str:
            log_func(
                "   [Google Drive] ⚠️ Bandwidth Quota Exceeded: Google has temporarily "
                "locked public downloads for this file ('Too many users have viewed or "
                "downloaded this file recently'). Google imposes a 24-hour cooldown on "
                "heavily accessed files. Please try again later or open in a browser "
                "while logged in."
            )
        elif "Cancelled by user" in err_str or "InterruptedError" in err_str:
            log_func("   [Google Drive] ℹ️ Download cancelled.")
        elif "Cannot retrieve the public link" in err_str or "Access denied" in err_str or "Permission" in err_str:
            log_func("   [Google Drive] ⚠️ Access Denied: File may be private or requires Google account permissions.")
        else:
            log_func(f"   [Google Drive] ❌ Download error: {e}")
        return False


class GDriveCloudProvider(CloudProvider):
    """Plug-and-play provider for Google Drive file and folder links."""

    name = "gdrive"

    def can_handle(self, url: str) -> bool:
        low = (url or "").lower()
        return "drive.google.com" in low or "docs.google.com" in low

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
            download_gdrive_link(
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
