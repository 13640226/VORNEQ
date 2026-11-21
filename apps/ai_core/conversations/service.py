"""Conversation rules and transactions (owner-bound via the repository)."""
from __future__ import annotations

from datetime import timedelta
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai_core.models import AIConversation, AIMessage
from apps.ai_core.engine.passages import MAX_PASSAGES

from . import repository
from .repository import ConversationNotFound

TITLE_LIMIT = 120


class ConversationLimit(Exception):
    pass


class ConversationNotInTrash(Exception):
    pass


def _title_from(text):
    text = " ".join(str(text or "").split())
    return (text[:TITLE_LIMIT - 1] + "…") if len(text) > TITLE_LIMIT else text


def create(owner, *, language="fa", title=""):
    repository._owned(owner)
    if repository.count_live(owner) >= settings.VORNEQ_AI_CONVERSATIONS_PER_USER:
        raise ConversationLimit("conversation limit reached")
    return AIConversation.objects.create(owner=owner, language=language if language in ("fa", "de", "en") else "fa",
                                         title=_title_from(title))


def rename(owner, conversation_id, title):
    title = _title_from(title)
    if not title:
        raise ValueError("empty title")
    conversation = repository.get_conversation(owner, conversation_id)
    conversation.title = title
    conversation.save(update_fields=["title", "updated_at"])
    return conversation


def set_archived(owner, conversation_id, archived):
    conversation = repository.get_conversation(owner, conversation_id)
    conversation.archived_at = timezone.now() if archived else None
    conversation.save(update_fields=["archived_at", "updated_at"])
    return conversation


def move_to_trash(owner, conversation_id):
    conversation = repository.get_conversation(owner, conversation_id)
    conversation.deleted_at = timezone.now()
    conversation.save(update_fields=["deleted_at", "updated_at"])
    return conversation


def restore(owner, conversation_id):
    conversation = repository.get_conversation(owner, conversation_id, include_deleted=True)
    if conversation.deleted_at is None:
        return conversation
    conversation.deleted_at = None
    conversation.save(update_fields=["deleted_at", "updated_at"])
    return conversation


def delete_permanently(owner, conversation_id):
    """Only conversations already in the trash can be deleted for good."""
    conversation = repository.get_conversation(owner, conversation_id, include_deleted=True)
    if conversation.deleted_at is None:
        raise ConversationNotInTrash("move to trash first")
    conversation.delete()


def purge_expired(*, now=None, days=None):
    """Permanently delete conversations whose trash period has ended."""
    days = settings.VORNEQ_AI_CONVERSATION_TRASH_DAYS if days is None else days
    cutoff = (now or timezone.now()) - timedelta(days=days)
    deleted, _ = AIConversation.objects.filter(deleted_at__isnull=False, deleted_at__lt=cutoff).delete()
    return deleted


def ensure_capacity(conversation):
    if conversation.message_count + 2 > settings.VORNEQ_AI_CONVERSATION_MAX_MESSAGES:
        raise ConversationLimit("message limit reached")


# Provider outcomes that may have been billed although no answer arrived.
_UNCERTAIN_ERRORS = {"provider_timeout"}
_PASSAGE_ID = re.compile(r"S[1-5]\.P[1-9][0-9]?\Z")


def _v2_citation(source):
    """Allowlisted metadata only; never persist arbitrary provider/user objects."""
    if not isinstance(source, dict):
        return None
    fields = ("source_id", "source_key", "title", "url", "publisher",
              "evidence_quote", "retrieved_at", "evidence_digest")
    result = {k: source[k] for k in fields
              if isinstance(source.get(k), str)
              and len(source[k]) <= (300 if k == "evidence_quote" else 500)}
    source_id = result.get("source_id", "")
    if source_id not in ("S1", "S2", "S3", "S4", "S5"):
        return None
    passages = source.get("passages")
    if not isinstance(passages, list) or len(passages) > MAX_PASSAGES:
        return result
    safe = []
    seen = set()
    for p in passages:
        if not isinstance(p, dict) or set(p) != {"passage_id", "quote", "section_indices"}:
            continue
        pid, quote, indexes = p["passage_id"], p["quote"], p["section_indices"]
        if (not isinstance(pid, str) or not _PASSAGE_ID.fullmatch(pid)
                or not pid.startswith(source_id + ".") or pid in seen
                or not isinstance(quote, str) or not 80 <= len(quote) <= 300
                or not isinstance(indexes, list) or not 1 <= len(indexes) <= 6
                or any(type(i) is not int or not 0 <= i <= 5 for i in indexes)
                or indexes != sorted(set(indexes))):
            continue
        seen.add(pid)
        safe.append({"passage_id": pid, "quote": quote, "section_indices": indexes})
    if safe:
        result["passages"] = safe
    return result


def classify(result, http_status):
    """Map the exact client response to (status, content, error_code, citations)."""
    result = result if isinstance(result, dict) else {}
    if http_status == 200 and result.get("mode") == "grounded_draft":
        if result.get("format_version") == 2:
            raw = result.get("citations")
            citations = [_v2_citation(c) for c in (raw[:5] if isinstance(raw, list) else [])]
            citations = [c for c in citations if c is not None]
            # The engine permits at most MAX_PASSAGES across all sources.
            # Do not persist a misleading partial set if replay metadata is oversized.
            if sum(len(c.get("passages", ())) for c in citations) > MAX_PASSAGES:
                for c in citations:
                    c.pop("passages", None)
            return AIMessage.STATUS_COMPLETED, str(result.get("answer", "")), "", citations
        # V1 behavior intentionally unchanged for existing clients and rows.
        citations = [
            {key: c.get(key) for key in ("source_id", "title", "url", "publisher", "evidence_quote", "retrieved_at")
             if isinstance(c, dict) and isinstance(c.get(key), str)}
            for c in (result.get("citations") or [])[:3]
        ]
        return AIMessage.STATUS_COMPLETED, str(result.get("answer", "")), "", citations
    if http_status in (200, 422):
        code = result.get("reason_code") or result.get("error") or "insufficient_evidence"
        return AIMessage.STATUS_INSUFFICIENT, "", str(code)[:40], []
    code = str(result.get("error") or "failed")[:40]
    status = AIMessage.STATUS_UNCERTAIN if code in _UNCERTAIN_ERRORS else AIMessage.STATUS_FAILED
    return status, "", code, []


def begin_turn(owner, conversation_id, *, question, request_id=None):
    """Durably record the user question and a PENDING assistant turn.

    Committed BEFORE any quota, retrieval, ledger or provider work. Returns
    (user_message, pending_assistant_message).
    """
    with transaction.atomic():
        conversation = repository.get_conversation(owner, conversation_id, for_update=True)
        ensure_capacity(conversation)
        base = conversation.message_count
        user_message = AIMessage.objects.create(conversation=conversation, sequence=base + 1,
                                                role=AIMessage.ROLE_USER, content=question)
        pending = AIMessage.objects.create(conversation=conversation, sequence=base + 2,
                                           role=AIMessage.ROLE_ASSISTANT, status=AIMessage.STATUS_PENDING,
                                           request_id=request_id)
        conversation.message_count = base + 2
        conversation.last_message_at = timezone.now()
        fields = ["message_count", "last_message_at", "updated_at"]
        if not conversation.title:
            conversation.title = _title_from(question)
            fields.append("title")
        conversation.save(update_fields=fields)
        return user_message, pending


def complete_turn(owner, message_id, *, result, http_status, reservation_id=None, model="",
                  finalize_guard=None):
    """Finalize a PENDING assistant turn in ONE PostgreSQL transaction.

    ``finalize_guard`` (request recovery) runs inside the same transaction, so the
    message and the guard become final together or not at all. A guard that
    cannot be finalized for a non-database reason (e.g. the session changed) does
    not discard the answer: the guard simply stays "running", which still blocks
    any replay. Idempotent: an already final message is returned unchanged.
    Returns (message, guard_finalized).
    """
    status, content, error, citations = classify(result, http_status)
    with transaction.atomic():
        try:
            message = (AIMessage.objects.select_for_update()
                       .get(pk=message_id, role=AIMessage.ROLE_ASSISTANT, conversation__owner_id=owner.pk))
        except AIMessage.DoesNotExist as exc:
            raise ConversationNotFound("turn not found") from exc
        if message.status != AIMessage.STATUS_PENDING:
            return message, False
        message.status, message.content, message.error_code, message.citations = status, content, error, citations
        message.http_status = http_status
        message.ledger_reservation_id = reservation_id
        message.model = (model or "")[:100]
        message.finalized_at = timezone.now()
        message.save(update_fields=["status", "content", "error_code", "citations", "http_status",
                                    "ledger_reservation_id", "model", "finalized_at"])
        AIConversation.objects.filter(pk=message.conversation_id).update(last_message_at=timezone.now(),
                                                                         updated_at=timezone.now())
        guard_finalized = False
        if finalize_guard is not None:
            from apps.ai_core import request_recovery
            try:
                finalize_guard()
                guard_finalized = True
            except (request_recovery.RecoveryNotFound, request_recovery.RecoveryUnavailable):
                guard_finalized = False
        return message, guard_finalized


def mark_uncertain(message_id, *, error_code="interrupted"):
    """Operator reconciliation: a stale PENDING turn whose outcome is unknown."""
    return AIMessage.objects.filter(pk=message_id, role=AIMessage.ROLE_ASSISTANT,
                                    status=AIMessage.STATUS_PENDING).update(
        status=AIMessage.STATUS_UNCERTAIN, error_code=error_code[:40], finalized_at=timezone.now())


def finalize_from_cache(message_id, cached):
    """Operator reconciliation: finalize a stale PENDING turn from the Redis result."""
    status, content, error, citations = classify(cached.get("response"), cached.get("http_status"))
    return AIMessage.objects.filter(pk=message_id, role=AIMessage.ROLE_ASSISTANT,
                                    status=AIMessage.STATUS_PENDING).update(
        status=status, content=content, error_code=error, citations=citations,
        http_status=cached.get("http_status"), finalized_at=timezone.now())


def stored_response(message, conversation):
    """Rebuild the client response of a FINAL turn (replay after cache expiry)."""
    base = {"conversation_id": str(conversation.id), "persisted": True, "replayed": True}
    if message.status == AIMessage.STATUS_COMPLETED:
        v2 = any(isinstance(c, dict) and isinstance(c.get("passages"), list)
                 for c in (message.citations or []))
        response = dict(base, mode="grounded_draft", answer=message.content, language=conversation.language,
                        citations=message.citations, verified=False, model_status="generated",
                        grounded_status=("passage_linked_claims_unverified" if v2
                                         else "citation_and_quote_checked_claims_unverified"), error_code="")
        # A DB replay has the flat answer and passage mappings; sections were
        # deliberately not persisted without a separately approved migration.
        if v2:
            response["format_version"] = 2
        return response, 200
    if message.status == AIMessage.STATUS_INSUFFICIENT:
        if message.http_status == 200:
            return dict(base, mode="insufficient_evidence", answer="", language=conversation.language,
                        citations=[], verified=False, model_status="not_called",
                        grounded_status="insufficient_evidence", error_code="INSUFFICIENT_EVIDENCE"), 200
        if message.error_code == "UNSUPPORTED_QUESTION":
            return dict(base, error="UNSUPPORTED_QUESTION"), 422
        return dict(base, error="INSUFFICIENT_EVIDENCE", reason_code=message.error_code), 422
    return dict(base, error=message.error_code or "failed"), message.http_status or 503


def record_turn(owner, conversation_id, *, question, language, result, http_status,
                request_id=None, reservation_id=None, model=""):
    """Convenience (seeding/tests): begin + complete without a recovery guard."""
    if request_id is not None and AIMessage.objects.filter(request_id=request_id).exists():
        return None
    _, pending = begin_turn(owner, conversation_id, question=question, request_id=request_id)
    message, _ = complete_turn(owner, pending.id, result=result, http_status=http_status,
                               reservation_id=reservation_id, model=model)
    return message


def export(owner, conversation_id):
    conversation, messages = repository.list_messages(owner, conversation_id, limit=1000, include_deleted=True)
    return {
        "format": "vorneq.ai.conversation.v1",
        "id": str(conversation.id),
        "title": conversation.title,
        "language": conversation.language,
        "created_at": conversation.created_at.isoformat(),
        "messages": [serialize_message(m) for m in messages],
    }


def serialize_conversation(conversation):
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "language": conversation.language,
        "message_count": conversation.message_count,
        "last_message_at": conversation.last_message_at.isoformat(),
        "archived": conversation.archived_at is not None,
        "in_trash": conversation.deleted_at is not None,
        "purge_after": ((conversation.deleted_at + timedelta(days=settings.VORNEQ_AI_CONVERSATION_TRASH_DAYS))
                        .isoformat() if conversation.deleted_at else None),
    }


def serialize_message(message):
    return {
        "id": str(message.id),
        "sequence": message.sequence,
        "role": message.role,
        "content": message.content,
        "status": message.status,
        "error_code": message.error_code,
        "citations": message.citations,
        "request_id": str(message.request_id) if message.request_id else None,
        "created_at": message.created_at.isoformat(),
        "finalized": message.status != AIMessage.STATUS_PENDING,
    }


__all__ = ["ConversationLimit", "ConversationNotFound", "ConversationNotInTrash"]
