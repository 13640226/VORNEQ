"""Deterministic citation identity and verbatim-quote checks.

IMPORTANT: quote alignment is NOT semantic claim verification. We explicitly
return verified=False and do not claim factual truth.
"""
import hashlib
import re

from apps.ai_core.gateway import Citation, PUBLIC_LIBRARY_TYPES, PUBLIC_PREFIXES
from apps.ai_core.sanitization import screen_and_redact, UnsafePrompt

_ALLOWED = set(PUBLIC_PREFIXES.values()) | {"library:"}
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class EvidenceRejected(ValueError):
    code = "insufficient_evidence"


def _valid_key(key):
    return isinstance(key, str) and len(key) <= 100 and any(
        key.startswith(prefix) and len(key) > len(prefix) for prefix in _ALLOWED
    )


def authorized_context(sources):
    """Accept public-only snapshots; no private Document/MediaAsset selectors.

    The production retrieval caller must use published-only adapters. These
    snapshots are not proof of tenant authorization for any private data.
    """
    if not isinstance(sources, (tuple, list)) or len(sources) > 3:
        raise EvidenceRejected("invalid source collection")
    result, keys = [], set()
    for source in sources:
        if not isinstance(source, Citation) or not _valid_key(source.key):
            raise EvidenceRejected("source is outside public allowlist")
        if source.key.startswith("official:"):
            # An official prefix alone is not authority. Only exact reviewed
            # snapshots may pass; prevent spoofed URLs, titles or excerpts.
            from apps.ai_core.official_public_sources import retrieve_official_public
            trusted = {s.key: s for s in retrieve_official_public("VORNEQ", "en")}
            if source.key not in trusted or source != trusted[source.key]:
                raise EvidenceRejected("unreviewed official source")
        if source.key in keys:
            raise EvidenceRejected("duplicate source")
        keys.add(source.key)
        if source.url is not None and (
            not source.url.startswith("/") or source.url.startswith("//")
            or "\\" in source.url
        ):
            raise EvidenceRejected("unsafe source url")
        try:
            title = screen_and_redact(source.title, limit=140)
            excerpt = screen_and_redact(source.excerpt, limit=300)
        except UnsafePrompt as exc:
            raise EvidenceRejected("unsafe source data") from exc
        if not title or len(excerpt) < 8:
            continue
        source_id = "S" + str(len(result) + 1)
        evidence_digest = hashlib.sha256(
            ("\n".join((source.key, title, excerpt, source.url or ""))).encode("utf-8")
        ).hexdigest()
        result.append({
            "source_id": source_id,
            "source_key": source.key,
            "title": title,
            "excerpt": excerpt,
            "url": source.url,
            "evidence_digest": evidence_digest,
        })
    return result


def validate_generated(output, *, sources, language):
    """Reject fabricated IDs/digests/quotes or claimed independent verification.

    NOT an NLI/semantic-claim validator. Users must see verified=False.
    """
    fields = {"answer", "language", "citations", "model_status",
              "grounded_status", "verified", "error_code"}
    if not isinstance(output, dict) or set(output) != fields:
        raise EvidenceRejected("invalid output schema")
    if output["language"] != language or output["verified"] is not False:
        raise EvidenceRejected("language or verification claim invalid")
    if (output["model_status"] != "generated" or
            output["grounded_status"] != "proposed" or output["error_code"] != ""):
        raise EvidenceRejected("untrusted status claim")
    answer = output["answer"]
    if not isinstance(answer, str) or not 1 <= len(answer.strip()) <= 1000:
        raise EvidenceRejected("invalid generated answer")
    try:
        answer = screen_and_redact(answer, limit=1000)
    except UnsafePrompt as exc:
        raise EvidenceRejected("unsafe generated output") from exc
    cites = output["citations"]
    if not isinstance(cites, list) or not 1 <= len(cites) <= min(3, len(sources)):
        raise EvidenceRejected("missing or oversized citation list")
    source_map = {s["source_id"]: s for s in sources}
    used = set()
    for citation in cites:
        if not isinstance(citation, dict) or set(citation) != {
            "source_id", "evidence_digest", "evidence_quote"
        }:
            raise EvidenceRejected("citation shape mismatch")
        sid = citation["source_id"]
        if not isinstance(sid, str) or sid in used or sid not in source_map:
            raise EvidenceRejected("unknown or duplicate citation")
        used.add(sid)
        source = source_map[sid]
        if (citation["evidence_digest"] != source["evidence_digest"] or
                not isinstance(citation["evidence_digest"], str) or
                not _DIGEST.fullmatch(citation["evidence_digest"])):
            raise EvidenceRejected("citation snapshot digest mismatch")
        quote = citation["evidence_quote"]
        if (not isinstance(quote, str) or not 8 <= len(quote) <= 300 or
                quote not in source["excerpt"]):
            raise EvidenceRejected("citation lacks exact source evidence")
    return {
        "mode": "grounded_draft",
        "answer": answer,
        "language": language,
        "citations": [{k: v for k, v in s.items()
                       if k in ("source_id", "source_key", "title", "url", "evidence_digest")}
                      for s in sources if s["source_id"] in used],
        "verified": False,
        "model_status": "generated",
        "grounded_status": "citation_and_quote_checked_claims_unverified",
        "error_code": "",
    }
