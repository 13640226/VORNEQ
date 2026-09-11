from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class HomepageResponsiveCssContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        css_path = Path(settings.BASE_DIR) / "assets" / "css" / "homepage.css"
        cls.css = css_path.read_text(encoding="utf-8")

    def test_desktop_shell_uses_1280px_max_width_with_32px_inline_space(self):
        self.assertIn(
            ".global-home__shell{width:min(1280px,calc(100% - 64px));margin-inline:auto}",
            self.css,
        )

    def test_tablet_breakpoint_stacks_hero_at_1024px_boundary(self):
        self.assertIn(
            "@media(max-width:1023px){.global-home__brand-row{grid-template-columns:1fr;gap:var(--space-5)}",
            self.css,
        )
