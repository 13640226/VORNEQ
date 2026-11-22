import os
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from apps.ai_core import deploy_authorization as d

SHA = "a" * 40
OWNER = {"login": d.OWNER, "id": d.OWNER_ID, "type": "User"}
BOT = {"login": "github-actions[bot]", "id": d.BOT_ID, "type": "Bot"}


def records():
    return [
        [{"id": 10, "sha": SHA, "environment": "staging", "description": "authorized by DEPLOY-ABC", "creator": BOT, "created_at": "2026-11-22T01:00:00Z"}],
        [{"state": "success", "environment": "staging", "description": "DEPLOY-ABC: success", "creator": BOT}],
        [{"id": 11, "sha": SHA, "environment": "deploy-staging", "creator": OWNER, "performed_via_github_app": {"slug": "github-actions", "id": 15368}}],
        [{"state": "success", "environment": "deploy-staging", "creator": OWNER, "log_url": "https://github.com/13640226/VORNEQ/actions/runs/123/job/456"}],
        {"id": 123, "event": "workflow_dispatch", "path": ".github/workflows/deploy.yml", "head_branch": "main", "head_sha": SHA, "status": "completed", "conclusion": "success", "actor": OWNER, "triggering_actor": OWNER, "created_at": "2026-11-22T00:59:00Z", "updated_at": "2026-11-22T01:01:00Z"},
    ]


class DeploymentProofTests(SimpleTestCase):
    def test_official_deploy(self):
        with patch.object(d, "_get", side_effect=records()):
            self.assertTrue(d.verify_deployment("staging", SHA, "synthetic"))

    def test_reject_wrong_record_or_run(self):
        for index, changes in [(0, {"sha": "b"*40}), (0, {"creator": OWNER}),
                               (1, {"state": "failure"}), (1, {"description": "wrong"}),
                               (2, {"performed_via_github_app": {}}),
                               (3, {"log_url": "https://evil.example/runs/123/job/456"}),
                               (4, {"actor": BOT}), (4, {"triggering_actor": BOT}),
                               (4, {"path": ".github/workflows/other.yml"}),
                               (4, {"conclusion": "failure"}), (4, {"head_sha": "b"*40})]:
            values = records()
            if isinstance(values[index], list):
                values[index][0] = {**values[index][0], **changes}
            else:
                values[index] = {**values[index], **changes}
            with self.subTest(index=index, changes=changes), patch.object(d, "_get", side_effect=values):
                if index == 0 and "sha" in changes:
                    with self.assertRaises(ValueError):
                        d.verify_deployment("staging", SHA, "synthetic")
                else:
                    self.assertFalse(d.verify_deployment("staging", SHA, "synthetic"))

    @override_settings(VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=False)
    def test_legacy_sha_unchanged(self):
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": SHA}), patch.object(d, "verify_deployment") as verify:
            self.assertTrue(d.release_allowed("staging", SHA))
            self.assertFalse(d.release_allowed("staging", "b"*40))
            verify.assert_not_called()

    @override_settings(VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=True, VORNEQ_ENV="staging", DEBUG=False)
    def test_opt_in_fails_closed_when_no_token_or_proof(self):
        d._cache.clear()
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": SHA, "RENDER_SERVICE_ID": d.SERVICES["staging"], "VORNEQ_AI_DEPLOY_READ_TOKEN": ""}):
            self.assertFalse(d.release_allowed("staging", SHA))
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": SHA, "RENDER_SERVICE_ID": d.SERVICES["staging"], "VORNEQ_AI_DEPLOY_READ_TOKEN": "synthetic"}), patch.object(d, "verify_deployment", side_effect=OSError):
            self.assertFalse(d.release_allowed("staging", SHA))
        d._cache.clear()

    @override_settings(VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=True, VORNEQ_ENV="staging", DEBUG=False)
    def test_opt_in_accepts_verified_new_sha(self):
        d._cache.clear()
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": SHA, "RENDER_SERVICE_ID": d.SERVICES["staging"], "VORNEQ_AI_DEPLOY_READ_TOKEN": "synthetic"}), patch.object(d, "verify_deployment", return_value=True) as verify:
            self.assertTrue(d.release_allowed("staging", "b"*40))
            self.assertTrue(d.release_allowed("staging", "b"*40))
            verify.assert_called_once()
        d._cache.clear()
