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
        self.assertContains(response, 'id="home-intro"')
        self.assertContains(response, 'id="start"')
        self.assertContains(response, 'id="values"')
        self.assertContains(response, 'id="capabilities"')
        self.assertContains(response, 'class="global-home__footer"')

        self.assertNotContains(response, 'id="discoveries"')
        self.assertNotContains(response, 'id="identity"')
        self.assertNotContains(response, 'id="apps"')
        self.assertNotContains(response, 'id="explore"')
        self.assertNotContains(response, "Featured Discoveries")
        self.assertNotContains(response, "Latest Discoveries")
        self.assertNotContains(response, "Explore topics")
        self.assertNotContains(response, "Software categories")

    def test_homepage_search_is_primary_entry_without_refinement(self):
        response = self.get_english_home()

        self.assertContains(response, f'action="{reverse("search_page")}"')
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
        discover_url = reverse("discover")

        self.assertContains(response, f'href="{discover_url}"')
        self.assertContains(response, "Explore Discover")
        self.assertContains(response, "Open Discover")

    def test_homepage_capability_surface_routes_without_replication(self):
        response = self.get_english_home()

        for url in (
            reverse("search_page"),
            reverse("discover"),
            reverse("marketplace:index"),
        ):
            self.assertContains(response, f'href="{url}"')

        self.assertContains(response, "Choose your next step")
        self.assertNotContains(response, "Checkout")
        self.assertNotContains(response, "Entitlement")
        self.assertNotContains(response, "Search results")

    def test_homepage_preserves_platform_principles_and_visual_contract(self):
        response = self.get_english_home()

        self.assertContains(response, "Global Knowledge Platform")
        self.assertContains(response, "Context, not Score")
        self.assertContains(response, "Evidence, not Truth")
        self.assertContains(response, "Portable Identity")
        self.assertContains(response, 'class="global-home__globe"')
        self.assertContains(response, 'class="global-home__globe-node"', count=3)
        self.assertNotContains(response, "global-home__atlas")

    def test_signal_navigation_matches_residual_home_sections(self):
        response = self.get_english_home()

        self.assertContains(response, "data-homepage-signal-nav")
        self.assertContains(response, 'data-signal-target="home-intro" aria-current="location"')
        self.assertContains(response, 'data-signal-target="start"')
        self.assertContains(response, 'data-signal-target="values"')
        self.assertContains(response, 'data-signal-target="capabilities"')
        self.assertContains(response, 'class="homepage-signal-nav__icon"', count=4)
        self.assertContains(response, 'stroke="currentColor"', count=4)
        self.assertContains(response, 'stroke-width="1.75"', count=4)

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
                self.assertContains(response, "canonical discovery route is available")

    def test_placeholder_does_not_define_discover_product_surface(self):
        with override("en"):
            response = self.client.get(reverse("discover"))

        self.assertNotContains(response, "Search results")
        self.assertNotContains(response, "Advanced filters")
        self.assertNotContains(response, "Checkout")
        self.assertNotContains(response, "Buy")
