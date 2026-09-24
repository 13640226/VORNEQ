from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.core.paginator import Paginator
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.content.models import Article, Category
from apps.search.services import ArticleAdapter, UnifiedSearch


class WindowCountProductionSearchTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Window Production")
        self.search = UnifiedSearch(adapters=(ArticleAdapter(),))
        base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        for index in range(30):
            Article.objects.create(
                title=f"Article {index} {'ai' if index % 2 == 0 else 'science'}",
                summary=f"Knowledge {index}",
                content=f"Research {index}",
                category=self.category,
                is_published=True,
                published_at=base_time + timedelta(days=index // 3),
            )

    def reference(self, *, query="", page=1, page_size=7):
        rows = self.search.collect(query=query)
        page_obj = Paginator(rows, page_size).get_page(page)
        return {
            "results": page_obj.object_list,
            "total": page_obj.paginator.count,
            "page": page_obj.number,
            "total_pages": page_obj.paginator.num_pages,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        }

    def test_window_primary_path_matches_full_reference(self):
        for query in ("", "ai", "knowledge", "science"):
            for page in (1, 2, 5, 999):
                self.assertEqual(
                    self.search.search(query=query, page=page, page_size=7),
                    self.reference(query=query, page=page, page_size=7),
                )

    def test_supported_backend_uses_one_query_for_one_adapter(self):
        if not connection.features.supports_over_clause:
            self.skipTest("Database backend does not support window functions")
        with CaptureQueriesContext(connection) as captured:
            payload = self.search.search(page=1, page_size=7)
        self.assertEqual(payload["total"], 30)
        self.assertEqual(len(captured), 1)

    def test_invalid_pages_preserve_get_page_contract_via_bounded_fallback(self):
        for page in (0, -2, "not-a-number"):
            self.assertEqual(
                self.search.search(page=page, page_size=7),
                self.reference(page=page, page_size=7),
            )

    def test_backend_without_over_support_uses_bounded_fallback(self):
        with patch.object(connection.features, "supports_over_clause", False):
            actual = self.search.search(page=2, page_size=7)
        self.assertEqual(actual, self.reference(page=2, page_size=7))

    def test_search_is_read_only(self):
        before = Article.objects.count()
        self.search.search(query="ai", page=1, page_size=7)
        self.assertEqual(Article.objects.count(), before)
