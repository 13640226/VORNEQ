"""C02 Stage C runner: authorization matrix and real PostgreSQL behaviour.

The integration tests run only on PostgreSQL, against Django's disposable test
database. They unapply ai_core to zero, exercise the runner and restore the
schema afterwards. No Render, Production or provider access.
"""
import io
from unittest import mock, skipUnless

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase

from apps.core import c02_stage_c_runner as runner

SHA = "a" * 40
OTHER_SHA = "b" * 40
INTERNAL_URL = ("postgresql://vorneq_production_db_user:synthetic@dpg-dagru1h42hec73eqr960-a"
                "/vorneq_production_db")


def _prod_settings(url=INTERNAL_URL):
    import dj_database_url

    return {"ENGINE": "django.db.backends.postgresql", **dj_database_url.parse(url)}


def _prod_env(**overrides):
    env = {
        "VORNEQ_ENV": "production",
        "RENDER_SERVICE_ID": runner.PRODUCTION_SERVICE_ID,
        "RENDER_GIT_COMMIT": SHA,
        "VORNEQ_C02_MIGRATION_AUTH": f"OWNER-AUTH-C02-MIGRATION-TEST-0001 @ {SHA}",
        "VORNEQ_C02_BACKUP_EVIDENCE": "render-backup:2026-11-15T21:00Z",
        "VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED": "false",
        "DATABASE_URL": INTERNAL_URL,
    }
    env.update(overrides)
    return {k: v for k, v in env.items() if v is not None}


LAB_SETTINGS = {"ENGINE": "django.db.backends.postgresql", "HOST": "127.0.0.1", "NAME": "test_vorneq", "USER": "vorneq"}
LAB_ENV = {"VORNEQ_ENV": "development", "C02_STAGE_C_LAB": "YES"}


class ProductionWritePathGuardTests(SimpleTestCase):
    def test_explicit_production_gate_requires_all_runtime_controls(self):
        self.assertIs(runner.PRODUCTION_WRITE_ENABLED, True)
        with self.assertRaisesRegex(runner.RunnerRefused, "SHA-bound owner authorization missing"):
            runner.authorize(
                "production", _prod_env(VORNEQ_C02_MIGRATION_AUTH=None),
                SHA, _prod_settings(), SHA,
            )

    def test_command_refuses_production_rehearsal_before_sql(self):
        fake = mock.MagicMock()
        with mock.patch("apps.core.management.commands.c02_stage_c_runner.connections", {"default": fake}), \
                mock.patch.dict("os.environ", _prod_env()):
            with self.assertRaisesRegex(CommandError, "requires explicit --commit"):
                call_command("c02_stage_c_runner", "--target", "production", "--expected-sha", SHA,
                             stdout=io.StringIO())
        fake.cursor.assert_not_called()

    def test_command_refuses_production_without_fresh_auth_before_sql(self):
        fake = mock.MagicMock()
        fake.settings_dict = _prod_settings()
        with mock.patch("apps.core.management.commands.c02_stage_c_runner.connections", {"default": fake}), \
                mock.patch.dict("os.environ", _prod_env(VORNEQ_C02_MIGRATION_AUTH=None)):
            with self.assertRaisesRegex(CommandError, "SHA-bound owner authorization missing"):
                call_command("c02_stage_c_runner", "--target", "production", "--expected-sha", SHA, "--commit",
                             stdout=io.StringIO())
        fake.cursor.assert_not_called()

    def test_apply_ai_core_guarded_write_path_still_disabled(self):
        with self.assertRaisesRegex(CommandError, "C02 OPEN"):
            call_command("apply_ai_core_guarded", "--expected-sha", SHA, "--apply", stdout=io.StringIO())


class FutureProductionGateSpecificationTests(SimpleTestCase):
    """Specifies the gate that would apply once a separate PR enables the flag."""

    def setUp(self):
        patcher = mock.patch.object(runner, "PRODUCTION_WRITE_ENABLED", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_complete_inputs_yield_the_production_target(self):
        target = runner.authorize("production", _prod_env(), SHA, _prod_settings(), SHA)
        self.assertEqual((target.database, target.user, target.pg_major),
                         ("vorneq_production_db", "vorneq_production_db_user", 18))

    def test_each_missing_condition_is_refused(self):
        external = INTERNAL_URL.replace("-a/", "-a.oregon-postgres.render.com/")
        cases = {
            "env": (_prod_env(VORNEQ_ENV="staging"), _prod_settings(), SHA),
            "service": (_prod_env(RENDER_SERVICE_ID="srv-other"), _prod_settings(), SHA),
            "deployed sha": (_prod_env(RENDER_GIT_COMMIT=OTHER_SHA), _prod_settings(), SHA),
            "no auth": (_prod_env(VORNEQ_C02_MIGRATION_AUTH=None), _prod_settings(), SHA),
            "auth other sha": (_prod_env(VORNEQ_C02_MIGRATION_AUTH=f"OWNER-AUTH-C02-MIGRATION-TEST-0001 @ {OTHER_SHA}"),
                               _prod_settings(), SHA),
            "auth malformed": (_prod_env(VORNEQ_C02_MIGRATION_AUTH=f"owner says yes @ {SHA}"), _prod_settings(), SHA),
            "no backup": (_prod_env(VORNEQ_C02_BACKUP_EVIDENCE=None), _prod_settings(), SHA),
            "ai on": (_prod_env(VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED="true"), _prod_settings(), SHA),
            "no url": (_prod_env(DATABASE_URL=None), _prod_settings(), SHA),
            "external host": (_prod_env(DATABASE_URL=external), _prod_settings(external), SHA),
            "settings drift": (_prod_env(), {**_prod_settings(), "HOST": "dpg-other-a"}, SHA),
            "source sha": (_prod_env(), _prod_settings(), OTHER_SHA),
        }
        for label, (env, settings, source) in cases.items():
            with self.subTest(case=label), self.assertRaises(runner.RunnerRefused):
                runner.authorize("production", env, SHA, settings, source)


class LabAuthorizationTests(SimpleTestCase):
    def test_lab_target_accepts_only_disposable_local_test_database(self):
        target = runner.authorize("lab", LAB_ENV, SHA, LAB_SETTINGS, SHA)
        self.assertEqual(target.database, "test_vorneq")
        cases = {
            "production env": ({**LAB_ENV, "VORNEQ_ENV": "production"}, LAB_SETTINGS),
            "no explicit enable": ({"VORNEQ_ENV": "development"}, LAB_SETTINGS),
            "render env": ({**LAB_ENV, "RENDER_SERVICE_ID": "srv-x"}, LAB_SETTINGS),
            "remote host": (LAB_ENV, {**LAB_SETTINGS, "HOST": "dpg-dagru1h42hec73eqr960-a"}),
            "non-test db": (LAB_ENV, {**LAB_SETTINGS, "NAME": "vorneq"}),
            "production db": (LAB_ENV, {**LAB_SETTINGS, "NAME": "vorneq_production_db"}),
            "sqlite": (LAB_ENV, {**LAB_SETTINGS, "ENGINE": "django.db.backends.sqlite3"}),
        }
        for label, (env, settings) in cases.items():
            with self.subTest(case=label), self.assertRaises(runner.RunnerRefused):
                runner.authorize("lab", env, SHA, settings, SHA)

    def test_unknown_target_and_bad_sha_are_refused(self):
        for args in (("staging", LAB_ENV, SHA, LAB_SETTINGS, SHA), ("lab", LAB_ENV, "abc", LAB_SETTINGS, "abc"),
                     ("lab", LAB_ENV, SHA, LAB_SETTINGS, OTHER_SHA)):
            with self.subTest(args=args[0]), self.assertRaises(runner.RunnerRefused):
                runner.authorize(*args)


@skipUnless(connection.vendor == "postgresql", "requires PostgreSQL")
class StageCRunnerPostgresTests(TransactionTestCase):
    databases = {"default"}

    def setUp(self):
        call_command("migrate", "ai_core", "zero", verbosity=0)
        self.addCleanup(call_command, "migrate", "ai_core", verbosity=0)
        settings = connection.settings_dict
        self.target = runner.Target("lab", settings["NAME"], settings["USER"], None)
        self.lines = []

    def state(self):
        return runner._state(connection)

    def run_runner(self, commit, source=lambda: SHA):
        return runner.run(connection, self.target, SHA, commit=commit, source_sha=source, out=self.lines.append)

    def test_rehearsal_executes_both_migrations_then_rolls_back(self):
        result = self.run_runner(commit=False)
        self.assertEqual(result["state"], (0, 0))
        self.assertTrue(result["pending"])
        self.assertIn("C02_STAGE_C: PRE_COMMIT_VERIFICATION PASS", self.lines)
        self.assertEqual(self.state(), (0, 0))

    def test_commit_persists_exactly_the_expected_schema(self):
        result = self.run_runner(commit=True)
        self.assertEqual(result, {"target": "lab", "committed": True, "state": (2, 2), "pending": False})
        runner._verify_schema(connection)

    def test_second_run_after_commit_is_refused(self):
        self.run_runner(commit=True)
        with self.assertRaisesRegex(runner.RunnerRefused, "already present"):
            self.run_runner(commit=True)

    def test_partial_prior_state_is_refused_without_changes(self):
        call_command("migrate", "ai_core", "0001", verbosity=0)
        with self.assertRaises(runner.RunnerRefused):
            self.run_runner(commit=True)
        self.assertEqual(self.state(), (1, 1))

    def test_wrong_live_identity_is_refused(self):
        self.target = runner.Target("lab", "vorneq_production_db", self.target.user, None)
        with self.assertRaisesRegex(runner.RunnerRefused, "identity"):
            self.run_runner(commit=True)

    def test_session_change_after_migrate_aborts_and_rolls_back(self):
        original = runner._snapshot
        calls = {"n": 0}

        def flaky(conn):
            calls["n"] += 1
            row = original(conn)
            return (row[0] + 1,) + row[1:] if calls["n"] >= 4 else row

        with mock.patch.object(runner, "_snapshot", side_effect=flaky):
            with self.assertRaisesRegex(runner.RunnerAborted, "session or transaction changed"):
                self.run_runner(commit=True)
        self.assertEqual(self.state(), (0, 0))

    def test_pre_commit_verification_failure_rolls_back(self):
        with mock.patch.object(runner, "_verify_schema", side_effect=runner.RunnerAborted("injected")):
            with self.assertRaises(runner.RunnerAborted):
                self.run_runner(commit=True)
        self.assertEqual(self.state(), (0, 0))

    def test_source_sha_drift_rolls_back(self):
        with self.assertRaisesRegex(runner.RunnerAborted, "source SHA drift"):
            self.run_runner(commit=True, source=lambda: OTHER_SHA)
        self.assertEqual(self.state(), (0, 0))

    def test_unexpected_exception_inside_transaction_rolls_back(self):
        with mock.patch("django.db.migrations.executor.MigrationExecutor.migrate", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(runner.RunnerAborted, "RuntimeError"):
                self.run_runner(commit=True)
        self.assertEqual(self.state(), (0, 0))

    def _second_connection(self):
        import psycopg2

        s = connection.settings_dict
        other = psycopg2.connect(dbname=s["NAME"], user=s["USER"], password=s["PASSWORD"],
                                 host=s["HOST"], port=s["PORT"] or 5432)
        self.addCleanup(other.close)
        return other

    def test_advisory_lock_held_elsewhere_aborts(self):
        other = self._second_connection()
        other.autocommit = True
        with other.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [runner.ADVISORY_LOCK_KEY])
        with self.assertRaisesRegex(runner.RunnerAborted, "advisory lock busy"):
            self.run_runner(commit=True)
        self.assertEqual(self.state(), (0, 0))

    def test_migration_history_lock_held_elsewhere_aborts(self):
        other = self._second_connection()
        with other.cursor() as cursor:
            cursor.execute("LOCK TABLE django_migrations IN EXCLUSIVE MODE")
        with self.assertRaises(runner.RunnerAborted):
            self.run_runner(commit=True)
        other.rollback()
        self.assertEqual(self.state(), (0, 0))

    def test_command_lab_rehearsal_end_to_end(self):
        out = io.StringIO()
        env = {"VORNEQ_ENV": "development", "C02_STAGE_C_LAB": "YES"}
        # clear=True: the lab gate must see only the explicit lab environment.
        with mock.patch.dict("os.environ", env, clear=True), \
                mock.patch("apps.core.management.commands.c02_stage_c_runner.checkout_sha", return_value=SHA):
            call_command("c02_stage_c_runner", "--target", "lab", "--expected-sha", SHA, stdout=out)
        self.assertIn("rehearsal rolled back", out.getvalue())
        self.assertIn("PRODUCTION_MIGRATION_GO=NO", out.getvalue())
        self.assertEqual(self.state(), (0, 0))
