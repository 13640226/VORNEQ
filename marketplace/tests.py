from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

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


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": (
                "django.contrib.staticfiles.storage.StaticFilesStorage"
            ),
        },
    }
)
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
