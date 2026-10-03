"""
QML bridge for app updates: checks GitHub in the background, shows the result, and hands
over to the updater (which installs the update after the app has closed normally).
"""

import os
import threading

from PySide6.QtCore import Property, QCoreApplication, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from core.logger import logger
from services import update_service as us


class UpdaterBridge(QObject):
    isCheckingChanged = Signal()
    updateAvailableChanged = Signal()
    statusChanged = Signal()
    infoChanged = Signal()
    launchingChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_checking = False
        self._update_available = False
        self._launching = False
        self._checked_once = False
        self._status_message = ""
        self._info = {}

        # Quick version from version.json now; the commit (git) is filled in off the UI thread
        data = us._read_version_file(us.get_app_dir())
        self._current_version = us.version_display(str(data.get("version") or ""))
        self._edition = us.edition_label(not us.is_compiled())
        threading.Thread(target=self._load_local_info, daemon=True, name="UpdaterLocalInfo").start()
        threading.Thread(target=us.cleanup_update_leftovers, daemon=True, name="UpdaterCleanup").start()

        QTimer.singleShot(3500, lambda: self.checkForUpdates(True))

    def _load_local_info(self):
        try:
            info = us.get_local_version_info()
            self._current_version = info["display"]
            self._edition = info["edition_label"]
            self.infoChanged.emit()
        except Exception as e:
            logger.debug(f"Couldn't read the local version: {e}", category="system")

    # ── Properties ────────────────────────────────────────────────────────────
    @Property(bool, notify=isCheckingChanged)
    def isChecking(self) -> bool:
        return self._is_checking

    @Property(bool, notify=updateAvailableChanged)
    def updateAvailable(self) -> bool:
        return self._update_available

    @Property(bool, notify=launchingChanged)
    def isLaunching(self) -> bool:
        return self._launching

    @Property(bool, notify=statusChanged)
    def checkedOnce(self) -> bool:
        return self._checked_once

    @Property(str, notify=statusChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=infoChanged)
    def currentVersion(self) -> str:
        return self._current_version

    @Property(str, notify=infoChanged)
    def edition(self) -> str:
        """'Windows build', 'Linux build' or 'Source code (git)'."""
        return self._edition

    @Property(str, notify=infoChanged)
    def latestVersion(self) -> str:
        return self._info.get("remote_display", "") or self._info.get("remote_version", "")

    @Property(str, notify=infoChanged)
    def releaseNotes(self) -> str:
        return self._info.get("notes", "")

    @Property(str, notify=infoChanged)
    def releaseDate(self) -> str:
        return (self._info.get("published_at", "") or "")[:10]

    @Property(str, notify=infoChanged)
    def releaseUrl(self) -> str:
        return self._info.get("release_url", "")

    @Property(int, notify=infoChanged)
    def commitsBehind(self) -> int:
        return int(self._info.get("commits_behind") or 0)

    @Property(bool, constant=True)
    def isCompiled(self) -> bool:
        return us.is_compiled()

    @Property(bool, notify=infoChanged)
    def isSourceUpdate(self) -> bool:
        return self._info.get("kind", "") in ("source-git", "source-archive")

    # ── Slots ─────────────────────────────────────────────────────────────────
    @Slot(bool)
    def checkForUpdates(self, silent: bool = False):
        """Check GitHub in the background."""
        if self._is_checking or self._launching:
            return
        self._is_checking = True
        self.isCheckingChanged.emit()
        if not silent:
            self._status_message = "Checking for updates…"
            self.statusChanged.emit()

        def _worker():
            res = us.check_for_updates(timeout=10)
            self._info = res
            self._update_available = bool(res.get("update_available"))
            self._checked_once = True
            if self._update_available:
                self._status_message = f"Version {self.latestVersion} is ready to install."
                logger.info(f"Update available: {res.get('local_display')} -> {self.latestVersion}", category="system")
            elif res.get("error"):
                self._status_message = "Couldn't check for updates: " + res["error"]
                if not silent:
                    logger.warning(self._status_message, category="system")
            else:
                self._status_message = res.get("message") or "You're running the latest version."
            self._is_checking = False
            self.isCheckingChanged.emit()
            self.updateAvailableChanged.emit()
            self.infoChanged.emit()
            self.statusChanged.emit()

        threading.Thread(target=_worker, daemon=True, name="UpdateCheck").start()

    @Slot()
    def startUpdate(self):
        """Start the updater, then close the app normally (the session is saved on the way out)."""
        if self._launching or not self._update_available:
            return
        try:
            plan_path = us.launch_updater(self._info)
        except Exception as e:
            self._status_message = f"The updater couldn't start: {e}"
            self.statusChanged.emit()
            logger.error(self._status_message, category="system")
            return
        self._launching = True
        self.launchingChanged.emit()
        logger.info(f"Updater started ({os.path.basename(os.path.dirname(plan_path))}); closing the app…", category="system")
        QTimer.singleShot(250, QCoreApplication.quit)

    @Slot()
    def openReleasePage(self):
        url = self._info.get("release_url") or f"https://github.com/{us.GITHUB_OWNER}/{us.GITHUB_REPO}/releases"
        QDesktopServices.openUrl(QUrl(url))

    @Slot()
    def dismissUpdate(self):
        """Hide the update badge for this session."""
        self._update_available = False
        self.updateAvailableChanged.emit()
