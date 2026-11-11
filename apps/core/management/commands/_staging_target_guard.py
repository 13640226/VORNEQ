"""Fail-closed target attestation for staging-only data-mutating commands.

Environment labels alone do not attest the PostgreSQL target. Require pinned
expected DB name, login role, server endpoint and port, and verify runtime SQL
identity before the first write.
"""
import os

from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection


def require_staging_target():
    if getattr(settings, "VORNEQ_ENV", None) != "staging":
        raise CommandError("Refusing to seed outside VORNEQ_ENV=staging.")
    expected_name = os.environ.get("VORNEQ_EXPECTED_STAGING_DATABASE", "").strip()
    expected_user = os.environ.get("VORNEQ_EXPECTED_STAGING_DB_USER", "").strip()
    expected_host = os.environ.get("VORNEQ_EXPECTED_STAGING_DB_HOST", "").strip().lower().rstrip(".")
    expected_port = os.environ.get("VORNEQ_EXPECTED_STAGING_DB_PORT", "").strip()

    if not expected_name.startswith("vorneq_staging_db_"):
        raise CommandError("Refusing to seed: staging database identity is missing or invalid.")
    if expected_user != f"{expected_name}_user":
        raise CommandError("Refusing to seed: staging database user identity is missing or invalid.")
    if not expected_host or expected_host in {"localhost", "127.0.0.1", "::1"}:
        raise CommandError("Refusing to seed: expected staging database host is missing or invalid.")
    if not expected_port.isdecimal() or not (1 <= int(expected_port) <= 65535):
        raise CommandError("Refusing to seed: expected staging database port is missing or invalid.")

    if connection.vendor != "postgresql":
        raise CommandError("Refusing to seed: target must be PostgreSQL.")

    configured_host = str(connection.settings_dict.get("HOST") or "").strip().lower().rstrip(".")
    configured_port = str(connection.settings_dict.get("PORT") or "").strip()
    if configured_host != expected_host or configured_port != expected_port:
        raise CommandError("Refusing to seed: PostgreSQL connection endpoint does not match staging target.")

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user, inet_server_port()")
        row = cursor.fetchone()
    if (
        not row
        or len(row) != 3
        or row[0] != expected_name
        or row[1] != expected_user
        or str(row[2]) != expected_port
    ):
        raise CommandError("Refusing to seed: PostgreSQL runtime identity does not match staging target.")
