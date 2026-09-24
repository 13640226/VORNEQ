from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class DocumentLifecycleState(models.TextChoices):
    ACTIVE = "active", "Active"
    DEACTIVATED = "deactivated", "Deactivated"
    PENDING_DELETION = "pending_deletion", "Pending deletion"


class DocumentPreviousLifecycleState(models.TextChoices):
    ACTIVE = DocumentLifecycleState.ACTIVE, "Active"
    DEACTIVATED = DocumentLifecycleState.DEACTIVATED, "Deactivated"


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
    lifecycle_state = models.CharField(
        max_length=20,
        choices=DocumentLifecycleState.choices,
        default=DocumentLifecycleState.ACTIVE,
    )
    previous_lifecycle_state = models.CharField(
        max_length=20,
        choices=DocumentPreviousLifecycleState.choices,
        null=True,
        blank=True,
    )
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    deletion_requested_by = models.ForeignKey(
        "core.Identity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_deletion_requests",
    )
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

        if self.lifecycle_state == DocumentLifecycleState.PENDING_DELETION:
            if not self.deletion_requested_at or not self.deletion_requested_by_id:
                raise ValidationError(
                    "Pending deletion requires deletion_requested_at and deletion_requested_by."
                )
            if self.previous_lifecycle_state not in {
                DocumentPreviousLifecycleState.ACTIVE,
                DocumentPreviousLifecycleState.DEACTIVATED,
            }:
                raise ValidationError(
                    "Pending deletion requires a previous active or deactivated lifecycle state."
                )
        elif any(
            value is not None
            for value in (
                self.previous_lifecycle_state,
                self.deletion_requested_at,
                self.deletion_requested_by_id,
            )
        ):
            raise ValidationError(
                "Deletion request metadata is only valid while deletion is pending."
            )

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


class RetentionHold(models.Model):
    """Domain-owned hold that blocks later erasure while unreleased."""

    class Scope(models.TextChoices):
        LEGAL = "legal", "Legal"
        SECURITY = "security", "Security"
        INVESTIGATION = "investigation", "Investigation"

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="retention_holds",
    )
    reason = models.CharField(max_length=255)
    scope = models.CharField(max_length=20, choices=Scope.choices)
    placed_at = models.DateTimeField(auto_now_add=True)
    placed_by = models.ForeignKey(
        "core.Identity",
        on_delete=models.PROTECT,
        related_name="document_retention_holds_placed",
    )
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        "core.Identity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_retention_holds_released",
    )

    class Meta:
        ordering = ["-placed_at", "-id"]
        indexes = [
            models.Index(fields=["document", "released_at"], name="docs_hold_doc_release_idx"),
        ]

    @property
    def is_active(self):
        return self.released_at is None

    def clean(self):
        super().clean()
        if (self.released_at is None) != (self.released_by_id is None):
            raise ValidationError(
                "released_at and released_by must either both be set or both be empty."
            )

    def __str__(self):
        return f"{self.scope}:{self.document_id}:{'active' if self.is_active else 'released'}"


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
        DELETION_REQUESTED = "deletion_requested", "Deletion requested"
        DELETION_CANCELLED = "deletion_cancelled", "Deletion cancelled"

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
