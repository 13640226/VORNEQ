"""Offline persistent image release binding, independent of chat."""
import os
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from apps.ai_core import deploy_authorization as proof
from apps.ai_core.image_generation import policy

OLD = "a"*40
LIVE = "b"*40
WEB = proof.SERVICES["staging"]
WORKER = "srv-wwwwwwwwwwwwwwwwwwww"

@override_settings(VORNEQ_ENV="staging", DEBUG=False,
    VORNEQ_AI_IMAGE_ENABLED=True, VORNEQ_AI_EMERGENCY_STOP=False,
    VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS=True,
    VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=False,
    VORNEQ_AI_IMAGE_PROVIDER="openai",
    VORNEQ_AI_IMAGE_AUTHORIZED_SHA=OLD,
    VORNEQ_AI_IMAGE_OWNER_AUTH="OWNER-AUTH-AI-IMAGE-STAGING-TEST-01",
    VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED=True,
    VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH="OWNER-AUTH-AI-IMAGE-PAID-WORKER-STAGING-TEST-01",
    VORNEQ_AI_IMAGE_WORKER_SERVICE_ID=WORKER, VORNEQ_AI_IMAGE_ALLOWED_USER_IDS="3")
class ImageDeploymentTests(SimpleTestCase):
    def setUp(self):
        proof._cache.clear()
        self.addCleanup(proof._cache.clear)

    def test_web_new_sha_independent_of_chat(self):
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": WEB, "RENDER_GIT_COMMIT": LIVE, "VORNEQ_AI_DEPLOY_READ_TOKEN": "synthetic"}), patch.object(proof,"verify_deployment",return_value=True) as verify:
            self.assertTrue(policy.enabled())
            self.assertFalse(proof.release_allowed("staging",OLD))
            verify.assert_called_once_with("staging",LIVE,"synthetic")

    def test_worker_new_sha_requires_separate_grant(self):
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": WORKER, "RENDER_GIT_COMMIT": LIVE, "VORNEQ_AI_DEPLOY_READ_TOKEN": "synthetic"}), patch.object(proof,"verify_deployment",return_value=True), patch.object(policy,"_paid_controls_ready",return_value=True):
            self.assertTrue(policy.paid_worker_enabled())
            self.assertFalse(policy.enabled())
            with override_settings(VORNEQ_AI_IMAGE_PAID_WORKER_OWNER_AUTH=""):
                self.assertFalse(policy.paid_worker_enabled())
            with override_settings(VORNEQ_AI_IMAGE_WORKER_SERVICE_ID=WEB):
                self.assertFalse(policy.paid_worker_enabled())
            with override_settings(VORNEQ_ENV="production"):
                self.assertFalse(policy.paid_worker_enabled())

    def test_missing_proof_fails_closed(self):
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": WEB, "RENDER_GIT_COMMIT": LIVE, "VORNEQ_AI_DEPLOY_READ_TOKEN": ""}), patch.object(proof,"verify_deployment") as verify:
            self.assertFalse(policy.enabled())
            verify.assert_not_called()
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": WEB, "RENDER_GIT_COMMIT": LIVE, "VORNEQ_AI_DEPLOY_READ_TOKEN": "synthetic"}), patch.object(proof,"verify_deployment",return_value=False):
            self.assertFalse(policy.enabled())

    def test_legacy_and_mock_keep_exact_sha(self):
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": WEB, "RENDER_GIT_COMMIT": LIVE}):
            with override_settings(VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS=False):
                self.assertFalse(policy.enabled())
            with override_settings(VORNEQ_AI_IMAGE_PROVIDER="mock"):
                self.assertFalse(policy.enabled())
            with override_settings(VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS=False, VORNEQ_AI_IMAGE_AUTHORIZED_SHA=LIVE):
                self.assertTrue(policy.enabled())
