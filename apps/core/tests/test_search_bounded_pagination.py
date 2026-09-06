from datetime import UTC, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.test import TestCase

from apps.content.models import Article, Category
from apps.media.models import MediaAsset
from apps.search.services import (
    ArticleAdapter,
    LibraryItemAdapter,
    MediaAssetAdapter,
    ProductAdapter,
    UnifiedSearch,
)
from library.models import LibraryItem
from marketplace.models import Product


class BoundedSearchPaginationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="bounded-search-user",
            password="test-password",
        )
        self.category = Category.objects.create(name="Bounded Search")
        self.search = UnifiedSearch(
            adapters=(
                ArticleAdapter(),
                ProductAdapter(),
                LibraryItemAdapter(),
                MediaAssetAdapter(),
            )
        )

        base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        for index in range(18):
            # Deliberately create timestamp ties across adapters so the key
            # tie-break is exercised as part of exact pagination equivalence.
            published_at = base_time + timedelta(days=index // 3)
            token = "ai" if index % 2 == 0 else "science"

            Article.objects.create(
                title=f"Article {index} {token}",
                summary=f"Knowledge summary {index}",
                content=f"Research content {index} {token}",
                category=self.category,
                is_published=True,
                published_at=published_at,
            )
            Product.objects.create(
                seller=self.user,
                title=f"Product {index} {token}",
                short_description=f"Knowledge product {index}",
                description=f"Research product description {index} {token}",
                tags=f"knowledge,{token}",
                status=Product.STATUS_APPROVED,
                is_published=True,
                published_at=published_at,
            )
            LibraryItem.objects.create(
                title=f"Library {index} {token}",
                slug=f"bounded-library-{index}",
                short_description=f"Knowledge library {index}",
                content=f"Research library content {index} {token}",
                author="Benchmark Author",
                category="science",
                item_type="book",
                is_published=True,
                published_at=published_at,
            )
            MediaAsset.objects.create(
                media_type=MediaAsset.MediaType.IMAGE,
                title=f"Media {index} {token}",
                alt_text=f"Knowledge science media {index} {token}",
                file=f"media_assets/benchmark-{index}.jpg",
                mime_type="image/jpeg",
                byte_size=1024 + index,
                width=100,
                height=100,
                is_active=True,
            )

    def _reference_page(self, *, query="", page=1, page_size=12, filters=None):
        all_results = self.search.collect(query=query, filters=filters)
        page_obj = Paginator(all_results, page_size).get_page(page)
        return {
            "results": page_obj.object_list,
            "total": page_obj.paginator.count,
            "page": page_obj.number,
            "total_pages": page_obj.paginator.num_pages,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        }

    def assert_matches_reference(self, *, query="", page=1, page_size=12, filters=None):
        expected = self._reference_page(
            query=query,
            page=page,
            page_size=page_size,
            filters=filters,
        )
        actual = self.search.search(
            query=query,
            page=page,
            page_size=page_size,
            filters=filters,
        )
        self.assertEqual(actual, expected)

    def test_first_middle_and_last_pages_match_full_materialization(self):
        self.assert_matches_reference(page=1, page_size=11)
        self.assert_matches_reference(page=4, page_size=11)
        self.assert_matches_reference(page=7, page_size=11)

    def test_out_of_range_and_invalid_pages_keep_get_page_contract(self):
        self.assert_matches_reference(page=999, page_size=10)
        self.assert_matches_reference(page=0, page_size=10)
        self.assert_matches_reference(page=-3, page_size=10)
        self.assert_matches_reference(page="not-a-number", page_size=10)

    def test_query_filtering_matches_reference(self):
        self.assert_matches_reference(query="ai", page=1, page_size=9)
        self.assert_matches_reference(query="science", page=3, page_size=7)
        self.assert_matches_reference(query="knowledge", page=5, page_size=8)

    def test_type_filter_matches_reference(self):
        self.assert_matches_reference(
            page=2,
            page_size=7,
            filters={"types": ["article", "mediaasset"]},
        )

    def test_tie_breaking_has_no_duplicates_between_adjacent_pages(self):
        first = self.search.search(page=1, page_size=13)
        second = self.search.search(page=2, page_size=13)
        first_keys = {item["key"] for item in first["results"]}
        second_keys = {item["key"] for item in second["results"]}
        self.assertFalse(first_keys & second_keys)
