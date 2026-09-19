"""
Telegram Bridge
Exposes TelegramService state, authentication flows, QR code generation,
channel metadata resolution, and download controls to PySide6 / QML.
"""

from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer
from typing import Dict, Any, List, Optional
from services.telegram_service import TelegramService


class TelegramBridge(QObject):
    # ── Public signals ─────────────────────────────────────────────────────
    isLoggedInChanged = Signal()
    currentUsernameChanged = Signal()
    currentPhoneChanged = Signal()
    loginStateChanged = Signal()
    statusMessageChanged = Signal()
    qrCodeDataUrlChanged = Signal()
    cooldownSecondsChanged = Signal()
    isFloodWaitingChanged = Signal()
    disclaimerAcceptedChanged = Signal()

    channelMetadataReady = Signal(dict)
    channelMessagesReady = Signal(list)
    channelMessagesForSelectionReady = Signal(list)
    channelResolutionFailed = Signal(str)
    authRequired = Signal(bool)  # is_private

    # ── Private relay signals (thread-safe bridge from background → main) ──
    # Emitting a signal from a non-main thread is safe in Qt; the connection
    # is automatically queued, so the slot runs on the object's (main) thread.
    _relayAuthState = Signal(str, str)
    _relayQrUpdated = Signal(str)
    _relayFloodWait = Signal(int)
    _relayStatusChecked = Signal(bool, dict)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._service = TelegramService.instance()

        has_session = self._service.has_saved_session()
        self._is_logged_in = has_session
        cached_info = self._service.load_cached_user_info() if has_session else {}
        if cached_info.get("is_logged_in"):
            uname = cached_info.get("username", "")
            fname = cached_info.get("first_name", "")
            self._current_username = uname or fname or "Telegram User"
            self._current_phone = cached_info.get("phone", "")
        else:
            self._current_username = ""
            self._current_phone = ""
        self._login_state = "checking" if has_session else "idle"
        self._status_message = "Verifying Telegram session..." if has_session else ""
        self._qr_code_data_url = ""
        self._cooldown_seconds = 0
        self._is_flood_waiting = False
        self._disclaimer_accepted = False

        # Wire relay signals → main-thread slots (auto queued cross-thread)
        self._relayAuthState.connect(self._apply_auth_state)
        self._relayQrUpdated.connect(self._apply_qr_update)
        self._relayFloodWait.connect(self._apply_flood_wait)
        self._relayStatusChecked.connect(self._apply_status_checked)

        # Hook service callbacks (called from Telethon background thread)
        self._service.on_qr_code_updated = self._on_qr_updated
        self._service.on_auth_state_changed = self._on_auth_state
        self._service.on_flood_wait = self._on_flood_wait

        # Initial check (QTimer.singleShot is safe here — called from main thread)
        QTimer.singleShot(250, self.checkStatus)

    # ── Properties ────────────────────────────────────────────────────────────

    @Property(bool, constant=True)
    def isAvailable(self) -> bool:
        return self._service.is_available()

    @Property(bool, notify=isLoggedInChanged)
    def isLoggedIn(self) -> bool:
        return self._is_logged_in

    @Property(str, notify=currentUsernameChanged)
    def currentUsername(self) -> str:
        return self._current_username

    @Property(str, notify=currentPhoneChanged)
    def currentPhone(self) -> str:
        return self._current_phone

    @Property(str, notify=loginStateChanged)
    def loginState(self) -> str:
        return self._login_state

    @Property(str, notify=statusMessageChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=qrCodeDataUrlChanged)
    def qrCodeDataUrl(self) -> str:
        return self._qr_code_data_url

    @Property(int, notify=cooldownSecondsChanged)
    def cooldownSeconds(self) -> int:
        return self._cooldown_seconds

    @Property(bool, notify=isFloodWaitingChanged)
    def isFloodWaiting(self) -> bool:
        return self._is_flood_waiting

    @Property(bool, notify=disclaimerAcceptedChanged)
    def disclaimerAccepted(self) -> bool:
        return self._disclaimer_accepted

    # ── Raw callbacks (called from Telethon background thread) ──────────────
    # These only emit relay signals — signal emission is thread-safe in Qt.
    def _on_qr_updated(self, data_url: str):
        self._relayQrUpdated.emit(data_url)

    def _on_auth_state(self, state: str, message: str):
        self._relayAuthState.emit(state, message)

    def _on_flood_wait(self, seconds: int):
        self._relayFloodWait.emit(seconds)

    # ── Relay slots (always run on main thread via queued connection) ─────────
    @Slot(str)
    def _apply_qr_update(self, data_url: str):
        self._qr_code_data_url = data_url
        self.qrCodeDataUrlChanged.emit()

    @Slot(str, str)
    def _apply_auth_state(self, state: str, message: str):
        self._login_state = state
        self._status_message = message
        self.loginStateChanged.emit()
        self.statusMessageChanged.emit()
        if state == "connected":
            self.checkStatus()

    @Slot(int)
    def _apply_flood_wait(self, seconds: int):
        self._cooldown_seconds = seconds
        self._is_flood_waiting = (seconds > 0)
        self.cooldownSecondsChanged.emit()
        self.isFloodWaitingChanged.emit()

    @Slot(bool, dict)
    def _apply_status_checked(self, logged_in: bool, info: dict):
        if logged_in:
            uname = info.get("username", "")
            fname = info.get("first_name", "")
            self._current_username = uname or fname or "Telegram User"
            self._current_phone = info.get("phone", "")
            self._login_state = "connected"
            display_handle = f"@{uname}" if uname else fname
            self._status_message = f"Connected as {display_handle}" if display_handle else "Connected"
        else:
            self._current_username = ""
            self._current_phone = ""
            self._login_state = "idle"
            self._status_message = ""

        if logged_in != self._is_logged_in:
            self._is_logged_in = logged_in
            self.isLoggedInChanged.emit()

        self.currentUsernameChanged.emit()
        self.currentPhoneChanged.emit()
        self.loginStateChanged.emit()
        self.statusMessageChanged.emit()

    # ── Invokable Slots ───────────────────────────────────────────────────────
    @Slot()
    def checkStatus(self):
        if not self._service.is_available():
            self._is_logged_in = False
            self.isLoggedInChanged.emit()
            return

        if self._login_state in ("qr_generating", "qr_ready"):
            return

        def _worker():
            try:
                logged_in = self._service.is_logged_in()
                info = self._service.get_user_info() if logged_in else {}
            except Exception:
                logged_in = False
                info = {}
            self._relayStatusChecked.emit(logged_in, info)

        import threading
        threading.Thread(target=_worker, name="TelegramBridgeCheckStatus", daemon=True).start()

    @Slot()
    def startQrLogin(self):
        if self._is_logged_in:
            return
        self._qr_code_data_url = ""
        self.qrCodeDataUrlChanged.emit()
        self._login_state = "qr_generating"
        self._status_message = "Preparing QR Code..."
        self.loginStateChanged.emit()
        self.statusMessageChanged.emit()
        self._service.start_qr_login()

    @Slot()
    def cancelQrLogin(self):
        self._service.cancel_qr_login()
        self._login_state = "idle"
        self._status_message = ""
        self._qr_code_data_url = ""
        self.loginStateChanged.emit()
        self.statusMessageChanged.emit()
        self.qrCodeDataUrlChanged.emit()

    @Slot(str)
    def sendPhoneCode(self, phone: str):
        self._service.send_phone_code(phone.strip())

    @Slot(str)
    def verifyPhoneCode(self, code: str):
        self._service.verify_phone_code(code.strip())

    @Slot(str)
    def submit2faPassword(self, password: str):
        self._service.submit_2fa_password(password)

    @Slot(str)
    def loginWithBotToken(self, token: str):
        self._service.login_with_bot_token(token.strip())

    @Slot()
    def disconnectAccount(self):
        def _worker():
            self._service.disconnect()
            self.checkStatus()
        import threading
        threading.Thread(target=_worker, daemon=True).start()

    @Slot(int, str)
    def setCustomCredentials(self, api_id: int, api_hash: str):
        def _worker():
            self._service.set_custom_credentials(api_id, api_hash)
            self.checkStatus()
        import threading
        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def resetSession(self):
        """Wipes the Telethon session file, forcing a clean re-login."""
        def _worker():
            self._service.reset_session()
        import threading
        threading.Thread(target=_worker, daemon=True).start()
        self._is_logged_in = False
        self._current_username = ""
        self._current_phone = ""
        self._login_state = "idle"
        self._status_message = "Session reset. Please log in again."
        self.isLoggedInChanged.emit()
        self.currentUsernameChanged.emit()
        self.currentPhoneChanged.emit()
        self.loginStateChanged.emit()
        self.statusMessageChanged.emit()

    @Slot()
    def acceptDisclaimer(self):
        self._disclaimer_accepted = True
        self.disclaimerAcceptedChanged.emit()

    @Slot(str, bool)
    def resolveTarget(self, target: str, is_private: bool = False):
        def _worker():
            try:
                meta = self._service.resolve_target_metadata(target, is_private=is_private)
                if "error" in meta and not meta.get("title"):
                    self.channelResolutionFailed.emit(meta.get("error", "Unknown resolution error"))
                else:
                    self.channelMetadataReady.emit(meta)
            except Exception as e:
                self.channelResolutionFailed.emit(str(e))

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    @Slot(str, int, list, int)
    @Slot(str, int, list, int, bool)
    def fetchMessages(self, target: str, limit: int, media_types: List[str], max_size_mb: int, for_selection: bool = False):
        import logging, sys
        print(f">>> FETCH_MESSAGES CALLED: target={target}, limit={limit}, types={media_types}, max_size={max_size_mb}, for_selection={for_selection}", flush=True)
        logger = logging.getLogger("pawchive")
        logger.info(f"[TelegramBridge] fetchMessages called: target={target}, limit={limit}, media_types={media_types}, max_size_mb={max_size_mb}, for_selection={for_selection}")

        def _worker():
            try:
                print(">>> WORKER STARTED", flush=True)
                msgs = self._service.fetch_channel_messages(
                    target=target,
                    limit=limit,
                    media_types=media_types,
                    max_size_mb=max_size_mb,
                    fetch_thumbnails=for_selection
                )
                print(f">>> WORKER GOT {len(msgs)} messages", flush=True)
                if for_selection:
                    self.channelMessagesForSelectionReady.emit(msgs)
                else:
                    self.channelMessagesReady.emit(msgs)
                print(">>> SIGNAL EMITTED", flush=True)
            except Exception as e:
                print(f">>> WORKER EXCEPTION: {e}", flush=True)
                self.channelResolutionFailed.emit(str(e))

        import threading
        threading.Thread(target=_worker, daemon=True).start()


