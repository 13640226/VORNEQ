"""Global AI V1: deterministic, local question router and language detection.

No model, network or database access. Routing decides only WHICH trusted
retrieval layer may be asked; it never authorizes a source by itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from apps.ai_core.sanitization import UnsafePrompt, screen_and_redact

OFFICIAL_VORNEQ = "official_vorneq"
GENERAL_PUBLIC = "general_public"
UNSUPPORTED = "unsupported_or_unsafe"

LANGUAGES = ("fa", "de", "en")

_BRAND = re.compile(r"(?i)(?<![a-z0-9])vorneq(?![a-z0-9])")
_PERSIAN = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_GERMAN_CHARS = re.compile(r"[äöüßÄÖÜ]")
_GERMAN_WORDS = re.compile(
    r"(?i)\b(wie|was|warum|wieso|weshalb|welche[rsmn]?|wer|wo|wann|ist|sind|gibt|"
    r"entstehen|entsteht|der|die|das|den|dem|des|und|ein|eine|einen|nicht|über|"
    r"funktioniert|bedeutet|kann|können)\b")
_ENGLISH_WORDS = re.compile(
    r"(?i)\b(what|how|why|which|who|where|when|is|are|does|do|did|the|and|a|an|"
    r"can|explain|many|much|of|in)\b")
# Questions about a person's own (private) VORNEQ data are never answered from
# the public web or by the model. They belong to authenticated product views.
_PRIVATE = re.compile(
    r"(?i)(\b(my|mine|our)\s+(own\s+)?(documents?|notes?|account|files?|passwords?|data|"
    r"messages?|orders?|purchases?)\b|"
    r"\b(meine?[nrs]?|unsere?[nrs]?)\s+(dokumente?|notizen|konto|dateien|passw(o|ö)rter?|"
    r"passwort|daten|nachrichten|bestellungen)\b|"
    r"(اسناد|مدارک|یادداشت‌?های|یادداشت|حساب|فایل‌?های|فایل|رمز|پیام‌?های|سفارش‌?های)"
    r"\s*(خودم|من)(?![؀-ۿ]))")


@dataclass(frozen=True)
class Route:
    kind: str
    language: str
    reason: str


def detect_language(question: str, fallback: str = "en") -> str:
    """Return the language of the QUESTION (not the UI). Latin brand names or
    technical terms inside Persian text never override the Persian script."""
    fallback = fallback if fallback in LANGUAGES else "en"
    if not isinstance(question, str) or not question.strip():
        return fallback
    if _PERSIAN.search(question):
        return "fa"
    german = len(_GERMAN_WORDS.findall(question)) + 2 * len(_GERMAN_CHARS.findall(question))
    english = len(_ENGLISH_WORDS.findall(question))
    if german > english:
        return "de"
    if english > german:
        return "en"
    return fallback


def route_question(question: str, fallback_language: str = "en") -> Route:
    """Deterministic routing; no OpenAI call. Unknown or unsafe input fails safe."""
    language = detect_language(question, fallback_language)
    if not isinstance(question, str):
        return Route(UNSUPPORTED, language, "not_text")
    normalized = " ".join(question.split())
    if not normalized or len(normalized) > 200:
        return Route(UNSUPPORTED, language, "length")
    try:
        screen_and_redact(normalized, limit=200)
    except UnsafePrompt:
        return Route(UNSUPPORTED, language, "unsafe")
    if _PRIVATE.search(normalized):
        return Route(UNSUPPORTED, language, "private_data")
    if _BRAND.search(normalized):
        return Route(OFFICIAL_VORNEQ, language, "brand")
    if not re.search(r"\w{2,}", normalized):
        return Route(UNSUPPORTED, language, "no_terms")
    return Route(GENERAL_PUBLIC, language, "general")
