"""
Pawchive Downloader — update checks and shared update rules.

Used by the app (to check for updates and start the updater) and by the updater itself
(to install them). Standard library only: it must load in the updater before anything else,
on every Linux distribution and on Windows.

Versions are standardised for every kind of install:
  • the version number always comes from version.json ("1.2.1")
  • source checkouts also know their commit, shown as "1.2.1 (ad0390c)"

How updates are found:
  • release builds: the latest GitHub release, compared by version number, and only when the
    release has a download for this platform
  • source installs: GitHub's own comparison of the local commit with `main`; an update is offered
    only when the install is strictly behind (local commits or another branch never trigger it)
  • source installs without a known commit: version.json on `main`, compared by version number
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from typing import Any, Dict, List, Optional, Tuple

GITHUB_OWNER = "whyamihere773"
GITHUB_REPO = "Pawchive-Downloader"
GITHUB_BRANCH = "main"
USER_AGENT = "Pawchive-Downloader-Updater/2.0"

# Never touched by an update (top-level folder names / file names, compared in lower case)
PROTECTED_DIRS = {
    "config", "downloads", "temp", "logs", "data", "models", "scratch",
    "venv", ".venv", "env", ".git", ".idea", ".vscode", "__pycache__", ".update_backup",
}
PROTECTED_FILES = {
    "settings.json", "watchlist.json", "known.txt", "cookies.txt", "link_vault.json",
    "link_vault.json.bak", "storage_pools.json", "schedules.json", "download_archive.db",
    "credentials_vault.enc", ".credential_key", "history.json", "session.json", "recovery_journal.json",
    "download_archive.db-wal", "download_archive.db-shm", "download_archive.db.bak",
    "history.db", "history.db-wal", "history.db-shm", "history.json.migrated",
    "link_vault.db", "link_vault.db-wal", "link_vault.db-shm", "link_vault.json.migrated", "link_vault.json.bak.migrated",
    "watchlist.db", "watchlist.db-wal", "watchlist.db-shm", "watchlist.db.bak", "watchlist.json.migrated",
    "recovery_journal.db", "recovery_journal.db-wal", "recovery_journal.db-shm", "recovery_journal.json.migrated",
    ".env", ".env.local", ".install_manifest.json", ".pawchive_update_state.json",
}
UPDATE_STATE_FILE = ".pawchive_update_state.json"   # commit installed from an archive over a git checkout
INSTALL_MANIFEST = ".install_manifest.json"          # files the last update installed
BACKUP_DIR = ".update_backup"                        # old files kept until an update is confirmed


# ── Paths & platform ────────────────────────────────────────────────────────
def is_compiled() -> bool:
    """True when running as a packaged build (PyInstaller) rather than from source."""
    return bool(getattr(sys, "frozen", False))


def get_app_dir() -> str:
    """The installation root (folder of the executable, or the project root from source)."""
    if is_compiled():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def platform_key() -> str:
    """'windows', 'linux' or 'other'. macOS isn't a supported update target."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


def edition(is_source: bool) -> str:
    """Which kind of install this is: 'windows', 'linux', 'macos' (compiled builds) or 'source'."""
    if is_source:
        return "source"
    key = platform_key()
    return "macos" if key == "other" and sys.platform == "darwin" else key


def edition_label(is_source: bool, is_git: bool = False) -> str:
    """What the user sees: 'Windows build', 'Linux build', 'Source code (git)'..."""
    if is_source:
        return "Source code (git)" if is_git else "Source code"
    return {"windows": "Windows build", "linux": "Linux build", "macos": "macOS build"}.get(edition(False), "Build")


def is_protected(rel_path: str) -> bool:
    """rel_path uses '/' separators, relative to the app folder."""
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p and p != "."]
    if not parts:
        return True
    if [p.lower() for p in parts[:2]] == ["_internal", "logs"]:      # where older Windows builds kept logs
        return True
    return parts[0].lower() in PROTECTED_DIRS or parts[-1].lower() in PROTECTED_FILES


# ── Versions ────────────────────────────────────────────────────────────────
def parse_version(text: str) -> Tuple:
    """'v1.2.10-beta.2' -> comparable tuple. Releases sort after their pre-releases."""
    s = (text or "").strip().lstrip("vV")
    s = s.split("+", 1)[0]
    core, _, pre = s.partition("-")
    nums = []
    for part in core.split(".")[:4]:
        m = re.match(r"\d+", part)
        nums.append(int(m.group(0)) if m else 0)
    while len(nums) < 3:
        nums.append(0)
    pre_key: Tuple = (1,)
    if pre:
        pre_key = (0,) + tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"[.\-]", pre))
    return tuple(nums) + pre_key


def is_newer(remote: str, local: str) -> bool:
    return bool(remote) and parse_version(remote) > parse_version(local or "0")


def _read_version_file(app_dir: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(app_dir, "version.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _safe_dir_arg(app_dir: str) -> str:
    """git -c safe.directory=<this folder>: git refuses checkouts owned by another user
    (WSL /mnt drives, Docker volumes, NTFS mounts). Only this folder is trusted."""
    return "safe.directory=" + os.path.abspath(app_dir).replace("\\", "/")


def git_command(app_dir: str, *args: str) -> List[str]:
    return ["git", "-c", _safe_dir_arg(app_dir), *args]


def _git_head(app_dir: str) -> str:
    """Commit of the checkout: git if it works, else .git/HEAD (loose or packed refs)."""
    if shutil.which("git"):
        try:
            res = subprocess.run(git_command(app_dir, "rev-parse", "HEAD"), cwd=app_dir,
                                 capture_output=True, text=True, timeout=5,
                                 creationflags=NO_WINDOW)
            sha = res.stdout.strip()
            if res.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha):
                return sha
        except (OSError, subprocess.SubprocessError):
            pass
    git_dir = os.path.join(app_dir, ".git")
    try:
        with open(os.path.join(git_dir, "HEAD"), "r", encoding="utf-8") as f:
            head = f.read().strip()
        if re.fullmatch(r"[0-9a-f]{40}", head):
            return head
        if head.startswith("ref:"):
            ref = head[4:].strip()
            ref_path = os.path.join(git_dir, *ref.split("/"))
            if os.path.exists(ref_path):
                with open(ref_path, "r", encoding="utf-8") as rf:
                    sha = rf.read().strip()
                    return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else ""
            packed = os.path.join(git_dir, "packed-refs")
            if os.path.exists(packed):
                with open(packed, "r", encoding="utf-8") as pf:
                    for line in pf:
                        parts = line.strip().split(" ", 1)
                        if len(parts) == 2 and parts[1] == ref and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
                            return parts[0]
    except OSError:
        pass
    return ""


def git_branch(app_dir: str) -> str:
    """Current branch name ('' when detached or unknown)."""
    try:
        with open(os.path.join(app_dir, ".git", "HEAD"), "r", encoding="utf-8") as f:
            head = f.read().strip()
        if head.startswith("ref: refs/heads/"):
            return head[len("ref: refs/heads/"):]
    except OSError:
        pass
    return ""


def get_local_version_info() -> Dict[str, Any]:
    """{"version", "commit", "short_commit", "is_git", "display", ...} for this install."""
    app_dir = get_app_dir()
    data = _read_version_file(app_dir)
    info: Dict[str, Any] = {
        "version": str(data.get("version") or "0.0.0"),
        "date": str(data.get("date") or ""),
        "commit": "",
        "short_commit": "",
        "is_git": False,
        "is_source": not is_compiled(),
        "branch": "",
    }
    if info["is_source"]:
        if os.path.isdir(os.path.join(app_dir, ".git")):
            info["is_git"] = True
            info["branch"] = git_branch(app_dir)
            info["commit"] = _git_head(app_dir)
        # An archive update over a git checkout records the commit it really installed
        try:
            with open(os.path.join(app_dir, UPDATE_STATE_FILE), "r", encoding="utf-8") as f:
                state = json.load(f)
            installed = str(state.get("installed_commit", "")).strip()
            if installed and (not info["commit"] or state.get("replaced_over_head") == info["commit"]):
                info["commit"] = installed
                info["from_update_state"] = True
        except (OSError, ValueError):
            pass
        info["short_commit"] = info["commit"][:7]
    info["display"] = version_display(info["version"], info["short_commit"])
    info["edition"] = edition(info["is_source"])
    info["edition_label"] = edition_label(info["is_source"], info["is_git"])
    return info


def version_display(version: str, short_commit: str = "") -> str:
    """'1.2.1' for releases, '1.2.1 (ad0390c)' for source checkouts."""
    v = (version or "").lstrip("vV") or "?"
    return f"{v} ({short_commit})" if short_commit else v


# ── GitHub ──────────────────────────────────────────────────────────────────
def _get_json(url: str, timeout: float) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_error_text(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 403:
            return "GitHub is limiting requests right now. Try again in a few minutes."
        if e.code == 404:
            return "Not found on GitHub."
        return f"GitHub answered {e.code}."
    if isinstance(e, urllib.error.URLError):
        return "Couldn't reach GitHub. Check your internet connection."
    return str(e) or e.__class__.__name__


def find_matching_release_asset(assets: list, platform: Optional[str] = None) -> Dict[str, Any]:
    """The release file for this platform: {"url", "name", "size", "sha256"}, or {} if there's none."""
    plat = platform or platform_key()
    best, best_score = {}, 0
    for a in assets or []:
        name = str(a.get("name", "")).lower()
        url = a.get("browser_download_url", "")
        if not url:
            continue
        score = 0
        if plat == "windows":
            if "windows" in name or re.search(r"\bwin(64|32)?\b", name.replace("-", " ").replace("_", " ")):
                score += 20
            if any(k in name for k in ("linux", "darwin", "macos", "osx")):
                score -= 50
            score += 8 if name.endswith(".zip") else 0
        elif plat == "linux":
            if "linux" in name:
                score += 20
            if any(k in name for k in ("windows", "darwin", "macos", "osx")) or name.endswith(".exe"):
                score -= 50
            score += 8 if name.endswith((".tar.gz", ".tgz")) else (3 if name.endswith(".zip") else -50)
        if score > best_score:
            digest = str(a.get("digest") or "")
            best_score = score
            best = {
                "url": url,
                "name": a.get("name", ""),
                "size": int(a.get("size") or 0),
                "sha256": digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else "",
            }
    return best


def check_for_updates(timeout: float = 8) -> Dict[str, Any]:
    """Ask GitHub whether this install can be updated. Never raises.

    Result keys: update_available, kind ("release" | "source-git" | "source-archive"),
    local_version, local_display, remote_version, remote_display, commits_behind, notes,
    download_url, sha256, size, commit, branch, published_at, release_url, message, error.
    """
    local = get_local_version_info()
    res: Dict[str, Any] = {
        "update_available": False,
        "local_version": local["version"],
        "local_display": local["display"],
        "edition": local["edition"],
        "edition_label": local["edition_label"],
        "remote_version": "",
        "remote_display": "",
        "commits_behind": 0,
        "notes": "",
        "download_url": "",
        "sha256": "",
        "size": 0,
        "commit": "",
        "branch": GITHUB_BRANCH,
        "published_at": "",
        "release_url": "",
        "message": "",
        "error": "",
        "kind": "release" if not local["is_source"] else ("source-git" if local["is_git"] else "source-archive"),
    }
    base = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
    try:
        if not local["is_source"]:
            return _check_release(res, local, base, timeout)
        return _check_source(res, local, base, timeout)
    except Exception as e:  # network / JSON trouble: report, never crash the app
        res["error"] = _http_error_text(e)
        return res


def _check_release(res: Dict[str, Any], local: Dict[str, Any], base: str, timeout: float) -> Dict[str, Any]:
    data = _get_json(f"{base}/releases/latest", timeout)
    tag = str(data.get("tag_name", "")).strip()
    res.update({
        "remote_version": tag.lstrip("vV"),
        "remote_display": tag.lstrip("vV"),
        "notes": data.get("body", "") or "",
        "published_at": data.get("published_at", "") or "",
        "release_url": data.get("html_url", "") or "",
    })
    if not is_newer(tag, local["version"]):
        res["message"] = "You're running the latest version."
        return res
    asset = find_matching_release_asset(data.get("assets", []))
    if not asset:
        # Announcing an update with nothing to install would just close the app (#report: no Linux build)
        res["message"] = f"Version {res['remote_version']} is out, but it has no download for this system yet."
        return res
    res.update({"update_available": True, "download_url": asset["url"], "sha256": asset["sha256"], "size": asset["size"]})
    return res


def _check_source(res: Dict[str, Any], local: Dict[str, Any], base: str, timeout: float) -> Dict[str, Any]:
    head = _get_json(f"{base}/commits/{GITHUB_BRANCH}", timeout)
    remote_sha = str(head.get("sha", ""))
    res["commit"] = remote_sha
    res["published_at"] = head.get("commit", {}).get("committer", {}).get("date", "") or ""
    res["release_url"] = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
    try:
        remote_ver = str(_get_json(f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{remote_sha}/version.json", timeout).get("version", ""))
    except Exception:
        remote_ver = ""
    res["remote_version"] = remote_ver or local["version"]
    res["download_url"] = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/{remote_sha}.zip"

    local_sha = local["commit"]
    if local_sha and local_sha == remote_sha:
        res["message"] = "You're running the latest version."
        res["remote_display"] = version_display(res["remote_version"], remote_sha[:7])
        return res

    behind = None
    if local_sha:
        try:
            cmp = _get_json(f"{base}/compare/{local_sha}...{GITHUB_BRANCH}", timeout)
            status = cmp.get("status")
            if status == "ahead":          # main has commits this install doesn't
                behind = int(cmp.get("ahead_by") or 0)
                msgs = [c.get("commit", {}).get("message", "").splitlines()[0] for c in (cmp.get("commits") or [])]
                res["notes"] = "\n".join(f"• {m}" for m in reversed(msgs[-12:]) if m)
            elif status in ("identical", "behind"):
                behind = 0                 # same, or this install has extra commits
            else:                          # "diverged": local work on top of an older base
                res["message"] = "Your copy has its own changes on top of an older version; update it with git."
                return res
        except urllib.error.HTTPError as e:
            if e.code != 404:              # 404: a local-only commit GitHub doesn't know
                raise
    if behind is None:
        behind = 1 if is_newer(remote_ver, local["version"]) else 0

    if behind <= 0:
        res["message"] = "You're running the latest version."
        return res
    if local["is_git"] and local.get("branch") not in ("", GITHUB_BRANCH):
        res["message"] = f"You're on the '{local['branch']}' branch; switch to '{GITHUB_BRANCH}' or update with git."
        return res

    res["update_available"] = True
    res["commits_behind"] = behind
    if is_newer(res["remote_version"], local["version"]):
        res["remote_display"] = res["remote_version"]
    else:
        res["remote_display"] = f"{res['remote_version']} + {behind} new change{'s' if behind != 1 else ''}"
    if not res["notes"]:
        res["notes"] = head.get("commit", {}).get("message", "") or ""
    return res


# ── Archives ────────────────────────────────────────────────────────────────
def safe_extract(archive_path: str, dest_dir: str) -> None:
    """Extract a .zip / .tar.* refusing anything that would land outside dest_dir
    (absolute paths, '..', links pointing outside, device files). Raises ValueError."""
    dest = os.path.realpath(dest_dir)

    def inside(path: str) -> bool:
        p = os.path.realpath(os.path.join(dest, path))
        return p == dest or p.startswith(dest + os.sep)

    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as zf:
            bad = zf.testzip()
            if bad:
                raise ValueError(f"The download is damaged ({bad}).")
            for m in zf.infolist():
                if os.path.isabs(m.filename) or m.filename.startswith(("/", "\\")) or not inside(m.filename):
                    raise ValueError(f"Unsafe path in the update package: {m.filename}")
            zf.extractall(dest)
        return
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as tf:
            members = []
            for m in tf.getmembers():
                if m.isdev() or m.isfifo():
                    continue
                if os.path.isabs(m.name) or not inside(m.name):
                    raise ValueError(f"Unsafe path in the update package: {m.name}")
                if m.issym() and (os.path.isabs(m.linkname) or not inside(os.path.join(os.path.dirname(m.name), m.linkname))):
                    raise ValueError(f"Unsafe link in the update package: {m.name}")
                if m.islnk() and not inside(m.linkname):
                    raise ValueError(f"Unsafe link in the update package: {m.name}")
                members.append(m)
            if hasattr(tarfile, "data_filter"):        # Python 3.12+ and security backports
                tf.extractall(dest, members=members, filter="data")
            else:
                tf.extractall(dest, members=members)
        return
    raise ValueError("The download isn't a zip or tar archive.")


# ── Starting the updater ────────────────────────────────────────────────────
def build_update_plan(info: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the updater needs, so it never has to guess."""
    app_dir = get_app_dir()
    return {
        "version": 2,
        "target_dir": app_dir,
        "pid": os.getpid(),
        "kind": info.get("kind", "release"),
        "is_source": not is_compiled(),
        "download_url": info.get("download_url", ""),
        "sha256": info.get("sha256", ""),
        "size": int(info.get("size") or 0),
        "commit": info.get("commit", ""),
        "branch": info.get("branch", GITHUB_BRANCH),
        "from_display": info.get("local_display", ""),
        "edition": info.get("edition") or edition(not is_compiled()),
        "edition_label": info.get("edition_label") or edition_label(not is_compiled()),
        "to_display": info.get("remote_display", "") or info.get("remote_version", ""),
        "to_version": info.get("remote_version", ""),
        "notes": (info.get("notes", "") or "")[:6000],
        "python_exe": sys.executable if not is_compiled() else "",
        "app_executable": os.path.abspath(sys.executable) if is_compiled() else "",
        "repo_url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git",
        "created": time.time(),
    }


def updater_command(app_dir: str, python_exe: str = "") -> List[str]:
    """How to start the updater for this install."""
    if is_compiled():
        exe = os.path.join(app_dir, "updater.exe" if sys.platform == "win32" else "updater")
        if not os.path.exists(exe):
            raise FileNotFoundError("The updater program is missing from the install folder.")
        return [exe]
    script = os.path.join(app_dir, "updater.py")
    if not os.path.exists(script):
        raise FileNotFoundError("updater.py is missing from the app folder.")
    return [gui_python(python_exe or sys.executable), script]


def gui_python(python_exe: str) -> str:
    """On Windows prefer pythonw.exe next to python.exe, so no console window pops up."""
    if sys.platform == "win32" and python_exe.lower().endswith("python.exe"):
        cand = python_exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(cand):
            return cand
    return python_exe


# Console tools (git, pip) started from the window app: no console window flashing up on Windows
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def detached_popen_kwargs() -> Dict[str, Any]:
    kw: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    return kw


def launch_updater(info: Dict[str, Any]) -> str:
    """Write the update plan to a private folder and start the updater. Returns the plan path.
    The caller then closes the app normally; the updater waits for it to exit."""
    if not info.get("update_available"):
        raise RuntimeError("There's no update to install.")
    plan = build_update_plan(info)
    plan_dir = tempfile.mkdtemp(prefix="pawchive_plan_")
    plan_path = os.path.join(plan_dir, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    cmd = updater_command(plan["target_dir"], plan["python_exe"]) + ["--plan", plan_path]
    subprocess.Popen(cmd, cwd=plan["target_dir"], **detached_popen_kwargs())
    return plan_path


def cleanup_update_leftovers(app_dir: Optional[str] = None, max_age_hours: float = 12.0) -> None:
    """Remove old update backups and stale temp folders. Only touches the updater's own folders."""
    app_dir = app_dir or get_app_dir()
    backup_root = os.path.join(app_dir, BACKUP_DIR)
    if os.path.isdir(backup_root):
        for name in os.listdir(backup_root):
            shutil.rmtree(os.path.join(backup_root, name), ignore_errors=True)
        try:
            os.rmdir(backup_root)
        except OSError:
            pass
    tmp = tempfile.gettempdir()
    cutoff = time.time() - max_age_hours * 3600
    try:
        for name in os.listdir(tmp):
            if name.startswith(("pawchive_plan_", "pawchive_update_", "pawchive_updater_run_")):
                p = os.path.join(tmp, name)
                try:
                    if os.path.getmtime(p) < cutoff:
                        if os.path.isdir(p):
                            shutil.rmtree(p, ignore_errors=True)
                        else:
                            os.remove(p)
                except OSError:
                    pass
    except OSError:
        pass
