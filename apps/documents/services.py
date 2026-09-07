from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from .models import Document, DocumentAccess


class DocumentService:
    """Domain service for Documents CRUD and authorization."""

    READ_ROLES = {DocumentAccess.Role.OWNER, DocumentAccess.Role.EDITOR, DocumentAccess.Role.VIEWER}
    WRITE_ROLES = {DocumentAccess.Role.OWNER, DocumentAccess.Role.EDITOR}

    @staticmethod
    def _validate_user(user):
        if user is None or not getattr(user, "is_authenticated", False):
            raise PermissionDenied("Authentication is required.")

    @classmethod
    def _role_for(cls, *, user, document):
        cls._validate_user(user)
        try:
            return DocumentAccess.objects.only("role").get(document=document, user=user).role
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
        cls._validate_user(user)
        document = Document(
            title=title,
            content=content,
            tags=[] if tags is None else tags,
            created_by=user,
        )
        document.full_clean()
        document.save()

        access = DocumentAccess(
            document=document,
            user=user,
            role=DocumentAccess.Role.OWNER,
            granted_by=user,
        )
        access.full_clean()
        access.save()
        return document

    @classmethod
    def get_document(cls, *, user, document_id):
        document = cls._get_active_document(document_id)
        cls._require_role(user=user, document=document, allowed_roles=cls.READ_ROLES)
        return document

    @classmethod
    def list_documents(cls, *, user):
        cls._validate_user(user)
        return Document.objects.filter(
            is_active=True,
            access_entries__user=user,
            access_entries__role__in=cls.READ_ROLES,
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
            allowed_roles={DocumentAccess.Role.OWNER},
        )
        cls._validate_user(collaborator)

        if collaborator.pk == document.created_by_id:
            raise ValidationError("The document owner role cannot be replaced.")
        if role not in {DocumentAccess.Role.EDITOR, DocumentAccess.Role.VIEWER}:
            raise ValidationError("Shared access role must be editor or viewer.")

        access, _ = DocumentAccess.objects.get_or_create(
            document=document,
            user=collaborator,
            defaults={"role": role, "granted_by": user},
        )
        if access.role != role or access.granted_by_id != user.pk:
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
            allowed_roles={DocumentAccess.Role.OWNER},
        )
        if collaborator.pk == document.created_by_id:
            raise ValidationError("Owner access cannot be revoked.")
        DocumentAccess.objects.filter(document=document, user=collaborator).delete()

    @classmethod
    @transaction.atomic
    def deactivate_document(cls, *, user, document_id):
        document = cls._get_active_document(document_id)
        cls._require_role(
            user=user,
            document=document,
            allowed_roles={DocumentAccess.Role.OWNER},
        )
        document.is_active = False
        document.save(update_fields=["is_active", "updated_at"])
        return document
