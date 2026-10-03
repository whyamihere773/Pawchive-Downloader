"""
Pawchive Downloader — update installer (no Qt; used by the updater window and console mode).

Safety rules:
  • the app must be closed first (waits for its process; never installs over a running app)
  • downloads are checked (sha256 from GitHub for releases, archive integrity for source)
  • archives can't write outside their folder
  • installing is a transaction: every file it replaces or removes is moved to .update_backup
    first; any failure moves everything back, so the app is never left half-updated
  • only files a previous update installed are ever removed; unknown files (anything the user
    put in the folder) are never touched, and protected folders (config, downloads, logs, data…)
    are skipped entirely
  • git checkouts are only fast-forwarded; local changes are never overwritten without asking

Frozen builds swap the very files the updater runs from, so everything it needs is imported
up front (nothing may be loaded lazily from the install folder once the swap starts).
"""

import bz2  # noqa: F401  (tar.bz2 support, imported before files are swapped)
import encodings.idna  # noqa: F401  (hostname encoding for HTTPS, same reason)
import gzip  # noqa: F401
import hashlib
import json
import lzma  # noqa: F401
import os
import shutil
import ssl  # noqa: F401
import stat
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from core.log_utils import redact, safe_filename, system_summary
from services import update_service as us

# ── Results & reporting ─────────────────────────────────────────────────────


class UpdateError(Exception):
    """A failure with a code the UI can act on."""

    def __init__(self, code: str, message: str, details: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


# Codes: cancelled, app_running, network, verify, extract, disk, locked, permission,
#        local_changes, diverged, wrong_branch, git_failed, unknown

class Reporter:
    """Override what you need. Called from the worker thread."""

    def step(self, step_id: str, state: str) -> None:  # state: active | done | failed | skipped
        pass

    def progress(self, fraction: Optional[float], detail: str = "") -> None:  # None = unknown
        pass

    def log(self, message: str) -> None:
        pass

    def cancelled(self) -> bool:
        return False

    def install_started(self) -> None:  # from here on the update can't be cancelled
        pass


STEPS_ARCHIVE = [
    ("wait", "Waiting for Pawchive to close"),
    ("download", "Downloading the update"),
    ("verify", "Checking the download"),
    ("install", "Installing new files"),
    ("deps", "Updating components"),
    ("finish", "Finishing up"),
]
STEPS_GIT = [
    ("wait", "Waiting for Pawchive to close"),
    ("download", "Getting the latest changes"),
    ("install", "Applying the changes"),
    ("deps", "Updating components"),
    ("finish", "Finishing up"),
]


def steps_for(plan: Dict[str, Any]) -> List[Tuple[str, str]]:
    return STEPS_GIT if uses_git(plan) else STEPS_ARCHIVE


def uses_git(plan: Dict[str, Any]) -> bool:
    return (plan.get("kind") == "source-git" and not plan.get("force_archive")
            and os.path.isdir(os.path.join(plan["target_dir"], ".git")) and bool(shutil.which("git")))


# ── Log file ────────────────────────────────────────────────────────────────
class UpdateLog:
    """One log file per updater run: <app>/logs/updater/<date_time> (<from> to <to>).log
    (or the temp folder when the app folder can't be written). Never deleted automatically."""

    def __init__(self, target_dir: str, plan: Optional[Dict[str, Any]] = None):
        plan = plan or {}
        self.path = ""
        self._lock = threading.Lock()
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        frm = safe_filename(str(plan.get("from_display") or "").replace("(", "").replace(")", ""))
        to = str(plan.get("to_version") or "")
        if plan.get("commit") and plan.get("is_source"):
            to = f"{to} {str(plan['commit'])[:7]}".strip()
        to = safe_filename(to)
        label = f" ({frm} to {to})" if frm and to else (f" (to {to})" if to else "")
        for folder in (os.path.join(target_dir, "logs", "updater"),
                       os.path.join(tempfile.gettempdir(), "Pawchive updater logs")):
            try:
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, f"{stamp}{label}.log")
                n = 2
                while os.path.exists(path):
                    path = os.path.join(folder, f"{stamp}{label} ({n}).log")
                    n += 1
                with open(path, "a", encoding="utf-8") as f:
                    f.write(self._header(plan))
                self.path = path
                break
            except OSError:
                continue

    @staticmethod
    def _header(plan: Dict[str, Any]) -> str:
        lines = [
            "=" * 72,
            f"Pawchive Downloader updater · {plan.get('from_display') or '?'} -> {plan.get('to_display') or plan.get('to_version') or 'latest'}"
            + (f" · {plan['edition_label']}" if plan.get("edition_label") else ""),
            f"Started {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"System: {system_summary()}",
            f"Python {sys.version.split()[0]}",
            "=" * 72,
        ]
        return "\n".join(lines) + "\n"

    def write(self, message: str) -> None:
        if not self.path:
            return
        with self._lock:
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {redact(str(message))}\n")
            except OSError:
                pass


# ── Waiting for the app ─────────────────────────────────────────────────────
def process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        SYNCHRONIZE = 0x00100000
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        WAIT_TIMEOUT = 0x102
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            # ERROR_ACCESS_DENIED (5): exists but belongs to someone else; anything else: gone
            return k32.GetLastError() == 5
        try:
            return k32.WaitForSingleObject(h, 0) == WAIT_TIMEOUT
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    try:  # a zombie has exited but isn't reaped yet
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as f:
            return f.read().rsplit(")", 1)[-1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def wait_for_exit(pid: int, timeout: float, rep: Reporter) -> None:
    start = time.time()
    while process_running(pid):
        if rep.cancelled():
            raise UpdateError("cancelled", "The update was cancelled.")
        waited = time.time() - start
        if waited > timeout:
            raise UpdateError("app_running", "Pawchive is still running. Close it completely, then try again.")
        rep.progress(None, f"Waiting for Pawchive to close… ({int(waited)}s)" if waited >= 2 else "Waiting for Pawchive to close…")
        time.sleep(0.25)


# ── Download & checks ───────────────────────────────────────────────────────
def _fmt_mb(n: float) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


def download(url: str, dest: str, expected_sha256: str, expected_size: int, rep: Reporter, log: UpdateLog) -> None:
    last_err: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            _download_once(url, dest, expected_sha256, expected_size, rep)
            return
        except UpdateError:
            raise
        except Exception as e:  # network trouble: retry a couple of times
            last_err = e
            log.write(f"download attempt {attempt} failed: {e!r}")
            if attempt < 3:
                for i in range(attempt * 3, 0, -1):
                    if rep.cancelled():
                        raise UpdateError("cancelled", "The update was cancelled.")
                    rep.progress(None, f"Connection problem, retrying in {i}s…")
                    time.sleep(1)
    msg = us._http_error_text(last_err) if last_err else "The download failed."
    raise UpdateError("network", "The update couldn't be downloaded. " + msg, repr(last_err))


def _download_once(url: str, dest: str, expected_sha256: str, expected_size: int, rep: Reporter) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": us.USER_AGENT})
    sha = hashlib.sha256()
    done = 0
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0) or expected_size
        start = last = time.time()
        while True:
            if rep.cancelled():
                raise UpdateError("cancelled", "The update was cancelled.")
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            out.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            now = time.time()
            if now - last >= 0.2:
                last = now
                speed = done / max(0.001, now - start)
                if total:
                    eta = int((total - done) / max(1.0, speed))
                    eta_s = f"{eta}s" if eta < 90 else f"{eta // 60}m {eta % 60}s"
                    rep.progress(min(1.0, done / total), f"{_fmt_mb(done)} of {_fmt_mb(total)}  ·  {_fmt_mb(speed)}/s  ·  {eta_s} left")
                else:  # GitHub's source archives don't say how big they are
                    rep.progress(None, f"{_fmt_mb(done)} downloaded  ·  {_fmt_mb(speed)}/s")
    if expected_size and done != expected_size:
        raise OSError(f"incomplete download ({done} of {expected_size} bytes)")
    if expected_sha256 and sha.hexdigest().lower() != expected_sha256.lower():
        raise UpdateError("verify", "The download didn't match GitHub's checksum, so it wasn't installed.",
                          f"expected {expected_sha256}, got {sha.hexdigest()}")


def prepare(archive: str, work_dir: str, plan: Dict[str, Any], rep: Reporter) -> str:
    """Extract safely and return the folder holding the new app files."""
    stage = os.path.join(work_dir, "staging")
    os.makedirs(stage, exist_ok=True)
    rep.progress(None, "Unpacking…")
    try:
        us.safe_extract(archive, stage)
    except ValueError as e:
        raise UpdateError("verify", str(e)) from e
    except (OSError, EOFError) as e:
        raise UpdateError("verify", "The download is damaged. Try again.", repr(e)) from e
    root = stage
    entries = os.listdir(stage)
    if len(entries) == 1 and os.path.isdir(os.path.join(stage, entries[0])):
        root = os.path.join(stage, entries[0])
    # Sanity check: it has to look like Pawchive
    if plan.get("is_source"):
        ok = os.path.isfile(os.path.join(root, "main.py")) and os.path.isfile(os.path.join(root, "updater.py"))
    else:
        names = {n.lower() for n in os.listdir(root)}
        ok = "_internal" in names and any(n.endswith(".exe") or n in ("pawchive", "pawchive downloader") for n in names)
    if not ok:
        raise UpdateError("verify", "The download doesn't look like a Pawchive package, so it wasn't installed.")
    # ...and it has to be the same edition: a Linux install must never get the Windows build
    if not plan.get("is_source"):
        package = package_edition(root)
        mine = plan.get("edition") or us.edition(False)
        if package and mine in ("windows", "linux") and package != mine:
            raise UpdateError("verify", f"This download is the {package.capitalize()} build, but you're using the "
                                        f"{mine.capitalize()} build, so it wasn't installed.")
    return root


def package_edition(root: str) -> str:
    """'windows' or 'linux' from the program files in an unpacked build ('' if unclear)."""
    names = {n.lower() for n in os.listdir(root)}
    if "pawchive downloader.exe" in names:
        return "windows"
    if "pawchive" in names:
        return "linux"
    return ""


def _staged_files(stage_root: str) -> List[str]:
    """Relative paths ('/' separated) of everything to install. Links count as files."""
    out = []
    for root, dirs, files in os.walk(stage_root):
        rel_root = os.path.relpath(root, stage_root)
        rel_root = "" if rel_root == "." else rel_root.replace("\\", "/")
        if rel_root and us.is_protected(rel_root + "/x"):
            dirs[:] = []
            continue
        keep = []
        for d in dirs:
            full = os.path.join(root, d)
            rel = f"{rel_root}/{d}" if rel_root else d
            if os.path.islink(full):
                files.append(d)          # a linked folder is installed as a link
            elif not us.is_protected(rel + "/x"):
                keep.append(d)
        dirs[:] = keep
        for f in files:
            rel = f"{rel_root}/{f}" if rel_root else f
            if not us.is_protected(rel):
                out.append(rel)
    return sorted(set(out))


def _dir_size(path: str) -> int:
    total = 0
    for root, _d, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


# ── File transaction ────────────────────────────────────────────────────────
class FileTransaction:
    """Replaces files with a way back: old files are moved aside (a rename, which also works on
    files Windows still has open), and moved back if anything fails."""

    def __init__(self, target_dir: str, log: UpdateLog):
        self.target = target_dir
        self.backup = os.path.join(target_dir, us.BACKUP_DIR, time.strftime("%Y%m%d-%H%M%S"))
        self.moved: List[Tuple[str, str]] = []   # (original path, backup path)
        self.created: List[str] = []
        self.log = log

    def _move_aside(self, path: str) -> None:
        rel = os.path.relpath(path, self.target)
        dest = os.path.join(self.backup, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        last: Optional[Exception] = None
        for _ in range(8):                          # antivirus scanners hold files briefly
            try:
                os.replace(path, dest)
                self.moved.append((path, dest))
                return
            except PermissionError as e:
                last = e
                time.sleep(0.4)
            except OSError as e:
                last = e
                break
        code = "locked" if (sys.platform == "win32" and isinstance(last, PermissionError)) else "permission"
        raise UpdateError(code, "Some app files couldn't be replaced.", f"{rel}: {last!r}")

    def place(self, src: str, dst: str) -> None:
        if os.path.lexists(dst):
            if os.path.isdir(dst) and not os.path.islink(dst):
                raise UpdateError("unknown", "A folder is in the way of a new file.", dst)
            self._move_aside(dst)
        else:
            self.created.append(dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".pawchive-new"
        if os.path.lexists(tmp):
            os.remove(tmp)
        if os.path.islink(src):
            os.symlink(os.readlink(src), tmp)
        else:
            shutil.copy2(src, tmp)
        os.replace(tmp, dst)

    def remove(self, path: str) -> None:
        if os.path.lexists(path) and not (os.path.isdir(path) and not os.path.islink(path)):
            self._move_aside(path)

    def rollback(self) -> None:
        self.log.write(f"rolling back: {len(self.created)} new, {len(self.moved)} moved")
        for p in reversed(self.created):
            try:
                if os.path.lexists(p):
                    os.remove(p)
            except OSError as e:
                self.log.write(f"rollback: couldn't remove {p}: {e!r}")
        for orig, bak in reversed(self.moved):
            try:
                os.makedirs(os.path.dirname(orig), exist_ok=True)
                os.replace(bak, orig)
            except OSError as e:
                self.log.write(f"rollback: couldn't restore {orig}: {e!r}")
        self._drop_backup()

    def commit(self) -> None:
        self._drop_backup()

    def _drop_backup(self) -> None:
        shutil.rmtree(self.backup, ignore_errors=True)   # files Windows still holds stay; removed next start
        root = os.path.dirname(self.backup)
        try:
            os.rmdir(root)
        except OSError:
            pass


def _load_manifest(target: str) -> List[str]:
    try:
        with open(os.path.join(target, us.INSTALL_MANIFEST), "r", encoding="utf-8") as f:
            files = json.load(f).get("files", [])
        return [str(x) for x in files if isinstance(x, str)]
    except (OSError, ValueError, AttributeError):
        return []


def install_files(stage_root: str, plan: Dict[str, Any], rep: Reporter, log: UpdateLog) -> FileTransaction:
    target = plan["target_dir"]
    new_files = _staged_files(stage_root)
    # Only files the previous update installed can be stale; anything else in the folder is the user's
    stale = [r for r in set(_load_manifest(target)) - set(new_files) if not us.is_protected(r)]

    need = _dir_size(stage_root)
    try:
        free = shutil.disk_usage(target).free
        if free < need * 1.2 + 50 * 1024 * 1024:
            raise UpdateError("disk", f"Not enough free space: the update needs about {_fmt_mb(need * 1.2)}.")
    except OSError:
        pass

    tx = FileTransaction(target, log)
    total = max(1, len(new_files) + len(stale))
    try:
        for i, rel in enumerate(new_files, 1):
            tx.place(os.path.join(stage_root, *rel.split("/")), os.path.join(target, *rel.split("/")))
            if i % 25 == 0 or i == len(new_files):
                rep.progress(i / total, f"{i} of {len(new_files)} files")
        for rel in stale:
            tx.remove(os.path.join(target, *rel.split("/")))
        if sys.platform != "win32":
            for name in ("pawchive", "updater", "Pawchive Downloader", "7za", "yt-dlp"):
                p = os.path.join(target, name)
                if os.path.isfile(p) and not os.path.islink(p):
                    os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        with open(os.path.join(target, us.INSTALL_MANIFEST + ".tmp"), "w", encoding="utf-8") as f:
            json.dump({"version": plan.get("to_version", ""), "installed": time.time(), "files": new_files}, f)
        os.replace(os.path.join(target, us.INSTALL_MANIFEST + ".tmp"), os.path.join(target, us.INSTALL_MANIFEST))
    except UpdateError:
        tx.rollback()
        raise
    except OSError as e:
        tx.rollback()
        code = "disk" if getattr(e, "errno", None) == 28 else ("permission" if isinstance(e, PermissionError) else "unknown")
        raise UpdateError(code, "Installing failed, so your previous version was restored.", repr(e)) from e
    except BaseException:
        tx.rollback()
        raise
    log.write(f"installed {len(new_files)} files, removed {len(stale)} stale")
    return tx


def record_installed_commit(target: str, commit: str, log: UpdateLog) -> None:
    """After an archive update of a git checkout, .git still points at the old commit: note what
    was really installed so the app doesn't keep offering the same update."""
    if not commit or not os.path.isdir(os.path.join(target, ".git")):
        return
    head = us._git_head(target)
    try:
        with open(os.path.join(target, us.UPDATE_STATE_FILE), "w", encoding="utf-8") as f:
            json.dump({"installed_commit": commit, "replaced_over_head": head, "at": time.time()}, f)
    except OSError as e:
        log.write(f"couldn't record installed commit: {e!r}")


# ── Git checkouts ───────────────────────────────────────────────────────────
def _git(target: str, *args: str, timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(us.git_command(target, *args), cwd=target, capture_output=True, text=True, timeout=timeout,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), creationflags=us.NO_WINDOW)


def git_update(plan: Dict[str, Any], rep: Reporter, log: UpdateLog) -> str:
    """Fast-forward the checkout to GitHub's branch. Never merges, rebases or discards anything.
    With plan["stash_changes"], local edits are first put away with `git stash` (recoverable).
    Returns a note for the user ('' if none)."""
    note = ""
    target = plan["target_dir"]
    branch = plan.get("branch") or us.GITHUB_BRANCH
    current = us.git_branch(target)
    if current and current != branch:
        raise UpdateError("wrong_branch", f"Your copy is on the '{current}' branch, not '{branch}'.")
    status = _git(target, "status", "--porcelain", "--untracked-files=no")
    if status.returncode != 0:
        raise UpdateError("git_failed", "git couldn't read this folder.", status.stderr.strip())
    if status.stdout.strip():
        changed = len(status.stdout.strip().splitlines())
        if not plan.get("stash_changes"):
            raise UpdateError("local_changes", f"You've changed {changed} file{'s' if changed != 1 else ''} in the app folder.",
                              status.stdout.strip()[:2000])
        stash = _git(target, "stash", "push", "-m", f"Pawchive update {time.strftime('%Y-%m-%d %H:%M')}")
        log.write(f"git stash: {stash.returncode} {stash.stdout.strip()[:300]} {stash.stderr.strip()[:300]}")
        if stash.returncode != 0:
            raise UpdateError("git_failed", "Your changes couldn't be put aside with git stash.", stash.stderr.strip())
        note = "Your changes were saved with git stash. Run 'git stash pop' in the app folder to bring them back."
    rep.progress(None, "Contacting GitHub…")
    fetch = _git(target, "fetch", "--quiet", plan.get("repo_url") or "origin", branch, timeout=300)
    log.write(f"git fetch: {fetch.returncode} {fetch.stderr.strip()[:500]}")
    if fetch.returncode != 0:
        raise UpdateError("network", "The latest changes couldn't be downloaded.", fetch.stderr.strip())
    rep.step("download", "done")
    rep.install_started()
    rep.step("install", "active")
    rep.progress(None, "Applying the changes…")
    merge = _git(target, "merge", "--ff-only", "FETCH_HEAD", timeout=120)
    log.write(f"git merge --ff-only: {merge.returncode} {merge.stdout.strip()[:300]} {merge.stderr.strip()[:500]}")
    if merge.returncode != 0:
        raise UpdateError("diverged", "Your copy has its own commits, so it can't simply be moved to the new version.",
                          merge.stderr.strip())
    return note


# ── Dependencies ────────────────────────────────────────────────────────────
def find_uv() -> str:
    found = shutil.which("uv")
    if found:
        return found
    home = os.path.expanduser("~")
    for p in (os.path.join(home, ".local", "bin", "uv"), os.path.join(home, ".cargo", "bin", "uv"),
              os.path.join(home, ".local", "bin", "uv.exe"), os.path.join(home, ".cargo", "bin", "uv.exe")):
        if os.path.isfile(p):
            return p
    return ""


def install_requirements(target: str, python_exe: str, rep: Reporter, log: UpdateLog) -> str:
    """Install requirements.txt with uv (if installed) or pip, into the Python the app uses.
    Returns '' on success, otherwise a message for the user. Never forces packages into a
    system Python the distribution manages (PEP 668)."""
    req = os.path.join(target, "requirements.txt")
    if not os.path.exists(req) or not python_exe:
        return ""
    attempts = []
    uv = find_uv()
    if uv:
        attempts.append(("uv", [uv, "pip", "install", "--python", python_exe, "-r", req]))
    attempts.append(("pip", [python_exe, "-m", "pip", "install", "--disable-pip-version-check", "-r", req]))
    outputs = []
    for name, cmd in attempts:
        rep.progress(None, f"Installing components with {name}…")
        try:
            r = subprocess.run(cmd, cwd=target, capture_output=True, text=True, timeout=900,
                               creationflags=us.NO_WINDOW)
            out = (r.stderr or "") + "\n" + (r.stdout or "")
            log.write(f"{name}: exit {r.returncode}\n{out[-3000:]}")
            if r.returncode == 0:
                return ""
            outputs.append(out)
        except (OSError, subprocess.SubprocessError) as e:
            log.write(f"{name}: {e!r}")
            outputs.append(str(e))
    text = "\n".join(outputs).lower()
    if "externally-managed" in text or "externally managed" in text:
        return ("Your system manages this Python's packages, so new components weren't installed automatically. "
                "Run Pawchive from a virtual environment (python -m venv .venv, or uv venv), or install the "
                "packages in requirements.txt with your package manager.")
    if "no module named pip" in text and not uv:
        return "This Python has no pip. Install uv (docs.astral.sh/uv) or pip, then run: uv pip install -r requirements.txt"
    return "New components couldn't be installed. Run 'uv pip install -r requirements.txt' or 'pip install -r requirements.txt'."


# ── Relaunch ────────────────────────────────────────────────────────────────
def app_command(plan: Dict[str, Any]) -> List[str]:
    target = plan["target_dir"]
    if plan.get("is_source"):
        py = plan.get("python_exe") or sys.executable
        return [us.gui_python(py), os.path.join(target, "main.py")]
    exe = plan.get("app_executable", "")
    if not exe or not os.path.exists(exe):
        names = ["Pawchive Downloader.exe", "pawchive.exe"] if sys.platform == "win32" else ["pawchive", "Pawchive Downloader"]
        exe = next((os.path.join(target, n) for n in names if os.path.exists(os.path.join(target, n))), "")
    return [exe] if exe else []


def relaunch(plan: Dict[str, Any], log: UpdateLog) -> bool:
    cmd = app_command(plan)
    if not cmd:
        log.write("relaunch: app executable not found")
        return False
    try:
        subprocess.Popen(cmd, cwd=plan["target_dir"], **us.detached_popen_kwargs())
        log.write(f"relaunched: {cmd}")
        return True
    except OSError as e:
        log.write(f"relaunch failed: {e!r}")
        return False


# ── The whole update ────────────────────────────────────────────────────────
def run_update(plan: Dict[str, Any], rep: Reporter, log: UpdateLog, wait_timeout: float = 90) -> Dict[str, Any]:
    """Install the update described by plan. Returns {"ok", "code", "message", "details", "warning"}."""
    target = plan["target_dir"]
    work_dir = ""
    step = "wait"
    try:
        rep.step("wait", "active")
        if plan.get("pid") and not plan.get("no_wait"):
            wait_for_exit(int(plan["pid"]), wait_timeout, rep)
        time.sleep(0.5 if sys.platform != "win32" else 1.2)    # let Windows release file handles
        rep.step("wait", "done")
        us.cleanup_update_leftovers(target)

        git_note = ""
        if uses_git(plan):
            step = "download"
            rep.step("download", "active")
            git_note = git_update(plan, rep, log)
            rep.step("install", "done")
        else:
            step = "download"
            rep.step("download", "active")
            work_dir = tempfile.mkdtemp(prefix="pawchive_update_")
            archive = os.path.join(work_dir, "update.tar.gz" if ".tar" in plan["download_url"].lower() else "update.zip")
            download(plan["download_url"], archive, plan.get("sha256", ""), int(plan.get("size") or 0), rep, log)
            rep.step("download", "done")
            step = "verify"
            rep.step("verify", "active")
            stage_root = prepare(archive, work_dir, plan, rep)
            rep.step("verify", "done")
            if rep.cancelled():
                raise UpdateError("cancelled", "The update was cancelled.")
            step = "install"
            rep.install_started()
            rep.step("install", "active")
            tx = install_files(stage_root, plan, rep, log)
            tx.commit()
            if plan.get("is_source"):
                record_installed_commit(target, plan.get("commit", ""), log)
            rep.step("install", "done")

        warning = git_note
        step = "deps"
        if plan.get("is_source"):
            rep.step("deps", "active")
            deps_problem = install_requirements(target, plan.get("python_exe") or sys.executable, rep, log)
            warning = " ".join(x for x in (warning, deps_problem) if x)
            rep.step("deps", "failed" if deps_problem else "done")
        else:
            rep.step("deps", "skipped")
        step = "finish"
        rep.step("finish", "active")
        rep.progress(1.0, "Done")
        rep.step("finish", "done")
        log.write(f"update finished ok (warning: {warning!r})")
        return {"ok": True, "code": "", "message": "", "details": "", "warning": warning}
    except UpdateError as e:
        rep.step(step, "failed")
        log.write(f"update failed [{e.code}] {e.message} | {e.details}")
        return {"ok": False, "code": e.code, "message": e.message, "details": e.details, "warning": ""}
    except Exception as e:
        rep.step(step, "failed")
        log.write("update crashed:\n" + traceback.format_exc())
        return {"ok": False, "code": "unknown", "message": "Something went wrong, and nothing was changed.",
                "details": repr(e), "warning": ""}
    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
