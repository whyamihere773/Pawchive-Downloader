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
        plan = {"target_dir": us.get_app_dir(), "pid": 0, "_manual": True, "is_source": is_source,
                "python_exe": sys.executable if is_source else "", "app_executable": ""}
    if args.no_wait:
        plan["no_wait"] = True
    plan["target_dir"] = os.path.abspath(plan["target_dir"])
    return plan


def plan_from_check(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Manual run: ask GitHub what to install."""
    info = us.check_for_updates(timeout=15)
    if not info.get("update_available"):
        return {**plan, "_uptodate": True, "_message": info.get("error") or info.get("message") or "You're up to date."}
    built = us.build_update_plan(info)
    built.update({"pid": 0, "target_dir": plan["target_dir"], "_manual": True})
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
    from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
    from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
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
            if self.plan.get("_manual"):
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
            self._cancel.clear()
            self.changed.emit()
            self._worker = threading.Thread(target=self._work, daemon=False)
            self._worker.start()

        def _check_worker(self):
            self._event.emit("checked", plan_from_check(self.plan))

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
                self._detail = "Cancelling…"
                self.changed.emit()

        @Slot()
        def nudge(self):
            self._shake += 1
            self.changed.emit()

        @Slot(str)
        def act(self, action):
            self._timer.stop()
            if action == "open":
                if self._code not in ("app_running",):
                    ui.relaunch(self.plan, log)
                self._quit()
            elif action == "close":
                self._quit()
            elif action == "retry":
                self.plan["no_wait"] = False
                self.start()
            elif action == "admin":
                if elevate(self.plan):
                    QGuiApplication.quit()       # the elevated updater carries on
                else:
                    self._text = "Windows didn't allow running as administrator."
                    self._shake += 1
                    self.changed.emit()
            elif action == "stash":
                self.plan["stash_changes"] = True
                self.start()
            elif action == "keep":
                ui.relaunch(self.plan, log)
                self._quit()
            elif action == "archive":
                self.plan["force_archive"] = True
                self.start()
            elif action == "log" and log.path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(log.path))

        @Slot(result=bool)
        def canClose(self):
            return not self._installing or self._phase != "running"

        @Slot()
        def windowClosing(self):
            if self._phase == "running" and self._can_cancel:
                self.cancel()
            elif self._phase != "running":
                self._quit()

        def _quit(self):
            drop_plan(self.plan)
            QGuiApplication.quit()

    ctrl = Controller()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("upd", ctrl)
    engine.loadData(UPDATER_QML.encode("utf-8"), QUrl("pawchive-updater.qml"))
    if not engine.rootObjects():
        log.write("QML window failed to load; falling back to console mode")
        return run_console(plan, log)
    ctrl.start()
    rc = app.exec()
    if ctrl._worker and ctrl._worker.is_alive():
        ctrl._worker.join(timeout=600)       # never leave mid-install
    return rc


# Spring presets (the same "weight" feel as the app's own buttons and cards): light parts snap,
# heavy parts settle.
#   light  : spring 5.5  damping 0.28  mass 0.55
#   medium : spring 4.2  damping 0.34  mass 1.0
#   heavy  : spring 3.4  damping 0.36  mass 1.6
UPDATER_QML = r'''
import QtQuick
import QtQuick.Window
import QtQuick.Layouts

// Looks like the app itself (same colours, cards, buttons and progress bar as Theme.qml).
Window {
    id: win
    visible: true
    width: 560
    height: 540
    minimumWidth: 480
    minimumHeight: 460
    title: "Pawchive Downloader Update"
    color: "#0F1117"

    readonly property string ff: "Segoe UI, Inter, Roboto, sans-serif"
    readonly property string mono: "Cascadia Code, Consolas, Fira Code, monospace"
    readonly property color primary: "#38BDF8"
    readonly property color success: "#10B981"
    readonly property color danger: "#EF4444"
    readonly property color warning: "#F59E0B"
    readonly property bool running: upd.phase === "running"
    readonly property color tone: upd.phase === "error" ? (upd.code === "cancelled" ? warning : danger)
                                : (running ? primary : success)

    function activeIndex() {
        var s = upd.stepStates
        for (var i = 0; i < s.length; i++)
            if (s[i] === "active" || s[i] === "failed") return i
        return -1
    }

    onClosing: (close) => {
        if (!upd.canClose()) { close.accepted = false; upd.nudge(); return }
        if (running) { close.accepted = false; upd.windowClosing(); return }
        upd.windowClosing()
    }

    // ── Pieces shared with the app's look ──
    component Btn: Rectangle {
        id: btn
        property string label: ""
        property string variant: "default"        // default | primary | ghost
        property bool active: true
        signal clicked()
        implicitWidth: Math.max(80, btnText.implicitWidth + 24)
        implicitHeight: 34
        radius: 8
        color: !active ? "#1F232B"
             : variant === "primary" ? (btnMouse.pressed ? "#0284C7" : (btnMouse.containsMouse ? "#0EA5E9" : "#38BDF8"))
             : variant === "ghost" ? (btnMouse.containsMouse ? "#242B38" : "transparent")
             : (btnMouse.pressed ? "#1E222A" : (btnMouse.containsMouse ? "#2C3340" : "#222732"))
        border.color: !active ? "#2A303C" : variant === "ghost" ? "transparent"
                    : variant === "primary" ? "#38BDF8" : (btnMouse.containsMouse ? "#475569" : "#333A48")
        Behavior on color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
        // light spring, same as StyledButton
        scale: btnMouse.pressed ? 0.945 : (btnMouse.containsMouse && active ? 1.025 : 1.0)
        Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.35; mass: 0.75; epsilon: 0.005 } }
        Text {
            id: btnText
            anchors.centerIn: parent
            text: btn.label
            font.family: win.ff; font.pixelSize: 12; font.weight: Font.Medium
            color: !btn.active ? "#64748B" : btn.variant === "primary" ? "#0F172A"
                 : (btn.variant === "ghost" && btnMouse.containsMouse ? "#38BDF8" : "#E2E8F0")
        }
        MouseArea {
            id: btnMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }
    }

    component Card: Rectangle {
        id: card
        property int delay: 0
        property real enter: 0
        color: "#181B22"
        border.color: "#282E3D"
        radius: 10
        // settles into place when the window opens (medium weight)
        opacity: enter
        transform: Translate { y: (1 - card.enter) * 14 }
        Behavior on enter { SpringAnimation { spring: 4.0; damping: 0.38; mass: 1.0; epsilon: 0.002 } }
        Timer { running: true; interval: card.delay + 40; onTriggered: card.enter = 1 }
    }

    // ── Header (like the app's top bar) ──
    Rectangle {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 64
        color: "#151820"
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: "#1E2330" }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            spacing: 12

            Item {
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30
                Image {
                    id: logo
                    anchors.fill: parent
                    source: upd.iconUrl
                    sourceSize: Qt.size(64, 64)
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    visible: status === Image.Ready
                }
                Rectangle {
                    anchors.fill: parent
                    visible: logo.status !== Image.Ready
                    radius: 8
                    color: "#1E293B"
                    border.color: "#2A303F"
                    Text { anchors.centerIn: parent; text: "P"; font.family: win.ff; font.pixelSize: 15; font.bold: true; color: win.primary }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                Text {
                    text: "Pawchive Downloader"
                    font.family: win.ff; font.pixelSize: 15; font.weight: Font.DemiBold
                    color: "#F1F5F9"
                }
                Row {
                    spacing: 6
                    Text {
                        text: upd.phase === "success" ? "Updated" : (upd.phase === "uptodate" ? "Up to date"
                            : (upd.phase === "error" ? "Update stopped" : "Updating"))
                        font.family: win.ff; font.pixelSize: 12; color: "#94A3B8"
                    }
                    Text {
                        visible: upd.fromVersion.length > 0
                        text: upd.fromVersion
                        font.family: win.mono; font.pixelSize: 11; color: "#94A3B8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        visible: upd.fromVersion.length > 0 && upd.toVersion.length > 0
                        text: "→"
                        font.pixelSize: 12; color: "#64748B"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        visible: upd.toVersion.length > 0
                        text: upd.toVersion
                        font.family: win.mono; font.pixelSize: 11; color: win.primary
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    // Which edition is being updated: Windows build, Linux build or source code
                    Rectangle {
                        visible: upd.edition.length > 0
                        anchors.verticalCenter: parent.verticalCenter
                        width: editionText.implicitWidth + 12
                        height: 18
                        radius: 4
                        color: "#161E2E"
                        border.color: "#1E293B"
                        Text {
                            id: editionText
                            anchors.centerIn: parent
                            text: upd.edition
                            font.family: win.ff; font.pixelSize: 10; font.weight: Font.Medium
                            color: "#A78BFA"
                        }
                    }
                }
            }
            Item { Layout.fillWidth: true }

            // Status badge (like the inline badges next to the app's progress bar)
            Rectangle {
                Layout.preferredHeight: 22
                Layout.preferredWidth: badgeText.implicitWidth + 16
                radius: 5
                color: Qt.rgba(win.tone.r, win.tone.g, win.tone.b, 0.12)
                border.color: Qt.rgba(win.tone.r, win.tone.g, win.tone.b, 0.35)
                Behavior on color { ColorAnimation { duration: 220 } }
                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: win.running ? ("Step " + Math.max(1, win.activeIndex() + 1) + " of " + Math.max(1, upd.stepLabels.length))
                        : (upd.phase === "error" ? (upd.code === "cancelled" ? "Cancelled" : "Stopped") : "Done")
                    font.family: win.mono; font.pixelSize: 10; font.weight: Font.Medium
                    color: win.tone
                }
            }
        }
    }

    // ── Body ──
    Item {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: footer.top
        anchors.margins: 20

        // a short damped shake when something needs attention
        property real kick: 0
        transform: Translate { x: body.kick }
        Behavior on kick { SpringAnimation { spring: 9; damping: 0.2; mass: 0.5; epsilon: 0.05 } }
        property int shakes: upd.shake
        onShakesChanged: { kickTimer.restart(); body.kick = 10 }
        Timer { id: kickTimer; interval: 40; onTriggered: body.kick = 0 }

        ColumnLayout {
            anchors.fill: parent
            spacing: 12

            // Progress + steps
            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: progressCol.implicitHeight + 28
                ColumnLayout {
                    id: progressCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 14
                    spacing: 10

                    // Current step + detail
                    RowLayout {
                        Layout.fillWidth: true
                        visible: win.running
                        spacing: 8
                        Text {
                            text: (upd.stepLabels[win.activeIndex()] || "Starting") + ":"
                            font.family: win.ff; font.pixelSize: 11; font.weight: Font.DemiBold
                            color: win.primary
                        }
                        Text {
                            Layout.fillWidth: true
                            text: upd.detail
                            elide: Text.ElideRight
                            font.family: win.mono; font.pixelSize: 11; color: "#94A3B8"
                        }
                        Text {
                            visible: upd.progress >= 0
                            text: Math.round(upd.progress * 100) + "%"
                            font.family: win.mono; font.pixelSize: 11; color: "#CBD5E1"
                        }
                    }

                    // Progress bar (spring fill; a sliding segment when the size isn't known)
                    Rectangle {
                        id: track
                        Layout.fillWidth: true
                        Layout.preferredHeight: 6
                        visible: win.running
                        radius: 3
                        color: "#1A2234"
                        clip: true
                        property real shown: upd.progress < 0 ? 0 : upd.progress
                        Behavior on shown { SpringAnimation { spring: 3.0; damping: 0.42; mass: 1.0; epsilon: 0.001 } }
                        Rectangle {
                            visible: upd.progress >= 0
                            width: track.width * Math.max(0, Math.min(1, track.shown))
                            height: parent.height
                            radius: 3
                            color: win.primary
                        }
                        Rectangle {
                            id: slider
                            visible: upd.progress < 0
                            width: track.width * 0.25
                            height: parent.height
                            radius: 3
                            color: win.primary
                            opacity: 0.8
                            SequentialAnimation on x {
                                running: slider.visible
                                loops: Animation.Infinite
                                NumberAnimation { from: -slider.width; to: track.width; duration: 1400; easing.type: Easing.InOutQuad }
                            }
                        }
                    }

                    // Result (drops in with weight when the update ends)
                    Rectangle {
                        id: result
                        Layout.fillWidth: true
                        Layout.preferredHeight: resultCol.implicitHeight + 22
                        visible: !win.running
                        radius: 8
                        color: "#0B0E14"
                        border.color: Qt.rgba(win.tone.r, win.tone.g, win.tone.b, 0.45)
                        property real drop: win.running ? 0 : 1
                        Behavior on drop { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.002 } }
                        opacity: drop
                        transform: Translate { y: (1 - result.drop) * -10 }
                        Rectangle { x: 0; y: 8; width: 3; height: parent.height - 16; radius: 1.5; color: win.tone }
                        ColumnLayout {
                            id: resultCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.leftMargin: 16
                            anchors.rightMargin: 12
                            anchors.topMargin: 11
                            spacing: 5
                            Text {
                                Layout.fillWidth: true
                                text: upd.title
                                wrapMode: Text.WordWrap
                                font.family: win.ff; font.pixelSize: 13; font.bold: true; color: "#F1F5F9"
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: text.length > 0
                                text: upd.text
                                wrapMode: Text.WordWrap
                                font.family: win.ff; font.pixelSize: 12; color: "#CBD5E1"
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: upd.warning.length > 0
                                text: "⚠ " + upd.warning
                                wrapMode: Text.WordWrap
                                font.family: win.ff; font.pixelSize: 12; color: "#FBBF24"
                            }
                            Text {
                                visible: upd.countdown > 0
                                text: "Opening Pawchive in " + upd.countdown + "s"
                                font.family: win.mono; font.pixelSize: 11; color: "#64748B"
                            }
                        }
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: "#222A3A" }

                    // Steps
                    Column {
                        Layout.fillWidth: true
                        spacing: 4
                        Repeater {
                            model: upd.stepLabels
                            delegate: Item {
                                id: stepRow
                                width: parent.width
                                height: 22
                                readonly property string st: upd.stepStates[index] || "pending"

                                Item {
                                    id: mark
                                    width: 16; height: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 6; height: 6; radius: 3
                                        color: "#334155"
                                        visible: stepRow.st === "pending"
                                    }
                                    Canvas {
                                        id: spinner
                                        anchors.centerIn: parent
                                        width: 14; height: 14
                                        visible: stepRow.st === "active"
                                        onPaint: {
                                            var c = getContext("2d")
                                            c.reset()
                                            c.lineWidth = 2
                                            c.strokeStyle = "#38BDF8"
                                            c.lineCap = "round"
                                            c.beginPath()
                                            c.arc(7, 7, 5.5, 0, Math.PI * 1.5)
                                            c.stroke()
                                        }
                                        RotationAnimation on rotation {
                                            running: spinner.visible
                                            loops: Animation.Infinite
                                            from: 0; to: 360; duration: 900
                                        }
                                    }
                                    Text {
                                        anchors.centerIn: parent
                                        text: stepRow.st === "failed" ? "✕" : (stepRow.st === "skipped" ? "–" : "✓")
                                        visible: pop > 0.01
                                        font.family: win.ff; font.pixelSize: 13; font.bold: true
                                        color: stepRow.st === "failed" ? win.danger : (stepRow.st === "skipped" ? "#475569" : win.success)
                                        // light spring pop when a step finishes
                                        property real pop: (stepRow.st === "done" || stepRow.st === "failed" || stepRow.st === "skipped") ? 1 : 0
                                        Behavior on pop { SpringAnimation { spring: 5.5; damping: 0.28; mass: 0.55; epsilon: 0.002 } }
                                        scale: pop
                                    }
                                }
                                Text {
                                    anchors.left: mark.right
                                    anchors.leftMargin: 10
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    elide: Text.ElideRight
                                    text: modelData + (stepRow.st === "skipped" ? "  ·  not needed" : "")
                                    font.family: win.ff
                                    font.pixelSize: 12
                                    font.weight: stepRow.st === "active" ? Font.Medium : Font.Normal
                                    color: stepRow.st === "active" ? "#F1F5F9" : (stepRow.st === "done" ? "#94A3B8"
                                         : (stepRow.st === "failed" ? "#FCA5A5" : "#64748B"))
                                    Behavior on color { ColorAnimation { duration: 180 } }
                                }
                            }
                        }
                    }
                }
            }

            // What's new (CardSection style)
            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                delay: 70
                visible: upd.notes.length > 0
                clip: true
                Row {
                    id: notesHead
                    x: 14; y: 12
                    spacing: 8
                    Text { text: "📝"; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: "What's new" + (upd.toVersion.length > 0 ? " in " + upd.toVersion : "")
                        font.family: win.ff; font.pixelSize: 12; font.weight: Font.DemiBold
                        color: "#CBD5E1"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                Flickable {
                    id: notesFlick
                    anchors.fill: parent
                    anchors.topMargin: 40
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    anchors.bottomMargin: 10
                    contentHeight: notesText.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Text {
                        id: notesText
                        width: notesFlick.width - 8
                        text: upd.notes
                        textFormat: Text.MarkdownText
                        wrapMode: Text.WordWrap
                        font.family: win.ff; font.pixelSize: 12; color: "#CBD5E1"
                        linkColor: win.primary
                        onLinkActivated: (link) => Qt.openUrlExternally(link)
                    }
                }
                // thin scroll indicator
                Rectangle {
                    visible: notesFlick.contentHeight > notesFlick.height
                    x: parent.width - 6
                    y: notesFlick.y + notesFlick.visibleArea.yPosition * notesFlick.height
                    width: 3
                    height: notesFlick.visibleArea.heightRatio * notesFlick.height
                    radius: 1.5
                    color: "#334155"
                }
            }
            Item { Layout.fillHeight: true; visible: upd.notes.length === 0 }
        }
    }

    // ── Footer ──
    Rectangle {
        id: footer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 58
        color: "#151820"
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 1; color: "#1E2330" }

        Btn {
            anchors.left: parent.left
            anchors.leftMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            visible: upd.hasLog && upd.phase === "error"
            variant: "ghost"
            label: "Show log"
            onClicked: upd.act("log")
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Btn {
                visible: win.running
                label: "Cancel"
                active: upd.canCancel
                onClicked: upd.canCancel ? upd.cancel() : upd.nudge()
            }
            Repeater {
                model: upd.actions.slice().reverse()       // main action on the right
                delegate: Btn {
                    readonly property var names: ({
                        "open": "Open Pawchive", "close": "Close", "retry": "Try again",
                        "admin": "Try again as administrator", "stash": "Save my changes and update",
                        "keep": "Keep my changes", "archive": "Download the files instead"
                    })
                    label: names[modelData] || modelData
                    variant: index === upd.actions.length - 1 ? "primary" : "default"
                    onClicked: upd.act(modelData)
                }
            }
        }
    }
}
'''


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
