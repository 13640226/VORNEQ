from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Reputation, ReputationHistory
from apps.core.services import ReputationService
from apps.evidence.models import Claim
from apps.evidence.services import EvidenceService, PredictionLedgerService


class ReputationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="forecaster",
            email="forecaster@example.com",
            password="test-pass-123",
        )
        self.claim = Claim.objects.create(
            claim_text="Pilot revenue will exceed the target by year end",
            scope="pilot",
            created_by=self.user,
        )

    def test_source_quality_updates_from_provenance_creation(self):
        EvidenceService.create_with_provenance(
            content="Audited pilot revenue report",
            source_ref="https://example.com/audit",
            created_by=self.user,
        )

        reputation = self.user.reputation
        self.assertEqual(reputation.source_quality_score, 1.0)
        self.assertTrue(
            ReputationHistory.objects.filter(
                user=self.user,
                dimension=ReputationHistory.Dimension.SOURCE_QUALITY,
                event_type="ProvenanceStep",
            ).exists()
        )

    def test_prediction_resolution_updates_mean_prediction_accuracy(self):
        due = timezone.now() + timedelta(days=1)
        prediction = PredictionLedgerService.create(
            claim=self.claim,
            event_statement="Pilot revenue target is exceeded",
            probability=0.8,
            resolution_date=due,
            created_by=self.user,
        )
        PredictionLedgerService.resolve(
            prediction=prediction,
            outcome_occurred=True,
            resolved_at=due + timedelta(days=1),
            resolved_by=self.user,
        )

        reputation = self.user.reputation
        self.assertAlmostEqual(reputation.prediction_accuracy_score, 0.96)
        self.assertTrue(
            ReputationHistory.objects.filter(
                user=self.user,
                dimension=ReputationHistory.Dimension.PREDICTION_ACCURACY,
                event_type="PredictionResolution",
            ).exists()
        )

    def test_unscored_dimensions_are_not_inferred_from_activity(self):
        EvidenceService.create_with_provenance(
            content="Technical report",
            source_ref="https://example.com/report",
            created_by=self.user,
        )
        reputation = ReputationService.recalculate_all(self.user)

        self.assertEqual(reputation.accuracy_score, 0.0)
        self.assertEqual(reputation.corrigibility_score, 0.0)
        self.assertEqual(reputation.fair_critique_score, 0.0)
        self.assertEqual(reputation.domain_expertise_score, 0.0)
        self.assertEqual(reputation.social_behavior_score, 0.0)

    def test_history_is_append_only(self):
        EvidenceService.create_with_provenance(
            content="Source-backed evidence",
            source_ref="https://example.com/source",
            created_by=self.user,
        )
        history = ReputationHistory.objects.filter(user=self.user).first()
        history.new_value = 0.2
        with self.assertRaises(RuntimeError):
            history.save()
        with self.assertRaises(RuntimeError):
            history.delete()

    def test_authenticated_reputation_endpoint_is_read_only(self):
        EvidenceService.create_with_provenance(
            content="Source-backed evidence",
            source_ref="https://example.com/source",
            created_by=self.user,
        )
        history_count = ReputationHistory.objects.filter(user=self.user).count()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("core:reputation-detail", kwargs={"user_id": self.user.pk})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user_id"], self.user.pk)
        self.assertEqual(payload["scores"]["source_quality"], 1.0)
        self.assertIn("methodology", payload)
        self.assertEqual(
            ReputationHistory.objects.filter(user=self.user).count(),
            history_count,
        )

    def test_reputation_endpoint_without_cache_row_does_not_write(self):
        self.assertFalse(Reputation.objects.filter(user=self.user).exists())
        reputation_count = Reputation.objects.count()
        history_count = ReputationHistory.objects.count()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("core:reputation-detail", kwargs={"user_id": self.user.pk})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["persisted"])
        self.assertIsNone(payload["last_updated"])
        self.assertEqual(Reputation.objects.count(), reputation_count)
        self.assertEqual(ReputationHistory.objects.count(), history_count)

    def test_demo_dashboard_without_cache_row_does_not_write_reputation(self):
        self.assertFalse(Reputation.objects.filter(user=self.user).exists())
        reputation_count = Reputation.objects.count()
        history_count = ReputationHistory.objects.count()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("graph:demo-dashboard", kwargs={"claim_id": self.claim.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reputation.objects.count(), reputation_count)
        self.assertEqual(ReputationHistory.objects.count(), history_count)
