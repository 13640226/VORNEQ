"""Independent STAGING daily ceiling on the shared prepaid ledger.

Closes the gap where VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS /
VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD were skipped whenever the shared ledger
governs cost. The ceiling is checked inside the locked reservation transaction.
REAL PostgreSQL only (row locks); no provider, no network, synthetic data.
"""
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import timedelta, timezone as dt_timezone
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import OperationalError, connections
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.ai_ledger import service
from apps.ai_ledger.models import BudgetAccount, BudgetReservation
from apps.ai_ledger.service import (LEDGER_ALIAS, LedgerConfig, LedgerUnavailable, StagingDailyCapReached,
                                    StagingDailyLimit, reserve_with_config, settle)
from apps.ai_ledger.tests import helpers as h
from apps.ai_ledger.tests.test_ledger_postgres import account, do_reserve, race

IS_PG = settings.DATABASES[LEDGER_ALIAS]["ENGINE"].endswith("postgresql")


def staging_cap(max_requests, cap_micro):
    return override_settings(VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS=max_requests,
                             VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD=cap_micro)


def explicit(environment, staging_daily):
    """Thread-safe: identity passed explicitly instead of patching os.environ."""
    config = LedgerConfig(h.LEDGER_ID, connections[LEDGER_ALIAS].settings_dict["NAME"])
    return reserve_with_config(
        config, environment=environment, service_id=h.runtime(environment)["RENDER_SERVICE_ID"],
        git_sha=h.SHA, actor_id=7, model=h.MODEL, input_bytes=h.INPUT_BYTES,
        max_output_tokens=h.MAX_OUT, staging_daily=staging_daily)


def staging_rows():
    return BudgetReservation.objects.using(LEDGER_ALIAS).filter(environment="staging")


class StagingDailyLimitConfigTests(SimpleTestCase):
    def test_missing_or_invalid_configuration_fails_closed(self):
        for max_requests, cap in ((0, 1), (1, 0), (-1, 5), ("3", 5), (True, 5), (3, 2.5), (100_001, 5)):
            with self.subTest(max_requests=max_requests, cap=cap), staging_cap(max_requests, cap):
                with self.assertRaises(LedgerUnavailable):
                    service.staging_daily_limit()

    def test_valid_configuration(self):
        with staging_cap(3, 30_000):
            self.assertEqual(service.staging_daily_limit(), StagingDailyLimit(3, 30_000))

    def test_day_starts_at_utc_midnight_independent_of_site_time_zone(self):
        now = timezone.now().replace(hour=1, minute=30)
        start = service._utc_day_start(now)
        self.assertEqual((start.hour, start.minute, start.utcoffset()), (0, 0, timedelta(0)))
        self.assertEqual(start.date(), now.astimezone(dt_timezone.utc).date())


@skipUnless(IS_PG, "real PostgreSQL row locking required")
class StagingDailyCapPostgresTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        override = override_settings(**h.ledger_settings())
        override.enable()
        self.addCleanup(override.disable)

    def assert_invariants(self):
        acc = account()
        rows = BudgetReservation.objects.using(LEDGER_ALIAS).filter(account=acc)
        self.assertEqual(acc.reserved_micro, sum(r.reserved_micro for r in rows if r.status == "reserved"))
        self.assertEqual(acc.uncertain_micro, sum(r.reserved_micro for r in rows if r.status == "uncertain"))
        self.assertEqual(acc.finalized_micro, sum(r.observed_micro for r in rows if r.status == "finalized"))
        self.assertGreaterEqual(acc.remaining_micro(), 0)

    def test_request_ceiling_applies_even_with_ample_shared_allowance(self):
        h.provision(20)
        with staging_cap(3, 10 ** 9):
            for _ in range(3):
                do_reserve("staging")
            with self.assertLogs("apps.ai_ledger.service", "WARNING") as logs, \
                    self.assertRaises(StagingDailyCapReached):
                do_reserve("staging")
        self.assertIn("kind=requests", "\n".join(logs.output))
        self.assertEqual(staging_rows().count(), 3)
        self.assertEqual(account().reserved_micro, 3 * h.COST)  # rejected call reserved nothing
        self.assert_invariants()

    def test_amount_ceiling_counts_worst_case_before_the_call(self):
        h.provision(20)
        with staging_cap(100, 2 * h.COST + h.COST - 1):
            do_reserve("staging"), do_reserve("staging")
            with self.assertRaises(StagingDailyCapReached):
                do_reserve("staging")
        self.assertEqual(staging_rows().count(), 2)

    def test_finalized_counts_observed_uncertain_and_unsettled_count_in_full(self):
        h.provision(20)
        with staging_cap(100, 2 * h.COST):
            first = do_reserve("staging")
            settle(first, usage=(10, 10), outcome="completed")   # observed << reserved
            second = do_reserve("staging")
            settle(second, usage=None, outcome="ProviderTimeout")  # uncertain: full amount
            with self.assertRaises(StagingDailyCapReached):       # observed + COST + COST > 2*COST
                do_reserve("staging")
        statuses = sorted(staging_rows().values_list("status", flat=True))
        self.assertEqual(statuses, ["finalized", "uncertain"])
        self.assert_invariants()

    def test_settlement_failure_keeps_full_reservation_counted(self):
        h.provision(20)
        with staging_cap(100, 2 * h.COST - 1):
            res = do_reserve("staging")
            with patch.object(BudgetReservation.objects, "using", side_effect=OperationalError("down")):
                settle(res, usage=(1, 1), outcome="completed")      # swallowed, row stays RESERVED
            with self.assertRaises(StagingDailyCapReached):
                do_reserve("staging")
        self.assertEqual(staging_rows().get().status, "reserved")

    def test_previous_utc_days_do_not_count(self):
        h.provision(20)
        with staging_cap(1, 10 ** 9):
            do_reserve("staging")
            staging_rows().update(created_at=service._utc_day_start() - timedelta(seconds=1))
            do_reserve("staging")
            with self.assertRaises(StagingDailyCapReached):
                do_reserve("staging")

    def test_production_is_never_limited_by_the_staging_ceiling(self):
        h.provision(10)
        with staging_cap(1, 1):
            for _ in range(4):
                do_reserve("production")
        with staging_cap(0, 0):
            do_reserve("production")
            with self.assertRaises(LedgerUnavailable):
                do_reserve("staging")
        self.assertEqual(BudgetReservation.objects.using(LEDGER_ALIAS).filter(environment="production").count(), 5)
        self.assertEqual(staging_rows().count(), 0)

    def test_production_reservations_do_not_consume_the_staging_ceiling(self):
        h.provision(10)
        with staging_cap(2, 10 ** 9):
            for _ in range(3):
                do_reserve("production")
            do_reserve("staging"), do_reserve("staging")
            with self.assertRaises(StagingDailyCapReached):
                do_reserve("staging")

    def test_misapplied_ceiling_is_rejected(self):
        h.provision(2)
        with self.assertRaises(LedgerUnavailable):
            explicit("production", StagingDailyLimit(5, 10 ** 9))
        with self.assertRaises(LedgerUnavailable):
            explicit("staging", (5, 10 ** 9))
        self.assertEqual(BudgetReservation.objects.using(LEDGER_ALIAS).count(), 0)

    def test_database_failure_during_ceiling_check_fails_closed(self):
        h.provision(5)
        with staging_cap(3, 10 ** 9), patch("apps.ai_ledger.service._staging_usage_today",
                                            side_effect=OperationalError("down")):
            with self.assertRaises(LedgerUnavailable):
                do_reserve("staging")
        self.assertEqual((account().reserved_micro, BudgetReservation.objects.using(LEDGER_ALIAS).count()), (0, 0))

    def test_emergency_stop_still_wins_over_the_ceiling(self):
        h.provision(5, emergency_stop=True)
        with staging_cap(3, 10 ** 9), self.assertRaises(service.EmergencyStop):
            do_reserve("staging")

    def test_twenty_concurrent_staging_requests_only_ceiling_accepted(self):
        h.provision(30)
        limit = StagingDailyLimit(3, 10 ** 9)
        results = race(20, lambda i: _classify(lambda: explicit("staging", limit)))
        self.assertEqual(results.count("accepted"), 3, results)
        self.assertEqual(results.count("cap"), 17, results)
        self.assertEqual(account().reserved_micro, 3 * h.COST)
        self.assert_invariants()

    def test_concurrent_amount_ceiling_with_mixed_production_traffic(self):
        h.provision(30)
        limit = StagingDailyLimit(100, 2 * h.COST + h.COST // 2)
        results = race(16, lambda i: _classify(
            lambda: explicit("staging", limit) if i % 2 else explicit("production", None)))
        staging_ok = sum(1 for i, r in enumerate(results) if i % 2 and r == "accepted")
        production_ok = sum(1 for i, r in enumerate(results) if not i % 2 and r == "accepted")
        self.assertEqual((staging_ok, production_ok), (2, 8), results)
        self.assert_invariants()

    def test_separate_processes_cannot_exceed_the_ceiling(self):
        """Independent OS processes (separate Gunicorn workers / instances)."""
        h.provision(30)
        cfg = connections[LEDGER_ALIAS].settings_dict
        url = "postgres://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}".format(**{
            k: cfg.get(k) or "" for k in ("USER", "PASSWORD", "HOST", "PORT", "NAME")})
        start_at = time.time() + 4
        code = (
            "import sys,time,uuid,django;django.setup()\n"
            "from apps.ai_ledger.service import (reserve_with_config,LedgerConfig,StagingDailyLimit,"
            "StagingDailyCapReached,EXPECTED_SERVICES)\n"
            "cfg=LedgerConfig(uuid.UUID(sys.argv[1]),sys.argv[2])\n"
            "time.sleep(max(0,float(sys.argv[3])-time.time()))\n"
            "try:\n"
            " reserve_with_config(cfg,environment='staging',service_id=EXPECTED_SERVICES['staging'],"
            "git_sha='a'*40,actor_id=9,model=sys.argv[4],input_bytes=1000,max_output_tokens=1024,"
            "staging_daily=StagingDailyLimit(4,10**9));print('ACCEPTED')\n"
            "except StagingDailyCapReached:print('CAP')\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("RENDER", "DATABASE_URL"))}
        env.update({"VORNEQ_AI_LEDGER_DATABASE_URL": url, "DJANGO_SETTINGS_MODULE": "config.settings",
                    "VORNEQ_ENV": "development", "DJANGO_SECRET_KEY": "x" * 50, "DJANGO_DEBUG": "false",
                    "DJANGO_ALLOWED_HOSTS": "localhost"})
        procs = [subprocess.Popen([sys.executable, "-c", code, str(h.LEDGER_ID), cfg["NAME"], str(start_at),
                                   h.MODEL], cwd=settings.BASE_DIR, env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for _ in range(10)]
        outputs = []
        for p in procs:
            out, err = p.communicate(timeout=90)
            self.assertEqual(p.returncode, 0, err[-1500:])
            outputs.append(out.strip().splitlines()[-1])
        self.assertEqual((outputs.count("ACCEPTED"), outputs.count("CAP")), (4, 6), outputs)
        self.assertEqual(staging_rows().count(), 4)
        self.assert_invariants()


def _classify(fn):
    try:
        fn()
        return "accepted"
    except StagingDailyCapReached:
        return "cap"


@skipUnless(IS_PG, "real PostgreSQL row locking required")
class StagingEndpointDailyCapTests(TransactionTestCase):
    """Global AI endpoint on STAGING with the shared ledger: the ceiling holds end to end."""
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        from apps.ai_core.tests.test_ai_staging_trial import STAGING_SETTINGS, TEST_ENV
        from apps.ai_core.tests.test_global_ai_api import FakeRetriever, evidence, good_output
        self.FakeRetriever, self.evidence, self.good_output = FakeRetriever, evidence, good_output
        self.user = get_user_model().objects.create_superuser(username="stg-ai", email="stg@example.invalid",
                                                             password="synthetic-only")
        env = {**h.env_without_render(), **TEST_ENV, "RENDER_GIT_COMMIT": STAGING_SETTINGS[
            "VORNEQ_AI_STAGING_AUTHORIZED_SHA"], "VORNEQ_AI_PHASE_B_MODEL": h.MODEL}
        stg = {**STAGING_SETTINGS, "VORNEQ_AI_STAGING_APPROVED_MODEL": h.MODEL,
               "VORNEQ_AI_STAGING_ALLOWED_USER_IDS": str(self.user.pk), "VORNEQ_GLOBAL_AI_ENABLED": True,
               "VORNEQ_AI_CHAT_RECOVERY_ENABLED": True, "VORNEQ_GLOBAL_AI_QUOTA": {"per_minute": 5},
               # The ceiling must hold even with every "unlimited" staging flag set.
               "VORNEQ_AI_STAGING_UNMETERED": True, "VORNEQ_GLOBAL_AI_UNLIMITED_STAGING": True,
               "VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS": 2, "VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD": 10 ** 9,
               **h.ledger_settings()}
        for p in (patch.dict(os.environ, env, clear=True), override_settings(**stg),
                  patch("apps.ai_core.request_recovery._require_shared_redis", return_value=None)):
            p.enable() if hasattr(p, "enable") else p.start()
            self.addCleanup(p.disable if hasattr(p, "disable") else p.stop)
        BudgetAccount.objects.using(LEDGER_ALIAS).create(
            ledger_id=h.LEDGER_ID, total_allowance_micro=50_000_000, model_id=h.MODEL,
            input_price_micro_per_mtok=h.IN_PRICE, output_price_micro_per_mtok=h.OUT_PRICE)
        self.client.force_login(self.user)
        from django.core.cache import cache
        cache.clear()

    def ask(self, request_id=None):
        def generate(self_, *, question, language, sources, **_):
            self_.last_usage = (700, 200)
            return self.good_output(sources, language)
        with patch("apps.ai_core.views_global.default_retriever",
                   return_value=self.FakeRetriever(self.evidence("en"))), \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate", autospec=True,
                      side_effect=generate) as gen:
            r = self.client.post(reverse("ai_core:ask-global"),
                                 data=json.dumps({"question": "What is quantum computing?", "language": "en"}),
                                 content_type="application/json",
                                 HTTP_X_VQ_REQUEST_ID=request_id or str(uuid.uuid4()))
        return r, gen.call_count

    def test_daily_ceiling_blocks_the_third_paid_call_and_replay_costs_nothing(self):
        first_id = str(uuid.uuid4())
        results = [self.ask(first_id), self.ask()]
        with self.assertLogs("apps.ai_ledger.service", "WARNING") as logs:
            results.append(self.ask())
        self.assertIn("ai_ledger_staging_daily_cap_reached kind=requests", "\n".join(logs.output))
        self.assertEqual([(r.status_code, c) for r, c in results], [(200, 1), (200, 1), (429, 0)],
                         [r.content[:200] for r, _ in results])
        self.assertEqual(results[2][0].json(), {"error": "rate_limited"})
        replay, calls = self.ask(first_id)
        self.assertEqual((replay.status_code, calls), (200, 0))
        self.assertEqual(staging_rows().count(), 2)
        self.assertEqual(set(staging_rows().values_list("status", flat=True)), {"finalized"})

    def test_redis_outage_fails_closed_before_any_reservation(self):
        with patch("apps.ai_core.global_budget.cache.incr", side_effect=ConnectionError("redis down")), \
                override_settings(VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=False):
            r, calls = self.ask()
        self.assertEqual((r.status_code, calls), (429, 0))
        self.assertEqual(staging_rows().count(), 0)

    def test_ledger_outage_fails_closed_without_provider_call(self):
        with patch("apps.ai_ledger.service._verify_identity", side_effect=OperationalError("down")):
            r, calls = self.ask()
        self.assertEqual((r.status_code, calls), (429, 0))
        self.assertEqual(staging_rows().count(), 0)

    def test_unconfigured_ceiling_fails_closed(self):
        with override_settings(VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS=0):
            r, calls = self.ask()
        self.assertEqual((r.status_code, calls), (429, 0))
        self.assertEqual(staging_rows().count(), 0)
