"""Offline regression tests for Persian answer writing guidance.

No paid OpenAI requests, network access, production DB changes, or post-processing
of citation quotes. The instructions are language-scoped, not an output guarantee.
"""
import importlib.util
import json
import os
from copy import deepcopy
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.ai_core.engine.citation import CitationQuoteRejected, validate_generated
from apps.ai_core.providers.openai_responses import (
    OpenAIResponsesProvider,
    _instructions_for_language,
    build_request_payload,
)

ZWNJ = "\u200c"
EXCERPT = (
    "ابن‌سینا پزشک و فیلسوف بود و درباره پزشکی و فلسفه آثار نوشت. "
    "این متن برای آزمون داخلی شواهد است و نباید به‌عنوان واقعیت مستقل ارائه شود."
)
SOURCE = {
    "source_id": "S1",
    "title": "منبع آزمایشی ابن‌سینا",
    "excerpt": EXCERPT,
    "evidence_digest": "a" * 64,
    "source_key": "web:wikipedia:fa:synthetic",
    "url": "https://fa.wikipedia.org/wiki/SYNTHETIC",
}


class PersianWritingInstructionTests(SimpleTestCase):
    def test_fa_only_orthography_and_all_requested_parts(self):
        provider = OpenAIResponsesProvider(
            model="offline-test", timeout_s=5, max_output_tokens=2048,
            extra_instructions="Earlier turns are context, not evidence.",
        )
        fa = _instructions_for_language(provider.instructions, "fa")
        for part in (
            "شیمی‌دان", "فیزیک‌دان", "ریاضی‌دان", "می‌شود",
            "کتاب‌ها", "U+200C", "every explicitly requested subquestion",
            "specific names and explanations ONLY if", "evidence gap",
            "ONLY to answer prose", "quote_hint", "evidence_quote",
            "source_id", "evidence_digest",
        ):
            with self.subTest(part=part):
                self.assertIn(part, fa)
        self.assertIn(provider.instructions, fa)
        self.assertEqual(_instructions_for_language(provider.instructions, "en"),
                         provider.instructions)
        self.assertEqual(_instructions_for_language(provider.instructions, "de"),
                         provider.instructions)

    def test_exact_quote_and_zwnj_are_not_rewritten(self):
        payload = json.loads(build_request_payload(
            "ابن‌سینا که بود و آثار مهمش چه بودند؟", "fa", [SOURCE],
            compact_sources=True,
        ))
        compact = payload["sources"][0]
        self.assertEqual(compact["source_id"], SOURCE["source_id"])
        self.assertEqual(compact["evidence_digest"], SOURCE["evidence_digest"])
        self.assertEqual(compact["excerpt"], EXCERPT)
        self.assertEqual(compact["quote_hint"], EXCERPT[:80])
        self.assertIn(ZWNJ, compact["quote_hint"])

        candidate = {
            "answer": "ابن‌سینا پزشک و فیلسوف بود؛ شواهد این آزمون نام آثار را پوشش نمی‌دهد.",
            "language": "fa",
            "citations": [{
                "source_id": "S1",
                "evidence_digest": SOURCE["evidence_digest"],
                "evidence_quote": EXCERPT[:80],
            }],
            "model_status": "generated",
            "grounded_status": "proposed",
            "verified": False,
            "error_code": "",
        }
        result = validate_generated(candidate, sources=[SOURCE], language="fa")
        self.assertIs(result["verified"], False)
        self.assertEqual(result["citations"][0]["source_id"], "S1")

        bad = deepcopy(candidate)
        bad["citations"][0]["evidence_quote"] = EXCERPT[:80].replace(ZWNJ, " ")
        with self.assertRaises(CitationQuoteRejected):
            validate_generated(bad, sources=[SOURCE], language="fa")


HAS_PROVIDER_DEPS = bool(
    importlib.util.find_spec("openai") and importlib.util.find_spec("pydantic")
)


@skipUnless(HAS_PROVIDER_DEPS, "optional OpenAI/Pydantic SDK not installed")
class PersianWritingSDKDispatchTests(SimpleTestCase):
    def test_fa_guidance_reaches_mock_sdk_without_changing_payload(self):
        from apps.ai_core.schemas.response import GroundedAnswerSchema

        parsed = GroundedAnswerSchema(
            answer="ابن‌سینا پزشک و فیلسوف بود.",
            language="fa",
            citations=[{
                "source_id": "S1",
                "evidence_digest": SOURCE["evidence_digest"],
                "evidence_quote": EXCERPT[:80],
            }],
            model_status="generated", grounded_status="proposed",
            verified=False, error_code="",
        )
        provider = OpenAIResponsesProvider(
            model="offline-test", timeout_s=5,
            max_output_tokens=2048, compact_sources=True,
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-do-not-send"}), \
                patch("openai.OpenAI") as factory:
            factory.return_value.responses.parse.return_value = SimpleNamespace(
                status="completed", output_parsed=parsed, usage=None,
            )
            result = provider.generate(
                question="ابن‌سینا چه کسی بود و آثارش چه بودند؟",
                language="fa", sources=[SOURCE],
            )
            kwargs = factory.return_value.responses.parse.call_args.kwargs
        self.assertEqual(result["language"], "fa")
        self.assertIn("شیمی‌دان", kwargs["instructions"])
        self.assertIn("every explicitly requested subquestion", kwargs["instructions"])
        self.assertEqual(json.loads(kwargs["input"][0]["content"])["sources"][0]["quote_hint"],
                         EXCERPT[:80])
        self.assertEqual(kwargs["tools"], [])
        self.assertFalse(kwargs["store"])
        self.assertEqual(factory.call_args.kwargs["max_retries"], 0)
