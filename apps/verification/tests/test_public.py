from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Artifact, ArtifactBinding
from apps.core.services.registry import register_artifact
from apps.evidence.models import Claim, Evidence, EvidenceRelation
from apps.verification.models import (
    VerificationEvidence,
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)
from apps.verification.public import get_public_verification_summary
from apps.verification.services.target_identity import CanonicalTargetConflict
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

    def test_summary_legacy_bound_is_read_only(self):
        canonical, _ = register_artifact(self.product, created_by=self.user)
        before = (Artifact.objects.count(), ArtifactBinding.objects.count())

        summary = get_public_verification_summary(self.product)

        self.request.refresh_from_db()
        self.assertEqual(summary["total_verifications"], 1)
        self.assertEqual((Artifact.objects.count(), ArtifactBinding.objects.count()), before)
        self.assertIsNone(self.request.canonical_artifact_id)
        self.assertTrue(Artifact.objects.filter(pk=canonical.pk).exists())

    def test_summary_matching_persisted_canonical_is_valid(self):
        canonical, _ = register_artifact(self.product, created_by=self.user)
        self.request.canonical_artifact = canonical
        self.request.save(update_fields=["canonical_artifact"])

        summary = get_public_verification_summary(self.product)

        self.request.refresh_from_db()
        self.assertEqual(summary["total_verifications"], 1)
        self.assertEqual(self.request.canonical_artifact_id, canonical.pk)

    def test_summary_persisted_canonical_without_binding_fails_closed(self):
        canonical = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        self.request.canonical_artifact = canonical
        self.request.save(update_fields=["canonical_artifact"])
        before = (Artifact.objects.count(), ArtifactBinding.objects.count())

        with self.assertRaises(CanonicalTargetConflict):
            get_public_verification_summary(self.product)

        self.request.refresh_from_db()
        self.assertEqual((Artifact.objects.count(), ArtifactBinding.objects.count()), before)
        self.assertEqual(self.request.canonical_artifact_id, canonical.pk)

    def test_summary_non_latest_conflicting_request_fails_closed(self):
        bound, _ = register_artifact(self.product, created_by=self.user)
        conflicting = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        self.request.canonical_artifact = conflicting
        self.request.save(update_fields=["canonical_artifact"])

        newer_request = VerificationRequest.objects.create(
            artifact_content_type=self.request.artifact_content_type,
            artifact_object_id=str(self.product.pk),
            canonical_artifact=bound,
            claim=self.claim,
            method=self.method,
            requested_by=self.user,
            status=VerificationRequest.Status.COMPLETED,
        )
        VerificationResult.objects.create(
            request=newer_request,
            verifier=self.user,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=100,
        )

        with self.assertRaises(CanonicalTargetConflict):
            get_public_verification_summary(self.product)

    def test_summary_persisted_canonical_mismatch_fails_closed(self):
        bound, _ = register_artifact(self.product, created_by=self.user)
        conflicting = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        self.request.canonical_artifact = conflicting
        self.request.save(update_fields=["canonical_artifact"])
        before = (Artifact.objects.count(), ArtifactBinding.objects.count())

        with self.assertRaises(CanonicalTargetConflict):
            get_public_verification_summary(self.product)

        self.request.refresh_from_db()
        self.assertNotEqual(bound.pk, conflicting.pk)
        self.assertEqual((Artifact.objects.count(), ArtifactBinding.objects.count()), before)
        self.assertEqual(self.request.canonical_artifact_id, conflicting.pk)

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
