# ADR-016: Phase 2 Migration Rollback Policy

**Status:** Proposed (frozen policy; implementation deferred)  
**Date:** 2026-09-10

## Context

ADR-013 Phase 2 is expected to introduce `core.0010_identityhandle` through PR A. The proposed PR B lifecycle adapter and PR C backfill command are migration-free but depend on the schema introduced by PR A.

This ADR defines migration rollback policy for failures around schema application and subsequent rollout. It defines policy rather than migration implementation.

### Boundary with ADR-013 D3.1

Transaction ownership for provisioning remains deferred under ADR-013 D3.1. This ADR does not select Model A or Model B. Migration/schema rollback policy and request-lifecycle transaction ownership are independent decisions.

## Decision Drivers

1. Data safety.
2. Operational clarity.
3. Failure isolation.
4. Explicit rollback ordering.
5. Independence from ADR-013 D3.1.
6. Separation of global migration prerequisites from change-specific blockers.

## Decision

### D1. Reversibility is two-dimensional and state-aware

Every migration MUST be evaluated independently for schema reversibility and operational/data reversibility.

#### Schema reversibility

- **R-Schema:** reverse DDL is safe for the intended rollback state, such as dropping a newly introduced table or index when permitted by the data classification.
- **F-Schema:** reverse requires unsafe or lossy DDL.
- **M-Schema:** reverse requires an explicit human decision because safety cannot be established generically.

#### Operational/data reversibility

- **R-Data:** reverse is safe in the relevant states and does not destroy, orphan, or semantically invalidate production-consumed data.
- **R-Data-Cond:** reverse is safe only while a documented condition remains true. This classification is state-dependent and MUST be re-evaluated in the change window.
- **F-Data:** reverse is prohibited because it would destroy, orphan, or semantically invalidate relevant data.
- **M-Data:** reverse requires a human decision based on the actual state.

`R-Data-Cond` is not a permanent classification. The initial classification is documented before execution and MUST be re-evaluated at apply/rollback decision time, especially after provisioning or backfill begins.

For the proposed Phase 2 migration, the initial classification is:

| Migration | Schema | Initial data classification | Apply-time classification |
| --- | --- | --- | --- |
| `core.0010_identityhandle` (PR A) | R-Schema | R-Data-Cond | TBD; MUST be re-evaluated |

The frozen rule is that a single R/F/M label at schema level is insufficient. Both dimensions and the current state MUST be considered.

### D2. Rollback ordering

The canonical deployment rollback sequence is:

1. Stop incoming traffic using maintenance mode or service suspension.
2. Freeze writes, including backfill and signup provisioning that depend on the new behavior.
3. Roll back the service layer to code compatible with the target schema state.
4. Reverse the schema only when schema classification is R-Schema and operational/data conditions permit it.
5. Perform data restoration or reconciliation only with explicit approval.
6. Resume traffic only after code and schema are mutually compatible.
7. Verify deployment/database health and run smoke checks.

Code rollback before schema rollback is permitted only when the old code is compatible with the currently deployed schema. If it is not, maintenance mode and frozen writes MUST remain in effect until code and schema are aligned.

Data restoration/reconciliation requires explicit approval and a plan for preserving newer valid writes. Restoring a backup is disaster-recovery remediation, not the default inverse of an F-Data migration. If valid data was created after the backup, preservation of those writes MUST be defined before restore.

### D3. Partial failure behavior

#### A. Pre-deploy failure

If migration execution never began, no database rollback is required. The deployment stops and the plan/CI failure is investigated before another attempt.

#### B. Atomic failure

If the migration is atomic and the database backend and migration operations support transactional rollback for the executed DDL/data operations, failure is expected to restore the database to its pre-migration transactional state.

This behavior MUST NOT be assumed when the backend or individual operations do not provide the required transactional semantics. In that case, state reconciliation is mandatory.

This policy intentionally does not depend on a hidden assumption that all supported databases provide PostgreSQL-equivalent transactional DDL behavior.

#### C. Non-atomic partial failure

No reverse command may be executed blindly after a non-atomic partial failure. A single migration can itself leave partially applied DDL or data changes.

Before remediation, operators MUST:

1. compare actual schema/data state with the `django_migrations` recorder;
2. identify which DDL/data operations actually completed; and
3. explicitly select forward-fix, manual state alignment, or reverse only after reverse safety is established.

`migrate <app> <last-good-state>` by itself is not considered sufficient reconciliation evidence.

#### D. Post-deploy failure

When schema application succeeds but the service is unstable, remediation is selected per case. Service-layer failures should normally prefer compatible code rollback or forward-fix; data-invariant failures require explicit investigation; schema failures may use reverse only when D1 and D4 permit it.

Partial non-atomic failure requires manual state reconciliation before any rollback action.

### D4. Forward-fix versus reverse migration

Forward-fix is the default remediation strategy.

Reverse migration MAY be selected only when all of the following are established:

1. schema classification is R-Schema;
2. operational classification is R-Data, or R-Data-Cond with its documented condition currently satisfied;
3. target code and schema states are compatible;
4. reverse will not cause data loss, orphaning, or semantic invalidation; and
5. reverse is explicitly approved.

If reverse would destroy, orphan, or semantically invalidate data produced after deployment, reverse is prohibited. Forward-fix or a preservation/export-first procedure is required.

F-Schema, M-Schema, F-Data, and M-Data states do not qualify for routine reverse. They require forward-fix, preservation/reconciliation, or explicit human decision as applicable.

### D5. Backup and restore prerequisites

Before a migration change window, the following prerequisites MUST be satisfied:

| # | Prerequisite | Freshness/scope |
| --- | --- | --- |
| 1 | Production database backup | Less than 24 hours old, per migration window |
| 2 | Successful restore rehearsal | Within an approved freshness window, initially to be resolved as 7 or 30 days |
| 3 | Isolated DR target | Available on demand |
| 4 | Documented and approved rollback runbook | Must exist before migration execution |
| 5 | Relevant monitoring | Continuous |
| 6 | Announced change window | Per change |
| 7 | On-call awareness | Per change |

A high-risk migration MAY require a rehearsal specific to that change by explicit operational decision.

The fresh backup requirement and restore-rehearsal freshness are deliberately separate. The policy does not require restoring every less-than-24-hour backup before every migration.

### D6. Stop/go criteria

#### GO

Migration execution is permitted only when:

- all D5 prerequisites are satisfied;
- `migrate --plan` shows exactly the migration set expected for the change window and no unexpected migrations;
- a documented data preflight, using a command/tool to be selected during implementation, reports SAFE;
- the migration graph has been verified;
- ADR-013 D3.1 remains independently governed and no transaction-ownership decision is inferred from this policy;
- applicable change-specific blockers are cleared; and
- every R-Data-Cond classification is re-evaluated for the current state.

#### NO-GO

Execution is prohibited when any D5 prerequisite is missing, data preflight is UNSAFE, an M-Schema/M-Data condition lacks the required explicit decision, a change-specific blocker remains active, or an approved rollback runbook is absent.

#### STOP

Execution MUST stop and escalate when:

- a migration exceeds its pre-declared per-migration execution budget;
- lock contention or deadlock is detected;
- a deployment/database health probe that remains meaningful during maintenance reaches an unexpected state;
- a database-level error is recorded; or
- partial completion is detected.

After STOP, D3 state reconciliation precedes any reverse action.

### D6.1. Execution budget

A per-migration execution budget MUST be established for each change window before apply. This ADR intentionally does not freeze a universal numeric threshold because migration DDL has a different time and risk model from request/email timeouts.

Exceeding the declared budget causes STOP and escalation.

### D7. Global prerequisites versus change-specific blockers

Global migration prerequisites are safety invariants applicable across migration rollouts, such as backup freshness, restore-rehearsal freshness, an approved rollback runbook, and relevant monitoring.

Change-specific blockers apply only to a particular rollout. The current Auth baseline failure is a change-specific blocker for the ADR-013 rollout; Auth PASS is not a global prerequisite for every future database migration.

## Options Considered

### Option A — No formal rollback policy

Rejected because it leaves operational and data-loss decisions undefined until an incident occurs.

### Option B — Automatic rollback on any failure

Rejected because automatic reverse can worsen partial states or destroy data when operational reversibility is not established.

### Option C — Explicit policy, forward-fix default, reverse only with evidence

**Selected.** It prioritizes data safety while retaining reverse migration as an explicitly approved tool when both schema and operational evidence show it is safe.

## Failure Semantics and ADR-013 D3.1

Migration rollback policy and provisioning transaction ownership are independent domains. This ADR does not choose Model A or Model B and does not amend the deferred transaction-ownership decision in ADR-013 D3.1.

## Rollout

### Phase 1 — Policy adoption

This ADR is docs-only and does not itself alter configuration, code, schema, or runtime behavior.

### Phase 2 — Prerequisite verification, runbook creation, and rehearsal

- verify D5 prerequisites with the two-level freshness model;
- create and approve the rollback runbook;
- rehearse the runbook against an isolated DR target as required by the approved freshness/risk policy; and
- if the runbook is delivered in a separate PR, that PR MUST be merged/approved before Phase 3 execution.

### Phase 3 — Migration execution

PR A migration execution proceeds only under D6 GO criteria and after applicable change-specific blockers are cleared. Execution requires explicit authorization under the project's normal change-control process.

## Rollback of This ADR

This ADR is policy documentation rather than implementation. Reverting or superseding the document has no direct migration or data impact.

## Related ADRs

- ADR-013: IdentityHandle — Phase 2 context and D3.1 deferred transaction ownership.
- ADR-014: Email Delivery Strategy — parallel operational context only.

These references do not create binding precedent beyond the dependencies explicitly stated here.

## Consequences

### Positive

- Two-dimensional, state-aware reversibility is explicit.
- Forward-fix is the default and reverse requires evidence.
- Global prerequisites and change-specific blockers are separated.
- Rollout ordering guarantees a runbook before migration execution.
- ADR-013 D3.1 remains independent.
- Health checks used during maintenance have explicit semantics.

### Negative

- Each migration requires classification and re-evaluation where conditional.
- Restore-rehearsal freshness still requires a later operational choice.
- Execution budgets must be set per change.

### Neutral

- Django migration atomicity is used where its backend/operation guarantees actually apply.
- This ADR does not alter the current migration structure.

## Open Questions

1. STOP decision authority: on-call, tech lead, or two-person approval.
2. Which rollback-runbook sections should be automated versus manual.
3. Backup retention requirements for the Phase 2 window.
4. Restore-rehearsal freshness window: 7 versus 30 days.

The numeric execution budget is intentionally resolved per change window rather than as a universal ADR constant.

## Out of Scope

- Transaction ownership under ADR-013 D3.1.
- Provider selection under ADR-014 Phase 2.
- PR A migration implementation details.
- PR C backfill command design.
- Automated rollback in CI/CD.
