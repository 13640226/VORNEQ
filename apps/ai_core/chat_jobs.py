"""V7-03.1a: dauerhafte Antwort-Jobs auf PostgreSQL (ADR-0010).

Bausteine (keine HTTP-Endpunkte, kein SSE – das ist V7-03.1b):

* **Durable Queue:** ``AIChatJob`` in PostgreSQL. ``claim`` nutzt
  ``SELECT … FOR UPDATE SKIP LOCKED``; Redis wird nicht benötigt.
* **Zustandsmaschine:** ``TRANSITIONS``; jede Änderung ist ein bedingtes UPDATE
  (``status`` alt → neu), nie ein blindes ``save()``.
* **Lease + Fencing:** jeder Claim erhöht ``fencing_token``. Schreibzugriffe eines
  Workers verlangen ``worker_id`` + ``fencing_token`` + gültige Lease; sonst
  ``StaleLease`` (veralteter Worker ändert nichts mehr).
* **Idempotenz:** ``request_id`` (eindeutig) ist an Eigentümer, Unterhaltung und
  Fingerabdruck (Frage + Sprache) gebunden; gleiche ID + anderer Inhalt -> Konflikt.
* **Kapazität:** global und je Nutzer, atomar unter einer Transaktions-Sperre
  (PostgreSQL ``pg_advisory_xact_lock``), Werte aus der Konfiguration.
* **Ledger:** bezahlt wird nur über ``prepare_paid_text_for_actor`` →
  ``BudgetedProvider.stream_knowledge`` (Reservierung direkt vor dem Aufruf, genau
  eine Abrechnung). ``ledger_state`` ist vom Job-Status unabhängig. Kein
  automatischer Retry eines möglicherweise gesendeten Aufrufs.
* **Checkpoints:** Teiltext in der PENDING-``AIMessage`` (keine Kopie im Job),
  ``checkpoint_sequence``/``checkpoint_chars`` monoton im Job.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, connection, transaction
from django.db.models import F
from django.utils import timezone

from apps.ai_core.models import AIChatJob, AIMessage

_log = logging.getLogger(__name__)

J = AIChatJob
TRANSITIONS = {
    J.QUEUED: {J.CLAIMED, J.CANCELLED, J.FAILED},
    J.CLAIMED: {J.RUNNING, J.CANCEL_REQUESTED, J.FAILED, J.UNCERTAIN},
    J.RUNNING: {J.CANCEL_REQUESTED, J.COMPLETED, J.INCOMPLETE, J.FAILED, J.UNCERTAIN},
    J.CANCEL_REQUESTED: {J.CANCELLED, J.COMPLETED, J.INCOMPLETE, J.FAILED, J.UNCERTAIN},
}
for _terminal in J.TERMINAL:
    TRANSITIONS[_terminal] = set()

ADMISSION_LOCK = (0x564F, 0x43484A)       # pg_advisory_xact_lock: Kapazität serialisieren
DEFAULT_MAX_ACTIVE_GLOBAL = 32
DEFAULT_MAX_ACTIVE_PER_USER = 2
DEFAULT_LEASE_SECONDS = 120          # > Provider-Timeout (60 s) + Checkpoint-Abstand
DEFAULT_DEADLINE_SECONDS = 300
CHECKPOINT_CHARS = 2000
CHECKPOINT_SECONDS = 1.5


class ChatJobError(Exception):
    code = "chat_job_error"

    def __init__(self, message="", *, code=None):
        super().__init__(message or self.code)
        if code:
            self.code = code


class JobsDisabled(ChatJobError):
    code = "chat_jobs_disabled"


class RequestConflict(ChatJobError):
    code = "request_id_conflict"


class CapacityExceeded(ChatJobError):
    code = "capacity_exceeded"


class InvalidTransition(ChatJobError):
    code = "invalid_transition"


class StaleLease(ChatJobError):
    """Lease abgelaufen oder von einem neueren Claim (höherer Fencing-Token) abgelöst."""
    code = "stale_lease"


@dataclass(frozen=True)
class Lease:
    job_id: uuid.UUID
    worker_id: str
    token: int


# ------------------------------------------------------------------ Konfiguration
def enabled() -> bool:
    env = getattr(settings, "VORNEQ_ENV", None)
    if env in ("development", "staging"):
        return getattr(settings, "VORNEQ_AI_CHAT_JOBS_ENABLED", False) is True
    if env == "production":
        return getattr(settings, "VORNEQ_AI_CHAT_JOBS_PRODUCTION_ENABLED", False) is True
    return False


def _positive(name, default, maximum):
    raw = getattr(settings, name, "")
    if isinstance(raw, int) and not isinstance(raw, bool):
        value = raw
    elif isinstance(raw, str) and raw.isascii() and raw.isdecimal() and len(raw) <= 6:
        value = int(raw)
    else:
        return default
    return value if 1 <= value <= maximum else default


def max_active_global():
    return _positive("VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_GLOBAL", DEFAULT_MAX_ACTIVE_GLOBAL, 100_000)


def max_active_per_user():
    return _positive("VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_PER_USER", DEFAULT_MAX_ACTIVE_PER_USER, 1_000)


def lease_seconds():
    return _positive("VORNEQ_AI_CHAT_JOB_LEASE_SECONDS", DEFAULT_LEASE_SECONDS, 3600)


def deadline_seconds():
    return _positive("VORNEQ_AI_CHAT_JOB_DEADLINE_SECONDS", DEFAULT_DEADLINE_SECONDS, 3600)


OPERATION = "chat.answer.v1"
# Namensraum für die interne Nachrichten-Request-ID (uuid5, nie gleich einer Client-UUIDv4).
MESSAGE_REQUEST_NAMESPACE = uuid.UUID("7f3d6a1e-9c4b-5e2f-8a17-3b6c0d9e4f21")


def fingerprint(owner_id, conversation_id, question, language, operation=OPERATION):
    """Bindet eine Request-ID an Eigentümer, Unterhaltung, Operation, Sprache und Inhalt."""
    raw = f"{operation}␟{owner_id}␟{conversation_id}␟{language}␟{question}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def message_request_id(owner_id, request_id):
    """Eigentümer-gebundene, kollisionsfreie Request-ID für die AIMessage (global eindeutig)."""
    return uuid.uuid5(MESSAGE_REQUEST_NAMESPACE, f"{OPERATION}:{owner_id}:{request_id}")


# ----------------------------------------------------------------------- Enqueue
def _admission_lock():
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", list(ADMISSION_LOCK))


def enqueue(user, conversation_id, *, question, language, request_id):
    """Frage + PENDING-Antwort + QUEUED-Job in EINER Transaktion (keine Reservierung).

    Rückgabe ``(job, created)``. Idempotenz ist **je Eigentümer**: gleiche
    ``request_id`` + gleicher Fingerabdruck liefert den bestehenden Job (auch nach
    Abschluss oder Fehler – kein zweiter Job, keine zweite Reservierung); gleiche ID +
    anderer Inhalt/Unterhaltung -> ``RequestConflict``. Die ID eines anderen Nutzers
    ist ein eigener Namensraum: kein Konflikt, keine Auskunft über fremde Jobs.
    """
    from apps.ai_core.conversations import repository, service
    if not enabled():
        raise JobsDisabled()
    if type(request_id) is not uuid.UUID or request_id.version != 4:
        raise ChatJobError(code="invalid_request_id")
    if language not in ("fa", "de", "en") or not isinstance(question, str) or not question.strip():
        raise ChatJobError(code="invalid_input")
    digest = fingerprint(user.pk, conversation_id, question, language)
    with transaction.atomic():
        _admission_lock()
        existing = J.objects.filter(owner=user, request_id=request_id).first()
        if existing is not None:
            if existing.conversation_id != conversation_id or existing.fingerprint != digest:
                raise RequestConflict()
            return existing, False
        conversation = repository.get_conversation(user, conversation_id, for_update=True)
        active = J.objects.filter(status__in=J.ACTIVE)
        if active.count() >= max_active_global():
            raise CapacityExceeded(code="global_capacity_exceeded")
        if active.filter(owner=user).count() >= max_active_per_user():
            raise CapacityExceeded(code="user_capacity_exceeded")
        question_message, pending = service.begin_turn(
            user, conversation.id, question=question, request_id=message_request_id(user.pk, request_id))
        job = J.objects.create(owner=user, conversation=conversation, user_message=question_message,
                               assistant_message=pending, request_id=request_id, fingerprint=digest,
                               language=language)
    _notify()
    return job, True


def _notify():
    """Weckhinweis für Worker (Redis, optional). Die Queue bleibt PostgreSQL."""
    from django.core.cache import cache
    try:
        cache.set("vorneq:chat-jobs:wakeup", "1", timeout=30)
    except Exception as exc:  # Redis nicht verfügbar: Job ist trotzdem dauerhaft gespeichert
        _log.warning("ai_chat_job_wakeup_unavailable kind=%s", type(exc).__name__)


# ------------------------------------------------------------------------- Claim
def claim(worker_id, *, now=None):
    """Nächsten QUEUED-Job atomar übernehmen; ``None`` wenn keiner frei ist."""
    if not isinstance(worker_id, str) or not 1 <= len(worker_id) <= 64:
        raise ChatJobError(code="invalid_worker_id")
    now = now or timezone.now()
    from apps.ai_ledger.service import emergency_stop_active
    if not enabled() or emergency_stop_active() is True:
        # Not-Aus oder geschlossenes Gate: nichts übernehmen (Jobs bleiben QUEUED).
        return None
    with transaction.atomic():
        qs = J.objects.filter(status=J.QUEUED).order_by("created_at")
        if connection.features.has_select_for_update_skip_locked:
            qs = qs.select_for_update(skip_locked=True)
        else:
            qs = qs.select_for_update()
        job = qs.first()
        if job is None:
            return None
        token = job.fencing_token + 1
        updated = J.objects.filter(pk=job.pk, status=J.QUEUED, fencing_token=job.fencing_token).update(
            status=J.CLAIMED, worker_id=worker_id, fencing_token=token, attempts=F("attempts") + 1,
            claimed_at=now, heartbeat_at=now, lease_until=now + timedelta(seconds=lease_seconds()),
            updated_at=now)
        if updated != 1:
            return None
    return Lease(job.pk, worker_id, token)


def _fenced(lease, *, now=None, statuses=None):
    now = now or timezone.now()
    qs = J.objects.filter(pk=lease.job_id, worker_id=lease.worker_id, fencing_token=lease.token,
                          lease_until__gt=now)
    return qs.filter(status__in=statuses or (J.CLAIMED, J.RUNNING, J.CANCEL_REQUESTED))


def heartbeat(lease, *, now=None):
    """Lease verlängern; ``StaleLease`` wenn Lease abgelaufen oder abgelöst."""
    now = now or timezone.now()
    updated = _fenced(lease, now=now).update(heartbeat_at=now, updated_at=now,
                                             lease_until=now + timedelta(seconds=lease_seconds()))
    if updated != 1:
        raise StaleLease()
    return J.objects.values_list("status", flat=True).get(pk=lease.job_id)


def transition(lease, target, *, now=None, **fields):
    """Fencing-geschützter Zustandswechsel; prüft die erlaubten Übergänge."""
    now = now or timezone.now()
    with transaction.atomic():
        job = _fenced(lease, now=now).select_for_update().first()
        if job is None:
            raise StaleLease()
        if target not in TRANSITIONS[job.status]:
            raise InvalidTransition(f"{job.status}->{target}")
        updates = {"status": target, "updated_at": now, **fields}
        if target in J.TERMINAL:
            updates.update(finished_at=now, lease_until=None)
        if target == J.RUNNING:
            updates.setdefault("started_at", now)
        J.objects.filter(pk=job.pk, fencing_token=lease.token, status=job.status).update(**updates)
        return target


def checkpoint(lease, text, sequence, *, now=None):
    """Teiltext sichern (PENDING-Nachricht) und Sequenz monoton erhöhen – fencing-geschützt."""
    now = now or timezone.now()
    with transaction.atomic():
        job = _fenced(lease, now=now, statuses=(J.RUNNING, J.CANCEL_REQUESTED)).select_for_update().first()
        if job is None:
            raise StaleLease()
        if sequence <= job.checkpoint_sequence:
            return job.status                     # Wiederholung/Out-of-order: ignorieren
        AIMessage.objects.filter(pk=job.assistant_message_id, status=AIMessage.STATUS_PENDING).update(content=text)
        J.objects.filter(pk=job.pk, fencing_token=lease.token).update(
            checkpoint_sequence=sequence, checkpoint_chars=len(text), heartbeat_at=now, updated_at=now,
            lease_until=now + timedelta(seconds=lease_seconds()))
        return job.status


def bind_ledger(lease, *, reservation_id=None, ledger_state=None, request_sent=None, now=None):
    """Ledger-Bindung am Job festhalten (fencing-geschützt, unabhängig vom Status)."""
    fields = {}
    if reservation_id is not None:
        fields["reservation_id"] = reservation_id
    if ledger_state is not None:
        fields["ledger_state"] = ledger_state
    if request_sent is not None:
        fields["provider_request_sent"] = bool(request_sent)
    if not fields:
        return
    updated = _fenced(lease, now=now).update(**fields)
    if updated != 1:
        raise StaleLease()


# ------------------------------------------------------------------------ Cancel
def request_cancel(user, job_id):
    """Eigener Job: QUEUED -> CANCELLED (nichts gesendet); laufend -> CANCEL_REQUESTED.

    CANCELLED für laufende Jobs setzt nur der Worker nach bestätigtem Stopp.
    Rückgabe: neuer bzw. unveränderter Status; ``None`` für fremde/unbekannte Jobs.
    """
    now = timezone.now()
    with transaction.atomic():
        job = J.objects.select_for_update().filter(pk=job_id, owner_id=user.pk).first()
        if job is None:
            return None
        if job.status == J.QUEUED:
            J.objects.filter(pk=job.pk, status=J.QUEUED).update(status=J.CANCELLED, error_code="cancelled",
                                                              finished_at=now, updated_at=now)
            AIMessage.objects.filter(pk=job.assistant_message_id, status=AIMessage.STATUS_PENDING).update(
                status=AIMessage.STATUS_FAILED, error_code="cancelled", http_status=499, finalized_at=now)
            return J.CANCELLED
        if job.status in (J.CLAIMED, J.RUNNING):
            J.objects.filter(pk=job.pk, status=job.status).update(status=J.CANCEL_REQUESTED, updated_at=now)
            AIMessage.objects.filter(pk=job.assistant_message_id, status=AIMessage.STATUS_PENDING).update(
                error_code="cancel_requested")
            return J.CANCEL_REQUESTED
        return job.status


# -------------------------------------------------------------------- Ausführung
OUTCOME_STATUS = {
    "completed": J.COMPLETED, "output_limit_reached": J.INCOMPLETE, "stream_timeout": J.INCOMPLETE,
    "cancelled": J.CANCELLED, "emergency_stop": J.INCOMPLETE, "provider_timeout": J.UNCERTAIN,
}


def run_claimed(lease, *, provider_factory=None, clock=None):
    """Einen übernommenen Job ausführen (genau ein bezahlter Aufruf, kein Retry).

    ``provider_factory(job)`` liefert den Provider; Standard ist der gemeinsame Pfad
    ``prepare_paid_text_for_actor`` (Ledger-Pflicht, Not-Aus, Quote, BudgetedProvider).
    Rückgabe: finaler Job-Status oder ``None``, wenn die Lease verloren ging.
    """
    import time
    from apps.ai_core.conversations import context
    from apps.ai_core.engine.budget import BudgetExceeded
    from apps.ai_core.error_contracts import budget_reason
    from apps.ai_core.budgeted_provider import BudgetedProvider
    from apps.ai_core.providers.exceptions import GatewayError
    clock = clock or time.monotonic
    job = J.objects.select_related("owner", "conversation", "user_message", "assistant_message").get(pk=lease.job_id)
    if job.conversation is None or job.user_message is None or job.assistant_message is None:
        return _finish(lease, job, J.FAILED, {"error": "conversation_unavailable"}, 404)
    if job.conversation.deleted_at is not None:
        return _finish(lease, job, J.FAILED, {"error": "not_found"}, 404)
    question = job.user_message.content
    try:
        status = transition(lease, J.RUNNING)
    except InvalidTransition:
        status = J.objects.values_list("status", flat=True).get(pk=job.pk)
    except StaleLease:
        _log.warning("ai_chat_job_lease_lost job=%s", job.pk)
        return None
    if status == J.CANCEL_REQUESTED or J.objects.filter(pk=job.pk, status=J.CANCEL_REQUESTED).exists():
        # Vor jedem Aufruf gestoppt: nichts gesendet, keine Reservierung.
        return _finish(lease, job, J.CANCELLED, {"error": "cancelled", "partial_answer": "",
                                                 "complete": False}, 499)
    from apps.ai_ledger.service import emergency_stop_active
    if emergency_stop_active() is True:
        return _finish(lease, job, J.FAILED, {"error": "rate_limited", "reason": "EMERGENCY_STOP_ACTIVE"}, 429)
    turns = context.prior_turns(job.conversation, question=question)
    try:
        provider = (provider_factory or _default_provider)(job, turns)
    except BudgetExceeded as exc:
        return _finish(lease, job, J.FAILED, {"error": "rate_limited", "reason": budget_reason(exc)}, 429)
    except GatewayError as exc:
        return _finish(lease, job, J.FAILED, {"error": getattr(exc, "code", "provider_unavailable")}, 503)
    # COR-03: Korrelations-ID VOR der Reservierung dauerhaft am Job vermerken. Stürzt der
    # Worker zwischen Ledger-Reservierung (eigene DB) und Bindung ab, bleibt die
    # Reservierung über diese ID auffindbar (Reconciliation V7-03.1c).
    reservation_id = uuid.uuid4() if isinstance(provider, BudgetedProvider) else None
    if reservation_id is not None:
        try:
            bind_ledger(lease, reservation_id=reservation_id, ledger_state=J.LEDGER_RESERVING)
        except StaleLease:
            _log.warning("ai_chat_job_lease_lost job=%s", job.pk)
            return None
    session = _JobStream(lease, job, provider, question, turns, clock, reservation_id=reservation_id)
    outcome, reason = session.run()
    if outcome is None:
        return None                                # Lease verloren: keine Finalisierung
    session.bind_final_ledger()
    if outcome == "rate_limited":
        return _finish(lease, job, J.FAILED, {"error": "rate_limited", "reason": reason}, 429)
    if outcome == "UNSUPPORTED_QUESTION":
        return _finish(lease, job, J.FAILED, {"error": "UNSUPPORTED_QUESTION"}, 422)
    if outcome == "completed":
        result, http = session.result_completed()
        status = J.COMPLETED if http == 200 else J.FAILED
        return _finish(lease, job, status, result, http)
    if outcome in OUTCOME_STATUS:
        partial = {"error": outcome, "partial_answer": session.text(), "complete": False}
        if reason:
            partial["reason"] = reason
        http = {"cancelled": 499, "provider_timeout": 504}.get(outcome, 503)
        if outcome == "provider_timeout":
            partial = {"error": "provider_timeout"}
        return _finish(lease, job, OUTCOME_STATUS[outcome], partial, http)
    return _finish(lease, job, J.FAILED, {"error": outcome}, 503)


def _default_provider(job, turns):
    from apps.ai_core.views_global import prepare_paid_text_for_actor
    _shared, provider, _stage2, _budget, answer_chars = prepare_paid_text_for_actor(job.owner, turns)
    provider._vq_answer_chars = answer_chars
    return provider


class _JobStream:
    """Worker-Schleife: Provider-Deltas lesen, fenced checkpointen, Stop/Not-Aus prüfen."""

    def __init__(self, lease, job, provider, question, turns, clock, *, reservation_id=None):
        self.lease, self.job, self.provider = lease, job, provider
        self.reservation_id = reservation_id
        self.question, self.turns, self.clock = question, turns, clock
        self.parts, self.length, self.sequence = [], 0, 0
        self.max_chars = getattr(provider, "_vq_answer_chars", None) or 8 * getattr(provider, "max_output_tokens", 1000)

    def text(self):
        return "".join(self.parts)

    def run(self):
        from apps.ai_core.engine.budget import BudgetExceeded
        from apps.ai_core.providers.exceptions import GatewayError, ProviderTimeout
        from apps.ai_core.sanitization import UnsafePrompt, screen_and_redact
        from apps.ai_core.chat_input_budget import global_budget
        from apps.ai_ledger.service import emergency_stop_active
        from apps.ai_core.uncited_answer_guard import find_violation
        try:
            clean = screen_and_redact(self.question, limit=global_budget().question_chars)
        except UnsafePrompt:
            return "UNSUPPORTED_QUESTION", None
        deadline = self.clock() + deadline_seconds()
        since, last = 0, self.clock()
        extra = {"reservation_id": self.reservation_id} if self.reservation_id is not None else {}
        stream = self.provider.stream_knowledge(question=clean, language=self.job.language,
                                                prior_turns=self.turns, **extra)
        try:
            for kind, value in stream:
                self._bind_reservation()
                if kind == "delta":
                    if self.length + len(value) > self.max_chars:
                        return "output_limit_reached", "answer_chars"
                    self.parts.append(value)
                    self.length += len(value)
                    since += len(value)
                elif kind == "final":
                    if value.status == "completed":
                        return "completed", None
                    if value.status == "incomplete" and value.reason == "max_output_tokens":
                        return "output_limit_reached", "max_output_tokens"
                    return "provider_unavailable", value.reason
                if self.clock() >= deadline:
                    return "stream_timeout", "deadline"
                if since >= CHECKPOINT_CHARS or self.clock() - last >= CHECKPOINT_SECONDS:
                    since, last = 0, self.clock()
                    if find_violation(self.text()) is not None:
                        return "provider_unavailable", "invalid_provider_response"
                    self.sequence += 1
                    status = checkpoint(self.lease, self.text(), self.sequence)
                    if status == J.CANCEL_REQUESTED:
                        return "cancelled", None
                    if emergency_stop_active() is True:
                        return "emergency_stop", "emergency_stop"
            return "provider_unavailable", "stream_ended"
        except StaleLease:
            # Lease verloren: keine Job-Schreibzugriffe mehr. Die Abrechnung erfolgt
            # trotzdem genau einmal (BudgetedProvider, finally) – mit Usage, falls bekannt.
            self.lease_lost = True
            return None, None
        except BudgetExceeded as exc:
            # Reservierung abgelehnt (Ledger/Budget/Not-Aus): kein Provider-Aufruf.
            from apps.ai_core.error_contracts import budget_reason
            return "rate_limited", budget_reason(exc)
        except ProviderTimeout:
            return "provider_timeout", None
        except GatewayError as exc:
            return getattr(exc, "code", "provider_unavailable"), None
        finally:
            stream.close()                          # BudgetedProvider rechnet genau einmal ab
            if getattr(self, "lease_lost", False):
                reservation = getattr(self.provider, "last_reservation", None)
                _log.warning("ai_chat_job_lease_lost job=%s reservation=%s settlement=%s", self.job.pk,
                             getattr(reservation, "id", None), getattr(self.provider, "last_settlement", None))

    def _bind_reservation(self):
        reservation = getattr(self.provider, "last_reservation", None)
        if reservation is not None and not getattr(self, "_bound", False):
            bind_ledger(self.lease, reservation_id=reservation.id, ledger_state=J.LEDGER_RESERVED,
                        request_sent=True)
            self._bound = True

    def bind_final_ledger(self):
        state = getattr(self.provider, "last_settlement", None)
        mapping = {"finalized": J.LEDGER_FINALIZED, "uncertain": J.LEDGER_UNCERTAIN,
                   "released": J.LEDGER_RELEASED, "unacknowledged": J.LEDGER_UNACKNOWLEDGED}
        reservation = getattr(self.provider, "last_reservation", None)
        ledger_state = mapping.get(state)
        if reservation is None and self.reservation_id is not None:
            # Reservierung wurde abgelehnt (Transaktion im Ledger zurückgerollt): nichts
            # reserviert. Die vermerkte Korrelations-ID bleibt für die Reconciliation stehen.
            ledger_state = J.LEDGER_NONE
        try:
            bind_ledger(self.lease, reservation_id=getattr(reservation, "id", None),
                        ledger_state=ledger_state,
                        request_sent=getattr(getattr(self.provider, "inner", self.provider), "request_sent", None))
        except StaleLease:
            _log.warning("ai_chat_job_ledger_bind_lost job=%s reservation=%s settlement=%s", self.job.pk,
                         getattr(reservation, "id", None), state)

    def result_completed(self):
        from apps.ai_core.general_knowledge_runtime import validate_knowledge
        from apps.ai_core.providers.exceptions import ProviderInvalidResponse
        try:
            return validate_knowledge({"answer": self.text(), "language": self.job.language},
                                      language=self.job.language, max_answer_chars=self.max_chars), 200
        except ProviderInvalidResponse:
            return {"error": "provider_unavailable", "reason_code": "invalid_provider_response"}, 503


def _finish(lease, job, target, result, http_status):
    """Job-Terminalstatus + Antwort-Turn in EINER Transaktion (fencing-geschützt)."""
    from apps.ai_core.conversations import service
    now = timezone.now()
    try:
        with transaction.atomic():
            locked = _fenced(lease, now=now).select_for_update().first()
            if locked is None:
                raise StaleLease()
            if target not in TRANSITIONS[locked.status]:
                raise InvalidTransition(f"{locked.status}->{target}")
            if job.assistant_message_id:
                service.complete_turn(job.owner, job.assistant_message_id, result=result,
                                      http_status=http_status, reservation_id=locked.reservation_id,
                                      model="")
            J.objects.filter(pk=job.pk, fencing_token=lease.token, status=locked.status).update(
                status=target, error_code=str(result.get("error", "") if isinstance(result, dict) else "")[:40],
                finished_at=now, lease_until=None, updated_at=now)
    except StaleLease:
        _log.warning("ai_chat_job_finish_lost job=%s", job.pk)
        return None
    except DatabaseError as exc:
        # Ergebnis nicht gespeichert: Job bleibt aktiv bis zur Reconciliation (V7-03.1c).
        _log.error("ai_chat_job_finish_failed job=%s kind=%s", job.pk, type(exc).__name__)
        return None
    return target
