from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Identity, UserIdentity
from apps.evidence.models import Claim
from apps.verification.models import (
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)
from apps.verification.services.activity import get_verification_activity
from library.models import LibraryItem
from marketplace.models import Product


User = get_user_model()


class VerificationActivityTests(TestCase):
    def setUp(self):
        self.verifier = User.objects.create_user(
            username="activity-verifier",
            password="test-pass-123",
        )
        self.other_user = User.objects.create_user(
            username="other-verifier",
            password="test-pass-123",
        )
        self.product = Product.objects.create(
            seller=self.verifier,
            title="Activity Product",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self.claim = Claim.objects.create(
            claim_text="Activity claim",
            created_by=self.verifier,
        )
        self.method = VerificationMethod.objects.create(
            code="activity-method",
            name="Activity method",
        )

    def _result(
        self,
        verifier,
        artifact=None,
        *,
        outcome=VerificationResult.Outcome.PASS,
        confidence=84,
        summary="PRIVATE RESULT SUMMARY",
        metadata=None,
    ):
        artifact = artifact or self.product
        content_type = ContentType.objects.get_for_model(
            artifact,
            for_concrete_model=False,
        )
        verification_request = VerificationRequest.objects.create(
            artifact_content_type=content_type,
            artifact_object_id=str(artifact.pk),
            claim=self.claim,
            method=self.method,
            requested_by=verifier,
            status=VerificationRequest.Status.COMPLETED,
        )
        return VerificationResult.objects.create(
            request=verification_request,
            verifier=verifier,
            outcome=outcome,
            reported_confidence=confidence,
            summary=summary,
            metadata=metadata or {"private_note": "PRIVATE RESULT METADATA"},
        )

    def test_service_returns_narrow_projection_without_private_result_fields(self):
        result = self._result(self.verifier)

        activity = get_verification_activity(self.verifier)

        self.assertEqual(len(activity), 1)
        self.assertEqual(
            set(activity[0]),
            {
                "artifact_title",
                "artifact_url",
                "method",
                "outcome",
                "confidence",
                "recorded_at",
            },
        )
        self.assertEqual(activity[0]["artifact_title"], self.product.title)
        self.assertEqual(activity[0]["artifact_url"], self.product.get_absolute_url())
        self.assertEqual(
            activity[0]["method"],
            {"code": self.method.code, "name": self.method.name},
        )
        self.assertEqual(activity[0]["outcome"], VerificationResult.Outcome.PASS)
        self.assertEqual(activity[0]["confidence"], 84)
        self.assertEqual(activity[0]["recorded_at"], result.created_at)
        self.assertNotIn("summary", activity[0])
        self.assertNotIn("metadata", activity[0])
        self.assertNotIn("verifier", activity[0])

    def test_service_resolves_library_item_from_explicit_allowed_artifact_type(self):
        item = LibraryItem.objects.create(
            title="Activity Library Item",
            slug="activity-library-item",
            is_published=True,
        )
        self._result(self.verifier, item)

        activity = get_verification_activity(self.verifier)

        self.assertEqual(activity[0]["artifact_title"], item.title)
        self.assertEqual(
            activity[0]["artifact_url"],
            reverse("library:detail", kwargs={"slug": item.slug}),
        )

    def test_service_returns_empty_for_invalid_or_unsaved_user(self):
        self.assertEqual(get_verification_activity(None), [])
        self.assertEqual(get_verification_activity(User(username="unsaved")), [])

    def test_api_requires_authentication(self):
        response = self.client.get(reverse("verification:activity"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "authentication_required")

    def test_api_isolates_activity_to_authenticated_verifier(self):
        self._result(self.verifier)
        other_product = Product.objects.create(
            seller=self.other_user,
            title="Other User Secret Artifact",
            status=Product.STATUS_APPROVED,
            is_published=True,
        )
        self._result(self.other_user, other_product)
        self.client.force_login(self.verifier)

        response = self.client.get(reverse("verification:activity"))

        self.assertEqual(response.status_code, 200)
        activity = response.json()["activity"]
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity[0]["artifact_title"], self.product.title)
        self.assertNotContains(response, "Other User Secret Artifact")
        self.assertNotContains(response, "PRIVATE RESULT SUMMARY")
        self.assertNotContains(response, "PRIVATE RESULT METADATA")
        self.assertNotContains(response, self.verifier.username)

    def test_api_empty_state_and_rejects_non_get_method(self):
        self.client.force_login(self.verifier)

        response = self.client.get(reverse("verification:activity"))
        post_response = self.client.post(reverse("verification:activity"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"activity": []})
        self.assertEqual(post_response.status_code, 405)

    def test_profile_displays_activity_and_public_safe_canonical_identity(self):
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="PRIVATE CANONICAL DISPLAY NAME",
            metadata={"private_note": "PRIVATE IDENTITY METADATA"},
        )
        UserIdentity.objects.create(user=self.verifier, identity=identity)
        self._result(self.verifier)
        self.client.force_login(self.verifier)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verification Activity")
        self.assertContains(response, self.product.title)
        self.assertContains(response, self.method.name)
        self.assertContains(response, "Pass")
        self.assertContains(response, "84%")
        self.assertContains(response, "Canonical identity")
        self.assertContains(response, str(identity.id))
        self.assertContains(response, "Human")
        self.assertNotContains(response, "PRIVATE RESULT SUMMARY")
        self.assertNotContains(response, "PRIVATE RESULT METADATA")
        self.assertNotContains(response, "PRIVATE CANONICAL DISPLAY NAME")
        self.assertNotContains(response, "PRIVATE IDENTITY METADATA")

    def test_profile_keeps_identity_absence_neutral_and_activity_empty(self):
        self.client.force_login(self.verifier)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Canonical identity")
        self.assertContains(response, "No verification activity yet.")
