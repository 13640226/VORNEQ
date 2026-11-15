"""C02 v2 guard negative tests; all tests use pure policy/mocks, NO real DB."""
from dataclasses import dataclass
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts.c02_tests import guarded_ai_core_executor_v2 as gate

SHA = "a" * 40
ENV = {
    "VORNEQ_ENV": "development",
    "C02_ENABLE_DISPOSABLE_DDL_REHEARSAL": "YES",
    "C02_TEST_LOOPBACK": "1",
}


@dataclass
class FakeMigration:
    app_label: str
    name: str


class GuardedC02LabGateTests(TestCase):
    def test_valid_sha_and_exact_disposable_context(self):
        gate.require_lab_environment(ENV, SHA, SHA)
        self.assertEqual(gate.fixed_lab_target(ENV), ("127.0.0.1", 15432))
        gate.require_db_identity(("isolated_c02_test", "c02test", 18, False))

    def test_production_env_denied_before_database_setup(self):
        with self.assertRaisesRegex(gate.LabGateError, "ENV DENIED"):
            gate.require_lab_environment({**ENV, "VORNEQ_ENV": "production"}, SHA, SHA)

    def test_staging_env_denied(self):
        with self.assertRaises(gate.LabGateError):
            gate.require_lab_environment({**ENV, "VORNEQ_ENV": "staging"}, SHA, SHA)

    def test_missing_explicit_enable_rejected(self):
        e = dict(ENV)
        e.pop("C02_ENABLE_DISPOSABLE_DDL_REHEARSAL")
        with self.assertRaises(gate.LabGateError):
            gate.require_lab_environment(e, SHA, SHA)

    def test_render_service_env_rejected(self):
        with self.assertRaises(gate.LabGateError):
            gate.require_lab_environment({**ENV, "RENDER_SERVICE_ID": "srv-something"}, SHA, SHA)

    def test_render_key_env_rejected(self):
        with self.assertRaises(gate.LabGateError):
            gate.require_lab_environment({**ENV, "RENDER_API_KEY": "not-real"}, SHA, SHA)

    def test_database_url_env_rejected(self):
        with self.assertRaises(gate.LabGateError):
            gate.require_lab_environment({**ENV, "DATABASE_URL": "postgres://unrelated"}, SHA, SHA)

    def test_sha_drift_rejected(self):
        with self.assertRaisesRegex(gate.LabGateError, "SHA MISMATCH"):
            gate.require_lab_environment(ENV, SHA, "b" * 40)

    def test_malformed_sha_rejected(self):
        for bad in ("abc", "G" * 40, "a" * 39, "A" * 40):
            with self.subTest(sha=bad), self.assertRaises(gate.LabGateError):
                gate.require_lab_environment(ENV, bad, bad)

    def test_unexpected_network_mode_rejected(self):
        with self.assertRaises(gate.LabGateError):
            gate.fixed_lab_target({**ENV, "C02_TEST_LOOPBACK": "2"})

    def test_disposable_pg18_identity_is_exact(self):
        for bad in (
            ("production", "c02test", 18, False),
            ("isolated_c02_test", "postgres", 18, False),
            ("isolated_c02_test", "c02test", 16, False),
            ("isolated_c02_test", "c02test", 18, True),
        ):
            with self.subTest(identity=bad), self.assertRaises(gate.LabGateError):
                gate.require_db_identity(bad)

    def test_only_exact_forward_ai_core_migrations_allowed(self):
        migrations = [
            (FakeMigration(app, name), False)
            for app, name in gate.EXPECTED
        ]
        gate.verify_exact_plan(migrations)
        with self.assertRaises(gate.LabGateError):
            gate.verify_exact_plan(migrations[:1])
        with self.assertRaises(gate.LabGateError):
            gate.verify_exact_plan(migrations + [(FakeMigration("misc", "0001"), False)])
        with self.assertRaises(gate.LabGateError):
            gate.verify_exact_plan([(migration, True) for migration, _ in migrations])

    def test_same_driver_backend_and_txid_required(self):
        driver = object()
        connection = SimpleNamespace(connection=driver)
        identity = (123, "isolated_c02_test", "c02test", 18, "127.0.0.1", 5432, "off", False, 555)
        gate.verify_same_write_transaction(identity, identity, driver, connection)

        for changed in (
            (124, *identity[1:]),
            (*identity[:-1], 556),
            (*identity[:6], "on", False, 555),
            (*identity[:7], True, 555),
        ):
            with self.subTest(observation=changed), self.assertRaises(gate.LabGateError):
                gate.verify_same_write_transaction(identity, changed, driver, connection)
        connection.connection = object()
        with self.assertRaises(gate.LabGateError):
            gate.verify_same_write_transaction(identity, identity, driver, connection)

    def test_main_cannot_run_on_render_even_if_expected_sha_matches(self):
        with patch.object(gate, "current_checkout_sha", return_value=SHA), patch.dict(
            gate.os.environ,
            {"VORNEQ_ENV": "production", "C02_ENABLE_DISPOSABLE_DDL_REHEARSAL": "YES"},
            clear=True,
        ), self.assertRaises(gate.LabGateError):
            gate.run_lab(SHA)
