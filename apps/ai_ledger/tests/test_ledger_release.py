"""ledger.release(): atomic, idempotent, auditable; never after settle.

REAL PostgreSQL row locks (disposable test database only). Skipped on SQLite.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import connections
from django.test import TransactionTestCase, override_settings

from apps.ai_ledger.models import BudgetReservation
from apps.ai_ledger.service import RELEASED, release, settle
from apps.ai_ledger.tests import helpers as h
from apps.ai_ledger.tests.test_ledger_postgres import IS_PG, LEDGER_ALIAS, account, do_reserve_explicit


@skipUnless(IS_PG, "real PostgreSQL row locking required")
class LedgerReleaseTests(TransactionTestCase):
    databases = {"default", LEDGER_ALIAS}

    def setUp(self):
        override = override_settings(**h.ledger_settings())
        override.enable()
        self.addCleanup(override.disable)
        h.provision(5)

    def row(self, reservation):
        return BudgetReservation.objects.using(LEDGER_ALIAS).get(pk=reservation.id)

    def assert_invariants(self):
        acc = account()
        rows = BudgetReservation.objects.using(LEDGER_ALIAS).filter(account=acc)
        self.assertEqual(acc.reserved_micro, sum(r.reserved_micro for r in rows if r.status == "reserved"))
        self.assertEqual(acc.finalized_micro, sum(r.observed_micro for r in rows if r.status == "finalized"))
        self.assertEqual(acc.uncertain_micro, sum(r.reserved_micro for r in rows if r.status == "uncertain"))
        return acc

    def test_release_returns_allowance_and_is_auditable(self):
        before = account().remaining_micro()
        res = do_reserve_explicit("staging")
        self.assertEqual(account().remaining_micro(), before - h.COST)
        self.assertEqual(release(res, reason="prompt_moderated"), RELEASED)
        row = self.row(res)
        self.assertEqual((row.status, row.observed_micro, row.input_tokens, row.output_tokens),
                         ("finalized", 0, 0, 0))
        self.assertEqual(row.outcome, "released:prompt_moderated")
        self.assertIsNotNone(row.settled_at)
        self.assertEqual(self.assert_invariants().remaining_micro(), before)

    def test_release_is_idempotent_and_never_follows_settle(self):
        # Another open reservation keeps reserved_micro high enough that the
        # non-negative DB constraint alone could not catch a double release.
        do_reserve_explicit("staging")
        res = do_reserve_explicit("staging")
        self.assertEqual(release(res, reason="sdk_unavailable"), RELEASED)
        self.assertIsNone(release(res, reason="sdk_unavailable"))
        self.assertIsNone(settle(res, usage=None, outcome="late"))
        self.assertEqual(self.row(res).outcome, "released:sdk_unavailable")
        settled = do_reserve_explicit("staging")
        self.assertEqual(settle(settled, usage=None, outcome="uncertain:provider_timeout"),
                         "uncertain")
        self.assertIsNone(release(settled, reason="provider_timeout"))
        self.assertEqual(self.row(settled).status, "uncertain")
        finalized = do_reserve_explicit("staging")
        self.assertEqual(settle(finalized, usage=(10, 20), outcome="ok"), "finalized")
        self.assertIsNone(release(finalized, reason="late"))
        self.assertGreater(self.row(finalized).observed_micro, 0)
        self.assert_invariants()

    def test_invalid_reason_or_database_error_changes_nothing(self):
        res = do_reserve_explicit("staging")
        for reason in ("", "Has Spaces", "x" * 31, None, "prompt;drop"):
            self.assertIsNone(release(res, reason=reason))
        with patch("apps.ai_ledger.models.BudgetAccount.objects.using",
                   side_effect=RuntimeError("synthetic db failure")):
            self.assertIsNone(release(res, reason="sdk_unavailable"))
        self.assertEqual(self.row(res).status, "reserved")
        self.assert_invariants()

    def test_concurrent_release_and_settle_exactly_one_wins(self):
        for _ in range(3):
            res = do_reserve_explicit("staging")
            barrier = Barrier(2)

            def work(i):
                connections.close_all()
                try:
                    barrier.wait(timeout=20)
                    if i == 0:
                        return release(res, reason="sdk_unavailable")
                    return settle(res, usage=None, outcome="uncertain:provider_timeout")
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(work, range(2)))
            self.assertEqual(sum(r is not None for r in results), 1, results)
            self.assertIn(self.row(res).status, ("finalized", "uncertain"))
        self.assert_invariants()
