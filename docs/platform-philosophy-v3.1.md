# VORNEQ — Platform Philosophy V3.1
## The Interconnected Application Ecosystem

DOCUMENT_ID: VORNEQ_PLATFORM_PHILOSOPHY_V3_1
VERSION: V3.1
DATE: 2026-11-06
STATUS: OWNER_DIRECTION_ACCEPTED / DOCUMENTARY_REVISION
SCOPE: PRODUCT_PHILOSOPHY / ARCHITECTURAL_DIRECTION
IMPLEMENTATION_AUTHORIZATION: NONE

## 1. Identity and mission

VORNEQ is an interconnected ecosystem of specialized digital applications, knowledge, tools and services. It is **one platform with many independently governed applications**, not a universal domain-data store or an unrestricted super-app.

**One Platform. Many Applications. Connected Possibilities.**

Its mission is to provide continuity of identity, language, preferences, navigation and workflow context across specialized experiences, without transferring data access or business authority implicitly. Its vision is interoperable, extensible applications connected through reviewed contracts and meaningful human control.

## 2. Ten foundational principles

- **PHIL-01 — One Platform, Many Applications:** each app owns its domain data, business logic and authorization.
- **PHIL-02 — Interoperability Without Coupling:** versioned, reviewed contracts; no private-table access or hidden cross-app imports.
- **PHIL-03 — User-Centered Continuity:** consistent identity, preferences, navigation and Workspace context; continuity is not consent to share private data.
- **PHIL-04 — Identity Is Not Authorization:** actor identity never establishes resource permission.
- **PHIL-05 — Discovery Before Dependency:** canonical registry and descriptive capabilities facilitate discovery; registration grants neither access nor execution.
- **PHIL-06 — Contextual Trust and Inspectable Evidence:** no universal trust score or platform declaration of final truth.
- **PHIL-07 — Human Control and Data Responsibility:** meaningful export, deletion, preference and privacy controls subject to applicable law, retention and shared-reference rules.
- **PHIL-08 — AI as an Ecosystem Capability:** AI assists discovery and analysis within tenant, authorization, privacy and evidence boundaries; output is not verified evidence.
- **PHIL-09 — Modular Growth, Not Architectural Inflation:** shared primitives require genuine cross-domain demand; Core must not absorb app-specific models.
- **PHIL-10 — Transparency and Accountability:** proportionate explanations and auditability; audit is not a source of truth.

The PHIL-* namespace intentionally avoids confusion with governance blocker P_06.

## 3. Architectural layers

**A — Platform Core:** reviewed shared identity, Artifact, ArtifactBinding, Evidence and Verification primitives. Artifact is not a domain model, publication state or authorization.

**B — Platform Shell:** Launcher, navigation and Workspace provide presentation and composition, not shared mutable state, domain permissions or arbitrary embedded app execution.

**C — Platform Registry and Capability Bus:** AppManifest/PlatformRegistry provide canonical, deploy-time-reviewed app metadata. Capability Discovery v1 is **stable for descriptive discovery only**; no execution or permission is implied. Executable Capability Bus v2 remains **PROPOSED** under ADR 012: synchronous, read-only, typed, bounded PoC with explicit CapabilityContext, domain-owned authorization, and no arbitrary runtime provider loading. `read_artifact_v1` and its `is_active` PoC eligibility must never be treated as general publication/read permission. Executable capability providers require separate reviewed contracts and approval.

**D — Specialized Applications:** Documents/Knowledge, Notes, Marketplace, Search/Discovery and other domain applications. Examples describe current or intended product areas, not proof of operational readiness.

**E — Infrastructure:** databases, queues, storage and external adapters implement infrastructure without changing domain ownership or security boundaries.

The preferred direction is a modular monolith with extraction-friendly boundaries, not mandatory microservices.

## 4. Inter-app connection and user control

Any cross-app invocation must have a reviewed versioned contract, explicit actor/request context, authorization by the owning domain, least-necessary data access, tenant/privacy isolation, bounded failures and appropriate evidence/audit. Registry visibility, Launcher access, Entitlement, reputation, verification and search inclusion cannot substitute for authorization. No unreviewed runtime plugins, side-effecting bus providers, implicit shared state or remote code execution are authorized by this philosophy.

## 5. Economic independence and discovery integrity

Paid placement, subscriptions and marketplace services may be offered, but payment must not covertly affect organic discovery ranking or be represented as trust, verification or permission. Sponsored placements must be distinguishable and clearly labeled. Any ranking-policy change needs separate product and architectural review.

PAYMENT != TRUST != VERIFICATION != AUTHORIZATION

## 6. Capability maturity and production readiness

- **PROPOSED:** direction or contract under review, not a stable dependency.
- **EXPERIMENTAL:** bounded implementation or semantics subject to change.
- **STABLE (CURRENT DEVELOPMENT):** reviewed in-repository contract, not a perpetual compatibility guarantee.

No maturity label implies production security verification. The precise status of each component is governed by the Platform Contract and relevant ADR, not by this philosophy.

## 7. Non-collapsible boundaries

```text
IDENTITY != AUTHORIZATION
CAPABILITY != PERMISSION
SEARCH != VERIFICATION
VERIFICATION != TRUTH
REPUTATION != GLOBAL_TRUST_SCORE
ARTIFACT != DOMAIN_MODEL
REGISTRY != SERVICE_LOCATOR
WORKSPACE != DOMAIN_AUTHORITY
AI_OUTPUT != VERIFIED_EVIDENCE
INTEROPERABILITY != DATA_ACCESS
PAYMENT != TRUST
CONTRACT_STABLE != PRODUCTION_VERIFIED
DOCUMENTARY_ACCEPTANCE != EXECUTION_AUTHORIZATION
```

## 8. Relationship to V2 and decision discipline

V3.1 preserves V2's Discovery-not-Feed, Context-not-Score, Evidence-not-Truth, Portable-Identity and One-Platform principles while broadening the primary product identity to an interconnected application ecosystem. Portable identity beyond the current platform is a long-term direction, not a required DID protocol.

This philosophy defines **why**, not a new runtime contract. Architecture contracts define boundaries; ADRs define technical decisions. Any substantive contract change requires its own review/ADR. This document changes no backend, migrations, security rules, AI Core, production environment or deployment authorization.

## 9. Success criteria (proposed, not adopted KPIs)

Evaluate real cross-app workflow adoption, user experience continuity, module independence, authorization/tenant boundary quality, provenance inspectability, app onboarding cost and algorithmic explainability. Numerical targets, measurement methods and formal KPI adoption require a separate product decision.

KPI_STATUS: PROPOSED / NOT_FORMALLY_ADOPTED

## 10. Source alignment and review record

Documentary comparison performed against the main-branch texts of:
- `docs/platform-philosophy-v2.md`
- `docs/architecture/platform-contract.md`
- `docs/architecture/platform-app-contract.md`
- `docs/adr/010-installable-platform-app-contract.md`
- `docs/adr/011-app-launcher-capability-bus-workspace-shell.md`
- `docs/adr/012-executable-capabilities.md`

Alignment: compatible as **normative product direction**, provided no proposed capability is represented as stable or production-verified. This is a documentary comparison, not a source-code/runtime security audit.

ANM_PH_01: ADDRESSED (PHIL-* identifiers)
ANM_PH_02: ADDRESSED (KPIs remain proposed)
ANM_PH_03: ADDRESSED (organic/sponsored ranking transparency)
ANM_PH_04: ADDRESSED (Capability Bus v2 remains proposed)

OWNER_DIRECTION: ACCEPTED
ARCHITECTURAL_CONTRACTS: UNCHANGED
IMPLEMENTATION_AUTHORIZATION: NONE
MERGE_AUTHORIZATION: NONE
DEPLOY_AUTHORIZATION: NONE
DATABASE_CHANGES: NONE
PRODUCTION_SECURITY_VERIFICATION: NOT_CLAIMED
