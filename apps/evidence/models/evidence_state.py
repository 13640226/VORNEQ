from django.db import models

from .claim import Claim
from .relation import EvidenceRelation


class EvidenceState(models.Model):
    """Derived read model summarizing active evidence relations for a claim."""

    class State(models.TextChoices):
        NO_EVIDENCE = "no_evidence", "No evidence"
        SUPPORTING_ONLY = "supporting_only", "Supporting only"
        CONTRADICTING_ONLY = "contradicting_only", "Contradicting only"
        NEUTRAL_ONLY = "neutral_only", "Neutral only"
        SUPPORTING_NEUTRAL = "supporting_neutral", "Supporting + neutral"
        CONTRADICTING_NEUTRAL = "contradicting_neutral", "Contradicting + neutral"
        MIXED = "mixed", "Mixed"

    claim = models.OneToOneField(
        Claim,
        on_delete=models.CASCADE,
        related_name="evidence_state",
        primary_key=True,
    )
    state = models.CharField(max_length=32, choices=State.choices, default=State.NO_EVIDENCE)
    supporting_count = models.PositiveIntegerField(default=0)
    contradicting_count = models.PositiveIntegerField(default=0)
    neutral_count = models.PositiveIntegerField(default=0)
    evidence_count = models.PositiveIntegerField(default=0)
    refreshed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Evidence state"
        verbose_name_plural = "Evidence states"

    @classmethod
    def derive_values(cls, claim):
        active = EvidenceRelation.objects.filter(claim=claim, retired_at__isnull=True)
        supporting = active.filter(relation=EvidenceRelation.RelationType.SUPPORTS).count()
        contradicting = active.filter(relation=EvidenceRelation.RelationType.CONTRADICTS).count()
        neutral = active.filter(
            relation__in=[
                EvidenceRelation.RelationType.CONTEXTUALIZES,
                EvidenceRelation.RelationType.UNCLEAR,
            ]
        ).count()
        evidence_count = active.values("evidence_id").distinct().count()

        if not evidence_count:
            state = cls.State.NO_EVIDENCE
        elif supporting and contradicting:
            state = cls.State.MIXED
        elif supporting and neutral:
            state = cls.State.SUPPORTING_NEUTRAL
        elif contradicting and neutral:
            state = cls.State.CONTRADICTING_NEUTRAL
        elif supporting:
            state = cls.State.SUPPORTING_ONLY
        elif contradicting:
            state = cls.State.CONTRADICTING_ONLY
        else:
            state = cls.State.NEUTRAL_ONLY

        return {
            "state": state,
            "supporting_count": supporting,
            "contradicting_count": contradicting,
            "neutral_count": neutral,
            "evidence_count": evidence_count,
        }

    @classmethod
    def update_for_claim(cls, claim):
        values = cls.derive_values(claim)
        obj, _ = cls.objects.update_or_create(claim=claim, defaults=values)
        return obj

    def __str__(self):
        return f"{self.claim_id}: {self.state}"
