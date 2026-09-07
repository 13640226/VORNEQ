from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.core.models import Identity, UserIdentity
from apps.documents.models import (
    Document,
    DocumentAccess,
    DocumentAuditLog,
    DocumentAuditMutationForbidden,
)
from apps.documents.services import DocumentService


User = get_user_model()


def bind_identity(user, display_name):
    identity = Identity.objects.create(
        kind=Identity.Kind.HUMAN,
        display_name=display_name,
    )
    UserIdentity.objects.create(user=user, identity=identity)
    return identity


class DocumentAuditTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="audit-owner")
        self.viewer = User.objects.create_user(username="audit-viewer")
        self.outsider = User.objects.create_user(username="audit-outsider")
        self.owner_identity = bind_identity(self.owner, "Audit Owner")
        self.viewer_identity = bind_identity(self.viewer, "Audit Viewer")
        self.outsider_identity = bind_identity(self.outsider, "Audit Outsider")
        self.document = DocumentService.create_document(
            user=self.owner,
            title="Audit boundary",
            content="sensitive body",
            tags=["audit"],
        )

    def events(self):
        return list(self.document.audit_log.order_by("timestamp", "id"))

    def test_create_records_canonical_actor_identity(self):
        event = self.events()[0]
        self.assertEqual(event.event_type, DocumentAuditLog.EventType.CREATED)
        self.assertEqual(event.actor_identity, self.owner_identity)
        self.assertEqual(event.metadata, {})

    def test_authorized_view_is_recorded_but_denied_view_is_not(self):
        before = self.document.audit_log.count()
        DocumentService.get_document(user=self.owner, document_id=self.document.pk)
        self.assertEqual(self.document.audit_log.count(), before + 1)
        self.assertEqual(
            self.document.audit_log.first().event_type,
            DocumentAuditLog.EventType.VIEWED,
        )

        before_denied = self.document.audit_log.count()
        with self.assertRaises(PermissionDenied):
            DocumentService.get_document(user=self.outsider, document_id=self.document.pk)
        self.assertEqual(self.document.audit_log.count(), before_denied)

    def test_update_records_changed_fields_without_copying_document_content(self):
        DocumentService.update_document(
            user=self.owner,
            document_id=self.document.pk,
            title="Updated title",
            content="new sensitive body",
        )
        event = self.document.audit_log.first()
        self.assertEqual(event.event_type, DocumentAuditLog.EventType.UPDATED)
        self.assertEqual(event.metadata, {"changed_fields": ["content", "title"]})
        self.assertNotIn("sensitive body", str(event.metadata))
        self.assertNotIn("new sensitive body", str(event.metadata))

    def test_share_and_revoke_record_target_identity_and_role(self):
        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.viewer,
            role=DocumentAccess.Role.VIEWER,
        )
        shared = self.document.audit_log.first()
        self.assertEqual(shared.event_type, DocumentAuditLog.EventType.SHARED)
        self.assertEqual(shared.actor_identity, self.owner_identity)
        self.assertEqual(shared.metadata["target_identity"], self.viewer_identity.pk)
        self.assertEqual(shared.metadata["role"], DocumentAccess.Role.VIEWER)

        DocumentService.revoke_access(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.viewer,
        )
        revoked = self.document.audit_log.first()
        self.assertEqual(revoked.event_type, DocumentAuditLog.EventType.REVOKED)
        self.assertEqual(revoked.metadata["target_identity"], self.viewer_identity.pk)
        self.assertEqual(revoked.metadata["previous_role"], DocumentAccess.Role.VIEWER)

    def test_no_revoke_event_is_written_when_access_does_not_exist(self):
        before = self.document.audit_log.count()
        DocumentService.revoke_access(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.viewer,
        )
        self.assertEqual(self.document.audit_log.count(), before)

    def test_deactivation_is_recorded_and_history_remains_queryable(self):
        DocumentService.deactivate_document(user=self.owner, document_id=self.document.pk)
        event = self.document.audit_log.first()
        self.assertEqual(event.event_type, DocumentAuditLog.EventType.DEACTIVATED)

        history = DocumentService.get_audit_history(
            user=self.owner,
            document_id=self.document.pk,
        )
        self.assertEqual(history.first().event_type, DocumentAuditLog.EventType.DEACTIVATED)

    def test_audit_history_requires_document_read_access(self):
        with self.assertRaises(PermissionDenied):
            list(
                DocumentService.get_audit_history(
                    user=self.outsider,
                    document_id=self.document.pk,
                )
            )

        DocumentService.share_document(
            user=self.owner,
            document_id=self.document.pk,
            collaborator=self.viewer,
            role=DocumentAccess.Role.VIEWER,
        )
        history = DocumentService.get_audit_history(
            user=self.viewer,
            document_id=self.document.pk,
        )
        self.assertGreaterEqual(history.count(), 2)

    def test_audit_rows_are_append_only(self):
        event = self.document.audit_log.first()
        event.metadata = {"tampered": True}
        with self.assertRaises(DocumentAuditMutationForbidden):
            event.save()
        with self.assertRaises(DocumentAuditMutationForbidden):
            event.delete()
        with self.assertRaises(DocumentAuditMutationForbidden):
            DocumentAuditLog.objects.filter(pk=event.pk).update(metadata={})
        with self.assertRaises(DocumentAuditMutationForbidden):
            DocumentAuditLog.objects.filter(pk=event.pk).delete()

    def test_audit_failure_rolls_back_domain_update(self):
        with patch(
            "apps.documents.services.DocumentAuditService.record",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                DocumentService.update_document(
                    user=self.owner,
                    document_id=self.document.pk,
                    title="Must roll back",
                )

        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Audit boundary")

    def test_create_rolls_back_when_audit_write_fails(self):
        before = Document.objects.count()
        with patch(
            "apps.documents.services.DocumentAuditService.record",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                DocumentService.create_document(
                    user=self.owner,
                    title="Must not persist",
                )
        self.assertEqual(Document.objects.count(), before)
