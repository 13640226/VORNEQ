from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class BrandIntegrationTests(TestCase):
    def test_homepage_renders_canonical_wordmark_without_decorative_symbol(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode()

        self.assertContains(response, 'class="standalone-nav__brand"')
        self.assertNotContains(response, 'class="standalone-nav__symbol"')
        self.assertContains(response, 'class="standalone-nav__wordmark">VORNEQ</span>')

        brand_start = content.index('class="standalone-nav__brand"')
        brand_end = content.index("</a>", brand_start)
        brand_markup = content[brand_start:brand_end]
        self.assertNotIn("<img", brand_markup)
        self.assertNotIn("<svg", brand_markup)
        self.assertNotIn("vorneq-node", brand_markup)
        self.assertNotIn("vorneq-traj", brand_markup)

    def test_ia_s_asset_is_discoverable_by_staticfiles(self):
        asset_path = finders.find("images/brand/ia-s.svg")
        self.assertIsNotNone(asset_path)
        self.assertTrue(Path(asset_path).is_file())

    def test_navigation_css_keeps_brand_neutral_and_removes_decorative_mark_rules(self):
        css_path = finders.find("css/standalone-nav.css")
        self.assertIsNotNone(css_path)
        css = Path(css_path).read_text(encoding="utf-8")

        self.assertNotIn('mask-image: url("../images/brand/ia-s.svg")', css)
        self.assertNotIn('-webkit-mask-image: url("../images/brand/ia-s.svg")', css)
        self.assertNotIn(".standalone-nav__symbol", css)
        self.assertNotIn(".vorneq-mark", css)
        self.assertNotIn(".vorneq-traj", css)
        self.assertNotIn(".vorneq-node--cobalt", css)
        self.assertNotIn(".vorneq-node--cyan", css)
        self.assertNotIn("@keyframes vorneq-logo-rotate", css)

        wordmark_block = css.split(".standalone-nav__wordmark {", 1)[1].split("}", 1)[0]
        self.assertIn("color: var(--color-text-primary);", wordmark_block)
        self.assertIn(
            ".standalone-nav__brand:hover .standalone-nav__wordmark,",
            css,
        )
        self.assertIn(
            ".standalone-nav__brand:focus-visible .standalone-nav__wordmark {",
            css,
        )
        self.assertIn("color: var(--color-accent);", css)

    def test_vorneq_theme_uses_brand_blue_without_changing_semantic_state_tokens(self):
        palette_path = finders.find("css/theme-palettes.css")
        self.assertIsNotNone(palette_path)
        palette = Path(palette_path).read_text(encoding="utf-8")

        vorneq_block = palette.split('[data-theme="vorneq"] {', 1)[1].split("}", 1)[0]
        self.assertIn("--color-accent: #1e6fff;", vorneq_block)
        self.assertIn("--color-focus: #1e6fff;", vorneq_block)
        self.assertNotIn("--color-success", vorneq_block)
        self.assertNotIn("--color-warning", vorneq_block)
        self.assertNotIn("--color-error", vorneq_block)

    def test_navy_is_default_runtime_theme_and_selectable_preference(self):
        project_root = Path(__file__).resolve().parents[2]
        base = (project_root / "templates" / "base.html").read_text(encoding="utf-8")
        profile = (project_root / "templates" / "profile.html").read_text(encoding="utf-8")

        preference_path = finders.find("js/theme-preference.js")
        selector_path = finders.find("css/theme-selector.css")
        self.assertIsNotNone(preference_path)
        self.assertIsNotNone(selector_path)
        preference = Path(preference_path).read_text(encoding="utf-8")
        selector = Path(selector_path).read_text(encoding="utf-8")

        bootstrap_path = finders.find("js/theme-bootstrap.js")
        self.assertIsNotNone(bootstrap_path)
        bootstrap = Path(bootstrap_path).read_text(encoding="utf-8")

        self.assertIn("js/theme-bootstrap.js", base)
        self.assertIn("var valid = ['navy',", bootstrap)
        self.assertIn("var preference = 'navy';", bootstrap)
        self.assertIn("localStorage.getItem('vorneq-theme') || 'navy'", bootstrap)
        self.assertIn("navy: '#071426'", bootstrap)

        self.assertIn("const DEFAULT_THEME = 'navy';", preference)
        self.assertIn("'navy',", preference)
        self.assertIn("navy: '#071426'", preference)

        self.assertIn('data-theme-option="navy"', profile)
        self.assertIn("theme-selector-preview--navy", profile)
        self.assertIn(".theme-selector-preview--navy", selector)
