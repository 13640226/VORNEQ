"""Runtime database identity on /health/ (G5 / C02 runtime identity probe)."""

from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from config.health import database_identity, render_database_id

PROD_ID = "dpg-dagru1h42hec73eqr960-a"
STAGING_ID = "dpg-dbm74m8u01pc738j8r1g-a"


class RenderDatabaseIdTests(SimpleTestCase):
    def test_internal_host(self):
        self.assertEqual(render_database_id(PROD_ID), PROD_ID)

    def test_external_host_is_reduced_to_instance_id(self):
        self.assertEqual(
            render_database_id(f"{STAGING_ID}.oregon-postgres.render.com"), STAGING_ID
        )

    def test_case_and_whitespace_are_normalized(self):
        self.assertEqual(render_database_id(f"  {PROD_ID.upper()} "), PROD_ID)

    def test_non_render_hosts_are_not_echoed(self):
        for host in ("postgres", "localhost", "10.0.0.5", "db.example.com", "dpg-x-a; DROP"):
            with self.subTest(host=host):
                self.assertEqual(render_database_id(host), "other")

    def test_missing_host(self):
        self.assertEqual(render_database_id(""), "unknown")
        self.assertEqual(render_database_id(None), "unknown")


class _FakeCursor:
    def __init__(self, name=None, error=None):
        self.name, self.error = name, error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        if self.error:
            raise self.error
        self.sql = sql

    def fetchone(self):
        return (self.name,)


class _FakeConnection:
    def __init__(self, vendor, host, cursor=None):
        self.vendor = vendor
        self.settings_dict = {"HOST": host, "USER": "u", "PASSWORD": "p"}
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class DatabaseIdentityTests(SimpleTestCase):
    def _identity(self, host, cursor, vendor="postgresql"):
        with patch("config.health.connection", _FakeConnection(vendor, host, cursor)):
            return database_identity()

    def test_reports_name_and_render_id_only(self):
        identity = self._identity(PROD_ID, _FakeCursor("vorneq_production_db"))
        self.assertEqual(
            identity,
            {"vendor": "postgresql", "name": "vorneq_production_db", "render_id": PROD_ID},
        )

    def test_query_failure_yields_unknown_name(self):
        identity = self._identity(PROD_ID, _FakeCursor(error=RuntimeError("secret-in-error")))
        self.assertEqual(identity["name"], "unknown")
        self.assertNotIn("secret", str(identity))

    def test_unexpected_name_is_not_echoed(self):
        identity = self._identity(PROD_ID, _FakeCursor("bad name; --"))
        self.assertEqual(identity["name"], "unknown")

    def test_non_postgres_vendor(self):
        self.assertEqual(
            self._identity(PROD_ID, None, vendor="sqlite"),
            {"vendor": "sqlite", "name": "unknown", "render_id": "unknown"},
        )


class HealthPayloadTests(TestCase):
    def test_health_includes_database_identity_without_credentials(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        database = response.json()["database"]
        self.assertEqual(set(database), {"vendor", "name", "render_id"})
        self.assertEqual(database["vendor"], connection.vendor)
        body = response.content.decode()
        for marker in ("postgres://", "postgresql://", "@"):
            self.assertNotIn(marker, body)
        # User and password may be substrings of the database name (CI uses
        # "vorneq" for both and the test database "test_vorneq"), so no field
        # may equal either of them exactly.
        values = set(database.values())
        for key in ("USER", "PASSWORD"):
            secret = str(connection.settings_dict.get(key) or "")
            if secret:
                self.assertNotIn(secret, values)

    @patch("config.health.connection.cursor", side_effect=RuntimeError("down"))
    def test_database_failure_reports_unknown_identity(self, _cursor):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        database = response.json()["database"]
        self.assertEqual((database["name"], database["render_id"]), ("unknown", "unknown"))
