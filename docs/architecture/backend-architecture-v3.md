# VORNEQ Backend Architecture Map — v3

**Version:** 3.0  
**Status:** Descriptive snapshot  
**Date:** 2026-09-08  
**Snapshot Reference:** `ee53dc77c0878a89b92a4c4f5ba401252f5e78d2`  
**Purpose:** Provide a code-based map of selected VORNEQ backend concerns, their data flows, dependencies, and current implementation boundaries at the referenced snapshot.

---

## 1. Scope

This document focuses on three backend concerns that are easy to conflate but are implemented with distinct boundaries:

- **Trust / Assessment:** Evidence, Verification, Quality Signals, and Contextual Reputation.
- **Public Retrieval / Discovery:** Unified retrieval across public domain content.
- **Entitlement:** Access eligibility during the legacy-to-canonical identity/artifact migration.

This is not an exhaustive map of every VORNEQ backend subsystem. Platform Shell, Documents, Notes, Profiles, Graph, Audit, and other areas are documented separately.

Two invariants are especially important:

- **Verification is not truth.** A verification result is an assertion in a defined method/context.
- **Search is not verification.** Retrieval does not implicitly establish evidence quality, verification status, or reputation.

---

## 2. Domain Inputs Used by Public Retrieval

| Model | Source | Search role |
|---|---|---|
| `Article` | `apps.content` | Published article retrieval |
| `Product` | `marketplace` | Approved, published product retrieval |
| `LibraryItem` | `library` | Published library-item retrieval |
| `AudioItem` | `library` | Published audio compatibility path |
| `MediaAsset` | `apps.media` | Active media retrieval |

These models remain domain-owned. Unified Search reads them through adapters; it does not make them shared search-owned records.

---

## 3. Trust / Assessment Path

### 3.1 Evidence

The verified core relationship is:

```text
Claim ── EvidenceRelation ── Evidence
  │
  └──── EvidenceState (derived side projection)
```

`Claim` and `Evidence` are independent records. `EvidenceRelation` captures the semantic relationship between them with values including `supports`, `contradicts`, `contextualizes`, and `unclear`.

`EvidenceState` is a derived read model for a `Claim`. It summarizes active evidence relations and is **not** a required lifecycle step before verification.

### 3.2 Verification

```text
VerificationRequest
  ├── Claim
  ├── VerificationMethod
  └── artifact GenericForeignKey
        ├── marketplace.Product
        └── library.LibraryItem

VerificationResult ── VerificationRequest

VerificationEvidence
  ├── VerificationResult
  └── EvidenceRelation
```

At this snapshot, `VerificationRequest.artifact` is a `GenericForeignKey`, but its allowed target models are explicitly restricted to `marketplace.Product` and `library.LibraryItem`. It is not a generic reference to `core.Artifact`.

`VerificationEvidence` links a result to an `EvidenceRelation`; it does not attach arbitrary evidence unrelated to the request claim.

The public verification API exposed at this snapshot contains summary endpoints for products and library items rather than a general-purpose verification command API.

### 3.3 Verification activity and contextual reputation

`record_verification_activity()` records completed verifier activity:

```text
VerificationResult
       │
       ▼
record_verification_activity()
       │
       ▼
ContextualReputationEvent
  type = VERIFICATION_SUBMITTED
       │
       ├── increment sample_count
       └── update last_event_at

       no score change
```

The service requires a verifier and a completed verification request. During the staged identity migration, the legacy `user` subject remains required; an existing `UserIdentity` binding may also be written to the same contextual projection. The service does not create an Identity and does not infer an actor role beyond `VERIFIER`.

Submitting a verification result does **not** by itself prove verifier accuracy and therefore does not directly change reputation score.

### 3.4 Quality Signal eligibility

Quality assessment is a separate step:

```text
VerificationResult
       │
       ▼
QualitySignal
       │
       ▼
eligibility-v1 decision
```

V1 eligible signal types are:

- `EXTERNAL_REFERENCE`
- `REPRODUCIBILITY`
- `ADJUDICATION`
- `INDEPENDENT_CORROBORATION`

Eligibility also checks request completion, source/domain presence, verification-method consistency, provenance, independence declaration/basis, self-assessment exclusion, claim consistency for an attached `EvidenceRelation`, and the supported eligibility policy version.

A `QualitySignal` is an assessment signal, not a reputation score.

### 3.5 Policy-mediated scoring

```text
eligible QualitySignal + ScoringPolicy
                 │
                 ▼
        apply_scoring_policy()
                 │
                 ▼
 ContextualReputationEvent
       type = SCORE_APPLIED
                 │
                 ▼
  ContextualReputation.score
```

Scoring is explicit and versioned. The delta is derived from the signal direction through `ScoringPolicy.direction_weights` and `base_weight`; it is not derived directly from `VerificationResult.outcome`.

The scoring service is idempotent for the same reputation projection, quality signal, and scoring policy. It also refuses to mix incompatible policy versions in an existing projection and can return `projection_rebuild_required` instead of silently combining them.

Legacy `Reputation` and `ContextualReputation` coexist in Core at this snapshot. The code therefore contains a transitional data-model boundary, while contextual scoring itself is implemented.

### 3.6 Reputation layer — current status

The Trust reputation path is implemented as an explicit, staged set of services and projections rather than as an automatic end-to-end pipeline.

`ContextualReputation` is a method-, role-, and domain-scoped projection backed by append-only `ContextualReputationEvent` records. Legacy `Reputation` also remains present and operational for selected legacy reputation dimensions, so the current model boundary is transitional rather than fully consolidated.

Verification activity can be recorded explicitly through `record_verification_activity()`. The service accepts a completed `VerificationResult`, creates an idempotent `VERIFICATION_SUBMITTED` reputation event, increments the verifier projection's `sample_count`, and updates `last_event_at`. Verification submission alone does not change reputation score.

Quality assessment is a separate path. `QualitySignal` references a `VerificationResult` directly, and `create_quality_signal()` persists a versioned eligibility decision after checking completion state, signal type, source and domain information, verification-method consistency, provenance, independence, self-assessment exclusion, and claim consistency where an `EvidenceRelation` is supplied.

Eligible signals may be scored explicitly through `apply_scoring_policy()`. Scoring is domain- and method-scoped, versioned, idempotent for the same projection/signal/policy combination, and refuses incompatible policy-version mixing by returning `projection_rebuild_required`. Score deltas are derived from the signal direction and `ScoringPolicy`, not directly from `VerificationResult.outcome`.

The inspected Verification submission workflow does not automatically invoke reputation activity recording, QualitySignal creation, or scoring. These remain explicit service operations rather than an automatically orchestrated pipeline.

`ContextualReputation` is not dormant: production read/display consumers exist, including the authenticated profile path and public-safe reputation/trust-context presentation. Unified Search remains intentionally independent of Contextual Reputation and does not use reputation for retrieval eligibility or ranking.

Current integration caveats:

- Verification completion is not automatically wired to `record_verification_activity()`.
- QualitySignal creation and policy application are explicit operations rather than an automatic consequence of Verification completion.
- Legacy `Reputation` and `ContextualReputation` coexist during the ongoing subject/model migration.
- Search remains deliberately outside the Trust scoring boundary.

---

## 4. Public Retrieval / Discovery

### 4.1 Unified Search adapters

`apps.search.services.UnifiedSearch` uses five adapters:

```text
Article ───────────┐
Product ───────────┤
LibraryItem ───────┤
AudioItem ─────────┤──► UnifiedSearch ──► normalized merged results
MediaAsset ────────┘
```

The service is retrieval-only. In `apps/search/services.py` there is no direct dependency on Evidence, Verification, Contextual Reputation, Quality Signals, or Entitlement.

Each adapter owns domain-specific filtering and serialization into a common `SearchResult` representation.

### 4.2 Ordering and bounded candidate retrieval

For paginated search paths, adapters can order and limit candidates in the database using a global timestamp expression plus a textual primary-key tie-breaker. Candidate sets are then merged in Python and sorted by `(published_at, key)` in descending order.

This is an in-process federated retrieval design rather than a separate external search index.

### 4.3 Search execution strategies

`UnifiedSearch.search()` selects among three execution paths:

1. **Bounded fallback** — separate exact counts plus bounded candidates; also used when window functions are unavailable or page input follows the compatibility path.
2. **Window-count path** — bounded candidates with `COUNT(...) OVER()` for an exact adapter total.
3. **Narrow CTE path** — selected when `supports_narrow_cte()` is true.

`apps/search/narrow_window.py` enables the narrow CTE path only when Django reports window-function support and the database vendor is PostgreSQL or SQLite. It builds a narrow inner query containing primary key, total count, global timestamp, and tie-break key, then joins back to the base table for enrichment after limiting.

### 4.4 API caller versus Home caller

The public search API calls `UnifiedSearch.search()`, so it uses the execution-strategy routing above.

The current Home view is different: `config.views.home` calls `UnifiedSearch().collect()`, filters out URL-less cards, and applies Django `Paginator` in the view. Therefore the optimized `search()` strategy routing should not be described as the current Home pagination path.

Within `home()`, no Trust-derived enrichment or Trust-based ranking is applied to discovery results. The same `config/views.py` file also contains a separate authenticated profile view that reads Entitlement and Contextual Reputation; those profile reads are not part of Home discovery.

### 4.5 Unified Search boundary — current status

`UnifiedSearch` remains a public retrieval/composition boundary rather than an authorization or Trust boundary. Domain adapters determine retrieval eligibility through domain-owned publication/state filters such as `is_published`, approved product status, and active media state. The public Search API constrains caller-supplied filters, normalizes result representation, and delegates retrieval to the same adapter layer. No Evidence, Verification, Contextual Reputation, Quality Signal, or Entitlement dependency is present in the inspected Search service or API path.

Production search execution remains read-only and preserves equivalent pagination and ordering contracts across bounded fallback, window-count, and supported narrow-CTE paths. Unexpected database failures are not silently converted into fallback behavior.

Two implementation caveats remain:

- public eligibility is currently expressed through domain-specific model-state filters rather than a shared publication abstraction;
- Search-focused production tests currently live under `apps/core/tests/`, which is a historical ownership/layout coupling rather than a runtime architectural dependency.

---

## 5. Entitlement Boundary

Entitlement is implemented in Core with a staged legacy/canonical migration shape:

```text
legacy request key
User + Product
     │
     ▼
Entitlement
     │
     └── optional canonical pair
           Identity + Artifact
```

### 5.1 Grant semantics

`grant_entitlement()` continues to grant by the legacy `user + product` key. It enriches the same row with `identity + artifact` only when both canonical registry bindings already exist, or when an explicitly supplied canonical pair can be verified against those bindings.

A partial explicit canonical pair is rejected. Explicit canonical references that cannot be verified or that conflict with registry bindings are rejected. Existing incomplete/conflicting canonical state also fails closed.

The service does not create registry Identity or Artifact records.

### 5.2 Authorization semantics

`has_valid_entitlement()` does more than test `is_active` and expiry. It:

- requires an authenticated user;
- resolves the entitlement by the legacy `user + product` key;
- requires `Entitlement.is_valid()`;
- rejects a partial canonical pair;
- permits legacy fallback only while the row has no canonical references;
- when canonical references exist, requires resolvable registry bindings and exact identity/artifact agreement.

No Evidence or Verification check is part of this entitlement validation path.

This makes Entitlement a distinct authorization concern; Trust context does not silently grant access.

### 5.3 Architectural role of Entitlement

Entitlement remains a **transitional access primitive**, not a universal platform permission model. Its public service shape is still centered on the legacy `user + product` key, with canonical `Identity + Artifact` references populated and validated where bindings exist. Canonical inconsistency fails closed rather than silently falling back to legacy authorization.

This boundary must remain distinct from the executable Capability Bus. `has_valid_entitlement()` is appropriate inside a capability provider only when the owning domain explicitly defines entitlement as part of that domain's authorization policy. It must not become the default or universal authorization mechanism for executable capabilities.

### 5.4 Capability Bus v2 — current status

**Capability Bus v2 remains Proposed.** The core synchronous invocation framework is implemented and contract-tested, including bounded failure contracts, with one narrow read-only PoC provider registered at application startup. Product adoption remains pending. Some ADR 012 guardrails remain architectural constraints rather than mechanically enforced framework invariants.

Implemented behavior includes:

- `ExecutableCapabilityRegistry` enforces declaration-before-binding: a provider can be registered only for a capability identifier already declared through `AppManifest.capabilities`.
- `CapabilityInvoker` validates typed input and output, invokes the provider-owned `authorize()` hook before `execute()`, and converts controlled and unexpected failures into bounded `CapabilityResult` failure envelopes.
- The narrow `read_artifact_v1` PoC provider reads active Artifacts, is registered from `CoreConfig.ready()`, and is exercised through isolated tests. Its current authorization check is intentionally narrow and does not consume `CapabilityContext.actor`.
- Contract tests cover declaration enforcement, typed input/output, authorization denial, unknown capabilities, invalid output, controlled error conversion, and exception isolation.

ADR 012 constraints that are not fully enforced by the framework itself include:

- **Read-only execution:** the framework does not mechanically prevent a provider from performing writes.
- **Deploy-time-only registration:** the current provider uses application-startup registration, but the registry API does not itself prevent later runtime registration.
- **Versioned identifiers:** names such as `read_artifact_v1` follow the versioned naming convention, but the registry does not syntactically enforce that identifier format.

ADR 012 therefore remains **Proposed**; implementation of the core framework does not by itself promote the architectural decision to a stable product-adoption status.

### 5.5 Platform Shell runtime paths — Capability Bus consumer status

Inspection of the current Platform Shell runtime paths preserves a composition boundary rather than introducing capability execution:

```text
Personal Home
  Platform composition
        │
        └── DocumentService domain-owned summaries
            authorization/query policy remains in Documents

Launcher
  PlatformRegistry metadata
        │
        └── navigation/discovery only

Workspace
  PlatformRegistry + URL resolution
        │
        └── composition context only
            no app execution or domain-data access
```

`personal_home` directly composes `DocumentService.personal_home_recent_documents()` and `personal_home_recently_viewed()`. That dependency is currently legitimate because query and authorization policy remain domain-owned. `app_launcher` operates on registry metadata for navigation. `workspace_index` and `workspace_app` provide application entry points and URL resolution without embedding or executing the application.

**No production Capability Bus consumer is evidenced in the inspected Platform Shell runtime paths.** This is consistent with the current responsibility split: Platform Shell provides composition and navigation context without taking ownership of domain policy.

### 5.6 Consumer-driven capability adoption

Executable capabilities should be introduced in response to a concrete cross-domain contract need, not merely to increase adoption of the Capability Bus. No provider or consumer should be added solely to demonstrate use of the framework.

Direct domain-service composition remains valid where the dependency is explicit, policy remains domain-owned, and no stable cross-domain execution contract is required. A future Workspace need for a bounded domain summary is an illustrative example of the kind of pressure that could justify a capability contract; it is not a roadmap commitment.

Until such a consumer need exists, the Bus remains implemented infrastructure with a registered PoC provider and tested contracts, without being artificially inserted into product data flows.

---

## 6. Dependency Summary

| Concern | Verified direct dependencies / inputs at this snapshot |
|---|---|
| Evidence relationship | `Claim`, `Evidence`, `EvidenceRelation`; user attribution on relevant records |
| Evidence state projection | `Claim` + active `EvidenceRelation` rows |
| Verification request | `Claim`, `VerificationMethod`, `User`, restricted GFK to `Product` / `LibraryItem` |
| Verification evidence | `VerificationResult` + `EvidenceRelation` |
| Verification activity reputation | `VerificationResult`, `VerificationRequest`, `UserIdentity`, `ContextualReputation`, `ContextualReputationEvent` |
| Quality signal eligibility | `QualitySignal`, `VerificationResult`, request/method consistency, optional `EvidenceRelation` or provenance reference |
| Scoring service | `QualitySignal`, `ScoringPolicy`, `ContextualReputation`, `ContextualReputationEvent` |
| Unified Search | `Article`, `Product`, `LibraryItem`, `AudioItem`, `MediaAsset` |
| Entitlement service | `Entitlement`, legacy `User` / `Product`, registry resolution for canonical `Identity` / `Artifact` |

The table describes verified dependencies in the inspected paths. It should not be read as an exhaustive inventory of every model-level dependency in each Django app.

---

## 7. Component Status at the Snapshot

| Component | Status | Notes |
|---|---|---|
| Evidence core relationship and projection | Implemented | Claim/Evidence relation model plus derived claim-level EvidenceState |
| Verification models | Implemented | Request/result/evidence-link model set; artifact target restricted to Product/LibraryItem |
| Verification public API | Implemented, bounded surface | Product and LibraryItem summary endpoints |
| Verification activity recording | Implemented | Activity/sample tracking without automatic score change |
| Quality Signal eligibility v1 | Implemented | Versioned eligibility decision persisted on the signal |
| Contextual scoring | Implemented | Explicit versioned policy application with idempotency/rebuild guardrails |
| Reputation data model | Transitional | Legacy Reputation and ContextualReputation coexist |
| Unified Search service | Implemented | Five adapters; retrieval-only in inspected service |
| Search API strategy routing | Implemented | Bounded, window-count, and supported narrow-CTE paths |
| Home discovery | Implemented | Uses `collect()` plus view-level pagination; no Trust enrichment in `home()` |
| Entitlement migration path | Transitional / Implemented | Legacy authorization key retained while canonical pair is validated/backfilled |

---

## 8. Architectural Invariants Captured by the Code

| Principle | Observed boundary |
|---|---|
| **Verification ≠ Truth** | Submission activity is recorded without automatically changing reputation score. |
| **Quality Signal ≠ Score** | Eligibility is evaluated and persisted before any scoring policy is applied. |
| **Contextual scoring, not universal trust** | Score application is domain/method/policy-specific and versioned. |
| **Search ≠ Verification** | Unified retrieval does not import or rank by Trust subsystems in the inspected service. |
| **Identity ≠ inferred string metadata** | Canonical identity resolution uses registry bindings; services do not infer Identity from fields such as author text. |
| **Entitlement ≠ Trust status** | Access validation checks entitlement/canonical binding consistency, not Evidence or Verification state. |
| **Domain ownership remains local** | Search adapters read domain-owned models rather than moving canonical domain state into Search. |

---

## 9. Snapshot Notes

This document describes repository state at:

```text
ee53dc77c0878a89b92a4c4f5ba401252f5e78d2
```

Later code changes may invalidate individual implementation details. Update this document only after re-validating claims against the relevant repository state.
