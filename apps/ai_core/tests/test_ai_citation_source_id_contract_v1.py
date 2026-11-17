"""Offline citation identity hardening: synthetic evidence only, no OpenAI calls.

This intentionally tests the ORIGINAL strict fail-closed validator unchanged:
a better system prompt must never turn untrusted identifiers into trusted ones.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.ai_core.engine.citation import (
    CitationDigestRejected,
    CitationIdentityRejected,
    CitationQuoteRejected,
    GeneratedAnswerRejected,
    validate_generated,
)
from apps.ai_core.engine.global_grounded import ask_global, authorized_web_context
from apps.ai_core.providers.openai_responses import (
    OpenAIResponsesProvider, _SYSTEM_INSTRUCTIONS, build_request_payload,
)
from apps.ai_core.web_retrieval import WebEvidence, WikipediaRetriever


SOLAR_EVIDENCE = (
    "A solar cell converts sunlight into electrical energy. "
    "Its semiconductor absorbs light and produces electric current in a circuit."
)
BATTERY_EVIDENCE = (
    "A battery stores electrical energy by means of chemical reactions. "
    "This synthetic source is not evidence about the operation of solar cells."
)
TS = "2026-11-17T20:40:00+00:00"


def web_evidence(index, title, excerpt):
    return WebEvidence(
        f"web:wikipedia:en:{index}", title,
        f"https://en.wikipedia.org/wiki/SYNTHETIC_{index}",
        "Wikipedia (en)", excerpt, TS,
    )


def cited(s, *, source_id=None, digest=None, quote=None):
    return {
        "source_id": s["source_id"] if source_id is None else source_id,
        "evidence_digest": s["evidence_digest"] if digest is None else digest,
        "evidence_quote": s["excerpt"][:36] if quote is None else quote,
    }


def generated(citations, **changes):
    result = {
        "answer": "Sunlight is converted into electrical energy.",
        "language": "en",
        "citations": citations,
        "model_status": "generated",
        "grounded_status": "proposed",
        "verified": False,
        "error_code": "",
    }
    result.update(changes)
    return result


class CitationContractTests(SimpleTestCase):
    def setUp(self):
        self.sources = authorized_web_context(
            [
                web_evidence(1, "Solar cell", SOLAR_EVIDENCE),
                web_evidence(2, "Battery", BATTERY_EVIDENCE),
            ],
            allowed_hosts=WikipediaRetriever.allowed_hosts,
        )
        self.first, self.second = self.sources

    def check(self, payload):
        return validate_generated(payload, sources=self.sources, language="en")

    def test_instructions_use_current_source_id_not_other_identifiers(self):
        prompt = _SYSTEM_INSTRUCTIONS
        for clause in (
            "sources array", "source_id EXACTLY", "same source_id twice",
            "source_key", "URL", "earlier conversation turn",
            "evidence_digest EXACTLY", "SAME chosen source",
            "8-300 character evidence_quote",
            "Do not swap digests or quotes",
            "do not fabricate a source or quote",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, prompt)
        self.assertIn("verified=false", prompt)
        self.assertIn("model_status='generated'", prompt)

    def test_compact_payload_contains_exact_authorized_ids_and_digests(self):
        serialized = build_request_payload(
            "How does a solar cell work?", "en", self.sources,
            compact_sources=True,
            prior_turns=({"role": "assistant", "content": "Not a source."},),
        )
        payload = json.loads(serialized)
        self.assertEqual([s["source_id"] for s in payload["sources"]], ["S1", "S2"])
        for actual, trusted in zip(payload["sources"], self.sources):
            self.assertEqual(actual["evidence_digest"], trusted["evidence_digest"])
            self.assertEqual(actual["excerpt"], trusted["excerpt"])
            self.assertEqual(
                set(actual),
                {"source_id", "title", "excerpt", "evidence_digest"},
            )
        self.assertEqual(len(payload["prior_turns"]), 1)
        self.assertNotIn("source_key", serialized)

    def test_good_trusted_citation_still_accepted_as_unverified(self):
        output = self.check(generated([cited(self.first)]))
        self.assertEqual(output["citations"][0]["source_id"], "S1")
        self.assertEqual(output["citations"][0]["source_key"], self.first["source_key"])
        self.assertIs(output["verified"], False)

    def test_two_distinct_trusted_citations_still_accepted(self):
        output = self.check(generated([cited(self.first), cited(self.second)]))
        self.assertEqual([c["source_id"] for c in output["citations"]], ["S1", "S2"])

    def test_unknown_case_shift_sourcekey_and_index_all_rejected(self):
        for bad_id in ("S3", "s1", "S01", "S1 ", "1", self.first["source_key"]):
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(CitationIdentityRejected):
                    self.check(generated([cited(self.first, source_id=bad_id)]))

    def test_duplicate_source_id_rejected_even_with_valid_digest_quote(self):
        with self.assertRaises(CitationIdentityRejected):
            self.check(generated([cited(self.first), cited(self.first)]))

    def test_missing_or_oversized_citation_list_rejected(self):
        for bad in ([], [cited(self.first), cited(self.second), cited(self.first)]):
            with self.subTest(count=len(bad)), self.assertRaises(CitationIdentityRejected):
                self.check(generated(bad))

    def test_swapped_digest_rejected(self):
        with self.assertRaises(CitationDigestRejected):
            self.check(generated([
                cited(self.first, digest=self.second["evidence_digest"]),
            ]))

    def test_unchanged_source_id_with_fabricated_digest_rejected(self):
        with self.assertRaises(CitationDigestRejected):
            self.check(generated([cited(self.first, digest="0" * 64)]))

    def test_swapped_quote_rejected(self):
        with self.assertRaises(CitationQuoteRejected):
            self.check(generated([
                cited(self.first, quote=self.second["excerpt"][:36]),
            ]))

    def test_unknown_extra_citation_field_rejected(self):
        citation = cited(self.first)
        citation["source_key"] = self.first["source_key"]
        with self.assertRaises(CitationIdentityRejected):
            self.check(generated([citation]))

    def test_claim_of_independent_verification_rejected(self):
        with self.assertRaises(GeneratedAnswerRejected):
            self.check(generated([cited(self.first)], verified=True))


class SyntheticGlobalPathTests(SimpleTestCase):
    def test_invalid_model_source_id_fails_closed_without_automatic_regeneration(self):
        source = web_evidence(1, "Solar cell", SOLAR_EVIDENCE)
        class FakeRetriever:
            allowed_hosts = WikipediaRetriever.allowed_hosts
            name = "wikipedia"
            source_type = "encyclopedia"
            last_status = (("wikipedia", "synthetic"),)

            def __init__(self):
                self.searches = 0

            def search(self, query, language, limit=3):
                self.searches += 1
                return (source,)

        retriever = FakeRetriever()
        provider = Mock()
        provider.generate.return_value = generated([
            {"source_id": "S999", "evidence_digest": "a" * 64,
             "evidence_quote": SOLAR_EVIDENCE[:36]}
        ])
        with self.assertRaises(CitationIdentityRejected):
            ask_global(
                "How does a solar cell work?", "en",
                actor=SimpleNamespace(is_authenticated=True),
                provider=provider,
                retriever=retriever,
                enabled=True,
            )
        self.assertEqual(retriever.searches, 1)
        provider.generate.assert_called_once()
        sent = provider.generate.call_args.kwargs["sources"]
        self.assertEqual([s["source_id"] for s in sent], ["S1"])
        self.assertEqual(sent[0]["evidence_digest"], authorized_web_context(
            (source,), allowed_hosts=WikipediaRetriever.allowed_hosts
        )[0]["evidence_digest"])

    def test_provider_settings_retain_zero_retry_and_no_live_request(self):
        provider = OpenAIResponsesProvider(
            model="mock-only", timeout_s=60,
            max_output_tokens=2048, compact_sources=True,
        )
        self.assertEqual(provider.timeout_s, 60)
        self.assertTrue(provider.compact_sources)
        self.assertEqual(provider.max_output_tokens, 2048)
        # The test never invokes provider.generate or initializes the SDK.
