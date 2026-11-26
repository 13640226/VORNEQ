"""Product UI V6-02 (Complete Visual Transformation): product-first workspace contract.

Rendering, gating, privacy, accessibility, i18n and design-system checks. The AI
provider and the OpenAI client are patched to fail (V3 mixin), so any AI call from
the homepage would fail the test run. No network, no paid request.
"""
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse
from django.utils import timezone, translation

from config import views
from config.tests.test_homepage_v3 import DEV_AI, NoProviderMixin, home_fragment, parse

CSS_DIR = Path(settings.BASE_DIR) / "assets" / "css"
DS = (CSS_DIR / "v6-design-system.css").read_text(encoding="utf-8")
WS = (CSS_DIR / "v6-workspace.css").read_text(encoding="utf-8")
JS = (Path(settings.BASE_DIR) / "assets" / "js" / "v6-workspace.js").read_text(encoding="utf-8")


def block(css, selector):
    start = css.index(selector)
    return css[start:css.index("}", start)]


def var(css_block, name):
    return re.search(re.escape(name) + r":\s*(#[0-9a-fA-F]{6})", css_block).group(1)


def contrast(a, b):
    def lum(h):
        rgb = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        rgb = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def tint(fg, bg, alpha):
    return "#" + "".join(
        f"{round(int(fg[i:i + 2], 16) * alpha + int(bg[i:i + 2], 16) * (1 - alpha)):02x}" for i in (1, 3, 5))


def section(html, start_marker, end_tag):
    start = html.index(start_marker)
    return html[start:html.index(end_tag, start)]


class HomepageV602RenderingTests(NoProviderMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="home-v602", password="synthetic-only")

    def get(self, lang="en", **overrides):
        with translation.override(lang), override_settings(**overrides):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    # --- structure ------------------------------------------------------------
    def test_guest_gets_product_shell_not_landing_page(self):
        html = self.get()
        for marker in ('class="vq-header"', 'class="vq-sidebar"', 'class="vq-ix"', 'class="vq-ix-hero"',
                       'class="vq-ix-section vq-ix-quick"', 'class="vq-ix-section vq-ix-apps"', 'class="vq-bottomnav"'):
            self.assertIn(marker, html)
        for removed in ("vq-global-hero", "vq-v5-sections", "vq-rail", "One Platform. Many Applications.",
                        "Platform Philosophy", 'class="standalone-nav'):
            self.assertNotIn(removed, html)
        fragment = home_fragment(html)
        self.assertLess(fragment.index('id="vq-ix-title"'), fragment.index('class="vq-ix-section vq-ix-apps"'))

    def test_guest_homepage_has_no_private_data_and_no_queries(self):
        with CaptureQueriesContext(connection) as ctx:
            html = self.get()
        self.assertEqual(len(ctx.captured_queries), 0)
        self.assertNotIn("vq-ix-recent", html)
        self.assertNotIn(reverse("documents:list"), html)
        self.assertIn(f'href="{reverse("account_login")}"', html)

    def test_authenticated_shell_menu_and_private_navigation(self):
        self.client.force_login(self.user)
        html = self.get()
        side = section(html, '<nav id="vq-sidebar"', "</nav>")
        for name in ("profile", "profile_edit", "platform_shell:personal_home", "account_logout", "documents:list", "notes:list"):
            self.assertIn(f'href="{reverse(name)}"', side)
        header = section(html, '<header class="vq-header"', "</header>")
        self.assertIn(f'href="{reverse("platform_shell:personal_home")}"', header)
        self.assertNotIn(f'href="{reverse("account_login")}"', header)


    # --- header -------------------------------------------------------------------
    def test_header_controls_are_real_and_labelled(self):
        header = section(self.get(), '<header class="vq-header"', "</header>")
        self.assertRegex(header, r'data-vq-drawer-open aria-controls="vq-sidebar" aria-expanded="false" aria-label="[^"]+"')
        for theme in ("light", "dark", "system"):
            self.assertRegex(header, rf'data-theme-option="{theme}" aria-pressed="false" aria-label="[^"]+"')
        self.assertIn('data-vq-cmd-open', header)
        self.assertIn('aria-controls="vq-cmd"', header)
        self.assertEqual(header.count(f'action="{reverse("set_language")}" method="post"'), 3)
        self.assertEqual(header.count('name="csrfmiddlewaretoken"'), 3)
        self.assertNotIn("bell", header)


    def test_header_height_token_is_compact(self):
        css = (CSS_DIR / "shell.css").read_text(encoding="utf-8")
        self.assertIn("--vq-header-h: 52px;", css)
        self.assertIn("height: var(--vq-header-h)", block(css, ".vq-header {"))
        self.assertIn("position: sticky", block(css, ".vq-header {"))


    # --- sidebar ----------------------------------------------------------------------
    def test_sidebar_links_resolve_and_home_is_current(self):
        self.client.force_login(self.user)
        html = self.get(**DEV_AI)
        side = section(html, '<nav id="vq-sidebar"', "</nav>")
        hrefs = re.findall(r'<a [^>]*href="([^"]+)"', side)
        self.assertGreaterEqual(len(hrefs), 10)
        for href in hrefs:
            resolve(href.split("?")[0])
        self.assertEqual(side.count('aria-current="page"'), 1)
        self.assertIn(f'href="{reverse("home")}" aria-current="page"', side)

    def test_ai_destinations_follow_server_gates(self):
        self.client.force_login(self.user)
        off = self.get()
        self.assertNotIn(reverse("ai_core:chat"), off)
        self.assertNotIn(reverse("ai_core:image-studio"), off)
        self.assertGreaterEqual(off.count('aria-disabled="true"'), 3)
        on = self.get(**DEV_AI)
        self.assertIn(f'href="{reverse("ai_core:chat")}?lang=en"', section(on, '<nav id="vq-sidebar"', "</nav>"))
        self.assertNotIn(reverse("ai_core:image-studio"), on)  # dev settings do not enable images
        with patch("apps.ai_core.image_generation.page.production_studio_preview_allowed", return_value=True):
            studio = self.get()
        self.assertIn(f'href="{reverse("ai_core:image-studio")}?lang=en"', studio)

    def test_anonymous_never_reaches_image_gates(self):
        with patch("apps.ai_core.image_generation.page.production_studio_preview_allowed") as preview, \
                patch("apps.ai_core.image_generation.page.image_studio_allowed") as staging:
            html = self.get(**DEV_AI)
        preview.assert_not_called()
        staging.assert_not_called()
        self.assertNotIn(reverse("ai_core:image-studio"), html)

    # --- composer ----------------------------------------------------------------------
    def test_composer_is_search_not_fake_ai(self):
        self.client.force_login(self.user)
        for overrides in ({}, DEV_AI):
            html = self.get(**overrides)
            form = section(html, '<form class="vq-ix-composer"', "</form>")
            self.assertIn(f'method="get" action="{reverse("search_page")}" role="search"', form)
            self.assertNotIn('method="post"', form)
            self.assertNotIn("csrfmiddlewaretoken", form)
            for forbidden in ("ask-global", "/api/ai/v1/ask", "data-vq-ai-secret", "type=\"file\"", "model"):
                self.assertNotIn(forbidden, form)
            self.assertIn('maxlength="200"', form)
            self.assertIn('aria-label="Search"', form)

    # --- application grid -----------------------------------------------------------
    def test_every_app_card_is_a_real_link_or_disabled(self):
        self.client.force_login(self.user)
        html = self.get()
        grid = section(html, '<ul class="vq-ix-apps__grid">', "</ul>")
        cards = re.findall(r'<(a|div) class="vq-ix-app[^"]*"([^>]*)>', grid)
        self.assertGreaterEqual(len(cards), 9)
        for tag, attrs in cards:
            if tag == "a":
                resolve(re.search(r'href="([^"?]+)', attrs).group(1))
            else:
                self.assertIn('aria-disabled="true"', attrs)
                self.assertNotIn("href", attrs)
        self.assertEqual(grid.count('class="vq-ix-status'), len(cards))

    # --- recent work (privacy) ----------------------------------------------------
    def test_recent_work_uses_owner_scoped_services(self):
        self.client.force_login(self.user)
        doc = SimpleNamespace(pk=7, title="SYNTHETIC own document", updated_at=timezone.now())
        note = SimpleNamespace(pk=9, title="SYNTHETIC own note", updated_at=timezone.now())
        with patch("apps.documents.services.DocumentService.personal_home_recent_documents",
                   return_value=[doc]) as docs, \
                patch("apps.notes.services.NoteService.list_notes", return_value=[note]) as notes:
            html = self.get()
        self.assertEqual(docs.call_args.kwargs["user"], self.user)
        self.assertEqual(notes.call_args.args[0], self.user)
        self.assertIn("SYNTHETIC own document", html)
        self.assertIn(f'href="{reverse("documents:detail", args=[7])}"', html)
        self.assertIn(f'href="{reverse("notes:detail", args=[9])}"', html)

    def test_user_without_identity_gets_empty_state(self):
        self.client.force_login(self.user)
        with patch("apps.documents.services.DocumentService.personal_home_recent_documents",
                   side_effect=PermissionDenied("no identity")):
            html = self.get()
        self.assertIn("Nothing here yet", html)
        self.assertEqual(views._recent_work_for(SimpleNamespace(is_authenticated=False)), ([], []))

    # --- mobile -----------------------------------------------------------------------
    def test_bottom_nav_five_targets_with_more_button(self):
        html = self.get()
        nav = section(html, '<nav class="vq-bottomnav"', "</nav>")
        hrefs = re.findall(r'<a [^>]*href="([^"]+)"', nav)
        self.assertEqual(len(hrefs), 3)
        for href in hrefs:
            resolve(href.split("?")[0])
        self.assertRegex(nav, r'<button[^>]*data-vq-cmd-open[^>]*aria-controls="vq-cmd"')
        self.assertIn('id="vq-cmd"', html)
        self.assertIn('id="vq-create"', html)


    # --- i18n ----------------------------------------------------------------------------
    def test_three_languages_direction_and_titles(self):
        expected = {"fa": ("rtl", "امروز چه چیزی می‌خواهید بسازید؟", "برنامه‌ها"),
                    "de": ("ltr", "Was möchten Sie heute erstellen?", "Anwendungen"),
                    "en": ("ltr", "What will you create today?", "Applications")}
        for lang, (direction, title, apps) in expected.items():
            html = self.get(lang)
            self.assertIn(f'lang="{lang}"', html)
            self.assertIn(f'dir="{direction}"', html)
            self.assertIn(title, html)
            self.assertIn(apps, html)

    def test_farsi_does_not_leak_new_english_strings(self):
        self.client.force_login(self.user)
        html = self.get("fa", **DEV_AI)
        for english in ("What will you create today?", "Applications", "Controlled testing", "Recent work",
                        "New chat", "Toggle sidebar", "Dark theme", "Account menu", "Main navigation",
                        "Not available yet", "Welcome back", "Account settings", ">Settings<", ">More<"):
            self.assertNotIn(english, html, english)
        self.assertIn("‌", html)  # zero-width non-joiner present in Persian copy

    # --- accessibility and CSP -----------------------------------------------------
    def test_accessibility_semantics(self):
        self.client.force_login(self.user)
        html = self.get(**DEV_AI)
        self.assertEqual(html.count("<h1"), 1)
        ids = re.findall(r'\sid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)), "duplicate id")
        self.assertIn('href="#vq-main" class="vq-skip"', html)
        page = parse(html)
        for tag, attrs in page.tags:
            if tag == "svg":
                self.assertEqual(attrs.get("aria-hidden"), "true")
            if tag == "button":
                self.assertTrue(attrs.get("type"), attrs)
        header = section(html, '<header class="vq-header"', "</header>")
        controls = re.findall(r"<(button|summary)([^>]*)>(.*?)</\1>", header, re.S)
        self.assertGreaterEqual(len(controls), 4)
        for _, attrs, inner in controls:
            text = re.sub(r"<[^>]+>", "", inner).strip()
            if not text or len(text) <= 2:  # icon-only or a bare code such as "EN"
                self.assertIn("aria-label=", attrs, inner[:80])
        symbols = set(re.findall(r'<symbol id="([^"]+)"', html))
        for ref in re.findall(r'<use href="#([^"]+)"', html):
            self.assertIn(ref, symbols)

    def test_page_is_csp_clean(self):
        self.client.force_login(self.user)
        html = self.get(**DEV_AI)
        self.assertNotRegex(html, r"<script(?![^>]*\ssrc=)[^>]*>")
        self.assertNotRegex(html, r"\sstyle=\"")
        self.assertNotRegex(html, r"\son[a-z]+=\"")

    # --- design system and assets -------------------------------------------------
    def test_assets_exist_and_load_in_order(self):
        for path in ("css/tokens.css", "css/theme-palettes.css", "css/shell.css", "css/index-workspace-v8.css",
                     "js/theme-bootstrap.js", "js/shell.js", "js/homepage-ai-workspace-v1.js"):
            self.assertIsNotNone(finders.find(path), path)
        html = self.get()
        self.assertLess(html.index("css/theme-palettes"), html.index("css/shell"))
        self.assertLess(html.index("css/shell"), html.index("css/index-workspace-v8"))
        self.assertLess(html.index("js/theme-bootstrap"), html.index("css/shell"))
        self.assertIn('<body class="vq-shell-body vq-index-v8">', html)
        self.assertNotIn("css/v6-workspace", html)


    def test_design_system_is_real_and_meets_aa(self):
        dark = block(DS, "body.vq-ds {")
        light = block(DS, ':root[data-theme="light"] body.vq-ds,')
        for name in ("--ds-bg", "--ds-surface", "--ds-text", "--ds-primary", "--ds-radius-md", "--ds-shadow-md",
                     "--ds-icon-24", "--ds-fast", "--ds-ring-width", "--ds-appbar-h", "--ds-2"):
            self.assertIn(name + ":", dark)
        self.assertNotIn("var(--vq-", DS)  # not an alias layer over V6-01
        for palette in (dark, light):
            surfaces = [var(palette, n) for n in ("--ds-bg", "--ds-side", "--ds-surface", "--ds-elevated")]
            for surface in surfaces:
                for text in ("--ds-text", "--ds-text-2", "--ds-primary-text"):
                    self.assertGreaterEqual(contrast(var(palette, text), surface), 4.5, (text, surface))
                self.assertGreaterEqual(contrast(var(palette, "--ds-focus"), surface), 3, surface)
            self.assertGreaterEqual(contrast(var(dark, "--ds-on-primary"), var(palette, "--ds-primary-btn")), 4.5)
            mix = 0.16 if palette is dark else 0.12
            for tone in ("violet", "pink", "blue", "teal", "cyan", "amber", "indigo", "slate"):
                colour = var(palette, f"--tone-{tone}")
                tile = tint(colour, var(palette, "--ds-surface"), mix)
                self.assertGreaterEqual(contrast(colour, tile), 3, tone)  # non-text icon contrast

    def test_css_is_logical_motion_safe_and_local(self):
        for css in (DS, WS):
            for forbidden in (r"margin-(left|right)\s*:", r"padding-(left|right)\s*:", r"(?<![-\w])(left|right)\s*:",
                              r"text-align:\s*(left|right)", r"border-(left|right)", r"@import", r"@font-face",
                              r"url\(\s*['\"]?https?:", r"100vw", r"!important"):
                self.assertIsNone(re.search(forbidden, css), forbidden)
        self.assertIn("prefers-reduced-motion", WS)
        self.assertIn("forced-colors: active", WS)
        self.assertIn('html[dir="rtl"] .vq-side { transform: translateX(100%); }', WS)
        self.assertIn("env(safe-area-inset-bottom", WS)
        self.assertIn(":has(.vq-composer__input:focus) .vq-bottom-nav { display: none; }", WS)

    def test_javascript_is_ui_only(self):
        for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "innerHTML", "eval(", "WebSocket", "document.cookie"):
            self.assertNotIn(forbidden, JS)
        self.assertEqual(set(re.findall(r'store\("([^"]+)"', JS)), {"vorneq-theme", "vq-side"})
        bootstrap = (Path(settings.BASE_DIR) / "assets" / "js" / "v6-shell-bootstrap.js").read_text(encoding="utf-8")
        self.assertIn('localStorage.getItem("vq-side")', bootstrap)
        self.assertNotIn("fetch(", bootstrap)

    def test_other_pages_keep_site_header(self):
        with translation.override("en"):
            response = self.client.get(reverse("discover"))
        self.assertContains(response, 'class="standalone-nav')
        self.assertNotContains(response, "vq-appbar")
        self.assertNotContains(response, "v6-workspace.css")
