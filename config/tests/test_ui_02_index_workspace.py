"""UI-02: live index contract, not the retired V6 layout."""
import re
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse, resolve
from django.utils import translation

from config.tests.test_homepage_v3 import DEV_AI, NoProviderMixin


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def select(self, tag):
        return [attrs for name, attrs in self.tags if name == tag]


class IndexWorkspaceTests(NoProviderMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="ui02-synthetic", password="synthetic-only"
        )

    def home(self, lang="en", **overrides):
        with translation.override(lang), override_settings(**overrides):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "shell/app_base.html")
        return response.content.decode()

    def test_single_shell_and_unique_accessible_targets(self):
        html = self.home()
        doc = Markup(html)
        for tag in ("header", "main", "h1"):
            self.assertEqual(len(doc.select(tag)), 1, tag)
        ids = [attrs["id"] for _, attrs in doc.tags if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for _, attrs in doc.tags:
            for key in ("aria-labelledby", "aria-describedby", "aria-controls"):
                for target in attrs.get(key, "").split():
                    self.assertIn(target, ids)
        for attrs in doc.select("use"):
            self.assertIn(attrs["href"].removeprefix("#"), ids)
        self.assertIn('href="#vq-main"', html)
        self.assertIn('data-vq-index-v8', html)

    def test_guest_privacy_and_no_queries(self):
        with CaptureQueriesContext(connection) as queries:
            html = self.home(**DEV_AI)
        self.assertEqual(len(queries), 0)
        for name in ("documents:list", "notes:list", "profile", "profile_edit",
                     "account_logout", "platform_shell:personal_home",
                     "ai_core:chat", "ai_core:image-studio"):
            self.assertNotIn(reverse(name), html)
        self.assertNotIn("vq-ix-recent", html)

    def test_account_and_gate_contract(self):
        self.client.force_login(self.user)
        off = self.home()
        for name in ("profile", "profile_edit", "account_logout",
                     "documents:list", "notes:list"):
            self.assertIn(f'href="{reverse(name)}"', off)
        for name in ("ai_core:chat", "ai_core:image-studio"):
            self.assertNotIn(reverse(name), off)
        on = self.home(**DEV_AI)
        self.assertIn(reverse("ai_core:chat"), on)
        self.assertNotIn(reverse("ai_core:image-studio"), on)
        with patch("apps.ai_core.image_generation.page.production_studio_preview_allowed", return_value=True):
            self.assertIn(reverse("ai_core:image-studio"), self.home())

    def test_search_native_get_and_local_assets(self):
        html = self.home()
        doc = Markup(html)
        forms = [a for a in doc.select("form") if a.get("role") == "search"]
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]["method"], "get")
        self.assertEqual(forms[0]["action"], reverse("search_page"))
        fields = [a for a in doc.select("textarea") if a.get("name") == "q"]
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["maxlength"], "200")
        self.assertIn("required", fields[0])
        for attrs in doc.select("script"):
            self.assertIn("src", attrs)
            self.assertFalse(urlsplit(attrs["src"]).netloc)
        for _, attrs in doc.tags:
            self.assertNotIn("style", attrs)
            self.assertFalse(any(k.startswith("on") for k in attrs))
        self.assertIn("css/index-workspace-v8", html)
        self.assertNotIn("css/v6-workspace", html)
        self.assertNotIn("/api/ai/", html)

    def test_all_index_strings_translated(self):
        root = Path(settings.BASE_DIR)
        files = [root / "templates/index.html", *(root / "templates/home/v8").glob("*.html")]
        strings = {m.group(2) for p in files for m in re.finditer(
            r"""{%\s*trans\s+(['"])(.*?)\1\s*%}""", p.read_text(encoding="utf-8")
        )}
        for lang, direction in (("fa", "rtl"), ("de", "ltr"), ("en", "ltr")):
            html = self.home(lang)
            self.assertIn(f'lang="{lang}"', html)
            self.assertIn(f'dir="{direction}"', html)
            if lang != "en":
                with translation.override(lang):
                    for msg in strings:
                        self.assertNotEqual(translation.gettext(msg), msg, (lang, msg))

    def test_v8_css_contract(self):
        css = (Path(settings.BASE_DIR) / "assets/css/index-workspace-v8.css").read_text(encoding="utf-8")
        for value in ("prefers-reduced-motion", "var(--vq-target)", "minmax(0, 1fr)", "overflow-wrap: anywhere"):
            self.assertIn(value, css)
        self.assertNotRegex(css, r"@import|@font-face|100vw|url\(\s*['\"]?https?:")
