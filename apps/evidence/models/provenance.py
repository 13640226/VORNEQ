import uuid

from django.db import models
from django.utils import timezone

from .evidence import Evidence


class ProvenanceStep(models.Model):
    """
    یک گام در زنجیره منشأ Evidence.

    هر ProvenanceStep توضیح می‌دهد Evidence از کجا آمده،
    چه تبدیلی روی آن انجام شده و چه زمانی ثبت شده است.

    Provenance تاریخچه canonical است و پس از ایجاد immutable است.
    """

    class SourceType(models.TextChoices):
        HUMAN = "human", "Human"
        SYSTEM = "system", "System"
        DOCUMENT = "document", "Document"
        SENSOR = "sensor", "Sensor"
        ALGORITHM = "algorithm", "Algorithm"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    evidence = models.ForeignKey(
        Evidence,
        on_delete=models.PROTECT,
        related_name="provenance_chain",
        verbose_name="شاهد",
    )

    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        verbose_name="نوع منبع",
    )

    source_ref = models.CharField(
        max_length=255,
        verbose_name="ارجاع منبع",
    )

    transformation = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="تبدیل",
    )

    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="زمان",
    )

    note = models.TextField(
        blank=True,
        verbose_name="یادداشت",
    )

    class Meta:
        verbose_name = "گام منشأ"
        verbose_name_plural = "گام‌های منشأ"
        ordering = [
            "timestamp",
            "id",
        ]
        indexes = [
            models.Index(
                fields=["evidence", "timestamp"],
                name="prov_evidence_time_idx",
            ),
        ]

    def __str__(self):
        return f"{self.evidence_id}: {self.source_type}"

    def save(self, *args, **kwargs):
        """
        ProvenanceStep پس از ایجاد immutable است.
        """

        if not self._state.adding:
            raise RuntimeError(
                "ProvenanceStep is immutable after creation"
            )

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError(
            "ProvenanceStep is immutable and cannot be deleted"
        )