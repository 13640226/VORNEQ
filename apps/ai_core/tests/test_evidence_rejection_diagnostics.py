"""Offline multilingual evidence-rejection diagnostics regression.

Every question/source/provider response is synthetic. No live OpenAI request,
Production database, secrets, or network access is permitted by NoNetworkMixin.
"""
import json
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.chat_strings import chat_labels
from apps.ai_core.tests.test_ai_chat_ui_v2 import render_page
from apps.ai_core.tests.test_global_ai_api import (
    DEV, FakeRetriever, NoNetworkMixin, evidence, good_output,
)

QUESTION = "سلول خورشیدی چگونه کار می‌کند؟"
EXCERPT = "[SYNTHETIC] سلول خورشیدی نور را جذب می‌کند و با حرکت بارهای الکتریکی در یک مادهٔ نیمه‌رسانا انرژی نور را به جریان الکتریکی تبدیل می‌کند."
REASONS = frozenset({
    "invalid_generated_output", "citation_identity_rejected",
    "citation_digest_mismatch", "citation_quote_mismatch",
    "unsupported_numeric_claim", "evidence_rejected",
})


@override_settings(**DEV)
class PersianEvidenceDiagnosticsTests(NoNetworkMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(
            username="fa-evidence-test", email="fa-evidence@example.invalid",
            password="synthetic-only",
        )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.actor)
        self.endpoint = reverse("ai_core:ask-global")

    def _post(self, make, *, items=None, question=QUESTION):
        cache.clear()
        if items is None:
            items = evidence("fa", excerpt=EXCERPT)
        retriever = FakeRetriever(items)

        def produce(self_, *, question, language, sources):
            return make(sources, language)

        with patch("apps.ai_core.views_global.default_retriever", return_value=retriever), \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate",
                      autospec=True, side_effect=produce) as gen, \
                self.assertLogs("apps.ai_core.views_global", level="WARNING") as log:
            response = self.client.post(
                self.endpoint,
                data=json.dumps({"question": question, "language": "fa"}),
                content_type="application/json",
            )
        return response, gen, retriever, log.output

    def test_persian_rejection_categories_are_exact_and_do_not_log_content(self):
        def forged_quote(s, lang):
            obj = good_output(s, lang)
            obj["citations"][0]["evidence_quote"] = "PRIVATE_FAKED_QUOTE_SENTINEL"
            return obj

        def forged_digest(s, lang):
            obj = good_output(s, lang)
            obj["citations"][0]["evidence_digest"] = "a" * 64
            return obj

        def forged_identity(s, lang):
            obj = good_output(s, lang)
            obj["citations"][0]["source_id"] = "S9"
            return obj

        def malformed_output(s, lang):
            return {**good_output(s, lang), "verified": True}

        def fabricated_number(s, lang):
            return {**good_output(s, lang),
                    "answer": "این سلول خورشیدی ۹۹ درصد نور را به برق تبدیل می‌کند."}

        scenarios = {
            "citation_quote_mismatch": forged_quote,
            "citation_digest_mismatch": forged_digest,
            "citation_identity_rejected": forged_identity,
            "invalid_generated_output": malformed_output,
            "unsupported_numeric_claim": fabricated_number,
        }
        for reason, produce in scenarios.items():
            with self.subTest(reason=reason):
                response, gen, retriever, records = self._post(produce)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json(), {
                    "error": "INSUFFICIENT_EVIDENCE", "reason_code": reason,
                })
                self.assertIn("no-store", response["Cache-Control"])
                gen.assert_called_once()
                self.assertEqual(retriever.calls[0][1], "fa")
                # Bounded log has a static enum only, never the exception or any source text.
                self.assertEqual(records, [
                    f"WARNING:apps.ai_core.views_global:ai_evidence_rejected reason_code={reason}",
                ])
                for sensitive in (QUESTION, EXCERPT, "PRIVATE_FAKED_QUOTE_SENTINEL",
                                  "۹۹ درصد", "S9"):
                    self.assertNotIn(sensitive, "".join(records))

    def test_untrusted_source_identity_fails_closed_before_model(self):
        invalid = evidence("fa", key="official:forged", excerpt=EXCERPT)
        response, gen, _, messages = self._post(
            lambda s, lang: good_output(s, lang), items=invalid
        )
        self.assertEqual(response.json(), {
            "error": "INSUFFICIENT_EVIDENCE", "reason_code": "evidence_rejected"
        })
        gen.assert_not_called()
        self.assertEqual(len(messages), 1)

    def test_persian_missing_sources_returns_not_called_and_no_model(self):
        cache.clear()
        with patch("apps.ai_core.views_global.default_retriever",
                   return_value=FakeRetriever(())), \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate",
                      autospec=True) as gen:
            response = self.client.post(
                self.endpoint,
                data=json.dumps({"question": QUESTION, "language": "fa"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "insufficient_evidence")
        self.assertEqual(response.json()["model_status"], "not_called")
        gen.assert_not_called()

    def test_persian_private_question_still_denied_before_any_model_call(self):
        with patch("apps.ai_core.views_global.default_retriever") as retriever, \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate",
                      autospec=True) as gen:
            response = self.client.post(
                self.endpoint,
                data=json.dumps({"question": "اسناد خودم را نشان بده", "language": "fa"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"error": "UNSUPPORTED_QUESTION"})
        retriever.assert_not_called()
        gen.assert_not_called()


class MultilingualSafeUiEvidenceTests(SimpleTestCase):
    def test_fa_de_en_labels_for_all_bounded_rejection_codes(self):
        fields = (
            "unsupported", "rejectedEvidence", "rejectedOutput", "citationIdentity",
            "citationDigest", "citationQuote", "unsupportedNumber",
        )
        for language in ("fa", "de", "en"):
            with self.subTest(language=language):
                labels = chat_labels(language, environment="production")
                self.assertTrue(all(isinstance(labels[k], str) and labels[k] for k in fields))
                html = render_page(language, "production")
                for key in (
                    "data-vq-unsupported=", "data-vq-rejected-evidence=",
                    "data-vq-rejected-output=", "data-vq-citation-identity=",
                    "data-vq-citation-digest=", "data-vq-citation-quote=",
                    "data-vq-unsupported-number=",
                ):
                    self.assertIn(key, html)
                self.assertNotIn("Development preview", html)
                self.assertNotIn("Staging recovery", html)
        fa = chat_labels("fa", "production")
        self.assertIn("نقل‌قول", fa["citationQuote"])
        self.assertIn("اثر انگشت", fa["citationDigest"])
        self.assertIn("عدد", fa["unsupportedNumber"])
        self.assertIn("درخواستی به مدل ارسال نشد", fa["unsupported"])
        self.assertIn("هزینه", fa["rejectedEvidence"])

    def test_js_reason_enum_allowlist_used_for_fresh_and_recovered_422(self):
        js = (Path(settings.BASE_DIR) / "assets" / "js" /
              "phase-c-chat.js").read_text(encoding="utf-8")
        for code in REASONS:
            self.assertIn(code + ":", js)
        self.assertIn("function rejectionMessage(data)", js)
        self.assertIn("Object.prototype.hasOwnProperty.call(safeReasons, data.reason_code)", js)
        self.assertIn("appendMessage(rejectionMessage(data.response)", js)
        self.assertIn("appendMessage(rejectionMessage(failure)", js)
        self.assertIn('data.error === "UNSUPPORTED_QUESTION"', js)
        self.assertNotIn("appendMessage(data.reason_code", js)
        self.assertNotIn("appendMessage(failure.message", js)
        example_block = js[js.index("Example prompts only fill the box"):js.index("const language =")]
        self.assertNotIn("requestSubmit", example_block)
