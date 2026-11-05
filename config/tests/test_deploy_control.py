"""Tests for scripts/deploy_control.py and the /health/ release identifier (G4)."""

import importlib.util
import os
import sys
import urllib.error
from pathlib import Path
from unittest import TestCase, mock

from django.test import TestCase as DjangoTestCase
from django.urls import reverse

from config.health import release_identifier

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "deploy_control.py"
_SPEC = importlib.util.spec_from_file_location("vorneq_deploy_control", _PATH)
dc = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = dc
_SPEC.loader.exec_module(dc)

OWNER = "13640226"
SHA = "a" * 40
OTHER = "b" * 40
T0 = "2026-11-05T10:00:00Z"
T1 = "2026-11-05T10:05:00Z"


def comment(body, *, cid=1, login=OWNER, assoc="OWNER", created=T0, updated=None, user_type="User"):
    return {"id": cid, "body": body, "user": {"login": login, "type": user_type},
            "author_association": assoc, "created_at": created, "updated_at": updated or created}


def auth(env="staging", sha=SHA, auth_id="OWNER-AUTH-DEPLOY-TEST-01"):
    return f"OWNER-AUTH-DEPLOY {auth_id} {env} @ {sha}"


class DecideDeployTests(TestCase):
    def test_no_authorization_denies(self):
        self.assertFalse(dc.decide_deploy("staging", SHA, [comment("bitte deployen")]).allowed)

    def test_valid_authorization_allows(self):
        decision = dc.decide_deploy("staging", SHA, [comment(auth())])
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.auth_id, "OWNER-AUTH-DEPLOY-TEST-01")

    def test_other_environment_denies(self):
        self.assertFalse(dc.decide_deploy("production", SHA, [comment(auth("staging"))]).allowed)

    def test_other_sha_denies(self):
        self.assertFalse(dc.decide_deploy("staging", SHA, [comment(auth(sha=OTHER))]).allowed)

    def test_short_sha_and_extra_text_deny(self):
        self.assertFalse(dc.decide_deploy("staging", SHA, [comment(auth(sha=SHA[:7]))]).allowed)
        self.assertFalse(dc.decide_deploy("staging", SHA, [comment(auth() + " jetzt")]).allowed)
        self.assertFalse(dc.decide_deploy("staging", SHA, [comment("> " + auth())]).allowed)

    def test_other_account_or_bot_denies(self):
        self.assertFalse(dc.decide_deploy("staging", SHA, [comment(auth(), login="hamidrezaasadian7-boop", assoc="COLLABORATOR")]).allowed)
        self.assertFalse(dc.decide_deploy("staging", SHA, [comment(auth(), assoc="COLLABORATOR")]).allowed)
        self.assertFalse(dc.decide_deploy("staging", SHA, [comment(auth(), user_type="Bot")]).allowed)

    def test_edited_authorization_denies(self):
        self.assertFalse(dc.decide_deploy("staging", SHA, [comment(auth(), updated=T1)]).allowed)

    def test_revoke_cancels_only_that_authorization(self):
        revoked = [comment(auth(), cid=1), comment("OWNER-AUTH-DEPLOY-REVOKE OWNER-AUTH-DEPLOY-TEST-01", cid=2, created=T1)]
        self.assertFalse(dc.decide_deploy("staging", SHA, revoked).allowed)
        other_revoked = [comment(auth(), cid=1), comment("OWNER-AUTH-DEPLOY-REVOKE OTHER-ID-01", cid=2, created=T1)]
        self.assertTrue(dc.decide_deploy("staging", SHA, other_revoked).allowed)

    def test_revoke_by_other_account_is_ignored(self):
        comments = [comment(auth(), cid=1),
                    comment("OWNER-AUTH-DEPLOY-REVOKE OWNER-AUTH-DEPLOY-TEST-01", cid=2, created=T1, login="x", assoc="NONE")]
        self.assertTrue(dc.decide_deploy("staging", SHA, comments).allowed)

    def test_invalid_inputs_deny(self):
        self.assertFalse(dc.decide_deploy("prod", SHA, [comment(auth())]).allowed)
        self.assertFalse(dc.decide_deploy("staging", "A" * 40, [comment(auth())]).allowed)
        self.assertFalse(dc.decide_deploy("staging", SHA, None).allowed)
        self.assertFalse(dc.decide_deploy("staging", SHA, [{"body": auth()}]).allowed)


class HelperTests(TestCase):
    def test_sha_contained_in_main(self):
        self.assertTrue(dc.sha_contained_in_main("identical"))
        self.assertTrue(dc.sha_contained_in_main("ahead"))
        for status in ("behind", "diverged", None, ""):
            self.assertFalse(dc.sha_contained_in_main(status))

    def test_required_checks(self):
        green = [{"name": n, "status": "completed", "conclusion": "success", "completed_at": T0}
                 for n in dc.REQUIRED_MAIN_CHECKS]
        self.assertTrue(dc.required_checks_green(green)[0])
        self.assertFalse(dc.required_checks_green(green[:-1])[0])
        red = green[:-1] + [{**green[-1], "conclusion": "failure"}]
        self.assertFalse(dc.required_checks_green(red)[0])
        rerun = red + [{**green[-1], "completed_at": T1}]
        self.assertTrue(dc.required_checks_green(rerun)[0])
        self.assertFalse(dc.required_checks_green(None)[0])

    def test_deployment_succeeded_uses_newest_status(self):
        self.assertTrue(dc.deployment_succeeded([{"state": "success"}, {"state": "in_progress"}]))
        self.assertFalse(dc.deployment_succeeded([{"state": "failure"}, {"state": "success"}]))
        self.assertFalse(dc.deployment_succeeded([]))

    def test_watch_verdict_is_fail_closed(self):
        self.assertTrue(dc.watch_verdict("staging", SHA, SHA)[0])
        self.assertTrue(dc.watch_verdict("staging", SHA[:12], SHA)[0])
        self.assertFalse(dc.watch_verdict("staging", OTHER, SHA)[0])
        self.assertFalse(dc.watch_verdict("staging", "unknown", SHA)[0])
        self.assertFalse(dc.watch_verdict("staging", None, SHA)[0])
        self.assertFalse(dc.watch_verdict("staging", SHA, None)[0])


class PreflightTests(TestCase):
    def _gh(self, *, compare="ahead", checks=None, comments=None, staged=True):
        gh = mock.Mock()
        gh.compare_status.return_value = compare
        gh.check_runs.return_value = checks if checks is not None else [
            {"name": n, "status": "completed", "conclusion": "success", "completed_at": T0}
            for n in dc.REQUIRED_MAIN_CHECKS]
        gh.issue_comments.return_value = comments if comments is not None else [comment(auth("staging")), comment(auth("production"), cid=2)]
        gh.deployments.return_value = [{"id": 7}] if staged else []
        gh.deployment_statuses.return_value = [{"state": "success"}]
        return gh

    def test_staging_allows(self):
        self.assertEqual(dc.preflight(self._gh(), "staging", SHA, 448, OWNER, OWNER), "OWNER-AUTH-DEPLOY-TEST-01")

    def test_other_actor_rejected(self):
        with self.assertRaises(dc.DeployRejected):
            dc.preflight(self._gh(), "staging", SHA, 448, "someone", OWNER)
        with self.assertRaises(dc.DeployRejected):
            dc.preflight(self._gh(), "staging", SHA, 448, OWNER, "someone")

    def test_sha_not_on_main_rejected(self):
        with self.assertRaises(dc.DeployRejected):
            dc.preflight(self._gh(compare="diverged"), "staging", SHA, 448, OWNER, OWNER)

    def test_red_ci_rejected(self):
        with self.assertRaises(dc.DeployRejected):
            dc.preflight(self._gh(checks=[]), "staging", SHA, 448, OWNER, OWNER)

    def test_missing_authorization_rejected(self):
        with self.assertRaises(dc.DeployRejected):
            dc.preflight(self._gh(comments=[]), "staging", SHA, 448, OWNER, OWNER)

    def test_production_requires_successful_staging(self):
        self.assertTrue(dc.preflight(self._gh(), "production", SHA, 448, OWNER, OWNER))
        with self.assertRaises(dc.DeployRejected):
            dc.preflight(self._gh(staged=False), "production", SHA, 448, OWNER, OWNER)

    def test_main_preflight_api_error_is_fail_closed(self):
        env = {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r", "GITHUB_ACTOR": OWNER, "GITHUB_TRIGGERING_ACTOR": OWNER}
        gh = self._gh()
        gh.compare_status.side_effect = urllib.error.URLError("down")
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(dc, "GitHub", return_value=gh):
            self.assertEqual(dc.main(["preflight", "--environment", "staging", "--sha", SHA]), 1)

    def test_trigger_rejects_malformed_hook_without_network(self):
        with mock.patch.dict(os.environ, {"RENDER_DEPLOY_HOOK_URL": "https://example.com/x"}, clear=True), \
                mock.patch.object(dc.urllib.request, "urlopen") as urlopen:
            self.assertEqual(dc.main(["trigger", "--environment", "staging", "--sha", SHA]), 1)
            urlopen.assert_not_called()


class HardeningTests(TestCase):
    """Fixes from the 2026-11-05 staging/production runs (OWNER-AUTH-BUILD-DEPLOY-CONTROL-02)."""

    STAGING_HOOK = "https://api.render.com/deploy/srv-dbm7dvc9v7es7393g70g?key=abc"
    PROD_HOOK = "https://api.render.com/deploy/srv-dadn07eq1p3s73eccau0?key=abc"

    def _gh(self, deployments=None):
        gh = PreflightTests._gh(PreflightTests())
        if deployments is not None:
            gh.deployments.side_effect = lambda env, sha=None: deployments.get(env, [])
        return gh

    def test_normalize_sha_strips_pasted_whitespace(self):
        self.assertEqual(dc.normalize_sha("   " + SHA + "\n"), SHA)
        self.assertEqual(dc.normalize_sha(SHA.upper()), SHA)
        self.assertEqual(dc.normalize_sha(None), "")

    def test_main_accepts_padded_sha_input(self):
        env = {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r", "GITHUB_ACTOR": OWNER, "GITHUB_TRIGGERING_ACTOR": OWNER}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(dc, "GitHub", return_value=self._gh()):
            self.assertEqual(dc.main(["preflight", "--environment", "staging", "--sha", "   " + SHA]), 0)

    def test_hook_of_other_service_is_rejected_without_network(self):
        with mock.patch.object(dc.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(dc.DeployRejected):
                dc.trigger_hook(self.STAGING_HOOK, SHA, "production")
            with self.assertRaises(dc.DeployRejected):
                dc.trigger_hook(self.PROD_HOOK, SHA, "staging")
            with self.assertRaises(dc.DeployRejected):
                dc.trigger_hook("https://api.render.com/deploy/srv-other?key=x", SHA, "production")
            urlopen.assert_not_called()

    def test_hook_of_expected_service_is_called(self):
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        with mock.patch.object(dc.urllib.request, "urlopen", return_value=response) as urlopen:
            dc.trigger_hook(self.PROD_HOOK, SHA, "production")
        self.assertIn("ref=" + SHA, urlopen.call_args[0][0].full_url)

    def test_authorization_is_single_use(self):
        used = {"staging": [{"id": 1, "description": "authorized by OWNER-AUTH-DEPLOY-TEST-01"}]}
        with self.assertRaises(dc.DeployRejected):
            dc.preflight(self._gh(used), "staging", SHA, 448, OWNER, OWNER)
        other = {"staging": [{"id": 1, "description": "authorized by OTHER-01"}]}
        self.assertEqual(dc.preflight(self._gh(other), "staging", SHA, 448, OWNER, OWNER), "OWNER-AUTH-DEPLOY-TEST-01")

    def test_authorization_used_is_fail_closed(self):
        with self.assertRaises(dc.DeployRejected):
            dc.authorization_used(None, "X-01")

    def test_sha_already_live_is_rejected(self):
        with self.assertRaises(dc.DeployRejected):
            dc.preflight(self._gh(), "staging", SHA, 448, OWNER, OWNER, live_release=SHA)
        self.assertTrue(dc.preflight(self._gh(), "staging", SHA, 448, OWNER, OWNER, live_release=OTHER))
        self.assertTrue(dc.preflight(self._gh(), "staging", SHA, 448, OWNER, OWNER, live_release=None))

    def test_unknown_sha_gets_clear_message(self):
        gh = dc.GitHub("t", "o/r")
        error = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        with mock.patch.object(gh, "request", side_effect=error):
            with self.assertRaisesRegex(dc.DeployRejected, "not found"):
                gh.compare_status(SHA)


class HealthReleaseTests(DjangoTestCase):
    def test_release_prefers_override_then_render_commit(self):
        with mock.patch.dict(os.environ, {"RENDER_GIT_COMMIT": SHA}, clear=False):
            os.environ.pop("VORNEQ_RELEASE", None)
            self.assertEqual(release_identifier(), SHA)
        with mock.patch.dict(os.environ, {"VORNEQ_RELEASE": "abc1234", "RENDER_GIT_COMMIT": SHA}, clear=False):
            self.assertEqual(release_identifier(), "abc1234")

    def test_release_never_echoes_non_sha_values(self):
        with mock.patch.dict(os.environ, {"VORNEQ_RELEASE": "<script>", "RENDER_GIT_COMMIT": "main"}, clear=False):
            self.assertEqual(release_identifier(), "unknown")

    def test_health_endpoint_reports_render_commit(self):
        with mock.patch.dict(os.environ, {"RENDER_GIT_COMMIT": SHA}, clear=False):
            os.environ.pop("VORNEQ_RELEASE", None)
            payload = self.client.get(reverse("health")).json()
        self.assertEqual(payload["release"], SHA)
