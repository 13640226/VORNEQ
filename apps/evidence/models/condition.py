import uuid

from django.db import models
from django.utils import timezone

from .claim import Claim
from .evidence import Evidence


class ChangeCondition(models.Model):
    """
    شرطی که در صورت تغییر وضعیت آن، ممکن است نیاز به
    بازنگری یک Claim ایجاد شود.

    ChangeCondition خودش verdict یا assessment نیست.
    وضعیت operational آن از ConditionObservation مشتق می‌شود.
    """

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    claim = models.ForeignKey(
        Claim,
        on_delete=models.PROTECT,
        related_name="change_conditions",
        verbose_name="ادعا",
    )

    description = models.TextField(
        verbose_name="شرح شرط",
    )

    evidence_required = models.TextField(
        blank=True,
        verbose_name="شاهد موردنیاز",
    )

    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.MEDIUM,
        verbose_name="شدت",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین به‌روزرسانی",
    )

    class Meta:
        verbose_name = "شرط تغییر"
        verbose_name_plural = "شرایط تغییر"
        ordering = [
            "-created_at",
            "-id",
        ]

    def __str__(self):
        return self.description[:100]


class ConditionObservation(models.Model):
    """
    مشاهده‌ی وضعیت یک ChangeCondition در یک لحظه مشخص.

    این مدل assessment یا verdict ایجاد نمی‌کند.
    وضعیت جاری Condition از آخرین Observation مشتق می‌شود.
    """

    class ObservedState(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        NOT_OBSERVED = "not_observed", "Not Observed"
        POSSIBLY_MET = "possibly_met", "Possibly Met"
        MET = "met", "Met"
        DISPUTED = "disputed", "Disputed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    condition = models.ForeignKey(
        ChangeCondition,
        on_delete=models.PROTECT,
        related_name="observations",
        verbose_name="شرط",
    )

    observed_state = models.CharField(
        max_length=20,
        choices=ObservedState.choices,
        default=ObservedState.UNKNOWN,
        verbose_name="وضعیت مشاهده‌شده",
    )

    evidence_ref = models.ForeignKey(
        Evidence,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="condition_observations",
        verbose_name="شاهد مرتبط",
    )

    observer_actor = models.CharField(
        max_length=255,
        verbose_name="عامل مشاهده‌گر",
    )

    observed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="زمان مشاهده",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="یادداشت",
    )

    class Meta:
        verbose_name = "مشاهده شرط"
        verbose_name_plural = "مشاهدات شرایط"
        ordering = [
            "-observed_at",
            "-id",
        ]

    def __str__(self):
        return (
            f"{self.condition_id}: "
            f"{self.observed_state}"
        )