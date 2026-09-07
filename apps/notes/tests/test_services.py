from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.core.models import Artifact, ArtifactIdentityRole, Identity, UserIdentity
from apps.notes.models import Note
from apps.notes.services import NoteService


User = get_user_model()


class NoteServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="notes-owner")
        self.identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Notes Owner",
        )
        self.binding = UserIdentity.objects.create(
            user=self.user,
            identity=self.identity,
        )

    def test_create_note_creates_artifact_and_owner_role(self):
        note = NoteService.create_note(
            user=self.user,
            title="First note",
            content="Private content",
        )

        self.assertEqual(note.artifact.kind, Artifact.Kind.OTHER)
        self.assertEqual(note.artifact.metadata, {"vertical": "notes"})
        self.assertTrue(
            ArtifactIdentityRole.objects.filter(
                artifact=note.artifact,
                identity=self.identity,
                role=ArtifactIdentityRole.Role.OWNER,
                is_primary=True,
            ).exists()
        )

    def test_list_notes_is_scoped_to_owner_identity(self):
        owned = NoteService.create_note(user=self.user, title="Owned", content="")
        other_user = User.objects.create_user(username="notes-other")
        other_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Other Notes Owner",
        )
        UserIdentity.objects.create(user=other_user, identity=other_identity)
        NoteService.create_note(user=other_user, title="Other", content="")

        self.assertEqual(list(NoteService.list_notes(self.user)), [owned])

    def test_missing_identity_binding_is_denied(self):
        unbound_user = User.objects.create_user(username="notes-unbound")
        with self.assertRaises(PermissionDenied):
            NoteService.list_notes(unbound_user)

    def test_delete_note_soft_deactivates_note_and_artifact(self):
        note = NoteService.create_note(user=self.user, title="Delete", content="")

        NoteService.delete_note(user=self.user, note_id=note.pk)

        note.refresh_from_db()
        note.artifact.refresh_from_db()
        self.assertFalse(note.is_active)
        self.assertFalse(note.artifact.is_active)

    def test_non_owner_cannot_read_note(self):
        note = NoteService.create_note(user=self.user, title="Private", content="")
        other_user = User.objects.create_user(username="notes-reader")
        other_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Reader",
        )
        UserIdentity.objects.create(user=other_user, identity=other_identity)

        with self.assertRaises(PermissionDenied):
            NoteService.get_note(other_user, note.pk)
