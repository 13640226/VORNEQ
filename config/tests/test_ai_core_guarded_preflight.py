"""Negative tests for fail-closed ai_core preflight policy."""
from unittest import TestCase
from unittest.mock import patch

from django.core.management.base import CommandError

from apps.core.management.commands.apply_ai_core_guarded import (
    EXPECTED,
    verify_observation,
    verify_plan,
    verify_render_host_binding,
    EXPECTED_RENDER_DB_RESOURCE,
)


class FakeMigration:
    def __init__(self, app, name):
        self.app_label = app
        self.name = name


class GuardedPreflightTests(TestCase):
    def test_exact_plan(self):
        self.assertEqual(
            verify_plan([(FakeMigration(*item), False) for item in EXPECTED]),
            EXPECTED,
        )

    def test_extra_migration_rejected(self):
        with self.assertRaises(CommandError):
            verify_plan([(FakeMigration(*item), False) for item in EXPECTED]
                        + [(FakeMigration("ai_ledger", "0001_initial"), False)])

    def test_missing_migration_rejected(self):
        with self.assertRaises(CommandError):
            verify_plan([(FakeMigration(*EXPECTED[0]), False)])

    def test_reverse_migration_rejected(self):
        with self.assertRaises(CommandError):
            verify_plan([(FakeMigration(*item), item == EXPECTED[0])
                         for item in EXPECTED])

    def test_wrong_database_rejected(self):
        with self.assertRaises(CommandError):
            verify_observation("srv-dadn07eq1p3s73eccau0", "staging", False,
                               "on", "a"*40, "a"*40)

    def test_wrong_service_rejected(self):
        with self.assertRaises(CommandError):
            verify_observation("other", "vorneq_production_db", False,
                               "on", "a"*40, "a"*40)

    def test_replica_rejected(self):
        with self.assertRaises(CommandError):
            verify_observation("srv-dadn07eq1p3s73eccau0", "vorneq_production_db",
                               True, "on", "a"*40, "a"*40)

    def test_writable_transaction_rejected(self):
        with self.assertRaises(CommandError):
            verify_observation("srv-dadn07eq1p3s73eccau0", "vorneq_production_db",
                               False, "off", "a"*40, "a"*40)

    def test_wrong_sha_rejected(self):
        with self.assertRaises(CommandError):
            verify_observation("srv-dadn07eq1p3s73eccau0", "vorneq_production_db",
                               False, "on", "a"*40, "b"*40)

    def test_short_sha_rejected(self):
        with self.assertRaises(CommandError):
            verify_observation("srv-dadn07eq1p3s73eccau0", "vorneq_production_db",
                               False, "on", "abc", "abc")

    def test_correct_readonly_observation(self):
        verify_observation("srv-dadn07eq1p3s73eccau0", "vorneq_production_db",
                           False, "on", "a"*40, "a"*40)

    def test_unknown_readonly_status_rejected(self):
        with self.assertRaises(CommandError):
            verify_observation("srv-dadn07eq1p3s73eccau0", "vorneq_production_db",
                               False, None, "a"*40, "a"*40)

    def test_unknown_replica_status_rejected(self):
        with self.assertRaises(CommandError):
            verify_observation("srv-dadn07eq1p3s73eccau0", "vorneq_production_db",
                               None, "on", "a"*40, "a"*40)

    def test_disconnected_database_rejected(self):
        with self.assertRaises(CommandError):
            verify_observation("srv-dadn07eq1p3s73eccau0", None,
                               False, "on", "a"*40, "a"*40)

    def test_apply_is_disabled_before_any_db_access(self):
        from apps.core.management.commands.apply_ai_core_guarded import Command
        with self.assertRaisesRegex(CommandError, "write path deliberately disabled"):
            Command().handle(expected_sha="a"*40, apply=True)


class RenderHostBindingTests(TestCase):
    HOST = EXPECTED_RENDER_DB_RESOURCE + ".internal"

    def test_matching_host_user_ip_port(self):
        with patch(
            "apps.core.management.commands.apply_ai_core_guarded.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.21.80.49", 5432))],
        ):
            self.assertTrue(verify_render_host_binding(
                self.HOST, "vorneq_production_db_user", "10.21.80.49", 5432
            ))

    def test_wrong_resource_rejected(self):
        with self.assertRaises(CommandError):
            verify_render_host_binding(
                "dpg-wrong-a.internal", "vorneq_production_db_user", "10.21.80.49", 5432
            )

    def test_ip_not_in_dns_rejected(self):
        with patch(
            "apps.core.management.commands.apply_ai_core_guarded.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.21.80.50", 5432))],
        ), self.assertRaises(CommandError):
            verify_render_host_binding(
                self.HOST, "vorneq_production_db_user", "10.21.80.49", 5432
            )

    def test_wrong_db_user_rejected(self):
        with self.assertRaises(CommandError):
            verify_render_host_binding(self.HOST, "other", "10.21.80.49", 5432)

    def test_wrong_port_rejected(self):
        with self.assertRaises(CommandError):
            verify_render_host_binding(
                self.HOST, "vorneq_production_db_user", "10.21.80.49", 15432
            )

    def test_dns_failure_rejected(self):
        with patch(
            "apps.core.management.commands.apply_ai_core_guarded.socket.getaddrinfo",
            side_effect=OSError("unavailable"),
        ), self.assertRaises(CommandError):
            verify_render_host_binding(
                self.HOST, "vorneq_production_db_user", "10.21.80.49", 5432
            )
