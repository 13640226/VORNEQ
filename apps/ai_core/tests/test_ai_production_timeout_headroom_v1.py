"""Offline Production timeout + Ledger invariants (no network, secrets or paid API).

Regression for the 2026-11-17 HTTP 500 Gunicorn WORKER TIMEOUT.
"""
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.providers.exceptions import ProviderTimeout
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core.tests.test_ai_staging_timeout_hardening import (
    _synthetic_sdk_context, _SyntheticTimeout,
)
from apps.ai_core.views_global import (
    _provider_timeout_for_environment, _output_cap_for_environment,
    run_global_pipeline,
)


class ProductionHeadroomTests(SimpleTestCase):
    def test_worker_headroom_for_every_environment(self):
        config = Path(settings.BASE_DIR) / "gunicorn.conf.py"
        self.assertTrue(config.is_file())
        for name, provider_seconds, worker_seconds in (
            ("production", 60, 100), ("staging", 60, 100),
            ("development", 15, 30), ("unexpected", 15, 30),
        ):
            with self.subTest(environment=name), patch.dict(os.environ, {"VORNEQ_ENV": name}):
                self.assertEqual(_provider_timeout_for_environment(name), provider_seconds)
                self.assertEqual(runpy.run_path(str(config))["timeout"], worker_seconds)
                self.assertGreater(worker_seconds, provider_seconds)
        self.assertEqual(_output_cap_for_environment("production"), 2048)

    @override_settings(VORNEQ_ENV="production")
    def test_pipeline_passes_60s_with_one_ledger_wrapper_and_no_staging_quota(self):
        request = SimpleNamespace(user=SimpleNamespace(pk=3))
        answer = {"answer": "offline synthetic only"}
        with patch("apps.ai_core.views_global.route_question",
                   return_value=SimpleNamespace(kind="GENERAL_PUBLIC")), \
             patch("apps.ai_core.views_global.ledger_enabled", return_value=True), \
             patch("apps.ai_core.views_global.reserve_global_request") as quota, \
             patch("apps.ai_core.views_global.reserve_staging_request") as staging_quota, \
             patch("apps.ai_core.views_global.OpenAIResponsesProvider") as provider, \
             patch("apps.ai_core.views_global.BudgetedProvider") as budgeted, \
             patch("apps.ai_core.views_global.default_retriever", return_value=object()), \
             patch("apps.ai_core.views_global.ask_global", return_value=answer) as ask:
            body, code, meta = run_global_pipeline(request, "Who was Ibn Sina?", "en")
        self.assertEqual((body, code), (answer, 200))
        provider.assert_called_once()
        self.assertEqual(provider.call_args.kwargs["timeout_s"], 60)
        self.assertEqual(provider.call_args.kwargs["max_output_tokens"], 2048)
        budgeted.assert_called_once()
        self.assertIs(meta["budgeted"], budgeted.return_value)
        self.assertIs(ask.call_args.kwargs["provider"], budgeted.return_value)
        quota.assert_called_once()
        staging_quota.assert_not_called()

    def test_timeout_remains_single_attempt_with_uncertain_ledger_settlement(self):
        provider = OpenAIResponsesProvider(
            model="offline-test-only", timeout_s=60, max_output_tokens=2048,
        )
        client, sdk, pydantic, schema = _synthetic_sdk_context(
            parse_side_effect=_SyntheticTimeout("synthetic network timeout")
        )
        reservation = object()
        sources = [{"source_id": "S1", "title": "Synthetic only",
                    "excerpt": "A synthetic excerpt with more than eight characters.",
                    "evidence_digest": "a" * 64, "url": "https://example.org/example"}]
        with patch.dict(sys.modules, {
            "openai": sdk, "pydantic": pydantic,
            "apps.ai_core.schemas.response": schema,
        }), patch.dict(
            os.environ, {"OPENAI_API_KEY": "offline-placeholder-not-real"}
        ), patch(
            "apps.ai_core.budgeted_provider.ledger.reserve",
            return_value=reservation
        ) as reserve, patch(
            "apps.ai_core.budgeted_provider.ledger.settle"
        ) as settle:
            with self.assertRaises(ProviderTimeout):
                BudgetedProvider(provider, actor_id=3).generate(
                    question="Who was Ibn Sina?", language="en", sources=sources
                )
        self.assertEqual(sdk.OpenAI.call_args.kwargs["timeout"], 60)
        self.assertEqual(sdk.OpenAI.call_args.kwargs["max_retries"], 0)
        self.assertEqual(client.responses.parse.call_count, 1)
        reserve.assert_called_once()
        settle.assert_called_once_with(reservation, usage=None, outcome="ProviderTimeout")
        self.assertIsNone(provider.last_usage)
