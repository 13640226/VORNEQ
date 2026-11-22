"""Production image identity evidence must not authorize a paid route."""
import os
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from apps.ai_core.image_generation.policy import production_release_identity, production_enabled, enabled

SHA = "a" * 40
BASE = dict(VORNEQ_ENV="production", DEBUG=False,
    VORNEQ_AI_IMAGE_PRODUCTION_AUTHORIZED_SHA=SHA,
    VORNEQ_AI_IMAGE_PRODUCTION_OWNER_AUTH="OWNER-AUTH-AI-IMAGE-PRODUCTION-TEST-20261123",
    VORNEQ_AI_IMAGE_PRODUCTION_ALLOWED_USER_IDS="1",
    VORNEQ_AI_IMAGE_ENABLED=True, VORNEQ_AI_IMAGE_PRODUCTION_ENABLED=True,
    VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED=True, VORNEQ_AI_EMERGENCY_STOP=False)
ENV = {"RENDER_SERVICE_ID": "srv-dadn07eq1p3s73eccau0", "RENDER_GIT_COMMIT": SHA,
       "VORNEQ_AI_DEPLOY_READ_TOKEN": "test-read-token"}

class ProductionImageIdentityTests(SimpleTestCase):
    def test_attested_identity_still_cannot_unlock_paid_provider(self):
        with override_settings(**BASE), patch.dict(os.environ, ENV), patch(
            "apps.ai_core.deploy_authorization._verified_release", return_value=True
        ) as verified:
            self.assertTrue(production_release_identity())
            verified.assert_called_with("production", SHA)
            self.assertFalse(production_enabled())
            self.assertFalse(enabled())

    def test_missing_or_invalid_evidence_fails_closed(self):
        with override_settings(**BASE), patch.dict(os.environ, ENV), patch(
            "apps.ai_core.deploy_authorization._verified_release", return_value=False
        ):
            self.assertFalse(production_release_identity())
        with override_settings(**BASE), patch.dict(os.environ, ENV), patch(
            "apps.ai_core.deploy_authorization._verified_release", return_value=True
        ) as verified:
            with override_settings(VORNEQ_AI_IMAGE_PRODUCTION_ALLOWED_USER_IDS="1,3"):
                self.assertFalse(production_release_identity())
            with override_settings(VORNEQ_AI_IMAGE_PRODUCTION_OWNER_AUTH="OWNER-AUTH-AI-IMAGE-STAGING-TEST"):
                self.assertFalse(production_release_identity())
            with patch.dict(os.environ, {"RENDER_GIT_COMMIT": "b" * 40}):
                self.assertFalse(production_release_identity())
            with patch.dict(os.environ, {"RENDER_SERVICE_ID": "srv-dbm7dvc9v7es7393g70g"}):
                self.assertFalse(production_release_identity())
            with patch.dict(os.environ, {"VORNEQ_AI_DEPLOY_READ_TOKEN": ""}):
                self.assertFalse(production_release_identity())
            verified.assert_not_called()
