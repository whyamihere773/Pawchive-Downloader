"""
Pawchive.pw Modular Browser Provider Adapter (`PawchiveBrowserProvider`).

Subclasses `KemonoStyleCatalogProvider` so adding future Kemono-API-compatible
providers requires only a declarative subclass like this one.
"""

from __future__ import annotations

from core.browser_providers.base import KemonoStyleCatalogProvider
from core.browser_providers.registry import register_browser_provider
from core.providers import PAWCHIVE


@register_browser_provider
class PawchiveBrowserProvider(KemonoStyleCatalogProvider):
    provider_id = PAWCHIVE
    display_name = "Pawchive"
    base_domain = "pawchive.pw"
    order = 20

    default_services = (
        ("all", "All Services"),
        ("favorites", "⭐ Favorites"),
        ("patreon", "Patreon"),
        ("fanbox", "Pixiv Fanbox"),
        ("fantia", "Fantia"),
        ("boosty", "Boosty"),
        ("gumroad", "Gumroad"),
        ("subscribestar", "SubscribeStar"),
        ("dlsite", "DLsite"),
    )
    default_accent_color = "#A78BFA"
    default_badge_icon = "🐾"
    default_supports_favorites = True
