"""Synthetic, disposable PostgreSQL compatibility and guard tests."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.contrib.auth import get_user_model

from apps.core import c02_message_feedback_0006_runner as runner
from apps.ai_core.models import AIConversation, AIMessage, AIMessageFeedback

SHA = "a" * 40
ENV = {"VORNEQ_ENV": "development", "C02_FEEDBACK_0006_LAB": "YES"}
OLD = ("ai_core", "0005_chat_job_v1")


@override_settings(VORNEQ_ENV="development")
class GuardTests(SimpleTestCase):
    def fake(self):
        return SimpleNamespace(alias="default", vendor="postgresql",
            settings_dict={"HOST": "postgres", "NAME": "test_vorneq", "USER": "vorneq"},
            in_atomic_block=False, get_autocommit=Mock(return_value=True), cursor=Mock())

    def test_hosted_refused_before_connection(self):
        for env in ("staging", "production"):
            db = self.fake()
            with self.assertRaises(runner.Refused):
                runner.run(db, SHA, source_sha=lambda: SHA, mode="lab_commit",
                           environ=dict(ENV, VORNEQ_ENV=env))
            db.cursor.assert_not_called()
            db.get_autocommit.assert_not_called()

    def test_wrong_target_or_no_opt_in(self):
        for key, value in (("HOST", "dpg-live"), ("NAME", "vorneq_production_db"),
                           ("OPTIONS", {"options": "-c role=other"})):
            db = self.fake()
            db.settings_dict[key] = value
            with self.assertRaises(runner.Refused):
                runner.guard(db, SHA, lambda: SHA, ENV)
            db.cursor.assert_not_called()
        for env in ({}, dict(ENV, RENDER_SERVICE_ID="x")):
            db = self.fake()
            with self.assertRaises(runner.Refused):
                runner.guard(db, SHA, lambda: SHA, env)
            db.cursor.assert_not_called()

    def test_wrong_sha(self):
        with self.assertRaises(runner.Refused):
            runner.guard(self.fake(), SHA, lambda: "b"*40, ENV)

    def test_exact_plan_refuses_reverse_extra_and_empty(self):
        m = SimpleNamespace(app_label="ai_core", name=runner.TARGET[1])
        for plan in ([], [(m, True)], [(m, False), (m, False)]):
            executor = Mock()
            executor.loader.detect_conflicts.return_value = {}
            executor.migration_plan.return_value = plan
            with patch.object(runner, "MigrationExecutor", return_value=executor):
                with self.assertRaises(runner.Aborted):
                    runner.exact_plan(Mock())


@override_settings(VORNEQ_ENV="development")
class PostgresRunnerTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL only")
        self.addCleanup(self.restore_schema)
        MigrationExecutor(connection).migrate([OLD])
        self.old = MigrationExecutor(connection).loader.project_state([OLD]).apps

    def restore_schema(self):
        MigrationExecutor(connection).migrate([runner.TARGET])

    def invoke(self, mode):
        return runner.run(connection, SHA, source_sha=lambda: SHA, mode=mode, environ=ENV)

    def synthetic(self):
        user = get_user_model().objects.create_user(username="c02-lab-user")
        conversation = AIConversation.objects.create(owner=user, title="Synthetic")
        message = AIMessage.objects.create(conversation=conversation, sequence=1,
            role="assistant", content="Synthetic")
        return user, conversation, message

    def test_inspect_rehearse_and_exact_commit(self):
        self.assertFalse(self.invoke("inspect")["committed"])
        self.assertFalse(self.invoke("rehearse")["committed"])
        self.assertEqual(runner.state(connection), (runner.PRE_HISTORY, runner.PRE_TABLES))
        self.assertTrue(self.invoke("lab_commit")["committed"])
        runner.verify_schema(connection)
        with self.assertRaises(runner.Aborted):
            self.invoke("lab_commit")

    def test_failure_after_ddl_rolls_back(self):
        with patch.object(runner, "verify_schema", side_effect=runner.Aborted("synthetic failure")):
            with self.assertRaises(runner.Aborted):
                self.invoke("lab_commit")
        self.assertEqual(runner.state(connection), (runner.PRE_HISTORY, runner.PRE_TABLES))

    def test_old_empty_table_and_populated_rollback_hazard(self):
        self.invoke("lab_commit")
        _, conversation, message = self.synthetic()
        old_message = self.old.get_model("ai_core", "AIMessage")
        old_message.objects.get(pk=message.pk).delete()
        self.assertFalse(AIMessage.objects.filter(pk=message.pk).exists())
        new = AIMessage.objects.create(conversation=conversation, sequence=2,
                                      role="assistant", content="Synthetic")
        AIMessageFeedback.objects.create(message=new, rating="like")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                old_message.objects.get(pk=new.pk).delete()
                connection.check_constraints()
        self.assertTrue(AIMessageFeedback.objects.filter(message=new).exists())
        message_id = new.pk
        new.delete()
        self.assertFalse(AIMessageFeedback.objects.filter(message_id=message_id).exists())

    def test_new_runtime_cascade_and_constraint(self):
        self.invoke("lab_commit")
        user, conversation, message = self.synthetic()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AIMessageFeedback.objects.create(message=message, rating="invalid")
        AIMessageFeedback.objects.create(message=message, rating="like")
        with override_settings(VORNEQ_AI_FEEDBACK_ENABLED=False):
            user.delete()
        self.assertFalse(AIMessageFeedback.objects.filter(message_id=message.pk).exists())


    def test_concurrent_migration_lock_refuses(self):
        other = connection.copy(alias="c02_feedback_test_lock")
        try:
            other.ensure_connection()
            with other.cursor() as c:
                c.execute("SELECT pg_advisory_lock(%s)", [runner.LOCK_KEY])
            with self.assertRaises(runner.Aborted):
                self.invoke("lab_commit")
            self.assertEqual(runner.state(connection), (runner.PRE_HISTORY, runner.PRE_TABLES))
        finally:
            other.close()

    def test_hosted_receipt_survives_rollback_and_replay_is_denied(self):
        from datetime import datetime, timezone, timedelta
        from apps.core import c02_message_feedback_0006_hosted as hosted
        from apps.core import c02_message_feedback_0006_release as release
        from apps.audit.models import AuditEvent
        with connection.cursor() as c:
            c.execute("SELECT current_setting('server_version_num')::int / 10000")
            if c.fetchone()[0] != 18:
                self.skipTest("hosted contract targets PostgreSQL 18")
        # No Render settings or network access: only the external identity and
        # issuer checks are mocked; SQL/receipt/locks/rollback are real.
        cfg = connection.settings_dict
        target = release.Target("synthetic", "synthetic", cfg["NAME"], cfg["USER"], cfg["USER"])
        proof = release.Proof("staging", "SYNTHETIC-0006-TEST", 1, SHA,
                              hosted.COMPATIBLE_LIVE_SHA, "b"*64, "c"*64,
                              "TEST-RESTORE", datetime.now(timezone.utc)+timedelta(minutes=1))
        def execute():
            return hosted.run_hosted(connection, environment="staging", expected_sha=SHA,
                live_sha=proof.live_sha, release_id=proof.release_id,
                artifact_sha=lambda: SHA, environ=ENV)
        with patch.object(hosted, "verify_context", return_value=target), \
             patch.object(hosted, "observe_owner", return_value=proof), \
             patch.object(release, "verify_main_sha"), \
             patch.dict(release.TARGETS, {"staging": target}):
            with patch.object(runner, "verify_schema", side_effect=runner.Aborted("synthetic failure")):
                with self.assertRaises(runner.Aborted):
                    execute()
            self.assertEqual(runner.state(connection), (runner.PRE_HISTORY, runner.PRE_TABLES))
            self.assertTrue(AuditEvent.objects.filter(event_id=hosted.receipt_uuid(proof)).exists())
            with self.assertRaisesRegex(runner.Aborted, "already consumed"):
                execute()
            self.assertEqual(runner.state(connection), (runner.PRE_HISTORY, runner.PRE_TABLES))
            # A different independently scoped synthetic grant may complete.
            from dataclasses import replace
            second = replace(proof, release_id="SYNTHETIC-0006-TEST-SECOND")
            proof = second
            with patch.object(hosted, "observe_owner", return_value=second):
                self.assertTrue(execute()["committed"])
            self.assertTrue(AuditEvent.objects.filter(event_id=hosted.receipt_uuid(second)).exists())
