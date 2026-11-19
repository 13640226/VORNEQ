"""Marketplace UI V2: templates, honest commerce state, i18n/RTL, a11y and security.

No production data, no network. Synthetic records only inside the test DB.
"""
import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from apps.core.services.entitlement import grant_entitlement

from .models import Product, ProductReview
from .tests import TEST_STORAGES

User = get_user_model()


def _url(name, lang="en", *args):
    with translation.override(lang):
        return reverse(name, args=args)


def _product(seller, **kw):
    defaults = dict(title="Course", status=Product.STATUS_APPROVED, is_published=True,
                    category=Product.CATEGORY_COURSE, published_at=timezone.now())
    defaults.update(kw)
    return Product.objects.create(seller=seller, **defaults)


@override_settings(STORAGES=TEST_STORAGES)
class IndexV2Tests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username="ui-seller", password="x-test-only")

    def test_empty_catalog_state_with_real_create_route(self):
        response = self.client.get(_url("marketplace:index"))
        self.assertContains(response, 'data-marketplace-ui="v2"')
        self.assertContains(response, 'data-empty-state="catalog"')
        self.assertContains(response, "No products have been published yet.")
        login = reverse("account_login") + "?next=" + _url("marketplace:product_create")
        self.assertContains(response, login)
        self.client.force_login(self.seller)
        response = self.client.get(_url("marketplace:index"))
        self.assertContains(response, 'href="%s"' % _url("marketplace:product_create"))

    def test_filtered_empty_state_is_distinct(self):
        _product(self.seller, title="Alpha", slug="alpha")
        response = self.client.get(_url("marketplace:index"), {"q": "no-such-thing"})
        self.assertContains(response, 'data-empty-state="filtered"')
        self.assertContains(response, "No products match your search")
        self.assertNotContains(response, "No products have been published yet.")

    def test_price_state_never_invents_currency_or_purchase(self):
        _product(self.seller, title="Free Thing", slug="free-thing", price=Decimal("0"))
        _product(self.seller, title="Paid Thing", slug="paid-thing", price=Decimal("12.50"))
        for url in (_url("marketplace:index"), _url("marketplace:detail", "en", "paid-thing")):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn("12.50", html)
                self.assertNotRegex(html, r"(€|\$|USD|EUR|﷼|تومان|ریال)\s*\d")
                self.assertNotRegex(html, r"(?i)>\s*(buy now|add to cart|checkout|purchase now)\s*<")
        self.assertContains(self.client.get(_url("marketplace:index")), "Free")
        detail = self.client.get(_url("marketplace:detail", "en", "paid-thing"))
        self.assertContains(detail, "Paid product")
        self.assertContains(detail, "Purchasing is not available yet.")

    def test_sort_is_allowlisted_and_deterministic(self):
        _product(self.seller, title="Beta", slug="beta", price=Decimal("5"))
        _product(self.seller, title="Alpha", slug="alpha", price=Decimal("0"))
        titles = lambda r: [p.title for p in r.context["products"]]  # noqa: E731
        self.assertEqual(titles(self.client.get(_url("marketplace:index"), {"sort": "title"})), ["Alpha", "Beta"])
        self.assertEqual(titles(self.client.get(_url("marketplace:index"), {"sort": "price_low"}))[0], "Alpha")
        for hostile in ("-seller__password", "seller__password", "?", "title;DROP", ""):
            with self.subTest(sort=hostile):
                response = self.client.get(_url("marketplace:index"), {"sort": hostile})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["sort"], "newest")

    def test_query_is_bounded(self):
        response = self.client.get(_url("marketplace:index"), {"q": "x" * 5000})
        self.assertEqual(len(response.context["query"]), 100)
        self.assertContains(response, 'maxlength="100"')

    def test_pagination_preserves_filters_and_escapes_ampersands(self):
        for i in range(11):
            _product(self.seller, title=f"Item {i:02d}", slug=f"item-{i:02d}")
        response = self.client.get(_url("marketplace:index"), {"category": "course", "sort": "title", "q": "Item"})
        html = response.content.decode()
        self.assertIn("?page=2&amp;q=Item&amp;category=course&amp;sort=title", html)
        self.assertNotRegex(html, r'href="[^"]*&(?!amp;)[a-z]+=')

    def test_untrusted_text_is_escaped(self):
        _product(self.seller, title='<script>alert(1)</script>', slug="xss",
                 short_description='<img src=x onerror=alert(2)>')
        for url in (_url("marketplace:index"), _url("marketplace:detail", "en", "xss")):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn("<script>alert(1)</script>", html)
                self.assertNotIn("<img src=x onerror", html)

    def test_cards_have_stable_media_and_labelled_actions(self):
        _product(self.seller, title="No Image", slug="no-image")
        html = self.client.get(_url("marketplace:index")).content.decode()
        self.assertIn("mkt-card__placeholder--course", html)
        self.assertIn('<span class="sr-only">: No Image</span>', html)
        self.assertIn('role="search"', html)
        self.assertIn('aria-current="page"', html)


@override_settings(STORAGES=TEST_STORAGES)
class LocalizationV2Tests(TestCase):
    def test_persian_is_rtl_and_translated(self):
        response = self.client.get(_url("marketplace:index", "fa"))
        html = response.content.decode()
        self.assertIn('dir="rtl"', html)
        self.assertIn("هنوز محصولی منتشر نشده است.", html)
        self.assertIn("مرتب‌سازی بر اساس", html)
        self.assertNotIn("No products have been published yet.", html)
        self.assertNotIn("Sort by", html)

    def test_german_is_translated(self):
        html = self.client.get(_url("marketplace:index", "de")).content.decode()
        self.assertIn("Es wurden noch keine Produkte veröffentlicht.", html)
        self.assertIn("Sortieren nach", html)
        self.assertIn('dir="ltr"', html)


@override_settings(STORAGES=TEST_STORAGES)
class DetailV2Tests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username="detail-seller", password="x-test-only")
        self.buyer = User.objects.create_user(username="detail-buyer", password="x-test-only")
        self.product = _product(
            self.seller, title="File Product", slug="file-product",
            digital_file=SimpleUploadedFile("guide.pdf", b"%PDF-1.4 synthetic", content_type="application/pdf"))
        self.download = reverse("marketplace:download_product", args=[self.product.pk])

    def test_breadcrumb_and_no_fake_checkout(self):
        html = self.client.get(_url("marketplace:detail", "en", "file-product")).content.decode()
        self.assertIn('aria-label="Breadcrumb"', html)
        self.assertIn('aria-current="page"', html)
        self.assertNotRegex(html, r"(?i)checkout|add to cart")

    def test_download_only_for_entitled_accounts(self):
        url = _url("marketplace:detail", "en", "file-product")
        anonymous = self.client.get(url)
        self.assertNotContains(anonymous, self.download)
        self.assertContains(anonymous, "Sign in to check your access")
        self.client.force_login(self.buyer)
        self.assertNotContains(self.client.get(url), self.download)
        grant_entitlement(self.buyer, self.product)
        self.assertContains(self.client.get(url), self.download)
        self.assertNotContains(self.client.get(url), self.product.digital_file.url)

    def test_unpublished_detail_is_404(self):
        _product(self.seller, title="Hidden", slug="hidden", is_published=False)
        self.assertEqual(self.client.get(_url("marketplace:detail", "en", "hidden")).status_code, 404)


@override_settings(STORAGES=TEST_STORAGES)
class SellerDashboardV2Tests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username="dash-seller", password="x-test-only")
        self.other = User.objects.create_user(username="dash-other", password="x-test-only")
        self.moderator = User.objects.create_user(username="dash-mod", password="x-test-only", is_staff=True)
        self.published = _product(self.seller, title="Mine Published", slug="mine-pub")
        self.pending = _product(self.seller, title="Mine Pending", slug="mine-pen",
                                status=Product.STATUS_PENDING, is_published=False)
        self.rejected = _product(self.seller, title="Mine Rejected", slug="mine-rej",
                                 status=Product.STATUS_REJECTED, is_published=False)
        _product(self.other, title="Someone Else", slug="other-1")
        ProductReview.objects.create(product=self.rejected, moderator=self.moderator,
                                     decision=ProductReview.DECISION_REJECTED, notes="internal-note-xyz")

    def test_login_required(self):
        response = self.client.get(_url("marketplace:seller_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_counts_isolation_and_latest_decision(self):
        self.client.force_login(self.seller)
        response = self.client.get(_url("marketplace:seller_dashboard"))
        counts = response.context["counts"]
        self.assertEqual((counts["total"], counts["pending"], counts["approved"], counts["rejected"],
                          counts["published"]), (3, 1, 1, 1, 1))
        html = response.content.decode()
        self.assertNotIn("Someone Else", html)
        self.assertIn("Latest moderation decision", html)
        self.assertIn("Waiting for a moderator.", html)
        self.assertNotIn("internal-note-xyz", html)  # moderator notes stay internal
        self.assertIn(_url("marketplace:product_edit", "en", self.pending.pk), html)
        self.assertNotIn(_url("marketplace:product_edit", "en", Product.objects.get(slug="other-1").pk), html)

    def test_empty_dashboard(self):
        self.client.force_login(self.other)
        Product.objects.filter(seller=self.other).delete()
        response = self.client.get(_url("marketplace:seller_dashboard"))
        self.assertContains(response, 'data-empty-state="seller"')


class StylesheetContractTests(TestCase):
    CSS = Path(settings.BASE_DIR) / "assets" / "css" / "marketplace-v2.css"

    def test_logical_properties_only_for_rtl(self):
        css = self.CSS.read_text(encoding="utf-8")
        physical = re.findall(r"(?<![-\w])(margin|padding|border)-(left|right)\s*:|(?<![-\w])(left|right)\s*:", css)
        self.assertEqual(physical, [])

    def test_tokens_only_no_hardcoded_colors(self):
        css = self.CSS.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), [])

    def test_reduced_motion_and_focus_rules_exist(self):
        css = self.CSS.read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("--mkt-touch: 44px", css)
