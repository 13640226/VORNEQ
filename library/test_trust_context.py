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
from library.services import build_public_trust_context_for_library


User = get_user_model()


class LibraryTrustContextTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="library-owner", password="x")
        self.verifier = User.objects.create_user(username="library-verifier", password="x")
        self.item = LibraryItem.objects.create(
            title="Trust Context Library Item",
            slug="trust-context-library-item",
            author="Library Author",
            item_type="book",
            is_published=True,
        )
        self.claim = Claim.objects.create(
            claim_text="Library trust context claim",
            created_by=self.owner,
        )
        self.method = VerificationMethod.objects.create(
            code="library-trust-manual",
            name="Manual review",
        )
        content_type = ContentType.objects.get_for_model(
            self.item,
            for_concrete_model=False,
        )
        self.request = VerificationRequest.objects.create(
            artifact_content_type=content_type,
            artifact_object_id=str(self.item.pk),
            claim=self.claim,
            method=self.method,
            requested_by=self.owner,
            status=VerificationRequest.Status.COMPLETED,
        )
        self.result = VerificationResult.objects.create(
            request=self.request,
            verifier=self.verifier,
            outcome=VerificationResult.Outcome.PASS,
            reported_confidence=80,
        )

    def _add_evidence(self, visibility, content):
        evidence = Evidence.objects.create(
            content=content,
            content_type=Evidence.ContentType.TEXT,
            integrity_digest=("a" if visibility == VerificationEvidence.Visibility.PUBLIC else "b") * 64,
            created_by=self.owner,
        )
        relation = EvidenceRelation.objects.create(
            claim=self.claim,
            evidence=evidence,
            relation=EvidenceRelation.RelationType.SUPPORTS,
            created_by=self.owner,
        )
        VerificationEvidence.objects.create(
            result=self.result,
            evidence_relation=relation,
            visibility=visibility,
        )

    def test_builder_returns_descriptive_public_metadata_only(self):
        self._add_evidence(
            VerificationEvidence.Visibility.PUBLIC,
            "public library evidence",
        )

        context = build_public_trust_context_for_library(self.item)

        self.assertTrue(context["has_verification"])
        self.assertEqual(context["verification_count"], 1)
        self.assertEqual(context["verification_methods"], ["Manual review"])
        self.assertEqual(context["public_evidence_count"], 1)
        self.assertIsNotNone(context["last_verified_at"])
        self.assertNotIn("score", context)
        self.assertNotIn("reputation_context", context)
        self.assertNotIn("verifier", context)

    def test_library_card_renders_context_without_private_details(self):
        self._add_evidence(
            VerificationEvidence.Visibility.PRIVATE,
            "PRIVATE LIBRARY DISCOVERY SECRET",
        )

        response = self.client.get(reverse("library:index"))
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("1 completed verification", body)
        self.assertIn("Manual review", body)
        self.assertIn("not a trust score or truth claim", body)
        self.assertNotIn("PRIVATE LIBRARY DISCOVERY SECRET", body)
        self.assertNotIn(self.verifier.username, body)
