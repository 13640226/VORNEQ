from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class HomepageResponsiveCssContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        css_path = Path(settings.BASE_DIR) / "assets" / "css" / "homepage.css"
        cls.css = css_path.read_text(encoding="utf-8")

    def test_desktop_shell_uses_1440px_max_width_with_48px_inline_space(self):
        self.assertIn(".world-home {", self.css)
        self.assertIn("max-width: 1440px;", self.css)
        self.assertIn("padding: 96px 48px 64px;", self.css)

    def test_canonical_compact_and_medium_breakpoints_are_preserved(self):
        self.assertIn(
            "@media (min-width: 640px) and (max-width: 1023px)",
            self.css,
        )
        self.assertIn("@media (max-width: 639px)", self.css)
        self.assertIn("grid-template-columns: repeat(8, minmax(0, 1fr));", self.css)
        self.assertIn("grid-template-columns: repeat(4, minmax(0, 1fr));", self.css)
        self.assertIn(".world-principles__grid", self.css)
        self.assertIn(".world-search {", self.css)
        self.assertIn("grid-template-columns: 1fr;", self.css)
