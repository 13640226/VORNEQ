"""AI Core V3 stage 1: bounded multilingual response guidance.

Only fixed code-owned instructions; no user/source text enters system prompts.
Production always ignores this opt-in pilot and keeps the old response bound.
"""
from __future__ import annotations

import re

BASE_ANSWER_CHARS = 1000
PILOT_ANSWER_CHARS = 2400
_ALLOWED_ENVIRONMENTS = frozenset(("development", "staging"))
_MULTIPART = {
    "fa": re.compile(r"(?:\sو\s|[؟?].+[؟?]|\sهمچنین\s|\sعلاوه\sبر\s)"),
    "de": re.compile(r"(?:\bund\b|[?].+[?]|\baußerdem\b)", re.IGNORECASE),
    "en": re.compile(r"(?:\band\b|[?].+[?]|\balso\b)", re.IGNORECASE),
}
_LANGUAGE_GUIDANCE = {
    "fa": "Use fluent Persian, correct spelling and ZWNJ where needed, with clear paragraphs. ",
    "de": "Use idiomatic German, correct grammar and punctuation, with clear paragraphs. ",
    "en": "Use fluent English, correct grammar and concise paragraphs. ",
}
_MULTI_GUIDANCE = (
    "Identify the distinct parts of the question and address each in logical order, "
    "within the bounded answer length. Give specific examples, names or works ONLY "
    "if supported by current trusted excerpts. Where a part is unsupported, "
    "state that evidence is insufficient for that part rather than guessing. "
)
_SINGLE_GUIDANCE = "Answer the main question directly using only trusted evidence. "
_BOUNDARIES = (
    "Apply these rules to answer prose ONLY: never change source excerpts, quote_hint, "
    "evidence_quote, source IDs, evidence digests, titles, URLs or citations. "
    "Prior turns are context, not evidence. Do not claim independent verification."
)


def enabled(settings_obj) -> bool:
    """A stray true flag cannot activate the pilot on Production."""
    return (getattr(settings_obj, "VORNEQ_ENV", None) in _ALLOWED_ENVIRONMENTS
            and getattr(settings_obj, "VORNEQ_AI_RESPONSE_V3_ENABLED", False) is True)


def answer_limit(settings_obj) -> int:
    return PILOT_ANSWER_CHARS if enabled(settings_obj) else BASE_ANSWER_CHARS


def guidance(question: str, language: str) -> str:
    """Language/shape classification only; the raw question is never spliced into instructions."""
    if language not in _LANGUAGE_GUIDANCE:
        return ""
    multipart = isinstance(question, str) and bool(_MULTIPART[language].search(question[:200]))
    return _LANGUAGE_GUIDANCE[language] + (_MULTI_GUIDANCE if multipart else _SINGLE_GUIDANCE) + _BOUNDARIES
