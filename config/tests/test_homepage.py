from django.test import TestCase
from django.urls import reverse


class HomepageSignalNavigationTests(TestCase):
    def test_homepage_renders_signal_navigation_and_semantic_anchors(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-homepage-signal-nav')
        self.assertContains(response, 'aria-label="Homepage sections"')
        self.assertContains(response, 'href="#home-intro"')
        self.assertContains(response, 'href="#trust"')
        self.assertContains(response, 'href="#apps"')
        self.assertContains(response, 'href="#platform"')
        self.assertContains(response, 'id="home-intro"')
        self.assertContains(response, 'id="trust"')
        self.assertContains(response, 'id="apps"')
        self.assertContains(response, 'id="platform"')

    def test_homepage_signal_navigation_has_accessible_initial_state(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'data-signal-target="home-intro" aria-current="location"')
        self.assertContains(response, 'class="homepage-signal-nav__dot" aria-hidden="true"')

    def test_homepage_loads_signal_navigation_assets_without_replacing_global_nav(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'href="/static/css/homepage-signal-nav')
        self.assertContains(response, 'src="/static/js/homepage-signal-nav')
        self.assertContains(response, 'class="standalone-nav"')
        self.assertContains(response, 'class="standalone-nav__menu"')

    def test_discoveries_dashboard_stays_rendered_while_signal_tracks_results(self):
        response = self.client.get(reverse("home"))

        self.assertNotContains(response, 'data-signal-target="discoveries"')
        self.assertContains(response, 'id="discoveries"')
        self.assertContains(response, 'class="global-home__result global-home__empty-state"')

        filtered = self.client.get(reverse("home"), {"q": "no-matching-query-expected"})
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, 'data-signal-target="discoveries"')
        self.assertContains(filtered, 'id="discoveries"')
