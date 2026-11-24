"""WCAG-2.2-AA-Prüfung der Theme-Tokens (Page Shell V2).

Bildet die CSS-Kaskade von tokens.css und theme-palettes.css für jedes Theme
nach (Selektorliste, Spezifität, Quellreihenfolge) und prüft die
Kontrastpaare, die überall in der Plattform als Text verwendet werden.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS_DIR = Path(settings.BASE_DIR) / "assets" / "css"
SOURCES = ("tokens.css", "theme-palettes.css")
THEMES = ("navy", "light", "vorneq", "dark", "blue", "gold", "emerald", "purple")

TEXT_TOKENS = ("text-primary", "text-secondary", "text-muted", "accent-text")
AA_NON_TEXT = 3.0
SURFACES = ("bg-page", "bg-surface", "bg-elevated")
AA_NORMAL = 4.5


def _rules():
    order = 0
    for name in SOURCES:
        css = (CSS_DIR / name).read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            decls = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", body))
            if not decls:
                continue
            for selector in selectors.split(","):
                order += 1
                yield selector.strip(), decls, order


def _applies(selector, theme):
    """Rückgabe: Spezifität (int) oder None, wenn der Selektor nicht greift."""
    if selector == ":root":
        return 10
    if selector == ":root:not([data-theme])":
        return None  # Theme ist immer gesetzt
    match = re.fullmatch(r'(:root)?\[data-theme="([a-z]+)"\]', selector)
    if match:
        if match.group(2) != theme:
            return None
        return 20 if match.group(1) else 10
    return None


def effective_tokens(theme):
    candidates = []
    for selector, decls, order in _rules():
        spec = _applies(selector, theme)
        if spec is not None:
            candidates.append((spec, order, decls))
    tokens = {}
    for _spec, _order, decls in sorted(candidates, key=lambda c: (c[0], c[1])):
        tokens.update(decls)
    # var()-Verweise auflösen
    for _ in range(5):
        for key, value in list(tokens.items()):
            ref = re.fullmatch(r"var\(--([a-z0-9-]+)\)", value.strip())
            if ref and ref.group(1) in tokens:
                tokens[key] = tokens[ref.group(1)]
    return tokens


def _rgba(value):
    value = value.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) + (1.0,)
    if re.fullmatch(r"#[0-9a-fA-F]{3}", value):
        return tuple(int(c * 2, 16) for c in value[1:]) + (1.0,)
    match = re.fullmatch(r"rgba?\(([^)]+)\)", value)
    if match:
        parts = [float(p) for p in re.split(r"[\s,/]+", match.group(1).strip())]
        return (parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else 1.0)
    raise ValueError(f"Farbe nicht lesbar: {value}")


def _over(fg, bg):
    alpha = fg[3]
    return tuple(fg[i] * alpha + bg[i] * (1 - alpha) for i in range(3)) + (1.0,)


def _luminance(color):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color[0]) + 0.7152 * channel(color[1]) + 0.0722 * channel(color[2])


def contrast(fg, bg):
    fg = _over(fg, bg)
    a, b = _luminance(fg), _luminance(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


class ThemeTokenContrastTests(SimpleTestCase):
    def test_all_themes_define_required_tokens(self):
        required = {f"color-{t}" for t in TEXT_TOKENS + SURFACES} | {
            "color-text-on-accent", "color-accent-subtle", "color-error", "color-text-on-error",
        }
        for theme in THEMES:
            with self.subTest(theme=theme):
                missing = required - set(effective_tokens(theme))
                self.assertFalse(missing, f"{theme}: fehlende Tokens {sorted(missing)}")

    def test_text_tokens_reach_aa_on_every_surface(self):
        for theme in THEMES:
            tokens = effective_tokens(theme)
            for text in TEXT_TOKENS:
                for surface in SURFACES:
                    with self.subTest(theme=theme, text=text, surface=surface):
                        ratio = contrast(_rgba(tokens[f"color-{text}"]), _rgba(tokens[f"color-{surface}"]))
                        self.assertGreaterEqual(ratio, AA_NORMAL, f"{theme} {text}/{surface} = {ratio:.2f}")

    def test_accent_reaches_non_text_contrast_on_every_surface(self):
        for theme in THEMES:
            tokens = effective_tokens(theme)
            for surface in SURFACES:
                with self.subTest(theme=theme, surface=surface):
                    ratio = contrast(_rgba(tokens["color-accent"]), _rgba(tokens[f"color-{surface}"]))
                    self.assertGreaterEqual(ratio, AA_NON_TEXT, f"{theme} accent/{surface} = {ratio:.2f}")

    def test_modules_use_accent_text_token_for_text(self):
        pattern = re.compile(r"(?<![-\w])color:\s*var\(--color-accent\)")
        root = Path(settings.BASE_DIR)
        files = list((root / "assets" / "css").glob("*.css")) + list((root / "apps").glob("*/static/**/*.css"))
        offenders = []
        for path in files:
            css = path.read_text(encoding="utf-8")
            for match in pattern.finditer(css):
                selector = css[css.rfind("}", 0, match.start()) + 1:match.start()]
                if "standalone-nav__wordmark" not in selector:  # Markenwortmarke (Hover)
                    offenders.append(f"{path.name}: {selector.strip()[:60]}")
        self.assertEqual(offenders, [])

    def test_accent_text_is_readable_on_accent_tint(self):
        for theme in THEMES:
            tokens = effective_tokens(theme)
            tint = _rgba(tokens["color-accent-subtle"])
            for surface in SURFACES:
                with self.subTest(theme=theme, surface=surface):
                    bg = _over(tint, _rgba(tokens[f"color-{surface}"]))
                    ratio = contrast(_rgba(tokens["color-accent-text"]), bg)
                    self.assertGreaterEqual(ratio, AA_NORMAL, f"{theme} accent-text/tint = {ratio:.2f}")

    def test_text_on_accent_and_error_reach_aa(self):
        for theme in THEMES:
            tokens = effective_tokens(theme)
            for fg, bg in (("text-on-accent", "accent"), ("text-on-error", "error")):
                with self.subTest(theme=theme, pair=fg):
                    ratio = contrast(_rgba(tokens[f"color-{fg}"]), _rgba(tokens[f"color-{bg}"]))
                    self.assertGreaterEqual(ratio, AA_NORMAL, f"{theme} {fg}/{bg} = {ratio:.2f}")

    def test_dark_theme_is_not_shadowed_by_navy_root_block(self):
        tokens = effective_tokens("dark")
        self.assertEqual(tokens["color-bg-page"].lower(), "#0b1120")
        css = (CSS_DIR / "tokens.css").read_text(encoding="utf-8")
        self.assertIn(':root[data-theme="dark"] {', css)

    def test_brand_reference_colors_are_available(self):
        tokens = effective_tokens("navy")
        expected = {
            "color-brand-primary": "#1e6fff",
            "color-brand-secondary": "#4a8cff",
            "color-brand-dark": "#0b1120",
            "color-brand-light": "#f8fafc",
            "color-brand-text-secondary": "#64748b",
            "color-brand-text-muted": "#94a3b8",
        }
        for key, value in expected.items():
            self.assertEqual(tokens[key].lower(), value)


class ModuleThemeBindingTests(SimpleTestCase):
    """Entdecken und Orientierung dürfen keine fest codierten Hellfarben mehr
    für Seitentext verwenden (vorher im dunklen Theme unlesbar)."""

    def test_orientation_uses_theme_tokens(self):
        css = (CSS_DIR / "orientation.css").read_text(encoding="utf-8")
        for literal in ("#0B1F3D", "#2563EB", "#E5E7EB", "background: #fff"):
            self.assertNotIn(literal, css)
        self.assertIn("--orientation-navy: var(--color-text-primary);", css)

    def test_discover_binds_local_colors_to_theme_tokens(self):
        css = (CSS_DIR / "discover.css").read_text(encoding="utf-8")
        binding = css[css.index("Page Shell V2 — Theme-Bindung"):]
        for line in (
            "--discover-navy: var(--color-text-primary);",
            "--discover-blue: var(--color-accent);",
            "color: var(--color-text-on-accent);",
            "--discover-border: var(--color-border);",
        ):
            self.assertIn(line, binding)
        self.assertRegex(binding, r"discover-pagination a[^{]*\{\s*color: var\(--color-accent-text\);")

    def test_danger_buttons_use_on_error_token(self):
        for path in (
            CSS_DIR / "account-system.css",
            CSS_DIR / "accounts.css",
            Path(settings.BASE_DIR) / "apps" / "notes" / "static" / "notes" / "notes.css",
        ):
            css = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertIn("color: var(--color-text-on-error);", css)
                self.assertNotIn("#991b1b", css)
