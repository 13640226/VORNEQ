# VORNEQ — Architecture Overview

This document summarizes the current architecture of VORNEQ on `main`, including the production homepage merged in PR #151. It is intended as an onboarding reference for developers and as a compact map of the platform's current architectural boundaries.

## Project structure

Key areas of the repository include:

- `apps/core/` — shared domain foundations, identity/artifact models, services, tests, and migrations.
- `apps/search/` — unified retrieval services and narrow-window search helpers.
- `apps/platform_shell/` — app registry, capability discovery, Launcher, Workspace Shell, URL contribution, context processors, and platform-shell tests.
- `apps/verification/` — verification workflows and domain services.
- `apps/audit/` — structured audit-event persistence and schema validation.
- `apps/marketplace/` — marketplace application and domain behavior.
- `apps/notes/` — Notes application and its artifact integration.
- `assets/css/` — shared design tokens, theme styles, shell styles, and homepage styles.
- `templates/` — shared base layout, navigation partials, application templates, and the root homepage.
- `docs/architecture/` — architecture decisions and platform-contract documentation.

The root homepage remains part of the existing site architecture rather than a separate application. `/` is served by `config.views.home`, which uses the existing search layer, and `templates/index.html` contains the production homepage introduced by PR #151.

## Core domain foundations

### Artifact

`Artifact` is the shared platform representation for a knowledge or product resource. Current kinds include Product, LibraryItem, and Other. It stores shared metadata and lifecycle state such as `is_active`.

Domain applications should continue to own their detailed vertical data rather than moving all domain state into the Core Artifact model.

### Identity

Typed identity resolution uses `UserIdentity`. Ownership and other artifact relationships use `ArtifactIdentityRole`, including the `owner` role.

Identity primitives are shared foundations; they should not be interpreted as a complete authorization framework.

### Artifact binding

`ArtifactBinding` connects a domain record to its Core Artifact representation. Current patterns include one-to-one artifact references where appropriate, such as Notes preserving its own domain model while exposing a shared artifact identity.

### Entitlement

`Entitlement` is transitional and intentionally limited. It is not a generic permission system and should not be used as a substitute for domain-owned authorization rules.

### Evidence and verification

Core evidence primitives include `Evidence` and `EvidenceRelation`. Verification workflows use `VerificationRequest` and `VerificationResult`, with `ReviewRecord` preserving review history.

## Service layer

### Unified search

The current homepage and search surfaces use `UnifiedSearch` from `apps.search.services` rather than a duplicate homepage-specific search implementation.

Search-related helpers also live under `apps/search/`, including narrow-window retrieval logic.

### Verification, reputation, and entitlement

Domain services include verification, reputation, and entitlement behavior. These services should remain the owner of their domain rules rather than moving authorization or business logic into templates, the registry, or capability metadata.

### Audit recording

Audit persistence is exposed through `record_audit_event` in `apps.audit.services`.

The current accepted audit-event schemas are deliberately bounded to:

- `verification.request.created`
- `verification.request.changed`
- `verification.result.recorded`

Unknown event names are rejected with `ValidationError`. New audit taxonomies should therefore be introduced explicitly rather than inferred or invented by callers.

## Platform Shell

The Platform Shell is the canonical app-discovery and workspace layer.

### AppManifest

`AppManifest` describes an installed VORNEQ application. Its current contract includes metadata such as:

- `slug`
- `label`
- `url_name`
- ordering and primary-navigation visibility
- authentication visibility
- active namespaces
- optional URL configuration and route prefix
- descriptive capability strings
- platform contract version

Selected manifest and registry behavior is treated as stable for current application development; future expansion should remain versioned and reviewed.

### PlatformRegistry

`PlatformRegistry` is the canonical source for installed application metadata. It supports registration, lookup, sorted enumeration, navigation generation, and localized URL contribution.

Applications should register through their `vorneq_app.py` manifest instead of being hard-coded into the Launcher, Workspace, navigation, or homepage.

### Launcher and Workspace

The current shell routes include:

- `/apps/` — App Launcher
- `/apps/workspace/` — Workspace index
- `/apps/workspace/<slug>/` — application workspace

Localized route prefixes are contributed through the existing platform-shell URL integration.

### Global context

The Platform Shell context processor exposes canonical registry information to templates, including `platform_apps` and `platform_navigation`.

Templates should reuse those values rather than create a second registry or parallel application-discovery mechanism.

## Capability discovery v1

Capability discovery is currently descriptive only.

Capability strings on app manifests are metadata used for discovery and classification. They do not:

- execute code,
- grant permissions,
- authorize cross-app access,
- define generic request/response contracts.

Executable capabilities belong to a future contract and require typed and bounded I/O, explicit actor/request context, domain-owned authorization, failure isolation, versioning, and a separate architecture decision.

## Homepage architecture

The production homepage merged in PR #151 deliberately reuses existing architecture instead of introducing a new homepage application.

Current behavior includes:

- `/` continues to use `config.views.home`.
- Existing `UnifiedSearch` retrieval and pagination are preserved.
- Installed app cards are sourced from the Platform Registry context.
- Shared VORNEQ design tokens are used rather than a parallel design system.
- `assets/css/homepage.css` contains homepage-specific layout and presentation styles.
- The visual knowledge-network globe is lightweight inline SVG with no external icon or font dependency.
- Scale metrics remain neutral (`—`) until real production data exists.
- Unsupported partner logos and fabricated usage figures are not presented as factual.
- Platform maturity labels distinguish current stable foundations, experimental descriptive capabilities, and future executable-provider contracts.

The homepage is a presentation and discovery surface; it is not a second registry, authorization layer, or platform API.

## UI and theme foundations

Shared UI primitives come from the existing token and theme system in `assets/css/`, including `tokens.css`, theme palettes, base styles, global-experience styles, and standalone navigation styles.

Primary templates inherit from `templates/base.html`, which provides the common shell, theme handling, shared navigation, and footer.

New application or homepage CSS should prefer shared tokens such as page/surface backgrounds, text colors, accent colors, spacing, typography, radii, shadows, and motion values rather than defining a parallel token namespace.

## Application registration

A platform application registers itself through `vorneq_app.py`, typically by constructing an `AppManifest` and calling `registry.register(manifest)`.

Once registered, the application can participate in the canonical Launcher, Workspace, localized routes, navigation visibility, and descriptive capability discovery according to its manifest.

## Contract maturity

The following summary reflects current architectural maturity rather than a promise of permanent API stability:

| Area | Current maturity |
| --- | --- |
| Selected `AppManifest` fields | Stable for current development |
| `PlatformRegistry.register/all/get` | Stable for current development |
| App Launcher | Stable for current development |
| Workspace Shell | Stable for current development |
| Capability strings | Experimental / descriptive |
| Capability discovery | Experimental / descriptive |
| Audit event contract | Experimental and explicitly bounded |
| Entitlement | Transitional / experimental |
| Executable capabilities/providers | Future contract |

For detailed contract guidance, use the App Developer Guide and Platform App Contract documentation in this repository.

## Important boundaries

Keep these constraints in mind when extending VORNEQ:

- There is no separate `apps/homepage/`; the homepage reuses the existing root view and template flow.
- Unified search comes from `apps.search.services`.
- The Platform Registry is canonical for installed-app discovery.
- `Entitlement` is not generic authorization.
- Capability discovery v1 is metadata only.
- Audit event names are currently limited to the explicitly registered verification schemas.
- Domain applications should retain ownership of their detailed models and authorization rules.
- New executable cross-app contracts should be introduced through versioned architecture work rather than inferred from descriptive capability strings.

## Useful development commands

```bash
git clone https://github.com/13640226/VORNEQ.git
cd VORNEQ
git checkout main
git pull

python manage.py migrate
python manage.py runserver
python manage.py test
```

For historical review, the repository state immediately after PR #150 and before the homepage work can be inspected with:

```bash
git checkout 7b68a7e78955c1fadfaa77bbf99922141de19462
```

Do not use that historical snapshot as the current development base. Current work should branch from the latest `main`.