from django.db import models

from .claim import Claim
from .review import ReviewRecord


class AssessmentSnapshot(models.Model):
    """
    Cache مشتق‌شده از ReviewRecord برای وضعیت جاری Claim.

    AssessmentSnapshot منبع حقیقت نیست.
    در صورت مغایرت، ReviewRecord authoritative است.
    """

    claim = models.OneToOneField(
        Claim,
        on_delete=models.PROTECT,
        related_name="assessment_snapshot",
        primary_key=True,
        verbose_name="ادعا",
    )

    current_assessment = models.CharField(
        max_length=100,
        verbose_name="ارزیابی جاری",
    )

    snapshot_at = models.DateTimeField(
        verbose_name="زمان Snapshot",
    )

    derived_from = models.ForeignKey(
        ReviewRecord,
        on_delete=models.PROTECT,
        related_name="derived_assessment_snapshots",
        verbose_name="رکورد مبنا",
    )

    digest = models.CharField(
        max_length=64,
        verbose_name="هش Snapshot",
    )

    digest_version = models.CharField(
        max_length=10,
        default="v1",
        verbose_name="نسخه هش",
    )

    class Meta:
        verbose_name = "Snapshot ارزیابی"
        verbose_name_plural = "Snapshotهای ارزیابی"

    def __str__(self):
        return f"{self.claim_id}: {self.current_assessment}"