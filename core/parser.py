"""
URL Parsing Engine
Decodes and validates creator URLs, single posts, and third-party media endpoints
across Kemono, Coomer, Pawchive, Cum.st, Bunkr, Erome, and nHentai.
"""

import re
from urllib.parse import urlparse
from typing import Optional, Dict, Any


# Current Kemono / Coomer domains. The old kemono.su / coomer.su / .party addresses no longer
# resolve, so every Kemono / Coomer link is normalised to these.
KEMONO_DOMAIN = "kemono.cr"
COOMER_DOMAIN = "coomer.st"


def _canonical_archive_domain(domain: str) -> str:
    """The domain to use for an archive site link, or '' if the domain isn't one of them."""
    from core.providers import provider_for_host, KEMONO, COOMER, PAWCHIVE, CUMST, COOMERFANS
    return {KEMONO: KEMONO_DOMAIN, COOMER: COOMER_DOMAIN, PAWCHIVE: "pawchive.pw", CUMST: "cum.st", COOMERFANS: "coomerfans.com"}.get(
        provider_for_host(domain), "")


def canonical_site_url(domain: str, service: str, user_id: str, route: str = "", post_id: str = "") -> str:
    """Build the canonical frontend page URL for an archive domain (cum.st uses /creators/...)."""
    dom = _canonical_archive_domain(domain) or (domain or "").strip().lower()
    svc = (service or "").strip()
    uid = str(user_id or "").strip()
    rt = (route or "").strip().strip("/")
    pid = str(post_id or "").strip()
    if not (dom and svc and uid):
        return ""
    base = f"https://cum.st/creators/{svc}/{uid}" if "cum.st" in dom else f"https://{dom}/{svc}/user/{uid}"
    if rt and pid:
        return f"{base}/{rt}/{pid}"
    if rt:
        return f"{base}/{rt}"
    return base


_CUMST_USERLESS_POST_RE = re.compile(
    r"^https?://(?:www\.)?cum\.st/(?:"
    r"(?P<svc1>[^/?#]+)/(?P<rt1>post|posts|dm|dms)/(?P<pid1>[^/?#]+)"
    r"|(?P<rt2>posts|post|dm|dms)/(?P<svc2>[^/?#]+)/(?P<pid2>[^/?#]+)"
    r")/?$",
    re.IGNORECASE,
)


def normalize_archive_url(
    url: str,
    fallback_service: str = "",
    fallback_user_id: str = "",
    fallback_post_id: str = "",
) -> str:
    """Rewrite legacy/incomplete cum.st page URLs (/{svc}/user/{id}..., /posts/{svc}/{id}/{pid},
    or userless /{svc}/post/{pid} when `fallback_user_id` is known) to canonical /creators/{svc}/{id}..."""
    clean = str(url or "").strip()
    if not clean or "cum.st" not in clean.lower():
        return clean
    low = clean.lower()
    if "/api/" in low or "cdn.cum.st" in low or "img.cum.st" in low:
        return clean

    head_path, sep, query_str = clean.partition("?")

    def _with_query(built_url: str) -> str:
        return f"{built_url}?{query_str}" if (sep and query_str and built_url) else built_url

    # Already canonical /creators/{service}/{user_id}...
    if KemonoURLParser.CREATORS_PATTERN.match(head_path):
        return clean

    # Legacy /{service}/user/{user_id}[/post|dm/{post_id}]
    m = KemonoURLParser.KEMONO_PATTERN.match(head_path)
    if m and "cum.st" in m.group(1).lower():
        svc, uid, pid = m.group(2), m.group(3), m.group(4) or fallback_post_id or ""
        tail_path = head_path.rstrip("/")
        if pid:
            route = "dm" if re.search(rf"/dms?/{re.escape(pid)}$", tail_path, re.IGNORECASE) else "post"
        elif re.search(r"/dms?$", tail_path, re.IGNORECASE):
            route = "dms"
        else:
            route = ""
        built = canonical_site_url("cum.st", svc, uid, route=route, post_id=pid)
        return _with_query(built) if built else clean

    # /posts/{service}/{user_id}/{post_id}
    m_posts = KemonoURLParser.POSTS_PATTERN.match(head_path)
    if m_posts and "cum.st" in m_posts.group(1).lower():
        svc, uid, pid = m_posts.group(2), m_posts.group(3), m_posts.group(4)
        built = canonical_site_url("cum.st", svc, uid, route="post", post_id=pid)
        return _with_query(built) if built else clean

    # Incomplete userless /{service}/post/{post_id} or /posts/{service}/{post_id}
    m_ul = _CUMST_USERLESS_POST_RE.match(head_path)
    if m_ul:
        svc = (m_ul.group("svc1") or m_ul.group("svc2") or fallback_service or "").strip().lower()
        raw_rt = (m_ul.group("rt1") or m_ul.group("rt2") or "post").strip().lower()
        route = "dm" if raw_rt.startswith("dm") else "post"
        pid = (m_ul.group("pid1") or m_ul.group("pid2") or fallback_post_id or "").strip()
        uid = str(fallback_user_id or "").strip()
        if svc and uid and pid:
            built = canonical_site_url("cum.st", svc, uid, route=route, post_id=pid)
            if built:
                return _with_query(built)
    return clean


class URLParseResult:
    def __init__(
        self,
        domain: str,
        service: str,
        user_id: str,
        post_id: Optional[str] = None,
        raw_url: str = "",
        is_valid: bool = True,
        error_msg: str = "",
        provider: str = "kemono",
        extra_data: Optional[Dict[str, Any]] = None
    ):
        self.domain = domain
        self.service = service
        self.user_id = user_id
        self.post_id = post_id
        self.raw_url = raw_url
        self.is_valid = is_valid
        self.error_msg = error_msg
        self.provider = provider
        self.extra_data = extra_data or {}

    @property
    def is_single_post(self) -> bool:
        if self.provider == "telegram":
            return bool(self.post_id)
        return bool(self.post_id) or self.provider in ("bunkr", "erome", "nhentai")

    @property
    def is_external_provider(self) -> bool:
        return self.provider not in ("kemono", "coomerfans")

    @property
    def api_base_url(self) -> str:
        return f"https://{self.domain}/api/v1"

    @property
    def user_api_url(self) -> str:
        return f"{self.api_base_url}/{self.service}/user/{self.user_id}"

    @property
    def post_api_url(self) -> Optional[str]:
        if self.post_id:
            return f"{self.api_base_url}/{self.service}/user/{self.user_id}/post/{self.post_id}"
        return None

    @property
    def is_dms(self) -> bool:
        return bool(self.extra_data.get("is_dms", False))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "service": self.service,
            "user_id": self.user_id,
            "post_id": self.post_id,
            "provider": self.provider,
            "is_single_post": self.is_single_post,
            "is_dms": self.is_dms,
            "is_valid": self.is_valid,
            "raw_url": self.raw_url,
            "error_msg": self.error_msg
        }


class KemonoURLParser:
    KEMONO_PATTERN = re.compile(
        r"https?://(?:www\.)?([^/]+)/([^/]+)/user/([^/?#]+)(?:/(?:post|posts|dm|dms)(?:/([^/?#]+))?)?",
        re.IGNORECASE
    )

    CREATORS_PATTERN = re.compile(
        r"https?://(?:www\.)?([^/]+)/(?:creators|artists)/([^/]+)/([^/?#]+)(?:/(?:post|posts|dm|dms)(?:/([^/?#]+))?)?",
        re.IGNORECASE
    )

    POSTS_PATTERN = re.compile(
        r"https?://(?:www\.)?([^/]+)/posts/([^/]+)/([^/?#]+)/([^/?#]+)",
        re.IGNORECASE
    )

    BUNKR_PATTERN = re.compile(
        r"https?://(?:[a-zA-Z0-9_-]+\.)?(?:bunkr|bunkrr|bunk)\.[a-z0-9]+/(?:a|v|d|f|i|file)/([a-zA-Z0-9_-]+)",
        re.IGNORECASE
    )

    BALBUMS_PATTERN = re.compile(
        r"https?://(?:[a-zA-Z0-9_-]+\.)?balbums\.st(?:/a/([a-zA-Z0-9_-]+))?",
        re.IGNORECASE
    )

    BUNKR_CDN_PATTERN = re.compile(
        r"https?://(?:[a-zA-Z0-9_-]+\.)?(?:cdn\.cr|scdn\.st)/storage/media/([a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9]+)?)",
        re.IGNORECASE
    )

    EROME_PATTERN = re.compile(
        r"https?://(?:www\.)?erome\.com/a/([a-zA-Z0-9_-]+)",
        re.IGNORECASE
    )

    NHENTAI_PATTERN = re.compile(
        r"https?://(?:www\.)?nhentai\.net/g/(\d+)",
        re.IGNORECASE
    )

    SAINT2_PATTERN = re.compile(
        r"https?://(?:www\.)?saint2\.su/([^\s]+)",
        re.IGNORECASE
    )

    # CoomerFans patterns
    COOMERFANS_POST_PATTERN = re.compile(
        r"https?://(?:www\.)?coomerfans\.com/p/(\d+)/([^/?#]+)/([^/?#]+)",
        re.IGNORECASE
    )
    COOMERFANS_USER_PATTERN = re.compile(
        r"https?://(?:www\.)?coomerfans\.com/u/([^/?#]+)/([^/?#]+)(?:/([^/?#]+))?",
        re.IGNORECASE
    )

    # Native platform patterns for cross-post resolution
    PATREON_NATIVE_PATTERN = re.compile(
        r"https?://(?:www\.)?patreon\.com/posts/(?:[a-zA-Z0-9_-]+-)?(\d+)",
        re.IGNORECASE
    )
    FANBOX_NATIVE_PATTERN = re.compile(
        r"https?://(?:(?:www\.)?fanbox\.cc/@([a-zA-Z0-9_-]+)/posts/(\d+)|([a-zA-Z0-9_-]+)\.fanbox\.cc/posts/(\d+))",
        re.IGNORECASE
    )
    FANTIA_NATIVE_PATTERN = re.compile(
        r"https?://(?:www\.)?fantia\.jp/posts/(\d+)",
        re.IGNORECASE
    )
    BOOSTY_NATIVE_PATTERN = re.compile(
        r"https?://(?:www\.)?boosty\.to/([a-zA-Z0-9_-]+)/posts/([a-zA-Z0-9_-]+)",
        re.IGNORECASE
    )
    SUBSCRIBESTAR_NATIVE_PATTERN = re.compile(
        r"https?://(?:www\.)?subscribestar\.(?:adult|com)/posts/(\d+)",
        re.IGNORECASE
    )
    DLSITE_NATIVE_PATTERN = re.compile(
        r"https?://(?:www\.)?dlsite\.com/[^/]+/work/=/product_id/([A-Z0-9]+)",
        re.IGNORECASE
    )

    # Telegram patterns
    TELEGRAM_PRIVATE_POST_PATTERN = re.compile(
        r"https?://(?:www\.)?(?:t\.me|telegram\.me)/c/(\d+)/(\d+)",
        re.IGNORECASE
    )
    TELEGRAM_INVITE_PATTERN = re.compile(
        r"https?://(?:www\.)?(?:t\.me|telegram\.me)/(?:\+|joinchat/)([a-zA-Z0-9_-]+)",
        re.IGNORECASE
    )
    TELEGRAM_PUBLIC_POST_PATTERN = re.compile(
        r"https?://(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([a-zA-Z0-9_]{4,})/(\d+)",
        re.IGNORECASE
    )
    TELEGRAM_CHANNEL_PATTERN = re.compile(
        r"https?://(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([a-zA-Z0-9_]{4,})/?$",
        re.IGNORECASE
    )

    @classmethod
    def parse(cls, url: str) -> URLParseResult:
        if not url:
            return URLParseResult("", "", "", raw_url=url, is_valid=False, error_msg="URL cannot be empty.")

        url = url.strip()
        if not re.match(r"^https?://", url, re.IGNORECASE):
            url = "https://" + url

        # Telegram Private Post (e.g. t.me/c/123456789/45)
        m_tg_priv = cls.TELEGRAM_PRIVATE_POST_PATTERN.search(url)
        if m_tg_priv:
            channel_id = m_tg_priv.group(1)
            message_id = m_tg_priv.group(2)
            return URLParseResult(
                domain="t.me",
                service="telegram",
                user_id=channel_id,
                post_id=message_id,
                raw_url=url,
                is_valid=True,
                provider="telegram",
                extra_data={"is_private": True, "type": "private_post", "channel_id": channel_id, "message_id": int(message_id)}
            )

        # Telegram Invite Link (e.g. t.me/+hash or t.me/joinchat/hash)
        m_tg_inv = cls.TELEGRAM_INVITE_PATTERN.search(url)
        if m_tg_inv:
            invite_hash = m_tg_inv.group(1)
            return URLParseResult(
                domain="t.me",
                service="telegram",
                user_id=invite_hash,
                post_id=None,
                raw_url=url,
                is_valid=True,
                provider="telegram",
                extra_data={"is_private": True, "type": "invite", "invite_hash": invite_hash}
            )

        # Telegram Public Post (e.g. t.me/channel/123)
        m_tg_post = cls.TELEGRAM_PUBLIC_POST_PATTERN.search(url)
        if m_tg_post:
            channel_name = m_tg_post.group(1)
            message_id = m_tg_post.group(2)
            return URLParseResult(
                domain="t.me",
                service="telegram",
                user_id=channel_name,
                post_id=message_id,
                raw_url=url,
                is_valid=True,
                provider="telegram",
                extra_data={"is_private": False, "type": "public_post", "channel_name": channel_name, "message_id": int(message_id)}
            )

        # Telegram Public Channel (e.g. t.me/channel_name)
        m_tg_chan = cls.TELEGRAM_CHANNEL_PATTERN.search(url)
        if m_tg_chan:
            channel_name = m_tg_chan.group(1)
            return URLParseResult(
                domain="t.me",
                service="telegram",
                user_id=channel_name,
                post_id=None,
                raw_url=url,
                is_valid=True,
                provider="telegram",
                extra_data={"is_private": False, "type": "channel", "channel_name": channel_name}
            )

        # CoomerFans Single Post: /p/{post_id}/{user_id}/{service}
        m_cf_post = cls.COOMERFANS_POST_PATTERN.search(url)
        if m_cf_post:
            post_id = m_cf_post.group(1)
            user_id = m_cf_post.group(2)
            service = m_cf_post.group(3).lower()
            return URLParseResult(
                domain="coomerfans.com",
                service=service,
                user_id=user_id,
                post_id=post_id,
                raw_url=url,
                is_valid=True,
                provider="coomerfans"
            )

        # CoomerFans Creator Profile: /u/{service}/{user_id}/{username}
        m_cf_user = cls.COOMERFANS_USER_PATTERN.search(url)
        if m_cf_user:
            service = m_cf_user.group(1).lower()
            user_id = m_cf_user.group(2)
            slug = m_cf_user.group(3) or ""
            return URLParseResult(
                domain="coomerfans.com",
                service=service,
                user_id=user_id,
                post_id=None,
                raw_url=url,
                is_valid=True,
                provider="coomerfans",
                extra_data={"username": slug}
            )

        m_nh = cls.NHENTAI_PATTERN.search(url)
        if m_nh:
            gid = m_nh.group(1)
            return URLParseResult(
                domain="nhentai.net",
                service="nhentai",
                user_id=gid,
                post_id=gid,
                raw_url=url,
                is_valid=True,
                provider="nhentai"
            )

        m_bunkr = cls.BUNKR_PATTERN.search(url)
        if m_bunkr:
            item_id = m_bunkr.group(1)
            netloc = urlparse(url).netloc.lower() or "bunkr.cr"
            return URLParseResult(
                domain=netloc,
                service="bunkr",
                user_id="bunkr_user",
                post_id=item_id,
                raw_url=url,
                is_valid=True,
                provider="bunkr"
            )

        m_balbums = cls.BALBUMS_PATTERN.search(url)
        if m_balbums:
            item_id = m_balbums.group(1) or "album"
            return URLParseResult(
                domain="balbums.st",
                service="bunkr",
                user_id="bunkr_user",
                post_id=item_id,
                raw_url=url,
                is_valid=True,
                provider="bunkr"
            )

        m_cdn = cls.BUNKR_CDN_PATTERN.search(url)
        if m_cdn:
            item_id = m_cdn.group(1)
            netloc = urlparse(url).netloc.lower() or "cdn.cr"
            return URLParseResult(
                domain=netloc,
                service="bunkr",
                user_id="bunkr_user",
                post_id=item_id,
                raw_url=url,
                is_valid=True,
                provider="bunkr"
            )

        m_erome = cls.EROME_PATTERN.search(url)
        if m_erome:
            album_id = m_erome.group(1)
            return URLParseResult(
                domain="erome.com",
                service="erome",
                user_id="erome_user",
                post_id=album_id,
                raw_url=url,
                is_valid=True,
                provider="erome"
            )

        # Kemono-style links (/{service}/user/{id}) — only on the archive sites themselves
        match = cls.KEMONO_PATTERN.match(url)
        if match and not _canonical_archive_domain(match.group(1)):
            match = None
        if not match:
            match = cls.CREATORS_PATTERN.match(url)
            if match and not _canonical_archive_domain(match.group(1)):
                match = None
        if not match:
            match_posts = cls.POSTS_PATTERN.match(url)
            if match_posts and _canonical_archive_domain(match_posts.group(1)):
                domain = _canonical_archive_domain(match_posts.group(1))
                service = match_posts.group(2).lower()
                user_id = match_posts.group(3)
                post_id = match_posts.group(4)
                return URLParseResult(
                    domain=domain,
                    service=service,
                    user_id=user_id,
                    post_id=post_id,
                    raw_url=url,
                    is_valid=True,
                    provider="kemono"
                )

        if match:
            domain = _canonical_archive_domain(match.group(1))
            service = match.group(2).lower()
            user_id = match.group(3)
            post_id = match.group(4) if match.group(4) else None

            clean_path = url.split("?")[0].rstrip("/")
            is_dms = (not post_id) and (
                bool(re.search(r'[?&]tab=dms?\b', url, re.IGNORECASE)) or
                bool(re.search(r'/(?:dms|dm)$', clean_path, re.IGNORECASE))
            )
            extra_data = {"is_dms": True} if is_dms else {}

            return URLParseResult(
                domain=domain,
                service=service,
                user_id=user_id,
                post_id=post_id,
                raw_url=url,
                is_valid=True,
                provider="kemono",
                extra_data=extra_data
            )

        # Check native platforms (Patreon, Fanbox, Fantia, Boosty, Subscribestar, DLsite)
        m_pat = cls.PATREON_NATIVE_PATTERN.search(url)
        if m_pat:
            return URLParseResult(
                domain="pawchive.pw",
                service="patreon",
                user_id="",
                post_id=m_pat.group(1),
                raw_url=url,
                is_valid=True,
                provider="native"
            )

        m_fb = cls.FANBOX_NATIVE_PATTERN.search(url)
        if m_fb:
            slug = m_fb.group(1) or m_fb.group(3) or ""
            pid = m_fb.group(2) or m_fb.group(4) or ""
            return URLParseResult(
                domain="pawchive.pw",
                service="fanbox",
                user_id=slug,
                post_id=pid,
                raw_url=url,
                is_valid=True,
                provider="native"
            )

        m_fan = cls.FANTIA_NATIVE_PATTERN.search(url)
        if m_fan:
            return URLParseResult(
                domain="pawchive.pw",
                service="fantia",
                user_id="",
                post_id=m_fan.group(1),
                raw_url=url,
                is_valid=True,
                provider="native"
            )

        m_bst = cls.BOOSTY_NATIVE_PATTERN.search(url)
        if m_bst:
            return URLParseResult(
                domain="pawchive.pw",
                service="boosty",
                user_id=m_bst.group(1),
                post_id=m_bst.group(2),
                raw_url=url,
                is_valid=True,
                provider="native"
            )

        m_sub = cls.SUBSCRIBESTAR_NATIVE_PATTERN.search(url)
        if m_sub:
            return URLParseResult(
                domain="pawchive.pw",
                service="subscribestar",
                user_id="",
                post_id=m_sub.group(1),
                raw_url=url,
                is_valid=True,
                provider="native"
            )

        m_dl = cls.DLSITE_NATIVE_PATTERN.search(url)
        if m_dl:
            return URLParseResult(
                domain="pawchive.pw",
                service="dlsite",
                user_id="",
                post_id=m_dl.group(1),
                raw_url=url,
                is_valid=True,
                provider="native"
            )

        return URLParseResult(
            "", "", "",
            raw_url=url,
            is_valid=False,
            error_msg="URL does not match supported formats (Kemono, Pawchive, Coomer, Cum.st, CoomerFans, Bunkr, Erome, nHentai, Patreon, Fanbox)."
        )

    parse_url = parse
