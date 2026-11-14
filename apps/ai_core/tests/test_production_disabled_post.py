"""Fail-closed production AI endpoint tests; no DB or external network access."""
from unittest.mock import patch

from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(
    VORNEQ_ENV="production", DEBUG=False,
    VORNEQ_AI_CORE_ENABLED=False,
    VORNEQ_AI_PHASE_B_ENABLED=False,
    VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED=False,
    VORNEQ_AI_EMERGENCY_STOP=True,
)
class ProductionAiDisabledPostTests(SimpleTestCase):
    def test_unauthenticated_post_rejected_without_provider_or_retrieval(self):
        client = Client(enforce_csrf_checks=False)
        with patch("apps.ai_core.views_global.OpenAIResponsesProvider", side_effect=AssertionError("provider constructed")) as provider, \
             patch("apps.ai_core.views_global.default_retriever", side_effect=AssertionError("retriever called")) as retriever, \
             patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider", side_effect=AssertionError("phase B provider constructed")) as phase_b_provider, \
             patch("apps.ai_core.gateway.ask_public", side_effect=AssertionError("offline AI invoked")) as offline:
            for name in ("ai_core:ask-global", "ai_core:ask-grounded", "ai_core:ask"):
                with self.subTest(endpoint=name):
                    response = client.post(reverse(name), data=b"", content_type="application/json")
                    self.assertEqual(response.status_code, 404)
            provider.assert_not_called()
            retriever.assert_not_called()
            phase_b_provider.assert_not_called()
            offline.assert_not_called()

    def test_global_emergency_stop_overrides_production_flag(self):
        client = Client(enforce_csrf_checks=False)
        with override_settings(VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED=True), \
             patch("apps.ai_core.views_global.OpenAIResponsesProvider", side_effect=AssertionError("provider constructed")) as provider, \
             patch("apps.ai_core.views_global.default_retriever", side_effect=AssertionError("retriever called")) as retriever:
            response = client.post(reverse("ai_core:ask-global"), data=b"", content_type="application/json")
            self.assertEqual(response.status_code, 404)
            provider.assert_not_called()
            retriever.assert_not_called()