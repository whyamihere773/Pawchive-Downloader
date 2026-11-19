"""
Modular Browser Provider Base Contracts, Normalized DTOs, and Reusable Catalog Engine.

Re-exports all DTO builders, `ProviderCapabilities`, `BrowserPageResult`,
`BaseBrowserProvider`, and `KemonoStyleCatalogProvider` from focused submodules.
"""

from core.browser_providers.dto import (
    BrowserPageResult,
    ProviderCapabilities,
    SERVICE_DISPLAY_NAMES,
    _ARCHIVE_EXTS,
    _AUDIO_EXTS,
    _IMAGE_EXTS,
    _VIDEO_EXTS,
    _infer_url_extension,
    build_creator_card_dto,
    build_media_attachment_dto,
    build_post_card_dto,
    format_service_label,
    html_to_readable_text,
    resolve_kemono_media_urls,
)
from core.browser_providers.kemono_catalog import KemonoStyleCatalogProvider
from core.browser_providers.provider_contract import BaseBrowserProvider

__all__ = [
    "SERVICE_DISPLAY_NAMES",
    "format_service_label",
    "ProviderCapabilities",
    "BrowserPageResult",
    "build_creator_card_dto",
    "build_media_attachment_dto",
    "build_post_card_dto",
    "html_to_readable_text",
    "resolve_kemono_media_urls",
    "BaseBrowserProvider",
    "KemonoStyleCatalogProvider",
]
