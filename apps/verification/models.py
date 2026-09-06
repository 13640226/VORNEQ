from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.evidence.models import Claim, EvidenceRelation


ALLOWED_ARTIFACT_MODELS = {
    ("marketplace", "product"),
    ("library", "libraryitem"),
}


class VerificationMethod(models.Model):
    """A named protocol used to perform a verification."""

    class Mode(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATED = "automated", "Automated"
        HYBRID = "hybrid", "Hybrid"

    code = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    mode = models.CharField(
        max_length=20,
        choices=Mode.choices,
        default=Mode.MANUAL,
    )
    version = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    metadata_schema = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.name


class VerificationRequest(models.Model):
    """Workflow request to assess a canonical Claim for one artifact."""

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    artifact_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="verification_requests",
    )
    artifact_object_id = models.CharField(max_length=255)
    artifact = GenericForeignKey(
        "artifact_content_type",
        "artifact_object_id",
        for_concrete_model=False,
    )
    claim = models.ForeignKey(
        Claim,
        on_delete=models.PROTECT,
        related_name="verification_requests",
    )
    method = models.ForeignKey(
        VerificationMethod,
        on_delete=models.PROTECT,
        related_name="requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="verify_req_status_time_idx",
            ),
            models.Index(
                fields=["artifact_content_type", "artifact_object_id"],
                name="verify_req_artifact_idx",
            ),
            models.Index(fields=["claim"], name="verify_req_claim_idx"),
        ]

    def clean(self):
        super().clean()

        content_type = self.artifact_content_type
        if content_type is None:
            return

        key = (content_type.app_label, content_type.model)
        if key not in ALLOWED_ARTIFACT_MODELS:
            raise ValidationError(
                {
                    "artifact_content_type": (
                        "Artifact type is not supported by Verification V1."
                    )
                }
            )

        if not self.artifact_object_id:
            raise ValidationError(
                {"artifact_object_id": "Artifact object id is required."}
            )

        try:
            content_type.get_object_for_this_type(pk=self.artifact_object_id)
        except (ObjectDoesNotExist, ValueError, TypeError):
            raise ValidationError(
                {"artifact_object_id": "Referenced artifact does not exist."}
            )

    def __str__(self):
        return f"{self.claim} via {self.method} ({self.status})"


class VerificationResult(models.Model):
    """One verifier's scoped assertion for a VerificationRequest."""

    class Outcome(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        PARTIAL = "partial", "Partial"
        INCONCLUSIVE = "inconclusive", "Inconclusive"

    request = models.ForeignKey(
        VerificationRequest,
        on_delete=models.PROTECT,
        related_name="results",
    )
    verifier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_results",
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    reported_confidence = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Verifier-reported confidence from 0 to 100.",
    )
    summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["request", "outcome"],
                name="verify_result_req_out_idx",
            ),
            models.Index(
                fields=["verifier", "created_at"],
                name="verify_result_actor_idx",
            ),
        ]

    def __str__(self):
        return f"{self.request_id}: {self.outcome} ({self.reported_confidence}%)"


class VerificationEvidence(models.Model):
    """Context-specific visibility policy for canonical EvidenceRelation."""

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        PARTICIPANTS = "participants", "Participants"
        PUBLIC = "public", "Public"

    result = models.ForeignKey(
        VerificationResult,
        on_delete=models.CASCADE,
        related_name="evidence_links",
    )
    evidence_relation = models.ForeignKey(
        EvidenceRelation,
        on_delete=models.PROTECT,
        related_name="verification_links",
    )
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["result", "evidence_relation"],
                name="uniq_verify_result_evidence_relation",
            )
        ]
        indexes = [
            models.Index(
                fields=["result", "visibility"],
                name="verify_evidence_visibility_idx",
            ),
            models.Index(
                fields=["evidence_relation"],
                name="verify_evidence_relation_idx",
            ),
        ]

    @property
    def evidence(self):
        return self.evidence_relation.evidence

    def clean(self):
        super().clean()

        if not self.result_id or not self.evidence_relation_id:
            return

        request_claim_id = self.result.request.claim_id
        if self.evidence_relation.claim_id != request_claim_id:
            raise ValidationError(
                {
                    "evidence_relation": (
                        "EvidenceRelation must belong to the VerificationRequest claim."
                    )
                }
            )

    def __str__(self):
        return (
            f"{self.evidence_relation_id} -> {self.result_id} "
            f"({self.visibility})"
        )
