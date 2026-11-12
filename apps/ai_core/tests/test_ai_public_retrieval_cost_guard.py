"""Real public adapter SQL and development request-cost guard regression tests.

All records are synthetic and created in Django's disposable test database.
No production database, external model calls, or tenant records are accessed.
"""
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from apps.ai_core.engine.budget import BudgetExceeded, reserve_request
from apps.ai_core.engine.grounded import ask_grounded
from apps.ai_core.gateway import retrieve_public
from apps.content.models import Article, Category
from apps.media.models import MediaAsset
from library.models import LibraryItem, AudioItem


MARKER = "vqsafepubq7"


class PublicSearchViaRealAdaptersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="public-evidence-local-actor",
            password="synthetic-only-no-use",
        )
        category = Category.objects.create(name="Synthetic Safety", slug="synthetic-safety")
        cls.public_article = Article.objects.create(
            title=MARKER + " article public",
            summary="The " + MARKER + " published public article has blue evidence.",
            content="Synthetic publication test body.",
            category=category,
            is_published=True,
        )
        cls.held_article = Article.objects.create(
            title=MARKER + " article hidden",
            summary="The " + MARKER + " hidden article must never leave the database.",
            content="Private synthetic marker.",
            category=category,
            is_published=False,
        )
        cls.public_library = LibraryItem.objects.create(
            title=MARKER + " library public",
            slug="local-safe-public-library",
            short_description=MARKER + " public library reference in this test.",
            content="Non-secret synthetic library fixture.",
            author="Test researcher",
            item_type="article",
            category="Testing",
            is_published=True,
        )
        cls.hidden_library = LibraryItem.objects.create(
            title=MARKER + " library hidden",
            slug="local-safe-hidden-library",
            short_description=MARKER + " private synthetic library item.",
            content="Hidden fixture data.",
            author="Test researcher",
            item_type="article",
            category="Testing",
            is_published=False,
        )
        cls.public_audio = AudioItem.objects.create(
            title=MARKER + " audio public",
            description=MARKER + " public synthetic audio reference.",
            audio_file="audio/synthetic-public.mp3",
            is_published=True,
        )
        cls.held_media = MediaAsset.objects.create(
            media_type=MediaAsset.MediaType.IMAGE,
            title=MARKER + " held media",
            alt_text=MARKER + " held image content",
            file="media_assets/held-only.jpg",
            mime_type="image/jpeg",
            byte_size=10,
            width=10,
            height=10,
            is_active=True,
        )

    def test_real_unified_search_adapters_retrieve_only_published_public(self):
        found = retrieve_public(MARKER, "en")
        self.assertEqual(len(found), 3)
        keys = {x.key for x in found}
        self.assertEqual(keys, {
            "article:" + str(self.public_article.pk),
            "library:" + str(self.public_library.pk),
            "audio:" + str(self.public_audio.pk),
        })
        self.assertNotIn("article:" + str(self.held_article.pk), keys)
        self.assertNotIn("library:" + str(self.hidden_library.pk), keys)
        self.assertTrue(all(x.excerpt for x in found))
        self.assertTrue(all(x.url is None or x.url.startswith("/") for x in found))
        self.assertTrue(all(not key.startswith("mediaasset:") for key in keys))

    def test_real_adapter_sql_and_grounded_citations_without_llm_egress(self):
        actor = SimpleNamespace(is_authenticated=True)
        observed = []

        class SafeOfflineProvider:
            def generate(self, *, question, language, sources):
                observed.append((question, language, sources))
                evidence = sources[0]
                return {
                    "answer": "The source discusses synthetic public evidence.",
                    "language": language,
                    "citations": [{
                        "source_id": evidence["source_id"],
                        "evidence_digest": evidence["evidence_digest"],
                        "evidence_quote": evidence["excerpt"][:45],
                    }],
                    "model_status": "generated",
                    "grounded_status": "proposed",
                    "verified": False,
                    "error_code": "",
                }

        result = ask_grounded(
            MARKER, "en", actor=actor, provider=SafeOfflineProvider(),
            enabled=True,
        )
        self.assertEqual(result["mode"], "grounded_draft")
        self.assertIs(result["verified"], False)
        self.assertEqual(result["model_status"], "generated")
        self.assertEqual(len(observed), 1)
        self.assertEqual(len(observed[0][2]), 3)
        self.assertEqual(len(result["citations"]), 1)
        self.assertIn(result["citations"][0]["source_key"],
                      {"article:" + str(self.public_article.pk),
                       "library:" + str(self.public_library.pk),
                       "audio:" + str(self.public_audio.pk)})

    @override_settings(VORNEQ_ENV="development", VORNEQ_AI_PHASE_B_ENABLED=True)
    def test_real_retrieval_exercised_by_actual_authenticated_http_endpoint(self):
        self.client.force_login(self.user)
        class OfflineProvider:
            def __init__(self, **kwargs):
                pass

            def generate(self, *, question, language, sources):
                src = sources[0]
                return {
                    "answer": "Evidence was obtained through actual public SQL adapters.",
                    "language": language,
                    "citations": [{
                        "source_id": src["source_id"],
                        "evidence_digest": src["evidence_digest"],
                        "evidence_quote": src["excerpt"][:45],
                    }],
                    "model_status": "generated",
                    "grounded_status": "proposed",
                    "verified": False,
                    "error_code": "",
                }

        with patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider", OfflineProvider):
            response = self.client.post(
                reverse("ai_core:ask-grounded"),
                data=json.dumps({"question": MARKER, "language": "en"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200, response.content[:400])
        body = response.json()
        self.assertEqual(body["mode"], "grounded_draft")
        self.assertIs(body["verified"], False)
        self.assertEqual(len(body["citations"]), 1)

    @override_settings(VORNEQ_ENV="development", VORNEQ_AI_PHASE_B_ENABLED=True)
    def test_search_without_public_source_abstains_and_skips_provider(self):
        self.client.force_login(self.user)
        with patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider") as provider:
            response = self.client.post(
                reverse("ai_core:ask-grounded"),
                data=json.dumps({"question": "nosuchcontentq7", "language": "en"}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200, response.content[:400])
        self.assertEqual(response.json()["model_status"], "not_called")
        provider.return_value.generate.assert_not_called()


    @override_settings(VORNEQ_ENV="development", VORNEQ_AI_PHASE_B_ENABLED=True)
    def test_exhausted_global_quota_is_http_429_before_provider_invocation(self):
        self.client.force_login(self.user)
        counters = {}

        def fake_add(key, value, timeout):
            counters.setdefault(key, value)
            return True

        def fake_incr(key):
            counters[key] += 1
            return counters[key]

        with patch("apps.ai_core.engine.budget.cache") as mocked_cache:
            mocked_cache.add.side_effect = fake_add
            mocked_cache.incr.side_effect = fake_incr
            with patch("apps.ai_core.views_phase_b.reserve_request",
                       side_effect=lambda user_id: reserve_request(
                           user_id, global_per_day=1)):
                with patch("apps.ai_core.views_phase_b.OpenAIResponsesProvider") as provider:
                    with patch("apps.ai_core.views_phase_b.ask_grounded",
                               return_value={"mode": "grounded_draft",
                                             "verified": False}) as grounded:
                        data = json.dumps({"question": MARKER, "language": "en"})
                        first = self.client.post(
                            reverse("ai_core:ask-grounded"),
                            data=data, content_type="application/json")
                        second = self.client.post(
                            reverse("ai_core:ask-grounded"),
                            data=data, content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error"], "rate_limited")
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(grounded.call_count, 1)


class DevelopmentGlobalRequestCapTests(SimpleTestCase):
    def test_global_daily_limit_applies_across_different_users(self):
        counts = {}
        def add(key, value, timeout):
            counts.setdefault(key, value)
            return True
        def incr(key):
            counts[key] += 1
            return counts[key]
        with patch("apps.ai_core.engine.budget.cache") as mocked_cache:
            mocked_cache.add.side_effect = add
            mocked_cache.incr.side_effect = incr
            reserve_request(501, per_minute=5, per_day=5, global_per_day=2)
            reserve_request(502, per_minute=5, per_day=5, global_per_day=2)
            with self.assertRaises(BudgetExceeded):
                reserve_request(503, per_minute=5, per_day=5, global_per_day=2)
        global_keys = [k for k in counts if k.startswith("phase-b:global:day:")]
        self.assertEqual(len(global_keys), 1)
        self.assertEqual(counts[global_keys[0]], 3)

    def test_global_cache_failure_denies_request(self):
        def add(key, value, timeout):
            if ":global:day:" in key:
                raise RuntimeError("cache backend unavailable")
            return True
        with patch("apps.ai_core.engine.budget.cache") as mocked_cache:
            mocked_cache.add.side_effect = add
            mocked_cache.incr.return_value = 1
            with self.assertRaises(BudgetExceeded):
                reserve_request(989, per_minute=5, per_day=5, global_per_day=5)
