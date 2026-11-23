import uuid
from unittest.mock import patch
from django.test import SimpleTestCase
from apps.ai_ledger.service import LedgerConfig, LedgerUnavailable
from apps.ai_ledger.production_image import record_production_image_intent, reconcile_production_image

class ProductionImageAccountingValidationTests(SimpleTestCase):
    def setUp(self):
        self.config = LedgerConfig(uuid.uuid4(), "image_ledger")
        self.kwargs = dict(request_id=uuid.uuid4(), actor_id=1,
                           service_id="srv-dadn07eq1p3s73eccau0",
                           git_sha="a" * 40, model="gpt-image-2.6-flare",
                           estimated_micro=100)

    def test_closed_by_default(self):
        with self.assertRaises(LedgerUnavailable):
            record_production_image_intent(self.config, **self.kwargs)

    @patch("apps.ai_core.image_generation.policy.production_uncapped_budget_requested", return_value=True)
    def test_rejects_non_owner(self, _):
        with self.assertRaises(LedgerUnavailable):
            record_production_image_intent(self.config, **{**self.kwargs, "actor_id": 2})

    @patch("apps.ai_core.image_generation.policy.production_uncapped_budget_requested", return_value=True)
    def test_rejects_invalid_estimate(self, _):
        with self.assertRaises(LedgerUnavailable):
            record_production_image_intent(self.config, **{**self.kwargs, "estimated_micro": 0})

    def test_reconcile_rejects_negative_cost(self):
        with self.assertRaises(LedgerUnavailable):
            reconcile_production_image(uuid.uuid4(), observed_micro=-1)

    def test_reconcile_rejects_non_uuid4(self):
        with self.assertRaises(LedgerUnavailable):
            reconcile_production_image(uuid.uuid1(), observed_micro=0)
