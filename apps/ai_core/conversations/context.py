"""ContextBuilder: bounded prior turns for the model (design V1, D5).

Prior turns are conversation context, NEVER evidence: they travel in the
request payload (``prior_turns``), not in instructions; citations and numbers
are still validated only against the current retrieved sources.
"""
from __future__ import annotations

from django.conf import settings

from apps.ai_core.models import AIMessage
from apps.ai_core.response_engine_v3 import answer_limit
from apps.ai_core.sanitization import UnsafePrompt, screen_and_redact

PER_MESSAGE_LIMIT = 1000


def prior_turns(conversation, *, turns=None, max_chars=None, limits=None, question=""):
    """Return oldest->newest [{"role", "content"}] of the last completed pairs.

    V7-02: Mit vollständiger Modell-Policy (``model_limits``) entscheidet das
    Token-Budget des Verlaufs statt fester Turn-/Zeichenzahlen. Der gespeicherte
    Verlauf bleibt unverändert; nur die gesendete Auswahl wird begrenzt.
    """
    from apps.ai_core.model_limits import chat_limits, history_budget, select_history
    policy = limits if limits is not None else chat_limits()
    budgeted = policy.extended and turns is None and max_chars is None
    turns = turns if turns is not None else settings.VORNEQ_AI_CONTEXT_TURNS
    max_chars = max_chars if max_chars is not None else settings.VORNEQ_AI_CONTEXT_MAX_CHARS
    if not budgeted and (turns <= 0 or max_chars <= 0):
        return ()
    # V7-02.1: dynamisches Budget (tatsächliche Größe der aktuellen Frage statt
    # voller Eingabereserve); nie kleiner als das statische Budget.
    dynamic_budget = history_budget(policy, question) if budgeted else 0
    if budgeted and not dynamic_budget:
        return ()
    cap = getattr(settings, "VORNEQ_AI_CONVERSATION_MAX_MESSAGES", 500) if budgeted else turns * 2 + 8
    rows = list(conversation.messages.order_by("-sequence")[:cap])
    by_sequence = {m.sequence: m for m in rows}
    pairs = []
    question_limit = policy.max_message_characters if budgeted else PER_MESSAGE_LIMIT
    assistant_limit = (max(PER_MESSAGE_LIMIT, policy.answer_chars) if budgeted
                       else max(PER_MESSAGE_LIMIT, answer_limit(settings)))
    for message in rows:
        if message.role != AIMessage.ROLE_ASSISTANT or message.status != AIMessage.STATUS_COMPLETED:
            continue
        question = by_sequence.get(message.sequence - 1)
        if question is None or question.role != AIMessage.ROLE_USER:
            continue
        try:
            pair = (screen_and_redact(question.content, limit=question_limit),
                    screen_and_redact(message.content, limit=assistant_limit))
        except UnsafePrompt:
            continue
        if not pair[0] or not pair[1]:
            continue
        pairs.append(pair)
        if not budgeted and len(pairs) == turns:
            break
    if budgeted:
        return select_history(pairs, policy, budget=dynamic_budget)
    selected, used = [], 0
    for question, answer in pairs:  # newest first
        size = len(question) + len(answer)
        if used + size > max_chars:
            break
        selected.append(({"role": "user", "content": question}, {"role": "assistant", "content": answer}))
        used += size
    return tuple(turn for pair in reversed(selected) for turn in pair)


def search_question(conversation, question, language, *, exclude_message_id=None):
    """Context-aware retrieval text for a follow-up, or None (flag OFF by default)."""
    if not getattr(settings, "VORNEQ_AI_CONTEXT_RETRIEVAL_ENABLED", False):
        return None
    from apps.ai_core.engine.evidence_ranking import followup_search_text

    answered = (conversation.messages.filter(role=AIMessage.ROLE_ASSISTANT, status=AIMessage.STATUS_COMPLETED)
                .exclude(pk=exclude_message_id).order_by("-sequence").first())
    if answered is None:
        return None
    previous = conversation.messages.filter(sequence=answered.sequence - 1, role=AIMessage.ROLE_USER).first()
    if previous is None:
        return None
    return followup_search_text(question, previous.content, language)
