from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Entitlement
from apps.core.services import grant_entitlement

from .models import Product


User = get_user_model()


class MarketplaceModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="seller",
            password="testpass",
            email="seller@test.com",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Test Product",
            description="Test description",
            price=19.99,
            status="pending",
        )

    def test_product_creation(self):
        self.assertEqual(self.product.title, "Test Product")
        self.assertEqual(self.product.seller, self.user)
        self.assertEqual(self.product.status, "pending")

    def test_slug_generation(self):
        self.assertEqual(self.product.slug, "test-product")

    def test_product_status_choices(self):
        self.product.status = "approved"
        self.product.save()
        self.assertEqual(self.product.status, "approved")


TEST_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=TEST_STORAGES)
class MarketplaceViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass",
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            password="testpass",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Test Product",
            description="Test",
            price=10.00,
            status="approved",
            is_published=True,
        )

    def test_index_view(self):
        response = self.client.get(reverse("marketplace:index"))
        self.assertEqual(response.status_code, 200)

    def test_product_detail_view(self):
        response = self.client.get(
            reverse("marketplace:detail", args=[self.product.slug])
        )
        self.assertEqual(response.status_code, 200)

    def test_product_create_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("marketplace:product_create"))
        self.assertEqual(response.status_code, 200)

    def test_seller_dashboard_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("marketplace:seller_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_product_edit_owner_returns_200(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("marketplace:product_edit", args=[self.product.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_product_edit_other_user_returns_404(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse("marketplace:product_edit", args=[self.product.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_product_edit_anonymous_redirects_to_login(self):
        url = reverse("marketplace:product_edit", args=[self.product.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertIn("next=", response.url)


@override_settings(STORAGES=TEST_STORAGES)
class DownloadSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="download-user",
            password="testpass",
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Protected Product",
            description="Protected file",
            price=10.00,
            status=Product.STATUS_APPROVED,
            is_published=True,
            digital_file=SimpleUploadedFile(
                "test.pdf",
                b"%PDF-1.4 test content",
                content_type="application/pdf",
            ),
        )
        self.download_url = reverse(
            "marketplace:download_product",
            args=[self.product.pk],
        )

    def tearDown(self):
        if self.product.digital_file:
            storage = self.product.digital_file.storage
            name = self.product.digital_file.name
            if name and storage.exists(name):
                storage.delete(name)

    def test_unauthenticated_download_redirects_to_login(self):
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)
        self.assertIn("next=", response.url)

    def test_authenticated_without_entitlement_returns_404(self):
        self.client.force_login(self.user)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 404)

    def test_authenticated_with_valid_entitlement_returns_file(self):
        grant_entitlement(self.user, self.product)
        self.client.force_login(self.user)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("test.pdf", response["Content-Disposition"])

    def test_expired_entitlement_returns_404(self):
        Entitlement.objects.create(
            user=self.user,
            product=self.product,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.client.force_login(self.user)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 404)

    def test_inactive_entitlement_returns_404(self):
        Entitlement.objects.create(
            user=self.user,
            product=self.product,
            is_active=False,
        )
        self.client.force_login(self.user)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 404)

    def test_product_without_file_returns_404(self):
        storage = self.product.digital_file.storage
        name = self.product.digital_file.name
        self.product.digital_file = None
        self.product.save(update_fields=["digital_file"])
        if storage.exists(name):
            storage.delete(name)

        grant_entitlement(self.user, self.product)
        self.client.force_login(self.user)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 404)

    def test_digital_file_url_not_exposed_in_public_detail(self):
        response = self.client.get(
            reverse("marketplace:detail", args=[self.product.slug])
        )
        self.assertNotContains(response, self.product.digital_file.url)
        self.assertNotContains(response, "products/files/")

    def test_download_link_only_appears_with_valid_entitlement(self):
        self.client.force_login(self.user)
        detail_url = reverse("marketplace:detail", args=[self.product.slug])

        response = self.client.get(detail_url)
        self.assertNotContains(response, self.download_url)

        grant_entitlement(self.user, self.product)
        response = self.client.get(detail_url)
        self.assertContains(response, self.download_url)
