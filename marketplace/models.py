"""
Marketplace models for Saman Kherad.

سامان خرد — بازار دیجیتال

Includes:
- Product
- ProductReview
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


# ============================================================
# PRODUCT
# ============================================================

class Product(models.Model):

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Pending review")),
        (STATUS_APPROVED, _("Approved")),
        (STATUS_REJECTED, _("Rejected")),
    ]


    # --------------------------------------------------------
    # Categories
    # --------------------------------------------------------

    CATEGORY_EBOOK = "ebook"
    CATEGORY_COURSE = "course"
    CATEGORY_AUDIO = "audio"
    CATEGORY_SOFTWARE = "software"
    CATEGORY_TEMPLATE = "template"
    CATEGORY_ARTWORK = "artwork"
    CATEGORY_OTHER = "other"

    CATEGORY_CHOICES = [
        (CATEGORY_EBOOK, _("E-book")),
        (CATEGORY_COURSE, _("Course")),
        (CATEGORY_AUDIO, _("Audio product")),
        (CATEGORY_SOFTWARE, _("Software")),
        (CATEGORY_TEMPLATE, _("Template")),
        (CATEGORY_ARTWORK, _("Artwork")),
        (CATEGORY_OTHER, _("Other")),
    ]


    # --------------------------------------------------------
    # Seller
    # --------------------------------------------------------

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="marketplace_products",
        verbose_name=_("Seller"),
    )


    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    title = models.CharField(
        max_length=250,
        verbose_name=_("Title"),
    )

    slug = models.SlugField(
        max_length=250,
        unique=True,
        blank=True,
        allow_unicode=True,
        verbose_name=_("Slug"),
    )


    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------

    short_description = models.TextField(
        blank=True,
        verbose_name=_("Short description"),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Full description"),
    )


    # --------------------------------------------------------
    # Classification
    # --------------------------------------------------------

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHER,
        verbose_name=_("Category"),
    )

    tags = models.CharField(
        max_length=250,
        blank=True,
        verbose_name=_("Tags"),
        help_text=_("Comma-separated tags"),
    )

    version = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_("Version"),
    )


    # --------------------------------------------------------
    # Price
    # --------------------------------------------------------

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
        ],
        verbose_name=_("Price"),
    )


    # --------------------------------------------------------
    # Product image
    # --------------------------------------------------------

    image = models.ImageField(
        upload_to="products/images/",
        blank=True,
        null=True,
        verbose_name=_("Product image"),
    )


    # --------------------------------------------------------
    # Protected digital file
    # --------------------------------------------------------

    digital_file = models.FileField(
        upload_to="products/files/",
        blank=True,
        null=True,
        verbose_name=_("Digital file"),
        help_text=_(
            "Protected product file. "
            "Do not expose digital_file.url in public templates."
        ),
    )


    # --------------------------------------------------------
    # Moderation
    # --------------------------------------------------------

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        verbose_name=_("Review status"),
    )


    # --------------------------------------------------------
    # Publication
    # --------------------------------------------------------

    is_published = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Published"),
        help_text=_(
            "The product is publicly visible only when "
            "it is both approved and published."
        ),
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Published at"),
    )


    # --------------------------------------------------------
    # Timestamps
    # --------------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated at"),
    )


    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    def save(self, *args, **kwargs):

        if not self.slug:

            base_slug = slugify(
                self.title,
                allow_unicode=True,
            )

            if not base_slug:
                base_slug = "product"

            candidate = base_slug
            counter = 2

            while (
                Product.objects
                .exclude(pk=self.pk)
                .filter(slug=candidate)
                .exists()
            ):
                candidate = f"{base_slug}-{counter}"
                counter += 1

            self.slug = candidate


        # Rejected or pending products must not remain public.
        if self.status != self.STATUS_APPROVED:
            self.is_published = False


        # Set publication time only when actually public.
        if (
            self.status == self.STATUS_APPROVED
            and self.is_published
            and self.published_at is None
        ):
            self.published_at = timezone.now()


        super().save(*args, **kwargs)


    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    def get_absolute_url(self):

        return reverse(
            "marketplace:detail",
            kwargs={
                "slug": self.slug,
            },
        )


    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    @property
    def is_public(self):

        return (
            self.status == self.STATUS_APPROVED
            and self.is_published
        )


    @property
    def has_digital_file(self):

        return bool(
            self.digital_file
        )


    def __str__(self):

        return self.title


    class Meta:

        ordering = [
            "-published_at",
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "is_published",
                ],
                name="market_status_pub_idx",
            ),
            models.Index(
                fields=[
                    "seller",
                    "status",
                ],
                name="market_seller_stat_idx",
            ),
        ]

        verbose_name = _("Product")
        verbose_name_plural = _("Products")


# ============================================================
# PRODUCT REVIEW
# ============================================================

class ProductReview(models.Model):

    # --------------------------------------------------------
    # Decisions
    # --------------------------------------------------------

    DECISION_APPROVED = "approved"
    DECISION_REJECTED = "rejected"
    DECISION_CHANGES = "changes"

    DECISION_CHOICES = [
        (
            DECISION_APPROVED,
            _("Approved"),
        ),
        (
            DECISION_REJECTED,
            _("Rejected"),
        ),
        (
            DECISION_CHANGES,
            _("Changes requested"),
        ),
    ]


    # --------------------------------------------------------
    # Product
    # --------------------------------------------------------

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name=_("Product"),
    )


    # --------------------------------------------------------
    # Moderator
    # --------------------------------------------------------

    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="marketplace_reviews",
        verbose_name=_("Moderator"),
    )


    # --------------------------------------------------------
    # Decision
    # --------------------------------------------------------

    decision = models.CharField(
        max_length=20,
        choices=DECISION_CHOICES,
        verbose_name=_("Decision"),
    )


    # --------------------------------------------------------
    # Notes
    # --------------------------------------------------------

    notes = models.TextField(
        blank=True,
        verbose_name=_("Review notes"),
    )


    # --------------------------------------------------------
    # Quality score
    # --------------------------------------------------------

    quality_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(10),
        ],
        verbose_name=_("Quality score"),
        help_text=_("Optional score from 1 to 10"),
    )


    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    reviewed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Reviewed at"),
    )


    # --------------------------------------------------------
    # String representation
    # --------------------------------------------------------

    def __str__(self):

        return (
            f"{self.product.title} — "
            f"{self.get_decision_display()}"
        )


    class Meta:

        ordering = [
            "-reviewed_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "product",
                    "reviewed_at",
                ],
                name="market_review_prod_idx",
            ),
        ]

        verbose_name = _("Product review")
        verbose_name_plural = _("Product reviews")