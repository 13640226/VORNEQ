# VORNEQ Platform Contract v0.1

## 1. Purpose & Non-Goals

### Purpose

This document defines the reviewed architectural contract for building independent applications on VORNEQ. It establishes shared platform boundaries, primitive maturity, cross-cutting invariants, app-isolation rules, and compatibility expectations.

The goal is not to make every current implementation permanently stable. The goal is to make the status and ownership of each surface explicit so applications can depend only on contracts whose maturity is understood.

### Non-goals

This contract does not:

- define domain-specific models such as `EmailMessage`, `Transaction`, or `VM`;
- require domain state to be moved into Core primitives;
- define migrations, caching, indexing, storage engines, queues, or other implementation details;
- define deployment, monitoring, backup, or other operational processes;
- permit arbitrary runtime installation or execution of remote application code;
- turn descriptive discovery metadata into authorization or executable behavior;
- define a global trust score or a universal permission system.

A domain model may expose an `Artifact` representation when shared identity, provenance, discovery, or cross-platform referencing is useful. The domain model does not thereby become an `Artifact`, and `Artifact` must not become a universal container for domain state.

## 2. Architectural Layers

VORNEQ is developed as a modular platform with hard domain boundaries.

| Layer | Responsibility | Dependency boundary |
| --- | --- | --- |
| Core Domain | Shared domain foundations such as identity, artifact, evidence, and other reviewed primitives | Must not depend on higher layers |
| Platform Shell | App manifest, canonical registry, Launcher, Workspace, route contribution, and platform context | Depends on reviewed Core contracts |
| Capability Bus | Versioned cross-app invocation contracts where explicitly approved | Depends on Core and canonical platform declarations; does not own domain policy |
| App Layer | Independent applications such as Notes, Marketplace, and future Documents/Knowledge apps | Owns domain models, business rules, and authorization |
| Infrastructure | Database, cache, queues, object storage, external adapters, and operational integrations | Implements lower-level technical concerns without redefining domain contracts |

The architectural direction is a modular monolith with extraction-friendly boundaries. Service decomposition is an operational choice, not a prerequisite for platform modularity.

## 3. Primitive Status Matrix

Status in this document is intentionally explicit:

- **Stable (current development):** reviewed behavior that in-repository applications may rely on today. This is not a promise of indefinite backward compatibility.
- **Experimental:** implemented or partially implemented behavior whose semantics are intentionally bounded or transitional.
- **Proposed:** architecture under review or validation that must not be treated as a stable platform dependency.

| Primitive / Surface | Status | Current contract |
| --- | --- | --- |
| Identity | Stable (current development) | Shared typed identity foundations and artifact relationships; not a complete authorization framework |
| Artifact | Stable (current development) | Shared representation for identity/provenance/discovery with bounded lifecycle metadata; not a domain model |
| ArtifactBinding | Stable (current development) | Connects a domain record to a Core Artifact representation while preserving domain ownership |
| Evidence | Stable (current development) | Shared evidence primitives and evidence relations |
| Verification | Stable (current development) | Verification request/result workflow with review history |
| Contextual Reputation | Stable (current development) | Domain/context-specific reputation behavior; never a global trust score |
| AppManifest | Stable (current development) | Deploy-time application declaration with validated metadata and platform contract version |
| PlatformRegistry | Stable (current development) | Canonical source of installed application metadata, lookup, ordering, and route/navigation contribution |
| Launcher | Stable (current development) | Authenticated discovery and navigation surface; never an authorization layer |
| Workspace Shell | Stable (current development) | Presentation/composition context for installed apps; no shared state or implicit authority |
| Unified Search | Stable (current development) | Shared retrieval surface provided by `apps.search.services.UnifiedSearch` |
| Entitlement | Experimental | Transitional and intentionally limited; not a generic permission framework |
| AuditEvent contract | Experimental | Append-only persistence with an explicitly bounded event taxonomy |
| Capability discovery v1 | Stable (descriptive only) | Read-only discovery over declared capability strings; no execution or authority |
| Executable Capability Bus v2 | Proposed | Typed, versioned, synchronous, read-only PoC contract described by ADR 012 |

This matrix is a maturity declaration, not an instruction to centralize domain logic in shared primitives.

## 4. Primitive Contracts

### Identity

Identity provides shared typed identity references for platform actors and relationships.

Invariants:

- identity is not authorization;
- identity resolution does not grant access;
- domain applications remain responsible for policy decisions involving their data.

### Artifact

Artifact is a shared platform representation used where common identity, provenance, lifecycle metadata, discovery, or cross-platform referencing is useful.

Invariants:

- an Artifact has a bounded kind and shared metadata/lifecycle representation;
- domain-specific state remains in the owning application;
- Artifact presence does not imply publication, verification, trustworthiness, or permission to read;
- Artifact must not become a God Model for unrelated domains.

### ArtifactBinding

ArtifactBinding connects a domain-owned record to its shared Artifact representation.

Invariants:

- the binding does not transfer ownership of domain semantics to Core;
- app-specific lifecycle and integrity rules remain domain-owned;
- one shared Artifact identity must not be used to erase meaningful domain boundaries.

### Evidence

Evidence represents referencable material used by domain workflows such as verification.

Invariants:

- Evidence is not automatically proof of truth;
- consumers must preserve provenance and domain interpretation;
- evidence relationships must not silently grant permissions.

### Verification

Verification represents an explicit review/verification workflow and result, not a property inferred from search ranking, reputation, or artifact existence.

Invariants:

- verification state must be explicit;
- historical review information must remain referencable where the implementation provides it;
- search presence or popularity cannot substitute for verification.

### Contextual Reputation

Reputation is contextual rather than globally aggregatable.

Invariants:

- reputation is scoped to a defined context, role, domain, or method;
- unrelated reputation values must not be collapsed into a universal trust score;
- reputation does not independently authorize access.

### Entitlement

Entitlement is transitional and experimental.

Invariants:

- Entitlement is not a universal authorization system;
- applications must not assume that an entitlement record replaces domain-owned access policy;
- broader semantics require a separately reviewed contract before stabilization.

### AuditEvent

Audit recording is append-oriented and its accepted taxonomy is deliberately bounded.

Current accepted event schemas are limited to the reviewed verification events documented in the architecture overview. New platform-wide audit semantics must be introduced explicitly rather than inferred by callers.

### AppManifest

AppManifest is the deploy-time declaration for an installed reviewed VORNEQ application.

It may describe identity, labels, routes, navigation behavior, descriptive capabilities, and a platform contract version according to the current Platform App Contract.

Invariants:

- registration occurs from reviewed deploy-time code;
- manifest modules remain lightweight and must not derive request-specific authority;
- capability declarations are metadata unless a separately reviewed executable contract exists;
- unsupported contract versions fail closed according to the app contract.

### PlatformRegistry

PlatformRegistry is the canonical source of truth for installed application metadata.

Invariants:

- Launcher, Workspace, navigation, and discovery must not create parallel app registries;
- registry presence does not grant permission to an app or its data;
- registration must not be used as a hidden cross-app service locator for internal implementations.

### Launcher

Launcher provides discovery and navigation for installed applications.

Invariants:

- **Launcher != Authorization**;
- visibility and launchability do not imply data access;
- unknown or unresolvable launch targets must be handled neutrally rather than guessed.

### Workspace Shell

Workspace provides a shared composition and presentation context around applications.

Invariants:

- **Workspace = Composition Context**;
- Workspace does not own app data, shared mutable state, or domain authorization;
- Workspace must not bypass app-owned routes, authentication, permissions, or entitlement interpretation;
- embedded execution, shared-state systems, or executable workspace providers require separate contracts.

### Unified Search

Search provides shared retrieval across supported platform data sources.

Invariants:

- **Search != Verification**;
- ranking, retrieval, or inclusion is not proof, endorsement, authority, or trust;
- domain adapters and search surfaces must not silently mutate source-of-truth domain state.

### Capability Discovery v1

Capability strings declared in AppManifest are descriptive discovery tokens.

Invariants:

- **Capability != Permission**;
- declaration does not execute code;
- declaration does not grant cross-app data access;
- declaration does not define a generic request/response protocol.

### Executable Capability Bus v2

Executable Capability Bus v2 is currently Proposed and governed by ADR 012.

Its PoC direction is deliberately narrow: deploy-time reviewed providers, versioned identifiers, typed and bounded input/output, explicit invocation context, bounded failure results, synchronous execution, and read-only behavior.

Authorization and business policy remain with the owning domain. The bus may resolve and invoke an approved provider, but it must not invent a platform-wide permission model.

## 5. Cross-Cutting Invariants

These invariants apply across all platform layers:

1. **Capability != Permission.** Declaring or registering a capability never grants authority.
2. **Search != Verification.** Retrieval or ranking never establishes truth, trust, or approval.
3. **Launcher != Authorization.** Navigation is not access control.
4. **Workspace = Composition Context.** Workspace composes presentation/context; it does not own permissions or domain state.
5. **Artifact != Domain Model.** Artifact provides shared representation, not universal domain storage.
6. **Reputation != Global Trust Score.** Reputation remains contextual and must not be collapsed into one global scalar.
7. **Identity != Authorization.** Resolving an actor does not determine what the actor may do.
8. **Registry != Service Locator.** Canonical app metadata must not become hidden access to another app's internals.
9. **Verification != Reputation.** One cannot be silently substituted for the other.
10. **Platform metadata != policy.** Labels, routes, capabilities, search presence, or shell visibility cannot be interpreted as authority.

## 6. App Isolation Rules

Applications must preserve explicit ownership boundaries.

- An app owns its domain models, business rules, authorization, and state transitions.
- An app must not import or depend on another app's internal implementation as an integration mechanism.
- Shared platform behavior must use an explicitly reviewed shared contract.
- Cross-app executable interaction, where approved, must use a versioned capability/provider contract rather than hidden imports or database coupling.
- Direct access to another app's private tables, services, or internal state is outside the platform contract.
- Platform Shell must not accumulate domain business logic merely because multiple apps need navigation or discovery.
- Infrastructure choices must not redefine domain ownership.

The target is strong modular isolation inside the monolith so components can evolve or later be extracted without rewriting platform semantics.

## 7. Capability / Permission Boundary

A capability answers: **what integration contract can a provider expose?**

A permission answers: **may this actor perform this operation on this domain resource in this context?**

These are separate concerns.

For executable capabilities:

- the canonical manifest/registry remains the declaration source;
- executable registration must be explicitly reviewed and versioned;
- the invoker validates contract shape, resolves the provider, passes explicit context, isolates failures, and returns a bounded result;
- the owning domain evaluates authorization or eligibility;
- the bus must not infer permission from capability presence, Entitlement, reputation, verification, Workspace context, Launcher visibility, or search presence;
- raw provider exceptions must not become a cross-app API contract.

Capability Bus is therefore an integration boundary, not a central authorization service.

## 8. Versioning & Compatibility

VORNEQ platform contracts must evolve deliberately.

### Contract levels

- **Major:** incompatible semantic or shape changes that require explicit migration/review.
- **Minor:** backward-compatible additions to an existing stable contract.
- **Patch:** backward-compatible corrections or clarifications that do not change intended semantics.

App manifests declare the platform `contract_version` supported by the app according to the current Platform App Contract. Unsupported versions must fail closed rather than being guessed or silently coerced.

Executable capabilities use independently versioned capability identifiers/contracts. A bus-generation label such as v2 must not be confused with the version of an individual capability.

### Compatibility rules

- Stable-for-current-development surfaces may be used by reviewed in-repository apps.
- Experimental surfaces may change after review and must not be assumed to carry long-term compatibility guarantees.
- Proposed surfaces must not be treated as stable dependencies until their ADR and implementation status are promoted explicitly.
- Breaking semantic changes require explicit documentation and, where architecture meaning changes, ADR-level review.
- No future contract may be inferred merely from a suggestive capability name, route, model field, or documentation example.

## 9. Experimental Surface

The following areas are intentionally not part of the stable platform contract:

### Entitlement

Entitlement is transitional and limited. It must not be generalized into a universal permission service without a separately reviewed design.

### AuditEvent taxonomy

Audit persistence exists, but the generic platform event taxonomy is not stable. The accepted events are currently deliberately bounded. New event families require explicit schema and ownership decisions.

### Executable capabilities

ADR 012 proposes Capability Bus v2 and a bounded `read_artifact_v1` PoC. Until that proposal is accepted and its implementation contract survives review, applications must not treat executable capabilities as a stable cross-app API.

### Explicitly outside v0.1

The following require separate design/review before entering the contract:

- arbitrary runtime plugin loading;
- remote unreviewed code execution;
- generic cross-domain permission or entitlement semantics;
- global commands/search/notification/payment providers as implicit contracts;
- asynchronous or side-effecting capability execution;
- shared mutable cross-app state;
- iframe/microfrontend execution contracts;
- universal reputation or trust scoring.

## 10. Future Vertical Validation

The recommended first platform-validation vertical is a Knowledge / Documents Workspace.

Its purpose is not merely to add another application. It should validate whether the platform boundaries support a complete workflow without adding domain-specific special cases to Core.

A representative validation chain is:

```text
Identity
  -> Workspace
  -> domain-owned Document model
  -> Artifact representation
  -> ArtifactBinding
  -> domain authorization / experimental Entitlement where explicitly appropriate
  -> Unified Search
  -> Verification / Evidence
  -> versioned document.preview capability after executable capabilities are approved
```

Success criteria:

- the Documents domain owns document-specific state and rules;
- Core requires no document-specific fields or branching;
- Artifact provides shared representation without absorbing the document model;
- Workspace composes context without taking ownership of access policy;
- Search retrieves documents without implying verification;
- Evidence/Verification remain explicit workflows;
- any executable capability uses typed, versioned, auditable boundaries and domain-owned authorization;
- no direct dependency on another app's internal implementation is required.

If this vertical can be implemented without violating the invariants in this document, VORNEQ has demonstrated a reusable platform contract rather than an application suite held together by conventions.

## Related Documentation

- [Architecture Overview](overview.md)
- [Platform App Contract](platform-app-contract.md)
- [ADR 010: Installable Platform App Contract](../adr/010-installable-platform-app-contract.md)
- [ADR 011: App Launcher, Capability Bus, and Workspace Shell](../adr/011-app-launcher-capability-bus-workspace-shell.md)
- [ADR 012: Executable Capabilities (v2)](../adr/012-executable-capabilities.md)
