from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import Artifact, ArtifactBinding, Identity, UserIdentity
from apps.documents.models import Document
from apps.documents.services import DocumentService


User = get_user_model()


class DocumentArtifactSyncTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="artifact-owner", password="pass")
        self.owner_identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Artifact Owner",
        )
        UserIdentity.objects.create(user=self.owner, identity=self.owner_identity)

    def _binding_for(self, document):
        return ArtifactBinding.objects.select_related("artifact", "content_type").get(
            content_type__app_label="documents",
            content_type__model="document",
            object_id=str(document.pk),
        )

    def test_create_document_creates_document_artifact_and_binding(self):
        document = DocumentService.create_document(
            user=self.owner,
            title="Canonical document",
            tags=["knowledge", "core"],
        )

        binding = self._binding_for(document)
        artifact = binding.artifact
        self.assertEqual(artifact.kind, Artifact.Kind.DOCUMENT)
        self.assertTrue(artifact.is_active)
        self.assertEqual(
            artifact.metadata,
            {"title": "Canonical document", "tags": ["knowledge", "core"]},
        )
        self.assertEqual(binding.content_object, document)
        self.assertEqual(binding.created_by, self.owner)
        binding.full_clean()

    def test_title_and_tags_update_refresh_artifact_projection(self):
        document = DocumentService.create_document(
            user=self.owner,
            title="Before",
            tags=["old"],
        )

        DocumentService.update_document(
            user=self.owner,
            document_id=document.pk,
            title="After",
            tags=["new"],
        )

        artifact = self._binding_for(document).artifact
        artifact.refresh_from_db()
        self.assertEqual(artifact.metadata, {"title": "After", "tags": ["new"]})

    def test_content_only_update_does_not_change_artifact_metadata(self):
        document = DocumentService.create_document(
            user=self.owner,
            title="Stable projection",
            content="Before",
            tags=["stable"],
        )
        artifact = self._binding_for(document).artifact
        original_metadata = artifact.metadata.copy()

        DocumentService.update_document(
            user=self.owner,
            document_id=document.pk,
            content="After",
        )

        artifact.refresh_from_db()
        self.assertEqual(artifact.metadata, original_metadata)

    def test_deactivate_document_deactivates_artifact(self):
        document = DocumentService.create_document(user=self.owner, title="Deactivate")
        artifact = self._binding_for(document).artifact

        DocumentService.deactivate_document(user=self.owner, document_id=document.pk)

        artifact.refresh_from_db()
        self.assertFalse(artifact.is_active)

    def test_create_rolls_back_when_artifact_sync_fails(self):
        with patch(
            "apps.documents.services.DocumentArtifactSync.create",
            side_effect=RuntimeError("sync failed"),
        ):
            with self.assertRaises(RuntimeError):
                DocumentService.create_document(user=self.owner, title="Rollback")

        self.assertFalse(Document.objects.filter(title="Rollback").exists())
        self.assertEqual(Artifact.objects.count(), 0)
        self.assertEqual(ArtifactBinding.objects.count(), 0)

    def test_update_rolls_back_when_artifact_sync_fails(self):
        document = DocumentService.create_document(user=self.owner, title="Before")
        artifact = self._binding_for(document).artifact
        original_metadata = artifact.metadata.copy()

        with patch(
            "apps.documents.services.DocumentArtifactSync.update",
            side_effect=RuntimeError("sync failed"),
        ):
            with self.assertRaises(RuntimeError):
                DocumentService.update_document(
                    user=self.owner,
                    document_id=document.pk,
                    title="After",
                )

        document.refresh_from_db()
        artifact.refresh_from_db()
        self.assertEqual(document.title, "Before")
        self.assertEqual(artifact.metadata, original_metadata)

    def test_deactivate_rolls_back_when_artifact_sync_fails(self):
        document = DocumentService.create_document(user=self.owner, title="Active")
        artifact = self._binding_for(document).artifact

        with patch(
            "apps.documents.services.DocumentArtifactSync.deactivate",
            side_effect=RuntimeError("sync failed"),
        ):
            with self.assertRaises(RuntimeError):
                DocumentService.deactivate_document(user=self.owner, document_id=document.pk)

        document.refresh_from_db()
        artifact.refresh_from_db()
        self.assertTrue(document.is_active)
        self.assertTrue(artifact.is_active)
