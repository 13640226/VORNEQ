import uuid

from django.db import models
from django.utils import timezone


class AuditEventMutationForbidden(Exception):
    """Raised when attempting to mutate an append-only AuditEvent."""


class AuditEventQuerySet(models.QuerySet):
    def update(self, *args, **kwargs):
        raise AuditEventMutationForbidden("Bulk update on AuditEvent is not allowed.")

    def delete(self, *args, **kwargs):
        raise AuditEventMutationForbidden("Bulk delete on AuditEvent is not allowed.")


class AuditEventManager(models.Manager):
    def get_queryset(self):
        return AuditEventQuerySet(self.model, using=self._db)


class AuditEvent(models.Model):
    class Outcome(models.TextChoices):
        CREATED = "created", "Created"
        CHANGED = "changed", "Changed"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        GRANTED = "granted", "Granted"
        DENIED = "denied", "Denied"
        REVOKED = "revoked", "Revoked"

    class RetentionClass(models.TextChoices):
        STANDARD = "standard", "Standard"
        SECURITY = "security", "Security"

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    event_name = models.CharField(max_length=100, db_index=True)
    actor = models.JSONField()
    target = models.JSONField()
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    reason_code = models.CharField(max_length=50, blank=True)
    correlation_id = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict)
    retention_class = models.CharField(
        max_length=20,
        choices=RetentionClass.choices,
        default=RetentionClass.STANDARD,
    )
    timestamp = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    objects = AuditEventManager()

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(
                fields=["event_name", "timestamp"],
                name="audit_event_name_time_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AuditEventMutationForbidden(
                "AuditEvent is append-only; update is not allowed."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditEventMutationForbidden(
            "AuditEvent is append-only; deletion is not allowed."
        )
