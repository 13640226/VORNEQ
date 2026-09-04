from django.conf import settings
from django.db import models


class Reputation(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reputation",
    )
    accuracy_score = models.FloatField(default=0.0)
    corrigibility_score = models.FloatField(default=0.0)
    source_quality_score = models.FloatField(default=0.0)
    fair_critique_score = models.FloatField(default=0.0)
    domain_expertise_score = models.FloatField(default=0.0)
    prediction_accuracy_score = models.FloatField(default=0.0)
    social_behavior_score = models.FloatField(default=0.0)
    overall_score = models.FloatField(default=0.0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "last_updated"], name="core_rep_user_time_idx"),
        ]

    def update_overall(self):
        values = [
            self.accuracy_score,
            self.corrigibility_score,
            self.source_quality_score,
            self.fair_critique_score,
            self.domain_expertise_score,
            self.prediction_accuracy_score,
            self.social_behavior_score,
        ]
        self.overall_score = sum(values) / len(values)

    def __str__(self):
        return f"{self.user} reputation"


class ReputationHistory(models.Model):
    class Dimension(models.TextChoices):
        ACCURACY = "accuracy", "Accuracy"
        CORRIGIBILITY = "corrigibility", "Corrigibility"
        SOURCE_QUALITY = "source_quality", "Source Quality"
        FAIR_CRITIQUE = "fair_critique", "Fair Critique"
        DOMAIN_EXPERTISE = "domain_expertise", "Domain Expertise"
        PREDICTION_ACCURACY = "prediction_accuracy", "Prediction Accuracy"
        SOCIAL_BEHAVIOR = "social_behavior", "Social Behavior"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reputation_history",
    )
    dimension = models.CharField(max_length=30, choices=Dimension.choices)
    old_value = models.FloatField()
    new_value = models.FloatField()
    event_type = models.CharField(max_length=80)
    event_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["user", "dimension", "created_at"],
                name="core_rep_hist_user_dim_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dimension", "event_type", "event_id"],
                name="core_rep_hist_event_unique",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("ReputationHistory is append-only and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("ReputationHistory is append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.user_id} {self.dimension}: {self.old_value} -> {self.new_value}"
