"""Phase A: deterministic security and multilingual contract checks."""
import json
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.gateway import Citation, InputError, ask_public, public_citations, retrieve_public
from apps.ai_core.provider import OpenAIResponsesProvider, ProviderUnavailable

class GatewayTests(TestCase):
    def setUp(self):
        self.source = (Citation("S1", "library:1", "Source", "public excerpt", "/en/library/1/"),)
        self.retrieve = lambda q, lang: self.source

    def test_public_sources_only_and_relative_urls(self):
        items = public_citations({"results": [
            {"type":"document", "key":"document:1", "title":"PRIVATE", "description":"SECRET"},
            {"type":"libraryitem", "key":"library:1", "title":"Public", "url":"https://unsafe.test/"},
            {"type":"book", "key":"library:2", "title":"کتاب", "url":"/library/book/"},
            {"type":"article", "key":"article:3", "title":"Evidence", "url":"//unsafe.test"},
            {"type":"product", "key":"product:4", "title":"Over limit"},
        ]})
        self.assertEqual([s.key for s in items], ["library:1", "library:2", "article:3"])
        self.assertEqual([s.url for s in items], [None, "/library/book/", None])
        self.assertNotIn("SECRET", str(items))

    def test_multilingual_sources_fallback(self):
        for lang in ("fa", "de", "en"):
            with self.subTest(lang=lang):
                reply = ask_public(" public \n query ", lang, retrieval=self.retrieve)
                self.assertEqual(reply["mode"], "sources_only")
                self.assertFalse(reply["verified"])
                self.assertEqual(reply["citations"][0]["id"], "S1")

    def test_empty_sources_never_call_model(self):
        provider = Mock()
        out = ask_public("Question", "en", allow_model=True, egress_enabled=True,
                         provider=provider, retrieval=lambda q, lang: ())
        self.assertEqual(out["mode"], "no_sources")
        provider.generate.assert_not_called()

    def test_requires_egress_and_per_request_consent(self):
        provider = Mock()
        for consent, enabled in ((True, False), (False, True), (False, False)):
            reply = ask_public("Question", "en", allow_model=consent,
                               egress_enabled=enabled, provider=provider, retrieval=self.retrieve)
            self.assertEqual(reply["mode"], "sources_only")
        provider.generate.assert_not_called()

    def test_model_draft_citation_validation(self):
        provider = Mock()
        provider.generate.return_value = "Draft [S1]"
        valid = ask_public("question", "de", allow_model=True, egress_enabled=True,
                           provider=provider, retrieval=self.retrieve)
        self.assertEqual(valid["mode"], "model_draft")
        self.assertFalse(valid["verified"])
        provider.generate.return_value = "Fabrication [S999]"
        bad = ask_public("question", "de", allow_model=True, egress_enabled=True,
                         provider=provider, retrieval=self.retrieve)
        self.assertEqual(bad["mode"], "sources_only")

    def test_provider_failure_does_not_leak_keys(self):
        provider = Mock()
        provider.generate.side_effect = RuntimeError("SECRET-TOKEN")
        out = ask_public("question", "en", allow_model=True, egress_enabled=True,
                         provider=provider, retrieval=self.retrieve)
        self.assertNotIn("SECRET-TOKEN", repr(out))
        self.assertEqual(out["mode"], "sources_only")

    def test_invalid_question_language_rejected(self):
        for query, lang in (("", "en"), ("x"*201, "en"), ("hi\x00secret", "en"),
                            ("test", "ru"), (None, "fa")):
            with self.subTest(query=str(query)[:10], lang=lang):
                with self.assertRaises(InputError):
                    ask_public(query, lang, retrieval=self.retrieve)

    @patch("apps.search.services.UnifiedSearch")
    def test_explicit_public_adapter_selection(self, Search):
        Search.return_value.search.return_value = {"results": [
            {"type":"book", "key":"library:1", "title":"Book"}
        ]}
        out = retrieve_public("search", "fa")
        self.assertEqual(len(out), 1)
        self.assertEqual([a.type_name for a in Search.call_args.kwargs["adapters"]],
                         ["article", "product", "libraryitem", "audio"])
        self.assertEqual(Search.return_value.search.call_args.kwargs["page_size"], 3)

    def test_provider_transport_no_tools_or_storage(self):
        transport = Mock(return_value={"status":"completed", "output":[{"type":"message",
            "content":[{"type":"output_text", "text":"Answer [S1]"}]}]})
        provider = OpenAIResponsesProvider(api_key="synthetic", model="test-model", transport=transport)
        self.assertEqual(provider.generate(question="What?", language="en",
                                           sources=self.source), "Answer [S1]")
        sent = transport.call_args.args[0]
        self.assertFalse(sent["store"])
        self.assertEqual(sent["tools"], [])
        self.assertNotIn("synthetic", repr(sent))
        with self.assertRaises(ProviderUnavailable):
            OpenAIResponsesProvider(api_key="", model="")

class GlobalAIApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="ai-core-synthetic", password="synthetic-local-password")

    def setUp(self):
        self.url = reverse("ai_core:ask")
        self.client.force_login(self.user)

    def post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload), content_type="application/json")

    @override_settings(VORNEQ_AI_CORE_ENABLED=False)
    def test_default_feature_off(self):
        self.assertEqual(self.post({"question":"test"}).status_code, 404)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="production")
    def test_production_fails_closed(self):
        self.assertEqual(self.post({"question":"test"}).status_code, 404)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="development")
    def test_anonymous_denied(self):
        self.client.logout()
        self.assertEqual(self.post({"question":"test"}).status_code, 401)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="development",
                       VORNEQ_AI_EXTERNAL_EGRESS_ENABLED=False)
    @patch("apps.ai_core.views.ask_public")
    def test_no_egress_and_no_cache(self, service):
        service.return_value = {"mode":"no_sources","answer":"None","citations":[],
                                "language":"en","verified":False}
        response = self.post({"question":"test", "language":"en", "allow_model":True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertFalse(service.call_args.kwargs["egress_enabled"])
        self.assertIsNone(service.call_args.kwargs["provider"])

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="development")
    def test_bad_input_rejected(self):
        for body in ({"question":None}, {"question":""}, {"question":"x"*201},
                     {"question":"test","allow_model":"true"},
                     {"question":"test","extra":"private"},
                     {"question":"test","language":"ru"}):
            with self.subTest(body=str(body)[:60]):
                self.assertEqual(self.post(body).status_code, 400)
        self.assertEqual(self.client.post(self.url, data="x"*2050,
                         content_type="application/json").status_code, 413)
        self.assertEqual(self.client.post(self.url, data="bad",
                         content_type="text/plain").status_code, 415)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="development")
    def test_csrf_is_not_exempted(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.url, data=json.dumps({"question":"hello"}),
                               content_type="application/json")
        self.assertEqual(response.status_code, 403)
