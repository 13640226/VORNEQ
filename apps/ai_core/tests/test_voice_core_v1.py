"""Voice core foundation tests: synthetic data, mock provider, no network, no paid calls."""
import json
import sys
import threading
import types
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.ai_core.models import AIConversation
from apps.ai_core.voice import config as voice_config
from apps.ai_core.voice import store as voice_store
from apps.ai_core.voice.provider import MockVoiceProvider, VoiceProviderBlocked, get_provider
from apps.ai_core.voice.store import EventLimit, SessionBusy, StoreFull, VoiceSessionStore


def flags(user_ids, **extra):
    base = {
        "VORNEQ_ENV": "development",
        "VORNEQ_AI_VOICE_ENABLED": True,
        "VORNEQ_AI_VOICE_PROVIDER": "mock",
        "VORNEQ_AI_VOICE_PAID_CALLS_ENABLED": False,
        "VORNEQ_AI_VOICE_SESSION_TTL_SECONDS": 120,
        "VORNEQ_AI_VOICE_ALLOWED_USER_IDS": ",".join(str(i) for i in user_ids),
        "VORNEQ_AI_EMERGENCY_STOP": False,
    }
    base.update(extra)
    return base


class VoiceBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        model = get_user_model()
        cls.alice = model.objects.create_user(username="voice-alice", password="safe-test")
        cls.bob = model.objects.create_user(username="voice-bob", password="safe-test")
        cls.mallory = model.objects.create_user(username="voice-mallory", password="safe-test")

    def setUp(self):
        voice_store.reset_store()
        self.addCleanup(voice_store.reset_store)
        self.sdk_calls = []
        module = types.ModuleType("openai")

        def forbidden(*args, **kwargs):
            self.sdk_calls.append("OpenAI")
            raise AssertionError("PAID_SDK_CONSTRUCTED")

        module.OpenAI = forbidden
        sdk = patch.dict(sys.modules, {"openai": module})
        sdk.start()
        self.addCleanup(sdk.stop)
        sock = patch("socket.socket.connect", side_effect=AssertionError("NETWORK_USED"))
        sock.start()
        self.addCleanup(sock.stop)
        self.ledger = [patch("apps.ai_ledger.service." + name, side_effect=AssertionError("LEDGER_CALLED"))
                       for name in ("reserve", "reserve_with_config", "reserve_prepaid_image", "settle", "release")]
        for item in self.ledger:
            item.start()
            self.addCleanup(item.stop)
        self.client.force_login(self.alice)

    def tearDown(self):
        self.assertEqual(self.sdk_calls, [])

    def post(self, name, data=None, *, client=None, args=None, raw=None):
        client = client or self.client
        body = raw if raw is not None else json.dumps(data if data is not None else {})
        return client.post(reverse("ai_core:" + name, args=args or []), body, content_type="application/json")

    def create(self, data=None, **kwargs):
        return self.post("voice-session-create", data, **kwargs)

    def client_for(self, user, **kwargs):
        client = Client(**kwargs)
        client.force_login(user)
        return client

    def conversation(self, owner=None, **fields):
        return AIConversation.objects.create(owner=owner or self.alice, title="voice test", **fields)


class ConfigFailClosedTests(VoiceBase):
    def test_default_is_unavailable(self):
        self.assertEqual(self.create().status_code, 404)

    def test_each_misconfiguration_disables_voice(self):
        good = flags([self.alice.pk])
        bad = [
            {"VORNEQ_ENV": "production"}, {"VORNEQ_ENV": "unknown"}, {"VORNEQ_ENV": None},
            {"VORNEQ_AI_VOICE_ENABLED": "true"}, {"VORNEQ_AI_VOICE_ENABLED": 1}, {"VORNEQ_AI_VOICE_ENABLED": False},
            {"VORNEQ_AI_VOICE_PROVIDER": "openai"}, {"VORNEQ_AI_VOICE_PROVIDER": ""},
            {"VORNEQ_AI_VOICE_PAID_CALLS_ENABLED": True}, {"VORNEQ_AI_VOICE_PAID_CALLS_ENABLED": "yes"},
            {"VORNEQ_AI_VOICE_SESSION_TTL_SECONDS": 29}, {"VORNEQ_AI_VOICE_SESSION_TTL_SECONDS": 3601},
            {"VORNEQ_AI_VOICE_SESSION_TTL_SECONDS": "300"}, {"VORNEQ_AI_VOICE_SESSION_TTL_SECONDS": True},
            {"VORNEQ_AI_VOICE_SESSION_TTL_SECONDS": 60.5},
            {"VORNEQ_AI_VOICE_ALLOWED_USER_IDS": ""}, {"VORNEQ_AI_VOICE_ALLOWED_USER_IDS": "abc"},
            {"VORNEQ_AI_VOICE_ALLOWED_USER_IDS": "1,1"}, {"VORNEQ_AI_VOICE_ALLOWED_USER_IDS": "0"},
            {"VORNEQ_AI_VOICE_ALLOWED_USER_IDS": "1," * 60 + "2"},
        ]
        for override in bad:
            with override_settings(**{**good, **override}):
                self.assertIsNone(voice_config.load_config(), override)
        with override_settings(**good):
            self.assertIsNotNone(voice_config.load_config())

    def test_ttl_bounds_are_inclusive(self):
        for ttl in (30, 3600):
            with override_settings(**flags([self.alice.pk], VORNEQ_AI_VOICE_SESSION_TTL_SECONDS=ttl)):
                self.assertEqual(voice_config.load_config().ttl_seconds, ttl)

    def test_paid_provider_cannot_be_selected(self):
        with override_settings(VORNEQ_AI_VOICE_PROVIDER="openai"):
            with self.assertRaises(VoiceProviderBlocked):
                get_provider()
        self.assertFalse(MockVoiceProvider.paid)

    def test_namespace_is_nested(self):
        self.assertEqual(voice_config.NAMESPACE, "ai_core:ai_core_voice")
        self.assertEqual(voice_store.user_key(7), "ai_core:ai_core_voice:session:7")


class AuthorizationTests(VoiceBase):
    def test_anonymous_gets_401(self):
        with override_settings(**flags([self.alice.pk])):
            self.assertEqual(self.create(client=Client()).status_code, 401)

    def test_user_not_on_allowlist_gets_404_same_as_disabled(self):
        with override_settings(**flags([self.alice.pk])):
            denied = self.create(client=self.client_for(self.mallory))
            self.assertEqual(denied.status_code, 404)
            self.assertEqual(denied.json(), {"error": "unavailable"})
        self.assertEqual(self.create().json(), {"error": "unavailable"})

    def test_csrf_is_enforced(self):
        with override_settings(**flags([self.alice.pk])):
            client = self.client_for(self.alice, enforce_csrf_checks=True)
            self.assertEqual(self.create(client=client).status_code, 403)

    def test_get_is_not_allowed(self):
        with override_settings(**flags([self.alice.pk])):
            self.assertEqual(self.client.get(reverse("ai_core:voice-session-create")).status_code, 405)


@override_settings()
class SessionTests(VoiceBase):
    def setUp(self):
        super().setUp()
        patcher = override_settings(**flags([self.alice.pk, self.bob.pk]))
        patcher.enable()
        self.addCleanup(patcher.disable)

    def test_create_session(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["provider"], "mock")
        self.assertIs(body["mock"], True)
        self.assertEqual(body["expires_in_seconds"], 120)
        self.assertEqual(str(uuid.UUID(body["session_id"])), body["session_id"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_invalid_create_payloads(self):
        for data in ({"x": 1}, {"conversation_id": 5}, {"conversation_id": "nope"},
                     {"conversation_id": str(uuid.uuid4()).upper()}, {"conversation_id": None}):
            self.assertEqual(self.create(data).status_code, 400, data)
        for raw in ("not json", "[1]", '"s"', "\xff"):
            self.assertEqual(self.create(raw=raw).status_code, 400, raw)

    def test_oversized_payload_is_rejected(self):
        raw = json.dumps({"conversation_id": "x" * (voice_config.MAX_BODY_BYTES + 10)})
        self.assertEqual(self.create(raw=raw).status_code, 413)

    def test_own_conversation_is_accepted(self):
        conversation = self.conversation()
        self.assertEqual(self.create({"conversation_id": str(conversation.pk)}).status_code, 201)

    def test_foreign_missing_and_trashed_conversations_are_404(self):
        foreign = self.conversation(owner=self.bob)
        trashed = self.conversation(deleted_at=timezone.now())
        for pk in (foreign.pk, trashed.pk, uuid.uuid4()):
            self.assertEqual(self.create({"conversation_id": str(pk)}).status_code, 404)

    def test_archived_conversation_is_denied(self):
        archived = self.conversation(archived_at=timezone.now())
        response = self.create({"conversation_id": str(archived.pk)})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"error": "conversation_archived"})
        self.assertEqual(voice_store.get_store().clear(), 0)

    def test_second_session_is_429_with_consistent_retry_after(self):
        self.assertEqual(self.create().status_code, 201)
        second = self.create()
        self.assertEqual(second.status_code, 429)
        seconds = second.json()["retry_after_seconds"]
        self.assertEqual(second["Retry-After"], str(seconds))
        self.assertTrue(1 <= seconds <= 120)
        self.assertEqual(self.create(client=self.client_for(self.bob)).status_code, 201)

    def test_close_then_new_session_allowed_and_second_close_is_404(self):
        sid = self.create().json()["session_id"]
        self.assertEqual(self.post("voice-session-close", args=[sid]).json(), {"closed": True})
        self.assertEqual(self.post("voice-session-close", args=[sid]).status_code, 404)
        self.assertEqual(self.create().status_code, 201)

    def test_other_user_cannot_close_or_use_session(self):
        sid = self.create().json()["session_id"]
        bob = self.client_for(self.bob)
        self.assertEqual(self.post("voice-session-close", args=[sid], client=bob).status_code, 404)
        self.assertEqual(self.post("voice-event", {"type": "text", "text": "hi"}, args=[sid], client=bob).status_code, 404)
        self.assertEqual(self.post("voice-event", {"type": "text", "text": "hi"}, args=[sid]).status_code, 200)

    def test_session_expires_after_ttl(self):
        clock = {"now": 1000.0}
        with patch("apps.ai_core.voice.store.time.monotonic", lambda: clock["now"]):
            sid = self.create().json()["session_id"]
            clock["now"] += 119
            self.assertEqual(self.post("voice-event", {"type": "text", "text": "a"}, args=[sid]).status_code, 200)
            clock["now"] += 2
            self.assertEqual(self.post("voice-event", {"type": "text", "text": "a"}, args=[sid]).status_code, 404)
            self.assertEqual(self.create().status_code, 201)

    def test_retry_after_counts_down_under_lock(self):
        clock = {"now": 50.0}
        with patch("apps.ai_core.voice.store.time.monotonic", lambda: clock["now"]):
            self.create()
            clock["now"] += 100.2
            self.assertEqual(self.create().json()["retry_after_seconds"], 20)


@override_settings()
class EventTests(VoiceBase):
    def setUp(self):
        super().setUp()
        patcher = override_settings(**flags([self.alice.pk, self.bob.pk]))
        patcher.enable()
        self.addCleanup(patcher.disable)
        self.sid = self.create().json()["session_id"]

    def event(self, data=None, **kwargs):
        return self.post("voice-event", data, args=[self.sid], **kwargs)

    def test_valid_events_use_mock_provider(self):
        text = self.event({"type": "text", "text": "salam"}).json()["event"]
        self.assertEqual(text, {"type": "mock_response", "received": "text", "size": 5, "provider": "mock", "paid": False})
        audio = self.event({"type": "audio_chunk", "size": 4096}).json()["event"]
        self.assertEqual((audio["received"], audio["size"], audio["paid"]), ("audio_chunk", 4096, False))

    def test_invalid_events_are_rejected(self):
        bad = [
            {}, {"type": "video"}, {"type": 5}, {"type": "text"}, {"type": "text", "text": ""},
            {"type": "text", "text": 5}, {"type": "text", "text": "a" * (voice_config.MAX_TEXT_CHARS + 1)},
            {"type": "text", "text": "a", "extra": 1}, {"type": "audio_chunk"},
            {"type": "audio_chunk", "size": "10"}, {"type": "audio_chunk", "size": True},
            {"type": "audio_chunk", "size": 0}, {"type": "audio_chunk", "size": 1.5},
            {"type": "audio_chunk", "size": voice_config.MAX_AUDIO_CHUNK_BYTES + 1},
        ]
        for data in bad:
            self.assertEqual(self.event(data).status_code, 400, data)

    def test_oversized_and_malformed_bodies(self):
        self.assertEqual(self.event(raw="x" * (voice_config.MAX_BODY_BYTES + 1)).status_code, 413)
        self.assertEqual(self.event(raw="{").status_code, 400)

    def test_event_limit(self):
        for _ in range(voice_config.MAX_EVENTS_PER_SESSION):
            self.assertEqual(self.event({"type": "text", "text": "a"}).status_code, 200)
        self.assertEqual(self.event({"type": "text", "text": "a"}).status_code, 429)

    def test_unknown_session_is_404(self):
        response = self.post("voice-event", {"type": "text", "text": "a"}, args=[str(uuid.uuid4())])
        self.assertEqual(response.status_code, 404)

    def test_conversation_archived_mid_session_releases_it(self):
        voice_store.reset_store()
        conversation = self.conversation()
        sid = self.create({"conversation_id": str(conversation.pk)}).json()["session_id"]
        AIConversation.objects.filter(pk=conversation.pk).update(archived_at=timezone.now())
        response = self.post("voice-event", {"type": "text", "text": "a"}, args=[sid])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.post("voice-session-close", args=[sid]).status_code, 404)
        self.assertEqual(self.create().status_code, 201)


class EmergencyStopTests(VoiceBase):
    def test_emergency_stop_blocks_and_cleans_up_sessions(self):
        with override_settings(**flags([self.alice.pk])):
            sid = self.create().json()["session_id"]
            with override_settings(VORNEQ_AI_EMERGENCY_STOP=True):
                blocked = self.post("voice-event", {"type": "text", "text": "a"}, args=[sid])
                self.assertEqual(blocked.status_code, 503)
                self.assertEqual(blocked.json(), {"error": "emergency_stop"})
                self.assertEqual(self.create().status_code, 503)
                self.assertEqual(self.post("voice-session-close", args=[sid]).status_code, 503)
            # Stop lifted: the old session is gone, a fresh one can start.
            self.assertEqual(self.post("voice-event", {"type": "text", "text": "a"}, args=[sid]).status_code, 404)
            self.assertEqual(self.create().status_code, 201)

    def test_non_boolean_stop_value_fails_closed(self):
        with override_settings(**flags([self.alice.pk], VORNEQ_AI_EMERGENCY_STOP="0")):
            self.assertEqual(self.create().status_code, 503)

    def test_stop_does_not_reveal_voice_to_unlisted_users(self):
        with override_settings(**flags([self.alice.pk], VORNEQ_AI_EMERGENCY_STOP=True)):
            self.assertEqual(self.create(client=self.client_for(self.mallory)).status_code, 404)


class ConcurrencyTests(TestCase):
    def run_threads(self, count, target):
        barrier = threading.Barrier(count)
        results, errors = [], []

        def worker(index):
            try:
                barrier.wait(timeout=5)
                results.append(target(index))
            except Exception as exc:  # collected for the assertion
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(errors, [])
        return results

    def test_only_one_session_per_user_under_contention(self):
        store = VoiceSessionStore()

        def attempt(_):
            try:
                return store.acquire(1, None, 60)
            except SessionBusy as busy:
                self.assertGreaterEqual(busy.retry_after, 1)
                return None

        results = self.run_threads(32, attempt)
        self.assertEqual(len([r for r in results if r]), 1)

    def test_release_is_atomic_single_winner(self):
        store = VoiceSessionStore()
        session = store.acquire(1, None, 60)
        results = self.run_threads(32, lambda _: store.release(session.id, 1))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 31)

    def test_store_is_bounded(self):
        store = VoiceSessionStore(max_sessions=5)
        results = self.run_threads(20, lambda i: _try(store, i + 1))
        self.assertEqual(results.count("ok"), 5)
        self.assertEqual(results.count("full"), 15)

    def test_event_counter_is_exact_under_contention(self):
        store = VoiceSessionStore()
        session = store.acquire(1, None, 60)

        def record(_):
            try:
                return store.record_event(session.id, 1) is not None
            except EventLimit:
                return False

        results = self.run_threads(voice_config.MAX_EVENTS_PER_SESSION + 20, record)
        self.assertEqual(results.count(True), voice_config.MAX_EVENTS_PER_SESSION)

    def test_session_record_is_frozen(self):
        session = VoiceSessionStore().acquire(1, None, 60)
        with self.assertRaises(Exception):
            session.user_id = 2


def _try(store, user_id):
    try:
        store.acquire(user_id, None, 60)
        return "ok"
    except StoreFull:
        return "full"


class NoPaidCallTests(VoiceBase):
    def test_full_flow_makes_no_network_ledger_or_sdk_calls(self):
        with override_settings(**flags([self.alice.pk])):
            sid = self.create().json()["session_id"]
            self.assertEqual(self.post("voice-event", {"type": "text", "text": "a"}, args=[sid]).status_code, 200)
            self.assertEqual(self.post("voice-session-close", args=[sid]).status_code, 200)
        # setUp's tripwires (socket.connect, openai SDK, ledger functions) would have raised.
        self.assertEqual(self.sdk_calls, [])

    def test_voice_modules_import_no_provider_sdk(self):
        import apps.ai_core.voice.provider as provider
        import apps.ai_core.voice.views as views
        for module in (provider, views, voice_store, voice_config):
            self.assertFalse(hasattr(module, "openai"), module.__name__)
