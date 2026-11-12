"""Offline Phase C integration: real Django/CSRF -> real SDK -> HTTP MockTransport.

A synthetic public-source snapshot is used instead of production search/DB.
The optional SDK dependency is intentionally not present in standard CI.
"""
import importlib.util
import json
import os
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.engine.citation import authorized_context
from apps.ai_core.gateway import Citation

SDK_READY = all(importlib.util.find_spec(name) is not None
                for name in ("openai", "httpx2", "pydantic"))
SOURCE = Citation(
    "S1", "article:synthetic-dev-e2e", "Synthetic public evidence",
    "The synthetic VORNEQ training marker is BLUE-Q7. This is sample evidence only.",
    "/en/orientation/",
)


@skipUnless(SDK_READY, "Optional OpenAI SDK is not present in normal CI")
@override_settings(
    VORNEQ_ENV="development",
    VORNEQ_AI_PHASE_B_ENABLED=True,
    VORNEQ_AI_PHASE_C_ENABLED=True,
)
class OfflineDjangoOpenAIIntegration(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="synthetic-openai-e2e", password="synthetic-never-reuse"
        )

    def csrf_client(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        page = browser.get(reverse("ai_core:chat") + "?lang=en")
        self.assertEqual(page.status_code, 200)
        self.assertIn("csrftoken", browser.cookies)
        return browser, browser.cookies["csrftoken"].value

    def test_real_sdk_mock_http_through_csrf_protected_backend(self):
        import httpx2
        from openai import OpenAI

        context = authorized_context([SOURCE])[0]
        output = {
            "answer": "The synthetic public source identifies marker BLUE-Q7.",
            "language": "en",
            "citations": [{
                "source_id": context["source_id"],
                "evidence_digest": context["evidence_digest"],
                "evidence_quote": "The synthetic VORNEQ training marker is BLUE-Q7.",
            }],
            "model_status": "generated",
            "grounded_status": "proposed",
            "verified": False,
            "error_code": "",
        }
        observed = []

        def mock_http(request):
            body = json.loads(request.content)
            self.assertEqual(request.url.host, "offline-vorneq.invalid")
            self.assertEqual(request.method, "POST")
            self.assertEqual(body["model"], "synthetic-model")
            self.assertIs(body["store"], False)
            self.assertEqual(body["tools"], [])
            self.assertEqual(body["max_output_tokens"], 512)
            self.assertIn("BLUE-Q7", body["input"][0]["content"])
            observed.append(body)
            return httpx2.Response(200, json={
                "id": "resp_vorneq_offline_e2e",
                "object": "response", "created_at": 1762920000,
                "model": "synthetic-model", "status": "completed",
                "error": None, "incomplete_details": None,
                "output": [{
                    "id": "msg_offline_e2e", "type": "message",
                    "status": "completed", "role": "assistant",
                    "content": [{
                        "type": "output_text", "annotations": [],
                        "text": json.dumps(output),
                    }],
                }],
                "usage": {
                    "input_tokens": 30, "output_tokens": 40, "total_tokens": 70
                },
            })

        offline_client = OpenAI(
            api_key="sk-synthetic-no-external-call",
            base_url="https://offline-vorneq.invalid/v1",
            timeout=8, max_retries=0,
            http_client=httpx2.Client(transport=httpx2.MockTransport(mock_http)),
        )
        browser, csrf = self.csrf_client()
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-synthetic-no-external-call",
            "VORNEQ_AI_PHASE_B_MODEL": "synthetic-model",
        }):
            with patch("apps.ai_core.engine.grounded.retrieve_public",
                       return_value=(SOURCE,)):
                with patch("openai.OpenAI", return_value=offline_client):
                    response = browser.post(
                        reverse("ai_core:ask-grounded"),
                        data=json.dumps({
                            "question": "Which marker does the synthetic evidence state?",
                            "language": "en",
                        }), content_type="application/json",
                        HTTP_X_CSRFTOKEN=csrf,
                    )
        self.assertEqual(response.status_code, 200, response.content[:500])
        result = response.json()
        self.assertIs(result["verified"], False)
        self.assertEqual(result["mode"], "grounded_draft")
        self.assertEqual(result["model_status"], "generated")
        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["citations"][0]["evidence_digest"],
                         context["evidence_digest"])
        self.assertEqual(len(observed), 1)

    def test_missing_csrf_rejected_without_provider(self):
        browser, csrf = self.csrf_client()
        with patch("apps.ai_core.engine.grounded.retrieve_public") as retrieval:
            response = browser.post(
                reverse("ai_core:ask-grounded"),
                data=json.dumps({"question": "public test", "language": "en"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 403)
        retrieval.assert_not_called()

    def test_missing_sources_refuses_without_provider(self):
        browser, csrf = self.csrf_client()
        with patch.dict(os.environ, {"VORNEQ_AI_PHASE_B_MODEL": "synthetic-model"}):
            with patch("apps.ai_core.engine.grounded.retrieve_public",
                       return_value=()):
                with patch("apps.ai_core.providers.openai_responses.OpenAIResponsesProvider.generate"
                           ) as provider:
                    response = browser.post(
                        reverse("ai_core:ask-grounded"),
                        data=json.dumps({
                            "question": "no source expected", "language": "en"
                        }), content_type="application/json",
                        HTTP_X_CSRFTOKEN=csrf,
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model_status"], "not_called")
        provider.assert_not_called()
