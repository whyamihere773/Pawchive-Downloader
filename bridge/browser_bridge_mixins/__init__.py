"""Modular domain mixins composing BrowserBridge."""

from bridge.browser_bridge_mixins.auth_favorites_mixin import BrowserAuthFavoritesMixin
from bridge.browser_bridge_mixins.cart_dispatch_mixin import BrowserCartDispatchMixin
from bridge.browser_bridge_mixins.fetch_posts_mixin import BrowserFetchPostsMixin
from bridge.browser_bridge_mixins.links_relocate_mixin import BrowserLinksRelocateMixin
from bridge.browser_bridge_mixins.local_newposts_mixin import BrowserLocalNewPostsMixin
from bridge.browser_bridge_mixins.props_filters_mixin import BrowserPropsFiltersMixin
from bridge.browser_bridge_mixins.signals_mixin import BrowserSignalsMixin

__all__ = [
    "BrowserSignalsMixin",
    "BrowserPropsFiltersMixin",
    "BrowserFetchPostsMixin",
    "BrowserCartDispatchMixin",
    "BrowserAuthFavoritesMixin",
    "BrowserLocalNewPostsMixin",
    "BrowserLinksRelocateMixin",
]
