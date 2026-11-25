"""V7-03: Streaming, Stop und Wiederherstellung – offline mit Fake-Providern.

Keine Netzwerk- oder bezahlten Aufrufe: der Provider wird über
``apps.ai_core.views_global.paid_text_provider`` durch Fakes ersetzt; das OpenAI-SDK
ist in den Provider-Tests durch einen Stolperdraht/Fake-Client ersetzt.
"""
import codecs
import json
import os
import sys
import types
import uuid
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.ai_core import streaming
from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.conversations import context, service
from apps.ai_core.models import AIConversation, AIMessage
from apps.ai_core.providers.exceptions import ProviderTimeout, ProviderUnavailable
from apps.ai_core.providers.openai_responses import OpenAIResponsesProvider, StreamOutcome
from apps.ai_core.tests.ledger_fakes import fake_reservation
from apps.ai_ledger.call_authorization import UnauthorizedPaidCall, require_authorized_paid_call

ROOT = Path(__file__).resolve().parents[3]
BASE = dict(VORNEQ_ENV="development", VORNEQ_AI_CORE_ENABLED=True, VORNEQ_AI_PHASE_B_ENABLED=True,
            VORNEQ_AI_PHASE_C_ENABLED=True, VORNEQ_GLOBAL_AI_ENABLED=True,
            VORNEQ_AI_CONVERSATIONS_ENABLED=True, VORNEQ_AI_CONVERSATIONS_ACTOR_POLICY="authenticated",
            VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=True, VORNEQ_AI_CHAT_STREAMING_ENABLED=True,
            VORNEQ_AI_EMERGENCY_STOP=False)
QUESTION = "What is quantum computing?"
COMPLETED = StreamOutcome("completed", None, (120, 340))


class FakeStreamProvider:
    """Inner provider double: same streaming contract as OpenAIResponsesProvider."""

    model = "mock-only"
    max_output_tokens = 8192

    def __init__(self, deltas, final=COMPLETED, on_step=None, raise_at=None, exc=None, guard=False):
        self.deltas, self.final, self.on_step = list(deltas), final, on_step
        self.raise_at, self.exc, self.guard = raise_at, exc, guard
        self.calls, self.closed, self.last_usage, self.request_sent = 0, False, None, False
        self.authorized_after_first = None

    def stream_knowledge_instructions(self, language):
        return "fixed instructions"

    def check_context_budget(self, input_bytes):
        return None

    def stream_knowledge(self, *, question, language, prior_turns=()):
        self.calls += 1
        if self.guard:
            require_authorized_paid_call("text")
        if self.raise_at == -1:
            raise self.exc
        self.request_sent = True
        try:
            for index, delta in enumerate(self.deltas):
                if self.on_step:
                    self.on_step(index)
                if self.raise_at == index:
                    raise self.exc
                yield ("delta", delta)
                if self.guard and index == 0:
                    try:
                        require_authorized_paid_call("text")
                        self.authorized_after_first = True
                    except UnauthorizedPaidCall:
                        self.authorized_after_first = False
            self.last_usage = self.final.usage
            yield ("final", self.final)
        finally:
            self.closed = True


def close_response(response):
    """Wie WSGI bei Verbindungsabbruch: den Antwort-Iterator schließen.

    Im Test-Client ist das der ``closing_iterator_wrapper``, der dabei – wie Djangos
    Test-Client selbst – das Schließen der DB-Verbindung über ``request_finished``
    unterdrückt (sonst würde die TestCase-Transaktion geschlossen)."""
    iterator = getattr(response, "_iterator", None)
    if iterator is not None and hasattr(iterator, "close"):
        iterator.close()


def frames(raw):
    events = []
    for block in raw.decode("utf-8").split("\n\n"):
        data = [line[5:].strip() for line in block.split("\n") if line.startswith("data:")]
        if data:
            events.append(json.loads("".join(data)))
    return events


@override_settings(**BASE)
class StreamingFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(username=f"s{uuid.uuid4().hex[:8]}", email="s@example.invalid",
                                             password="x-1!Aa-long")
        self.other = User.objects.create_user(username=f"o{uuid.uuid4().hex[:8]}", email="o@example.invalid",
                                              password="x-1!Aa-long")
        self.client.force_login(self.user)
        self.conversation = AIConversation.objects.create(owner=self.user, language="en")
        env = patch.dict(os.environ, {"VORNEQ_AI_PHASE_B_MODEL": "mock-only"})
        env.start()
        self.addCleanup(env.stop)

    def url(self, conversation=None):
        return reverse("ai_core:conversation-messages-stream", args=[(conversation or self.conversation).id])

    def post(self, provider, question=QUESTION, client=None, close_after=None):
        with patch("apps.ai_core.views_global.paid_text_provider", return_value=provider):
            response = (client or self.client).post(self.url(), data=json.dumps({"question": question, "language": "en"}),
                                                     content_type="application/json")
            if not getattr(response, "streaming", False):
                return response, None
            chunks = []
            iterator = iter(response.streaming_content)
            for index, chunk in enumerate(iterator):
                chunks.append(chunk)
                if close_after is not None and index + 1 >= close_after:
                    close_response(response)  # Browser weg: WSGI schließt den Iterator
                    break
            else:
                close_response(response)
            return response, b"".join(chunks)

    def assistant(self):
        return AIMessage.objects.filter(conversation=self.conversation, role=AIMessage.ROLE_ASSISTANT).latest("sequence")

    # ------------------------------------------------------------ success
    def test_stream_success_protocol_and_persistence(self):
        provider = FakeStreamProvider(["Quantum ", "computing ", "uses **qubits**."])
        response, raw = self.post(provider)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/event-stream"))
        self.assertEqual(response["X-Accel-Buffering"], "no")
        events = frames(raw)
        types_ = [e["type"] for e in events]
        self.assertEqual(types_[0], "response.created")
        self.assertIn("response.started", types_)
        self.assertEqual(types_[-2:], ["response.usage", "response.completed"])
        self.assertEqual([e["sequence_number"] for e in events], list(range(1, len(events) + 1)))
        message = self.assistant()
        self.assertTrue(all(e["response_id"] == str(message.id) for e in events))
        self.assertTrue(all(e["conversation_id"] == str(self.conversation.id) for e in events))
        final = events[-1]["payload"]["response"]
        self.assertEqual((final["mode"], final["answer"], final["persisted"]),
                         ("model_knowledge", "Quantum computing uses **qubits**.", True))
        self.assertEqual((message.status, message.content), (AIMessage.STATUS_COMPLETED, final["answer"]))
        self.assertEqual(provider.calls, 1)
        self.assertTrue(provider.closed)
        turns = context.prior_turns(self.conversation, question="next")
        self.assertEqual(turns[-1]["content"], final["answer"])

    def test_multilingual_and_utf8_boundaries(self):
        cases = {"fa": ["هوش مصنوعی", "‌ها ", "متن را ", "تولید می‌کنند."],
                 "de": ["Größere ", "Sprachmodelle ", "über Kontext ", "äöü 😀"],
                 "en": ["Mixed فارسی ", "and English ", "✅"]}
        for language, deltas in cases.items():
            with self.subTest(language=language):
                AIMessage.objects.all().delete()
                self.conversation.message_count = 0
                self.conversation.save()
                _response, raw = self.post(FakeStreamProvider(deltas))
                decoder = codecs.getincrementaldecoder("utf-8")()
                text = "".join(decoder.decode(raw[i:i + 1]) for i in range(len(raw)))  # Byte für Byte
                self.assertEqual(text, raw.decode("utf-8"))
                self.assertEqual(self.assistant().content, "".join(deltas))

    @override_settings(VORNEQ_AI_CHAT_BUDGET_MODEL="mock-only", VORNEQ_AI_CHAT_MODEL_CONTEXT_TOKENS="65536",
                       VORNEQ_AI_CHAT_INPUT_TOKEN_BUDGET="8192", VORNEQ_AI_CHAT_OUTPUT_TOKEN_BUDGET="8192")
    def test_long_answer_is_chunked_and_checkpointed_sparingly(self):
        deltas = ["x" * 50] * 600 + ["y" * 5000]
        with patch("apps.ai_core.streaming._checkpoint", wraps=streaming._checkpoint) as checkpoint:
            _response, raw = self.post(FakeStreamProvider(deltas))
        events = frames(raw)
        self.assertTrue(all(len(e["payload"].get("text", "")) <= streaming.MAX_DELTA_CHARS for e in events))
        self.assertLess(checkpoint.call_count, 40)          # nie pro Token
        self.assertEqual(len(self.assistant().content), 600 * 50 + 5000)

    def test_answer_bound_without_policy_stops_as_incomplete(self):
        _response, raw = self.post(FakeStreamProvider(["z" * 600, "z" * 600]))
        self.assertEqual(frames(raw)[-1]["type"], "response.incomplete")
        message = self.assistant()
        self.assertEqual((message.error_code, len(message.content)), ("output_limit_reached", 600))

    # --------------------------------------------------------------- stop
    def test_stop_during_generation_keeps_partial_and_marks_cancelled(self):
        state = {}

        def on_step(index):
            if index == 3:
                state["id"] = self.assistant().id
                self.assertEqual(streaming.request_cancel(self.user, state["id"]), ("cancel_requested", None))

        with patch("apps.ai_core.streaming.CHECKPOINT_CHARS", 1):
            _response, raw = self.post(FakeStreamProvider(["a ", "b ", "c ", "d ", "e ", "f "], on_step=on_step))
        events = frames(raw)
        self.assertEqual(events[-1]["type"], "response.cancelled")
        self.assertEqual(events[-1]["payload"]["cost"], "uncertain")
        message = self.assistant()
        self.assertEqual((message.status, message.error_code), (AIMessage.STATUS_FAILED, "cancelled"))
        self.assertTrue(message.content.startswith("a b c"))
        self.assertNotIn("f", message.content)
        self.assertEqual(context.prior_turns(self.conversation, question="x"), ())   # nie als vollständig
        body, status = service.stored_response(message, self.conversation)
        self.assertEqual((body["error"], body["complete"], status), ("cancelled", False, 499))
        self.assertFalse(service.serialize_message(message)["complete"])

    def test_stop_before_first_token_and_after_completion(self):
        def cancel_first(index):
            if index == 0:
                streaming.request_cancel(self.user, self.assistant().id)
        with patch("apps.ai_core.streaming.CHECKPOINT_CHARS", 1):
            _response, raw = self.post(FakeStreamProvider(["one ", "two"], on_step=cancel_first))
        self.assertEqual(frames(raw)[-1]["type"], "response.cancelled")
        self.assertEqual(self.assistant().content, "one ")
        _response, _raw = self.post(FakeStreamProvider(["done"]))
        done = self.assistant()
        self.assertEqual(streaming.request_cancel(self.user, done.id), ("already_final", AIMessage.STATUS_COMPLETED))
        self.assertEqual(AIMessage.objects.get(pk=done.id).status, AIMessage.STATUS_COMPLETED)

    def test_cancel_vs_complete_race_completed_wins_when_no_checkpoint_saw_flag(self):
        def cancel_last(index):
            if index == 1:
                streaming.request_cancel(self.user, self.assistant().id)
        with patch("apps.ai_core.streaming.CHECKPOINT_CHARS", 10 ** 9), \
                patch("apps.ai_core.streaming.CHECKPOINT_SECONDS", 10 ** 9):
            _response, raw = self.post(FakeStreamProvider(["a", "b"], on_step=cancel_last))
        self.assertEqual(frames(raw)[-1]["type"], "response.completed")
        message = self.assistant()
        self.assertEqual((message.status, message.error_code), (AIMessage.STATUS_COMPLETED, "model_knowledge"))

    def test_cancel_endpoint_authorization_isolation_idempotency_and_csrf(self):
        pending = AIMessage.objects.create(conversation=self.conversation, sequence=2, role=AIMessage.ROLE_ASSISTANT,
                                           status=AIMessage.STATUS_PENDING)
        url = reverse("ai_core:conversation-message-cancel", args=[self.conversation.id, pending.id])
        first = self.client.post(url, data="{}", content_type="application/json")
        again = self.client.post(url, data="{}", content_type="application/json")
        self.assertEqual((first.status_code, first.json()), (202, {"status": "cancel_requested", "confirmed": False}))
        self.assertEqual(again.status_code, 202)
        self.assertEqual(AIMessage.objects.get(pk=pending.id).error_code, streaming.CANCEL_FLAG)
        intruder = Client()
        intruder.force_login(self.other)
        self.assertEqual(intruder.post(url, data="{}", content_type="application/json").status_code, 404)
        foreign = AIConversation.objects.create(owner=self.other)
        wrong = reverse("ai_core:conversation-message-cancel", args=[foreign.id, pending.id])
        self.assertEqual(self.client.post(wrong, data="{}", content_type="application/json").status_code, 404)
        self.assertEqual(Client().post(url, data="{}", content_type="application/json").status_code, 401)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(url, data="{}", content_type="application/json").status_code, 403)

    def test_cross_user_stream_is_refused(self):
        foreign = AIConversation.objects.create(owner=self.other)
        provider = FakeStreamProvider(["x"])
        with patch("apps.ai_core.views_global.paid_text_provider", return_value=provider):
            response = self.client.post(self.url(foreign), data=json.dumps({"question": QUESTION, "language": "en"}),
                                        content_type="application/json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(Client().post(self.url(), data="{}", content_type="application/json").status_code, 401)

    # ----------------------------------------------------------- recovery
    def test_browser_disconnect_drains_and_persists_without_second_call(self):
        provider = FakeStreamProvider(["part one ", "part two ", "part three"])
        _response, raw = self.post(provider, close_after=2)          # nach created + started/delta
        self.assertLessEqual(len(frames(raw)), 3)
        message = self.assistant()
        self.assertEqual((message.status, message.content), (AIMessage.STATUS_COMPLETED,
                                                              "part one part two part three"))
        self.assertEqual(provider.calls, 1)
        detail = self.client.get(reverse("ai_core:conversation-detail", args=[self.conversation.id])).json()
        stored = [m for m in detail["messages"] if m["role"] == "assistant"][-1]
        self.assertEqual((stored["status"], stored["complete"]), ("completed", True))

    def test_checkpoint_is_visible_while_running_and_survives_interruption(self):
        seen = {}

        def look(index):
            if index == 2:
                seen["content"] = self.assistant().content
                seen["finalized"] = service.serialize_message(self.assistant())["finalized"]
        with patch("apps.ai_core.streaming.CHECKPOINT_CHARS", 1):
            self.post(FakeStreamProvider(["alpha ", "beta ", "gamma"], on_step=look))
        self.assertEqual(seen, {"content": "alpha beta ", "finalized": False})

    def test_deadline_output_limit_provider_failure_timeout_and_guard(self):
        scenarios = [
            ("deadline", FakeStreamProvider(["a", "b"]), {"STREAM_DEADLINE_SECONDS": -1},
             "response.incomplete", (AIMessage.STATUS_FAILED, "stream_timeout")),
            ("limit", FakeStreamProvider(["a"], final=StreamOutcome("incomplete", "max_output_tokens", (1, 2))), {},
             "response.incomplete", (AIMessage.STATUS_FAILED, "output_limit_reached")),
            ("failure", FakeStreamProvider(["a", "b"], raise_at=1, exc=ProviderUnavailable("x")), {},
             "response.failed", (AIMessage.STATUS_FAILED, "provider_unavailable")),
            ("timeout", FakeStreamProvider(["a", "b"], raise_at=1, exc=ProviderTimeout("x")), {},
             "response.failed", (AIMessage.STATUS_UNCERTAIN, "provider_timeout")),
            ("links", FakeStreamProvider(["see https://example.com/x"]), {},
             "response.failed", (AIMessage.STATUS_FAILED, "provider_unavailable")),
        ]
        for name, provider, patches, last, expected in scenarios:
            cache.clear()   # lokale Entwicklungs-Quote je Szenario zurücksetzen
            with self.subTest(name), patch.multiple("apps.ai_core.streaming", **patches) if patches else _null():
                _response, raw = self.post(provider)
                self.assertEqual(frames(raw)[-1]["type"], last)
                message = self.assistant()
                self.assertEqual((message.status, message.error_code), expected)
                self.assertNotEqual(message.status, AIMessage.STATUS_COMPLETED)

    def test_emergency_stop_during_and_before_streaming(self):
        with patch("apps.ai_core.streaming.CHECKPOINT_CHARS", 1), \
                patch("apps.ai_ledger.service.emergency_stop_active", return_value=True):
            _response, raw = self.post(FakeStreamProvider(["a", "b", "c"]))
        self.assertEqual(frames(raw)[-1]["payload"]["error"], "emergency_stop")
        self.assertEqual(self.assistant().error_code, "emergency_stop")
        provider = FakeStreamProvider(["x"])
        with override_settings(VORNEQ_AI_EMERGENCY_STOP=True):
            response, _raw = self.post(provider)
        self.assertEqual(response.status_code, 404)        # global_ai_available() == False
        self.assertEqual(provider.calls, 0)

    def test_ledger_refusal_before_first_byte_is_json(self):
        from apps.ai_ledger.service import LedgerUnavailable
        provider = FakeStreamProvider(["x"])
        with patch("apps.ai_core.views_global.require_paid_text_ledger", side_effect=LedgerUnavailable("x")):
            response, _raw = self.post(provider)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["reason"], "LEDGER_UNAVAILABLE")
        self.assertEqual(provider.calls, 0)
        self.assertEqual(self.assistant().status, AIMessage.STATUS_FAILED)

    def test_feature_gate_and_grounded_route(self):
        with override_settings(VORNEQ_AI_CHAT_STREAMING_ENABLED=False):
            response, _raw = self.post(FakeStreamProvider(["x"]))
            self.assertEqual(response.status_code, 404)
        grounded = {"mode": "grounded_draft", "answer": "Belegt.", "citations": [], "verified": False,
                    "language": "en", "model_status": "generated", "grounded_status": "proposed", "error_code": ""}
        with override_settings(VORNEQ_AI_GENERAL_KNOWLEDGE_ENABLED=False), \
                patch("apps.ai_core.views_streaming.run_global_pipeline", return_value=(grounded, 200, {})) as run:
            _response, raw = self.post(FakeStreamProvider(["never"]))
        self.assertEqual([e["type"] for e in frames(raw)], ["response.created", "response.completed"])
        self.assertEqual(run.call_count, 1)

    def test_replay_returns_json_without_provider_call(self):
        provider = FakeStreamProvider(["x"])
        with patch("apps.ai_core.request_recovery.enabled", return_value=True), \
                patch("apps.ai_core.request_recovery.claim",
                      return_value={"status": "completed", "http_status": 200, "response": {"mode": "cached"}}):
            response, _raw = self.post(provider)
        self.assertEqual((response.status_code, response.json()), (200, {"mode": "cached"}))
        self.assertEqual(provider.calls, 0)

    def test_non_streaming_message_view_unchanged(self):
        knowledge = {"mode": "model_knowledge", "answer": "ok", "language": "en", "citations": [],
                     "verified": False, "model_status": "generated", "grounded_status": "model_knowledge_unverified",
                     "error_code": "", "route": "general_public"}
        with patch("apps.ai_core.views_conversations.run_global_pipeline", return_value=(knowledge, 200, {})):
            response = self.client.post(reverse("ai_core:conversation-messages", args=[self.conversation.id]),
                                        data=json.dumps({"question": QUESTION, "language": "en"}),
                                        content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "ok")


class _null:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class LedgerStreamingTests(SimpleTestCase):
    def wrapped(self, inner):
        return BudgetedProvider(inner, actor_id=7)

    def run_stream(self, wrapped, stop_after=None):
        items = []
        generator = wrapped.stream_knowledge(question=QUESTION, language="en")
        for item in generator:
            items.append(item)
            if stop_after is not None and len(items) >= stop_after:
                generator.close()
                break
        return items

    def test_reserve_once_settle_with_usage_and_authorization_only_for_first_step(self):
        inner = FakeStreamProvider(["a", "b"], guard=True)
        with patch("apps.ai_core.budgeted_provider.ledger.reserve", return_value=fake_reservation()) as reserve, \
                patch("apps.ai_core.budgeted_provider.ledger.settle") as settle, \
                patch("apps.ai_core.budgeted_provider.ledger.release") as release:
            items = self.run_stream(self.wrapped(inner))
        self.assertEqual(items[-1][0], "final")
        self.assertEqual(reserve.call_count, 1)
        self.assertEqual(reserve.call_args.kwargs["max_output_tokens"], 8192)
        settle.assert_called_once()
        self.assertEqual(settle.call_args.kwargs, {"usage": (120, 340), "outcome": "completed"})
        release.assert_not_called()
        self.assertIs(inner.authorized_after_first, False)    # keine Freigabe während Pausen
        with self.assertRaises(UnauthorizedPaidCall):
            require_authorized_paid_call("text")

    def test_stop_settles_uncertain_never_zero(self):
        inner = FakeStreamProvider(["a", "b", "c"])
        with patch("apps.ai_core.budgeted_provider.ledger.reserve", return_value=fake_reservation()), \
                patch("apps.ai_core.budgeted_provider.ledger.settle") as settle, \
                patch("apps.ai_core.budgeted_provider.ledger.release") as release:
            self.run_stream(self.wrapped(inner), stop_after=1)
        self.assertEqual(settle.call_args.kwargs, {"usage": None, "outcome": "stream_closed"})
        release.assert_not_called()
        self.assertTrue(inner.closed)

    def test_not_sent_is_released_and_errors_settle_once(self):
        inner = FakeStreamProvider([], raise_at=-1, exc=ProviderUnavailable("no key"))
        with patch("apps.ai_core.budgeted_provider.ledger.reserve", return_value=fake_reservation()), \
                patch("apps.ai_core.budgeted_provider.ledger.settle") as settle, \
                patch("apps.ai_core.budgeted_provider.ledger.release") as release:
            with self.assertRaises(ProviderUnavailable):
                self.run_stream(self.wrapped(inner))
        release.assert_called_once()
        settle.assert_not_called()
        inner = FakeStreamProvider(["a", "b"], raise_at=1, exc=ProviderTimeout("t"))
        with patch("apps.ai_core.budgeted_provider.ledger.reserve", return_value=fake_reservation()), \
                patch("apps.ai_core.budgeted_provider.ledger.settle") as settle:
            with self.assertRaises(ProviderTimeout):
                self.run_stream(self.wrapped(inner))
        self.assertEqual(settle.call_args.kwargs, {"usage": None, "outcome": "ProviderTimeout"})

    def test_reservation_refusal_means_no_provider_call(self):
        from apps.ai_ledger.service import EmergencyStop
        inner = FakeStreamProvider(["a"])
        with patch("apps.ai_core.budgeted_provider.ledger.reserve", side_effect=EmergencyStop("stop")):
            with self.assertRaises(EmergencyStop):
                self.run_stream(self.wrapped(inner))
        self.assertEqual(inner.calls, 0)


class ProviderStreamingAdapterTests(SimpleTestCase):
    """Adapter mit Fake-SDK: kein Netzwerk, keine echten Schlüssel."""

    def fake_sdk(self, events, created):
        class Stream:
            def __init__(self):
                self.closed = False

            def __iter__(self):
                return iter(events)

            def close(self):
                self.closed = True

        stream = Stream()

        class Responses:
            def create(self, **kwargs):
                created.append(kwargs)
                return stream

        class Client:
            def __init__(self, **kwargs):
                self.responses = Responses()

        class _Err(Exception):
            pass

        module = types.SimpleNamespace(OpenAI=Client, APITimeoutError=_Err, APIConnectionError=_Err,
                                       APIStatusError=_Err, APIError=_Err)
        return module, stream

    def provider(self):
        return OpenAIResponsesProvider(model="mock-only", timeout_s=5, max_output_tokens=2048,
                                       response_v3_enabled=False, response_stage2_enabled=False)

    @override_settings(VORNEQ_ENV="development")
    def test_requires_ledger_reservation_before_any_client(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-only"}), \
                patch.dict(sys.modules, {"openai": None}):
            with self.assertRaises(ProviderUnavailable):
                next(self.provider().stream_knowledge(question=QUESTION, language="en"))

    @override_settings(VORNEQ_ENV="development")
    def test_maps_sdk_events_and_closes_stream(self):
        from apps.ai_ledger.call_authorization import authorized_paid_call
        ev = types.SimpleNamespace
        usage = ev(input_tokens=5, output_tokens=7)
        events = [ev(type="response.created"), ev(type="response.output_text.delta", delta="Hal"),
                  ev(type="response.output_text.delta", delta="lo"),
                  ev(type="response.completed", response=ev(usage=usage, incomplete_details=None))]
        created = []
        module, stream = self.fake_sdk(events, created)
        provider = self.provider()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-only"}), \
                patch.dict(sys.modules, {"openai": module}):
            generator = provider.stream_knowledge(question=QUESTION, language="en")
            with authorized_paid_call(fake_reservation(), kind="text"):
                first = next(generator)
            items = [first] + list(generator)
        self.assertEqual([i for i in items if i[0] == "delta"], [("delta", "Hal"), ("delta", "lo")])
        self.assertEqual(items[-1], ("final", StreamOutcome("completed", None, (5, 7))))
        self.assertTrue(created[0]["stream"])
        self.assertEqual(created[0]["max_output_tokens"], 2048)
        self.assertNotIn("text_format", created[0])
        self.assertTrue(stream.closed)
        self.assertTrue(provider.request_sent)


class ProtocolTests(SimpleTestCase):
    def test_encoder_fields_sequence_and_limits(self):
        encoder = streaming.EventEncoder(request_id=None, conversation_id=uuid.uuid4(), response_id=uuid.uuid4())
        first = frames(encoder.encode("response.created", {"protocol": 1}))[0]
        second = frames(encoder.encode("heartbeat"))[0]
        self.assertEqual((first["sequence_number"], second["sequence_number"]), (1, 2))
        for key in ("type", "request_id", "conversation_id", "response_id", "timestamp", "payload"):
            self.assertIn(key, first)
        with self.assertRaises(ValueError):
            encoder.encode("response.unknown")
        with self.assertRaises(ValueError):
            encoder.encode("response.delta", {"text": "x" * (streaming.MAX_EVENT_BYTES + 1)})
        chunks = list(encoder.deltas("ab" * streaming.MAX_DELTA_CHARS))
        self.assertEqual(len(chunks), 2)

    def test_gates_are_independent_and_default_off(self):
        with override_settings(VORNEQ_ENV="production", VORNEQ_AI_CHAT_STREAMING_ENABLED=True,
                               VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED=False):
            self.assertFalse(streaming.enabled())
        with override_settings(VORNEQ_ENV="production", VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED=True):
            self.assertTrue(streaming.enabled())
        with override_settings(VORNEQ_ENV="staging", VORNEQ_AI_CHAT_STREAMING_ENABLED=False,
                               VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED=True):
            self.assertFalse(streaming.enabled())
        with override_settings(VORNEQ_ENV="prod", VORNEQ_AI_CHAT_STREAMING_ENABLED=True):
            self.assertFalse(streaming.enabled())
        from django.conf import settings
        self.assertIs(settings.VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED, False)

    def test_report_streaming_section_without_secrets(self):
        out = StringIO()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-never-print-v703"}):
            call_command("ai_gateway_report", "--json", stdout=out)
        self.assertNotIn("sk-never-print-v703", out.getvalue())
        section = json.loads(out.getvalue())["streaming"]
        self.assertFalse(section["enabled"])
        self.assertEqual(section["provider_streaming_capability"]["openai-text"],
                         "IMPLEMENTED (Responses API stream=True)")


@override_settings(**BASE)
class FrontendStreamingTests(TestCase):
    def test_page_and_client_contract(self):
        user = get_user_model().objects.create_user(username="v703ui", email="ui@example.invalid",
                                                    password="x-1!Aa-long")
        self.client.force_login(user)
        for language in ("fa", "de", "en"):
            html = self.client.get(reverse("ai_core:chat") + f"?lang={language}").content.decode()
            self.assertIn('data-vq-streaming="true"', html)
            self.assertIn("data-vq-chat-stop", html)
            self.assertIn("data-vq-stream-cancelled=", html)
        js = (ROOT / "assets" / "js" / "phase-c-chat.js").read_text(encoding="utf-8")
        for needle in ('new TextDecoder("utf-8")', "{ stream: true }", "event.sequence_number <= lastSequence",
                       "nearBottom()", "conv.cancelUrl(current.responseId)", "textNode.textContent = partial",
                       "vq-chat__message--partial", "highlightCode(", "addCodeCopy("):
            self.assertIn(needle, js)
        start = js.index("// ------------------------------------------------------------ V7-03 streaming")
        self.assertNotIn("innerHTML", js[start:])
        self.assertNotIn("insertAdjacentHTML", js)
        from apps.ai_core.chat_strings import chat_labels
        stops = {chat_labels(code)["stream_stop"] for code in ("fa", "de", "en")}
        self.assertEqual(len(stops), 3)
