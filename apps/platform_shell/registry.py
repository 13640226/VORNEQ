from dataclasses import dataclass
from importlib import import_module

from django.apps import apps
from django.urls import NoReverseMatch, include, path, reverse
from django.utils.module_loading import module_has_submodule


PLATFORM_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class AppManifest:
    slug: str
    label: str
    url_name: str
    order: int = 100
    show_in_primary_nav: bool = True
    requires_authentication: bool = False
    active_namespaces: tuple[str, ...] = ()
    urlconf: str | None = None
    route_prefix: str = ""
    capabilities: tuple[str, ...] = ()
    contract_version: int = PLATFORM_CONTRACT_VERSION


def validate_capabilities(capabilities: tuple[str, ...]) -> None:
    """Validate descriptive capability declarations for one app manifest."""
    seen: set[str] = set()
    for capability in capabilities:
        if not isinstance(capability, str):
            raise ValueError(
                "VORNEQ capabilities must be strings, "
                f"got {type(capability).__name__}"
            )
        if not capability:
            raise ValueError("VORNEQ capabilities must not be empty")
        if capability != capability.strip():
            raise ValueError(
                "VORNEQ capabilities must not contain surrounding whitespace"
            )
        if capability in seen:
            raise ValueError(f"Duplicate VORNEQ capability: {capability}")
        seen.add(capability)


class PlatformRegistry:
    def __init__(self):
        self._apps: dict[str, AppManifest] = {}

    def register(self, manifest: AppManifest) -> None:
        if manifest.contract_version != PLATFORM_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported VORNEQ app contract version: {manifest.contract_version}"
            )
        if manifest.slug in self._apps:
            raise ValueError(f"Duplicate VORNEQ app slug: {manifest.slug}")
        if manifest.route_prefix.startswith("/"):
            raise ValueError("VORNEQ app route_prefix must be relative, without a leading slash")
        validate_capabilities(manifest.capabilities)
        self._apps[manifest.slug] = manifest

    def all(self) -> tuple[AppManifest, ...]:
        return tuple(sorted(self._apps.values(), key=lambda item: (item.order, item.slug)))

    def navigation(self, request) -> list[dict[str, object]]:
        resolver_match = getattr(request, "resolver_match", None)
        namespace = getattr(resolver_match, "namespace", None)
        url_name = getattr(resolver_match, "url_name", None)
        items: list[dict[str, object]] = []

        for manifest in self.all():
            if not manifest.show_in_primary_nav:
                continue
            if manifest.requires_authentication and not request.user.is_authenticated:
                continue
            try:
                url = reverse(manifest.url_name)
            except NoReverseMatch:
                continue

            active = manifest.url_name == url_name or (
                namespace is not None and namespace in manifest.active_namespaces
            )
            items.append({"manifest": manifest, "url": url, "active": active})

        return items

    def localized_urlpatterns(self):
        """Return URL patterns contributed by installable VORNEQ apps."""
        patterns = []
        for manifest in self.all():
            if manifest.urlconf:
                patterns.append(path(manifest.route_prefix, include(manifest.urlconf)))
        return patterns


registry = PlatformRegistry()


def autodiscover() -> None:
    """Import optional ``vorneq_app`` modules from installed Django apps.

    Apps opt into the VORNEQ platform shell by exposing a lightweight
    ``vorneq_app.py`` module that registers an :class:`AppManifest`.
    """
    for app_config in apps.get_app_configs():
        if module_has_submodule(app_config.module, "vorneq_app"):
            import_module(f"{app_config.name}.vorneq_app")
