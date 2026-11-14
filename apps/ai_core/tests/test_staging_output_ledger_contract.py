"""Staging-only output sizing and prepaid-ledger error settlement.

SYNTHETIC ONLY: no actual network, provider key, billing, or persistent DB.
"""
import importlib.util
import json
import os
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.providers.exceptions import ProviderInvalidResponse
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider, build_request_payload
from apps.ai_core.views_global import STAGING_BRIEF_INSTRUCTIONS, _output_cap_for_environment

HAS_PROVIDER_DEPS = bool(importlib.util.find_spec("openai") and importlib.util.find_spec("pydantic"))

SOURCES = [{
    "source_id": "S1",
    "source_key": "web:wikipedia:en:10",
    "title": "Berlin",
    "excerpt": "Berlin is Germany's capital city, and its largest city by population.",
    "evidence_digest": "a" * 64,
    "url": "https://en.wikipedia.org/wiki/Berlin",
    "publisher": "Wikipedia (en)",
    "retrieved_at": "2026-11-14T00:00:00+00:00",
}]


class StagingPromptBudgetContractTests(SimpleTestCase):
    def test_staging_only_cap(self):
        self.assertEqual(_output_cap_for_environment("staging"), 2048)
        self.assertEqual(_output_cap_for_environment("production"), 1024)
        self.assertEqual(_output_cap_for_environment("development"), 512)

    def test_compact_sources_preserve_trusted_citation_fields(self):
        full = build_request_payload("What is Berlin?", "en", SOURCES)
        compact = build_request_payload("What is Berlin?", "en", SOURCES, compact_sources=True)
        source = json.loads(compact)["sources"][0]
        self.assertEqual(set(source), {"source_id", "title", "excerpt", "evidence_digest"})
        self.assertEqual(source["evidence_digest"], SOURCES[0]["evidence_digest"])
        self.assertEqual(source["excerpt"], SOURCES[0]["excerpt"])
        self.assertEqual(json.loads(full)["sources"], SOURCES)
        self.assertNotIn("retrieved_at", compact)
        self.assertNotIn("source_key", compact)
        self.assertLess(len(compact), len(full))

    def test_ledger_estimates_the_exact_compact_prompt_bytes(self):
        class FakeProvider:
            model = "synthetic-model"
            max_output_tokens = 2048
            compact_sources = True
            instructions = "SYNTHETIC instructions"
            last_usage = None

            def generate(self, **kwargs):
                self.last_usage = (100, 20)
                return {"answer": "SYNTHETIC answer"}

        provider = FakeProvider()
        reservation = object()
        with patch("apps.ai_core.budgeted_provider.ledger.reserve", return_value=reservation) as reserve, \
                patch("apps.ai_core.budgeted_provider.ledger.settle") as settle:
            result = BudgetedProvider(provider, actor_id=3).generate(
                question="What is Berlin?", language="en", sources=SOURCES)
        self.assertEqual(result, {"answer": "SYNTHETIC answer"})
        payload = build_request_payload("What is Berlin?", "en", SOURCES, compact_sources=True)
        expected_bytes = len(provider.instructions.encode("utf-8")) + len(payload.encode("utf-8"))
        self.assertEqual(reserve.call_args.kwargs["input_bytes"], expected_bytes)
        self.assertEqual(reserve.call_args.kwargs["max_output_tokens"], 2048)
        settle.assert_called_once_with(reservation, usage=(100, 20), outcome="completed")


@skipUnless(HAS_PROVIDER_DEPS, "OpenAI/Pydantic optional SDK unavailable")
class IncompleteResponseLedgerTests(SimpleTestCase):
    def setUp(self):
        self.provider = OpenAIResponsesProvider(
            model="synthetic-model", timeout_s=5, max_output_tokens=2048,
            extra_instructions=STAGING_BRIEF_INSTRUCTIONS, compact_sources=True)

    def test_incomplete_with_observed_usage_is_finalized_once(self):
        response = SimpleNamespace(
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            output_parsed=None,
            usage=SimpleNamespace(input_tokens=1019, output_tokens=2048),
        )
        reservation = object()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-only"}), \
                patch("openai.OpenAI") as factory, \
                patch("apps.ai_core.budgeted_provider.ledger.reserve", return_value=reservation) as reserve, \
                patch("apps.ai_core.budgeted_provider.ledger.settle") as settle, \
                self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as logs:
            factory.return_value.responses.parse.return_value = response
            with self.assertRaises(ProviderInvalidResponse):
                BudgetedProvider(self.provider, actor_id=3).generate(
                    question="What is Berlin?", language="en", sources=SOURCES)
            kwargs = factory.return_value.responses.parse.call_args.kwargs
        self.assertEqual(kwargs["max_output_tokens"], 2048)
        self.assertTrue(any("reason=max_output_tokens" in x for x in logs.output))
        self.assertEqual(self.provider.last_usage, (1019, 2048))
        self.assertEqual(reserve.call_count, 1)
        settle.assert_called_once_with(
            reservation, usage=(1019, 2048), outcome="ProviderInvalidResponse")

    def test_incomplete_without_usage_keeps_uncertain_reservation(self):
        response = SimpleNamespace(
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            output_parsed=None, usage=None)
        reservation = object()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-only"}), \
                patch("openai.OpenAI") as factory, \
                patch("apps.ai_core.budgeted_provider.ledger.reserve", return_value=reservation), \
                patch("apps.ai_core.budgeted_provider.ledger.settle") as settle, \
                self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING"):
            factory.return_value.responses.parse.return_value = response
            with self.assertRaises(ProviderInvalidResponse):
                BudgetedProvider(self.provider, actor_id=3).generate(
                    question="What is Berlin?", language="en", sources=SOURCES)
        settle.assert_called_once_with(
            reservation, usage=None, outcome="ProviderInvalidResponse")
