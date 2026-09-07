from collections.abc import Iterable

from apps.platform_shell.registry import PlatformRegistry, registry as platform_registry

from .base import BaseCapability


class ExecutableCapabilityRegistry:
    """Deploy-time mapping of declared capability identifiers to providers.

    The canonical declaration authority remains PlatformRegistry/AppManifest.
    """

    def __init__(self, registry: PlatformRegistry = platform_registry) -> None:
        self.platform_registry = registry
        self._providers: dict[str, type[BaseCapability]] = {}

    def _declared_capabilities(self) -> Iterable[str]:
        for manifest in self.platform_registry.all():
            yield from manifest.capabilities

    def register(self, capability_cls: type[BaseCapability]) -> None:
        capability_name = getattr(capability_cls, "name", "")
        if not capability_name:
            raise ValueError("Executable capability must define a non-empty name.")
        if capability_name not in set(self._declared_capabilities()):
            raise ValueError(
                f"Capability '{capability_name}' is not declared in any "
                "AppManifest.capabilities."
            )
        if capability_name in self._providers:
            raise ValueError(f"Capability '{capability_name}' is already registered.")
        self._providers[capability_name] = capability_cls

    def get(self, name: str) -> type[BaseCapability] | None:
        return self._providers.get(name)

    def all(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


executable_registry = ExecutableCapabilityRegistry()
