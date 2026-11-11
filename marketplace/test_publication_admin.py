from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event as real_record_audit_event
from marketplace.admin import ProductAdmin, ProductReviewAdmin
from marketplace.models import Product, ProductReview


class ProductPublicationAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.seller = User.objects.create_user(username="regular-seller", password="pass123")
        self.staff = User.objects.create_user(username="regular-staff", password="pass123", is_staff=True)
        self.owner = User.objects.create_superuser(
            username="publication-owner", email="owner@example.invalid", password="pass123"
        )
        self.admin = ProductAdmin(Product, AdminSite())
        self.product = Product.objects.create(
            seller=self.seller, title="Real Product", status=Product.STATUS_PENDING
        )

    def action(self, name, user, queryset=None):
        request = RequestFactory().post("/admin/marketplace/product/")
        request.user = user
        with patch.object(self.admin, "message_user"):
            return getattr(self.admin, name)(
                request, queryset if queryset is not None
                else Product.objects.filter(pk=self.product.pk)
            )

    def _approved(self, product=None, moderator=None):
        product = product or self.product
        moderator = moderator or self.staff
        ProductReview.objects.create(
            product=product, moderator=moderator,
            decision=ProductReview.DECISION_APPROVED,
        )
        product.status = Product.STATUS_APPROVED
        product.save()
        return product

    def _audit(self, event):
        return AuditEvent.objects.filter(event_name=event).order_by("pk")

    def test_admin_cannot_approve_without_canonical_review(self):
        self.assertNotIn("approve_products", self.admin.actions)
        self.assertIn("status", self.admin.get_readonly_fields(
            RequestFactory().get("/admin/"), self.product,
        ))

    def test_review_is_immutable_in_admin(self):
        admin = ProductReviewAdmin(ProductReview, AdminSite())
        request = RequestFactory().get("/admin/")
        request.user = self.owner
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))

    def test_approved_product_contents_are_readonly_in_admin(self):
        self._approved()
        request = RequestFactory().get("/admin/")
        for field in ("seller", "title", "price", "digital_file", "description", "status"):
            self.assertIn(field, self.admin.get_readonly_fields(request, self.product))

    def test_review_view_approval_does_not_publish(self):
        self._approved()
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.STATUS_APPROVED)
        self.assertFalse(self.product.is_published)
        self.assertIsNone(self.product.published_at)

    def test_superuser_publication_requires_approval_and_review(self):
        self.action("publish_approved_products", self.owner)
        self.product.status = Product.STATUS_APPROVED
        self.product.save()
        self.action("publish_approved_products", self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)
        self.assertFalse(self._audit("marketplace.product.published").exists())
        self._approved()
        self.action("publish_approved_products", self.owner)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_published)
        self.assertIsNotNone(self.product.published_at)

    def test_staff_cannot_publish(self):
        self._approved()
        self.action("publish_approved_products", self.staff)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)
        self.assertFalse(AuditEvent.objects.exists())

    def test_latest_rejected_review_blocks_publication(self):
        self._approved()
        ProductReview.objects.create(
            product=self.product, moderator=self.staff,
            decision=ProductReview.DECISION_REJECTED,
        )
        self.action("publish_approved_products", self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)

    def test_nonstaff_review_is_not_valid(self):
        self._approved(moderator=self.seller)
        self.action("publish_approved_products", self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)

    def test_self_review_is_not_valid(self):
        self.seller.is_staff = True
        self.seller.save(update_fields=["is_staff"])
        self._approved(moderator=self.seller)
        self.action("publish_approved_products", self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)

    def test_inactive_moderator_cannot_authorize_publication(self):
        self._approved()
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        self.action("publish_approved_products", self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)

    def test_fixture_products_cannot_be_published_even_with_reviews(self):
        User = get_user_model()
        seed_seller = User.objects.create_user(username="vorneq-benchmark-seed")
        smoke_seller = User.objects.create_user(username="vorneq-inspect-smoke")
        benchmark = Product.objects.create(
            seller=seed_seller, title="Benchmark", slug="vorneq-benchmark-product-000001",
            status=Product.STATUS_APPROVED,
        )
        smoke = Product.objects.create(
            seller=smoke_seller, title="Smoke", slug="inspect-staging-smoke",
            status=Product.STATUS_APPROVED,
        )
        for product in (benchmark, smoke):
            self._approved(product)
        self.action(
            "publish_approved_products", self.owner,
            Product.objects.filter(pk__in=[benchmark.pk, smoke.pk]),
        )
        self.assertFalse(Product.objects.get(pk=benchmark.pk).is_published)
        self.assertFalse(Product.objects.get(pk=smoke.pk).is_published)

    def test_publication_has_append_only_security_audit(self):
        self._approved()
        self.action("publish_approved_products", self.owner)
        event = self._audit("marketplace.product.published").get()
        review = ProductReview.objects.get(product=self.product)
        self.assertEqual(event.actor, {"type": "user", "identifier": self.owner.pk})
        self.assertEqual(event.target, {"type": "Product", "identifier": self.product.pk})
        self.assertEqual(event.reason_code, "PRODUCT_PUBLISHED")
        self.assertEqual(event.outcome, AuditEvent.Outcome.CHANGED)
        self.assertEqual(event.metadata["review_id"], review.pk)
        self.assertEqual(event.retention_class, AuditEvent.RetentionClass.SECURITY)
        self.action("publish_approved_products", self.owner)
        self.assertEqual(self._audit("marketplace.product.published").count(), 1)

    def test_unpublish_has_security_audit(self):
        self._approved()
        self.action("publish_approved_products", self.owner)
        self.action("unpublish_products", self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)
        self.assertIsNone(self.product.published_at)
        event = self._audit("marketplace.product.unpublished").get()
        self.assertEqual(event.actor["identifier"], self.owner.pk)
        self.assertEqual(event.reason_code, "PRODUCT_UNPUBLISHED")
        self.assertEqual(event.outcome, AuditEvent.Outcome.REVOKED)

    def test_staff_cannot_unpublish_via_explicit_action(self):
        self._approved()
        self.action("publish_approved_products", self.owner)
        self.action("unpublish_products", self.staff)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_published)
        self.assertFalse(self._audit("marketplace.product.unpublished").exists())

    def test_reject_and_reset_clear_publication_and_audit(self):
        self._approved()
        self.action("publish_approved_products", self.owner)
        self.action("reject_products", self.staff)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.STATUS_REJECTED)
        self.assertFalse(self.product.is_published)
        self.assertIsNone(self.product.published_at)
        self.assertTrue(self._audit("marketplace.product.unpublished").filter(
            reason_code="PRODUCT_REJECTED",
        ).exists())

        self.product.status = Product.STATUS_APPROVED
        self.product.is_published = True
        self.product.save()
        self.action("reset_products_to_pending", self.staff)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.STATUS_PENDING)
        self.assertFalse(self.product.is_published)
        self.assertIsNone(self.product.published_at)
        self.assertTrue(self._audit("marketplace.product.unpublished").filter(
            reason_code="PRODUCT_RESET",
        ).exists())

    def test_audit_failure_rolls_back_publication(self):
        self._approved()
        with patch("marketplace.publication.record_audit_event", side_effect=RuntimeError("audit down")):
            with self.assertRaisesRegex(RuntimeError, "audit down"):
                self.action("publish_approved_products", self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)
        self.assertIsNone(self.product.published_at)
        self.assertFalse(AuditEvent.objects.exists())

    def test_audit_failure_rolls_back_moderation_revocation(self):
        self._approved()
        self.action("publish_approved_products", self.owner)
        with patch("marketplace.publication.record_audit_event", side_effect=RuntimeError("audit down")):
            with self.assertRaisesRegex(RuntimeError, "audit down"):
                self.action("reject_products", self.staff)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.STATUS_APPROVED)
        self.assertTrue(self.product.is_published)
        self.assertFalse(self._audit("marketplace.product.unpublished").exists())

    def test_bulk_audit_failure_rolls_back_every_product(self):
        self._approved()
        other = Product.objects.create(
            seller=self.seller, title="Second Real Product", status=Product.STATUS_APPROVED,
        )
        self._approved(other)
        count = [0]
        def emit_then_fail(**kwargs):
            count[0] += 1
            if count[0] == 2:
                raise RuntimeError("second event rejected")
            return real_record_audit_event(**kwargs)
        with patch("marketplace.publication.record_audit_event", side_effect=emit_then_fail):
            with self.assertRaisesRegex(RuntimeError, "second event rejected"):
                self.action(
                    "publish_approved_products", self.owner,
                    Product.objects.filter(pk__in=[self.product.pk, other.pk]),
                )
        self.assertFalse(Product.objects.get(pk=self.product.pk).is_published)
        self.assertFalse(Product.objects.get(pk=other.pk).is_published)
        self.assertFalse(AuditEvent.objects.exists())
