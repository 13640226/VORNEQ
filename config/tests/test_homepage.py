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
        self.assertContains(response, 'class="world-home"')
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
        self.assertNotContains(response, "Checkout")
        self.assertNotContains(response, "Entitlement")
        self.assertNotContains(response, "Search results")

    def test_homepage_preserves_platform_principles_and_visual_contract(self):
        response = self.get_english_home()

        self.assertContains(
            response,
            "Precision infrastructure for a trusted digital future.",
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


class DiscoverRouteContractTests(TestCase):
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
        self.assertNotContains(response, "Buy")