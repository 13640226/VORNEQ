"""Offline owner-only Staging request recovery tests. No OpenAI egress."""
import json
import os
import time
import uuid
from unittest.mock import patch

from apps.ai_core.tests.ledger_fakes import start_fake_ledger

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from apps.ai_core.models import AIChatRequestGuard
from django.urls import reverse

from apps.ai_core import request_recovery as recovery
_REAL_REDIS_CHECK = recovery._require_shared_redis
from apps.ai_core.tests.test_ai_staging_trial import STAGING_SETTINGS, TEST_ENV
from apps.ai_core.tests.test_global_ai_api import FakeRetriever, evidence, good_output


@override_settings(**{
    **STAGING_SETTINGS,
    "VORNEQ_GLOBAL_AI_ENABLED": True,
    "VORNEQ_AI_CHAT_RECOVERY_ENABLED": True,
    "VORNEQ_AI_STAGING_UNMETERED": True,
})
class RecoveryEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="ai-recovery-owner", email="recovery@example.invalid",
            password="synthetic-local-only"
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.owner)
        self.id = str(uuid.uuid4())
        self.submit_url = reverse("ai_core:ask-global")
        self.status_url = reverse("ai_core:request-status")
        env = patch.dict(os.environ, TEST_ENV)
        env.start()
        self.addCleanup(env.stop)
        ids = override_settings(VORNEQ_AI_STAGING_ALLOWED_USER_IDS=str(self.owner.pk))
        ids.enable()
        self.addCleanup(ids.disable)
        # Unit integration: real Redis is required by hosted runtime; local tests
        # replace only the Redis backend selector, retaining atomic cache.add.
        redis_gate = patch.object(recovery, "_require_shared_redis", return_value=None)
        redis_gate.start()
        self.addCleanup(redis_gate.stop)
        quota = patch("apps.ai_core.views_global.reserve_global_request")
        quota.start()
        self.addCleanup(quota.stop)
        # V4-01: hosted chat is always ledger-bound; simulate the shared ledger.
        self.ledger_reserve, self.ledger_settle = start_fake_ledger(self)
        retriever = patch("apps.ai_core.views_global.default_retriever",
                          return_value=FakeRetriever(evidence("en")))
        retriever.start()
        self.addCleanup(retriever.stop)
        def produce(self_, *, question, language, sources):
            return good_output(sources, language)
        provider = patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate",
                         autospec=True, side_effect=produce)
        self.generator = provider.start()
        self.addCleanup(provider.stop)

    def post(self, request_id=None, question="What is quantum computing?", client=None):
        headers = {"HTTP_X_VQ_REQUEST_ID": self.id if request_id is None else request_id}
        return (client or self.client).post(
            self.submit_url,
            data=json.dumps({"question": question, "language": "en"}),
            content_type="application/json", **headers
        )

    def get_status(self, request_id=None, client=None):
        return (client or self.client).get(
            self.status_url, {"request_id": self.id if request_id is None else request_id}
        )

    def test_first_request_generates_exactly_once_and_status_restores(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.generator.call_count, 1)
        status = self.get_status()
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "completed")
        self.assertEqual(status.json()["response"], response.json())
        self.generator.assert_called_once()

    def test_duplicate_post_uses_existing_answer_without_new_provider(self):
        first = self.post()
        second = self.post()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), first.json())
        self.generator.assert_called_once()

    def test_v4_duplicate_request_reserves_ledger_exactly_once(self):
        """TEST-09: the same request ID never creates a second reservation or charge."""
        first = self.post()
        second = self.post()
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(second.json(), first.json())
        self.ledger_reserve.assert_called_once()
        self.ledger_settle.assert_called_once()
        self.generator.assert_called_once()

    def test_same_id_different_question_is_conflict(self):
        self.assertEqual(self.post().status_code, 200)
        other = self.post(question="What is a different public topic?")
        self.assertEqual(other.status_code, 409)
        self.assertEqual(other.json()["error"], "request_id_conflict")
        self.generator.assert_called_once()

    def test_duplicate_while_running_returns_pending_without_provider(self):
        request = self._request_with_session()
        self.assertEqual(
            recovery.claim(request, self.id, question="What is quantum computing?", language="en")["status"],
            "claimed"
        )
        self.assertEqual(self.post().status_code, 202)
        self.assertEqual(self.get_status().json()["status"], "running")
        self.generator.assert_not_called()

    def _request_with_session(self):
        from types import SimpleNamespace
        session = self.client.session
        return SimpleNamespace(user=self.owner, session=session)

    def test_repeated_claims_have_one_owner_only(self):
        # SQLite TestCase uses a wrapping transaction, not shared across
        # threads. Real PostgreSQL concurrency is tested separately below.
        request = self._request_with_session()
        outcomes = [
            recovery.claim(request, self.id,
                           question="What is quantum computing?", language="en")["status"]
            for _ in range(8)
        ]
        self.assertEqual(outcomes.count("claimed"), 1)
        self.assertEqual(outcomes.count("running"), 7)
        self.generator.assert_not_called()

    def test_stale_running_request_is_uncertain_not_replayed(self):
        request = self._request_with_session()
        recovery.claim(request, self.id, question="What is quantum computing?", language="en")
        AIChatRequestGuard.objects.filter(request_id=self.id).update(
            created_at=timezone.now() - timedelta(seconds=130)
        )
        self.assertEqual(self.get_status().json()["status"], "uncertain")
        self.assertEqual(self.post().status_code, 409)
        self.generator.assert_not_called()

    def test_response_expiry_keeps_replay_guard(self):
        self.assertEqual(self.post().status_code, 200)
        _, result_key = recovery._keys(self.id)
        cache.delete(result_key)
        self.assertEqual(self.get_status().json()["status"], "expired")
        self.assertEqual(self.post().status_code, 409)
        self.generator.assert_called_once()

    def test_other_authenticated_session_cannot_read_or_replay(self):
        self.assertEqual(self.post().status_code, 200)
        other = Client()
        other.force_login(self.owner)
        self.assertEqual(self.get_status(client=other).status_code, 404)
        self.assertEqual(self.post(client=other).status_code, 404)
        self.generator.assert_called_once()

    def test_unauthorized_user_and_anonymous_denied(self):
        self.assertEqual(self.post().status_code, 200)
        other = get_user_model().objects.create_user(username="no-access", password="test")
        browser = Client()
        self.assertEqual(self.get_status(client=browser).status_code, 404)
        browser.force_login(other)
        self.assertEqual(self.get_status(client=browser).status_code, 404)
        self.generator.assert_called_once()

    def test_missing_or_invalid_uuid_rejected_without_provider(self):
        for value in ("", "not-a-uuid", str(uuid.uuid1()), "a" * 36):
            self.assertEqual(self.post(request_id=value).status_code, 400)
        self.generator.assert_not_called()

    def test_cost_free_unsupported_question_recovers_without_provider(self):
        first = self.post(question="?!")
        self.assertEqual(first.status_code, 422)
        state = self.get_status()
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json()["status"], "failed")
        self.assertEqual(state.json()["http_status"], 422)
        second = self.post(question="?!")
        self.assertEqual(second.status_code, 422)
        self.generator.assert_not_called()

    def test_rejected_quote_is_recovered_without_second_provider_call(self):
        def forged(self_, *, question, language, sources):
            result = good_output(sources, language)
            result["citations"][0]["evidence_quote"] = "PRIVATE_FAKED_QUOTE_SENTINEL"
            return result
        self.generator.side_effect = forged
        with self.assertLogs("apps.ai_core.views_global", level="WARNING") as log:
            first = self.post()
        self.assertEqual(first.status_code, 422)
        self.assertEqual(first.json(), {"error": "INSUFFICIENT_EVIDENCE",
                                        "reason_code": "citation_quote_mismatch"})
        self.assertNotIn("PRIVATE_FAKED_QUOTE_SENTINEL", " ".join(log.output))
        state = self.get_status().json()
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["http_status"], 422)
        self.assertEqual(state["response"], first.json())
        self.assertEqual(self.post().json(), first.json())
        self.generator.assert_called_once()

    def test_cache_claim_failure_fails_closed(self):
        with patch.object(recovery.cache, "add", side_effect=ConnectionError("offline")):
            self.assertEqual(self.post().status_code, 503)
        self.assertTrue(AIChatRequestGuard.objects.filter(request_id=self.id).exists())
        self.generator.assert_not_called()

    def test_redis_policy_denies_local_cache_in_hosted_staging(self):
        with patch.object(recovery, "_require_shared_redis", new=_REAL_REDIS_CHECK):
            with override_settings(REDIS_URL=None):
                self.assertEqual(self.post().status_code, 503)
        self.generator.assert_not_called()

    def test_feature_disabled_and_production_status_denied(self):
        with override_settings(VORNEQ_AI_CHAT_RECOVERY_ENABLED=False):
            self.assertEqual(self.get_status().status_code, 404)
        with override_settings(VORNEQ_ENV="production"):
            self.assertEqual(self.get_status().status_code, 404)
        self.generator.assert_not_called()

    def test_no_csrf_header_does_not_consume_any_quota_or_model(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        result = self.post(client=strict)
        self.assertEqual(result.status_code, 403)
        self.generator.assert_not_called()

    def test_durable_guard_survives_total_redis_cache_loss(self):
        """A 200 response must never be charged twice after Redis reset."""
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.generator.call_count, 1)
        self.assertEqual(AIChatRequestGuard.objects.get(request_id=self.id).state, "finished")
        cache.clear()
        self.assertEqual(self.get_status().json()["status"], "expired")
        repeat = self.post()
        self.assertEqual(repeat.status_code, 409)
        self.assertEqual(repeat.json()["status"], "expired")
        self.generator.assert_called_once()

    def test_redis_outage_after_durable_insert_fails_closed(self):
        request = self._request_with_session()
        with patch.object(recovery.cache, "add", side_effect=ConnectionError("offline")):
            with self.assertRaises(recovery.RecoveryUnavailable):
                recovery.claim(request, self.id,
                               question="What is quantum computing?", language="en")
        self.assertTrue(AIChatRequestGuard.objects.filter(request_id=self.id).exists())
        cache.clear()
        # Never re-claim the UUID after losing the Redis guard.
        self.assertEqual(recovery.claim(
            request, self.id, question="What is quantum computing?", language="en"
        )["status"], "running")
        self.generator.assert_not_called()

    def test_database_unavailable_never_invokes_provider(self):
        with patch.object(recovery.AIChatRequestGuard.objects, "using",
                          side_effect=DatabaseError("synthetic database outage")):
            self.assertEqual(self.post().status_code, 503)
        self.generator.assert_not_called()

    def test_durable_row_is_missing_no_cache_only_replay(self):
        request = self._request_with_session()
        key, _ = recovery._keys(self.id)
        cache.add(key, {"actor": self.owner.pk}, timeout=86400)
        with self.assertRaises(recovery.RecoveryUnavailable):
            recovery.claim(request, self.id,
                           question="What is quantum computing?", language="en")
        self.assertTrue(AIChatRequestGuard.objects.filter(request_id=self.id).exists())
        self.generator.assert_not_called()


@override_settings(VORNEQ_ENV="staging", VORNEQ_AI_CHAT_RECOVERY_ENABLED=True)
class DurableGuardPostgresConcurrencyTests(TransactionTestCase):
    """Runs on CI's disposable Postgres database, never production."""

    databases = {"default"}

    def test_postgres_unique_claim_with_eight_workers(self):
        if connection.vendor != "postgresql":
            self.skipTest("real PostgreSQL concurrency is only checked on PostgreSQL CI")
        from concurrent.futures import ThreadPoolExecutor
        from types import SimpleNamespace

        request_id = str(uuid.uuid4())
        user = SimpleNamespace(pk=7777, is_authenticated=True, is_active=True)
        request = SimpleNamespace(
            user=user, session=SimpleNamespace(session_key="synthetic-session")
        )

        def attempt(_):
            try:
                return recovery.claim(
                    request, request_id,
                    question="What is quantum computing?", language="en"
                )["status"]
            finally:
                connections.close_all()

        with patch.object(recovery, "_require_shared_redis", return_value=None):
            with ThreadPoolExecutor(max_workers=8) as pool:
                observed = list(pool.map(attempt, range(8)))
        self.assertEqual(observed.count("claimed"), 1, observed)
        self.assertEqual(observed.count("running"), 7, observed)
        self.assertEqual(AIChatRequestGuard.objects.filter(
            request_id=request_id
        ).count(), 1)
