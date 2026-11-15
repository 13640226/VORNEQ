"""Fail-closed documentary preflight for ai_core migration (no writes).

C02 requires independently verified Render resource identity and same-context
attestation; neither a caller-provided IP nor Django's database name proves it.
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

TARGET = ("ai_core", "0002_aichatrequestguard")
EXPECTED = (("ai_core", "0001_initial"), ("ai_core", "0002_aichatrequestguard"))
EXPECTED_SERVICE = "srv-dadn07eq1p3s73eccau0"
EXPECTED_DATABASE = "vorneq_production_db"


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
                executor = MigrationExecutor(connection)
                executor.loader.check_consistent_history(connection)
                if executor.loader.detect_conflicts():
                    raise CommandError("Migration conflicts")
                plan = executor.migration_plan([TARGET])
                verify_plan(plan)
                self.stdout.write("PREFLIGHT_PLAN_PASS: exactly ai_core.0001 and ai_core.0002")
                self.stdout.write("C02_INDEPENDENT_RESOURCE_ATTESTATION: UNKNOWN")
                self.stdout.write("MIGRATION_GO: NO; no SQL writes performed")
            finally:
                cursor.execute("ROLLBACK")
