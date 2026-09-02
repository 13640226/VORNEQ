"""
Admin configuration for the Marketplace app of Saman Kherad.

Provides:
- Product management
- Product moderation
- ProductReview management
- Bulk approval/rejection actions
"""

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Product, ProductReview


# ============================================================================
# PRODUCT REVIEW INLINE
# ============================================================================

class ProductReviewInline(admin.StackedInline):
    """
    Display the moderation review inside the Product admin page.
    """

    model = ProductReview
    extra = 0
    max_num = 1
    can_delete = False

    fields = (
        "moderator",
        "notes",
        "quality_score",
        "reviewed_at",
    )

    readonly_fields = (
        "reviewed_at",
    )

    verbose_name = _("Product review")
    verbose_name_plural = _("Product review")


# ============================================================================
# PRODUCT ADMIN
# ============================================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Administration interface for marketplace products.
    """

    # ------------------------------------------------------------------------
    # List page
    # ------------------------------------------------------------------------

    list_display = (
        "title",
        "seller",
        "category",
        "price_display",
        "status_badge",
        "created_at",
        "published_at",
    )

    list_filter = (
        "status",
        "category",
        "created_at",
        "published_at",
    )

    search_fields = (
        "title",
        "short_description",
        "description",
        "tags",
        "seller__username",
        "seller__email",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    date_hierarchy = "created_at"

    # ------------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------------

    list_select_related = (
        "seller",
    )

    # ------------------------------------------------------------------------
    # Form configuration
    # ------------------------------------------------------------------------

    prepopulated_fields = {
        "slug": ("title",),
    }

    readonly_fields = (
        "created_at",
        "updated_at",
        "published_at",
    )

    fieldsets = (
        (
            _("Identity"),
            {
                "fields": (
                    "title",
                    "slug",
                    "seller",
                    "category",
                ),
            },
        ),
        (
            _("Description"),
            {
                "fields": (
                    "short_description",
                    "description",
                ),
            },
        ),
        (
            _("Pricing"),
            {
                "fields": (
                    "price",
                ),
            },
        ),
        (
            _("Files"),
            {
                "fields": (
                    "image",
                    "digital_file",
                ),
            },
        ),
        (
            _("Metadata"),
            {
                "fields": (
                    "tags",
                    "version",
                ),
            },
        ),
        (
            _("Moderation & Publication"),
            {
                "fields": (
                    "status",
                    "published_at",
                ),
            },
        ),
        (
            _("System information"),
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    inlines = (
        ProductReviewInline,
    )

    actions = (
        "approve_products",
        "reject_products",
        "reset_products_to_pending",
    )

    # ------------------------------------------------------------------------
    # Price
    # ------------------------------------------------------------------------

    @admin.display(
        description=_("Price"),
        ordering="price",
    )
    def price_display(self, obj):
        """
        Display the product price without assuming a currency.
        """
        return f"{obj.price:,.2f}"

    # ------------------------------------------------------------------------
    # Status badge
    # ------------------------------------------------------------------------

    @admin.display(
        description=_("Status"),
        ordering="status",
    )
    def status_badge(self, obj):
        """
        Display moderation status with a small visual badge.
        """

        styles = {
            Product.STATUS_PENDING: (
                "#d69e2e",
                _("Pending"),
            ),
            Product.STATUS_APPROVED: (
                "#38a169",
                _("Approved"),
            ),
            Product.STATUS_REJECTED: (
                "#e53e3e",
                _("Rejected"),
            ),
        }

        color, label = styles.get(
            obj.status,
            (
                "#718096",
                obj.get_status_display(),
            ),
        )

        return format_html(
            '<span style="'
            'display:inline-block;'
            'padding:3px 8px;'
            'border:1px solid {};'
            'border-radius:3px;'
            'color:{};'
            'font-weight:600;'
            'font-size:12px;'
            '">{}</span>',
            color,
            color,
            label,
        )

    # ------------------------------------------------------------------------
    # Bulk action: approve
    # ------------------------------------------------------------------------

    @admin.action(
        description=_("Approve selected products"),
    )
    def approve_products(self, request, queryset):
        """
        Approve selected products and set their publication time.

        queryset.update() is intentionally used here, so published_at
        must be assigned explicitly because Product.save() is not called.
        """

        now = timezone.now()

        updated = queryset.exclude(
            status=Product.STATUS_APPROVED,
        ).update(
            status=Product.STATUS_APPROVED,
            published_at=now,
        )

        self.message_user(
            request,
            _("%(count)s product(s) approved successfully.")
            % {
                "count": updated,
            },
            level=messages.SUCCESS,
        )

    # ------------------------------------------------------------------------
    # Bulk action: reject
    # ------------------------------------------------------------------------

    @admin.action(
        description=_("Reject selected products"),
    )
    def reject_products(self, request, queryset):
        """
        Reject selected products.

        A rejected product is no longer considered published.
        """

        updated = queryset.exclude(
            status=Product.STATUS_REJECTED,
        ).update(
            status=Product.STATUS_REJECTED,
            published_at=None,
        )

        self.message_user(
            request,
            _("%(count)s product(s) rejected.")
            % {
                "count": updated,
            },
            level=messages.WARNING,
        )

    # ------------------------------------------------------------------------
    # Bulk action: reset to pending
    # ------------------------------------------------------------------------

    @admin.action(
        description=_("Return selected products to pending review"),
    )
    def reset_products_to_pending(self, request, queryset):
        """
        Return selected products to the moderation queue.
        """

        updated = queryset.exclude(
            status=Product.STATUS_PENDING,
        ).update(
            status=Product.STATUS_PENDING,
            published_at=None,
        )

        self.message_user(
            request,
            _("%(count)s product(s) returned to pending review.")
            % {
                "count": updated,
            },
            level=messages.INFO,
        )


# ============================================================================
# PRODUCT REVIEW ADMIN
# ============================================================================

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    """
    Standalone administration interface for moderation reviews.
    """

    list_display = (
        "product",
        "moderator",
        "quality_score",
        "reviewed_at",
    )

    list_filter = (
        "quality_score",
        "reviewed_at",
    )

    search_fields = (
        "product__title",
        "moderator__username",
        "moderator__email",
        "notes",
    )

    ordering = (
        "-reviewed_at",
    )

    list_per_page = 25

    date_hierarchy = "reviewed_at"

    list_select_related = (
        "product",
        "moderator",
    )

    readonly_fields = (
        "reviewed_at",
    )

    fieldsets = (
        (
            _("Product & Moderator"),
            {
                "fields": (
                    "product",
                    "moderator",
                ),
            },
        ),
        (
            _("Review"),
            {
                "fields": (
                    "notes",
                    "quality_score",
                ),
            },
        ),
        (
            _("System information"),
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "reviewed_at",
                ),
            },
        ),
    )