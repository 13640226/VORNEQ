from django.db import models


class LibraryItem(models.Model):
    title = models.CharField(
        max_length=200,
        verbose_name="عنوان",
    )

    slug = models.SlugField(
        max_length=220,
        unique=True,
        verbose_name="نامک",
    )

    icon = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="آیکون",
    )

    category = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="دسته‌بندی",
    )

    version = models.CharField(
        max_length=20,
        blank=True,
        default="v1.0",
        verbose_name="نسخه",
    )

    short_description = models.TextField(
        blank=True,
        default="",
        verbose_name="توضیح کوتاه",
    )

    content = models.TextField(
        blank=True,
        default="",
        verbose_name="محتوا",
    )

    is_published = models.BooleanField(
        default=True,
        verbose_name="منتشر شده",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین بروزرسانی",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "سند کتابخانه"
        verbose_name_plural = "اسناد کتابخانه"

    def __str__(self):
        return self.title


class AudioItem(models.Model):
    COVER_DIALOGUE = "dialogue"
    COVER_ANALYSIS = "analysis"
    COVER_METHOD = "method"

    COVER_CHOICES = [
        (COVER_DIALOGUE, "گفت‌وگو"),
        (COVER_ANALYSIS, "تحلیل"),
        (COVER_METHOD, "روش"),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان",
    )

    description = models.TextField(
        blank=True,
        default="",
        verbose_name="توضیحات",
    )

    cover_type = models.CharField(
        max_length=30,
        choices=COVER_CHOICES,
        default=COVER_DIALOGUE,
        verbose_name="نوع کاور",
    )

    audio_file = models.FileField(
        upload_to="audio/",
        blank=True,
        null=True,
        verbose_name="فایل صوتی",
    )

    mime_type = models.CharField(
        max_length=50,
        blank=True,
        default="audio/mpeg",
        verbose_name="نوع فایل",
    )

    is_published = models.BooleanField(
        default=True,
        verbose_name="منتشر شده",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین بروزرسانی",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "محتوای صوتی"
        verbose_name_plural = "محتواهای صوتی"

    def __str__(self):
        return self.title