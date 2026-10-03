"""
Which archive site a link or file server belongs to, which sites are switched off, and which
login cookie may be sent where.

Kemono and Coomer are currently in limbo (mostly not working), so they are switched off: their
code is kept, and removing an entry from DISABLED_PROVIDERS turns a site back on.
"""

from typing import Dict, Optional
from urllib.parse import urlparse

KEMONO = "kemono"
COOMER = "coomer"
PAWCHIVE = "pawchive"
CUMST = "cumst"

ARCHIVE_PROVIDERS = (KEMONO, COOMER, PAWCHIVE, CUMST)

PROVIDER_NAMES = {KEMONO: "Kemono", COOMER: "Coomer", PAWCHIVE: "Pawchive", CUMST: "cum.st"}

# Sites that are switched off, with where to go instead.
DISABLED_PROVIDERS: Dict[str, Dict[str, str]] = {
    KEMONO: {
        "alternative": PAWCHIVE,
        "message": "Kemono isn't working reliably right now, so it's turned off in Pawchive Downloader. "
                   "Pawchive (pawchive.pw) has the same creators and posts — open the same link on "
                   "pawchive.pw instead.",
    },
    COOMER: {
        "alternative": CUMST,
        "message": "Coomer isn't working reliably right now, so it's turned off in Pawchive Downloader. "
                   "Use cum.st instead: it hosts the same kind of creators (OnlyFans, Fansly, CandFans…).",
    },
}


def _host(url_or_host: str) -> str:
    s = (url_or_host or "").strip().lower()
    if "://" in s:
        s = urlparse(s).netloc
    return s.split("@")[-1].split(":")[0].strip(".")


def provider_for_host(url_or_host: str) -> str:
    """'kemono' / 'coomer' / 'pawchive' / 'cumst' for that site's pages, APIs and file servers, else ''."""
    h = _host(url_or_host)
    if not h:
        return ""
    labels = h.split(".")
    if "kemono" in labels:
        return KEMONO
    if "coomer" in labels:
        return COOMER
    if h == "pawchive.pw" or h.endswith(".pawchive.pw"):
        return PAWCHIVE
    if h == "cum.st" or h.endswith(".cum.st"):
        return CUMST
    return ""


def is_disabled(provider_or_url: str) -> bool:
    p = provider_or_url if provider_or_url in ARCHIVE_PROVIDERS else provider_for_host(provider_or_url)
    return p in DISABLED_PROVIDERS


def disabled_message(provider_or_url: str) -> str:
    p = provider_or_url if provider_or_url in ARCHIVE_PROVIDERS else provider_for_host(provider_or_url)
    return DISABLED_PROVIDERS.get(p, {}).get("message", "")


def alternative_url(url: str) -> str:
    """The same link on the site that replaces a switched-off one, when the links match 1:1.

    Pawchive uses Kemono's service / creator / post IDs, so a Kemono link maps directly. Coomer and
    cum.st don't share link formats, so no automatic replacement is offered for Coomer.
    """
    if provider_for_host(url) != KEMONO:
        return ""
    parsed = urlparse(url if "://" in url else "https://" + url)
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"https://pawchive.pw{path}{query}"


def cookie_for_url(url: str, general_cookie: str = "") -> str:
    """The login cookie that may be sent to this URL — only to the site it belongs to.

    An account cookie saved for a site (Settings → Accounts) is used for that site only. The general
    cookie from Settings → Network is used for the archive sites that have no account cookie of their
    own. Nothing is ever sent to third-party hosts (Bunkr, Erome, cloud drives…), and a saved password
    is never used as a cookie.
    """
    provider = provider_for_host(url)
    if not provider or provider in DISABLED_PROVIDERS:
        return ""
    try:
        from core.auth_manager import auth_manager
        account_cookie = auth_manager.get_credential(provider, "cookie")
    except Exception:
        account_cookie = ""
    return normalize_cookie(account_cookie or general_cookie)


def normalize_cookie(value: Optional[str]) -> str:
    """A bare JWT / session value becomes 'session=<value>'."""
    c = (value or "").strip()
    if not c:
        return ""
    if c.startswith("eyJ") and "session=" not in c:
        return f"session={c}"
    if "=" not in c:
        return f"session={c}"
    return c
