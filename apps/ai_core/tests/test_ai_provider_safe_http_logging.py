"""Offline tests: OpenAI HTTP error logging must never disclose secrets or messages.

No provider calls; fixtures only. Optional SDK integration is mocked locally.
"""
import importlib.util
import os
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.ai_core.providers.exceptions import ProviderUnavailable
from apps.ai_core.tests.ledger_fakes import allow_paid_adapter_calls
from apps.ai_core.providers.openai_responses import (
    OpenAIResponsesProvider,
    _log_safe_api_status,
)


class SafeOpenAIHttpLogTests(SimpleTestCase):

    def setUp(self):
        super().setUp()
        # V4-01: Adapter-Unit-Test mit gemocktem SDK -> synthetische Ledger-Freigabe.
        allow_paid_adapter_calls(self, "text")
    def test_expected_operational_fields_only(self):
        error = SimpleNamespace(
            status_code=401,
            code="invalid_api_key",
            type="invalid_request_error",
            request_id="req_SyntheticABC123",
            body={"error": {"message": "NEVER_LOG_sk-synthetic-secret"}},
        )
        with self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as log:
            _log_safe_api_status(error)
        message = "\n".join(log.output)
        self.assertIn("http_status=401", message)
        self.assertIn("error_code=invalid_api_key", message)
        self.assertIn("error_type=invalid_request_error", message)
        self.assertIn("openai_request_id=req_SyntheticABC123", message)
        self.assertNotIn("NEVER_LOG", message)

    def test_untrusted_values_are_redacted_including_log_injection(self):
        error = SimpleNamespace(
            status_code="401",
            code="bad_code\nLEAKED_SECRET",
            type="bad type",
            request_id="req_Bad\r\nInjectedHeader",
            body={"error": {"message": "NEVER_LOG_sk-synthetic-secret"}},
        )
        with self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as log:
            _log_safe_api_status(error)
        message = "\n".join(log.output)
        self.assertIn("http_status=unavailable", message)
        self.assertIn("error_code=unavailable", message)
        self.assertIn("error_type=unavailable", message)
        self.assertIn("openai_request_id=unavailable", message)
        self.assertNotIn("LEAKED_SECRET", message)
        self.assertNotIn("InjectedHeader", message)
        self.assertNotIn("NEVER_LOG", message)

    def test_nested_error_and_response_header_fallback(self):
        error = SimpleNamespace(
            status_code=403, code=None, type=None, request_id=None,
            response=SimpleNamespace(headers={"x-request-id": "req_SyntheticHeader"}),
            body={"error": {"code": "permission_denied", "type": "permission_error",
                            "message": "NEVER_LOG_sensitive_body"}},
        )
        with self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as log:
            _log_safe_api_status(error)
        message = "\n".join(log.output)
        self.assertIn("http_status=403", message)
        self.assertIn("error_code=permission_denied", message)
        self.assertIn("error_type=permission_error", message)
        self.assertIn("openai_request_id=req_SyntheticHeader", message)
        self.assertNotIn("NEVER_LOG", message)


_HAS_SDK = bool(importlib.util.find_spec("openai")
                and importlib.util.find_spec("httpx2")
                and importlib.util.find_spec("pydantic"))


@skipUnless(_HAS_SDK, "OpenAI/httpx2 optional SDK not installed in standard CI")
class OfflineProviderHttpErrorIntegrationTests(SimpleTestCase):

    def setUp(self):
        super().setUp()
        # V4-01: Adapter-Unit-Test mit gemocktem SDK -> synthetische Ledger-Freigabe.
        allow_paid_adapter_calls(self, "text")
    def test_actual_sdk_status_error_is_caught_and_safely_logged(self):
        import httpx2
        from openai import APIStatusError

        raw = {"error": {"code": "invalid_api_key", "type": "invalid_request_error",
                         "message": "NEVER_LOG_sk-synthetic-secret"}}
        http_response = httpx2.Response(
            401,
            request=httpx2.Request("POST", "https://offline.invalid/v1/responses"),
            headers={"x-request-id": "req_SyntheticFromSDK"},
            json=raw,
        )
        failure = APIStatusError(
            "NEVER_LOG_secret_exception_message", response=http_response, body=raw
        )
        provider = OpenAIResponsesProvider(
            model="synthetic-only", timeout_s=5, max_output_tokens=128
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-synthetic-offline"}), patch(
            "openai.OpenAI"
        ) as factory:
            factory.return_value.responses.parse.side_effect = failure
            with self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as logs:
                with self.assertRaises(ProviderUnavailable):
                    provider.generate(question="synthetic public text", language="en", sources=[])
        message = "\n".join(logs.output)
        self.assertIn("http_status=401", message)
        self.assertIn("error_code=invalid_api_key", message)
        self.assertIn("error_type=invalid_request_error", message)
        self.assertIn("openai_request_id=req_SyntheticFromSDK", message)
        self.assertNotIn("NEVER_LOG", message)
        self.assertNotIn("sk-synthetic-offline", message)
