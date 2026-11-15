"""Staging-only idempotent AI request recovery.

One POST may claim a UUID once per Redis cache retention window. Every later
request with that UUID reads status or the cached result, never calls the model.
This is a bounded safety guard, not an exactly-once guarantee after Redis loss.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

from django.conf import settings
from django.core.cache import cache

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


def _snapshot(request, request_id):
    _require_shared_redis()
    user_id, session_digest = _identity(request)
    guard_key, result_key = _keys(request_id)
    record = _checked_get(guard_key)
    if not isinstance(record, dict):
        raise RecoveryNotFound("request not found")
    if record.get("actor") != user_id or not hmac.compare_digest(
        str(record.get("session", "")), session_digest
    ):
        raise RecoveryNotFound("request not owned by session")
    if record.get("state") not in ("running", "finished"):
        raise RecoveryUnavailable("malformed recovery guard")
    result = _checked_get(result_key)
    if result is not None:
        if (not isinstance(result, dict) or result.get("status") not in ("completed", "failed")
                or not isinstance(result.get("http_status"), int)
                or not isinstance(result.get("response"), dict)):
            raise RecoveryUnavailable("malformed response cache")
        return result, record
    if record["state"] == "finished":
        return {"status": "expired"}, record
    age = max(0, int(time.time()) - int(record.get("created_at", 0)))
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
    try:
        created = cache.add(guard_key, record, timeout=GUARD_TTL_SECONDS)
    except Exception as exc:
        raise RecoveryUnavailable("Redis atomic claim failed") from exc
    if created:
        return {"status": "claimed"}
    snapshot, original = _snapshot(request, request_id)
    if not hmac.compare_digest(str(original.get("fingerprint", "")), fingerprint):
        raise RecoveryConflict("same request id used for different content")
    return snapshot


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
    original = _checked_get(guard_key)
    if not isinstance(original, dict):
        raise RecoveryUnavailable("claim disappeared")
    actor, session = _identity(request)
    if original.get("actor") != actor or original.get("session") != session:
        raise RecoveryNotFound("different principal")
    if not isinstance(response, dict) or not 100 <= http_status <= 599:
        raise RecoveryUnavailable("invalid result")
    value = {
        "status": "completed" if 200 <= http_status < 400 else "failed",
        "http_status": http_status,
        "response": response,
    }
    try:
        # Persist result FIRST: a crash before the guard update remains recoverable.
        cache.set(result_key, value, timeout=RESPONSE_TTL_SECONDS)
        if _checked_get(result_key) != value:
            raise RecoveryUnavailable("Redis result write not confirmed")
        finished = dict(original, state="finished")
        cache.set(guard_key, finished, timeout=GUARD_TTL_SECONDS)
        if _checked_get(guard_key) != finished:
            raise RecoveryUnavailable("Redis guard write not confirmed")
    except RecoveryUnavailable:
        raise
    except Exception as exc:
        raise RecoveryUnavailable("Redis result write failed") from exc
