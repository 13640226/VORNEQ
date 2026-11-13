"""PostgreSQL concurrency regression for staging AI budget. No provider calls.

Run with a dedicated PostgreSQL test database:
python manage.py test apps.ai_core.tests.test_ai_staging_budget_concurrency
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connection, connections
from django.test import TransactionTestCase, override_settings

from apps.ai_core.engine.budget import BudgetExceeded
from apps.ai_core.models import StagingAIBudgetDay
from apps.ai_core.staging_budget import reserve_staging_request


@override_settings(
    VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD=30_000,
    VORNEQ_AI_STAGING_RESERVE_MICROUSD=10_000,
    VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS=3,
)
class StagingBudgetConcurrencyTests(TransactionTestCase):
    """Real transactions and separate connections, not TestCase's outer transaction."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL required for row-lock concurrency assertions")

    def _race(self, workers=10):
        barrier = Barrier(workers)

        def reserve(_index):
            # A new worker thread owns its own connection. Always close it,
            # including when CONN_MAX_AGE keeps connections persistent.
            connections.close_all()
            try:
                barrier.wait(timeout=20)
                reserve_staging_request()
                return "allowed"
            except BudgetExceeded:
                return "denied"
            finally:
                connections.close_all()

        # Only bypass authorization in the isolated test; never call a provider.
        with patch("apps.ai_core.staging_budget.trial_enabled", return_value=True):
            with ThreadPoolExecutor(max_workers=workers) as pool:
                return list(pool.map(reserve, range(workers)))

    def _assert_ceiling(self, results):
        row = StagingAIBudgetDay.objects.get()
        self.assertEqual(results.count("allowed"), 3)
        self.assertEqual(results.count("denied"), 7)
        self.assertEqual(row.request_count, 3)
        self.assertEqual(row.reserved_micro_usd, 30_000)

    def test_concurrent_creation_of_first_daily_row(self):
        self.assertFalse(StagingAIBudgetDay.objects.exists())
        self._assert_ceiling(self._race())

    def test_concurrent_reservations_with_existing_row(self):
        from datetime import datetime, timezone

        StagingAIBudgetDay.objects.create(day_utc=datetime.now(timezone.utc).date())
        self._assert_ceiling(self._race())
