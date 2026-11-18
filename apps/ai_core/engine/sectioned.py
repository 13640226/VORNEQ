"""Fail-closed validation of Stage 2 sectioned answers.

Only the server creates citations, snapshots, digests and exact passage quotes.
A citation is a claim-to-passage *link*, not semantic proof of factual truth.
"""
from __future__ import annotations

import re

from apps.ai_core.engine.evidence_ranking import numeric_tokens, unsupported_numbers
from apps.ai_core.engine.fa_normalize import prose
from apps.ai_core.engine.passages import Passage
from apps.ai_core.sanitization import screen_and_redact, UnsafePrompt
from apps.ai_core.engine.citation import (
    EvidenceRejected, GeneratedAnswerRejected, CitationIdentityRejected,
)

_ID = re.compile(r"S[1-5]\.P[1-9][0-9]?\Z")
_FIELDS = {"language", "sections", "model_status", "grounded_status", "verified", "error_code"}
_SECTION_FIELDS = {"kind", "heading", "text", "passage_ids"}


class UnsupportedSectionNumber(EvidenceRejected):
    code = "section_numeric_claim"


def _safe(value: str, limit: int) -> str:
    try:
        return screen_and_redact(value, limit=limit)
    except UnsafePrompt as exc:
        raise GeneratedAnswerRejected("unsafe answer section") from exc


def validate_sectioned(output, *, passages, sources, language, question="", max_chars=2400):
    if not isinstance(output, dict) or set(output) != _FIELDS:
        raise GeneratedAnswerRejected("invalid sectioned response fields")
    if (output["language"] != language or output["verified"] is not False
            or output["model_status"] != "generated"
            or output["grounded_status"] != "proposed"
            or output["error_code"] != ""):
        raise GeneratedAnswerRejected("untrusted sectioned response status")
    if type(max_chars) is not int or not 1 <= max_chars <= 2400:
        raise GeneratedAnswerRejected("invalid answer bound")
    sections = output["sections"]
    if not isinstance(sections, list) or not 1 <= len(sections) <= 6:
        raise GeneratedAnswerRejected("invalid section count")
    if (not isinstance(sources, (tuple, list)) or not 1 <= len(sources) <= 5
            or not isinstance(passages, (tuple, list)) or len(passages) > 24):
        raise GeneratedAnswerRejected("invalid evidence collection")
    source_map = {s["source_id"]: s for s in sources}
    if len(source_map) != len(sources):
        raise CitationIdentityRejected("duplicate sources")
    passage_map = {}
    for passage in passages:
        if (not isinstance(passage, Passage)
                or not _ID.fullmatch(passage.passage_id)
                or passage.passage_id in passage_map
                or passage.source_id not in source_map
                or not passage.passage_id.startswith(passage.source_id + ".")
                or not 80 <= len(passage.text) <= 300
                or passage.text not in source_map[passage.source_id]["excerpt"]):
            raise CitationIdentityRejected("invalid trusted passage collection")
        passage_map[passage.passage_id] = passage

    normalized = []
    usage: dict[str, list[int]] = {}
    distinct = set()
    has_answer = False
    for idx, section in enumerate(sections):
        if not isinstance(section, dict) or set(section) != _SECTION_FIELDS:
            raise GeneratedAnswerRejected("invalid section fields")
        kind, heading, content, refs = (section[k] for k in ("kind", "heading", "text", "passage_ids"))
        if (kind not in ("answer", "gap") or not isinstance(heading, str)
                or not isinstance(content, str) or not isinstance(refs, list)
                or len(heading) > 80 or not 1 <= len(content.strip()) <= 700):
            raise GeneratedAnswerRejected("invalid answer section")
        heading, content = _safe(heading, 80), _safe(content, 700)
        if kind == "gap":
            if (refs or len(content) > 200
                    or numeric_tokens(heading + " " + content)):
                raise GeneratedAnswerRejected("invalid evidence gap")
        else:
            has_answer = True
            if (not 1 <= len(refs) <= 4
                    or any(not isinstance(r, str) or not _ID.fullmatch(r)
                           or r not in passage_map for r in refs)
                    or len(set(refs)) != len(refs)):
                raise CitationIdentityRejected("unknown or duplicate passage")
            distinct.update(refs)
            if len(distinct) > 8:
                raise CitationIdentityRejected("too many referenced passages")
        if language == "fa":
            heading, content = prose(heading), prose(content)
        if kind == "answer" and unsupported_numbers(
                heading + " " + content, [passage_map[p].text for p in refs], question):
            raise UnsupportedSectionNumber("unsupported number in answer section")
        for ref in refs:
            usage.setdefault(ref, []).append(idx)
        normalized.append({"kind": kind, "heading": heading, "text": content, "refs": list(refs)})
    if not has_answer:
        raise GeneratedAnswerRejected("no grounded answer sections")

    text = "\n\n".join((s["heading"] + "\n" if s["heading"] else "") + s["text"]
                       for s in normalized)
    evidence_bound = min(2400, 400 + 250 * len(distinct))
    if len(text) > min(max_chars, evidence_bound):
        raise GeneratedAnswerRejected("answer exceeds evidence-backed length")

    citations = []
    for source in sources:
        cited = [p for p in passages if p.passage_id in usage and p.source_id == source["source_id"]]
        if not cited:
            continue
        citations.append({
            **{k: source[k] for k in (
                "source_id", "source_key", "title", "url", "publisher",
                "retrieved_at", "evidence_digest"
            ) if k in source},
            "evidence_quote": cited[0].text,
            "passages": [
                {"passage_id": p.passage_id, "quote": p.text,
                 "section_indices": usage[p.passage_id]} for p in cited
            ],
            "source_class": "public_web",
        })
    if not 1 <= len(citations) <= 5:
        raise CitationIdentityRejected("invalid cited source count")
    return {
        "mode": "grounded_draft", "format_version": 2, "answer": text,
        "sections": normalized, "language": language, "citations": citations,
        "verified": False, "model_status": "generated",
        "grounded_status": "passage_linked_claims_unverified", "error_code": "",
    }
