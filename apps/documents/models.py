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


class DocumentAuditMutationForbidden(Exception):
    """Raised when attempting to mutate an append-only document audit row."""


class DocumentAuditLogQuerySet(models.QuerySet):
    def update(self, *args, **kwargs):
        raise DocumentAuditMutationForbidden("Bulk update on DocumentAuditLog is not allowed.")

    def delete(self, *args, **kwargs):
        raise DocumentAuditMutationForbidden("Bulk delete on DocumentAuditLog is not allowed.")


class DocumentAuditLogManager(models.Manager):
    def get_queryset(self):
        return DocumentAuditLogQuerySet(self.model, using=self._db)


class DocumentAuditLog(models.Model):
    """Append-only, domain-owned audit trail for Documents."""

    class EventType(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DEACTIVATED = "deactivated", "Deactivated"
        SHARED = "shared", "Shared"
        REVOKED = "revoked", "Revoked"
        VIEWED = "viewed", "Viewed"

    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        related_name="audit_log",
    )
    actor_identity = models.ForeignKey(
        "core.Identity",
        on_delete=models.PROTECT,
        related_name="document_audit_events",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = DocumentAuditLogManager()

    class Meta:
        ordering = ["-timestamp", "-id"]
        indexes = [
            models.Index(fields=["document", "timestamp"], name="docs_audit_doc_time_idx"),
            models.Index(fields=["actor_identity", "timestamp"], name="docs_audit_actor_time_idx"),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "Document audit metadata must be an object."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise DocumentAuditMutationForbidden(
                "DocumentAuditLog is append-only; update is not allowed."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise DocumentAuditMutationForbidden(
            "DocumentAuditLog is append-only; deletion is not allowed."
        )

    def __str__(self):
        return f"{self.event_type}:{self.document_id}:{self.actor_identity_id}"
