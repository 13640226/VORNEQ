from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from apps.core.models import Artifact, ArtifactBinding

from .models import Document


class DocumentArtifactSync:
    """Maintain the shared Artifact projection for one domain-owned Document."""

    @staticmethod
    def _metadata(document):
        return {
            "title": document.title,
            "tags": list(document.tags),
        }

    @staticmethod
    def _content_type():
        return ContentType.objects.get_for_model(Document, for_concrete_model=False)

    @classmethod
    def _binding_for(cls, document):
        try:
            return ArtifactBinding.objects.select_related("artifact").get(
                content_type=cls._content_type(),
                object_id=str(document.pk),
            )
        except ArtifactBinding.DoesNotExist as exc:
            raise ValidationError("Document ArtifactBinding is missing.") from exc

    @classmethod
    def create(cls, *, document, user):
        artifact = Artifact(
            kind=Artifact.Kind.DOCUMENT,
            is_active=document.is_active,
            metadata=cls._metadata(document),
        )
        artifact.full_clean()
        artifact.save()

        binding = ArtifactBinding(
            artifact=artifact,
            content_type=cls._content_type(),
            object_id=str(document.pk),
            created_by=user,
        )
        binding.full_clean()
        binding.save()
        return artifact

    @classmethod
    def update(cls, *, document):
        binding = cls._binding_for(document)
        artifact = binding.artifact
        if artifact.kind != Artifact.Kind.DOCUMENT:
            raise ValidationError("Document binding must reference a document Artifact.")
        artifact.metadata = cls._metadata(document)
        artifact.full_clean()
        artifact.save(update_fields=["metadata", "updated_at"])
        return artifact

    @classmethod
    def deactivate(cls, *, document):
        binding = cls._binding_for(document)
        artifact = binding.artifact
        if artifact.kind != Artifact.Kind.DOCUMENT:
            raise ValidationError("Document binding must reference a document Artifact.")
        artifact.is_active = False
        artifact.full_clean()
        artifact.save(update_fields=["is_active", "updated_at"])
        return artifact

    @classmethod
    def reactivate(cls, *, document):
        binding = cls._binding_for(document)
        artifact = binding.artifact
        if artifact.kind != Artifact.Kind.DOCUMENT:
            raise ValidationError("Document binding must reference a document Artifact.")
        artifact.is_active = True
        artifact.full_clean()
        artifact.save(update_fields=["is_active", "updated_at"])
        return artifact
