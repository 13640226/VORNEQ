from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import Artifact, ArtifactIdentityRole, UserIdentity

from .models import Note


class NoteService:
    @staticmethod
    def identity_for_user(user):
        try:
            binding = UserIdentity.objects.select_related("identity").get(user=user)
        except UserIdentity.DoesNotExist as exc:
            raise PermissionDenied("A verified user identity binding is required.") from exc
        if not binding.identity.is_active:
            raise PermissionDenied("The bound identity is inactive.")
        return binding.identity

    @staticmethod
    def _owned_artifact_ids(identity):
        now = timezone.now()
        return ArtifactIdentityRole.objects.filter(
            identity=identity,
            role=ArtifactIdentityRole.Role.OWNER,
            valid_from__lte=now,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now)).values("artifact_id")

    @classmethod
    def list_notes(cls, user):
        identity = cls.identity_for_user(user)
        return Note.objects.filter(
            is_active=True,
            artifact_id__in=cls._owned_artifact_ids(identity),
        ).select_related("artifact")

    @classmethod
    def get_note(cls, user, note_id):
        identity = cls.identity_for_user(user)
        try:
            return Note.objects.select_related("artifact").get(
                pk=note_id,
                is_active=True,
                artifact_id__in=cls._owned_artifact_ids(identity),
            )
        except Note.DoesNotExist as exc:
            raise PermissionDenied("You do not have access to this note.") from exc

    @classmethod
    @transaction.atomic
    def create_note(cls, *, user, title, content):
        identity = cls.identity_for_user(user)
        artifact = Artifact.objects.create(
            kind=Artifact.Kind.OTHER,
            metadata={"vertical": "notes"},
        )
        note = Note.objects.create(
            artifact=artifact,
            title=title,
            content=content,
        )
        role = ArtifactIdentityRole(
            artifact=artifact,
            identity=identity,
            role=ArtifactIdentityRole.Role.OWNER,
            is_primary=True,
        )
        role.full_clean()
        role.save()
        return note

    @classmethod
    @transaction.atomic
    def update_note(cls, *, user, note_id, title, content):
        note = cls.get_note(user, note_id)
        note.title = title
        note.content = content
        note.save(update_fields=["title", "content", "updated_at"])
        return note

    @classmethod
    @transaction.atomic
    def delete_note(cls, *, user, note_id):
        note = cls.get_note(user, note_id)
        note.is_active = False
        note.save(update_fields=["is_active", "updated_at"])
        artifact = note.artifact
        artifact.is_active = False
        artifact.save(update_fields=["is_active", "updated_at"])
