from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Document(models.Model):
    """Domain-owned document state."""

    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="documents_created",
    )
    owner_identity = models.ForeignKey(
        "core.Identity",
        on_delete=models.PROTECT,
        related_name="documents_owned",
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
    """Domain-owned collaborator role for one Identity on one Document."""

    class Role(models.TextChoices):
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="access_entries",
    )
    identity = models.ForeignKey(
        "core.Identity",
        on_delete=models.PROTECT,
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
                fields=["document", "identity"],
                name="docs_access_document_identity_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["identity", "role"], name="docs_access_identity_role_idx"),
            models.Index(fields=["document", "role"], name="docs_access_doc_role_idx"),
        ]

    def clean(self):
        super().clean()
        if self.identity_id == self.document.owner_identity_id:
            raise ValidationError({"identity": "The document owner cannot have a collaborator access row."})

    def __str__(self):
        return f"{self.identity_id}:{self.role}:{self.document_id}"
