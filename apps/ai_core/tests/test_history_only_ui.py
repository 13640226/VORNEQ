"""History-only UI must never activate the paid pipeline."""
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.chat_strings import chat_labels
from apps.ai_core.models import AIConversation, AIMessage
from apps.ai_core.tests.test_global_ai_api import NoNetworkMixin
from apps.ai_core.tests.test_ai_staging_trial import STAGING_SETTINGS, TEST_ENV

HISTORY = dict(STAGING_SETTINGS, VORNEQ_AI_CONVERSATIONS_ENABLED=True,
               VORNEQ_AI_FEEDBACK_ENABLED=True,
               VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY="allowlist",
               VORNEQ_GLOBAL_AI_ENABLED=False,
               VORNEQ_AI_STAGING_TRIAL_ENABLED=False,
               VORNEQ_AI_EMERGENCY_STOP=True)


@override_settings(**HISTORY)
class HistoryOnlyTests(NoNetworkMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.owner = get_user_model().objects.create_user(
            username="history-owner", password="synthetic-only")
        self.other = get_user_model().objects.create_user(
            username="history-other", password="synthetic-only")
        env = patch.dict(os.environ, {"RENDER_SERVICE_ID": "srv-dbm7dvc9v7es7393g70g"})
        env.start()
        self.addCleanup(env.stop)
        flags = override_settings(VORNEQ_AI_CONVERSATIONS_ALLOWED_USER_IDS=str(self.owner.pk))
        flags.enable()
        self.addCleanup(flags.disable)
        self.client.force_login(self.owner)
        self.conv = AIConversation.objects.create(owner=self.owner)
        self.msg = AIMessage.objects.create(conversation=self.conv, sequence=1,
            role=AIMessage.ROLE_ASSISTANT, status=AIMessage.STATUS_COMPLETED,
            content="Synthetic saved answer")
        self.feedback_url = reverse("ai_core:conversation-message-feedback",
                                    args=[self.conv.pk, self.msg.pk])
        for name in ("apps.ai_core.views_conversations.run_global_pipeline",
                     "apps.ai_core.views_global.paid_text_provider",
                     "apps.ai_ledger.service.reserve", "apps.ai_ledger.service.reserve_with_config"):
            p = patch(name, side_effect=AssertionError("paid path invoked"))
            p.start()
            self.addCleanup(p.stop)

    def test_history_only_page_and_home_link_in_three_languages(self):
        for lang in ("fa", "de", "en"):
            with self.subTest(lang=lang):
                page = self.client.get(reverse("ai_core:chat"), {"lang": lang})
                self.assertEqual(page.status_code, 200)
                self.assertContains(page, 'data-vq-history-only="true"')
                self.assertContains(page, 'data-vq-feedback="true"')
                labels = chat_labels(lang, "staging")
                self.assertContains(page, labels["history_only"])
                self.assertContains(page, labels["history_title"])
                self.assertContains(page, labels["history_intro"])
                self.assertNotContains(page, labels["examples_title"])
                self.assertContains(page, 'data-vq-history-notice', count=1)
                self.assertContains(page, '<h2 class="vq-chat__welcome-title">' +
                                    labels["history_title"] + '</h2>', html=True)
                self.assertContains(page, 'hidden inert data-vq-chat-form')
                self.assertNotContains(page, 'action="' + reverse("ai_core:ask-grounded") + '"')
                self.assertNotContains(page, 'action="' + reverse("ai_core:ask-global") + '"')
                self.assertNotContains(page, 'data-vq-streaming="true"')
                self.assertNotContains(page, 'mic-button.js')
                self.assertIn("no-store", page["Cache-Control"])
                self.assertIn("noindex", page["X-Robots-Tag"])
        home = self.client.get(reverse("home"))
        self.assertContains(home, "data-vq-history-link")
        self.assertFalse(home.context["phase_c_chat_enabled"])

    def test_owner_history_feedback_and_paid_send_denial(self):
        detail = reverse("ai_core:conversation-detail", args=[self.conv.pk])
        self.assertEqual(self.client.get(detail).json()["messages"][0]["feedback"], None)
        self.assertEqual(self.client.post(self.feedback_url, data='{"rating":"like"}',
                                        content_type="application/json").status_code, 200)
        self.assertEqual(self.client.get(detail).json()["messages"][0]["feedback"], "like")
        self.assertEqual(self.client.post(self.feedback_url, data='{"rating":"dislike"}',
                                        content_type="application/json").status_code, 200)
        self.assertEqual(self.client.get(self.feedback_url).json()["rating"], "dislike")
        self.assertEqual(self.client.delete(self.feedback_url).json()["rating"], None)
        for endpoint in ("conversation-messages", "conversation-messages-stream"):
            result = self.client.post(reverse("ai_core:"+endpoint,args=[self.conv.pk]),
                                     data='{"question":"synthetic","language":"en"}',
                                     content_type="application/json")
            self.assertEqual(result.status_code,404)
        self.assertEqual(AIMessage.objects.filter(conversation=self.conv).count(),1)

    def test_cross_user_and_csrf(self):
        other = Client()
        other.force_login(self.other)
        self.assertEqual(other.get(reverse("ai_core:chat")).status_code,404)
        self.assertEqual(other.get(self.feedback_url).status_code, 404)
        self.assertEqual(other.post(self.feedback_url, data='{"rating":"like"}',
                                    content_type="application/json").status_code, 404)
        self.assertEqual(other.delete(self.feedback_url).status_code, 404)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(self.feedback_url,data='{"rating":"like"}',
                                    content_type="application/json").status_code,403)
        self.assertEqual(Client().get(self.feedback_url).status_code,401)

    def test_disabled_flags_wrong_runtime_and_actor_policy(self):
        with override_settings(VORNEQ_AI_FEEDBACK_ENABLED=False):
            for lang in ("fa", "de", "en"):
                page = self.client.get(reverse("ai_core:chat"), {"lang": lang})
                labels = chat_labels(lang, "staging")
                self.assertNotContains(page, 'data-vq-feedback="true"')
                self.assertNotContains(page, labels["history_only"])
                self.assertContains(page, labels["history_generation_off"])
                self.assertContains(page, labels["history_title"])
        with override_settings(VORNEQ_AI_CONVERSATIONS_ENABLED=False):
            self.assertEqual(self.client.get(reverse("ai_core:chat")).status_code,404)
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": "wrong"}):
            self.assertEqual(self.client.get(reverse("ai_core:chat")).status_code,404)
        with override_settings(VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY="invalid"):
            self.assertEqual(self.client.get(reverse("ai_core:chat")).status_code,404)

    def test_production_history_uses_own_identity_without_paid_gate(self):
        with override_settings(VORNEQ_ENV="production", VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED=False):
            self.assertEqual(self.client.get(reverse("ai_core:chat")).status_code,404)
            with patch.dict(os.environ, {"RENDER_SERVICE_ID":"srv-dadn07eq1p3s73eccau0"}):
                page = self.client.get(reverse("ai_core:chat"))
                self.assertContains(page,'data-vq-history-only="true"')
                self.assertContains(page,'data-vq-feedback="true"')

    def test_global_switch_off_does_not_fall_back_to_legacy_trial(self):
        # Even with an otherwise valid legacy trial, history mode must be non-generating.
        with patch("apps.ai_core.chat_page.is_chat_enabled", return_value=True):
            self.assertContains(self.client.get(reverse("ai_core:chat")),
                                'data-vq-history-only="true"')
