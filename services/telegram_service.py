"""
Telegram Service & MTProto Manager
Coordinates Telethon async client lifecycle, QR code / Phone / 2FA / Bot authentication,
channel and post resolution, rate-limit backoff, and chunked media downloads.
"""

import os
import sys
import io
import time
import base64
import asyncio
import logging
import threading
import concurrent.futures
from typing import Optional, Dict, Any, List, Callable

try:
    from telethon import TelegramClient, errors, functions, types
    from telethon.sessions import StringSession
    from telethon.tl.types import (
        MessageMediaPhoto,
        MessageMediaDocument,
        DocumentAttributeVideo,
        DocumentAttributeAudio,
        DocumentAttributeFilename,
        Channel,
        Chat
    )
    import qrcode
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    StringSession = None

from core.crypto_utils import encrypt_credential, decrypt_credential, patch_telethon_crypto
from core.logger import logger

# Automatically apply hardware-accelerated OpenSSL AES-IGE cryptography
if HAS_TELEGRAM:
    patch_telethon_crypto()

# Default application credentials (can be overridden in Settings)
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"


class TelegramService:
    _instance: Optional["TelegramService"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "TelegramService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        os.makedirs(self.data_dir, exist_ok=True)
        self.session_path = os.path.join(self.data_dir, "pawchive_telegram")
        self.encrypted_session_path = os.path.join(self.data_dir, "telegram_session.enc")

        # Configurable credentials
        self.api_id = DEFAULT_API_ID
        self.api_hash = DEFAULT_API_HASH

        # Concurrency & limits
        self.max_concurrent_downloads = 2
        self.flood_wait_seconds = 0
        self.is_flood_waiting = False
        self._download_semaphore: Optional[asyncio.Semaphore] = None
        self._entity_cache: Dict[str, Any] = {}

        # Internal state
        self._client: Optional["TelegramClient"] = None
        self._string_session: Optional[Any] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._qr_active = False
        self._qr_future: Optional[Any] = None
        self._qr_task: Optional[asyncio.Task] = None
        self._phone_code_hash: Optional[str] = None
        self._phone_number: Optional[str] = None
        self._session_authenticated = False  # True only after confirmed user authorization

        # Active download tracking for instant cancellation
        self._active_download_tasks: set = set()
        self._active_download_futures: set = set()
        self._active_download_lock = threading.Lock()

        # Callbacks
        self.on_qr_code_updated: Optional[Callable[[str], None]] = None  # (base64_data_url)
        self.on_auth_state_changed: Optional[Callable[[str, str], None]] = None  # (state, message)
        self.on_flood_wait: Optional[Callable[[int], None]] = None  # (seconds)

        # Migrate legacy plaintext .session SQLite files to encrypted storage
        self._migrate_legacy_session_if_needed()

        if HAS_TELEGRAM:
            self._start_loop()

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
            return raw_bytes.decode("utf-8", errors="ignore").strip()
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

    # ── Channel & Message Resolution ─────────────────────────────────────────
    def resolve_target_metadata(self, target: str, is_private: bool = False) -> Dict[str, Any]:
        """Fetches channel or chat metadata (title, username, photo, count)."""
        async def _coro():
            try:
                client = await self._get_or_create_client()
                entity = None

                # Handle invite links (t.me/+... or t.me/joinchat/...)
                if "joinchat/" in target or "+" in target:
                    hash_part = target.split("+")[-1].split("/")[-1]
                    try:
                        invite_info = await client(functions.messages.CheckChatInviteRequest(hash=hash_part))
                        if isinstance(invite_info, types.ChatInvite):
                            return {
                                "title": invite_info.title,
                                "username": "",
                                "is_private": True,
                                "is_channel": invite_info.channel,
                                "members_count": invite_info.participants_count,
                                "needs_join": True,
                                "invite_hash": hash_part
                            }
                        elif isinstance(invite_info, types.ChatInviteAlready):
                            entity = invite_info.chat
                    except Exception as e:
                        return {"title": "Private Channel", "error": str(e), "is_private": True}

                if not entity:
                    # Target can be integer channel ID (for private channels) or username
                    try:
                        if target.isdigit():
                            entity = await client.get_entity(int(f"-100{target}" if not target.startswith("-100") else target))
                        else:
                            entity = await client.get_entity(target)
                    except (errors.SessionRevokedError, errors.AuthKeyUnregisteredError) as e:
                        logger.warning(f"Telegram session was revoked or invalidated: {e}", category="telegram")
                        await self._handle_auth_invalidation("Telegram session expired or was revoked. Please log in again.")
                        return {
                            "title": target,
                            "error": "Telegram session expired or was revoked. Please log in again.",
                            "is_private": is_private
                        }
                    except Exception as e:
                        return {
                            "title": target,
                            "error": str(e),
                            "is_private": is_private
                        }

                title = getattr(entity, "title", None) or getattr(entity, "first_name", target)
                username = getattr(entity, "username", "") or ""
                ent_id = getattr(entity, "id", None)
                if ent_id:
                    self._entity_cache[str(ent_id)] = entity
                self._entity_cache[str(target)] = entity
                return {
                    "title": title,
                    "username": username,
                    "is_private": is_private or not bool(username),
                    "id": ent_id
                }
            except (errors.SessionRevokedError, errors.AuthKeyUnregisteredError) as e:
                logger.warning(f"Telegram session was revoked or invalidated: {e}", category="telegram")
                await self._handle_auth_invalidation("Telegram session expired or was revoked. Please log in again.")
                return {
                    "title": target,
                    "error": "Telegram session expired or was revoked. Please log in again.",
                    "is_private": is_private
                }

        return self._run_coro(_coro(), timeout=20.0)

    def fetch_channel_messages(
        self,
        target: str,
        limit: int = 100,
        media_types: Optional[List[str]] = None,
        max_size_mb: int = 0,
        fetch_thumbnails: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetches messages with attachments from public/private channels.
        media_types: ['video', 'photo', 'document', 'audio']
        fetch_thumbnails: If True, fetches and caches small preview thumbnails for visual post selection.
        """
        media_types = media_types or ["video", "photo", "document", "audio"]

        async def _coro():
            try:
                client = await self._get_or_create_client()
                if target.isdigit():
                    peer = int(f"-100{target}" if not target.startswith("-100") else target)
                else:
                    peer = target

                print(f">>> TG_SERVICE: resolving entity for peer={peer}", flush=True)
                entity = await client.get_entity(peer)
                channel_title = getattr(entity, "title", "Telegram")
                channel_username = getattr(entity, "username", "") or str(getattr(entity, "id", "channel"))
                print(f">>> TG_SERVICE: entity resolved: title='{channel_title}', id={getattr(entity, 'id', '?')}", flush=True)

                ent_id = getattr(entity, "id", None)
                if ent_id:
                    self._entity_cache[str(ent_id)] = entity
                self._entity_cache[str(target)] = entity

                items = []
                msg_count = 0
                media_count = 0
                skipped_type = 0
                skipped_size = 0

                # Deep scan ceiling so channels/groups with text messages can be scanned to collect `limit` media items
                max_scan = max(limit * 30, 3000)

                video_exts = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v"}
                audio_exts = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
                image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

                async for msg in client.iter_messages(entity, limit=max_scan):
                    msg_count += 1
                    if not msg.media:
                        continue
                    media_count += 1

                    fn = ""
                    m_type = "document"
                    file_size = 0

                    if isinstance(msg.media, MessageMediaPhoto):
                        m_type = "photo"
                        fn = f"photo_{msg.id}.jpg"
                        file_size = 0  # Photos don't have explicit size in photo object
                    elif isinstance(msg.media, MessageMediaDocument):
                        doc = msg.media.document
                        file_size = doc.size if doc else 0

                        # Check attributes
                        is_video = any(isinstance(a, DocumentAttributeVideo) for a in (doc.attributes or []))
                        is_audio = any(isinstance(a, DocumentAttributeAudio) for a in (doc.attributes or []))

                        # Get filename
                        for a in (doc.attributes or []):
                            if isinstance(a, DocumentAttributeFilename):
                                fn = a.file_name
                                break

                        lower_fn = fn.lower() if fn else ""
                        if is_video or any(lower_fn.endswith(ext) for ext in video_exts):
                            m_type = "video"
                        elif is_audio or any(lower_fn.endswith(ext) for ext in audio_exts):
                            m_type = "audio"
                        elif any(lower_fn.endswith(ext) for ext in image_exts):
                            m_type = "photo"
                        else:
                            m_type = "document"

                        if not fn:
                            ext = ".mp4" if m_type == "video" else (".mp3" if m_type == "audio" else ".bin")
                            fn = f"file_{msg.id}{ext}"
                    else:
                        # Unknown media type
                        print(f">>> TG_SERVICE: msg {msg.id} has unknown media type: {type(msg.media).__name__}", flush=True)

                    if m_type not in media_types:
                        skipped_type += 1
                        continue

                    if max_size_mb > 0 and file_size > (max_size_mb * 1024 * 1024):
                        skipped_size += 1
                        continue

                    caption = msg.message or ""
                    date_str = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else ""

                    thumb_url = ""
                    if fetch_thumbnails and msg.media:
                        try:
                            from pathlib import Path
                            tg_thumb_dir = Path.home() / ".pawchive_telegram_cache" / "thumbs"
                            tg_thumb_dir.mkdir(parents=True, exist_ok=True)
                            local_thumb_file = tg_thumb_dir / f"tg_thumb_{getattr(entity, 'id', target)}_{msg.id}.jpg"
                            if local_thumb_file.exists() and local_thumb_file.stat().st_size > 0:
                                thumb_url = local_thumb_file.as_uri()
                            else:
                                downloaded_thumb = await asyncio.wait_for(
                                    client.download_media(msg, file=str(local_thumb_file), thumb=-1),
                                    timeout=4.0
                                )
                                if downloaded_thumb and os.path.exists(downloaded_thumb) and os.path.getsize(downloaded_thumb) > 0:
                                    thumb_url = Path(downloaded_thumb).as_uri()
                        except Exception as thumb_err:
                            logger.debug(f"Could not load thumbnail for TG msg {msg.id}: {thumb_err}", category="telegram")

                    items.append({
                        "id": str(msg.id),
                        "title": fn or f"Telegram Media {msg.id}",
                        "filename": fn,
                        "media_type": m_type,
                        "file_size": file_size,
                        "caption": caption,
                        "date": date_str,
                        "channel_title": channel_title,
                        "channel_username": channel_username,
                        "message_id": msg.id,
                        "channel_id": str(getattr(entity, "id", target)),
                        "url": f"tg://{getattr(entity, 'id', target)}/{msg.id}",
                        "thumbnail": thumb_url
                    })

                    if len(items) >= limit:
                        break

                print(f">>> TG_SERVICE: iterated {msg_count} messages, {media_count} with media, {skipped_type} skipped by type, {skipped_size} skipped by size, {len(items)} matched", flush=True)
                return items
            except (errors.SessionRevokedError, errors.AuthKeyUnregisteredError) as e:
                logger.warning(f"Telegram session was revoked or invalidated: {e}", category="telegram")
                await self._handle_auth_invalidation("Telegram session expired or was revoked. Please log in again.")
                raise RuntimeError("Telegram session expired or was revoked. Please log in again.") from e

        return self._run_coro(_coro(), timeout=120.0)

    def fetch_single_post(self, channel_target: str, message_id: int) -> Optional[Dict[str, Any]]:
        """Fetches a specific message by channel and message ID."""
        async def _coro():
            try:
                client = await self._get_or_create_client()
                if channel_target.isdigit():
                    peer = int(f"-100{channel_target}" if not channel_target.startswith("-100") else channel_target)
                else:
                    peer = channel_target

                msg = await client.get_messages(peer, ids=message_id)
                if not msg or not msg.media:
                    return None

                fn = ""
                m_type = "document"
                file_size = 0

                video_exts = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v"}
                audio_exts = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}
                image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

                if isinstance(msg.media, MessageMediaPhoto):
                    m_type = "photo"
                    fn = f"photo_{msg.id}.jpg"
                elif isinstance(msg.media, MessageMediaDocument):
                    doc = msg.media.document
                    file_size = doc.size if doc else 0
                    is_video = any(isinstance(a, DocumentAttributeVideo) for a in (doc.attributes or []))
                    is_audio = any(isinstance(a, DocumentAttributeAudio) for a in (doc.attributes or []))

                    for a in (doc.attributes or []):
                        if isinstance(a, DocumentAttributeFilename):
                            fn = a.file_name
                            break

                    lower_fn = fn.lower() if fn else ""
                    if is_video or any(lower_fn.endswith(ext) for ext in video_exts):
                        m_type = "video"
                    elif is_audio or any(lower_fn.endswith(ext) for ext in audio_exts):
                        m_type = "audio"
                    elif any(lower_fn.endswith(ext) for ext in image_exts):
                        m_type = "photo"
                    else:
                        m_type = "document"

                    if not fn:
                        ext = ".mp4" if m_type == "video" else (".mp3" if m_type == "audio" else ".bin")
                        fn = f"file_{msg.id}{ext}"

                caption = msg.message or ""
                date_str = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else ""

                return {
                    "id": str(msg.id),
                    "title": fn or f"Telegram Media {msg.id}",
                    "filename": fn,
                    "media_type": m_type,
                    "file_size": file_size,
                    "caption": caption,
                    "date": date_str,
                    "message_id": msg.id,
                    "channel_id": channel_target,
                    "url": f"tg://{channel_target}/{msg.id}"
                }
            except (errors.SessionRevokedError, errors.AuthKeyUnregisteredError) as e:
                logger.warning(f"Telegram session was revoked or invalidated: {e}", category="telegram")
                await self._handle_auth_invalidation("Telegram session expired or was revoked. Please log in again.")
                raise RuntimeError("Telegram session expired or was revoked. Please log in again.") from e

        return self._run_coro(_coro(), timeout=20.0)

    def cancel_all_downloads(self):
        """Instantly terminates all active Telegram media download tasks and coroutines."""
        with self._active_download_lock:
            for fut in list(self._active_download_futures):
                try:
                    fut.cancel()
                except Exception:
                    pass
            self._active_download_futures.clear()

        if self._loop and self._loop.is_running():
            def _cancel_tasks():
                with self._active_download_lock:
                    for t in list(self._active_download_tasks):
                        if not t.done():
                            t.cancel()
                    self._active_download_tasks.clear()
            try:
                self._loop.call_soon_threadsafe(_cancel_tasks)
            except Exception:
                pass

    # ── Media File Download Execution ─────────────────────────────────────────
    def download_media(
        self,
        channel_id: str,
        message_id: int,
        target_path: str,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None
    ) -> tuple[bool, str]:
        """
        Downloads a media file chunk by chunk, reporting progress,
        handling pause/cancel events and FloodWait backoff.
        """
        async def _coro():
            curr_task = asyncio.current_task()
            if curr_task is not None:
                with self._active_download_lock:
                    self._active_download_tasks.add(curr_task)

            try:
                try:
                    client = await self._get_or_create_client()
                    cached_peer = self._entity_cache.get(str(channel_id))
                    if cached_peer is not None:
                        peer = cached_peer
                    elif channel_id.isdigit():
                        peer = int(f"-100{channel_id}" if not channel_id.startswith("-100") else channel_id)
                    else:
                        peer = channel_id

                    msg = await client.get_messages(peer, ids=message_id)
                    if not msg or not msg.media:
                        return False, "Message or media not found"
                except (errors.SessionRevokedError, errors.AuthKeyUnregisteredError, errors.AuthKeyDuplicatedError) as e:
                    logger.warning(f"Telegram session was revoked or invalidated: {e}", category="telegram")
                    await self._handle_auth_invalidation("Telegram session expired or was revoked. Please log in again.")
                    return False, "Telegram session expired or was revoked. Please log in again."
                except Exception as e:
                    return False, str(e)

                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                part_path = target_path + ".part"

                last_bytes = [0]
                start_time = [time.time()]
                last_callback_time = [0.0]
                last_speed_time = [time.time()]
                bytes_since_speed = [0]
                cached_speed_str = ["0 KB/s"]
                cached_eta_str = ["--"]

                def _prog(received_bytes, total_bytes):
                    if cancel_event and cancel_event.is_set():
                        raise asyncio.CancelledError("Download cancelled by user")

                    delta = received_bytes - last_bytes[0]
                    last_bytes[0] = received_bytes
                    bytes_since_speed[0] += max(0, delta)

                    now = time.time()
                    is_finished = (total_bytes > 0 and received_bytes >= total_bytes)

                    # Throttle progress callbacks to max 4 times per second (every 250ms) unless finished
                    if not is_finished and (now - last_callback_time[0] < 0.25):
                        return
                    last_callback_time[0] = now

                    # Compute live windowed speed and ETA
                    dt_speed = max(0.001, now - last_speed_time[0])
                    if dt_speed >= 0.25 or is_finished:
                        spd = bytes_since_speed[0] / dt_speed
                        cached_speed_str[0] = f"{spd / (1024 * 1024):.1f} MB/s" if spd >= 1024 * 1024 else f"{spd / 1024:.1f} KB/s"
                        rem = max(0, total_bytes - received_bytes)
                        eta_s = int(rem / max(1, spd))
                        cached_eta_str[0] = f"{eta_s}s" if eta_s < 60 else f"{eta_s // 60}m {eta_s % 60}s"
                        last_speed_time[0] = now
                        bytes_since_speed[0] = 0

                    if progress_callback:
                        try:
                            progress_callback(received_bytes, total_bytes, cached_speed_str[0], cached_eta_str[0])
                        except Exception:
                            pass

                if self._download_semaphore is None:
                    self._download_semaphore = asyncio.Semaphore(self.max_concurrent_downloads)

                async with self._download_semaphore:
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            await client.download_media(
                                msg,
                                file=part_path,
                                progress_callback=_prog
                            )
                            # Successfully finished
                            if os.path.exists(target_path):
                                os.remove(target_path)
                            os.rename(part_path, target_path)
                            return True, "Download successful"

                        except asyncio.CancelledError:
                            if os.path.exists(part_path):
                                try:
                                    os.remove(part_path)
                                except Exception:
                                    pass
                            return False, "Cancelled by user"

                        except errors.FloodWaitError as e:
                            self.flood_wait_seconds = e.seconds
                            self.is_flood_waiting = True
                            if self.on_flood_wait:
                                self.on_flood_wait(e.seconds)

                            # Sleep remaining seconds + 1
                            for sec in range(e.seconds, 0, -1):
                                if cancel_event and cancel_event.is_set():
                                    return False, "Cancelled during flood wait"
                                if self.on_flood_wait:
                                    self.on_flood_wait(sec)
                                await asyncio.sleep(1)

                            self.is_flood_waiting = False
                            self.flood_wait_seconds = 0
                            if self.on_flood_wait:
                                self.on_flood_wait(0)

                        except (errors.SessionRevokedError, errors.AuthKeyUnregisteredError, errors.AuthKeyDuplicatedError) as e:
                            logger.warning(f"Telegram session was revoked or invalidated during download: {e}", category="telegram")
                            await self._handle_auth_invalidation("Telegram session expired or was revoked. Please log in again.")
                            if os.path.exists(part_path):
                                try:
                                    os.remove(part_path)
                                except Exception:
                                    pass
                            return False, "Telegram session expired or was revoked. Please log in again."

                        except Exception as e:
                            if attempt == max_retries - 1:
                                if os.path.exists(part_path):
                                    try:
                                        os.remove(part_path)
                                    except Exception:
                                        pass
                                return False, str(e)
                            await asyncio.sleep(2)

                    return False, "Exceeded retry limit"
            finally:
                if curr_task is not None:
                    with self._active_download_lock:
                        self._active_download_tasks.discard(curr_task)

        if cancel_event and cancel_event.is_set():
            return False, "Cancelled by user"

        if not self._loop or not self._running:
            raise RuntimeError("TelegramService event loop is not running")

        future = asyncio.run_coroutine_threadsafe(_coro(), self._loop)
        with self._active_download_lock:
            self._active_download_futures.add(future)

        try:
            while not future.done():
                if cancel_event and cancel_event.is_set():
                    future.cancel()
                    self.cancel_all_downloads()
                    part_path = target_path + ".part"
                    if os.path.exists(part_path):
                        try:
                            os.remove(part_path)
                        except Exception:
                            pass
                    return False, "Cancelled by user"
                try:
                    return future.result(timeout=0.08)
                except (TimeoutError, concurrent.futures.TimeoutError):
                    continue
            return future.result(timeout=0.2)
        except (asyncio.CancelledError, concurrent.futures.CancelledError):
            part_path = target_path + ".part"
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except Exception:
                    pass
            return False, "Cancelled by user"
        except Exception as e:
            return False, str(e)
        finally:
            with self._active_download_lock:
                self._active_download_futures.discard(future)
