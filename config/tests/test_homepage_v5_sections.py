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
            # V6-02: the four V5 sections were merged into the application grid and a
            # compact evidence strip; the long philosophy text was removed (owner decision).
            for name in ("Applications", "Evidence and sources", "Image Studio", "AI chat"):
                self.assertIn(name, html)
            for removed in ("Application Explorer", "Platform Philosophy"):
                self.assertNotIn(removed, html)
            for route in ("search_page", "discover", "marketplace:index", "orientation", "inspect_entry", "discover_knowledge"):
                self.assertIn('href="' + reverse(route) + '"', html)
            self.assertNotIn('href="' + reverse("documents:list") + '"', html)
            self.assertNotIn('href="' + reverse("notes:list") + '"', html)
            self.assertNotIn('data-vq-activate-ai', html)

    def test_anonymous_ai_card_is_not_a_link(self):
        with override("en"):
            html = self.client.get(reverse("home")).content.decode()
            self.assertIn('Sign in required', html)
            self.assertNotIn(reverse('ai_core:chat'), html)
            self.assertNotIn(reverse('ai_core:image-studio'), html)
            self.assertIn('href="' + reverse('account_login') + '"', html)
            self.assertNotIn('href="' + reverse("ai_core:chat") + '"', html)

    def test_all_three_languages(self):
        for lang in ("en", "de", "fa"):
            with self.subTest(lang=lang), override(lang):
                response = self.client.get(reverse("home"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="vq-ix-apps-title"')  # V6-02 ids
                self.assertContains(response, 'id="vq-ix-trust-title"')
