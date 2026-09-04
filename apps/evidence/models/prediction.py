import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .claim import Claim
from .evidence import Evidence


class Prediction(models.Model):
    """Append-only probabilistic forecast attached to a Claim."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey(
        Claim,
        on_delete=models.PROTECT,
        related_name="predictions",
    )
    event_statement = models.TextField(
        help_text="A falsifiable event that can be resolved as occurred or did not occur.",
    )
    probability = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Forecast probability from 0 to 1.",
    )
    resolution_date = models.DateTimeField()
    rationale = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predictions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["resolution_date", "created_at", "id"]
        indexes = [
            models.Index(fields=["claim", "resolution_date"], name="prediction_claim_due_idx"),
            models.Index(fields=["created_by", "created_at"], name="prediction_author_time_idx"),
        ]

    def clean(self):
        super().clean()
        if self._state.adding and self.resolution_date <= timezone.now():
            from django.core.exceptions import ValidationError

            raise ValidationError({"resolution_date": "Resolution date must be in the future."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Prediction is append-only and cannot be updated.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Prediction is append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.event_statement[:80]} ({self.probability})"


class PredictionResolution(models.Model):
    """Immutable resolution for one Prediction."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prediction = models.OneToOneField(
        Prediction,
        on_delete=models.PROTECT,
        related_name="resolution",
    )
    outcome_occurred = models.BooleanField()
    evidence_ref = models.ForeignKey(
        Evidence,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prediction_resolutions",
    )
    notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prediction_resolutions_created",
    )
    resolved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["resolved_at", "id"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("PredictionResolution is immutable and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("PredictionResolution is immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.prediction_id}: {self.outcome_occurred}"
