from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.evidence.models import Claim
from apps.verification.models import VerificationMethod, VerificationRequest, VerificationResult
from apps.verification.public import get_public_verification_summary
from marketplace.models import Product


User = get_user_model()


class LatestVerificationBadgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="latest-verification-staff",
            password="test-pass-123",
            is_staff=True,
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Latest Verification Product",
            slug="latest-verification-product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.content_type = ContentType.objects.get_for_model(
            self.product,
            for_concrete_model=False,
        )
        self.method = VerificationMethod.objects.create(
            code="latest-method",
            name="Latest verification method",
        )
        self._claim_counter = 0

    def _create_result(
        self,
        *,
        status=VerificationRequest.Status.COMPLETED,
        outcome=VerificationResult.Outcome.PASS,
        confidence=80,
        summary="",
    ):
        self._claim_counter += 1
        claim = Claim.objects.create(
            claim_text=f"Sensitive claim {self._claim_counter}",
            created_by=self.user,
        )
        verification_request = VerificationRequest.objects.create(
            artifact_content_type=self.content_type,
            artifact_object_id=str(self.product.pk),
            claim=claim,
            method=self.method,
            requested_by=self.user,
            status=status,
        )
        result = VerificationResult.objects.create(
            request=verification_request,
            verifier=self.user,
            outcome=outcome,
            reported_confidence=confidence,
            summary=summary,
            metadata={"private": "SECRET METADATA"},
        )
        return claim, verification_request, result

    def test_latest_completed_result_is_selected_by_created_at(self):
        _, _, older = self._create_result(
            outcome=VerificationResult.Outcome.FAIL,
            confidence=25,
        )
        _, _, newer = self._create_result(
            outcome=VerificationResult.Outcome.PARTIAL,
            confidence=70,
        )
        now = timezone.now()
        VerificationResult.objects.filter(pk=older.pk).update(created_at=now - timedelta(hours=1))
        VerificationResult.objects.filter(pk=newer.pk).update(created_at=now)

        summary = get_public_verification_summary(self.product)

        latest = summary["latest_verification"]
        self.assertEqual(latest["outcome"], VerificationResult.Outcome.PARTIAL)
        self.assertEqual(latest["reported_confidence"], 70)
        self.assertEqual(latest["method"]["code"], self.method.code)
        self.assertEqual(latest["method"]["name"], self.method.name)

    def test_non_completed_requests_are_ignored(self):
        self._create_result(status=VerificationRequest.Status.IN_PROGRESS)
        self._create_result(status=VerificationRequest.Status.FAILED)
        self._create_result(status=VerificationRequest.Status.CANCELLED)

        summary = get_public_verification_summary(self.product)

        self.assertIsNone(summary["latest_verification"])
        self.assertEqual(summary["total_verifications"], 0)

    def test_latest_result_tie_breaks_by_highest_id(self):
        _, _, first = self._create_result(
            outcome=VerificationResult.Outcome.FAIL,
            confidence=20,
        )
        _, _, second = self._create_result(
            outcome=VerificationResult.Outcome.INCONCLUSIVE,
            confidence=40,
        )
        same_time = timezone.now()
        VerificationResult.objects.filter(pk__in=[first.pk, second.pk]).update(created_at=same_time)

        summary = get_public_verification_summary(self.product)

        self.assertEqual(
            summary["latest_verification"]["outcome"],
            VerificationResult.Outcome.INCONCLUSIVE,
        )

    def test_public_summary_and_badge_do_not_expose_sensitive_fields(self):
        claim, _, result = self._create_result(
            outcome=VerificationResult.Outcome.PASS,
            confidence=91,
            summary="SECRET RESULT SUMMARY",
        )

        api_response = self.client.get(
            reverse("verification:product_summary", args=[self.product.pk])
        )
        detail_response = self.client.get(
            reverse("marketplace:detail", args=[self.product.slug])
        )

        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        api_body = api_response.content.decode()
        detail_body = detail_response.content.decode()
        for body in (api_body, detail_body):
            self.assertNotIn(self.user.username, body)
            self.assertNotIn(claim.claim_text, body)
            self.assertNotIn(result.summary, body)
            self.assertNotIn("SECRET METADATA", body)
        self.assertContains(detail_response, "Latest verification: Pass")
        self.assertContains(detail_response, "Reported confidence")
        self.assertContains(detail_response, self.method.name)
        self.assertNotContains(detail_response, "Verified True")

    def test_product_detail_has_neutral_empty_state(self):
        response = self.client.get(
            reverse("marketplace:detail", args=[self.product.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No completed verification yet")
        self.assertNotContains(response, "Not verified yet")
