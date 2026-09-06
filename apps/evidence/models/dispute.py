import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .critique import Critique


class Dispute(models.Model):
    """Immutable case container for a contestation.

    The linked Critique carries the argument and targets exactly one Claim or
    EvidenceRelation. Lifecycle state is derived exclusively from append-only
    ReviewRecord history; this model intentionally has no mutable status field.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    critique = models.OneToOneField(
        Critique,
        on_delete=models.PROTECT,
        related_name="dispute",
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputes_opened",
    )
    opened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-opened_at", "-id"]
        indexes = [
            models.Index(fields=["opened_at"], name="dispute_opened_idx"),
        ]

    @property
    def target(self):
        return self.critique.claim or self.critique.relation

    def clean(self):
        super().clean()
        if self.critique_id is None:
            raise ValidationError("Dispute requires a persisted Critique.")
        if self.critique.parent_id is not None:
            raise ValidationError("Dispute must be opened from a top-level Critique.")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Dispute is immutable; update is forbidden.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Dispute is immutable; delete is forbidden.")

    def __str__(self):
        return f"Dispute {self.id} -> {self.target}"
