from dataclasses import dataclass
from importlib import import_module

from django.apps import apps
from django.urls import NoReverseMatch, reverse
from django.utils.module_loading import module_has_submodule


@dataclass(frozen=True)
class AppManifest:
    slug: str
    label: str
    url_name: str
    order: int = 100
    show_in_primary_nav: bool = True
    requires_authentication: bool = False
    active_namespaces: tuple[str, ...] = ()


class PlatformRegistry:
    def __init__(self):
        self._apps: dict[str, AppManifest] = {}

    def register(self, manifest: AppManifest) -> None:
        if manifest.slug in self._apps:
            raise ValueError(f"Duplicate VORNEQ app slug: {manifest.slug}")
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


registry = PlatformRegistry()


def autodiscover() -> None:
    """Import optional ``vorneq_app`` modules from installed Django apps.

    Apps opt into the VORNEQ platform shell by exposing a lightweight
    ``vorneq_app.py`` module that registers an :class:`AppManifest`.
    """
    for app_config in apps.get_app_configs():
        if module_has_submodule(app_config.module, "vorneq_app"):
            import_module(f"{app_config.name}.vorneq_app")
