"""Offline-only tests for the optional model-specific Stage 2 output budget."""
import importlib.util
import json
import os
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.chat_output_budget import configured_output_budget
from apps.ai_core.engine.citation import GeneratedAnswerRejected, validate_sectioned
from apps.ai_core.engine.fa_normalize import prose
from apps.ai_core.engine.passages import split
from apps.ai_core.providers.exceptions import (ProviderContextLimited, ProviderInvalidResponse,
                                                    ProviderOutputLimited, ProviderUnavailable)
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core.tests.test_v3_stage2_contract import SOURCE, valid_output
from apps.ai_core.tests.test_v3_stage2_pipeline import _SyntheticRetriever
from apps.ai_core.views_global import ask_global_view

PILOT = dict(VORNEQ_ENV="development", VORNEQ_AI_RESPONSE_V3_ENABLED=True,
             VORNEQ_AI_RESPONSE_V3_STAGE2_ENABLED=True,
             VORNEQ_AI_CHAT_BUDGET_MODEL="mock-only",
             VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET="4096",
             VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS="32768")


HAS_PROVIDER_DEPS = bool(importlib.util.find_spec("openai") and importlib.util.find_spec("pydantic"))


@override_settings(**PILOT)
class OutputBudgetTests(SimpleTestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"VORNEQ_AI_PHASE_B_MODEL": "mock-only", "OPENAI_API_KEY": "synthetic-only"})
        env.start()
        self.addCleanup(env.stop)

    def provider(self):
        return OpenAIResponsesProvider(model="mock-only", timeout_s=5,
                                       max_output_tokens=4096, response_v3_enabled=True,
                                       response_stage2_enabled=True)

    def test_production_and_invalid_config_cannot_enable_pilot(self):
        self.assertEqual(configured_output_budget().output_tokens, 4096)
        for settings in ({"VORNEQ_ENV": "production"}, {"VORNEQ_AI_RESPONSE_V3_STAGE2_ENABLED": False},
                         {"VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET": "8193"},
                         {"VORNEQ_AI_CHAT_BUDGET_MODEL": "other"},
                         {"VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS": "8191"}):
            with self.subTest(settings=settings), override_settings(**settings):
                self.assertIsNone(configured_output_budget())
                with self.assertRaises(ProviderUnavailable):
                    self.provider()

    @override_settings(VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS="8192")
    def test_exact_context_headroom_boundary(self):
        self.assertEqual(configured_output_budget().context_tokens, 8192)
        self.assertEqual(self.provider().max_output_tokens, 4096)

    def test_staging_needs_approved_model_ledger_and_recovery(self):
        with override_settings(VORNEQ_ENV="staging", VORNEQ_AI_STAGING_APPROVED_MODEL="mock-only",
                               VORNEQ_AI_LEDGER_ENABLED=False, VORNEQ_AI_CHAT_RECOVERY_ENABLED=True):
            self.assertIsNone(configured_output_budget())

    def test_context_bound_fails_before_reserve_and_generation(self):
        provider = self.provider()
        provider.generate = Mock()
        with patch("apps.ai_core.budgeted_provider.ledger.reserve") as reserve:
            with self.assertRaises(ProviderContextLimited):
                BudgetedProvider(provider, actor_id=1).generate(
                    question="x" * 40000, language="en", sources=[])
        reserve.assert_not_called()
        provider.generate.assert_not_called()

    @override_settings(VORNEQ_ENV="staging", VORNEQ_AI_STAGING_APPROVED_MODEL="mock-only",
                       VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS="8192",
                       VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET="8192",
                       VORNEQ_AI_LEDGER_ENABLED=True,
                       VORNEQ_AI_LEDGER_ID="fba6bd94-96bb-4094-818f-84c0935ed211",
                       VORNEQ_AI_LEDGER_DB_NAME="test_only",
                       VORNEQ_AI_CHAT_RECOVERY_ENABLED=True)
    def test_http_context_413_precedes_reservation_and_provider(self):
        question = ("solar cells " * 300).strip()
        request = RequestFactory().post("/api/ai/v1/ask-global/",
            data=json.dumps({"question": question, "language": "en"}),
            content_type="application/json", HTTP_X_VQ_REQUEST_ID="synthetic")
        request.user = SimpleNamespace(is_authenticated=True, pk=1)
        request._dont_enforce_csrf_checks = True
        with patch("apps.ai_core.views_global.global_ai_available", return_value=True), patch(
                "apps.ai_core.views_global.actor_allowed", return_value=True), patch(
                "apps.ai_core.views_global.reserve_global_request"), patch(
                "apps.ai_core.views_global.default_retriever", return_value=_SyntheticRetriever()), patch(
                "apps.ai_core.request_recovery.claim", return_value={"status": "claimed"}), patch(
                "apps.ai_core.request_recovery.finish") as finish, patch(
                "apps.ai_core.budgeted_provider.ledger.reserve") as reserve, patch("apps.ai_core.providers.openai_responses.OpenAIResponsesProvider.generate") as sdk:
            response = ask_global_view(request)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(json.loads(response.content), {"error": "context_limit_reached"})
        reserve.assert_not_called()
        sdk.assert_not_called()
        finish.assert_called_once_with(request, "synthetic", http_status=413,
                                       response={"error": "context_limit_reached"})

    def test_larger_cap_is_reserved_exactly_and_only_one_call(self):
        provider = self.provider()
        provider.generate = Mock(return_value={})
        with patch("apps.ai_core.budgeted_provider.ledger.reserve") as reserve, \
                patch("apps.ai_core.budgeted_provider.ledger.settle") as settle:
            BudgetedProvider(provider, actor_id=1).generate(
                question="synthetic", language="en", sources=[], mode="sectioned")
        self.assertEqual(reserve.call_args.kwargs["max_output_tokens"], 4096)
        provider.generate.assert_called_once()
        settle.assert_called_once()

    def test_long_section_preserves_evidence_and_no_truncation(self):
        policy = configured_output_budget()
        passages = split([SOURCE])
        refs = [p.passage_id for p in passages[:4]]
        self.assertGreaterEqual(len(refs), 3)
        text = ("Solar cells produce electricity from sunlight. " * 20).strip()
        self.assertGreater(len(text), 700)
        data = valid_output(text=text)
        data["sections"][0]["passage_ids"] = refs[:3]
        with self.assertRaises(GeneratedAnswerRejected):
            validate_sectioned(data, passages=passages, sources=[SOURCE], language="en")
        result = validate_sectioned(data, passages=passages, sources=[SOURCE], language="en",
                                    max_chars=policy.answer_chars, output_budget=policy)
        self.assertEqual(result["answer"], text)
        self.assertFalse(result["verified"])
        data["sections"][0]["passage_ids"] = refs[:1]
        with self.assertRaises(GeneratedAnswerRejected):
            validate_sectioned(data, passages=passages, sources=[SOURCE], language="en",
                               max_chars=policy.answer_chars, output_budget=policy)

    @skipUnless(HAS_PROVIDER_DEPS, "OpenAI/Pydantic optional SDK unavailable")
    def test_provider_incomplete_does_not_return_partial_json(self):
        from apps.ai_core.tests.ledger_fakes import allow_paid_adapter_calls

        allow_paid_adapter_calls(self)  # V4-01: Adapter direkt, SDK gemockt
        provider = self.provider()
        response = SimpleNamespace(status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            usage=SimpleNamespace(input_tokens=100, output_tokens=4096))
        with patch("openai.OpenAI") as client:
            client.return_value.responses.parse.return_value = response
            with self.assertRaises(ProviderOutputLimited):
                provider.generate(question="synthetic", language="en", sources=[], mode="sectioned")
        self.assertEqual(provider.last_usage, (100, 4096))
        client.assert_called_once()
        client.return_value.responses.parse.assert_called_once()

    @skipUnless(HAS_PROVIDER_DEPS, "OpenAI/Pydantic optional SDK unavailable")
    def test_incomplete_settles_observed_usage_without_retry(self):
        provider = self.provider()
        reservation = object()
        response = SimpleNamespace(status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            usage=SimpleNamespace(input_tokens=100, output_tokens=4096))
        with patch("openai.OpenAI") as client, patch(
                "apps.ai_core.budgeted_provider.ledger.reserve", return_value=reservation) as reserve, patch(
                "apps.ai_core.budgeted_provider.ledger.settle") as settle, patch(
                "apps.ai_core.budgeted_provider.ledger.release") as release:
            client.return_value.responses.parse.return_value = response
            with self.assertRaises(ProviderOutputLimited):
                BudgetedProvider(provider, actor_id=1).generate(
                    question="synthetic", language="en", sources=[], mode="sectioned")
        self.assertEqual(client.call_args.kwargs["max_retries"], 0)
        client.return_value.responses.parse.assert_called_once()
        reserve.assert_called_once()
        settle.assert_called_once_with(reservation, usage=(100, 4096), outcome="ProviderOutputLimited")
        release.assert_not_called()

    @skipUnless(HAS_PROVIDER_DEPS, "OpenAI/Pydantic optional SDK unavailable")
    def test_sdk_parse_exception_without_usage_keeps_reservation_uncertain(self):
        provider = self.provider()
        provider.last_usage = (111, 222)  # stale usage must never leak into settlement
        reservation = object()
        with patch("openai.OpenAI") as client, patch(
                "apps.ai_core.budgeted_provider.ledger.reserve", return_value=reservation) as reserve, patch(
                "apps.ai_core.budgeted_provider.ledger.settle") as settle, patch(
                "apps.ai_core.budgeted_provider.ledger.release") as release:
            client.return_value.responses.parse.side_effect = ValueError("synthetic incomplete JSON")
            with self.assertRaises(ProviderInvalidResponse):
                BudgetedProvider(provider, actor_id=1).generate(
                    question="synthetic", language="en", sources=[], mode="sectioned")
        self.assertEqual(client.call_args.kwargs["max_retries"], 0)
        client.return_value.responses.parse.assert_called_once()
        reserve.assert_called_once()
        settle.assert_called_once_with(reservation, usage=None, outcome="ProviderInvalidResponse")
        release.assert_not_called()

    def test_persian_citation_fields_remain_exact(self):
        source = dict(SOURCE, excerpt=SOURCE["excerpt"].replace("Solar", "\u0645\u064a \u0631\u0648\u062f"))
        passages = split([source])
        data = valid_output(text="\u0645\u064a \u0631\u0648\u062f")
        data["language"] = "fa"
        result = validate_sectioned(data, passages=passages, sources=[source], language="fa")
        self.assertEqual(result["citations"][0]["source_id"], source["source_id"])
        self.assertEqual(result["citations"][0]["evidence_digest"], source["evidence_digest"])
        self.assertEqual(result["citations"][0]["evidence_quote"], passages[0].text)
        self.assertEqual(result["citations"][0]["passages"][0]["passage_id"], passages[0].passage_id)

    def test_persian_normalization_protects_code_and_urls(self):
        phrase = "\u0645\u064a \u0631\u0648\u062f"
        code = "\x60" + phrase + "\x60"
        fence = "\x60" * 3 + "python\n" + phrase + "\n" + "\x60" * 3
        url = "https://example.invalid/" + phrase.replace(" ", "")
        text = phrase + "\n" + code + "\n" + fence + "\n" + url
        normalized = prose(text)
        self.assertNotEqual(normalized, text)
        self.assertIn(code, normalized)
        self.assertIn(fence, normalized)
        self.assertIn(url, normalized)
