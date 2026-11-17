"""
Modular Browser Providers Package.

Importing this package registers all built-in browser providers (`cum.st`,
`pawchive.pw`, `coomerfans.com`). Future sites can be added by creating a
new module in `core/browser_providers/` and decorating with `@register_browser_provider`.
"""

from core.browser_providers.base import (
    BaseBrowserProvider,
    BrowserPageResult,
    KemonoStyleCatalogProvider,
    ProviderCapabilities,
    build_creator_card_dto,
    build_media_attachment_dto,
    build_post_card_dto,
    format_service_label,
    resolve_kemono_media_urls,
)
from core.browser_providers.registry import (
    BrowserProviderRegistry,
    browser_registry,
    register_browser_provider,
)

# Register built-in site providers
from core.browser_providers import cumst_provider as _cumst_provider  # noqa: F401
from core.browser_providers import pawchive_provider as _pawchive_provider  # noqa: F401
from core.browser_providers import coomerfans_provider as _coomerfans_provider  # noqa: F401

__all__ = [
    "BaseBrowserProvider",
    "BrowserPageResult",
    "KemonoStyleCatalogProvider",
    "ProviderCapabilities",
    "BrowserProviderRegistry",
    "browser_registry",
    "register_browser_provider",
    "build_creator_card_dto",
    "build_media_attachment_dto",
    "build_post_card_dto",
    "format_service_label",
    "resolve_kemono_media_urls",
]
