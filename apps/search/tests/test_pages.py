from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.search.services import UnifiedSearch


EMPTY_SEARCH_PAYLOAD = {
    "results": [],
    "total": 0,
    "page": 1,
    "total_pages": 1,
    "has_next": False,
    "has_previous": False,
}


class HomeSearchBoundaryTests(TestCase):
    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_does_not_execute_search_or_forward_advanced_filters(self, collect):
        response = self.client.get(
            reverse("home"),
            {
                "q": "Knowledge",
                "type": "product",
                "item_type": "book",
                "media_type": "image",
                "category": "ebook",
                "price_min": "1.50",
                "price_max": "9.99",
            },
        )

        self.assertEqual(response.status_code, 200)
        collect.assert_not_called()
        self.assertContains(response, 'name="q"')
        self.assertNotContains(response, 'name="type"')
        self.assertNotContains(response, 'name="item_type"')
        self.assertNotContains(response, 'name="media_type"')
        self.assertNotContains(response, 'name="category"')
        self.assertNotContains(response, 'name="price_min"')
        self.assertNotContains(response, 'name="price_max"')
        self.assertNotContains(response, "Advanced filters")
        self.assertNotContains(response, "Quick content filters")

    @patch.object(
        UnifiedSearch,
        "collect",
        return_value=[
            {
                "type": "article",
                "title": "Legacy Home result",
                "description": "Legacy result presentation",
                "url": None,
            }
        ],
    )
    def test_home_does_not_render_query_results_or_featured_feed(self, collect):
        response = self.client.get(reverse("home"), {"q": "article"})

        self.assertEqual(response.status_code, 200)
        collect.assert_not_called()
        self.assertNotContains(response, "Legacy Home result")
        self.assertNotContains(response, "Featured discovery")
        self.assertNotContains(response, "Latest Discoveries")
        self.assertNotContains(response, 'id="discoveries"')

    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_keeps_search_as_handoff_only(self, collect):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        collect.assert_not_called()
        self.assertContains(response, 'role="search"')
        self.assertContains(response, f'action="{reverse("search_page")}"')
        self.assertContains(response, "Start searching")


class StandaloneSearchPageTests(TestCase):
    @patch.object(UnifiedSearch, "search", return_value=EMPTY_SEARCH_PAYLOAD)
    def test_search_page_uses_full_allowlisted_filter_set(self, search):
        response = self.client.get(
            reverse("search_page"),
            {
                "q": "Library",
                "type": "libraryitem",
                "item_type": "document",
                "media_type": "video",
                "category": "research",
                "price_min": "2",
                "price_max": "20",
                "page": "2",
                "page_size": "999",
            },
        )

        self.assertEqual(response.status_code, 200)
        kwargs = search.call_args.kwargs
        self.assertEqual(kwargs["filters"]["types"], {"libraryitem"})
        self.assertEqual(kwargs["filters"]["item_type"], "document")
        self.assertEqual(kwargs["filters"]["media_type"], "video")
        self.assertEqual(kwargs["filters"]["category"], "research")
        self.assertEqual(kwargs["filters"]["price_min"], Decimal("2"))
        self.assertEqual(kwargs["filters"]["price_max"], Decimal("20"))
        self.assertEqual(kwargs["page"], 2)
        self.assertEqual(kwargs["page_size"], UnifiedSearch.MAX_PAGE_SIZE)

    @patch.object(UnifiedSearch, "search", return_value=EMPTY_SEARCH_PAYLOAD)
    def test_search_results_ui_stays_metadata_only(self, search):
        response = self.client.get(reverse("search_page"), {"q": "public"})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "trust_score")
        self.assertNotContains(response, "contextual_reputation")
        self.assertNotContains(response, "Canonical identity")
        self.assertNotContains(response, "Verification badge")
        self.assertContains(response, 'name="type"')
        self.assertContains(response, 'name="item_type"')
        self.assertContains(response, 'name="media_type"')
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="price_min"')
        self.assertContains(response, 'name="price_max"')
