"""Regression tests for the closed Production image-worker boundary.

These tests never call OpenAI, claim a queue job, or mutate a ledger.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.ai_core.image_generation.production_worker import (
    process_production_image_job,
    production_worker_preflight,
)


class ProductionImageWorkerClosedGateTests(SimpleTestCase):
    @override_settings(
        VORNEQ_ENV="production",
        DEBUG=False,
        VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET=True,
        VORNEQ_AI_IMAGE_PRODUCTION_ENABLED=True,
        VORNEQ_AI_IMAGE_PRODUCTION_ALLOWED_USER_IDS="1",
        VORNEQ_AI_IMAGE_PRODUCTION_OWNER_AUTH="OWNER-AUTH-AI-IMAGE-PRODUCTION-TEST-20261123",
        VORNEQ_AI_IMAGE_PRODUCTION_AUTHORIZED_SHA="a" * 40,
        VORNEQ_AI_IMAGE_PRODUCTION_WORKER_SERVICE_ID="srv-" + "b" * 20,
        VORNEQ_AI_EMERGENCY_STOP=False,
    )
    @patch("apps.ai_core.deploy_authorization._verified_release", return_value=True)
    def test_all_other_gates_cannot_enable_paid_worker(self, release):
        with patch.dict("os.environ", {
            "RENDER_SERVICE_ID": "srv-" + "b" * 20,
            "RENDER_GIT_COMMIT": "a" * 40,
            "VORNEQ_AI_DEPLOY_READ_TOKEN": "test-present-only",
        }):
            result = production_worker_preflight()
        self.assertIs(result["checks"]["provider_activation_authorized"], False)
        self.assertIs(result["ready"], False)
        self.assertIsNone(process_production_image_job())

    def test_worker_never_claims_or_calls_provider(self):
        with patch(
            "apps.ai_core.image_generation.production_worker.production_worker_preflight",
            side_effect=AssertionError("unexpected preflight invocation"),
        ):
            self.assertIsNone(process_production_image_job())
