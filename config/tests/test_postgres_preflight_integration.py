"""Mocked command-level session continuity tests, no DB connection."""
import os
from unittest import TestCase
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from django.core.management.base import CommandError

from apps.core.management.commands import apply_ai_core_guarded as module


class GuardedIntegrationTests(TestCase):
    def run_command(self, change_session=False, dns_ip="10.0.0.1"):
        conn = MagicMock()
        conn.vendor = "postgresql"
        conn.connection = object()
        conn.settings_dict = {"HOST": module.EXPECTED_RENDER_DB_RESOURCE + ".internal"}
        cursor = conn.cursor.return_value.__enter__.return_value
        identity = ("vorneq_production_db", False, "on")
        session = (123, "vorneq_production_db", "vorneq_production_db_user",
                   "10.0.0.1", 5432, "on", False, "vorneq_prod_app_rot_20261116")
        cursor.fetchone.side_effect = [identity, session, session]
        executor = MagicMock()
        executor.loader.detect_conflicts.return_value = {}
        executor.migration_plan.return_value = [
            (SimpleNamespace(app_label=app, name=name), False)
            for app, name in module.EXPECTED
        ]
        with patch.object(module, "connection", conn), patch.object(
            module, "MigrationExecutor", return_value=executor
        ), patch.object(module.socket, "getaddrinfo", return_value=[
            (2, 1, 6, "", (dns_ip, 5432))
        ]), patch.dict(os.environ, {
            "VORNEQ_ENV": "production",
            "RENDER_SERVICE_ID": module.EXPECTED_SERVICE,
            "RENDER_GIT_COMMIT": "a" * 40,
            "VORNEQ_AI_CORE_ENABLED": "false",
        }):
            if change_session:
                cursor.fetchone.side_effect = [
                    identity, session, (124,) + session[1:]
                ]
                with self.assertRaises(CommandError):
                    module.Command().handle(expected_sha="a" * 40, apply=False)
            else:
                module.Command().handle(expected_sha="a" * 40, apply=False)
        return cursor, executor

    def test_preflight_attests_same_session(self):
        cursor, executor = self.run_command()
        self.assertEqual(cursor.execute.call_args_list[-1].args[0], "ROLLBACK")
        executor.migrate.assert_not_called()

    def test_preflight_rejects_changed_backend(self):
        cursor, executor = self.run_command(change_session=True)
        self.assertEqual(cursor.execute.call_args_list[-1].args[0], "ROLLBACK")
        executor.migrate.assert_not_called()

    def test_mismatched_dns_is_readonly_diagnostic(self):
        cursor, executor = self.run_command(dns_ip="10.1.99.88")
        self.assertEqual(cursor.execute.call_args_list[-1].args[0], "ROLLBACK")
        executor.migrate.assert_not_called()

    def test_retired_login_is_rejected_without_migration(self):
        # Even when current_user remains the expected execution role,
        # the authenticated session_user must use the rotated credential.
        conn = MagicMock()
        conn.vendor = "postgresql"
        conn.connection = object()
        conn.settings_dict = {"HOST": module.EXPECTED_RENDER_DB_RESOURCE + ".internal"}
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ("vorneq_production_db", False, "on"),
            (123, "vorneq_production_db", "vorneq_production_db_user",
             "10.0.0.1", 5432, "on", False, "vorneq_production_db_user"),
        ]
        with patch.object(module, "connection", conn), patch.dict(os.environ, {
            "VORNEQ_ENV": "production",
            "RENDER_SERVICE_ID": module.EXPECTED_SERVICE,
            "RENDER_GIT_COMMIT": "a" * 40,
            "VORNEQ_AI_CORE_ENABLED": "false",
        }):
            with self.assertRaisesRegex(CommandError, "Unexpected authenticated"):
                module.Command().handle(expected_sha="a" * 40, apply=False)
        self.assertEqual(cursor.execute.call_args_list[-1].args[0], "ROLLBACK")

