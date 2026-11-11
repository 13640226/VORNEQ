"""
Admin configuration for the Marketplace app of Saman Kherad.

Provides:
- Product management
- Product moderation
- ProductReview management
- Bulk approval/rejection actions
"""

from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Product, ProductReview
from .publication import transition_publication


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
        "decision",
        "notes",
        "quality_score",
        "reviewed_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

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
        "status",
    )

    def get_readonly_fields(self, request, obj=None):
        """Approved products must be reset and re-reviewed before content edits."""
        fields = super().get_readonly_fields(request, obj)
        if obj is not None and obj.status == Product.STATUS_APPROVED:
            return (*fields, "seller", "title", "slug", "short_description",
                    "description", "category", "tags", "version", "price",
                    "image", "digital_file")
        return fields

    def get_prepopulated_fields(self, request, obj=None):
        if obj is not None and obj.status == Product.STATUS_APPROVED:
            return {}
        return super().get_prepopulated_fields(request, obj)

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
        "publish_approved_products",
        "unpublish_products",
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

    @admin.action(description=_("Publish reviewed products (superuser)"))
    def publish_approved_products(self, request, queryset):
        """Only latest-approved, genuine products may become publicly visible."""
        if not request.user.is_superuser:
            self.message_user(request, _("Publication requires a superuser."), level=messages.ERROR)
            return
        changed = transition_publication(
            actor=request.user,
            product_ids=list(queryset.values_list("pk", flat=True)),
            publish=True,
        )
        self.message_user(
            request,
            _("%(count)s reviewed product(s) published.") % {"count": changed},
            level=messages.SUCCESS,
        )

    @admin.action(description=_("Unpublish products (superuser)"))
    def unpublish_products(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, _("Unpublication requires a superuser."), level=messages.ERROR)
            return
        changed = transition_publication(
            actor=request.user,
            product_ids=list(queryset.values_list("pk", flat=True)),
            publish=False,
        )
        self.message_user(
            request,
            _("%(count)s product(s) unpublished.") % {"count": changed},
            level=messages.SUCCESS,
        )

    @admin.action(description=_("Reject selected products"))
    def reject_products(self, request, queryset):
        """Revocation and moderation state change are one atomic operation."""
        if not request.user.is_staff:
            self.message_user(request, _("Staff is required."), level=messages.ERROR)
            return
        with transaction.atomic():
            ids = list(queryset.values_list("pk", flat=True))
            list(Product.objects.select_for_update().filter(pk__in=ids).values_list("pk", flat=True))
            transition_publication(
                actor=request.user, product_ids=ids, publish=False,
                reason_code="PRODUCT_REJECTED", staff_revoke=True,
            )
            count = Product.objects.filter(pk__in=ids).exclude(
                status=Product.STATUS_REJECTED,
            ).update(
                status=Product.STATUS_REJECTED, is_published=False, published_at=None,
            )
        self.message_user(
            request,
            _("%(count)s product(s) rejected.") % {"count": count},
            level=messages.WARNING,
        )

    @admin.action(description=_("Return selected products to pending review"))
    def reset_products_to_pending(self, request, queryset):
        if not request.user.is_staff:
            self.message_user(request, _("Staff is required."), level=messages.ERROR)
            return
        with transaction.atomic():
            ids = list(queryset.values_list("pk", flat=True))
            list(Product.objects.select_for_update().filter(pk__in=ids).values_list("pk", flat=True))
            transition_publication(
                actor=request.user, product_ids=ids, publish=False,
                reason_code="PRODUCT_RESET", staff_revoke=True,
            )
            count = Product.objects.filter(pk__in=ids).exclude(
                status=Product.STATUS_PENDING,
            ).update(
                status=Product.STATUS_PENDING, is_published=False, published_at=None,
            )
        self.message_user(
            request,
            _("%(count)s product(s) returned to pending review.") % {"count": count},
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
        "product",
        "moderator",
        "decision",
        "notes",
        "quality_score",
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
    def has_add_permission(self, request):
        # Canonical moderation lives in the staff review flow, not editable admin forms.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
