"""Global AI V2: multi-source registry, ranking, numeric-claim guard, mixed language.

SYNTHETIC evidence and mocked providers only. Real sockets/DNS are blocked by
NoNetworkMixin and the OpenAI client cannot be constructed.
"""
import json
import socket
import ssl
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.engine.evidence_ranking import (SCORE_SEMANTICS, numeric_tokens, rank_evidence,
                                                  unsupported_numbers)
from apps.ai_core.global_router import GENERAL_PUBLIC, OFFICIAL_VORNEQ, UNSUPPORTED, route_question
from apps.ai_core.retrieval_registry import (MultiSourceRetriever, configured_provider_names,
                                             default_retriever)
from apps.ai_core.tests.test_ai_staging_trial import STAGING_SETTINGS, TEST_ENV
from apps.ai_core.tests.test_global_ai_api import DEV, NoNetworkMixin
from apps.ai_core.tests.test_global_ai_router_retrieval import fake_connection, resolver
from apps.ai_core.web_retrieval import (RetrievalError, RetrievalTimeout, WebEvidence,
                                        WikipediaRetriever, clean_text, safe_get_json)

T = "2026-11-14T12:00:00+00:00"


def ev(provider, host, pid, title, excerpt, lang="en"):
    return WebEvidence(f"web:{provider}:{lang}:{pid}", title, f"https://{host}/wiki/SYNTHETIC_{pid}",
                       f"{provider} ({lang})", excerpt, T)


class FakeProvider:
    def __init__(self, name, hosts, items=(), error=None, source_type="unknown"):
        self.name, self.allowed_hosts, self.items, self.error = name, frozenset(hosts), items, error
        self.source_type, self.calls = source_type, 0

    def search(self, query, language, limit=3):
        self.calls += 1
        if self.error:
            raise self.error
        return self.items


A_TEXT = "[SYNTHETIC] Stars form when dense molecular clouds collapse under gravity and heat up."
B_TEXT = "[SYNTHETIC] Star formation happens inside molecular clouds over millions of years."


class MixedLanguageRoutingTests(SimpleTestCase):
    def test_mixed_and_edge_cases(self):
        cases = [
            ("Quantum computing چیست؟", GENERAL_PUBLIC, "fa"),
            ("CPU و GPU چه فرقی دارند؟", GENERAL_PUBLIC, "fa"),
            ("الگوریتم Dijkstra", GENERAL_PUBLIC, "fa"),
            ("What does سلام mean?", GENERAL_PUBLIC, "en"),
            ("Was ist die Schrödinger-Gleichung?", GENERAL_PUBLIC, "de"),
            ("What is the Schrödinger equation?", GENERAL_PUBLIC, "en"),
            ("Wie funktioniert Machine Learning?", GENERAL_PUBLIC, "de"),
            ("Was ist ein API Gateway?", GENERAL_PUBLIC, "de"),
            ("Größe der Milchstraße", GENERAL_PUBLIC, "de"),
            ("VORNEQ چیست؟", OFFICIAL_VORNEQ, "fa"),
            ("اطلاعات من را نشان بده", UNSUPPORTED, "fa"),
            ("Zeig mein Profil", UNSUPPORTED, "de"),
            ("Show my email history", UNSUPPORTED, "en"),
        ]
        for question, kind, language in cases:
            route = route_question(question, "en")
            self.assertEqual((route.kind, route.language), (kind, language), question)

    def test_umlauts_eszett_and_zwnj_preserved_in_source_text(self):
        self.assertEqual(clean_text("Die Größe der Milchstraße", 100), "Die Größe der Milchstraße")
        self.assertEqual(clean_text("کهکشان\u200cها", 100), "کهکشان\u200cها")


class RegistryTests(SimpleTestCase):
    def test_default_registry_is_wikipedia_only(self):
        self.assertEqual(configured_provider_names(), ("wikipedia",))
        retriever = default_retriever()
        self.assertEqual([r.name for r in retriever.retrievers], ["wikipedia"])
        self.assertEqual(retriever.allowed_hosts, WikipediaRetriever.allowed_hosts)

    def test_unknown_duplicate_or_too_many_providers_fail_closed(self):
        for value in (("wikipedia", "unknown"), ("wikipedia", "wikipedia"), (), "wikipedia",
                      ("wikipedia",) * 4):
            with override_settings(VORNEQ_GLOBAL_AI_PROVIDERS=value):
                with self.assertRaises(RetrievalError, msg=value):
                    default_retriever()

    def test_multi_source_success_and_cross_source_dedup(self):
        a = FakeProvider("alpha", {"alpha.example"}, (
            ev("alpha", "alpha.example", 1, "[SYNTHETIC] Star formation", A_TEXT),))
        b = FakeProvider("beta", {"beta.example"}, (
            ev("beta", "beta.example", 2, "[SYNTHETIC] Star formation", A_TEXT),
            ev("beta", "beta.example", 3, "[SYNTHETIC] Molecular cloud", B_TEXT)))
        multi = MultiSourceRetriever((a, b))
        items = multi.search("How do stars form?", "en")
        self.assertEqual(len(items), 3)
        self.assertEqual(multi.allowed_hosts, {"alpha.example", "beta.example"})
        self.assertEqual(multi.last_status, (("alpha", "ok"), ("beta", "ok")))
        ranked, _ = rank_evidence("How do stars form?", "en", items)
        self.assertEqual([e.source_key for e in ranked], ["web:alpha:en:1", "web:beta:en:3"])

    def test_empty_results(self):
        multi = MultiSourceRetriever((FakeProvider("alpha", {"a.example"}),))
        self.assertEqual(multi.search("q", "en"), ())
        self.assertEqual(multi.last_status, (("alpha", "empty"),))

    def test_partial_failure_is_recorded_but_total_failure_raises(self):
        good = FakeProvider("alpha", {"a.example"}, (ev("alpha", "a.example", 1, "t", A_TEXT),))
        slow = FakeProvider("beta", {"b.example"}, error=RetrievalTimeout("t"))
        multi = MultiSourceRetriever((good, slow))
        self.assertEqual(len(multi.search("stars", "en")), 1)
        self.assertEqual(multi.last_status, (("alpha", "ok"), ("beta", "timeout")))
        with self.assertRaises(RetrievalTimeout):
            MultiSourceRetriever((slow, FakeProvider("gamma", {"c.example"}, error=RetrievalError("x")))).search("s", "en")

    def test_unexpected_or_malformed_provider_output_fails_closed(self):
        bad_cases = [
            FakeProvider("alpha", {"a.example"}, error=KeyError("bug")),
            FakeProvider("alpha", {"a.example"}, items=[ev("alpha", "a.example", 1, "t", A_TEXT)]),
            FakeProvider("alpha", {"a.example"}, items=({"source_key": "web:alpha:en:1"},)),
            FakeProvider("alpha", {"a.example"}, items=(ev("alpha", "evil.example", 1, "t", A_TEXT),)),
            FakeProvider("alpha", {"a.example"}, items=tuple(ev("alpha", "a.example", i, "t", A_TEXT) for i in range(4))),
        ]
        for provider in bad_cases:
            good = FakeProvider("beta", {"b.example"}, (ev("beta", "b.example", 9, "t", A_TEXT),))
            with self.assertRaises(RetrievalError):
                MultiSourceRetriever((good, provider)).search("stars", "en")

    def test_tls_failure_is_controlled(self):
        for error in (ssl.SSLCertVerificationError("bad cert"), ssl.SSLError("handshake")):
            with self.assertRaises(RetrievalError):
                safe_get_json("en.wikipedia.org", "/w/api.php", {"q": "x"},
                              allowed_hosts=WikipediaRetriever.allowed_hosts,
                              resolver=resolver("198.35.26.96"),
                              connection_class=fake_connection(error=error))


class RankingAndNumericTests(SimpleTestCase):
    def test_irrelevant_evidence_is_dropped(self):
        unrelated = ev("wikipedia", "en.wikipedia.org", 5, "[SYNTHETIC] Football club",
                       "[SYNTHETIC] A football club founded in a small town with a long history.")
        self.assertEqual(rank_evidence("How do stars form?", "en", (unrelated,))[0], ())

    def test_persian_plural_and_digits_match(self):
        item = ev("wikipedia", "fa.wikipedia.org", 6, "کهکشان",
                  "[SYNTHETIC] جهان قابل مشاهده دست\u200cکم ۲۰۰ میلیارد کهکشان\u200cها دارد و این برآورد است.", "fa")
        ranked, info = rank_evidence("جهان چند کهکشان دارد؟", "fa", (item,))
        self.assertEqual(len(ranked), 1)
        self.assertEqual(info[0]["relevance"], 1.0)
        self.assertEqual(numeric_tokens("۲۰۰ میلیارد"), {"200"})

    def test_ranking_is_deterministic_and_bounded(self):
        items = tuple(ev("wikipedia", "en.wikipedia.org", i, f"[SYNTHETIC] Stars {i}",
                         A_TEXT + " x" * i) for i in range(1, 7))
        first = rank_evidence("How do stars form?", "en", items)
        self.assertEqual(first, rank_evidence("How do stars form?", "en", items))
        self.assertEqual(len(first[0]), 3)
        self.assertTrue(all(0 <= a["score"] <= 1 for a in first[1]))
        self.assertEqual(SCORE_SEMANTICS, "retrieval_relevance_not_truth")

    def test_unsupported_numbers(self):
        self.assertEqual(unsupported_numbers("about 300 billion", ["estimates 200 billion"]), {"300"})
        self.assertEqual(unsupported_numbers("۲۰۰ میلیارد", ["200 billion"]), set())
        self.assertEqual(unsupported_numbers("since 1969", [], question="What happened in 1969?"), set())
        self.assertEqual(unsupported_numbers("100,000 stars", ["100000 stars"]), set())


def output(sources, language, answer, ids=("S1",)):
    return {"answer": answer, "language": language, "verified": False, "model_status": "generated",
            "grounded_status": "proposed", "error_code": "",
            "citations": [{"source_id": i, "evidence_digest": next(s for s in sources if s["source_id"] == i)["evidence_digest"],
                           "evidence_quote": next(s for s in sources if s["source_id"] == i)["excerpt"][:50]}
                          for i in ids]}


@override_settings(**DEV)
class GroundingV2ApiTests(NoNetworkMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="v2", email="v2@example.invalid",
                                                        password="synthetic-only")

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def ask(self, provider_items, generate, question="How many galaxies are in the universe?"):
        retriever = MultiSourceRetriever((FakeProvider("wikipedia", WikipediaRetriever.allowed_hosts,
                                                       provider_items, source_type="encyclopedia"),))
        with patch("apps.ai_core.views_global.default_retriever", return_value=retriever), \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate", autospec=True,
                      side_effect=generate) as gen:
            r = self.client.post(reverse("ai_core:ask-global"),
                                 data=json.dumps({"question": question, "language": "en"}),
                                 content_type="application/json")
        return r, gen

    GAL_A = ev("wikipedia", "en.wikipedia.org", 21, "[SYNTHETIC] Galaxy count",
               "[SYNTHETIC] The observable universe is estimated to contain about 200 billion galaxies.")
    GAL_B = ev("wikipedia", "en.wikipedia.org", 22, "[SYNTHETIC] Galaxy survey",
               "[SYNTHETIC] Another estimate suggests the universe has up to 2 trillion galaxies.")

    def test_valid_answer_with_assessment_metadata(self):
        r, gen = self.ask((self.GAL_A,), lambda self_, **kw: output(
            kw["sources"], "en", "The source estimates about 200 billion galaxies."))
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertIs(data["verified"], False)
        assessment = data["evidence_assessment"]
        self.assertEqual(assessment["score_semantics"], "retrieval_relevance_not_truth")
        self.assertIs(assessment["independent_verification"], False)
        self.assertEqual(assessment["providers"], [{"name": "wikipedia", "status": "ok"}])
        self.assertEqual(assessment["cited"][0]["source_key"], "web:wikipedia:en:21")

    def test_fabricated_number_is_rejected(self):
        r, _ = self.ask((self.GAL_A,), lambda self_, **kw: output(
            kw["sources"], "en", "The source says there are exactly 500 billion galaxies."))
        self.assertEqual((r.status_code, r.json()), (422, {"error": "INSUFFICIENT_EVIDENCE"}))

    def test_conflicting_evidence_forwarded_and_both_sides_citable(self):
        seen = {}

        def generate(self_, **kw):
            seen["sources"] = kw["sources"]
            return output(kw["sources"], "en",
                          "Estimates differ: about 200 billion, or up to 2 trillion galaxies.", ids=("S1", "S2"))
        r, _ = self.ask((self.GAL_A, self.GAL_B), generate)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(seen["sources"]), 2)
        self.assertEqual(len(r.json()["citations"]), 2)
        self.assertIs(r.json()["verified"], False)

    def test_irrelevant_results_give_insufficient_evidence_without_model(self):
        unrelated = ev("wikipedia", "en.wikipedia.org", 30, "[SYNTHETIC] Football",
                       "[SYNTHETIC] A football club founded in a small town with a long history.")
        r, gen = self.ask((unrelated,), None)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["mode"], "insufficient_evidence")
        gen.assert_not_called()

    def test_unknown_id_and_modified_digest_still_rejected(self):
        for mutate in (lambda o: o["citations"][0].update(source_id="S7"),
                       lambda o: o["citations"][0].update(evidence_digest="f" * 64)):
            def generate(self_, mutate=mutate, **kw):
                o = output(kw["sources"], "en", "The source estimates about 200 billion galaxies.")
                mutate(o)
                return o
            cache.clear()
            r, _ = self.ask((self.GAL_A,), generate)
            self.assertEqual(r.status_code, 422)

    def test_invalid_provider_configuration_fails_closed(self):
        with override_settings(VORNEQ_GLOBAL_AI_PROVIDERS=("not-registered",)), \
                patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate") as gen:
            r = self.client.post(reverse("ai_core:ask-global"),
                                 data=json.dumps({"question": "What is a star?", "language": "en"}),
                                 content_type="application/json")
        self.assertEqual((r.status_code, r.json()), (503, {"error": "search_unavailable"}))
        gen.assert_not_called()


@override_settings(**{**STAGING_SETTINGS, "VORNEQ_GLOBAL_AI_ENABLED": True})
class UnlimitedModeApiTests(NoNetworkMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="v2-owner", email="v2o@example.invalid", password="synthetic-only")

    def setUp(self):
        super().setUp()
        p = patch.dict("os.environ", TEST_ENV)
        p.start()
        self.addCleanup(p.stop)
        ids = override_settings(VORNEQ_AI_STAGING_ALLOWED_USER_IDS=str(self.owner.pk),
                                VORNEQ_AI_STAGING_UNMETERED=True, VORNEQ_GLOBAL_AI_QUOTA={"per_minute": 1})
        ids.enable()
        self.addCleanup(ids.disable)
        self.client.force_login(self.owner)

    def codes(self, n):
        retriever = MultiSourceRetriever((FakeProvider("wikipedia", WikipediaRetriever.allowed_hosts),))
        with patch("apps.ai_core.views_global.default_retriever", return_value=retriever):
            return [self.client.post(reverse("ai_core:ask-global"),
                                     data=json.dumps({"question": "What is a star?", "language": "en"}),
                                     content_type="application/json").status_code for _ in range(n)]

    def test_default_staging_enforces_quota(self):
        self.assertEqual(self.codes(3), [200, 429, 429])

    def test_explicit_staging_unlimited_flag_removes_only_global_quota(self):
        with override_settings(VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=True):
            self.assertEqual(self.codes(4), [200, 200, 200, 200])
        with override_settings(VORNEQ_GLOBAL_AI_UNLIMITED_STAGING=True), \
                patch.dict("os.environ", {"RENDER_GIT_COMMIT": "f" * 40}):
            self.assertEqual(self.codes(1), [404])  # trial identity still required
