from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Identity, UserIdentity
from apps.core.templatetags.identity_tags import canonical_identity
from marketplace.models import Product


User = get_user_model()


class IdentityTagTests(TestCase):
    def test_identity_projection_when_binding_exists(self):
        user = User.objects.create_user(username="identity-user", password="x")
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Identity User",
            metadata={"private_note": "do-not-expose"},
        )
        UserIdentity.objects.create(user=user, identity=identity)

        projection = canonical_identity(user)

        self.assertEqual(
            projection,
            {
                "id": str(identity.id),
                "kind": Identity.Kind.HUMAN,
            },
        )
        self.assertNotIn("metadata", projection)
        self.assertNotIn("display_name", projection)

    def test_identity_projection_when_no_binding(self):
        user = User.objects.create_user(username="unbound-user", password="x")

        self.assertIsNone(canonical_identity(user))

    def test_identity_projection_with_invalid_user(self):
        self.assertIsNone(canonical_identity(None))
        self.assertIsNone(canonical_identity(User(username="unsaved-user")))


class ProductIdentityBadgeTests(TestCase):
    def _product_for(self, seller, *, title):
        return Product.objects.create(
            seller=seller,
            title=title,
            status=Product.STATUS_APPROVED,
            is_published=True,
        )

    def test_product_detail_displays_canonical_identity_when_binding_exists(self):
        seller = User.objects.create_user(username="bound-seller", password="x")
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Bound Seller",
            metadata={"private_note": "identity-private-marker"},
        )
        UserIdentity.objects.create(user=seller, identity=identity)
        product = self._product_for(seller, title="Bound identity product")

        response = self.client.get(reverse("marketplace:detail", args=[product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Canonical identity")
        self.assertContains(response, str(identity.id))
        self.assertContains(response, "Human")
        self.assertNotContains(response, "identity-private-marker")
        self.assertNotContains(response, "Bound Seller")

    def test_product_detail_omits_identity_badge_without_binding(self):
        seller = User.objects.create_user(username="unbound-seller", password="x")
        product = self._product_for(seller, title="Unbound identity product")

        response = self.client.get(reverse("marketplace:detail", args=[product.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Canonical identity")
