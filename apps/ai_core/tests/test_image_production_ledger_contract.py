from django.test import SimpleTestCase

from apps.ai_core.image_generation.production_ledger_contract import (
    ProductionImageBudget, production_image_ledger_ready,
)


class ProductionImageLedgerContractTests(SimpleTestCase):
    def setUp(self):
        self.budget = ProductionImageBudget(5_000_000, 200_000, 100_000)

    def test_exact_owner_caps(self):
        self.assertTrue(self.budget.valid())

    def test_budget_rejects_bool(self):
        self.assertFalse(ProductionImageBudget(True, 200_000, 100_000).valid())

    def test_reservation_within_limits(self):
        self.assertTrue(self.budget.permits_reservation(
            project_used=0, daily_used=0, amount=100_000
        ))

    def test_reservation_above_daily_remaining_denied(self):
        self.assertFalse(self.budget.permits_reservation(
            project_used=0, daily_used=150_000, amount=100_000
        ))

    def test_reservation_above_project_remaining_denied(self):
        self.assertFalse(self.budget.permits_reservation(
            project_used=4_950_000, daily_used=0, amount=100_000
        ))

    def test_negative_and_bool_denied(self):
        self.assertFalse(self.budget.permits_reservation(
            project_used=-1, daily_used=0, amount=1
        ))
        self.assertFalse(self.budget.permits_reservation(
            project_used=0, daily_used=False, amount=1
        ))

    def test_ledger_stays_closed(self):
        self.assertFalse(production_image_ledger_ready())
