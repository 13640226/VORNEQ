"""Offline Staging mock-Worker identity and no-paid queue guard tests."""
import os
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from apps.ai_core.image_generation import policy
from apps.ai_core.image_generation.service import process_next_image_job
from apps.ai_core.models import AIImageJob

WEB = "srv-dbm7dvc9v7es7393g70g"
WORKER = "srv-aaaaaaaaaaaaaaaaaaaa"
PRODUCTION = "srv-dadn07eq1p3s73eccau0"
SHA = "a" * 40
FLAGS = {
    "VORNEQ_ENV": "staging", "DEBUG": False,
    "VORNEQ_AI_IMAGE_ENABLED": True,
    "VORNEQ_AI_IMAGE_PROVIDER": "mock",
    "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False,
    "VORNEQ_AI_EMERGENCY_STOP": False,
    "VORNEQ_AI_IMAGE_ALLOWED_USER_IDS": "101",
    "VORNEQ_AI_IMAGE_AUTHORIZED_SHA": SHA,
    "VORNEQ_AI_IMAGE_OWNER_AUTH": "OWNER-AUTH-AI-IMAGE-STAGING-MOCK-WORKER-TEST",
    "VORNEQ_AI_IMAGE_WORKER_SERVICE_ID": WORKER,
}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "ai_images": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}


@override_settings(**FLAGS)
class ImageWorkerIdentityTests(SimpleTestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ, {"RENDER_SERVICE_ID": WORKER, "RENDER_GIT_COMMIT": SHA},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_separate_worker_mock_gate_and_owner_scope(self):
        self.assertFalse(policy.enabled())
        self.assertTrue(policy.worker_enabled())
        good = SimpleNamespace(pk=101, is_authenticated=True, is_active=True)
        bad = SimpleNamespace(pk=102, is_authenticated=True, is_active=True)
        self.assertFalse(policy.actor_allowed(good))
        self.assertTrue(policy.actor_allowed(good, worker=True))
        self.assertFalse(policy.actor_allowed(bad, worker=True))

    @override_settings(VORNEQ_AI_IMAGE_WORKER_SERVICE_ID=WEB)
    def test_web_service_id_cannot_be_worker_identity(self):
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": WEB}):
            self.assertFalse(policy.worker_enabled())

    @override_settings(VORNEQ_AI_IMAGE_WORKER_SERVICE_ID=PRODUCTION)
    def test_production_service_id_denied(self):
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": PRODUCTION}):
            self.assertFalse(policy.worker_enabled())

    @override_settings(VORNEQ_AI_IMAGE_WORKER_SERVICE_ID="")
    def test_unconfigured_worker_identity_denied(self):
        self.assertFalse(policy.worker_enabled())

    @override_settings(VORNEQ_AI_IMAGE_PROVIDER="openai")
    def test_paid_provider_denied(self):
        self.assertFalse(policy.worker_enabled())

    @override_settings(VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=True)
    def test_paid_flag_denied(self):
        self.assertFalse(policy.worker_enabled())

    @override_settings(VORNEQ_AI_EMERGENCY_STOP=True)
    def test_emergency_stop_denied(self):
        self.assertFalse(policy.worker_enabled())

    @override_settings(VORNEQ_ENV="production")
    def test_production_environment_denied(self):
        self.assertFalse(policy.worker_enabled())

    def test_sha_drift_denied(self):
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": "b" * 40}):
            self.assertFalse(policy.worker_enabled())

    @override_settings(VORNEQ_AI_IMAGE_OWNER_AUTH="")
    def test_missing_owner_auth_denied(self):
        self.assertFalse(policy.worker_enabled())


@override_settings(**{**FLAGS, "STORAGES": STORAGES})
class ImageWorkerQueueTests(TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ, {"RENDER_SERVICE_ID": WORKER, "RENDER_GIT_COMMIT": SHA},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.owner = get_user_model().objects.create_user(
            username="worker-mock-identity-test", password="test-only"
        )

    def create_job(self, provider="mock"):
        return AIImageJob.objects.create(
            id=uuid.uuid4(), owner=self.owner,
            prompt="Offline synthetic image worker test",
            prompt_digest="a" * 64, model_id=provider,
            image_size="1024x1024", provider=provider,
            status=AIImageJob.STATUS_QUEUED,
        )

    def test_mock_job_completes_inside_isolated_worker(self):
        with override_settings(VORNEQ_AI_IMAGE_ALLOWED_USER_IDS=str(self.owner.pk)):
            job = self.create_job()
            self.assertTrue(policy.worker_enabled())
            self.assertEqual(process_next_image_job(), job.id)
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_COMPLETED)
            self.assertEqual(job.attempts, 1)
            self.assertEqual(job.prompt, "")
            self.assertTrue(job.is_mock)

    def test_mock_worker_never_claims_paid_job(self):
        with override_settings(VORNEQ_AI_IMAGE_ALLOWED_USER_IDS=str(self.owner.pk)):
            job = self.create_job(provider="openai")
            self.assertIsNone(process_next_image_job())
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_QUEUED)
            self.assertEqual(job.attempts, 0)
