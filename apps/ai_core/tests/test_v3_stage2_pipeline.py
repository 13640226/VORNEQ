"""Offline end-to-end Stage-2 orchestration using a synthetic source only."""
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.ai_core.engine.global_grounded import ask_global
from apps.ai_core.engine.citation import CitationIdentityRejected
from apps.ai_core.web_retrieval import WebEvidence

EXCERPT = (
    "Solar cells turn sunlight into electricity using semiconductor materials. "
    "A photovoltaic solar cell generates electric current when exposed to light. "
    "This paragraph is synthetic test-only text, not a verified public excerpt. "
) * 3


class _SyntheticRetriever:
    allowed_hosts = frozenset({"en.wikipedia.org"})
    retrievers = (SimpleNamespace(name="wikipedia", source_type="encyclopedia"),)

    def __init__(self):
        self.requested_limits = []
        self.last_status = (("wikipedia", "ok"),)

    def search(self, query, language, limit=3):
        self.requested_limits.append(limit)
        return (WebEvidence(
            "web:wikipedia:en:123", "Solar cell",
            "https://en.wikipedia.org/wiki/Solar_cell",
            "Wikipedia (en)", EXCERPT, "2026-11-18T00:00:00+00:00", None,
        ),)


def generated(passage_id="S1.P1"):
    return {
        "language": "en",
        "sections": [{"kind": "answer", "heading": "Solar cells",
                      "text": "Solar cells turn sunlight into electricity.",
                      "passage_ids": [passage_id]}],
        "model_status": "generated", "grounded_status": "proposed",
        "verified": False, "error_code": "",
    }


class Stage2GlobalPipelineTests(SimpleTestCase):
    def test_uses_bounded_5_evidence_and_server_citations(self):
        retriever = _SyntheticRetriever()
        provider = Mock()
        provider.generate.return_value = generated()
        actor = SimpleNamespace(is_authenticated=True)
        result = ask_global(
            "What are solar cells?", "en", actor=actor, retriever=retriever,
            provider=provider, enabled=True, stage2=True,
            max_answer_chars=2400,
        )
        self.assertEqual(retriever.requested_limits, [5])
        self.assertEqual(result["format_version"], 2)
        self.assertEqual(result["route"], "general_public")
        self.assertEqual(result["sections"][0]["refs"], ["S1.P1"])
        self.assertEqual(result["citations"][0]["source_id"], "S1")
        self.assertEqual(result["citations"][0]["evidence_quote"],
                         result["citations"][0]["passages"][0]["quote"])
        self.assertFalse(result["verified"])
        call = provider.generate.call_args.kwargs
        self.assertEqual(call["mode"], "sectioned")
        self.assertEqual(call["sources"][0]["passages"][0]["passage_id"], "S1.P1")

    def test_different_request_passage_fails_without_retry(self):
        retriever = _SyntheticRetriever()
        provider = Mock()
        provider.generate.return_value = generated(passage_id="S5.P9")
        with self.assertRaises(CitationIdentityRejected):
            ask_global("What are solar cells?", "en",
                       actor=SimpleNamespace(is_authenticated=True),
                       retriever=retriever, provider=provider,
                       enabled=True, stage2=True, max_answer_chars=2400)
        provider.generate.assert_called_once()
