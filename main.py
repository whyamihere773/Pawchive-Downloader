import sys
import os
import signal

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
# Use default hardware-accelerated threaded render loop (Direct3D 11 on Windows) for silky smooth 60-144+ FPS

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

    from bridge.translation_manager import TranslationManager
    app_bridge = AppBridge()

    locales_dir = os.path.join(base_dir, "locales")
    translation_manager = TranslationManager(locales_dir=locales_dir)
    translation_manager.setLanguage(app_bridge.language)
    app_bridge.languageChanged.connect(lambda: translation_manager.setLanguage(app_bridge.language))

    from bridge.updater_bridge import UpdaterBridge
    updater_bridge = UpdaterBridge()

    from PySide6.QtQuickControls2 import QQuickStyle

    engine = QQmlApplicationEngine()
    style_dir = os.path.join(base_dir, "qml", "style")
    if os.path.exists(style_dir):
        engine.addImportPath(style_dir)
        QQuickStyle.setFallbackStyle("Basic")
        QQuickStyle.setStyle("PawchiveStyle")

    engine.rootContext().setContextProperty("appBridge", app_bridge)
    engine.rootContext().setContextProperty("decompressorBridge", app_bridge.decompressorBridge)
    engine.rootContext().setContextProperty("telegramBridge", app_bridge.telegramBridge)
    engine.rootContext().setContextProperty("updaterBridge", updater_bridge)
    engine.rootContext().setContextProperty("Lang", translation_manager)

    qml_file = os.path.join(base_dir, "qml", "main.qml")

    logger.info("Initializing Kemono & Pawchive Desktop Suite...", category="system")
    logger.info(f"Loading QML interface from: {qml_file}", category="system")

    engine.load(QUrl.fromLocalFile(qml_file))

    if not engine.rootObjects():
        logger.error("Failed to load QML interface. Check console for QML errors.", category="system")
        sys.exit(-1)

    win = engine.rootObjects()[0]

    from core.memory_collector import memory_collector
    memory_collector.start()

    def update_screen_hz(target_screen=None):
        scr = target_screen or win.screen() or app.primaryScreen()
        if scr:
            app_bridge.setScreenHz(int(round(scr.refreshRate())))

    update_screen_hz()
    win.screenChanged.connect(update_screen_hz)

    from services.telegram_service import TelegramService
    app.aboutToQuit.connect(app_bridge.onAppClosing)
    app.aboutToQuit.connect(memory_collector.stop)
    app.aboutToQuit.connect(TelegramService.instance().stop)

    logger.success("Application interface initialized successfully.", category="system")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
