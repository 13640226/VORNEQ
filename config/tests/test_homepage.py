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

    def test_discoveries_signal_is_only_rendered_when_results_surface_exists(self):
        """
        در redesign جدید، بخش discoveries همیشه رندر می‌شود.
        در صورت نبود نتیجه، empty state نمایش داده می‌شود.
        """
        response = self.client.get('/')
        self.assertContains(response, 'id="discoveries"')
        self.assertContains(response, 'No public discoveries are available yet.')
