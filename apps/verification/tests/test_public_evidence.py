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
from library.models import LibraryItem
from marketplace.models import Product


User = get_user_model()


class PublicEvidenceProjectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="public-evidence-staff",
            password="test-pass-123",
            is_staff=True,
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Public Evidence Product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.other_product = Product.objects.create(
            seller=self.user,
            title="Other Product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.library_item = LibraryItem.objects.create(
            title="Public Evidence Library Item",
            slug="public-evidence-library-item",
            is_published=True,
        )
        self.method = VerificationMethod.objects.create(
            code="public-evidence",
            name="Public evidence method",
        )
        self._digest_counter = 0

    def _create_result(self, artifact, claim_text, *, status=VerificationRequest.Status.COMPLETED):
        claim = Claim.objects.create(
            claim_text=claim_text,
            created_by=self.user,
        )
        content_type = ContentType.objects.get_for_model(
            artifact,
            for_concrete_model=False,
        )
        request = VerificationRequest.objects.create(
            artifact_content_type=content_type,
            artifact_object_id=str(artifact.pk),
            claim=claim,
            method=self.method,
            requested_by=self.user,
            status=status,
        )
        result = VerificationResult.objects.create(
            request=request,
            verifier=self.user,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=80,
        )
        return claim, result

    def _link_evidence(
        self,
        claim,
        result,
        *,
        visibility=VerificationEvidence.Visibility.PUBLIC,
        relation_type=EvidenceRelation.RelationType.SUPPORTS,
        content="evidence content",
    ):
        self._digest_counter += 1
        digest = f"{self._digest_counter:064x}"[-64:]
        evidence = Evidence.objects.create(
            content=content,
            content_type=Evidence.ContentType.TEXT,
            integrity_digest=digest,
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

    def _get_projection(self, artifact_id=None, artifact_type="product"):
        return self.client.get(
            reverse("verification:public_evidence"),
            {
                "artifact_id": artifact_id if artifact_id is not None else self.product.pk,
                "artifact_type": artifact_type,
            },
        )

    def test_only_public_evidence_is_exposed_without_raw_content(self):
        claim, result = self._create_result(self.product, "Privacy claim")
        public_evidence, public_relation, _ = self._link_evidence(
            claim,
            result,
            visibility=VerificationEvidence.Visibility.PUBLIC,
            relation_type=EvidenceRelation.RelationType.SUPPORTS,
            content="PUBLIC RAW CONTENT",
        )
        self._link_evidence(
            claim,
            result,
            visibility=VerificationEvidence.Visibility.PRIVATE,
            content="PRIVATE RAW CONTENT",
        )
        self._link_evidence(
            claim,
            result,
            visibility=VerificationEvidence.Visibility.PARTICIPANTS,
            content="PARTICIPANTS RAW CONTENT",
        )

        response = self._get_projection()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_public_evidence_count"], 1)
        self.assertEqual(len(payload["claims"]), 1)
        self.assertEqual(
            payload["claims"][0]["evidences"][0]["evidence_id"],
            str(public_evidence.pk),
        )
        self.assertEqual(
            payload["claims"][0]["evidences"][0]["relation"],
            public_relation.relation,
        )
        body = response.content.decode()
        self.assertNotIn("PUBLIC RAW CONTENT", body)
        self.assertNotIn("PRIVATE RAW CONTENT", body)
        self.assertNotIn("PARTICIPANTS RAW CONTENT", body)
        self.assertNotIn("claim_text", body)

    def test_public_link_for_another_artifact_is_not_exposed(self):
        claim, result = self._create_result(self.product, "Target claim")
        target_evidence, _, _ = self._link_evidence(claim, result, content="target")
        other_claim, other_result = self._create_result(self.other_product, "Other claim")
        self._link_evidence(other_claim, other_result, content="other")

        response = self._get_projection()

        payload = response.json()
        self.assertEqual(payload["total_public_evidence_count"], 1)
        self.assertEqual(
            payload["claims"][0]["evidences"][0]["evidence_id"],
            str(target_evidence.pk),
        )

    def test_groups_public_evidence_by_claim(self):
        first_claim, first_result = self._create_result(self.product, "First claim")
        second_claim, second_result = self._create_result(self.product, "Second claim")
        self._link_evidence(
            first_claim,
            first_result,
            relation_type=EvidenceRelation.RelationType.SUPPORTS,
        )
        self._link_evidence(
            first_claim,
            first_result,
            relation_type=EvidenceRelation.RelationType.CONTEXTUALIZES,
        )
        self._link_evidence(
            second_claim,
            second_result,
            relation_type=EvidenceRelation.RelationType.CONTRADICTS,
        )

        response = self._get_projection()

        payload = response.json()
        self.assertEqual(payload["total_public_evidence_count"], 3)
        self.assertEqual(len(payload["claims"]), 2)
        grouped = {row["claim_id"]: row["evidences"] for row in payload["claims"]}
        self.assertEqual(len(grouped[str(first_claim.pk)]), 2)
        self.assertEqual(len(grouped[str(second_claim.pk)]), 1)

    def test_empty_state_for_public_artifact_without_public_evidence(self):
        response = self._get_projection()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "artifact_id": str(self.product.pk),
                "artifact_type": "product",
                "claims": [],
                "total_public_evidence_count": 0,
            },
        )

    def test_public_evidence_from_incomplete_request_is_not_exposed(self):
        claim, result = self._create_result(
            self.product,
            "Incomplete claim",
            status=VerificationRequest.Status.IN_PROGRESS,
        )
        self._link_evidence(claim, result)

        response = self._get_projection()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_public_evidence_count"], 0)

    def test_library_item_projection_uses_explicit_artifact_mapping(self):
        claim, result = self._create_result(self.library_item, "Library claim")
        evidence, relation, _ = self._link_evidence(
            claim,
            result,
            relation_type=EvidenceRelation.RelationType.UNCLEAR,
        )

        response = self._get_projection(
            artifact_id=self.library_item.pk,
            artifact_type="libraryitem",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["artifact_type"], "libraryitem")
        self.assertEqual(payload["total_public_evidence_count"], 1)
        projected = payload["claims"][0]["evidences"][0]
        self.assertEqual(projected["evidence_id"], str(evidence.pk))
        self.assertEqual(projected["relation"], relation.relation)

    def test_invalid_artifact_type_returns_400(self):
        response = self._get_projection(artifact_type="audio")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_artifact_type")

    def test_missing_required_parameter_returns_400(self):
        response = self.client.get(
            reverse("verification:public_evidence"),
            {"artifact_type": "product"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_request")

    def test_missing_or_non_public_artifact_returns_404(self):
        response = self._get_projection(artifact_id="999999999")
        self.assertEqual(response.status_code, 404)

        self.product.is_published = False
        self.product.save()
        response = self._get_projection()
        self.assertEqual(response.status_code, 404)
