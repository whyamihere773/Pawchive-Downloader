"""
In-App GitHub Updater Service.
Supports running both from source (main.py) and compiled (.exe).
Compares commit SHA for source or release tag for compiled versions,
downloads the latest zip from GitHub, stages the files, and performs
a safe restart hand-off.
"""

import os
import sys
import json
import shutil
import zipfile
import tarfile
import urllib.request
import subprocess
import threading
import time
from typing import Optional, Dict, Any, Callable

GITHUB_OWNER = "whyamihere773"
GITHUB_REPO = "Pawchive-Downloader"
GITHUB_BRANCH = "main"

USER_AGENT = "Pawchive-Downloader-Updater/1.0"


def find_matching_release_asset(assets: list, platform_name: str = sys.platform) -> str:
    """
    Selects the best release asset for the current OS platform.
    - On Linux: prefers archives matching 'linux', 'cachyos', 'arch', 'ubuntu' ending in .tar.gz, .tgz, or .zip.
    - On Windows: prefers archives matching 'win' or 'windows' ending in .zip or .exe.
    - On macOS: prefers archives matching 'darwin', 'mac', 'osx' ending in .dmg, .zip, or .tar.gz.
    """
    is_win = platform_name == "win32"
    is_linux = platform_name.startswith("linux")
    is_mac = platform_name == "darwin"

    candidates = []
    for asset in assets:
        name = asset.get("name", "").lower()
        url = asset.get("browser_download_url", "")
        if not url:
            continue

        score = 0
        if is_linux:
            if any(k in name for k in ("linux", "cachyos", "ubuntu", "arch", "debian", "x86_64")):
                score += 15
            if "win" in name or name.endswith(".exe"):
                score -= 30
            if name.endswith((".tar.gz", ".tgz")):
                score += 8
            elif name.endswith(".zip"):
                score += 3
        elif is_win:
            if "win" in name or "windows" in name:
                score += 15
            if "linux" in name or "darwin" in name or "mac" in name:
                score -= 30
            if name.endswith(".zip"):
                score += 8
            elif name.endswith(".exe"):
                score += 5
        elif is_mac:
            if any(k in name for k in ("mac", "darwin", "osx")):
                score += 15
            if "win" in name or "linux" in name:
                score -= 30
            if name.endswith((".dmg", ".zip", ".tar.gz")):
                score += 8

        if score > 0:
            candidates.append((score, url))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    # Fallback matching based strictly on file extensions and safety checks
    for asset in assets:
        name = asset.get("name", "").lower()
        url = asset.get("browser_download_url", "")
        if is_linux and (name.endswith((".tar.gz", ".tgz")) or ("linux" in name and name.endswith(".zip"))):
            return url
        if is_win and (name.endswith(".zip") or name.endswith(".exe")) and "linux" not in name:
            return url

    return ""


def extract_archive(archive_path: str, destination_dir: str):
    """Safely extracts both .zip and .tar.gz / .tgz / .tar archives."""
    if tarfile.is_tarfile(archive_path) or archive_path.lower().endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar")):
        with tarfile.open(archive_path, "r:*") as t:
            t.extractall(destination_dir)
    else:
        with zipfile.ZipFile(archive_path, "r") as z:
            z.extractall(destination_dir)



def is_compiled() -> bool:
    """Return True if running as a compiled standalone executable (PyInstaller/Nuitka/etc)."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS") or getattr(sys, "frozen", False)


def get_app_dir() -> str:
    """Get the root directory of the application."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # When running from source, app dir is the project root (parent of services/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_local_version_info() -> Dict[str, str]:
    """Retrieve currently installed version or commit SHA."""
    app_dir = get_app_dir()
    version_file = os.path.join(app_dir, "version.json")
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback to local git if running from source with .git
    git_dir = os.path.join(app_dir, ".git")
    if os.path.exists(git_dir):
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=app_dir,
                capture_output=True,
                text=True,
                timeout=3
            )
            if res.returncode == 0 and res.stdout.strip():
                return {
                    "commit": res.stdout.strip(),
                    "short_commit": res.stdout.strip()[:7],
                    "version": "source-dev",
                    "date": ""
                }
        except Exception:
            pass

        # Fallback to direct .git file reading (handles Docker/WSL safe.directory restriction)
        head_file = os.path.join(git_dir, "HEAD")
        if os.path.exists(head_file):
            try:
                with open(head_file, "r", encoding="utf-8") as f:
                    head_content = f.read().strip()
                if head_content.startswith("ref:"):
                    ref_rel = head_content[4:].strip()
                    ref_path = os.path.join(git_dir, ref_rel)
                    if os.path.exists(ref_path):
                        with open(ref_path, "r", encoding="utf-8") as rf:
                            sha = rf.read().strip()
                            if sha:
                                return {
                                    "commit": sha,
                                    "short_commit": sha[:7],
                                    "version": "source-dev",
                                    "date": ""
                                }
                elif len(head_content) == 40:
                    return {
                        "commit": head_content,
                        "short_commit": head_content[:7],
                        "version": "source-dev",
                        "date": ""
                    }
            except Exception:
                pass

    return {
        "commit": "",
        "short_commit": "current",
        "version": "1.0.0",
        "date": ""
    }


def check_for_updates(timeout: int = 8) -> Dict[str, Any]:
    """
    Check GitHub API for updates.
    - If running from source: checks latest commit on default branch.
    - If running as compiled: checks latest release.
    """
    local_info = get_local_version_info()
    compiled = is_compiled()

    if compiled:
        # Check GitHub Releases
        api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {
                "update_available": False,
                "error": f"Could not check releases: {e}",
                "compiled": True,
                "local_version": local_info.get("version", "1.0.0")
            }

        remote_tag = data.get("tag_name", "").strip().lstrip("v")
        local_ver = local_info.get("version", "").strip().lstrip("v")
        body = data.get("body", "")
        release_url = data.get("html_url", "")

        # Select platform-specific release asset (Linux .tar.gz vs Windows .zip)
        download_url = find_matching_release_asset(data.get("assets", []))

        update_available = bool(remote_tag and remote_tag != local_ver)
        return {
            "update_available": update_available,
            "compiled": True,
            "local_version": local_info.get("version", "1.0.0"),
            "remote_version": data.get("tag_name", ""),
            "commit_message": data.get("name", "") or data.get("tag_name", ""),
            "release_notes": body,
            "download_url": download_url,
            "release_url": release_url,
            "published_at": data.get("published_at", "")
        }

    else:
        # Running from source: check commits on main branch
        api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {
                "update_available": False,
                "error": f"Could not check commits: {e}",
                "compiled": False,
                "local_commit": local_info.get("short_commit", "")
            }

        remote_sha = data.get("sha", "").strip()
        remote_short = remote_sha[:7] if remote_sha else ""
        commit_msg = data.get("commit", {}).get("message", "").split("\n")[0]
        commit_date = data.get("commit", {}).get("author", {}).get("date", "")
        download_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"

        local_sha = local_info.get("commit", "").strip()
        # Require a valid local commit SHA to prevent endless update loops if git is unavailable
        update_available = bool(remote_sha and local_sha and remote_sha != local_sha)

        return {
            "update_available": update_available,
            "compiled": False,
            "local_commit": local_info.get("short_commit", "") or local_sha[:7],
            "remote_commit": remote_short,
            "full_remote_sha": remote_sha,
            "commit_message": commit_msg,
            "download_url": download_url,
            "published_at": commit_date
        }


class UpdateDownloader:
    """Handles downloading and staging the update zip in a background thread."""

    def __init__(self, download_url: str, update_info: Dict[str, Any]):
        self.download_url = download_url
        self.update_info = update_info
        self.app_dir = get_app_dir()
        self.temp_dir = os.path.join(self.app_dir, "temp", "update")
        
        # Determine archive file extension (.tar.gz vs .zip)
        ext = ".tar.gz" if ".tar" in download_url.lower() else ".zip"
        self.archive_path = os.path.join(self.temp_dir, f"update{ext}")
        self.zip_path = self.archive_path  # Backwards compatibility alias
        self.staging_dir = os.path.join(self.temp_dir, "staging")

        self.is_downloading = False
        self.progress = 0.0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed_str = "--"
        self.status_text = "Idle"
        self.error_message = ""
        self.is_ready = False

        self._cancel_event = threading.Event()

    def start_download(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_finished: Optional[Callable[[bool, str], None]] = None
    ):
        """Starts asynchronous download and staging."""
        self._cancel_event.clear()
        self.is_downloading = True
        self.error_message = ""
        self.is_ready = False

        def _worker():
            try:
                os.makedirs(self.temp_dir, exist_ok=True)
                if os.path.exists(self.staging_dir):
                    shutil.rmtree(self.staging_dir, ignore_errors=True)
                os.makedirs(self.staging_dir, exist_ok=True)

                self.status_text = "Connecting to GitHub..."
                if on_progress:
                    on_progress(0.05, self.status_text)

                req = urllib.request.Request(self.download_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    self.total_bytes = total
                    downloaded = 0
                    start_time = time.time()
                    last_time = start_time

                    with open(self.archive_path, "wb") as out_f:
                        while True:
                            if self._cancel_event.is_set():
                                self.status_text = "Cancelled"
                                self.is_downloading = False
                                return

                            chunk = resp.read(64 * 1024)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            downloaded += len(chunk)
                            self.downloaded_bytes = downloaded

                            now = time.time()
                            if now - last_time >= 0.25 or downloaded == total:
                                last_time = now
                                pct = (downloaded / total) if total > 0 else 0.5
                                elapsed = max(0.001, now - start_time)
                                speed_bps = downloaded / elapsed
                                speed_mb = speed_bps / (1024 * 1024)
                                self.speed_str = f"{speed_mb:.1f} MB/s"
                                self.progress = pct
                                self.status_text = f"Downloading: {int(pct * 100)}% ({self.speed_str})"
                                if on_progress:
                                    on_progress(pct, self.status_text)

                self.status_text = "Extracting & verifying update package..."
                if on_progress:
                    on_progress(0.95, self.status_text)

                # Extract archive (supports both .zip and .tar.gz)
                extract_archive(self.archive_path, self.staging_dir)

                # If extracted folder has a single root directory (e.g. Pawchive-Downloader-main/),
                # locate that inner root
                entries = os.listdir(self.staging_dir)
                actual_stage_root = self.staging_dir
                if len(entries) == 1 and os.path.isdir(os.path.join(self.staging_dir, entries[0])):
                    actual_stage_root = os.path.join(self.staging_dir, entries[0])

                self.staging_root = actual_stage_root
                self.is_ready = True
                self.is_downloading = False
                self.status_text = "Update Ready to Install!"
                if on_finished:
                    on_finished(True, "")

            except Exception as e:
                self.is_downloading = False
                self.error_message = str(e)
                self.status_text = f"Error: {e}"
                if on_finished:
                    on_finished(False, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def cancel(self):
        self._cancel_event.set()


def launch_external_updater(update_info: Dict[str, Any]):
    """
    Launches the standalone updater (updater.exe on Windows, updater on Linux)
    or updater.py in source mode and exits the main application immediately
    so all files are unlocked.
    """
    app_dir = get_app_dir()
    current_pid = os.getpid()
    download_url = update_info.get("download_url", "")
    version = update_info.get("remote_version", "") or update_info.get("commit_message", "")

    # Locate updater binary or updater.py
    bin_name = "updater.exe" if sys.platform == "win32" else "updater"
    updater_bin = os.path.join(app_dir, bin_name)
    updater_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "updater.py")

    if is_compiled() and os.path.exists(updater_bin):
        if sys.platform != "win32":
            try:
                st = os.stat(updater_bin)
                os.chmod(updater_bin, st.st_mode | 0o755)
            except Exception:
                pass
        cmd = [
            updater_bin,
            "--target-dir", app_dir,
            "--pid", str(current_pid),
            "--download-url", download_url,
            "--version", version
        ]
    else:
        # Running from source or fallback
        python_exe = sys.executable if not is_compiled() else ("python.exe" if sys.platform == "win32" else "python3")
        cmd = [
            python_exe,
            updater_script,
            "--target-dir", app_dir,
            "--pid", str(current_pid),
            "--download-url", download_url,
            "--version", version
        ]

    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, creationflags=creationflags, close_fds=True)
    else:
        subprocess.Popen(cmd, start_new_session=True, close_fds=True)


    # Terminate the current application immediately
    os._exit(0)


def apply_update_and_restart(staging_root: str, update_info: Dict[str, Any]):
    """Alias for backwards compatibility: launches standalone updater."""
    launch_external_updater(update_info)

