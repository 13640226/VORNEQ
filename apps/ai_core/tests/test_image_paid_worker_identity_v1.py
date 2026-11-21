"""Paid Staging image Worker: separate switch, separate owner grant, never Production.

Offline: no network, no SDK, no real ledger. The ledger client side is covered
on PostgreSQL in apps.ai_ledger.tests.test_ledger_image_worker_client.
"""
import os
import socket
import uuid
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from apps.ai_core.image_generation import policy, service
from apps.ai_core.image_generation.providers import ImageResult
from apps.ai_core.models import AIImageJob
from apps.ai_core.tests.test_image_settlement_v1 import _synthetic_png
from apps.ai_core.tests.test_image_worker_identity_v1 import (
    PRODUCTION,
    SHA,
    STORAGES,
    WEB,
    WORKER,
)
from apps.ai_ledger.service import Reservation

MODEL = "gpt-image-2.6-flare"
PAID_GRANT = "OWNER-AUTH-AI-IMAGE-PAID-WORKER-STAGING-TEST-01"
FLAGS = {
    "VORNEQ_ENV": "staging", "DEBUG": False,
    "VORNEQ_AI_IMAGE_ENABLED": True,
    "VORNEQ_AI_IMAGE_PROVIDER": "openai",
    "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": True,
    "VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED": True,
    "VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH": PAID_GRANT,
    "VORNEQ_AI_IMAGE_OWNER_AUTH": "",
    "VORNEQ_AI_EMERGENCY_STOP": False,
    "VORNEQ_AI_IMAGE_ALLOWED_USER_IDS": "101",
    "VORNEQ_AI_IMAGE_AUTHORIZED_SHA": SHA,
    "VORNEQ_AI_IMAGE_WORKER_SERVICE_ID": WORKER,
    "VORNEQ_AI_IMAGE_MODEL": MODEL,
}


@override_settings(**FLAGS)
class PaidWorkerIdentityTests(SimpleTestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"RENDER_SERVICE_ID": WORKER, "RENDER_GIT_COMMIT": SHA})
        env.start()
        self.addCleanup(env.stop)
        controls = patch.object(policy, "_paid_controls_ready", return_value=True)
        self.controls = controls.start()
        self.addCleanup(controls.stop)

    def test_paid_worker_gate_and_owner_scope(self):
        self.assertTrue(policy.paid_worker_enabled())
        self.assertFalse(policy.worker_enabled())
        self.assertFalse(policy.enabled())
        good = SimpleNamespace(pk=101, is_authenticated=True, is_active=True)
        bad = SimpleNamespace(pk=102, is_authenticated=True, is_active=True)
        self.assertTrue(policy.actor_allowed(good, worker=True))
        self.assertFalse(policy.actor_allowed(bad, worker=True))
        self.assertFalse(policy.actor_allowed(good))

    def test_default_off_and_every_identity_condition_is_required(self):
        cases = [
            {"VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED": False},
            {"VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH": ""},
            # The web grant and the mock-worker grant never unlock the paid worker.
            {"VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH": "OWNER-AUTH-AI-IMAGE-STAGING-WEB-GRANT"},
            {"VORNEQ_AI_IMAGE_ENABLED": False},
            {"VORNEQ_AI_EMERGENCY_STOP": True},
            {"VORNEQ_ENV": "production"},
            {"DEBUG": True},
            {"VORNEQ_AI_IMAGE_WORKER_SERVICE_ID": ""},
            {"VORNEQ_AI_IMAGE_WORKER_SERVICE_ID": WEB},
            {"VORNEQ_AI_IMAGE_WORKER_SERVICE_ID": PRODUCTION},
            {"VORNEQ_AI_IMAGE_ALLOWED_USER_IDS": ""},
            {"VORNEQ_AI_IMAGE_AUTHORIZED_SHA": "b" * 40},
        ]
        for case in cases:
            with self.subTest(case=case), override_settings(**case):
                self.assertFalse(policy.paid_worker_enabled())

    def test_runtime_identity_must_be_the_worker(self):
        for service_id in (WEB, PRODUCTION, "srv-otherotherotherother"):
            with self.subTest(service_id=service_id), \
                    patch.dict(os.environ, {"RENDER_SERVICE_ID": service_id}):
                self.assertFalse(policy.paid_worker_enabled())

    def test_paid_controls_are_required(self):
        self.controls.return_value = False
        self.assertFalse(policy.paid_worker_enabled())


@override_settings(**FLAGS)
class PaidControlsTests(SimpleTestCase):
    """The real control function: mock provider or no paid flag is always closed."""

    def test_paid_controls_need_openai_provider_paid_flag_and_key(self):
        with patch.dict(os.environ, {"VORNEQ_OPENAI_IMAGE_API_KEY": ""}):
            self.assertFalse(policy._paid_controls_ready())
        with override_settings(VORNEQ_AI_IMAGE_PROVIDER="mock"):
            self.assertFalse(policy._paid_controls_ready())
        with override_settings(VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=False):
            self.assertFalse(policy._paid_controls_ready())

    def test_mock_worker_and_paid_worker_are_mutually_exclusive(self):
        mock_flags = {"VORNEQ_AI_IMAGE_PROVIDER": "mock", "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False,
                      "VORNEQ_AI_IMAGE_OWNER_AUTH": "OWNER-AUTH-AI-IMAGE-STAGING-MOCK-WORKER-TEST"}
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": WORKER, "RENDER_GIT_COMMIT": SHA,
                                     "VORNEQ_OPENAI_IMAGE_API_KEY": "synthetic-not-a-key"}):
            with patch.object(policy, "_paid_controls_ready", return_value=True):
                self.assertFalse(policy.worker_enabled())
            with override_settings(**mock_flags):
                self.assertTrue(policy.worker_enabled())
                self.assertFalse(policy.paid_worker_enabled())


@override_settings(**{**FLAGS, "STORAGES": STORAGES,
                      "VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS": 3,
                      "VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD": 100_000,
                      "VORNEQ_AI_IMAGE_MAX_REQUEST_MICROUSD": 100_000,
                      "VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND": 2_000,
                      "VORNEQ_AI_IMAGE_SAFETY_ID_KEY": "synthetic-offline-test-key-not-a-secret-0001"})
class PaidWorkerQueueTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="paid-worker-test",
                                                          password="synthetic-only")
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.dict(os.environ, {"RENDER_SERVICE_ID": WORKER,
                                                    "RENDER_GIT_COMMIT": SHA}))
        stack.enter_context(override_settings(VORNEQ_AI_IMAGE_ALLOWED_USER_IDS=str(self.owner.pk)))
        stack.enter_context(patch.object(socket.socket, "connect",
                                         side_effect=AssertionError("NETWORK_FORBIDDEN")))
        self.gate = stack.enter_context(patch.object(service, "paid_worker_enabled",
                                                     return_value=True))
        stack.enter_context(patch.object(service, "actor_allowed", return_value=True))
        self.web_paid = stack.enter_context(patch.object(service, "paid_provider_enabled",
                                                         return_value=False))
        stack.enter_context(patch("apps.ai_core.image_generation.policy.image_ledger_config",
                                  return_value=SimpleNamespace(ledger_id=uuid.uuid4())))
        self.reserve = stack.enter_context(patch(
            "apps.ai_ledger.service.reserve_with_config",
            return_value=Reservation(uuid.uuid4(), 50_000, 5, 30)))
        self.settle = stack.enter_context(patch("apps.ai_ledger.service.settle",
                                                return_value="finalized"))
        self.release = stack.enter_context(patch("apps.ai_ledger.service.release",
                                                 return_value="released"))
        self.provider = stack.enter_context(patch.object(service, "OpenAIImageProvider"))
        self.provider.return_value.generate.return_value = ImageResult(
            _synthetic_png(), input_tokens=19, output_tokens=824, is_mock=False)

    def job(self, provider="openai"):
        return AIImageJob.objects.create(
            id=uuid.uuid4(), owner=self.owner, prompt="Offline paid worker test",
            prompt_digest="0" * 64, model_id=MODEL if provider == "openai" else "mock",
            image_size="1024x1024", provider=provider, status=AIImageJob.STATUS_QUEUED)

    def test_paid_worker_processes_one_paid_job_with_worker_identity(self):
        job = self.job()
        self.assertEqual(service.process_next_image_job(), job.pk)
        job.refresh_from_db()
        self.assertEqual((job.status, job.attempts, job.prompt), (AIImageJob.STATUS_COMPLETED, 1, ""))
        kwargs = self.reserve.call_args.kwargs
        self.assertEqual((kwargs["environment"], kwargs["service_id"]), ("staging", WORKER))
        self.provider.return_value.generate.assert_called_once()
        self.web_paid.assert_not_called()
        self.assertIsNone(service.process_next_image_job())

    def test_paid_worker_never_claims_mock_jobs(self):
        job = self.job(provider="mock")
        self.assertIsNone(service.process_next_image_job())
        job.refresh_from_db()
        self.assertEqual((job.status, job.attempts), (AIImageJob.STATUS_QUEUED, 0))

    def test_gate_closing_after_reservation_releases_without_provider_call(self):
        job = self.job()
        # initial claim, check before reserve, then CLOSED just before the provider call
        self.gate.side_effect = [True, True, False]
        self.assertEqual(service.process_next_image_job(), job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, AIImageJob.STATUS_FAILED)
        self.provider.return_value.generate.assert_not_called()
        self.release.assert_called_once()

    def test_mock_worker_identity_takes_precedence_and_never_claims_paid(self):
        job = self.job()
        with patch.object(service, "worker_enabled", return_value=True):
            self.assertIsNone(service.process_next_image_job())
        job.refresh_from_db()
        self.assertEqual((job.status, job.attempts), (AIImageJob.STATUS_QUEUED, 0))
        self.reserve.assert_not_called()

    def test_closed_gate_claims_nothing(self):
        self.gate.return_value = False
        job = self.job()
        self.assertIsNone(service.process_next_image_job())
        job.refresh_from_db()
        self.assertEqual(job.status, AIImageJob.STATUS_QUEUED)
        self.reserve.assert_not_called()
