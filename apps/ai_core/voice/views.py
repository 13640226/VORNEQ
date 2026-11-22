"""Voice foundation endpoints (mock-only). Responses use local helpers, not shared ones."""
from __future__ import annotations

import json
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.ai_core.models import AIConversation
from .config import (MAX_AUDIO_CHUNK_BYTES, MAX_BODY_BYTES, MAX_TEXT_CHARS,
                     emergency_stop_active, load_config)
from .provider import get_provider
from .store import EventLimit, SessionBusy, StoreFull, get_store


def _headers(response):
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _ok(data, status=200):
    return _headers(JsonResponse(data, status=status))


def _refuse(code, status, retry_after=None):
    body = {"error": code}
    if retry_after is not None:
        body["retry_after_seconds"] = retry_after
    response = _headers(JsonResponse(body, status=status))
    if retry_after is not None:
        response["Retry-After"] = str(retry_after)
    return response


def _gate(request):
    """Return (config, None) or (None, refusal). Order: auth, cleanup, allowlist, stop."""
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return None, _refuse("authentication_required", 401)
    stopped = emergency_stop_active()
    if stopped:
        get_store().clear()  # Emergency Stop ends every live mock session
    config = load_config()
    if (config is None or not getattr(user, "is_active", False)
            or user.pk not in config.allowed_user_ids):
        return None, _refuse("unavailable", 404)  # same answer for every denial reason
    if stopped:
        return None, _refuse("emergency_stop", 503)
    return config, None


def _json_body(request):
    """Parse a bounded JSON object. Returns (dict, None) or (None, refusal)."""
    declared = request.META.get("CONTENT_LENGTH", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return None, _refuse("payload_too_large", 413)
    raw = request.read(MAX_BODY_BYTES + 1)
    if len(raw) > MAX_BODY_BYTES:
        return None, _refuse("payload_too_large", 413)
    if not raw:
        return {}, None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, _refuse("invalid_request", 400)
    if not isinstance(data, dict):
        return None, _refuse("invalid_request", 400)
    return data, None


def _canonical_uuid(value):
    if not isinstance(value, str) or len(value) != 36:
        return None
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return None
    return str(parsed) if str(parsed) == value else None


def _conversation_state(user, conversation_id):
    """'ok', 'missing' (absent, foreign or trashed) or 'archived'."""
    conversation = AIConversation.objects.filter(
        pk=conversation_id, owner=user, deleted_at__isnull=True).first()
    if conversation is None:
        return "missing"
    return "archived" if conversation.archived_at is not None else "ok"


@require_POST
def voice_session_create_view(request):
    config, refusal = _gate(request)
    if refusal:
        return refusal
    body, refusal = _json_body(request)
    if refusal:
        return refusal
    if set(body) - {"conversation_id"}:
        return _refuse("invalid_request", 400)
    conversation_id = None
    if "conversation_id" in body:
        conversation_id = _canonical_uuid(body["conversation_id"])
        if conversation_id is None:
            return _refuse("invalid_request", 400)
        state = _conversation_state(request.user, conversation_id)
        if state == "missing":
            return _refuse("not_found", 404)
        if state == "archived":
            return _refuse("conversation_archived", 409)
    try:
        session = get_store().acquire(request.user.pk, conversation_id, config.ttl_seconds)
    except SessionBusy as busy:
        return _refuse("session_active", 429, busy.retry_after)
    except StoreFull as full:
        return _refuse("capacity", 503, full.retry_after)
    return _ok({"session_id": session.id, "expires_in_seconds": config.ttl_seconds,
                "provider": get_provider().name, "mock": True}, 201)


def _validate_event(body):
    """Return (type, size) or None. Strict types, exact keys, bounded sizes."""
    kind = body.get("type")
    if kind == "text":
        text = body.get("text")
        if set(body) != {"type", "text"} or not isinstance(text, str) or not 1 <= len(text) <= MAX_TEXT_CHARS:
            return None
        return kind, len(text)
    if kind == "audio_chunk":
        size = body.get("size")
        if set(body) != {"type", "size"} or type(size) is not int or not 1 <= size <= MAX_AUDIO_CHUNK_BYTES:
            return None
        return kind, size
    return None


@require_POST
def voice_event_view(request, session_id):
    config, refusal = _gate(request)
    if refusal:
        return refusal
    body, refusal = _json_body(request)
    if refusal:
        return refusal
    event = _validate_event(body)
    if event is None:
        return _refuse("invalid_request", 400)
    store, sid = get_store(), str(session_id)
    session = store.get(sid, request.user.pk)
    if session is None:
        return _refuse("not_found", 404)
    if session.conversation_id and _conversation_state(request.user, session.conversation_id) != "ok":
        store.release(sid, request.user.pk)  # archived or removed mid-session
        return _refuse("conversation_archived", 409)
    try:
        if store.record_event(sid, request.user.pk) is None:
            return _refuse("not_found", 404)
    except EventLimit:
        return _refuse("event_limit", 429)
    return _ok({"event": get_provider().respond(*event)})


@require_POST
def voice_session_close_view(request, session_id):
    config, refusal = _gate(request)
    if refusal:
        return refusal
    if not get_store().release(str(session_id), request.user.pk):
        return _refuse("not_found", 404)  # unknown, expired, foreign or already closed
    return _ok({"closed": True})
