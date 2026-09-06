from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


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


class ContextualReputation(models.Model):
    """Method- and domain-scoped reputation projection.

    Verification activity and scored quality signals are recorded as immutable
    events. This row is only the current projection of those events.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contextual_reputations",
    )
    domain = models.SlugField(max_length=100)
    verification_method = models.ForeignKey(
        "verification.VerificationMethod",
        on_delete=models.PROTECT,
        related_name="contextual_reputations",
    )
    score = models.FloatField(default=0.0)
    sample_count = models.PositiveIntegerField(default=0)
    last_event_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id", "domain", "verification_method_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "domain", "verification_method"],
                name="core_ctx_rep_user_domain_method_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "domain"],
                name="core_ctx_rep_user_domain_idx",
            ),
            models.Index(
                fields=["verification_method", "last_event_at"],
                name="core_ctx_rep_method_time_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.domain}:{self.verification_method_id}"


class QualitySignal(models.Model):
    """Append-only quality assessment signal for one VerificationResult.

    Eligibility is a versioned policy decision, not a truth claim and not a score.
    The canonical Evidence/Claim relationship stays in apps.evidence.
    """

    class SignalType(models.TextChoices):
        EXTERNAL_REFERENCE = "external_reference", "External reference"
        REPRODUCIBILITY = "reproducibility", "Reproducibility"
        ADJUDICATION = "adjudication", "Adjudication"
        INDEPENDENT_CORROBORATION = (
            "independent_corroboration",
            "Independent corroboration",
        )
        PROXY_STATISTICAL = "proxy_statistical", "Statistical or proxy"
        CONTESTATION_CORRECTION = (
            "contestation_correction",
            "Contestation or correction",
        )
        CONSENSUS = "consensus", "Consensus"

    class Direction(models.TextChoices):
        SUPPORTS_RESULT = "supports_result", "Supports result"
        CONTRADICTS_RESULT = "contradicts_result", "Contradicts result"
        INCONCLUSIVE = "inconclusive", "Inconclusive"

    verification_result = models.ForeignKey(
        "verification.VerificationResult",
        on_delete=models.PROTECT,
        related_name="quality_signals",
    )
    signal_type = models.CharField(max_length=50, choices=SignalType.choices)
    direction = models.CharField(
        max_length=30,
        choices=Direction.choices,
        default=Direction.INCONCLUSIVE,
    )
    assessor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_signals_assessed",
    )
    source_ref = models.CharField(max_length=255)
    provenance_ref = models.CharField(max_length=500, blank=True)
    evidence_relation = models.ForeignKey(
        "evidence.EvidenceRelation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quality_signals",
    )
    independence_declared = models.BooleanField(default=False)
    independence_basis = models.TextField(blank=True)
    domain = models.SlugField(max_length=100)
    method = models.ForeignKey(
        "verification.VerificationMethod",
        on_delete=models.PROTECT,
        related_name="quality_signals",
    )
    observed_at = models.DateTimeField(default=timezone.now)
    policy_version = models.CharField(max_length=40, default="eligibility-v1")
    is_eligible = models.BooleanField(default=False, editable=False)
    eligibility_reasons = models.JSONField(default=list, blank=True, editable=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "verification_result",
                    "signal_type",
                    "source_ref",
                    "method",
                    "policy_version",
                ],
                name="core_quality_signal_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["verification_result", "signal_type"],
                name="core_quality_result_type_idx",
            ),
            models.Index(
                fields=["domain", "method"],
                name="core_quality_domain_method_idx",
            ),
            models.Index(
                fields=["is_eligible", "created_at"],
                name="core_quality_eligible_time_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("QualitySignal is append-only and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("QualitySignal is append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.signal_type}:{self.source_ref}:{self.is_eligible}"


class ScoringPolicy(models.Model):
    """Immutable, versioned interpretation policy for contextual reputation."""

    domain = models.SlugField(max_length=100)
    verification_method = models.ForeignKey(
        "verification.VerificationMethod",
        on_delete=models.PROTECT,
        related_name="scoring_policies",
    )
    version = models.CharField(max_length=40)
    active = models.BooleanField(default=False)
    direction_weights = models.JSONField(default=dict)
    base_weight = models.FloatField(default=1.0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["domain", "verification_method_id", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["domain", "verification_method", "version"],
                name="core_score_policy_scope_version_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["domain", "verification_method", "version"],
                name="core_score_policy_scope_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("ScoringPolicy is immutable; create a new version instead.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("ScoringPolicy is immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.domain}:{self.verification_method_id}:{self.version}"


class ContextualReputationEvent(models.Model):
    """Append-only audit event for contextual reputation activity and scoring."""

    class EventType(models.TextChoices):
        VERIFICATION_SUBMITTED = "verification_submitted", "Verification submitted"
        SCORE_APPLIED = "score_applied", "Score applied"

    contextual_reputation = models.ForeignKey(
        ContextualReputation,
        on_delete=models.PROTECT,
        related_name="events",
    )
    verification_result = models.ForeignKey(
        "verification.VerificationResult",
        on_delete=models.PROTECT,
        related_name="reputation_events",
    )
    quality_signal = models.ForeignKey(
        QualitySignal,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reputation_events",
    )
    scoring_policy = models.ForeignKey(
        ScoringPolicy,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reputation_events",
    )
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        default=EventType.VERIFICATION_SUBMITTED,
    )
    old_score = models.FloatField(null=True, blank=True)
    delta = models.FloatField(null=True, blank=True)
    new_score = models.FloatField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["contextual_reputation", "verification_result", "event_type"],
                condition=Q(event_type="verification_submitted"),
                name="core_ctx_rep_activity_unique",
            ),
            models.UniqueConstraint(
                fields=["contextual_reputation", "quality_signal", "scoring_policy"],
                condition=Q(event_type="score_applied"),
                name="core_ctx_rep_score_event_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["contextual_reputation", "created_at"],
                name="core_ctx_rep_event_time_idx",
            ),
            models.Index(
                fields=["verification_result"],
                name="core_ctx_rep_result_idx",
            ),
            models.Index(
                fields=["quality_signal", "scoring_policy"],
                name="core_ctx_rep_score_signal_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError(
                "ContextualReputationEvent is append-only and cannot be updated."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError(
            "ContextualReputationEvent is append-only and cannot be deleted."
        )

    def __str__(self):
        return f"{self.contextual_reputation_id}:{self.event_type}:{self.verification_result_id}"


class Entitlement(models.Model):
    """Proof of a user's right to access a digital product."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entitlements",
    )
    product = models.ForeignKey(
        "marketplace.Product",
        on_delete=models.CASCADE,
        related_name="entitlements",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="core_ent_user_product_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "product", "is_active"],
                name="core_ent_user_prod_active_idx",
            ),
            models.Index(
                fields=["expires_at"],
                name="core_ent_expires_idx",
            ),
        ]

    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() >= self.expires_at:
            return False
        return True

    def __str__(self):
        return f"{self.user_id} -> product:{self.product_id}"
