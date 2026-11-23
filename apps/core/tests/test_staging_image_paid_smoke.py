"""Offline tests for the one-use Staging PAID image smoke runner.

No network, no real SDK, no billing: a recording fake replaces ``openai`` and
the ledger runs on the disposable PostgreSQL test database (skipped on SQLite).
"""
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from apps.ai_core.image_generation.policy import OFFICIAL_PRICES_MICRO_PER_MTOK
from apps.ai_core.image_generation.storage import image_storage
from apps.ai_core.models import AIImageJob
from apps.ai_core.tests.test_image_paid_provider_v1 import FakeSDK, sdk_error
from apps.ai_ledger.models import BudgetAccount, BudgetReservation
from apps.ai_ledger.service import LEDGER_ALIAS
from apps.ai_ledger.tests import helpers as h
from apps.ai_ledger.tests.test_ledger_postgres import IS_PG
from apps.core import c02_owner_release as legacy
from apps.core import staging_image_mock_e2e as e2e
from apps.core import staging_image_paid_smoke as smoke
from apps.core.tests.test_staging_image_mock_e2e import (
    HOST, R2_HOST, STORES, ExecuteOnceTests,
)

SHA = "a" * 40
BACKUP = "b" * 64
EVIDENCE = "STAGING-IMAGE0004-RESTORE-PG18-20261121-0900Z-V1"
RELEASE_ID = "IMGPAID-20261121-0900Z-01"
NOW = datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc)
IMAGE_LEDGER = uuid.UUID("22222222-3333-4444-8555-666666666666")
API = "https://api.github.com/repos/13640226/VORNEQ"
KEY = "synthetic-offline-test-key-not-a-secret-0001"


def comment(*, created=NOW, header=smoke.HEADER, **over):
    manifest = {
        "decision": smoke.DECISION, "release_id": RELEASE_ID, "sha": SHA,
        "service_id": e2e.SERVICE, "postgres_id": e2e.POSTGRES, "database": e2e.DATABASE,
        "provider": "openai", "paid_calls": True, "model": smoke.MODEL, "size": smoke.SIZE,
        "quality": "low", "complexity": "low", "max_jobs": 1, "max_cost_microusd": 100_000,
        "image_ledger_id": str(IMAGE_LEDGER), "ledger_shared_with_production_accepted": True,
        "openai_project_budget_usd": 5, "bucket": e2e.BUCKET,
        "backup_sha256": BACKUP, "backup_evidence": EVIDENCE,
        "backup_exported_at": (created - timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "restore_verified_at": (created - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (created + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_acceptance": smoke.RISK,
    }
    manifest.update(over)
    return {
        "id": 123456, "url": f"{API}/issues/comments/123456", "issue_url": f"{API}/issues/664",
        "html_url": "https://github.com/13640226/VORNEQ/issues/664#issuecomment-123456",
        "user": {"login": "13640226", "id": 199411505, "type": "User"},
        "author_association": "OWNER",
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "updated_at": created.isoformat().replace("+00:00", "Z"),
        "body": header + "\n" + json.dumps(manifest),
    }


def verify(data, now=None):
    return smoke.validate_comment(data, comment_id=123456, expected_sha=SHA, release_id=RELEASE_ID,
                                  backup_sha256=BACKUP, backup_evidence=EVIDENCE,
                                  now=now or NOW + timedelta(minutes=1))


class PaidReleaseTests(SimpleTestCase):
    def test_exact_release_validates(self):
        target = verify(comment())
        self.assertEqual((target.max_cost_micro, target.image_ledger_id), (100_000, IMAGE_LEDGER))

    def test_scope_drift_rejected(self):
        cases = {
            "mock header reused": comment(header=e2e.HEADER),
            "mock decision": comment(decision=e2e.DECISION),
            "mock provider": comment(provider="mock"),
            "paid flag off": comment(paid_calls=False),
            "other model": comment(model="gpt-image-2.6-sunburst"),
            "quality high": comment(quality="high"),
            "complexity high": comment(complexity="high"),
            "bigger size": comment(size="1536x1024"),
            "two jobs": comment(max_jobs=2),
            "cost over 0.10": comment(max_cost_microusd=100_001),
            "cost as string": comment(max_cost_microusd="100000"),
            "zero cost": comment(max_cost_microusd=0),
            "shared ledger not accepted": comment(ledger_shared_with_production_accepted=False),
            "provider budget missing": comment(openai_project_budget_usd=0),
            "provider budget too high": comment(openai_project_budget_usd=500),
            "bad ledger id": comment(image_ledger_id="not-a-uuid"),
            "production service": comment(service_id="srv-dadn07eq1p3s73eccau0"),
            "stale backup": comment(backup_exported_at=(NOW - timedelta(hours=3))
                                    .strftime("%Y-%m-%dT%H:%M:%SZ")),
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(legacy.OwnerReleaseDenied):
                verify(data)
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(comment(), now=NOW + timedelta(minutes=31))


class CostModelTests(SimpleTestCase):
    def test_worst_case_uses_ledger_formula_and_official_prices(self):
        from apps.ai_ledger.service import worst_case_cost_micro
        self.assertEqual(OFFICIAL_PRICES_MICRO_PER_MTOK[smoke.MODEL], (5_000_000, 30_000_000))
        expected = worst_case_cost_micro(input_bytes=len(smoke.PROMPT.encode()),
                                         max_output_tokens=2_000, input_price=5_000_000,
                                         output_price=30_000_000)
        self.assertEqual(smoke.worst_case_micro(output_bound=2_000), expected)

    def test_largest_bound_for_ten_cents(self):
        bound = smoke.max_output_bound_for(100_000)
        self.assertLessEqual(smoke.worst_case_micro(output_bound=bound), 100_000)
        self.assertGreater(smoke.worst_case_micro(output_bound=bound + 1), 100_000)
        self.assertGreater(bound, 1_000)


def image_account(**over):
    fields = dict(ledger_id=IMAGE_LEDGER, total_allowance_micro=2_000_000, safety_reserve_micro=0,
                  model_id=smoke.MODEL, input_price_micro_per_mtok=5_000_000,
                  output_price_micro_per_mtok=30_000_000, allowed_environments="staging")
    fields.update(over)
    return BudgetAccount.objects.using(LEDGER_ALIAS).create(**fields)


PAID_SETTINGS = dict(
    VORNEQ_AI_IMAGE_LEDGER_ID=str(IMAGE_LEDGER), VORNEQ_AI_IMAGE_MODEL=smoke.MODEL,
    VORNEQ_AI_IMAGE_COMPLEXITY="low", VORNEQ_AI_IMAGE_SAFETY_ID_KEY=KEY,
    VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND=2_000, VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD=100_000,
    VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=100_000, VORNEQ_AI_IMAGE_WORKER_SERVICE_ID="",
    VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS=1, VORNEQ_AI_IMAGE_LEDGER_DAILY_MAX_REQUESTS=None,
)


@skipUnless(IS_PG, "ledger needs PostgreSQL")
class LedgerPreflightTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        override = override_settings(**h.ledger_settings(), **PAID_SETTINGS)
        override.enable()
        self.addCleanup(override.disable)
        h.provision(1)  # chat account, shared ledger

    def run_checks(self):
        checks = smoke.Checks()
        info = smoke.ledger_checks(checks, cap_micro=100_000,
                                   expected_image_ledger_id=IMAGE_LEDGER)
        return checks, info

    def test_correct_staging_only_image_account_passes_read_only(self):
        image_account()
        counts = (BudgetAccount.objects.using(LEDGER_ALIAS).count(),
                  BudgetReservation.objects.using(LEDGER_ALIAS).count())
        checks, info = self.run_checks()
        self.assertTrue(checks.go, list(checks.lines()))
        self.assertIn("CHECK ledger_readable PASS read_only_txn=on", list(checks.lines()))
        self.assertFalse(info["shared_with_production"])
        self.assertEqual(counts, (BudgetAccount.objects.using(LEDGER_ALIAS).count(),
                                  BudgetReservation.objects.using(LEDGER_ALIAS).count()))

    def test_unsafe_accounts_are_no_go(self):
        cases = {
            "image_account_staging_only": {"allowed_environments": "staging,production"},
            "image_account_official_prices": {"output_price_micro_per_mtok": 20_000_000},
            "image_account_model": {"model_id": "gpt-image-2.6-sunburst"},
            "image_account_not_stopped": {"emergency_stop": True},
            "image_account_balance": {"total_allowance_micro": 50_000},
        }
        for check, over in cases.items():
            with self.subTest(check):
                BudgetAccount.objects.using(LEDGER_ALIAS).filter(ledger_id=IMAGE_LEDGER).delete()
                image_account(**over)
                checks, _ = self.run_checks()
                self.assertFalse(checks.go)
                self.assertIn(check, [n for n, ok, _ in checks.items if not ok])

    def test_missing_account_or_shared_id_is_no_go(self):
        checks, _ = self.run_checks()
        self.assertIn("image_account_exists", [n for n, ok, _ in checks.items if not ok])
        with override_settings(VORNEQ_AI_IMAGE_LEDGER_ID=str(h.LEDGER_ID)):
            checks, _ = self.run_checks()
        self.assertIn("image_ledger_separate_from_chat", [n for n, ok, _ in checks.items if not ok])

    def test_reports_ledger_shared_with_production(self):
        image_account()
        from apps.ai_ledger.tests.test_ledger_postgres import do_reserve_explicit
        do_reserve_explicit("production")
        _, info = self.run_checks()
        self.assertTrue(info["shared_with_production"])


@skipUnless(IS_PG, "ledger needs PostgreSQL")
class LedgerAuditTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        override = override_settings(**h.ledger_settings(), **PAID_SETTINGS)
        override.enable()
        self.addCleanup(override.disable)
        h.provision(2)
        image_account()

    def test_audit_is_read_only_complete_and_redacted(self):
        from apps.ai_ledger.tests.test_ledger_postgres import do_reserve_explicit
        do_reserve_explicit("production")
        before = (BudgetAccount.objects.using(LEDGER_ALIAS).count(),
                  BudgetReservation.objects.using(LEDGER_ALIAS).count())
        lines = []
        smoke.ledger_audit(out=lines.append)
        text = "\n".join(lines)
        self.assertIn("LEDGER_AUDIT transaction_read_only=on", lines)
        self.assertIn("LEDGER_AUDIT db_matches_expected=True", lines)
        self.assertIn("LEDGER_AUDIT ai_ledger_migrations=0001_initial,0002_productionimageusage", lines)
        for table in ("budgetaccount", "budgetreservation", "externalusagerecord"):
            self.assertIn("LEDGER_AUDIT columns_ai_ledger_{}=MATCH".format(table), lines)
        accounts = [json.loads(l.split("=", 1)[1]) for l in lines
                    if l.startswith("LEDGER_AUDIT account=")]
        self.assertEqual(sorted(a["role"] for a in accounts), ["chat", "image"])
        chat = next(a for a in accounts if a["role"] == "chat")
        self.assertEqual(chat["reservations_by_environment"], {"production": 1})
        self.assertTrue(all(a["totals_match_rows"] for a in accounts))
        self.assertNotIn(str(h.LEDGER_ID), text)
        self.assertNotIn(str(IMAGE_LEDGER), text)
        self.assertEqual(lines[-1], "LEDGER_AUDIT RESULT=READ_ONLY_LEDGER_AUDIT_COMPLETE")
        self.assertEqual(before, (BudgetAccount.objects.using(LEDGER_ALIAS).count(),
                                  BudgetReservation.objects.using(LEDGER_ALIAS).count()))


class SettingsChecksTests(SimpleTestCase):
    def failing(self, **over):
        checks = smoke.Checks()
        with override_settings(**dict(PAID_SETTINGS, **over)), \
                patch.dict(os.environ, {"VORNEQ_OPENAI_IMAGE_API_KEY": "synthetic-never-live"}):
            smoke._settings_checks(checks, cap_micro=100_000)
        return [n for n, ok, _ in checks.items if not ok]

    def test_preflight_does_not_accept_chat_key_in_place_of_image_key(self):
        checks = smoke.Checks()
        with (override_settings(**PAID_SETTINGS),
              patch.dict(os.environ, {
                  "OPENAI_API_KEY": "synthetic-chat-project-key",
                  "VORNEQ_OPENAI_IMAGE_API_KEY": "",
              })):
            smoke._settings_checks(checks, cap_micro=100_000)
        self.assertIn("image_openai_key_present",
                      [name for name, ok, _ in checks.items if not ok])

    def test_ledger_limit_unset_inherits_service_limit_invalid_fails_closed(self):
        from apps.ai_core.image_generation.service import ImageQueueError, image_ledger_daily_limit
        with override_settings(VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS=1,
                               VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=200_000,
                               VORNEQ_AI_IMAGE_LEDGER_DAILY_MAX_REQUESTS=None):
            self.assertEqual(image_ledger_daily_limit().max_requests, 1)
            for invalid in (0, -1, 51, "2", True):
                with self.subTest(invalid=invalid), \
                        override_settings(VORNEQ_AI_IMAGE_LEDGER_DAILY_MAX_REQUESTS=invalid):
                    with self.assertRaises(ImageQueueError):
                        image_ledger_daily_limit()

    def test_bound_and_caps(self):
        self.assertNotIn("worst_case_within_cap", self.failing())
        self.assertIn("worst_case_within_cap",
                      self.failing(VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND=10_000))
        self.assertIn("output_token_bound", self.failing(VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND=0))
        self.assertIn("per_request_cap", self.failing(VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD=0))
        self.assertIn("daily_cap", self.failing(VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=10))
        self.assertIn("safety_identifier_key", self.failing(VORNEQ_AI_IMAGE_SAFETY_ID_KEY=""))
        self.assertIn("complexity_low", self.failing(VORNEQ_AI_IMAGE_COMPLEXITY="high"))
        self.assertIn("no_worker_identity",
                      self.failing(VORNEQ_AI_IMAGE_WORKER_SERVICE_ID="srv-" + "a" * 20))


TARGET = smoke.ApprovedTarget(RELEASE_ID, legacy.VerifiedOwnerRelease(
    release_id=RELEASE_ID, comment_id=123456, sha=SHA, body_sha256="e" * 64,
    backup_sha256=BACKUP, backup_evidence=EVIDENCE, expires_at=NOW), 100_000, IMAGE_LEDGER)
STAGING = {"VORNEQ_ENV": "staging", "DEBUG": False, "ALLOWED_HOSTS": [HOST],
           "VORNEQ_AI_IMAGE_ENABLED": False, "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False,
           "VORNEQ_AI_EMERGENCY_STOP": False, "STORAGES": STORES}


@skipUnless(IS_PG, "ledger needs PostgreSQL")
class PaidExecuteTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        override = override_settings(**h.ledger_settings(), **PAID_SETTINGS, **STAGING)
        override.enable()
        self.addCleanup(override.disable)
        for p in (patch.dict(os.environ, {"RENDER_SERVICE_ID": e2e.SERVICE,
                                          "RENDER_GIT_COMMIT": SHA,
                                          "VORNEQ_OPENAI_IMAGE_API_KEY": "synthetic-never-live"}),
                  patch("apps.ai_core.image_generation.storage.durable_storage_ready",
                        return_value=True)):
            p.start()
            self.addCleanup(p.stop)
        image_account()
        self.consume = Mock()
        self.fetcher = ExecuteOnceTests()
        self.fetcher.sdk_imports = []

    def run_smoke(self, sdk):
        lines = []
        with patch.dict(sys.modules, {"openai": sdk.module()}):
            try:
                smoke.execute_once(None, TARGET, SHA, public_host=HOST, out=lines.append,
                                   fetch=self.fetcher.fetch, consume=self.consume,
                                   endpoint_host=R2_HOST)
                error = None
            except smoke.Aborted as exc:
                error = str(exc)
        return lines, error

    def reservation(self):
        return BudgetReservation.objects.using(LEDGER_ALIAS).get(account__ledger_id=IMAGE_LEDGER)

    def test_success_is_one_call_finalized_and_cleaned(self):
        sdk = FakeSDK()
        lines, error = self.run_smoke(sdk)
        self.assertIsNone(error, lines)
        self.assertEqual(len(sdk.image_calls()), 1)
        call = sdk.image_calls()[0]
        self.assertEqual((call["quality"], call["complexity"], call["size"], call["n"]),
                         ("low", "low", "1024x1024", 1))
        row = self.reservation()
        self.assertEqual((row.status, row.input_tokens, row.output_tokens), ("finalized", 12, 310))
        self.assertLessEqual(row.observed_micro, 100_000)
        self.assertLessEqual(row.observed_micro, row.reserved_micro)
        self.assertIn("E2E_STEP_OK signed_download_digest_match", lines)
        self.assertTrue(any(line.startswith("PAID_SMOKE_LEDGER status=finalized") for line in lines))
        self.assertFalse(AIImageJob.objects.exists())
        self.assertFalse(get_user_model().objects.exists())
        self.assertEqual(image_storage().listdir("")[1], [])
        self.consume.assert_called_once()
        self.assertFalse(any("sk-" in line or "PROMPT-SECRET" in line for line in lines))

    def test_rate_limit_after_send_stays_uncertain_and_keeps_evidence(self):
        sdk = FakeSDK(generate_error=sdk_error("RateLimitError", 429))
        lines, error = self.run_smoke(sdk)
        self.assertIn("provider_rate_limited", error)
        self.assertEqual(len(sdk.image_calls()), 1)  # never retried
        self.assertEqual(self.reservation().status, "uncertain")
        self.assertIn("PAID_SMOKE_CLEANUP DEFERRED_FOR_RECONCILIATION", lines)
        self.assertEqual(AIImageJob.objects.get().status, AIImageJob.STATUS_UNCERTAIN)
        self.assertTrue(get_user_model().objects.filter(
            username__startswith=smoke.USER_PREFIX).exists())

    def test_moderated_prompt_is_released_and_cleaned(self):
        sdk = FakeSDK(flagged=True)
        lines, error = self.run_smoke(sdk)
        self.assertIn("prompt_moderated", error)
        self.assertEqual(sdk.image_calls(), [])
        row = self.reservation()
        self.assertEqual((row.status, row.observed_micro, row.outcome),
                         ("finalized", 0, "released:prompt_moderated"))
        self.assertFalse(AIImageJob.objects.exists())
        self.assertFalse(get_user_model().objects.exists())

    def test_cost_over_ceiling_never_calls_provider(self):
        sdk = FakeSDK()
        with override_settings(VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND=10_000,
                               VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=1_000_000):
            lines, error = self.run_smoke(sdk)
        self.assertIn("cost_ceiling_exceeded", error)
        self.assertIsNone(sdk.ctor_kwargs)
        self.assertEqual(self.reservation().outcome, "released:cost_ceiling_exceeded")

    def test_daily_cap_refuses_reservation_before_any_call(self):
        sdk = FakeSDK()
        with override_settings(VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND=10_000), \
                patch.dict(sys.modules, {"openai": sdk.module()}), \
                self.assertRaises(smoke.Refused) as ctx:
            smoke.execute_once(None, TARGET, SHA, public_host=HOST, out=lambda _: None,
                               fetch=self.fetcher.fetch, consume=self.consume,
                               endpoint_host=R2_HOST)
        self.assertIn("image_ledger_daily_amount_available", str(ctx.exception))
        self.consume.assert_not_called()
        self.assertIsNone(sdk.ctor_kwargs)
        self.assertFalse(BudgetReservation.objects.using(LEDGER_ALIAS).filter(
            account__ledger_id=IMAGE_LEDGER).exists())

    def test_existing_queue_or_residue_refuses_before_receipt(self):
        get_user_model().objects.create(username=smoke.USER_PREFIX + "old")
        with patch.dict(sys.modules, {"openai": FakeSDK().module()}), \
                self.assertRaises(smoke.Refused):
            smoke.execute_once(None, TARGET, SHA, public_host=HOST, out=lambda _: None,
                               fetch=self.fetcher.fetch, consume=self.consume,
                               endpoint_host=R2_HOST)
        self.consume.assert_not_called()
        self.assertFalse(BudgetReservation.objects.using(LEDGER_ALIAS).filter(
            account__ledger_id=IMAGE_LEDGER).exists())


    def seed_completed_mock_job_today(self, *, submitted=1):
        """The real incident: an earlier Image Studio mock job on the same UTC day."""
        from apps.ai_core.models import AIImageDailyQuota
        owner = get_user_model().objects.create(username="studio-owner-mock")
        AIImageJob.objects.create(
            id=uuid.uuid4(), owner=owner, prompt="", prompt_digest="0" * 64, model_id="mock",
            image_size="1024x1024", provider="mock", status=AIImageJob.STATUS_COMPLETED,
            is_mock=True)
        AIImageDailyQuota.objects.update_or_create(
            day_utc=datetime.now(timezone.utc).date(), defaults={"submitted": submitted})

    def test_full_global_quota_refuses_before_receipt_reservation_or_provider(self):
        self.seed_completed_mock_job_today(submitted=1)
        sdk = FakeSDK()
        with override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=1), \
                patch.dict(sys.modules, {"openai": sdk.module()}), \
                self.assertRaises(smoke.Refused) as ctx:
            smoke.execute_once(None, TARGET, SHA, public_host=HOST, out=lambda _: None,
                               fetch=self.fetcher.fetch, consume=self.consume,
                               endpoint_host=R2_HOST)
        self.assertIn("PAID_SMOKE_PREFLIGHT_GLOBAL_QUOTA_EXHAUSTED", str(ctx.exception))
        self.assertIn("submitted_today=1 global_cap=1", str(ctx.exception))
        self.consume.assert_not_called()
        self.assertIsNone(sdk.ctor_kwargs)
        self.assertEqual(sdk.image_calls(), [])
        self.assertFalse(BudgetReservation.objects.using(LEDGER_ALIAS).filter(
            account__ledger_id=IMAGE_LEDGER).exists())
        self.assertEqual(AIImageJob.objects.count(), 1)  # retained mock job untouched

    def test_earlier_mock_job_with_capacity_left_allows_exactly_one_paid_call(self):
        from apps.ai_core.models import AIImageDailyQuota
        self.seed_completed_mock_job_today(submitted=1)
        sdk = FakeSDK()
        with override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=10):
            lines, error = self.run_smoke(sdk)
        self.assertIsNone(error, lines)
        self.assertEqual(len(sdk.image_calls()), 1)
        self.consume.assert_called_once()
        self.assertEqual(self.reservation().status, "finalized")
        # Only the paid job is cleaned up; the earlier mock job and its quota stay.
        self.assertEqual(AIImageJob.objects.count(), 1)
        self.assertEqual(AIImageDailyQuota.objects.get(
            day_utc=datetime.now(timezone.utc).date()).submitted, 1)


    def seed_paid_reservation_today(self, observed_micro=24_815):
        account = BudgetAccount.objects.using(LEDGER_ALIAS).get(ledger_id=IMAGE_LEDGER)
        row = BudgetReservation.objects.using(LEDGER_ALIAS).create(
            id=uuid.uuid4(), account=account, environment="staging", service_id=e2e.SERVICE,
            git_sha=SHA, actor_id=7, reserved_micro=87_938, observed_micro=observed_micro,
            status="finalized", outcome="completed")
        BudgetAccount.objects.using(LEDGER_ALIAS).filter(pk=account.pk).update(
            finalized_micro=observed_micro)
        return row

    def test_full_ledger_count_refuses_before_receipt_even_with_global_capacity(self):
        self.seed_completed_mock_job_today()
        prior = self.seed_paid_reservation_today()
        sdk = FakeSDK()
        with override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=2,
                               VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=200_000), \
                patch.dict(sys.modules, {"openai": sdk.module()}), \
                self.assertRaises(smoke.Refused) as ctx:
            smoke.execute_once(None, TARGET, SHA, public_host=HOST, out=lambda _: None,
                               fetch=self.fetcher.fetch, consume=self.consume,
                               endpoint_host=R2_HOST)
        self.assertIn("image_ledger_daily_requests_available", str(ctx.exception))
        self.consume.assert_not_called()
        self.assertEqual(sdk.image_calls(), [])
        self.assertEqual(BudgetReservation.objects.using(LEDGER_ALIAS).get(
            account__ledger_id=IMAGE_LEDGER).pk, prior.pk)
        self.assertEqual(AIImageJob.objects.count(), 1)

    def test_explicit_ledger_count_two_records_one_new_call_without_reset(self):
        self.seed_completed_mock_job_today()
        prior = self.seed_paid_reservation_today()
        sdk = FakeSDK()
        with override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=2,
                               VORNEQ_AI_IMAGE_LEDGER_DAILY_MAX_REQUESTS=2,
                               VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=200_000):
            lines, error = self.run_smoke(sdk)
        self.assertIsNone(error, lines)
        self.consume.assert_called_once()
        self.assertEqual(len(sdk.image_calls()), 1)
        rows = BudgetReservation.objects.using(LEDGER_ALIAS).filter(
            account__ledger_id=IMAGE_LEDGER)
        self.assertEqual(rows.count(), 2)
        self.assertTrue(rows.filter(pk=prior.pk, observed_micro=24_815).exists())
        self.assertEqual(AIImageJob.objects.count(), 1)

    def test_prior_spend_plus_reserve_over_amount_cap_refuses_even_with_count_room(self):
        self.seed_paid_reservation_today()
        sdk = FakeSDK()
        with override_settings(VORNEQ_AI_IMAGE_LEDGER_DAILY_MAX_REQUESTS=2,
                               VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=100_000), \
                patch.dict(sys.modules, {"openai": sdk.module()}), \
                self.assertRaises(smoke.Refused) as ctx:
            smoke.execute_once(None, TARGET, SHA, public_host=HOST, out=lambda _: None,
                               fetch=self.fetcher.fetch, consume=self.consume,
                               endpoint_host=R2_HOST)
        self.assertIn("image_ledger_daily_amount_available", str(ctx.exception))
        self.consume.assert_not_called()
        self.assertEqual(sdk.image_calls(), [])
        self.assertEqual(BudgetReservation.objects.using(LEDGER_ALIAS).filter(
            account__ledger_id=IMAGE_LEDGER).count(), 1)

    def test_gate_allows_one_submission_on_top_of_today_never_above_service_cap(self):
        gate = smoke._gate_settings(TARGET, SHA, 7, submitted_today=4, ledger_max_requests=2)
        self.assertEqual(gate["VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS"], 5)
        self.assertEqual(gate["VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS"], 1)
        self.assertEqual(gate["VORNEQ_AI_IMAGE_LEDGER_DAILY_MAX_REQUESTS"], 2)
        for submitted, cap, ok in ((0, 1, True), (1, 1, False), (4, 5, True), (5, 5, False),
                                   (0, None, False), (-1, 5, False)):
            with self.subTest(submitted=submitted, cap=cap):
                self.assertIs(smoke.global_quota_available(submitted, cap), ok)

    def test_rejected_submit_is_classified_without_sensitive_data(self):
        from apps.ai_core.models import AIImageDailyQuota
        day = datetime.now(timezone.utc).date()
        AIImageDailyQuota.objects.create(day_utc=day, submitted=3)
        response = Mock(status_code=400)
        response.json.return_value = {"error": "invalid_or_limited_request"}
        with override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=3):
            reason = smoke._submit_rejection(response, day)
        self.assertTrue(reason.startswith("PAID_SMOKE_SUBMIT_REJECTED_GLOBAL_DAILY_CAP status=400"))
        self.assertIn("provider not called", reason)
        response.json.return_value = {"error": "x" * 5 + "<script>"}
        with override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=10):
            reason = smoke._submit_rejection(response, day)
        self.assertEqual(reason, "PAID_SMOKE_SUBMIT_REJECTED status=400 error=unknown; "
                                 "provider not called")
        self.assertNotIn(smoke.PROMPT, reason)


@skipUnless(IS_PG, "ledger needs PostgreSQL")
class QuotaPreflightTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def test_preflight_reports_global_quota_state_read_only(self):
        from apps.ai_core.models import AIImageDailyQuota
        day = datetime.now(timezone.utc).date()
        with override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=1):
            self.assertEqual(smoke.global_quota_state(day), (0, 1))
            AIImageDailyQuota.objects.create(day_utc=day, submitted=1)
            self.assertEqual(smoke.global_quota_state(day), (1, 1))
            self.assertFalse(smoke.global_quota_available(*smoke.global_quota_state(day)))
        with override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=0):
            self.assertEqual(smoke.global_quota_state(day), (1, None))
        self.assertEqual(AIImageDailyQuota.objects.get(day_utc=day).submitted, 1)


class CommandTests(TransactionTestCase):
    def test_refuses_outside_staging_without_writes(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        for args in (["--expected-sha", SHA],
                     ["--expected-sha", SHA, "--execute", "--release-id", RELEASE_ID],
                     ["--expected-sha", SHA, "--release-id", RELEASE_ID],
                     ["--expected-sha", SHA, "--ledger-audit"],
                     ["--expected-sha", SHA, "--ledger-audit", "--execute"]):
            with self.subTest(args), self.assertRaisesMessage(
                    CommandError, "STAGING_IMAGE_PAID_SMOKE_REFUSED"):
                call_command("run_staging_image_paid_smoke_once", *args)
        self.assertFalse(AIImageJob.objects.exists())
