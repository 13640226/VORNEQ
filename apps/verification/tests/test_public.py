from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from apps.evidence.models import Claim, Evidence, EvidenceRelation
from apps.verification.models import (
    VerificationEvidence,
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)
from apps.verification.public import get_public_verification_summary
from marketplace.models import Product


User = get_user_model()


class PublicVerificationSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="summary-staff",
            password="test-pass-123",
            is_staff=True,
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Public Summary Product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.claim = Claim.objects.create(
            claim_text="Public summary claim",
            created_by=self.user,
        )
        self.method = VerificationMethod.objects.create(
            code="public-summary",
            name="Public summary method",
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
            requested_by=self.user,
            status=VerificationRequest.Status.COMPLETED,
        )
        self.result = VerificationResult.objects.create(
            request=self.request,
            verifier=self.user,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=80,
            summary="Public result summary",
        )

    def make_evidence_link(self, visibility, content):
        evidence = Evidence.objects.create(
            content=content,
            content_type=Evidence.ContentType.TEXT,
            integrity_digest=("a" if visibility == "public" else "b") * 64,
            created_by=self.user,
        )
        relation = EvidenceRelation.objects.create(
            claim=self.claim,
            evidence=evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            created_by=self.user,
        )
        VerificationEvidence.objects.create(
            result=self.result,
            evidence_relation=relation,
            visibility=visibility,
        )
        return evidence

    def test_summary_is_descriptive_and_counts_public_links_only(self):
        self.make_evidence_link(VerificationEvidence.Visibility.PUBLIC, "public evidence")
        self.make_evidence_link(VerificationEvidence.Visibility.PRIVATE, "secret evidence")

        summary = get_public_verification_summary(self.product)

        self.assertEqual(summary["total_verifications"], 1)
        self.assertEqual(summary["outcomes"]["pass"], 1)
        self.assertEqual(summary["average_reported_confidence"], 80.0)
        self.assertEqual(summary["public_evidence_count"], 1)

    def test_api_does_not_expose_evidence_content_or_verifier_identity(self):
        self.make_evidence_link(VerificationEvidence.Visibility.PRIVATE, "TOP SECRET EVIDENCE")

        response = self.client.get(
            reverse("verification:product_summary", args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertNotIn("TOP SECRET EVIDENCE", body)
        self.assertNotIn(self.user.username, body)
        self.assertNotIn("trust_score", body)

    def test_non_public_product_summary_is_not_exposed(self):
        self.product.is_published = False
        self.product.save()

        response = self.client.get(
            reverse("verification:product_summary", args=[self.product.pk])
        )
        self.assertEqual(response.status_code, 404)
