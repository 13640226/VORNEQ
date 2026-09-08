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


class HomeSearchExpansionTests(TestCase):
    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_forwards_supported_filters(self, collect):
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
        filters = collect.call_args.kwargs["filters"]
        self.assertEqual(filters["types"], {"product"})
        self.assertNotIn("item_type", filters)
        self.assertEqual(filters["media_type"], "image")
        self.assertEqual(filters["category"], "ebook")
        self.assertEqual(filters["price_min"], Decimal("1.50"))
        self.assertEqual(filters["price_max"], Decimal("9.99"))
        self.assertContains(response, 'name="item_type"')
        self.assertContains(response, 'name="media_type"')
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="price_min"')
        self.assertContains(response, 'name="price_max"')

    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_ignores_invalid_advanced_filters(self, collect):
        self.client.get(
            reverse("home"),
            {
                "item_type": "private",
                "media_type": "audio",
                "price_min": "-1",
                "price_max": "not-a-number",
            },
        )

        filters = collect.call_args.kwargs["filters"]
        self.assertNotIn("item_type", filters)
        self.assertNotIn("media_type", filters)
        self.assertNotIn("price_min", filters)
        self.assertNotIn("price_max", filters)

    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_type_book_keeps_implied_item_type(self, collect):
        self.client.get(
            reverse("home"),
            {"type": "book", "item_type": "document"},
        )

        filters = collect.call_args.kwargs["filters"]
        self.assertEqual(filters["types"], {"libraryitem"})
        self.assertEqual(filters["item_type"], "book")

    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_type_all_allows_item_type(self, collect):
        self.client.get(
            reverse("home"),
            {"type": "all", "item_type": "document"},
        )

        filters = collect.call_args.kwargs["filters"]
        self.assertNotIn("types", filters)
        self.assertEqual(filters["item_type"], "document")

    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_type_article_keeps_implied_item_type(self, collect):
        self.client.get(
            reverse("home"),
            {"type": "article", "item_type": "book"},
        )

        filters = collect.call_args.kwargs["filters"]
        self.assertEqual(filters["types"], {"article", "libraryitem"})
        self.assertEqual(filters["item_type"], "article")

    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_type_audio_ignores_item_type(self, collect):
        self.client.get(
            reverse("home"),
            {"type": "audio", "item_type": "document"},
        )

        filters = collect.call_args.kwargs["filters"]
        self.assertEqual(filters["types"], {"audio"})
        self.assertNotIn("item_type", filters)

    @patch.object(
        UnifiedSearch,
        "collect",
        return_value=[
            {
                "type": "article",
                "title": "Article without route",
                "description": "Article summary",
                "url": None,
            }
        ],
    )
    def test_home_displays_article_without_url(self, collect):
        response = self.client.get(reverse("home"), {"q": "article"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Article without route")
        self.assertContains(response, "<h3>Article without route</h3>", html=True)

    @patch.object(
        UnifiedSearch,
        "collect",
        return_value=[
            {
                "type": "mediaasset",
                "title": "Media without route",
                "description": "Media metadata",
                "url": None,
            }
        ],
    )
    def test_home_displays_media_without_url(self, collect):
        response = self.client.get(reverse("home"), {"q": "media"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Media without route")
        self.assertContains(response, "<h3>Media without route</h3>", html=True)

    @patch.object(
        UnifiedSearch,
        "collect",
        return_value=[
            {
                "type": "product",
                "title": "Linked product",
                "description": "Product summary",
                "url": "/products/example/",
            }
        ],
    )
    def test_home_keeps_link_for_result_with_url(self, collect):
        response = self.client.get(reverse("home"), {"q": "product"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<h3><a href="/products/example/">Linked product</a></h3>',
            html=True,
        )

    @patch.object(
        UnifiedSearch,
        "collect",
        return_value=[
            {
                "type": "product",
                "title": "Featured product",
                "description": "Lead item",
                "url": "/products/featured/",
            },
            {
                "type": "article",
                "title": "Second discovery",
                "description": "Feed item",
                "url": None,
            },
        ],
    )
    def test_home_uses_first_page_item_as_presentation_featured(self, collect):
        response = self.client.get(reverse("home"), {"q": "dashboard"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["featured"][0]["title"], "Featured product")
        self.assertEqual(response.context["results"][0]["title"], "Second discovery")
        self.assertEqual(response.context["total_results"], 2)
        self.assertContains(response, "Featured discovery")

    @patch.object(UnifiedSearch, "collect", return_value=[])
    def test_home_exposes_contract_safe_quick_filters_and_informative_trust(self, collect):
        response = self.client.get(reverse("home"), {"q": "dashboard"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["value"] for item in response.context["quick_filters"]],
            ["product", "book", "article", "document", "audio"],
        )
        self.assertContains(response, "No global trust score")
        self.assertContains(response, "Verification is evidence about an assertion")
        self.assertContains(response, "Reputation is contextual")
        self.assertNotContains(response, "trust_score")
        self.assertNotContains(response, "contextual_reputation")


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
