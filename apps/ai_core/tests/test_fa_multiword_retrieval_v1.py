"""Persian compound-name retrieval: synthetic, deterministic, no network/AI calls."""
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.ai_core.engine.evidence_ranking import (
    persian_fallback_search_text, rank_evidence, search_keywords,
)
from apps.ai_core.engine.global_grounded import ask_global
from apps.ai_core.web_retrieval import RetrievalError, WebEvidence, WikipediaRetriever

TS = "2026-11-17T19:00:00+00:00"
QUESTION = "ابن‌سینا که بود؟"
EXCERPT = (
    "[SYNTHETIC EVIDENCE] ابن سینا دانشمند و فیلسوف بود. "
    "در این آزمایش همه گزاره‌ها ساختگی هستند و فقط تطبیق نام ارزیابی می‌شود."
)


def article(title="ابن سینا", pageid=123, excerpt=EXCERPT, host="fa.wikipedia.org"):
    return WebEvidence(
        f"web:wikipedia:fa:{pageid}", title,
        f"https://{host}/wiki/SYNTHETIC_{pageid}",
        "Wikipedia (fa)", excerpt, TS,
    )


class FakeRetriever:
    """All source data are synthetic and no network transport is constructed."""

    name = "wikipedia"
    source_type = "encyclopedia"
    allowed_hosts = WikipediaRetriever.allowed_hosts

    def __init__(self, first=(), second=(), error=None):
        self.calls = []
        self.first = tuple(first)
        self.second = tuple(second)
        self.error = error
        self.last_status = (("wikipedia", "synthetic"),)

    def search(self, query, language, limit=3):
        self.calls.append((query, language, limit))
        if self.error:
            raise self.error
        if len(self.calls) == 1:
            return self.first
        if len(self.calls) == 2:
            return self.second
        raise AssertionError("unbounded fallback retrieval")


def generated_answer(*, sources, language, **kwargs):
    first = sources[0]
    return {
        "answer": "ابن سینا دانشمند و فیلسوف بود.",
        "language": language,
        "verified": False,
        "model_status": "generated",
        "grounded_status": "proposed",
        "error_code": "",
        "citations": [
            {"source_id": first["source_id"],
             "evidence_digest": first["evidence_digest"],
             "evidence_quote": first["excerpt"][:45]}
        ],
    }


class PersianMultiwordRankingTests(SimpleTestCase):
    def test_four_spellings_match_without_fuzzy_semantics(self):
        cases = (
            ("ابن‌سینا که بود؟", "ابن سینا"),
            ("ابن سینا که بود؟", "ابن‌سینا"),
            ("ابنسینا که بود؟", "ابن سینا"),
            ("ابن سینا که بود؟", "ابنسینا"),
            ("ابن سينا كه بود؟", "ابن سینا"),
        )
        for question, title in cases:
            with self.subTest(question=question, title=title):
                selected, assessments = rank_evidence(
                    question, "fa", (article(title=title),),
                    source_types={"wikipedia": "encyclopedia"})
                self.assertEqual(len(selected), 1)
                self.assertGreaterEqual(assessments[0]["relevance"], 0.25)

    def test_unrelated_evidence_still_rejected(self):
        bad = article(title="ستاره‌شناسی", pageid=987,
                      excerpt="[SYNTHETIC EVIDENCE] موضوع دیگر، بدون نام فیلسوف مورد پرسش است.")
        self.assertEqual(rank_evidence(QUESTION, "fa", (bad,))[0], ())

    def test_only_persian_zwnj_produces_bounded_fallback(self):
        self.assertEqual(
            persian_fallback_search_text(QUESTION, "fa"), "ابن سینا که بود؟")
        self.assertIsNone(persian_fallback_search_text("ابن سینا که بود؟", "fa"))
        self.assertIsNone(persian_fallback_search_text(QUESTION, "en"))
        self.assertIsNone(persian_fallback_search_text("anything", "fa"))
        self.assertIsNone(persian_fallback_search_text(QUESTION * 100, "fa"))

    def test_outgoing_persian_keyword_fixture_behavior_still_preserves_zwnj(self):
        self.assertEqual(search_keywords(QUESTION, "fa"), "ابن‌سینا")
        self.assertEqual(search_keywords("ابن سینا که بود؟", "fa"), "ابن سینا")


class PersianGroundingFallbackTests(SimpleTestCase):
    def run_question(self, retriever, question=QUESTION):
        provider = Mock()
        provider.generate.side_effect = generated_answer
        result = ask_global(
            question, "fa", actor=SimpleNamespace(is_authenticated=True),
            provider=provider, retriever=retriever, enabled=True)
        return result, provider

    def test_primary_relevant_source_never_triggers_fallback(self):
        retriever = FakeRetriever(first=(article(),))
        result, provider = self.run_question(retriever)
        self.assertEqual(len(retriever.calls), 1)
        self.assertEqual(result["route"], "general_public")
        self.assertEqual(len(result["citations"]), 1)
        self.assertFalse(result["verified"])
        provider.generate.assert_called_once()

    def test_fallback_only_after_irrelevant_first_source(self):
        irrelevant = article(title="زیست‌شناسی", pageid=987,
                             excerpt="[SYNTHETIC EVIDENCE] این مقاله موضوع دیگری را توضیح می‌دهد.")
        retriever = FakeRetriever(first=(irrelevant,), second=(article(),))
        result, provider = self.run_question(retriever)
        self.assertEqual([q for q, _, _ in retriever.calls],
                         ["ابن‌سینا که بود؟", "ابن سینا که بود؟"])
        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["citations"][0]["source_id"], "S1")
        self.assertFalse(result["verified"])
        provider.generate.assert_called_once()

    def test_fallback_empty_stays_insufficient_and_never_uses_model(self):
        retriever = FakeRetriever(first=(), second=())
        result, provider = self.run_question(retriever)
        self.assertEqual(result["mode"], "insufficient_evidence")
        self.assertEqual(result["model_status"], "not_called")
        self.assertEqual(len(retriever.calls), 2)
        provider.generate.assert_not_called()

    def test_no_second_search_without_persian_compound(self):
        retriever = FakeRetriever()
        result, provider = self.run_question(retriever, "ابن سینا که بود؟")
        self.assertEqual(result["mode"], "insufficient_evidence")
        self.assertEqual(len(retriever.calls), 1)
        provider.generate.assert_not_called()

    def test_retrieval_error_fails_closed_without_retry(self):
        retriever = FakeRetriever(error=RetrievalError("synthetic upstream unavailable"))
        provider = Mock()
        try:
            ask_global(QUESTION, "fa", actor=SimpleNamespace(is_authenticated=True),
                       provider=provider, retriever=retriever, enabled=True)
        except RetrievalError:
            pass
        else:
            self.fail("RetrievalError must propagate, not invoke fallback")
        self.assertEqual(len(retriever.calls), 1)
        provider.generate.assert_not_called()

    def test_fallback_never_accepts_untrusted_source_host(self):
        from apps.ai_core.engine.citation import EvidenceRejected
        retriever = FakeRetriever(first=(), second=(article(host="untrusted.example"),))
        provider = Mock()
        with self.assertRaises(EvidenceRejected):
            ask_global(QUESTION, "fa", actor=SimpleNamespace(is_authenticated=True),
                       provider=provider, retriever=retriever, enabled=True)
        self.assertEqual(len(retriever.calls), 2)
        provider.generate.assert_not_called()

class WikipediaRetrieverIntegrationTests(SimpleTestCase):
    def test_initial_zwnj_search_then_spaced_fallback_with_real_parser(self):
        calls = []

        def offline_fetch(host, path, params, *, allowed_hosts):
            self.assertEqual(host, "fa.wikipedia.org")
            self.assertEqual(path, "/w/api.php")
            self.assertIn(host, allowed_hosts)
            calls.append(params["gsrsearch"])
            if params["gsrsearch"] == "ابن‌سینا":
                return {"query": {"pages": []}}
            self.assertEqual(params["gsrsearch"], "ابن سینا")
            return {"query": {"pages": [{
                "index": 0, "pageid": 123, "title": "ابن سینا",
                "fullurl": "https://fa.wikipedia.org/wiki/SYNTHETIC_123",
                "extract": EXCERPT,
            }]}}

        retriever = WikipediaRetriever(fetch=offline_fetch)
        provider = Mock()
        provider.generate.side_effect = generated_answer
        result = ask_global(
            QUESTION, "fa", actor=SimpleNamespace(is_authenticated=True),
            provider=provider, retriever=retriever, enabled=True)
        self.assertEqual(calls, ["ابن‌سینا", "ابن سینا"])
        self.assertEqual(result["answer"], "ابن سینا دانشمند و فیلسوف بود.")
        self.assertEqual(result["citations"][0]["url"],
                         "https://fa.wikipedia.org/wiki/SYNTHETIC_123")
        self.assertFalse(result["verified"])
        provider.generate.assert_called_once()

class OtherCompoundNameTests(SimpleTestCase):
    def test_no_hardcoded_person_name_is_needed(self):
        source = article(
            title="خواجه نصیر", pageid=765,
            excerpt="[SYNTHETIC EVIDENCE] خواجه نصیر یک شخصیت تاریخی بود؛ "
                    "این متن صرفاً داده ساختگی آزمون تطبیق نام است.")
        selected, assessments = rank_evidence(
            "خواجه‌نصیر که بود؟", "fa", (source,))
        self.assertEqual(len(selected), 1)
        self.assertGreaterEqual(assessments[0]["relevance"], 0.25)
