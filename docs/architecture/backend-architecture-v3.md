# VORNEQ Backend Architecture Map — v3

**Version:** 3.0  
**Status:** Descriptive snapshot  
**Date:** 2026-09-08  
**Snapshot Reference:** `95f4181e6326b18d2f16d3622b9fc041d82aa4e5`  
**Purpose:** Provide a code-based map of selected VORNEQ backend concerns, their data flows, dependencies, and current implementation boundaries at the referenced snapshot.

---

## 1. Scope

This document focuses on backend concerns that are easy to conflate but are implemented with distinct boundaries:

- **Trust / Assessment:** Evidence, Verification, Quality Signals, and Contextual Reputation.
- **Audit / Accountability:** Structured, append-only accountability records with bounded Verification integration.
- **Public Retrieval / Discovery:** Unified retrieval across public domain content.
- **Identity Registry:** Canonical identity and artifact attribution with gradual subsystem adoption.
- **Entitlement:** Access eligibility during the legacy-to-canonical identity/artifact migration.

This is not an exhaustive map of every VORNEQ backend subsystem. Platform Shell, Documents, Notes, Profiles, Graph, and other areas may have additional implementation details outside this map.

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

Verification lifecycle transitions produce both a transactionally coupled `ReviewRecord` and a post-commit `AuditEvent`. Audit persistence failures are isolated and logged after commit; they do not roll back the Verification business transaction. The detailed accountability boundary is documented in Section 4.

#### Evidence/Verification caveats

Two implementation caveats are worth noting in the current snapshot:

1. **Potential concurrency gap in duplicate active VerificationRequest prevention**  
   The service checks for duplicate active requests using `select_for_update().filter(...).exists()`, but there is no database-level uniqueness constraint covering `(artifact, claim, method)` for active statuses. Because an initial creation may occur when no matching row yet exists to lock, concurrent first-create attempts may race. Duplicate prevention should therefore be understood as a service-level safeguard rather than a database-enforced invariant.

2. **Evidence immutability is model/application-level, not database-enforced**  
   Canonical Evidence fields such as `content`, `content_type`, `digest`, and `observed_at` are protected against mutation through the model's `save()` path. No database constraint, trigger, or equivalent database-level mechanism was observed enforcing that immutability. ORM operations that bypass model `save()` hooks, such as `QuerySet.update()`, as well as lower-level database writes, can therefore bypass this protection. The current guarantee is application/model-level rather than database-enforced.

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

## 4. Audit and Accountability Boundary

VORNEQ has an implemented Audit subsystem under `apps.audit`. Its current production integration is intentionally bounded and should not be interpreted as a generic platform-wide event bus or authoritative state store.

### 4.1 AuditEvent model and append-only contract

`AuditEvent` records structured accountability events with an independent UUID `event_id`, schema version, event name, structured actor and target references, outcome, reason code, optional correlation identifier, bounded metadata, retention class, and timestamp.

The model enforces an append-only contract through the Django ORM:

- updates to an existing `AuditEvent` through `save()` are rejected;
- instance deletion is rejected;
- bulk `QuerySet.update()` and `QuerySet.delete()` are rejected.

These protections are implemented at the model/queryset layer. No database trigger or equivalent database-level immutability mechanism is evidenced in the inspected implementation, so AuditEvent should not be described as database-enforced immutable storage.

### 4.2 Bounded event schemas

`record_audit_event()` accepts only explicitly registered event schemas. At this snapshot the supported event names are:

- `verification.request.created`
- `verification.request.changed`
- `verification.result.recorded`

Each schema constrains the allowed outcome, reason codes, metadata keys, and metadata value types. Actor and target references must use the exact structured `{type, identifier}` shape, and actor type is limited to `user` or `system`.

The service therefore acts as a bounded event recorder rather than an open-ended metadata sink. Extra or missing metadata fields and unknown event names are rejected.

### 4.3 Verification integration and failure isolation

Verification records two different forms of history:

```text
Verification operation
        │
        ├── ReviewRecord
        │     created synchronously
        │     inside business transaction
        │
        └── AuditEvent
              scheduled with transaction.on_commit()
                        │
                        ▼
                 emitted after commit
                        │
              failure logged and isolated
```

`ReviewRecord` creation is transactionally coupled to the Verification lifecycle transition. Audit emission is not. Verification schedules Audit through `transaction.on_commit()`, and Audit persistence failures are caught and logged after the business transaction has committed.

A failed Audit write therefore does not roll back a successful Verification transition. This behavior is explicitly tested.

### 4.4 Authoritative state boundary

`AuditEvent` is an accountability and observability record, not the authoritative state store for Verification.

The authoritative current state remains `VerificationRequest` and `VerificationResult`. `ReviewRecord` provides transactionally coupled transition history. AuditEvent provides an append-only post-commit accountability record whose delivery is best-effort in the current Verification integration.

Because Audit delivery can fail after the business transaction succeeds, downstream correctness, authorization, or lifecycle decisions must not assume that the presence of an AuditEvent is required evidence that a Verification transition occurred.

### 4.5 Current adoption status

| Subsystem / Area | Audit adoption status |
|---|---|
| AuditEvent model | Implemented |
| Structured schema validation | Implemented |
| ORM/model append-only enforcement | Implemented |
| Database-enforced immutability | Not evidenced |
| Verification request lifecycle | Integrated |
| Verification result recording | Integrated |
| Post-commit failure isolation | Implemented and tested |
| Guaranteed Audit delivery | Not provided |
| Identity-native actor | Not adopted; current actor is Django User or system |
| Evidence-specific Audit events | Not present |
| Entitlement Audit events | Not present |
| Reputation / QualitySignal dependency | Not present |
| Generic platform event registry | Not implemented |

Audit should therefore be described as an implemented, bounded accountability subsystem with Verification integration and explicit post-commit failure isolation—not as a universal event ledger or source of truth.

---

## 5. Public Retrieval / Discovery

### 5.1 Unified Search adapters

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

### 5.2 Ordering and bounded candidate retrieval

For paginated search paths, adapters can order and limit candidates in the database using a global timestamp expression plus a textual primary-key tie-breaker. Candidate sets are then merged in Python and sorted by `(published_at, key)` in descending order.

This is an in-process federated retrieval design rather than a separate external search index.

### 5.3 Search execution strategies

`UnifiedSearch.search()` selects among three execution paths:

1. **Bounded fallback** — separate exact counts plus bounded candidates; also used when window functions are unavailable or page input follows the compatibility path.
2. **Window-count path** — bounded candidates with `COUNT(...) OVER()` for an exact adapter total.
3. **Narrow CTE path** — selected when `supports_narrow_cte()` is true.

`apps/search/narrow_window.py` enables the narrow CTE path only when Django reports window-function support and the database vendor is PostgreSQL or SQLite. It builds a narrow inner query containing primary key, total count, global timestamp, and tie-break key, then joins back to the base table for enrichment after limiting.

### 5.4 API caller versus Home caller

The public search API calls `UnifiedSearch.search()`, so it uses the execution-strategy routing above.

The current Home view is different: `config.views.home` calls `UnifiedSearch().collect()`, filters out URL-less cards, and applies Django `Paginator` in the view. Therefore the optimized `search()` strategy routing should not be described as the current Home pagination path.

Within `home()`, no Trust-derived enrichment or Trust-based ranking is applied to discovery results. The same `config/views.py` file also contains a separate authenticated profile view that reads Entitlement and Contextual Reputation; those profile reads are not part of Home discovery.

### 5.5 Unified Search boundary — current status

`UnifiedSearch` remains a public retrieval/composition boundary rather than an authorization or Trust boundary. Domain adapters determine retrieval eligibility through domain-owned publication/state filters such as `is_published`, approved product status, and active media state. The public Search API constrains caller-supplied filters, normalizes result representation, and delegates retrieval to the same adapter layer. No Evidence, Verification, Contextual Reputation, Quality Signal, or Entitlement dependency is present in the inspected Search service or API path.

Production search execution remains read-only and preserves equivalent pagination and ordering contracts across bounded fallback, window-count, and supported narrow-CTE paths. Unexpected database failures are not silently converted into fallback behavior.

Two implementation caveats remain:

- public eligibility is currently expressed through domain-specific model-state filters rather than a shared publication abstraction;
- Search-focused production tests currently live under `apps/core/tests/`, which is a historical ownership/layout coupling rather than a runtime architectural dependency.

---

## 6. Identity Registry and Adoption Boundary

VORNEQ has an implemented canonical Identity registry that is separate from Django authentication. The registry provides stable subject identifiers for trust and cross-domain attribution, while adoption by existing subsystems remains gradual. The transitional boundary is therefore subsystem adoption of Identity, not the existence or status of the Identity registry itself.

```text
Django User
    │ explicit UserIdentity binding
    ▼
Identity

Domain object
    │ explicit ArtifactBinding
    ▼
Artifact

Identity ── explicit ArtifactIdentityRole ── Artifact
```

### 6.1 Identity registry — current status

`Identity` uses an independent UUID primary key and supports human, organization, agent, and system/service identity kinds. `UserIdentity` provides the explicit bridge between Django authentication and a canonical human Identity.

`register_user_identity()` is an explicit, atomic, idempotent registration operation. When no binding exists, it creates a human Identity and binds the supplied saved Django user to it. In contrast, `resolve_identity_for_user()` is resolution-only: it returns the existing bound Identity or `None` and never creates registry state implicitly.

Registry adoption does not infer identity or attribution from ordinary domain data. Artifact registration does not infer roles such as seller from the vertical model. Library author text is not normalized or matched to an Identity. Where canonical attribution is needed, an explicit `ArtifactIdentityRole` must be established; the library author bridge, for example, requires an existing active Identity and never derives one from `LibraryItem.author`.

Identity adoption remains transitional in existing subsystems:

- Entitlement continues to use the legacy `user + product` request key. The canonical `identity + artifact` pair is populated only when both registry bindings exist or when an explicitly supplied pair can be verified against them.
- Contextual Reputation still requires its legacy `user` subject. A pre-existing `UserIdentity` binding may also populate the canonical `identity` field, but the reputation service does not create Identity records.
- Verification continues to use Django User references for request and verifier attribution in the inspected path. Canonical Identity is not a required Verification subject.
- The inspected Evidence path does not require canonical Identity as its record subject.
- Platform Shell continues to operate through Django request/user semantics in the inspected runtime paths.
- The current `read_artifact_v1` Capability Bus PoC does not consume `CapabilityContext.actor` in its authorization decision.

Django `User` therefore remains the dominant runtime authentication principal at this snapshot. Identity is an explicit canonical subject and attribution registry, not yet a system-wide replacement for `request.user` or a universal Capability Bus actor.

### 6.2 Guarantees and caveats

Database constraints enforce important structural guarantees. `UserIdentity.user` and `UserIdentity.identity` are one-to-one relationships, and `ArtifactIdentityRole` is unique for the same artifact, identity, and role tuple.

Other invariants remain model- or service-level rather than database-enforced. `UserIdentity` requires a human Identity through model validation, and `ArtifactIdentityRole` validates that `valid_until` follows `valid_from`. Callers that bypass canonical services and model validation should therefore not be assumed to receive those same guarantees automatically.

Identity resolution is deliberately non-creative. Missing `UserIdentity` state resolves to `None`; Entitlement and Contextual Reputation decide how to handle that transitional state rather than silently manufacturing canonical subjects.

Likewise, legacy domain strings and metadata are not general identity-resolution inputs. Explicit bridges may establish canonical relationships, but the registry does not perform fuzzy or implicit identity inference.

### 6.3 Current adoption state

| Subsystem / Area | Identity adoption status |
|---|---|
| Identity registry | Implemented canonical abstraction |
| `UserIdentity` binding | Implemented; one-to-one structure DB-enforced |
| Registration service | Implemented, explicit, atomic, idempotent |
| Resolution service | Implemented, explicit, non-creative |
| Artifact identity roles | Implemented; explicit attribution |
| Entitlement | Transitional legacy/canonical adoption |
| Contextual Reputation | Transitional dual-subject adoption; `user` remains required |
| Verification | Not Identity-native in the inspected request/result path |
| Evidence | Canonical Identity not required in the inspected path |
| Platform Shell | Identity is not the default runtime principal |
| Capability Bus PoC | Identity/actor is not consumed by current PoC authorization |
| Unified Search | Deliberately independent of Identity for retrieval eligibility and ranking |

The Identity registry should therefore be described as an implemented canonical abstraction with gradual, explicit subsystem adoption—not as a purely transitional model.

---

## 7. Entitlement Boundary

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

### 7.1 Grant semantics

`grant_entitlement()` continues to grant by the legacy `user + product` key. It enriches the same row with `identity + artifact` only when both canonical registry bindings already exist, or when an explicitly supplied canonical pair can be verified against those bindings.

A partial explicit canonical pair is rejected. Explicit canonical references that cannot be verified or that conflict with registry bindings are rejected. Existing incomplete/conflicting canonical state also fails closed.

The service does not create registry Identity or Artifact records.

### 7.2 Authorization semantics

`has_valid_entitlement()` does more than test `is_active` and expiry. It:

- requires an authenticated user;
- resolves the entitlement by the legacy `user + product` key;
- requires `Entitlement.is_valid()`;
- rejects a partial canonical pair;
- permits legacy fallback only while the row has no canonical references;
- when canonical references exist, requires resolvable registry bindings and exact identity/artifact agreement.

No Evidence or Verification check is part of this entitlement validation path.

This makes Entitlement a distinct authorization concern; Trust context does not silently grant access.

### 7.3 Architectural role of Entitlement

Entitlement remains a **transitional access primitive**, not a universal platform permission model. Its public service shape is still centered on the legacy `user + product` key, with canonical `Identity + Artifact` references populated and validated where bindings exist. Canonical inconsistency fails closed rather than silently falling back to legacy authorization.

This boundary must remain distinct from the executable Capability Bus. `has_valid_entitlement()` is appropriate inside a capability provider only when the owning domain explicitly defines entitlement as part of that domain's authorization policy. It must not become the default or universal authorization mechanism for executable capabilities.

### 7.4 Capability Bus v2 — current status

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

### 7.5 Platform Shell runtime paths — Capability Bus consumer status

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

### 7.6 Consumer-driven capability adoption

Executable capabilities should be introduced in response to a concrete cross-domain contract need, not merely to increase adoption of the Capability Bus. No provider or consumer should be added solely to demonstrate use of the framework.

Direct domain-service composition remains valid where the dependency is explicit, policy remains domain-owned, and no stable cross-domain execution contract is required. A future Workspace need for a bounded domain summary is an illustrative example of the kind of pressure that could justify a capability contract; it is not a roadmap commitment.

Until such a consumer need exists, the Bus remains implemented infrastructure with a registered PoC provider and tested contracts, without being artificially inserted into product data flows.

---

## 8. Dependency Summary

| Concern | Verified direct dependencies / inputs at this snapshot |
|---|---|
| Evidence relationship | `Claim`, `Evidence`, `EvidenceRelation`; user attribution on relevant records |
| Evidence state projection | `Claim` + active `EvidenceRelation` rows |
| Verification request | `Claim`, `VerificationMethod`, `User`, restricted GFK to `Product` / `LibraryItem` |
| Verification evidence | `VerificationResult` + `EvidenceRelation` |
| Verification Audit | `VerificationRequest` / `VerificationResult`, `ReviewRecord`, post-commit `AuditEvent`; Django User/system actor references |
| Verification activity reputation | `VerificationResult`, `VerificationRequest`, `UserIdentity`, `ContextualReputation`, `ContextualReputationEvent` |
| Quality signal eligibility | `QualitySignal`, `VerificationResult`, request/method consistency, optional `EvidenceRelation` or provenance reference |
| Scoring service | `QualitySignal`, `ScoringPolicy`, `ContextualReputation`, `ContextualReputationEvent` |
| Unified Search | `Article`, `Product`, `LibraryItem`, `AudioItem`, `MediaAsset` |
| Entitlement service | `Entitlement`, legacy `User` / `Product`, registry resolution for canonical `Identity` / `Artifact` |

The table describes verified dependencies in the inspected paths. It should not be read as an exhaustive inventory of every model-level dependency in each Django app.

---

## 9. Component Status at the Snapshot

| Component | Status | Notes |
|---|---|---|
| Evidence core relationship and projection | Implemented | Claim/Evidence relation model plus derived claim-level EvidenceState |
| Verification models | Implemented | Request/result/evidence-link model set; artifact target restricted to Product/LibraryItem |
| Verification public API | Implemented, bounded surface | Product and LibraryItem summary endpoints |
| Verification Audit integration | Implemented, bounded | ReviewRecord inside transaction; AuditEvent emitted post-commit with isolated failure |
| AuditEvent model | Implemented | Structured, ORM/model append-only accountability record; no DB-enforced immutability evidenced |
| Verification activity recording | Implemented | Activity/sample tracking without automatic score change |
| Quality Signal eligibility v1 | Implemented | Versioned eligibility decision persisted on the signal |
| Contextual scoring | Implemented | Explicit versioned policy application with idempotency/rebuild guardrails |
| Reputation data model | Transitional | Legacy Reputation and ContextualReputation coexist |
| Unified Search service | Implemented | Five adapters; retrieval-only in inspected service |
| Search API strategy routing | Implemented | Bounded, window-count, and supported narrow-CTE paths |
| Home discovery | Implemented | Uses `collect()` plus view-level pagination; no Trust enrichment in `home()` |
| Entitlement migration path | Transitional / Implemented | Legacy authorization key retained while canonical pair is validated/backfilled |

---

## 10. Architectural Invariants Captured by the Code

| Principle | Observed boundary |
|---|---|
| **Verification ≠ Truth** | Submission activity is recorded without automatically changing reputation score. |
| **Audit ≠ authoritative state** | Verification state lives in Verification models; Audit delivery is post-commit and may fail without rolling back business state. |
| **Quality Signal ≠ Score** | Eligibility is evaluated and persisted before any scoring policy is applied. |
| **Contextual scoring, not universal trust** | Score application is domain/method/policy-specific and versioned. |
| **Search ≠ Verification** | Unified retrieval does not import or rank by Trust subsystems in the inspected service. |
| **Identity ≠ inferred string metadata** | Canonical identity resolution uses registry bindings; services do not infer Identity from fields such as author text. |
| **Entitlement ≠ Trust status** | Access validation checks entitlement/canonical binding consistency, not Evidence or Verification state. |
| **Domain ownership remains local** | Search adapters read domain-owned models rather than moving canonical domain state into Search. |

---

## 11. Snapshot Notes

This document describes repository state at:

```text
95f4181e6326b18d2f16d3622b9fc041d82aa4e5
```

Later code changes may invalidate individual implementation details. Update this document only after re-validating claims against the relevant repository state.
