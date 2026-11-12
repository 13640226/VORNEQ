"""Homepage stylesheet contract (Homepage V3 Phase A1).

The former assertions targeted ``assets/css/homepage.css``, which no template
loads since the V2 AI workspace. Responsive breakpoints of the live homepage
stylesheet are covered in ``test_homepage_ai_workspace``. This module guards
the A1 cleanup: retired stylesheets stay removed and every stylesheet a Django
template references through ``{% static %}`` actually exists.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ASSETS_CSS = Path(settings.BASE_DIR) / "assets" / "css"

RETIRED_STYLESHEETS = (
    "homepage.css",
    "homepage-modern-v2.css",
    "homepage-redesign.css",
    "homepage-signal-nav.css",
    "homepage-signal-nav-v2.css",
    "home-hero.css",
    "how-it-works-upgrade.css",
)

STATIC_CSS_RE = re.compile(r"""\{%\s*static\s+['"]css/([^'"]+\.css)['"]\s*%\}""")


def _template_files():
    base = Path(settings.BASE_DIR)
    roots = [base / "templates", *sorted((base / "apps").glob("*/templates"))]
    for root in roots:
        yield from sorted(root.rglob("*.html"))


class HomepageStylesheetContractTests(SimpleTestCase):
    def test_retired_homepage_stylesheets_are_absent(self):
        present = [name for name in RETIRED_STYLESHEETS if (ASSETS_CSS / name).exists()]
        self.assertEqual(present, [])

    def test_templates_do_not_reference_retired_stylesheets(self):
        offenders = []
        for path in _template_files():
            text = path.read_text(encoding="utf-8")
            offenders += [f"{path.name}:{name}" for name in RETIRED_STYLESHEETS if f"css/{name}" in text]
        self.assertEqual(offenders, [])

    def test_every_static_stylesheet_reference_exists(self):
        missing = []
        for path in _template_files():
            for name in STATIC_CSS_RE.findall(path.read_text(encoding="utf-8")):
                if not (ASSETS_CSS / name).is_file():
                    missing.append(f"{path.relative_to(settings.BASE_DIR)} -> css/{name}")
        self.assertEqual(missing, [])

    def test_homepage_loads_single_page_stylesheet(self):
        index = (Path(settings.BASE_DIR) / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(STATIC_CSS_RE.findall(index), ["homepage-ai-cloud-v2.css"])
