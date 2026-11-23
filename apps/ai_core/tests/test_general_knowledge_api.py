from unittest.mock import Mock, patch
from django.test import SimpleTestCase, override_settings
from apps.ai_core.views_global import run_global_pipeline


class KnowledgePipelineApiTests(SimpleTestCase):
    @override_settings(VORNEQ_ENV="production",
                       VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=True)
    def test_pipeline_preserves_ledger_wrapper_and_uncited_mode(self):
        request = Mock()
        request.user.pk = 1
        with patch("apps.ai_core.views_global.ledger_enabled", return_value=True), \
             patch("apps.ai_core.views_global.reserve_global_request"), \
             patch("apps.ai_core.views_global.OpenAIResponsesProvider") as provider, \
             patch("apps.ai_core.views_global.BudgetedProvider") as wrapper, \
             patch("apps.ai_core.views_global.default_retriever") as retriever:
            wrapper.return_value.generate_knowledge.return_value = {
                "answer": "55", "language": "en"}
            body, status, meta = run_global_pipeline(
                request, "Write Python code to sum numbers 1 to 10", "en")
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "model_knowledge")
        self.assertEqual(body["citations"], [])
        wrapper.assert_called_once()
        wrapper.return_value.generate_knowledge.assert_called_once()
        retriever.return_value.search.assert_not_called()
