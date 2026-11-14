"""Shared prepaid ledger on REAL PostgreSQL (disposable test database only).

Concurrency matrix C01-C15. Skipped on SQLite. No provider, no network.
"""
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import OperationalError, connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from apps.ai_ledger.models import BudgetAccount, BudgetReservation
from apps.ai_ledger.service import (LEDGER_ALIAS, BudgetExhausted, EmergencyStop, LedgerConfig,
                                    LedgerUnavailable, reserve, reserve_with_config, settle)
from apps.ai_ledger.tests import helpers as h

IS_PG = settings.DATABASES[LEDGER_ALIAS]["ENGINE"].endswith("postgresql")


def do_reserve(environment="production", **kw):
    with patch.dict(os.environ, h.runtime(environment)), override_settings(VORNEQ_ENV=environment):
        return reserve(actor_id=kw.get("actor", 7), model=kw.get("model", h.MODEL),
                       input_bytes=h.INPUT_BYTES, max_output_tokens=h.MAX_OUT)


def account():
    return BudgetAccount.objects.using(LEDGER_ALIAS).get(ledger_id=h.LEDGER_ID)


def race(n, fn):
    barrier = Barrier(n)

    def worker(i):
        connections.close_all()
        try:
            barrier.wait(timeout=20)
            try:
                return fn(i)
            except BudgetExhausted:
                return "exhausted"
            except LedgerUnavailable:
                return "unavailable"
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(worker, range(n)))


@skipUnless(IS_PG, "real PostgreSQL row locking required")
class SharedLedgerPostgresTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        self.settings_override = override_settings(**h.ledger_settings())
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def assert_invariants(self):
        acc = account()
        rows = BudgetReservation.objects.using(LEDGER_ALIAS).filter(account=acc)
        self.assertEqual(acc.reserved_micro, sum(r.reserved_micro for r in rows if r.status == "reserved"))
        self.assertEqual(acc.finalized_micro, sum(r.observed_micro for r in rows if r.status == "finalized"))
        self.assertEqual(acc.uncertain_micro, sum(r.reserved_micro for r in rows if r.status == "uncertain"))
        self.assertGreaterEqual(acc.remaining_micro(), 0)
        return acc

    def test_c01_twenty_simultaneous_only_three_affordable(self):
        h.provision(3, extra=h.COST - 1)
        results = race(20, lambda i: do_reserve())
        self.assertEqual(sum(1 for r in results if not isinstance(r, str)), 3, results)
        self.assertEqual(results.count("exhausted"), 17)
        self.assertEqual(self.assert_invariants().reserved_micro, 3 * h.COST)

    def test_c02_staging_and_production_share_one_cap(self):
        h.provision(4)
        results = race(12, lambda i: do_reserve("staging" if i % 2 else "production"))
        accepted = [r for r in results if not isinstance(r, str)]
        self.assertEqual(len(accepted), 4, results)
        envs = set(BudgetReservation.objects.using(LEDGER_ALIAS).values_list("environment", flat=True))
        self.assertTrue(envs <= {"staging", "production"})
        self.assert_invariants()

    def test_c03_c04_separate_processes_are_atomic(self):
        """Independent OS processes (separate Django instances / Gunicorn workers)."""
        h.provision(4)
        cfg = connections[LEDGER_ALIAS].settings_dict
        url = "postgres://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}".format(**{
            k: cfg.get(k) or "" for k in ("USER", "PASSWORD", "HOST", "PORT", "NAME")})
        start_at = time.time() + 4
        code = (
            "import os,sys,time,json,django;django.setup()\n"
            "from apps.ai_ledger.service import reserve_with_config,LedgerConfig,BudgetExhausted,EXPECTED_SERVICES\n"
            "import uuid\n"
            "env=sys.argv[1];cfg=LedgerConfig(uuid.UUID(sys.argv[2]),sys.argv[3])\n"
            "time.sleep(max(0,float(sys.argv[4])-time.time()))\n"
            "try:\n"
            " r=reserve_with_config(cfg,environment=env,service_id=EXPECTED_SERVICES[env],git_sha='a'*40,"
            "actor_id=9,model=sys.argv[5],input_bytes=1000,max_output_tokens=1024);print('ACCEPTED')\n"
            "except BudgetExhausted:print('EXHAUSTED')\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("RENDER", "DATABASE_URL"))}
        env.update({"VORNEQ_AI_LEDGER_DATABASE_URL": url, "DJANGO_SETTINGS_MODULE": "config.settings",
                    "VORNEQ_ENV": "development", "DJANGO_SECRET_KEY": "x" * 50, "DJANGO_DEBUG": "false",
                    "DJANGO_ALLOWED_HOSTS": "localhost"})
        procs = [subprocess.Popen([sys.executable, "-c", code, "staging" if i % 2 else "production",
                                   str(h.LEDGER_ID), cfg["NAME"], str(start_at), h.MODEL],
                                  cwd=settings.BASE_DIR, env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for i in range(10)]
        outputs = []
        for p in procs:
            out, err = p.communicate(timeout=90)
            self.assertEqual(p.returncode, 0, err[-1500:])
            outputs.append(out.strip().splitlines()[-1])
        self.assertEqual(outputs.count("ACCEPTED"), 4, outputs)
        self.assertEqual(outputs.count("EXHAUSTED"), 6, outputs)
        self.assertEqual(self.assert_invariants().reserved_micro, 4 * h.COST)

    def test_c05_database_unavailable_fails_closed(self):
        h.provision(5)
        with patch("apps.ai_ledger.service._verify_identity", side_effect=OperationalError("down")):
            with self.assertRaises(LedgerUnavailable):
                do_reserve()
        self.assertEqual(account().reserved_micro, 0)

    def test_c06_exact_exhaustion_then_reject(self):
        h.provision(2)
        do_reserve(), do_reserve()
        self.assertEqual(account().remaining_micro(), 0)
        with self.assertRaises(BudgetExhausted):
            do_reserve()

    def test_c07_just_below_reservation_rejected(self):
        h.provision(0, extra=h.COST - 1)
        with self.assertRaises(BudgetExhausted):
            do_reserve()
        self.assertEqual(BudgetReservation.objects.using(LEDGER_ALIAS).count(), 0)

    def test_c08_timeout_after_reservation_is_never_refunded(self):
        h.provision(2)
        res = do_reserve()
        settle(res, usage=None, outcome="ProviderTimeout")
        acc = self.assert_invariants()
        self.assertEqual((acc.reserved_micro, acc.uncertain_micro), (0, h.COST))
        self.assertEqual(acc.remaining_micro(), h.COST)  # one request left, not two
        settle(res, usage=(1, 1), outcome="late")       # idempotent: no double settlement
        self.assertEqual(account().uncertain_micro, h.COST)

    def test_finalized_usage_reconciles_below_reservation(self):
        h.provision(1)
        res = do_reserve()
        settle(res, usage=(800, 300), outcome="completed")
        acc = self.assert_invariants()
        row = BudgetReservation.objects.using(LEDGER_ALIAS).get(id=res.id)
        self.assertEqual((row.status, row.input_tokens, row.output_tokens), ("finalized", 800, 300))
        self.assertEqual(acc.finalized_micro, (800 * h.IN_PRICE + 300 * h.OUT_PRICE) // 1_000_000)
        self.assertLess(acc.finalized_micro, h.COST)

    def test_c09_repeated_client_retries_each_cost(self):
        h.provision(3)
        outcomes = []
        for _ in range(6):
            try:
                settle(do_reserve(), usage=None, outcome="client_retry")
                outcomes.append("accepted")
            except BudgetExhausted:
                outcomes.append("exhausted")
        self.assertEqual(outcomes, ["accepted"] * 3 + ["exhausted"] * 3)

    def test_c10_missing_or_invalid_configuration(self):
        h.provision(5)
        for overrides in ({"VORNEQ_AI_LEDGER_ENABLED": False}, {"VORNEQ_AI_LEDGER_ID": "not-a-uuid"},
                          {"VORNEQ_AI_LEDGER_DB_NAME": ""}, {"VORNEQ_AI_LEDGER_DB_NAME": "x;drop"}):
            with override_settings(**overrides), self.assertRaises(LedgerUnavailable):
                do_reserve()
        with self.assertRaises(LedgerUnavailable):
            do_reserve(model="unapproved-model")

    def test_c11_wrong_database_identity(self):
        h.provision(5)
        with override_settings(VORNEQ_AI_LEDGER_DB_NAME="vorneq_production"):
            with self.assertRaises(LedgerUnavailable):
                do_reserve()

    def test_c12_emergency_stop(self):
        h.provision(5, emergency_stop=True)
        with self.assertRaises(EmergencyStop):
            do_reserve()
        BudgetAccount.objects.using(LEDGER_ALIAS).update(emergency_stop=False)
        with override_settings(VORNEQ_AI_EMERGENCY_STOP=True), self.assertRaises(EmergencyStop):
            do_reserve()
        do_reserve()

    def test_c13_c14_foreign_ledger_or_runtime_rejected(self):
        h.provision(5, ledger_id=h.OTHER_LEDGER_ID)
        for environment in ("staging", "production"):
            with self.assertRaises(LedgerUnavailable):
                do_reserve(environment)
        cfg = LedgerConfig(h.OTHER_LEDGER_ID, connections[LEDGER_ALIAS].settings_dict["NAME"])
        for env, service in (("staging", "srv-dadn07eq1p3s73eccau0"), ("production", "srv-other"),
                             ("development", "srv-dbm7dvc9v7es7393g70g")):
            with self.assertRaises(LedgerUnavailable):
                reserve_with_config(cfg, environment=env, service_id=service, git_sha=h.SHA, actor_id=1,
                                    model=h.MODEL, input_bytes=1, max_output_tokens=64)
        BudgetAccount.objects.using(LEDGER_ALIAS).update(allowed_environments="staging")
        with self.assertRaises(LedgerUnavailable):
            reserve_with_config(cfg, environment="production", service_id="srv-dadn07eq1p3s73eccau0",
                                git_sha=h.SHA, actor_id=1, model=h.MODEL, input_bytes=1, max_output_tokens=64)

    def test_c15_concurrent_reserve_and_settle_no_overspend(self):
        h.provision(10)
        first = [do_reserve() for _ in range(5)]

        def work(i):
            if i < 5:
                settle(first[i], usage=(100 * i, 50), outcome="completed") if i % 2 else \
                    settle(first[i], usage=None, outcome="timeout")
                return "settled"
            return do_reserve()
        results = race(16, work)
        accepted = [r for r in results if not isinstance(r, str)]
        # Settled-below-reservation amounts legitimately free room; what must
        # never happen is committed money exceeding the allowance.
        self.assertGreaterEqual(len(accepted), 5, results)
        acc = self.assert_invariants()
        committed = acc.safety_reserve_micro + acc.consumed_before_micro + acc.reserved_micro \
            + acc.finalized_micro + acc.uncertain_micro
        self.assertLessEqual(committed, acc.total_allowance_micro)
        self.assertLess(acc.remaining_micro(), h.COST)  # no affordable request left unclaimed


@skipUnless(IS_PG, "real PostgreSQL row locking required")
class ProductionEndpointLedgerTests(TransactionTestCase):
    """End-to-end: production policy + Global AI endpoint + shared ledger."""
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        from apps.ai_core.tests.test_global_ai_api import FakeRetriever, evidence, good_output
        self.FakeRetriever, self.evidence, self.good_output = FakeRetriever, evidence, good_output
        self.user = get_user_model().objects.create_user(username="prod-ai", password="synthetic-only")
        env = {**h.env_without_render(), **h.runtime("production"),
               "VORNEQ_AI_PHASE_B_MODEL": h.MODEL, "OPENAI_API_KEY": "sk-synthetic-never-use"}
        for p in (patch.dict(os.environ, env, clear=True),
                  override_settings(VORNEQ_ENV="production", DEBUG=False, VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED=True,
                                    VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA=h.SHA,
                                    VORNEQ_AI_PRODUCTION_OWNER_AUTH="OWNER-AUTH-AI-PRODUCTION-TEST-01",
                                    VORNEQ_AI_PRODUCTION_APPROVED_MODEL=h.MODEL,
                                    VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS=str(self.user.pk),
                                    VORNEQ_GLOBAL_AI_QUOTA={"per_minute": 5}, **h.ledger_settings())):
            p.enable() if hasattr(p, "enable") else p.start()
            self.addCleanup(p.disable if hasattr(p, "disable") else p.stop)
        self.client.force_login(self.user)
        from django.core.cache import cache
        cache.clear()

    def ask(self, usage=(700, 200)):
        def generate(self_, *, question, language, sources):
            self_.last_usage = usage
            return self.good_output(sources, language)
        with patch("apps.ai_core.views_global.default_retriever",
                   return_value=self.FakeRetriever(self.evidence("en"))), \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate", autospec=True,
                      side_effect=generate) as gen:
            r = self.client.post(reverse("ai_core:ask-global"),
                                 data=json.dumps({"question": "What is quantum computing?", "language": "en"}),
                                 content_type="application/json")
        return r, gen.call_count

    def test_budget_governs_production_calls(self):
        # Reservation size depends on the real request payload; provision for exactly 2.
        BudgetAccount.objects.using(LEDGER_ALIAS).create(
            ledger_id=h.LEDGER_ID, total_allowance_micro=50_000_000, model_id=h.MODEL,
            input_price_micro_per_mtok=h.IN_PRICE, output_price_micro_per_mtok=h.OUT_PRICE)
        r, calls = self.ask()
        self.assertEqual((r.status_code, calls), (200, 1), r.content)
        row = BudgetReservation.objects.using(LEDGER_ALIAS).get()
        self.assertEqual((row.status, row.environment, row.input_tokens), ("finalized", "production", 700))
        per_call = row.reserved_micro
        acc = account()
        BudgetAccount.objects.using(LEDGER_ALIAS).update(
            total_allowance_micro=acc.finalized_micro + 2 * per_call)
        # Without authoritative usage each call stays counted at its full reservation.
        codes = [self.ask(usage=None) for _ in range(4)]
        self.assertEqual([c[0].status_code for c in codes], [200, 200, 429, 429])
        self.assertEqual([c[1] for c in codes], [1, 1, 0, 0])
        self.assertGreaterEqual(account().remaining_micro(), 0)

    def test_production_without_ledger_is_disabled(self):
        with override_settings(VORNEQ_AI_LEDGER_ENABLED=False):
            r, calls = self.ask()
        self.assertEqual((r.status_code, calls), (404, 0))


@skipUnless(IS_PG, "real PostgreSQL required")
class LedgerCommandTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def test_provision_stop_resume_record_external_status(self):
        from io import StringIO
        from django.core.management import CommandError, call_command
        with override_settings(**h.ledger_settings()):
            lid = str(h.LEDGER_ID)
            with self.assertRaises(CommandError):
                call_command("ai_ledger", "provision", "--ledger-id", lid, "--total-usd", "8",
                             "--model", h.MODEL, "--input-usd-per-mtok", "1", "--output-usd-per-mtok", "4",
                             "--confirm-ledger-id", str(h.OTHER_LEDGER_ID))
            call_command("ai_ledger", "provision", "--ledger-id", lid, "--total-usd", "8.00",
                         "--safety-usd", "2.00", "--consumed-before-usd", "0.25", "--model", h.MODEL,
                         "--input-usd-per-mtok", "1", "--output-usd-per-mtok", "4",
                         "--confirm-ledger-id", lid, stdout=StringIO())
            acc = account()
            self.assertEqual((acc.total_allowance_micro, acc.safety_reserve_micro, acc.consumed_before_micro),
                             (8_000_000, 2_000_000, 250_000))
            with self.assertRaises(CommandError):  # second provisioning refused
                call_command("ai_ledger", "provision", "--ledger-id", lid, "--total-usd", "9", "--model", h.MODEL,
                             "--input-usd-per-mtok", "1", "--output-usd-per-mtok", "4", "--confirm-ledger-id", lid)
            call_command("ai_ledger", "stop", "--confirm-ledger-id", lid, stdout=StringIO())
            self.assertTrue(account().emergency_stop)
            call_command("ai_ledger", "resume", "--confirm-ledger-id", lid, stdout=StringIO())
            call_command("ai_ledger", "record-external", "--usd", "0.10", "--note", "SYNTHETIC console reading",
                         "--confirm-ledger-id", lid, stdout=StringIO())
            out = StringIO()
            call_command("ai_ledger", "status", stdout=out)
            self.assertIn("consumed_before_micro=350000", out.getvalue())
            self.assertIn("remaining_micro=5650000", out.getvalue())
            self.assertFalse(account().emergency_stop)
        with override_settings(**{**h.ledger_settings(), "VORNEQ_AI_LEDGER_DB_NAME": "wrong_db"}):
            with self.assertRaises(LedgerUnavailable):
                call_command("ai_ledger", "status", stdout=StringIO())
