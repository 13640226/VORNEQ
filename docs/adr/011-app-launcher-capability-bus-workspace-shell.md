# ADR 011: App Launcher, Capability Bus, and Workspace Shell

**Status:** Proposed  
**Date:** 2026-09-07

## Context

ADR 010 introduced the **Platform Shell** with an installable app manifest contract. The current implementation of `AppManifest` provides:

- `slug`, `label`, `url_name`, `order`, `show_in_primary_nav`, `requires_authentication`, `active_namespaces`, `urlconf`, `route_prefix`, `capabilities`, `contract_version`.

The current contract intentionally keeps capabilities descriptive. It does not define executable providers for global commands, global search, notifications, or workspace panels. This ADR records the boundaries for an App Launcher, a transitional Capability Bus, and a Workspace Shell without expanding the current runtime contract.

## Decision

Adopt a layered platform composition model.

### 1. App Launcher

The App Launcher is a discovery and navigation surface, such as `/apps` or a sidebar, for installed VORNEQ apps.

In v1, launcher presentation must be derived from fields that exist in the current manifest contract: `label`, `slug`, and the named landing route in `url_name`. A launch action resolves that named route rather than inventing a second routing contract.

`description` and `version` are not part of the current manifest. They may be introduced later through an explicitly versioned contract extension.

The launcher provides no authorization or access rights. Authentication visibility in the shell remains presentation behavior only; domain authorization stays with the owning app.

### 2. Capability Bus v1: declarative discovery

Capability Bus v1 is transitional. Apps declare descriptive capability identifiers through the existing `AppManifest.capabilities` tuple. The existing platform registry remains the source of truth; v1 must not create a parallel app or capability-registration authority.

Example identifiers may include:

- `search_provider_v1`
- `global_command_v1`

In v1 these identifiers are discovery/declaration tokens only. They do not register callable providers, execute handlers, grant permissions, or authorize access.

Future executable provider contracts require a separate versioned extension or ADR. Such a contract must preserve these boundaries:

- Capability is not permission.
- No arbitrary runtime code loading.
- No hidden cross-app data access.
- Invocation carries explicit actor/request context plus any domain-specific authorization context required by the owning app.
- `Entitlement`, where applicable, is one possible domain authorization input and is not a universal authorization primitive.
- Provider outputs are typed and bounded and cannot inject arbitrary HTML or executable payloads.

### 3. Workspace Shell

The Workspace Shell is a composition surface capable of hosting app workspaces in isolated navigation/state contexts, for example tabs or panels.

Each app continues to own its routes, state, data, and authorization policy. The Workspace Shell does not gain direct access to another app's domain data and does not become a cross-app service locator.

## Boundaries and Guardrails

The following guardrails apply to any future executable capability contract:

| Principle | Implementation |
| :--- | :--- |
| Capability ≠ Permission | Declaring or exposing a capability does not grant access to user data or cross-app resources. |
| No runtime code loading | Apps remain deploy-time reviewed code; providers are not downloaded or loaded from arbitrary external sources at runtime. |
| Explicit invocation context | Invocation carries explicit actor/request context and any domain-specific authorization inputs required by the owning app. |
| Typed and bounded outputs | Provider responses follow an explicit schema and cannot inject arbitrary HTML or executable code. |
| No hidden cross-app access | Providers access only data authorized by their owning domain policy; the bus itself does not bypass those policies. |

## Consequences

### Positive

- Preserves one source of truth for installed apps and current capability declarations.
- Separates discovery, presentation, provider execution, and authorization.
- Enables incremental platform growth without turning the manifest into an unbounded service locator.
- Keeps future provider contracts compatible with VORNEQ's identity, verification, evidence, reputation, entitlement, and audit boundaries.

### Costs / Risks

- Capability Bus v1 remains declarative; it does not yet provide executable integrations.
- Future provider contracts require typed schemas, authorization semantics, and audit policy before execution is introduced.
- Workspace composition adds lifecycle and isolation complexity that should not be hidden inside the current manifest contract.

## Rejected Alternatives

- **Arbitrary runtime plugin loading:** rejected because it expands the threat model beyond deploy-time reviewed code.
- **Direct cross-app data access:** rejected because it bypasses domain ownership and authorization boundaries.
- **Launcher-based authorization:** rejected because discoverability/navigation must not become authority.
- **Parallel capability registry:** rejected for v1 because `AppManifest.capabilities` already provides the canonical declaration surface.

## Related Documents

- [ADR 010: Installable Platform App Contract](010-installable-platform-app-contract.md) — currently Proposed.
- [`docs/architecture/platform-app-contract.md`](../architecture/platform-app-contract.md) — developer guide for the current manifest contract.

## Follow-up

1. Record this ADR as a docs-only change.
2. Implement Capability Bus v1 as indexing, discovery, and validation over existing manifest capability declarations, without a parallel registry.
3. Build the App Launcher UI using VORNEQ design tokens and current manifest fields.
4. Introduce a Workspace Shell through a separately bounded implementation step.
5. Validate the composition contract with a small non-email proof-of-concept app before attempting a complex communications product.
