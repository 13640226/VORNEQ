from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.evidence.models import Claim, Prediction
from apps.evidence.services import PredictionLedgerService


class PredictionLedgerTests(TestCase):
    def setUp(self):
        self.claim = Claim.objects.create(
            claim_text="A pilot cell will retain at least 90% capacity after 1,000 cycles.",
            scope="technical diligence pilot",
        )

    def test_prediction_is_probabilistic_append_only_and_scored_after_resolution(self):
        resolution_date = timezone.now() + timedelta(days=30)
        prediction = PredictionLedgerService.create(
            claim=self.claim,
            event_statement="Independent testing will confirm at least 90% retained capacity.",
            probability="0.8000",
            resolution_date=resolution_date,
            rationale="Based on current cycle-test evidence.",
        )

        with self.assertRaises(RuntimeError):
            prediction.save()

        with self.assertRaises(ValidationError):
            PredictionLedgerService.resolve(
                prediction=prediction,
                outcome_occurred=True,
                resolved_at=timezone.now(),
            )

        resolution = PredictionLedgerService.resolve(
            prediction=prediction,
            outcome_occurred=True,
            resolved_at=resolution_date + timedelta(minutes=1),
        )

        score = PredictionLedgerService.score(prediction)
        self.assertAlmostEqual(score["brier_score"], 0.04)
        self.assertAlmostEqual(score["accuracy_score"], 0.96)

        with self.assertRaises(RuntimeError):
            resolution.save()

        with self.assertRaises(ValidationError):
            PredictionLedgerService.resolve(
                prediction=prediction,
                outcome_occurred=False,
                resolved_at=resolution_date + timedelta(days=1),
            )

    def test_resolve_rechecks_database_when_caller_instance_is_stale(self):
        resolution_date = timezone.now() + timedelta(days=1)
        prediction = PredictionLedgerService.create(
            claim=self.claim,
            event_statement="A stale caller cannot create a second resolution.",
            probability="0.5000",
            resolution_date=resolution_date,
        )
        stale_prediction = Prediction.objects.get(pk=prediction.pk)

        PredictionLedgerService.resolve(
            prediction=prediction,
            outcome_occurred=True,
            resolved_at=resolution_date + timedelta(minutes=1),
        )

        with self.assertRaisesMessage(ValidationError, "Prediction has already been resolved."):
            PredictionLedgerService.resolve(
                prediction=stale_prediction,
                outcome_occurred=False,
                resolved_at=resolution_date + timedelta(minutes=2),
            )

        self.assertEqual(Prediction.objects.get(pk=prediction.pk).resolution.outcome_occurred, True)

    def test_scoring_summary_uses_resolved_predictions_only(self):
        due = timezone.now() + timedelta(days=1)
        resolved = PredictionLedgerService.create(
            claim=self.claim,
            event_statement="Resolved event",
            probability="0.7500",
            resolution_date=due,
        )
        PredictionLedgerService.create(
            claim=self.claim,
            event_statement="Still open event",
            probability="0.6000",
            resolution_date=due,
        )
        PredictionLedgerService.resolve(
            prediction=resolved,
            outcome_occurred=True,
            resolved_at=due + timedelta(minutes=1),
        )

        summary = PredictionLedgerService.scoring_summary(claim=self.claim)
        self.assertEqual(summary["resolved_predictions"], 1)
        self.assertAlmostEqual(summary["mean_brier_score"], 0.0625)
        self.assertAlmostEqual(summary["mean_accuracy_score"], 0.9375)
