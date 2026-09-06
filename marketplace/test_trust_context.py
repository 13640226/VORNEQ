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
from marketplace.models import Product
from marketplace.services import build_public_trust_context


User = get_user_model()


class MarketplaceTrustContextTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username="trust-seller", password="x")
        self.verifier = User.objects.create_user(username="trust-verifier", password="x")
        self.product = Product.objects.create(
            seller=self.seller,
            title="Trust Context Product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.claim = Claim.objects.create(
            claim_text="Trust context claim",
            created_by=self.seller,
        )
        self.method = VerificationMethod.objects.create(
            code="trust-context-manual",
            name="Manual review",
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
            requested_by=self.seller,
            status=VerificationRequest.Status.COMPLETED,
        )
        self.result = VerificationResult.objects.create(
            request=self.request,
            verifier=self.verifier,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=80,
        )

    def _add_public_evidence(self):
        evidence = Evidence.objects.create(
            content="public discovery evidence",
            content_type=Evidence.ContentType.TEXT,
            integrity_digest="c" * 64,
            created_by=self.seller,
        )
        relation = EvidenceRelation.objects.create(
            claim=self.claim,
            evidence=evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            created_by=self.seller,
        )
        VerificationEvidence.objects.create(
            result=self.result,
            evidence_relation=relation,
            visibility=VerificationEvidence.Visibility.PUBLIC,
        )

    def test_builder_returns_descriptive_public_metadata_only(self):
        self._add_public_evidence()

        context = build_public_trust_context(self.product)

        self.assertTrue(context["has_verification"])
        self.assertEqual(context["verification_count"], 1)
        self.assertEqual(context["verification_methods"], ["Manual review"])
        self.assertEqual(context["public_evidence_count"], 1)
        self.assertIsNotNone(context["last_verified_at"])
        self.assertNotIn("score", context)
        self.assertNotIn("reputation_context", context)
        self.assertNotIn("verifier", context)

    def test_marketplace_card_renders_context_without_private_details(self):
        private_evidence = Evidence.objects.create(
            content="PRIVATE DISCOVERY SECRET",
            content_type=Evidence.ContentType.TEXT,
            integrity_digest="d" * 64,
            created_by=self.seller,
        )
        relation = EvidenceRelation.objects.create(
            claim=self.claim,
            evidence=private_evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            created_by=self.seller,
        )
        VerificationEvidence.objects.create(
            result=self.result,
            evidence_relation=relation,
            visibility=VerificationEvidence.Visibility.PRIVATE,
        )

        response = self.client.get(reverse("marketplace:index"))
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("1 completed verification", body)
        self.assertIn("Manual review", body)
        self.assertIn("not a trust score or truth claim", body)
        self.assertNotIn("PRIVATE DISCOVERY SECRET", body)
        self.assertNotIn(self.verifier.username, body)
