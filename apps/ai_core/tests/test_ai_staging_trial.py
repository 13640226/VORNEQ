"""Staging AI trial negative tests. NO real key, network or provider egress."""
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.engine.budget import BudgetExceeded
from apps.ai_core.staging_policy import actor_allowed, trial_enabled
from apps.ai_core.staging_budget import reserve_staging_request
from apps.ai_core.models import StagingAIBudgetDay

TEST_SHA = "468d210fb062c4bd2cf3169dd0be728c8a396c45"
OWNER_AUTH = "OWNER-AUTH-AI-STAGING-LOCAL-TEST-01"
TEST_ENV = {
    "RENDER_SERVICE_ID": "srv-dbm7dvc9v7es7393g70g",
    "RENDER_GIT_COMMIT": TEST_SHA,
    "VORNEQ_AI_PHASE_B_MODEL": "synthetic-model",
    "OPENAI_API_KEY": "sk-synthetic-never-use",
}
STAGING_SETTINGS = {
    "VORNEQ_ENV": "staging",
    "DEBUG": False,
    "VORNEQ_AI_CORE_ENABLED": True,
    "VORNEQ_AI_PHASE_B_ENABLED": True,
    "VORNEQ_AI_STAGING_TRIAL_ENABLED": True,
    "VORNEQ_AI_STAGING_OWNER_AUTH": OWNER_AUTH,
    "VORNEQ_AI_STAGING_AUTHORIZED_SHA": TEST_SHA,
    "VORNEQ_AI_STAGING_APPROVED_MODEL": "synthetic-model",
    "VORNEQ_AI_STAGING_ALLOWED_USER_IDS": "101",
    "VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD": 100_000,
    "VORNEQ_AI_STAGING_RESERVE_MICROUSD": 50_000,
    "VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS": 2,
}


@override_settings(**STAGING_SETTINGS)
class StagingTrialPolicyTests(SimpleTestCase):
    def setUp(self):
        env = patch.dict(os.environ, TEST_ENV)
        env.start()
        self.addCleanup(env.stop)

    def test_unmetered_staging_opt_in_keeps_identity_guards(self):
        with override_settings(
            VORNEQ_AI_STAGING_UNMETERED=True,
            VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD=0,
            VORNEQ_AI_STAGING_RESERVE_MICROUSD=0,
            VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS=0,
        ):
            self.assertTrue(trial_enabled())
            with override_settings(VORNEQ_ENV="production"):
                self.assertFalse(trial_enabled())
            with patch.dict(os.environ, {"RENDER_GIT_COMMIT": "f" * 40}):
                self.assertFalse(trial_enabled())
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                self.assertFalse(trial_enabled())
            with override_settings(VORNEQ_AI_STAGING_ALLOWED_USER_IDS=""):
                self.assertFalse(trial_enabled())

    def test_staging_contract_passes_with_all_guards(self):
        self.assertTrue(trial_enabled())

    def test_production_always_blocked(self):
        with override_settings(VORNEQ_ENV="production"):
            self.assertFalse(trial_enabled())

    def test_dev_never_treated_as_staging_trial(self):
        with override_settings(VORNEQ_ENV="development"):
            self.assertFalse(trial_enabled())

    def test_staging_feature_flag_must_be_explicit(self):
        with override_settings(VORNEQ_AI_STAGING_TRIAL_ENABLED=False):
            self.assertFalse(trial_enabled())

    def test_staging_phase_a_and_phase_b_each_must_be_enabled(self):
        for flag in ("VORNEQ_AI_CORE_ENABLED", "VORNEQ_AI_PHASE_B_ENABLED"):
            with self.subTest(flag=flag), override_settings(**{flag: False}):
                self.assertFalse(trial_enabled())

    def test_debug_mode_rejected(self):
        with override_settings(DEBUG=True):
            self.assertFalse(trial_enabled())

    def test_wrong_service_id_rejected(self):
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": "srv-dadn07eq1p3s73eccau0"}):
            self.assertFalse(trial_enabled())

    def test_wrong_sha_rejected(self):
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": "0" * 40}):
            self.assertFalse(trial_enabled())

    def test_wrong_or_unformatted_owner_authorization_rejected(self):
        for value in ("", "OWNER-AUTH-DEPLOY-PRODUCTION", "OWNER-AUTH-AI-STAGING-a"):
            with self.subTest(value=value), override_settings(VORNEQ_AI_STAGING_OWNER_AUTH=value):
                self.assertFalse(trial_enabled())

    def test_missing_openai_secret_rejected(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertFalse(trial_enabled())

    def test_model_mismatch_rejected(self):
        with patch.dict(os.environ, {"VORNEQ_AI_PHASE_B_MODEL": "unreviewed-model"}):
            self.assertFalse(trial_enabled())

    def test_missing_actor_allowlist_rejected(self):
        with override_settings(VORNEQ_AI_STAGING_ALLOWED_USER_IDS=""):
            self.assertFalse(trial_enabled())

    def test_malformed_actor_ids_rejected(self):
        for ids in ("101,101", "-1", "101,102,103,104,105,106", "one", "101,"):
            with self.subTest(ids=ids), override_settings(VORNEQ_AI_STAGING_ALLOWED_USER_IDS=ids):
                self.assertFalse(trial_enabled())

    def test_non_superuser_staff_or_inactive_rejected(self):
        actor = SimpleNamespace(
            is_authenticated=True, is_active=True, is_staff=True, is_superuser=True,
            pk=101,
        )
        self.assertTrue(actor_allowed(actor))
        for field, value in [
            ("is_authenticated", False), ("is_active", False),
            ("is_staff", False), ("is_superuser", False), ("pk", 102),
        ]:
            data = vars(actor).copy()
            data[field] = value
            with self.subTest(field=field):
                self.assertFalse(actor_allowed(SimpleNamespace(**data)))

    def test_reject_incomplete_invalid_or_excessive_budgets(self):
        variants = (
            ("VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD", 0),
            ("VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD", 500_000),
            ("VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD", 70_000),
            ("VORNEQ_AI_STAGING_RESERVE_MICROUSD", 0),
            ("VORNEQ_AI_STAGING_RESERVE_MICROUSD", 300_000),
            ("VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS", 0),
            ("VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS", 6),
            ("VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS", "2"),
        )
        for key, value in variants:
            with self.subTest(key=key, value=value), override_settings(**{key: value}):
                self.assertFalse(trial_enabled())


@override_settings(**STAGING_SETTINGS)
class StagingTrialDatabaseAndEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="staging-ai-owner-test",
            email="staging-owner@example.invalid",
            password="synthetic-local-only",
        )

    def setUp(self):
        env = patch.dict(os.environ, TEST_ENV)
        env.start()
        self.addCleanup(env.stop)
        self.user_id_override = override_settings(
            VORNEQ_AI_STAGING_ALLOWED_USER_IDS=str(self.owner.pk)
        )
        self.user_id_override.enable()
        self.addCleanup(self.user_id_override.disable)
        self.url = reverse("ai_core:ask-grounded")
        self.offline_url = reverse("ai_core:ask")
        self.client.force_login(self.owner)

    def post(self, url=None):
        return self.client.post(
            url or self.url,
            data=json.dumps({"question": "public sample", "language": "en"}),
            content_type="application/json",
        )

    def test_unmetered_owner_requests_do_not_reserve_budget(self):
        with override_settings(
            VORNEQ_AI_STAGING_UNMETERED=True,
            VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD=0,
            VORNEQ_AI_STAGING_RESERVE_MICROUSD=0,
            VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS=0,
        ), patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider") as provider, patch(
            "apps.ai_core.views_phase_b.ask_grounded",
            return_value={"mode": "insufficient_evidence", "verified": False},
        ):
            responses = [self.post() for _ in range(7)]
        self.assertTrue(all(r.status_code == 200 for r in responses))
        self.assertEqual(provider.call_count, 7)
        self.assertFalse(StagingAIBudgetDay.objects.exists())

    def test_unmetered_rejects_unauthorized_actor_without_provider(self):
        with override_settings(
            VORNEQ_AI_STAGING_UNMETERED=True,
            VORNEQ_AI_STAGING_ALLOWED_USER_IDS="999999",
        ), patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider") as provider:
            self.assertEqual(self.post().status_code, 403)
            provider.assert_not_called()
        self.assertFalse(StagingAIBudgetDay.objects.exists())

    def test_first_and_second_reservation_then_daily_cap_denies(self):
        reserve_staging_request()
        reserve_staging_request()
        row = StagingAIBudgetDay.objects.get()
        self.assertEqual((row.request_count, row.reserved_micro_usd), (2, 100000))
        with self.assertRaises(BudgetExceeded):
            reserve_staging_request()
        row.refresh_from_db()
        self.assertEqual((row.request_count, row.reserved_micro_usd), (2, 100000))

    def test_database_failure_fails_closed(self):
        from django.db import DatabaseError
        with patch(
            "apps.ai_core.staging_budget.StagingAIBudgetDay.objects.select_for_update",
            side_effect=DatabaseError("synthetic DB unavailable"),
        ):
            with self.assertRaises(BudgetExceeded):
                reserve_staging_request()
        self.assertFalse(StagingAIBudgetDay.objects.exists())

    def test_production_provider_never_called_even_when_flags_forced(self):
        with override_settings(VORNEQ_ENV="production"), patch(
            "apps.ai_core.views_phase_b.OpenAIResponsesProvider"
        ) as provider:
            self.assertEqual(self.post().status_code, 404)
            provider.assert_not_called()

    def test_staging_without_exact_sha_never_calls_provider(self):
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": "f" * 40}), patch(
            "apps.ai_core.views_phase_b.OpenAIResponsesProvider"
        ) as provider:
            self.assertEqual(self.post().status_code, 404)
            provider.assert_not_called()

    def test_unallowlisted_authenticated_user_rejected_before_cost(self):
        with override_settings(VORNEQ_AI_STAGING_ALLOWED_USER_IDS="999999"), patch(
            "apps.ai_core.views_phase_b.OpenAIResponsesProvider"
        ) as provider:
            self.assertEqual(self.post().status_code, 403)
            provider.assert_not_called()
        self.assertFalse(StagingAIBudgetDay.objects.exists())

    def test_anonymous_request_requires_login(self):
        self.client.logout()
        self.assertEqual(self.post().status_code, 401)
        self.assertFalse(StagingAIBudgetDay.objects.exists())

    def test_csrf_denies_before_budget_or_provider(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        r = strict.post(
            self.url, data=json.dumps({"question": "hello", "language": "en"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)
        self.assertFalse(StagingAIBudgetDay.objects.exists())

    def test_mock_provider_staging_with_cap_and_output_tokens(self):
        with patch(
            "apps.ai_core.views_phase_b.OpenAIResponsesProvider"
        ) as provider, patch(
            "apps.ai_core.views_phase_b.ask_grounded",
            return_value={"mode": "grounded_draft", "verified": False}
        ):
            first = self.post()
            second = self.post()
            third = self.post()
        self.assertEqual((first.status_code, second.status_code, third.status_code), (200, 200, 429))
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(provider.call_args.kwargs["max_output_tokens"], 256)
        self.assertEqual(provider.call_args.kwargs["timeout_s"], 10)
        self.assertIn("no-store", first["Cache-Control"])
        row = StagingAIBudgetDay.objects.get()
        self.assertEqual(row.reserved_micro_usd, 100000)

    def test_phase_a_requires_same_owner_and_allowed_sha(self):
        with patch("apps.ai_core.views.ask_public",
                   return_value={"mode": "sources_only", "citations": []}) as offline:
            self.assertEqual(self.post(self.offline_url).status_code, 200)
            with patch.dict(os.environ, {"RENDER_GIT_COMMIT": "f" * 40}):
                self.assertEqual(self.post(self.offline_url).status_code, 404)
            offline.assert_called_once()

    def test_default_staging_trial_flag_is_not_enough(self):
        with override_settings(VORNEQ_AI_STAGING_TRIAL_ENABLED=False):
            self.assertEqual(self.post().status_code, 404)

    def test_failed_provider_calls_still_consume_budget(self):
        from apps.ai_core.providers.exceptions import ProviderUnavailable
        with patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider") as provider, patch(
            "apps.ai_core.views_phase_b.ask_grounded",
            side_effect=ProviderUnavailable("synthetic failure")
        ):
            self.assertEqual(self.post().status_code, 503)
            self.assertEqual(self.post().status_code, 503)
            self.assertEqual(self.post().status_code, 429)
        self.assertEqual(provider.call_count, 2)
        row = StagingAIBudgetDay.objects.get()
        self.assertEqual(row.request_count, 2)


@override_settings(**STAGING_SETTINGS)
class StagingBudgetPostgresConcurrencyTests(
    __import__("django.test", fromlist=["TransactionTestCase"]).TransactionTestCase
):
    def test_four_real_db_workers_only_two_allowed(self):
        """Four independent connections race for the same persisted daily row."""
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connection, connections

        if connection.vendor != "postgresql":
            self.skipTest("Real PostgreSQL select_for_update is required")

        barrier = Barrier(4)

        def worker():
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                try:
                    reserve_staging_request()
                except BudgetExceeded:
                    return "denied"
                return "accepted"
            finally:
                connections.close_all()

        with patch.dict(os.environ, TEST_ENV):
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(lambda _: worker(), range(4)))
        self.assertEqual(results.count("accepted"), 2, results)
        self.assertEqual(results.count("denied"), 2, results)
        ledger = StagingAIBudgetDay.objects.get()
        self.assertEqual(ledger.request_count, 2)
        self.assertEqual(ledger.reserved_micro_usd, 100_000)
