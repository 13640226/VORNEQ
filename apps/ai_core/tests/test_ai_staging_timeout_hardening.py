"""Offline Staging timeout and incomplete-result contract.

No network, credentials, provider billing, Render DB or real wall-clock delays.
Uses a synthetic OpenAI SDK module so these checks run in the normal CI
environment where the optional OpenAI SDK is deliberately absent.
"""
from apps.ai_core.tests.ledger_fakes import fake_reservation
import os
import runpy
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.providers.exceptions import (
    ProviderInvalidResponse, ProviderTimeout, ProviderUnavailable,
)
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core.views_global import (
    _provider_timeout_for_environment, _output_cap_for_environment,
    run_global_pipeline,
)


class HostedTimeoutPolicyTests(SimpleTestCase):
    def test_provider_timeout_scoped_to_staging(self):
        self.assertEqual(_provider_timeout_for_environment("staging"), 60)
        self.assertEqual(_provider_timeout_for_environment("production"), 60)
        self.assertEqual(_provider_timeout_for_environment("development"), 15)
        self.assertEqual(_provider_timeout_for_environment("unexpected"), 15)
        self.assertEqual(_output_cap_for_environment("staging"), 2048)
        self.assertEqual(_output_cap_for_environment("production"), 2048)

    def test_gunicorn_worker_timeout_leaves_headroom_only_for_staging(self):
        config = Path(settings.BASE_DIR) / "gunicorn.conf.py"
        self.assertTrue(config.is_file())
        for environment, expected in (
            ("staging", 100), ("production", 100), ("development", 30),
            ("unexpected", 30),
        ):
            with self.subTest(environment=environment), patch.dict(
                os.environ, {"VORNEQ_ENV": environment}
            ):
                result = runpy.run_path(str(config))
                self.assertEqual(result["timeout"], expected)
        self.assertGreater(100, _provider_timeout_for_environment("staging"))
        self.assertGreater(100, _provider_timeout_for_environment("production"))

    def test_provider_accepts_60_seconds_but_rejects_unsafe_values(self):
        accepted = OpenAIResponsesProvider(
            model="synthetic", timeout_s=60, max_output_tokens=2048)
        self.assertEqual(accepted.timeout_s, 60)
        for value in (0, 91, -1, True, None, float("nan")):
            with self.subTest(value=value), self.assertRaises(ProviderUnavailable):
                OpenAIResponsesProvider(model="synthetic", timeout_s=value,
                                        max_output_tokens=2048)
        with self.assertRaises(ProviderUnavailable):
            OpenAIResponsesProvider(model="synthetic", timeout_s=60,
                                    max_output_tokens=2049)

    @override_settings(VORNEQ_ENV="staging")
    def test_pipeline_refuses_staging_without_ledger_before_quota_or_provider(self):
        """V4-01: a ledger-less staging request is refused before any paid work."""
        question = "What is a public encyclopedia?"
        request = SimpleNamespace(user=SimpleNamespace(pk=3))
        with patch("apps.ai_core.views_global.route_question", return_value=SimpleNamespace(kind="GENERAL_PUBLIC")), \
             patch("apps.ai_core.views_global.ledger_enabled", return_value=False), \
             patch("apps.ai_core.views_global.reserve_global_request") as quota, \
             patch("apps.ai_core.staging_budget.reserve_staging_request") as staging_quota, \
             patch("apps.ai_core.views_global.OpenAIResponsesProvider") as provider_factory, \
             patch("apps.ai_core.views_global.default_retriever", return_value=object()) as retriever, \
             patch("apps.ai_core.views_global.ask_global") as ask:
            body, status, _meta = run_global_pipeline(request, question, "en")
        self.assertEqual((body, status), ({"error": "rate_limited"}, 429))
        provider_factory.assert_not_called()
        quota.assert_not_called()
        staging_quota.assert_not_called()
        retriever.assert_not_called()
        ask.assert_not_called()

    @override_settings(VORNEQ_ENV="staging")
    def test_pipeline_passes_staging_timeout_with_ledger_wrapper(self):
        question = "What is a public encyclopedia?"
        request = SimpleNamespace(user=SimpleNamespace(pk=3))
        expected = {"answer": "synthetic only"}
        with patch("apps.ai_core.views_global.route_question", return_value=SimpleNamespace(kind="GENERAL_PUBLIC")), \
             patch("apps.ai_core.views_global.ledger_enabled", return_value=True), \
             patch("apps.ai_core.views_global.reserve_global_request") as quota, \
             patch("apps.ai_core.views_global.OpenAIResponsesProvider") as provider_factory, \
             patch("apps.ai_core.paid_provider.BudgetedProvider") as budgeted, \
             patch("apps.ai_core.views_global.default_retriever", return_value=object()), \
             patch("apps.ai_core.views_global.ask_global", return_value=expected) as ask:
            body, status, meta = run_global_pipeline(request, question, "en")
        self.assertEqual((body, status), (expected, 200))
        self.assertEqual(provider_factory.call_count, 1)
        self.assertEqual(provider_factory.call_args.kwargs["timeout_s"], 60)
        self.assertEqual(provider_factory.call_args.kwargs["max_output_tokens"], 2048)
        budgeted.assert_called_once_with(provider_factory.return_value, actor_id=3)
        self.assertIs(meta["budgeted"], budgeted.return_value)
        self.assertEqual(quota.call_args.kwargs, {"burst_only": True})
        ask.assert_called_once()


class _SyntheticTimeout(Exception):
    pass


class _SyntheticStatusError(Exception):
    pass


class _SyntheticConnectionError(Exception):
    pass


class _SyntheticApiError(Exception):
    pass


class _SyntheticValidationError(Exception):
    pass


class _SyntheticGroundedAnswer:
    def __init__(self, result):
        self._result = result

    def model_dump(self):
        return self._result


def _synthetic_sdk_context(parse_side_effect=None, parse_return_value=None):
    """Create a fully mocked SDK and schema; impossible to open real sockets."""
    client = Mock()
    client.responses.parse.side_effect = parse_side_effect
    client.responses.parse.return_value = parse_return_value
    sdk = types.ModuleType("openai")
    sdk.OpenAI = Mock(return_value=client)
    sdk.APITimeoutError = _SyntheticTimeout
    sdk.APIStatusError = _SyntheticStatusError
    sdk.APIConnectionError = _SyntheticConnectionError
    sdk.APIError = _SyntheticApiError
    pydantic = types.ModuleType("pydantic")
    pydantic.ValidationError = _SyntheticValidationError
    schema = types.ModuleType("apps.ai_core.schemas.response")
    schema.GroundedAnswerSchema = _SyntheticGroundedAnswer
    return client, sdk, pydantic, schema


class SlowAndIncompleteProviderTests(SimpleTestCase):
    def setUp(self):
        self.provider = OpenAIResponsesProvider(
            model="synthetic-only", timeout_s=60, max_output_tokens=2048)
        self.sources = [{
            "source_id": "S1", "title": "Synthetic public source",
            "excerpt": "Synthetic public sentence.", "evidence_digest": "a" * 64,
            "url": "/en/",
        }]

    def invoke(self, *, parse_side_effect=None, parse_return_value=None, wrapped=True):
        client, sdk, pydantic, schema = _synthetic_sdk_context(
            parse_side_effect=parse_side_effect, parse_return_value=parse_return_value)
        reservation = fake_reservation()  # V7-01: strukturell gültige Reservierung
        with patch.dict(sys.modules, {
            "openai": sdk, "pydantic": pydantic,
            "apps.ai_core.schemas.response": schema,
        }), patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-never-live"}), \
             patch("apps.ai_core.budgeted_provider.ledger.reserve", return_value=reservation) as reserve, \
             patch("apps.ai_core.budgeted_provider.ledger.settle") as settle:
            call = BudgetedProvider(self.provider, actor_id=3).generate if wrapped else self.provider.generate
            error = None
            result = None
            try:
                result = call(question="What is a synthetic test?", language="en",
                              sources=self.sources)
            except (ProviderInvalidResponse, ProviderTimeout) as e:
                error = e
        return SimpleNamespace(
            client=client, factory=sdk.OpenAI, reserve=reserve, settle=settle,
            reservation=reservation, result=result, error=error,
        )

    def test_slow_timeout_has_one_sdk_attempt_and_uncertain_ledger_usage(self):
        def synthetic_delay_then_timeout(**kwargs):
            time.sleep(0.015)  # short deterministic simulation; no 60-second wait
            raise _SyntheticTimeout("synthetic slow upstream")

        result = self.invoke(parse_side_effect=synthetic_delay_then_timeout)
        self.assertIsInstance(result.error, ProviderTimeout)
        self.assertEqual(result.factory.call_count, 1)
        self.assertEqual(result.factory.call_args.kwargs["timeout"], 60)
        self.assertEqual(result.factory.call_args.kwargs["max_retries"], 0)
        self.assertEqual(result.client.responses.parse.call_count, 1)
        self.assertEqual(result.reserve.call_count, 1)
        result.settle.assert_called_once_with(
            result.reservation, usage=None, outcome="ProviderTimeout")
        self.assertIsNone(self.provider.last_usage)

    def test_delayed_completed_response_preserves_authoritative_usage(self):
        answer = {"answer": "Synthetic response", "language": "en"}
        def slow_but_completed(**kwargs):
            time.sleep(0.015)
            return SimpleNamespace(
                status="completed",
                output_parsed=_SyntheticGroundedAnswer(answer),
                usage=SimpleNamespace(input_tokens=221, output_tokens=314),
            )
        result = self.invoke(parse_side_effect=slow_but_completed)
        self.assertIsNone(result.error)
        self.assertEqual(result.result, answer)
        self.assertEqual(result.client.responses.parse.call_count, 1)
        self.assertEqual(self.provider.last_usage, (221, 314))
        result.settle.assert_called_once_with(
            result.reservation, usage=(221, 314), outcome="completed")

    def test_incomplete_at_output_limit_settles_observed_usage_once(self):
        response = SimpleNamespace(
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            output_parsed=None,
            usage=SimpleNamespace(input_tokens=811, output_tokens=2048),
        )
        with self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as logs:
            result = self.invoke(parse_return_value=response)
        self.assertIsInstance(result.error, ProviderInvalidResponse)
        self.assertEqual(self.provider.last_usage, (811, 2048))
        self.assertEqual(result.client.responses.parse.call_count, 1)
        self.assertEqual(result.reserve.call_count, 1)
        result.settle.assert_called_once_with(
            result.reservation, usage=(811, 2048),
            outcome="ProviderInvalidResponse")
        self.assertTrue(any("reason=max_output_tokens" in line for line in logs.output))

    def test_incomplete_without_usage_remains_uncertain_without_retry(self):
        unsafe_reason = "injected-secret-never-log"
        response = SimpleNamespace(
            status="incomplete",
            incomplete_details=SimpleNamespace(reason=unsafe_reason),
            output_parsed=None,
            usage=None,
        )
        with self.assertLogs("apps.ai_core.providers.openai_responses", "WARNING") as logs:
            result = self.invoke(parse_return_value=response)
        self.assertIsInstance(result.error, ProviderInvalidResponse)
        self.assertEqual(result.client.responses.parse.call_count, 1)
        self.assertIsNone(self.provider.last_usage)
        result.settle.assert_called_once_with(
            result.reservation, usage=None, outcome="ProviderInvalidResponse")
        self.assertTrue(any("reason=other" in line for line in logs.output))
        self.assertFalse(any(unsafe_reason in line for line in logs.output))
