"""Offline tests for paid image prepaid-only mode."""
import os
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.ai_core.image_generation import policy, service
from apps.ai_core.models import AIImageJob, AIImageDailyQuota
from apps.ai_ledger import service as ledger

FLAGS = dict(VORNEQ_ENV="staging", DEBUG=False, VORNEQ_AI_IMAGE_ENABLED=True,
             VORNEQ_AI_EMERGENCY_STOP=False, VORNEQ_AI_IMAGE_PROVIDER="openai",
             VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=True,
             VORNEQ_AI_IMAGE_STAGING_PREPAID_ONLY=True,
             VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS=1, VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=1,
             VORNEQ_AI_IMAGE_LEDGER_DAILY_MAX_REQUESTS=1, VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=100000,
             VORNEQ_AI_IMAGE_MODEL="gpt-image-2.6-flare",
             VORNEQ_AI_IMAGE_AUTHORIZED_SHA="a"*40,
             VORNEQ_AI_IMAGE_OWNER_AUTH="OWNER-AUTH-AI-IMAGE-STAGING-TEST-01")
IMAGE = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CHAT = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


@override_settings(**FLAGS)
class PrepaidPolicyTests(SimpleTestCase):
    def test_opt_in_only_and_legacy_caps_unchanged(self):
        self.assertTrue(policy.prepaid_only_requested())
        with patch.object(service, "paid_provider_enabled", return_value=True):
            self.assertIsNone(service.image_ledger_daily_limit())
        with override_settings(VORNEQ_AI_IMAGE_STAGING_PREPAID_ONLY=False):
            self.assertEqual(service.image_ledger_daily_limit().max_requests, 1)
        for change in ({"VORNEQ_ENV": "production"}, {"VORNEQ_AI_IMAGE_PROVIDER": "mock"},
                       {"VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": False}):
            with override_settings(**change):
                self.assertFalse(policy.prepaid_only_requested())

    def test_unapproved_prepaid_fails_closed(self):
        with patch.object(service, "paid_provider_enabled", return_value=False), patch.object(service, "paid_worker_enabled", return_value=False):
            with self.assertRaises(service.ImageQueueError):
                service.image_ledger_daily_limit()

    @override_settings(VORNEQ_AI_IMAGE_LEDGER_ID=str(IMAGE))
    def test_separate_account_and_atomic_reservation_entry_point(self):
        web = ledger.EXPECTED_SERVICES["staging"]
        kwargs = dict(service_id=web, git_sha="a"*40, actor_id=3,
                      model=FLAGS["VORNEQ_AI_IMAGE_MODEL"], input_bytes=100, max_output_tokens=200)
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": web, "RENDER_GIT_COMMIT": "a"*40}), patch.object(ledger, "ledger_configuration", return_value=ledger.LedgerConfig(CHAT, "test_db")), patch.object(ledger, "reserve_with_config") as reserve:
            ledger.reserve_prepaid_image(ledger.LedgerConfig(IMAGE, "test_db"), **kwargs)
            self.assertIsNone(reserve.call_args.kwargs["staging_daily"])
            self.assertTrue(reserve.call_args.kwargs["image_only"])
            reserve.reset_mock()
            with self.assertRaises(ledger.LedgerUnavailable):
                ledger.reserve_prepaid_image(ledger.LedgerConfig(CHAT, "test_db"), **kwargs)
            reserve.assert_not_called()
            with override_settings(VORNEQ_AI_EMERGENCY_STOP=True):
                with self.assertRaises(ledger.LedgerUnavailable):
                    ledger.reserve_prepaid_image(ledger.LedgerConfig(IMAGE, "test_db"), **kwargs)
            reserve.assert_not_called()


@override_settings(**FLAGS)
class PrepaidQueueTests(TestCase):
    def test_multiple_jobs_per_day_but_rate_limit_and_idempotency_preserved(self):
        owner = get_user_model().objects.create_user(username="prepaid-image-test")
        with patch.object(service, "actor_allowed", return_value=True), patch.object(service, "paid_provider_enabled", return_value=True):
            rid = uuid.uuid4()
            first, created = service.submit_image_job(owner, request_id=rid, prompt="first image", size="1024x1024")
            self.assertTrue(created)
            _, created = service.submit_image_job(owner, request_id=rid, prompt="first image", size="1024x1024")
            self.assertFalse(created)
            with self.assertRaisesRegex(service.ImageQueueError, "rate limit"):
                service.submit_image_job(owner, request_id=uuid.uuid4(), prompt="second image", size="1024x1024")
            AIImageJob.objects.filter(pk=first.pk).update(created_at=timezone.now()-timedelta(seconds=61))
            _, created = service.submit_image_job(owner, request_id=uuid.uuid4(), prompt="second image", size="1024x1024")
            self.assertTrue(created)
            self.assertEqual(AIImageDailyQuota.objects.get().submitted, 2)
