"""Offline regression: quote hints, provider parsing and guarded error UX.

No API calls, credentials, Production DB writes or live user questions.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from apps.ai_core.engine.citation import (
    CitationDigestRejected, CitationIdentityRejected, CitationQuoteRejected,
    validate_generated,
)
from apps.ai_core.providers.exceptions import ProviderInvalidResponse
from apps.ai_core.providers.openai_responses import (
    _SYSTEM_INSTRUCTIONS, build_request_payload,
)
from apps.ai_core.views_global import run_global_pipeline


EXCERPT = (
    "سلول خورشیدی نور را در نیمه‌رسانا جذب می‌کند و جریان برق تولید می‌کند. "
    "این جمله صرفاً داده آزمایشی است و استناد واقعی محسوب نمی‌شود."
)
SOURCES = [{
    "source_id": "S1", "source_key": "web:wikipedia:fa:synthetic",
    "title": "منبع آزمایشی", "excerpt": EXCERPT,
    "evidence_digest": "b" * 64, "url": "https://fa.wikipedia.org/wiki/SYNTHETIC",
}]


def _candidate(quote, **changes):
    candidate = {
        "answer": "سلول خورشیدی می‌تواند برق تولید کند.",
        "language": "fa",
        "citations": [{
            "source_id": "S1", "evidence_digest": "b" * 64,
            "evidence_quote": quote,
        }],
        "model_status": "generated", "grounded_status": "proposed",
        "verified": False, "error_code": "",
    }
    candidate["citations"][0].update(changes)
    return candidate


class TrustedQuoteHintTests(SimpleTestCase):
    def test_compact_payload_contains_exact_span_without_normalization(self):
        payload = json.loads(build_request_payload(
            "سلول خورشیدی چگونه کار می‌کند؟", "fa", SOURCES,
            compact_sources=True))
        quote_hint = payload["sources"][0]["quote_hint"]
        self.assertEqual(quote_hint, EXCERPT[:80])
        self.assertIn("\u200c", quote_hint)
        self.assertGreaterEqual(len(quote_hint), 8)
        self.assertLessEqual(len(quote_hint), 80)
        self.assertIn("quote_hint", _SYSTEM_INSTRUCTIONS)
        self.assertIn("ZWNJ", _SYSTEM_INSTRUCTIONS)
        output = validate_generated(
            _candidate(quote_hint), sources=SOURCES, language="fa")
        self.assertFalse(output["verified"])
        self.assertEqual(output["citations"][0]["source_id"], "S1")

    def test_bogus_quote_and_zwnj_changes_still_rejected(self):
        hint = EXCERPT[:80]
        for tampered in ("متن نامربوط و ساختگی", hint.replace("\u200c", " ")):
            with self.subTest(quote=tampered[:25]):
                with self.assertRaises(CitationQuoteRejected):
                    validate_generated(_candidate(tampered), sources=SOURCES,
                                       language="fa")

    def test_digest_or_source_id_spoofing_still_rejected(self):
        hint = EXCERPT[:80]
        with self.assertRaises(CitationDigestRejected):
            validate_generated(_candidate(hint, evidence_digest="0" * 64),
                               sources=SOURCES, language="fa")
        with self.assertRaises(CitationIdentityRejected):
            validate_generated(_candidate(hint, source_id="S9"),
                               sources=SOURCES, language="fa")


@override_settings(VORNEQ_ENV="development")
class PostProviderFailureContractTests(SimpleTestCase):
    def test_invalid_parsed_response_returns_fixed_diagnostic_without_retry(self):
        secret = "PROVIDER_PRIVATE_RAW_PAYLOAD_DO_NOT_LOG"
        request = SimpleNamespace(user=SimpleNamespace(pk=1))
        with patch("apps.ai_core.views_global.reserve_global_request"), \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider"), \
                patch("apps.ai_core.views_global.ask_global",
                      side_effect=ProviderInvalidResponse(secret)) as call, \
                self.assertLogs("apps.ai_core.views_global", "WARNING") as logs:
            data, status, meta = run_global_pipeline(
                request, "How does a solar cell work?", "en")
        self.assertEqual(status, 503)
        self.assertEqual(data, {
            "error": "provider_unavailable",
            "reason_code": "invalid_provider_response",
        })
        self.assertEqual(call.call_count, 1)
        self.assertNotIn(secret, "\n".join(logs.output))
        self.assertEqual(logs.output, [
            "WARNING:apps.ai_core.views_global:"
            "ai_provider_response_rejected reason_code=invalid_provider_response",
        ])
        self.assertIsNone(meta["budgeted"])

    def test_browser_error_is_fixed_and_never_auto_retries(self):
        js = (Path(settings.BASE_DIR) / "assets/js/phase-c-chat.js").read_text(
            encoding="utf-8")
        self.assertIn('data.reason_code === "invalid_provider_response"', js)
        self.assertIn("return labels.rejectedOutput || labels.error", js)
        self.assertIn('if (response.status === 503)', js)
        self.assertIn("if (requestId) recoveryBlocked = true;", js)
        self.assertNotIn("appendMessage(failure.message", js)
