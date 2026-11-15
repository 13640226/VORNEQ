"""Offline tests: C02 runtime snapshot never performs a migration or write."""
import io
import json
import os
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.core.management.base import CommandError
from apps.core.management.commands import c02_runtime_observation as module

SHA = "c" * 40


class C02RuntimeSnapshotTests(TestCase):
    def run_snapshot(self, user="vorneq_production_db_user", service="srv-dadn07eq1p3s73eccau0"):
        db = MagicMock()
        db.vendor = "postgresql"
        db.settings_dict = {"HOST": "dpg-dagru1h42hec73eqr960-a.internal"}
        cur = db.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = ("vorneq_production_db", False, "on", 180006)
        observed = SimpleNamespace(
            database="vorneq_production_db", username=user,
            server_port=5432, replica=False, readonly="on", backend_pid=455,
        )
        command = module.Command()
        command.stdout = io.StringIO()
        with patch.object(module, "connection", db), patch.object(
            module, "capture_session", return_value=observed
        ), patch.object(module, "assert_same_session") as continuity, patch.dict(os.environ, {
            "VORNEQ_ENV": "production",
            "RENDER_SERVICE_ID": service,
            "RENDER_GIT_COMMIT": SHA,
            "VORNEQ_AI_CORE_ENABLED": "false",
        }):
            try:
                command.handle(expected_sha=SHA)
            except CommandError:
                self.assertEqual(cur.execute.call_args_list[-1].args[0], "ROLLBACK")
                raise
        self.assertEqual(cur.execute.call_args_list[0].args[0], "BEGIN TRANSACTION READ ONLY")
        self.assertEqual(cur.execute.call_args_list[-1].args[0], "ROLLBACK")
        continuity.assert_called_once()
        result = json.loads(command.stdout.getvalue().splitlines()[0])
        self.assertEqual(result["deploy_sha"], SHA)
        self.assertEqual(result["postgres_major"], 18)
        self.assertNotIn("password", result)
        self.assertNotIn("token", result)
        return result

    def test_runtime_snapshot_correct(self):
        self.assertEqual(self.run_snapshot()["database"], "vorneq_production_db")

    def test_wrong_user_rejected(self):
        with self.assertRaisesRegex(CommandError, "Unexpected Production PostgreSQL user"):
            self.run_snapshot(user="unrelated")

    def test_wrong_service_rejected(self):
        with self.assertRaisesRegex(CommandError, "Service or database identity mismatch"):
            self.run_snapshot(service="srv-unrelated")
