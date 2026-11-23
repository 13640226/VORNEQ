"""Homepage V5 public discovery and authorization presentation tests."""
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomepageV5SectionsTests(TestCase):
    def test_public_sections_and_real_routes(self):
        with override("en"):
            response = self.client.get(reverse("home"))
            html = response.content.decode()
            self.assertEqual(response.status_code, 200)
            for name in ("Application Explorer", "AI Studio", "Trust Center", "Platform Philosophy"):
                self.assertIn(name, html)
            for route in ("search_page", "discover", "marketplace:index", "orientation", "inspect_entry", "discover_knowledge"):
                self.assertIn('href="' + reverse(route) + '"', html)
            self.assertNotIn('href="' + reverse("documents:list") + '"', html)
            self.assertNotIn('href="' + reverse("notes:list") + '"', html)
            self.assertNotIn('data-vq-activate-ai', html)

    def test_anonymous_ai_card_is_not_a_link(self):
        with override("en"):
            html = self.client.get(reverse("home")).content.decode()
            self.assertIn('vq-v5-card--disabled', html)
            self.assertIn('Availability not confirmed', html)
            self.assertNotIn('href="' + reverse("ai_core:chat") + '"', html)

    def test_all_three_languages(self):
        for lang in ("en", "de", "fa"):
            with self.subTest(lang=lang), override(lang):
                response = self.client.get(reverse("home"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="vq-v5-apps-title"')
                self.assertContains(response, 'id="vq-v5-trust-title"')
