from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.core.models import Identity, UserIdentity
from apps.documents.identity_resolver import IdentityNotFoundError, IdentityResolver


User = get_user_model()


class IdentityResolverTests(TestCase):
    def test_resolves_authenticated_user_to_canonical_identity(self):
        user = User.objects.create_user(username="bound", password="pass")
        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Bound User",
        )
        UserIdentity.objects.create(user=user, identity=identity)

        self.assertEqual(IdentityResolver.resolve(user), identity)

    def test_missing_user_identity_fails_closed(self):
        user = User.objects.create_user(username="unbound", password="pass")

        with self.assertRaises(IdentityNotFoundError):
            IdentityResolver.resolve(user)

    def test_anonymous_user_is_rejected_before_resolution(self):
        with self.assertRaises(PermissionDenied):
            IdentityResolver.resolve(AnonymousUser())
