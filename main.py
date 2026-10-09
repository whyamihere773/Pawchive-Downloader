import sys
import os
import signal

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
# Use default hardware-accelerated threaded render loop (Direct3D 11 on Windows) for silky smooth 60-144+ FPS

if sys.platform.startswith("linux"):
    os.environ["QT_QPA_PLATFORMTHEME"] = "xdgdesktopportal"

if sys.platform == "win32":
    # Ensure Windows searches PySide6's directory for multimedia backend & FFmpeg DLLs
    try:
        import PySide6
        _pyside_dir = os.path.dirname(PySide6.__file__)
        if hasattr(os, "add_dll_directory") and os.path.isdir(_pyside_dir):
            os.add_dll_directory(_pyside_dir)
    except Exception:
        pass

from core.logger import logger

# Open this session's log file first, so everything after this (including errors while the app
# loads) ends up in logs/v<version>/ next to the app.
logger.start_session()
logger.install_crash_handlers()

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtCore import QUrl, QTimer, QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6 import QtMultimedia  # noqa: E402, F401

from bridge.app_bridge import AppBridge  # noqa: E402


def _install_qt_message_handler():
    """QML errors and Qt warnings go to the log file (release builds have no console)."""
    levels = {
        QtMsgType.QtDebugMsg: "DEBUG",
        QtMsgType.QtInfoMsg: "INFO",
        QtMsgType.QtWarningMsg: "WARNING",
        QtMsgType.QtCriticalMsg: "ERROR",
        QtMsgType.QtFatalMsg: "ERROR",
    }
    seen = {}

    def _handler(mode, context, message):
        # Ignore benign internal Qt/FFmpeg cancellation notifications (e.g. when clearing source or stopping playback)
        if "Immediate exit requested" in message:
            return

        # The same warning can fire thousands of times (e.g. on every frame); keep the first 20
        count = seen.get(message, 0) + 1
        seen[message] = count
        if count > 20:
            return
        if count == 20:
            message += "  (repeated 20 times; further copies of this message are hidden)"
        where = ""
        if context is not None and context.file and context.file not in message:
            where = f"  [{context.file}:{context.line}]"
        logger.log(message + where, levels.get(mode, "WARNING"), "qt")

    qInstallMessageHandler(_handler)


def _setup_memory_management(app, win, app_bridge, memory_collector):
    """Plug the parts that hold memory into the collector, and run full cleanups only when free."""
    import time as _time
    from PySide6.QtGui import QWindow
    from bridge.thumbnail_provider import media_cache

    def _mb(n):
        return f"{n / (1024 * 1024):.0f} MB"

    # Pictures / animations kept in memory: each expires 5 minutes after it was last shown
    memory_collector.register_cleanup_hook(media_cache.expire)
    memory_collector.register_reporter("pictures in memory", lambda: "{} ({})".format(media_cache.usage()[0], _mb(media_cache.usage()[1])))

    # AI models: unloaded after 5 minutes without use
    km = getattr(app_bridge, "known_manager", None)

    def _unload_idle_ai():
        for engine in (getattr(km, "semantic_matcher", None), getattr(km, "contextual_reasoner", None)):
            if engine is not None and hasattr(engine, "unload_if_idle") and engine.unload_if_idle():
                logger.debug(f"{type(engine).__name__}: unloaded after 5 minutes unused.", category="memory")

    def _ai_report():
        loaded = [name for name, engine in (("semantic matcher", getattr(km, "semantic_matcher", None)),
                                            ("language model", getattr(km, "contextual_reasoner", None)))
                  if engine is not None and getattr(engine, "is_loaded", lambda: False)()]
        return ", ".join(loaded) if loaded else "none loaded"

    memory_collector.register_cleanup_hook(_unload_idle_ai)
    memory_collector.register_reporter("AI models", _ai_report)
    memory_collector.register_reporter("download queue", lambda: f"{len(getattr(app_bridge.downloader, 'tasks', []) or [])} file(s)")

    # A full cleanup while the window is minimized, where a short pause can't be noticed
    last = {"t": 0.0}

    def _on_visibility(visibility):
        if visibility == QWindow.Visibility.Minimized and _time.monotonic() - last["t"] > 300:
            last["t"] = _time.monotonic()
            memory_collector.collect_in_background(reason="window minimized")

    win.visibilityChanged.connect(_on_visibility)


def main():
    _install_qt_message_handler()

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())

    app = QApplication(sys.argv)
    app.setApplicationName("PawchiveDownloader")
    app.setOrganizationName("PawchiveProject")
    app.setApplicationDisplayName("Pawchive Downloader")
    if hasattr(app, "setDesktopFileName"):
        app.setDesktopFileName("pawchive.desktop")

    # Periodic heartbeat timer to allow Python signal handling in Qt event loop
    sig_timer = QTimer()
    sig_timer.start(300)
    sig_timer.timeout.connect(lambda: None)

    from core.path_utils import get_base_dir
    base_dir = get_base_dir()

    # Search for app icon (prefer pawchive.png for Linux desktop integration, fallback to icon.png)
    icon_candidates = [
        os.path.join(base_dir, "assets", "pawchive.png"),
        os.path.join(base_dir, "assets", "icon.png"),
        os.path.join(base_dir, "pawchive.png"),
        os.path.join(base_dir, "icon.png"),
    ]
    for icp in icon_candidates:
        if os.path.exists(icp):
            app.setWindowIcon(QIcon(icp))
            break

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

    from bridge.thumbnail_provider import FrameProvider, FullImageProvider, ThumbnailProvider
    engine.addImageProvider("thumb", ThumbnailProvider())
    engine.addImageProvider("full", FullImageProvider())   # image viewer: AVIF / mis-named files via Pillow
    engine.addImageProvider("frame", FrameProvider())      # animations Qt can't play (APNG, animated AVIF)

    from bridge.gallery_tools_bridge import GalleryToolsBridge
    gallery_tools_bridge = GalleryToolsBridge(app_bridge, getattr(app_bridge, "_watchlist_manager", None))
    engine.rootContext().setContextProperty("galleryTools", gallery_tools_bridge)

    from bridge.gallery_updates import GalleryUpdates
    gallery_updates = GalleryUpdates(app_bridge, getattr(app_bridge, "_watchlist_manager", None))
    engine.rootContext().setContextProperty("galleryUpdates", gallery_updates)

    from bridge.gallery_archive_bridge import GalleryArchiveBridge
    gallery_archive_bridge = GalleryArchiveBridge(app_bridge, gallery_tools_bridge)
    engine.rootContext().setContextProperty("galleryArchiveBridge", gallery_archive_bridge)

    qml_file = os.path.join(base_dir, "qml", "main.qml")

    logger.info("Initializing Kemono & Pawchive Desktop Suite...", category="system")
    logger.info(f"Loading QML interface from: {qml_file}", category="system")

    # Startup objects (character database, settings, modules) are left out of future cleanups. Done
    # before the window appears: that first full cleanup takes a few hundred ms, and 8 s after start
    # (where it used to run) it froze the window
    from core.memory_collector import memory_collector
    memory_collector.freeze_startup_objects()

    engine.load(QUrl.fromLocalFile(qml_file))

    if not engine.rootObjects():
        logger.error("Failed to load QML interface. The errors above (category 'qt') say why.", category="system")
        logger.end_session("after the window failed to load")
        sys.exit(-1)

    win = engine.rootObjects()[0]

    from core.memory_collector import memory_collector
    _setup_memory_management(app, win, app_bridge, memory_collector)
    memory_collector.start()

    # A window that stops responding writes what it was doing to the log
    from core.hang_detector import hang_detector
    hang_detector.start(app)
    app.aboutToQuit.connect(hang_detector.stop)

    def update_screen_hz(target_screen=None):
        scr = target_screen or win.screen() or app.primaryScreen()
        if scr:
            app_bridge.setScreenHz(int(round(scr.refreshRate())))

    update_screen_hz()
    win.screenChanged.connect(update_screen_hz)

    from services.telegram_service import TelegramService
    app.aboutToQuit.connect(app_bridge.onAppClosing)

    # Exit watchdog: Python waits for every download thread before the process ends. If one is
    # stuck in a network call that never returns, the app would linger with no window (#24).
    def _arm_exit_watchdog():
        import threading as _th

        def _force_exit():
            logger.warning("Some background work didn't stop in time; closing the app anyway.", category="system")
            busy = [t.name for t in _th.enumerate() if t is not _th.current_thread() and not t.daemon]
            if busy:
                logger.warning(f"Still running: {', '.join(busy)}", category="system")
            logger.end_session("after 20s wait (background work didn't stop)")
            os._exit(0)

        t = _th.Timer(20.0, _force_exit)
        t.daemon = True
        t.start()

    app.aboutToQuit.connect(_arm_exit_watchdog)
    app.aboutToQuit.connect(memory_collector.stop)
    app.aboutToQuit.connect(TelegramService.instance().stop)

    logger.success("Application interface initialized successfully.", category="system")
    sys.exit(app.exec())       # the log's closing line is written once background work has stopped


if __name__ == "__main__":
    main()
