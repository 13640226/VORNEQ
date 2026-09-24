# ADR 009: Contextual Reputation Subject Architecture

**Status:** Proposed  
**Date:** 2026-09-06  
**Owners:** VORNEQ Core Team

## Context

VORNEQ already has contextual reputation projections keyed by Django `User`, domain, and verification method. In the current scoring workflow, that `User` is the verifier whose verification activity and eligible quality signals contribute to reputation events.

This is valid for verifier reputation, but it is not sufficient for broader actor contexts such as seller, creator, publisher, author, or owner.

The Artifact/Identity registry introduced a canonical actor model where `Identity` represents a trust actor and `ArtifactIdentityRole` expresses explicit relationships such as `seller`, `creator`, `publisher`, `author`, and `owner`.

A Marketplace Product may therefore have an explicit seller Identity, while the existing `ContextualReputation.user` still represents a Django account and, operationally, a verifier in the current scoring pipeline. Joining these two relationships implicitly would create a semantic error: verifier reputation could be presented as seller reputation merely because the same account is involved.

VORNEQ must preserve the principle:

`Reputation is contextual actor history, not a global trust score and not an inferred role.`

## Decision

VORNEQ will evolve contextual reputation toward a canonical Identity subject with an explicit actor role as part of the reputation context. Existing User-based verifier projections will remain valid during a staged migration and must not be silently reinterpreted as seller, creator, publisher, or other role-specific reputation.

### 1. Canonical reputation subject is Identity

The long-term canonical subject of contextual reputation will be `Identity`, not Django `User`.

Rationale:

- `User` is an authentication/account primitive;
- `Identity` is the canonical trust actor;
- organizations, agents, and service identities may need reputation without being reducible to a Django login;
- one account relationship must not define every actor role in the trust graph.

`UserIdentity` may be used during migration to map existing User-based verifier projections to their canonical Identity where an explicit binding exists.

Missing or ambiguous UserIdentity mappings must fail closed and must not create inferred identities automatically.

### 2. Actor role is part of reputation context

Contextual reputation must distinguish the role in which an Identity accumulated the relevant history.

Initial role vocabulary should reuse or align with explicit registry semantics, including at least:

- `verifier`;
- `seller`;
- `creator`;
- `publisher`;
- `author`;
- `owner` where a product policy requires it.

A reputation projection for `actor_role=verifier` MUST NOT be presented as `actor_role=seller`, even when both roles resolve to the same Identity.

Role transitions or multiple concurrent roles must remain separate contextual projections unless a future policy explicitly defines aggregation. This ADR does not authorize cross-role aggregation.

### 3. Domain remains explicit and policy-defined

`domain` remains an explicit reputation context value.

It MUST NOT be inferred automatically from:

- Product category;
- Artifact kind;
- URL route;
- UI surface;
- arbitrary metadata strings.

A service or scoring policy must supply the domain intentionally according to a versioned policy contract.

This prevents taxonomy changes in Marketplace or Content from silently changing the semantic meaning of reputation history.

### 4. Verification method remains part of context

`verification_method` remains a first-class dimension of contextual reputation.

Reputation associated with one method must not silently mix with another method. If a product experience needs a cross-method summary, that must be a separate, explicitly versioned presentation or scoring policy.

### 5. No global or composite trust score

The migration to Identity does not create a global reputation score.

A contextual reputation projection is scoped by at least:

- subject Identity;
- actor role;
- domain;
- verification method;
- scoring policy/version where scoring events apply;
- time/sample history.

UI and APIs must not collapse these dimensions into a universal "trustworthiness" number.

### 6. Existing User-based verifier reputation remains semantically verifier-scoped

Current `ContextualReputation(user, domain, verification_method)` rows represent the existing verifier-oriented workflow.

During migration they must be interpreted as:

`subject = canonical Identity resolved from user, actor_role = verifier`

only when an explicit `UserIdentity` binding exists.

They MUST NOT be backfilled as seller, creator, publisher, author, or owner merely because the same user owns or manages an Artifact.

### 7. Migration is staged, not a destructive cutover

Implementation should follow a staged migration similar in spirit to prior entitlement migration work:

1. introduce canonical subject/role fields or a replacement projection model without removing the legacy `user` field;
2. dual-write new verifier reputation activity to the canonical representation where Identity resolution is unambiguous;
3. dual-read with explicit parity checks;
4. backfill existing verifier rows using `UserIdentity` only;
5. report unresolved/conflicting mappings;
6. validate parity and policy-version compatibility;
7. deprecate legacy User-based lookup only after operational validation.

No registry objects may be created implicitly during reputation backfill.

### 8. Role-specific reputation requires role-specific evidence/activity policy

Adding `actor_role=seller` to the schema does not by itself create seller reputation.

A future seller reputation workflow must define what events legitimately contribute to seller reputation, for example verified delivery behavior, dispute/adjudication outcomes, verified product claims, or other policy-approved signals.

The existing verifier scoring pipeline MUST NOT be reused as seller scoring merely by changing a foreign key or display label.

The same requirement applies to creator, publisher, author, and other roles.

### 9. ArtifactIdentityRole is a binding source, not a scoring source

`ArtifactIdentityRole` may establish that an Identity is explicitly related to an Artifact in a role such as seller or creator.

That binding answers:

> Which Identity acts in this role for this Artifact?

It does not answer:

> What is this Identity's reputation in that role?

Reputation data must come from a role-specific contextual reputation projection whose activity/scoring policy matches that role.

### 10. Public presentation remains disclosure-safe

Public reputation presentation must continue to use a dedicated disclosure-safe service contract.

A public surface may expose policy-approved fields such as:

- actor role;
- domain;
- verification method;
- sample strength/sample count where approved;
- recency;
- policy version;
- score only where a dedicated presentation decision explicitly permits it.

It must not expose private Evidence, assessors, raw event deltas, provenance internals, or audit records.

Marketplace cards MUST NOT display seller reputation until an explicit seller-role reputation projection exists under this architecture.

## Consequences

### Positive

- Reputation aligns with the canonical Identity registry rather than authentication accounts.
- Verifier, seller, creator, publisher, and author semantics cannot be silently conflated.
- Organizations and non-user actors can participate in future reputation workflows.
- Marketplace presentation can resolve actor identity explicitly without inventing reputation semantics.
- Existing verifier reputation remains usable during migration.

### Costs / Trade-offs

- Migration requires dual-write/dual-read and parity tooling rather than a simple foreign-key replacement.
- Role-specific reputation requires separate event/scoring policy design.
- Some existing rows may be unresolved if no valid UserIdentity exists.
- Public UI for seller reputation must wait until the seller-specific projection and policy are implemented.

## Non-goals

This ADR does not:

- implement a seller reputation score;
- define seller scoring weights or quality signals;
- change Marketplace ranking;
- create a global trust score;
- infer actor roles from ownership strings or account relationships;
- infer domain from Product category or Artifact type;
- delete the existing `ContextualReputation.user` field immediately;
- authorize cross-role or cross-method aggregation;
- change Verification outcomes or Evidence semantics.

## Implementation direction

Recommended follow-up sequence:

1. add canonical Identity + actor-role reputation foundation while preserving legacy User-based verifier fields/behavior;
2. add dual-write for verifier activity with fail-closed Identity resolution;
3. add backfill/parity tooling for existing verifier projections;
4. validate migration operationally before legacy deprecation;
5. design a separate seller reputation activity/scoring policy;
6. only after seller-role projections exist, add Marketplace reputation presentation through a public-safe service contract.

The first implementation PR after this ADR should focus on schema/service migration safety, not Marketplace UI.