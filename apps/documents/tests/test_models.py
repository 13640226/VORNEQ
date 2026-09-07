from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.documents.models import Document, DocumentAccess


User = get_user_model()


class DocumentModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

    def test_tags_must_be_list_of_strings(self):
        document = Document(title="Doc", content="", tags=["ok", 1], created_by=self.owner)
        with self.assertRaises(ValidationError):
            document.full_clean()

    def test_creator_can_hold_owner_role(self):
        document = Document.objects.create(title="Doc", created_by=self.owner)
        access = DocumentAccess(
            document=document,
            user=self.owner,
            role=DocumentAccess.Role.OWNER,
            granted_by=self.owner,
        )
        access.full_clean()

    def test_non_creator_cannot_hold_owner_role(self):
        document = Document.objects.create(title="Doc", created_by=self.owner)
        access = DocumentAccess(
            document=document,
            user=self.other,
            role=DocumentAccess.Role.OWNER,
            granted_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            access.full_clean()

    def test_creator_cannot_be_downgraded(self):
        document = Document.objects.create(title="Doc", created_by=self.owner)
        access = DocumentAccess(
            document=document,
            user=self.owner,
            role=DocumentAccess.Role.EDITOR,
            granted_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            access.full_clean()
