from dataclasses import dataclass

from .registry import PlatformRegistry, registry


@dataclass(frozen=True)
class CapabilityApp:
    """Typed representation of an app that declares a capability."""

    slug: str
    label: str
    url_name: str
    route_prefix: str = ""


class CapabilityDiscovery:
    """Read-only capability discovery over the canonical platform registry."""

    def __init__(self, platform_registry: PlatformRegistry = registry):
        self.registry = platform_registry

    @staticmethod
    def _app_info(manifest) -> CapabilityApp:
        return CapabilityApp(
            slug=manifest.slug,
            label=manifest.label,
            url_name=manifest.url_name,
            route_prefix=manifest.route_prefix,
        )

    def get_all_capabilities(self) -> dict[str, list[CapabilityApp]]:
        """Return capability identifiers mapped to every declaring app."""
        result: dict[str, list[CapabilityApp]] = {}
        for manifest in self.registry.all():
            app_info = self._app_info(manifest)
            for capability in manifest.capabilities:
                result.setdefault(capability, []).append(app_info)
        return result

    def get_app_capabilities(self, app_slug: str) -> tuple[str, ...]:
        """Return capabilities declared by one app, or an empty tuple."""
        for manifest in self.registry.all():
            if manifest.slug == app_slug:
                return manifest.capabilities
        return ()

    def get_apps_with_capability(self, capability: str) -> list[CapabilityApp]:
        """Return every app declaring the requested capability."""
        return [
            self._app_info(manifest)
            for manifest in self.registry.all()
            if capability in manifest.capabilities
        ]
