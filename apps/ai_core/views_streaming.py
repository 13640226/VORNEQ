"""V7-03: gestreamte Unterhaltungsantworten und Stop (ADR-0009).

Gleiche Gates wie ``conversation_message_view`` (gemeinsame Vorprüfung
``_prepare_message``): Feature-Flag Unterhaltungen, Authentifizierung, Actor-Policy,
CSRF, Recovery-Claim (gehostet), Body-/Eingabebudget, Eigentümerbindung. Zusätzlich
``streaming.enabled()``. Bezahlte Arbeit nur über ``prepare_paid_text`` (Ledger-Pflicht,
Not-Aus, Quote, ``paid_text_provider``/``BudgetedProvider``). Kein neuer SDK-Pfad.
"""
import logging

from django.db import DatabaseError
from django.http import Http404, StreamingHttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from apps.ai_core import streaming
from apps.ai_core.conversations import context, service
from apps.ai_core.conversations.repository import ConversationNotFound
from apps.ai_core.conversations.service import ConversationLimit
from apps.ai_core.engine.budget import BudgetExceeded
from apps.ai_core.error_contracts import budget_reason
from apps.ai_core.providers.exceptions import ProviderContextLimited, GatewayError
from apps.ai_core.views_conversations import (_enabled_user, _finish, _json, _may_ask, _prepare_message,
                                              may_start, persist_turn)
from apps.ai_core.views_global import global_ai_available, prepare_paid_text, run_global_pipeline

_log = logging.getLogger(__name__)


def _streams_knowledge(question, language):
    """Nur die unzitierte Wissensroute streamt Text; alles andere bleibt geprüft-vollständig."""
    from apps.ai_core.general_knowledge_policy import general_knowledge_candidate
    return general_knowledge_candidate(question, language)


def _single_event_stream(encoder, body, status):
    """Belegte/abgelehnte Antworten: ein abschließendes Ereignis nach voller Prüfung."""
    def events():
        yield encoder.encode("response.created", {"protocol": streaming.PROTOCOL_VERSION, "mode": "validated"})
        if status == 200:
            yield encoder.encode("response.completed", {"response": body})
        else:
            payload = {"error": body.get("error", "failed") if isinstance(body, dict) else "failed",
                       "http_status": status}
            for key in ("reason", "reason_code", "persisted"):
                if isinstance(body, dict) and key in body:
                    payload[key] = body[key]
            yield encoder.encode("response.failed", payload)
    return events()


def _response(generator):
    reply = StreamingHttpResponse(generator, content_type=streaming.CONTENT_TYPE)
    reply["Cache-Control"] = "private, no-store, no-transform"
    reply["X-Accel-Buffering"] = "no"           # Proxies/Render: nicht puffern
    reply["X-Content-Type-Options"] = "nosniff"
    return reply


@never_cache
@csrf_protect
@require_POST
def conversation_message_stream_view(request, conversation_id):
    if not streaming.enabled():
        raise Http404("streaming disabled")
    refusal, prepared = _prepare_message(request, conversation_id)
    if refusal is not None:
        return refusal                          # JSON: Ablehnung oder Replay (kein neuer Aufruf)
    user, conversation, question, language, request_id = prepared
    turns = context.prior_turns(conversation, question=question)
    try:
        _question, pending = service.begin_turn(user, conversation.id, question=question, request_id=request_id)
    except (DatabaseError, ConversationNotFound, ConversationLimit) as exc:
        _log.warning("ai_stream_begin_failed kind=%s", type(exc).__name__)
        code, status = {ConversationNotFound: ("not_found", 404), ConversationLimit: ("conversation_full", 409)}.get(
            type(exc), ("persistence_unavailable", 503))
        return _finish(request, request_id, {"error": code}, status)
    encoder = streaming.EventEncoder(request_id=request_id, conversation_id=conversation.id,
                                     response_id=pending.id)
    if not _streams_knowledge(question, language):
        # Belegter Pfad: unveränderte Pipeline (inkl. Zitatprüfung), dann ein Ereignis.
        search_question = context.search_question(conversation, question, language, exclude_message_id=pending.id)
        data, status, meta = run_global_pipeline(request, question, language, prior_turns=turns,
                                                 search_question=search_question)
        body, _persisted = persist_turn(request, user, conversation, pending, request_id, data, status,
                                        reservation=getattr(meta.get("budgeted"), "last_reservation", None),
                                        model=meta.get("model") or "")
        return _response(_single_event_stream(encoder, body, status))
    # Wissensroute: Ledger/Not-Aus/Quote/Provider VOR dem ersten Byte (Ablehnung = JSON).
    from apps.ai_core.chat_input_budget import global_budget
    from apps.ai_core.global_router import route_question
    from apps.ai_core.sanitization import UnsafePrompt, screen_and_redact
    route = route_question(question, language)
    try:
        clean = screen_and_redact(question, limit=global_budget().question_chars)
    except UnsafePrompt:
        body, _persisted = persist_turn(request, user, conversation, pending, request_id,
                                        {"error": "UNSUPPORTED_QUESTION"}, 422)
        return _json(body, 422)
    try:
        _shared, provider, _stage2, _output_budget, answer_chars = prepare_paid_text(request, turns)
    except BudgetExceeded as exc:
        data, status = {"error": "rate_limited", "reason": budget_reason(exc)}, 429
    except ProviderContextLimited:
        data, status = {"error": "context_limit_reached", "reason": "CONTEXT_LIMIT_EXCEEDED"}, 413
    except GatewayError:
        data, status = {"error": "provider_unavailable"}, 503
    else:
        data = None
    if data is not None:
        body, _persisted = persist_turn(request, user, conversation, pending, request_id, data, status)
        return _json(body, status)
    model = getattr(provider, "model", "") or getattr(getattr(provider, "inner", None), "model", "")

    def finalize(result, status):
        reservation = getattr(provider, "last_reservation", None)
        _body, persisted = persist_turn(request, user, conversation, pending, request_id, result, status,
                                        reservation=reservation, model=model)
        return persisted

    session = streaming.KnowledgeStream(
        provider=provider, question=clean, language=route.language, prior_turns=turns,
        pending_id=pending.id, encoder=encoder, max_answer_chars=answer_chars, finalize=finalize)
    return _response(session.events())


@never_cache
@csrf_protect
@require_POST
def conversation_message_cancel_view(request, conversation_id, message_id):
    """Stop für die EIGENE laufende Antwort (idempotent, ohne Redis, keine Kosten)."""
    user = _enabled_user(request)
    if user is None:
        return _json({"error": "authentication_required"}, 401)
    if not global_ai_available() or not streaming.enabled():
        raise Http404("streaming disabled")
    if not (_may_ask(user) and may_start(user)):
        return _json({"error": "forbidden"}, 403)
    from apps.ai_core.models import AIMessage
    if not AIMessage.objects.filter(pk=message_id, conversation_id=conversation_id,
                                    conversation__owner_id=user.pk).exists():
        return _json({"error": "not_found"}, 404)
    try:
        outcome = streaming.request_cancel(user, message_id)
    except DatabaseError:
        return _json({"error": "cancellation_unavailable"}, 503)
    if outcome is None:
        return _json({"error": "not_found"}, 404)
    state, final_status = outcome
    if state == "cancel_requested":
        # Lokal angefordert; bestätigt erst durch response.cancelled im Stream.
        return _json({"status": "cancel_requested", "confirmed": False}, 202)
    return _json({"status": "already_final", "message_status": final_status}, 200)
