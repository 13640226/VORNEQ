"""Image Worker requires a committed ledger receipt before publishing success.

No live SDK, network or production DB. CI uses disposable test databases.
"""
import io
import socket
import uuid
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.ai_core.models import AIImageJob
from apps.ai_core.image_generation import service
from apps.ai_core.image_generation.providers import ImageResult
from apps.ai_ledger.service import LedgerConfig, Reservation

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "ai_images": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}
MODEL = "gpt-image-2.6-flare"


def _synthetic_png():
    data = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 60, 80)).save(data, format="PNG")
    return data.getvalue()


@override_settings(
    VORNEQ_ENV="development", VORNEQ_AI_IMAGE_ENABLED=False,
    VORNEQ_AI_IMAGE_PROVIDER="openai", VORNEQ_AI_IMAGE_MODEL=MODEL,
    VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS=3,
    VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=100_000,
    STORAGES=STORAGES,
)
class ImageSettlementWorkerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="settlement-test-owner", password="synthetic-only"
        )

    def make_job(self, *, status=AIImageJob.STATUS_QUEUED):
        return AIImageJob.objects.create(
            id=uuid.uuid4(), owner=self.owner, prompt="Offline example landscape",
            prompt_digest="0" * 64, model_id=MODEL, image_size="1024x1024",
            provider="openai", status=status,
        )

    @contextmanager
    def isolated_worker(self):
        with ExitStack() as patches:
            patches.enter_context(patch.object(socket.socket, "connect",
                                               side_effect=AssertionError("NETWORK_FORBIDDEN")))
            patches.enter_context(patch.object(service, "enabled", return_value=True))
            patches.enter_context(patch.object(service, "actor_allowed", return_value=True))
            patches.enter_context(patch.object(service, "paid_provider_enabled", return_value=True))
            patches.enter_context(patch(
                "apps.ai_core.image_generation.policy.image_ledger_config",
                return_value=LedgerConfig(uuid.uuid4(), "synthetic_disposable_db")
            ))
            reserve = patches.enter_context(patch(
                "apps.ai_ledger.service.reserve_with_config",
                return_value=Reservation(uuid.uuid4(), 1000, 5, 30)
            ))
            settle = patches.enter_context(patch("apps.ai_ledger.service.settle",
                                                 return_value="finalized"))
            provider = patches.enter_context(patch.object(service, "OpenAIImageProvider"))
            provider.return_value.generate.return_value = ImageResult(
                _synthetic_png(), input_tokens=11, output_tokens=27,
                is_mock=False,
            )
            yield reserve, settle, provider

    def test_completed_requires_confirmed_ledger_finalization(self):
        job = self.make_job()
        with self.isolated_worker() as (_, settle, provider):
            self.assertEqual(service.process_next_image_job(), job.pk)
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_COMPLETED)
            self.assertEqual(job.prompt, "")
            self.assertTrue(job.storage_key)
            self.assertIn("image_url", service.serialize_job(job))
            settle.assert_called_once()
            self.assertEqual(settle.call_args.kwargs["usage"], (11, 27))
            provider.return_value.generate.assert_called_once()

    def test_no_ledger_ack_never_publishes_completed_image(self):
        job = self.make_job()
        with self.isolated_worker() as (_, settle, provider):
            settle.return_value = None
            service.process_next_image_job()
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_UNCERTAIN)
            self.assertEqual(job.error_code, "ledger_settlement_unconfirmed")
            self.assertEqual(job.prompt, "")
            self.assertTrue(job.storage_key)  # private object for manual reconciliation
            self.assertNotIn("image_url", service.serialize_job(job))
            self.assertIsNone(service.process_next_image_job())
            settle.assert_called_once()  # never retry settlement after uncertain result
            provider.return_value.generate.assert_called_once()

    def test_missing_usage_keeps_job_uncertain_after_ledger_uncertain_receipt(self):
        job = self.make_job()
        with self.isolated_worker() as (_, settle, _):
            settle.return_value = "uncertain"
            with patch.object(service, "OpenAIImageProvider") as provider:
                provider.return_value.generate.return_value = ImageResult(
                    _synthetic_png(), input_tokens=None, output_tokens=None,
                )
                service.process_next_image_job()
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_UNCERTAIN)
            self.assertEqual(job.prompt, "")
            self.assertIsNone(settle.call_args.kwargs["usage"])
            self.assertNotIn("image_url", service.serialize_job(job))

    def test_unexpected_settle_exception_is_uncertain_and_not_retried(self):
        job = self.make_job()
        with self.isolated_worker() as (_, settle, provider):
            settle.side_effect = RuntimeError("synthetic ledger failure")
            service.process_next_image_job()
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_UNCERTAIN)
            self.assertEqual(job.prompt, "")
            self.assertNotIn("image_url", service.serialize_job(job))
            self.assertEqual(settle.call_count, 1)
            self.assertIsNone(service.process_next_image_job())
            provider.return_value.generate.assert_called_once()

    def test_provider_failure_and_ledger_exception_do_not_strand_running(self):
        job = self.make_job()
        with self.isolated_worker() as (_, settle, provider):
            provider.return_value.generate.side_effect = RuntimeError("synthetic provider failure")
            settle.side_effect = RuntimeError("synthetic ledger failure")
            service.process_next_image_job()
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_UNCERTAIN)
            self.assertEqual(job.prompt, "")
            self.assertEqual(settle.call_count, 1)
            self.assertIsNone(service.process_next_image_job())

    def test_preexisting_running_is_never_retried(self):
        job = self.make_job(status=AIImageJob.STATUS_RUNNING)
        with self.isolated_worker() as (reserve, settle, provider):
            self.assertIsNone(service.process_next_image_job())
            reserve.assert_not_called()
            settle.assert_not_called()
            provider.return_value.generate.assert_not_called()
