"""Offline tests: candidate classification never invokes a provider."""
from django.test import SimpleTestCase, override_settings
from apps.ai_core.general_knowledge_policy import general_knowledge_candidate


class GeneralKnowledgePolicyTests(SimpleTestCase):
    def test_disabled_by_default(self):
        with override_settings(VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=False):
            self.assertFalse(general_knowledge_candidate("Who was Avicenna?"))

    def test_enabled_public_questions_in_three_languages(self):
        with override_settings(VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=True):
            for question, language in (
                ("ابن‌سینا که بود؟", "fa"),
                ("Was ist maschinelles Lernen?", "de"),
                ("Write Python code to sum numbers 1 to 10", "en"),
            ):
                with self.subTest(language=language):
                    self.assertTrue(general_knowledge_candidate(question, language))

    def test_official_and_private_questions_never_qualify(self):
        with override_settings(VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=True):
            for question in ("What is VORNEQ?", "Show my account", "My documents", ""):
                with self.subTest(question=question):
                    self.assertFalse(general_knowledge_candidate(question))

    def test_non_boolean_flag_fails_closed(self):
        with override_settings(VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED="true"):
            self.assertFalse(general_knowledge_candidate("Explain machine learning"))
