from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.models import (
    ContextualReputation,
    ContextualReputationEvent,
    Identity,
    UserIdentity,
)
from apps.core.services.contextual_reputation import record_verification_activity
from apps.evidence.models import Claim
from apps.verification.models import (
    VerificationMethod,
    VerificationRequest,
    VerificationResult,
)
from marketplace.models import Product


User = get_user_model()


class ContextualReputationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="context-verifier",
            password="test-pass-123",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Contextual Reputation Product",
        )
        self.claim = Claim.objects.create(
            claim_text="The product satisfies the scoped claim.",
            created_by=self.user,
        )
        self.method = VerificationMethod.objects.create(
            code="context-manual-review",
            name="Context manual review",
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
            reported_confidence=95,
        )

    def _bind_identity(self, display_name="Context Verifier"):
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name=display_name,
        )
        binding = UserIdentity.objects.create(user=self.user, identity=identity)
        return identity, binding

    def test_activity_creates_context_without_changing_score(self):
        reputation, event, created = record_verification_activity(
            verification_result=self.result,
            domain="security",
        )

        self.assertTrue(created)
        self.assertEqual(reputation.domain, "security")
        self.assertEqual(reputation.verification_method, self.method)
        self.assertEqual(reputation.score, 0.0)
        self.assertEqual(reputation.sample_count, 1)
        self.assertIsNone(reputation.identity)
        self.assertEqual(
            reputation.actor_role,
            ContextualReputation.ActorRole.VERIFIER,
        )
        self.assertEqual(event.verification_result, self.result)

    def test_activity_dual_writes_existing_user_identity(self):
        identity, _ = self._bind_identity()

        reputation, _, created = record_verification_activity(
            verification_result=self.result,
            domain="security",
        )

        self.assertTrue(created)
        self.assertEqual(reputation.user, self.user)
        self.assertEqual(reputation.identity, identity)
        self.assertEqual(
            reputation.actor_role,
            ContextualReputation.ActorRole.VERIFIER,
        )

    def test_activity_does_not_create_identity_when_binding_is_missing(self):
        self.assertEqual(Identity.objects.count(), 0)

        reputation, _, _ = record_verification_activity(
            verification_result=self.result,
            domain="security",
        )

        self.assertIsNone(reputation.identity)
        self.assertEqual(Identity.objects.count(), 0)

    def test_activity_is_idempotent_within_same_context(self):
        identity, _ = self._bind_identity()

        first_rep, first_event, first_created = record_verification_activity(
            verification_result=self.result,
            domain="security",
        )
        second_rep, second_event, second_created = record_verification_activity(
            verification_result=self.result,
            domain="security",
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_rep.pk, second_rep.pk)
        self.assertEqual(first_event.pk, second_event.pk)
        second_rep.refresh_from_db()
        self.assertEqual(second_rep.sample_count, 1)
        self.assertEqual(second_rep.score, 0.0)
        self.assertEqual(second_rep.identity, identity)

    def test_conflicting_identity_binding_is_not_overwritten(self):
        original_identity, binding = self._bind_identity("Original Identity")
        reputation, _, _ = record_verification_activity(
            verification_result=self.result,
            domain="security",
        )

        replacement_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Replacement Identity",
        )
        binding.identity = replacement_identity
        binding.save(update_fields=["identity"])

        with self.assertRaises(ValidationError):
            record_verification_activity(
                verification_result=self.result,
                domain="security",
            )

        reputation.refresh_from_db()
        self.assertEqual(reputation.identity, original_identity)
        self.assertEqual(reputation.sample_count, 1)

    def test_domains_are_isolated(self):
        security, _, _ = record_verification_activity(
            verification_result=self.result,
            domain="security",
        )
        medicine, _, _ = record_verification_activity(
            verification_result=self.result,
            domain="medicine",
        )

        self.assertNotEqual(security.pk, medicine.pk)
        self.assertEqual(security.sample_count, 1)
        self.assertEqual(medicine.sample_count, 1)
        self.assertEqual(security.score, medicine.score)

    def test_incomplete_request_cannot_create_reputation_event(self):
        self.request.status = VerificationRequest.Status.IN_PROGRESS
        self.request.save(update_fields=["status", "updated_at"])

        with self.assertRaises(ValidationError):
            record_verification_activity(
                verification_result=self.result,
                domain="security",
            )

    def test_event_is_append_only(self):
        _, event, _ = record_verification_activity(
            verification_result=self.result,
            domain="security",
        )
        event.metadata = {"changed": True}

        with self.assertRaises(RuntimeError):
            event.save()
        with self.assertRaises(RuntimeError):
            event.delete()

        self.assertEqual(ContextualReputationEvent.objects.count(), 1)
