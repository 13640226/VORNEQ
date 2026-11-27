"""Owner-only feedback: no real provider, ledger, or external network."""
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.ai_core.chat_strings import chat_labels
from apps.ai_core.conversations import feedback, service
from apps.ai_core.models import AIConversation, AIMessage, AIMessageFeedback
from apps.ai_core.tests.test_global_ai_api import NoNetworkMixin
from apps.ai_core.tests.test_conversations_v1 import CONV
from apps.ai_core.tests.test_v7_03_streaming import FakeStreamProvider, frames

FLAGS = {**CONV, "VORNEQ_AI_FEEDBACK_ENABLED": True}
ANSWER = "Synthetic completed answer."
RESULT = {"mode": "grounded_draft", "answer": ANSWER, "verified": False,
          "citations": []}


def user(name):
    return get_user_model().objects.create_user(username=name, email=f"{name}@example.invalid",
                                                password="synthetic-only")


def message(conv, *, seq=1, role=AIMessage.ROLE_ASSISTANT,
            status=AIMessage.STATUS_COMPLETED, content=ANSWER):
    return AIMessage.objects.create(conversation=conv, sequence=seq, role=role,
                                    status=status, content=content)


def url(conv, msg):
    return reverse("ai_core:conversation-message-feedback", args=[conv.pk, msg.pk])


@override_settings(**FLAGS)
class FeedbackApiTests(NoNetworkMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.owner, self.other = user("feedback-owner"), user("feedback-other")
        self.conv = AIConversation.objects.create(owner=self.owner, title="Synthetic")
        self.msg = message(self.conv)
        self.conv.message_count = 1
        self.conv.save(update_fields=["message_count"])
        self.client.force_login(self.owner)
        self.url = url(self.conv, self.msg)
        # Any call into paid pipeline/ledger from this API is an immediate failure.
        for name in ("apps.ai_core.views_conversations.run_global_pipeline",
                     "apps.ai_core.views_global.paid_text_provider",
                     "apps.ai_ledger.service.reserve", "apps.ai_ledger.service.reserve_with_config"):
            p = patch(name, side_effect=AssertionError("feedback must not invoke " + name))
            p.start()
            self.addCleanup(p.stop)

    def post(self, rating="like", target=None, client=None):
        return (client or self.client).post(target or self.url,
                                            data=json.dumps({"rating": rating}),
                                            content_type="application/json")

    def test_create_change_remove_idempotent(self):
        self.assertEqual(self.client.get(self.url).json(), {"rating": None})
        self.assertEqual(self.post().json(), {"rating": "like"})
        row = AIMessageFeedback.objects.get(pk=self.msg.pk)
        old_time = row.updated_at
        self.assertEqual(self.post().json(), {"rating": "like"})
        row.refresh_from_db()
        self.assertEqual(row.updated_at, old_time)
        self.assertEqual(self.post("dislike").json(), {"rating": "dislike"})
        self.assertEqual(AIMessageFeedback.objects.count(), 1)
        self.assertEqual(self.client.get(self.url).json(), {"rating": "dislike"})
        self.assertEqual(self.client.delete(self.url).json(), {"rating": None})
        self.assertEqual(self.client.delete(self.url).json(), {"rating": None})
        self.assertFalse(AIMessageFeedback.objects.exists())

    def test_history_and_export_restore_ratings_without_n_plus_one(self):
        self.post()
        second = message(self.conv, seq=2)
        third = message(self.conv, seq=3, role=AIMessage.ROLE_USER)
        detail = reverse("ai_core:conversation-detail", args=[self.conv.pk])
        with CaptureQueriesContext(connection) as ctx:
            data = self.client.get(detail).json()["messages"]
        feedback_queries = [q for q in ctx.captured_queries if "ai_core_aimessagefeedback" in q["sql"].lower()]
        self.assertEqual(len(feedback_queries), 1)
        self.assertEqual([m.get("feedback", "absent") for m in data], ["like", None, "absent"])
        exported = self.client.get(reverse("ai_core:conversation-export", args=[self.conv.pk])).json()
        self.assertEqual(exported["messages"][0]["feedback"], "like")
        self.assertEqual(data[1]["id"], str(second.pk))
        self.assertEqual(data[2]["id"], str(third.pk))

    def test_foreign_mismatch_unknown_indistinguishable(self):
        foreign = AIConversation.objects.create(owner=self.other)
        foreign_msg = message(foreign)
        same_owner = AIConversation.objects.create(owner=self.owner)
        other_msg = message(same_owner)
        targets = [url(foreign, foreign_msg), url(self.conv, foreign_msg),
                   url(self.conv, other_msg),
                   reverse("ai_core:conversation-message-feedback", args=[self.conv.pk, uuid.uuid4()]),
                   reverse("ai_core:conversation-message-feedback", args=[uuid.uuid4(), self.msg.pk])]
        for target in targets:
            for reply in (self.client.get(target), self.post(target=target), self.client.delete(target)):
                self.assertEqual(reply.status_code, 404)
                self.assertEqual(reply.json(), {"error": "not_found"})
        self.assertFalse(AIMessageFeedback.objects.exists())

    def test_auth_csrf_and_method(self):
        anonymous = Client()
        for reply in (anonymous.get(self.url), self.post(client=anonymous), anonymous.delete(self.url)):
            self.assertEqual(reply.status_code, 401)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(self.post(client=strict).status_code, 403)
        self.assertEqual(strict.delete(self.url).status_code, 403)
        strict.cookies["csrftoken"] = "a" * 32
        self.assertEqual(strict.post(self.url, data='{"rating":"like"}',
                                     content_type="application/json", HTTP_X_CSRFTOKEN="a" * 32).status_code, 200)
        self.assertEqual(strict.delete(self.url, HTTP_X_CSRFTOKEN="a" * 32).status_code, 200)
        self.assertEqual(self.client.put(self.url).status_code, 405)

    def test_inactive_user(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertEqual(self.post().status_code, 401)
        self.assertFalse(AIMessageFeedback.objects.exists())

    def test_strict_payload(self):
        for body in ('{}', '{"rating":null}', '{"rating":1}', '{"rating":[]}', '{"rating":"LIKE"}',
                     '{"rating":"like","user":1}', '{"rating":"like","rating":"dislike"}', '[]',
                     '{"rating":"' + "x" * 140 + '"}', '{"rating":'):
            with self.subTest(body=body[:50]):
                self.assertEqual(self.client.post(self.url, data=body,
                                                  content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(self.url, data="like", content_type="text/plain").status_code, 400)
        self.assertFalse(AIMessageFeedback.objects.exists())

    def test_ineligible_states_and_blank(self):
        states = [(AIMessage.ROLE_USER, AIMessage.STATUS_COMPLETED, ANSWER),
                  (AIMessage.ROLE_ASSISTANT, AIMessage.STATUS_PENDING, ANSWER),
                  (AIMessage.ROLE_ASSISTANT, AIMessage.STATUS_FAILED, ANSWER),
                  (AIMessage.ROLE_ASSISTANT, AIMessage.STATUS_UNCERTAIN, ANSWER),
                  (AIMessage.ROLE_ASSISTANT, AIMessage.STATUS_INSUFFICIENT, ANSWER),
                  (AIMessage.ROLE_ASSISTANT, AIMessage.STATUS_COMPLETED, " ")]
        for index, (role, status, content) in enumerate(states, 2):
            target = url(self.conv, message(self.conv, seq=index, role=role, status=status, content=content))
            self.assertEqual(self.post(target=target).status_code, 409)
            self.assertEqual(self.client.get(target).status_code, 409)
            self.assertEqual(self.client.delete(target).status_code, 409)
        self.assertFalse(AIMessageFeedback.objects.exists())

    def test_archive_allowed_trash_denied_and_cascade(self):
        self.conv.archived_at = timezone.now()
        self.conv.save(update_fields=["archived_at"])
        self.assertEqual(self.post().status_code, 200)
        service.move_to_trash(self.owner, self.conv.pk)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.post("dislike").status_code, 404)
        self.assertEqual(self.client.delete(self.url).status_code, 404)
        self.assertEqual(AIMessageFeedback.objects.get(pk=self.msg.pk).rating, "like")
        service.restore(self.owner, self.conv.pk)
        self.assertEqual(self.client.get(self.url).json(), {"rating": "like"})
        service.move_to_trash(self.owner, self.conv.pk)
        service.delete_permanently(self.owner, self.conv.pk)
        self.assertFalse(AIMessageFeedback.objects.exists())

    def test_flag_disabled_both_layers_and_no_rating_query(self):
        self.post()
        detail = reverse("ai_core:conversation-detail", args=[self.conv.pk])
        for flags in ({"VORNEQ_AI_FEEDBACK_ENABLED": False},
                      {"VORNEQ_AI_CONVERSATIONS_ENABLED": False}):
            with override_settings(**flags):
                for reply in (self.client.get(self.url), self.post(), self.client.delete(self.url)):
                    self.assertEqual(reply.status_code, 404)
        with override_settings(VORNEQ_AI_FEEDBACK_ENABLED=False), CaptureQueriesContext(connection) as ctx:
            self.assertNotIn("feedback", self.client.get(detail).json()["messages"][0])
            self.assertNotIn("data-vq-feedback=", self.client.get(reverse("ai_core:chat")).content.decode())
        self.assertFalse(any("ai_core_aimessagefeedback" in q["sql"].lower() for q in ctx.captured_queries))

    def test_history_feedback_independent_of_paid_gates(self):
        with override_settings(VORNEQ_GLOBAL_AI_ENABLED=False, VORNEQ_AI_EMERGENCY_STOP=True):
            self.assertEqual(self.post().json(), {"rating": "like"})
        self.assertEqual(self.client.get(self.url).json(), {"rating": "like"})

    def test_database_check_constraint_and_failure(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AIMessageFeedback.objects.create(message=self.msg, rating="bogus")
        with patch("apps.ai_core.views_conversations.feedback.access", side_effect=DatabaseError("down")):
            reply = self.post()
        self.assertEqual(reply.status_code, 503)
        self.assertEqual(reply.json(), {"error": "persistence_unavailable"})
        self.assertFalse(AIMessageFeedback.objects.exists())

    def test_feedback_read_failure_does_not_break_history_or_fake_export(self):
        with patch("apps.ai_core.conversations.feedback.ratings", side_effect=DatabaseError("down")):
            detail = self.client.get(reverse("ai_core:conversation-detail", args=[self.conv.pk]))
            self.assertEqual(detail.status_code, 200)
            self.assertNotIn("feedback", detail.json()["messages"][0])
            export = self.client.get(reverse("ai_core:conversation-export", args=[self.conv.pk]))
            self.assertEqual(export.status_code, 503)

    def test_ui_localized_flag_and_private_cache(self):
        for lang in ("fa", "de", "en"):
            page = self.client.get(reverse("ai_core:chat"), {"lang": lang})
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, 'data-vq-feedback="true"')
            self.assertContains(page, chat_labels(lang, "development")["feedback_like"])
        reply = self.post()
        self.assertIn("no-store", reply["Cache-Control"])

    def test_persisted_identity_and_db_replay_only_for_matching_complete_answer(self):
        response = dict(RESULT)
        self.assertEqual(feedback.response_identity(self.msg, response), {"assistant_message_id": str(self.msg.pk)})
        self.assertEqual(feedback.response_identity(self.msg, {"answer": "different"}), {})
        body, status = service.stored_response(self.msg, self.conv)
        self.assertEqual(status, 200)
        self.assertEqual(body["assistant_message_id"], str(self.msg.pk))
        with override_settings(VORNEQ_AI_FEEDBACK_ENABLED=False):
            self.assertNotIn("assistant_message_id", service.stored_response(self.msg, self.conv)[0])

    def test_json_and_grounded_stream_completion_identity(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                name = "ai_core:conversation-messages-stream" if stream else "ai_core:conversation-messages"
                with override_settings(VORNEQ_AI_CHAT_STREAMING_ENABLED=True,
                                       VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=False):
                    # Only this synthetic request may run a stub pipeline. Feedback
                    # mutation still has the provider/ledger tripwires installed.
                    with patch("apps.ai_core.views_conversations.run_global_pipeline",
                               return_value=(dict(RESULT), 200, {})), patch(
                               "apps.ai_core.views_streaming.run_global_pipeline",
                               return_value=(dict(RESULT), 200, {})):
                        reply = self.client.post(reverse(name, args=[self.conv.pk]),
                                                 data='{"question":"Synthetic question?","language":"en"}',
                                                 content_type="application/json")
                self.assertEqual(reply.status_code, 200)
                if stream:
                    events = frames(b"".join(reply.streaming_content))
                    data = events[-1]["payload"]["response"]
                else:
                    data = reply.json()
                target = AIMessage.objects.get(pk=data["assistant_message_id"])
                self.assertEqual(target.content, ANSWER)
                self.assertEqual(target.conversation_id, self.conv.pk)
                self.assertTrue(data["persisted"])
                self.assertEqual(self.post(target=url(self.conv, target)).json(), {"rating": "like"})

    def test_knowledge_stream_identity(self):
        import os
        with override_settings(VORNEQ_AI_CHAT_STREAMING_ENABLED=True,
                               VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=True), patch.dict(
                               os.environ, {"VORNEQ_AI_PHASE_B_MODEL": "mock-only"}), patch(
                               "apps.ai_core.views_global.paid_text_provider",
                               return_value=FakeStreamProvider(["Synthetic knowledge answer."])):
            reply = self.client.post(reverse("ai_core:conversation-messages-stream", args=[self.conv.pk]),
                                     data='{"question":"What is quantum computing?","language":"en"}',
                                     content_type="application/json")
            self.assertEqual(reply.status_code, 200)
            events = frames(b"".join(reply.streaming_content))
        final = events[-1]
        self.assertEqual(final["type"], "response.completed")
        data = final["payload"]["response"]
        self.assertEqual(data["assistant_message_id"], final["response_id"])
        self.assertEqual(data["conversation_id"], str(self.conv.pk))
        self.assertTrue(data["persisted"])

    def test_durable_identity_from_json_persist_and_failure(self):
        from django.test import RequestFactory
        from apps.ai_core.views_conversations import persist_turn
        _, pending = service.begin_turn(self.owner, self.conv.pk, question="Synthetic")
        body, saved = persist_turn(RequestFactory().post("/"), self.owner, self.conv, pending, None,
                                   RESULT, 200)
        self.assertTrue(saved)
        self.assertEqual(body["assistant_message_id"], str(pending.pk))
        _, pending = service.begin_turn(self.owner, self.conv.pk, question="Other")
        with patch("apps.ai_core.views_conversations.service.complete_turn", side_effect=DatabaseError("down")):
            body, saved = persist_turn(RequestFactory().post("/"), self.owner, self.conv, pending, None,
                                       RESULT, 200)
        self.assertFalse(saved)
        self.assertNotIn("assistant_message_id", body)


@override_settings(**FLAGS)
class FeedbackConcurrencyTests(TransactionTestCase):
    def test_postgres_concurrent_writes_and_delete(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock evidence required; SQLite functional tests run separately")
        owner = user("feedback-concurrent")
        conv = AIConversation.objects.create(owner=owner)
        msg = message(conv)
        for values in (["like", "like"], ["dislike", "like"], [None, "dislike"]):
            gate = threading.Barrier(len(values))
            def worker(value):
                close_old_connections()
                try:
                    actor = get_user_model().objects.get(pk=owner.pk)
                    gate.wait(timeout=10)
                    return feedback.access(actor, conv.pk, msg.pk,
                                           method="DELETE" if value is None else "POST", rating=value)
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(worker, values))
            self.assertEqual(results, values)
            self.assertLessEqual(AIMessageFeedback.objects.filter(pk=msg.pk).count(), 1)
            final = AIMessageFeedback.objects.filter(pk=msg.pk).values_list("rating", flat=True).first()
            self.assertIn(final, values)
