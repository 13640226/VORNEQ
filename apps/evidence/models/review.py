import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.evidence.managers.review import ReviewRecordManager


class ReviewRecord(models.Model):
    """
    رویداد canonical بازنگری.

    ReviewRecord منبع حقیقت برای stateهای مشتق‌شده از Review است.
    این مدل append-only است.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="evidence_review_records",
        verbose_name="نوع موجودیت",
    )

    object_id = models.CharField(
        max_length=255,
        verbose_name="شناسه موجودیت",
    )

    target = GenericForeignKey(
        "content_type",
        "object_id",
        for_concrete_model=False,
    )

    reviewer_actor = models.CharField(
        max_length=255,
        verbose_name="عامل بازنگری",
    )

    previous_state = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="وضعیت قبلی",
    )

    new_state = models.CharField(
        max_length=100,
        verbose_name="وضعیت جدید",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="یادداشت",
    )

    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="زمان بازنگری",
    )

    change_conditions_met = models.JSONField(
        default=list,
        blank=True,
        verbose_name="شرایط تغییر مرتبط",
    )

    objects = ReviewRecordManager()

    class Meta:
        verbose_name = "رکورد بازنگری"
        verbose_name_plural = "رکوردهای بازنگری"
        ordering = [
            "-timestamp",
            "-id",
        ]
        indexes = [
            models.Index(
                fields=[
                    "content_type",
                    "object_id",
                    "-timestamp",
                    "-id",
                ],
                name="evidence_review_target_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.content_type_id}:{self.object_id} "
            f"{self.previous_state} -> {self.new_state}"
        )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError(
                "ReviewRecord is append-only; update is forbidden"
            )

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError(
            "ReviewRecord is append-only; delete is forbidden"
        )