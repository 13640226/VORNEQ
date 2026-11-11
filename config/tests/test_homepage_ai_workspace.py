"""Homepage AI-first UI contract tests. Search handoff only; no LLM or Production access."""
import re
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.templatetags.static import static
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.translation import override


class HomepageAIWorkspaceTests(TestCase):
    def test_renders_all_languages_without_db_read(self):
        titles = {
            "en": "What would you like to explore?",
            "de": "Was möchten Sie entdecken?",
            "fa": "دوست دارید چه چیزی را کاوش کنید؟",
        }
        for language, title in titles.items():
            with self.subTest(language=language):
                with override(language), CaptureQueriesContext(connection) as queries:
                    response = self.client.get(reverse("home"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(queries), 0, "Homepage must not fetch private data")
                html = response.content.decode("utf-8")
                self.assertIn(title, html)
                self.assertIn(f'lang="{language}"', html)
                self.assertIn('dir="rtl"' if language == "fa" else 'dir="ltr"', html)

    def test_form_is_real_search_handoff_not_fake_chat(self):
        with override("en"):
            response = self.client.get(reverse("home"))
            search_url = reverse("search_page")
        html = response.content.decode("utf-8")
        self.assertIn(f'action="{search_url}"', html)
        self.assertIn('data-vq-composer', html)
        self.assertIn('name="q"', html)
        self.assertIn('maxlength="200"', html)
        self.assertIn("Live AI chat answers are not enabled here.", html)
        self.assertIn('href="#trust"', html)
        self.assertNotIn('data-vq-ai-secret', html)
        self.assertEqual(html.count('data-homepage-signal-section'), 7)
        ids = re.findall(r'\bid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)), "Duplicate HTML id detected")

    def test_progressive_enhancement_and_accessibility(self):
        with override("en"):
            response = self.client.get(reverse("home"))
        html = response.content.decode("utf-8")
        self.assertIn('id="vq-ai-question"', html)
        self.assertIn('for="vq-ai-question"', html)
        self.assertIn('aria-describedby="vq-ai-search-limitation"', html)
        self.assertIn('data-vq-example', html)
        # Resolve through the configured storage: CI runs collectstatic, so the
        # manifest storage emits hashed names (homepage-ai-workspace-v1.<hash>.css).
        self.assertIn(static("css/homepage-ai-workspace-v1.css"), html)
        self.assertIn(static("js/homepage-ai-workspace-v1.js"), html)
        self.assertIn('role="search"', html)
        self.assertIn("Platform Principles", html)

    def test_new_css_js_are_local_and_non_generative(self):
        base = Path(settings.BASE_DIR)
        css = (base / "assets/css/homepage-ai-workspace-v1.css").read_text(encoding="utf-8")
        js = (base / "assets/js/homepage-ai-workspace-v1.js").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 639px)", css)
        self.assertIn("@media (max-width: 1023px)", css)
        self.assertIn('html[dir="rtl"]', css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn('form.addEventListener("submit"', js)
        self.assertNotIn("fetch(", js)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("localStorage", js)
        self.assertNotIn("eval(", js)
