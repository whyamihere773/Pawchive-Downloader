"""
Project Kemono & Pawchive Desktop Suite
Main application entry point initializing Qt/QML runtime and core bridge context.
"""

import sys
import os

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["QSG_RENDER_LOOP"] = "basic"

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon

from core.logger import logger
from bridge.app_bridge import AppBridge


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PawchiveDownloader")
    app.setOrganizationName("PawchiveProject")
    app.setApplicationDisplayName("Pawchive Downloader")

    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(base_dir, "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    app_bridge = AppBridge()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("appBridge", app_bridge)

    qml_file = os.path.join(base_dir, "qml", "main.qml")

    logger.info("Initializing Kemono & Pawchive Desktop Suite...", category="system")
    logger.info(f"Loading QML interface from: {qml_file}", category="system")

    engine.load(QUrl.fromLocalFile(qml_file))

    if not engine.rootObjects():
        logger.error("Failed to load QML interface. Check console for QML errors.", category="system")
        sys.exit(-1)

    app.aboutToQuit.connect(app_bridge.onAppClosing)

    logger.success("Application interface initialized successfully.", category="system")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
