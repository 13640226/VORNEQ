"""No-network tests. Never construct an OpenAI client or touch paid models."""
import json
import os
import uuid
import hashlib
import sys
import types
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
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

    def test_rate_limit_one_per_minute(self):
        self.assertEqual(self.submit().status_code, 202)
        self.assertEqual(self.submit().status_code, 400)
        self.assertEqual(AIImageJob.objects.count(), 1)

    @override_settings(VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=1)
    def test_global_daily_cap_cross_actor(self):
        self.assertEqual(self.submit().status_code, 202)
        self.client.force_login(self.other)
        self.assertEqual(self.submit().status_code, 400)

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
        with patch("apps.ai_core.image_generation.policy.paid_provider_enabled", return_value=True), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-never-live"}), \
             self.assertRaises(ImageProviderError):
            OpenAIImageProvider().generate(
                prompt="A harmless landscape", model="gpt-image-2.6-flare", size="1024x1024"
            )
        self.assertEqual(self.sdk_calls, ["OpenAI"])
        self.sdk_calls.clear()
