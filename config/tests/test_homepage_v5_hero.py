"""Homepage V5 Hero integration and safety contract."""
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomepageV5HeroTests(TestCase):
    def home(self, language="en"):
        with override(language):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        return response.content.decode("utf-8")

    def test_localized_hero_for_anonymous_visitors(self):
        """V6-02: the large V5 brand hero was removed by owner decision (product-first).

        The page now opens directly with the localized composer title; the old
        hero headline must not return.
        """
        expected = {
            "en": ("What will you create today?", "One Platform. Many Applications."),
            "de": ("Was möchten Sie heute erstellen?", "Eine Plattform. Viele Anwendungen."),
            "fa": ("امروز چه چیزی می‌خواهید بسازید؟", "یک پلتفرم. اپلیکیشن‌های متعدد."),
        }
        for language, (title, old_hero) in expected.items():
            with self.subTest(language=language):
                html = self.home(language)
                self.assertNotIn("vq-global-hero", html)
                self.assertNotIn(old_hero, html)
                self.assertIn(title, html)

    def test_real_ctas_and_target(self):
        html = self.home()
        with override("en"):
            search_url = reverse("search_page")
        self.assertIn('href="' + search_url + '"', html)
        # V6-02: in-page targets are the quick actions (#vq-create) and the app grid.
        self.assertIn('href="#vq-create"', html)
        self.assertIn('id="vq-create"', html)
        self.assertIn('id="vq-apps-title"', html)

    def test_semantics_and_composer_regression(self):
        html = self.home()
        self.assertEqual(html.count("<h1"), 1)
        ids = re.findall(r'\bid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn('method="get"', html)
        self.assertIn('maxlength="200"', html)
        self.assertIn('data-vq-composer', html)
        self.assertNotIn("data-vq-activate-ai", html)

    def test_existing_composer_source_unchanged(self):
        composer = (Path(settings.BASE_DIR) / "templates/home/v6/_composer.html").read_text(encoding="utf-8")
        self.assertIn('maxlength="200"', composer)
        self.assertIn("phase_c_chat_enabled", composer)
