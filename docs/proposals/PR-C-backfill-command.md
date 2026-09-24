# PR C — Backfill Identity Handles Specification v2.1

## Status

Proposal-only · Backfill recovery path for IdentityHandle

**Date:** 2026-09-10  
**Dependency:** ADR-013 §D3.1 (Model A) · PR #251 · PR B Spec v2.1 (PR #252)  
**Type:** Recovery / backfill command specification

This document is a specification only. It does not implement PR C.

## 1. Position Statement

PR C completes the recovery path for the failure semantics frozen in ADR-013 §D3.1 (Model A):

```text
Identity: canonical and durable
Handle:   recoverable provisioning
State:    Identity-without-Handle = valid but incomplete
```

PR C is the backfill command for this state. Eligibility is limited to user-backed Identities; organization, agent, system, and other Identities without a `UserIdentity` binding are not targets.

## 2. Scope

Proposed implementation scope:

- `apps/core/management/commands/backfill_identity_handles.py` — NEW
- `apps/core/tests/test_backfill_identity_handles.py` — NEW

Out of scope:

- changes to `models.py`, `services/handles.py`, or `registry.py`
- changes to `UserIdentity`, `Identity`, or adapters
- migrations
- audit schema
- mandatory metric instrumentation
- lifecycle integration (PR B scope)
- handles for organization/agent/system Identities without a `UserIdentity` binding

## 3. Command Interface

### 3.1 Signature

```bash
python manage.py backfill_identity_handles [options]
```

### 3.2 Arguments

| Argument | Type | Default | Behavior |
| --- | --- | --- | --- |
| `--batch-size` | int | `200` | `1 <= size <= 1000`; argparse-validated |
| `--dry-run` | flag | false | scan only; no writes |
| `--identity-id` | UUID | none | single UUID only in V1; argparse-validated |
| `--quiet` | flag | false | suppress per-batch and per-item output |
| `--verbose` | flag | false | emit per-identity detail |

`--quiet` takes precedence over `--verbose`.

### 3.3 Validation

- `--batch-size` outside the allowed range: `argparse.ArgumentTypeError`; CLI exit status 2.
- invalid `--identity-id`: `argparse.ArgumentTypeError`; CLI exit status 2.
- validation is not reimplemented inside `handle()`.
- implementation MUST NOT manually raise `SystemExit`.

## 4. Target Selection

### 4.1 Eligibility

PR C MUST target only Identities with an existing `UserIdentity` binding and without an `IdentityHandle`.

Illustrative query shape:

```python
has_handle = IdentityHandle.objects.filter(identity=OuterRef("pk"))
has_user = UserIdentity.objects.filter(identity=OuterRef("pk"))

qs = (
    Identity.objects
    .annotate(
        _has_handle=Exists(has_handle),
        _has_user=Exists(has_user),
    )
    .filter(_has_handle=False, _has_user=True)
    .order_by("id")
)
```

This deliberately avoids reliance on a reverse relation name.

Rationale:

- ADR-013 lifecycle provisioning starts from `register_user_identity(user)`.
- PR C is a recovery path for user-backed Identity provisioning.
- An Identity without a `UserIdentity` binding is not made eligible by substituting `identity.display_name`.
- Service-level fallback for an unusable seed is distinct from inventing a PR C seed for an Identity without a user binding.

### 4.2 Batching

Pagination is cursor-like and ordered by `Identity.id`:

- each batch starts after the current `last_id`;
- the cursor always advances;
- only the current batch is held in memory;
- `--batch-size` is bounded at 1000.

The command does not introduce row locking. Race safety remains the allocation service's responsibility.

### 4.3 Seed Contract

PR C passes `UserIdentity.user.username` verbatim as `base_seed`.

PR C MUST NOT itself substitute `identity.display_name`.

Any handling of an empty username is owned by the canonical `reserve_handle_for_identity` service contract and MUST NOT be reimplemented or assumed by PR C.

For a non-empty seed whose normalization becomes empty, for example a non-Latin-only input, ADR-013 requires the deterministic fallback.

Seed values are loaded in bulk per batch rather than per Identity:

```python
usernames_by_identity = dict(
    UserIdentity.objects
    .filter(identity_id__in=batch_ids)
    .values_list("identity_id", "user__username")
)
```

N+1 seed lookup is prohibited.

### 4.4 Per-Identity Processing

Illustrative processing shape:

```python
for identity in batch:
    stats.scanned += 1
    seed = usernames_by_identity[identity.id]
    try:
        reserve_handle_for_identity(identity, base_seed=seed)
        stats.succeeded += 1
    except HandleAllocationError:
        stats.failed += 1
        stats.errors.append((identity.id, "allocation_failed"))
        logger.warning(...)
    except Exception:
        stats.failed += 1
        stats.errors.append((identity.id, "unexpected_failure"))
        logger.exception(...)
```

Each Identity is an independent processing unit. A failure for one Identity MUST NOT roll back successful processing of the rest of the batch.

### 4.5 Dry Run

`--dry-run`:

- scans eligible targets only;
- MUST NOT call `reserve_handle_for_identity`;
- performs no write;
- reports an aggregate count;
- does not dump usernames, seeds, or handles.

## 5. Invariants

1. **I1 — Canonical allocation:** PR C uses only `reserve_handle_for_identity`; it MUST NOT implement parallel allocation logic.
2. **I2 — Idempotency:** repeated execution produces no additional side effect for already provisioned Identities.
3. **I3 — Safe to resume:** successfully provisioned Identities no longer match the target query.
4. **I4 — Failure isolation:** one Identity failure does not roll back successful processing of other Identities.
5. **I5 — Dry-run safety:** dry-run performs no writes and does not invoke the reservation service.
6. **I6 — Seed contract:** PR C passes the `UserIdentity.user.username` value verbatim and does not substitute `identity.display_name`.
7. **I7 — Exit-code semantics:** a valid command invocation exits non-zero iff one or more per-Identity processing failures occurred. Invalid CLI arguments follow Django/argparse parser semantics separately and have process exit status 2.
8. **I8 — Query efficiency:** seed lookup is bulk per batch; N+1 lookup is prohibited.
9. **I9 — Relation independence:** target selection does not rely on a reverse relation name.
10. **I10 — Eligibility:** only user-backed Identities without a handle are eligible.

## 6. Accounting Semantics

The command tracks:

| Counter | Meaning |
| --- | --- |
| `scanned` | eligible Identities iterated during this run |
| `succeeded` | `reserve_handle_for_identity` returned without raising |
| `failed` | reservation raised `HandleAllocationError` or another exception |

The command MUST NOT claim that `succeeded` means "created". The reservation service is idempotent and may return an existing/race-winning handle.

### 6.1 Bounded Error Categories

```python
stats.errors: list[tuple[UUID, str]]
# (identity_id, error_category)
# bounded categories:
#   "allocation_failed"  — HandleAllocationError
#   "unexpected_failure" — any other exception
```

The final stdout summary may include at most the first 10 `(identity_id, error_category)` entries.

Raw exception text MUST NOT be emitted in the summary. `logger.exception(...)` retains the full traceback for unexpected failures in operational logs.

## 7. Observability

Required:

- default per-batch aggregate progress output;
- final `scanned / succeeded / failed` summary on stdout;
- at most 10 bounded error entries in stdout;
- `logger.warning(...)` for `HandleAllocationError`;
- `logger.exception(...)` for unexpected exceptions.

Optional/follow-up:

- metric instrumentation, in ADR-017 context;
- audit events, requiring an appropriate audit schema/policy extension.

## 8. Output Modes

| Mode | Behavior |
| --- | --- |
| default | per-batch aggregate progress plus final summary |
| `--quiet` | final summary only |
| `--verbose` | per-identity detail, including resulting handle value |
| `--dry-run` | aggregate count only; no username/handle list |

Default output MUST remain aggregate and MUST NOT expose username, seed, or handle values per item.

## 9. Exit Codes — CLI Contract

### 9.1 CLI Contract

| Scenario | Process exit | Source |
| --- | ---: | --- |
| success | 0 | Django default |
| nothing to backfill | 0 | Django default |
| one or more per-Identity failures | 1 | `CommandError` after processing |
| invalid CLI arguments | 2 | Django command parser / argparse |

### 9.2 Implementation Rule

Implementation and unit tests MUST NOT manually raise `SystemExit`.

Unit tests may assert Django parser behavior (`CommandError` or the equivalent parser exception). If exact process exit status is retained as an acceptance criterion, it belongs to a CLI/subprocess-level test rather than being inferred from `call_command()` behavior.

## 10. Concurrency Behavior

Two concurrent command runs may select the same Identity. `reserve_handle_for_identity` is the canonical idempotent/race-safe boundary; the command MUST NOT duplicate that logic.

PR C provides only a PostgreSQL concurrency smoke test:

```python
class BackfillConcurrencySmokeTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_runs_do_not_create_duplicate_handles(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL.")
        # two parallel call_command invocations targeting the same identity
        # assert a single IdentityHandle row
```

This is smoke coverage, not a proof of race safety. Full race-safety guarantees belong to PR A and the allocation service.

Duplicate-work warnings are not required; concurrent overlap is expected and the canonical service is idempotent.

## 11. Retry Semantics

- The command is stateless; retry means re-invocation.
- Failed eligible Identities remain eligible for a later run.
- Successfully provisioned Identities no longer match the query.
- This is the operational recovery path for ADR-013 Model A handle-provisioning failures.

## 12. Relationship to ADR-013 §D3.1 — Model A

| Aspect | Relationship |
| --- | --- |
| Trigger | valid but incomplete, user-backed Identity without Handle |
| Mechanism | invoke canonical `reserve_handle_for_identity` |
| Scope | existing user-backed Identities |
| Not in scope | lifecycle integration, new-user provisioning, non-user-backed Identity |
| Frozen basis | ADR-013 §D3.1 Model A and PR B Spec v2.1 |

PR C MUST NOT operate without the canonical `reserve_handle_for_identity` service; it is the only supported allocation entry point for this command.

## 13. Relationship to ADR-016 — Rollback Policy

PR C is migration-free:

| Aspect | Status |
| --- | --- |
| Migration | none |
| Schema change | none |
| Schema rollback | N/A |
| Data rollback | no supported inverse operation is defined for V1 |
| ADR-016 applicability | limited; migration prerequisites are not backfill-run prerequisites |

A successful handle allocation is treated according to ADR-013's V1 immutability contract. Operational recovery SHOULD prefer forward-fix/reconciliation rather than deleting allocated handles.

The previous notion of treating successful backfill as "reversible via delete" is explicitly rejected by this specification.

## 14. Non-Goals

PR C MUST NOT:

1. implement new allocation logic;
2. modify `reserve_handle_for_identity`;
3. modify `register_user_identity`;
4. modify adapters;
5. integrate with lifecycle provisioning;
6. add `post_save(User)`;
7. add a migration;
8. dump username/handle lists in default output;
9. introduce catch-all error codes beyond the bounded reporting categories defined here;
10. rely on a reverse relation name;
11. target non-user-backed Identities;
12. provide a handle delete/rollback path;
13. manually raise `SystemExit`.

## 15. Acceptance Criteria

1. Calls only `reserve_handle_for_identity` for allocation.
2. Is idempotent under repeated execution.
3. Dry-run performs no writes and does not call the reservation service.
4. Isolates per-Identity failures.
5. Uses cursor-like batching with a maximum batch size of 1000.
6. Uses bulk seed lookup without N+1 queries.
7. Does not rely on a reverse relation name.
8. Uses Django-native exit behavior and the CLI contract in §9.
9. Reports `scanned / succeeded / failed` without claiming `created` attribution.
10. Default output is aggregate and `--quiet` suppresses per-batch/per-item output.
11. `--identity-id` accepts one argparse-validated UUID in V1.
12. Includes a PostgreSQL concurrency smoke test.
13. Does not manually raise `SystemExit`.
14. Targets only user-backed Identities without a handle.
15. Passes `UserIdentity.user.username` verbatim as `base_seed` and performs no PR C-level `display_name` substitution.
16. Changes no implementation code outside the two files listed in §2.
17. Emits only bounded error categories in stdout summaries; raw exception text is excluded.

## 16. Test Coverage

### Unit — `test_backfill_identity_handles.py`

Eligibility:

- Identity without `UserIdentity` is not scanned.
- Identity with a handle is not scanned.
- Identity with `UserIdentity` and no handle is scanned.

Success:

- single eligible Identity produces `succeeded=1`;
- multiple eligible Identities are processed;
- reserved username produces the service-defined suffixed handle.

Idempotency:

- second run scans nothing after successful provisioning;
- rerun does not modify an existing handle.

Seed:

- username is passed verbatim as `base_seed`;
- PR C performs no `display_name` fallback;
- empty username handling remains owned by the service contract and is not reimplemented or assumed by PR C;
- a non-empty non-Latin-only username exercises ADR-013's service-level deterministic fallback.

Query efficiency:

- bulk seed lookup is performed per batch without per-Identity lookup; query-count coverage SHOULD verify the intended bound without coupling tests to unrelated framework queries.

Dry-run:

- creates nothing;
- does not call `reserve_handle_for_identity`;
- reports aggregate count only.

Failure:

- one failure does not roll back successful processing of other Identities;
- one or more processing failures cause `CommandError` after processing;
- `HandleAllocationError` emits a warning;
- unexpected exception emits exception-level operational logging;
- stdout contains only bounded error categories, not raw exception text.

Batching and validation:

- configured batch size is respected;
- invalid batch size follows parser error semantics;
- invalid UUID follows parser error semantics;
- `--identity-id` restricts processing to one eligible Identity.

Output:

- `--quiet` suppresses per-batch and per-item output while retaining final summary;
- `--verbose` emits per-identity detail;
- default emits aggregate progress only;
- summary is written to stdout.

Accounting:

- `succeeded` counts successful reservation calls and is not labelled as `created`.

### Concurrency Smoke — `TransactionTestCase`

- two parallel runs targeting the same Identity produce a single `IdentityHandle` row;
- skipped when the database vendor is not PostgreSQL.

## 17. Alignment Check

| Reference | Alignment |
| --- | --- |
| ADR-013 §D3.1 | Model A recovery path |
| ADR-013 §D4 | consumes canonical idempotent/race-safe allocation service |
| ADR-013 §D7 | V1 immutability; no delete path |
| ADR-016 | limited applicability because PR C is migration-free |
| PR A | schema and allocation service must exist first |
| PR B Spec v2.1 | same lifecycle seed source: username; PR C does not own empty-seed service behavior |

## 18. Suspension Status

| Gate | Status |
| --- | --- |
| Auth baseline | FAIL / suspended |
| PR A schema/service | must merge before PR C implementation |
| PR B implementation | suspended |
| PR C implementation | suspended; this document is specification only |

PR C implementation is code-independent from PR B implementation, but it is the recovery path for the failure semantics consumed by PR B and frozen in ADR-013 Model A.

## 19. Resolved Questions

1. `HandleAllocationError` logging level: WARNING.
2. `--identity-id`: single UUID only in V1.
3. Final summary: stdout.
4. Duplicate-work warning: not required; concurrency is expected and the service is idempotent.
5. `--reason`: not included; audit-trail schema/policy is not part of PR C.

## 20. Changes from v1/v2

Relative to the earlier proposal discussion, v2.1 freezes these corrections:

1. eligibility is user-backed Identity only;
2. PR C seed source is verbatim `UserIdentity.user.username`, with no PR C-level `display_name` fallback;
3. empty-username handling remains owned by the canonical service and is not assumed by PR C;
4. stdout error reporting uses bounded categories rather than raw exception messages;
5. data rollback via handle deletion is rejected in favor of ADR-013's immutability contract and forward-fix/reconciliation;
6. CLI process-exit semantics are separated from internal Django test behavior;
7. I7 distinguishes valid invocation failures from parser-invalid CLI input;
8. concurrency coverage is smoke-only and does not duplicate the service's race-safety proof.

## Freeze Boundary

If merged, this document freezes PR C Specification v2.1 as a proposal only. It does not authorize or implement PR C runtime code, PR A, PR B runtime integration, migrations, Auth changes, deployment changes, or changes to PR #239.
