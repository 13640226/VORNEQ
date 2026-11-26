import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Entitlement
from apps.core.services.entitlement import grant_entitlement

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
        # Isolate uploaded files from the real media/ directory so test runs
        # neither collide with leftovers nor pollute it.
        self.media_dir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
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
        self.settings_override.disable()
        self.media_dir.cleanup()

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
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertIn("attachment", response["Content-Disposition"])
            self.assertIn("test.pdf", response["Content-Disposition"])
        finally:
            # Exhaust the test client's guarded streaming iterator. It closes
            # the file without closing the TestCase PostgreSQL transaction.
            if response.streaming:
                for _ in response.streaming_content:
                    pass

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


@override_settings(STORAGES=TEST_STORAGES)
class MarketplaceKnownFixtureVisibilityTests(TestCase):
    """Historical published fixtures must not appear in public catalog or detail."""

    def setUp(self):
        self.seller = User.objects.create_user(
            username="real-marketplace-seller", password="testpass"
        )
        self.seed_seller = User.objects.create_user(
            username="vorneq-benchmark-seed", password="testpass"
        )
        self.smoke_seller = User.objects.create_user(
            username="vorneq-inspect-smoke", password="testpass"
        )
        self.real = Product.objects.create(
            seller=self.seller, title="Real Published Course",
            slug="real-published-course", status=Product.STATUS_APPROVED,
            is_published=True, category=Product.CATEGORY_COURSE,
        )
        self.fixtures = [
            Product.objects.create(
                seller=self.seller, title="Benchmark Fixture By Slug",
                slug="vorneq-benchmark-000001",
                status=Product.STATUS_APPROVED, is_published=True,
            ),
            Product.objects.create(
                seller=self.seller, title="Smoke Fixture By Slug",
                slug="inspect-staging-smoke-public",
                status=Product.STATUS_APPROVED, is_published=True,
            ),
            Product.objects.create(
                seller=self.seed_seller, title="Benchmark Fixture By Seller",
                slug="ordinary-looking-benchmark",
                status=Product.STATUS_APPROVED, is_published=True,
            ),
            Product.objects.create(
                seller=self.smoke_seller, title="Smoke Fixture By Seller",
                slug="ordinary-looking-smoke",
                status=Product.STATUS_APPROVED, is_published=True,
            ),
        ]

    def test_catalog_shows_real_product_but_hides_all_known_fixtures(self):
        response = self.client.get(reverse("marketplace:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].count, 1)
        self.assertContains(response, self.real.title)
        for product in self.fixtures:
            self.assertNotContains(response, product.title)

    def test_search_and_category_filters_cannot_reveal_fixtures(self):
        response = self.client.get(reverse("marketplace:index"), {"q": "Fixture"})
        self.assertEqual(response.context["paginator"].count, 0)
        response = self.client.get(
            reverse("marketplace:index"), {"category": Product.CATEGORY_COURSE}
        )
        self.assertEqual(response.context["paginator"].count, 1)
        self.assertContains(response, self.real.title)

    def test_public_detail_returns_404_for_historical_fixtures(self):
        self.assertEqual(
            self.client.get(reverse("marketplace:detail", args=[self.real.slug])).status_code,
            200,
        )
        for product in self.fixtures:
            response = self.client.get(
                reverse("marketplace:detail", args=[product.slug])
            )
            self.assertEqual(response.status_code, 404, product.slug)

    def test_products_remain_in_database_and_seller_dashboard(self):
        self.assertEqual(
            Product.objects.filter(pk__in=[p.pk for p in self.fixtures]).count(),
            len(self.fixtures),
        )
        self.client.force_login(self.seller)
        response = self.client.get(reverse("marketplace:seller_dashboard"))
        self.assertContains(response, "Benchmark Fixture By Slug")


@override_settings(STORAGES=TEST_STORAGES)
class PublicFixtureGuardAllSurfacesTests(TestCase):
    """Every public product surface uses the shared selector (no mutation)."""

    def setUp(self):
        real_seller = User.objects.create_user(username="real-surface-seller", password="testpass")
        seed = User.objects.create_user(username="vorneq-benchmark-seed", password="testpass")
        self.real = Product.objects.create(
            seller=real_seller, title="Zebra Real Product", slug="zebra-real-product",
            status=Product.STATUS_APPROVED, is_published=True,
        )
        self.fixture = Product.objects.create(
            seller=seed, title="Zebra Benchmark Product", slug="vorneq-benchmark-product-000777",
            status=Product.STATUS_APPROVED, is_published=True,
        )
        self.pending_real = Product.objects.create(
            seller=real_seller, title="Zebra Pending Product", slug="zebra-pending",
            status=Product.STATUS_PENDING, is_published=False,
        )

    def test_global_search_api_hides_fixtures_and_unpublished(self):
        response = self.client.get(reverse("search:unified"), {"q": "Zebra"})
        self.assertEqual(response.status_code, 200)
        titles = [item.get("title") for item in response.json()["results"]]
        self.assertIn(self.real.title, titles)
        self.assertNotIn(self.fixture.title, titles)
        self.assertNotIn(self.pending_real.title, titles)

    def test_ai_public_retrieval_never_cites_fixture_products(self):
        from apps.ai_core.gateway import retrieve_public

        keys = [getattr(c, "key", "") for c in retrieve_public("Zebra", "en")]
        self.assertTrue(any(str(self.real.pk) in k or self.real.slug in k for k in keys), keys)
        self.assertFalse(any(str(self.fixture.pk) in k or self.fixture.slug in k for k in keys), keys)

    def test_public_verification_api_404_for_fixture(self):
        ok = self.client.get(reverse("verification:product_summary", args=[self.real.pk]))
        hidden = self.client.get(reverse("verification:product_summary", args=[self.fixture.pk]))
        self.assertEqual((ok.status_code, hidden.status_code), (200, 404))

    def test_guard_never_mutates_records(self):
        before = list(Product.objects.order_by("pk").values_list("pk", "status", "is_published", "updated_at"))
        for url in (reverse("marketplace:index"), reverse("search:unified") + "?q=Zebra",
                    reverse("marketplace:detail", args=[self.fixture.slug])):
            self.client.get(url)
        after = list(Product.objects.order_by("pk").values_list("pk", "status", "is_published", "updated_at"))
        self.assertEqual(before, after)

    def test_database_and_python_predicates_agree(self):
        from .selectors import is_known_fixture, known_fixture_q

        smoke = User.objects.create_user(username="vorneq-inspect-smoke", password="testpass")
        cases = [
            Product.objects.create(seller=self.real.seller, title="a", slug="inspect-staging-smoke-x"),
            Product.objects.create(seller=smoke, title="b", slug="harmless-b"),
            Product.objects.create(seller=self.real.seller, title="c", slug="benchmark-vorneq-not-prefix"),
            Product.objects.create(seller=self.real.seller, title="d", slug="xvorneq-benchmark-1"),
        ]
        in_db = set(Product.objects.filter(known_fixture_q()).values_list("pk", flat=True))
        for product in [self.real, self.fixture, self.pending_real, *cases]:
            with self.subTest(slug=product.slug):
                self.assertEqual(is_known_fixture(product), product.pk in in_db)
        self.assertEqual(in_db, {self.fixture.pk, cases[0].pk, cases[1].pk})

    def test_publication_guard_uses_the_same_rule(self):
        from . import publication, selectors

        for product in (self.real, self.fixture):
            self.assertEqual(publication._is_known_fixture(product), selectors.is_known_fixture(product))


class MarketplaceV8Tests(TestCase):
    def test_public_shell_and_layout_controls(self):
        for lang in ('de', 'fa', 'en'):
            with self.subTest(lang=lang):
                response = self.client.get(f'/{lang}/marketplace/')
                self.assertContains(response, 'id="vq-main"', count=1)
                self.assertContains(response, 'data-layout="grid"')
                self.assertContains(response, 'data-layout="list"')
                from django.templatetags.static import static
                self.assertContains(response, static('css/marketplace-v8.css'))

    def test_private_routes_require_login(self):
        for name in ('seller_dashboard', 'product_create', 'review_queue'):
            self.assertEqual(self.client.get(reverse('marketplace:'+name)).status_code, 302)
