"""Isolated, uncited public-knowledge response contract."""
from apps.ai_core.providers.exceptions import ProviderInvalidResponse
from apps.ai_core.sanitization import screen_and_redact


def validate_knowledge(output, *, language, max_answer_chars):
    if not isinstance(output, dict) or set(output) != {"answer", "language"}:
        raise ProviderInvalidResponse("invalid uncited answer schema")
    answer = output["answer"]
    if (type(answer) is not str or not answer.strip() or len(answer) > max_answer_chars
            or output["language"] != language):
        raise ProviderInvalidResponse("invalid uncited answer")
    if "http://" in answer.lower() or "https://" in answer.lower():
        raise ProviderInvalidResponse("uncited answer contains a URL")
    return {
        "mode": "model_knowledge", "answer": answer, "language": language,
        "citations": [], "verified": False, "model_status": "generated",
        "grounded_status": "model_knowledge_unverified", "error_code": "",
        "route": "general_public",
    }


def ask_knowledge(question, language, *, provider, max_answer_chars, prior_turns=()):
    from apps.ai_core.chat_input_budget import global_budget
    clean = screen_and_redact(question, limit=global_budget().question_chars)
    output = provider.generate_knowledge(question=clean, language=language,
                                         prior_turns=tuple(prior_turns))
    return validate_knowledge(output, language=language, max_answer_chars=max_answer_chars)
