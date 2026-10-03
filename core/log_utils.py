"""
Helpers shared by the app's logger and the updater's log (standard library only).

- redact(): hides secrets before anything reaches a log file, because users attach logs to
  public bug reports: MEGA decryption keys, tokens/passwords in URLs, and the home folder
  (which contains the user's account name).
- system_summary(): one line describing the OS, for log headers.
"""

import os
import platform
import re
import sys

_SECRET_PATTERNS = [
    # MEGA: everything after '#' is the decryption key (new and old link formats)
    (re.compile(r"(mega(?:\.co)?\.nz/(?:file|folder|embed)/[A-Za-z0-9_-]+)#[A-Za-z0-9_-]+", re.I), r"\1#<key hidden>"),
    (re.compile(r"(mega(?:\.co)?\.nz/#F?!?[A-Za-z0-9_-]+!)[A-Za-z0-9_-]+", re.I), r"\1<key hidden>"),
    # user:password@ in proxy and other URLs
    (re.compile(r"(\b[a-z][a-z0-9+.-]*://)[^/\s:@'\"]+:[^/\s@'\"]+@", re.I), r"\1<login hidden>@"),
    # Tokens, signatures and passwords passed in URLs
    (re.compile(r"([?&](?:access_token|token|auth|key|api_key|apikey|session|sessionid|sig|signature|"
                r"password|pass|pwd|secret|hash)=)[^&#\s'\"]+", re.I), r"\1<hidden>"),
]


def _home_patterns():
    home = os.path.expanduser("~")
    if not home or len(home.rstrip("\\/")) < 4:      # "~" unresolved or a drive root
        return []
    flags = re.I if sys.platform == "win32" else 0
    variants = {home, home.replace("\\", "/")}
    return [re.compile(re.escape(v) + r"(?=[\\/]|$|[\s'\"])", flags) for v in variants]


_HOME_PATTERNS = _home_patterns()


def redact(text: str) -> str:
    """Hide secrets and the home folder in a log line."""
    if not text:
        return text
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    for pattern in _HOME_PATTERNS:
        text = pattern.sub("~", text)
    return text


def _linux_distro() -> str:
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "Linux"


def system_summary() -> str:
    """'Windows 11 (10.0.26200) AMD64' / 'Ubuntu 22.04.4 LTS · kernel 6.5.0 · x86_64 · wayland (KDE)'."""
    try:
        if sys.platform == "win32":
            return f"Windows {platform.release()} ({platform.version()}) {platform.machine()}"
        if sys.platform.startswith("linux"):
            parts = [_linux_distro(), f"kernel {platform.release()}", platform.machine()]
            session = os.environ.get("XDG_SESSION_TYPE", "")
            desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
            if session or desktop:
                parts.append(f"{session or '?'}{f' ({desktop})' if desktop else ''}")
            return " · ".join(p for p in parts if p)
        return f"{platform.system()} {platform.release()} {platform.machine()}"
    except Exception:
        return sys.platform


def safe_filename(text: str) -> str:
    """Make text usable in a file name on Windows and Linux."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text or "").strip(" .")
    return re.sub(r"\s+", " ", text)
