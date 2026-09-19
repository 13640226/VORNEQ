from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import Artifact, ArtifactBinding
from apps.core.services.registry import register_artifact
from apps.verification.services.target_identity import (
    CanonicalTargetConflict,
    resolve_verification_target,
)
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
