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

    # A different settings folder (the test suite uses this so it never touches real settings)
    env_dir = os.environ.get("PAWCHIVE_CONFIG_DIR")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return env_dir

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


def migrate_legacy_files(new_dir: str, legacy_dir: str, names) -> None:
    """Copies files from an older storage location into new_dir when new_dir doesn't have them yet.

    Some settings used to be kept next to the code (inside "_internal" in packaged builds, or in a
    folder that isn't writable for system-wide Linux installs) instead of the app's config folder.
    """
    import shutil
    try:
        if not legacy_dir or os.path.normcase(os.path.abspath(legacy_dir)) == os.path.normcase(os.path.abspath(new_dir)):
            return
        for name in names:
            src = os.path.join(legacy_dir, name)
            dst = os.path.join(new_dir, name)
            if os.path.isfile(src) and not os.path.exists(dst):
                os.makedirs(new_dir, exist_ok=True)
                shutil.copy2(src, dst)
    except Exception:
        pass


def get_data_dir() -> str:
    """
    Resolve data/state directory:
    - On Windows: `<base_dir>`.
    - On Linux/macOS: `$XDG_DATA_HOME/pawchive` (defaults to `~/.local/share/pawchive`),
      or `<base_dir>` if running from source and writable.
    """
    env_dir = os.environ.get("PAWCHIVE_DATA_DIR")
    if env_dir:
        os.makedirs(env_dir, exist_ok=True)
        return env_dir

    base_dir = get_base_dir()

    if sys.platform == "win32":
        return base_dir

    if not getattr(sys, "frozen", False) and _is_dir_writable(base_dir):
        return base_dir

    xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    app_data = os.path.join(xdg_data, "pawchive")
    os.makedirs(app_data, exist_ok=True)
    return app_data


def get_app_root() -> str:
    """The folder the user sees: next to the .exe / binary, or the folder holding main.py."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_logs_dir() -> str:
    """Resolve directory where log files should be written.

    Always `logs/` next to the app (the .exe, the Linux binary or main.py). Only when that folder
    can't be written (a system-wide or read-only install) do logs go to the user's folder instead.
    """
    local_logs = os.path.join(get_app_root(), "logs")
    if _is_dir_writable(local_logs):
        return local_logs

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        logs_dir = os.path.join(base, "Pawchive Downloader", "logs")
    else:
        xdg_state = os.environ.get("XDG_STATE_HOME")
        if xdg_state:
            logs_dir = os.path.join(xdg_state, "pawchive", "logs")
        else:
            logs_dir = os.path.join(get_data_dir(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def get_legacy_logs_dirs() -> list:
    """Folders older versions wrote logs to (their files are moved into the new layout)."""
    dirs = [os.path.join(get_base_dir(), "logs")]          # Windows builds: _internal/logs
    if sys.platform != "win32" and getattr(sys, "frozen", False):   # Linux builds used the user's folder
        xdg_state = os.environ.get("XDG_STATE_HOME")
        if xdg_state:
            dirs.append(os.path.join(xdg_state, "pawchive", "logs"))
        xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        dirs.append(os.path.join(xdg_data, "pawchive", "logs"))
    return dirs


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


def unique_name_in_batch(folder: str, name: str, taken: set) -> str:
    """The path for `name` in `folder` that no other file of the same batch uses yet.

    Albums (Bunkr, Telegram…) can hold different files with the same name; giving them all the
    same path made the second one count as "already downloaded" (or overwrite / mix with the
    first). Later ones become "name (2).ext", "name (3).ext"… Only names used in this batch are
    avoided, not files already on disk, so running the same album again finds its own files.
    `taken` holds normcase'd paths and is updated.
    """
    stem, ext = os.path.splitext(name)
    path = os.path.join(folder, name)
    n = 2
    while os.path.normcase(path) in taken:
        path = os.path.join(folder, f"{stem} ({n}){ext}")
        n += 1
    taken.add(os.path.normcase(path))
    return path
