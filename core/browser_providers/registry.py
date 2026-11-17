"""
Dynamic Registry for Modular Browser Providers.

Adding a new site in the future requires only decorating a `BaseBrowserProvider`
subclass with `@register_browser_provider`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type
from core.browser_providers.base import BaseBrowserProvider
from core.providers import provider_for_host


class BrowserProviderRegistry:
    """Central registry of modular browser site adapters."""

    def __init__(self):
        self._providers: Dict[str, BaseBrowserProvider] = {}

    def register(self, provider) -> BaseBrowserProvider:
        if isinstance(provider, type) and issubclass(provider, BaseBrowserProvider):
            provider = provider()
        if not provider or not provider.provider_id:
            raise ValueError("Browser provider must define a non-empty provider_id")
        self._providers[provider.provider_id] = provider
        return provider

    def unregister(self, provider_id: str) -> None:
        self._providers.pop(provider_id, None)

    def get(self, provider_id: str) -> Optional[BaseBrowserProvider]:
        return self.get_provider(provider_id)

    def get_provider(self, provider_id: str) -> Optional[BaseBrowserProvider]:
        prov = self._providers.get((provider_id or "").strip().lower())
        if prov and prov.is_enabled():
            return prov
        return None

    def get_provider_for_url(self, url_or_host: str) -> Optional[BaseBrowserProvider]:
        pid = provider_for_host(url_or_host)
        if pid:
            return self.get_provider(pid)
        h = (url_or_host or "").strip().lower()
        for prov in self.get_active_providers():
            if prov.base_domain and prov.base_domain.lower() in h:
                return prov
        return None

    def get_active_providers(self) -> List[BaseBrowserProvider]:
        active = [p for p in self._providers.values() if p.is_enabled()]
        active.sort(key=lambda p: (getattr(p, "order", 100), p.provider_id))
        return active

    def list_enabled_providers(self) -> List[BaseBrowserProvider]:
        return self.get_active_providers()

    def get_ui_manifest(self) -> List[Dict[str, Any]]:
        """Returns the dynamic UI manifest consumed by QML to build provider pills & filter bars."""
        return [p.get_manifest_entry() for p in self.get_active_providers()]

    def get_providers_manifest(self) -> List[Dict[str, Any]]:
        return self.get_ui_manifest()


# Global singleton registry
browser_registry = BrowserProviderRegistry()


def register_browser_provider(cls: Type[BaseBrowserProvider]) -> Type[BaseBrowserProvider]:
    """Class decorator to instantiate and register a `BaseBrowserProvider` subclass."""
    instance = cls()
    browser_registry.register(instance)
    return cls
