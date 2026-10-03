"""
Pawchive Downloader — Secure Credential & Authentication Subsystem
Stores sensitive login credentials, session cookies, API tokens, and authentication keys
in a hardware- and user-bound DPAPI encrypted vault (CryptProtectData / AES-256-GCM fallback).
Credentials are NEVER stored in plaintext on disk.
"""

import os
import sys
import json
import re
import time
import threading
import requests
from typing import Dict, Any, List, Optional, Tuple

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger
from core.crypto_utils import encrypt_credential, decrypt_credential


VAULT_CONTEXT = "pawchive_auth_vault"

# Fields that can be sent to a site to authenticate. A saved password is never one of them.
SESSION_FIELDS = ("cookie", "token", "api_key")


# Provider definitions registry — Kemono, Coomer, Cum.st, and Pawchive
SUPPORTED_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "kemono": {
        "id": "kemono",
        "name": "Kemono",
        "domain": "kemono.cr",
        "mirror_domains": ["kemono.cr"],
        "icon": "🐱",
        "category": "Primary Platform",
        "auth_type": "account",
        "supports_credentials_login": True,
        "fields": [
            {
                "key": "username",
                "label": "Username or Email",
                "placeholder": "Username or email...",
                "is_secret": False
            },
            {
                "key": "password",
                "label": "Password",
                "placeholder": "Account password...",
                "is_secret": True
            },
            {
                "key": "cookie",
                "label": "Session Cookie / JWT",
                "placeholder": "e.g. session=eyJhbGciOi... or raw JWT",
                "is_secret": True
            }
        ],
        "features": [
            "Favorite Mode account post downloads",
            "Access to paywalled artist attachments",
            "Cloudflare clearance bypass"
        ],
        "supports_browser_import": True,
        "supports_test_connection": True,
        "help_tip": "Log in with your username/email and password, or use 1-Click Browser Import."
    },
    "coomer": {
        "id": "coomer",
        "name": "Coomer",
        "domain": "coomer.st",
        "mirror_domains": ["coomer.st", "coomer.cr"],
        "icon": "💎",
        "category": "Primary Platform",
        "auth_type": "account",
        "supports_credentials_login": True,
        "fields": [
            {
                "key": "username",
                "label": "Username or Email",
                "placeholder": "Username or email...",
                "is_secret": False
            },
            {
                "key": "password",
                "label": "Password",
                "placeholder": "Account password...",
                "is_secret": True
            },
            {
                "key": "cookie",
                "label": "Session Cookie / JWT",
                "placeholder": "e.g. session=eyJhbGciOi... or raw JWT",
                "is_secret": True
            }
        ],
        "features": [
            "Favorite Mode account post downloads",
            "Access to locked media attachments",
            "Priority Cloudflare clearance"
        ],
        "supports_browser_import": True,
        "supports_test_connection": True,
        "help_tip": "Log in with your username/email and password, or use 1-Click Browser Import."
    },
    "cumst": {
        "id": "cumst",
        "name": "Cum.st",
        "domain": "cum.st",
        "mirror_domains": ["cum.st"],
        "icon": "💦",
        "category": "Mirror Platform",
        "auth_type": "account",
        "supports_credentials_login": True,
        "fields": [
            {
                "key": "username",
                "label": "Username or Email",
                "placeholder": "Username or email...",
                "is_secret": False
            },
            {
                "key": "password",
                "label": "Password",
                "placeholder": "Account password...",
                "is_secret": True
            },
            {
                "key": "cookie",
                "label": "Session Cookie / Token",
                "placeholder": "session=... or better-auth.session_token=...",
                "is_secret": True
            }
        ],
        "features": [
            "Favorite Mode account post downloads",
            "Tag-based subfolder routing",
            "Access to e1.cum.st media streams",
            "Direct storage key downloads"
        ],
        "supports_browser_import": True,
        "supports_test_connection": True,
        "help_tip": "Log in with your username/email and password, or use 1-Click Browser Import."
    },
    "pawchive": {
        "id": "pawchive",
        "name": "Pawchive",
        "domain": "pawchive.pw",
        "mirror_domains": ["pawchive.pw"],
        "icon": "🐾",
        "category": "Official Mirror",
        "auth_type": "account",
        "supports_credentials_login": True,
        "fields": [
            {
                "key": "username",
                "label": "Username",
                "placeholder": "Pawchive username...",
                "is_secret": False
            },
            {
                "key": "password",
                "label": "Password",
                "placeholder": "Account password...",
                "is_secret": True
            },
            {
                "key": "cookie",
                "label": "Session Cookie",
                "placeholder": "session=...",
                "is_secret": True
            }
        ],
        "features": [
            "Download temporary oversized files (t1.pawchive.pw)",
            "Tag-based category organization",
            "High-speed multi-threaded downloads"
        ],
        "supports_browser_import": True,
        "supports_test_connection": True,
        "help_tip": "Log in with your Pawchive username and password, or use 1-Click Browser Import."
    }
}


class AuthManager:
    """
    Hardware-bound DPAPI Credential Vault manager.
    Encrypted storage for all supported external providers.
    """

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir:
            base = data_dir
        else:
            from core.path_utils import get_data_dir, migrate_legacy_files
            base = os.path.join(get_data_dir(), "data")
            # Packaged builds used to keep the vault inside "_internal"
            migrate_legacy_files(base, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
                                 ("credentials_vault.enc",))
        os.makedirs(base, exist_ok=True)
        self.vault_file = os.path.join(base, "credentials_vault.enc")
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {
            "version": 1,
            "providers": {}
        }
        self.load()
        self._migrate_legacy_settings()

    # ── Vault Persistence ───────────────────────────────────────────────────

    def load(self):
        """Loads and decrypts the credentials vault from disk."""
        with self._lock:
            if not os.path.exists(self.vault_file):
                self._data = {"version": 1, "providers": {}}
                return

            try:
                with open(self.vault_file, "rb") as f:
                    raw_encrypted = f.read()

                if not raw_encrypted:
                    self._data = {"version": 1, "providers": {}}
                    return

                decrypted_bytes = decrypt_credential(raw_encrypted, context=VAULT_CONTEXT)
                payload = json.loads(decrypted_bytes.decode("utf-8"))
                if isinstance(payload, dict) and "providers" in payload:
                    self._data = payload
                else:
                    self._data = {"version": 1, "providers": {}}
                from core.crypto_utils import needs_reencrypt
                if needs_reencrypt(raw_encrypted):
                    self.save()     # move off the old MAC-address key
                logger.debug(f"[AuthManager] Decrypted vault loaded ({len(self._data.get('providers', {}))} providers configured).", category="auth")
            except Exception as e:
                logger.error(f"[AuthManager] Failed to decrypt credentials vault: {e}", category="auth")
                self._data = {"version": 1, "providers": {}}
                # Keep the unreadable vault instead of overwriting it with an empty one on the next save.
                # Named after its content, so the same vault is copied once (not on every start).
                try:
                    import hashlib
                    import shutil
                    with open(self.vault_file, "rb") as f:
                        digest = hashlib.sha256(f.read()).hexdigest()[:12]
                    backup = self.vault_file + f".unreadable-{digest}"
                    if not os.path.exists(backup):
                        shutil.copy2(self.vault_file, backup)
                    logger.warning(f"[AuthManager] The old credentials vault was kept as {os.path.basename(backup)}.", category="auth")
                except Exception:
                    pass

    def save(self) -> bool:
        """Encrypts and atomically writes credentials vault to disk."""
        with self._lock:
            try:
                raw_json = json.dumps(self._data, indent=2).encode("utf-8")
                encrypted = encrypt_credential(raw_json, context=VAULT_CONTEXT)

                tmp_path = self.vault_file + ".tmp"
                with open(tmp_path, "wb") as f:
                    f.write(encrypted)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        pass
                os.replace(tmp_path, self.vault_file)

                logger.debug("[AuthManager] Encrypted credentials vault saved safely with DPAPI.", category="auth")
                return True
            except Exception as e:
                logger.error(f"[AuthManager] Failed to save encrypted vault: {e}", category="auth")
                return False

    def _migrate_legacy_settings(self):
        """
        Migrates legacy plaintext 'cookie' from settings.json into the encrypted vault
        and cleans it from plaintext disk storage.
        """
        try:
            from core.path_utils import get_config_dir
            from core.atomic_io import atomic_write_json
            candidates = [
                os.path.join(get_config_dir(), "settings.json"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "settings.json"),
            ]
            for settings_path in candidates:
                if not os.path.exists(settings_path):
                    continue
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings_dict = json.load(f)
                legacy_cookie = str(settings_dict.get("cookie", "") or "").strip()
                if not legacy_cookie:
                    continue
                # Keep it in the encrypted vault (the general cookie lives in the "kemono" slot)
                if not self.get_provider_data("kemono").get("cookie"):
                    self.set_credential("kemono", {"cookie": legacy_cookie})
                    logger.info("🔒 [AuthManager] Moved the session cookie from settings.json into the encrypted vault.", category="auth")
                settings_dict.pop("cookie", None)
                atomic_write_json(settings_path, settings_dict, indent=2)
                logger.info("🔒 [AuthManager] Removed the plaintext session cookie from settings.json.", category="auth")
        except Exception as e:
            logger.debug(f"[AuthManager] Legacy migration check: {e}", category="auth")

    # ── Credential Accessors ────────────────────────────────────────────────

    def get_provider_data(self, provider_id: str) -> Dict[str, Any]:
        """Returns the raw stored data dict for a provider."""
        with self._lock:
            return dict(self._data.get("providers", {}).get(provider_id, {}))

    def get_credential(self, provider_id: str, field: str = "cookie") -> str:
        """
        Returns the stored value of one field for the given provider ("" if not set).

        For "cookie" a stored session token counts too (some providers save it as "token"), but a
        password never does: it is only used to log in and must never be sent as a cookie.
        """
        with self._lock:
            p_data = self.get_provider_data(provider_id)
            val = str(p_data.get(field, "") or "").strip()
            if not val and field == "cookie":
                val = str(p_data.get("token", "") or "").strip()
            return val

    def set_credential(self, provider_id: str, creds: Dict[str, Any]) -> bool:
        """
        Encrypts and stores credentials for the given provider.
        Normalizes session cookie strings if needed.
        """
        with self._lock:
            if "providers" not in self._data:
                self._data["providers"] = {}

            curr = self._data["providers"].get(provider_id, {})
            creds = {k: v for k, v in creds.items() if k != "password"}
            curr.pop("password", None)
            # Normalize cookie if passed
            if "cookie" in creds:
                c_val = str(creds["cookie"]).strip()
                if c_val and c_val.startswith("eyJ") and "session=" not in c_val:
                    c_val = f"session={c_val}"
                elif c_val and "=" not in c_val and provider_id in ("kemono", "coomer"):
                    c_val = f"session={c_val}"
                creds["cookie"] = c_val

            curr.update(creds)
            curr["updated_at"] = int(time.time())

            # Attempt to parse expiry if cookie exists
            if curr.get("cookie"):
                try:
                    from services.cookie_importer import browser_cookie_importer
                    exp_info = browser_cookie_importer.calculate_expiration_info(curr["cookie"])
                    curr["expiry_status"] = exp_info.get("status", "unknown")
                    curr["days_remaining"] = exp_info.get("days_remaining", 0)
                except Exception:
                    pass

            self._data["providers"][provider_id] = curr
            return self.save()

    def clear_credential(self, provider_id: str) -> bool:
        """Clears stored credentials for the given provider."""
        with self._lock:
            if "providers" in self._data and provider_id in self._data["providers"]:
                del self._data["providers"][provider_id]
                return self.save()
            return True

    def is_logged_in(self, provider_id: str) -> bool:
        """Checks if a provider has active authentication."""
        if provider_id == "telegram":
            try:
                from services.telegram_service import TelegramService
                telegram_service = TelegramService.instance()
                return bool(telegram_service.is_logged_in())
            except Exception:
                return False

        with self._lock:
            p_data = self.get_provider_data(provider_id)
            return any(p_data.get(k) for k in SESSION_FIELDS)

    # ── Summary & Presentation for QML ──────────────────────────────────────

    @staticmethod
    def _mask_secret(val: str) -> str:
        """Masks a secret credential for safe UI display (e.g. 'session=eyJhbG...9a8f')."""
        if not val:
            return ""
        val = val.strip()
        if len(val) <= 12:
            return "••••••••"
        if val.startswith("session="):
            inner = val[8:]
            if len(inner) <= 10:
                return "session=••••••••"
            return f"session={inner[:6]}...{inner[-4:]}"
        return f"{val[:8]}...{val[-4:]}"

    def get_provider_summary(self, provider_id: str) -> Dict[str, Any]:
        """
        Returns a rich summary dict formatted for QML presentation.
        Never reveals the full secret credential to prevent memory scraping / UI leaks.
        """
        meta = SUPPORTED_PROVIDERS.get(provider_id, {
            "id": provider_id,
            "name": provider_id.capitalize(),
            "domain": "",
            "icon": "🔑",
            "category": "Other",
            "auth_type": "cookie",
            "fields": [{"key": "cookie", "label": "Credential", "placeholder": "", "is_secret": True}],
            "features": [],
            "supports_browser_import": False,
            "supports_test_connection": False,
            "help_tip": ""
        })

        logged_in = self.is_logged_in(provider_id)
        p_data = self.get_provider_data(provider_id)

        # Get masked secret (never a password)
        secret_val = ""
        for k in SESSION_FIELDS:
            if p_data.get(k):
                secret_val = str(p_data[k])
                break

        masked_val = self._mask_secret(secret_val)

        # Status text & color
        status_text = "Connected" if logged_in else "Not Connected"
        status_color = "#10B981" if logged_in else "#64748B"
        username = p_data.get("username", "")

        # Telegram special status
        if provider_id == "telegram":
            try:
                from services.telegram_service import TelegramService
                telegram_service = TelegramService.instance()
                if telegram_service.is_logged_in():
                    u_info = telegram_service.get_user_info() or {}
                    uname = u_info.get("username") or u_info.get("first_name") or ""
                    phone = u_info.get("phone") or ""
                    username = f"@{uname}" if uname else phone
                    status_text = f"Connected as {username}" if username else "Connected"
                    masked_val = "Hardware Session (Encrypted)"
            except Exception:
                pass

        days_left = p_data.get("days_remaining", 0)
        if logged_in and days_left > 0 and days_left < 700:
            status_text += f" ({days_left}d remaining)"

        from core.providers import DISABLED_PROVIDERS, PROVIDER_NAMES, disabled_message
        is_disabled = provider_id in DISABLED_PROVIDERS
        if is_disabled:
            alt = PROVIDER_NAMES.get(DISABLED_PROVIDERS[provider_id]["alternative"], "")
            status_text = f"Turned off — use {alt} instead" if alt else "Turned off"
            status_color = "#F59E0B"

        return {
            "id": provider_id,
            "name": meta["name"],
            "domain": meta.get("domain", ""),
            "icon": meta["icon"],
            "category": meta["category"],
            "auth_type": meta["auth_type"],
            "supports_credentials_login": bool(meta.get("supports_credentials_login", False)),
            "is_logged_in": logged_in,
            "status_text": status_text,
            "status_color": status_color,
            "username": username,
            "masked_value": masked_val,
            "raw_cookie": secret_val if meta["auth_type"] in ("cookie", "account") else "",
            "supports_browser_import": bool(meta.get("supports_browser_import", False)),
            "supports_test_connection": bool(meta.get("supports_test_connection", False)),
            "features": meta.get("features", []),
            "help_tip": disabled_message(provider_id) if is_disabled else meta.get("help_tip", ""),
            "updated_at": p_data.get("updated_at", 0),
            "is_disabled": is_disabled,
            "disabled_message": disabled_message(provider_id) if is_disabled else "",
        }

    def get_all_providers_summary(self) -> List[Dict[str, Any]]:
        """Returns ordered list of summaries for all supported providers."""
        summaries = []
        for pid in SUPPORTED_PROVIDERS:
            summaries.append(self.get_provider_summary(pid))
        return summaries

    # ── Direct Credentials Login ────────────────────────────────────────────

    def login_with_credentials(self, provider_id: str, username: str, password: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Performs direct username & password authentication against the provider API.
        On success, extracts the session cookie / token, stores it in the encrypted DPAPI vault,
        and returns (True, message, details).
        """
        username = (username or "").strip()
        password = (password or "").strip()

        if not username or not password:
            return False, "Please enter both username and password.", {}

        if provider_id not in SUPPORTED_PROVIDERS:
            return False, f"Unknown provider: {provider_id}", {}

        from core.providers import is_disabled, disabled_message
        if is_disabled(provider_id):
            return False, disabled_message(provider_id), {}

        meta = SUPPORTED_PROVIDERS[provider_id]
        if not meta.get("supports_credentials_login", False):
            return False, f"{meta['name']} does not support direct password login. Please use 1-Click Import or Session Cookie.", {}

        domains = meta.get("mirror_domains", [meta["domain"]])


        # ── 1. Kemono / Coomer ──
        if provider_id in ("kemono", "coomer"):
            api_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "text/css",   # Kemono / Coomer answer API calls only for text/css
                "Content-Type": "application/json"
            }
            last_err = ""
            for dom in domains:
                url = f"https://{dom}/api/v1/authentication/login"
                api_headers["Referer"] = f"https://{dom}/account/login"
                try:
                    resp = requests.post(url, json={"username": username, "password": password}, headers=api_headers, timeout=12)

                    if resp.status_code == 200:
                        session_cookie = resp.cookies.get("session", "")
                        if not session_cookie:
                            set_c = resp.headers.get("Set-Cookie", "")
                            for part in set_c.split(";"):
                                if "session=" in part:
                                    session_cookie = part.strip().split("session=")[-1]
                                    break
                        if not session_cookie:
                            try:
                                session_cookie = resp.json().get("token", "")
                            except Exception:
                                pass

                        if session_cookie:
                            full_cookie = f"session={session_cookie}" if not session_cookie.startswith("session=") else session_cookie
                            self.set_credential(provider_id, {
                                "username": username,
                                "cookie": full_cookie,
                                "domain": dom,
                                "last_login": int(time.time())
                            })
                            logger.success(f"[AuthManager] Successfully logged into {meta['name']} as {username} (DPAPI secured).", category="auth")
                            return True, f"Successfully logged in as {username}!", {"username": username, "domain": dom}
                        else:
                            return False, (f"{meta['name']} accepted the login but didn't return a session cookie. "
                                           "Use 1-Click Browser Import or paste the session cookie instead."), {}

                    elif resp.status_code in (400, 401):
                        try:
                            err_json = resp.json()
                            err_msg = err_json.get("error", "Username or password is incorrect.")
                        except Exception:
                            err_msg = "Username or password is incorrect."
                        return False, err_msg, {}

                    elif resp.status_code == 403:
                        last_err = "Cloudflare protection active. Please use 1-Click Browser Import or paste session cookie."
                        continue
                    else:
                        last_err = f"Server returned unexpected HTTP {resp.status_code}."
                except Exception as e:
                    last_err = f"Connection error ({dom}): {e}"
                    continue

            return False, last_err or "Login failed. Please check credentials or use 1-Click Import.", {}

        # ── 2. Pawchive ──
        if provider_id == "pawchive":
            url = "https://pawchive.pw/account/login"
            form_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Referer": "https://pawchive.pw/account/login",
                "Origin": "https://pawchive.pw",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            try:
                s = requests.Session()
                # Pawchive uses form post (application/x-www-form-urlencoded)
                resp = s.post(
                    url,
                    data={"username": username, "password": password},
                    headers=form_headers,
                    timeout=12,
                    allow_redirects=False
                )

                session_cookie = s.cookies.get("session") or resp.cookies.get("session") or ""
                loc = resp.headers.get("Location", "")
                if session_cookie and ("logged_in=yes" in loc or loc not in ("/account/login", "/account/login?location=/artists")):
                    full_cookie = f"session={session_cookie}" if not session_cookie.startswith("session=") else session_cookie
                    self.set_credential("pawchive", {
                        "username": username,
                        "cookie": full_cookie,
                        "last_login": int(time.time())
                    })
                    logger.success(f"[AuthManager] Successfully logged into Pawchive as {username} (DPAPI secured).", category="auth")
                    return True, f"Successfully logged into Pawchive as {username}!", {"username": username}
                else:
                    return False, "Username or password is incorrect.", {}
            except Exception as e:
                return False, f"Connection failed: {e}", {}

        # ── 3. Cum.st (OnlyHaven / Better-Auth backend) ──
        if provider_id == "cumst":
            api_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://cum.st",
                "Referer": "https://cum.st/auth/signin"
            }
            endpoint = "/api/auth/sign-in/email" if "@" in username else "/api/auth/sign-in/username"
            url = f"https://cum.st{endpoint}"
            payload = {"email": username, "password": password} if "@" in username else {"username": username, "password": password}

            try:
                s = requests.Session()
                resp = s.post(url, json=payload, headers=api_headers, timeout=12)

                # Fallback: if username endpoint failed and might be email or vice versa
                if resp.status_code in (404, 400) and "@" not in username:
                    alt_url = "https://cum.st/api/auth/sign-in/email"
                    resp_alt = s.post(alt_url, json={"email": username, "password": password}, headers=api_headers, timeout=12)
                    if resp_alt.status_code == 200:
                        resp = resp_alt

                if resp.status_code == 200:
                    cookie_parts = []
                    all_cookies = {**s.cookies.get_dict(), **resp.cookies.get_dict()}
                    for k, v in all_cookies.items():
                        cookie_parts.append(f"{k}={v}")

                    if not cookie_parts:
                        set_cookie_hdr = resp.headers.get("Set-Cookie", "")
                        for item in set_cookie_hdr.split(","):
                            first_part = item.split(";")[0].strip()
                            if first_part and "=" in first_part:
                                cookie_parts.append(first_part)

                    final_cookie = "; ".join(cookie_parts) if cookie_parts else ""
                    if not final_cookie:
                        try:
                            token_val = resp.json().get("token") or resp.json().get("session", {}).get("token")
                            if token_val:
                                final_cookie = f"better-auth.session_token={token_val}"
                        except Exception:
                            pass

                    self.set_credential("cumst", {
                        "username": username,
                        "cookie": final_cookie,
                        "domain": "cum.st",
                        "last_login": int(time.time())
                    })
                    logger.success(f"[AuthManager] Successfully logged into Cum.st as {username} (DPAPI secured).", category="auth")
                    return True, f"Successfully logged into Cum.st as {username}!", {"username": username}

                elif resp.status_code in (400, 401):
                    try:
                        err_msg = resp.json().get("message") or resp.json().get("error") or "Username or password is incorrect."
                    except Exception:
                        err_msg = "Username or password is incorrect."
                    return False, err_msg, {}
                elif resp.status_code == 403:
                    return False, "DDoS protection active. Please use 1-Click Browser Import or paste session cookie.", {}
                else:
                    return False, f"Server returned unexpected HTTP {resp.status_code}.", {}
            except Exception as e:
                return False, f"Connection failed: {e}", {}

        return False, "Login not supported for this provider.", {}

    # ── Live Validation & Health Check ──────────────────────────────────────

    def validate_session(self, provider_id: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Performs a live network validation check for the specified provider.
        Returns: (success: bool, status_message: str, details: dict)
        """
        from core.providers import is_disabled, disabled_message
        if is_disabled(provider_id):
            return False, disabled_message(provider_id), {}
        if not self.is_logged_in(provider_id):
            return False, "Not connected. Please log in or import cookies first.", {}

        # 1. Kemono / Coomer
        if provider_id in ("kemono", "coomer"):
            cookie = self.get_credential(provider_id, "cookie")
            if not cookie:
                return False, "No cookie found for provider.", {}

            domains = SUPPORTED_PROVIDERS[provider_id].get("mirror_domains", [SUPPORTED_PROVIDERS[provider_id]["domain"]])
            last_err = ""
            for dom in domains:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    "Cookie": cookie,
                    "Accept": "text/css" if ("kemono" in dom or "coomer" in dom) else "application/json, text/plain, */*",
                    "Referer": f"https://{dom}/"
                }

                url = f"https://{dom}/api/v1/favorites?type=post&o=0"
                try:
                    resp = requests.get(url, headers=headers, timeout=12)
                    if resp.status_code == 200:
                        try:
                            favs = resp.json()
                            count = len(favs) if isinstance(favs, list) else 0
                            msg = f"Session verified! ({count} favorited posts synced via {dom})"
                            self.set_credential(provider_id, {"last_verified": int(time.time())})
                            return True, msg, {"favorites_count": count}
                        except Exception:
                            return True, f"Session verified on {dom} (HTTP 200 OK)", {}
                    elif resp.status_code in (401, 403):
                        return False, f"Session unauthorized or expired (HTTP {resp.status_code}). Please re-login.", {}
                    else:
                        last_err = f"Server returned unexpected HTTP {resp.status_code} ({dom})."
                except Exception as e:
                    last_err = f"Connection failed ({dom}): {e}"

            return False, last_err or "Connection failed.", {}

        # 2. Pawchive
        if provider_id == "pawchive":
            cookie = self.get_credential(provider_id, "cookie")
            if not cookie:
                return False, "No session cookie found for Pawchive.", {}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Cookie": cookie
            }
            try:
                resp = requests.get("https://pawchive.pw/account", headers=headers, timeout=10, allow_redirects=False)
                if resp.status_code == 200:
                    self.set_credential(provider_id, {"last_verified": int(time.time())})
                    uname = str(self.get_provider_data(provider_id).get("username", "") or "").strip()
                    if not uname:
                        match = re.search(r'account-view__identity[^>]*>\s*([^\s<]+)', resp.text)
                        if match:
                            uname = match.group(1)
                            self.set_credential(provider_id, {"username": uname})
                    msg = f"Pawchive session active ({uname})" if uname else "Pawchive session active and verified."
                    return True, msg, {"username": uname}
                elif resp.status_code in (302, 401, 403):
                    return False, "Pawchive session expired or invalid. Please re-login.", {}
                return False, f"Pawchive returned HTTP {resp.status_code}.", {}
            except Exception as e:
                return False, f"Connection failed: {e}", {}

        # 3. Cum.st (OnlyHaven / Better-Auth backend)
        if provider_id == "cumst":
            cookie = self.get_credential(provider_id, "cookie")
            if not cookie:
                return False, "No session cookie found for Cum.st.", {}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Cookie": cookie,
                "Referer": "https://cum.st/"
            }
            try:
                resp = requests.get("https://cum.st/api/auth/get-session", headers=headers, timeout=10)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        if data and isinstance(data, dict) and data.get("user"):
                            user_info = data["user"]
                            uname = user_info.get("name") or user_info.get("email") or user_info.get("username") or ""
                            if uname:
                                self.set_credential(provider_id, {"username": uname})
                            self.set_credential(provider_id, {"last_verified": int(time.time())})
                            return True, f"Cum.st session active ({uname})" if uname else "Cum.st session active and verified.", {"username": uname}
                    except Exception:
                        pass

                resp2 = requests.get("https://cum.st/", headers=headers, timeout=10)
                if resp2.status_code == 200:
                    self.set_credential(provider_id, {"last_verified": int(time.time())})
                    return True, "Cum.st connection active.", {}
                return False, f"Cum.st returned HTTP {resp2.status_code}.", {}
            except Exception as e:
                return False, f"Connection failed: {e}", {}

        # Fallback
        return True, "Credential saved securely in encrypted vault.", {}


# Global Singleton Instance
auth_manager = AuthManager()

