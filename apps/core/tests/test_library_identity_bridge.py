from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from apps.core.models import ArtifactIdentityRole, Identity
from apps.core.services.library_bridge import (
    map_library_author_to_identity,
    resolve_library_author_identities,
)
from apps.core.services.registry import register_artifact
from library.models import LibraryItem


class LibraryIdentityBridgeTests(TestCase):
    def setUp(self):
        self.item = LibraryItem.objects.create(
            title="A Library Work",
            slug="a-library-work",
            author="Legacy Author Text",
        )
        self.identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Confirmed Author Identity",
        )

    def test_mapping_requires_registered_artifact(self):
        with self.assertRaises(ValidationError):
            map_library_author_to_identity(self.item, self.identity)

    def test_mapping_is_explicit_and_idempotent(self):
        register_artifact(self.item)

        role, created = map_library_author_to_identity(self.item, self.identity)
        role_again, created_again = map_library_author_to_identity(
            self.item, self.identity
        )

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(role.pk, role_again.pk)
        self.assertEqual(role.role, ArtifactIdentityRole.Role.AUTHOR)
        self.assertEqual(role.metadata["source"], "explicit_library_author_bridge")
        self.assertEqual(self.item.author, "Legacy Author Text")

    def test_mapping_never_creates_identity_from_author_text(self):
        register_artifact(self.item)
        before = Identity.objects.count()

        map_library_author_to_identity(self.item, self.identity)

        self.assertEqual(Identity.objects.count(), before)
        self.assertFalse(
            Identity.objects.filter(display_name=self.item.author).exists()
        )

    def test_inactive_identity_is_rejected(self):
        register_artifact(self.item)
        self.identity.is_active = False
        self.identity.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            map_library_author_to_identity(self.item, self.identity)

    def test_resolver_returns_only_explicit_author_roles(self):
        register_artifact(self.item)
        map_library_author_to_identity(self.item, self.identity)

        identities = list(resolve_library_author_identities(self.item))

        self.assertEqual(identities, [self.identity])

    def test_report_command_does_not_create_mapping_or_identity(self):
        register_artifact(self.item)
        before_identities = Identity.objects.count()
        out = StringIO()

        call_command("library_author_bridge", stdout=out)

        self.assertIn(f"LibraryItem {self.item.pk}", out.getvalue())
        self.assertIn("No identity suggestions or automatic mappings were made", out.getvalue())
        self.assertEqual(Identity.objects.count(), before_identities)
        self.assertFalse(ArtifactIdentityRole.objects.exists())

    def test_command_can_apply_explicit_mapping(self):
        register_artifact(self.item)
        out = StringIO()

        call_command(
            "library_author_bridge",
            library_item_id=self.item.pk,
            identity_id=str(self.identity.pk),
            stdout=out,
        )

        self.assertTrue(
            ArtifactIdentityRole.objects.filter(
                artifact__binding__object_id=str(self.item.pk),
                identity=self.identity,
                role=ArtifactIdentityRole.Role.AUTHOR,
            ).exists()
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.author, "Legacy Author Text")
