import uuid

from django.conf import settings
from django.db import models


class Claim(models.Model):
    """Canonical claim that can be assessed against evidence."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    claim_text = models.TextField(
        verbose_name="متن ادعا",
    )

    scope = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="دامنه یا زمینه",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claims_created",
        verbose_name="ایجادکننده",
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
        verbose_name = "ادعا"
        verbose_name_plural = "ادعاها"
        ordering = ["-created_at"]

    def __str__(self):
        return self.claim_text[:100]