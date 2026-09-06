from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.core.models import (
    ContextualReputationEvent,
    QualitySignal,
    ScoringPolicy,
)
from apps.core.services.contextual_reputation import record_verification_activity
from apps.core.services.quality_signals import create_quality_signal
from apps.core.services.scoring import apply_scoring_policy
from apps.evidence.models import Claim
from apps.verification.models import (
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)
from marketplace.models import Product


User = get_user_model()


class ContextualScoringTests(TestCase):
    def setUp(self):
        self.verifier = User.objects.create_user(
            username="score-verifier",
            password="test-pass-123",
        )
        self.assessor = User.objects.create_user(
            username="score-assessor",
            password="test-pass-123",
        )
        self.product = Product.objects.create(
            seller=self.verifier,
            title="Scoring Product",
        )
        self.claim = Claim.objects.create(
            claim_text="The product satisfies the scored claim.",
            created_by=self.verifier,
        )
        self.method = VerificationMethod.objects.create(
            code="scoring-manual-review",
            name="Scoring manual review",
        )
        content_type = ContentType.objects.get_for_model(
            self.product,
            for_concrete_model=False,
        )
        self.request = VerificationRequest.objects.create(
            artifact_content_type=content_type,
            artifact_object_id=str(self.product.pk),
            claim=self.claim,
            method=self.method,
            requested_by=self.verifier,
            status=VerificationRequest.Status.COMPLETED,
        )
        self.result = VerificationResult.objects.create(
            request=self.request,
            verifier=self.verifier,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=90,
        )
        self.policy = ScoringPolicy.objects.create(
            domain="security",
            verification_method=self.method,
            version="v1.0",
            direction_weights={
                QualitySignal.Direction.SUPPORTS_RESULT: 1.0,
                QualitySignal.Direction.CONTRADICTS_RESULT: -1.0,
                QualitySignal.Direction.INCONCLUSIVE: 0.0,
            },
            base_weight=1.0,
        )

    def create_signal(self, *, source_ref, direction):
        return create_quality_signal(
            verification_result=self.result,
            signal_type=QualitySignal.SignalType.EXTERNAL_REFERENCE,
            direction=direction,
            source_ref=source_ref,
            domain="security",
            method=self.method,
            assessor=self.assessor,
            provenance_ref=f"report:{source_ref}",
            independence_declared=True,
            independence_basis="Independent assessor and validation path.",
        )

    def test_supporting_signal_scores_verifier_not_assessor(self):
        reputation, _, _ = record_verification_activity(
            verification_result=self.result,
            domain="security",
        )
        signal = self.create_signal(
            source_ref="lab:supports",
            direction=QualitySignal.Direction.SUPPORTS_RESULT,
        )

        outcome = apply_scoring_policy(signal=signal, policy=self.policy)

        self.assertTrue(outcome.applied)
        reputation.refresh_from_db()
        self.assertEqual(reputation.user, self.verifier)
        self.assertEqual(reputation.score, 1.0)
        self.assertEqual(reputation.sample_count, 1)
        self.assertFalse(
            self.assessor.contextual_reputations.filter(domain="security").exists()
        )

    def test_contradicting_signal_applies_negative_delta(self):
        signal = self.create_signal(
            source_ref="lab:contradicts",
            direction=QualitySignal.Direction.CONTRADICTS_RESULT,
        )
        outcome = apply_scoring_policy(signal=signal, policy=self.policy)
        self.assertTrue(outcome.applied)
        self.assertEqual(outcome.delta, -1.0)
        self.assertEqual(outcome.reputation.score, -1.0)

    def test_inconclusive_signal_does_not_create_score_event(self):
        signal = self.create_signal(
            source_ref="lab:inconclusive",
            direction=QualitySignal.Direction.INCONCLUSIVE,
        )
        outcome = apply_scoring_policy(signal=signal, policy=self.policy)
        self.assertFalse(outcome.applied)
        self.assertEqual(outcome.reason, "non_scoring_direction")
        self.assertFalse(
            ContextualReputationEvent.objects.filter(
                event_type=ContextualReputationEvent.EventType.SCORE_APPLIED
            ).exists()
        )

    def test_duplicate_processing_is_idempotent(self):
        signal = self.create_signal(
            source_ref="lab:idempotent",
            direction=QualitySignal.Direction.SUPPORTS_RESULT,
        )
        first = apply_scoring_policy(signal=signal, policy=self.policy)
        second = apply_scoring_policy(signal=signal, policy=self.policy)
        self.assertTrue(first.applied)
        self.assertFalse(second.applied)
        self.assertEqual(second.reason, "already_applied")
        first.reputation.refresh_from_db()
        self.assertEqual(first.reputation.score, 1.0)
        self.assertEqual(
            ContextualReputationEvent.objects.filter(
                event_type=ContextualReputationEvent.EventType.SCORE_APPLIED
            ).count(),
            1,
        )

    def test_wrong_domain_policy_is_rejected(self):
        signal = self.create_signal(
            source_ref="lab:wrong-domain",
            direction=QualitySignal.Direction.SUPPORTS_RESULT,
        )
        wrong_policy = ScoringPolicy.objects.create(
            domain="medicine",
            verification_method=self.method,
            version="v1.0",
            direction_weights={QualitySignal.Direction.SUPPORTS_RESULT: 1.0},
        )
        outcome = apply_scoring_policy(signal=signal, policy=wrong_policy)
        self.assertFalse(outcome.applied)
        self.assertEqual(outcome.reason, "policy_domain_mismatch")

    def test_policy_version_mismatch_requires_projection_rebuild(self):
        first_signal = self.create_signal(
            source_ref="lab:policy-v1",
            direction=QualitySignal.Direction.SUPPORTS_RESULT,
        )
        first = apply_scoring_policy(signal=first_signal, policy=self.policy)
        self.assertTrue(first.applied)

        second_signal = self.create_signal(
            source_ref="lab:policy-v2",
            direction=QualitySignal.Direction.SUPPORTS_RESULT,
        )
        policy_v2 = ScoringPolicy.objects.create(
            domain="security",
            verification_method=self.method,
            version="v2.0",
            direction_weights={QualitySignal.Direction.SUPPORTS_RESULT: 1.0},
        )
        second = apply_scoring_policy(signal=second_signal, policy=policy_v2)
        self.assertFalse(second.applied)
        self.assertEqual(second.reason, "projection_rebuild_required")
        first.reputation.refresh_from_db()
        self.assertEqual(first.reputation.score, 1.0)

    def test_ineligible_signal_cannot_score(self):
        signal = create_quality_signal(
            verification_result=self.result,
            signal_type=QualitySignal.SignalType.CONSENSUS,
            direction=QualitySignal.Direction.SUPPORTS_RESULT,
            source_ref="panel:consensus",
            domain="security",
            method=self.method,
            assessor=self.assessor,
            provenance_ref="panel:report",
            independence_declared=True,
            independence_basis="Declared independent participants.",
        )
        self.assertFalse(signal.is_eligible)
        outcome = apply_scoring_policy(signal=signal, policy=self.policy)
        self.assertFalse(outcome.applied)
        self.assertEqual(outcome.reason, "signal_not_eligible")

    def test_scoring_policy_is_immutable(self):
        self.policy.description = "changed"
        with self.assertRaises(RuntimeError):
            self.policy.save()
        with self.assertRaises(RuntimeError):
            self.policy.delete()
