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


TOKENS_CSS = BASE_DIR / "assets" / "css" / "tokens.css"
STANDARD_SHELLS = (
    ".notes", ".documents", ".discover-page", ".orientation-page", ".profile-shell",
    ".profile-edit-shell", ".account-experience", ".personal-home", ".app-launcher", ".workspace",
)


class PageShellV2ContractTests(TestCase):
    """Page Shell V2: responsiver Rand, einheitlicher Kopfabstand, schmale
    Seiten an der gemeinsamen Kante, stabile Übergänge."""

    def setUp(self):
        self.css = SHELL_CSS.read_text(encoding="utf-8")
        self.tokens = TOKENS_CSS.read_text(encoding="utf-8")

    def test_gutter_is_responsive_not_a_fixed_pixel_value(self):
        self.assertRegex(self.tokens, r"--page-gutter:\s*clamp\(16px,[^;]+,\s*40px\);")
        self.assertIn(
            "--container-width: min(var(--page-max-width), calc(100vw - 2 * var(--page-gutter)));",
            self.tokens,
        )
        self.assertNotIn("calc(100vw - 48px)", self.tokens)

    def test_structural_tokens_exist(self):
        for token in (
            "--page-max-width", "--form-width", "--form-width-compact", "--button-height-md",
            "--icon-size-md", "--border-width", "--focus-ring-width",
        ):
            self.assertIn(f"{token}:", self.tokens)

    def test_standard_shells_share_top_spacing(self):
        start = self.css.index("/* 2 —")
        block = self.css[start:self.css.index("}", start)]
        for selector in STANDARD_SHELLS:
            self.assertIn(selector, block)
        self.assertIn("padding-block-start: var(--page-shell-pad-top);", block)

    def test_narrow_pages_align_to_shell_edge(self):
        start = self.css.index("/* 3 —")
        body = self.css[start:self.css.index("}", start)]
        self.assertIn("width: var(--page-shell-width);", body)
        self.assertIn("padding-inline: 0;", body)
        self.assertIn("max-width: var(--form-width);", self.css)
        self.assertIn("max-width: var(--form-width-compact);", self.css)

    def test_back_row_is_a_stable_view_transition_group(self):
        self.assertIn("view-transition-name: vorneq-back;", self.css)
        self.assertRegex(
            self.css,
            r"::view-transition-old\(vorneq-back\),\s*::view-transition-new\(vorneq-back\)\s*\{\s*animation: none;",
        )

    def test_brand_logo_is_never_mirrored_in_rtl(self):
        self.assertRegex(self.css, r'\[dir="rtl"\][^{]*standalone-nav__brand[^{]*\{\s*transform: none;')

    def test_shell_uses_logical_properties_only(self):
        for physical in ("margin-left", "margin-right", "padding-left", "padding-right", "text-align: left", "text-align: right"):
            self.assertNotIn(physical, self.css)

    def test_reduced_motion_is_respected_for_transitions(self):
        transitions = (BASE_DIR / "assets" / "css" / "transitions.css").read_text(encoding="utf-8")
        self.assertIn("@media (prefers-reduced-motion: reduce)", transitions)
        self.assertIn("@view-transition", transitions)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class PageShellRenderingTests(TestCase):
    """Öffentliche Seiten in FA/DE/EN: Richtung, Sprache, Rahmen-Elemente."""

    PAGES = ("orientation", "discover", "search_page")

    def test_pages_render_shell_chrome_in_all_languages(self):
        for lang, direction in (("fa", "rtl"), ("de", "ltr"), ("en", "ltr")):
            for name in self.PAGES:
                with self.subTest(lang=lang, page=name), translation.override(lang):
                    response = self.client.get(reverse(name))
                    self.assertEqual(response.status_code, 200)
                    html = response.content.decode()
                    self.assertRegex(html, rf'<html\s+lang="{lang}"\s+dir="{direction}"')
                    if name == "search_page":
                        self.assertIn('class="vq-header"', html)
                        self.assertIn('id="vq-sidebar"', html)
                        self.assertIn('id="vq-main"', html)
                        self.assertIn('class="vq-bottomnav"', html)
                        self.assertIn("css/search-workspace-v8.css", html)
                        self.assertIn("js/search-workspace-v8.js", html)
                        self.assertEqual(html.count('aria-current="page"'), 2)
                        self.assertIn(f'href="{reverse(name)}" aria-current="page"', html)
                        self.assertIn('data-search-view="grid"', html)
                        self.assertIn('data-search-view="list"', html)
                        self.assertIn('id="suchen-filter-panel"', html)
                        self.assertNotIn('class="global-back"', html)
                    elif name == "discover":
                        self.assertIn('class="vq-header"', html)
                        self.assertIn('id="vq-sidebar"', html)
                        self.assertIn('id="vq-main"', html)
                        self.assertIn("css/discover-workspace-v8.css", html)
                        self.assertEqual(html.count('aria-current="page"'), 3)
                        self.assertNotIn('class="global-back"', html)
                    else:
                        self.assertIn('class="global-back"', html)
                        self.assertIn('class="main-content"', html)
                        self.assertIn("css/page-shell.css", html)


class NavigationStabilityTests(TestCase):
    """Kopfhöhe darf sich weder zwischen Seiten noch beim Sprachwechsel ändern."""

    def test_tablet_navigation_stays_single_row(self):
        css = SHELL_CSS.read_text(encoding="utf-8")
        start = css.index("@media (min-width: 640px) and (max-width: 1023px)")
        block = css[start:]
        self.assertIn("flex-wrap: nowrap;", block)
        self.assertIn("overflow-x: auto;", block)
        self.assertIn('[dir="rtl"] .standalone-nav__menu', block)

    def test_layout_stability_reserves_scrollbar_and_header(self):
        stability = (BASE_DIR / "assets" / "css" / "layout-stability.css").read_text(encoding="utf-8")
        self.assertIn("scrollbar-gutter: stable", stability)
        self.assertIn("min-height: 64px", stability)
