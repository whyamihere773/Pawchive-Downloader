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
        r"https?://(?:www\.)?(?:bunkr|bunkrr)\.(?:is|si|cr|ru|black|media|site|ac|su|la)/(?:a|v|d)/([a-zA-Z0-9_-]+)",
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

    @classmethod
    def parse(cls, url: str) -> URLParseResult:
        if not url:
            return URLParseResult("", "", "", raw_url=url, is_valid=False, error_msg="URL cannot be empty.")

        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

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
            album_id = m_bunkr.group(1)
            return URLParseResult(
                domain="bunkr.is",
                service="bunkr",
                user_id="bunkr_user",
                post_id=album_id,
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

        return URLParseResult(
            "", "", "",
            raw_url=url,
            is_valid=False,
            error_msg="URL does not match supported formats (Kemono, Pawchive, Coomer, Cum.st, Bunkr, Erome, nHentai)."
        )
