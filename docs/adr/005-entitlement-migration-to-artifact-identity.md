# ADR 005: Entitlement Migration to Artifact and Identity

**Status:** Proposed  
**Date:** 2026-09-06  
**Owners:** VORNEQ Core Team

## Context

The current Deliver layer authorizes access with `Entitlement(user, product)`. The protected Marketplace download endpoint calls `has_valid_entitlement(user, product)` before serving a digital file. This behavior is security-sensitive and must remain available throughout migration.

ADR 004 introduced canonical `Artifact` and `Identity` registries plus explicit bindings from `Product`/`LibraryItem` and Django `User`. The next step is to evolve Entitlement toward those canonical references without breaking existing authorization behavior or manufacturing registry data.

The migration must preserve these principles:

- authorization must fail closed;
- no Artifact or Identity may be inferred from names, strings, or heuristics;
- registry bindings must already exist before a legacy entitlement can be mapped;
- old and new references must never silently disagree;
- rollback must be possible until the legacy path is deliberately retired.

## Decision

Entitlement will migrate from `(User, Product)` to `(Identity, Artifact)` in staged, reversible steps.

### 1. Add nullable canonical references

Add nullable `identity` and `artifact` foreign keys to `Entitlement` while keeping `user` and `product` unchanged.

During this stage, legacy rows remain valid and existing delivery behavior remains unchanged.

### 2. Explicit dual-write

Entitlement creation and grant services will continue accepting the legacy business inputs used by current callers, but when both registry bindings already exist they will also populate `identity` and `artifact`.

Dual-write MUST NOT create missing registry records. A missing `UserIdentity` or `ArtifactBinding` is a registry-readiness problem, not permission to infer or create trust relationships inside the entitlement service.

### 3. Fail-closed consistency rules

When an Entitlement contains both legacy and canonical references, they must describe the same subject and object:

- `identity` must equal the Identity explicitly bound to `user`;
- `artifact` must equal the Artifact explicitly bound to `product`.

If both representations exist and disagree, authorization MUST fail closed and surface an auditable inconsistency. The system must not silently prefer one representation.

### 4. Backfill existing rows

A dedicated idempotent management command will backfill nullable canonical fields only when both explicit registry bindings already exist.

For each legacy Entitlement:

1. resolve `user -> UserIdentity -> Identity`;
2. resolve `product -> ArtifactBinding -> Artifact`;
3. populate only missing canonical fields when both resolutions succeed;
4. detect and report conflicting existing canonical values;
5. leave unresolved rows unchanged.

The command will support `--dry-run` and emit counts for mapped, already-mapped, unresolved-user, unresolved-product, and conflicting rows.

The backfill MUST NOT create `Identity`, `UserIdentity`, `Artifact`, or `ArtifactBinding` records.

### 5. Dual-read authorization

After canonical fields and backfill tooling exist, the Deliver layer will use a compatibility resolver with the following semantics:

- if both canonical references exist and are consistent, authorize using the canonical pair;
- if canonical references are incomplete, fall back to the legacy pair during the migration window;
- if canonical and legacy references conflict, deny access;
- entitlement validity (`is_active`, expiry) remains unchanged.

This preserves availability for rows not yet migrated while preventing privilege expansion from inconsistent mappings.

### 6. Validation period

Before removing legacy fields, production/staging telemetry or audit reporting must show:

- zero conflicting Entitlements;
- zero expected-download regressions caused by canonical resolution;
- all active Entitlements intended for migration have canonical references;
- grant/revoke/read paths behave equivalently under legacy and canonical resolution.

No fixed calendar duration is mandated by this ADR; removal depends on demonstrated parity, not elapsed time alone.

### 7. Legacy-field retirement

Removing `user` and `product` is a separate, explicitly reviewed migration after the validation criteria above are met.

The removal PR must also update all call sites, tests, admin, indexes, uniqueness constraints, and delivery authorization to use only `Identity` and `Artifact`.

## Data integrity and constraints

During the compatibility phase:

- legacy uniqueness remains enforced for current behavior;
- canonical uniqueness may be added only when nullable-field semantics and existing data are proven safe;
- model/service validation must prevent mismatched dual references from being newly written;
- bulk operations that bypass model validation must be handled through vetted services or dedicated migrations.

A later PR may introduce a canonical uniqueness constraint such as one effective Entitlement per `(identity, artifact)` once the backfill is complete and conflicts have been audited.

## Service boundaries

The Entitlement service may resolve existing registry bindings, but it does not own registry creation. Registry creation remains in the registry services defined by ADR 004 and PR #64.

Likewise, the Deliver layer consumes entitlement authorization; it does not repair registry or entitlement data during a download request.

## Security behavior

Migration must not weaken the existing protected-delivery contract:

- unauthenticated requests remain denied by authentication controls;
- missing, inactive, or expired Entitlements remain denied;
- inconsistent dual representations are denied;
- missing files remain non-disclosing failures;
- direct storage URLs remain outside the public authorization path.

## Rollback

Until legacy fields are removed, rollback consists of disabling canonical-read preference and returning to the legacy `user + product` authorization path. Canonical fields may remain populated because they are additive and nullable.

Backfill writes are deterministic from existing explicit Registry bindings; unresolved rows are untouched. Conflicts are reported rather than overwritten.

## Implementation sequence

### PR #66 — Entitlement canonical fields foundation

- add nullable `identity` and `artifact` fields;
- add validation for dual-reference consistency where possible;
- update grant/revoke services for safe dual-write when bindings exist;
- no Deliver read-path switch yet;
- no destructive migration.

### PR #67 — Dual-read Deliver authorization

- add compatibility authorization resolver;
- prefer complete, consistent canonical references;
- legacy fallback for incomplete migration rows;
- fail closed on conflicts;
- add security regression tests.

### PR #68 — Auditable Entitlement backfill

- idempotent management command;
- `--dry-run`;
- no registry creation or inference;
- explicit unresolved/conflict reporting.

### Later retirement PR

Legacy-field removal is intentionally not pre-committed to a PR number. It occurs only after validation evidence demonstrates parity and complete migration readiness.

## Consequences

### Positive

- Deliver authorization becomes independent of Marketplace-specific `Product` and Django-auth-specific `User` references.
- Future Artifact types and non-user Identities can reuse the same entitlement primitive.
- Migration is reversible and auditable.
- Registry ownership boundaries remain intact.
- Conflicts cannot silently grant access.

### Costs and risks

- temporary model and service complexity from dual representations;
- additional consistency tests and operational reporting;
- legacy fields must remain longer than a simple one-shot migration;
- careless bulk writes could bypass compatibility validation and therefore require discipline.

## Non-goals

This ADR does not:

- migrate payment processing;
- create Entitlements for LibraryItems automatically;
- infer Identity from `LibraryItem.author` or other strings;
- create registry records during entitlement backfill;
- define organization/agent authentication;
- remove legacy fields immediately;
- change Evidence, Verification, Reputation, or QualitySignal semantics.

## Decision summary

VORNEQ will migrate Entitlement through an additive, dual-representation compatibility period. Canonical `Identity + Artifact` references become authoritative only when explicit bindings exist and agree with legacy `User + Product` references. Any disagreement fails closed. Backfill is auditable and non-creative, and legacy fields are removed only after demonstrated behavioral parity.