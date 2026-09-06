from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.evidence.models import Claim, Evidence, EvidenceRelation
from apps.verification.models import (
    VerificationEvidence,
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)
from marketplace.models import Product


User = get_user_model()


class VerificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="verifier",
            email="verifier@example.com",
            password="test-pass-123",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Verification Test Product",
        )
        self.claim = Claim.objects.create(
            claim_text="The artifact satisfies the requested check.",
            created_by=self.user,
        )
        self.method = VerificationMethod.objects.create(
            code="manual-review",
            name="Manual review",
        )

    def make_request(self, *, claim=None):
        content_type = ContentType.objects.get_for_model(
            self.product,
            for_concrete_model=False,
        )
        return VerificationRequest.objects.create(
            artifact_content_type=content_type,
            artifact_object_id=str(self.product.pk),
            claim=claim or self.claim,
            method=self.method,
            requested_by=self.user,
        )

    def test_product_is_allowed_artifact(self):
        request = self.make_request()
        request.full_clean()
        self.assertEqual(request.artifact, self.product)

    def test_unsupported_artifact_type_is_rejected(self):
        user_content_type = ContentType.objects.get_for_model(
            User,
            for_concrete_model=False,
        )
        request = VerificationRequest(
            artifact_content_type=user_content_type,
            artifact_object_id=str(self.user.pk),
            claim=self.claim,
            method=self.method,
            requested_by=self.user,
        )

        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_missing_artifact_is_rejected(self):
        content_type = ContentType.objects.get_for_model(
            self.product,
            for_concrete_model=False,
        )
        request = VerificationRequest(
            artifact_content_type=content_type,
            artifact_object_id="999999",
            claim=self.claim,
            method=self.method,
            requested_by=self.user,
        )

        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_reported_confidence_is_bounded(self):
        request = self.make_request()
        result = VerificationResult(
            request=request,
            verifier=self.user,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=101,
        )

        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_evidence_relation_must_match_request_claim(self):
        request = self.make_request()
        result = VerificationResult.objects.create(
            request=request,
            verifier=self.user,
            outcome=VerificationResult.Outcome.PARTIAL,
            reported_confidence=70,
        )
        other_claim = Claim.objects.create(
            claim_text="A different claim.",
            created_by=self.user,
        )
        evidence = Evidence.objects.create(
            content="Supporting material",
            content_type=Evidence.ContentType.TEXT,
            integrity_digest="0" * 64,
            created_by=self.user,
        )
        relation = EvidenceRelation.objects.create(
            claim=other_claim,
            evidence=evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            created_by=self.user,
        )
        link = VerificationEvidence(
            result=result,
            evidence_relation=relation,
            visibility=VerificationEvidence.Visibility.PRIVATE,
        )

        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_user_deletion_preserves_verification_history(self):
        request = self.make_request()
        result = VerificationResult.objects.create(
            request=request,
            verifier=self.user,
            outcome=VerificationResult.Outcome.INCONCLUSIVE,
            reported_confidence=25,
        )

        self.user.delete()
        request.refresh_from_db()
        result.refresh_from_db()

        self.assertIsNone(request.requested_by)
        self.assertIsNone(result.verifier)
