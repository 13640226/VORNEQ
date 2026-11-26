"""Homepage V2 AI workspace contract. Search handoff only; no LLM or data API."""
import re
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override


class HomepageAIWorkspaceTests(TestCase):
    def get_home(self, language="en"):
        with override(language):
            return self.client.get(reverse("home"))

    def test_renders_all_languages(self):
        titles = {  # V6-02: owner-specified product titles
            "en": "What will you create today?",
            "de": "Was möchten Sie heute erstellen?",
            "fa": "امروز چه چیزی می‌خواهید بسازید؟",
        }
        for language, title in titles.items():
            with self.subTest(language=language):
                response = self.get_home(language)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, title)

    def test_form_is_real_search_handoff_not_fake_chat(self):
        with override("en"):
            search_url = reverse("search_page")
        html = self.get_home().content.decode("utf-8")
        self.assertIn(f'action="{search_url}"', html)
        self.assertIn('method="get"', html)
        self.assertIn("data-vq-composer", html)
        self.assertIn('name="q"', html)
        self.assertIn('maxlength="200"', html)
        self.assertNotIn("data-vq-ai-secret", html)
        self.assertNotIn("api/ai", html)
        ids = re.findall(r'\bid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)), "Duplicate HTML id detected")

    def test_progressive_enhancement_and_accessibility(self):
        html = self.get_home().content.decode("utf-8")
        self.assertIn('id="vq-ix-question"', html)
        self.assertIn('for="vq-ix-question"', html)
        self.assertIn('aria-describedby="vq-ix-search-limitation"', html)
        self.assertIn('aria-label="Search across VORNEQ"', html)
        self.assertIn("data-vq-example", html)
        # V6-02: the homepage stylesheet is now design system + workspace layout.
        self.assertIn(static("css/shell.css"), html)
        self.assertIn(static("css/index-workspace-v8.css"), html)
        self.assertNotIn("homepage-ai-cloud-v2.css", html)
        self.assertIn(static("js/homepage-ai-workspace-v1.js"), html)
        self.assertEqual(html.count("<h1"), 1)

    def test_css_js_are_local_and_non_generative(self):
        base = Path(settings.BASE_DIR)
        css = (base / "assets/css/v6-workspace.css").read_text(encoding="utf-8")  # V6-02 layout
        js = (base / "assets/js/homepage-ai-workspace-v1.js").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 767px)", css)  # V6-02 mobile breakpoint
        self.assertIn("@media (max-width: 1023px)", css)
        self.assertIn('html[dir="rtl"]', css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn('form.addEventListener("submit"', js)
        for forbidden in ("fetch(", "innerHTML", "localStorage", "eval(", "XMLHttpRequest"):
            self.assertNotIn(forbidden, js)

    def test_composer_keyboard_and_empty_submission_contract(self):
        """The optional JavaScript must keep the native search handoff safe."""
        base = Path(settings.BASE_DIR)
        js = (base / "assets/js/homepage-ai-workspace-v1.js").read_text(encoding="utf-8")
        self.assertIn('send.disabled = !input.value.trim()', js)
        self.assertIn('event.isComposing || event.keyCode === 229', js)
        self.assertIn('else if (send) send.click()', js)
        self.assertIn('input.value = question.slice(0, limit)', js)
        self.assertNotIn("form.submit()", js)
