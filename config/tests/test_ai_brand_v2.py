from django.test import SimpleTestCase
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from pathlib import Path


class AIBrandTests(SimpleTestCase):
    def test_shared_markup(self):
        html = render_to_string("partials/_ai_brand.html")
        self.assertIn('data-state="idle"', html)
        self.assertIn('aria-hidden="true"', html)
        self.assertIn('ai-avatar', html)

    def test_four_styles(self):
        css = Path(finders.find("css/ai-brand.css")).read_text(encoding="utf-8")
        for state in ("thinking", "speaking", "error"):
            self.assertIn('data-state="' + state + '"', css)
        self.assertIn("prefers-reduced-motion", css)
