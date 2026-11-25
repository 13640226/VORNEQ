"""Fail-closed diagnosis of HTTP-200 knowledge responses; no paid calls."""
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.ai_core.providers.exceptions import ProviderInvalidResponse, ProviderOutputLimited
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core.tests.ledger_fakes import allow_paid_adapter_calls


class KnowledgeProviderIncompleteTests(SimpleTestCase):
    def setUp(self):
        # V4-01: Adapter-Unit-Test mit gemocktem SDK -> synthetische Ledger-Freigabe.
        allow_paid_adapter_calls(self, "text")
        self.provider = OpenAIResponsesProvider(model="gpt-5-mini", timeout_s=10, max_output_tokens=2048)

    def _call(self, status, reason=None, parsed=None):
        response = SimpleNamespace(
            status=status,
            incomplete_details=SimpleNamespace(reason=reason),
            output_parsed=parsed,
            usage=SimpleNamespace(input_tokens=12, output_tokens=2048),
        )
        client = Mock()
        client.responses.parse.return_value = response
        fake_openai = ModuleType("openai")
        fake_openai.OpenAI = Mock(return_value=client)
        for name in ("APITimeoutError", "APIConnectionError", "APIStatusError", "APIError"):
            setattr(fake_openai, name, type(name, (Exception,), {}))
        fake_pydantic = ModuleType("pydantic")
        fake_pydantic.ValidationError = type("ValidationError", (Exception,), {})
        fake_schema = ModuleType("apps.ai_core.schemas.response")
        fake_schema.KnowledgeAnswerSchema = type("KnowledgeAnswerSchema", (), {})
        with patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}), patch.dict(
            sys.modules, {
                "openai": fake_openai,
                "pydantic": fake_pydantic,
                "apps.ai_core.schemas.response": fake_schema,
            }
        ):
            try:
                self.provider.generate_knowledge(question="What is AI?", language="en")
            finally:
                client.responses.parse.assert_called_once()

    def test_token_exhaustion_has_distinct_error_and_usage(self):
        with self.assertLogs("apps.ai_core.providers.openai_responses", level="WARNING") as logs:
            with self.assertRaises(ProviderOutputLimited):
                self._call("incomplete", "max_output_tokens")
        self.assertEqual(self.provider.last_usage, (12, 2048))
        self.assertIn("reason=output_token_limit", logs.output[0])

    def test_other_incomplete_fails_closed(self):
        with self.assertRaises(ProviderInvalidResponse):
            self._call("incomplete", "content_filter")

    def test_completed_missing_schema_fails_closed(self):
        with self.assertRaises(ProviderInvalidResponse):
            self._call("completed")
