"""Global AI V1 orchestration: route -> trusted retrieval -> model -> validation.

The model may only cite sources returned by the trusted retrieval layer in
THIS request. Identity (key, URL, publisher, digest) comes from retrieval,
never from the model. Quote checks are not factual verification: the result
always keeps verified=False.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit

from apps.ai_core.engine.citation import EvidenceRejected, validate_generated
from apps.ai_core.engine.evidence_ranking import SCORE_SEMANTICS, rank_evidence, unsupported_numbers
from apps.ai_core.engine.grounded import ask_grounded
from apps.ai_core.global_router import GENERAL_PUBLIC, OFFICIAL_VORNEQ, route_question
from apps.ai_core.providers.exceptions import ProviderUnavailable
from apps.ai_core.sanitization import UnsafePrompt, screen_and_redact
from apps.ai_core.web_retrieval import MAX_EXCERPT, MAX_RESULTS, MAX_TITLE, WebEvidence


class GlobalUnsupported(ValueError):
    code = "UNSUPPORTED_QUESTION"


class UnsupportedNumericClaim(EvidenceRejected):
    """The generated answer contains a number absent from every cited excerpt."""


GLOBAL_INSTRUCTIONS = (
    "The excerpts are third-party public web pages (for example an encyclopedia), "
    "not VORNEQ statements. State uncertainty, estimates or ranges exactly as the "
    "excerpts do; never add numbers, dates or facts that are absent from them. "
    "If excerpts disagree, say so and cite each side. Keep source titles untranslated."
)


def evidence_digest(source_key, title, excerpt, url, publisher):
    return hashlib.sha256("\n".join((source_key, title, excerpt, url, publisher)).encode("utf-8")).hexdigest()


def authorized_web_context(evidence, *, allowed_hosts):
    """Accept only WebEvidence from an allowlisted host; skip unsafe snapshots."""
    if not isinstance(evidence, (tuple, list)) or len(evidence) > MAX_RESULTS:
        raise EvidenceRejected("invalid web evidence collection")
    result, keys, urls = [], set(), set()
    for item in evidence:
        if not isinstance(item, WebEvidence):
            raise EvidenceRejected("untrusted web evidence object")
        if not re.fullmatch(r"web:[a-z]{2,20}:(fa|de|en):[0-9A-Za-z_-]{1,40}", item.source_key):
            raise EvidenceRejected("invalid web source key")
        parts = urlsplit(item.url)
        if (parts.scheme != "https" or parts.hostname not in allowed_hosts or parts.port
                or parts.username or parts.password):
            raise EvidenceRejected("unsupported web source url")
        if item.source_key in keys or item.url in urls:
            continue
        try:
            title = screen_and_redact(item.title, limit=MAX_TITLE)
            excerpt = screen_and_redact(item.excerpt, limit=MAX_EXCERPT)
        except UnsafePrompt:
            # Untrusted page text that looks like an instruction is dropped,
            # never forwarded; other sources may still be used.
            continue
        if not title or len(excerpt) < 40 or "[REDACTED_" in excerpt:
            continue
        keys.add(item.source_key)
        urls.add(item.url)
        result.append({
            "source_id": "S" + str(len(result) + 1),
            "source_key": item.source_key,
            "title": title,
            "excerpt": excerpt,
            "url": item.url,
            "publisher": item.publisher,
            "retrieved_at": item.retrieved_at,
            "evidence_digest": evidence_digest(item.source_key, title, excerpt, item.url, item.publisher),
        })
    return result


def _insufficient(language, route):
    return {
        "mode": "insufficient_evidence", "answer": "", "language": language,
        "citations": [], "verified": False, "model_status": "not_called",
        "grounded_status": "insufficient_evidence", "error_code": "INSUFFICIENT_EVIDENCE",
        "route": route,
    }


def ask_global(question, fallback_language, *, actor, provider, retriever, enabled=False):
    if not enabled:
        raise GlobalUnsupported("Global AI disabled")
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise GlobalUnsupported("actor not authenticated")
    route = route_question(question, fallback_language)
    if route.kind == OFFICIAL_VORNEQ:
        result = dict(ask_grounded(question, route.language, actor=actor,
                                   provider=provider, enabled=True))
        result["route"] = OFFICIAL_VORNEQ
        return result
    if route.kind != GENERAL_PUBLIC:
        raise GlobalUnsupported(route.reason)
    language = route.language
    evidence = retriever.search(question, language, limit=MAX_RESULTS)
    source_types = _source_types(retriever)
    ranked, assessments = rank_evidence(question, language, evidence, source_types=source_types)
    sources = authorized_web_context(ranked, allowed_hosts=retriever.allowed_hosts)
    if not sources:
        return _insufficient(language, GENERAL_PUBLIC)
    if provider is None:
        raise ProviderUnavailable("no provider configured")
    output = provider.generate(question=screen_and_redact(question, limit=200),
                               language=language, sources=sources)
    result = validate_generated(output, sources=sources, language=language)
    trusted = {s["source_id"]: s for s in sources}
    cited = [trusted[c["source_id"]]["excerpt"] for c in result["citations"]]
    if unsupported_numbers(result["answer"], cited, question):
        raise UnsupportedNumericClaim("answer contains numbers absent from cited evidence")
    for citation in result["citations"]:
        source = trusted[citation["source_id"]]
        citation["publisher"] = source["publisher"]
        citation["retrieved_at"] = source["retrieved_at"]
        citation["source_class"] = "public_web"
    result["route"] = GENERAL_PUBLIC
    by_key = {a["source_key"]: a for a in assessments}
    result["evidence_assessment"] = {
        "score_semantics": SCORE_SEMANTICS,
        "sources_considered": len(sources),
        "providers": [{"name": n, "status": st} for n, st in getattr(retriever, "last_status", ())],
        "cited": [{k: by_key[c["source_key"]][k] for k in ("source_key", "relevance", "completeness", "score")}
                  for c in result["citations"] if c["source_key"] in by_key],
        "independent_verification": False,
    }
    return result


def _source_types(retriever):
    members = getattr(retriever, "retrievers", (retriever,))
    return {getattr(r, "name", ""): getattr(r, "source_type", "unknown") for r in members}
