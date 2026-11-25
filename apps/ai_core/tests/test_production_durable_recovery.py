"""Fail-closed Production AI recovery tests. Synthetic only; no OpenAI network."""
import json
import os
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.ai_core import request_recovery as recovery
from apps.ai_core.models import AIChatRequestGuard
from apps.ai_core.tests.test_global_ai_api import FakeRetriever, evidence, good_output
from apps.ai_ledger.tests.test_ledger_unit import PROD, PROD_ENV
from apps.ai_ledger.tests import helpers as h


class ProductionDurableRecoveryTests(TestCase):
    """Real test-database guard + in-memory cache + a fake-only model."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="synthetic-prod-guard", password="synthetic-test-only"
        )

    def setUp(self):
        self.request_id = str(uuid.uuid4())
        self.question = "What is quantum computing?"
        self.submit = reverse("ai_core:ask-global")
        self.lookup = reverse("ai_core:request-status")
        self.client.force_login(self.owner)
        cache.clear()
        self.client.cookies["csrftoken"] = "a" * 32

        env = patch.dict(os.environ, {**h.env_without_render(), **PROD_ENV}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        overrides = override_settings(**{
            **PROD,
            "VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS": str(self.owner.pk),
            "VORNEQ_GLOBAL_AI_QUOTA": {"per_minute": 5},
        })
        overrides.enable()
        self.addCleanup(overrides.disable)

        def fake_generate(_provider, *, question, language, sources):
            return good_output(sources, language)
        fixtures = [
            patch.object(recovery, "_require_shared_redis", return_value=None),
            patch("apps.ai_core.production_policy.ledger_enabled", return_value=True),
            patch("apps.ai_core.views_global.ledger_enabled", return_value=True),
            patch("apps.ai_core.views_global.reserve_global_request"),
            patch("apps.ai_core.paid_provider.BudgetedProvider",
                  side_effect=lambda provider, actor_id: provider),
            patch("apps.ai_core.views_global.default_retriever",
                  return_value=FakeRetriever(evidence("en"))),
        ]
        for fixture in fixtures:
            fixture.start()
            self.addCleanup(fixture.stop)
        fake = patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate",
                     autospec=True, side_effect=fake_generate)
        self.model = fake.start()
        self.addCleanup(fake.stop)

    def post(self, uid=None, question=None, client=None, add_uuid=True):
        kw = {"HTTP_X_VQ_REQUEST_ID": self.request_id if uid is None else uid} if add_uuid else {}
        return (client or self.client).post(
            self.submit,
            data=json.dumps({"question": question or self.question, "language": "en"}),
            content_type="application/json", **kw
        )

    def status(self, uid=None, client=None):
        return (client or self.client).get(
            self.lookup, {"request_id": self.request_id if uid is None else uid}
        )

    def test_production_requires_unique_uuid_and_recovers_once(self):
        self.assertEqual(self.post(add_uuid=False).status_code, 400)
        self.model.assert_not_called()
        first = self.post()
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(self.status().json()["status"], "completed")
        self.assertEqual(self.status().json()["response"], first.json())
        self.assertEqual(self.post().json(), first.json())
        self.assertEqual(self.model.call_count, 1)
        self.assertEqual(AIChatRequestGuard.objects.get(request_id=self.request_id).state, "finished")

    def test_cache_loss_does_not_repeat_charge_or_model(self):
        self.assertEqual(self.post().status_code, 200)
        cache.clear()
        self.assertEqual(self.status().json()["status"], "expired")
        self.assertEqual(self.post().status_code, 409)
        self.model.assert_called_once()

    def test_request_id_payload_or_session_isolation(self):
        self.assertEqual(self.post().status_code, 200)
        conflict = self.post(question="Another question?")
        self.assertEqual(conflict.status_code, 409)
        other = Client()
        other.force_login(self.owner)
        self.assertEqual(self.status(client=other).status_code, 404)
        self.assertEqual(self.post(client=other).status_code, 404)
        self.model.assert_called_once()

    def test_production_status_policy_is_not_staging_actor_policy(self):
        self.assertEqual(self.post().status_code, 200)
        with patch("apps.ai_core.views_global.actor_allowed",
                   side_effect=AssertionError("staging actor policy called")):
            self.assertEqual(self.status().status_code, 200)
        other = get_user_model().objects.create_user(
            username="synthetic-prod-denied", password="synthetic-test-only"
        )
        viewer = Client()
        viewer.force_login(other)
        self.assertEqual(self.status(client=viewer).status_code, 404)
        self.model.assert_called_once()

    def test_prod_recovery_flag_off_denies_before_model(self):
        with override_settings(VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED=False):
            self.assertEqual(self.post().status_code, 404)
            self.assertEqual(self.status().status_code, 404)
        self.model.assert_not_called()

    def test_redis_and_database_outage_fail_closed(self):
        with patch.object(recovery, "_require_shared_redis",
                          side_effect=recovery.RecoveryUnavailable("redis unavailable")):
            self.assertEqual(self.post().status_code, 503)
        self.model.assert_not_called()
        with patch.object(AIChatRequestGuard.objects, "using",
                          side_effect=DatabaseError("synthetic outage")):
            self.assertEqual(self.post(uid=str(uuid.uuid4())).status_code, 503)
        self.model.assert_not_called()

    def test_cache_key_namespace_is_environment_isolated(self):
        production_keys = recovery._keys(self.request_id)
        with override_settings(VORNEQ_ENV="staging"):
            staging_keys = recovery._keys(self.request_id)
        self.assertNotEqual(production_keys, staging_keys)
        self.assertTrue(production_keys[0].startswith("vq:ai:production:"))

    def test_production_recovery_not_enabled_from_staging_flag(self):
        with override_settings(VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED=False,
                               VORNEQ_AI_CHAT_RECOVERY_ENABLED=True):
            self.assertFalse(recovery.enabled())
        self.model.assert_not_called()
