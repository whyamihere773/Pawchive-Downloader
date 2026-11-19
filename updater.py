"""
Pawchive Downloader — updater.

Started by the app with `--plan <file>` (written by services.update_service.launch_updater),
after which the app closes itself. Shows a QML window when a display is available, otherwise
updates in the console. Works on Windows and every Linux distribution; on its own it can also
check for and install the latest version (run it with no arguments).

    updater(.exe) --plan plan.json [--no-wait] [--console]
    python updater.py                      # check GitHub and update this copy
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional

# Running from source: make the app's packages importable whatever the working folder is
_HERE = os.path.dirname(os.path.abspath(__file__))
if not getattr(sys, "frozen", False) and _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from services import update_installer as ui  # noqa: E402
from services import update_service as us  # noqa: E402


# ── Plan ────────────────────────────────────────────────────────────────────
def load_plan(args: argparse.Namespace) -> Dict[str, Any]:
    if args.plan:
        with open(args.plan, "r", encoding="utf-8") as f:
            plan = json.load(f)
        plan["_plan_path"] = args.plan
    elif args.download_url:
        # Older versions of the app started the updater with these flags
        target = os.path.abspath(args.target_dir or us.get_app_dir())
        is_source = bool(args.source) or not getattr(sys, "frozen", False)
        plan = {
            "target_dir": target, "pid": args.pid, "download_url": args.download_url, "sha256": "", "size": 0,
            "kind": ("source-git" if os.path.isdir(os.path.join(target, ".git")) else "source-archive") if is_source else "release",
            "is_source": is_source, "commit": args.commit or "", "branch": us.GITHUB_BRANCH,
            "from_display": "", "to_display": args.version or "", "to_version": args.version or "", "notes": "",
            "python_exe": args.python_exe or (sys.executable if is_source else ""), "app_executable": "",
            "repo_url": f"https://github.com/{us.GITHUB_OWNER}/{us.GITHUB_REPO}.git",
        }
    else:
        is_source = not getattr(sys, "frozen", False)
        plan = {"target_dir": us.get_app_dir(), "pid": 0, "_manual": True, "_needs_check": True, "is_source": is_source,
                "python_exe": sys.executable if is_source else "", "app_executable": ""}
    if args.no_wait:
        plan["no_wait"] = True
    plan["target_dir"] = os.path.abspath(plan["target_dir"])
    return plan


def plan_from_check(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Manual run: ask GitHub what to install."""
    info = us.check_for_updates(timeout=15)
    if not info.get("update_available"):
        return {**plan, "_needs_check": False, "_uptodate": True, "_message": info.get("error") or info.get("message") or "You're up to date."}
    built = us.build_update_plan(info)
    built.update({"pid": 0, "target_dir": plan["target_dir"], "_manual": True, "_needs_check": False})
    return built


def save_plan(plan: Dict[str, Any]) -> str:
    path = plan.get("_plan_path")
    if not path:
        import tempfile
        path = os.path.join(tempfile.mkdtemp(prefix="pawchive_plan_"), "plan.json")
        plan["_plan_path"] = path
    with open(path, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in plan.items() if not k.startswith("_")}, f, indent=1)
    return path


def drop_plan(plan: Dict[str, Any]) -> None:
    path = plan.get("_plan_path", "")
    folder = os.path.dirname(path)
    if path and os.path.basename(folder).startswith("pawchive_plan_"):
        import shutil
        shutil.rmtree(folder, ignore_errors=True)


def elevate(plan: Dict[str, Any]) -> bool:
    """Windows: start the updater again with administrator rights (Windows shows its own prompt)."""
    if sys.platform != "win32":
        return False
    import ctypes
    path = save_plan(plan)
    if getattr(sys, "frozen", False):
        exe, args = os.path.abspath(sys.executable), ["--plan", path, "--no-wait"]
    else:
        exe, args = us.gui_python(sys.executable), [os.path.abspath(__file__), "--plan", path, "--no-wait"]
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, subprocess.list2cmdline(args), plan["target_dir"], 1)
    return int(rc) > 32


# ── Error → what the user can do ────────────────────────────────────────────
def actions_for(code: str) -> List[str]:
    if code == "cancelled":
        return ["open", "close"]
    if code in ("locked", "permission"):
        return (["admin"] if sys.platform == "win32" else []) + ["retry", "open"]
    if code == "local_changes":
        return ["stash", "keep"]
    if code in ("diverged", "wrong_branch"):
        return ["open", "close"]
    if code == "git_failed":
        return ["archive", "open"]
    return ["retry", "open"]


def error_title(code: str) -> str:
    return {
        "cancelled": "Update cancelled",
        "app_running": "Pawchive is still open",
        "network": "Couldn't download the update",
        "verify": "The download didn't check out",
        "disk": "Not enough free space",
        "locked": "Some files are in use",
        "permission": "No permission to update this folder",
        "path_too_long": "Install folder path is too long",
        "local_changes": "You've changed some app files",
        "diverged": "Your copy has its own commits",
        "wrong_branch": "You're on a different branch",
        "git_failed": "git couldn't update this folder",
    }.get(code, "The update didn't finish")


def error_hint(code: str) -> str:
    return {
        "cancelled": "Nothing was changed.",
        "locked": "Another program (often an antivirus scan) is holding them. Your previous version was restored.",
        "permission": ("Your previous version was restored. Try again as administrator." if sys.platform == "win32"
                       else "Your previous version was restored. The app folder needs to be writable by your user."),
        "path_too_long": ("Your previous version was restored. Move the Pawchive Downloader folder to a shorter "
                          "path (for example C:\\Pawchive Downloader) and try updating again."
                          if sys.platform == "win32"
                          else "Your previous version was restored. Move the Pawchive Downloader folder to a shorter "
                               "path and try updating again."),
        "local_changes": "Updating would replace your edits. You can keep them safe with git stash and update, or keep "
                         "your changes and skip this update.",
        "diverged": "It can't simply be moved to the new version. Update it with git (git pull).",
        "wrong_branch": f"Switch to '{us.GITHUB_BRANCH}' or update with git yourself.",
        "git_failed": "You can download the new files instead (a backup is kept until it succeeds).",
    }.get(code, "Nothing was changed. You can try again.")


# ── Console mode ────────────────────────────────────────────────────────────
class ConsoleReporter(ui.Reporter):
    def __init__(self, labels: Dict[str, str]):
        self.labels = labels
        self._last = 0.0

    def step(self, step_id: str, state: str) -> None:
        mark = {"active": "…", "done": "✓", "failed": "✗", "skipped": "–"}.get(state, " ")
        if state != "active" or step_id in self.labels:
            print(f"[{mark}] {self.labels.get(step_id, step_id)}", flush=True)

    def progress(self, fraction: Optional[float], detail: str = "") -> None:
        now = time.time()
        if now - self._last >= 1.5 and detail:
            self._last = now
            pct = f"{int(fraction * 100):3d}%  " if fraction is not None else ""
            print(f"      {pct}{detail}", flush=True)


def run_console(plan: Dict[str, Any], log: ui.UpdateLog) -> int:
    proxy = plan.get("proxy_url") or us.resolve_proxy(plan.get("target_dir"), plan)
    if proxy:
        us.apply_proxy(proxy)
    if plan.get("_manual"):
        plan = plan_from_check(plan)
        if plan.get("_uptodate"):
            print(plan["_message"])
            return 0
    edition = f" ({plan['edition_label']})" if plan.get("edition_label") else ""
    print(f"Updating Pawchive Downloader{edition} {plan.get('from_display') or ''} -> {plan.get('to_display') or 'latest'}", flush=True)
    rep = ConsoleReporter(dict(ui.steps_for(plan)))
    result = ui.run_update(plan, rep, log)
    if result["ok"]:
        if result["warning"]:
            print("[!] " + result["warning"])
        print("Update complete. Starting Pawchive…", flush=True)
        ui.relaunch(plan, log)
        drop_plan(plan)
        return 0
    print(f"[!] {error_title(result['code'])}: {result['message']} {error_hint(result['code'])}", flush=True)
    if log.path:
        print(f"    Details: {log.path}")
    if result["code"] != "app_running":
        ui.relaunch(plan, log)      # bring back the version that's still installed
    drop_plan(plan)
    return 1


def gui_possible(force_console: bool) -> bool:
    if force_console or os.environ.get("PAWCHIVE_UPDATER_CONSOLE"):
        return False
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False
    try:
        import PySide6.QtGui  # noqa: F401
        import PySide6.QtQml  # noqa: F401
        import PySide6.QtQuick  # noqa: F401
        return True
    except ImportError:
        return False


# ── Window ──────────────────────────────────────────────────────────────────
def find_icon(target_dir: str) -> str:
    """The app's paw icon: next to the app, inside a build's _internal folder, or bundled with the updater."""
    roots = [target_dir, os.path.join(target_dir, "_internal"), getattr(sys, "_MEIPASS", ""),
             os.path.dirname(os.path.abspath(__file__))]
    for root in filter(None, roots):
        for name in ("assets/pawchive.png", "assets/icon.png", "pawchive.png", "icon.png"):
            p = os.path.join(root, *name.split("/"))
            if os.path.isfile(p):
                return p
    return ""


def run_gui(plan: Dict[str, Any], log: ui.UpdateLog) -> int:
    proxy = plan.get("proxy_url") or us.resolve_proxy(plan.get("target_dir"), plan)
    if proxy:
        us.apply_proxy(proxy)
    from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
    from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    try:
        from core.graphics_backend import configure_qt_graphics_backend, parse_software_render_args
        force_sw, _ = parse_software_render_args(sys.argv)
        configure_qt_graphics_backend(
            app,
            force_software=force_sw,
            on_log=lambda _lvl, msg: log.write(msg),
        )
    except Exception:
        pass
    app.setApplicationName("PawchiveUpdater")
    app.setApplicationDisplayName("Pawchive Downloader Updater")
    icon_path = find_icon(plan["target_dir"])
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    class Controller(QObject):
        changed = Signal()
        _event = Signal(str, "QVariant")   # worker thread → window thread (queued)

        def __init__(self):
            super().__init__()
            self.plan = plan
            self._steps: List[Any] = []
            self._states: List[str] = []
            self._progress = -1.0
            self._detail = ""
            self._phase = "running"     # running | success | error | uptodate
            self._can_cancel = True
            self._title = ""
            self._text = ""
            self._details = ""
            self._warning = ""
            self._code = ""
            self._actions: List[str] = []
            self._countdown = 0
            self._shake = 0
            self._cancel = threading.Event()
            self._installing = False
            self._quitting = False
            self._relaunched = False
            self._worker: Optional[threading.Thread] = None
            self._timer = QTimer(self)
            self._timer.setInterval(1000)
            self._timer.timeout.connect(self._tick)
            self._event.connect(self._on_event)

        # ── properties (read-only for QML; one change signal keeps this small) ──
        stepLabels = Property("QVariantList", lambda self: [s[1] for s in self._steps], notify=changed)
        stepStates = Property("QVariantList", lambda self: list(self._states), notify=changed)
        progress = Property(float, lambda self: self._progress, notify=changed)
        detail = Property(str, lambda self: self._detail, notify=changed)
        phase = Property(str, lambda self: self._phase, notify=changed)
        canCancel = Property(bool, lambda self: self._can_cancel and self._phase == "running", notify=changed)
        title = Property(str, lambda self: self._title, notify=changed)
        text = Property(str, lambda self: self._text, notify=changed)
        details = Property(str, lambda self: self._details, notify=changed)
        warning = Property(str, lambda self: self._warning, notify=changed)
        actions = Property("QVariantList", lambda self: list(self._actions), notify=changed)
        countdown = Property(int, lambda self: self._countdown, notify=changed)
        shake = Property(int, lambda self: self._shake, notify=changed)
        code = Property(str, lambda self: self._code, notify=changed)
        fromVersion = Property(str, lambda self: self.plan.get("from_display") or "", notify=changed)
        edition = Property(str, lambda self: self.plan.get("edition_label")
                           or us.edition_label(bool(self.plan.get("is_source")),
                                               os.path.isdir(os.path.join(self.plan["target_dir"], ".git"))),
                           notify=changed)
        toVersion = Property(str, lambda self: self.plan.get("to_display") or "", notify=changed)
        notes = Property(str, lambda self: self.plan.get("notes") or "", notify=changed)
        isWindows = Property(bool, lambda self: sys.platform == "win32", constant=True)
        hasLog = Property(bool, lambda self: bool(log.path), constant=True)
        iconUrl = Property(str, lambda self: QUrl.fromLocalFile(icon_path).toString() if icon_path else "", constant=True)

        # ── running ──
        def start(self):
            if self.plan.get("_needs_check", False) or (self.plan.get("_manual") and "_needs_check" not in self.plan):
                self._phase = "running"
                self._steps = [("check", "Checking for updates")]
                self._states = ["active"]
                self.changed.emit()
                threading.Thread(target=self._check_worker, daemon=True).start()
                return
            self._steps = ui.steps_for(self.plan)
            self._states = ["pending"] * len(self._steps)
            self._phase, self._title, self._text, self._details, self._warning = "running", "", "", "", ""
            self._actions, self._progress, self._detail = [], -1.0, ""
            self._can_cancel, self._installing = True, False
            self._relaunched = False
            self._cancel.clear()
            self.changed.emit()
            self._worker = threading.Thread(target=self._work, daemon=True)
            self._worker.start()

        def _check_worker(self):
            try:
                checked = plan_from_check(self.plan)
            except Exception as e:
                self._event.emit("result", {"ok": False, "code": "network", "message": f"Update check failed: {e}"})
                return
            if self._cancel.is_set():
                self._event.emit("result", {"ok": False, "code": "cancelled", "message": "The update check was cancelled."})
                return
            self._event.emit("checked", checked)

        def _work(self):
            ctrl = self

            class Rep(ui.Reporter):
                def step(self, step_id, state):
                    ctrl._event.emit("step", [step_id, state])

                def progress(self, fraction, detail=""):
                    ctrl._event.emit("progress", [-1.0 if fraction is None else float(fraction), detail])

                def cancelled(self):
                    return ctrl._cancel.is_set()

                def install_started(self):
                    ctrl._event.emit("installing", True)

            result = ui.run_update(self.plan, Rep(), log)
            self._event.emit("result", result)

        @Slot(str, "QVariant")
        def _on_event(self, kind, value):
            if kind == "step":
                ids = [s[0] for s in self._steps]
                if value[0] in ids:
                    self._states[ids.index(value[0])] = value[1]
                    if value[1] == "active":
                        self._progress, self._detail = -1.0, ""
            elif kind == "progress":
                self._progress, self._detail = value[0], value[1]
            elif kind == "installing":
                self._installing, self._can_cancel = True, False
            elif kind == "checked":
                if value.get("_uptodate"):
                    self._phase, self._title, self._text = "uptodate", "You're up to date", value.get("_message", "")
                    self._states = ["done"]
                    self._actions = ["open", "close"]
                else:
                    self.plan = value
                    self.start()
                    return
            elif kind == "result":
                self._finish(value)
            self.changed.emit()

        def _finish(self, r):
            if self._phase != "running":
                return
            self._installing = False
            self._can_cancel = False
            self._code = r.get("code", "")
            if r.get("ok"):
                self._phase = "success"
                self._title = "Updated to " + (self.plan.get("to_display") or "the latest version")
                self._warning = r.get("warning", "")
                self._actions = ["open", "close"]
                self._countdown = 8 if self._warning else 4
                self._timer.start()
                return
            self._phase = "error"
            self._title = error_title(self._code)
            self._text = (r.get("message", "") + " " + error_hint(self._code)).strip()
            self._details = r.get("details", "")
            self._actions = actions_for(self._code)
            self._shake += 1
            if self._code == "cancelled":
                self._countdown = 4          # bring the app back on its own
                self._timer.start()

        def _tick(self):
            self._countdown -= 1
            if self._countdown <= 0:
                self._timer.stop()
                self.act("open")
            self.changed.emit()

        # ── buttons ──
        @Slot()
        def cancel(self):
            if self._phase == "running" and self._can_cancel:
                self._cancel.set()
                if not self._installing:
                    self._finish({"ok": False, "code": "cancelled", "message": "The update was cancelled."})
                    self.changed.emit()
                else:
                    self._detail = "Cancelling…"
                    self.changed.emit()

        @Slot()
        def nudge(self):
            self._shake += 1
            self.changed.emit()

        @Slot(str)
        def act(self, action):
            if self._quitting:
                return
            self._timer.stop()
            if action == "open":
                if not self._relaunched and self._code not in ("app_running",):
                    self._relaunched = True
                    ui.relaunch(self.plan, log)
                self._quit()
            elif action == "close":
                self._quit()
            elif action == "retry":
                self.plan["no_wait"] = False
                self.start()
            elif action == "admin":
                if elevate(self.plan):
                    self._quit(drop=False)       # the elevated updater carries on
                else:
                    self._text = "Windows didn't allow running as administrator."
                    self._shake += 1
                    self.changed.emit()
            elif action == "stash":
                self.plan["stash_changes"] = True
                self.start()
            elif action == "keep":
                if not self._relaunched:
                    self._relaunched = True
                    ui.relaunch(self.plan, log)
                self._quit()
            elif action == "archive":
                self.plan["force_archive"] = True
                self.start()
            elif action == "log" and log.path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(log.path))

        @Slot(result=bool)
        def canClose(self):
            return self._quitting or not (self._phase == "running" and self._installing)

        @Slot()
        def windowClosing(self):
            if self._quitting:
                return
            if self._phase == "running":
                if self._can_cancel and not self._installing:
                    self._cancel.set()
                    if not self._relaunched and self.plan.get("pid") and not self.plan.get("_manual"):
                        self._relaunched = True
                        ui.relaunch(self.plan, log)
                    self._quit()
                elif self._can_cancel:
                    self.cancel()
            else:
                self._quit()

        def _quit(self, drop: bool = True):
            if self._quitting:
                return
            self._quitting = True
            self._timer.stop()
            if drop:
                drop_plan(self.plan)
            for w in list(QGuiApplication.topLevelWindows()):
                try:
                    w.close()
                except Exception:
                    pass
            QGuiApplication.quit()

    ctrl = Controller()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("upd", ctrl)
    qml_src = load_updater_qml(plan.get("target_dir", "")) or UPDATER_QML
    engine.loadData(qml_src.encode("utf-8"), QUrl("pawchive-updater.qml"))
    if not engine.rootObjects():
        log.write("QML window failed to load; falling back to console mode")
        return run_console(plan, log)
    ctrl.start()
    rc = app.exec()
    if ctrl._worker and ctrl._worker.is_alive():
        if ctrl._installing and ctrl._phase == "running":
            ctrl._worker.join(timeout=600)       # only wait if actively writing files
    del engine
    return rc


# Spring presets (the same "weight" feel as the app's own buttons and cards): light parts snap,
# heavy parts settle.
#   light  : spring 5.5  damping 0.28  mass 0.55
#   medium : spring 4.2  damping 0.34  mass 1.0
#   heavy  : spring 3.4  damping 0.36  mass 1.6
def load_updater_qml(target_dir: str = "") -> str:
    """Load the updater QML window from disk into memory before installation touches files."""
    roots = [
        getattr(sys, "_MEIPASS", ""),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.join(target_dir, "_internal") if target_dir else "",
        target_dir,
    ]
    for root in filter(None, roots):
        cand = os.path.join(root, "qml", "updater", "UpdaterWindow.qml")
        if os.path.isfile(cand):
            with open(cand, "r", encoding="utf-8") as f:
                return f.read()
    return ""


UPDATER_QML = load_updater_qml()


def main() -> int:
    parser = argparse.ArgumentParser(description="Pawchive Downloader updater")
    parser.add_argument("--plan", default="", help="Update plan written by the app")
    parser.add_argument("--no-wait", action="store_true", help="Don't wait for the app to close")
    parser.add_argument("--console", action="store_true", help="Update in the console, without a window")
    # Older versions of the app started the updater with these
    parser.add_argument("--target-dir", default="")
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--download-url", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--source", action="store_true")
    parser.add_argument("--python-exe", default="")
    parser.add_argument("--commit", default="")
    parser.add_argument("--temp-runner", action="store_true")
    args = parser.parse_args()

    try:
        plan = load_plan(args)
    except (OSError, ValueError) as e:
        print(f"Couldn't read the update plan: {e}")
        return 2
    log = ui.UpdateLog(plan["target_dir"], plan)
    log.write(f"plan: { {k: v for k, v in plan.items() if k != 'notes'} }")
    if gui_possible(args.console):
        try:
            return run_gui(plan, log)
        except Exception as e:  # a broken display setup shouldn't stop the update
            log.write(f"window mode failed ({e!r}); using console mode")
    return run_console(plan, log)


if __name__ == "__main__":
    sys.exit(main())
