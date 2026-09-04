import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .claim import Claim
from .relation import EvidenceRelation


class Critique(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey(
        Claim,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="critiques",
    )
    relation = models.ForeignKey(
        EvidenceRelation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="critiques",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="critiques_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(claim__isnull=False, relation__isnull=True)
                    | models.Q(claim__isnull=True, relation__isnull=False)
                ),
                name="critique_exactly_one_target",
            )
        ]

    def clean(self):
        super().clean()
        if (self.claim_id is None) == (self.relation_id is None):
            raise ValidationError("Critique must target exactly one Claim or EvidenceRelation.")

    def __str__(self):
        target = self.claim_id or self.relation_id
        return f"Critique {self.id} -> {target}"
