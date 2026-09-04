import uuid

from django.conf import settings
from django.db import models

from .claim import Claim


class ContentVersion(models.Model):
    """Append-only snapshot of mutable Claim content for knowledge diff."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey(Claim, on_delete=models.PROTECT, related_name="content_versions")
    version_number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    change_note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claim_versions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["claim_id", "version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["claim", "version_number"],
                name="contentversion_unique_claim_version",
            )
        ]

    @classmethod
    def snapshot_for_claim(cls, claim):
        return {"claim_text": claim.claim_text, "scope": claim.scope}

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("ContentVersion is append-only and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("ContentVersion is append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.claim_id} v{self.version_number}"
