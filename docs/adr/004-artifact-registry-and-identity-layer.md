# ADR 004: Artifact Registry and Identity Layer

**Status:** Proposed  
**Date:** 2026-09-06  
**Author:** VORNEQ Core Team

---

## 1. Context

ADR 001 established **Artifact** and **Identity** as two of VORNEQ's core architectural concepts. ADR 002 and ADR 003 then implemented and refined Verification, Evidence, Quality Signals, and Contextual Reputation without prematurely introducing generalized Artifact or Identity models.

That delay was intentional. The platform now has enough concrete behavior to define the next boundary from observed needs rather than speculation.

Today:

- Marketplace `Product` is a concrete digital asset with a real `seller` relation to `AUTH_USER_MODEL`.
- `LibraryItem` is another concrete content type, but its `author` is currently a plain string rather than a canonical identity relation.
- Verification uses a temporary generic artifact bridge to address Product and LibraryItem.
- Evidence remains canonical in `apps.evidence`.
- Contextual Reputation is associated with Django users and verification methods.
- Future verticals need to support organizations, AI agents, datasets, reports, agent outputs, attestations, and other digital artifacts.

The current system therefore has two structural gaps:

1. there is no stable, cross-vertical identifier for an artifact independent of its vertical model and database primary key;
2. there is no canonical identity layer that can represent humans, organizations, and future AI agents without forcing every trust primitive to depend directly on Django User.

The solution must preserve the existing Product, Library, Verification, Evidence, Entitlement, and Reputation behavior while creating a migration path toward reusable trust infrastructure.

---

## 2. Decision

VORNEQ will introduce **Artifact Registry** and **Identity Registry** as Core primitives using an incremental registry-and-binding architecture.

The registries do **not** replace existing vertical models or Django authentication.

The governing rule is:

> **Core registries provide stable identity and trust references; vertical models remain the source of domain-specific content and behavior.**

### 2.1 Artifact Registry

An `Artifact` is the canonical VORNEQ identity of a digital object that can participate in trust workflows.

It is not a universal content table. Product-specific price, Library-specific text, files, publication rules, and future Agent-specific execution data remain in their vertical models.

The registry should provide only stable cross-vertical properties such as:

- a non-sequential public identifier, preferably UUID;
- artifact kind/classification;
- lifecycle status where needed by Core;
- timestamps;
- registry metadata limited to cross-vertical concerns.

A separate binding maps an Artifact to its current vertical object.

Conceptually:

```text
Artifact
  id / public_id / kind / timestamps
        |
        v
ArtifactBinding
  content_type + object_id
        |
        +--> Product
        +--> LibraryItem
        +--> future AgentOutput
        +--> future Dataset / Attestation / other vertical types
```

`ArtifactBinding` is a transitional polymorphic bridge. The canonical identifier is the `Artifact`, not the GenericForeignKey target.

The binding must enforce:

- one canonical Artifact per bound vertical object;
- one active primary vertical binding per Artifact in V1;
- an allowlist of supported model types through service-level validation;
- no implicit creation through model signals.

Artifact registration must occur through explicit services so migration, validation, provenance, and audit behavior remain visible.

### 2.2 Identity Registry

An `Identity` is the canonical VORNEQ identity of an actor that can create, verify, transact, attest, or receive rights.

Identity types are expected to include:

- human;
- organization;
- AI agent;
- system/service identity where operationally required.

The Identity registry does **not** replace `AUTH_USER_MODEL`. Django User remains responsible for authentication, login, password/account lifecycle, and current permission integration.

Instead, a typed binding connects a human Identity to a Django user:

```text
Identity(kind=human)
        |
        v
UserIdentity
        |
        v
AUTH_USER_MODEL
```

Future organization and agent bindings should be explicit typed relations rather than forcing every actor type into Django User or a single opaque GenericForeignKey.

This preserves referential integrity and allows different identity types to have different lifecycle and authorization semantics.

### 2.3 Artifact-to-Identity roles

VORNEQ must not collapse `seller`, `author`, `creator`, `publisher`, `owner`, and `verifier` into one ambiguous field.

Cross-vertical participation will be represented through an explicit role relation between Artifact and Identity, conceptually:

```text
ArtifactIdentityRole
- artifact
- identity
- role
- valid_from / valid_until (optional)
- provenance / metadata where appropriate
```

Initial roles may include creator, author, seller, publisher, owner, or contributor. Role vocabulary must remain versionable and should not imply legal ownership unless the source system provides evidence for that claim.

Existing vertical fields remain authoritative during migration:

- `Product.seller` remains unchanged;
- `LibraryItem.author` remains unchanged;
- new Core role records are bridges/projections until a later migration explicitly changes vertical ownership.

#### Semantics of `is_primary`

- `is_primary` is a **presentation/selection hint** for UI/API consumers. It does **not** imply ownership, legal authority, verification, trustworthiness, or any canonical status beyond the scope of the role.
- This field is **only meaningful within a specific `role`**. For example, `author` and `seller` are separate roles; `is_primary` is evaluated independently per role.
- `is_primary` must **not** be interpreted as a single authoritative actor or primary representative at the Artifact level. An Artifact may have multiple primary roles (e.g., a primary author and a primary seller).
- `is_primary` should be interpreted **together with `valid_from`/`valid_until`**. The temporal boundaries model the history of roles; `is_primary` is only a hint associated with that interval.
- In **V1**, `is_primary` **has no database-level uniqueness guarantee**. Multiple identities for the same `(artifact, role)` may have `is_primary=True`. This is intentional to:
  - Remain compatible with `valid_from`/`valid_until` and support role history (e.g., primary changes over time) without artificial constraints.
  - Avoid enforcing a business rule that may conflict with real-world requirements (e.g., multiple co-authors considered primary).
- Any workflow or service that requires **exactly one active actor** for a given `(artifact, role)` must enforce that invariant in its own policy or service logic. **It must not be locked at the database level.**

**Note:** This ADR does **not** introduce any database constraint on `is_primary` in V1. Any future requirement for hard cardinality (e.g., exactly one primary per `(artifact, role)`) must be handled as a separate architectural change, with clear temporal semantics and overlap management.

### 2.4 Identity is not reputation

Identity answers **who or what is participating**.

Reputation answers **what auditable history exists for that identity in a defined context**.

The Identity model must not contain a global trust score or universal verified flag. Contextual Reputation remains separate and continues to require domain, method, policy, and evidence context.

### 2.5 Artifact is not evidence

Artifact answers **what digital object is being referenced**.

Evidence answers **what material supports, contradicts, contextualizes, or otherwise relates to a claim**.

The Artifact Registry does not absorb `Claim`, `Evidence`, `EvidenceRelation`, `Provenance`, or review history from `apps.evidence`.

The Evidence Kernel remains canonical.

---

## 3. Why a Registry Instead of Renaming Existing Models

Renaming `Product` or `LibraryItem` to `Artifact` would conflate two responsibilities:

- vertical business/domain behavior;
- cross-vertical trust identity.

Product contains marketplace-specific fields such as seller, price, moderation state, digital delivery, and publication behavior. LibraryItem contains knowledge-specific content, localization, author text, and PDF behavior. Future AgentOutput will have different requirements again.

A registry preserves these domain models while giving trust services a stable reference that no longer depends on the vertical object's primary key or URL scheme.

This approach also permits gradual migration of Verification and Entitlement instead of requiring a high-risk rewrite.

---

## 4. Public Identifiers

Artifact and Identity must use non-sequential stable public identifiers.

V1 should use UUID-based identifiers unless a stronger requirement emerges.

Public identifiers must:

- remain stable if a vertical object's slug or title changes;
- not reveal database row counts;
- be safe to expose in URLs and external APIs;
- remain independent of locale;
- survive future vertical migrations where practical.

Internal integer primary keys may still be used by Django for database efficiency, but external trust references should use the stable public identifier.

---

## 5. Migration Strategy

Migration is incremental and reversible until each bridge is proven.

### Stage A — Foundation

Introduce Core registry models and explicit services only:

- `Artifact`;
- `ArtifactBinding`;
- `Identity`;
- `UserIdentity`;
- `ArtifactIdentityRole`.

No existing Product, Library, Verification, Entitlement, or Reputation field is removed.

### Stage B — Register existing objects

Backfill registry entries for supported existing data:

- each Product receives one Artifact and ArtifactBinding;
- each existing Django User that participates in trust workflows receives a human Identity and UserIdentity;
- Product seller relationships may be mirrored into an ArtifactIdentityRole with an explicit `seller` role.

Backfills must be idempotent and migration-safe.

### Stage C — Library identity bridge

`LibraryItem.author` remains as the historical/display string.

A new optional relation to canonical Identity may be introduced later, for example through an Artifact role rather than replacing the author string immediately.

No automatic identity match may be performed merely because a username/display name equals an author string.

Unresolved authors remain unresolved until explicitly linked.

This is required to avoid false attribution.

### Stage D — Trust-service adoption

After registry data is stable:

- Verification can migrate from its temporary Product/Library GenericForeignKey target to Artifact references;
- public Verification APIs can use Artifact public IDs;
- Contextual Reputation presentation can resolve actor identity through Identity/UserIdentity;
- Entitlement may later migrate from `user + product` to an Identity/Artifact-aware entitlement model through a separate ADR and migration plan.

These migrations should happen in separate PRs with dual-read or compatibility adapters where necessary.

### Stage E — Future actor types

Organizations and AI agents may receive typed identity bindings once concrete models exist.

The existence of `Identity(kind=agent)` must not by itself imply that an agent is autonomous, safe, verified, or authorized. Those properties require separate verification, entitlement, policy, and reputation records.

---

## 6. Ownership and Service Boundaries

`apps/core` owns:

- Artifact registry identity;
- Identity registry identity;
- typed bindings;
- cross-vertical Artifact/Identity role relations;
- registration and resolution services.

Vertical applications own:

- vertical data;
- vertical lifecycle rules;
- presentation and product behavior;
- domain-specific authorization beyond shared Core primitives.

`apps.evidence` continues to own:

- Claim;
- Evidence;
- EvidenceRelation;
- Provenance;
- evidence review/history.

`apps.verification` continues to own Verification orchestration.

Core must not silently create registry records through Django `post_save` signals. Explicit service calls are preferred so registration failures are observable and testable.

---

## 7. Referential Integrity and Generic Relations

The Artifact Registry intentionally limits use of generic relations to the **binding edge**, not the trust primitives themselves.

This is a compromise:

- heterogeneous vertical objects require a bridge during migration;
- a GenericForeignKey at the binding edge provides flexibility;
- the Artifact row supplies the stable canonical key used by future trust services.

Core services must validate allowed ContentTypes and object existence.

Future mature verticals may replace generic bindings with typed one-to-one bindings if operational evidence shows that stronger database-level referential integrity is worth the additional schema complexity.

Identity bindings should prefer typed relations from the beginning because actor lifecycle and authorization semantics differ substantially between User, Organization, and Agent.

---

## 8. Deletion and Historical Integrity

Trust infrastructure must preserve historical references wherever legally and operationally appropriate.

Deletion behavior should therefore distinguish between:

- deleting a vertical object;
- deactivating a registry identity;
- erasing personal data when required;
- preserving non-personal audit references.

V1 registry models should prefer status/deactivation semantics over cascading deletion of trust history.

A deleted Product or deactivated User must not silently erase Verification, Quality Signal, Reputation event, or provenance history that is required for auditability.

Exact retention and privacy behavior requires separate policy/legal review and is not fully specified by this ADR.

---

## 9. Security and Privacy Principles

The registry increases the ability to connect data across verticals, which creates privacy risk if handled carelessly.

Therefore:

1. Identity public IDs do not imply that all identity attributes are public.
2. User email, authentication state, permissions, private profile fields, and private Evidence are never exposed merely because an Identity exists.
3. Artifact registration does not make an Artifact publicly discoverable.
4. Public visibility remains a vertical/policy decision.
5. Identity links must not be inferred from untrusted display strings.
6. Organization or Agent identities must not inherit human-user authorization automatically.
7. Registry APIs must expose only explicit public-safe representations.

---

## 10. Consequences

### Positive

- stable cross-vertical references for trust workflows;
- migration path away from temporary GenericForeignKey usage in Verification;
- support for future human, organization, and AI-agent actors;
- no immediate rewrite of Product or Library;
- Library authors can later be linked without destructive replacement of historical author text;
- contextual Reputation can eventually attach to canonical identities without becoming a global score;
- external APIs can use stable public IDs independent of internal vertical schemas.

### Costs and risks

- additional registry/binding tables and migration logic;
- temporary duplication between vertical relationships and Core role projections;
- explicit synchronization is required during migration;
- GenericForeignKey remains present at the Artifact binding edge in V1;
- Identity introduces privacy and lifecycle responsibilities that require careful policy design;
- dual-read compatibility periods may increase implementation complexity.

---

## 11. Non-Goals

ADR 004 does not:

- replace Django authentication;
- create an AI Agent runtime or sandbox;
- migrate Entitlement immediately;
- replace Product or LibraryItem;
- move Evidence into Core;
- define a global trust score;
- automatically convert Library author strings into identities;
- define legal ownership of artifacts;
- make all registered artifacts or identities public;
- define organization membership/authorization;
- implement cross-platform decentralized identifiers or blockchain identity.

Those concerns may be addressed by later ADRs when concrete requirements exist.

---

## 12. Proposed Implementation Sequence

After this ADR is accepted, Phase 3 should proceed in small PRs:

| PR | Scope |
| --- | --- |
| **Foundation PR** | Add Artifact, ArtifactBinding, Identity, UserIdentity, ArtifactIdentityRole + migrations/admin/tests |
| **Registration PR** | Explicit registration/resolution services + idempotent Product/User backfill |
| **Marketplace bridge PR** | Register Product artifacts and mirror seller role without changing existing seller behavior |
| **Library bridge PR** | Add explicit, nullable author/creator Identity linkage workflow without string-based inference |
| **Verification migration PR** | Move Verification artifact targeting toward Artifact IDs with compatibility for existing records |
| **Public API PR** | Public-safe Artifact/Identity lookup contracts using stable UUIDs |

Entitlement migration should remain a separate architectural decision because access rights have stronger security and payment implications than registry identity.

---

## 13. Decision Rules

Future Phase 3 work must follow these rules:

1. **Registry is identity, not content storage.**
2. **Django User remains authentication; Identity is the trust actor abstraction.**
3. **Do not infer Identity from names or strings.**
4. **Use explicit registration services, not hidden synchronization signals.**
5. **Preserve existing vertical fields until migration is proven.**
6. **Artifact/Identity registration does not imply public visibility or trustworthiness.**
7. **Roles must remain explicit and scoped; seller, author, creator, owner, and verifier are not synonyms.**
8. **Evidence and Verification retain their existing ownership boundaries.**
9. **Public APIs use stable public IDs and disclosure-safe serializers.**
10. **Every migration must preserve auditability and have regression tests.**

---

## 14. Conclusion

Phase 2 proved that VORNEQ can build evidence-backed Verification and Contextual Reputation without claiming ownership of truth.

Phase 3 now creates the stable object and actor references required to extend those trust primitives across Knowledge, Marketplace, future Agents, Attestations, and other verticals.

The architectural decision is:

> **Artifact and Identity become canonical Core registries, while vertical models and Django authentication remain authoritative for their existing domain responsibilities.**

This gives VORNEQ a migration path from application-specific trust features toward reusable trust infrastructure without a destructive rewrite or premature universal data model.
