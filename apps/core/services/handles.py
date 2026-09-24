"""Canonical IdentityHandle allocation service (ADR-013)."""

from __future__ import annotations

import re
import unicodedata

from django.db import IntegrityError, transaction

from apps.core.constants.handles import (
    HANDLE_FALLBACK_PREFIX,
    HANDLE_MAX_LENGTH,
    HANDLE_SUFFIX_MAX_RETRY,
    RESERVED_HANDLES,
)
from apps.core.models import Identity, IdentityHandle


class HandleAllocationError(Exception):
    """Raised when no unique handle candidate can be allocated."""


_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALLOWED_RE = re.compile(r"[^a-z0-9-]+")
_MULTI_DASH_RE = re.compile(r"-+")

# Django/PostgreSQL's exact unique constraint name for
# core_identityhandle.handle when declared with unique=True. The migration/CI
# verification for this PR must keep this value aligned with the real schema.
_POSTGRES_HANDLE_UNIQUE_CONSTRAINT = "core_identityhandle_handle_key"
_SQLITE_IDENTITY_UNIQUE = "unique:core_identityhandle.identity_id"
_SQLITE_HANDLE_UNIQUE = "unique:core_identityhandle.handle"


def normalize_handle(raw: str | None) -> str:
    """Normalize a seed to the frozen ASCII-only handle policy."""
    if not raw:
        return ""
    normalized = unicodedata.normalize("NFKC", raw).lower()
    normalized = _WHITESPACE_RE.sub("-", normalized)
    normalized = _NON_ALLOWED_RE.sub("", normalized)
    normalized = _MULTI_DASH_RE.sub("-", normalized)
    return normalized.strip("-")


def _truncate_for_suffix(base: str, suffix_len: int) -> str:
    """Return the usable prefix after reserving room for a suffix."""
    limit = HANDLE_MAX_LENGTH - suffix_len
    if limit <= 0:
        return ""
    return base[:limit].rstrip("-")


def _derive_default_seed(identity: Identity) -> str:
    return identity.display_name or ""


def _deterministic_fallback(identity: Identity) -> str:
    return normalize_handle(f"{HANDLE_FALLBACK_PREFIX}-{identity.id.hex[:8]}")


def _extract_violated_constraint(exc: IntegrityError) -> str | None:
    """Extract a stable constraint marker from PostgreSQL or SQLite errors."""
    cause = getattr(exc, "__cause__", None)
    diag = getattr(cause, "diag", None)
    if diag is not None:
        name = getattr(diag, "constraint_name", None)
        if name:
            return name

    message = str(exc)
    prefix = "UNIQUE constraint failed:"
    if prefix in message:
        columns = message.split(prefix, 1)[1].strip()
        return f"unique:{columns}"

    return None


def _is_one_handle_per_identity_conflict(exc: IntegrityError) -> bool:
    constraint = _extract_violated_constraint(exc)
    return constraint in {
        "uniq_handle_per_identity_v1",
        _SQLITE_IDENTITY_UNIQUE,
    }


def _is_handle_uniqueness_conflict(exc: IntegrityError) -> bool:
    constraint = _extract_violated_constraint(exc)
    return constraint in {
        _POSTGRES_HANDLE_UNIQUE_CONSTRAINT,
        _SQLITE_HANDLE_UNIQUE,
    }


def reserve_handle_for_identity(
    identity: Identity,
    base_seed: str | None = None,
) -> IdentityHandle:
    """Idempotently reserve one unique handle for an Identity.

    Existing allocation wins. New allocations try the normalized base followed
    by ``-2`` through ``-10``. Each create attempt has its own atomic boundary;
    there is deliberately no function-wide transaction.
    """
    existing = IdentityHandle.objects.filter(identity=identity).first()
    if existing:
        return existing

    seed = _derive_default_seed(identity) if base_seed is None else base_seed
    base = normalize_handle(seed)
    if not base:
        base = _deterministic_fallback(identity)

    if base in RESERVED_HANDLES:
        base = f"{base}-user"

    fallback = _deterministic_fallback(identity)

    for attempt in range(1, HANDLE_SUFFIX_MAX_RETRY + 1):
        suffix = "" if attempt == 1 else f"-{attempt}"
        prefix = _truncate_for_suffix(base, len(suffix))
        if not prefix:
            prefix = _truncate_for_suffix(fallback, len(suffix))
        if not prefix:
            raise HandleAllocationError(
                f"Could not derive a valid handle prefix for identity {identity.id}"
            )
        candidate = prefix + suffix

        try:
            with transaction.atomic():
                return IdentityHandle.objects.create(
                    identity=identity,
                    handle=candidate,
                )
        except IntegrityError as exc:
            if _is_one_handle_per_identity_conflict(exc):
                winner = IdentityHandle.objects.filter(identity=identity).first()
                if winner:
                    return winner
                continue

            if _is_handle_uniqueness_conflict(exc):
                continue

            raise

    raise HandleAllocationError(
        f"Could not allocate a unique handle for identity {identity.id}"
    )
