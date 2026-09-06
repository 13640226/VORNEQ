from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import Entitlement, Identity
from apps.core.services.entitlement import grant_entitlement, has_valid_entitlement
from apps.core.services.registry import register_artifact, register_user_identity
from marketplace.models import Product


User = get_user_model()


class EntitlementDualReadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dual-read-user",
            password="pass12345",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Dual Read Product",
        )

    def test_legacy_only_row_falls_back_successfully(self):
        entitlement = grant_entitlement(self.user, self.product)
        self.assertIsNone(entitlement.identity_id)
        self.assertIsNone(entitlement.artifact_id)

        self.assertTrue(has_valid_entitlement(self.user, self.product))

    def test_canonical_pair_matching_registry_authorizes(self):
        identity, _ = register_user_identity(self.user)
        artifact, _ = register_artifact(self.product)
        entitlement = grant_entitlement(self.user, self.product)

        self.assertEqual(entitlement.identity, identity)
        self.assertEqual(entitlement.artifact, artifact)
        self.assertTrue(has_valid_entitlement(self.user, self.product))

    def test_conflicting_canonical_identity_fails_closed(self):
        register_user_identity(self.user)
        artifact, _ = register_artifact(self.product)
        entitlement = grant_entitlement(self.user, self.product)
        wrong_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Wrong identity",
        )

        Entitlement.objects.filter(pk=entitlement.pk).update(
            identity=wrong_identity,
            artifact=artifact,
        )

        self.assertFalse(has_valid_entitlement(self.user, self.product))

    def test_missing_registry_binding_for_canonical_row_fails_closed(self):
        identity, _ = register_user_identity(self.user)
        register_artifact(self.product)
        entitlement = grant_entitlement(self.user, self.product)

        identity.user_binding.delete()

        self.assertFalse(has_valid_entitlement(self.user, self.product))

    def test_incomplete_canonical_pair_fails_closed(self):
        identity, _ = register_user_identity(self.user)
        register_artifact(self.product)
        entitlement = grant_entitlement(self.user, self.product)

        Entitlement.objects.filter(pk=entitlement.pk).update(
            identity=identity,
            artifact=None,
        )

        self.assertFalse(has_valid_entitlement(self.user, self.product))

    def test_inactive_entitlement_never_authorizes(self):
        grant_entitlement(self.user, self.product)
        Entitlement.objects.filter(user=self.user, product=self.product).update(
            is_active=False
        )

        self.assertFalse(has_valid_entitlement(self.user, self.product))

    def test_wrong_legacy_key_does_not_find_canonical_row(self):
        register_user_identity(self.user)
        register_artifact(self.product)
        grant_entitlement(self.user, self.product)
        other_user = User.objects.create_user(username="other-dual-read-user")

        self.assertFalse(has_valid_entitlement(other_user, self.product))
