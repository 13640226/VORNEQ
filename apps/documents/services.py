from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from .identity_resolver import IdentityResolver
from .models import Document, DocumentAccess


class DocumentService:
    """Domain service for Documents CRUD and identity-based authorization."""

    OWNER_ROLE = "owner"
    READ_ROLES = {OWNER_ROLE, DocumentAccess.Role.EDITOR, DocumentAccess.Role.VIEWER}
    WRITE_ROLES = {OWNER_ROLE, DocumentAccess.Role.EDITOR}

    @classmethod
    def _role_for(cls, *, user, document):
        identity = IdentityResolver.resolve(user)
        if identity.pk == document.owner_identity_id:
            return cls.OWNER_ROLE
        try:
            return DocumentAccess.objects.only("role").get(
                document=document,
                identity=identity,
            ).role
        except DocumentAccess.DoesNotExist:
            return None

    @classmethod
    def _require_role(cls, *, user, document, allowed_roles):
        role = cls._role_for(user=user, document=document)
        if role not in allowed_roles:
            raise PermissionDenied("You do not have permission to perform this action.")
        return role

    @staticmethod
    def _get_active_document(document_id):
        try:
            return Document.objects.get(pk=document_id, is_active=True)
        except Document.DoesNotExist as exc:
            raise PermissionDenied("Document is unavailable or inaccessible.") from exc

    @classmethod
    @transaction.atomic
    def create_document(cls, *, user, title, content="", tags=None):
        identity = IdentityResolver.resolve(user)
        document = Document(
            title=title,
            content=content,
            tags=[] if tags is None else tags,
            created_by=user,
            owner_identity=identity,
        )
        document.full_clean()
        document.save()
        return document

    @classmethod
    def get_document(cls, *, user, document_id):
        document = cls._get_active_document(document_id)
        cls._require_role(user=user, document=document, allowed_roles=cls.READ_ROLES)
        return document

    @classmethod
    def list_documents(cls, *, user):
        identity = IdentityResolver.resolve(user)
        return Document.objects.filter(is_active=True).filter(
            Q(owner_identity=identity)
            | Q(
                access_entries__identity=identity,
                access_entries__role__in={
                    DocumentAccess.Role.EDITOR,
                    DocumentAccess.Role.VIEWER,
                },
            )
        ).distinct()

    @classmethod
    @transaction.atomic
    def update_document(cls, *, user, document_id, title=None, content=None, tags=None):
        document = cls._get_active_document(document_id)
        cls._require_role(user=user, document=document, allowed_roles=cls.WRITE_ROLES)

        update_fields = []
        if title is not None:
            document.title = title
            update_fields.append("title")
        if content is not None:
            document.content = content
            update_fields.append("content")
        if tags is not None:
            document.tags = tags
            update_fields.append("tags")

        if update_fields:
            document.full_clean()
            document.save(update_fields=[*update_fields, "updated_at"])
        return document

    @classmethod
    @transaction.atomic
    def share_document(cls, *, user, document_id, collaborator, role):
        document = cls._get_active_document(document_id)
        cls._require_role(
            user=user,
            document=document,
            allowed_roles={cls.OWNER_ROLE},
        )
        collaborator_identity = IdentityResolver.resolve(collaborator)

        if collaborator_identity.pk == document.owner_identity_id:
            raise ValidationError("The document owner cannot be added as a collaborator.")
        if role not in {DocumentAccess.Role.EDITOR, DocumentAccess.Role.VIEWER}:
            raise ValidationError("Shared access role must be editor or viewer.")

        access, created = DocumentAccess.objects.get_or_create(
            document=document,
            identity=collaborator_identity,
            defaults={"role": role, "granted_by": user},
        )
        if created:
            access.full_clean()
        elif access.role != role or access.granted_by_id != user.pk:
            access.role = role
            access.granted_by = user
            access.full_clean()
            access.save(update_fields=["role", "granted_by", "updated_at"])
        return access

    @classmethod
    @transaction.atomic
    def revoke_access(cls, *, user, document_id, collaborator):
        document = cls._get_active_document(document_id)
        cls._require_role(
            user=user,
            document=document,
            allowed_roles={cls.OWNER_ROLE},
        )
        collaborator_identity = IdentityResolver.resolve(collaborator)
        if collaborator_identity.pk == document.owner_identity_id:
            raise ValidationError("Owner access cannot be revoked.")
        DocumentAccess.objects.filter(
            document=document,
            identity=collaborator_identity,
        ).delete()

    @classmethod
    @transaction.atomic
    def deactivate_document(cls, *, user, document_id):
        document = cls._get_active_document(document_id)
        cls._require_role(
            user=user,
            document=document,
            allowed_roles={cls.OWNER_ROLE},
        )
        document.is_active = False
        document.save(update_fields=["is_active", "updated_at"])
        return document
