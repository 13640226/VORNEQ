"""WCAG AA contrast invariant checks for the default navy palette."""
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]


def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    return sum(weight * v for weight, v in zip((0.2126, 0.7152, 0.0722), linear))


def ratio(a, b):
    top, bottom = sorted((luminance(a), luminance(b)), reverse=True)
    return (top + 0.05) / (bottom + 0.05)


class Qa69ContrastRegressionTests(SimpleTestCase):
    def test_navy_accent_on_dark_and_text_on_accent(self):
        css = (ROOT / "assets/css/theme-palettes.css").read_text(encoding="utf-8")
        navy = css.split('[data-theme="navy"] {', 1)[1].split("}", 1)[0]
        tokens = {}
        for line in navy.splitlines():
            line = line.strip().rstrip(";")
            if line.startswith("--") and ":" in line:
                key, value = line.split(":", 1)
                tokens[key.strip()] = value.strip()
        accent, on_accent = tokens["--color-accent"], tokens["--color-text-on-accent"]
        for bg in ("#071426", "#132743", "#182b53"):
            with self.subTest(bg=bg):
                self.assertGreaterEqual(ratio(accent, bg), 4.5)
        self.assertGreaterEqual(ratio(on_accent, accent), 4.5)

    def test_dark_text_on_light_cards_and_screenreader_labels(self):
        base = (ROOT / "assets/css/base.css").read_text(encoding="utf-8")
        discover = (ROOT / "assets/css/discover.css").read_text(encoding="utf-8")
        search = (ROOT / "assets/css/search-scene.css").read_text(encoding="utf-8")
        self.assertIn(".sr-only {", base)
        self.assertIn("clip: rect(0, 0, 0, 0);", base)
        self.assertIn("color: var(--color-text-primary);", discover)
        self.assertIn("color: var(--discover-navy);", discover)
        self.assertIn("color: #0b1f3d;", search)
        self.assertGreaterEqual(ratio("#0b1f3d", "#ffffff"), 4.5)
        self.assertGreaterEqual(ratio("#475569", "#d2d5d8"), 4.5)

    def test_empty_state_heading_contrast(self):
        """Empty-state headings must not inherit pale global h3 colors on light cards."""
        discover = (ROOT / "assets/css/discover.css").read_text(encoding="utf-8")
        search = (ROOT / "assets/css/search-scene.css").read_text(encoding="utf-8")
        self.assertIn(
            ".discover-state h3 { margin-top: 0; color: var(--discover-navy); }",
            discover,
        )
        self.assertIn(
            ".world-search__card h3, .world-search__empty h3 "
            "{ margin: .55rem 0 .7rem; font-size: 1.2rem; color: #0b1f3d; }",
            search,
        )
        # WCAG AA minimum for normal text; stricter than the 3:1 for large h3.
        for background in ("#ffffff", "#f8fafc", "#d2d5d8"):
            with self.subTest(background=background):
                self.assertGreaterEqual(ratio("#0b1f3d", background), 4.5)
