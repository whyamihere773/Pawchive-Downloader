"""
Cross-Platform Path Resolver for Pawchive Downloader
Provides clean, transparent resolution between Windows portable folders and
Linux / macOS XDG Base Directory specifications (~/.config, ~/.local/share).
"""

import os
import sys
from typing import Optional


def get_base_dir() -> str:
    """Return the root application directory."""
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS") and os.path.exists(os.path.join(sys._MEIPASS, "qml")):
            return sys._MEIPASS
        cand = os.path.join(os.path.dirname(sys.executable), "_internal")
        return cand if os.path.exists(cand) else os.path.dirname(sys.executable)
    # Check if installed system-wide on Linux (e.g. via PKGBUILD / pacman)
    if sys.platform != "win32" and os.path.exists("/usr/share/pawchive/qml"):
        return "/usr/share/pawchive"
    # When running from source, root is the project root (parent of core/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_dir_writable(path: str) -> bool:
    """Check if a directory is writable or can be created."""
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, ".write_test")
        with open(test_file, "w") as f:
            f.write("1")
        os.remove(test_file)
        return True
    except Exception:
        return False


def get_config_dir(custom_dir: Optional[str] = None) -> str:
    """
    Resolve the configuration directory:
    - If custom_dir is provided, use it.
    - On Windows: prefers portable `<base_dir>/config`.
    - On Linux/macOS:
      - If running from source and `<base_dir>/config` is writable, use it.
      - Otherwise, use `$XDG_CONFIG_HOME/pawchive` (defaults to `~/.config/pawchive`).
    """
    if custom_dir:
        os.makedirs(custom_dir, exist_ok=True)
        return custom_dir

    base_dir = get_base_dir()
    local_cfg = os.path.join(base_dir, "config")

    if sys.platform == "win32":
        os.makedirs(local_cfg, exist_ok=True)
        return local_cfg

    # On Linux / POSIX:
    # If running from source (not frozen) and local_cfg is writable, keep local config
    if not getattr(sys, "frozen", False) and _is_dir_writable(local_cfg):
        return local_cfg

    # Use standard XDG config directory
    xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    app_config = os.path.join(xdg_config, "pawchive")
    os.makedirs(app_config, exist_ok=True)
    return app_config


def get_data_dir() -> str:
    """
    Resolve data/state directory:
    - On Windows: `<base_dir>`.
    - On Linux/macOS: `$XDG_DATA_HOME/pawchive` (defaults to `~/.local/share/pawchive`),
      or `<base_dir>` if running from source and writable.
    """
    base_dir = get_base_dir()

    if sys.platform == "win32":
        return base_dir

    if not getattr(sys, "frozen", False) and _is_dir_writable(base_dir):
        return base_dir

    xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    app_data = os.path.join(xdg_data, "pawchive")
    os.makedirs(app_data, exist_ok=True)
    return app_data


def get_logs_dir() -> str:
    """Resolve directory where log files should be written."""
    base_dir = get_base_dir()
    local_logs = os.path.join(base_dir, "logs")

    if sys.platform == "win32":
        os.makedirs(local_logs, exist_ok=True)
        return local_logs

    if not getattr(sys, "frozen", False) and _is_dir_writable(local_logs):
        return local_logs

    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        logs_dir = os.path.join(xdg_state, "pawchive", "logs")
    else:
        app_data = get_data_dir()
        logs_dir = os.path.join(app_data, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def get_dependencies_dir() -> str:
    """Resolve directory where helper binaries (yt-dlp, 7za) reside or should be downloaded."""
    base_dir = get_base_dir()
    local_deps = os.path.join(base_dir, "dependencies")

    if sys.platform == "win32":
        os.makedirs(local_deps, exist_ok=True)
        return local_deps

    if not getattr(sys, "frozen", False) and _is_dir_writable(local_deps):
        return local_deps

    app_data = get_data_dir()
    deps_dir = os.path.join(app_data, "bin")
    os.makedirs(deps_dir, exist_ok=True)
    return deps_dir
