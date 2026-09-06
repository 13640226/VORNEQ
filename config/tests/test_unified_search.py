from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.content.models import Article, Category
from apps.media.models import MediaAsset
from apps.search.services import UnifiedSearch
from library.models import LibraryItem
from marketplace.models import Product


User = get_user_model()


class UnifiedSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="search-user", password="test-pass")
        self.category = Category.objects.create(name="Test Category")
        self.article = Article.objects.create(
            title="Test Article",
            summary="Test summary",
            content="Test article content",
            category=self.category,
            is_published=True,
        )
        self.product = Product.objects.create(
            seller=self.user,
            title="Test Product",
            short_description="Test product description",
            status=Product.STATUS_APPROVED,
            is_published=True,
            price="10.00",
        )
        self.library_item = LibraryItem.objects.create(
            title="Test Book",
            slug="test-book",
            short_description="Test library description",
            author="Test Author",
            item_type="book",
            is_published=True,
        )
        self.media_asset = MediaAsset.objects.create(
            title="Test Media",
            alt_text="Test image description",
            media_type=MediaAsset.MediaType.IMAGE,
            file=SimpleUploadedFile("test.png", b"image-bytes", content_type="image/png"),
            mime_type="image/png",
            byte_size=11,
            width=10,
            height=10,
            is_active=True,
        )

    def test_normalize_query_is_conservative_and_deterministic(self):
        self.assertEqual(
            UnifiedSearch.normalize_query("  Test   Query  "),
            "test query",
        )

    def test_search_retrieves_all_primary_adapter_types(self):
        payload = UnifiedSearch().search("test", page_size=20)
        keys = {result["key"].split(":", 1)[0] for result in payload["results"]}
        self.assertTrue({"article", "product", "library", "media"}.issubset(keys))

    def test_type_filter_limits_to_article_adapter(self):
        payload = UnifiedSearch().search("test", filters={"types": {"article"}})
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["results"][0]["type"], "article")

    def test_library_item_filter_is_applied(self):
        payload = UnifiedSearch().search(
            "test",
            filters={"types": {"libraryitem"}, "item_type": "book"},
        )
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["results"][0]["key"], f"library:{self.library_item.pk}")

    def test_unpublished_content_is_not_returned(self):
        Article.objects.create(
            title="Test Hidden Article",
            summary="Test hidden",
            content="Test hidden content",
            category=self.category,
            is_published=False,
        )
        payload = UnifiedSearch().search("hidden", page_size=20)
        self.assertFalse(any(result["key"].startswith("article:") for result in payload["results"]))

    def test_api_returns_paginated_contract(self):
        response = self.client.get(
            reverse("search:unified"),
            {"q": "TEST", "page_size": 2},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["normalized_query"], "test")
        self.assertEqual(data["page"], 1)
        self.assertEqual(len(data["results"]), 2)
        self.assertGreaterEqual(data["total"], 4)

    def test_api_type_filter(self):
        response = self.client.get(
            reverse("search:unified"),
            {"q": "test", "type": "product"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["type"], "product")
