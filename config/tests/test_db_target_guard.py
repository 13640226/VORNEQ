"""Tests for scripts/db_target_guard.py (identity probe and production guard)."""
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

_PATH = Path(settings.BASE_DIR) / "scripts" / "db_target_guard.py"
_SPEC = importlib.util.spec_from_file_location("db_target_guard", _PATH)
guard = importlib.util.module_from_spec(_SPEC)
# dataclasses resolve annotations through sys.modules, so register first.
sys.modules.setdefault(_SPEC.name, guard)
_SPEC.loader.exec_module(guard)

SECRET_URL = "postgresql://vorneq_user:S3cr3t-P4ss@dpg-abc-a.oregon-postgres.render.com:5432/vorneq_production_db"
OTHER_URL = "postgresql://dr_user:Other-P4ss@dpg-xyz-a.oregon-postgres.render.com/vorneq_dr_restore"

PROD = guard.Identity("vorneq_production_db", "10.0.0.5", "5432", "180001")
DR = guard.Identity("vorneq_dr_restore", "10.0.0.9", "5432", "180001")


class DecisionMatrixTests(SimpleTestCase):
    def test_confirm_only_without_allow_on_production_is_refused(self):
        ok, message = guard.decide(target_is_production=True, allow_production=False, confirmed=True)
        self.assertFalse(ok)
        self.assertIn("PRODUCTION", message)

    def test_allow_only_without_confirm_is_refused(self):
        ok, _ = guard.decide(target_is_production=True, allow_production=True, confirmed=False)
        self.assertFalse(ok)
        ok, _ = guard.decide(target_is_production=False, allow_production=True, confirmed=False)
        self.assertFalse(ok)

    def test_both_flags_non_production_target_is_allowed(self):
        ok, message = guard.decide(target_is_production=False, allow_production=True, confirmed=True)
        self.assertTrue(ok)
        self.assertIn("not production", message)

    def test_both_flags_production_target_is_allowed_explicitly(self):
        ok, message = guard.decide(target_is_production=True, allow_production=True, confirmed=True)
        self.assertTrue(ok)
        self.assertIn("explicit production target", message)

    def test_normal_non_production_run_is_allowed(self):
        ok, _ = guard.decide(target_is_production=False, allow_production=False, confirmed=True)
        self.assertTrue(ok)


class DetectionTests(SimpleTestCase):
    def test_detection_by_identity_not_by_name_list(self):
        # Same database reached through the production secret: detected even
        # when its name is not on the protected list.
        self.assertTrue(guard.is_production(PROD, PROD, ("some_other_name",)))

    def test_detection_by_protected_name_without_production_secret(self):
        self.assertTrue(guard.is_production(PROD, None, ("vorneq_production_db",)))

    def test_other_database_is_not_production(self):
        self.assertFalse(guard.is_production(DR, PROD, ("vorneq_production_db",)))

    def test_protected_names_from_environment(self):
        self.assertEqual(guard.protected_databases({"VORNEQ_PROTECTED_DATABASES": "a, b"}), ("a", "b"))
        self.assertEqual(guard.protected_databases({}), ("vorneq_production_db",))


class SanitizationTests(SimpleTestCase):
    def test_sanitized_url_has_no_credentials(self):
        text = guard.sanitized(SECRET_URL)
        self.assertEqual(
            text, "host=dpg-abc-a.oregon-postgres.render.com port=5432 database=vorneq_production_db"
        )
        self.assertNotIn("S3cr3t", text)
        self.assertNotIn("vorneq_user", text)

    def test_rejects_non_postgres_url(self):
        with self.assertRaises(ValueError):
            guard.parse_url("mysql://u:p@h/db")

    def _run(self, argv, environ, identities):
        out, err = io.StringIO(), io.StringIO()
        fake = mock.Mock(side_effect=lambda url: identities[url])
        with mock.patch.dict(os.environ, environ, clear=False), \
             mock.patch.object(guard, "query_identity", fake), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = guard.main(argv)
        return code, out.getvalue() + err.getvalue()

    def test_probe_output_never_contains_credentials(self):
        code, output = self._run(
            ["probe", "--env", "T_URL", "--compare-env", "P_URL"],
            {"T_URL": OTHER_URL, "P_URL": SECRET_URL},
            {OTHER_URL: DR, SECRET_URL: PROD},
        )
        self.assertEqual(code, 0)
        for secret in ("S3cr3t-P4ss", "Other-P4ss", "vorneq_user", "dr_user", "postgresql://"):
            self.assertNotIn(secret, output)
        self.assertIn("current_database:  vorneq_dr_restore", output)
        self.assertIn("same database as P_URL: no", output)

    def test_guard_refuses_production_without_flag_and_hides_credentials(self):
        code, output = self._run(
            ["guard", "--target-env", "T_URL", "--production-env", "P_URL"],
            {"T_URL": SECRET_URL, "P_URL": SECRET_URL, "CONFIRM": "yes", "ALLOW_PRODUCTION_TARGET": "false"},
            {SECRET_URL: PROD},
        )
        self.assertEqual(code, 1)
        self.assertIn("REFUSING", output)
        self.assertNotIn("S3cr3t-P4ss", output)

    def test_guard_marks_explicit_production_run_in_log(self):
        code, output = self._run(
            ["guard", "--target-env", "T_URL", "--production-env", "P_URL"],
            {"T_URL": SECRET_URL, "P_URL": SECRET_URL, "CONFIRM": "yes", "ALLOW_PRODUCTION_TARGET": "true"},
            {SECRET_URL: PROD},
        )
        self.assertEqual(code, 0)
        self.assertIn("::warning title=Production target::", output)

    def test_guard_detects_production_reached_through_a_different_url(self):
        internal_url = "postgresql://vorneq_user:S3cr3t-P4ss@dpg-abc-a/vorneq_production_db"
        code, output = self._run(
            ["guard", "--target-env", "T_URL", "--production-env", "P_URL"],
            {
                "T_URL": internal_url,
                "P_URL": SECRET_URL,
                "CONFIRM": "yes",
                "ALLOW_PRODUCTION_TARGET": "false",
                "VORNEQ_PROTECTED_DATABASES": "some_other_name",
            },
            {internal_url: PROD, SECRET_URL: PROD},
        )
        self.assertEqual(code, 1)
        self.assertIn("Detected as production: YES", output)

    def test_guard_allows_dr_target(self):
        code, _ = self._run(
            ["guard", "--target-env", "T_URL", "--production-env", "P_URL"],
            {"T_URL": OTHER_URL, "P_URL": SECRET_URL, "CONFIRM": "yes", "ALLOW_PRODUCTION_TARGET": "false"},
            {OTHER_URL: DR, SECRET_URL: PROD},
        )
        self.assertEqual(code, 0)

    def test_psql_failure_is_refused_without_echoing_stderr(self):
        failing = mock.Mock(side_effect=subprocess.CalledProcessError(2, "psql", stderr=f"FATAL {SECRET_URL}"))
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"T_URL": SECRET_URL, "CONFIRM": "yes"}), \
             mock.patch.object(guard, "query_identity", failing), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = guard.main(["guard", "--target-env", "T_URL"])
        self.assertEqual(code, 2)
        self.assertNotIn("S3cr3t-P4ss", out.getvalue() + err.getvalue())
