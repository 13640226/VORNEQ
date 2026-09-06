import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .evidence import Evidence
from .provenance import ProvenanceStep


class SignatureEnvelope(models.Model):
    """Append-only cryptographic signature over one supported trust object.

    The signed target remains the canonical source of domain data. This envelope
    stores only the cryptographic assertion, the digest of the canonical payload,
    and key metadata so key rotation can create new signatures without mutating
    Evidence, ProvenanceStep, or VerificationResult rows.
    """

    class Algorithm(models.TextChoices):
        ED25519 = "ed25519", "Ed25519"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evidence = models.ForeignKey(
        Evidence,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="signature_envelopes",
    )
    provenance_step = models.ForeignKey(
        ProvenanceStep,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="signature_envelopes",
    )
    verification_result = models.ForeignKey(
        "verification.VerificationResult",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="signature_envelopes",
    )
    key_id = models.CharField(max_length=120)
    algorithm = models.CharField(
        max_length=20,
        choices=Algorithm.choices,
        default=Algorithm.ED25519,
    )
    canonical_version = models.CharField(max_length=40, default="trust-signature-v1")
    payload_digest = models.CharField(max_length=64)
    signature = models.TextField()
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-signed_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(evidence__isnull=False, provenance_step__isnull=True, verification_result__isnull=True)
                    | Q(evidence__isnull=True, provenance_step__isnull=False, verification_result__isnull=True)
                    | Q(evidence__isnull=True, provenance_step__isnull=True, verification_result__isnull=False)
                ),
                name="evidence_signature_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["evidence", "key_id", "canonical_version", "payload_digest"],
                condition=Q(evidence__isnull=False),
                name="evidence_signature_evidence_unique",
            ),
            models.UniqueConstraint(
                fields=["provenance_step", "key_id", "canonical_version", "payload_digest"],
                condition=Q(provenance_step__isnull=False),
                name="evidence_signature_provenance_unique",
            ),
            models.UniqueConstraint(
                fields=["verification_result", "key_id", "canonical_version", "payload_digest"],
                condition=Q(verification_result__isnull=False),
                name="evidence_signature_verification_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["key_id", "signed_at"], name="sig_key_time_idx"),
            models.Index(fields=["payload_digest"], name="sig_digest_idx"),
        ]

    @property
    def target(self):
        return self.evidence or self.provenance_step or self.verification_result

    def clean(self):
        super().clean()
        targets = [self.evidence_id, self.provenance_step_id, self.verification_result_id]
        if sum(value is not None for value in targets) != 1:
            raise ValidationError("SignatureEnvelope must target exactly one supported object.")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("SignatureEnvelope is append-only and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("SignatureEnvelope is append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.algorithm}:{self.key_id}:{self.payload_digest[:12]}"
