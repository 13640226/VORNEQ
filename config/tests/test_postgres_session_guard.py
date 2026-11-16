"""Mocked negative tests; never connect to Production PostgreSQL."""
from unittest import TestCase
from unittest.mock import MagicMock

from django.core.management.base import CommandError

from apps.core.management.commands.postgres_session_guard import (
    assert_same_session, capture_session,
)


def fake_connection(row=(123, "vorneq_production_db", "vorneq_production_db_user",
                         "10.0.0.1", 5432, "on", False, "vorneq_prod_app_rot_20261116")):
    conn = MagicMock()
    conn.vendor = "postgresql"
    conn.connection = object()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = row
    return conn, cursor


class PostgresSessionGuardTests(TestCase):
    def test_stable_session(self):
        conn, _ = fake_connection()
        baseline = capture_session(conn)
        self.assertEqual(assert_same_session(conn, baseline), baseline)

    def test_driver_replacement(self):
        conn, _ = fake_connection()
        baseline = capture_session(conn)
        conn.connection = object()
        with self.assertRaises(CommandError):
            assert_same_session(conn, baseline)

    def test_connection_disappears(self):
        conn, _ = fake_connection()
        baseline = capture_session(conn)
        conn.connection = None
        with self.assertRaises(CommandError):
            assert_same_session(conn, baseline)

    def test_backend_pid_changes(self):
        conn, cursor = fake_connection()
        baseline = capture_session(conn)
        cursor.fetchone.return_value = (124, "vorneq_production_db",
                                        "vorneq_production_db_user",
                                        "10.0.0.1", 5432, "on", False, "vorneq_prod_app_rot_20261116")
        with self.assertRaises(CommandError):
            assert_same_session(conn, baseline)

    def test_server_address_changes(self):
        conn, cursor = fake_connection()
        baseline = capture_session(conn)
        cursor.fetchone.return_value = (123, "vorneq_production_db",
                                        "vorneq_production_db_user",
                                        "10.0.0.2", 5432, "on", False, "vorneq_prod_app_rot_20261116")
        with self.assertRaises(CommandError):
            assert_same_session(conn, baseline)

    def test_session_user_change_detected_even_when_current_user_is_stable(self):
        conn, cursor = fake_connection()
        baseline = capture_session(conn)
        cursor.fetchone.return_value = (
            123, "vorneq_production_db", "vorneq_production_db_user",
            "10.0.0.1", 5432, "on", False, "vorneq_production_db_user",
        )
        with self.assertRaises(CommandError):
            assert_same_session(conn, baseline)

    def test_execution_role_change_detected_even_when_login_is_stable(self):
        conn, cursor = fake_connection()
        baseline = capture_session(conn)
        cursor.fetchone.return_value = (
            123, "vorneq_production_db", "vorneq_prod_app_rot_20261116",
            "10.0.0.1", 5432, "on", False, "vorneq_prod_app_rot_20261116",
        )
        with self.assertRaises(CommandError):
            assert_same_session(conn, baseline)

    def test_writable_connection(self):
        conn, _ = fake_connection((123, "db", "user", "10.0.0.1", 5432, "off", False, "vorneq_prod_app_rot_20261116"))
        with self.assertRaises(CommandError):
            capture_session(conn)

    def test_replica(self):
        conn, _ = fake_connection((123, "db", "user", "10.0.0.1", 5432, "on", True, "vorneq_prod_app_rot_20261116"))
        with self.assertRaises(CommandError):
            capture_session(conn)

    def test_incomplete_observation(self):
        conn, _ = fake_connection(None)
        with self.assertRaises(CommandError):
            capture_session(conn)

    def test_non_postgresql(self):
        conn, _ = fake_connection()
        conn.vendor = "sqlite"
        with self.assertRaises(CommandError):
            capture_session(conn)

    def test_query_error_fails_closed(self):
        conn, cursor = fake_connection()
        cursor.execute.side_effect = ConnectionError("lost")
        with self.assertRaises(ConnectionError):
            capture_session(conn)
