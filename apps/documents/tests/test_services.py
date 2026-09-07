from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.documents.models import DocumentAccess
from apps.documents.services import DocumentService


User = get_user_model()


class DocumentServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.editor = User.objects.create_user(username="editor", password="pass")
        self.viewer = User.objects.create_user(username="viewer", password="pass")
        self.outsider = User.objects.create_user(username="outsider", password="pass")
        self.document = DocumentService.create_document(
            user=self.owner,
            title="Domain boundary",
            content="Initial",
            tags=["architecture"],
        )

    def test_create_document_creates_single_owner_access(self):
        access = DocumentAccess.objects.get(document=self.document, user=self.owner)
        self.assertEqual(access.role, DocumentAccess.Role.OWNER)
        self.assertEqual(access.granted_by, self.owner)

    def test_owner_can_read_and_update(self):
        document = DocumentService.get_document(user=self.owner, document_id=self.document.pk)
        self.assertEqual(document.pk, self.document.pk)
        updated = DocumentService.update_document(
            user=self.owner,
            document_id=self.document.pk,
            content="Updated",
        )
        self.assertEqual(updated.content, "Updated")

    def test_editor_can_read_and_write(self):
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.editor,
            role=DocumentAccess.Role.EDITOR,
        )
        self.assertEqual(
            DocumentService.get_document(user=self.editor, document_id=self.document.pk).pk,
            self.document.pk,
        )
        updated = DocumentService.update_document(
            user=self.editor,
            document_id=self.document.pk,
            title="Edited",
        )
        self.assertEqual(updated.title, "Edited")

    def test_viewer_can_read_but_cannot_write(self):
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.viewer,
            role=DocumentAccess.Role.VIEWER,
        )
        self.assertEqual(
            DocumentService.get_document(user=self.viewer, document_id=self.document.pk).pk,
            self.document.pk,
        )
        with self.assertRaises(PermissionDenied):
            DocumentService.update_document(
                user=self.viewer,
                document_id=self.document.pk,
                title="Blocked",
            )

    def test_outsider_cannot_read(self):
        with self.assertRaises(PermissionDenied):
            DocumentService.get_document(user=self.outsider, document_id=self.document.pk)

    def test_non_owner_cannot_share_or_escalate_privilege(self):
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.editor,
            role=DocumentAccess.Role.EDITOR,
        )
        with self.assertRaises(PermissionDenied):
            DocumentService.share_document(
                user=self.editor,
                document_id=self.document.pk,
                collaborator=self.outsider,
                role=DocumentAccess.Role.EDITOR,
            )
        with self.assertRaises(ValidationError):
            DocumentService.share_document(
                user=self.owner,
                document_id=self.document.pk,
                collaborator=self.outsider,
                role=DocumentAccess.Role.OWNER,
            )

    def test_owner_can_change_and_revoke_collaborator_role(self):
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.editor,
            role=DocumentAccess.Role.EDITOR,
        )
        access = DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.editor,
            role=DocumentAccess.Role.VIEWER,
        )
        self.assertEqual(access.role, DocumentAccess.Role.VIEWER)

        DocumentService.revoke_access(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.editor,
        )
        with self.assertRaises(PermissionDenied):
            DocumentService.get_document(user=self.editor, document_id=self.document.pk)

    def test_owner_access_cannot_be_revoked(self):
        with self.assertRaises(ValidationError):
            DocumentService.revoke_access(
                user=self.owner,
                document_id=self.document.pk,
                collaborator=self.owner,
            )

    def test_only_owner_can_deactivate(self):
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.editor,
            role=DocumentAccess.Role.EDITOR,
        )
        with self.assertRaises(PermissionDenied):
            DocumentService.deactivate_document(
                user=self.editor,
                document_id=self.document.pk,
            )
        DocumentService.deactivate_document(user=self.owner, document_id=self.document.pk)
        with self.assertRaises(PermissionDenied):
            DocumentService.get_document(user=self.owner, document_id=self.document.pk)

    def test_list_documents_isolated_by_user(self):
        other = DocumentService.create_document(user=self.outsider, title="Other")
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.viewer,
            role=DocumentAccess.Role.VIEWER,
        )
        self.assertEqual(list(DocumentService.list_documents(user=self.viewer)), [self.document])
        self.assertEqual(list(DocumentService.list_documents(user=self.outsider)), [other])
