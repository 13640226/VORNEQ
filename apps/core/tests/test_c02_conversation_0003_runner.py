"""C02 0003: fail-closed offline tests and disposable PostgreSQL integration."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase

from apps.core import c02_conversation_0003_release as release
from apps.core import c02_conversation_0003_runner as runner
from apps.core import c02_owner_release as legacy
from apps.core import c02_stage_c_runner as previous

SHA = "a" * 40
NOW = datetime(2026, 11, 17, 21, 40, tzinfo=timezone.utc)
RELEASE_ID = "CONVERSATION-0003-V1"
BACKUP = "b" * 64
EVIDENCE = "TEST-RESTORE-PASS-NO-PRODUCTION"


def signed_comment(*, created=NOW, sha=SHA, decision=release.DECISION,
                   migrations=None, digest=BACKUP, revision=False):
    fields = {
        "decision": decision, "release_id": RELEASE_ID, "sha": sha,
        "service_id": "srv-dadn07eq1p3s73eccau0",
        "postgres_id": "dpg-dagru1h42hec73eqr960-a",
        "database": "vorneq_production_db",
        "session_user": "vorneq_prod_app_rot_20261116",
        "current_user": "vorneq_production_db_user",
        "migrations": migrations or ["ai_core.0003_conversation"],
        "backup_sha256": digest, "backup_evidence": EVIDENCE,
        "expires_at": (created + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "risk_acceptance": "ACCEPT_RENDER_OPERATIONAL_IDENTITY_LIMIT",
    }
    root = "https://api.github.com/repos/13640226/VORNEQ"
    return {
        "id": 123456, "url": root + "/issues/comments/123456",
        "issue_url": root + "/issues/407",
        "html_url": "https://github.com/13640226/VORNEQ/issues/407#issuecomment-123456",
        "user": {"login": "13640226", "id": 199411505, "type": "User"},
        "author_association": "OWNER",
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "updated_at": (created + timedelta(seconds=1) if revision else created
                       ).isoformat().replace("+00:00", "Z"),
        "body": release.HEADER + "\n" + json.dumps(fields, separators=(",", ":")),
    }


def check(comment):
    return release.validate_comment(
        comment, comment_id=123456, expected_sha=SHA, release_id=RELEASE_ID,
        backup_digest=BACKUP, backup_evidence=EVIDENCE,
        now=NOW + timedelta(minutes=1),
    )


class OwnerContractTests(SimpleTestCase):
    def test_new_scope_and_exact_sha(self):
        proof = check(signed_comment())
        self.assertIsInstance(proof, legacy.VerifiedOwnerRelease)
        self.assertEqual(proof.sha, SHA)

    def test_old_0001_0002_scope_rejected(self):
        with self.assertRaises(legacy.OwnerReleaseDenied):
            check(signed_comment(decision="AUTHORIZE_PRODUCTION_AI_CORE_0001_0002",
                                 migrations=["ai_core.0001_initial",
                                             "ai_core.0002_aichatrequestguard"]))

    def test_wrong_sha_or_backup_rejected(self):
        for comment in (signed_comment(sha="f" * 40),
                        signed_comment(digest="0" * 64)):
            with self.assertRaises(legacy.OwnerReleaseDenied):
                check(comment)

    def test_old_or_edited_owner_grant_rejected(self):
        for comment in (signed_comment(created=NOW - timedelta(hours=1)),
                        signed_comment(revision=True)):
            with self.assertRaises(legacy.OwnerReleaseDenied):
                check(comment)

    def test_wrong_actor_and_comment_origin_rejected(self):
        for key, value in (("author_association", "CONTRIBUTOR"),
                           ("issue_url", "https://api.github.com/repos/13640226/VORNEQ/issues/448"),
                           ("id", 123457)):
            with self.subTest(key=key):
                comment = signed_comment()
                comment[key] = value
                with self.assertRaises(legacy.OwnerReleaseDenied):
                    check(comment)

    def test_duplicate_manifest_keys_rejected(self):
        comment = signed_comment()
        comment["body"] = release.HEADER + '\n{"decision":"x","decision":"y"}'
        with self.assertRaises(legacy.OwnerReleaseDenied):
            check(comment)

    def test_missing_token_fails_before_network(self):
        with patch.object(legacy, "fetch_github_comment") as fetch:
            with self.assertRaises(legacy.OwnerReleaseDenied):
                release.verify_live({}, expected_sha=SHA, release_id=RELEASE_ID)
            fetch.assert_not_called()


class GuardTests(SimpleTestCase):
    def prod_env(self):
        return {
            "VORNEQ_C02_0003_WRITE_MODE": "ONE_USE_OWNER_RELEASE",
            "VORNEQ_C02_0003_ARMED_SHA": SHA,
            "VORNEQ_ENV": "production",
            "RENDER_SERVICE_ID": "srv-dadn07eq1p3s73eccau0",
            "RENDER_GIT_COMMIT": SHA,
            "VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED": "false",
            "VORNEQ_AI_CONVERSATIONS_ENABLED": "false",
        }

    def test_arm_requires_sha_and_service(self):
        good = self.prod_env()
        self.assertTrue(runner.arm_open(good, SHA))
        for key, value in (("RENDER_GIT_COMMIT", "b" * 40),
                           ("RENDER_SERVICE_ID", "unexpected"),
                           ("VORNEQ_C02_0003_ARMED_SHA", "b" * 40),
                           ("VORNEQ_C02_0003_WRITE_MODE", "")):
            with self.subTest(key=key):
                env = good.copy()
                env[key] = value
                self.assertFalse(runner.arm_open(env, SHA))

    def test_ai_writes_must_be_disabled(self):
        env = self.prod_env()
        self.assertTrue(runner._ai_writes_stopped(env))
        env["VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED"] = "true"
        self.assertFalse(runner._ai_writes_stopped(env))
        env["VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED"] = "false"
        env["VORNEQ_AI_CONVERSATIONS_ENABLED"] = "true"
        self.assertFalse(runner._ai_writes_stopped(env))

    def test_no_scoped_owner_auth_blocks_before_sql(self):
        env = self.prod_env()
        with patch.object(release, "verify_live") as verifier:
            with self.assertRaises(runner.Refused):
                runner.authorize("production", env, SHA, {}, SHA)
            verifier.assert_not_called()

    def test_legacy_arm_cannot_authorize_new_runner(self):
        env = self.prod_env()
        del env["VORNEQ_C02_0003_WRITE_MODE"]
        env["VORNEQ_C02_STAGE_C_WRITE_MODE"] = "ONE_USE_OWNER_RELEASE"
        self.assertFalse(runner.arm_open(env, SHA))

    def test_lab_rejects_render_context_and_prod_db(self):
        env = {"VORNEQ_ENV": "development", "C02_CONV_0003_LAB": "YES"}
        db = {"ENGINE": "django.db.backends.postgresql", "HOST": "postgres",
              "NAME": "test_vorneq", "USER": "vorneq"}
        with self.assertRaises(runner.Refused):
            runner.authorize("lab", dict(env, RENDER_SERVICE_ID="accidental"), SHA, db, SHA)
        with self.assertRaises(runner.Refused):
            runner.authorize("lab", env, SHA, dict(db, NAME="vorneq_production_db"), SHA)

    def test_run_without_prod_arm_touches_no_db(self):
        target = previous.Target("production", "vorneq_production_db",
                                 "vorneq_production_db_user", 18)
        with self.assertRaises(runner.Refused):
            runner.run(SimpleNamespace(), target, SHA, commit=True,
                       source_sha=lambda: SHA, environ={})

    def test_planner_denies_unexpected_migrations(self):
        fake = Mock()
        executor = Mock()
        executor.loader.detect_conflicts.return_value = {}
        node = SimpleNamespace(app_label="ai_core", name="0003_conversation")
        executor.migration_plan.return_value = [(node, False), (node, True)]
        with patch.object(runner, "MigrationExecutor", return_value=executor):
            with self.assertRaises(runner.Aborted):
                runner._plan(fake)


class DisposablePostgresRunnerTests(TransactionTestCase):
    """Never connects to Production; Django test runner creates and drops this DB."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-only integration")

    def _exercise(self, commit):
        MigrationExecutor(connection).migrate([("ai_core", "0002_aichatrequestguard")])
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user")
                dbname, role = cursor.fetchone()
            target = previous.Target("lab", dbname, role, None)
            response = runner.run(
                connection, target, SHA, commit=commit,
                source_sha=lambda: SHA, environ={"VORNEQ_ENV": "development"},
                out=lambda message: None,
            )
            self.assertEqual(response["committed"], commit)
            if commit:
                self.assertFalse(response["pending"])
                runner._verify_schema(connection)
            else:
                self.assertTrue(response["pending"])
                runner._state(connection, runner.PRE_HISTORY, runner.PRE_TABLES)
        finally:
            MigrationExecutor(connection).migrate([("ai_core", "0003_conversation")])

    def test_rehearsal_rollback(self):
        self._exercise(commit=False)

    def test_disposable_postgres_commit(self):
        self._exercise(commit=True)
