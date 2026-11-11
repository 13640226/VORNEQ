from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from marketplace.admin import ProductAdmin
from marketplace.models import Product


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
            getattr(self.admin, name)(
                request, queryset if queryset is not None else Product.objects.filter(pk=self.product.pk)
            )

    def test_approval_does_not_publish(self):
        self.action("approve_products", self.staff)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.STATUS_APPROVED)
        self.assertFalse(self.product.is_published)
        self.assertIsNone(self.product.published_at)

    def test_superuser_publication_requires_approval(self):
        self.action("publish_approved_products", self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)
        self.product.status = Product.STATUS_APPROVED
        self.product.save()
        self.action("publish_approved_products", self.owner)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_published)
        self.assertIsNotNone(self.product.published_at)

    def test_staff_cannot_publish(self):
        self.product.status = Product.STATUS_APPROVED
        self.product.save()
        self.action("publish_approved_products", self.staff)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)

    def test_synthetic_products_cannot_be_published_by_action(self):
        User = get_user_model()
        seed_seller = User.objects.create_user(username="vorneq-benchmark-seed")
        smoke_seller = User.objects.create_user(username="vorneq-inspect-smoke")
        benchmark = Product.objects.create(
            seller=seed_seller, title="Benchmark", slug="vorneq-benchmark-product-000001",
            status=Product.STATUS_APPROVED
        )
        smoke = Product.objects.create(
            seller=smoke_seller, title="Smoke", slug="inspect-staging-smoke",
            status=Product.STATUS_APPROVED
        )
        self.action(
            "publish_approved_products", self.owner,
            Product.objects.filter(pk__in=[benchmark.pk, smoke.pk])
        )
        self.assertFalse(Product.objects.get(pk=benchmark.pk).is_published)
        self.assertFalse(Product.objects.get(pk=smoke.pk).is_published)

    def test_reject_and_reset_clear_publication(self):
        self.product.status = Product.STATUS_APPROVED
        self.product.is_published = True
        self.product.save()
        self.action("reject_products", self.staff)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.STATUS_REJECTED)
        self.assertFalse(self.product.is_published)
        self.assertIsNone(self.product.published_at)

        self.product.status = Product.STATUS_APPROVED
        self.product.is_published = True
        self.product.save()
        self.action("reset_products_to_pending", self.staff)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.STATUS_PENDING)
        self.assertFalse(self.product.is_published)
        self.assertIsNone(self.product.published_at)

    def test_superuser_unpublish_only(self):
        self.product.status = Product.STATUS_APPROVED
        self.product.is_published = True
        self.product.save()
        self.action("unpublish_products", self.staff)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_published)
        self.action("unpublish_products", self.owner)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_published)
        self.assertIsNone(self.product.published_at)
