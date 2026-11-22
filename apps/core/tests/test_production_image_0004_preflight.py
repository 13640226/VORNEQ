from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.core import c02_operational_binding as binding
from apps.core import production_image_0004_preflight as p
from apps.core.management.commands.inspect_production_image_0004 import Command


class ProductionImagePreflightTests(SimpleTestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.env = {
            "VORNEQ_ENV": "production", "RENDER_SERVICE_ID": p.SERVICE,
            "RENDER_GIT_COMMIT": self.sha,
            "DATABASE_URL": ("postgresql://" + binding.EXPECTED_DATABASE_USER
                             + ":synthetic-test-password@" + binding.EXPECTED_RESOURCE_ID
                             + ":5432/" + binding.EXPECTED_DATABASE),
        }
        self.db = {
            "ENGINE": "django.db.backends.postgresql", "NAME": binding.EXPECTED_DATABASE,
            "USER": binding.EXPECTED_DATABASE_USER, "PASSWORD": "synthetic-test-password",
            "HOST": binding.EXPECTED_RESOURCE_ID, "PORT": "5432",
        }
        self.runtime = SimpleNamespace(VORNEQ_ENV="production", DEBUG=False)
        self.identity = (binding.EXPECTED_DATABASE, binding.EXPECTED_DATABASE_USER,
                         binding.EXPECTED_DATABASE_USER, 5432, "on", False, 18, None)
        self.plan = ((p.TARGET[0], p.TARGET[1], False),)

    def test_valid_context(self):
        p.check_context(self.env, self.sha, self.db, runtime=self.runtime)

    def test_wrong_environment_service_sha_or_open_gate_denied(self):
        for key, value in (
            ("VORNEQ_ENV", "staging"), ("RENDER_SERVICE_ID", "wrong"),
            ("RENDER_GIT_COMMIT", "b" * 40), ("VORNEQ_AI_IMAGE_ENABLED", "true"),
            ("VORNEQ_AI_IMAGE_UI_ENABLED", "true"),
            ("VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", "true"),
            ("VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED", "true"),
            ("DATABASE_URL", self.env["DATABASE_URL"].replace(binding.EXPECTED_RESOURCE_ID, "wrong")),
        ):
            with self.subTest(key=key), self.assertRaises(p.PreflightDenied):
                p.check_context(dict(self.env, **{key: value}), self.sha, self.db,
                                runtime=self.runtime)

    def test_mismatched_db_settings_and_runtime_denied(self):
        for changed in ({"HOST": "wrong"}, {"NAME": "wrong"}, {"USER": "wrong"},
                        {"PASSWORD": "wrong"}, {"ENGINE": "sqlite3"}):
            with self.subTest(changed=changed), self.assertRaises(p.PreflightDenied):
                p.check_context(self.env, self.sha, dict(self.db, **changed), runtime=self.runtime)
        for changed in ({"DEBUG": True}, {"VORNEQ_ENV": "staging"},
                        {"VORNEQ_AI_IMAGE_ENABLED": True}):
            runtime = SimpleNamespace(**dict(vars(self.runtime), **changed))
            with self.subTest(changed=changed), self.assertRaises(p.PreflightDenied):
                p.check_context(self.env, self.sha, self.db, runtime=runtime)

    def test_identity_mismatch_denied(self):
        p.check_identity(self.identity)
        for index, value in ((0, "wrong"), (1, "wrong"), (2, "wrong"), (3, 5433),
                             (4, "off"), (5, True), (6, 17), (7, 1)):
            row = list(self.identity)
            row[index] = value
            with self.subTest(index=index), self.assertRaises(p.PreflightDenied):
                p.check_identity(row)

    def test_exact_plan_only(self):
        p.check_state(p.HISTORY_BEFORE, p.TABLES_BEFORE, self.plan)
        for history, tables, plan in (
            (p.HISTORY_BEFORE + (p.TARGET[1],), p.TABLES_BEFORE, self.plan),
            (p.HISTORY_BEFORE, p.TABLES_BEFORE | p.IMAGE_TABLES, self.plan),
            (p.HISTORY_BEFORE, p.TABLES_BEFORE, ()),
            (p.HISTORY_BEFORE, p.TABLES_BEFORE, ((p.TARGET[0], p.TARGET[1], True),)),
            (p.HISTORY_BEFORE, p.TABLES_BEFORE, self.plan + (("other", "0001", False),)),
        ):
            with self.subTest(plan=plan), self.assertRaises(p.PreflightDenied):
                p.check_state(history, tables, plan)

    @patch.object(p, "check_context")
    @patch.object(p, "MigrationRecorder")
    @patch.object(p, "MigrationExecutor")
    @patch.object(p.transaction, "atomic")
    def test_inspect_sets_read_only_and_never_migrates(self, atomic, executor, recorder, context):
        conn = MagicMock(vendor="postgresql", alias="default", in_atomic_block=False)
        conn.get_autocommit.return_value = True
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = self.identity
        cur.fetchall.side_effect = [[(name,) for name in p.HISTORY_BEFORE],
                                   [(table,) for table in p.TABLES_BEFORE]]
        recorder.return_value.has_table.return_value = True
        executor.return_value.loader.detect_conflicts.return_value = {}
        executor.return_value.migration_plan.return_value = [
            (SimpleNamespace(app_label=p.TARGET[0], name=p.TARGET[1]), False)]
        result = p.inspect(conn, self.sha, environ=self.env)
        self.assertEqual(cur.execute.call_args_list[0].args, ("SET TRANSACTION READ ONLY",))
        self.assertTrue(result["identity_and_plan_pass"])
        self.assertFalse(result["migration_authorized"])
        self.assertFalse(result["migration_executed"])
        executor.return_value.migrate.assert_not_called()

    def test_no_write_command_flag(self):
        parser = Command().create_parser("manage.py", "inspect_production_image_0004")
        options = {key for act in parser._actions for key in act.option_strings}
        self.assertNotIn("--commit", options)
        self.assertNotIn("--execute", options)
