"""Development-only grounded generation orchestration; no external side effects by default."""
from django.contrib.auth.models import AnonymousUser

from apps.ai_core.gateway import validate, retrieve_public
from apps.ai_core.sanitization import UnsafePrompt, screen_and_redact
from apps.ai_core.providers.exceptions import ProviderUnavailable
from .citation import EvidenceRejected, authorized_context, validate_generated


class PhaseBDisabled(ValueError):
    pass


def ask_grounded(question, language, *, actor, provider=None, retrieval=None, enabled=False,
                 max_answer_chars=1000, input_budget=None):
    if not enabled:
        raise PhaseBDisabled("Phase B disabled")
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PhaseBDisabled("actor not authenticated")
    from apps.ai_core.chat_input_budget import LEGACY
    budget = input_budget or LEGACY
    question, language = validate(question, language, input_budget=budget)
    try:
        safe_question = screen_and_redact(question, limit=budget.question_chars)
        query = question
        if budget.question_utf8_bytes:
            from apps.ai_core.chat_search_query import bounded_query
            query = bounded_query(question, language, max_chars=budget.question_chars)
    except UnsafePrompt as exc:
        raise EvidenceRejected("unsafe question") from exc
    # Retrieval always runs against local explicit public adapters. A mock may
    # replace it only in tests. Never call a private or tenant-specific index.
    raw_sources = tuple((retrieval or retrieve_public)(query, language))
    sources = authorized_context(raw_sources)
    if not sources:
        return {
            "mode": "insufficient_evidence", "answer": "",
            "language": language, "citations": [], "verified": False,
            "model_status": "not_called", "grounded_status": "insufficient_evidence",
            "error_code": "INSUFFICIENT_EVIDENCE",
        }
    if provider is None:
        raise ProviderUnavailable("no provider configured")
    output = provider.generate(question=safe_question, language=language, sources=sources)
    return validate_generated(output, sources=sources, language=language,
                              max_answer_chars=max_answer_chars)
