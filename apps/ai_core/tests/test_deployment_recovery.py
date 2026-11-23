"""Manual-live evidence is advisory and never authorizes Production Chat."""
from django.test import SimpleTestCase
from apps.ai_core.deployment_recovery import classify_release

SHA = "a" * 40
OLD = "b" * 40


class DeploymentRecoveryClassificationTests(SimpleTestCase):
    def test_manual_live_without_official_proof_is_not_approved(self):
        self.assertEqual(classify_release(follow_owner_deployments=True, live_sha=SHA,
                         authorized_sha=OLD, official_release_allowed=False,
                         render_live_confirmed=True), "manual_live_without_official_proof")

    def test_official_proof_required_even_if_sha_matches(self):
        self.assertEqual(classify_release(follow_owner_deployments=True, live_sha=SHA,
                         authorized_sha=SHA, official_release_allowed=False,
                         render_live_confirmed=True), "manual_live_without_official_proof")

    def test_official_proof_verified(self):
        self.assertEqual(classify_release(follow_owner_deployments=True, live_sha=SHA,
                         authorized_sha=OLD, official_release_allowed=True), "official_proof_verified")

    def test_legacy_sha_mismatch(self):
        self.assertEqual(classify_release(follow_owner_deployments=False, live_sha=SHA,
                         authorized_sha=OLD, official_release_allowed=False), "authorized_sha_mismatch")

    def test_invalid_sha(self):
        self.assertEqual(classify_release(follow_owner_deployments=True, live_sha="bad",
                         authorized_sha="bad", official_release_allowed=True), "invalid_runtime_sha")
