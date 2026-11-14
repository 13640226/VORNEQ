"""Shared prepaid ledger: fail-closed configuration, policy and wiring (any DB).

SYNTHETIC data only. No network, no provider, no real billing.
"""
import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connections
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.production_policy import production_actor_allowed, production_enabled
from apps.ai_core.providers.exceptions import ProviderTimeout
from apps.ai_ledger.router import AILedgerRouter
from apps.ai_ledger.service import (LEDGER_ALIAS, EmergencyStop, LedgerUnavailable, Reservation,
                                    ledger_configuration, ledger_enabled, observed_cost_micro, reserve,
                                    worst_case_cost_micro)
from apps.ai_ledger.tests import helpers as h

PROD = dict(VORNEQ_ENV="production", DEBUG=False, VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED=True,
            VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA=h.SHA,
            VORNEQ_AI_PRODUCTION_OWNER_AUTH="OWNER-AUTH-AI-PRODUCTION-TEST-01",
            VORNEQ_AI_PRODUCTION_APPROVED_MODEL=h.MODEL, VORNEQ_AI_LEDGER_ENABLED=True,
            VORNEQ_AI_LEDGER_ID=str(h.LEDGER_ID), VORNEQ_AI_LEDGER_DB_NAME="vorneq_ai_ledger")
PROD_ENV = {**h.runtime("production"), "VORNEQ_AI_PHASE_B_MODEL": h.MODEL,
            "OPENAI_API_KEY": "sk-synthetic-never-use"}


class ConfigurationTests(SimpleTestCase):
    def test_disabled_by_default(self):
        self.assertFalse(settings.VORNEQ_AI_LEDGER_ENABLED)
        self.assertFalse(ledger_enabled())
        with self.assertRaises(LedgerUnavailable):
            reserve(actor_id=1, model=h.MODEL, input_bytes=1, max_output_tokens=64)

    def test_invalid_configuration_fails_closed(self):
        for overrides in ({"VORNEQ_AI_LEDGER_ID": "nope"}, {"VORNEQ_AI_LEDGER_DB_NAME": ""},
                          {"VORNEQ_AI_LEDGER_DB_NAME": "a b"}):
            with override_settings(**{**PROD, **overrides}):
                with self.assertRaises(LedgerUnavailable):
                    ledger_configuration()
        with override_settings(**PROD):
            self.assertEqual(ledger_configuration().ledger_id, h.LEDGER_ID)

    def test_emergency_stop_env_blocks_before_database(self):
        with override_settings(**PROD, VORNEQ_AI_EMERGENCY_STOP=True):
            with self.assertRaises(EmergencyStop):
                reserve(actor_id=1, model=h.MODEL, input_bytes=1, max_output_tokens=64)

    def test_ledger_alias_is_separate_from_default(self):
        self.assertIn(LEDGER_ALIAS, connections.databases)
        self.assertNotEqual(settings.DATABASES[LEDGER_ALIAS]["NAME"], settings.DATABASES["default"]["NAME"])

    def test_router_isolates_ledger_migrations(self):
        router = AILedgerRouter()
        self.assertTrue(router.allow_migrate(LEDGER_ALIAS, "ai_ledger"))
        self.assertFalse(router.allow_migrate("default", "ai_ledger"))
        self.assertFalse(router.allow_migrate(LEDGER_ALIAS, "auth"))
        self.assertIsNone(router.allow_migrate("default", "auth"))

    def test_worst_case_is_an_upper_bound_of_observed(self):
        worst = worst_case_cost_micro(input_bytes=h.INPUT_BYTES, max_output_tokens=h.MAX_OUT,
                                      input_price=h.IN_PRICE, output_price=h.OUT_PRICE)
        self.assertEqual(worst, h.COST)
        # tokens <= bytes, output <= max_output_tokens => observed <= worst
        self.assertLess(observed_cost_micro(h.INPUT_BYTES, h.MAX_OUT, h.IN_PRICE, h.OUT_PRICE), worst)
        with self.assertRaises(LedgerUnavailable):
            worst_case_cost_micro(input_bytes=-1, max_output_tokens=1, input_price=1, output_price=1)


class SettingsResolutionTests(SimpleTestCase):
    def resolve(self, extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("VORNEQ_", "RENDER", "DATABASE_URL"))}
        env.update({"DJANGO_SECRET_KEY": "x" * 60, "DJANGO_DEBUG": "false", "DJANGO_ALLOWED_HOSTS": "localhost",
                    "DJANGO_SETTINGS_MODULE": "config.settings", "VORNEQ_AI_LEDGER_ENABLED": "true",
                    "VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED": "true"})
        env.update(extra)
        code = ("import django,json;django.setup();from django.conf import settings as s;"
                "print(json.dumps([s.VORNEQ_AI_LEDGER_ENABLED,s.VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED,"
                "s.DATABASES['ai_ledger']['NAME']!=s.DATABASES['default']['NAME']]))")
        out = subprocess.run([sys.executable, "-c", code], cwd=settings.BASE_DIR, env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr[-1500:])
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_ledger_requires_hosted_env_and_explicit_url(self):
        self.assertEqual(self.resolve({"VORNEQ_ENV": "development"}), [False, False, True])
        self.assertEqual(self.resolve({"VORNEQ_ENV": "staging"}), [False, False, True])
        url = {"VORNEQ_AI_LEDGER_DATABASE_URL": "postgres://u:p@ledger.invalid:5432/vorneq_ai_ledger"}
        self.assertEqual(self.resolve({"VORNEQ_ENV": "staging", **url}), [True, False, True])
        self.assertEqual(self.resolve({"VORNEQ_ENV": "development", **url}), [False, False, True])


class ProductionPolicyTests(SimpleTestCase):
    def check(self, expected, settings_over=None, env_over=None):
        env = {**h.env_without_render(), **PROD_ENV, **(env_over or {})}
        env = {k: v for k, v in env.items() if v is not None}
        with patch.dict(os.environ, env, clear=True), override_settings(**{**PROD, **(settings_over or {})}):
            self.assertIs(production_enabled(), expected, (settings_over, env_over))

    def test_fully_configured_production_enabled(self):
        self.check(True)

    def test_every_guard_is_required(self):
        for s in ({"VORNEQ_ENV": "staging"}, {"DEBUG": True}, {"VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED": False},
                  {"VORNEQ_AI_EMERGENCY_STOP": True}, {"VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA": "b" * 40},
                  {"VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA": "short"}, {"VORNEQ_AI_PRODUCTION_OWNER_AUTH": "yes"},
                  {"VORNEQ_AI_PRODUCTION_APPROVED_MODEL": "other-model"}, {"VORNEQ_AI_LEDGER_ENABLED": False}):
            self.check(False, settings_over=s)
        for e in ({"RENDER_SERVICE_ID": "srv-dbm7dvc9v7es7393g70g"}, {"RENDER_GIT_COMMIT": "c" * 40},
                  {"OPENAI_API_KEY": None}, {"VORNEQ_AI_PHASE_B_MODEL": "other"}):
            self.check(False, env_over=e)

    def test_actor_policy(self):
        user = MagicMock(is_authenticated=True, is_active=True, pk=5)
        with override_settings(VORNEQ_AI_PRODUCTION_ACTOR_POLICY="allowlist", VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS=""):
            self.assertFalse(production_actor_allowed(user))
        with override_settings(VORNEQ_AI_PRODUCTION_ACTOR_POLICY="allowlist", VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS="5,6"):
            self.assertTrue(production_actor_allowed(user))
        with override_settings(VORNEQ_AI_PRODUCTION_ACTOR_POLICY="authenticated"):
            self.assertTrue(production_actor_allowed(user))
            self.assertFalse(production_actor_allowed(MagicMock(is_authenticated=True, is_active=False, pk=5)))
            self.assertFalse(production_actor_allowed(MagicMock(is_authenticated=False, is_active=True, pk=5)))
        with override_settings(VORNEQ_AI_PRODUCTION_ACTOR_POLICY="anything-else"):
            self.assertFalse(production_actor_allowed(user))


class SqliteLedgerTests(TestCase):
    databases = {"default", LEDGER_ALIAS}

    def test_sqlite_ledger_rejected(self):
        if connections[LEDGER_ALIAS].vendor != "sqlite":
            self.skipTest("SQLite-only negative check")
        with override_settings(**PROD), patch.dict(os.environ, h.runtime("production")):
            with self.assertRaises(LedgerUnavailable):
                reserve(actor_id=1, model=h.MODEL, input_bytes=1, max_output_tokens=64)


class BudgetedProviderTests(SimpleTestCase):
    def make(self, behaviour):
        inner = MagicMock(model=h.MODEL, max_output_tokens=512, instructions="x" * 100)
        inner.generate.side_effect = behaviour(inner)
        return inner, BudgetedProvider(inner, actor_id=3)

    def test_reserve_before_call_and_settle_with_usage(self):
        def behaviour(inner):
            def gen(**kw):
                inner.last_usage = (120, 40)
                return {"ok": True}
            return gen
        inner, provider = self.make(behaviour)
        res = Reservation("id", 10, 1, 1)
        with patch("apps.ai_ledger.service.reserve", return_value=res) as r, \
                patch("apps.ai_ledger.service.settle") as s:
            self.assertEqual(provider.generate(question="q", language="en", sources=[{"a": "ü"}]), {"ok": True})
        self.assertEqual(r.call_args.kwargs["max_output_tokens"], 512)
        self.assertGreater(r.call_args.kwargs["input_bytes"], 100)
        s.assert_called_once_with(res, usage=(120, 40), outcome="completed")

    def test_exhausted_budget_never_calls_model(self):
        from apps.ai_ledger.service import BudgetExhausted
        inner, provider = self.make(lambda inner: lambda **kw: {"ok": True})
        with patch("apps.ai_ledger.service.reserve", side_effect=BudgetExhausted("x")):
            with self.assertRaises(BudgetExhausted):
                provider.generate(question="q", language="en", sources=[])
        inner.generate.assert_not_called()

    def test_timeout_settles_uncertain_and_reraises(self):
        def behaviour(inner):
            def gen(**kw):
                raise ProviderTimeout("t")
            return gen
        inner, provider = self.make(behaviour)
        res = Reservation("id", 10, 1, 1)
        with patch("apps.ai_ledger.service.reserve", return_value=res), \
                patch("apps.ai_ledger.service.settle") as s:
            with self.assertRaises(ProviderTimeout):
                provider.generate(question="q", language="en", sources=[])
        s.assert_called_once_with(res, usage=None, outcome="ProviderTimeout")


@override_settings(**{k: v for k, v in PROD.items()}, VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS="")
class ProductionEndpointGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="prod-guard", password="synthetic-only")

    def setUp(self):
        cache.clear()
        p = patch.dict(os.environ, {**h.env_without_render(), **PROD_ENV}, clear=True)
        p.start()
        self.addCleanup(p.stop)
        self.client.force_login(self.user)

    def post(self):
        with patch("apps.ai_core.views_global.default_retriever") as retr, \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate") as gen:
            r = self.client.post(reverse("ai_core:ask-global"),
                                 data=json.dumps({"question": "What is a star?", "language": "en"}),
                                 content_type="application/json")
        return r, retr.call_count + gen.call_count

    def test_production_actor_not_allowlisted_forbidden(self):
        r, touched = self.post()
        self.assertEqual((r.status_code, touched), (403, 0))

    def test_production_disabled_variants_404_without_search_or_model(self):
        for overrides in ({"VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED": False}, {"VORNEQ_AI_EMERGENCY_STOP": True},
                          {"VORNEQ_AI_LEDGER_ENABLED": False}, {"DEBUG": True}):
            with override_settings(**overrides):
                r, touched = self.post()
                self.assertEqual((r.status_code, touched), (404, 0), overrides)

    def test_ledger_unavailable_in_production_returns_429_without_model(self):
        with override_settings(VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS=str(self.user.pk)), \
                patch("apps.ai_core.views_global.default_retriever") as retr, \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate") as gen:
            from apps.ai_core.tests.test_global_ai_api import FakeRetriever, evidence
            retr.return_value = FakeRetriever(evidence("en"))
            r = self.client.post(reverse("ai_core:ask-global"),
                                 data=json.dumps({"question": "What is quantum computing?", "language": "en"}),
                                 content_type="application/json")
        # Ledger alias in tests is unprovisioned -> LedgerUnavailable -> 429, model never called.
        self.assertEqual(r.status_code, 429)
        gen.assert_not_called()


class StagingSharedBudgetWiringTests(SimpleTestCase):
    def test_staging_emergency_stop_disables_trial(self):
        from apps.ai_core.staging_policy import trial_enabled
        from apps.ai_core.tests.test_ai_staging_trial import STAGING_SETTINGS, TEST_ENV
        with patch.dict(os.environ, TEST_ENV), override_settings(**STAGING_SETTINGS):
            self.assertTrue(trial_enabled())
            with override_settings(VORNEQ_AI_EMERGENCY_STOP=True):
                self.assertFalse(trial_enabled())

    def test_burst_only_skips_daily_counters(self):
        from apps.ai_core.global_budget import reserve_global_request
        with patch("apps.ai_core.global_budget.cache") as c:
            c.incr.return_value = 1
            reserve_global_request(5, burst_only=True)
            self.assertEqual(c.incr.call_count, 1)
            reserve_global_request(5)
            self.assertEqual(c.incr.call_count, 4)
