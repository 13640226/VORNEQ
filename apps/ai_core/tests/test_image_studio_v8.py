"""UI-03 shell, accessibility and production read-only contracts."""
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from config.tests.test_ui_02_index_workspace import Markup
from config.tests.test_homepage_v3 import NoProviderMixin
from apps.ai_core.image_generation.page import LABELS


class StudioV8Tests(NoProviderMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="ui03-synthetic")

    def visit(self, language, preview=False):
        self.client.force_login(self.user)
        with override_settings(VORNEQ_ENV="staging", DEBUG=False,
                               VORNEQ_AI_IMAGE_UI_ENABLED=True), patch(
            "apps.ai_core.image_generation.page.production_studio_preview_allowed",
            return_value=preview
        ), patch("apps.ai_core.image_generation.page.image_studio_allowed",
                 return_value=not preview), patch(
            "config.views._ai_chat_available_for", return_value=False
        ):
            response = self.client.get(reverse("ai_core:image-studio") + "?lang=" + language)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "shell/app_base.html")
        self.assertIn("no-store", response["Cache-Control"])
        return response.content.decode()

    def test_shell_navigation_and_unique_ids(self):
        doc = Markup(self.visit("en"))
        self.assertEqual(len(doc.select("main")), 1)
        self.assertEqual(len(doc.select("h1")), 1)
        self.assertEqual(sum(a.get("class") == "vq-header" for a in doc.select("header")), 1)
        ids = [a["id"] for _, a in doc.tags if "id" in a]
        self.assertEqual(len(ids), len(set(ids)))
        for _, a in doc.tags:
            for key in ("aria-labelledby", "aria-describedby", "aria-controls"):
                for target in a.get(key, "").split():
                    self.assertIn(target, ids)
        active = [a for a in doc.select("a") if a.get("aria-current") == "page"]
        self.assertEqual(len(active), 2)
        self.assertTrue(all(reverse("ai_core:image-studio") in a["href"] for a in active))
        self.assertNotIn(reverse("ai_core:chat"), self.visit("en"))

    def test_composer_hooks_and_localization(self):
        for lang in ("en", "de", "fa"):
            with self.subTest(lang=lang):
                html = self.visit(lang)
                doc = Markup(html)
                self.assertEqual(doc.select("html")[0]["dir"], "rtl" if lang == "fa" else "ltr")
                self.assertIn(LABELS[lang]["composer"], html)
                self.assertEqual({a["data-vq-ratio"] for a in doc.select("button") if "data-vq-ratio" in a},
                                 {"1024x1024", "1536x1024", "1024x1536"})
                self.assertIn("data-vq-image-count", html)
                self.assertIn("data-vq-gallery", html)
                self.assertIn("data-vq-viewer", html)
                self.assertNotIn("onclick=", html)

    def test_preview_is_localized_and_inert(self):
        for lang in ("en", "de", "fa"):
            with self.subTest(lang=lang):
                html = self.visit(lang, preview=True)
                self.assertIn(LABELS[lang]["readonly_mode"], html)
                self.assertNotIn("data-vq-image-studio", html)
                self.assertNotIn("images/jobs/", html)
                self.assertNotIn("image-studio-v8.js", html)
                doc = Markup(html)
                self.assertTrue(any("disabled" in a for a in doc.select("button")
                                    if a.get("class") == "vq-image__submit"))
                self.assertIn("readonly", doc.select("textarea")[0])

    def test_preview_size_choices_are_selectable(self):
        for lang in ('en', 'de', 'fa'):
            with self.subTest(lang=lang):
                doc = Markup(self.visit(lang, preview=True))
                size = next(a for a in doc.select('select') if a.get('id') == 'vq-image-size')
                self.assertNotIn('disabled', size)
                self.assertEqual({a.get('value') for a in doc.select('option') if a.get('value') in {'1024x1024', '1536x1024', '1024x1536'}}, {'1024x1024', '1536x1024', '1024x1536'})
