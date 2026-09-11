from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomepageSignalNavigationTests(TestCase):
    def get_english_home(self, params=None):
        """Render Home explicitly in English for stable structural assertions."""
        with override("en"):
            return self.client.get(reverse("home"), data=params or {})

    def test_homepage_renders_signal_navigation_and_semantic_anchors(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-homepage-signal-nav")
        self.assertContains(response, 'aria-label="Homepage sections"')

        self.assertContains(response, 'href="#home-intro"')
        self.assertContains(response, 'data-signal-target="home-intro"')
        self.assertContains(response, 'href="#explore"')
        self.assertContains(response, 'data-signal-target="explore"')
        self.assertContains(response, 'href="#values"')
        self.assertContains(response, 'data-signal-target="values"')
        self.assertContains(response, 'href="#apps"')
        self.assertContains(response, 'data-signal-target="apps"')
        self.assertNotContains(response, 'data-signal-target="discoveries"')

        self.assertContains(response, 'id="home-intro"')
        self.assertContains(response, 'id="explore"')
        self.assertContains(response, 'id="values"')
        self.assertContains(response, 'id="discoveries"')
        self.assertContains(response, 'id="identity"')
        self.assertContains(response, 'id="apps"')
        self.assertNotContains(response, 'id="trust"')
        self.assertNotContains(response, 'id="platform"')

        self.assertContains(response, ">Discover</")
        self.assertContains(response, ">Explore</")
        self.assertContains(response, ">Principles</")
        self.assertContains(response, ">Capabilities</")

        self.assertNotContains(response, "Platform status")
        self.assertNotContains(response, "Apps, Registry, Launcher & Workspace")
        self.assertNotContains(response, "Capability discovery")
        self.assertNotContains(response, "Future contract")
        self.assertNotContains(response, "Executable providers & integrations")

    def test_homepage_preserves_live_search_contract(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form method="get" class="global-search"')
        self.assertContains(response, 'name="type"')
        self.assertContains(response, 'class="global-search__advanced"')
        self.assertContains(response, "Advanced filters")
        self.assertContains(response, 'class="quick-filters global-home__quick-filters"')
        self.assertContains(response, "Open advanced search")
        self.assertContains(
            response,
            "Search knowledge, software, products, services, media, and more…",
        )

    def test_homepage_preserves_right_rail_and_adds_four_action_cards(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="right-rail global-home__right-rail"')
        self.assertContains(response, 'class="global-home__feature-card"', count=3)
        self.assertContains(response, 'class="global-home__action-card"', count=4)

        self.assertContains(response, "Identity across experiences, not app-local.")
        self.assertContains(response, "Find relevant resources")
        self.assertContains(response, "Save and organize your findings")
        self.assertContains(response, "Discover complementary tools and services")

        self.assertContains(
            response,
            "Search across knowledge, software, products, services, documents, media, and more.",
        )
        self.assertContains(
            response,
            "Save, tag, and structure your findings so they remain usable.",
        )
        self.assertContains(
            response,
            "Discover complementary software, tools, and specialized services.",
        )
        self.assertContains(
            response,
            "Explore digital and physical products and professional services.",
        )

        with override("en"):
            expected_urls = (
                reverse("search_page"),
                reverse("notes:list"),
                reverse("marketplace:index"),
            )

        for url in expected_urls:
            self.assertContains(response, f'href="{url}"')

        self.assertNotContains(response, "Open Launcher")
        self.assertNotContains(response, "Workspace")
        self.assertNotContains(response, "Registry")
        self.assertNotContains(response, "Manifest")

    def test_homepage_renders_platform_philosophy_without_overclaiming(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Global Knowledge Platform")
        self.assertContains(
            response,
            "Context, not Score · Evidence, not Truth · Portable Identity",
        )
        self.assertContains(response, "Context, not Score")
        self.assertContains(response, "Evidence, not Truth")
        self.assertContains(response, "Portable Identity")
        self.assertContains(
            response,
            "Information should be understood in context rather than reduced to a single, opaque score.",
        )
        self.assertContains(
            response,
            "Expose sources, evidence, and perspectives so you can form your own conclusions.",
        )
        self.assertContains(
            response,
            "Your identity is designed to travel across experiences, not be trapped in a single app.",
        )
        self.assertNotContains(response, "AI Search")
        self.assertNotContains(response, "Buy")
        self.assertNotContains(response, "Checkout")
        self.assertNotContains(response, "Trade")

    def test_homepage_signal_navigation_has_accessible_initial_state(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'data-signal-target="home-intro" aria-current="location"',
        )
        self.assertContains(
            response,
            'class="homepage-signal-nav__dot" aria-hidden="true"',
        )

    def test_homepage_loads_signal_navigation_assets_without_replacing_global_nav(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/static/css/homepage-signal-nav')
        self.assertContains(response, 'src="/static/js/homepage-signal-nav')
        self.assertContains(response, 'class="standalone-nav"')
        self.assertContains(response, 'class="standalone-nav__menu"')

    def test_discoveries_dashboard_stays_rendered_when_feed_is_empty(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="discoveries"')
        self.assertContains(response, "No public discoveries are available yet.")
        self.assertNotContains(response, 'data-signal-target="discoveries"')

    def test_discoveries_live_surface_is_preserved_for_filtered_requests(self):
        response = self.get_english_home({"q": "no-matching-query-expected"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="discoveries"')
        self.assertContains(response, "Search results")
        self.assertContains(response, "No results found")
        self.assertNotContains(response, 'data-signal-target="discoveries"')
