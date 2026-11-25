"""Offline provider response-contract tests; never contact OpenAI."""
import os
import importlib.util
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from unittest import skipUnless

from apps.ai_core.providers.exceptions import ProviderInvalidResponse
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core.tests.ledger_fakes import allow_paid_adapter_calls
HAS_PROVIDER_DEPS = bool(importlib.util.find_spec('openai') and importlib.util.find_spec('pydantic'))


@skipUnless(HAS_PROVIDER_DEPS, 'optional OpenAI/Pydantic dependencies not installed in base CI')
class ProviderStructuredResponseTests(SimpleTestCase):
    def setUp(self):
        # V4-01: Adapter-Unit-Test mit gemocktem SDK -> synthetische Ledger-Freigabe.
        allow_paid_adapter_calls(self, "text")
        self.provider = OpenAIResponsesProvider(
            model="mock-only", timeout_s=5, max_output_tokens=2048)
        self.sources = [{"source_id": "S1", "source_key": "official:home",
                         "title": "Public", "excerpt": "A public excerpt",
                         "evidence_digest": "a" * 64, "url": "/en/"}]

    def _generate(self, response):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-only"}), patch(
            "openai.OpenAI"
        ) as factory:
            factory.return_value.responses.parse.return_value = response
            result = self.provider.generate(
                question="VORNEQ چیست؟", language="fa", sources=self.sources)
            return result, factory.return_value.responses.parse.call_args

    def test_completed_structured_response_parses_offline(self):
        from apps.ai_core.schemas.response import GroundedAnswerSchema
        parsed = GroundedAnswerSchema(
            answer="پاسخ مستند", language="fa", citations=[{
                "source_id": "S1", "evidence_digest": "a" * 64,
                "evidence_quote": "A public excerpt",
            }], model_status="generated", grounded_status="proposed",
            verified=False, error_code="")
        result, call = self._generate(
            SimpleNamespace(status="completed", output_parsed=parsed))
        self.assertEqual(result["answer"], "پاسخ مستند")
        self.assertEqual(call.kwargs["max_output_tokens"], 2048)
        self.assertFalse(call.kwargs["store"])
        self.assertEqual(call.kwargs["tools"], [])

    def test_incomplete_token_limit_fails_closed_with_safe_reason(self):
        response = SimpleNamespace(
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            output_parsed=None)
        with self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as logs:
            with self.assertRaises(ProviderInvalidResponse):
                self._generate(response)
        self.assertTrue(any("reason=max_output_tokens" in x for x in logs.output))

    def test_parse_failure_after_http_200_logs_only_safe_reason_and_never_retries(self):
        secret = "PRIVATE_PROVIDER_BODY_SENTINEL"
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-only"}), \
                patch("openai.OpenAI") as factory, \
                self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as logs:
            factory.return_value.responses.parse.side_effect = ValueError(secret)
            with self.assertRaises(ProviderInvalidResponse):
                self.provider.generate(question="How do solar cells work?",
                                       language="en", sources=self.sources)
        factory.return_value.responses.parse.assert_called_once()
        self.assertEqual(logs.output, [
            "WARNING:apps.ai_core.providers.openai_responses:"
            "ai_provider_parse_rejected reason=invalid_response",
        ])
        self.assertNotIn(secret, "".join(logs.output))

    def test_provider_rejects_token_cap_above_2048(self):
        from apps.ai_core.providers.exceptions import ProviderUnavailable
        with self.assertRaises(ProviderUnavailable):
            OpenAIResponsesProvider(
                model="mock-only", timeout_s=5, max_output_tokens=2049)

    def test_completed_without_parsed_output_fails_closed(self):
        with self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as logs:
            with self.assertRaises(ProviderInvalidResponse):
                self._generate(SimpleNamespace(status="completed", output_parsed=None))
        self.assertTrue(any("ai_provider_parse_missing" in x for x in logs.output))
