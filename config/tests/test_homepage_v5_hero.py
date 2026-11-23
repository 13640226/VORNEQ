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
        expected = {
            "en": "One Platform. Many Applications.",
            "de": "Eine Plattform. Viele Anwendungen.",
            "fa": "یک پلتفرم. اپلیکیشن‌های متعدد.",
        }
        for language, title in expected.items():
            with self.subTest(language=language):
                html = self.home(language)
                self.assertIn("vq-global-hero", html)
                self.assertIn(title, html)

    def test_real_ctas_and_target(self):
        html = self.home()
        with override("en"):
            search_url = reverse("search_page")
        self.assertIn('href="' + search_url + '"', html)
        self.assertIn('href="#vq-tools-title"', html)
        self.assertIn('id="vq-tools-title"', html)

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
        composer = (Path(settings.BASE_DIR) / "templates/home/_composer.html").read_text(encoding="utf-8")
        self.assertIn('maxlength="200"', composer)
        self.assertIn("phase_c_chat_enabled", composer)
