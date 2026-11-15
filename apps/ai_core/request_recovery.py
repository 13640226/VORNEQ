"""Staging-only AI request recovery with durable PostgreSQL idempotency.

The default application database is the authoritative, unique request guard.
Redis is an ephemeral 15-minute response cache and 24-hour convenience guard.
A Redis eviction/restart cannot re-authorize an already accepted request.
This does not guarantee exactly-once if the database itself loses rows.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from apps.ai_core.models import AIChatRequestGuard

RESPONSE_TTL_SECONDS = 15 * 60
GUARD_TTL_SECONDS = 24 * 60 * 60
RUNNING_GRACE_SECONDS = 120
STORE_KEY_PREFIX = "vq:ai:staging:recovery:v1"


class RecoveryUnavailable(Exception):
    """No reliable shared idempotency state: fail closed before model access."""


class RecoveryInvalid(Exception):
    """Malformed or missing client-generated request identifier."""


class RecoveryConflict(Exception):
    """A valid request ID is already bound to different request content."""


class RecoveryNotFound(Exception):
    """Unknown request ID, or not owned by the authenticated session."""


def enabled():
    return (
        getattr(settings, "VORNEQ_ENV", None) == "staging"
        and getattr(settings, "VORNEQ_AI_CHAT_RECOVERY_ENABLED", False) is True
    )


def parse_id(value):
    if not isinstance(value, str) or len(value) != 36:
        raise RecoveryInvalid("request ID must be UUIDv4")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise RecoveryInvalid("invalid request ID") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise RecoveryInvalid("noncanonical request ID")
    return value


def _require_shared_redis():
    """Hosted Staging must never use process-local cache for deduplication."""
    conf = settings.CACHES.get("default", {})
    if (conf.get("BACKEND") != "django.core.cache.backends.redis.RedisCache"
            or not getattr(settings, "REDIS_URL", None)):
        raise RecoveryUnavailable("shared Redis not configured")


def _identity(request):
    if not request.user.is_authenticated or not request.user.is_active:
        raise RecoveryNotFound("not authenticated")
    session_key = getattr(request.session, "session_key", None)
    if not isinstance(session_key, str) or not session_key:
        raise RecoveryUnavailable("authenticated session unavailable")
    secret = str(settings.SECRET_KEY).encode("utf-8")
    session_digest = hmac.new(secret, session_key.encode("utf-8"), hashlib.sha256).hexdigest()
    return int(request.user.pk), session_digest


def _keys(request_id):
    base = f"{STORE_KEY_PREFIX}:{request_id}"
    return base + ":guard", base + ":result"


def _fingerprint(question, language):
    return hashlib.sha256(
        json.dumps([question, language], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _checked_get(key):
    try:
        return cache.get(key)
    except Exception as exc:
        raise RecoveryUnavailable("Redis read failed") from exc


def _durable_guard(request_id):
    """Read the authoritative guard. Database errors always fail closed."""
    try:
        return AIChatRequestGuard.objects.using("default").get(request_id=request_id)
    except AIChatRequestGuard.DoesNotExist as exc:
        raise RecoveryNotFound("durable request guard not found") from exc
    except DatabaseError as exc:
        raise RecoveryUnavailable("durable request guard unavailable") from exc


def _snapshot(request, request_id):
    """A Redis miss must never erase the PostgreSQL duplicate-request guard."""
    _require_shared_redis()
    user_id, session_digest = _identity(request)
    durable = _durable_guard(request_id)
    if durable.actor_id != user_id or not hmac.compare_digest(
        durable.session_digest, session_digest
    ):
        raise RecoveryNotFound("request not owned by session")
    if durable.state not in ("running", "finished"):
        raise RecoveryUnavailable("malformed durable guard")
    record = {
        "actor": durable.actor_id,
        "session": durable.session_digest,
        "fingerprint": durable.fingerprint,
        "state": durable.state,
        "created_at": int(durable.created_at.timestamp()),
    }
    _, result_key = _keys(request_id)
    result = _checked_get(result_key)
    if result is not None:
        if (not isinstance(result, dict) or result.get("status") not in ("completed", "failed")
                or not isinstance(result.get("http_status"), int)
                or not isinstance(result.get("response"), dict)):
            raise RecoveryUnavailable("malformed response cache")
        return result, record
    if durable.state == "finished":
        return {"status": "expired"}, record
    age = max(0, int(time.time()) - int(durable.created_at.timestamp()))
    if age > RUNNING_GRACE_SECONDS:
        return {"status": "uncertain"}, record
    return {"status": "running"}, record


def claim(request, request_id, *, question, language):
    """Atomic first-use claim. Return 'claimed' or a *read-only* prior snapshot."""
    request_id = parse_id(request_id)
    _require_shared_redis()
    actor, session = _identity(request)
    guard_key, _ = _keys(request_id)
    fingerprint = _fingerprint(question, language)
    record = {
        "actor": actor,
        "session": session,
        "fingerprint": fingerprint,
        "state": "running",
        "created_at": int(time.time()),
    }
    # A Redis connectivity failure must prevent a new provider request.
    _checked_get("__vq_ai_recovery_connection_check__")
    # PRIMARY AUTHORITY: PostgreSQL/SQL unique UUID insert, transactionally
    # committed *before* any budget, retrieval, ledger, or provider action.
    # Never DELETE this row to retry an uncertain or completed request.
    try:
        with transaction.atomic(using="default"):
            AIChatRequestGuard.objects.using("default").create(
                request_id=request_id,
                actor_id=actor,
                session_digest=session,
                fingerprint=fingerprint,
                state="running",
            )
    except IntegrityError:
        # The earlier request's durable row survives Redis eviction or
        # complete Redis restart. Read only; never issue a new provider call.
        snapshot, original = _snapshot(request, request_id)
        if not hmac.compare_digest(str(original.get("fingerprint", "")), fingerprint):
            raise RecoveryConflict("same request id used for different content")
        return snapshot
    except DatabaseError as exc:
        raise RecoveryUnavailable("durable idempotency claim unavailable") from exc
    try:
        created = cache.add(guard_key, record, timeout=GUARD_TTL_SECONDS)
    except Exception as exc:
        # An orphaned durable row is intentional and safe: no provider called.
        raise RecoveryUnavailable("Redis atomic claim failed") from exc
    if not created:
        # Existing Redis guard without a corresponding historical DB row:
        # fail closed rather than trust an ambiguous cache-only signal.
        raise RecoveryUnavailable("Redis guard already existed before durable claim")
    return {"status": "claimed"}


def status(request, request_id):
    request_id = parse_id(request_id)
    snapshot, _ = _snapshot(request, request_id)
    return snapshot


def finish(request, request_id, *, http_status, response):
    """Store a bounded response before marking the claim finalized.

    Failure to store never permits automatic replay or a second model call.
    """
    request_id = parse_id(request_id)
    _require_shared_redis()
    _identity(request)
    guard_key, result_key = _keys(request_id)
    durable = _durable_guard(request_id)
    actor, session = _identity(request)
    if durable.actor_id != actor or not hmac.compare_digest(durable.session_digest, session):
        raise RecoveryNotFound("different principal")
    if durable.state != "running":
        raise RecoveryUnavailable("durable guard is not running")
    if not isinstance(response, dict) or not 100 <= http_status <= 599:
        raise RecoveryUnavailable("invalid result")
    value = {
        "status": "completed" if 200 <= http_status < 400 else "failed",
        "http_status": http_status,
        "response": response,
    }
    try:
        # Persist response before marking the durable guard finalized.
        # A cache failure leaves a permanent running guard and blocks replay.
        cache.set(result_key, value, timeout=RESPONSE_TTL_SECONDS)
        if _checked_get(result_key) != value:
            raise RecoveryUnavailable("Redis result write not confirmed")
    except RecoveryUnavailable:
        raise
    except Exception as exc:
        raise RecoveryUnavailable("Redis result write failed") from exc
    try:
        updated = AIChatRequestGuard.objects.using("default").filter(
            request_id=request_id,
            actor_id=actor,
            session_digest=session,
            state="running",
        ).update(state="finished", finished_at=timezone.now())
        if updated != 1:
            raise RecoveryUnavailable("durable guard transition not confirmed")
    except DatabaseError as exc:
        raise RecoveryUnavailable("durable guard transition failed") from exc
    # Redis is convenience state only; PostgreSQL remains authoritative.
    try:
        cache.set(guard_key, {
            "actor": actor,
            "session": session,
            "fingerprint": durable.fingerprint,
            "state": "finished",
            "created_at": int(durable.created_at.timestamp()),
        }, timeout=GUARD_TTL_SECONDS)
    except Exception:
        # The DB is safely finalized; recovery can still use the cached result.
        pass
