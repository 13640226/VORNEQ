"""Global AI V2: deterministic evidence assessment and ranking.

Scores describe OBSERVABLE retrieval properties (query-term overlap, content
completeness, provenance metadata, source type). They are NOT a measure of
factual truth, and agreement between sources is NOT independent verification.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from apps.ai_core.web_retrieval import WebEvidence

MAX_SELECTED = 3
MIN_RELEVANCE = 0.25
SCORE_SEMANTICS = "retrieval_relevance_not_truth"

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی", "ة": "ه"})
_TOKEN = re.compile(r"[\w\u200c]+", re.UNICODE)
_STOP = {
    "fa": set("آیا چه چی چیست چیه چگونه چطور چرا چند کدام کجا کی که را از در به با و یا "
              "این آن است هست هستند دارد دارند می شود شوند بود ها های یک برای تا هم".split()),
    "de": set("was wie warum wieso weshalb welche welcher welches wer wo wann ist sind gibt es "
              "der die das den dem des ein eine einen einem und oder zu von mit im in auf für "
              "nicht über kann können wird werden hat haben".split()),
    "en": set("what how why which who where when is are was were does do did the a an and or "
              "of to in on for with by from can could will would there it its this that many "
              "much explain about".split()),
}
TYPE_WEIGHT = {"encyclopedia": 0.6, "reference": 0.6, "scientific_agency": 0.9,
               "peer_reviewed": 1.0, "unknown": 0.3}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").translate(_DIGITS).translate(_ARABIC_TO_PERSIAN)
    return text.casefold()


def terms(text: str, language: str) -> list[str]:
    stop = _STOP.get(language, set()) | _STOP["en"]
    out = []
    for token in _TOKEN.findall(normalize_text(text)):
        token = token.replace("\u200c", "")
        if len(token) >= 2 and token not in stop and token not in out:
            out.append(token)
    return out


def _matches(term: str, words: set[str]) -> bool:
    if term in words:
        return True
    # Light, language-agnostic morphology: plural/case suffixes (کهکشان\u200cها, Sterne).
    return len(term) >= 4 and any(
        len(w) >= 4 and (w.startswith(term) or term.startswith(w)) for w in words)


def _iso(value):
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def assess(question: str, language: str, item: WebEvidence, source_type: str = "unknown") -> dict:
    query = terms(question, language)
    words = {w.replace("\u200c", "") for w in _TOKEN.findall(normalize_text(item.title + " " + item.excerpt))}
    matched = [t for t in query if _matches(t, words)]
    relevance = round(len(matched) / len(query), 3) if query else 0.0
    completeness = round(min(len(item.excerpt) / 300, 1.0), 3)
    provenance = (0.5 if _iso(item.retrieved_at) else 0.0) + (0.5 if _iso(item.published_at) else 0.0)
    type_weight = TYPE_WEIGHT.get(source_type, TYPE_WEIGHT["unknown"])
    score = round(0.6 * relevance + 0.2 * completeness + 0.1 * provenance + 0.1 * type_weight, 3)
    return {"source_key": item.source_key, "relevance": relevance, "matched_terms": len(matched),
            "query_terms": len(query), "completeness": completeness, "provenance": provenance,
            "source_type": source_type, "score": score}


def _fingerprint(item: WebEvidence):
    return (normalize_text(item.title).strip(), normalize_text(item.excerpt)[:200])


def rank_evidence(question, language, evidence, *, source_types=None):
    """Return (selected evidence, assessments) — deterministic, bounded, deduplicated."""
    source_types = source_types or {}
    seen_keys, seen_prints, candidates = set(), set(), []
    for order, item in enumerate(evidence):
        if not isinstance(item, WebEvidence):
            continue
        fp = _fingerprint(item)
        if item.source_key in seen_keys or item.url in seen_keys or fp in seen_prints:
            continue
        seen_keys.update((item.source_key, item.url))
        seen_prints.add(fp)
        provider = item.source_key.split(":")[1] if item.source_key.count(":") >= 3 else ""
        info = assess(question, language, item, source_types.get(provider, "unknown"))
        if info["matched_terms"] >= 1 and info["relevance"] >= MIN_RELEVANCE:
            candidates.append((-info["score"], order, item, info))
    candidates.sort(key=lambda c: (c[0], c[1]))
    selected = candidates[:MAX_SELECTED]
    return tuple(c[2] for c in selected), [c[3] for c in selected]


_NUMBER = re.compile(r"\d+(?:[.,٫٬'’  ]\d{3})*(?:[.,٫]\d+)?")


def numeric_tokens(text: str) -> set[str]:
    """Digit sequences with separators removed (۱۲۳ == 123, 100,000 == 100000)."""
    normalized = unicodedata.normalize("NFKC", text or "").translate(_DIGITS)
    return {re.sub(r"\D", "", m) for m in _NUMBER.findall(normalized) if re.sub(r"\D", "", m)}


def unsupported_numbers(answer: str, cited_excerpts, question: str = "") -> set[str]:
    """Numbers in the answer that appear neither in a cited excerpt nor in the question."""
    allowed = numeric_tokens(question)
    for excerpt in cited_excerpts:
        allowed |= numeric_tokens(excerpt)
    return numeric_tokens(answer) - allowed
