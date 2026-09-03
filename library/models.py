from django.db import models


class LibraryItem(models.Model):
    TYPE_CHOICES = [
        ("book", "کتاب"),
        ("article", "مقاله"),
        ("document", "سند"),
        ("other", "سایر"),
    ]

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

    allow_public_reading = models.BooleanField(default=True)

    item_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="other",
    )

    title_en = models.CharField(max_length=200, blank=True, default="")
    title_de = models.CharField(max_length=200, blank=True, default="")
    short_description_en = models.TextField(blank=True, default="")
    short_description_de = models.TextField(blank=True, default="")
    content_en = models.TextField(blank=True, default="")
    content_de = models.TextField(blank=True, default="")
    author = models.CharField(max_length=200, blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)
    pdf_file = models.FileField(
        upload_to="library/pdfs/",
        blank=True,
        null=True,
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

    def get_title(self, lang="fa"):
        if lang == "en" and self.title_en:
            return self.title_en
        if lang == "de" and self.title_de:
            return self.title_de
        return self.title

    def get_short_description(self, lang="fa"):
        if lang == "en" and self.short_description_en:
            return self.short_description_en
        if lang == "de" and self.short_description_de:
            return self.short_description_de
        return self.short_description

    def get_content(self, lang="fa"):
        if lang == "en" and self.content_en:
            return self.content_en
        if lang == "de" and self.content_de:
            return self.content_de
        return self.content

    @property
    def has_pdf(self):
        return bool(self.pdf_file)


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
