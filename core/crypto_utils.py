"""
Pawchive Downloader — Secure Credential Encryption Utilities
Provides hardware- and user-bound DPAPI encryption on Windows (CryptProtectData / CryptUnprotectData)
with an authenticated AES-256-GCM fallback on non-Windows platforms.
"""

import os
import sys
import time
import uuid
import hashlib
import ctypes
from ctypes import wintypes

from core.logger import logger

try:
    from Crypto.Cipher import AES
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


_KEY_FILE_NAME = ".credential_key"


def _key_file_path() -> str:
    try:
        from core.path_utils import get_config_dir
        return os.path.join(get_config_dir(), _KEY_FILE_NAME)
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".pawchive_credential_key")


def _local_key() -> bytes:
    """A random 256-bit key kept in a private file (owner read/write only), created on first use.

    Replaces the old key derived from the network card's MAC address: that address can't always be
    read (Python then returns a random number on every start, e.g. in Flatpak/containers) and changes
    with USB Wi-Fi adapters or docks — either way saved logins could no longer be decrypted.
    """
    path = _key_file_path()
    try:
        with open(path, "rb") as f:
            key = f.read()
        if len(key) == 32:
            return key
        # Damaged: keep it aside (never overwrite a key that may still be needed)
        try:
            os.replace(path, path + f".damaged-{int(time.time())}")
        except OSError:
            pass
    except FileNotFoundError:
        pass
    # Any other read error (permissions, a locked or offline drive) is raised: making a new key
    # here would overwrite the real one and every saved login would become unreadable for good
    key = os.urandom(32)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _legacy_mac_key(entropy: bytes) -> bytes:
    return hashlib.sha256(str(uuid.getnode()).encode("utf-8") + entropy).digest()


def needs_reencrypt(enc_payload: bytes) -> bool:
    """True for data still encrypted with the old MAC-address key (re-save it to upgrade)."""
    return bool(enc_payload) and enc_payload.startswith(b"AESGCM\x01")


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_char))
    ]


def encrypt_credential(raw_bytes: bytes, context: str = "pawchive_telegram") -> bytes:
    """
    Encrypts raw bytes using Windows DPAPI (hardware- and Windows account-tied).
    Falls back to AES-256-GCM with machine-derived key on non-Windows platforms.
    Returns binary payload with version identifier header.
    """
    if not raw_bytes:
        return b""

    entropy = f"pawchive_{context}_secure_salt".encode("utf-8")

    if sys.platform == "win32":
        try:
            in_blob = DATA_BLOB(len(raw_bytes), ctypes.cast(ctypes.create_string_buffer(raw_bytes), ctypes.POINTER(ctypes.c_char)))
            ent_blob = DATA_BLOB(len(entropy), ctypes.cast(ctypes.create_string_buffer(entropy), ctypes.POINTER(ctypes.c_char)))
            out_blob = DATA_BLOB()
            ret = ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(in_blob),
                f"pawchive_{context}",
                ctypes.byref(ent_blob),
                None,
                None,
                0x01,  # CRYPTPROTECT_UI_FORBIDDEN
                ctypes.byref(out_blob)
            )
            if ret:
                enc_data = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                ctypes.windll.kernel32.LocalFree(out_blob.pbData)
                return b"DPAPI\x01" + enc_data
        except Exception as e:
            logger.debug(f"[Crypto] DPAPI encryption failed, falling back to AES: {e}", category="system")

    # Elsewhere (and if DPAPI fails): AES-256-GCM with the private random key file
    if _HAS_CRYPTO:
        key = hashlib.sha256(_local_key() + entropy).digest()
        cipher = AES.new(key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(raw_bytes)
        return b"AESGCM\x02" + cipher.nonce + tag + ciphertext

    raise RuntimeError("No cryptographic provider available to secure credential.")


def decrypt_credential(enc_payload: bytes, context: str = "pawchive_telegram") -> bytes:
    """
    Decrypts binary payload encrypted by encrypt_credential.
    """
    if not enc_payload:
        return b""

    entropy = f"pawchive_{context}_secure_salt".encode("utf-8")

    if enc_payload.startswith(b"DPAPI\x01"):
        raw_dpapi = enc_payload[6:]
        in_blob = DATA_BLOB(len(raw_dpapi), ctypes.cast(ctypes.create_string_buffer(raw_dpapi), ctypes.POINTER(ctypes.c_char)))
        ent_blob = DATA_BLOB(len(entropy), ctypes.cast(ctypes.create_string_buffer(entropy), ctypes.POINTER(ctypes.c_char)))
        out_blob = DATA_BLOB()
        ret = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            ctypes.byref(ent_blob),
            None,
            None,
            0x01,  # CRYPTPROTECT_UI_FORBIDDEN
            ctypes.byref(out_blob)
        )
        if not ret:
            raise RuntimeError("Windows DPAPI decryption failed (CryptUnprotectData returned 0).")
        res = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return res

    elif enc_payload[:7] in (b"AESGCM\x01", b"AESGCM\x02") and _HAS_CRYPTO:
        data = enc_payload[7:]
        nonce = data[:16]
        tag = data[16:32]
        ciphertext = data[32:]
        if enc_payload[6:7] == b"\x02":
            key = hashlib.sha256(_local_key() + entropy).digest()
        else:
            key = _legacy_mac_key(entropy)     # older versions; re-saved with the new key on next save
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    raise ValueError("Unrecognized or unsupported encrypted payload format.")


def patch_telethon_crypto() -> str:
    """
    Accelerates Telethon MTProto cryptography.
    On Windows/macOS/Linux, Telethon often fails to locate OpenSSL via ctypes.util.find_library,
    falling back to pure Python pyaes which runs at ~0.64 MB/s and locks the GIL 100%.
    This function locates the native OpenSSL libcrypto library and wires AES_ige_encrypt
    directly into telethon.crypto.libssl and telethon.crypto.aes.AES (~100 MB/s, 150x faster).
    If libcrypto is not found, falls back to PyCryptodome AES-ECB (~5 MB/s).
    """
    try:
        import telethon.crypto.libssl as libssl
        import telethon.crypto.aes as aes
    except ImportError:
        return "telethon_not_installed"

    # Already accelerated?
    if getattr(libssl, "_pawchive_accelerated", False):
        return getattr(libssl, "_pawchive_accel_type", "active")

    # 1. Search for OpenSSL libcrypto DLL / Shared Library
    candidates = [
        os.path.join(sys.base_prefix, "DLLs", "libcrypto-3.dll"),
        os.path.join(sys.base_prefix, "DLLs", "libcrypto-1_1-x64.dll"),
        os.path.join(sys.base_prefix, "DLLs", "libcrypto-1_1.dll"),
        os.path.join(sys.base_prefix, "libcrypto-3.dll"),
        os.path.join(sys.base_prefix, "libcrypto-1_1-x64.dll"),
        os.path.join(sys.base_prefix, "libcrypto.dll"),
    ]
    if sys.executable:
        candidates.append(os.path.join(os.path.dirname(sys.executable), "DLLs", "libcrypto-3.dll"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "libcrypto-3.dll"))

    import ctypes.util
    for name in ("crypto", "ssl", "libcrypto", "libssl"):
        found = ctypes.util.find_library(name)
        if found:
            candidates.append(found)

    lib = None
    for p in candidates:
        if p and os.path.exists(p):
            try:
                candidate_lib = ctypes.CDLL(p)
                if hasattr(candidate_lib, "AES_set_decrypt_key") and hasattr(candidate_lib, "AES_ige_encrypt"):
                    lib = candidate_lib
                    break
            except Exception:
                pass

    if lib:
        AES_ENCRYPT = ctypes.c_int(1)
        AES_DECRYPT = ctypes.c_int(0)
        AES_MAXNR = 14

        class AES_KEY(ctypes.Structure):
            _fields_ = [
                ('rd_key', ctypes.c_uint32 * (4 * (AES_MAXNR + 1))),
                ('rounds', ctypes.c_uint),
            ]

        def decrypt_ige(cipher_text, key, iv):
            usable_len = (len(cipher_text) // 16) * 16
            if usable_len == 0:
                return b""
            if len(cipher_text) != usable_len:
                cipher_text = cipher_text[:usable_len]

            aes_key = AES_KEY()
            key_len = ctypes.c_int(8 * len(key))
            key_buf = (ctypes.c_ubyte * len(key)).from_buffer_copy(key)
            iv_buf = (ctypes.c_ubyte * len(iv)).from_buffer_copy(iv)

            in_len = ctypes.c_size_t(usable_len)
            in_buf = (ctypes.c_ubyte * usable_len).from_buffer_copy(cipher_text)
            out_buf = (ctypes.c_ubyte * usable_len)()

            lib.AES_set_decrypt_key(key_buf, key_len, ctypes.byref(aes_key))
            lib.AES_ige_encrypt(
                ctypes.byref(in_buf),
                ctypes.byref(out_buf),
                in_len,
                ctypes.byref(aes_key),
                ctypes.byref(iv_buf),
                AES_DECRYPT
            )
            return bytes(out_buf)

        def encrypt_ige(plain_text, key, iv):
            padding = len(plain_text) % 16
            if padding:
                plain_text += os.urandom(16 - padding)

            aes_key = AES_KEY()
            key_len = ctypes.c_int(8 * len(key))
            key_buf = (ctypes.c_ubyte * len(key)).from_buffer_copy(key)
            iv_buf = (ctypes.c_ubyte * len(iv)).from_buffer_copy(iv)

            in_len = ctypes.c_size_t(len(plain_text))
            in_buf = (ctypes.c_ubyte * len(plain_text)).from_buffer_copy(plain_text)
            out_buf = (ctypes.c_ubyte * len(plain_text))()

            lib.AES_set_encrypt_key(key_buf, key_len, ctypes.byref(aes_key))
            lib.AES_ige_encrypt(
                ctypes.byref(in_buf),
                ctypes.byref(out_buf),
                in_len,
                ctypes.byref(aes_key),
                ctypes.byref(iv_buf),
                AES_ENCRYPT
            )
            return bytes(out_buf)

        libssl.decrypt_ige = decrypt_ige
        libssl.encrypt_ige = encrypt_ige
        aes.AES.decrypt_ige = staticmethod(decrypt_ige)
        aes.AES.encrypt_ige = staticmethod(encrypt_ige)
        libssl._pawchive_accelerated = True
        libssl._pawchive_accel_type = "openssl"
        logger.info("⚡ [Telegram] Hardware-accelerated OpenSSL AES-IGE enabled (96+ MB/s).", category="telegram")
        return "openssl"

    # 2. Fallback to PyCryptodome (ECB block mode)
    if _HAS_CRYPTO:
        def decrypt_ige_cryptodome(cipher_text, key, iv):
            usable_len = (len(cipher_text) // 16) * 16
            if usable_len == 0:
                return b""
            if len(cipher_text) != usable_len:
                cipher_text = cipher_text[:usable_len]

            iv1 = iv[:16]
            iv2 = iv[16:]
            cipher = AES.new(key, AES.MODE_ECB)
            plain = bytearray(usable_len)
            blocks_count = usable_len // 16
            for block_index in range(blocks_count):
                offset = block_index * 16
                block = cipher_text[offset:offset + 16]
                xored = bytes(b ^ iv2[j] for j, b in enumerate(block))
                dec = cipher.decrypt(xored)
                m = bytes(dec[j] ^ iv1[j] for j in range(16))
                plain[offset:offset + 16] = m
                iv1 = block
                iv2 = m
            return bytes(plain)

        def encrypt_ige_cryptodome(plain_text, key, iv):
            padding = len(plain_text) % 16
            if padding:
                plain_text += os.urandom(16 - padding)

            iv1 = iv[:16]
            iv2 = iv[16:]
            cipher = AES.new(key, AES.MODE_ECB)
            cipher_out = bytearray(len(plain_text))
            blocks_count = len(plain_text) // 16
            for block_index in range(blocks_count):
                offset = block_index * 16
                block = plain_text[offset:offset + 16]
                xored = bytes(b ^ iv1[j] for j, b in enumerate(block))
                enc = cipher.encrypt(xored)
                c = bytes(enc[j] ^ iv2[j] for j in range(16))
                cipher_out[offset:offset + 16] = c
                iv1 = c
                iv2 = block
            return bytes(cipher_out)

        libssl.decrypt_ige = decrypt_ige_cryptodome
        libssl.encrypt_ige = encrypt_ige_cryptodome
        aes.AES.decrypt_ige = staticmethod(decrypt_ige_cryptodome)
        aes.AES.encrypt_ige = staticmethod(encrypt_ige_cryptodome)
        libssl._pawchive_accelerated = True
        libssl._pawchive_accel_type = "pycryptodome"
        logger.info("⚡ [Telegram] Cryptographic acceleration enabled: PyCryptodome AES-IGE (~5 MB/s).", category="telegram")
        return "pycryptodome"

    return "pyaes"

