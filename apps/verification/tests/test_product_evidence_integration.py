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
from apps.verification.public import get_public_evidence_projection
from marketplace.models import Product


User = get_user_model()


class ProductDetailEvidenceIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="product-evidence-seller",
            password="test-pass-123",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Evidence Disclosure Product",
            slug="evidence-disclosure-product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.method = VerificationMethod.objects.create(
            code="product-evidence-ui",
            name="Product evidence UI method",
        )
        self._digest_counter = 0

    def _create_result(self, claim_text):
        claim = Claim.objects.create(
            claim_text=claim_text,
            created_by=self.user,
        )
        content_type = ContentType.objects.get_for_model(
            self.product,
            for_concrete_model=False,
        )
        request = VerificationRequest.objects.create(
            artifact_content_type=content_type,
            artifact_object_id=str(self.product.pk),
            claim=claim,
            method=self.method,
            requested_by=self.user,
            status=VerificationRequest.Status.COMPLETED,
        )
        result = VerificationResult.objects.create(
            request=request,
            verifier=self.user,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=75,
        )
        return claim, result

    def _link_evidence(
        self,
        claim,
        result,
        *,
        visibility=VerificationEvidence.Visibility.PUBLIC,
        relation_type=EvidenceRelation.RelationType.SUPPORTS,
        content="raw evidence content",
    ):
        self._digest_counter += 1
        evidence = Evidence.objects.create(
            content=content,
            content_type=Evidence.ContentType.TEXT,
            integrity_digest=f"{self._digest_counter:064x}"[-64:],
            created_by=self.user,
        )
        relation = EvidenceRelation.objects.create(
            claim=claim,
            evidence=evidence,
            relation=relation_type,
            created_by=self.user,
        )
        link = VerificationEvidence.objects.create(
            result=result,
            evidence_relation=relation,
            visibility=visibility,
        )
        return evidence, relation, link

    def _get_detail(self):
        return self.client.get(
            reverse("marketplace:detail", args=[self.product.slug])
        )

    def test_reusable_projection_groups_public_evidence_by_claim(self):
        first_claim, first_result = self._create_result("First UI claim")
        second_claim, second_result = self._create_result("Second UI claim")
        self._link_evidence(first_claim, first_result)
        self._link_evidence(
            second_claim,
            second_result,
            relation_type=EvidenceRelation.RelationType.CONTEXTUALIZES,
        )

        projection = get_public_evidence_projection(self.product, "product")

        self.assertEqual(projection["total_public_evidence_count"], 2)
        self.assertEqual(len(projection["claims"]), 2)
        self.assertEqual(
            {row["claim_id"] for row in projection["claims"]},
            {str(first_claim.pk), str(second_claim.pk)},
        )

    def test_product_detail_displays_public_evidence(self):
        claim, result = self._create_result("Visible UI claim")
        evidence, relation, _ = self._link_evidence(
            claim,
            result,
            relation_type=EvidenceRelation.RelationType.CONTRADICTS,
            content="PUBLIC RAW CONTENT MUST NOT LEAK",
        )

        response = self._get_detail()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public Evidence")
        self.assertContains(response, str(claim.pk))
        self.assertContains(response, str(evidence.pk))
        self.assertContains(response, relation.get_relation_display())
        self.assertNotContains(response, "PUBLIC RAW CONTENT MUST NOT LEAK")
        self.assertNotContains(response, "Visible UI claim")

    def test_product_detail_does_not_display_private_evidence(self):
        claim, result = self._create_result("Private UI claim")
        private_evidence, _, _ = self._link_evidence(
            claim,
            result,
            visibility=VerificationEvidence.Visibility.PRIVATE,
            content="PRIVATE UI CONTENT",
        )

        response = self._get_detail()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No public evidence available")
        self.assertNotContains(response, str(private_evidence.pk))
        self.assertNotContains(response, "PRIVATE UI CONTENT")

    def test_product_detail_empty_state_is_neutral(self):
        response = self._get_detail()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public Evidence")
        self.assertContains(response, "No public evidence available")
