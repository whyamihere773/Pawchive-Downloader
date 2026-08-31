import sys
import os
import signal

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["QSG_RENDER_LOOP"] = "basic"

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QIcon

from core.logger import logger
from bridge.app_bridge import AppBridge


def main():
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())

    app = QApplication(sys.argv)
    app.setApplicationName("PawchiveDownloader")
    app.setOrganizationName("PawchiveProject")
    app.setApplicationDisplayName("Pawchive Downloader")

    # Periodic heartbeat timer to allow Python signal handling in Qt event loop
    sig_timer = QTimer()
    sig_timer.start(300)
    sig_timer.timeout.connect(lambda: None)

    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS') and os.path.exists(os.path.join(sys._MEIPASS, "qml")):
            base_dir = sys._MEIPASS
        else:
            cand = os.path.join(os.path.dirname(sys.executable), "_internal")
            base_dir = cand if os.path.exists(cand) else os.path.dirname(sys.executable)
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
