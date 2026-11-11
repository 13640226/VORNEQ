"""Fail-closed target identity for commands that mutate synthetic staging data.

Required even when a GitHub workflow has its own DB guard: commands can also be
run locally or outside that workflow. This guard checks the ACTUAL database
identity, not just a label or an environment variable.
"""
import os

from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection


def require_staging_target():
    if getattr(settings, "VORNEQ_ENV", None) != "staging":
        raise CommandError("Refusing to seed outside VORNEQ_ENV=staging.")

    expected_database = os.environ.get("VORNEQ_EXPECTED_STAGING_DATABASE", "").strip()
    if not expected_database.startswith("vorneq_staging_db_"):
        raise CommandError(
            "Refusing to seed: an explicit staging database identity is required."
        )
    if connection.vendor != "postgresql":
        raise CommandError("Refusing to seed: target must be PostgreSQL.")

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()
    if not row or row[0] != expected_database:
        raise CommandError(
            "Refusing to seed: database identity does not match the expected staging target."
        )
