"""Separate long chat input from the existing bounded public search query."""
from apps.ai_core.sanitization import UnsafePrompt, screen_and_redact
from apps.ai_core.engine.evidence_ranking import search_keywords, terms


def bounded_query(question, language, *, max_chars):
    safe = screen_and_redact(question, limit=max_chars)
    if "[REDACTED_" in safe:
        raise UnsafePrompt("query contains personal data")
    if len(safe) <= 200:
        return safe
    words = search_keywords(safe, language).split() if language == "fa" else terms(safe, language)
    chosen = []
    for word in words:
        if len(" ".join(chosen + [word])) > 200:
            break
        chosen.append(word)
    if not chosen:
        raise UnsafePrompt("no bounded search terms")
    return " ".join(chosen)
