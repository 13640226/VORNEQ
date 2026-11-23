"""Production worker must remain inert even when release preflight flags look valid."""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.ai_core.image_generation.production_worker import (
    process_production_image_job, production_worker_preflight,
)


class ProductionImageWorkerContractTests(SimpleTestCase):
    @override_settings(
        VORNEQ_ENV="production", DEBUG=False,
        VORNEQ_AI_IMAGE_PRODUCTION_UNCAPPED_BUDGET=True,
        VORNEQ_AI_IMAGE_PRODUCTION_ENABLED=True,
        VORNEQ_AI_IMAGE_PRODUCTION_ALLOWED_USER_IDS="1",
        VORNEQ_AI_IMAGE_PRODUCTION_OWNER_AUTH="OWNER-AUTH-AI-IMAGE-PRODUCTION-TEST123",
        VORNEQ_AI_IMAGE_PRODUCTION_WORKER_SERVICE_ID="srv-aaaaaaaaaaaaaaaaaaaa",
        VORNEQ_AI_IMAGE_PRODUCTION_AUTHORIZED_SHA="a" * 40,
        VORNEQ_AI_EMERGENCY_STOP=False,
    )
    def test_worker_remains_closed_with_valid_identity(self):
        with patch.dict("os.environ", {
            "RENDER_SERVICE_ID": "srv-aaaaaaaaaaaaaaaaaaaa",
            "RENDER_GIT_COMMIT": "a" * 40,
            "VORNEQ_AI_DEPLOY_READ_TOKEN": "test-only",
        }), patch("apps.ai_core.deploy_authorization._verified_release", return_value=True):
            report = production_worker_preflight()
        self.assertFalse(report["ready"])
        self.assertFalse(report["checks"]["provider_activation_authorized"])

    def test_worker_never_claims_job(self):
        self.assertIsNone(process_production_image_job())
