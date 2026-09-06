from datetime import UTC, datetime, timedelta

from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from apps.content.models import Article, Category
from apps.search.services import ArticleAdapter, UnifiedSearch
from apps.search.window_count_poc import window_count_search_poc


class WindowCountSearchPocTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Window Count PoC")
        self.service = UnifiedSearch(adapters=(ArticleAdapter(),))
        base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        for index in range(25):
            token = "ai" if index % 2 == 0 else "science"
            Article.objects.create(
                title=f"Window Article {index} {token}",
                summary=f"Knowledge summary {index}",
                content=f"Research content {index} {token}",
                category=self.category,
                is_published=True,
                published_at=base_time + timedelta(hours=index),
            )

    def assert_matches_production(self, *, query="", page=1, page_size=7):
        expected = self.service.search(query=query, page=page, page_size=page_size)
        actual = window_count_search_poc(
            self.service,
            query=query,
            page=page,
            page_size=page_size,
        ).payload
        self.assertEqual(actual, expected)

    def test_first_middle_and_out_of_range_pages_match_production(self):
        self.assert_matches_production(page=1)
        self.assert_matches_production(page=3)
        self.assert_matches_production(page=999)

    def test_filtered_query_matches_production(self):
        self.assert_matches_production(query="ai", page=2, page_size=5)
        self.assert_matches_production(query="science", page=1, page_size=6)

    def test_positive_page_uses_one_query_per_nonfiltered_adapter(self):
        with CaptureQueriesContext(connection) as captured:
            profile = window_count_search_poc(self.service, page=1, page_size=7)
        self.assertEqual(profile.payload["total"], 25)
        self.assertEqual(len(captured), 1)

    def test_invalid_page_falls_back_to_production_contract(self):
        for page in (0, -3, "not-a-number"):
            expected = self.service.search(page=page, page_size=7)
            actual = window_count_search_poc(
                self.service,
                page=page,
                page_size=7,
            ).payload
            self.assertEqual(actual, expected)

    def test_prototype_is_read_only(self):
        before = Article.objects.count()
        window_count_search_poc(self.service, query="knowledge", page=1, page_size=7)
        self.assertEqual(Article.objects.count(), before)
