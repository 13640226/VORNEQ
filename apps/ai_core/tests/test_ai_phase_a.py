"""Phase A offline-only contract and negative security tests."""
import importlib.util
import json
import socket
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.ai_core.gateway import Citation, InputError, ask_public, public_citations, retrieve_public


class GatewayTests(TestCase):
    def setUp(self):
        self.source = (Citation("S1", "library:1", "Public", "public excerpt", "/en/library/1/"),)
        self.retrieve = lambda q, lang: self.source

    def test_public_only_and_safe_relative_urls(self):
        items = public_citations({"results": [
            {"type": "document", "key": "document:1", "title": "PRIVATE", "description": "SECRET"},
            {"type": "libraryitem", "key": "library:1", "title": "Public", "url": "https://unsafe.test/"},
            {"type": "book", "key": "library:2", "title": "Book", "url": "/library/book/"},
            {"type": "article", "key": "article:3", "title": "Evidence", "url": "//unsafe.test"},
            {"type": "product", "key": "product:4", "title": "Fourth"},
        ]})
        self.assertEqual([s.key for s in items], ["library:1", "library:2", "article:3"])
        self.assertEqual([s.url for s in items], [None, "/library/book/", None])
        self.assertNotIn("SECRET", str(items))

    def test_bounded_citation_content_and_duplicates(self):
        items = public_citations({"results": [
            {"type": "article", "key": "article:1", "title": "T" * 500,
             "description": "D" * 1000, "url": "/safe"},
            {"type": "article", "key": "article:1", "title": "DUPLICATE"},
            {"type": "product", "key": "product:2", "title": "Second", "url": "/unsafe\\path"},
        ]})
        self.assertEqual(len(items), 2)
        self.assertEqual(len(items[0].title), 140)
        self.assertEqual(len(items[0].excerpt), 300)
        self.assertIsNone(items[1].url)

    def test_malformed_payload_fail_closed(self):
        for payload in (None, [], {}, {"results": "bad"}):
            with self.subTest(payload=payload):
                self.assertEqual(public_citations(payload), ())

    def test_sources_only_multilingual(self):
        for lang in ("fa", "en", "de"):
            with self.subTest(lang=lang):
                result = ask_public(" public \n query ", lang, retrieval=self.retrieve)
                self.assertEqual(result["mode"], "sources_only")
                self.assertEqual(result["model_status"], "offline_only")
                self.assertFalse(result["verified"])
                self.assertEqual(result["citations"][0]["id"], "S1")

    def test_no_sources_no_fabricated_answer(self):
        result = ask_public("question", "en", retrieval=lambda q, lang: ())
        self.assertEqual(result["mode"], "no_sources")
        self.assertEqual(result["citations"], [])
        self.assertFalse(result["verified"])

    def test_invalid_question_and_language_rejected(self):
        for question, lang in (("", "en"), ("x" * 201, "en"), ("hi\x00token", "fa"),
                               ("test", "ru"), (None, "fa")):
            with self.subTest(lang=lang, question=str(question)[:15]):
                with self.assertRaises(InputError):
                    ask_public(question, lang, retrieval=self.retrieve)

    def test_untrusted_retrieval_objects_rejected(self):
        for sources in (("secret",), (1,), self.source * 4):
            with self.subTest(size=len(sources)):
                with self.assertRaises(InputError):
                    ask_public("question", "en", retrieval=lambda q, lang: sources)

    @patch("apps.search.services.UnifiedSearch")
    def test_public_adapter_allowlist(self, search):
        search.return_value.search.return_value = {"results": [
            {"type": "book", "key": "library:1", "title": "Public Book"}
        ]}
        result = retrieve_public("search", "fa")
        self.assertEqual(len(result), 1)
        self.assertEqual([a.type_name for a in search.call_args.kwargs["adapters"]],
                         ["article", "product", "libraryitem", "audio"])
        self.assertEqual(search.return_value.search.call_args.kwargs["page_size"], 3)

    @patch.object(socket.socket, "connect", side_effect=AssertionError("network attempted"))
    @patch.object(socket, "create_connection", side_effect=AssertionError("egress attempted"))
    def test_offline_responds_without_network(self, _create, _connect):
        result = ask_public("test", "en", retrieval=self.retrieve)
        self.assertEqual(result["mode"], "sources_only")
        _create.assert_not_called()
        _connect.assert_not_called()

    def test_live_provider_module_not_in_package(self):
        self.assertIsNone(importlib.util.find_spec("apps.ai_core.provider"))
        with self.assertRaises(TypeError):
            ask_public("test", "en", provider=object(), retrieval=self.retrieve)


class GlobalAIApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="ai-core-offline-synthetic", password="synthetic-local-password")

    def setUp(self):
        self.url = reverse("ai_core:ask")
        self.client.force_login(self.user)

    def post(self, payload):
        return self.client.post(self.url, data=json.dumps(payload), content_type="application/json")

    @override_settings(VORNEQ_AI_CORE_ENABLED=False)
    def test_feature_off(self):
        self.assertEqual(self.post({"question": "test"}).status_code, 404)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="production")
    def test_production_fails_closed(self):
        self.assertEqual(self.post({"question": "test"}).status_code, 404)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="staging")
    def test_staging_fails_closed(self):
        self.assertEqual(self.post({"question": "test"}).status_code, 404)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="development")
    def test_anonymous_denied(self):
        self.client.logout()
        self.assertEqual(self.post({"question": "test"}).status_code, 401)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="development")
    @patch("apps.ai_core.views.ask_public")
    def test_valid_offline_response_not_cached(self, service):
        service.return_value = {"mode": "no_sources", "answer": "None", "citations": [],
                                "language": "en", "verified": False,
                                "model_status": "offline_only"}
        response = self.post({"question": "test", "language": "en"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
        self.assertEqual(service.call_args.args, ("test", "en"))
        self.assertEqual(service.call_args.kwargs, {})

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="development",
                       VORNEQ_AI_EXTERNAL_EGRESS_ENABLED=True,
                       VORNEQ_AI_API_KEY="synthetic-do-not-use")
    @patch("apps.ai_core.views.ask_public")
    def test_legacy_egress_flags_do_not_enable_model(self, service):
        service.return_value = {"mode": "no_sources", "answer": "None", "citations": [],
                                "language": "en", "verified": False,
                                "model_status": "offline_only"}
        self.assertEqual(self.post({"question": "test"}).status_code, 200)
        self.assertEqual(service.call_args.kwargs, {})
        self.assertEqual(self.post({"question": "test", "allow_model": True}).status_code, 400)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="development")
    def test_bad_inputs_rejected(self):
        invalid = ({"question": None}, {"question": ""}, {"question": "x" * 201},
                   {"question": "test", "allow_model": True},
                   {"question": "test", "allow_model": False},
                   {"question": "test", "tools": []},
                   {"question": "test", "extra": "private"},
                   {"question": "test", "language": "ru"})
        for body in invalid:
            with self.subTest(body=str(body)[:70]):
                self.assertEqual(self.post(body).status_code, 400)
        self.assertEqual(self.client.post(self.url, data="x" * 2050,
                         content_type="application/json").status_code, 413)
        self.assertEqual(self.client.post(self.url, data="bad",
                         content_type="text/plain").status_code, 415)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    @override_settings(VORNEQ_AI_CORE_ENABLED=True, VORNEQ_ENV="development")
    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(self.url, data=json.dumps({"question": "hello"}),
                               content_type="application/json")
        self.assertEqual(response.status_code, 403)
