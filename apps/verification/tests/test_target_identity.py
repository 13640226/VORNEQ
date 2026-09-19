from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import Artifact, ArtifactBinding
from apps.core.services.registry import register_artifact
from apps.verification.services.target_identity import (
    CanonicalTargetConflict,
    resolve_verification_request_target,
    resolve_verification_target,
)
from apps.evidence.models import Claim
from apps.verification.models import VerificationMethod, VerificationRequest
from marketplace.models import Product


User = get_user_model()


class VerificationTargetIdentityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="target-identity-user")
        self.product = Product.objects.create(
            seller=self.user,
            title="Target Identity Product",
        )

    def test_existing_binding_resolves_to_same_artifact(self):
        artifact, _ = register_artifact(self.product, created_by=self.user)

        resolved = resolve_verification_target(legacy_target=self.product)

        self.assertEqual(resolved.canonical_artifact, artifact)

    def test_unbound_legacy_target_remains_valid_and_no_binding_created(self):
        self.assertFalse(ArtifactBinding.objects.exists())

        resolved = resolve_verification_target(legacy_target=self.product)

        self.assertIsNone(resolved.canonical_artifact)
        self.assertFalse(ArtifactBinding.objects.exists())

    def test_explicit_conflicting_canonical_identity_fails_closed(self):
        artifact, _ = register_artifact(self.product, created_by=self.user)
        conflicting = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)

        with self.assertRaises(CanonicalTargetConflict):
            resolve_verification_target(
                legacy_target=self.product,
                expected_canonical_artifact=conflicting,
            )

        self.assertNotEqual(artifact, conflicting)
        self.assertEqual(ArtifactBinding.objects.count(), 1)


class VerificationRequestTargetReadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="request-target-read-user")
        self.product = Product.objects.create(seller=self.user, title="Read Target Product")
        self.claim = Claim.objects.create(statement="Read target claim")
        self.method = VerificationMethod.objects.create(code="read-target", name="Read target")
        from django.contrib.contenttypes.models import ContentType
        self.content_type = ContentType.objects.get_for_model(self.product, for_concrete_model=False)

    def make_request(self, *, canonical_artifact=None):
        return VerificationRequest.objects.create(
            artifact_content_type=self.content_type,
            artifact_object_id=str(self.product.pk),
            canonical_artifact=canonical_artifact,
            claim=self.claim,
            method=self.method,
            requested_by=self.user,
        )

    def test_legacy_only_unbound_remains_valid_without_mutation(self):
        request = self.make_request()
        before = (Artifact.objects.count(), ArtifactBinding.objects.count(), request.updated_at)

        resolved = resolve_verification_request_target(request)

        request.refresh_from_db()
        self.assertEqual(resolved.legacy_target, self.product)
        self.assertIsNone(resolved.canonical_artifact)
        self.assertEqual((Artifact.objects.count(), ArtifactBinding.objects.count(), request.updated_at), before)
        self.assertIsNone(request.canonical_artifact)

    def test_legacy_only_bound_resolves_canonical_in_memory_only(self):
        canonical, _ = register_artifact(self.product, created_by=self.user)
        request = self.make_request()

        resolved = resolve_verification_request_target(request)

        request.refresh_from_db()
        self.assertEqual(resolved.canonical_artifact, canonical)
        self.assertIsNone(request.canonical_artifact)

    def test_persisted_canonical_with_matching_binding_is_valid(self):
        canonical, _ = register_artifact(self.product, created_by=self.user)
        request = self.make_request(canonical_artifact=canonical)

        resolved = resolve_verification_request_target(request)

        self.assertEqual(resolved.canonical_artifact, canonical)
        self.assertEqual(resolved.legacy_target, self.product)

    def test_persisted_canonical_without_binding_fails_closed(self):
        canonical = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        request = self.make_request(canonical_artifact=canonical)

        with self.assertRaises(CanonicalTargetConflict):
            resolve_verification_request_target(request)

        self.assertFalse(ArtifactBinding.objects.exists())

    def test_persisted_canonical_with_mismatching_binding_fails_closed(self):
        bound, _ = register_artifact(self.product, created_by=self.user)
        conflicting = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)
        request = self.make_request(canonical_artifact=conflicting)
        before = (Artifact.objects.count(), ArtifactBinding.objects.count())

        with self.assertRaises(CanonicalTargetConflict):
            resolve_verification_request_target(request)

        self.assertNotEqual(bound, conflicting)
        self.assertEqual((Artifact.objects.count(), ArtifactBinding.objects.count()), before)
