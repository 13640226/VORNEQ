"""Offline regressions for environment-correct multilingual Chat AI copy.

No OpenAI calls, no live Render credentials or external network access.
"""
from html import escape
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import override

from apps.ai_core.chat_strings import LABELS, PRODUCTION_LABELS, chat_labels


class ProductionChatCopyTests(SimpleTestCase):
    def test_production_has_explicit_warning_recovery_and_entry_in_three_languages(self):
        for language, expected in {
            "en": ("Production AI pilot", "Production request recovery", "Open AI chat"),
            "de": ("KI-Pilot in Production", "Production-Anfragen", "KI-Chat öffnen"),
            "fa": ("هوش مصنوعی Production", "بازیابی درخواست در Production",
                   "بازکردن گفت‌وگوی هوش مصنوعی"),
        }.items():
            with self.subTest(language=language):
                labels = chat_labels(language, environment="production")
                # Retain the PR #639 owner-approved safety and recovery copy verbatim.
                for protected_key in ("entry", "warning", "single_turn"):
                    self.assertEqual(labels[protected_key], PRODUCTION_LABELS[language][protected_key])
                self.assertIn(expected[0], labels["warning"])
                self.assertIn(expected[1], labels["single_turn"])
                self.assertEqual(labels["entry"], expected[2])
                self.assertNotIn("Staging", labels["single_turn"])
                self.assertNotIn("Development preview", labels["warning"])
                self.assertIn("۱۵" if language == "fa" else "15", labels["single_turn"])
                self.assertEqual(labels["status"], LABELS[language]["status"])
                self.assertEqual(labels["error"], LABELS[language]["error"])

    def test_existing_catalog_fields_preserved_with_v2_additions(self):
        for language in ("en", "de", "fa"):
            with self.subTest(language=language):
                dev = chat_labels(language, environment="development")
                stage = chat_labels(language, environment="staging")
                for key, value in LABELS[language].items():
                    self.assertEqual(dev[key], value)
                    if key not in ("entry", "warning"):
                        self.assertEqual(stage[key], value)
                self.assertTrue(stage["warning"])
                self.assertIn("staging", stage["warning"].lower().replace("?????? ???? ", "staging "))
        self.assertEqual(chat_labels("unknown", environment="production")["entry"], "Open AI chat")


class ProductionChatRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="production-copy-test", email="production-copy@example.invalid",
            password="synthetic-offline-test",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    @override_settings(VORNEQ_ENV="production", VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED=True)
    def test_authenticated_production_page_uses_correct_copy_without_model_calls(self):
        with patch("apps.ai_core.chat_page.global_ai_available", return_value=True), \
                patch("apps.ai_core.chat_page.production_actor_allowed", return_value=True):
            for language in ("en", "de", "fa"):
                with self.subTest(language=language):
                    response = self.client.get(reverse("ai_core:chat") + "?lang=" + language)
                    self.assertEqual(response.status_code, 200)
                    body = response.content.decode("utf-8")
                    labels = chat_labels(language, environment="production")
                    self.assertIn(escape(labels["warning"]), body)
                    self.assertIn(escape(labels["single_turn"]), body)
                    self.assertIn("Generated drafts · claims not verified", body)
                    self.assertIn('data-vq-recovery-enabled="true"', body)
                    self.assertIn(f'action="{reverse("ai_core:ask-global")}"', body)
                    self.assertNotIn("For Staging recovery", body)
                    self.assertNotIn("Development preview:", body)
                    self.assertIn("no-store", response["Cache-Control"])

    @override_settings(VORNEQ_ENV="production")
    def test_homepage_uses_production_entry_label_for_eligible_actor(self):
        with override("en"), \
                patch("apps.ai_core.chat_page.is_chat_enabled", return_value=True), \
                patch("apps.ai_core.production_policy.production_actor_allowed", return_value=True):
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["phase_c_chat_link_label"], "Open AI chat")
