import uuid

from django.conf import settings
from django.db import models

from .claim import Claim
from .evidence import Evidence


class EvidenceRelation(models.Model):
    """
    Canonical interpretation between a Claim and Evidence.

    A relation is not a verdict.

    Canonical fields are immutable after creation.
    retired_at is the only field allowed to change after creation,
    and should be changed through RelationService.
    """

    class RelationType(models.TextChoices):
        SUPPORTS = "supports", "Supports"
        CONTRADICTS = "contradicts", "Contradicts"
        CONTEXTUALIZES = "contextualizes", "Contextualizes"
        UNCLEAR = "unclear", "Unclear"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    claim = models.ForeignKey(
        Claim,
        on_delete=models.PROTECT,
        related_name="relations",
        verbose_name="ادعا",
    )

    evidence = models.ForeignKey(
        Evidence,
        on_delete=models.PROTECT,
        related_name="relations",
        verbose_name="شاهد",
    )

    supersedes = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_by",
        verbose_name="رابطه قبلی",
    )

    retired_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان بازنشستگی",
    )

    relation = models.CharField(
        max_length=20,
        choices=RelationType.choices,
        verbose_name="نوع رابطه",
    )

    relation_basis = models.TextField(
        blank=True,
        verbose_name="مبنای رابطه",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evidence_relations_created",
        verbose_name="ایجادکننده",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد",
    )

    class Meta:
        verbose_name = "رابطه شاهد و ادعا"
        verbose_name_plural = "روابط شاهد و ادعا"

        ordering = [
            "-created_at",
            "-id",
        ]

        indexes = [
            models.Index(
                fields=["claim", "evidence"],
                name="evrel_claim_evidence_idx",
            ),
            models.Index(
                fields=["retired_at"],
                name="evrel_retired_at_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["claim", "evidence"],
                condition=models.Q(
                    retired_at__isnull=True
                ),
                name="evrel_one_active_per_pair",
            ),
        ]

    def __str__(self):
        return (
            f"{self.claim_id} "
            f"{self.relation} "
            f"{self.evidence_id}"
        )

    def _changed_fields(self):
        """
        Return concrete fields changed relative to persisted state.
        """

        if self._state.adding:
            return set()

        persisted = type(self).objects.get(
            pk=self.pk
        )

        changed = set()

        for field in self._meta.concrete_fields:
            old_value = getattr(
                persisted,
                field.attname,
            )
            new_value = getattr(
                self,
                field.attname,
            )

            if old_value != new_value:
                changed.add(field.name)

        return changed

    def save(self, *args, **kwargs):
        """
        Canonical fields are immutable after creation.

        Only retired_at may change.
        """

        if not self._state.adding:
            forbidden = (
                self._changed_fields()
                - {"retired_at"}
            )

            if forbidden:
                fields = ", ".join(
                    sorted(forbidden)
                )

                raise RuntimeError(
                    "EvidenceRelation canonical fields are "
                    "immutable after creation. "
                    f"Changed fields: {fields}"
                )

        return super().save(
            *args,
            **kwargs,
        )