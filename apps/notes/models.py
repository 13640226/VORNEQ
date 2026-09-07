from django.db import models

from apps.core.models import Artifact


class Note(models.Model):
    """Private note content backed by a canonical Core Artifact."""

    artifact = models.OneToOneField(
        Artifact,
        on_delete=models.PROTECT,
        related_name="note",
    )
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["is_active", "updated_at"], name="notes_active_time_idx"),
        ]

    def __str__(self):
        return self.title
