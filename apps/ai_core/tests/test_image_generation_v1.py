"""No-network tests. Never construct an OpenAI client or touch paid models."""
import json
import os
import uuid
import hashlib
import sys
import types
from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse

from apps.ai_core.models import AIImageJob, AIImageDailyQuota
from apps.ai_core.image_generation.policy import actor_allowed, enabled, paid_provider_enabled
from apps.ai_core.image_generation.providers import OpenAIImageProvider, ImageProviderError
from apps.ai_core.image_generation.service import process_next_image_job

STORES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "ai_images": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}

FLAGS = {
    "VORNEQ_ENV": "development",
    "VORNEQ_AI_IMAGE_ENABLED": True,
    "VORNEQ_AI_IMAGE_PROVIDER": "mock",
    "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False,
    "VORNEQ_AI_IMAGE_MODEL": "gpt-image-2.6-flare",
    "VORNEQ_AI_EMERGENCY_STOP": False,
    "VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS": 3,
    "VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS": 10,
    "VORNEQ_AI_IMAGE_MIN_INTERVAL_SECONDS": 60,
    "VORNEQ_AI_IMAGE_ALLOW_ZERO_INTERVAL": False,
    "VORNEQ_AI_IMAGE_MAX_ACTIVE_JOBS_PER_USER": 3,
    "VORNEQ_AI_IMAGE_MAX_ACTIVE_JOBS_GLOBAL": 50,
    "STORAGES": STORES,
}


def _paid_sdk_tripwire(calls):
    module = types.ModuleType("openai")

    def _forbidden(*args, **kwargs):
        # Recorded separately: the provider maps every exception to
        # ImageProviderError, which would otherwise hide this tripwire.
        calls.append("OpenAI")
        raise AssertionError("PAID_SDK_CONSTRUCTED")

    module.OpenAI = _forbidden
    return module


@override_settings(**FLAGS)
class ImageGenerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="image-owner", password="safe-test")
        cls.other = get_user_model().objects.create_user(username="image-other", password="safe-test")

    def setUp(self):
        self.client.force_login(self.owner)
        self.url = reverse("ai_core:image-jobs")
        # Replace the SDK module itself (installed or not) with a tripwire, so the
        # suite needs no SDK in CI and any client construction fails loudly.
        self.sdk_calls = []
        self.sdk = patch.dict(sys.modules, {"openai": _paid_sdk_tripwire(self.sdk_calls)})
        self.sdk.start()
        self.addCleanup(self.sdk.stop)
        self.addCleanup(lambda: self.assertEqual(self.sdk_calls, [], "PAID_SDK_CONSTRUCTED"))
        self.env = patch.dict(os.environ, {"RENDER": "", "RENDER_SERVICE_ID": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def submit(self, *, request_id=None, prompt="A Persian calligraphy example", size="1024x1024"):
        return self.client.post(
            self.url, data=json.dumps({
                "request_id": str(request_id or uuid.uuid4()),
                "prompt": prompt, "size": size,
            }), content_type="application/json",
        )

    @override_settings(VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS=10)
    def test_queue_capacity_and_replay(self):
        rid = uuid.uuid4()
        self.assertEqual(self.submit(request_id=rid).status_code, 202)
        for status in (AIImageJob.STATUS_QUEUED, AIImageJob.STATUS_RUNNING):
            AIImageJob.objects.create(owner=self.owner, prompt="test", prompt_digest="a"*64,
                                      model_id="mock", status=status)
        self.assert_rejected_without_side_effects(self.submit, 429, "active_queue_full")
        self.assertEqual(self.submit(request_id=rid).status_code, 200)
        AIImageJob.objects.filter(owner=self.owner).update(created_at=timezone.now()-timedelta(seconds=61))
        AIImageJob.objects.filter(pk=rid).update(status=AIImageJob.STATUS_COMPLETED)
        self.assertEqual(self.submit().status_code, 202)

    @override_settings(VORNEQ_AI_IMAGE_MAX_ACTIVE_JOBS_GLOBAL=1)
    def test_global_queue_capacity(self):
        AIImageJob.objects.create(owner=self.other, prompt="test", prompt_digest="a"*64, model_id="mock")
        self.assert_rejected_without_side_effects(self.submit, 429, "global_active_queue_full")

    @override_settings(VORNEQ_ENV="staging", VORNEQ_AI_IMAGE_PROVIDER="openai",
                       VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=True,
                       VORNEQ_AI_IMAGE_STAGING_PREPAID_ONLY=True,
                       VORNEQ_AI_IMAGE_ALLOW_ZERO_INTERVAL=True)
    def test_real_interval_policy(self):
        from apps.ai_core.image_generation.policy import min_interval_seconds
        with patch("apps.ai_core.image_generation.policy.paid_provider_enabled", return_value=True):
            for value, expected in [(0,0),(10,10),(-1,60),(True,60),("bad",60),(4000,3600)]:
                with self.subTest(value=value), override_settings(VORNEQ_AI_IMAGE_MIN_INTERVAL_SECONDS=value):
                    self.assertEqual(min_interval_seconds(), expected)
            with override_settings(VORNEQ_AI_IMAGE_MIN_INTERVAL_SECONDS=0, VORNEQ_AI_IMAGE_ALLOW_ZERO_INTERVAL=False):
                self.assertEqual(min_interval_seconds(),60)

    def test_anonymous_is_denied(self):
        self.client.logout()
        response = self.submit()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(AIImageJob.objects.count(), 0)

    @override_settings(VORNEQ_AI_IMAGE_ENABLED=False)
    def test_feature_off_is_404(self):
        self.assertEqual(self.submit().status_code, 404)
        self.assertEqual(AIImageJob.objects.count(), 0)

    def test_submit_and_idempotency(self):
        request_id = uuid.uuid4()
        response = self.submit(request_id=request_id)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        self.assertNotIn("prompt", response.json())
        repeat = self.submit(request_id=request_id)
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(AIImageJob.objects.count(), 1)
        self.assertEqual(AIImageDailyQuota.objects.get().submitted, 1)

    def test_owner_isolation_and_unknown_uuid(self):
        r = self.submit()
        self.assertEqual(r.status_code, 202)
        path = reverse("ai_core:image-job-detail", kwargs={"job_id": r.json()["id"]})
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get(reverse(
            "ai_core:image-job-detail", kwargs={"job_id": uuid.uuid4()}
        )).status_code, 404)

    def test_request_reuse_must_match_prompt(self):
        rid = uuid.uuid4()
        self.assertEqual(self.submit(request_id=rid).status_code, 202)
        self.assertEqual(self.submit(request_id=rid, prompt="different prompt").status_code, 400)

    def assert_rejected_without_side_effects(self, submit, status, code):
        counts = (AIImageJob.objects.count(),
                  list(AIImageDailyQuota.objects.values_list("day_utc", "submitted")))
        with patch("apps.ai_ledger.service.reserve_with_config") as reserve, \
                patch("apps.ai_ledger.service.reserve_prepaid_image") as prepaid, \
                patch("apps.ai_core.image_generation.service.OpenAIImageProvider") as provider, \
                patch("apps.ai_core.image_generation.service.MockImageProvider") as mock:
            response = submit()
        for call in (reserve, prepaid, provider, mock):
            call.assert_not_called()
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json()["error_code"], code)
        self.assertIs(response.json()["request_rejected"], True)
        self.assertEqual(counts, (AIImageJob.objects.count(),
                                  list(AIImageDailyQuota.objects.values_list("day_utc", "submitted"))))
        self.assertFalse(AIImageJob.objects.exclude(reservation_id=None).exists())
        return response

    def test_rate_limit_one_per_minute(self):
        self.assertEqual(self.submit().status_code, 202)
        limited = self.assert_rejected_without_side_effects(self.submit, 429, "rate_limited")
        retry = limited.json()["retry_after_seconds"]
        self.assertTrue(1 <= retry <= 60)
        self.assertEqual(limited["Retry-After"], str(retry))
        self.assertEqual(AIImageJob.objects.count(), 1)

    @override_settings(VORNEQ_AI_IMAGE_PROVIDER="openai", VORNEQ_AI_IMAGE_STAGING_PREPAID_ONLY=True)
    def test_paid_admission_refusal_never_reserves_or_constructs_provider(self):
        with patch("apps.ai_core.image_generation.policy.enabled", return_value=True), \
                patch("apps.ai_core.image_generation.service.paid_provider_enabled", return_value=True), \
                patch("apps.ai_core.image_generation.service.prepaid_only_requested", return_value=True):
            self.assertEqual(self.submit().status_code, 202)
            self.assert_rejected_without_side_effects(self.submit, 429, "rate_limited")

    def test_explicit_validation_codes(self):
        for kwargs, code in (
                ({"prompt": "x"}, "invalid_prompt"),
                ({"size": "64000x64000"}, "unsupported_size"),
                ({"size": []}, "unsupported_size"),
                ({"request_id": uuid.uuid1()}, "invalid_request_id")):
            self.assert_rejected_without_side_effects(lambda: self.submit(**kwargs), 400, code)

    @override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=0)
    def test_invalid_quota_is_definite_503(self):
        self.assert_rejected_without_side_effects(self.submit, 503, "service_misconfigured")

    @override_settings(VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS=1)
    def test_user_daily_cap_is_429(self):
        self.assertEqual(self.submit().status_code, 202)
        limited = self.assert_rejected_without_side_effects(self.submit, 429, "user_daily_cap")
        self.assertEqual(limited["Retry-After"], str(limited.json()["retry_after_seconds"]))

    def test_active_list_and_latest_are_owner_scoped(self):
        rid = self.submit().json()["id"]
        active = self.url + "?active=1"
        latest = self.url + "?latest=1"
        self.assertEqual(self.client.get(active).json()["results"][0]["id"], rid)
        self.assertEqual(self.client.get(latest).json(), {"id": rid})
        AIImageJob.objects.filter(pk=rid).update(status="running")
        self.assertEqual(self.client.get(active).json()["results"][0]["status"], "running")
        for state in ("completed", "failed", "uncertain"):
            AIImageJob.objects.filter(pk=rid).update(status=state)
            self.assertEqual(self.client.get(active).json(), {"results": []})
            self.assertEqual(self.client.get(latest).json(), {"id": rid})
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(active).json(), {"results": []})
        self.assertEqual(self.client.get(latest).json(), {"id": None})
        self.client.logout()
        for path in (active, latest):
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_recovery_is_bounded_and_does_not_disclose_secrets(self):
        for _ in range(12):
            AIImageJob.objects.create(owner=self.owner, prompt="secret", prompt_digest="0"*64,
                                      model_id="mock", status="queued")
        response = self.client.get(self.url + "?active=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        results = response.json()["results"]
        self.assertEqual(len(results), 10)
        for job in results:
            self.assertFalse(set(job) & {"prompt", "storage_key", "reservation_id", "image_url"})

    @override_settings(VORNEQ_AI_IMAGE_ENABLED=False)
    def test_recovery_preserves_existing_gate(self):
        self.assertEqual(self.client.get(self.url + "?active=1").status_code, 404)
        self.assertEqual(self.client.get(self.url + "?latest=1").status_code, 404)

    @override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=1)
    def test_global_daily_cap_cross_actor(self):
        self.assertEqual(self.submit().status_code, 202)
        self.client.force_login(self.other)
        limited = self.assert_rejected_without_side_effects(self.submit, 429, "global_daily_cap")
        self.assertEqual(limited["Retry-After"], str(limited.json()["retry_after_seconds"]))

    def test_invalid_prompt_and_size(self):
        self.assertEqual(self.submit(prompt="x").status_code, 400)
        self.assertEqual(self.submit(size="64000x64000").status_code, 400)
        self.assertEqual(self.submit(prompt="x"*3000).status_code, 400)
        self.assertEqual(AIImageJob.objects.count(), 0)

    @override_settings(VORNEQ_AI_EMERGENCY_STOP=True)
    def test_emergency_stop_denies_queue(self):
        self.assertEqual(self.submit().status_code, 404)

    @override_settings(VORNEQ_ENV="production")
    def test_production_fails_closed(self):
        self.assertFalse(enabled())
        self.assertFalse(paid_provider_enabled())
        self.assertEqual(self.submit().status_code, 404)

    @override_settings(VORNEQ_ENV="staging", DEBUG=False)
    def test_staging_without_sha_and_owner_denied(self):
        self.assertFalse(enabled())
        self.assertEqual(self.submit().status_code, 404)

    def test_mock_worker_persists_image_and_removes_prompt(self):
        r = self.submit()
        self.assertEqual(r.status_code, 202)
        job_id = uuid.UUID(r.json()["id"])
        self.assertEqual(process_next_image_job(), job_id)
        job = AIImageJob.objects.get(pk=job_id)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.prompt, "")
        self.assertTrue(job.storage_key.startswith("ai-generated/"))
        self.assertTrue(job.is_mock)
        from apps.ai_core.image_generation.storage import image_storage
        with image_storage().open(job.storage_key, "rb") as image_file:
            self.assertEqual(job.image_digest, hashlib.sha256(image_file.read()).hexdigest())
        result = self.client.get(reverse("ai_core:image-job-detail", kwargs={"job_id": job_id}))
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["mock"])
        self.assertIn("AI-generated", result.json()["label"])
        self.assertIn("image_url", result.json())
        self.assertIsNone(process_next_image_job())

    @override_settings(STORAGES={
        "default": STORES["default"],
        "staticfiles": STORES["staticfiles"],
    })
    def test_missing_private_storage_fails_without_retry(self):
        r = self.submit()
        self.assertEqual(r.status_code, 202)
        job_id = uuid.UUID(r.json()["id"])
        self.assertEqual(process_next_image_job(), job_id)
        job = AIImageJob.objects.get(pk=job_id)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.prompt, "")
        self.assertIsNone(process_next_image_job())

    def test_no_paid_provider_bypass(self):
        self.assertFalse(paid_provider_enabled())
        with self.assertRaises(ImageProviderError):
            OpenAIImageProvider().generate(
                prompt="A harmless landscape", model="gpt-image-2.6-flare", size="1024x1024"
            )

    def test_csrf_is_enforced(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        result = strict.post(self.url, data=json.dumps({
            "request_id": str(uuid.uuid4()), "prompt": "A sunny valley"
        }), content_type="application/json")
        self.assertEqual(result.status_code, 403)

    def test_sdk_tripwire_is_active_and_detected(self):
        # Guard for the guard: if every runtime gate were bypassed, the tripwire
        # must be hit and recorded even though the provider swallows the error.
        from apps.ai_core.tests.ledger_fakes import fake_reservation
        from apps.ai_ledger.call_authorization import authorized_paid_call

        # V4-01: "alle Gates umgangen" schließt jetzt auch die Ledger-Freigabe ein.
        with patch("apps.ai_core.image_generation.policy.paid_provider_enabled", return_value=True), \
             patch.dict(os.environ, {"VORNEQ_OPENAI_IMAGE_API_KEY": "synthetic-never-live"}), \
             authorized_paid_call(fake_reservation(), kind="image"), \
             self.assertRaises(ImageProviderError):
            OpenAIImageProvider().generate(
                prompt="A harmless landscape", model="gpt-image-2.6-flare", size="1024x1024",
                safety_identifier="vq_" + "0" * 64,
            )
        self.assertEqual(self.sdk_calls, ["OpenAI"])
        self.sdk_calls.clear()

@override_settings(**{**FLAGS, "VORNEQ_AI_IMAGE_MAX_ACTIVE_JOBS_GLOBAL": 1})
class ImageQueueConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_parallel_admissions_across_utc_days(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier, local
        from datetime import datetime, timezone as utc
        from django.db import connections
        from apps.ai_core.image_generation import service

        users = [get_user_model().objects.create_user(username=f"queue-race-{i}") for i in range(2)]
        barrier = Barrier(2)
        clocks = local()

        class AdmissionClock:
            @staticmethod
            def now(tz):
                return clocks.value

            combine = staticmethod(datetime.combine)
            min = datetime.min

        def attempt(index):
            try:
                clocks.value = datetime(2026, 11, 22 + index, tzinfo=utc.utc)
                barrier.wait(timeout=10)
                try:
                    service.submit_image_job(users[index], request_id=uuid.uuid4(),
                                             prompt="offline concurrent image", size="1024x1024")
                    return "accepted"
                except service.ImageQueueError as exc:
                    return exc.code
            finally:
                connections.close_all()

        with patch.object(service, "datetime", AdmissionClock), \
                patch.dict(os.environ, {"RENDER": "", "RENDER_SERVICE_ID": ""}), \
                patch.object(service, "OpenAIImageProvider", side_effect=AssertionError("paid provider")):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(attempt, range(2)))
        self.assertCountEqual(results, ["accepted", "global_active_queue_full"])
        self.assertEqual(AIImageJob.objects.count(), 1)
        self.assertEqual(sum(AIImageDailyQuota.objects.values_list("submitted", flat=True)), 1)
