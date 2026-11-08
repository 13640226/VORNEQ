import re
from html.parser import HTMLParser
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomepageSimplificationTests(TestCase):
    def get_english_home(self, params=None):
        with override("en"):
            return self.client.get(reverse("home"), data=params or {})

    def test_homepage_keeps_only_orientation_and_routing_surfaces(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="world-home ')
        self.assertContains(response, 'id="start"')
        self.assertContains(response, 'id="principles"')
        self.assertContains(response, 'id="capabilities"')

        self.assertNotContains(response, 'id="discoveries"')
        self.assertNotContains(response, 'id="identity"')
        self.assertNotContains(response, 'id="apps"')
        self.assertContains(response, 'id="explore"')
        self.assertNotContains(response, "Featured Discoveries")
        self.assertNotContains(response, "Latest Discoveries")
        self.assertNotContains(response, "Explore topics")
        self.assertNotContains(response, "Software categories")

    def test_homepage_signal_navigation_contract(self):
        response = self.get_english_home()
        html = response.content.decode()

        section_ids = (
            "home",
            "start",
            "capabilities",
            "how-it-works",
            "trust",
            "principles",
            "explore",
        )

        for section_id in section_ids:
            self.assertContains(response, f'id="{section_id}"')

        self.assertContains(response, 'href="#home"')
        self.assertContains(response, 'href="#start"')
        self.assertContains(response, 'href="#capabilities"')
        self.assertContains(response, 'href="#how-it-works"')
        self.assertContains(response, 'href="#trust"')
        self.assertContains(response, 'href="#principles"')
        self.assertContains(response, 'href="#explore"')

        self.assertEqual(
            html.count("data-homepage-signal-section"),
            7,
        )
        self.assertEqual(
            html.count("data-homepage-signal-link"),
            7,
        )

        self.assertContains(
            response,
            'aria-label="Section navigation"',
        )
        self.assertEqual(
            html.count('aria-current="location"'),
            1,
        )

        self.assertContains(
            response,
            "css/homepage-signal-nav-v2",
        )
        self.assertContains(
            response,
            "js/homepage-signal-nav-v2",
        )

        # Global navigation and homepage section navigation coexist.
        self.assertContains(response, 'class="standalone-nav')
        self.assertContains(response, 'class="homepage-signal-nav')

    def test_signal_navigation_is_homepage_only(self):
        with override("en"):
            response = self.client.get(reverse("discover"))

        self.assertNotContains(
            response,
            'class="homepage-signal-nav',
        )

    def test_homepage_search_is_primary_entry_without_refinement(self):
        response = self.get_english_home()

        with override("en"):
            search_url = reverse("search_page")

        self.assertContains(response, f'action="{search_url}"')
        self.assertContains(response, 'name="q"')
        self.assertNotContains(response, 'name="type"')
        self.assertNotContains(response, 'name="item_type"')
        self.assertNotContains(response, 'name="media_type"')
        self.assertNotContains(response, 'name="category"')
        self.assertNotContains(response, "Advanced filters")
        self.assertNotContains(response, "Quick content filters")
        self.assertNotContains(response, "Open advanced search")

    def test_homepage_has_independent_discover_handoff(self):
        response = self.get_english_home()
        with override("en"):
            discover_url = reverse("discover")

        self.assertContains(response, f'href="{discover_url}"')
        self.assertContains(response, "Open Discover")

    def test_homepage_capability_surface_routes_without_replication(self):
        response = self.get_english_home()

        with override("en"):
            expected_urls = (
                reverse("search_page"),
                reverse("discover"),
                reverse("marketplace:index"),
            )

        for url in expected_urls:
            self.assertContains(response, f'href="{url}"')

        self.assertContains(response, "Capabilities")
        self.assertContains(response, "Independent applications. Connected possibilities. Permissions remain explicit.")
        self.assertNotContains(response, "Checkout")
        self.assertNotContains(response, "Entitlement")
        self.assertNotContains(response, "Search results")

    def test_homepage_preserves_platform_principles_and_visual_contract(self):
        response = self.get_english_home()

        self.assertContains(
            response,
            "One Platform. Many Applications. Connected Possibilities.",
        )
        self.assertContains(response, "Context, not Score")
        self.assertContains(response, "Evidence, not Truth")
        self.assertContains(response, "Portable Identity")
        self.assertNotContains(response, 'class="global-home__globe"')
        self.assertNotContains(response, 'class="global-home__globe-node"')
        self.assertNotContains(response, "global-home__atlas")

    def test_home_does_not_execute_search_for_query_parameters(self):
        response = self.get_english_home({"q": "anything", "type": "product"})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Search results")
        self.assertNotContains(response, "No results found")
        self.assertNotContains(response, 'id="discoveries"')


class _DiscoverVisibleText(HTMLParser):
    """Capture visible text and purchase-control labels, not hidden CSRF values."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments = []
        self._nonvisible_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._nonvisible_depth += 1
            return
        attrs = dict(attrs)
        if tag in {"a", "button", "form", "input"}:
            for name in ("aria-label", "title"):
                if attrs.get(name):
                    self.fragments.append(attrs[name])
            if tag == "input" and attrs.get("type", "").lower() in {"submit", "button"}:
                self.fragments.append(attrs.get("value", ""))

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._nonvisible_depth = max(0, self._nonvisible_depth - 1)

    def handle_data(self, data):
        if not self._nonvisible_depth:
            self.fragments.append(data)


class DiscoverRouteContractTests(TestCase):
    def assertNoVisibleBuy(self, html):
        parser = _DiscoverVisibleText()
        parser.feed(html)
        self.assertNotRegex(" ".join(parser.fragments), re.compile(r"\bbuy\b", re.I))

    def test_canonical_discover_routes_resolve(self):
        route_names = (
            "discover",
            "discover_knowledge",
            "discover_media",
            "discover_software_services",
            "discover_products_commerce",
        )

        with override("en"):
            for route_name in route_names:
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="discover-page"')
                self.assertContains(response, 'class="discover-controls"')

    def test_placeholder_does_not_define_discover_product_surface(self):
        with override("en"):
            response = self.client.get(reverse("discover"))

        self.assertNotContains(response, "Search results")
        self.assertNotContains(response, "Advanced filters")
        self.assertNotContains(response, "Checkout")
        self.assertNoVisibleBuy(response.content.decode(response.charset))

    def test_csrf_with_buy_text_does_not_create_a_false_purchase_control(self):
        token = "a" * 16 + "Buy" + "b" * 45  # 64 characters, like a masked CSRF token.
        with patch("django.middleware.csrf._mask_cipher_secret", return_value=token):
            with override("en"):
                response = self.client.get(reverse("discover"))
        self.assertContains(response, 'value="' + token + '"')
        self.assertNoVisibleBuy(response.content.decode(response.charset))

    def test_a_real_buy_button_is_rejected_by_the_contract(self):
        with self.assertRaises(AssertionError):
            self.assertNoVisibleBuy('<button type="submit"><span>Buy now</span></button>')
