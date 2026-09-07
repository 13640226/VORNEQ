from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.models import Identity
from apps.documents.models import Document, DocumentAccess


User = get_user_model()


class DocumentModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.owner_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Owner",
        )
        self.other_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Other",
        )

    def test_tags_must_be_list_of_strings(self):
        document = Document(
            title="Doc",
            content="",
            tags=["ok", 1],
            created_by=self.owner,
            owner_identity=self.owner_identity,
        )
        with self.assertRaises(ValidationError):
            document.full_clean()

    def test_owner_identity_is_canonical_owner(self):
        document = Document.objects.create(
            title="Doc",
            created_by=self.owner,
            owner_identity=self.owner_identity,
        )
        self.assertEqual(document.owner_identity, self.owner_identity)
        self.assertEqual(document.created_by, self.owner)

    def test_owner_identity_cannot_have_collaborator_access_row(self):
        document = Document.objects.create(
            title="Doc",
            created_by=self.owner,
            owner_identity=self.owner_identity,
        )
        access = DocumentAccess(
            document=document,
            identity=self.owner_identity,
            role=DocumentAccess.Role.EDITOR,
            granted_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_non_owner_identity_can_hold_collaborator_role(self):
        document = Document.objects.create(
            title="Doc",
            created_by=self.owner,
            owner_identity=self.owner_identity,
        )
        access = DocumentAccess(
            document=document,
            identity=self.other_identity,
            role=DocumentAccess.Role.VIEWER,
            granted_by=self.owner,
        )
        access.full_clean()
