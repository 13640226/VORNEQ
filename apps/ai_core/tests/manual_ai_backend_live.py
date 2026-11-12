"""MANUAL ONLY: one real OpenAI call through the authenticated Django Phase B API.

Not named test_*.py: standard Django test discovery does not run this file.
Invokable ONLY using scripts/ai_dev_live_backend_e2e.ps1 -Live after user approval.
A wholly synthetic Citation replaces public search. No production data is read.
"""
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.gateway import Citation

ACK = "I_AUTHORIZE_ONE_REAL_OPENAI_CALL"
SOURCE = Citation(
    "S1", "article:synthetic-dev-live-e2e", "Synthetic public VORNEQ evidence",
    "A synthetic example for API connectivity: marker BLUE-Q7 appears here. "
    "This content was created for a development test, not pulled from a user database.",
    "/en/orientation/",
)


@override_settings(
    VORNEQ_ENV="development",
    VORNEQ_AI_PHASE_B_ENABLED=True,
    VORNEQ_AI_PHASE_C_ENABLED=True,
)
class OneRealDevelopmentBackendRequest(TestCase):
    def test_one_real_responses_request_through_django_api(self):
        if os.getenv("VORNEQ_AI_LIVE_E2E_ACK") != ACK:
            self.fail("Explicit approval gate absent; no API call made.")
        if os.getenv("VORNEQ_ENV") != "development":
            self.fail("Environment must be development; no API call made.")
        if os.getenv("DATABASE_URL") or os.getenv("REDIS_URL"):
            self.fail("External DB/cache settings present; no API call made.")
        if not os.getenv("OPENAI_API_KEY"):
            self.fail("API key unavailable; no API call made.")
        if os.getenv("VORNEQ_AI_PHASE_B_MODEL") != "gpt-6-luna":
            self.fail("Model must be gpt-6-luna; no API call made.")

        user = get_user_model().objects.create_user(
            username="synthetic-live-development-test",
            password="synthetic-local-never-reuse",
        )
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(user)
        page = browser.get(reverse("ai_core:chat") + "?lang=en")
        self.assertEqual(page.status_code, 200)
        self.assertIn("csrftoken", browser.cookies)

        # This patch replaces ONLY retrieval with synthetic PUBLIC evidence.
        # Authentication, CSRF, request budget, OpenAIResponsesProvider and
        # answer schema/citation checks remain completely real.
        with patch("apps.ai_core.engine.grounded.retrieve_public",
                   return_value=(SOURCE,)):
            response = browser.post(
                reverse("ai_core:ask-grounded"),
                data=json.dumps({
                    "question": "According to the synthetic public source, which marker is named?",
                    "language": "en",
                }),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=browser.cookies["csrftoken"].value,
            )

        payload = response.json()
        print("VORNEQ_BACKEND_HTTP=" + str(response.status_code))
        print("VORNEQ_API_MODEL=gpt-6-luna")
        print("VORNEQ_RESULT_MODE=" + str(payload.get("mode", "none")))
        print("VORNEQ_VERIFIED=" + str(payload.get("verified", "unknown")))
        print("VORNEQ_CITATION_COUNT=" + str(len(payload.get("citations", []))))
        print("VORNEQ_ERROR_CODE=" + str(payload.get("error", payload.get("error_code", "")))[:64])
        self.assertEqual(response.status_code, 200,
                         "Provider or citation processing did not return HTTP 200.")
        self.assertEqual(payload.get("mode"), "grounded_draft")
        self.assertIs(payload.get("verified"), False)
        self.assertEqual(payload.get("model_status"), "generated")
        self.assertEqual(len(payload.get("citations", [])), 1)
        self.assertEqual(payload["citations"][0]["source_key"], SOURCE.key)
        self.assertEqual(payload["citations"][0]["url"], SOURCE.url)
        print("REAL_VORNEQ_BACKEND_E2E=PASS")
