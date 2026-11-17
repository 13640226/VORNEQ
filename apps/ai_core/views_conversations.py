"""Persistent conversation API V1 (docs/ai/PERSISTENT_CONVERSATION_V1_DESIGN.md).

Gates:
* every route: VORNEQ_AI_CONVERSATIONS_ENABLED, authenticated active user;
  data access is always owner-bound (foreign or unknown IDs -> 404).
* reading, renaming, archiving, deleting and exporting one's OWN history does
  not require the AI to be available (emergency stop, allowlist removal).
* starting a conversation and asking require the conversation pilot policy
  (VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY / _ALLOWED_USER_IDS), independent of
  the flag; asking also requires every existing Global AI gate, CSRF, the
  recovery claim, the ledger, and the unchanged citation validation.

Durable request state (asking): recovery claim (PostgreSQL guard) ->
begin_turn commits the question + a PENDING assistant turn -> pipeline (ledger
reserve/call/settle) -> complete_turn commits the final turn AND the guard
transition in ONE PostgreSQL transaction -> Redis cache best effort. PostgreSQL,
Redis and the separate ledger database never share a transaction.
Content is never logged.
"""
import json
import logging

from django.conf import settings
from django.db import DatabaseError
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST

from apps.ai_core import request_recovery
from apps.ai_core.conversations import context, repository, service
from apps.ai_core.conversations.repository import ConversationNotFound
from apps.ai_core.conversations.service import ConversationLimit, ConversationNotInTrash
from apps.ai_core.gateway import InputError, validate
from apps.ai_core.models import AIMessage
from apps.ai_core.production_policy import _ids, production_actor_allowed
from apps.ai_core.staging_policy import actor_allowed
from apps.ai_core.views_global import _strict_object, global_ai_available, run_global_pipeline

_log = logging.getLogger(__name__)
MAX_BODY = 2048


def _json(data, status=200):
    reply = JsonResponse(data, status=status)
    reply["Cache-Control"] = "private, no-store"
    return reply


def _enabled_user(request):
    if not getattr(settings, "VORNEQ_AI_CONVERSATIONS_ENABLED", False):
        raise Http404("conversations disabled")
    user = request.user
    return user if user.is_authenticated and user.is_active else None


def _body(request, allowed):
    if request.content_type != "application/json":
        raise ValueError("json_only")
    length = int(request.META.get("CONTENT_LENGTH", "0") or "0")
    if length < 0 or length > MAX_BODY or len(request.body) > MAX_BODY:
        raise ValueError("request_too_large")
    body = json.loads(request.body or b"{}", object_pairs_hook=_strict_object)
    if not isinstance(body, dict) or set(body) - set(allowed):
        raise ValueError("invalid_fields")
    return body


def may_start(user):
    """Conversation pilot policy (independent of the feature flag)."""
    if not (getattr(user, "is_authenticated", False) and getattr(user, "is_active", False)):
        return False
    policy = getattr(settings, "VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY", "allowlist")
    if policy == "authenticated":
        return True
    if policy == "allowlist":
        return user.pk in _ids(getattr(settings, "VORNEQ_AI_CONVERSATIONS_ALLOWED_USER_IDS", ""))
    return False


def _may_ask(user):
    if not global_ai_available():
        return False
    if settings.VORNEQ_ENV == "production":
        return production_actor_allowed(user)
    if settings.VORNEQ_ENV == "staging":
        return actor_allowed(user)
    return settings.VORNEQ_ENV == "development"


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def conversations_view(request):
    user = _enabled_user(request)
    if user is None:
        return _json({"error": "authentication_required"}, 401)
    if request.method == "GET":
        try:
            limit = int(request.GET.get("limit", "50"))
            offset = int(request.GET.get("offset", "0"))
        except ValueError:
            return _json({"error": "invalid_input"}, 400)
        items = repository.list_conversations(
            user, archived=request.GET.get("archived") == "1", trash=request.GET.get("trash") == "1",
            query=request.GET.get("q", ""), limit=limit, offset=offset)
        return _json({"conversations": [service.serialize_conversation(c) for c in items]})
    if not may_start(user):
        return _json({"error": "forbidden"}, 403)
    try:
        body = _body(request, {"language", "title"})
        conversation = service.create(user, language=body.get("language", "fa"), title=body.get("title", ""))
    except (ValueError, TypeError, UnicodeDecodeError):
        return _json({"error": "invalid_input"}, 400)
    except ConversationLimit:
        return _json({"error": "conversation_limit"}, 409)
    return _json({"conversation": service.serialize_conversation(conversation)}, 201)


@never_cache
@csrf_protect
@require_http_methods(["GET", "PATCH", "DELETE"])
def conversation_detail_view(request, conversation_id):
    user = _enabled_user(request)
    if user is None:
        return _json({"error": "authentication_required"}, 401)
    try:
        if request.method == "GET":
            try:
                after = int(request.GET.get("after", "0"))
            except ValueError:
                return _json({"error": "invalid_input"}, 400)
            conversation, messages = repository.list_messages(user, conversation_id, after_sequence=after,
                                                              limit=1000)
            return _json({"conversation": service.serialize_conversation(conversation),
                          "messages": [service.serialize_message(m) for m in messages]})
        if request.method == "PATCH":
            try:
                body = _body(request, {"title", "archived"})
                conversation = None
                if "title" in body:
                    if not isinstance(body["title"], str):
                        raise ValueError("title")
                    conversation = service.rename(user, conversation_id, body["title"])
                if "archived" in body:
                    if not isinstance(body["archived"], bool):
                        raise ValueError("archived")
                    conversation = service.set_archived(user, conversation_id, body["archived"])
                if conversation is None:
                    raise ValueError("nothing to change")
            except (ValueError, TypeError, UnicodeDecodeError):
                return _json({"error": "invalid_input"}, 400)
            return _json({"conversation": service.serialize_conversation(conversation)})
        if request.GET.get("permanent") == "1":
            service.delete_permanently(user, conversation_id)
            return _json({"deleted": True})
        conversation = service.move_to_trash(user, conversation_id)
        return _json({"conversation": service.serialize_conversation(conversation)})
    except ConversationNotFound:
        return _json({"error": "not_found"}, 404)
    except ConversationNotInTrash:
        return _json({"error": "not_in_trash"}, 409)


@never_cache
@csrf_protect
@require_POST
def conversation_restore_view(request, conversation_id):
    user = _enabled_user(request)
    if user is None:
        return _json({"error": "authentication_required"}, 401)
    try:
        conversation = service.restore(user, conversation_id)
    except ConversationNotFound:
        return _json({"error": "not_found"}, 404)
    return _json({"conversation": service.serialize_conversation(conversation)})


@never_cache
@require_http_methods(["GET"])
def conversation_export_view(request, conversation_id):
    user = _enabled_user(request)
    if user is None:
        return _json({"error": "authentication_required"}, 401)
    try:
        data = service.export(user, conversation_id)
    except ConversationNotFound:
        return _json({"error": "not_found"}, 404)
    reply = _json(data)
    reply["Content-Disposition"] = f'attachment; filename="vorneq-conversation-{conversation_id}.json"'
    return reply


def _finish(request, request_id, data, status):
    if request_id is not None:
        try:
            request_recovery.finish(request, request_id, http_status=status, response=data)
        except (request_recovery.RecoveryUnavailable, request_recovery.RecoveryNotFound):
            _log.warning("ai_chat_recovery_result_unavailable")
    return _json(data, status)


@never_cache
@csrf_protect
@require_POST
def conversation_message_view(request, conversation_id):
    user = _enabled_user(request)
    if user is None:
        return _json({"error": "authentication_required"}, 401)
    if not global_ai_available():
        raise Http404("Global AI disabled")
    if not (_may_ask(user) and may_start(user)):
        return _json({"error": "forbidden"}, 403)
    # Hosted environments may invoke a billable provider. A durable recovery
    # claim and request UUID are mandatory BEFORE any provider/ledger work.
    # Development retains the existing offline fake-provider test path.
    if settings.VORNEQ_ENV in ("production", "staging") and not request_recovery.enabled():
        return _json({"error": "recovery_unavailable"}, 503)
    try:
        body = _body(request, {"question", "language"})
        question, language = validate(body.get("question"), body.get("language", "fa"))
    except ValueError as exc:
        code = str(exc) if str(exc) in ("json_only", "request_too_large", "invalid_fields") else "invalid_input"
        return _json({"error": code}, {"json_only": 415, "request_too_large": 413}.get(code, 400))
    except (TypeError, UnicodeDecodeError, InputError):
        return _json({"error": "invalid_input"}, 400)
    try:
        conversation = repository.get_conversation(user, conversation_id)
        service.ensure_capacity(conversation)
    except ConversationNotFound:
        return _json({"error": "not_found"}, 404)
    except ConversationLimit:
        return _json({"error": "conversation_full"}, 409)
    request_id = None
    if request_recovery.enabled():
        request_id = request.headers.get("X-VQ-Request-ID", "")
        try:
            # The conversation is part of the fingerprint: one request ID can
            # never be replayed into a different conversation.
            prior = request_recovery.claim(request, request_id,
                                           question=f"{conversation.id}\u241f{question}", language=language)
        except request_recovery.RecoveryInvalid:
            return _json({"error": "invalid_request_id"}, 400)
        except request_recovery.RecoveryNotFound:
            return _json({"error": "not_found"}, 404)
        except request_recovery.RecoveryConflict:
            return _json({"error": "request_id_conflict"}, 409)
        except request_recovery.RecoveryUnavailable:
            return _json({"error": "recovery_unavailable"}, 503)
        if prior["status"] in ("completed", "failed"):
            return _json(prior["response"], prior["http_status"])
        if prior["status"] != "claimed":
            # Redis no longer holds the result: PostgreSQL is authoritative.
            stored = (AIMessage.objects.filter(request_id=request_id, conversation=conversation,
                                               conversation__owner_id=user.pk)
                      .exclude(status=AIMessage.STATUS_PENDING).first())
            if stored is not None:
                body, status = service.stored_response(stored, conversation)
                return _json(body, status)
            return _json({"status": prior["status"], "request_id": request_id},
                         202 if prior["status"] == "running" else 409)
    turns = context.prior_turns(conversation)
    # 1) Durable request state BEFORE any quota, retrieval, ledger or provider work.
    try:
        _question_message, pending = service.begin_turn(user, conversation.id, question=question,
                                                        request_id=request_id)
    except (DatabaseError, ConversationNotFound, ConversationLimit) as exc:
        _log.warning("ai_conversation_begin_failed kind=%s", type(exc).__name__)
        code, status = {ConversationNotFound: ("not_found", 404), ConversationLimit: ("conversation_full", 409)}.get(
            type(exc), ("persistence_unavailable", 503))
        return _finish(request, request_id, {"error": code}, status)
    # 2) Existing pipeline: route, throttle, ledger reserve -> provider -> settle, validation.
    try:
        search_question = context.search_question(conversation, question, language, exclude_message_id=pending.id)
        data, status, meta = run_global_pipeline(request, question, language, prior_turns=turns,
                                                 search_question=search_question)
    except BaseException:
        # Interrupted after the durable record: the turn stays PENDING and the
        # guard stays running (no replay); reconciliation marks it uncertain.
        _log.warning("ai_conversation_pipeline_interrupted")
        raise
    reservation = getattr(meta.get("budgeted"), "last_reservation", None)
    # 3) Final turn + guard transition in ONE PostgreSQL transaction.
    persisted = False
    try:
        service.complete_turn(
            user, pending.id, result=data, http_status=status,
            reservation_id=getattr(reservation, "id", None), model=meta.get("model") or "",
            finalize_guard=((lambda: request_recovery.finalize_guard_in_transaction(request, request_id))
                            if request_id else None))
        persisted = True
    except (DatabaseError, ConversationNotFound):
        # The provider may have been billed. Never claim persistence; never retry.
        _log.warning("ai_conversation_persist_failed")
    body = dict(data, conversation_id=str(conversation.id), persisted=persisted) if isinstance(data, dict) else data
    if request_id is not None:
        if persisted:
            request_recovery.cache_result_best_effort(request, request_id, http_status=status, response=body)
        else:
            # PostgreSQL unavailable: keep the 15-minute Redis result so the
            # answer is not lost before reconciliation (not durable storage).
            try:
                request_recovery.finish(request, request_id, http_status=status, response=body)
            except (request_recovery.RecoveryUnavailable, request_recovery.RecoveryNotFound):
                _log.warning("ai_chat_recovery_result_unavailable")
    return _json(body, status)
