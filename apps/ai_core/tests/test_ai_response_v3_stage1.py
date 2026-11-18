"""Offline regression for V3 stage 1 (no paid API or network requests)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.engine.citation import (
    GeneratedAnswerRejected, CitationQuoteRejected, validate_generated,
)
from apps.ai_core.providers.openai_responses import (
    OpenAIResponsesProvider, build_request_payload,
)
from apps.ai_core.response_engine_v3 import (
    BASE_ANSWER_CHARS, PILOT_ANSWER_CHARS, enabled, answer_limit, guidance,
)

EXCERPT = (
    "A solar cell converts sunlight into electricity via a semiconductor. "
    "This is synthetic test evidence, not an authoritative public source."
)
SOURCE = {
    "source_id": "S1", "title": "Synthetic source", "excerpt": EXCERPT,
    "evidence_digest": "a" * 64, "source_key": "web:wikipedia:en:synthetic",
    "url": "https://en.wikipedia.org/wiki/SYNTHETIC",
}
LONG_ANSWER = ("Solar cells convert sunlight into electric current. " * 30).strip()


def generated(answer, quote=None):
    return {
        "answer": answer, "language": "en",
        "citations": [{
            "source_id": "S1", "evidence_digest": SOURCE["evidence_digest"],
            "evidence_quote": EXCERPT[:48] if quote is None else quote,
        }],
        "model_status": "generated", "grounded_status": "proposed",
        "verified": False, "error_code": "",
    }


class V3ScopeTests(SimpleTestCase):
    def test_only_development_and_staging_can_enable(self):
        for env, flag, expected in (
            ("production", True, False), ("staging", False, False),
            ("development", False, False), ("development", True, True),
            ("staging", True, True), ("unexpected", True, False),
        ):
            with self.subTest(env=env, flag=flag):
                config = SimpleNamespace(VORNEQ_ENV=env,
                                         VORNEQ_AI_RESPONSE_V3_ENABLED=flag)
                self.assertIs(enabled(config), expected)
                self.assertEqual(answer_limit(config),
                                 PILOT_ANSWER_CHARS if expected else BASE_ANSWER_CHARS)

    def test_multilingual_multipart_rules_never_echo_question(self):
        for question, lang in (
            ("ابن‌سینا که بود و آثار مهمش چه بودند؟", "fa"),
            ("What are solar cells and how do they work?", "en"),
            ("Was sind Solarzellen und wie funktionieren sie?", "de"),
        ):
            with self.subTest(lang=lang):
                rules = guidance(question, lang)
                self.assertIn("distinct parts", rules)
                self.assertIn("trusted excerpts", rules)
                self.assertIn("source IDs", rules)
                self.assertNotIn(question, rules)
        self.assertIn("main question directly", guidance("What is sunlight?", "en"))
        self.assertEqual(guidance("anything", "unsupported"), "")

    def test_model_instructions_are_default_off_and_citation_safe(self):
        regular = OpenAIResponsesProvider(model="mock", timeout_s=5, max_output_tokens=2048)
        v3 = OpenAIResponsesProvider(model="mock", timeout_s=5, max_output_tokens=2048,
                                     response_v3_enabled=True)
        question = "ابن‌سینا چه کسی بود و آثارش چه بودند؟"
        self.assertNotIn("distinct parts", regular.instructions_for(question, "fa"))
        self.assertIn("distinct parts", v3.instructions_for(question, "fa"))
        self.assertIn("source_id EXACTLY", v3.instructions_for(question, "fa"))
        self.assertIn("evidence_quote EXACTLY", v3.instructions_for(question, "fa"))


class V3AnswerBoundaryTests(SimpleTestCase):
    def test_pilot_can_accept_longer_answer_without_changing_default(self):
        self.assertGreater(len(LONG_ANSWER), BASE_ANSWER_CHARS)
        self.assertLess(len(LONG_ANSWER), PILOT_ANSWER_CHARS)
        with self.assertRaises(GeneratedAnswerRejected):
            validate_generated(generated(LONG_ANSWER), sources=[SOURCE], language="en")
        answer = validate_generated(
            generated(LONG_ANSWER), sources=[SOURCE], language="en",
            max_answer_chars=PILOT_ANSWER_CHARS,
        )
        self.assertEqual(answer["answer"], LONG_ANSWER)
        self.assertIs(answer["verified"], False)

    def test_rejects_invalid_limit_and_oversized_answer(self):
        for bad in (0, True, None, "2400", 2401):
            with self.subTest(bad=bad), self.assertRaises(GeneratedAnswerRejected):
                validate_generated(generated("ok"), sources=[SOURCE],
                                   language="en", max_answer_chars=bad)
        with self.assertRaises(GeneratedAnswerRejected):
            validate_generated(generated("x" * 2401), sources=[SOURCE],
                               language="en", max_answer_chars=2400)

    def test_exact_quote_validator_remains_fail_closed(self):
        bad_quote = EXCERPT[:48].replace(" ", "\u200c", 1)
        with self.assertRaises(CitationQuoteRejected):
            validate_generated(
                generated(LONG_ANSWER, quote=bad_quote), sources=[SOURCE],
                language="en", max_answer_chars=PILOT_ANSWER_CHARS,
            )


class V3PrepaidLedgerTests(SimpleTestCase):
    def test_synthetic_mock_with_no_declared_instructions_for_uses_base_prompt(self):
        """Dynamic MagicMock attrs must not make prepaid prompt smaller."""
        inner = MagicMock(model="synthetic", max_output_tokens=512,
                          instructions="x" * 100)
        inner.generate.return_value = generated("Synthetic answer.")
        with patch("apps.ai_core.budgeted_provider.ledger.reserve") as reserve, \
             patch("apps.ai_core.budgeted_provider.ledger.settle"):
            BudgetedProvider(inner, actor_id=3).generate(
                question="q", language="en", sources=[{"a": "ü"}],
            )
        expected = build_request_payload("q", "en", [{"a": "ü"}])
        self.assertEqual(
            reserve.call_args.kwargs["input_bytes"],
            100 + len(expected.encode("utf-8")),
        )
        inner.instructions_for.assert_not_called()

    def test_reservation_includes_effective_model_instructions(self):
        provider = OpenAIResponsesProvider(
            model="mock", timeout_s=5, max_output_tokens=2048,
            compact_sources=True, response_v3_enabled=True,
        )
        provider.generate = lambda **kwargs: generated("Synthetic answer.")
        question = "What are solar cells and how do they work?"
        with patch("apps.ai_core.budgeted_provider.ledger.reserve") as reserve, \
             patch("apps.ai_core.budgeted_provider.ledger.settle") as settle:
            BudgetedProvider(provider, actor_id=3).generate(
                question=question, language="en", sources=[SOURCE],
            )
        payload = build_request_payload(question, "en", [SOURCE], compact_sources=True)
        exact_bytes = (len(provider.instructions_for(question, "en").encode("utf-8"))
                       + len(payload.encode("utf-8")))
        self.assertEqual(reserve.call_args.kwargs["input_bytes"], exact_bytes)
        self.assertEqual(reserve.call_args.kwargs["max_output_tokens"], 2048)
        settle.assert_called_once()
