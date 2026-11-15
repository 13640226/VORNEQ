"""Fail-closed documentary preflight for ai_core migration (no writes).

C02 requires independently verified Render resource identity and same-context
attestation; neither a caller-provided IP nor Django's database name proves it.
"""
import ipaddress
import os
import socket
from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.core.management.commands.postgres_session_guard import (
    assert_same_session, capture_session,
)

TARGET = ("ai_core", "0002_aichatrequestguard")
EXPECTED = (("ai_core", "0001_initial"), ("ai_core", "0002_aichatrequestguard"))
EXPECTED_SERVICE = "srv-dadn07eq1p3s73eccau0"
EXPECTED_DATABASE = "vorneq_production_db"
EXPECTED_DATABASE_USER = "vorneq_production_db_user"
EXPECTED_RENDER_DB_RESOURCE = "dpg-dagru1h42hec73eqr960-a"


def verify_plan(plan):
    actual = tuple((migration.app_label, migration.name) for migration, backwards in plan)
    if any(backwards for _, backwards in plan) or actual != EXPECTED:
        raise CommandError("Unexpected migration plan: " + repr(actual))
    return actual


def verify_observation(service, database, replica, readonly, expected_sha, actual_sha):
    if service != EXPECTED_SERVICE or database != EXPECTED_DATABASE:
        raise CommandError("Service or database identity mismatch")
    if replica is not False or readonly != "on":
        raise CommandError("Read-only preflight required")
    if len(expected_sha) != 40 or expected_sha != actual_sha:
        raise CommandError("Deployed SHA mismatch")


@dataclass(frozen=True)
class HostBindingEvidence:
    """Advisory DNS comparison; not independent Render resource attestation."""

    dns_server_ip_match: bool
    dns_address_count: int


def verify_render_host_binding(host, username, server_address, server_port):
    """Validate expected host/user/port and collect non-authoritative DNS evidence.

    PostgreSQL inet_server_addr() may identify a backend behind a network
    proxy or NAT, while DNS resolves the connection frontend. Requiring equal
    IPs incorrectly rejects valid connections; equality does not prove Render
    resource identity either. This function only supports a READ-ONLY
    preflight; the migration write path remains disabled.
    """
    if not isinstance(host, str) or host.split(".")[0].lower() != EXPECTED_RENDER_DB_RESOURCE:
        raise CommandError("Configured PostgreSQL hostname does not match expected Render resource")
    if username != EXPECTED_DATABASE_USER or server_port != 5432 or not server_address:
        raise CommandError("PostgreSQL user, port or server address mismatch")
    try:
        observed = ipaddress.ip_interface(server_address).ip
    except (ValueError, TypeError) as exc:
        raise CommandError("Invalid PostgreSQL server address") from exc
    try:
        addresses = {
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(host, server_port, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError, TypeError, IndexError) as exc:
        raise CommandError("Cannot validate configured PostgreSQL host DNS") from exc
    if not addresses:
        raise CommandError("Configured PostgreSQL host DNS has no IP records")
    return HostBindingEvidence(
        dns_server_ip_match=observed in addresses,
        dns_address_count=len(addresses),
    )


class Command(BaseCommand):
    help = "Read-only fail-closed ai_core preflight; never applies migrations"

    def add_arguments(self, parser):
        parser.add_argument("--expected-sha", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if options["apply"]:
            raise CommandError("C02 OPEN: write path deliberately disabled")
        if connection.vendor != "postgresql":
            raise CommandError("PostgreSQL required")
        if os.environ.get("VORNEQ_ENV") != "production":
            raise CommandError("Production environment required")
        if os.environ.get("VORNEQ_AI_CORE_ENABLED", "").lower() in ("true", "yes", "1"):
            raise CommandError("AI must remain disabled")
        with connection.cursor() as cursor:
            cursor.execute("BEGIN TRANSACTION READ ONLY")
            try:
                cursor.execute("SET LOCAL statement_timeout = '5000ms'")
                cursor.execute(
                    "SELECT current_database(), pg_is_in_recovery(), "
                    "current_setting('transaction_read_only')"
                )
                db, replica, readonly = cursor.fetchone()
                verify_observation(
                    os.environ.get("RENDER_SERVICE_ID"), db, replica, readonly,
                    options["expected_sha"], os.environ.get("RENDER_GIT_COMMIT", "")
                )
                baseline_session = capture_session(connection)
                host_evidence = verify_render_host_binding(
                    connection.settings_dict.get("HOST", ""),
                    baseline_session.username,
                    baseline_session.server_address,
                    baseline_session.server_port,
                )
                executor = MigrationExecutor(connection)
                executor.loader.check_consistent_history(connection)
                if executor.loader.detect_conflicts():
                    raise CommandError("Migration conflicts")
                plan = executor.migration_plan([TARGET])
                verify_plan(plan)
                assert_same_session(connection, baseline_session)
                self.stdout.write("PREFLIGHT_PLAN_PASS: exactly ai_core.0001 and ai_core.0002")
                self.stdout.write("C02_CONFIGURED_RENDER_HOST_POLICY: PASS")
                self.stdout.write(
                    "C02_DNS_SERVER_IP_MATCH: "
                    + ("YES" if host_evidence.dns_server_ip_match else "NO")
                    + " (DIAGNOSTIC_ONLY)"
                )
                self.stdout.write(
                    "C02_ROUTE_REVIEW_REQUIRED: "
                    + ("NO" if host_evidence.dns_server_ip_match else "YES")
                )
                self.stdout.write("C02_INDEPENDENT_RESOURCE_ATTESTATION: UNKNOWN")
                self.stdout.write("MIGRATION_GO: NO; no SQL writes performed")
            finally:
                cursor.execute("ROLLBACK")
