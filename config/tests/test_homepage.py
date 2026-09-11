from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomepageSignalNavigationTests(TestCase):
    def get_english_home(self, params=None):
        """
        Render Home explicitly in English.

        Homepage structural tests should not accidentally depend on
        LANGUAGE_CODE or the language selected by another test.
        """
        with override("en"):
            return self.client.get(
                reverse("home"),
                data=params or {},
            )

    def test_homepage_renders_signal_navigation_and_semantic_anchors(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "data-homepage-signal-nav")
        self.assertContains(response, 'aria-label="Homepage sections"')

        self.assertContains(response, 'href="#home-intro"')
        self.assertContains(response, 'href="#trust"')
        self.assertContains(response, 'href="#apps"')
        self.assertContains(response, 'href="#platform"')

        self.assertContains(response, 'id="home-intro"')
        # #162 intentionally keeps the Trust section out of the DOM until a
        # complete KPI data contract exists. Restore a positive Trust-section
        # assertion only when all required KPI values are valid and renderable.
        self.assertNotContains(response, 'id="trust"')
        self.assertContains(response, 'id="identity"')
        self.assertContains(response, 'id="apps"')
        self.assertContains(response, 'id="platform"')

    def test_homepage_renders_platform_philosophy_without_overclaiming(self):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Discoverable Knowledge Platform")
        self.assertContains(
            response,
            "VORNEQ does not decide what is true, trustworthy, or valuable.",
        )
        self.assertContains(
            response,
            "Context, not Score · Evidence, not Truth · Portable Identity",
        )
        # Trust copy remains intentionally absent with the Trust section until
        # a complete KPI data contract exists and all required KPI values are valid.
        self.assertNotContains(
            response,
            "Verification produces inspectable findings and evidence about an assertion",
        )
        self.assertContains(
            response,
            "Identity is designed to be portable across experiences rather than app-local.",
        )
        self.assertNotContains(response, "Your identity moves across experiences")

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

    def test_homepage_loads_signal_navigation_assets_without_replacing_global_nav(
        self,
    ):
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'href="/static/css/homepage-signal-nav',
        )
        self.assertContains(
            response,
            'src="/static/js/homepage-signal-nav',
        )

        self.assertContains(response, 'class="standalone-nav"')
        self.assertContains(response, 'class="standalone-nav__menu"')

    def test_discoveries_dashboard_stays_rendered_when_feed_is_empty(self):
        """
        The redesign always renders the discoveries dashboard.

        With no public discoveries, the dashboard contains the empty
        state. The signal-navigation link itself remains conditional.
        """
        response = self.get_english_home()

        self.assertEqual(response.status_code, 200)

        # Dashboard itself always exists.
        self.assertContains(response, 'id="discoveries"')

        # No result surface means no discoveries item in signal nav.
        self.assertNotContains(
            response,
            'data-signal-target="discoveries"',
        )

        # Empty state from templates/index.html.
        self.assertContains(
            response,
            "No public discoveries are available yet.",
        )

    def test_discoveries_signal_is_rendered_for_filtered_surface(self):
        response = self.get_english_home(
            {
                "q": "no-matching-query-expected",
            }
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'id="discoveries"')
        self.assertContains(
            response,
            'data-signal-target="discoveries"',
        )
