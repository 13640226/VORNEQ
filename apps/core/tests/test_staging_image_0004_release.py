"""Fail-closed offline tests for the scoped Staging-only image 0004 runner."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.core import c02_owner_release as legacy
from apps.core import staging_image_0004_release as release
from apps.core import staging_image_0004_runner as runner

SHA = "a" * 40
BACKUP = "b" * 64
EVIDENCE = "STAGING-RESTORE-20261119-2319Z"
RELEASE_ID = "IMG0004-OWNER-20261120"
NOW = datetime(2026, 11, 20, 1, 0, tzinfo=timezone.utc)
ISSUE_URL = "https://api.github.com/repos/13640226/VORNEQ"


def comment(*, created=NOW, changed=False, sha=SHA, digest=BACKUP,
            decision=None, migrations=None, issue=release.ISSUE):
    manifest = {
        "decision": decision or release.DECISION,
        "release_id": RELEASE_ID,
        "sha": sha,
        "service_id": release.SERVICE,
        "postgres_id": release.POSTGRES,
        "database": release.DATABASE,
        "session_user": release.ROLE,
        "current_user": release.ROLE,
        "migrations": [release.MIGRATION] if migrations is None else migrations,
        "backup_sha256": digest,
        "backup_evidence": EVIDENCE,
        "backup_exported_at": (created-timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "restore_verified_at": (created-timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (created + timedelta(minutes=12)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_acceptance": release.RISK,
    }
    return {
        "id": 123456, "url": f"{ISSUE_URL}/issues/comments/123456",
        "issue_url": f"{ISSUE_URL}/issues/{issue}",
        "html_url":
            f"https://github.com/13640226/VORNEQ/issues/{issue}#issuecomment-123456",
        "user": {"login": "13640226", "id": 199411505, "type": "User"},
        "author_association": "OWNER",
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "updated_at": (created + timedelta(seconds=1) if changed else created
                       ).isoformat().replace("+00:00", "Z"),
        "body": release.HEADER + "\n" + json.dumps(manifest),
    }


def verify(comment_data, *, now=None):
    return release.validate_comment(
        comment_data, comment_id=123456, expected_sha=SHA, release_id=RELEASE_ID,
        backup_sha256=BACKUP, backup_evidence=EVIDENCE,
        now=now or NOW + timedelta(minutes=1),
    )


class GitHubStagingOwnerReleaseTests(SimpleTestCase):
    def test_exact_owner_grant_validates(self):
        proof = verify(comment())
        self.assertIsInstance(proof, legacy.VerifiedOwnerRelease)
        self.assertEqual(proof.sha, SHA)
        self.assertEqual(proof.backup_sha256, BACKUP)

    def test_wrong_issue_rejected(self):
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(comment(issue=407))

    def test_unrelated_scope_rejected(self):
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(comment(decision="AUTHORIZE_PRODUCTION_AI_CORE_0003_CONVERSATION"))

    def test_other_migration_rejected(self):
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(comment(migrations=["ai_core.0003_conversation"]))

    def test_backup_or_sha_drift_rejected(self):
        for variant in (comment(digest="c"*64), comment(sha="d"*40)):
            with self.subTest(variant=variant["body"][-50:]):
                with self.assertRaises(legacy.OwnerReleaseDenied):
                    verify(variant)

    def test_edited_comment_rejected(self):
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(comment(changed=True))

    def test_expired_comment_rejected(self):
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(comment(created=NOW-timedelta(hours=1)))

    def test_wrong_owner_rejected(self):
        v = comment()
        v["user"]["login"] = "someone-else"
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(v)

    def test_wrong_author_association_rejected(self):
        v = comment()
        v["author_association"] = "CONTRIBUTOR"
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(v)

    def test_wrong_comment_identity_rejected(self):
        v = comment()
        v["id"] += 1
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(v)

    def test_duplicate_manifest_keys_rejected(self):
        v = comment()
        v["body"] = release.HEADER + '\n{"decision":"A","decision":"B"}'
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(v)

    def test_no_token_no_network(self):
        with patch.object(legacy, "fetch_github_comment") as fetch:
            with self.assertRaises(legacy.OwnerReleaseDenied):
                release.verify_live(
                    {"VORNEQ_IMAGE_0004_OWNER_COMMENT_ID": "123456"},
                    expected_sha=SHA, release_id=RELEASE_ID,
                )
            fetch.assert_not_called()

    def test_bad_timestamp_rejected(self):
        v = comment()
        v["created_at"] = "nonsense"
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(v)

    def test_release_must_expire_within_fifteen_minutes(self):
        v = comment()
        body = json.loads(v["body"].split("\n", 1)[1])
        body["expires_at"] = (NOW+timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        v["body"] = release.HEADER + "\n" + json.dumps(body)
        with self.assertRaises(legacy.OwnerReleaseDenied):
            verify(v)

    def test_stale_backup_or_restoration_rejected(self):
        for field in ("backup_exported_at", "restore_verified_at"):
            with self.subTest(field=field):
                v = comment()
                body = json.loads(v["body"].split("\n", 1)[1])
                body[field] = (NOW-timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
                v["body"] = release.HEADER + "\n" + json.dumps(body)
                with self.assertRaises(legacy.OwnerReleaseDenied):
                    verify(v)


GOOD_SETTINGS = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": release.DATABASE,
    "USER": release.ROLE,
    "HOST": release.POSTGRES + ".oregon-postgres.render.com",
    "PORT": "5432",
}


def staging_env():
    return {
        "VORNEQ_ENV": "staging",
        "RENDER_SERVICE_ID": release.SERVICE,
        "RENDER_GIT_COMMIT": SHA,
        "VORNEQ_AI_IMAGE_ENABLED": "false",
        "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED": "false",
    }


@override_settings(VORNEQ_ENV="staging", DEBUG=False,
                   VORNEQ_AI_IMAGE_ENABLED=False,
                   VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=False)
class StagingRunnerGuardTests(SimpleTestCase):
    def test_matching_staging_runtime_is_read_only_eligible(self):
        runner.base_context(staging_env(), SHA, dict(GOOD_SETTINGS))

    def test_production_service_blocked_even_if_env_is_staging(self):
        env = staging_env()
        env["RENDER_SERVICE_ID"] = "srv-dadn07eq1p3s73eccau0"
        with self.assertRaises(runner.Refused):
            runner.base_context(env, SHA, dict(GOOD_SETTINGS))

    def test_wrong_database_or_host_or_login_blocked(self):
        for key, value in (
            ("NAME", "vorneq_production_db"),
            ("USER", "vorneq_production_db_user"),
            ("HOST", "dpg-dagru1h42hec73eqr960-a.oregon-postgres.render.com"),
            ("PORT", "6543"),
        ):
            with self.subTest(key=key):
                with self.assertRaises(runner.Refused):
                    runner.base_context(staging_env(), SHA, dict(GOOD_SETTINGS, **{key:value}))

    def test_sha_mismatch_denied(self):
        with self.assertRaises(runner.Refused):
            runner.base_context(staging_env(), "f"*40, dict(GOOD_SETTINGS))

    def test_image_gate_must_be_closed(self):
        env = staging_env()
        env["VORNEQ_AI_IMAGE_ENABLED"] = "true"
        with self.assertRaises(runner.Refused):
            runner.base_context(env, SHA, dict(GOOD_SETTINGS))

    def test_paid_gate_must_be_closed(self):
        env = staging_env()
        env["VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED"] = "true"
        with self.assertRaises(runner.Refused):
            runner.base_context(env, SHA, dict(GOOD_SETTINGS))

    def test_owner_arm_missing_denied(self):
        with self.assertRaises(runner.Refused):
            runner.base_context(staging_env(), SHA, dict(GOOD_SETTINGS), require_arm=True)

    def test_owner_arm_bound_to_sha(self):
        env = staging_env()
        env[runner.ARM_MODE_KEY] = runner.ARM_MODE
        env[runner.ARM_SHA_KEY] = SHA
        self.assertTrue(runner.arm_open(env, SHA))
        runner.base_context(env, SHA, dict(GOOD_SETTINGS), require_arm=True)
        self.assertFalse(runner.arm_open(env, "f"*40))

    def test_env_grant_cannot_fake_owner_issuance(self):
        env = staging_env()
        env[runner.ARM_MODE_KEY] = runner.ARM_MODE
        env[runner.ARM_SHA_KEY] = SHA
        env[runner.AUTH_KEY] = f"OWNER-AUTH-STAGING-AI-0004-{RELEASE_ID} @ {SHA}"
        with patch.object(release, "verify_live",
                          side_effect=legacy.OwnerReleaseDenied("no GitHub proof")) as fetch:
            with self.assertRaises(runner.Refused):
                runner.authorize(env, SHA, dict(GOOD_SETTINGS))
            fetch.assert_called_once()

    def test_no_grant_no_github_call(self):
        env = staging_env()
        env[runner.ARM_MODE_KEY] = runner.ARM_MODE
        env[runner.ARM_SHA_KEY] = SHA
        with patch.object(release, "verify_live") as fetch:
            with self.assertRaises(runner.Refused):
                runner.authorize(env, SHA, dict(GOOD_SETTINGS))
            fetch.assert_not_called()

    def test_preflight_without_valid_target_queries_no_db(self):
        mock_connection = Mock()
        mock_connection.settings_dict = dict(GOOD_SETTINGS, NAME="vorneq_production_db")
        with self.assertRaises(runner.Refused):
            runner.inspect(mock_connection, SHA, environ=staging_env())
        mock_connection.cursor.assert_not_called()

    def test_apply_without_verified_owner_never_queries_db(self):
        conn = Mock()
        conn.settings_dict = dict(GOOD_SETTINGS)
        with self.assertRaises(runner.Refused):
            runner.apply_once(conn, SimpleNamespace(), SHA, environ=staging_env())
        conn.cursor.assert_not_called()

    def test_reject_recovered_replica(self):
        bad = (123, release.DATABASE, release.ROLE, release.ROLE,
               "10.0.0.1", 5432, "off", True, 18, 22)
        with self.assertRaises(runner.Refused):
            runner.check_identity(bad, False)

    def test_reject_wrong_session_user(self):
        bad = (123, release.DATABASE, release.ROLE, "wrong",
               "10.0.0.1", 5432, "off", False, 18, 22)
        with self.assertRaises(runner.Refused):
            runner.check_identity(bad, False)

    def test_require_exact_one_migration_in_plan(self):
        mig = SimpleNamespace(app_label="ai_core", name="0004_image_generation_job_v1")
        fake = Mock()
        fake.migration_plan.return_value = [(mig, False)]
        fake.loader.detect_conflicts.return_value = {}
        with patch.object(runner, "MigrationExecutor", return_value=fake):
            self.assertIs(runner.exact_plan(Mock()), fake)
        fake.migration_plan.return_value = []
        with patch.object(runner, "MigrationExecutor", return_value=fake):
            with self.assertRaises(runner.Refused):
                runner.exact_plan(Mock())


class OneUseReceiptTests(SimpleTestCase):
    def _run_with_insert_result(self, receipt_result):
        connection = Mock()
        receipt_db = MagicMock()
        connection.copy.return_value = receipt_db
        receipt_db.get_autocommit.return_value = True
        cursor = receipt_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [("audit_auditevent",), receipt_result]
        proof = SimpleNamespace(
            comment_id=123456, backup_sha256=BACKUP, body_sha256="d"*64
        )
        target = runner.ApprovedTarget(RELEASE_ID, proof)
        with patch.object(runner, "snapshot",
                          return_value=(10, release.DATABASE, release.ROLE,
                                        release.ROLE, "10.2.0.1", 5432,
                                        "off", False, 18, None)):
            if receipt_result is None:
                with self.assertRaises(runner.Aborted):
                    runner.consume_one_use_receipt(connection, target, SHA)
            else:
                runner.consume_one_use_receipt(connection, target, SHA)
        receipt_db.close.assert_called_once()
        self.assertEqual(cursor.execute.call_count, 2)
        sql = cursor.execute.call_args_list[-1].args[0]
        self.assertIn("ON CONFLICT (event_id) DO NOTHING", sql)
        self.assertIn("staging.ai_image_0004_one_use_release_consumed", sql)

    def test_new_scoped_release_receipt_can_be_consumed(self):
        self._run_with_insert_result(("receipt-uuid",))

    def test_duplicate_release_receipt_is_denied(self):
        self._run_with_insert_result(None)
