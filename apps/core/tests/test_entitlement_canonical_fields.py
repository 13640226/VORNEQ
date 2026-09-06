from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Artifact, Entitlement, Identity
from apps.core.services.entitlement import (
    grant_entitlement,
    has_valid_entitlement,
    revoke_entitlement,
)
from apps.core.services.registry import register_artifact, register_user_identity
from marketplace.models import Product


User = get_user_model()


class EntitlementCanonicalFieldTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="entitlement-user",
            password="pass12345",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Entitlement Product",
        )

    def test_legacy_grant_remains_legacy_when_registry_bindings_are_absent(self):
        entitlement = grant_entitlement(self.user, self.product)

        self.assertEqual(entitlement.user, self.user)
        self.assertEqual(entitlement.product, self.product)
        self.assertIsNone(entitlement.identity_id)
        self.assertIsNone(entitlement.artifact_id)
        self.assertEqual(Entitlement.objects.count(), 1)

    def test_grant_dual_writes_same_row_when_both_bindings_exist(self):
        identity, _ = register_user_identity(self.user)
        artifact, _ = register_artifact(self.product)

        entitlement = grant_entitlement(self.user, self.product)

        self.assertEqual(Entitlement.objects.count(), 1)
        self.assertEqual(entitlement.identity, identity)
        self.assertEqual(entitlement.artifact, artifact)

    def test_existing_legacy_row_is_enriched_after_registry_registration(self):
        entitlement = grant_entitlement(self.user, self.product)
        self.assertIsNone(entitlement.identity_id)
        self.assertIsNone(entitlement.artifact_id)

        identity, _ = register_user_identity(self.user)
        artifact, _ = register_artifact(self.product)
        enriched = grant_entitlement(self.user, self.product)

        self.assertEqual(enriched.pk, entitlement.pk)
        self.assertEqual(Entitlement.objects.count(), 1)
        self.assertEqual(enriched.identity, identity)
        self.assertEqual(enriched.artifact, artifact)

    def test_explicit_canonical_pair_must_match_registry_bindings(self):
        expected_identity, _ = register_user_identity(self.user)
        artifact, _ = register_artifact(self.product)
        wrong_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Wrong Identity",
        )

        with self.assertRaises(ValidationError):
            grant_entitlement(
                self.user,
                self.product,
                identity=wrong_identity,
                artifact=artifact,
            )

        self.assertFalse(Entitlement.objects.exists())
        self.assertNotEqual(expected_identity, wrong_identity)

    def test_explicit_canonical_pair_requires_existing_bindings(self):
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Unbound Identity",
        )
        artifact = Artifact.objects.create(kind=Artifact.Kind.PRODUCT)

        with self.assertRaises(ValidationError):
            grant_entitlement(
                self.user,
                self.product,
                identity=identity,
                artifact=artifact,
            )

        self.assertFalse(Entitlement.objects.exists())

    def test_partial_explicit_canonical_pair_fails_closed(self):
        identity, _ = register_user_identity(self.user)
        register_artifact(self.product)

        with self.assertRaises(ValidationError):
            grant_entitlement(self.user, self.product, identity=identity)

    def test_dual_write_does_not_create_registry_objects(self):
        grant_entitlement(self.user, self.product)

        self.assertEqual(Identity.objects.count(), 0)
        self.assertEqual(Artifact.objects.count(), 0)

    def test_model_rejects_incomplete_canonical_pair(self):
        identity, _ = register_user_identity(self.user)
        entitlement = Entitlement(
            user=self.user,
            product=self.product,
            identity=identity,
            artifact=None,
        )

        with self.assertRaises(ValidationError):
            entitlement.full_clean()

    def test_legacy_authorization_behavior_is_unchanged(self):
        grant_entitlement(
            self.user,
            self.product,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertTrue(has_valid_entitlement(self.user, self.product))

        revoke_entitlement(self.user, self.product)
        self.assertFalse(has_valid_entitlement(self.user, self.product))
