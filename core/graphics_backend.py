"""
Cross-platform Qt Quick graphics backend negotiation & safe software fallback.

Prevents fatal SIGABRT crashes on Linux/Wayland/X11 systems (e.g. Arch/CachyOS,
headless VMs, mismatched Mesa/NVIDIA drivers) where Qt Quick's OpenGL/EGL RHI
context creation would otherwise call qFatal() and abort the process.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Callable, List, Optional, Tuple


def _read_software_render_setting() -> bool:
    """Reads optional `"software_render": true` from settings.json before Qt initializes."""
    try:
        from core.path_utils import get_config_dir
        path = os.path.join(get_config_dir(), "settings.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return bool(data.get("software_render", False))
    except Exception:
        pass
    return False


def parse_software_render_args(argv: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
    """
    Detects `--software-render` CLI flag, `PAWCHIVE_SOFTWARE_RENDER=1`,
    `QT_QUICK_BACKEND=software`, or `settings.json`'s `software_render` flag.
    Returns `(force_software, cleaned_argv)` with `--software-render` removed so Qt
    does not log unknown-option warnings.
    """
    raw = list(sys.argv if argv is None else argv)
    cleaned: List[str] = []
    flag_seen = False
    for idx, arg in enumerate(raw):
        if idx > 0 and arg in ("--software-render", "--software-rendering"):
            flag_seen = True
            continue
        cleaned.append(arg)

    env_sw = (
        os.environ.get("PAWCHIVE_SOFTWARE_RENDER", "").strip().lower() in ("1", "true", "yes")
        or os.environ.get("QT_QUICK_BACKEND", "").strip().lower() == "software"
    )
    force_sw = flag_seen or env_sw or _read_software_render_setting()
    return force_sw, cleaned


def probe_opengl_available() -> bool:
    """
    Non-fatal OpenGL/EGL probe using QOpenGLContext + QOffscreenSurface.
    Unlike QQuickWindow's RHI initialization (which calls qFatal/SIGABRT on failure),
    QOpenGLContext.create() cleanly returns False when EGL/GLX/DRI cannot initialize.
    """
    try:
        from PySide6.QtGui import QOffscreenSurface, QOpenGLContext

        ctx = QOpenGLContext()
        if not ctx.create():
            return False

        surface = QOffscreenSurface()
        surface.setFormat(ctx.format())
        surface.create()
        if not surface.isValid():
            return False

        ok = False
        try:
            ok = bool(ctx.makeCurrent(surface))
            if ok:
                ctx.doneCurrent()
        finally:
            surface.destroy()
        return ok
    except Exception:
        return False


def _enable_software_backend() -> None:
    os.environ["QT_QUICK_BACKEND"] = "software"
    try:
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)
    except Exception:
        pass


def configure_qt_graphics_backend(
    app=None,
    *,
    force_software: bool = False,
    on_log: Optional[Callable[[str, str], None]] = None,
) -> str:
    """
    Configures Qt Quick's graphics backend after QApplication/QGuiApplication exists
    and before QQmlApplicationEngine loads any window.

    Returns one of: `"software"`, `"software_fallback"`, `"hardware"`.
    """
    def _emit(level: str, msg: str) -> None:
        if on_log is not None:
            try:
                on_log(level, msg)
            except Exception:
                pass

    if force_software or os.environ.get("QT_QUICK_BACKEND", "").strip().lower() == "software":
        _enable_software_backend()
        _emit("INFO", "Software rendering backend enabled (--software-render / QT_QUICK_BACKEND=software).")
        return "software"

    # Respect explicit user override (e.g. QT_QUICK_BACKEND=vulkan or opengl)
    if os.environ.get("QT_QUICK_BACKEND", "").strip():
        return "hardware"

    # Skip probe on headless/offscreen Qt platform plugins (CI / test runs)
    plat_name = ""
    try:
        if app is not None and hasattr(app, "platformName"):
            plat_name = (app.platformName() or "").strip().lower()
    except Exception:
        plat_name = ""
    if plat_name in ("offscreen", "minimal", "minimalegl"):
        return "hardware"

    # On Linux, probe OpenGL/EGL before Qt Quick can abort with SIGABRT
    if sys.platform.startswith("linux"):
        if not probe_opengl_available():
            _enable_software_backend()
            _emit(
                "WARNING",
                "Hardware OpenGL/EGL context is unavailable on this display session — "
                "automatically falling back to software rendering.",
            )
            return "software_fallback"

    return "hardware"
