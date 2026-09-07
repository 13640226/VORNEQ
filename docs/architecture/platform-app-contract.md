# VORNEQ Platform App Contract

The platform shell lets reviewed Django applications join VORNEQ without editing global navigation or localized route declarations.

## Minimal installable app

Add the Django application to `INSTALLED_APPS`, then create `vorneq_app.py` inside that application:

```python
from django.utils.translation import gettext_lazy as _

from apps.platform_shell.registry import AppManifest, registry

registry.register(
    AppManifest(
        slug="example",
        label=_("Example"),
        url_name="example:index",
        urlconf="apps.example.urls",
        route_prefix="example/",
        active_namespaces=("example",),
        capabilities=("example.read",),
    )
)
```

The shell will autodiscover the manifest at Django startup, mount the localized URLconf, and expose the application to platform navigation.

## Manifest fields

- `slug`: stable, globally unique application identifier.
- `label`: user-facing localized label.
- `url_name`: named landing route used by the shell.
- `order`: stable navigation order; lower values appear first.
- `show_in_primary_nav`: whether the application appears in the primary shell navigation.
- `requires_authentication`: presentation filter for anonymous navigation only; it is not authorization.
- `active_namespaces`: namespaces that mark the navigation item active.
- `urlconf`: optional URLconf to mount through the shell.
- `route_prefix`: relative localized route prefix, such as `example/`.
- `capabilities`: descriptive integration identifiers. Capabilities do not grant authority.
- `contract_version`: version of the platform manifest contract. Unsupported versions fail closed.

### Capability discovery (v1)

Apps declare capabilities as a tuple of strings in their `AppManifest`:

```python
AppManifest(
    slug="marketplace",
    label=_("Marketplace"),
    url_name="marketplace:index",
    capabilities=("commerce.catalog", "commerce.entitlement"),
)
```

`apps.platform_shell.capability_discovery.CapabilityDiscovery` provides read-only discovery over the canonical `PlatformRegistry`:

- `get_all_capabilities()` returns a mapping from capability identifier to the apps that declare it.
- `get_app_capabilities(app_slug)` returns the tuple declared by one app.
- `get_apps_with_capability(capability)` returns every app that declares the requested capability.

Capability declarations are validated when the manifest enters the canonical registry. In v1, declarations must be non-empty strings, must not contain surrounding whitespace, and must not contain duplicates within the same manifest. Multiple apps may declare the same capability, legacy identifiers such as `commerce.catalog` remain valid, and there is no arbitrary per-app capability limit.

Capabilities remain discovery/declaration tokens only. They do not grant permissions, execute providers, or authorize cross-app access. Executable provider contracts require a future versioned contract and ADR.

### App Launcher UI

The localized App Launcher is mounted at `apps/` and provides an authenticated discovery surface for installed apps.

- App cards are derived from the canonical `PlatformRegistry` and preserve its deterministic `order`, then `slug`, ordering.
- Cards show the current manifest `label`, `slug`, and capability count as neutral discovery metadata.
- Launch targets are resolved from each manifest's named `url_name`; an unresolvable route is shown as unavailable rather than guessed.
- Search is client-side progressive enhancement over `label` and `slug`; without JavaScript, every registered app remains visible.
- The launcher extends the shared `base.html` shell and uses VORNEQ design-token custom properties instead of introducing a separate visual system.

The launcher is a navigation surface only. Visibility, capability declarations, and launchability do not grant permissions or bypass authorization owned by an app's domain layer.

Future launcher enhancements may introduce app icon assets, capability badges, favorites, or recent-app affordances through separately bounded contract changes. Semantic app versions are not displayed because app version metadata is not part of the current manifest contract.

## Design rules

Manifest modules must be lightweight and side-effect free except for registration. They must not query the database, perform network calls, infer identity, mutate domain state, or conditionally register routes from request-specific state.

Application authorization remains inside the application's domain layer. The platform shell must never convert authentication, a capability name, navigation visibility, reputation, verification state, or search presence into authority.

## What installation means

Installation is deploy-time composition of reviewed code. VORNEQ does not download or execute arbitrary remote application code at runtime. A future app marketplace, sandbox, iframe/microfrontend boundary, or signed package format would require a separate threat model and ADR.

## Growth path

The current contract intentionally covers the stable minimum: app discovery, localized route mounting, navigation, and descriptive capabilities. Future extensions can add versioned providers for global search, commands, notifications, workspace panels, or frontend assets without changing domain semantics.

## Related ADRs

- [ADR 011: App Launcher, Capability Bus, and Workspace Shell](../adr/011-app-launcher-capability-bus-workspace-shell.md)
