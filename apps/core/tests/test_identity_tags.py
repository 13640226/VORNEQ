from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Identity, UserIdentity
from apps.core.services.library_bridge import map_library_author_to_identity
from apps.core.services.registry import register_artifact
from apps.core.templatetags.identity_tags import (
    canonical_identity,
    library_canonical_identities,
)
from library.models import LibraryItem
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


class LibraryIdentityTagTests(TestCase):
    def _library_item(self, *, slug="identity-library-item", author="Legacy Author"):
        return LibraryItem.objects.create(
            title="Identity library item",
            slug=slug,
            author=author,
            is_published=True,
        )

    def _mapped_identity(self, item, *, display_name, metadata=None):
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name=display_name,
            metadata=metadata or {},
        )
        register_artifact(item)
        map_library_author_to_identity(item, identity)
        return identity

    def test_library_projection_uses_explicit_author_binding(self):
        item = self._library_item()
        identity = self._mapped_identity(
            item,
            display_name="Canonical Author",
            metadata={"private_note": "do-not-expose"},
        )

        projections = library_canonical_identities(item)

        self.assertEqual(
            projections,
            [{"id": str(identity.id), "kind": Identity.Kind.HUMAN}],
        )
        self.assertNotIn("metadata", projections[0])
        self.assertNotIn("display_name", projections[0])

    def test_library_projection_is_empty_without_binding(self):
        item = self._library_item(slug="unbound-library-item")

        self.assertEqual(library_canonical_identities(item), [])

    def test_library_projection_omits_inactive_identity(self):
        item = self._library_item(slug="inactive-library-item")
        identity = self._mapped_identity(item, display_name="Inactive Author")
        identity.is_active = False
        identity.save(update_fields=["is_active"])

        self.assertEqual(library_canonical_identities(item), [])

    def test_library_projection_keeps_multiple_authors_separate(self):
        item = self._library_item(slug="multiple-library-item")
        first = self._mapped_identity(item, display_name="First Author")
        second = self._mapped_identity(item, display_name="Second Author")

        projections = library_canonical_identities(item)

        self.assertEqual(len(projections), 2)
        self.assertEqual(
            {projection["id"] for projection in projections},
            {str(first.id), str(second.id)},
        )


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


class LibraryIdentityBadgeTests(TestCase):
    def _library_item(self, *, slug, author="Legacy Author"):
        return LibraryItem.objects.create(
            title="Library badge item",
            slug=slug,
            author=author,
            is_published=True,
        )

    def _mapped_identity(self, item, *, display_name, metadata=None):
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name=display_name,
            metadata=metadata or {},
        )
        register_artifact(item)
        map_library_author_to_identity(item, identity)
        return identity

    def test_library_detail_displays_explicit_canonical_identities(self):
        item = self._library_item(slug="bound-library-badge", author="Legacy Display Author")
        first = self._mapped_identity(
            item,
            display_name="Private Canonical One",
            metadata={"private_note": "identity-private-one"},
        )
        second = self._mapped_identity(
            item,
            display_name="Private Canonical Two",
            metadata={"private_note": "identity-private-two"},
        )

        response = self.client.get(reverse("library:detail", args=[item.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Legacy Display Author")
        self.assertContains(response, "Canonical identity", count=2)
        self.assertContains(response, str(first.id))
        self.assertContains(response, str(second.id))
        self.assertContains(response, "Human", count=2)
        self.assertNotContains(response, "identity-private-one")
        self.assertNotContains(response, "identity-private-two")
        self.assertNotContains(response, "Private Canonical One")
        self.assertNotContains(response, "Private Canonical Two")

    def test_library_detail_omits_identity_badge_without_binding(self):
        item = self._library_item(slug="unbound-library-badge")

        response = self.client.get(reverse("library:detail", args=[item.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Canonical identity")

    def test_library_detail_omits_inactive_identity(self):
        item = self._library_item(slug="inactive-library-badge")
        identity = self._mapped_identity(item, display_name="Inactive Badge Author")
        identity.is_active = False
        identity.save(update_fields=["is_active"])

        response = self.client.get(reverse("library:detail", args=[item.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Canonical identity")
        self.assertNotContains(response, str(identity.id))
