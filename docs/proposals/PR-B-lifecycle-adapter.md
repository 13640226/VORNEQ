# PR B — Lifecycle Adapter Specification

**Status:** Proposal-only · Ready-to-Freeze · Implementation suspended  
**Version:** 2.1  
**Date:** 2026-09-10  
**Dependency:** ADR-013 §D3.1 (Model A — non-atomic provisioning), frozen by PR #251

## 1. Position Statement

PR B does not decide transaction ownership. ADR-013 §D3.1 freezes **Model A — non-atomic provisioning**.

PR B consumes this contract:

```text
Identity: canonical and durable
Handle:   recoverable provisioning
Partial state (Identity-without-Handle): valid but incomplete
```

This specification defines lifecycle invariants rather than assuming django-allauth internals. Integration tests are responsible for verifying actual hook behavior against the pinned allauth version.

## 2. Scope

Proposed implementation scope:

| File | Change |
| --- | --- |
| `apps/core/services/provisioning.py` | NEW — lifecycle orchestration |
| `apps/core/adapters/__init__.py` | NEW |
| `apps/core/adapters/local.py` | NEW — `VORNEQLocalAccountAdapter` |
| `apps/core/adapters/social.py` | NEW — `VORNEQSocialAccountAdapter` |
| `config/settings.py` | EDIT — add `ACCOUNT_ADAPTER` and `SOCIALACCOUNT_ADAPTER` |
| `apps/core/tests/test_provisioning.py` | NEW — unit tests |
| `apps/core/tests/test_signup_lifecycle.py` | NEW — local/social integration tests |

Out of scope:

- `post_save(User)` lifecycle signals.
- Changes to `registry.py`, `handles.py`, `UserIdentity`, or `Identity` models.
- A shared outer `transaction.atomic()` spanning Identity and Handle provisioning.
- Backfill command (PR C).
- Audit schema integration.
- Required metric instrumentation; metrics MAY be added in a follow-up.

At the time of this proposal, `ACCOUNT_ADAPTER` and `SOCIALACCOUNT_ADAPTER` are not configured on canonical `main`; they are proposed implementation changes in PR B.

## 3. Lifecycle Invariants

### I1 — Provisioning Invocation Contract

Every successful new-user creation path MUST invoke `provision_new_user(user)` as part of that lifecycle.

Within one signup lifecycle, adapter composition MUST NOT cause duplicate provisioning invocation.

Subsequent explicit retry/recovery calls are permitted and MUST remain idempotent.

### I2 — Independent Transaction Ownership

`register_user_identity(user)` and `reserve_handle_for_identity(identity, ...)` retain independent transaction ownership.

### I3 — No Shared Outer Transaction

PR B MUST NOT wrap both provisioning services in a shared outer `transaction.atomic()` block.

### I4 — Identity Failure Visibility

Identity provisioning failures MUST propagate to the caller. Silent swallowing is prohibited.

### I5 — Handle Failure Isolation

An expected recoverable Handle allocation failure MUST NOT roll back a successfully created `Identity`/`UserIdentity`.

### I6 — Operational Observability

Expected Handle provisioning failures MUST be surfaced through structured logging with bounded context.

### I7 — Idempotency

Repeated explicit calls to `provision_new_user(user)` MUST remain safe and MUST NOT create duplicate Identity or Handle state.

### I8 — allauth Semantics Are Verified, Not Assumed

Exact user-visible and signup-persistence semantics under provisioning failure MUST be verified by integration tests against the pinned django-allauth version and MUST NOT be assumed by this proposal.

## 4. Failure Semantics

### 4.1 Identity Failure

Identity provisioning failure MUST propagate to the caller; exact user-visible / signup persistence semantics are verified by integration tests and MUST NOT be assumed by this proposal.

V1 MAY use a generic safe user-facing error. Dedicated provisioning-failure UX is separate scope.

### 4.2 Handle Failure

#### Expected recoverable failure — `HandleAllocationError`

| Aspect | Behavior |
| --- | --- |
| Propagation | MUST NOT raise beyond the provisioning orchestration |
| Rollback | MUST NOT roll back `Identity`/`UserIdentity` |
| Result | MAY return `handle_status="failed"` |
| Observability | Structured WARNING log |
| `handle_error_code` | `"allocation_failed"` |
| Recovery | Approved backfill/reconciliation path (PR C) |

#### Unexpected exceptions

Database, invariant, and programming failures are not recoverable allocation failures.

| Aspect | Behavior |
| --- | --- |
| Propagation | MUST remain visible and propagate |
| Observability | Log at ERROR level before propagation when PR B has useful bounded context |
| Rollback | Determined by underlying service/exception semantics; PR B MUST NOT mask it |
| Error code | MUST NOT be converted to a catch-all `unexpected_error` result |

PR B MUST preserve ADR-013 §D4's distinction between expected allocation exhaustion/conflict handling and unexpected integrity failures.

Conceptual orchestration:

```python
try:
    handle = reserve_handle_for_identity(identity, base_seed=username)
except HandleAllocationError:
    logger.warning("handle_provisioning_failed", extra={...})
    return ProvisioningResult(
        identity_id=identity.id,
        identity_created=identity_created,
        handle=None,
        handle_status="failed",
        handle_error_code="allocation_failed",
    )
# Other exceptions propagate naturally.
```

### 4.3 Result Envelope

```python
from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class ProvisioningResult:
    identity_id: UUID
    identity_created: bool
    handle: str | None
    handle_status: Literal["created", "existing", "failed"]
    handle_error_code: str | None
```

For V1, the bounded recoverable error-code set contains only:

- `allocation_failed` — `HandleAllocationError`.

`unexpected_error` is explicitly not a bounded result code: unexpected exceptions propagate. Reserved words are handled by ADR-013 normalization/transformation rules rather than a separate provisioning failure code.

## 5. Observability

Required in PR B:

- Structured `handle_provisioning_failed` log.
- Bounded context: `user_id`, `identity_id`, and `error_code`; no sensitive exception detail.
- WARNING for expected recoverable `HandleAllocationError`.
- ERROR for unexpected failures when logging at the orchestration boundary adds useful bounded context, followed by propagation.
- Returned `ProvisioningResult` for successful and expected-recoverable orchestration outcomes.

Optional/follow-up:

- `provisioning_handle_failure_total` or equivalent metric.
- Alerting/SLO policy.
- `AuditEvent` integration.

Structured logging plus the bounded returned status satisfies the PR B observability requirement without making Prometheus instrumentation part of this proposal's required scope. Any future metric MUST comply with ADR-017 metric-label and access-control policy.

## 6. Adapter Boundary

Adapters own lifecycle orchestration, not Identity/Handle implementation logic.

### 6.1 Local Adapter

Conceptual skeleton:

```python
class VORNEQLocalAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=commit)
        if commit and user.pk:
            provision_new_user(user)
        return user
```

Invariant: a successful committed local new-user creation path invokes provisioning as part of that lifecycle without adapter-induced duplicate invocation.

### 6.2 Social Adapter

The exact django-allauth internal call path is not frozen by this specification.

Invariant: every successful social new-user creation path invokes provisioning as part of that lifecycle, while adapter composition MUST NOT cause duplicate invocation within the same signup lifecycle.

Implementation MUST prove through integration tests that:

- social auto-signup triggers provisioning;
- explicit/form-based social signup triggers provisioning;
- adapter composition does not double-invoke provisioning;
- subsequent explicit retries remain permitted and idempotent.

A possible implementation skeleton, subject to verification against the pinned django-allauth version, is:

```python
class VORNEQSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        # Mechanism is not an architectural contract. Integration tests
        # must prove the lifecycle invariants against the pinned allauth version.
        if form is None and user.pk:
            provision_new_user(user)
        return user
```

## 7. Non-Goals

PR B MUST NOT:

1. Add an outer `transaction.atomic()` spanning both services.
2. Roll back Identity/UserIdentity solely because expected Handle allocation failed.
3. Silently swallow Handle provisioning failures.
4. Modify `register_user_identity` or `reserve_handle_for_identity`.
5. Modify `UserIdentity` or `Identity` models.
6. Add a `post_save(User)` provisioning signal.
7. Add the PR C backfill command.
8. Integrate with the `AuditEvent` schema.
9. Require metric instrumentation as part of PR B.
10. Override `on_authentication_error` unless implementation genuinely requires that hook and its scope is separately justified.
11. Convert unexpected exceptions into a bounded catch-all failure result.

## 8. Acceptance Criteria

1. Identity provisioning is mandatory and its failure propagates.
2. Expected `HandleAllocationError` is recoverable: Identity remains durable and the failure is logged at WARNING.
3. Unexpected Handle/database/invariant/programming exceptions remain visible, receive bounded ERROR logging when appropriate, and propagate.
4. No outer transaction wraps both provisioning services.
5. Handle allocation uses `base_seed = user.username`.
6. A real local django-allauth signup integration test covers lifecycle provisioning.
7. Social auto-signup integration test covers provisioning.
8. Social explicit/form-based signup test proves adapter composition does not duplicate provisioning.
9. No duplicate provisioning invocation occurs within a single signup lifecycle; explicit subsequent retries remain supported.
10. Repeated explicit `provision_new_user(user)` calls are idempotent.
11. Identity failure propagation and actual allauth persistence semantics are verified by integration test rather than assumed.
12. Expected Handle allocation failure leaves Identity durable and returns a bounded failed result.
13. `ACCOUNT_ADAPTER` and `SOCIALACCOUNT_ADAPTER` are registered as new settings.
14. `registry.py`, `handles.py`, `UserIdentity`, and `Identity` remain unchanged.
15. `ProvisioningResult` returns bounded `handle_status` and `handle_error_code` values.

## 9. Test Coverage

### Unit — `test_provisioning.py`

- Success path: `handle_status="created"`.
- Idempotent second explicit call: `handle_status="existing"`.
- Identity failure propagates.
- `HandleAllocationError`: `handle_status="failed"`, `handle_error_code="allocation_failed"`, Identity remains durable, WARNING logged.
- Unexpected Handle-side exception: ERROR logged when appropriate and exception propagates.
- `base_seed` derives from `user.username`.
- Provisioning does not depend on `post_save(User)`.

### Integration — `test_signup_lifecycle.py`

- Real local signup provisions Identity and Handle.
- Social auto-signup invokes provisioning.
- Social explicit/form-based signup invokes provisioning without duplicate adapter invocation.
- Reserved username produces the ADR-013-compliant transformed/suffixed handle.
- Non-Latin username produces the deterministic ADR-013 fallback handle.
- Provisioning does not rely on a `user_signed_up` signal receiver.
- Identity-provisioning failure test records actual signup/user-persistence behavior against the pinned django-allauth version.

## 10. Alignment

| Reference | Alignment |
| --- | --- |
| ADR-013 §D3 | Lifecycle orchestration honored |
| ADR-013 §D3.1 | Model A consumed; PR B does not decide transaction ownership |
| ADR-013 §D4 | Per-attempt savepoint and unexpected-integrity-error distinction preserved |
| ADR-013 §D5 | ASCII-only normalization consumed through Handle service |
| ADR-013 §D6 | Reserved-word policy consumed through Handle service |
| ADR-013 §D7 | Handle immutability contract preserved |
| PR A | Schema/service prerequisite; must exist before PR B implementation |
| PR C | Recovery path for valid incomplete Identity-without-Handle state |
| ADR-017 | Required metric instrumentation kept out of PR B; future metrics must follow observability policy |

## 11. Suspension Status

| Gate | Status |
| --- | --- |
| Auth baseline | FAIL — implementation precondition remains unresolved |
| PR A schema/service | Suspended; must be available before PR B implementation |
| ADR-016 rollout prerequisites | Gated/suspended |
| PR B implementation | Suspended |

PR B is architecturally unblocked with respect to transaction ownership only. This proposal does not authorize implementation.

## 12. Resolved Questions

1. Metric in PR B? **Not required; MAY be follow-up.**
2. Handle failure log level? **WARNING for expected recoverable allocation failure; ERROR for unexpected failures before propagation when useful.**
3. Envelope error representation? **Bounded code; V1 recoverable set contains only `allocation_failed`.**
4. Identity failure UX? **Generic safe error is sufficient for V1; dedicated UX is separate scope.**
5. `on_authentication_error` test? **No, unless implementation actually overrides that hook.**

## 13. Proposal Status

This document freezes the **PR B implementation proposal**, not runtime behavior.

It does not create or modify application code, migrations, adapters, settings, models, Auth/AXES behavior, PR #239, PR A, or PR C.

Implementation remains suspended until its independent execution gates are satisfied and separately authorized.
