"""Release diagnostics must not grant access or disclose runtime values."""
import json
import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings

from apps.ai_core import deploy_authorization as proof
from apps.ai_core import release_diagnostics as diag
from apps.ai_core.tests.test_chat_deploy_authorization import records, SHA

ENV = {
    "RENDER_GIT_COMMIT": SHA,
    "RENDER_SERVICE_ID": proof.SERVICES["staging"],
    "VORNEQ_AI_DEPLOY_READ_TOKEN": "PRIVATE_DEPLOY_TOKEN",
    "OPENAI_API_KEY": "PRIVATE_TEXT_KEY",
    "VORNEQ_AI_PHASE_B_MODEL": "private-model",
}
SETTINGS = dict(
    VORNEQ_ENV="staging", DEBUG=False,
    VORNEQ_AI_EMERGENCY_STOP=False,
    VORNEQ_AI_STAGING_TRIAL_ENABLED=True,
    VORNEQ_AI_CORE_ENABLED=True,
    VORNEQ_AI_PHASE_B_ENABLED=True,
    VORNEQ_GLOBAL_AI_ENABLED=True,
    VORNEQ_AI_STAGING_UNMETERED=True,
    VORNEQ_AI_STAGING_APPROVED_MODEL="private-model",
    VORNEQ_AI_STAGING_OWNER_AUTH="OWNER-AUTH-AI-STAGING-PRIVATE-001",
    VORNEQ_AI_STAGING_ALLOWED_USER_IDS="123456",
    VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=True,
    VORNEQ_AI_STAGING_AUTHORIZED_SHA="b" * 40,
    VORNEQ_AI_IMAGE_ENABLED=True,
    VORNEQ_AI_IMAGE_UI_ENABLED=True,
    VORNEQ_AI_IMAGE_PROVIDER="openai",
    VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS=True,
    VORNEQ_AI_IMAGE_OWNER_AUTH="OWNER-AUTH-AI-IMAGE-STAGING-PRIVATE-001",
    VORNEQ_AI_IMAGE_ALLOWED_USER_IDS="123456",
)


@override_settings(**SETTINGS)
class DiagnosticsTests(SimpleTestCase):
    def report(self, verify=False):
        with patch.dict(os.environ, ENV, clear=True), patch.object(
            diag.image, "_paid_controls_ready", return_value=True
        ):
            return diag.build_report("staging", verify=verify)

    def test_offline_is_default_and_never_uses_network(self):
        with patch.object(proof, "_get", side_effect=AssertionError) as get:
            report = self.report()
        get.assert_not_called()
        for key in ("chat_page", "global_chat", "image_studio"):
            self.assertEqual(report[key]["status"], "NOT_VERIFIED")
            self.assertEqual(report[key]["reasons"], ["NOT_VERIFIED"])
        self.assertEqual(report["evidence_mode"], "OFFLINE")

    def test_shared_fresh_evidence_does_not_modify_cache(self):
        with patch.object(proof, "_get", side_effect=records()) as get, patch.object(
            proof, "_cache", {"sentinel": "unchanged"}
        ):
            report = self.report(verify=True)
            self.assertEqual(proof._cache, {"sentinel": "unchanged"})
        self.assertEqual(get.call_count, 5)
        for key in ("chat_page", "global_chat", "image_studio"):
            self.assertEqual(report[key]["status"], "CONFIGURATION_READY")
            self.assertEqual(report[key]["actor_access"], "NOT_VERIFIED")
            self.assertEqual(report[key]["provider_delivery"], "NOT_VERIFIED")
        rendered = json.dumps(report)
        for value in ("PRIVATE", "private-model", "123456", SHA):
            self.assertNotIn(value, rendered)

    def test_drift_blocks_both_capabilities(self):
        rows = records()
        rows[0][0]["sha"] = "b" * 40
        with patch.object(proof, "_get", side_effect=rows):
            report = self.report(verify=True)
        for key in ("chat_page", "image_studio"):
            self.assertEqual(report[key]["status"], "BLOCKED")
            self.assertIn("DEPLOYMENT_SHA_OR_ENVIRONMENT_DRIFT", report[key]["reasons"])

    def test_transport_error_is_redacted_and_fail_closed(self):
        with patch.object(proof, "_get", side_effect=OSError("PRIVATE_DSN")):
            report = self.report(verify=True)
        self.assertIn("DEPLOYMENT_EVIDENCE_UNAVAILABLE", report["chat_page"]["reasons"])
        self.assertNotIn("PRIVATE_DSN", json.dumps(report))

    def test_missing_token_and_legacy_pin(self):
        with patch.dict(os.environ, {**ENV, "VORNEQ_AI_DEPLOY_READ_TOKEN": ""}, clear=True), patch.object(
            proof, "_get", side_effect=AssertionError
        ) as get:
            report = diag.build_report("staging", verify=True)
            self.assertIn("DEPLOY_READ_TOKEN_MISSING", report["chat_page"]["reasons"])
        get.assert_not_called()
        with override_settings(VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=False):
            report = self.report()
        self.assertIn("LEGACY_SHA_MISMATCH", report["chat_page"]["reasons"])

    @override_settings(VORNEQ_AI_EMERGENCY_STOP=True, VORNEQ_AI_IMAGE_UI_ENABLED=False)
    def test_static_blockers_are_not_masked_by_unverified_release(self):
        report = self.report()
        self.assertEqual(report["chat_page"]["status"], "BLOCKED")
        self.assertIn("EMERGENCY_STOP_ACTIVE", report["chat_page"]["reasons"])
        self.assertIn("IMAGE_UI_DISABLED", report["image_studio"]["reasons"])

    @override_settings(VORNEQ_GLOBAL_AI_ENABLED=False)
    def test_chat_page_and_global_chat_are_distinct(self):
        with patch.object(proof, "_get", side_effect=records()):
            report = self.report(verify=True)
        self.assertEqual(report["chat_page"]["status"], "CONFIGURATION_READY")
        self.assertIn("GLOBAL_AI_DISABLED", report["global_chat"]["reasons"])

    @override_settings(VORNEQ_AI_IMAGE_PROVIDER="mock", VORNEQ_AI_IMAGE_AUTHORIZED_SHA=SHA)
    def test_mock_image_uses_legacy_pin_even_with_follow_enabled(self):
        report = self.report()
        self.assertEqual(report["image_studio"]["status"], "CONFIGURATION_READY")

    def test_workflow_evidence_reasons_preserve_boolean_policy(self):
        cases = [
            (0, {"description": "PRIVATE_MARKER"}, "DEPLOYMENT_MARKER_OR_CREATOR_INVALID"),
            (1, {"state": "failure"}, "DEPLOYMENT_STATUS_INVALID"),
            (2, {"performed_via_github_app": {}}, "JOB_CREATOR_OR_APP_INVALID"),
            (3, {"log_url": "https://invalid.example/"}, "JOB_STATUS_OR_LOG_INVALID"),
            (4, {"conclusion": "failure"}, "WORKFLOW_EVIDENCE_INVALID"),
        ]
        for index, changes, reason in cases:
            values = records()
            row = values[index][0] if isinstance(values[index], list) else values[index]
            row.update(changes)
            with self.subTest(reason=reason):
                with patch.object(proof, "_get", side_effect=values):
                    self.assertEqual(proof._deployment_reason("staging", SHA, "token"), reason)
                with patch.object(proof, "_get", side_effect=values):
                    self.assertFalse(proof.verify_deployment("staging", SHA, "token"))

    def test_command_validates_identity_and_redacts_errors(self):
        with patch.dict(os.environ, ENV, clear=True), patch(
            "apps.ai_core.management.commands.audit_ai_release.build_report",
            side_effect=RuntimeError("PRIVATE_SECRET"),
        ) as build:
            with self.assertRaisesMessage(CommandError, "INVALID_HOSTED_IDENTITY"):
                call_command("audit_ai_release", environment="staging", expected_sha="b"*40)
            build.assert_not_called()
            with self.assertRaisesMessage(CommandError, "AI_RELEASE_DIAGNOSTIC_INCOMPLETE"):
                call_command("audit_ai_release", environment="staging", expected_sha=SHA)
        with patch.dict(os.environ, ENV, clear=True), patch.object(proof, "_get") as get:
            out = StringIO()
            call_command("audit_ai_release", environment="staging", expected_sha=SHA, stdout=out)
            self.assertEqual(json.loads(out.getvalue())["evidence_mode"], "OFFLINE")
            get.assert_not_called()

    @override_settings(VORNEQ_ENV="production", VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED=True)
    def test_production_preview_is_independent_and_not_paid(self):
        with patch.dict(os.environ, {**ENV, "RENDER_SERVICE_ID": proof.SERVICES["production"]},
                        clear=True), patch.object(proof, "_get") as get:
            report = diag.build_report("production")
        self.assertEqual(report["image_studio"]["status"], "CONFIGURATION_READY")
        self.assertEqual(report["image_studio"]["mode"], "READ_ONLY_PREVIEW")
        self.assertEqual(report["image_studio"]["release_evidence"], "NOT_APPLICABLE")
        get.assert_not_called()
