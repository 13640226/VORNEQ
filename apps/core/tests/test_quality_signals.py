from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.core.models import QualitySignal
from apps.core.services.quality_signals import create_quality_signal
from apps.evidence.models import Claim
from apps.verification.models import (
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)
from marketplace.models import Product


User = get_user_model()


class QualitySignalTests(TestCase):
    def setUp(self):
        self.verifier = User.objects.create_user(
            username="quality-verifier",
            password="test-pass-123",
        )
        self.assessor = User.objects.create_user(
            username="quality-assessor",
            password="test-pass-123",
        )
        self.product = Product.objects.create(
            seller=self.verifier,
            title="Quality Signal Product",
        )
        self.claim = Claim.objects.create(
            claim_text="The product satisfies the scoped claim.",
            created_by=self.verifier,
        )
        self.method = VerificationMethod.objects.create(
            code="quality-manual-review",
            name="Quality manual review",
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

    def create_signal(self, **overrides):
        values = {
            "verification_result": self.result,
            "signal_type": QualitySignal.SignalType.EXTERNAL_REFERENCE,
            "source_ref": "external-lab:42",
            "domain": "security",
            "method": self.method,
            "assessor": self.assessor,
            "provenance_ref": "report:validation-42",
            "independence_declared": True,
            "independence_basis": "Separate organization and validation pipeline.",
        }
        values.update(overrides)
        return create_quality_signal(**values)

    def test_strong_independent_signal_is_eligible(self):
        signal = self.create_signal()
        self.assertTrue(signal.is_eligible)
        self.assertEqual(signal.eligibility_reasons, [])

    def test_consensus_is_recorded_but_not_eligible_in_v1(self):
        signal = self.create_signal(
            signal_type=QualitySignal.SignalType.CONSENSUS,
            source_ref="consensus-panel:1",
        )
        self.assertFalse(signal.is_eligible)
        self.assertIn("signal_type_not_eligible_in_v1", signal.eligibility_reasons)

    def test_self_assessment_is_not_eligible(self):
        signal = self.create_signal(
            assessor=self.verifier,
            source_ref="self-assessment:1",
        )
        self.assertFalse(signal.is_eligible)
        self.assertIn("self_assessment_not_allowed", signal.eligibility_reasons)

    def test_missing_independence_basis_is_not_eligible(self):
        signal = self.create_signal(
            source_ref="external-lab:missing-basis",
            independence_basis="",
        )
        self.assertFalse(signal.is_eligible)
        self.assertIn("missing_independence_basis", signal.eligibility_reasons)

    def test_incomplete_verification_is_not_eligible(self):
        self.request.status = VerificationRequest.Status.IN_PROGRESS
        self.request.save(update_fields=["status", "updated_at"])
        signal = self.create_signal(source_ref="external-lab:incomplete")
        self.assertFalse(signal.is_eligible)
        self.assertIn("verification_result_not_completed", signal.eligibility_reasons)

    def test_method_mismatch_is_not_eligible(self):
        other_method = VerificationMethod.objects.create(
            code="quality-automated-review",
            name="Quality automated review",
        )
        signal = self.create_signal(
            source_ref="external-lab:method-mismatch",
            method=other_method,
        )
        self.assertFalse(signal.is_eligible)
        self.assertIn("verification_method_mismatch", signal.eligibility_reasons)

    def test_signal_is_append_only(self):
        signal = self.create_signal(source_ref="external-lab:immutable")
        signal.metadata = {"changed": True}
        with self.assertRaises(RuntimeError):
            signal.save()
        with self.assertRaises(RuntimeError):
            signal.delete()
