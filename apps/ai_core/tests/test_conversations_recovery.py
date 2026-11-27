"""Persistent conversations V1 with request recovery and the shared ledger (Staging config).

Offline: Redis backend selector, quota and provider are replaced; no network.
"""
import json
import os
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.ai_core import request_recovery as recovery
from apps.ai_core.conversations import service
from apps.ai_core.models import AIChatRequestGuard, AIMessage
from apps.ai_core.tests.test_ai_staging_trial import STAGING_SETTINGS, TEST_ENV
from apps.ai_core.tests.test_global_ai_api import FakeRetriever, evidence, good_output
from apps.ai_core.tests.ledger_fakes import start_fake_ledger


@override_settings(**{**STAGING_SETTINGS, "VORNEQ_GLOBAL_AI_ENABLED": True, "VORNEQ_AI_CHAT_RECOVERY_ENABLED": True,
                      "VORNEQ_AI_STAGING_UNMETERED": True, "VORNEQ_AI_CONVERSATIONS_ENABLED": True,
                      "VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY": "authenticated"})
class ConversationRecoveryLedgerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="conv-recovery-owner", email="cr@example.invalid", password="synthetic-local-only")

    def setUp(self):
        cache.clear()
        self.client.force_login(self.owner)
        for patcher in (
            patch.dict(os.environ, TEST_ENV),
            patch.object(recovery, "_require_shared_redis", return_value=None),
            patch("apps.ai_core.views_global.reserve_global_request"),
            patch("apps.ai_core.views_global.default_retriever", return_value=FakeRetriever(evidence("en"))),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        ids = override_settings(VORNEQ_AI_STAGING_ALLOWED_USER_IDS=str(self.owner.pk))
        ids.enable()
        self.addCleanup(ids.disable)
        # V4-01: hosted chat is always ledger-bound; simulate the shared ledger.
        start_fake_ledger(self)
        self.prior_seen = []

        def produce(self_, *, question, language, sources, prior_turns=()):
            self.prior_seen.append(tuple(prior_turns))
            self_.last_usage = (1000, 200)
            return good_output(sources, language)

        provider = patch("apps.ai_core.views_global.OpenAIResponsesProvider.generate", autospec=True,
                         side_effect=produce)
        self.generator = provider.start()
        self.addCleanup(provider.stop)
        self.conversation = service.create(self.owner)

    def ask(self, request_id, conversation=None, question="What is quantum computing?"):
        return self.client.post(
            reverse("ai_core:conversation-messages", args=[(conversation or self.conversation).id]),
            data=json.dumps({"question": question, "language": "en"}), content_type="application/json",
            HTTP_X_VQ_REQUEST_ID=request_id)

    def test_same_request_id_twice_stores_once_and_calls_model_once(self):
        rid = str(uuid.uuid4())
        first = self.ask(rid)
        second = self.ask(rid)
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(first.json(), second.json())
        self.assertEqual(self.generator.call_count, 1)
        self.assertEqual(AIMessage.objects.filter(conversation=self.conversation).count(), 2)
        assistant = AIMessage.objects.get(request_id=rid)
        self.assertEqual((assistant.role, assistant.sequence), ("assistant", 2))
        self.assertEqual(AIChatRequestGuard.objects.get(request_id=rid).state, "finished")

    @override_settings(VORNEQ_AI_FEEDBACK_ENABLED=True)
    def test_feedback_identity_survives_cache_and_database_replay(self):
        rid = str(uuid.uuid4())
        first = self.ask(rid)
        self.assertEqual(first.status_code, 200)
        assistant = AIMessage.objects.get(request_id=rid)
        identity = str(assistant.pk)
        self.assertEqual(first.json()["assistant_message_id"], identity)
        self.assertNotEqual(identity, rid)
        self.assertTrue(first.json()["persisted"])
        recovered = self.client.get(reverse("ai_core:request-status"), {"request_id": rid})
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json()["response"]["assistant_message_id"], identity)
        target = reverse("ai_core:conversation-message-feedback",
                         args=[self.conversation.pk, assistant.pk])
        rating = self.client.post(target, data='{"rating":"like"}',
                                  content_type="application/json")
        self.assertEqual(rating.json(), {"rating": "like"})
        self.assertEqual(self.ask(rid).json()["assistant_message_id"], identity)
        cache.clear()
        replay = self.ask(rid)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["assistant_message_id"], identity)
        self.assertEqual(self.client.get(target).json(), {"rating": "like"})
        self.assertEqual(self.generator.call_count, 1)

    def test_request_id_cannot_be_replayed_into_another_conversation(self):
        rid = str(uuid.uuid4())
        self.assertEqual(self.ask(rid).status_code, 200)
        other = service.create(self.owner)
        response = self.ask(rid, conversation=other)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"error": "request_id_conflict"})
        self.assertEqual(AIMessage.objects.filter(conversation=other).count(), 0)
        self.assertEqual(self.generator.call_count, 1)

    def test_missing_request_id_rejected_before_cost(self):
        response = self.client.post(reverse("ai_core:conversation-messages", args=[self.conversation.id]),
                                    data=json.dumps({"question": "What is quantum computing?", "language": "en"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.generator.assert_not_called()

    def test_history_survives_redis_loss(self):
        self.assertEqual(self.ask(str(uuid.uuid4())).status_code, 200)
        cache.clear()
        data = self.client.get(reverse("ai_core:conversation-detail", args=[self.conversation.id])).json()
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(self.ask(str(uuid.uuid4()), question="And how do qubits work?").status_code, 200)
        self.assertEqual(len(self.prior_seen[-1]), 2)

    def test_ledger_reserves_for_exact_payload_including_history_and_links_reservation(self):
        reservations = []

        def reserve(*, actor_id, model, input_bytes, max_output_tokens):
            reservation = SimpleNamespace(id=uuid.uuid4(), amount_micro=1, input_price=1, output_price=1)
            reservations.append((input_bytes, reservation.id))
            return reservation

        with patch("apps.ai_core.views_global.ledger_enabled", return_value=True), \
                patch("apps.ai_core.budgeted_provider.ledger.reserve", side_effect=reserve), \
                patch("apps.ai_core.budgeted_provider.ledger.settle") as settle:
            rid1, rid2 = str(uuid.uuid4()), str(uuid.uuid4())
            self.assertEqual(self.ask(rid1).status_code, 200)
            self.assertEqual(self.ask(rid2, question="And how do qubits work?").status_code, 200)
            self.assertEqual(self.ask(rid2, question="And how do qubits work?").status_code, 200)  # replay
        self.assertEqual(len(reservations), 2)
        self.assertGreater(reservations[1][0], reservations[0][0])  # history increases the reservation
        self.assertEqual(settle.call_count, 2)
        self.assertEqual(AIMessage.objects.get(request_id=rid1).ledger_reservation_id, reservations[0][1])
        self.assertEqual(AIMessage.objects.get(request_id=rid2).ledger_reservation_id, reservations[1][1])
