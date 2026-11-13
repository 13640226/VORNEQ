"""Staging chat UI access regression: no provider calls or real secrets."""
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.ai_core.tests.test_ai_staging_trial import STAGING_SETTINGS, TEST_ENV


@override_settings(**STAGING_SETTINGS)
class StagingOwnerChatUITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="staging-ui-owner", email="owner@example.invalid",
            password="synthetic-test-only",
        )
        cls.other = get_user_model().objects.create_user(
            username="staging-ui-other", password="synthetic-test-only",
        )

    def setUp(self):
        self.url = reverse("ai_core:chat")
        env = patch.dict(os.environ, TEST_ENV)
        env.start()
        self.addCleanup(env.stop)
        allow = override_settings(VORNEQ_AI_STAGING_ALLOWED_USER_IDS=str(self.owner.pk))
        allow.enable()
        self.addCleanup(allow.disable)

    def test_owner_can_open_staging_chat_without_provider_request(self):
        self.client.force_login(self.owner)
        with patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider") as provider:
            response = self.client.get(self.url + "?lang=fa")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Authorized staging trial")
        self.assertContains(response, reverse("ai_core:ask-grounded"))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])
        provider.assert_not_called()

    def test_anonymous_denied(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_other_user_denied(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_trial_disabled_denied(self):
        self.client.force_login(self.owner)
        with override_settings(VORNEQ_AI_STAGING_TRIAL_ENABLED=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_sha_mismatch_denied(self):
        self.client.force_login(self.owner)
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": "f" * 40}):
            self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_production_denied_even_with_staging_flags(self):
        self.client.force_login(self.owner)
        with override_settings(VORNEQ_ENV="production"):
            self.assertEqual(self.client.get(self.url).status_code, 404)
