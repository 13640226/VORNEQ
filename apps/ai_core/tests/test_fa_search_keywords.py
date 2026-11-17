"""Persian Wikipedia search query: keywords instead of the full question.

The fixture holds the exact queries of variant C that were measured against
fa.wikipedia on 2026-11-17 (see docs/ai/FA_RETRIEVAL_QUERY_V1.md). The code
must produce byte-identical queries, so the measured improvement applies.
No network access.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from django.test import SimpleTestCase

from apps.ai_core.engine.evidence_ranking import rank_evidence, search_keywords, terms
from apps.ai_core.web_retrieval import RetrievalError, WikipediaRetriever

FIXTURE = Path(__file__).parent / "fixtures" / "fa_search_queries_measured_2026-11-17.json"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


class SearchKeywordsTests(SimpleTestCase):
    def test_reproduces_all_40_measured_queries(self):
        pairs = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(pairs), 40)
        for question, expected in pairs:
            with self.subTest(question=question):
                self.assertEqual(search_keywords(question, "fa"), expected)

    def test_zwnj_kept_and_arabic_letters_and_digits_normalized(self):
        self.assertEqual(search_keywords("ابن‌سینا که بود؟", "fa"), "ابن‌سینا")
        self.assertEqual(search_keywords("كتاب علي چيست؟", "fa"), "کتاب علی")
        self.assertEqual(search_keywords("جنگ ۱۹۱۴ چه بود؟", "fa"), "جنگ 1914")

    def test_only_stopwords_falls_back_to_question(self):
        self.assertEqual(search_keywords("  چه   چیست؟ ", "fa"), "چه چیست؟")

    def test_other_languages_are_unchanged(self):
        self.assertEqual(search_keywords("how many  galaxies?", "en"), "how many galaxies?")
        self.assertEqual(search_keywords("Wie entstehen Sterne?", "de"), "Wie entstehen Sterne?")

    def test_relevance_terms_are_not_changed_by_the_search_list(self):
        # Scoring keeps its own stop list; only the outgoing search query changes.
        self.assertIn("کار", terms("واکسن چگونه کار می‌کند؟", "fa"))


class RetrieverQueryTests(SimpleTestCase):
    def retriever(self, calls):
        def fetch(host, path, params, *, allowed_hosts):
            calls.append((host, dict(params)))
            return {"query": {"pages": []}}
        return WikipediaRetriever(fetch=fetch, clock=lambda: NOW)

    def test_persian_question_is_sent_as_keywords(self):
        calls = []
        self.retriever(calls).search("فتوسنتز چیست؟", "fa")
        self.assertEqual(calls[0][0], "fa.wikipedia.org")
        self.assertEqual(calls[0][1]["gsrsearch"], "فتوسنتز")

    def test_english_and_german_queries_unchanged(self):
        for language, question in (("en", "how many galaxies?"), ("de", "Wie entstehen Sterne?")):
            calls = []
            self.retriever(calls).search(question, language)
            self.assertEqual(calls[0][1]["gsrsearch"], question)

    def test_personal_data_still_blocked_before_any_request(self):
        calls = []
        with self.assertRaises(RetrievalError):
            self.retriever(calls).search("ایمیل من test@example.com چیست؟", "fa")
        self.assertEqual(calls, [])

    def test_ranking_still_accepts_keyword_retrieved_persian_article(self):
        from apps.ai_core.web_retrieval import WebEvidence

        item = WebEvidence("web:wikipedia:fa:1", "فتوسنتز",
                           "https://fa.wikipedia.org/wiki/%D9%81%D8%AA%D9%88%D8%B3%D9%86%D8%AA%D8%B2",
                           "Wikipedia (fa)", "[SYNTHETIC] فتوسنتز فرایندی است که گیاهان با انرژی نور "
                           "کربن‌دی‌اکسید و آب را به قند تبدیل می‌کنند.", NOW.isoformat())
        selected, assessments = rank_evidence("فتوسنتز چیست؟", "fa", [item])
        self.assertEqual(len(selected), 1)
        self.assertGreaterEqual(assessments[0]["relevance"], 0.25)
