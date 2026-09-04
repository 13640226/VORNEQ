from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.evidence.models import Claim
from apps.evidence.services import PredictionLedgerService


class PredictionLedgerEndpointTests(TestCase):
    def setUp(self):
        self.claim = Claim.objects.create(
            claim_text="A manufacturing process will achieve 95% yield in the pilot line.",
            scope="technical diligence pilot",
        )
        self.due = timezone.now() + timedelta(days=7)
        self.prediction = PredictionLedgerService.create(
            claim=self.claim,
            event_statement="The independent pilot report will show at least 95% yield.",
            probability="0.7000",
            resolution_date=self.due,
            rationale="Forecast recorded before the pilot report is available.",
        )

    def test_prediction_ledger_endpoint_is_read_only_and_reports_open_forecast(self):
        response = self.client.get(
            reverse("graph:prediction-ledger", kwargs={"claim_id": self.claim.pk})
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["predictions"]), 1)
        self.assertIsNone(payload["predictions"][0]["resolution"])
        self.assertEqual(payload["scoring_summary"]["resolved_predictions"], 0)

    def test_decision_package_includes_prediction_ledger_and_score(self):
        PredictionLedgerService.resolve(
            prediction=self.prediction,
            outcome_occurred=False,
            resolved_at=self.due + timedelta(minutes=1),
        )

        response = self.client.get(
            reverse("graph:decision-package", kwargs={"claim_id": self.claim.pk})
        )
        self.assertEqual(response.status_code, 200)
        ledger = response.json()["prediction_ledger"]
        self.assertEqual(ledger["scoring_summary"]["resolved_predictions"], 1)
        self.assertAlmostEqual(
            ledger["scoring_summary"]["mean_brier_score"],
            0.49,
        )
