from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Document(models.Model):
    """Domain-owned document state.

    Artifact representation, shared search, and platform audit integration are
    intentionally outside this model's boundary.
    """

    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="documents_created",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["created_by", "is_active"], name="docs_owner_active_idx"),
            models.Index(fields=["is_active", "updated_at"], name="docs_active_time_idx"),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.tags, list) or not all(isinstance(tag, str) for tag in self.tags):
            raise ValidationError({"tags": "Document tags must be a list of strings."})

    def __str__(self):
        return self.title


class DocumentAccess(models.Model):
    """Domain-owned effective role for one subject on one Document."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="access_entries",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_access_entries",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_access_grants",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "user"],
                name="docs_access_document_user_unique",
            ),
            models.UniqueConstraint(
                fields=["document"],
                condition=Q(role="owner"),
                name="docs_access_single_owner",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "role"], name="docs_access_user_role_idx"),
            models.Index(fields=["document", "role"], name="docs_access_doc_role_idx"),
        ]

    def clean(self):
        super().clean()
        if self.role == self.Role.OWNER:
            if self.user_id != self.document.created_by_id:
                raise ValidationError({"role": "Only the document creator can hold the owner role."})
            if self.granted_by_id != self.document.created_by_id:
                raise ValidationError({"granted_by": "The owner role must be self-granted at creation."})
        elif self.user_id == self.document.created_by_id:
            raise ValidationError({"user": "The document creator must retain the owner role."})

    def __str__(self):
        return f"{self.user_id}:{self.role}:{self.document_id}"
