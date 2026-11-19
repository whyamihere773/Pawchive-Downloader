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
from core.text_utils import safe_file_name
from core.logger import logger
from core.bandwidth_limiter import bandwidth_limiter

# Automatically apply hardware-accelerated OpenSSL AES-IGE cryptography
if HAS_TELEGRAM:
    patch_telethon_crypto()

# Default application credentials (can be overridden in Settings)
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"


from services.telegram_auth_session import TelegramAuthSessionMixin


class TelegramService(TelegramAuthSessionMixin):
    _instance: Optional["TelegramService"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "TelegramService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir:
            self.data_dir = data_dir
        else:
            from core.path_utils import get_data_dir, migrate_legacy_files
            self.data_dir = os.path.join(get_data_dir(), "data")
            migrate_legacy_files(self.data_dir, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
                                 ("telegram_session.enc", "telegram_user.enc", "pawchive_telegram.session"))
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

                logger.debug(f"Telegram: resolving entity for peer={peer}", category="telegram")
                entity = await client.get_entity(peer)
                channel_title = getattr(entity, "title", "Telegram")
                channel_username = getattr(entity, "username", "") or str(getattr(entity, "id", "channel"))
                logger.debug(f"Telegram: entity resolved: title='{channel_title}', id={getattr(entity, 'id', '?')}", category="telegram")

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
                        fn = safe_file_name(fn, fallback=f"file_{msg.id}")   # chosen by the uploader
                    else:
                        # Unknown media type
                        logger.debug(f"Telegram: msg {msg.id} has unknown media type: {type(msg.media).__name__}", category="telegram")

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

                logger.debug(f"Telegram: iterated {msg_count} messages, {media_count} with media, {skipped_type} skipped by type, {skipped_size} skipped by size, {len(items)} matched", category="telegram")
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
                    fn = safe_file_name(fn, fallback=f"file_{msg.id}")   # chosen by the uploader

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

                    if delta > 0:
                        if not bandwidth_limiter.wait_for(delta, cancel_event, pause_event):
                            raise asyncio.CancelledError("Download cancelled by user")

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
