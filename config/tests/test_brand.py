from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class BrandIntegrationTests(TestCase):
    def test_homepage_renders_brand_lockup_without_symbol_img(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode()

        self.assertContains(response, 'class="standalone-nav__brand"')
        self.assertContains(response, 'class="standalone-nav__symbol"')
        self.assertContains(response, 'class="standalone-nav__wordmark">VORNEQ</span>')

        brand_start = content.index('class="standalone-nav__brand"')
        brand_end = content.index("</a>", brand_start)
        brand_markup = content[brand_start:brand_end]
        self.assertNotIn("<img", brand_markup)

    def test_ia_s_asset_is_discoverable_by_staticfiles(self):
        asset_path = finders.find("images/brand/ia-s.svg")
        self.assertIsNotNone(asset_path)
        self.assertTrue(Path(asset_path).is_file())

    def test_navigation_css_uses_theme_driven_inline_mark_colors(self):
        css_path = finders.find("css/standalone-nav.css")
        self.assertIsNotNone(css_path)
        css = Path(css_path).read_text(encoding="utf-8")

        self.assertNotIn('mask-image: url("../images/brand/ia-s.svg")', css)
        self.assertNotIn('-webkit-mask-image: url("../images/brand/ia-s.svg")', css)

        trajectory_block = css.split(".vorneq-traj {", 1)[1].split("}", 1)[0]
        cobalt_block = css.split(".vorneq-node--cobalt {", 1)[1].split("}", 1)[0]
        discovery_block = css.split(".vorneq-node--cyan {", 1)[1].split("}", 1)[0]

        self.assertIn("stroke: currentColor;", trajectory_block)
        self.assertIn("fill: currentColor;", cobalt_block)
        self.assertIn("fill: var(--color-accent);", discovery_block)

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
