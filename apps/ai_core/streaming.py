"""V7-03: Streaming, Stop und Wiederherstellung für Unterhaltungsantworten.

Architektur (ADR-0009):

* Transport: ``POST`` + ``fetch``-Streaming mit SSE-Rahmen (``text/event-stream``)
  über Djangos ``StreamingHttpResponse`` auf dem bestehenden WSGI/Gunicorn-Stack.
  Kein ASGI, kein zusätzlicher Dienst; ein Stream belegt einen Worker höchstens
  ``STREAM_DEADLINE_SECONDS`` (unter dem Worker-Timeout von 100 s) – wie bisher
  ein nicht gestreamter Aufruf.
* Nur die unzitierte Wissensroute (``model_knowledge``) streamt Text-Deltas. Belegte
  Antworten (Zitate, Abschnitte) werden erst nach der vollständigen Prüfung als
  ``response.completed`` gesendet – ungeprüfte Belegtexte werden nie angezeigt.
* Persistenz: Checkpoints des Teiltexts in der PENDING-Assistant-Nachricht
  (gebündelt, nie pro Token); Abschluss über ``service.complete_turn`` in EINER
  Transaktion mit dem Recovery-Guard (unverändert).
* Stop: ``error_code = "cancel_requested"`` an der eigenen PENDING-Nachricht
  (PostgreSQL, owner-gebunden, idempotent, ohne Redis). Der Stream prüft das Flag
  an jedem Checkpoint, schließt den Provider-Stream und speichert den Teiltext als
  ``cancelled``. Kosten ohne Usage-Ereignis bleiben im Ledger UNCERTAIN.
* Verbindungsabbruch des Browsers ist KEIN Stop: der Server liest den Provider-Stream
  (ohne weitere Ausgabe) bis zum Ende/Deadline weiter und speichert das Ergebnis, das
  nach Reload aus der Datenbank kommt – ohne neue bezahlte Anfrage.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

from django.conf import settings
from django.utils import timezone

_log = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
CONTENT_TYPE = "text/event-stream; charset=utf-8"
STREAM_DEADLINE_SECONDS = 85        # < Gunicorn-Timeout 100 s (gunicorn.conf.py)
CHECKPOINT_SECONDS = 1.5            # DB-Checkpoint/Stop-Prüfung höchstens so oft …
CHECKPOINT_CHARS = 2000             # … oder nach so vielen neuen Zeichen
HEARTBEAT_SECONDS = 10
MAX_DELTA_CHARS = 2048              # größere Deltas werden in mehrere Ereignisse geteilt
MAX_EVENT_BYTES = 64 * 1024         # Obergrenze je Ereignis (Missbrauchs-/Speicherschutz)
CANCEL_FLAG = "cancel_requested"

EVENT_TYPES = frozenset({
    "response.created", "response.started", "response.delta", "response.section",
    "response.citation", "response.usage", "response.completed", "response.incomplete",
    "response.cancelled", "response.failed", "heartbeat",
})
# Abbildung auf bestehende Nachrichtenstatus (keine Migration):
#   PENDING (+ Teiltext) = RUNNING/STREAMING; PENDING + cancel_requested = CANCEL_REQUESTED;
#   FAILED + "cancelled" = CANCELLED; FAILED + "output_limit_reached"/"stream_timeout" = INCOMPLETE;
#   COMPLETED; FAILED; UNCERTAIN = UNKNOWN.
PARTIAL_ERROR_CODES = frozenset({"cancelled", "output_limit_reached", "stream_timeout",
                                 "stream_interrupted", "emergency_stop"})


def enabled() -> bool:
    """Eigene Gates je Umgebung; Standard aus. Production nur mit eigenem Flag."""
    env = getattr(settings, "VORNEQ_ENV", None)
    if env in ("development", "staging"):
        return getattr(settings, "VORNEQ_AI_CHAT_STREAMING_ENABLED", False) is True
    if env == "production":
        return getattr(settings, "VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED", False) is True
    return False


class EventEncoder:
    """Fortlaufend nummerierte SSE-Rahmen; nur feste Felder, keine Secrets."""

    def __init__(self, *, request_id, conversation_id, response_id):
        self.ids = {
            "request_id": str(request_id) if request_id else None,
            "conversation_id": str(conversation_id),
            "response_id": str(response_id),
        }
        self.sequence = 0

    def encode(self, event_type, payload=None):
        if event_type not in EVENT_TYPES:
            raise ValueError("unknown stream event")
        self.sequence += 1
        body = {"type": event_type, "sequence_number": self.sequence, **self.ids,
                "timestamp": timezone.now().isoformat(timespec="milliseconds"),
                "payload": payload or {}}
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        if len(data.encode("utf-8")) > MAX_EVENT_BYTES:
            raise ValueError("stream event too large")
        return f"id: {self.sequence}\nevent: {event_type}\ndata: {data}\n\n".encode("utf-8")

    def deltas(self, text):
        for start in range(0, len(text), MAX_DELTA_CHARS):
            yield self.encode("response.delta", {"text": text[start:start + MAX_DELTA_CHARS]})


def request_cancel(user, message_id):
    """Idempotente Stop-Anforderung für die EIGENE laufende Antwort.

    Rückgabe ``("cancel_requested", None)`` oder ``("already_final", status)``;
    ``None`` für unbekannte/fremde Nachrichten (-> 404, keine Auskunft).
    """
    from apps.ai_core.models import AIMessage
    base = AIMessage.objects.filter(pk=message_id, role=AIMessage.ROLE_ASSISTANT,
                                    conversation__owner_id=user.pk, conversation__deleted_at__isnull=True)
    updated = base.filter(status=AIMessage.STATUS_PENDING).update(error_code=CANCEL_FLAG)
    if updated:
        return "cancel_requested", None
    status = base.values_list("status", flat=True).first()
    if status is None:
        return None
    return "already_final", status


def _cancel_requested(message_id):
    from apps.ai_core.models import AIMessage
    return AIMessage.objects.filter(pk=message_id, status=AIMessage.STATUS_PENDING,
                                    error_code=CANCEL_FLAG).exists()


def _checkpoint(message_id, text):
    """Teiltext sichern (nur solange PENDING); Fehler blockieren den Stream nicht."""
    from django.db import DatabaseError
    from apps.ai_core.models import AIMessage
    try:
        AIMessage.objects.filter(pk=message_id, status=AIMessage.STATUS_PENDING).update(content=text)
        return True
    except DatabaseError:
        _log.warning("ai_stream_checkpoint_failed")
        return False


class KnowledgeStream:
    """Zustandsmaschine eines gestreamten Wissens-Turns (ein bezahlter Aufruf)."""

    def __init__(self, *, provider, question, language, prior_turns, pending_id, encoder,
                 max_answer_chars, finalize, clock=time.monotonic):
        self.provider = provider
        self.question = question
        self.language = language
        self.prior_turns = tuple(prior_turns)
        self.pending_id = pending_id
        self.encoder = encoder
        self.max_answer_chars = max_answer_chars
        self.finalize = finalize          # callable(result_dict, http_status) -> persisted(bool)
        self.clock = clock
        self.text = []
        self.length = 0
        self.state = "running"
        self.finished = False

    # ---------------------------------------------------------------- helpers
    def _answer(self):
        return "".join(self.text)

    def _violation(self):
        from apps.ai_core.uncited_answer_guard import find_violation
        return find_violation(self._answer()) is not None

    def _result(self, outcome, reason=None):
        """(result, http_status) für ``complete_turn`` und den finalen Client-Body."""
        answer = self._answer()
        if outcome == "completed":
            from apps.ai_core.general_knowledge_runtime import validate_knowledge
            from apps.ai_core.providers.exceptions import ProviderInvalidResponse
            try:
                return validate_knowledge({"answer": answer, "language": self.language},
                                          language=self.language, max_answer_chars=self.max_answer_chars), 200
            except ProviderInvalidResponse:
                return {"error": "provider_unavailable", "reason_code": "invalid_provider_response"}, 503
        if outcome in PARTIAL_ERROR_CODES:
            status = {"cancelled": 499, "output_limit_reached": 503, "emergency_stop": 503}.get(outcome, 504)
            return {"error": outcome, "partial_answer": answer, "complete": False,
                    **({"reason": reason} if reason else {})}, status
        return {"error": outcome}, 503

    def _finish(self, outcome, reason=None):
        if self.finished:
            return None, None, False
        self.finished = True
        result, status = self._result(outcome, reason)
        persisted = self.finalize(result, status)
        return result, status, persisted

    # ------------------------------------------------------------------- run
    def events(self):
        """WSGI-Generator. Wird er vom Server geschlossen (Browser weg), läuft der
        Provider-Stream ohne Ausgabe bis zum Ende/Deadline weiter (siehe Modul-Doku)."""
        from apps.ai_core.providers.exceptions import (GatewayError, ProviderOutputLimited,
                                                        ProviderTimeout)
        deadline = self.clock() + STREAM_DEADLINE_SECONDS
        last_check = last_write = self.clock()
        since_check = 0
        detached = False
        stream = None
        outcome, reason = None, None
        try:
            yield self.encoder.encode("response.created", {"protocol": PROTOCOL_VERSION, "mode": "model_knowledge"})
            stream = self.provider.stream_knowledge(question=self.question, language=self.language,
                                                    prior_turns=self.prior_turns)
            for kind, value in stream:
                now = self.clock()
                if kind == "delta":
                    if self.length + len(value) > self.max_answer_chars:
                        outcome, reason = "output_limit_reached", "answer_chars"
                        break
                    self.text.append(value)
                    self.length += len(value)
                    since_check += len(value)
                    if self.length == len(value) and not detached:
                        yield self.encoder.encode("response.started", {})
                    if not detached:
                        yield from self.encoder.deltas(value)
                        last_write = now
                elif kind == "final":
                    if value.usage and not detached:
                        yield self.encoder.encode("response.usage", {"input_tokens": value.usage[0],
                                                                      "output_tokens": value.usage[1]})
                    if value.status == "completed":
                        outcome = "completed"
                    elif value.status == "incomplete" and value.reason == "max_output_tokens":
                        outcome, reason = "output_limit_reached", "max_output_tokens"
                    else:
                        outcome, reason = "provider_unavailable", value.reason
                    break
                elif not detached and now - last_write >= HEARTBEAT_SECONDS:
                    yield self.encoder.encode("heartbeat", {})
                    last_write = now
                if now >= deadline:
                    outcome, reason = "stream_timeout", "deadline"
                    break
                if now - last_check >= CHECKPOINT_SECONDS or since_check >= CHECKPOINT_CHARS:
                    last_check, since_check = now, 0
                    if self.text and self._violation():
                        outcome, reason = "provider_unavailable", "invalid_provider_response"
                        break
                    _checkpoint(self.pending_id, self._answer())
                    if _cancel_requested(self.pending_id):
                        outcome = "cancelled"
                        break
                    from apps.ai_ledger.service import emergency_stop_active
                    if emergency_stop_active() is True:
                        outcome, reason = "emergency_stop", "emergency_stop"
                        break
            if outcome is None:
                outcome, reason = "provider_unavailable", "stream_ended"
        except GeneratorExit:
            # Browser/Proxy hat die Verbindung geschlossen: kein Stop. Ohne weitere
            # Ausgabe zu Ende lesen (gleicher bezahlter Aufruf), dann speichern.
            detached = True
            outcome, reason = self._drain(stream, deadline)
            self._finish(outcome, reason)
            return
        except ProviderOutputLimited:
            outcome, reason = "output_limit_reached", "max_output_tokens"
        except ProviderTimeout:
            outcome = "provider_timeout"
        except GatewayError as exc:
            outcome = getattr(exc, "code", "provider_unavailable")
        finally:
            if stream is not None and not detached:
                stream.close()
        if outcome == "completed" and self._violation():
            outcome, reason = "provider_unavailable", "invalid_provider_response"
        result, status, persisted = self._finish(outcome, reason)
        if result is None:
            return
        if status == 200:
            yield self.encoder.encode("response.completed", {"response": dict(result, persisted=persisted)})
        elif outcome == "cancelled":
            yield self.encoder.encode("response.cancelled", {"confirmed": True, "persisted": persisted,
                                                             "cost": "uncertain", "partial": True})
        elif outcome in PARTIAL_ERROR_CODES:
            yield self.encoder.encode("response.incomplete", {"error": outcome, "reason": reason,
                                                              "persisted": persisted, "partial": True})
        else:
            yield self.encoder.encode("response.failed", {
                "error": result.get("error", "provider_unavailable"),
                "reason_code": result.get("reason_code", ""), "persisted": persisted})

    def _drain(self, stream, deadline):
        """Nach Verbindungsabbruch: Provider-Stream ohne Ausgabe weiterlesen."""
        from apps.ai_core.providers.exceptions import GatewayError
        if stream is None:
            return "stream_interrupted", "before_provider"
        last_check = self.clock()
        try:
            for kind, value in stream:
                now = self.clock()
                if kind == "delta":
                    if self.length + len(value) > self.max_answer_chars:
                        return "output_limit_reached", "answer_chars"
                    self.text.append(value)
                    self.length += len(value)
                elif kind == "final":
                    if value.status == "completed":
                        return "completed", None
                    if value.status == "incomplete" and value.reason == "max_output_tokens":
                        return "output_limit_reached", "max_output_tokens"
                    return "provider_unavailable", value.reason
                if now >= deadline:
                    return "stream_timeout", "deadline"
                if now - last_check >= CHECKPOINT_SECONDS:
                    last_check = now
                    _checkpoint(self.pending_id, self._answer())
                    if _cancel_requested(self.pending_id):
                        return "cancelled", None
            return "provider_unavailable", "stream_ended"
        except GatewayError as exc:
            return getattr(exc, "code", "provider_unavailable"), None
        finally:
            stream.close()


def new_response_id():
    return uuid.uuid4()
