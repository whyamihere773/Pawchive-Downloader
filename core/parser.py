"""
URL Parsing Engine
Decodes and validates creator URLs, single posts, and third-party media endpoints
across Kemono, Coomer, Pawchive, Cum.st, Bunkr, Erome, and nHentai.
"""

import re
from urllib.parse import urlparse
from typing import Optional, Dict, Any


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
        return self.provider != "kemono"

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "service": self.service,
            "user_id": self.user_id,
            "post_id": self.post_id,
            "provider": self.provider,
            "is_single_post": self.is_single_post,
            "is_valid": self.is_valid,
            "raw_url": self.raw_url,
            "error_msg": self.error_msg
        }


class KemonoURLParser:
    KEMONO_PATTERN = re.compile(
        r"https?://(?:www\.)?([^/]+)/([^/]+)/user/([^/?#]+)(?:/(?:post|dm)/([^/?#]+))?",
        re.IGNORECASE
    )

    CREATORS_PATTERN = re.compile(
        r"https?://(?:www\.)?([^/]+)/(?:creators|artists)/([^/]+)/([^/?#]+)(?:/(?:post|posts|dm)/([^/?#]+))?",
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
        if not url.startswith("http://") and not url.startswith("https://"):
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

        match = cls.KEMONO_PATTERN.match(url)
        if not match:
            match = cls.CREATORS_PATTERN.match(url)
        if not match:
            match_posts = cls.POSTS_PATTERN.match(url)
            if match_posts:
                domain = match_posts.group(1).lower()
                service = match_posts.group(2).lower()
                user_id = match_posts.group(3)
                post_id = match_posts.group(4)
                if "cum.st" in domain or "cum" in domain:
                    domain = "cum.st"
                elif "pawchive" in domain:
                    domain = "pawchive.pw"
                elif "kemono" in domain:
                    domain = "kemono.su"
                elif "coomer" in domain:
                    domain = "coomer.su"
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
            domain = match.group(1).lower()
            service = match.group(2).lower()
            user_id = match.group(3)
            post_id = match.group(4) if match.group(4) else None

            if "pawchive" in domain:
                domain = "pawchive.pw"
            elif "kemono" in domain:
                domain = "kemono.su"
            elif "coomer" in domain:
                domain = "coomer.su"
            elif "cum.st" in domain or "cum" in domain:
                domain = "cum.st"

            return URLParseResult(
                domain=domain,
                service=service,
                user_id=user_id,
                post_id=post_id,
                raw_url=url,
                is_valid=True,
                provider="kemono"
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
            error_msg="URL does not match supported formats (Kemono, Pawchive, Coomer, Cum.st, Bunkr, Erome, nHentai, Patreon, Fanbox)."
        )
