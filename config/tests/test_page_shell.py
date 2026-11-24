"""Vertrag für den gemeinsamen Seitenrahmen (kein Sprung beim Seitenwechsel)."""

import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

BASE_DIR = Path(settings.BASE_DIR)
SHELL_CSS = BASE_DIR / "assets" / "css" / "page-shell.css"
BASE_TEMPLATE = BASE_DIR / "templates" / "base.html"

# Modulrahmen, die vorher eigene Breiten/Innenabstände hatten.
ALIGNED_SHELLS = (".documents", ".discover-page", ".orientation-page")


def _rule_body(css: str, selector_fragment: str) -> str:
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        if selector_fragment in match.group(1):
            return match.group(2)
    return ""


class PageShellContractTests(TestCase):
    def setUp(self):
        self.css = SHELL_CSS.read_text(encoding="utf-8")

    def test_shell_width_uses_shared_container_token(self):
        self.assertIn("--page-shell-width: var(--container-width);", self.css)

    def test_module_shells_share_width_and_spacing(self):
        body = _rule_body(self.css, ALIGNED_SHELLS[0])
        for selector in ALIGNED_SHELLS:
            self.assertIn(selector, self.css)
        self.assertIn("width: var(--page-shell-width);", body)
        self.assertIn("max-width: none;", body)
        self.assertIn("padding-inline: 0;", body)
        self.assertIn("var(--page-shell-pad-top)", body)

    def test_search_inner_shell_follows_contract(self):
        body = _rule_body(self.css, ".suchen-page__shell")
        self.assertIn("width: var(--page-shell-width);", body)

    def test_header_chrome_aligns_to_shell_edge(self):
        body = _rule_body(self.css, ".global-back__inner")
        self.assertIn(".standalone-nav__inner", self.css)
        self.assertIn("padding-inline: 0;", body)

    def test_shell_css_is_loaded_after_module_styles(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        block = template.index("{% block extra_head %}{% endblock %}")
        link = template.index("css/page-shell.css")
        self.assertGreater(link, block)
        self.assertLess(link, template.index("</head>"))

    @override_settings(STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_rendered_page_loads_shell_css_last(self):
        for lang in ("de", "fa", "en"):
            with self.subTest(lang=lang), translation.override(lang):
                response = self.client.get(reverse("orientation"))
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                head = html[: html.index("</head>")]
                stylesheets = re.findall(r'<link rel="stylesheet" href="([^"]+)"', head)
                self.assertTrue(stylesheets, "keine Stylesheets gefunden")
                self.assertTrue(stylesheets[-1].endswith("css/page-shell.css"), stylesheets[-1])
