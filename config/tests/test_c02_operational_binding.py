"""C02 operational binding: secret-free DATABASE_URL vs Dashboard Internal URL."""
import importlib.util
import io
import sys
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.core import c02_operational_binding as binding

ROOT = Path(__file__).resolve().parents[2]
NONCE = "0123456789abcdef" * 4
PASSWORD = "synthetic-Pa55word-not-real"
INTERNAL_URL = f"postgresql://vorneq_prod_app_rot_20261116:{PASSWORD}@dpg-dagru1h42hec73eqr960-a/vorneq_production_db"
EXTERNAL_URL = (
    f"postgresql://vorneq_prod_app_rot_20261116:{PASSWORD}@dpg-dagru1h42hec73eqr960-a.oregon-postgres.render.com"
    "/vorneq_production_db?sslmode=require"
)


def _settings(url):
    import dj_database_url

    return dj_database_url.parse(url, conn_max_age=600)


def _script():
    spec = importlib.util.spec_from_file_location("c02_internal_url_digest", ROOT / "scripts" / "c02_tests" / "internal_url_digest.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DigestTests(SimpleTestCase):
    def test_nonce_must_be_long_lowercase_hex(self):
        for bad in ("", "abc", "G" * 32, NONCE.upper(), "a" * 129, None):
            with self.subTest(nonce=bad), self.assertRaises(binding.BindingError):
                binding.url_digest(bad, INTERNAL_URL)

    def test_digest_is_keyed_and_exact(self):
        first = binding.url_digest(NONCE, INTERNAL_URL)
        self.assertEqual(first, binding.url_digest(NONCE, "  " + INTERNAL_URL + "\n"))
        self.assertNotEqual(first, binding.url_digest("f" * 64, INTERNAL_URL))
        self.assertNotEqual(first, binding.url_digest(NONCE, INTERNAL_URL.replace("Pa55", "Pa56")))
        self.assertNotIn(PASSWORD, first)

    def test_local_script_uses_the_same_digest(self):
        script = _script()
        self.assertEqual(script.digest(NONCE, INTERNAL_URL), binding.url_digest(NONCE, INTERNAL_URL))

    def test_local_script_match_and_mismatch_without_printing_url(self):
        script = _script()
        expected = binding.url_digest(NONCE, INTERNAL_URL)
        for url, code, verdict in ((INTERNAL_URL, 0, "MATCH"), (EXTERNAL_URL, 2, "MISMATCH")):
            out = io.StringIO()
            with self.subTest(verdict=verdict), mock.patch.object(script.getpass, "getpass", return_value=url), \
                    mock.patch("sys.stdout", out):
                self.assertEqual(script.main(["--nonce", NONCE, "--expected-digest", expected]), code)
            self.assertIn(f"C02_DIGEST_COMPARISON: {verdict}", out.getvalue())
            self.assertNotIn(PASSWORD, out.getvalue())
            self.assertNotIn("postgresql://", out.getvalue())


class HostAndSettingsTests(SimpleTestCase):
    def test_host_classes(self):
        self.assertEqual(binding.classify_host("dpg-dagru1h42hec73eqr960-a"), "INTERNAL_EXACT")
        self.assertEqual(binding.classify_host("dpg-dagru1h42hec73eqr960-a.oregon-postgres.render.com"), "EXTERNAL_RENDER")
        for other in ("dpg-dagru1h42hec73eqr960-a.evil.example", "dpg-other-a", "dpg-dagru1h42hec73eqr960-a.internal",
                      "127.0.0.1", "", None):
            with self.subTest(host=other):
                self.assertEqual(binding.classify_host(other), "OTHER")

    def test_settings_must_derive_from_url(self):
        settings = _settings(INTERNAL_URL)
        self.assertTrue(binding.settings_match_url(settings, INTERNAL_URL))
        for key, value in (("PASSWORD", "other"), ("HOST", "dpg-other-a"), ("NAME", "x"), ("USER", "x"), ("PORT", 6543)):
            with self.subTest(key=key):
                self.assertFalse(binding.settings_match_url({**settings, key: value}, INTERNAL_URL))
        self.assertFalse(binding.settings_match_url(settings, "not a url"))


class ReportTests(SimpleTestCase):
    def test_internal_url_passes_precheck_but_never_grants_go(self):
        report = binding.binding_report({"DATABASE_URL": INTERNAL_URL}, _settings(INTERNAL_URL), NONCE)
        self.assertEqual(report["C02_HOST_CLASS"], "INTERNAL_EXACT")
        self.assertTrue(report["C02_OPERATIONAL_PRECHECK"])
        self.assertIs(report["C02_MIGRATION_GO"], False)
        self.assertEqual(report["POSTGRES_BACKEND_CRYPTOGRAPHIC_IDENTITY"], "NOT_AVAILABLE")
        self.assertNotIn(PASSWORD, repr(report))

    def test_external_or_mismatched_settings_fail_precheck(self):
        external = binding.binding_report({"DATABASE_URL": EXTERNAL_URL}, _settings(EXTERNAL_URL), NONCE)
        self.assertFalse(external["C02_OPERATIONAL_PRECHECK"])
        drift = binding.binding_report({"DATABASE_URL": INTERNAL_URL}, _settings(EXTERNAL_URL), NONCE)
        self.assertFalse(drift["C02_DJANGO_SETTINGS_FROM_DATABASE_URL"])
        self.assertFalse(drift["C02_OPERATIONAL_PRECHECK"])

    def test_retired_login_is_rejected_after_rotation(self):
        legacy = INTERNAL_URL.replace("vorneq_prod_app_rot_20261116", "vorneq_production_db_user")
        report = binding.binding_report({"DATABASE_URL": legacy}, _settings(legacy), NONCE)
        self.assertFalse(report["C02_LOGICAL_TARGET_MATCH"])
        self.assertFalse(report["C02_OPERATIONAL_PRECHECK"])
        self.assertEqual(binding.EXPECTED_DATABASE_USER, "vorneq_prod_app_rot_20261116")
        self.assertEqual(binding.EXPECTED_EXECUTION_ROLE, "vorneq_production_db_user")
        self.assertNotIn(PASSWORD, repr(report))

    def test_missing_url_is_refused(self):
        with self.assertRaises(binding.BindingError):
            binding.binding_report({}, {}, NONCE)


class CommandTests(SimpleTestCase):
    def test_command_prints_no_secret_and_runs_no_sql(self):
        fake = mock.MagicMock()
        fake.settings_dict = _settings(INTERNAL_URL)
        out = io.StringIO()
        with mock.patch.dict("os.environ", {"DATABASE_URL": INTERNAL_URL}), \
                mock.patch("apps.core.management.commands.c02_internal_url_binding.connections", {"default": fake}):
            call_command("c02_internal_url_binding", "--nonce", NONCE, stdout=out)
        text = out.getvalue()
        self.assertIn("C02_HOST_CLASS: INTERNAL_EXACT", text)
        self.assertIn("C02_MIGRATION_GO: False", text)
        self.assertNotIn(PASSWORD, text)
        self.assertNotIn("postgresql://", text)
        fake.cursor.assert_not_called()

    def test_command_rejects_bad_nonce(self):
        with self.assertRaises(CommandError):
            call_command("c02_internal_url_binding", "--nonce", "short", stdout=io.StringIO())
