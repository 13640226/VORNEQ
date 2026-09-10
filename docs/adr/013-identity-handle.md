# ADR-013: IdentityHandle — Canonical Handle Allocation

## Status

Proposed (frozen)

## Date

2026-09-10

## Context

VORNEQ has a canonical Identity registry that acts as a trust actor independently of Django authentication. In the current architecture:

- `Identity` is the canonical model with a UUID primary key and kinds limited to `human`, `organization`, `agent`, and `system`.
- `UserIdentity` is a one-to-one binding between Django `User` and `Identity`.
- `register_user_identity(user)` is an atomic, idempotent service boundary returning `(identity, created)`.
- There is currently no portable, displayable identity-address concept.

Product requirements:

- Each user needs a short, shareable identity address for Profile display and possible future mention/notification use.
- The address must not belong to an app-specific identity silo or authentication backend.
- In V1 the address is not a real mailbox and is not used for login or recovery.

## Decision

### D1. Introduce `IdentityHandle`

Introduce an independent model attached to `Identity`, not to `User` or `UserIdentity`:

```python
class IdentityHandle(models.Model):
    identity = models.ForeignKey(
        "core.Identity",
        on_delete=models.PROTECT,
        related_name="handles",
    )
    handle = models.SlugField(max_length=32, unique=True)
    reserved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["identity"],
                name="uniq_handle_per_identity_v1",
            ),
        ]
```

V1 permits exactly one handle per `Identity` as a database invariant. `is_primary` is intentionally omitted until multi-handle support is a real requirement. `db_index=True` is unnecessary because `unique=True` provides the required uniqueness index. `released_at` is not part of the V1 schema and is documented only under Future.

### D2. Derive the display address

Only the handle itself is stored and unique, for example `ali`. The display address is derived as:

```python
f"{handle}@vorneq.com"
```

The domain is never stored as part of the unique value. This keeps the handle namespace independent from a future domain or subdomain migration.

### D3. Keep lifecycle services independent

`register_user_identity(user)` remains unchanged and is out of scope for this ADR. The lifecycle is conceptualized as:

```text
Caller / Lifecycle Adapter:
  1. identity, created = register_user_identity(user)
  2. reserve_handle_for_identity(identity, base_seed=...)
```

Handle allocation must not be implemented in the `UserIdentity` model, a signup view, or a generic `post_save(User)` signal.

The two services remain independently idempotent: repeated identity registration returns the existing binding, and repeated handle reservation returns the existing handle.

### D4. Deterministic, race-safe allocation

Allocation follows this contract:

1. Compute `base = normalize_handle(seed)`, where the seed normally comes from a username or email local-part.
2. If normalization produces an empty value, use a deterministic fallback such as `user-<identity UUID hex prefix>`; an empty handle is never created.
3. If the normalized base is in `RESERVED_HANDLES`, transform it to `<base>-user`.
4. Try candidates deterministically in this order: `base`, `base-2`, `base-3`, and so on, with `MAX_RETRY = 10`.
5. Before each attempt, truncate the base so that `base + suffix` never exceeds 32 characters.
6. Perform each candidate creation inside its own `transaction.atomic()` savepoint.
7. Classify uniqueness conflicts separately from other integrity failures.
8. If the bounded retry set is exhausted, raise `HandleAllocationError`; there is no automatic unbounded fallback.

Illustrative service shape:

```python
MAX_RETRY = 10


def reserve_handle_for_identity(identity, base_seed=None):
    existing = IdentityHandle.objects.filter(identity=identity).first()
    if existing:
        return existing

    base = normalize_handle(base_seed or _derive_default_seed(identity))
    if not base:
        base = _deterministic_fallback(identity)

    if base in RESERVED_HANDLES:
        base = f"{base}-user"

    for i in range(1, MAX_RETRY + 1):
        suffix = "" if i == 1 else f"-{i}"
        candidate = _truncate_for_suffix(base, len(suffix)) + suffix
        try:
            with transaction.atomic():
                return IdentityHandle.objects.create(
                    identity=identity,
                    handle=candidate,
                )
        except IntegrityError as exc:
            if _is_one_handle_per_identity_conflict(exc):
                race_winner = IdentityHandle.objects.filter(
                    identity=identity,
                ).first()
                if race_winner:
                    return race_winner
                continue

            if _is_handle_uniqueness_conflict(exc):
                continue

            raise

    raise HandleAllocationError(
        f"Could not allocate a unique handle for identity {identity.id}"
    )
```

The whole function is deliberately not wrapped in a new `@transaction.atomic` boundary solely for retry handling. Each allocation attempt has its own atomic block/savepoint. When the service executes inside an existing outer transaction, the inner atomic block provides the savepoint needed to recover from an expected candidate conflict without leaving that outer transaction unusable.

Integrity failures fall into three categories:

1. `uniq_handle_per_identity_v1` violation: another concurrent caller may already have allocated a handle for the same identity; re-fetch and return the race winner when visible.
2. Handle uniqueness violation: the candidate is occupied; continue to the next deterministic candidate.
3. Any other `IntegrityError`, including unexpected FK, NOT NULL, or CHECK violations: propagate the exception rather than swallowing it as a collision.

Implementation note for Phase 2: uniqueness-conflict classification must be backend-aware and covered by integration tests against the real database. Constraint metadata such as the constraint name should be obtained from the backend exception/cause where supported rather than inferred from exception text alone.

### D5. ASCII-only normalization in V1

Normalization is deterministic and explicitly versioned by this ADR. V1 uses the following policy:

- Allowed character set: ASCII `[a-z0-9-]` only. Other characters are removed.
- Case: ASCII letters are converted to lowercase.
- Dashes: consecutive dashes collapse to one; leading and trailing dashes are removed.
- Length: the base is deterministically truncated before adding a suffix so the final handle is at most 32 characters.
- Transliteration: not performed in V1. No transliteration dependency such as `unidecode` is introduced.
- Non-Latin seeds, including Persian, Arabic, CJK, or emoji, may therefore normalize to an empty string.
- Empty output: use deterministic fallback `user-{identity.id.hex[:8]}` and normalize it under the same policy.

If transliteration is introduced later, it requires a separate architectural decision specifying the library, behavior, and pinned version.

### D6. Centralize reserved words

Reserved handles are maintained as a `frozenset` in `apps/core/constants/handles.py`. Comparison occurs after normalization so alternate casing or normalization cannot bypass reservations.

The initial set should include system-sensitive names such as `admin`, `administrator`, `root`, `support`, `vorneq`, `system`, `security`, `help`, `api`, `www`, `mail`, `noreply`, and `no-reply`.

Expansion of the reserved set should be reviewed explicitly rather than scattered across callers.

### D7. Treat immutability as an architectural contract in V1

A V1 handle is architecturally immutable. The proposed model alone does not mechanically prevent direct `update()` or `delete()` operations.

V1 enforcement is therefore based on the supported creation surface: handle creation goes through the allocation service, and no supported service updates an existing handle. If stronger mechanical enforcement is required later, model or database enforcement can be evaluated separately.

This ADR distinguishes this architectural contract from mechanically enforced invariants such as uniqueness and one-handle-per-identity.

Implementation note for Phase 2: because `SlugField` does not itself enforce the exact `[a-z0-9-]` business contract at the database layer, all supported V1 creation paths must go through the allocation service. A future DB `CHECK` or other enforcement mechanism requires separate review.

## Consequences

### Benefits

- Handle identity remains independent from Django `User` and compatible with portable canonical Identity.
- The Identity layer remains the single source of truth.
- Database uniqueness, bounded retry, savepoints, and explicit integrity-error classification provide race-safe allocation.
- Empty or nondeterministic handles are avoided through deterministic fallback.
- The design leaves room for aliases, release semantics, and mailbox integration without implementing them prematurely.

### Costs

- A new model and migration will be required in Phase 2.
- A new service will be required in `apps/core/services/handles.py`.
- The reserved-word list requires maintenance.
- Users whose seeds contain no usable ASCII characters receive a `user-<hex>` style fallback in V1.

### Known risks

- Until controlled backfill is completed, some existing identities may have no handle; V1 accepts this during rollout.
- Changing the display domain changes rendered addresses while stored unique handle values remain unchanged.
- Fallback handles for non-Latin usernames may be less human-readable.

## Future — documented only, not implemented in V1

- `released_at` for controlled handle migration scenarios.
- Multi-handle aliases if a product requirement is confirmed.
- Transliteration for non-Latin seeds, governed by a separate ADR with a pinned library/version.
- A real mailbox capability under a separate ADR.
- Forwarding from `handle@vorneq.com` to a user's real email address.

## Rollout Sequence

1. Phase 1 — this ADR, documentation only.
2. Phase 2 — model, allocation service, migration, and tests.
3. Phase 3 — controlled backfill for existing users using idempotent `reserve_handle_for_identity`.
4. Phase 4 — Profile projection displaying `handle@vorneq.com`.

## Related ADRs

- ADR-012: Executable Capabilities (Proposed)

## Out of Scope

- Login using a handle.
- Account recovery using a handle.
- A real mailbox.
- Changes to `Identity.Kind`.
- Changes to `Identity.display_name` or `Identity.metadata`.
- Changes to the behavior or signature of `register_user_identity(user)`.
