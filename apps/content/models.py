import hashlib
import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def _stable_slug(value, *, max_length, queryset, pk_suffix=None):
    base = slugify(value) or "item"
    base = base[:max_length]
    if not queryset.filter(slug=base).exists():
        return base

    if pk_suffix is None:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    else:
        digest = str(pk_suffix).replace("-", "")[:8]

    trimmed = base[: max_length - len(digest) - 1]
    return f"{trimmed}-{digest}"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        ordering = ["name", "id"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _stable_slug(
                self.name,
                max_length=self._meta.get_field("slug").max_length,
                queryset=Category.objects.all(),
            )
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)

    class Meta:
        ordering = ["name", "id"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _stable_slug(
                self.name,
                max_length=self._meta.get_field("slug").max_length,
                queryset=Tag.objects.all(),
            )
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Article(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    summary = models.TextField(max_length=500)
    content = models.TextField()
    image = models.ImageField(
        upload_to="articles/%Y/%m/%d/",
        blank=True,
        null=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="articles",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="articles")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    editorial_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(
                fields=["is_published", "published_at"],
                name="content_art_pub_time_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _stable_slug(
                self.title,
                max_length=self._meta.get_field("slug").max_length,
                queryset=Article.objects.all(),
                pk_suffix=self.pk,
            )
        if self.is_published and self.published_at is None:
            self.published_at = timezone.now()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title
