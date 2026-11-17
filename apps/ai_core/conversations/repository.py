"""All conversation queries. Every function requires the owner.

There is deliberately no function that loads a conversation by ID alone:
foreign or unknown IDs are indistinguishable (ConversationNotFound -> HTTP 404).
"""
from __future__ import annotations

from django.db.models import Q

from apps.ai_core.models import AIConversation, AIMessage

MAX_PAGE = 100


class ConversationNotFound(Exception):
    pass


def _owned(owner):
    if owner is None or not getattr(owner, "is_authenticated", False) or not owner.pk:
        raise ConversationNotFound("no authenticated owner")
    return AIConversation.objects.filter(owner_id=owner.pk)


def list_conversations(owner, *, archived=False, trash=False, query="", limit=50, offset=0):
    qs = _owned(owner)
    if trash:
        qs = qs.filter(deleted_at__isnull=False)
    else:
        qs = qs.filter(deleted_at__isnull=True, archived_at__isnull=not archived)
    query = (query or "").strip()[:100]
    if query:
        matching = AIMessage.objects.filter(conversation__owner_id=owner.pk,
                                            content__icontains=query).values("conversation_id")
        qs = qs.filter(Q(title__icontains=query) | Q(id__in=matching))
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))
    return list(qs.order_by("-last_message_at", "-created_at")[offset:offset + limit])


def get_conversation(owner, conversation_id, *, include_deleted=False, for_update=False):
    qs = _owned(owner)
    if not include_deleted:
        qs = qs.filter(deleted_at__isnull=True)
    if for_update:
        qs = qs.select_for_update()
    try:
        return qs.get(pk=conversation_id)
    except (AIConversation.DoesNotExist, ValueError, TypeError) as exc:
        raise ConversationNotFound("conversation not found") from exc


def list_messages(owner, conversation_id, *, after_sequence=0, limit=MAX_PAGE, include_deleted=False):
    conversation = get_conversation(owner, conversation_id, include_deleted=include_deleted)
    limit = max(1, min(int(limit), 1000))
    return conversation, list(conversation.messages.filter(sequence__gt=max(0, int(after_sequence)))
                              .order_by("sequence")[:limit])


def count_live(owner):
    return _owned(owner).count()
