from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.content.models import Article
from apps.search.narrow_window import _cte_rows
from apps.search.services import ArticleAdapter


class NarrowCteBuilderTests(TestCase):
    def test_cte_rows_uses_shared_sql_builder(self):
        adapter = ArticleAdapter()
        queryset = Article.objects.filter(is_published=True)

        with patch(
            "apps.search.narrow_window.build_narrow_cte_sql",
            return_value=("SELECT * FROM content_article WHERE 1 = 0", ()),
        ) as builder:
            rows = _cte_rows(adapter, queryset, 12)

        self.assertEqual(rows, [])
        builder.assert_called_once_with(adapter, queryset, 12)

    def test_nonpositive_limit_does_not_build_or_execute_sql(self):
        adapter = ArticleAdapter()
        queryset = Article.objects.filter(is_published=True)

        with patch("apps.search.narrow_window.build_narrow_cte_sql") as builder:
            self.assertEqual(_cte_rows(adapter, queryset, 0), [])

        builder.assert_not_called()
