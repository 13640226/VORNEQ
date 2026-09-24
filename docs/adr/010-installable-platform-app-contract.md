# ADR 010: Installable Platform App Contract

**Status:** Proposed  
**Date:** 2026-09-07

## Context

VORNEQ already contains multiple domain applications, but global navigation and localized URL mounting have historically been configured in central templates and `config/urls.py`. That approach is workable for a small product, but it creates increasing coupling as the platform grows: every new application must edit shared shell files simply to become discoverable and routable.

VORNEQ needs a bounded extension mechanism that lets future first-party applications join the platform without turning the codebase into a monolith or introducing runtime remote-code installation.

## Decision

Introduce a versioned **VORNEQ App Manifest** contract owned by `apps.platform_shell`.

An installed Django application may opt into the platform by providing a `vorneq_app.py` module and registering one `AppManifest`. The manifest may declare:

- a stable application slug;
- a localized display label;
- a named landing route;
- navigation order and visibility;
- authentication visibility requirements;
- active namespaces;
- an optional Django URLconf and relative route prefix;
- capability identifiers;
- the platform contract version.

The platform shell autodiscovers these modules from Django's installed application registry. It exposes registered applications to templates through a context processor and mounts contributed localized URL patterns from the same manifest contract.

The initial proof of the contract is Marketplace: its primary navigation entry and localized URL mount are contributed by `marketplace/vorneq_app.py`. The existing legacy Library redirect remains explicit and unchanged.

## Boundaries

This contract is **not** a remote plugin marketplace, sandbox, package downloader, or dynamic code execution system. Applications still enter the deployment through reviewed source code and `INSTALLED_APPS`.

The manifest does not grant authorization. Authentication visibility only controls shell presentation. Domain authorization, entitlements, object-level permissions, evidence access, verification authority, and audit obligations remain inside their owning domain policies.

Capabilities are descriptive integration identifiers, not permission grants and not truth/trust signals.

The platform shell must not infer Identity, Verification, Reputation, or Entitlement semantics from an application's registration metadata.

## Compatibility

The contract is explicitly versioned. Unsupported contract versions fail during registration instead of being interpreted heuristically.

Routes contributed by a manifest must use relative prefixes without a leading slash. Existing routes should only migrate into the manifest mechanism when behavior and backwards compatibility can be preserved.

## Consequences

### Positive

- Future applications can contribute routing and navigation without editing shared template logic.
- Application discovery becomes deterministic and testable.
- The shell gains a stable basis for future app launcher, capability discovery, workspace composition, and per-app resources.
- Domain code remains independently owned.

### Costs / Risks

- Manifest import happens during Django application startup, so manifest modules must remain lightweight and side-effect free except for registration.
- Duplicate slugs and unsupported contract versions are startup errors by design.
- A future capability system will require separate authorization and governance; capability strings alone must never become authority.

## Follow-up

Future ADRs may extend the contract for versioned frontend assets, command/search providers, notifications, workspace surfaces, or API discovery. Those extensions should remain explicit and backward-compatible rather than turning the manifest into an unbounded service locator.
