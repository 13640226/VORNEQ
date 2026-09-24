from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.core.models import ArtifactBinding, Identity, UserIdentity
from apps.documents.models import (
    DocumentAuditLog,
    DocumentLifecycleState,
    RetentionHold,
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


class DocumentDeletionLifecycleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="lifecycle-owner", password="pass")
        self.outsider = User.objects.create_user(username="lifecycle-outsider", password="pass")
        self.owner_identity = bind_identity(self.owner, "Lifecycle Owner")
        self.outsider_identity = bind_identity(self.outsider, "Lifecycle Outsider")
        self.document = DocumentService.create_document(
            user=self.owner,
            title="Deletion lifecycle",
        )

    def _artifact(self):
        return ArtifactBinding.objects.select_related("artifact").get(
            content_type__app_label="documents",
            content_type__model="document",
            object_id=str(self.document.pk),
        ).artifact

    def test_request_deletion_moves_active_document_to_pending_and_hides_it(self):
        artifact = self._artifact()

        document = DocumentService.request_deletion(
            user=self.owner,
            document_id=self.document.pk,
        )

        self.assertEqual(document.lifecycle_state, DocumentLifecycleState.PENDING_DELETION)
        self.assertEqual(document.previous_lifecycle_state, DocumentLifecycleState.ACTIVE)
        self.assertFalse(document.is_active)
        self.assertEqual(document.deletion_requested_by, self.owner_identity)
        self.assertIsNotNone(document.deletion_requested_at)
        self.assertFalse(DocumentService.list_documents(user=self.owner).exists())
        with self.assertRaises(PermissionDenied):
            DocumentService.get_document(user=self.owner, document_id=self.document.pk)

        artifact.refresh_from_db()
        self.assertFalse(artifact.is_active)
        event = DocumentAuditLog.objects.filter(
            document=document,
            event_type=DocumentAuditLog.EventType.DELETION_REQUESTED,
        ).get()
        self.assertEqual(event.actor_identity, self.owner_identity)
        self.assertEqual(event.metadata["previous_lifecycle_state"], DocumentLifecycleState.ACTIVE)

    def test_cancel_deletion_restores_active_state_and_artifact(self):
        artifact = self._artifact()
        DocumentService.request_deletion(user=self.owner, document_id=self.document.pk)

        document = DocumentService.cancel_deletion(
            user=self.owner,
            document_id=self.document.pk,
        )

        self.assertEqual(document.lifecycle_state, DocumentLifecycleState.ACTIVE)
        self.assertIsNone(document.previous_lifecycle_state)
        self.assertTrue(document.is_active)
        self.assertIsNone(document.deletion_requested_at)
        self.assertIsNone(document.deletion_requested_by)
        artifact.refresh_from_db()
        self.assertTrue(artifact.is_active)
        self.assertTrue(
            DocumentAuditLog.objects.filter(
                document=document,
                event_type=DocumentAuditLog.EventType.DELETION_CANCELLED,
                actor_identity=self.owner_identity,
            ).exists()
        )

    def test_cancel_deletion_restores_deactivated_state_without_reactivation(self):
        artifact = self._artifact()
        DocumentService.deactivate_document(user=self.owner, document_id=self.document.pk)
        DocumentService.request_deletion(user=self.owner, document_id=self.document.pk)

        document = DocumentService.cancel_deletion(
            user=self.owner,
            document_id=self.document.pk,
        )

        self.assertEqual(document.lifecycle_state, DocumentLifecycleState.DEACTIVATED)
        self.assertFalse(document.is_active)
        artifact.refresh_from_db()
        self.assertFalse(artifact.is_active)

    def test_non_owner_cannot_request_or_cancel_deletion(self):
        with self.assertRaises(PermissionDenied):
            DocumentService.request_deletion(
                user=self.outsider,
                document_id=self.document.pk,
            )

        DocumentService.request_deletion(user=self.owner, document_id=self.document.pk)
        with self.assertRaises(PermissionDenied):
            DocumentService.cancel_deletion(
                user=self.outsider,
                document_id=self.document.pk,
            )

    def test_repeated_request_and_cancel_outside_pending_are_rejected(self):
        with self.assertRaises(ValidationError):
            DocumentService.cancel_deletion(user=self.owner, document_id=self.document.pk)

        DocumentService.request_deletion(user=self.owner, document_id=self.document.pk)
        with self.assertRaises(ValidationError):
            DocumentService.request_deletion(user=self.owner, document_id=self.document.pk)

    def test_retention_hold_active_status_is_derived_from_release_timestamp(self):
        hold = RetentionHold.objects.create(
            document=self.document,
            reason="Preserve while legal review is active",
            scope=RetentionHold.Scope.LEGAL,
            placed_by=self.owner_identity,
        )
        self.assertTrue(hold.is_active)

        hold.released_at = timezone.now()
        hold.released_by = self.owner_identity
        hold.full_clean()
        hold.save(update_fields=["released_at", "released_by"])
        self.assertFalse(hold.is_active)

    def test_retention_hold_requires_release_actor_and_timestamp_together(self):
        hold = RetentionHold(
            document=self.document,
            reason="Security review",
            scope=RetentionHold.Scope.SECURITY,
            placed_by=self.owner_identity,
            released_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            hold.full_clean()
