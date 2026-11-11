"""Audited, fail-closed Marketplace publication transitions.

Requires superuser for explicit publication and de-publication. Moderators
can revoke publication only as part of a rejecting/resetting moderation action.
All state and audit records are written in the SAME database transaction.
"""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event

from .models import Product, ProductReview


def latest_valid_approval(product):
    """Only the latest moderation decision counts; it must be made by staff."""
    review = (
        ProductReview.objects.filter(product_id=product.pk)
        .select_related("moderator")
        .order_by("-reviewed_at", "-pk")
        .first()
    )
    if (
        review is not None
        and review.decision == ProductReview.DECISION_APPROVED
        and review.moderator.is_active
        and review.moderator.is_staff
        and review.moderator_id != product.seller_id
    ):
        return review
    return None


def _is_known_fixture(product):
    """Existing seed/smoke names are defense-in-depth, not immutable provenance."""
    return (
        product.slug.startswith(("vorneq-benchmark-", "inspect-staging-smoke"))
        or product.seller.username in {"vorneq-benchmark-seed", "vorneq-inspect-smoke"}
    )


@transaction.atomic
def transition_publication(*, actor, product_ids, publish, reason_code=None, staff_revoke=False):
    if not getattr(actor, "is_authenticated", False) or not getattr(actor, "is_active", False):
        raise PermissionDenied("An active authenticated actor is required.")
    if publish or not staff_revoke:
        if not getattr(actor, "is_superuser", False):
            raise PermissionDenied("Publication requires a superuser.")
    elif not getattr(actor, "is_staff", False):
        raise PermissionDenied("Moderation revocation requires staff.")

    reason_code = reason_code or ("PRODUCT_PUBLISHED" if publish else "PRODUCT_UNPUBLISHED")
    allowed_reasons = (
        {"PRODUCT_PUBLISHED"} if publish
        else {"PRODUCT_UNPUBLISHED", "PRODUCT_REJECTED", "PRODUCT_RESET"}
    )
    if reason_code not in allowed_reasons:
        raise ValueError("Unsupported publication reason")

    count = 0
    for product in (
        Product.objects.select_for_update()
        .select_related("seller")
        .filter(pk__in=product_ids)
        .order_by("pk")
    ):
        if publish:
            if product.is_published or product.status != Product.STATUS_APPROVED:
                continue
            if _is_known_fixture(product):
                continue
            review = latest_valid_approval(product)
            if review is None:
                continue
            Product.objects.filter(pk=product.pk).update(
                is_published=True, published_at=timezone.now()
            )
            record_audit_event(
                event_name="marketplace.product.published",
                actor={"type": "user", "identifier": actor.pk},
                target={"type": "Product", "identifier": product.pk},
                outcome=AuditEvent.Outcome.CHANGED,
                reason_code="PRODUCT_PUBLISHED",
                retention_class=AuditEvent.RetentionClass.SECURITY,
                metadata={
                    "previous_state": "unpublished",
                    "new_state": "published",
                    "review_id": review.pk,
                },
            )
        else:
            if not product.is_published:
                continue
            Product.objects.filter(pk=product.pk).update(
                is_published=False, published_at=None
            )
            record_audit_event(
                event_name="marketplace.product.unpublished",
                actor={"type": "user", "identifier": actor.pk},
                target={"type": "Product", "identifier": product.pk},
                outcome=AuditEvent.Outcome.REVOKED,
                reason_code=reason_code,
                retention_class=AuditEvent.RetentionClass.SECURITY,
                metadata={
                    "previous_state": "published",
                    "new_state": "unpublished",
                },
            )
        count += 1
    return count
