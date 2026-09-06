from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    ContextualReputation,
    ContextualReputationEvent,
    QualitySignal,
    ScoringPolicy,
)
from apps.evidence.models import Claim
from apps.verification.models import VerificationMethod, VerificationRequest, VerificationResult
from marketplace.models import Product


User = get_user_model()


class PublicReputationTests(TestCase):
    def setUp(self):
        self.verifier = User.objects.create_user(username="public-verifier", password="x")
        self.assessor = User.objects.create_user(username="private-assessor", password="x")
        self.product = Product.objects.create(seller=self.verifier, title="Public reputation product")
        self.claim = Claim.objects.create(claim_text="Scoped claim", created_by=self.verifier)
        self.method = VerificationMethod.objects.create(code="public-manual", name="Public manual")
        content_type = ContentType.objects.get_for_model(self.product, for_concrete_model=False)
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
            reported_confidence=80,
        )
        self.reputation = ContextualReputation.objects.create(
            user=self.verifier,
            domain="security",
            verification_method=self.method,
            score=2.0,
            sample_count=7,
            last_event_at=timezone.now(),
        )
        self.policy = ScoringPolicy.objects.create(
            domain="security",
            verification_method=self.method,
            version="score-v1",
            direction_weights={"supports_result": 1.0},
        )
        self.signal = QualitySignal.objects.create(
            verification_result=self.result,
            signal_type=QualitySignal.SignalType.EXTERNAL_REFERENCE,
            direction=QualitySignal.Direction.SUPPORTS_RESULT,
            assessor=self.assessor,
            source_ref="private-source-reference",
            provenance_ref="private-provenance-reference",
            independence_declared=True,
            independence_basis="Independent organization",
            domain="security",
            method=self.method,
            is_eligible=True,
        )
        ContextualReputationEvent.objects.create(
            contextual_reputation=self.reputation,
            verification_result=self.result,
            quality_signal=self.signal,
            scoring_policy=self.policy,
            event_type=ContextualReputationEvent.EventType.SCORE_APPLIED,
            old_score=1.0,
            delta=1.0,
            new_score=2.0,
        )

    def test_public_api_returns_context_not_private_audit_data(self):
        response = self.client.get(
            reverse("core:public-reputation-list", args=[self.verifier.pk])
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        item = body["reputations"][0]
        self.assertEqual(item["domain"], "security")
        self.assertEqual(item["verification_method"]["code"], "public-manual")
        self.assertEqual(item["policy_version"], "score-v1")
        self.assertEqual(item["sample_strength"], "medium")
        raw = response.content.decode()
        for private_value in (
            "private-assessor",
            "private-source-reference",
            "private-provenance-reference",
            "old_score",
            "delta",
            "quality_signal",
        ):
            self.assertNotIn(private_value, raw)

    def test_context_endpoint_filters_domain_and_method(self):
        response = self.client.get(
            reverse(
                "core:public-reputation-context",
                args=[self.verifier.pk, "security", "public-manual"],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reputation"]["score"], 2.0)

    def test_missing_context_returns_404(self):
        response = self.client.get(
            reverse(
                "core:public-reputation-context",
                args=[self.verifier.pk, "medicine", "public-manual"],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_sample_strength_is_descriptive_only(self):
        response = self.client.get(
            reverse("core:public-reputation-list", args=[self.verifier.pk])
        )
        item = response.json()["reputations"][0]
        self.assertEqual(item["sample_strength"], "medium")
        self.assertIn("not a confidence score or truth claim", item["interpretation_note"])
