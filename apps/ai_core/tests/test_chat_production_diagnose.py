"""Offline contract tests: diagnostics never call paid providers or expose secrets."""
import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class ChatProductionDiagnoseTests(SimpleTestCase):
    @override_settings(VORNEQ_ENV="production", DEBUG=False,
                       VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED=False,
                       VORNEQ_AI_EMERGENCY_STOP=True,
                       VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS="1")
    def test_fail_closed_and_no_sensitive_values(self):
        out = StringIO()
        with patch("apps.ai_core.management.commands.ai_chat_production_diagnose.release_allowed", return_value=False), \
             patch("apps.ai_core.management.commands.ai_chat_production_diagnose.ledger_enabled", return_value=False), \
             patch("apps.ai_core.management.commands.ai_chat_production_diagnose.recovery_enabled", return_value=False), \
             patch("apps.ai_core.management.commands.ai_chat_production_diagnose.production_enabled", return_value=False), \
             patch("apps.ai_core.providers.openai_responses.OpenAIResponsesProvider.generate", side_effect=AssertionError("paid call")):
            call_command("ai_chat_production_diagnose", stdout=out)
        result = json.loads(out.getvalue())
        self.assertFalse(result["chat_enabled"])
        self.assertFalse(result["checks"]["production_flag"])
        self.assertFalse(result["checks"]["emergency_stop_clear"])
        self.assertNotIn("OPENAI_API_KEY", out.getvalue())
        self.assertNotIn('"1"', out.getvalue())

    @override_settings(VORNEQ_ENV="production", DEBUG=False,
                       VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED=True,
                       VORNEQ_AI_EMERGENCY_STOP=False)
    def test_reports_gates_without_enabling_chat(self):
        out = StringIO()
        with patch("apps.ai_core.management.commands.ai_chat_production_diagnose.release_allowed", return_value=True), \
             patch("apps.ai_core.management.commands.ai_chat_production_diagnose.ledger_enabled", return_value=True), \
             patch("apps.ai_core.management.commands.ai_chat_production_diagnose.recovery_enabled", return_value=True), \
             patch("apps.ai_core.management.commands.ai_chat_production_diagnose.production_enabled", return_value=False):
            call_command("ai_chat_production_diagnose", stdout=out)
        result = json.loads(out.getvalue())
        self.assertTrue(result["checks"]["production_flag"])
        self.assertFalse(result["chat_enabled"])
