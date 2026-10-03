"""
Embedded Streaming Downloader Subsystem
Manages automatic updating, binary resolution, and background execution of yt-dlp.
"""

import os
import sys
import time
import shutil
import threading
import subprocess
import requests
from typing import Optional, Callable, Tuple
from core.logger import logger


class YtDlpManager:
    """
    Manages the standalone yt-dlp.exe binary in the dependencies/ folder,
    handles automatic startup updates from GitHub, and executes media downloads
    with real-time progress callbacks and cancellation support.
    """

    GITHUB_LATEST_RELEASE_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
    GITHUB_DIRECT_DOWNLOAD_URL = (
        "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        if sys.platform == "win32"
        else "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
    )

    def __init__(self, base_dir: Optional[str] = None):
        self.binary_name = "yt-dlp.exe" if sys.platform == "win32" else "yt-dlp"
        if base_dir:
            self.base_dir = base_dir
            self.dependencies_dir = os.path.join(self.base_dir, "dependencies")
        else:
            from core.path_utils import get_dependencies_dir, get_base_dir
            self.base_dir = get_base_dir()
            self.dependencies_dir = get_dependencies_dir()

        self.exe_path = os.path.join(self.dependencies_dir, self.binary_name)
        self._update_in_progress = False
        self._lock = threading.Lock()
        self._active_processes: set = set()
        self._proc_lock = threading.Lock()

    def get_executable_path(self) -> str:
        """Returns path to yt-dlp executable, checking local dependencies or system PATH."""
        if os.path.exists(self.exe_path):
            return self.exe_path
        if sys.platform != "win32":
            system_bin = shutil.which(self.binary_name)
            if system_bin:
                return system_bin
        os.makedirs(self.dependencies_dir, exist_ok=True)
        return self.exe_path

    def is_binary_available(self) -> bool:
        """Checks if yt-dlp exists and is executable."""
        if os.path.exists(self.exe_path) and os.path.getsize(self.exe_path) > 1024 * 1024:
            return True
        if sys.platform != "win32" and shutil.which(self.binary_name):
            return True
        return False

    def download_latest_binary(self) -> bool:
        """
        Downloads the latest official standalone yt-dlp.exe from GitHub releases.
        """
        if self.is_binary_available():
            return True

        os.makedirs(self.dependencies_dir, exist_ok=True)
        temp_exe = f"{self.exe_path}.{os.getpid()}_{threading.get_ident()}_{time.time_ns()}.tmp"
        logger.info(f"Downloading latest yt-dlp.exe from GitHub to {self.dependencies_dir}...", category="ytdlp")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/octet-stream, */*"
        }

        try:
            with requests.get(self.GITHUB_DIRECT_DOWNLOAD_URL, headers=headers, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                total_bytes = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(temp_exe, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=128 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

            got = os.path.getsize(temp_exe) if os.path.exists(temp_exe) else 0
            if total_bytes and got != total_bytes:
                logger.warning(f"yt-dlp download incomplete ({got} of {total_bytes} bytes); not installed.", category="ytdlp")
                os.remove(temp_exe)
                return False
            if got > 1024 * 1024 and not self._checksum_ok(temp_exe):
                os.remove(temp_exe)
                return False
            if got > 1024 * 1024:
                os.replace(temp_exe, self.exe_path)
                if sys.platform != "win32":
                    try:
                        os.chmod(self.exe_path, 0o755)
                    except Exception:
                        pass
                logger.success(f"{self.binary_name} successfully installed ({downloaded / (1024*1024):.2f} MB)", category="ytdlp")
                return True
            return False

        except Exception as e:
            if not self.is_binary_available():
                logger.error(f"Failed to download yt-dlp.exe: {e}", category="ytdlp")
            if os.path.exists(temp_exe):
                try:
                    os.remove(temp_exe)
                except Exception:
                    pass
            return False

    def _checksum_ok(self, path: str) -> bool:
        """Compares the downloaded file with the SHA-256 list yt-dlp publishes with each release.
        When the list can't be fetched the file is accepted (it came over HTTPS from GitHub)."""
        import hashlib
        try:
            r = requests.get("https://github.com/yt-dlp/yt-dlp/releases/latest/download/SHA2-256SUMS", timeout=20)
            if r.status_code != 200:
                return True
            expected = ""
            for line in r.text.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].lstrip("*") == self.binary_name:
                    expected = parts[0].lower()
                    break
            if not expected:
                return True
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest().lower() != expected:
                logger.error("The downloaded yt-dlp doesn't match its published checksum; it was not installed.", category="ytdlp")
                return False
            logger.debug("yt-dlp checksum verified.", category="ytdlp")
            return True
        except Exception as e:
            logger.debug(f"yt-dlp checksum check skipped: {e}", category="ytdlp")
            return True

    def update_binary_via_cli(self) -> bool:
        """
        Runs `yt-dlp.exe -U` to update in-place if binary already exists.
        """
        if not self.is_binary_available():
            return self.download_latest_binary()
        if not os.path.exists(self.exe_path):
            # Only a system-wide yt-dlp (Linux package / pip): its package manager updates it
            # ("-U" used to be run on a local copy that doesn't exist)
            logger.info("Using the system's yt-dlp; update it with your package manager.", category="ytdlp")
            return True

        try:
            logger.info("Checking for yt-dlp updates...", category="ytdlp")
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.run(
                [self.exe_path, "-U"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                timeout=45
            )

            output = (proc.stdout or "") + (proc.stderr or "")
            if "up to date" in output.lower():
                logger.info("yt-dlp is already up to date.", category="ytdlp")
                return True
            elif "updated yt-dlp" in output.lower() or proc.returncode == 0:
                logger.success("yt-dlp successfully updated to latest version!", category="ytdlp")
                return True
            else:
                logger.debug(f"yt-dlp -U output: {output.strip()}", category="ytdlp")
                # Fallback to direct github binary download if in-place update fails
                return self.download_latest_binary()
        except Exception as e:
            logger.debug(f"CLI update failed ({e}), falling back to direct download...", category="ytdlp")
            return self.download_latest_binary()

    def check_for_updates_async(self):
        """
        Asynchronously checks/downloads/updates yt-dlp.exe in a background thread
        so it never blocks UI launch.
        """
        with self._lock:
            if self._update_in_progress:
                return
            self._update_in_progress = True

        def _bg_worker():
            try:
                if not self.is_binary_available():
                    self.download_latest_binary()
                else:
                    self.update_binary_via_cli()
            except Exception as ex:
                logger.debug(f"Background yt-dlp update check exception: {ex}", category="ytdlp")
            finally:
                with self._lock:
                    self._update_in_progress = False

        threading.Thread(target=_bg_worker, daemon=True).start()

    def cancel_all(self):
        """Instantly terminates all active yt-dlp child processes."""
        with self._proc_lock:
            for proc in list(self._active_processes):
                try:
                    proc.kill()
                except Exception:
                    pass
            self._active_processes.clear()

    def download_media(
        self,
        url: str,
        target_folder: str,
        custom_filename: Optional[str] = None,
        cancel_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
        timeout: int = 600,
        referer: str = ""
    ) -> Tuple[bool, str]:
        """
        Executes yt-dlp.exe on a media URL, writing output to target_folder with
        live progress reporting.

        progress_callback signature: (done_bytes, total_bytes, speed_str, eta_str)
        Returns: (success: bool, error_msg_or_filename: str)
        """
        if cancel_event and cancel_event.is_set():
            return False, "Cancelled"

        if not self.is_binary_available():
            ok = self.download_latest_binary()
            if not ok or not self.is_binary_available():
                return False, "yt-dlp.exe is missing and could not be downloaded."

        os.makedirs(target_folder, exist_ok=True)

        if custom_filename:
            name_stem = os.path.splitext(custom_filename)[0]
            out_template = os.path.join(target_folder, f"{name_stem}.%(ext)s")
        else:
            out_template = os.path.join(target_folder, "%(title).100s [%(id)s].%(ext)s")

        # Command with custom progress formatting on stdout
        cmd = [
            self.get_executable_path(),
            "--no-playlist",
            "--no-warnings",
            "--newline",
            "-o", out_template,
            "--progress-template", "download:PROGRESS:%(progress.downloaded_bytes)s/%(progress.total_bytes_estimate|progress.total_bytes)s:%(progress.speed)s:%(progress.eta)s",
        ]
        # Domain-locked Vimeo embeds only play when the request says it comes from the creator's site
        if referer and "vimeo.com" in url.lower():
            cmd += ["--referer", referer]
        cmd.append(url)

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        proc = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags
            )
            with self._proc_lock:
                self._active_processes.add(proc)

            # Read stdout line by line for live progress
            while proc.poll() is None:
                if cancel_event and cancel_event.is_set():
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    return False, "Cancelled"

                while pause_event and pause_event.is_set():
                    time.sleep(0.3)
                    if cancel_event and cancel_event.is_set():
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        return False, "Cancelled"

                line = proc.stdout.readline()
                if line:
                    line_str = line.strip()
                    if line_str.startswith("PROGRESS:"):
                        try:
                            # PROGRESS:downloaded/total:speed:eta
                            parts = line_str[9:].split(":")
                            if len(parts) >= 3:
                                bytes_part = parts[0].split("/")
                                done_b = int(float(bytes_part[0])) if bytes_part[0] and bytes_part[0] != "NA" else 0
                                total_b = int(float(bytes_part[1])) if len(bytes_part) > 1 and bytes_part[1] and bytes_part[1] != "NA" else 0
                                
                                speed_val = float(parts[1]) if parts[1] and parts[1] != "NA" else 0.0
                                if speed_val > 1024 * 1024:
                                    speed_str = f"{speed_val / (1024*1024):.2f} MB/s"
                                elif speed_val > 1024:
                                    speed_str = f"{speed_val / 1024:.1f} KB/s"
                                else:
                                    speed_str = f"{int(speed_val)} B/s"

                                eta_val = int(float(parts[2])) if parts[2] and parts[2] != "NA" else 0
                                eta_str = f"{eta_val//60}m {eta_val%60}s" if eta_val > 60 else f"{eta_val}s"

                                if progress_callback:
                                    progress_callback(done_b, total_b, speed_str, eta_str)
                        except Exception:
                            pass

            if cancel_event and cancel_event.is_set():
                try:
                    proc.kill()
                except Exception:
                    pass
                return False, "Cancelled"

            stdout_rem, stderr_rem = proc.communicate(timeout=10)
            if proc.returncode == 0:
                return True, "Completed"
            else:
                err_msg = (stderr_rem or stdout_rem or f"yt-dlp exited with code {proc.returncode}").strip()
                # Clean up error message for UI
                if "ERROR:" in err_msg:
                    err_msg = err_msg.split("ERROR:")[-1].strip()
                return False, err_msg[:120]

        except Exception as e:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            if cancel_event and cancel_event.is_set():
                return False, "Cancelled"
            return False, str(e)
        finally:
            if proc is not None:
                with self._proc_lock:
                    self._active_processes.discard(proc)
