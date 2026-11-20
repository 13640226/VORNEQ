"""Paid image worker: release only provably-unsent requests; never retry.

Ledger and provider are replaced by mocks (SQLite + PostgreSQL); the real
ledger release()/settle() semantics are covered on PostgreSQL in ai_ledger.
"""
import uuid
from unittest.mock import patch

from django.test import override_settings

from apps.ai_core.image_generation import service
from apps.ai_core.image_generation.providers import ImageProviderError, ImageResult
from apps.ai_core.models import AIImageJob
from apps.ai_core.tests.test_image_settlement_v1 import ImageSettlementWorkerTests, _synthetic_png
from apps.ai_ledger.service import Reservation


class PaidWorkerOutcomeTests(ImageSettlementWorkerTests):
    def setUp(self):
        super().setUp()
        self.release = patch("apps.ai_ledger.service.release", return_value="released").start()
        self.addCleanup(patch.stopall)

    def run_with_error(self, error):
        job = self.make_job()
        with self.isolated_worker() as (_, settle, provider):
            provider.return_value.generate.side_effect = error
            self.assertEqual(service.process_next_image_job(), job.pk)
            job.refresh_from_db()
            return job, settle, provider

    def test_unsent_refusal_releases_and_fails_without_retry(self):
        job, settle, provider = self.run_with_error(
            ImageProviderError("x", code="prompt_moderated", request_sent=False))
        self.assertEqual((job.status, job.error_code), (AIImageJob.STATUS_FAILED, "prompt_moderated"))
        self.release.assert_called_once()
        self.assertEqual(self.release.call_args.kwargs["reason"], "prompt_moderated")
        settle.assert_not_called()
        self.assertIsNone(service.process_next_image_job())
        provider.return_value.generate.assert_called_once()

    def test_unconfirmed_release_is_uncertain(self):
        self.release.return_value = None
        job, settle, _ = self.run_with_error(
            ImageProviderError("x", code="sdk_unavailable", request_sent=False))
        self.assertEqual((job.status, job.error_code),
                         (AIImageJob.STATUS_UNCERTAIN, "ledger_release_unconfirmed"))
        settle.assert_not_called()

    def test_sent_failures_are_never_released(self):
        for code in ("provider_bad_request", "provider_auth", "provider_rate_limited",
                     "provider_server_error", "provider_timeout", "provider_connection",
                     "provider_empty_response", "provider_moderation_blocked"):
            with self.subTest(code):
                self.release.reset_mock()
                job, settle, _ = self.run_with_error(
                    ImageProviderError("x", code=code, request_sent=True))
                self.assertEqual((job.status, job.error_code), (AIImageJob.STATUS_UNCERTAIN, code))
                self.release.assert_not_called()
                settle.assert_called_once()
                self.assertIsNone(settle.call_args.kwargs["usage"])
                self.assertEqual(settle.call_args.kwargs["outcome"], "uncertain:" + code)
                self.assertEqual(job.prompt, "")
                self.assertNotIn("image_url", service.serialize_job(job))

    def test_unknown_send_state_is_treated_as_billed(self):
        job, settle, _ = self.run_with_error(ImageProviderError("x"))
        self.assertEqual(job.status, AIImageJob.STATUS_UNCERTAIN)
        self.release.assert_not_called()
        settle.assert_called_once()

    def test_reservation_over_request_cap_is_released_before_any_call(self):
        job = self.make_job()
        with self.isolated_worker() as (reserve, settle, provider):
            reserve.return_value = Reservation(uuid.uuid4(), 100_001, 5, 30)
            service.process_next_image_job()
            job.refresh_from_db()
            self.assertEqual((job.status, job.error_code),
                             (AIImageJob.STATUS_FAILED, "cost_ceiling_exceeded"))
            provider.return_value.generate.assert_not_called()
            self.assertEqual(self.release.call_args.kwargs["reason"], "cost_ceiling_exceeded")
            settle.assert_not_called()

    def test_usage_beyond_bound_is_settled_but_never_published(self):
        job = self.make_job()
        with self.isolated_worker() as (_, settle, provider):
            provider.return_value.generate.return_value = ImageResult(
                _synthetic_png(), input_tokens=11, output_tokens=5_001)
            service.process_next_image_job()
            job.refresh_from_db()
            self.assertEqual((job.status, job.error_code),
                             (AIImageJob.STATUS_UNCERTAIN, "usage_exceeded_bound"))
            self.assertEqual(settle.call_args.kwargs["usage"], (11, 5_001))
            self.assertNotIn("image_url", service.serialize_job(job))

    def test_r2_failure_after_provider_success_is_uncertain(self):
        job = self.make_job()
        with self.isolated_worker() as (_, settle, _), \
                patch.object(service, "store_image", side_effect=OSError("synthetic R2 outage")):
            service.process_next_image_job()
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_UNCERTAIN)
            settle.assert_called_once()
            self.assertIsNone(settle.call_args.kwargs["usage"])
            self.release.assert_not_called()

    def test_ledger_refusal_before_call_fails_without_provider(self):
        from apps.ai_ledger.service import StagingDailyCapReached
        job = self.make_job()
        with self.isolated_worker() as (reserve, settle, provider):
            reserve.side_effect = StagingDailyCapReached("synthetic cap")
            service.process_next_image_job()
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_FAILED)
            provider.return_value.generate.assert_not_called()
            settle.assert_not_called()

    def test_safety_identifier_is_hmac_of_owner(self):
        from apps.ai_core.image_generation.policy import safety_identifier
        job = self.make_job()
        with self.isolated_worker() as (_, _, provider):
            service.process_next_image_job()
            sent = provider.return_value.generate.call_args.kwargs["safety_identifier"]
        self.assertEqual(sent, safety_identifier(self.owner.pk))

    @override_settings(VORNEQ_AI_IMAGE_SAFETY_ID_KEY="")
    def test_missing_safety_key_fails_before_reservation(self):
        job = self.make_job()
        with self.isolated_worker() as (reserve, _, provider):
            service.process_next_image_job()
            job.refresh_from_db()
            self.assertEqual(job.status, AIImageJob.STATUS_FAILED)
            reserve.assert_not_called()
            provider.return_value.generate.assert_not_called()


# Reuse the fixtures only; the inherited settlement tests run in their own module.
for _name in [n for n in vars(ImageSettlementWorkerTests) if n.startswith("test_")]:
    setattr(PaidWorkerOutcomeTests, _name, None)
