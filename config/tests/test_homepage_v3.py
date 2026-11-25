"""Homepage V3 (AI-first application shell): rendering, gates, i18n, a11y, CSS contract.

No network, no provider: the OpenAI client and the provider are patched to fail
if they are ever constructed or invoked while rendering the homepage.
"""
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from apps.ai_core.tests.test_ai_staging_trial import STAGING_SETTINGS, TEST_ENV

PRIVATE_URLS = ("documents:list", "notes:list", "platform_shell:personal_home",
                "documents:create", "notes:create")
DEV_AI = dict(VORNEQ_ENV="development", VORNEQ_AI_PHASE_B_ENABLED=True, VORNEQ_AI_PHASE_C_ENABLED=True)
# V6-02: homepage-ai-cloud-v2.css was replaced by the design system + workspace layout.
CSS = Path(settings.BASE_DIR) / "assets" / "css" / "v6-workspace.css"
DS_CSS = Path(settings.BASE_DIR) / "assets" / "css" / "v6-design-system.css"


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.ids, self.stack, self.links, self.headings = [], [], [], [], []
        self._link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a":
            self._link = [attrs, ""]
        if tag in ("h1", "h2", "h3"):
            self.headings.append(tag)

    def handle_data(self, data):
        if self._link is not None:
            self._link[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            self.links.append((self._link[0], self._link[1].strip()))
            self._link = None


def home_fragment(html):
    start = html.index('<div class="vq-home"')
    end = html.index("</main>")
    return html[start:end]


def parse(html):
    collector = _Collector()
    collector.feed(home_fragment(html))
    return collector


class NoProviderMixin:
    def setUp(self):
        super().setUp()
        translation.activate("en")
        self.addCleanup(translation.deactivate)
        self.provider = patch("apps.ai_core.providers.openai_responses.OpenAIResponsesProvider.generate",
                              side_effect=AssertionError("provider invoked from homepage"))
        self.provider.start()
        self.addCleanup(self.provider.stop)
        try:
            sdk = patch("openai.OpenAI", side_effect=AssertionError("OpenAI client constructed"))
            sdk.start()
            self.addCleanup(sdk.stop)
        except ModuleNotFoundError:
            pass
        env = {k: v for k, v in os.environ.items() if not k.startswith("RENDER")}
        p = patch.dict(os.environ, env, clear=True)
        p.start()
        self.addCleanup(p.stop)


class HomepageShellTests(NoProviderMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="home-v3", password="synthetic-only")

    def get(self, lang="en"):
        with translation.override(lang):
            return self.client.get(reverse("home")).content.decode()

    def test_anonymous_shell_components_and_public_navigation_only(self):
        html = self.get()
        # V6-02 shell: app header, sidebar, stage (composer, quick actions, apps, trust).
        for marker in ('class="vq-appbar"', 'class="vq-side"', 'class="vq-stage"', 'class="vq-apps"', 'class="vq-trust"'):
            self.assertIn(marker, html)
        for name in ("search_page", "discover", "marketplace:index", "orientation", "inspect_entry",
                     "discover_knowledge", "account_login", "account_signup"):
            self.assertIn(f'href="{reverse(name)}"', html)
        for name in PRIVATE_URLS:
            self.assertNotIn(f'href="{reverse(name)}"', html)
        self.assertNotIn(reverse("ai_core:chat"), html)
        self.assertIn("Sign in required", html)
        self.assertIn("Controlled testing", html)  # V6-02 status label for gated AI cards
        self.assertIn("AI answers are not enabled yet.", html)

    def test_authenticated_private_navigation_and_actions(self):
        self.client.force_login(self.user)
        html = self.get()
        fragment = home_fragment(html)
        for name in PRIVATE_URLS:
            self.assertIn(f'href="{reverse(name)}"', fragment)
        self.assertIn("Welcome back", html)  # V6-02 greeting replaces the status panel
        self.assertIn("Quick actions", html)
        self.assertNotIn("Sign in required", html)
        self.assertIn('class="vq-status vq-status--private"', html)

    def test_search_form_destination_and_submission(self):
        html = self.get()
        self.assertEqual(html.count('role="search"'), 1)
        self.assertRegex(html, r'<form[^>]+method="get"[^>]+action="' + re.escape(reverse("search_page")) + '"')
        self.assertIn('name="q"', html)
        response = self.client.get(reverse("search_page"), {"q": "SYNTHETIC homepage query"})
        self.assertEqual(response.status_code, 200)

    def test_composer_input_attributes_match_server_contract(self):
        html = self.get()
        match = re.search(r'<textarea[^>]*id="vq-ai-question"[^>]*>', html, re.S)
        self.assertIsNotNone(match)
        tag = match.group(0)
        self.assertRegex(tag, r"\srequired[\s>]")
        self.assertIn('enterkeyhint="search"', tag)
        self.assertIn('aria-describedby="vq-ai-search-limitation"', tag)
        # Server truncates queries at 200 characters (apps/search/views.py);
        # the client limit must not promise more.
        self.assertIn('maxlength="200"', tag)

    def test_languages_and_rtl(self):
        expected = {
            # V6-02: new product title; the app grid replaces the status panel.
            "en": ("What will you create today?", "Applications", "Evidence vocabulary"),
            "de": ("Was möchten Sie heute erstellen?", "Anwendungen", "Öffentliches Wissen"),
            "fa": ("امروز چه چیزی می‌خواهید بسازید؟", "برنامه‌ها", "دانش عمومی"),
        }
        for lang, strings in expected.items():
            response = self.client.get(f"/{lang}/")
            self.assertEqual(response.status_code, 200)
            for text in strings:
                self.assertContains(response, text)
            self.assertContains(response, f'lang="{lang}"')
            if lang == "fa":
                self.assertContains(response, 'dir="rtl"')
            else:
                self.assertNotContains(response, 'dir="rtl"')

    def test_rail_destinations_remain_reachable_when_rail_is_hidden(self):
        """<1024px hides the sidebar (drawer); every sidebar link must exist elsewhere.

        V6-02: the V3 rail became the application sidebar (<aside class="vq-side">).
        """
        self.client.force_login(self.user)
        with override_settings(**DEV_AI):
            html = self.get()
        start = html.index('<aside class="vq-side"')
        rail = html[start:html.index("</aside>", start)]
        rest = html.replace(rail, "")
        # V6-01: <use href="#vq-i-…"> are icon-sprite references, not destinations.
        hrefs = re.findall(r'<a [^>]*href="([^"]+)"', rail)
        self.assertGreaterEqual(len(hrefs), 8)
        for href in hrefs:
            self.assertIn(f'href="{href}"', rest, href)

    def test_accessibility_semantics(self):
        self.client.force_login(self.user)
        page = parse(self.get())
        self.assertEqual(page.headings.count("h1"), 1)
        self.assertEqual(len(page.ids), len(set(page.ids)), "duplicate id")
        labelled = {attrs.get("aria-labelledby") for tag, attrs in page.tags if tag in ("nav", "aside", "section")}
        labelled.discard(None)
        for target in labelled:
            self.assertIn(target, page.ids, f"aria-labelledby target {target} missing")
        for tag, attrs in page.tags:
            if "tabindex" in attrs:
                self.assertLessEqual(int(attrs["tabindex"]), 0)
            self.assertNotIn("style", attrs, "inline style violates CSP")
        svgs = [attrs for tag, attrs in page.tags if tag == "svg"]
        self.assertTrue(svgs)
        for attrs in svgs:
            self.assertEqual((attrs.get("aria-hidden"), attrs.get("focusable")), ("true", "false"))
        for attrs, text in page.links:
            self.assertTrue(text, f"link without accessible text: {attrs.get('href')}")
        self.assertNotIn("<script", home_fragment(self.get()))


class AIChatGateTests(NoProviderMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="home-gate", password="synthetic-only")

    def html(self, **settings_over):
        with override_settings(**settings_over):
            return self.client.get(reverse("home")).content.decode()

    def assert_no_chat(self, html):
        self.assertNotIn("data-vq-phase-c-link", html)
        self.assertNotIn(reverse("ai_core:chat"), html)
        self.assertIn("AI answers · coming soon", html)
        self.assertIn('aria-disabled="true"', html)

    def test_default_disabled(self):
        self.client.force_login(self.user)
        self.assert_no_chat(self.html())

    def test_anonymous_never_triggers_ai_policy_checks(self):
        with patch("apps.ai_core.chat_page.is_chat_enabled") as gate:
            self.assert_no_chat(self.html(**DEV_AI))
        gate.assert_not_called()

    def test_development_flags_and_login_show_chat(self):
        self.client.force_login(self.user)
        html = self.html(**DEV_AI)
        self.assertIn("data-vq-phase-c-link", html)
        self.assertIn(reverse("ai_core:chat"), html)
        self.assertIn("Available for your account", html)
        self.assertNotIn("AI answers · coming soon", html)

    def test_development_on_hosted_runtime_hides_chat(self):
        self.client.force_login(self.user)
        with patch.dict(os.environ, {"RENDER": "true"}):
            self.assert_no_chat(self.html(**DEV_AI))

    def test_staging_requires_trial_and_allowlist(self):
        admin = get_user_model().objects.create_superuser(username="home-admin", password="synthetic-only")
        self.client.force_login(admin)
        with patch.dict(os.environ, TEST_ENV):
            self.assert_no_chat(self.html(**{**STAGING_SETTINGS, "VORNEQ_AI_STAGING_TRIAL_ENABLED": False}))
            self.assert_no_chat(self.html(**STAGING_SETTINGS))  # admin not on allowlist ("101")
            html = self.html(**{**STAGING_SETTINGS, "VORNEQ_AI_STAGING_ALLOWED_USER_IDS": str(admin.pk)})
            self.assertIn("data-vq-phase-c-link", html)

    def test_production_follows_production_policy(self):
        self.client.force_login(self.user)
        self.assert_no_chat(self.html(VORNEQ_ENV="production"))
        with patch("apps.ai_core.views_global.production_enabled", return_value=True):
            self.assert_no_chat(self.html(VORNEQ_ENV="production"))  # actor not allowlisted
            html = self.html(VORNEQ_ENV="production", VORNEQ_AI_PRODUCTION_ACTOR_POLICY="allowlist",
                             VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS=str(self.user.pk))
            self.assertIn("data-vq-phase-c-link", html)

    def test_emergency_stop_hides_chat(self):
        self.client.force_login(self.user)
        admin = get_user_model().objects.create_superuser(username="home-stop", password="synthetic-only")
        self.client.force_login(admin)
        with patch.dict(os.environ, TEST_ENV):
            self.assert_no_chat(self.html(**{**STAGING_SETTINGS, "VORNEQ_AI_EMERGENCY_STOP": True,
                                              "VORNEQ_AI_STAGING_ALLOWED_USER_IDS": str(admin.pk)}))


class ResponsiveCssContractTests(TestCase):
    css = CSS.read_text(encoding="utf-8")

    def test_wide_shell_and_breakpoints(self):
        # V6-02 layout: sidebar + stage, drawer below 1024px, mobile below 768px.
        for needle in ("max-width: var(--ds-content-max)", "grid-template-columns: var(--ds-side-w) minmax(0, 1fr)",
                       "@media (min-width: 1440px)", "@media (max-width: 1023px)",
                       "@media (max-width: 767px)", "grid-template-columns: minmax(0, 1fr);",
                       "minmax(0, 1fr)", "position: sticky"):
            self.assertIn(needle, self.css)

    def test_rtl_safe_logical_properties_only(self):
        for forbidden in (r"margin-(left|right)\s*:", r"padding-(left|right)\s*:", r"(?<![-\w])(left|right)\s*:",
                          r"text-align:\s*(left|right)", r"border-(left|right)"):
            self.assertIsNone(re.search(forbidden, self.css), forbidden)
        self.assertIn('html[dir="rtl"]', self.css)

    def test_touch_targets_focus_motion_and_contrast_modes(self):
        # V6-02: 44px is the design-system token --ds-tap.
        ds = DS_CSS.read_text(encoding="utf-8")
        self.assertIn("--ds-tap: 44px;", ds)
        self.assertGreaterEqual(self.css.count("min-height: var(--ds-tap)"), 8)
        self.assertIn(":focus-visible", self.css + ds)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("forced-colors: active", self.css)
        self.assertIn(':root[data-theme="vorneq"] body.vq-ds', ds)  # light palette variant
        self.assertNotIn("!important", self.css.split("prefers-reduced-motion")[0])

    def test_led_colours_meet_contrast(self):
        def lum(hex_):
            r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
            f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

        def ratio(a, b):
            hi, lo = sorted((lum(a), lum(b)), reverse=True)
            return (hi + 0.05) / (lo + 0.05)
        palettes = (Path(settings.BASE_DIR) / "assets" / "css" / "theme-palettes.css").read_text()
        surfaces = re.findall(r"--color-bg-(?:page|surface|elevated):\s*(#[0-9a-fA-F]{6})", palettes)
        light = {"#f7f8fa", "#ffffff"}
        for bg in surfaces:
            led = "#047857" if bg.lower() in light else "#34d399"
            self.assertGreaterEqual(ratio(led, bg), 4.5, (led, bg))


class MeaningfulTextContrastTests(TestCase):
    def test_status_and_disabled_labels_do_not_use_muted_token(self):
        css = CSS.read_text(encoding="utf-8")
        # V6-02: secondary text is --ds-text-2 (>= 4.5:1); --ds-text-3 is reserved for hints.
        for selector in (".vq-mode--soon", ".vq-status", ".vq-compose__note", ".vq-composer__count"):
            rule = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css).group(1)
            self.assertIn("--ds-text-2", rule, selector)
            self.assertNotIn("--ds-text-3", rule, selector)
