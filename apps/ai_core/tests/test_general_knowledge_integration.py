from apps.ai_core.tests.ledger_fakes import fake_reservation
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, override_settings
from apps.ai_core.engine.global_grounded import ask_global
from apps.ai_core.providers.exceptions import ProviderInvalidResponse
from apps.ai_core.general_knowledge_runtime import validate_knowledge
from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.providers.openai_responses import build_knowledge_payload
from apps.ai_core.tests.ledger_fakes import allow_paid_adapter_calls


class KnowledgeIntegrationTests(SimpleTestCase):
    def setUp(self):
        # V4-01: Adapter-Unit-Test mit gemocktem SDK -> synthetische Ledger-Freigabe.
        allow_paid_adapter_calls(self, "text")
        self.actor = Mock(is_authenticated=True)
        self.retriever = Mock()
        self.retriever.retrievers = ()
        self.provider = Mock()
        self.provider.generate_knowledge.return_value = {
            "answer": "Python: print(sum(range(1, 11))) = 55", "language": "en"}

    @override_settings(VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=True)
    def test_public_coding_bypasses_retrieval_without_citations(self):
        result = ask_global("Write Python code to sum numbers 1 to 10", "en",
                            actor=self.actor, provider=self.provider,
                            retriever=self.retriever, enabled=True)
        self.assertEqual(result["mode"], "model_knowledge")
        self.assertEqual(result["citations"], [])
        self.assertFalse(result["verified"])
        self.retriever.search.assert_not_called()

    @override_settings(VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=False)
    def test_flag_off_preserves_grounded_retrieval(self):
        self.retriever.search.return_value = []
        self.retriever.allowed_hosts = frozenset({"en.wikipedia.org"})
        result = ask_global("Write Python code to sum numbers 1 to 10", "en",
                            actor=self.actor, provider=self.provider,
                            retriever=self.retriever, enabled=True)
        self.assertEqual(result["mode"], "insufficient_evidence")
        self.provider.generate_knowledge.assert_not_called()

    @override_settings(VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=True)
    def test_official_question_never_uses_knowledge(self):
        with patch("apps.ai_core.engine.global_grounded.ask_grounded",
                   return_value={"answer": "", "citations": []}):
            result = ask_global("What is VORNEQ?", "en", actor=self.actor,
                                provider=self.provider, retriever=self.retriever,
                                enabled=True)
        self.assertEqual(result["route"], "official_vorneq")
        self.provider.generate_knowledge.assert_not_called()

    def test_uncited_schema_rejects_extra_citation_fields_and_urls(self):
        for output in (
            {"answer": "hello", "language": "en", "citations": []},
            {"answer": "https://example.org", "language": "en"},
            {"answer": "", "language": "en"},
        ):
            with self.assertRaises(ProviderInvalidResponse):
                validate_knowledge(output, language="en", max_answer_chars=1000)

    def test_budgeted_knowledge_uses_exact_payload_and_settles(self):
        inner = Mock()
        inner.model = "mock-model"
        inner.max_output_tokens = 100
        inner.last_usage = (12, 9)
        inner.knowledge_instructions.return_value = "fixed instructions"
        inner.generate_knowledge.return_value = {"answer": "55", "language": "en"}
        def call(**kwargs):
            inner.last_usage = (12, 9)
            return {"answer": "55", "language": "en"}
        inner.generate_knowledge.side_effect = call
        reservation = fake_reservation()  # V7-01: strukturell gültige Reservierung
        with patch("apps.ai_core.budgeted_provider.ledger.reserve",
                   return_value=reservation) as reserve, patch(
                       "apps.ai_core.budgeted_provider.ledger.settle") as settle:
            result = BudgetedProvider(inner, actor_id=1).generate_knowledge(
                question="sum 1 to 10", language="en")
        payload = build_knowledge_payload("sum 1 to 10", "en")
        self.assertEqual(reserve.call_args.kwargs["input_bytes"],
                         len(payload.encode("utf-8")) + len("fixed instructions"))
        settle.assert_called_once_with(reservation, usage=(12, 9), outcome="completed")
        self.assertEqual(result["answer"], "55")
