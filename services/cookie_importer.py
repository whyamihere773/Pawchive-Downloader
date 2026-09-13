"""
1-Click Browser Cookie Importer & Expiration Watchdog
Safely extracts session credentials and Cloudflare clearance cookies from
Google Chrome, Microsoft Edge, Brave, Opera, Opera GX, and Mozilla Firefox
on Windows using DPAPI and AES-256-GCM without locking active browser instances.
"""

import os
import sys
import json
import time
import base64
import shutil
import sqlite3
import tempfile
import ctypes
from ctypes import wintypes
from typing import Dict, Any, List, Optional, Tuple

if __name__ == "__main__" or "core" not in sys.modules:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from core.logger import logger
from Crypto.Cipher import AES


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_char))
    ]


class BrowserCookieImporter:
    """
    Extracts session and authorization cookies directly from local Windows browsers.
    """

    TARGET_DOMAINS = [
        "kemono",
        "coomer",
        "pawchive",
        "patreon",
        "fanbox",
        "fantia"
    ]

    TARGET_COOKIE_NAMES = [
        "session",
        "cf_clearance",
        "__cf_bm",
        "session_id",
        "p_session",
        "FANBOXSESSID",
        "__ddg1_",
        "__ddg8_",
        "__ddg9_",
        "__ddg10_",
        "a_csrf",
        "thumbSize"
    ]

    @classmethod
    def get_supported_browsers(cls) -> List[Dict[str, str]]:
        """Returns list of installed/detected browsers on the machine."""
        found = []
        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")

        candidates = [
            ("firefox", "Mozilla Firefox", os.path.join(appdata, "Mozilla", "Firefox", "Profiles")),
            ("edge", "Microsoft Edge", os.path.join(localappdata, "Microsoft", "Edge", "User Data")),
            ("brave", "Brave Browser", os.path.join(localappdata, "BraveSoftware", "Brave-Browser", "User Data")),
            ("opera", "Opera", os.path.join(appdata, "Opera Software", "Opera Stable")),
            ("operagx", "Opera GX", os.path.join(appdata, "Opera Software", "Opera GX Stable")),
            ("chrome", "Google Chrome", os.path.join(localappdata, "Google", "Chrome", "User Data")),
        ]

        for bid, name, path in candidates:
            if os.path.exists(path):
                found.append({"id": bid, "name": name, "path": path})

        return found

    @staticmethod
    def _dpapi_decrypt(encrypted_bytes: bytes) -> bytes:
        """Decrypts data using Windows DPAPI (CryptUnprotectData)."""
        if not encrypted_bytes:
            return b""
        in_blob = DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_char)))
        out_blob = DATA_BLOB()

        ret = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob)
        )
        if not ret:
            raise RuntimeError("CryptUnprotectData failed.")

        res = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return res

    @classmethod
    def _get_chromium_master_key(cls, user_data_path: str) -> bytes:
        """Extracts and decrypts AES master key from Chromium 'Local State'."""
        local_state_path = os.path.join(user_data_path, "Local State")
        if not os.path.exists(local_state_path):
            raise FileNotFoundError(f"Local State not found at {local_state_path}")

        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)

        enc_key_b64 = local_state.get("os_crypt", {}).get("encrypted_key")
        if not enc_key_b64:
            raise ValueError("os_crypt.encrypted_key not found in Local State")

        enc_key = base64.b64decode(enc_key_b64)
        if not enc_key.startswith(b"DPAPI"):
            raise ValueError("Encrypted key is not DPAPI-encrypted")

        # Strip DPAPI prefix (5 bytes)
        raw_dpapi = enc_key[5:]
        return cls._dpapi_decrypt(raw_dpapi)

    @staticmethod
    def _is_valid_cookie_value(value: str) -> bool:
        """
        Returns True only if the cookie value is safe to send in an HTTP header.
        Rejects control characters (0x00-0x1F, 0x7F) and Unicode surrogates that
        indicate a failed/garbage decryption rather than a real cookie value.
        """
        if not value:
            return False
        for ch in value:
            cp = ord(ch)
            if cp < 0x20 or cp == 0x7F:
                return False
            # Lone surrogates from errors='ignore' decode = corrupted output
            if 0xD800 <= cp <= 0xDFFF:
                return False
        return True

    @classmethod
    def _decrypt_chromium_cookie_value(cls, encrypted_value: bytes, master_key: bytes) -> str:
        """Decrypts a Chromium v10/v20 cookie value using AES-256-GCM."""
        if not encrypted_value:
            return ""

        prefix = encrypted_value[:3]
        if prefix in (b"v10", b"v20"):
            # AES-GCM
            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:-16]
            tag = encrypted_value[-16:]

            try:
                cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
                decrypted = cipher.decrypt_and_verify(ciphertext, tag)
                val = decrypted.decode("utf-8", errors="ignore")
                return val if cls._is_valid_cookie_value(val) else ""
            except Exception:
                if prefix == b"v20":
                    raise RuntimeError("App-Bound Encryption (v20) detected. Google Chrome 127+ restricts external cookie decryption. Please use Mozilla Firefox or Edge.")
                return ""
        else:
            # Legacy DPAPI directly on value
            try:
                dec = cls._dpapi_decrypt(encrypted_value)
                val = dec.decode("utf-8", errors="ignore")
                return val if cls._is_valid_cookie_value(val) else ""
            except Exception:
                return ""

    @classmethod
    def import_from_chromium(cls, user_data_path: str) -> Dict[str, Any]:
        """
        Extracts session and target cookies from a Chromium-based browser profile.
        Safely copies DB to tempdir to prevent locking conflicts with running browsers.
        """
        cookies_db_path = None
        # Check standard paths: Default/Network/Cookies or Network/Cookies
        for sub in [
            os.path.join("Default", "Network", "Cookies"),
            os.path.join("Network", "Cookies"),
            os.path.join("Default", "Cookies"),
            "Cookies"
        ]:
            cand = os.path.join(user_data_path, sub)
            if os.path.exists(cand):
                cookies_db_path = cand
                break

        if not cookies_db_path:
            raise FileNotFoundError(f"Cookies database not found in {user_data_path}")

        master_key = cls._get_chromium_master_key(user_data_path)

        # Safely copy DB to temporary directory
        temp_dir = tempfile.mkdtemp(prefix="paw_cookie_")
        temp_db = os.path.join(temp_dir, "Cookies.sqlite")
        try:
            shutil.copy2(cookies_db_path, temp_db)
        except Exception as e:
            err_msg = str(e)
            if "used by another process" in err_msg or getattr(e, 'winerror', 0) == 32:
                raise RuntimeError("Cookie database is currently locked by the browser. Please close the browser completely and try again.")
            raise

        extracted_cookies = {}
        min_expiry_timestamp = float("inf")

        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()

            # Query target cookies
            domain_clauses = " OR ".join(["host_key LIKE ?" for _ in cls.TARGET_DOMAINS])
            query = f"SELECT host_key, name, encrypted_value, expires_utc FROM cookies WHERE {domain_clauses}"
            params = [f"%{d}%" for d in cls.TARGET_DOMAINS]

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for host, name, enc_val, exp_utc in rows:
                if name in cls.TARGET_COOKIE_NAMES or "session" in name.lower() or "clearance" in name.lower():
                    val = cls._decrypt_chromium_cookie_value(enc_val, master_key)
                    if val:
                        extracted_cookies[name] = val

                        # Chromium expires_utc is microseconds since 1601-01-01
                        if exp_utc and exp_utc > 0:
                            unix_exp = (exp_utc / 1000000.0) - 11644473600
                            if unix_exp > 0 and unix_exp < min_expiry_timestamp:
                                min_expiry_timestamp = unix_exp

            conn.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        cookie_str = "; ".join([f"{k}={v}" for k, v in extracted_cookies.items()])
        expiry_info = cls.calculate_expiration_info(cookie_str, min_expiry_timestamp if min_expiry_timestamp != float("inf") else None)

        return {
            "cookie_string": cookie_str,
            "cookies": extracted_cookies,
            "count": len(extracted_cookies),
            "expiry": expiry_info
        }

    @classmethod
    def import_from_firefox(cls, profiles_dir: str) -> Dict[str, Any]:
        """
        Extracts cookies from Mozilla Firefox profiles.
        Scans all profile directories sorted by most recently modified first.
        """
        if not os.path.exists(profiles_dir):
            raise FileNotFoundError(f"Firefox profiles directory not found at {profiles_dir}")

        candidate_dbs = []
        for root, _, files in os.walk(profiles_dir):
            if "cookies.sqlite" in files:
                p = os.path.join(root, "cookies.sqlite")
                try:
                    mtime = os.path.getmtime(p)
                except Exception:
                    mtime = 0
                candidate_dbs.append((p, mtime))

        if not candidate_dbs:
            raise FileNotFoundError("Firefox cookies.sqlite not found in profiles")

        # Sort candidate DBs by most recently modified first
        candidate_dbs.sort(key=lambda x: x[1], reverse=True)

        extracted = {}
        min_expiry = float("inf")

        for cookie_db_path, _ in candidate_dbs:
            temp_dir = tempfile.mkdtemp(prefix="paw_ff_")
            temp_db = os.path.join(temp_dir, "cookies.sqlite")
            try:
                shutil.copy2(cookie_db_path, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()

                domain_clauses = " OR ".join(["host LIKE ?" for _ in cls.TARGET_DOMAINS])
                query = f"SELECT host, name, value, expiry FROM moz_cookies WHERE {domain_clauses}"
                params = [f"%{d}%" for d in cls.TARGET_DOMAINS]

                cursor.execute(query, params)
                rows = cursor.fetchall()

                for host, name, val, exp in rows:
                    if name in cls.TARGET_COOKIE_NAMES or "session" in name.lower() or "clearance" in name.lower():
                        if val and cls._is_valid_cookie_value(val) and name not in extracted:
                            extracted[name] = val
                            if exp and exp > 0 and exp < min_expiry:
                                min_expiry = exp

                conn.close()
            except Exception as e:
                logger.debug(f"Error reading Firefox profile DB {cookie_db_path}: {e}", category="cookie")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

            # If active session or clearance cookie was discovered in this profile, finish
            if "session" in extracted or "FANBOXSESSID" in extracted or "cf_clearance" in extracted:
                break

        cookie_str = "; ".join([f"{k}={v}" for k, v in extracted.items()])
        expiry_info = cls.calculate_expiration_info(cookie_str, min_expiry if min_expiry != float("inf") else None)

        return {
            "cookie_string": cookie_str,
            "cookies": extracted,
            "count": len(extracted),
            "expiry": expiry_info
        }

    @classmethod
    def import_auto_detect(cls, preferred_browser: Optional[str] = None) -> Dict[str, Any]:
        """
        Auto-detects installed browser and extracts credentials.
        If preferred_browser is specified, targets that specific browser.
        """
        browsers = cls.get_supported_browsers()
        if not browsers:
            raise RuntimeError("No supported web browsers found on this system.")

        # If user explicitly requested a specific browser, ONLY query that browser
        if preferred_browser:
            target_browser = next((b for b in browsers if b["id"].lower() == preferred_browser.lower()), None)
            if not target_browser:
                valid_ids = [b["id"] for b in browsers]
                raise RuntimeError(f"Browser '{preferred_browser}' not detected. Available: {', '.join(valid_ids)}")

            b_name = target_browser["name"]
            bid = target_browser["id"]
            path = target_browser["path"]

            try:
                if bid == "firefox":
                    res = cls.import_from_firefox(path)
                else:
                    res = cls.import_from_chromium(path)
            except Exception as e:
                err_msg = str(e)
                if "used by another process" in err_msg or "locked" in err_msg.lower():
                    raise RuntimeError(f"{b_name} has its cookie database locked. Please close {b_name} and click Import again.")
                raise RuntimeError(f"Could not import cookies from {b_name}: {e}")

            if not res.get("cookie_string") or res.get("count", 0) == 0:
                raise RuntimeError(f"No active Kemono/Coomer/Patreon session cookies found in {b_name}. Please make sure you are logged in on {b_name}.")

            res["browser_name"] = b_name
            res["browser_id"] = bid
            logger.success(
                f"Imported {res['count']} cookie(s) from {b_name} ({res['expiry']['status_text']}).",
                category="cookie"
            )
            return res

        # Auto-Detect mode: prioritize browsers that don't suffer from App-Bound encryption or lock issues
        priority_order = ["firefox", "edge", "operagx", "opera", "brave", "chrome"]
        ordered = []
        for pref in priority_order:
            for b in browsers:
                if b["id"] == pref and b not in ordered:
                    ordered.append(b)
        for b in browsers:
            if b not in ordered:
                ordered.append(b)

        diagnostic_notes = []
        for b in ordered:
            bid = b["id"]
            path = b["path"]
            try:
                if bid == "firefox":
                    res = cls.import_from_firefox(path)
                else:
                    res = cls.import_from_chromium(path)

                if res.get("cookie_string") and res.get("count", 0) > 0:
                    res["browser_name"] = b["name"]
                    res["browser_id"] = bid
                    logger.success(
                        f"Auto-detected cookies from {b['name']}: {res['count']} cookie(s) ({res['expiry']['status_text']}).",
                        category="cookie"
                    )
                    return res
                else:
                    diagnostic_notes.append(f"{b['name']}: No active cookies")
            except Exception as e:
                err_str = str(e)
                if "used by another process" in err_str or "locked" in err_str.lower():
                    diagnostic_notes.append(f"{b['name']}: Browser running (locked)")
                elif "App-Bound" in err_str or "v20" in err_str or "MAC check" in err_str:
                    diagnostic_notes.append(f"{b['name']}: Protected by App-Bound encryption")
                else:
                    diagnostic_notes.append(f"{b['name']}: {e}")

        summary = "; ".join(diagnostic_notes)
        raise RuntimeError(f"Could not auto-detect cookies ({summary}). Please select Mozilla Firefox from the dropdown or paste your session cookie manually.")

    @classmethod
    def calculate_expiration_info(cls, cookie_string: str, timestamp_expiry: Optional[float] = None) -> Dict[str, Any]:
        """
        Watchdog: analyzes cookie string (including JWT tokens) and SQLite timestamps
        to compute exact health and days remaining.
        """
        now = time.time()
        expiry_time = timestamp_expiry

        # Check for JWT token in session=...
        if cookie_string:
            for part in cookie_string.split(";"):
                part = part.strip()
                if part.startswith("session="):
                    token = part.split("=", 1)[1].strip()
                    if token.startswith("eyJ") and token.count(".") >= 2:
                        try:
                            payload_b64 = token.split(".")[1]
                            # Add padding
                            payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
                            payload_json = base64.b64decode(payload_b64).decode("utf-8", errors="ignore")
                            payload = json.loads(payload_json)
                            jwt_exp = payload.get("exp")
                            if jwt_exp and isinstance(jwt_exp, (int, float)):
                                expiry_time = float(jwt_exp)
                        except Exception:
                            pass

        if not expiry_time or expiry_time <= 0:
            if cookie_string:
                return {
                    "status": "active",
                    "days_remaining": 30,
                    "status_text": "Active · Session Verified",
                    "color": "#10B981"
                }
            return {
                "status": "missing",
                "days_remaining": 0,
                "status_text": "No Cookies Configured",
                "color": "#94A3B8"
            }

        delta_seconds = expiry_time - now
        days_left = max(0, int(delta_seconds / 86400))
        hours_left = max(0, int(delta_seconds / 3600))

        # Sanity cap: cookies showing > 730 days likely have no real expiry
        # (browser stores session cookies with far-future placeholder timestamps)
        if days_left > 730:
            return {
                "status": "active",
                "days_remaining": 730,
                "status_text": "Active · Session Verified",
                "color": "#10B981"
            }

        if delta_seconds <= 0:
            return {
                "status": "expired",
                "days_remaining": 0,
                "status_text": "Session Expired (Click to Re-import)",
                "color": "#EF4444"
            }
        elif delta_seconds <= 172800:  # <= 48 hours
            return {
                "status": "expiring",
                "days_remaining": days_left,
                "status_text": f"Expiring Soon ({hours_left}h left)",
                "color": "#F59E0B"
            }
        else:
            return {
                "status": "active",
                "days_remaining": days_left,
                "status_text": f"Active ({days_left} days left)",
                "color": "#10B981"
            }


# Global Singleton
browser_cookie_importer = BrowserCookieImporter()
