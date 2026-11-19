"""
Telegram Encrypted Session Storage, Event Loop & Authentication Mixin
Decomposed from services/telegram_service.py to keep modules cohesive and under 1,000 lines.
"""

import asyncio
import base64
import io
import os
import threading
import time
from typing import Any, Dict

try:
    from telethon import TelegramClient, errors
    from telethon.sessions import StringSession
    import qrcode
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    TelegramClient = None
    errors = None
    StringSession = None
    qrcode = None

from core.crypto_utils import decrypt_credential, encrypt_credential
from core.logger import logger

DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"


class TelegramAuthSessionMixin:
    """Manages encrypted Telethon StringSession storage, background asyncio loop, and QR/Phone/2FA/Bot login."""

    def _migrate_legacy_session_if_needed(self):
        """If unencrypted legacy .session SQLite file exists, migrate to encrypted storage and delete plaintext."""
        legacy_file = self.session_path + ".session"
        if os.path.exists(legacy_file):
            if not os.path.exists(self.encrypted_session_path):
                try:
                    from telethon.sessions import SQLiteSession
                    sq = SQLiteSession(self.session_path)
                    if sq.auth_key:
                        ss = StringSession()
                        ss._dc_id = sq.dc_id
                        ss._server_address = sq.server_address
                        ss._port = sq.port
                        ss._auth_key = sq.auth_key
                        saved_str = ss.save()
                        if saved_str:
                            self._save_encrypted_session_string(saved_str)
                            logger.info("Migrated legacy Telegram session to hardware-encrypted storage.", category="telegram")
                    sq.close()
                except Exception as e:
                    logger.debug(f"Failed to migrate legacy Telegram session: {e}", category="telegram")
            for ext in ("", ".session", ".session-journal"):
                fn = self.session_path + ext
                if os.path.exists(fn):
                    try:
                        os.remove(fn)
                    except Exception:
                        pass

    def _load_encrypted_session_string(self) -> str:
        """Loads and decrypts the session string from disk."""
        if not os.path.exists(self.encrypted_session_path):
            return ""
        try:
            with open(self.encrypted_session_path, "rb") as f:
                enc_data = f.read()
            if not enc_data:
                return ""
            raw_bytes = decrypt_credential(enc_data, context="pawchive_telegram")
            session_str = raw_bytes.decode("utf-8", errors="ignore").strip()
            from core.crypto_utils import needs_reencrypt
            if session_str and needs_reencrypt(enc_data):
                self._save_encrypted_session_string(session_str)     # move off the old MAC-address key
            return session_str
        except Exception as e:
            logger.error(f"Failed to decrypt Telegram session: {e}", category="telegram")
            return ""

    def _save_encrypted_session_string(self, session_str: str):
        """Encrypts and atomically persists the session string to disk."""
        if not session_str:
            return
        try:
            raw_bytes = session_str.encode("utf-8")
            enc_data = encrypt_credential(raw_bytes, context="pawchive_telegram")
            tmp_path = self.encrypted_session_path + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(enc_data)
            if os.path.exists(self.encrypted_session_path):
                os.replace(tmp_path, self.encrypted_session_path)
            else:
                os.rename(tmp_path, self.encrypted_session_path)
            logger.debug("Successfully saved encrypted Telegram session.", category="telegram")
        except Exception as e:
            logger.error(f"Failed to save encrypted Telegram session: {e}", category="telegram")

    def has_saved_session(self) -> bool:
        """Returns True if an encrypted Telegram session file exists on disk with content."""
        if not os.path.exists(self.encrypted_session_path):
            return False
        try:
            return bool(self._load_encrypted_session_string())
        except Exception:
            return False

    def _save_cached_user_info(self, info: Dict[str, Any]):
        """Caches user profile info (encrypted) for instant display on app startup."""
        try:
            import json as _json
            raw = _json.dumps(info).encode("utf-8")
            enc = encrypt_credential(raw, context="pawchive_telegram_user")
            path = os.path.join(self.data_dir, "telegram_user.enc")
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(enc)
            if os.path.exists(path):
                os.replace(tmp, path)
            else:
                os.rename(tmp, path)
        except Exception as e:
            logger.debug(f"Failed to cache Telegram user info: {e}", category="telegram")

    def load_cached_user_info(self) -> Dict[str, Any]:
        """Loads cached user profile info from encrypted storage (no network call needed)."""
        path = os.path.join(self.data_dir, "telegram_user.enc")
        if not os.path.exists(path):
            return {}
        try:
            import json as _json
            with open(path, "rb") as f:
                enc = f.read()
            if not enc:
                return {}
            raw = decrypt_credential(enc, context="pawchive_telegram_user")
            return _json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _wipe_cached_user_info(self):
        """Removes the encrypted user info cache file from disk."""
        path = os.path.join(self.data_dir, "telegram_user.enc")
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    def _persist_session(self):
        """Extracts current session string from client and writes it encrypted to disk."""
        if not self._session_authenticated:
            return
        if self._client and self._client.session:
            try:
                auth_key = getattr(self._client.session, "auth_key", None)
                if auth_key:
                    session_str = self._client.session.save()
                    if session_str:
                        self._save_encrypted_session_string(session_str)
            except Exception as e:
                logger.debug(f"Failed to persist Telegram session: {e}", category="telegram")

    def _start_loop(self):
        if self._thread and self._thread.is_alive():
            return

        def _worker():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._running = True
            self._loop.run_forever()

        self._thread = threading.Thread(target=_worker, name="TelegramServiceLoop", daemon=True)
        self._thread.start()

        # Wait until loop is running
        while self._loop is None or not self._loop.is_running():
            time.sleep(0.02)

    def _run_coro(self, coro, timeout: float = 60.0):
        if not self._loop or not self._running:
            raise RuntimeError("TelegramService event loop is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def set_custom_credentials(self, api_id: int, api_hash: str):
        new_id = api_id or DEFAULT_API_ID
        new_hash = api_hash or DEFAULT_API_HASH
        if new_id != self.api_id or new_hash != self.api_hash:
            self.api_id = new_id
            self.api_hash = new_hash
            # Recreate client with new credentials without deleting saved user session
            if self._client:
                try:
                    self._run_coro(self._client.disconnect(), timeout=3.0)
                except Exception:
                    pass
                self._client = None

    def is_available(self) -> bool:
        return HAS_TELEGRAM

    def is_logged_in(self) -> bool:
        if not HAS_TELEGRAM:
            return False
        try:
            return self._run_coro(self._check_login_status(), timeout=10.0)
        except Exception:
            return False

    async def _get_or_create_client(self) -> "TelegramClient":
        if self._client is None:
            session_str = self._load_encrypted_session_string()
            self._string_session = StringSession(session_str)
            self._client = TelegramClient(
                self._string_session,
                self.api_id,
                self.api_hash,
                device_model="Desktop",
                system_version="Windows 10/11",
                app_version="Pawchive Downloader",
                lang_code="en",
                loop=self._loop
            )
        if not self._client.is_connected():
            try:
                await self._client.connect()
            except (errors.SessionRevokedError, errors.AuthKeyUnregisteredError, errors.AuthKeyDuplicatedError) as e:
                # Corrupted / revoked session — wipe and recreate
                logger.warning(f"Telegram auth key was invalidated: {e}", category="telegram")
                await self._reset_session_files()
                self._string_session = StringSession("")
                self._client = TelegramClient(
                    self._string_session,
                    self.api_id,
                    self.api_hash,
                    device_model="Desktop",
                    system_version="Windows 10/11",
                    app_version="Pawchive Downloader",
                    lang_code="en",
                    loop=self._loop
                )
                await self._client.connect()
                if self.on_auth_state_changed:
                    self.on_auth_state_changed(
                        "idle",
                        "Session was corrupted or revoked. Please log in again."
                    )
            except Exception as e:
                # Network error, timeout, or temporary server issue — preserve session!
                logger.warning(f"Telegram connection error: {e}", category="telegram")
                raise
        return self._client

    async def _reset_session_files(self):
        """Wipes the encrypted session file and disconnects the client."""
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._client = None
        self._string_session = None
        self._session_authenticated = False
        self._wipe_cached_user_info()
        if os.path.exists(self.encrypted_session_path):
            try:
                os.remove(self.encrypted_session_path)
            except Exception:
                pass
        for ext in ("", ".session", ".session-journal"):
            fn = self.session_path + ext
            if os.path.exists(fn):
                try:
                    os.remove(fn)
                except Exception:
                    pass

    async def _handle_auth_invalidation(self, reason: str = "Telegram session expired or was revoked. Please log in again."):
        """Verifies with main client before wiping session files to prevent accidental deletion on transient DC errors."""
        try:
            if self._client and await self._client.is_user_authorized():
                logger.warning("Transient Telegram auth key error encountered on secondary connection, but main session is intact. Preserving session.", category="telegram")
                return
        except (errors.SessionRevokedError, errors.AuthKeyUnregisteredError, errors.AuthKeyDuplicatedError):
            # Main session IS definitively invalid — fall through to wipe
            pass
        except Exception as e:
            # Network error, timeout, etc. — cannot confirm invalidity, preserve session defensively
            logger.warning(f"Cannot verify main session due to {type(e).__name__}: {e}. Preserving session defensively.", category="telegram")
            return
        logger.warning(f"Telegram session invalidated: {reason}", category="telegram")
        await self._reset_session_files()
        if self.on_auth_state_changed:
            self.on_auth_state_changed("idle", reason)

    def reset_session(self):
        """Public method to force a full session wipe and re-login (call from bridge)."""
        try:
            self._run_coro(self._reset_session_files(), timeout=10.0)
        except Exception:
            pass
        if self.on_auth_state_changed:
            self.on_auth_state_changed("idle", "Session has been reset. Please log in again.")

    async def _check_login_status(self) -> bool:
        client = await self._get_or_create_client()
        authorized = await client.is_user_authorized()
        if authorized:
            self._session_authenticated = True
        return authorized

    def get_user_info(self) -> Dict[str, Any]:
        if not self.is_logged_in():
            return {"is_logged_in": False}

        async def _coro():
            client = await self._get_or_create_client()
            me = await client.get_me()
            if not me:
                return {"is_logged_in": False}
            info = {
                "is_logged_in": True,
                "id": me.id,
                "first_name": me.first_name or "",
                "last_name": me.last_name or "",
                "username": me.username or "",
                "phone": me.phone or "",
                "is_bot": bool(me.bot)
            }
            self._save_cached_user_info(info)
            return info

        try:
            return self._run_coro(_coro(), timeout=10.0)
        except Exception as e:
            return {"is_logged_in": False, "error": str(e)}

    # ── QR Code Authentication ────────────────────────────────────────────────
    def start_qr_login(self):
        """Starts asynchronous QR code login flow in background."""
        if not HAS_TELEGRAM:
            if self.on_auth_state_changed:
                self.on_auth_state_changed("error", "Telethon or qrcode library is not installed.")
            return

        if self._qr_active:
            logger.debug("QR login already active, ignoring duplicate request.", category="telegram")
            return

        self._qr_active = True

        async def _qr_runner():
            self._qr_task = asyncio.current_task()
            try:
                client = await self._get_or_create_client()
                if await client.is_user_authorized():
                    if self.on_auth_state_changed:
                        self.on_auth_state_changed("connected", "Already authenticated.")
                    return

                if self.on_auth_state_changed:
                    self.on_auth_state_changed("qr_generating", "Generating QR Code...")

                qr_login = await client.qr_login()

                while self._qr_active:
                    # Generate Base64 QR Image
                    qr = qrcode.QRCode(box_size=8, border=2)
                    qr.add_data(qr_login.url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="#FFFFFF", back_color="#0F172A")
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                    data_url = f"data:image/png;base64,{b64}"

                    if self.on_qr_code_updated:
                        self.on_qr_code_updated(data_url)
                    if self.on_auth_state_changed:
                        self.on_auth_state_changed("qr_ready", "Scan with your Telegram app: Settings -> Devices -> Link Desktop Device")

                    try:
                        # Wait for scan with 30s timeout
                        await qr_login.wait(timeout=30)
                        # Success
                        self._qr_active = False
                        self._session_authenticated = True
                        self._persist_session()
                        if self.on_auth_state_changed:
                            self.on_auth_state_changed("connected", "Successfully authenticated via QR Code!")
                        return
                    except asyncio.TimeoutError:
                        if not self._qr_active:
                            break
                        # Token expired; recreate
                        await qr_login.recreate()
                    except errors.SessionPasswordNeededError:
                        self._qr_active = False
                        if self.on_auth_state_changed:
                            self.on_auth_state_changed("need_2fa", "Two-step verification (2FA) cloud password required.")
                        return

            except asyncio.CancelledError:
                logger.debug("QR login task cancelled.", category="telegram")
            except (errors.SessionRevokedError, errors.AuthKeyUnregisteredError, errors.AuthKeyDuplicatedError) as e:
                self._qr_active = False
                logger.warning(f"QR login encountered invalidated session: {e}", category="telegram")
                await self._reset_session_files()
                if self.on_auth_state_changed:
                    self.on_auth_state_changed(
                        "error",
                        "Session was corrupted (invalid auth key). It has been reset — please close and re-open the Telegram login window to log in again."
                    )
            except Exception as e:
                self._qr_active = False
                if self.on_auth_state_changed:
                    self.on_auth_state_changed("error", f"QR Login error: {str(e)}")

        self._qr_future = asyncio.run_coroutine_threadsafe(_qr_runner(), self._loop)

    def cancel_qr_login(self):
        self._qr_active = False
        if self._qr_task and not self._qr_task.done() and self._loop:
            try:
                self._loop.call_soon_threadsafe(self._qr_task.cancel)
            except Exception:
                pass
        if self._qr_future and not self._qr_future.done():
            try:
                self._qr_future.cancel()
            except Exception:
                pass
        if self.on_auth_state_changed:
            self.on_auth_state_changed("idle", "QR code login cancelled.")

    # ── Phone Number + SMS/App Code Authentication ────────────────────────────
    def send_phone_code(self, phone: str):
        async def _coro():
            client = await self._get_or_create_client()
            res = await client.send_code_request(phone)
            self._phone_number = phone
            self._phone_code_hash = res.phone_code_hash
            if self.on_auth_state_changed:
                self.on_auth_state_changed("code_sent", f"Verification code sent to {phone}.")
            return True

        try:
            return self._run_coro(_coro(), timeout=15.0)
        except Exception as e:
            if self.on_auth_state_changed:
                self.on_auth_state_changed("error", f"Failed to send code: {str(e)}")
            return False

    def verify_phone_code(self, code: str):
        if not self._phone_number or not self._phone_code_hash:
            if self.on_auth_state_changed:
                self.on_auth_state_changed("error", "No active phone login session.")
            return False

        async def _coro():
            client = await self._get_or_create_client()
            try:
                await client.sign_in(
                    phone=self._phone_number,
                    code=code.strip(),
                    phone_code_hash=self._phone_code_hash
                )
                self._session_authenticated = True
                self._persist_session()
                if self.on_auth_state_changed:
                    self.on_auth_state_changed("connected", "Successfully logged in via Phone code!")
                return True
            except errors.SessionPasswordNeededError:
                if self.on_auth_state_changed:
                    self.on_auth_state_changed("need_2fa", "Account has 2FA enabled. Enter your password.")
                return True
            except Exception as e:
                if self.on_auth_state_changed:
                    self.on_auth_state_changed("error", f"Invalid code: {str(e)}")
                return False

        return self._run_coro(_coro(), timeout=15.0)

    # ── 2FA Password Submission ───────────────────────────────────────────────
    def submit_2fa_password(self, password: str):
        async def _coro():
            client = await self._get_or_create_client()
            try:
                await client.sign_in(password=password)
                self._session_authenticated = True
                self._persist_session()
                if self.on_auth_state_changed:
                    self.on_auth_state_changed("connected", "2FA authentication successful!")
                return True
            except Exception as e:
                if self.on_auth_state_changed:
                    self.on_auth_state_changed("error", f"Incorrect 2FA password: {str(e)}")
                return False

        return self._run_coro(_coro(), timeout=15.0)

    # ── Bot Token Authentication ──────────────────────────────────────────────
    def login_with_bot_token(self, bot_token: str):
        async def _coro():
            client = await self._get_or_create_client()
            try:
                await client.sign_in(bot_token=bot_token.strip())
                self._session_authenticated = True
                self._persist_session()
                if self.on_auth_state_changed:
                    self.on_auth_state_changed("connected", "Successfully connected via Bot Token!")
                return True
            except Exception as e:
                if self.on_auth_state_changed:
                    self.on_auth_state_changed("error", f"Failed to login with bot token: {str(e)}")
                return False

        return self._run_coro(_coro(), timeout=15.0)

    # ── Logout / Disconnect ───────────────────────────────────────────────────
    def disconnect(self):
        async def _coro():
            if self._client:
                try:
                    await self._client.log_out()
                except Exception:
                    pass
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
                self._string_session = None
            self._session_authenticated = False

            # Remove encrypted session file
            if os.path.exists(self.encrypted_session_path):
                try:
                    os.remove(self.encrypted_session_path)
                except Exception:
                    pass

            # Remove any legacy session files
            for ext in ("", ".session", ".session-journal"):
                fn = self.session_path + ext
                if os.path.exists(fn):
                    try:
                        os.remove(fn)
                    except Exception:
                        pass

            self._wipe_cached_user_info()

            if self.on_auth_state_changed:
                self.on_auth_state_changed("idle", "Logged out successfully.")

        try:
            self._run_coro(_coro(), timeout=10.0)
        except Exception:
            pass

    def stop(self):
        """Flushes session to encrypted storage and cleanly disconnects without logging out."""
        try:
            self._persist_session()
            if self._client:
                try:
                    self._run_coro(self._client.disconnect(), timeout=3.0)
                except Exception:
                    pass
                self._client = None
        except Exception:
            pass
