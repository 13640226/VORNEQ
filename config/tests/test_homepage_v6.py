"""Product UI V6-01 (Interactive Index): tokens, sprite, sidebar, bottom nav, i18n, a11y.

V6-02 replaced the V6-01 layout (rail, hero, V5 sections). Assertions that targeted
removed markup were moved to the V6-02 equivalents (marked "V6-02"); the V6-01
guarantees (aliases, sprite, gating, five real bottom links, i18n, a11y) still hold.

Rendering only. The provider and the OpenAI client are patched to fail (via the V3
mixin) so a regression that triggers an AI call from the homepage fails loudly.
"""
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, resolve, reverse
from django.utils import translation

from config.tests.test_homepage_v3 import DEV_AI, NoProviderMixin, home_fragment, parse

ASSETS = Path(settings.BASE_DIR) / "assets" / "css"
HOME_CSS = (ASSETS / "v6-workspace.css").read_text(encoding="utf-8")  # V6-02 layout
V6_TOKENS = (ASSETS / "v6-tokens.css").read_text(encoding="utf-8")
BASE_TOKENS = (ASSETS / "tokens.css").read_text(encoding="utf-8") + (ASSETS / "theme-palettes.css").read_text(
    encoding="utf-8")
SPRITE_ICONS = ("chat", "image", "mic", "folder", "notebook", "books", "search", "store", "grid",
                "sliders", "user", "paperclip", "send", "clock", "menu", "close", "sun", "moon")


def bottom_nav(html):
    start = html.index('<nav class="vq-bottom-nav"')
    return html[start:html.index("</nav>", start)]


class HomepageV6Tests(NoProviderMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="home-v6", password="synthetic-only")

    def get(self, lang="en", **overrides):
        with translation.override(lang), override_settings(**overrides):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    # --- rendering -------------------------------------------------------
    def test_guest_renders_200_with_v6_shell(self):
        html = self.get()
        for marker in ('data-vq-v6', 'class="vq-sprite"', 'data-vq-side', 'data-vq-bottom-nav'):  # V6-02 sidebar
            self.assertIn(marker, html)

    def test_authenticated_renders_200_with_private_bottom_nav_entry(self):
        self.client.force_login(self.user)
        nav = bottom_nav(self.get())
        self.assertIn(f'href="{reverse("platform_shell:personal_home")}"', nav)
        self.assertNotIn(f'href="{reverse("account_login")}"', nav)

    # --- tokens and CSS contract ----------------------------------------
    def test_v6_tokens_are_aliases_of_existing_tokens(self):
        declarations = re.findall(r"(--vq-[\w-]+):\s*([^;]+);", V6_TOKENS)
        self.assertGreaterEqual(len(declarations), 20)
        for name, value in declarations:
            self.assertNotRegex(value, r"#[0-9a-fA-F]{3,8}|rgba?\(", f"{name} must alias, not define a colour")
            for ref in re.findall(r"var\((--[\w-]+)\)", value):
                self.assertIn(f"{ref}:", BASE_TOKENS, f"{name} -> {ref} does not exist")
        self.assertNotIn("@font-face", V6_TOKENS)
        self.assertNotIn("@import", V6_TOKENS)

    def test_tokens_load_globally_after_palettes(self):
        base = (Path(settings.BASE_DIR) / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertLess(base.index("css/theme-palettes.css"), base.index("css/v6-tokens.css"))
        self.assertLess(base.index("css/v6-tokens.css"), base.index("css/page-shell.css"))

    def test_header_height_is_compact_and_aliased(self):
        height = re.search(r"--header-height:\s*(\d+)px", BASE_TOKENS)
        self.assertIsNotNone(height)
        self.assertLessEqual(int(height.group(1)), 64)
        self.assertIn("--vq-header-h: var(--header-height);", V6_TOKENS)
        # V6-02: the homepage header is the 56px application bar.
        self.assertIn("height: var(--ds-appbar-h)", HOME_CSS)

    def test_no_horizontal_overflow_contract(self):
        v6 = HOME_CSS[HOME_CSS.index("Product UI V6-02"):]
        self.assertIn("grid-template-columns: repeat(5, minmax(0, 1fr))", v6)
        self.assertIn("overflow-wrap: anywhere", v6)
        self.assertIn("inset-inline: 0", v6)
        rules = re.sub(r"@media[^{]*", "", v6)  # breakpoints are not element widths
        self.assertNotRegex(rules, r"(?<![-\w])(width|min-width):\s*(1\d{3}|[4-9]\d{2})px")
        self.assertNotRegex(v6, r"100vw")

    def test_breakpoints_tap_targets_and_focus_tokens(self):
        v6 = HOME_CSS[HOME_CSS.index("Product UI V6-02"):]
        ds = (ASSETS / "v6-design-system.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 767px)", v6)
        self.assertIn("@media (max-width: 1023px)", v6)  # V6-02: drawer for tablet and mobile
        self.assertGreaterEqual(v6.count("min-height: var(--ds-tap)"), 2)
        self.assertGreaterEqual(v6.count("min-width: var(--ds-tap)"), 2)
        self.assertIn("outline: var(--ds-ring-width) solid var(--ds-focus)", ds)
        self.assertNotIn("!important", v6)

    # --- composer --------------------------------------------------------
    def test_composer_stays_search_form_for_guest(self):
        html = self.get()
        self.assertRegex(html, r'<form[^>]+method="get"[^>]+action="' + re.escape(reverse("search_page")) + '"')
        self.assertNotIn(reverse("ai_core:chat"), html)
        self.assertNotIn("data-vq-bottom-chat", html)
        self.assertIn(f'href="{reverse("search_page")}"', bottom_nav(html))  # V6-02: Search replaces Chat

    def test_chat_link_only_for_enabled_account(self):
        self.client.force_login(self.user)
        html = self.get(**DEV_AI)
        self.assertIn("data-vq-phase-c-link", html)
        self.assertIn("data-vq-bottom-chat", html)
        self.assertIn(f'href="{reverse("ai_core:chat")}?lang=en"', bottom_nav(html))
        self.assertEqual(html.count('role="search"'), 1)

    # --- navigation ------------------------------------------------------
    def test_bottom_nav_has_at_most_five_real_links(self):
        for login in (False, True):
            if login:
                self.client.force_login(self.user)
            nav = bottom_nav(self.get(**DEV_AI))
            hrefs = re.findall(r'<a [^>]*href="([^"]+)"', nav)
            # V6-02: four links plus the "More" button that opens the sidebar drawer.
            self.assertEqual(nav.count("<li>"), 5)
            self.assertEqual(len(hrefs), 4, hrefs)
            self.assertIn("data-vq-more", nav)
            for href in hrefs:
                if href.startswith("#"):
                    self.assertEqual(href, "#vq-create")
                else:
                    resolve(href.split("?")[0])

    def test_all_index_links_resolve(self):
        self.client.force_login(self.user)
        html = home_fragment(self.get(**DEV_AI))
        ids = set(re.findall(r'id="([^"]+)"', html))
        hrefs = set(re.findall(r'<a [^>]*href="([^"]+)"', html))
        self.assertGreaterEqual(len(hrefs), 10)
        for href in hrefs:
            if href.startswith("#"):
                self.assertIn(href[1:], ids, href)
            else:
                resolve(href.split("?")[0])
        for name in ("chat", "library"):  # spec routes that do not exist at the root
            with self.assertRaises(NoReverseMatch):
                reverse(name)

    # --- i18n ------------------------------------------------------------
    def test_farsi_is_rtl_and_translated(self):
        html = self.get("fa")
        self.assertIn('dir="rtl"', html)
        nav = bottom_nav(html)
        for text in ("پیمایش سریع", "خانه", "ساختن", "بیشتر"):  # V6-02 bottom labels
            self.assertIn(text, nav)
        self.assertIn("پیمایش اصلی", html)

    def test_farsi_does_not_leak_new_english_strings(self):
        fragment = home_fragment(self.get("fa"))
        for english in ("Quick navigation", "Main navigation", ">Home<", ">Create<", ">More<", ">Sign in<"):
            self.assertNotIn(english, fragment)

    def test_german_and_english_strings(self):
        de = bottom_nav(self.get("de"))
        for text in ("Schnellnavigation", "Startseite", "Erstellen", "Mehr"):  # V6-02 labels
            self.assertIn(text, de)
        self.assertIn("Hauptnavigation", self.get("de"))
        en = bottom_nav(self.get("en"))
        for text in ("Quick navigation", "Home", "Create", "More"):
            self.assertIn(text, en)

    # --- accessibility ---------------------------------------------------
    def test_sprite_contains_required_icons_and_is_hidden(self):
        html = self.get()
        sprite = html[html.index('<svg class="vq-sprite"'):html.index("</svg>", html.index('<svg class="vq-sprite"'))]
        self.assertIn('aria-hidden="true"', sprite.split(">", 1)[0])
        for icon in SPRITE_ICONS:
            self.assertIn(f'<symbol id="vq-i-{icon}" viewBox="0 0 24 24">', sprite)
        self.assertGreaterEqual(sprite.count("<symbol"), 15)
        self.assertLessEqual(sprite.count("<symbol"), 40)  # V6-02 added 11 icons

    def test_every_svg_is_hidden_or_labelled_and_uses_exist(self):
        self.client.force_login(self.user)
        html = self.get(**DEV_AI)
        page = parse(html)
        for tag, attrs in page.tags:
            if tag == "svg":
                self.assertTrue(attrs.get("aria-hidden") == "true" or attrs.get("aria-label"), attrs)
        symbols = set(re.findall(r'<symbol id="([^"]+)"', html))
        for ref in re.findall(r'<use href="#([^"]+)"', html):
            self.assertIn(ref, symbols)

    def test_skip_link_unique_ids_and_labelled_landmarks(self):
        html = self.get()
        self.assertIn('href="#main-content" class="skip-link"', html)
        self.assertIn('id="main-content"', html)
        ids = re.findall(r'\sid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)), "duplicate id")
        nav = bottom_nav(html)
        self.assertRegex(nav, r'^<nav class="vq-bottom-nav" aria-label="[^"]+"')
        self.assertEqual(nav.count('aria-current="page"'), 1)

    def test_sidebar_toggle_is_a_button_hidden_without_js(self):
        """V6-02: header button toggles the sidebar (collapse >=1024px, drawer below)."""
        html = self.get()
        toggle = re.search(r"<button[^>]*data-vq-side-toggle[^>]*>", html).group(0)
        for attr in ('type="button"', 'aria-expanded="true"', 'aria-controls="vq-side"', "aria-label="):
            self.assertIn(attr, toggle)
        self.assertIn('id="vq-side"', html)
        js = (Path(settings.BASE_DIR) / "assets" / "js" / "v6-workspace.js").read_text(encoding="utf-8")
        self.assertIn('event.key === "Escape"', js)
        self.assertIn("opener.focus()", js)
        self.assertNotRegex(js, r"fetch\(|XMLHttpRequest|sendBeacon|innerHTML|eval\(")
