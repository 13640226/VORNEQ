"""UI-01: App-Shell V8 Fundament.

Prüft Zugriffsschranke der Vorschau, serverseitiges Markup (ARIA, RTL,
Theme-Bootstrap), CSP-Verträglichkeit und die Statik-Dateien. Das
Verhalten im Browser (Drawer, Palette, Layout) prüft
quality/test-ui-01-shell-browser.mjs mit Playwright.
"""

import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

ROOT = Path(__file__).resolve().parents[2]
SHELL_CSS = ROOT / "assets" / "css" / "shell.css"
SHELL_JS = ROOT / "assets" / "js" / "shell.js"
SHELL_BASE = ROOT / "templates" / "shell" / "app_base.html"


def _url(lang="fa"):
    with translation.override(lang):
        return reverse("shell_test")


class ShellPreviewGateTests(TestCase):
    @override_settings(VORNEQ_ENV="development")
    def test_development_renders(self):
        response = self.client.get(_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("no-store", response["Cache-Control"])

    @override_settings(VORNEQ_ENV="staging")
    def test_staging_anonymous_is_404(self):
        self.assertEqual(self.client.get(_url()).status_code, 404)

    @override_settings(VORNEQ_ENV="production")
    def test_production_anonymous_is_404(self):
        self.assertEqual(self.client.get(_url()).status_code, 404)

    @override_settings(VORNEQ_ENV="production")
    def test_production_regular_user_is_404(self):
        user = get_user_model().objects.create_user(username="ui01-user")
        self.client.force_login(user)
        self.assertEqual(self.client.get(_url()).status_code, 404)

    @override_settings(VORNEQ_ENV="production")
    def test_production_staff_renders(self):
        user = get_user_model().objects.create_user(username="ui01-staff", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(_url()).status_code, 200)


@override_settings(VORNEQ_ENV="development")
class ShellMarkupTests(TestCase):
    def test_rtl_for_persian_and_ltr_for_german(self):
        fa = self.client.get(_url("fa")).content.decode()
        de = self.client.get(_url("de")).content.decode()
        self.assertRegex(fa, r'<html lang="fa" dir="rtl"')
        self.assertRegex(de, r'<html lang="de" dir="ltr"')
        self.assertIn("پیش‌نمایش قاب برنامه", fa)
        self.assertIn("Vorschau des App-Rahmens", de)

    def test_theme_bootstrap_loads_before_styles(self):
        html = self.client.get(_url()).content.decode()
        boot = html.index("js/theme-bootstrap")
        self.assertLess(boot, html.index("css/shell"))
        self.assertLess(boot, html.index("<body"))
        self.assertIn('data-theme="navy"', html)
        self.assertIn("js/theme-preference", html)
        for option in ("light", "dark", "system"):
            self.assertIn(f'data-theme-option="{option}"', html)

    def test_aria_contract(self):
        html = self.client.get(_url()).content.decode()
        self.assertIn('aria-controls="vq-sidebar" aria-expanded="false"', html)
        self.assertIn('role="dialog" aria-modal="true"', html)
        self.assertIn('role="combobox"', html)
        self.assertIn('aria-activedescendant=""', html)
        self.assertIn('role="listbox"', html)
        self.assertIn('href="#vq-main"', html)
        self.assertIn('id="vq-main"', html)

    def test_navigation_targets_resolve(self):
        html = self.client.get(_url()).content.decode()
        for name in (
            "home",
            "discover",
            "discover_knowledge",
            "marketplace:index",
            "documents:list",
            "notes:list",
        ):
            with translation.override("fa"):
                self.assertIn(f'href="{reverse(name)}"', html, name)
        self.assertIn(reverse("ai_core:chat"), html)

    def test_no_inline_script_or_handlers(self):
        html = self.client.get(_url()).content.decode()
        for match in re.finditer(r"<script\b([^>]*)>", html):
            self.assertIn("src=", match.group(1), "inline <script> would violate CSP script-src")
        self.assertIsNone(re.search(r"\son[a-z]+\s*=", html), "inline event handler")
        self.assertNotIn(' style="', html)

    def test_csp_header_present(self):
        response = self.client.get(_url())
        header = response.get("Content-Security-Policy", "")
        self.assertIn("script-src 'self'", header)
        self.assertIn("frame-ancestors 'none'", header)


class ShellStaticTests(TestCase):
    def test_css_layout_contract(self):
        css = SHELL_CSS.read_text(encoding="utf-8")
        self.assertIn("minmax(0, 1fr)", css)
        self.assertIn("100dvh", css)
        self.assertIn("--vq-target: 44px", css)
        self.assertIn('[dir="rtl"] .vq-sidebar { transform: translateX(100%); }', css)
        self.assertIn("prefers-reduced-motion", css)
        # Farben nur über die geprüften Paletten, keine eigenen Hex-Farben.
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", css))

    def test_js_has_no_eval_or_inner_html(self):
        js = SHELL_JS.read_text(encoding="utf-8")
        for forbidden in ("eval(", "new Function", "innerHTML", "document.write", ".style."):
            self.assertNotIn(forbidden, js)
        self.assertIn("aria-activedescendant", js)

    def test_existing_base_unchanged_and_shell_is_opt_in(self):
        self.assertIn("theme-bootstrap.js", SHELL_BASE.read_text(encoding="utf-8"))
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertNotIn("'css/shell.css'", base)
