"""V4-01 — NO PAID AI CALL WITHOUT VALID LEDGER AUTHORIZATION (Laufzeitnachweis).

Alle Tests laufen offline: echter OpenAI-Client und Netzwerk sind blockiert
(NoNetworkMixin), Provider-Ausgaben sind synthetisch, das Ledger ist entweder
abgeschaltet, gezielt gestört oder per Mock simuliert. Kein kostenpflichtiger
Aufruf, keine Ledger-Datenbank.
"""
import json
import os
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.ai_core import paid_provider
from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.models import StagingAIBudgetDay
from apps.ai_core.providers.exceptions import ProviderTimeout
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider
from apps.ai_core.tests.ledger_fakes import fake_reservation, start_fake_ledger
from apps.ai_core.tests.test_ai_staging_trial import STAGING_SETTINGS, TEST_ENV
from apps.ai_core.tests.test_global_ai_api import FakeRetriever, NoNetworkMixin, evidence, good_output
from apps.ai_ledger.service import BudgetExhausted, EmergencyStop, LedgerUnavailable, StagingDailyCapReached

CHAT = {**STAGING_SETTINGS, "VORNEQ_GLOBAL_AI_ENABLED": True}
QUESTION = {"question": "What is quantum computing?", "language": "en"}


def produce(_self, *, question, language, sources, **_kwargs):
    return good_output(sources, language)


class HostedPaidPathMixin(NoNetworkMixin):
    """Staging trial actor, synthetic provider output, no ledger by default."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username=f"v4-owner-{uuid.uuid4().hex[:6]}", email="v4-owner@example.invalid",
            password="synthetic-local-only")
        cls.other = get_user_model().objects.create_user(
            username=f"v4-other-{uuid.uuid4().hex[:6]}", email="v4-other@example.invalid",
            password="synthetic-local-only")

    def setUp(self):
        super().setUp()
        for patcher in (
            patch.dict(os.environ, TEST_ENV),
            override_settings(VORNEQ_AI_STAGING_ALLOWED_USER_IDS=str(self.owner.pk)),
            patch("apps.ai_core.views_global.default_retriever", return_value=FakeRetriever(evidence("en"))),
        ):
            patcher.enable() if hasattr(patcher, "enable") else patcher.start()
            self.addCleanup(patcher.disable if hasattr(patcher, "disable") else patcher.stop)
        generate = patch.object(OpenAIResponsesProvider, "generate", autospec=True, side_effect=produce)
        self.generate = generate.start()
        self.addCleanup(generate.stop)
        constructed = patch.object(OpenAIResponsesProvider, "__init__", autospec=True,
                                   side_effect=OpenAIResponsesProvider.__init__)
        self.constructed = constructed.start()
        self.addCleanup(constructed.stop)
        self.client.force_login(self.owner)

    def chat(self, user=None):
        if user is not None:
            self.client.force_login(user)
        return self.client.post(reverse("ai_core:ask-global"), data=json.dumps(QUESTION),
                                content_type="application/json")

    def grounded(self):
        return self.client.post(reverse("ai_core:ask-grounded"), data=json.dumps(QUESTION),
                                content_type="application/json")

    def assert_no_paid_call(self):
        self.constructed.assert_not_called()
        self.generate.assert_not_called()


@override_settings(**CHAT)
class WithoutLedgerTests(HostedPaidPathMixin, TestCase):
    """TEST-01/02/03/07/08/19: fehlendes oder gesperrtes Ledger -> kein Provider."""

    def test_01_grounded_without_ledger_is_refused_before_provider(self):
        response = self.grounded()
        self.assertEqual((response.status_code, response.json()), (429, {"error": "rate_limited"}))
        self.assert_no_paid_call()
        self.assertFalse(StagingAIBudgetDay.objects.exists(), "legacy counter consumed without ledger")

    @override_settings(VORNEQ_AI_CHAT_STAGING_PREPAID_ONLY=False)
    def test_02_staging_chat_without_ledger_and_without_prepaid_only_is_refused(self):
        with patch("apps.ai_core.views_global.reserve_global_request") as quota:
            response = self.chat()
        self.assertEqual((response.status_code, response.json()), (429, {"error": "rate_limited"}))
        self.assert_no_paid_call()
        quota.assert_not_called()

    @override_settings(VORNEQ_AI_STAGING_UNMETERED=True, VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=True)
    def test_03_unmetered_and_unlimited_do_not_bypass_the_ledger(self):
        self.assertEqual(self.grounded().status_code, 429)
        self.assertEqual(self.chat().status_code, 429)
        self.assert_no_paid_call()

    @override_settings(VORNEQ_AI_EMERGENCY_STOP=True)
    def test_07_emergency_stop_blocks_paid_paths(self):
        self.assertEqual(self.chat().status_code, 404)  # Gate: Global AI aus
        self.assertEqual(self.grounded().status_code, 404)
        with self.assertRaises(EmergencyStop):
            paid_provider.require_paid_text_ledger(ledger_check=lambda: True)
        self.assert_no_paid_call()

    def test_08_unauthorized_actor_never_reaches_provider(self):
        start_fake_ledger(self)
        self.assertEqual(self.chat(user=self.other).status_code, 403)
        self.assert_no_paid_call()

    def test_19_ledger_configuration_error_fails_closed(self):
        """Ledger-Flag gelogen an, Konfiguration fehlt: reserve() schlägt fail-closed fehl."""
        with override_settings(VORNEQ_AI_LEDGER_ENABLED=True), \
                patch("apps.ai_core.views_global.ledger_enabled", return_value=True), \
                patch("apps.ai_core.views_global.reserve_global_request"):
            response = self.chat()
        self.assertEqual(response.status_code, 429)
        self.generate.assert_not_called()


@override_settings(**CHAT)
class WithLedgerTests(HostedPaidPathMixin, TestCase):
    """TEST-04/05/06/11/12/13/18: Reservierung entscheidet über den Provider-Aufruf."""

    def setUp(self):
        super().setUp()
        self.reserve, self.settle = start_fake_ledger(self)
        quota = patch("apps.ai_core.views_global.reserve_global_request")
        self.quota = quota.start()
        self.addCleanup(quota.stop)

    def test_04_insufficient_budget_never_calls_provider(self):
        for refusal in (BudgetExhausted("synthetic"), StagingDailyCapReached("synthetic")):
            with self.subTest(refusal=type(refusal).__name__):
                self.reserve.side_effect = refusal
                response = self.chat()
                self.assertEqual((response.status_code, response.json()), (429, {"error": "rate_limited"}))
        self.generate.assert_not_called()
        self.settle.assert_not_called()

    def test_05_valid_reservation_calls_mock_provider_and_settles(self):
        response = self.chat()
        self.assertEqual(response.status_code, 200, response.content)
        self.reserve.assert_called_once()
        self.generate.assert_called_once()
        self.settle.assert_called_once()
        self.assertEqual(self.settle.call_args.kwargs["outcome"], "completed")
        self.assertEqual(self.reserve.call_args.kwargs["actor_id"], self.owner.pk)
        self.assertEqual(self.quota.call_args.kwargs, {"burst_only": True})

    def test_05b_grounded_with_ledger_reserves_before_provider(self):
        order = []
        self.reserve.side_effect = lambda **_k: order.append("reserve") or fake_reservation()
        self.generate.side_effect = lambda *a, **k: order.append("provider") or {
            "answer": "x", "language": "en", "verified": False, "citations": []}
        with patch("apps.ai_core.views_phase_b.ask_grounded",
                   side_effect=lambda q, l, *, actor, provider, enabled: provider.generate(
                       question=q, language=l, sources=[])):
            response = self.grounded()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(order, ["reserve", "provider"])
        self.settle.assert_called_once()

    def test_06_reservation_failure_never_calls_provider(self):
        self.reserve.side_effect = LedgerUnavailable("synthetic reservation failure")
        self.assertEqual(self.chat().status_code, 429)
        with patch("apps.ai_core.views_phase_b.ask_grounded",
                   side_effect=lambda q, l, *, actor, provider, enabled: provider.generate(
                       question=q, language=l, sources=[])):
            self.assertEqual(self.grounded().status_code, 429)
        self.generate.assert_not_called()

    def test_11_provider_timeout_is_settled_uncertain_not_released(self):
        self.generate.side_effect = ProviderTimeout("synthetic timeout")
        with patch("apps.ai_core.budgeted_provider.ledger.release") as release:
            response = self.chat()
        self.assertEqual(response.status_code, 504)
        self.settle.assert_called_once()
        self.assertIsNone(self.settle.call_args.kwargs["usage"])  # -> UNCERTAIN at full amount
        self.assertEqual(self.settle.call_args.kwargs["outcome"], "ProviderTimeout")
        release.assert_not_called()
        self.assertEqual(self.generate.call_count, 1)

    def test_12_unexpected_provider_exception_is_uncertain_and_not_retried(self):
        provider = paid_provider.paid_text_provider(actor_id=self.owner.pk, ledger_check=lambda: True,
                                                    model="synthetic-model", timeout_s=30,
                                                    max_output_tokens=2048)
        self.generate.side_effect = RuntimeError("synthetic")
        with self.assertRaises(RuntimeError):
            provider.generate(question="q", language="en", sources=[])
        self.assertEqual(self.generate.call_count, 1)
        self.assertEqual(self.settle.call_args.kwargs, {"usage": None, "outcome": "unexpected_error"})

    def test_13_failed_finalization_keeps_reservation_and_does_not_recall_provider(self):
        self.settle.return_value = None  # settle() never raises; None = not committed
        with patch("apps.ai_core.budgeted_provider.ledger.release") as release:
            response = self.chat()
        self.assertEqual(response.status_code, 200)
        self.generate.assert_called_once()
        self.reserve.assert_called_once()
        release.assert_not_called()  # RESERVED bleibt für die manuelle Reconciliation

    def test_18_ledger_wrapper_does_not_change_provider_output_or_arguments(self):
        inner = SimpleNamespace(model="synthetic-model", max_output_tokens=2048, instructions="",
                                compact_sources=False, last_usage=(1, 2))
        output = {"answer": "unverändert", "citations": [{"source_id": "S1"}], "language": "de"}
        calls = []
        inner.generate = lambda **kwargs: calls.append(kwargs) or output
        result = BudgetedProvider(inner, actor_id=self.owner.pk).generate(
            question="Frage", language="de", sources=[])
        self.assertIs(result, output)
        self.assertEqual(calls, [{"question": "Frage", "language": "de", "sources": []}])


@override_settings(VORNEQ_ENV="production", DEBUG=False)
class ProductionRegressionTests(SimpleTestCase):
    """TEST-14: Production bleibt ledger-pflichtig und wird nicht schwächer."""

    def test_production_without_ledger_refuses_before_quota_and_provider(self):
        from apps.ai_core.views_global import run_global_pipeline

        request = SimpleNamespace(user=SimpleNamespace(pk=7))
        with patch("apps.ai_core.views_global.route_question", return_value=SimpleNamespace(kind="GENERAL_PUBLIC")), \
                patch("apps.ai_core.views_global.ledger_enabled", return_value=False), \
                patch("apps.ai_core.views_global.reserve_global_request") as quota, \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider") as provider:
            body, status, meta = run_global_pipeline(request, "Who was Ibn Sina?", "en")
        self.assertEqual((body, status, meta["budgeted"]), ({"error": "rate_limited"}, 429, None))
        provider.assert_not_called()
        quota.assert_not_called()

    def test_production_paid_provider_is_always_ledger_wrapped(self):
        with patch.object(OpenAIResponsesProvider, "__init__", return_value=None):
            provider = paid_provider.paid_text_provider(actor_id=7, ledger_check=lambda: True, model="m")
        self.assertIsInstance(provider, BudgetedProvider)

    def test_phase_b_stays_closed_in_production(self):
        from django.http import Http404
        from django.test import RequestFactory

        from apps.ai_core.views_phase_b import ask_phase_b

        request = RequestFactory().post("/api/ai/v1/ask-grounded/", data=json.dumps(QUESTION),
                                        content_type="application/json")
        request._dont_enforce_csrf_checks = True
        request.user = SimpleNamespace(is_authenticated=True, pk=7)
        with override_settings(VORNEQ_AI_PHASE_B_ENABLED=True), \
                patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider") as provider, \
                self.assertRaises(Http404):
            ask_phase_b(request)
        provider.assert_not_called()


class RuntimePolicyTests(SimpleTestCase):
    """Fail-closed-Matrix der zentralen Ledger-Pflicht."""

    @override_settings(VORNEQ_ENV="staging", VORNEQ_AI_EMERGENCY_STOP=False)
    def test_hosted_requires_ledger(self):
        with self.assertRaises(LedgerUnavailable):
            paid_provider.require_paid_text_ledger(ledger_check=lambda: False)
        self.assertTrue(paid_provider.require_paid_text_ledger(ledger_check=lambda: True))

    @override_settings(VORNEQ_ENV="development")
    def test_development_on_a_hosted_runtime_is_refused(self):
        with patch.dict(os.environ, {"RENDER": "true"}), self.assertRaises(LedgerUnavailable):
            paid_provider.require_paid_text_ledger()
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": "srv-x"}), self.assertRaises(LedgerUnavailable):
            paid_provider.require_paid_text_ledger()

    @override_settings(VORNEQ_ENV="development")
    def test_local_development_is_the_only_ledgerless_runtime(self):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("RENDER")}
        with patch.dict(os.environ, clean, clear=True):
            self.assertFalse(paid_provider.require_paid_text_ledger())

    @override_settings(VORNEQ_ENV="unexpected")
    def test_unknown_environment_is_refused(self):
        with self.assertRaises(LedgerUnavailable):
            paid_provider.require_paid_text_ledger(ledger_check=lambda: True)

    @override_settings(VORNEQ_ENV="staging")
    def test_invalid_actor_is_refused_before_construction(self):
        with patch.object(OpenAIResponsesProvider, "__init__", return_value=None) as init:
            for actor in (0, -1, None, "7", True):
                with self.subTest(actor=actor), self.assertRaises(LedgerUnavailable):
                    paid_provider.paid_text_provider(actor_id=actor, ledger_check=lambda: True)
        init.assert_not_called()

    @override_settings(VORNEQ_ENV="staging")
    def test_a_lying_precheck_cannot_skip_the_wrapper(self):
        """Selbst wenn ein Aufrufer die Vorprüfung fälscht, bleibt der Provider ledger-gebunden."""
        with patch.object(OpenAIResponsesProvider, "__init__", return_value=None):
            provider = paid_provider.paid_text_provider(actor_id=3, ledger_check=lambda: True)
        self.assertIsInstance(provider, BudgetedProvider)


class MockProviderRegressionTests(SimpleTestCase):
    """TEST-15/16: Mock-Bild- und Mock-Sprach-Provider bleiben kostenlos und explizit."""

    def test_mock_image_provider_needs_no_key_and_is_marked_mock(self):
        from apps.ai_core.image_generation.providers import MockImageProvider

        import sys

        # Ein Import des SDK schlüge fehl: der Mock darf es nie laden.
        with patch.dict(os.environ, {}, clear=True), patch.dict(sys.modules, {"openai": None}):
            result = MockImageProvider().generate(prompt="synthetic", model="mock", size="1024x1024",
                                                  safety_identifier=None)
        self.assertTrue(result.is_mock)

    @override_settings(VORNEQ_AI_VOICE_PROVIDER="mock")
    def test_voice_is_mock_only(self):
        from apps.ai_core.voice.provider import VoiceProviderBlocked, get_provider

        provider = get_provider()
        self.assertEqual((provider.name, provider.paid), ("mock", False))
        with override_settings(VORNEQ_AI_VOICE_PROVIDER="openai"), self.assertRaises(VoiceProviderBlocked):
            get_provider()
