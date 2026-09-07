# VORNEQ App Developer Guide

This guide describes the current, deploy-time path for adding a reviewed Django application to VORNEQ. It is based on the Platform Shell contract and the first reference application, Notes.

The goal is repeatable integration without turning platform metadata into authorization, identity, verification, reputation, or truth semantics.

## 1. Start with a bounded domain

Create an app only when its domain boundary is clear. The app owns its domain models, services, routes, templates, and authorization decisions. The Platform Shell discovers and routes to the app; it does not become the app's service locator or permission system.

Prefer a small vertical first. Do not introduce a generic cross-app abstraction merely because one app needs a feature.

## 2. Create the Django app package

A typical app has this shape:

```text
apps/example/
├── __init__.py
├── apps.py
├── vorneq_app.py
├── models.py
├── services.py
├── views.py
├── urls.py
├── migrations/
├── templates/example/
├── static/example/
└── tests/
```

Add the AppConfig to `INSTALLED_APPS`. Keep AppConfig startup work lightweight. Platform manifest discovery happens through `vorneq_app.py`.

## 3. Register one AppManifest

Create `apps/example/vorneq_app.py`:

```python
from django.utils.translation import gettext_lazy as _

from apps.platform_shell.registry import AppManifest, registry

registry.register(
    AppManifest(
        slug="example",
        label=_("Example"),
        url_name="example:list",
        order=100,
        show_in_primary_nav=False,
        requires_authentication=True,
        active_namespaces=("example",),
        urlconf="apps.example.urls",
        route_prefix="example/",
        capabilities=("example.read",),
    )
)
```

Manifest modules must be declarative and side-effect free except for registration. Do not query the database, call a network service, mutate domain state, infer identity, or make registration depend on request state.

### Manifest semantics

- `slug` is the stable, globally unique app identifier.
- `label` is presentation metadata.
- `url_name` is the named landing route. The shell resolves it with Django URL reversing; it does not guess URLs.
- `order` controls deterministic presentation ordering.
- `show_in_primary_nav` controls navigation presentation only.
- `requires_authentication` is a presentation filter for anonymous navigation. It is not authorization.
- `active_namespaces` supports active-navigation presentation.
- `urlconf` and `route_prefix` contribute reviewed localized routes at deploy time.
- `capabilities` are descriptive discovery tokens only.
- `contract_version` is the Platform Shell manifest contract version, not an app release version.

Use tuples for tuple-valued fields. A capability name must never be interpreted as permission or provider execution.

## 4. Own the app routes

Define a normal namespaced Django URLconf:

```python
from django.urls import path

from . import views

app_name = "example"

urlpatterns = [
    path("", views.example_list, name="list"),
]
```

When `urlconf` and `route_prefix` are present in the manifest, the canonical PlatformRegistry contributes the route under the localized URL configuration. Do not add a second hard-coded global include for the same app.

Use named URLs and `reverse()`/`{% url %}`. Never construct launch URLs from slugs.

## 5. Launcher and Workspace integration

A correctly registered manifest is discoverable by the existing App Launcher and Workspace Shell.

The Launcher is a discovery/navigation surface. Workspace provides app context and an explicit `Open App` action. Neither surface grants access to domain data or bypasses app authorization.

Do not add a second manifest for Workspace, and do not change Launcher launch semantics to route through Workspace.

## 6. Keep domain data in the vertical model

If an app needs canonical Core representation, keep domain-specific content in the app model and use Core models for their actual canonical purpose.

Notes is the reference pattern: `Note` owns title/content and has a one-to-one reference to a Core `Artifact`. It does not copy note content into `Artifact.metadata`.

Do not create synthetic Core records merely to satisfy an imagined generic API.

## 7. Resolve Identity explicitly

Authentication is not canonical identity. When a domain action needs an Identity, resolve the authenticated user through the existing typed `UserIdentity` binding and fail closed when the required binding is missing or inactive.

Never infer a verified or canonical Identity from a username, display name, email-like free text, author string, or content field.

When an Artifact needs an identity relationship, use the existing explicit Core relationship that matches the semantics. Notes uses `ArtifactIdentityRole(role=owner)` for ownership.

## 8. Keep authorization in the domain service layer

Views should delegate consequential reads and mutations to domain services. Services must enforce object scope before returning or mutating protected objects.

Platform metadata is never authorization. In particular, none of these grant authority:

- authentication by itself;
- manifest visibility;
- `requires_authentication`;
- a capability declaration;
- Launcher or Workspace presence;
- route availability;
- reputation, verification, or search presence.

### Entitlement boundary

The current Core `Entitlement` model is marketplace/Product-oriented and is not a generic `read`/`write` permission API. Do not create fake Products, invented permission strings, or a universal `EntitlementService` to authorize arbitrary app resources.

If a future app requires generic resource grants, define that contract separately and review its authorization semantics before adoption.

## 9. Treat capabilities as descriptive v1 metadata

Current capability discovery reads `AppManifest.capabilities` from the canonical PlatformRegistry. It supports declaration and discovery only.

Do not attach callable handlers, arbitrary HTML, runtime code, permission checks, or hidden cross-app data access to v1 capability strings.

Executable providers such as global commands, search providers, notifications, or workspace panels require a separately versioned contract and ADR. Such a contract must define typed and bounded input/output, explicit actor/request context, domain-owned authorization, failure isolation, and execution boundaries.

## 10. Audit only through supported taxonomy

Do not invent event names and pass them to the canonical audit recorder when its schema does not support them. The current recorder has strict schemas for the implemented audit slice.

If an app needs new canonical audit events, extend the audit taxonomy in a separately bounded change, define actor/target/outcome semantics, add tests, and then instrument the app.

## 11. Build UI on the shared shell

App templates should extend `base.html` unless a documented exception applies. Reuse VORNEQ CSS custom properties from the existing token/theme system rather than introducing a parallel palette.

Prefer accessible semantic HTML, keyboard-visible focus states, responsive layout, and reduced-motion handling. Do not duplicate global navigation or footer markup inside the app.

## 12. Mutations and deletion

Use normal Django CSRF protection and validated forms for browser mutations. Consequential state changes should not be exposed through GET routes.

Choose deletion semantics deliberately. Notes uses POST-only soft deactivation for both its vertical record and canonical Artifact. Another domain may require a different lifecycle, retention, or audit policy; do not copy soft-delete mechanically.

## 13. Tests required for a platform app

At minimum, cover the contracts the app actually relies on:

- manifest registration and expected metadata;
- localized route resolution through the PlatformRegistry;
- login behavior when the app requires authentication;
- missing or inactive identity binding behavior when Identity is required;
- owner/object-scope isolation for protected resources;
- successful create/read/update/delete paths that exist;
- mutation method restrictions such as POST-only delete;
- soft-delete or lifecycle behavior when applicable;
- Launcher/Workspace discoverability when it is part of the app contract.

Tests that temporarily alter the global registry must restore its previous state. Do not allow one test to leak manifest state into another.

## 14. Reference implementation: Notes

Use these files as the first concrete reference:

- `apps/notes/vorneq_app.py` — deploy-time manifest;
- `apps/notes/models.py` — vertical data plus canonical Artifact reference;
- `apps/notes/services.py` — identity resolution and ownership-scoped operations;
- `apps/notes/urls.py` and `apps/notes/views.py` — app-owned routing/presentation;
- `apps/notes/tests/` — service and view boundaries;
- `docs/architecture/notes-poc-app.md` — architectural rationale and deliberate exclusions.

Copy the architectural boundaries, not Notes-specific domain choices.

## 15. Pre-PR checklist

Before opening an app PR, confirm:

- the branch starts from the intended current `main`;
- the app is explicitly installed in `INSTALLED_APPS`;
- the manifest has a unique slug and resolvable named landing route;
- route contribution is not duplicated in global URL configuration;
- manifest import has no database/network/domain side effects;
- identity is resolved explicitly when required;
- authorization is enforced by the app/domain layer;
- capabilities are descriptive only;
- no unsupported Entitlement or audit API has been invented;
- templates use the shared shell and existing design tokens;
- migrations are included for new persistent models;
- tests cover authorization boundaries and route integration;
- CI, Security Audit, and Backup Restore Rehearsal are green on the exact PR head before merge.

## Contract maturity

The current platform provides a deliberately small deploy-time contract. Stable-for-current-development behavior and experimental/future surfaces are documented in `docs/architecture/platform-app-contract.md`.

Do not treat a documented future direction as an implemented API.