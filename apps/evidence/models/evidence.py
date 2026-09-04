import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Evidence(models.Model):
    """
    یک شاهد canonical در دامنه Evidence.

    Evidence خودش Truth یا Verdict نیست.

    فیلدهای canonical پس از ایجاد immutable هستند.
    metadata غیر-canonical است و می‌تواند بعداً به‌روزرسانی شود.

    تغییر مادی در محتوا باید با ایجاد Evidence جدید و
    Provenance جدید ثبت شود.
    """

    class ContentType(models.TextChoices):
        TEXT = "text", "Text"
        URL = "url", "URL"
        FILE = "file", "File"
        IMAGE = "image", "Image"
        DATA = "data", "Data"
        OTHER = "other", "Other"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    content = models.TextField(
        verbose_name="محتوای شاهد",
    )

    content_type = models.CharField(
        max_length=50,
        choices=ContentType.choices,
        default=ContentType.TEXT,
        verbose_name="نوع محتوا",
    )

    observed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="زمان مشاهده",
    )

    integrity_digest = models.CharField(
        max_length=64,
        verbose_name="هش یکپارچگی",
        help_text="SHA-256 digest of canonical Evidence content.",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="فراداده",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evidence_created",
        verbose_name="ایجادکننده",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد",
    )

    class Meta:
        verbose_name = "شاهد"
        verbose_name_plural = "شواهد"
        ordering = [
            "-created_at",
            "-id",
        ]
        indexes = [
            models.Index(
                fields=["content_type"],
                name="evidence_content_type_idx",
            ),
            models.Index(
                fields=["observed_at"],
                name="evidence_observed_at_idx",
            ),
            models.Index(
                fields=["integrity_digest"],
                name="evidence_digest_idx",
            ),
        ]

    def __str__(self):
        preview = self.content.replace("\n", " ").strip()

        if len(preview) > 80:
            preview = f"{preview[:77]}..."

        return f"{self.content_type}: {preview}"

    def _changed_fields(self):
        """
        فیلدهایی که نسبت به رکورد ذخیره‌شده تغییر کرده‌اند.

        هنگام creation مجموعه خالی برگردانده می‌شود.
        """

        if self._state.adding:
            return set()

        persisted = type(self).objects.get(
            pk=self.pk,
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
        پس از ایجاد فقط metadata اجازه تغییر دارد.

        فیلدهای canonical زیر immutable هستند:

        - content
        - content_type
        - observed_at
        - integrity_digest
        - created_by
        - created_at
        """

        if not self._state.adding:
            changed = self._changed_fields()

            forbidden = changed - {
                "metadata",
            }

            if forbidden:
                fields = ", ".join(
                    sorted(forbidden)
                )

                raise RuntimeError(
                    "Evidence canonical fields are immutable "
                    "after creation. "
                    f"Changed fields: {fields}"
                )

        return super().save(
            *args,
            **kwargs,
        )