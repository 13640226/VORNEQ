from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase


class HealthCheckTests(TestCase):
    def test_health_check_is_read_only_and_healthy(self):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks"]["database"], "ok")
        self.assertEqual(payload["checks"]["storage"], "ok")

    @patch("config.health.default_storage.exists", side_effect=RuntimeError("boom"))
    def test_health_check_fails_closed_when_storage_is_unavailable(self, _exists):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["checks"]["storage"], "error")
        self.assertNotIn("boom", response.content.decode("utf-8"))


class MigrationPreflightTests(TestCase):
    def test_preflight_is_read_only_and_reports_consistent_history(self):
        out = StringIO()

        call_command("migration_preflight", stdout=out)

        rendered = out.getvalue()
        self.assertIn("Running migration preflight", rendered)
        self.assertIn("Migration preflight passed", rendered)
