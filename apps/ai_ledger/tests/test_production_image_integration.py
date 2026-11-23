import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from django.db import connections
from django.test import TransactionTestCase, override_settings
from apps.ai_ledger.models import BudgetAccount, ProductionImageUsage
from apps.ai_ledger.service import LEDGER_ALIAS, LedgerConfig, LedgerUnavailable, EmergencyStop
from apps.ai_ledger.production_image import record_production_image_intent, reconcile_production_image
from apps.ai_core.image_generation.production_worker import production_worker_preflight, process_production_image_job

IS_PG = connections[LEDGER_ALIAS].vendor == "postgresql"

@skipUnless(IS_PG, "PostgreSQL required for transactional accounting")
class ProductionImageJournalPostgresTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        self.account_id = uuid.uuid4()
        self.config = LedgerConfig(self.account_id, connections[LEDGER_ALIAS].settings_dict["NAME"])
        self.account = BudgetAccount.objects.using(LEDGER_ALIAS).create(
            ledger_id=self.account_id, total_allowance_micro=1,
            model_id="gpt-image-2.6-flare", input_price_micro_per_mtok=5_000_000,
            output_price_micro_per_mtok=30_000_000, allowed_environments="production")
        self.sha = "a" * 40
        self.env = patch.dict(os.environ, {"RENDER_GIT_COMMIT": self.sha})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.auth = patch("apps.ai_core.image_generation.policy.production_uncapped_budget_requested", return_value=True)
        self.auth.start()
        self.addCleanup(self.auth.stop)
        self.ledger = patch("apps.ai_core.image_generation.policy.image_ledger_config", return_value=self.config)
        self.ledger.start()
        self.addCleanup(self.ledger.stop)

    def reserve(self, request_id=None, estimate=10_000_000):
        return record_production_image_intent(
            self.config, request_id=request_id or uuid.uuid4(), actor_id=1,
            service_id="srv-dadn07eq1p3s73eccau0", git_sha=self.sha,
            model="gpt-image-2.6-flare", estimated_micro=estimate)

    def test_uncapped_over_allowance_and_reconcile_once(self):
        request_id, created = self.reserve()
        self.assertTrue(created)
        self.assertEqual(self.reserve(request_id), (request_id, False))
        self.assertTrue(reconcile_production_image(request_id, observed_micro=20_000_000, outcome="success"))
        self.assertFalse(reconcile_production_image(request_id, observed_micro=0))
        row = ProductionImageUsage.objects.using(LEDGER_ALIAS).get(pk=request_id)
        self.assertEqual((row.status, row.observed_micro), ("finalized", 20_000_000))
        self.account.refresh_from_db(using=LEDGER_ALIAS)
        self.assertEqual(self.account.reserved_micro, 0)

    def test_uncertain_never_auto_zero(self):
        request_id, _ = self.reserve()
        self.assertTrue(reconcile_production_image(request_id, outcome="provider_timeout"))
        row = ProductionImageUsage.objects.using(LEDGER_ALIAS).get(pk=request_id)
        self.assertEqual(row.status, "uncertain")
        self.assertIsNone(row.observed_micro)

    def test_emergency_stop_denies_new_reservations(self):
        self.account.emergency_stop = True
        self.account.save(using=LEDGER_ALIAS)
        with self.assertRaises(EmergencyStop):
            self.reserve()

    def test_idempotency_conflict(self):
        request_id, _ = self.reserve()
        with self.assertRaises(LedgerUnavailable):
            self.reserve(request_id, estimate=1)

    def test_concurrent_same_request_only_one_created(self):
        request_id = uuid.uuid4()
        barrier = Barrier(3)
        def run(_):
            connections.close_all()
            try:
                barrier.wait(timeout=15)
                return self.reserve(request_id)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(run, range(3)))
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(ProductionImageUsage.objects.using(LEDGER_ALIAS).filter(pk=request_id).count(), 1)

class ProductionWorkerClosedTests(TransactionTestCase):
    def test_worker_cannot_open_via_env(self):
        with override_settings(VORNEQ_AI_IMAGE_PRODUCTION_ENABLED=True,
                               VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET=True,
                               VORNEQ_AI_EMERGENCY_STOP=False):
            with patch("apps.ai_core.deploy_authorization._verified_release", return_value=True):
                self.assertFalse(production_worker_preflight()["ready"])
                self.assertFalse(production_worker_preflight()["checks"]["provider_activation_authorized"])
                self.assertIsNone(process_production_image_job())
