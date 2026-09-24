from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from django.utils import timezone

from apps.content.models import Article, Category
from apps.media.models import MediaAsset
from apps.search.services import UnifiedSearch
from library.models import AudioItem, LibraryItem
from marketplace.models import Product


class NarrowWindowRolloutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        category = Category.objects.create(name="Research", slug="research")
        seller = get_user_model().objects.create_user(
            username="rollout-seller",
            email="rollout@example.com",
            password="unused-test-password",
        )

        article = Article.objects.create(
            title="Alpha article",
            summary="Alpha summary",
            content="Alpha body",
            category=category,
            is_published=True,
            published_at=now,
        )
        product = Product.objects.create(
            seller=seller,
            title="Alpha product",
            slug="rollout-alpha-product",
            short_description="Alpha short",
            description="Alpha product description",
            category=Product.CATEGORY_EBOOK,
            price="12.50",
            status=Product.STATUS_APPROVED,
            is_published=True,
            published_at=now,
        )
        library_item = LibraryItem.objects.create(
            title="Alpha library",
            slug="rollout-alpha-library",
            short_description="Alpha library summary",
            content="Alpha library body",
            author="Researcher",
            category="Research",
            item_type="article",
            is_published=True,
            published_at=now,
        )
        media = MediaAsset.objects.create(
            media_type=MediaAsset.MediaType.IMAGE,
            title="Alpha media",
            alt_text="Alpha asset",
            file="media_assets/rollout-alpha.jpg",
            mime_type="image/jpeg",
            byte_size=10,
            width=10,
            height=10,
            is_active=True,
        )
        audio = AudioItem.objects.create(
            title="Alpha audio",
            description="Alpha audio description",
            audio_file="audio/rollout-alpha.mp3",
            is_published=True,
        )

        # Exercise the historical global tie-break: (published_at, key).
        Article.objects.filter(pk=article.pk).update(created_at=now, published_at=now)
        Product.objects.filter(pk=product.pk).update(created_at=now, published_at=now)
        LibraryItem.objects.filter(pk=library_item.pk).update(
            created_at=now, published_at=now
        )
        MediaAsset.objects.filter(pk=media.pk).update(created_at=now)
        AudioItem.objects.filter(pk=audio.pk).update(created_at=now)

    def setUp(self):
        self.search = UnifiedSearch()

    @staticmethod
    def _contract(result):
        return {
            "keys": [item["key"] for item in result["results"]],
            "total": result["total"],
            "page": result["page"],
            "total_pages": result["total_pages"],
            "has_next": result["has_next"],
            "has_previous": result["has_previous"],
        }

    def _baseline(self, *, query="", filters=None, page=1, page_size=12):
        filters = filters or {}
        if int(page) <= 0:
            return self.search._search_bounded(
                query, filters, page, page_size, language="en"
            )
        return self.search._search_with_window_count(
            query, filters, int(page), page_size, language="en"
        )

    def assert_production_matches_baseline(
        self, *, query="", filters=None, page=1, page_size=12
    ):
        baseline = self._baseline(
            query=query, filters=filters, page=page, page_size=page_size
        )
        production = self.search.search(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            language="en",
        )
        self.assertEqual(self._contract(production), self._contract(baseline))
        return production

    def test_exact_pagination_and_historical_ordering_match(self):
        for page in (1, 2, 999):
            self.assert_production_matches_baseline(page=page, page_size=2)

    def test_query_type_and_category_filters_match(self):
        self.assert_production_matches_baseline(query="alpha")
        result = self.assert_production_matches_baseline(
            query="alpha", filters={"types": "article"}
        )
        self.assertEqual(result["total"], 1)
        self.assert_production_matches_baseline(filters={"category": "research"})

    def test_invalid_and_nonpositive_pages_preserve_bounded_semantics(self):
        for page in (0, -1, "not-a-page"):
            expected = self.search._search_bounded(
                "", {}, page, 2, language="en"
            )
            actual = self.search.search(page=page, page_size=2, language="en")
            self.assertEqual(self._contract(actual), self._contract(expected))

    def test_supported_production_path_uses_five_queries(self):
        with self.assertNumQueries(5):
            self.search.search(page=1, page_size=12, language="en")

    def test_explicit_capability_fallback_keeps_window_count_path(self):
        with mock.patch("apps.search.narrow_window.supports_narrow_cte", return_value=False):
            expected = self.search._search_with_window_count(
                "", {}, 1, 12, language="en"
            )
            actual = self.search.search(page=1, page_size=12, language="en")
        self.assertEqual(self._contract(actual), self._contract(expected))

    def test_unexpected_database_error_is_fail_visible(self):
        with mock.patch("apps.search.narrow_window.supports_narrow_cte", return_value=True), mock.patch(
            "apps.search.narrow_window.search_narrow_cte",
            side_effect=DatabaseError("unexpected production failure"),
        ):
            with self.assertRaises(DatabaseError):
                self.search.search(page=1, page_size=12, language="en")

    def test_production_path_is_read_only(self):
        before = {
            "article": Article.objects.count(),
            "product": Product.objects.count(),
            "library": LibraryItem.objects.count(),
            "media": MediaAsset.objects.count(),
            "audio": AudioItem.objects.count(),
        }
        self.search.search(query="alpha", language="en")
        after = {
            "article": Article.objects.count(),
            "product": Product.objects.count(),
            "library": LibraryItem.objects.count(),
            "media": MediaAsset.objects.count(),
            "audio": AudioItem.objects.count(),
        }
        self.assertEqual(after, before)
