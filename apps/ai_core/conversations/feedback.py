"""Feedback is a local history operation, independent of paid AI access."""
from django.conf import settings
from django.db import transaction

from apps.ai_core.models import AIMessage, AIMessageFeedback
from . import repository


class IneligibleMessage(Exception):
    pass


def enabled():
    return (getattr(settings, "VORNEQ_AI_CONVERSATIONS_ENABLED", False) is True
            and getattr(settings, "VORNEQ_AI_FEEDBACK_ENABLED", False) is True)


def eligible(message):
    return (message.role == AIMessage.ROLE_ASSISTANT
            and message.status == AIMessage.STATUS_COMPLETED
            and bool(message.content.strip()))


def ratings(messages):
    """One bounded lookup for an already owner-scoped list, never N+1."""
    ids = [m.pk for m in messages if eligible(m)]
    return dict(AIMessageFeedback.objects.filter(message_id__in=ids)
                .values_list("message_id", "rating"))


def response_identity(message, response):
    """Only attach the identity of the actual durable, displayed answer."""
    if (enabled() and eligible(message) and isinstance(response, dict)
            and response.get("answer") == message.content):
        return {"assistant_message_id": str(message.pk)}
    return {}


def access(owner, conversation_id, message_id, *, method, rating=None):
    """Only owner can rate a non-deleted conversation, archived or live.

    Lock the parent on PostgreSQL to serialize competing writes and trash
    operations. Unique primary key and check constraint enforce row validity.
    SQLite lock contention is handled by the view as a controlled 503.
    """
    if method not in ("GET", "POST", "DELETE"):
        raise ValueError("method")
    if method == "POST" and rating not in ("like", "dislike"):
        raise ValueError("rating")
    with transaction.atomic():
        conversation = repository.get_conversation(
            owner, conversation_id, for_update=(method != "GET"))
        try:
            message = conversation.messages.get(pk=message_id)
        except AIMessage.DoesNotExist as exc:
            raise repository.ConversationNotFound("message not found") from exc
        if not eligible(message):
            raise IneligibleMessage
        if method == "GET":
            return (AIMessageFeedback.objects.filter(message_id=message.pk)
                    .values_list("rating", flat=True).first())
        if method == "DELETE":
            AIMessageFeedback.objects.filter(message_id=message.pk).delete()
            return None
        # Identical requests are true no-ops (including updated_at).
        existing, created = AIMessageFeedback.objects.get_or_create(
            message=message, defaults={"rating": rating})
        if not created and existing.rating != rating:
            existing.rating = rating
            existing.save(update_fields=["rating", "updated_at"])
        return existing.rating
