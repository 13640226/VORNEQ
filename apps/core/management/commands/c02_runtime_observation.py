"""Emit a non-secret, read-only Production runtime observation for C02.

This is a *snapshot*, not authenticated server identity proof. Never authorizes
or invokes Django migrations. Keep the Render API token OUT of this command.
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.core.management.commands.apply_ai_core_guarded import (
    verify_observation, EXPECTED_DATABASE_USER,
)
from apps.core.management.commands.postgres_session_guard import (
    capture_session, assert_same_session,
)


class Command(BaseCommand):
    help = "C02 read-only runtime snapshot; no migration writes"

    def add_arguments(self, parser):
        parser.add_argument("--expected-sha", required=True)

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("C02 observation requires PostgreSQL")
        if os.environ.get("VORNEQ_ENV") != "production":
            raise CommandError("Production identity context required")
        if os.environ.get("VORNEQ_AI_CORE_ENABLED", "").lower() in ("1", "true", "yes"):
            raise CommandError("AI activation must remain disabled")
        with connection.cursor() as cursor:
            cursor.execute("BEGIN TRANSACTION READ ONLY")
            try:
                cursor.execute("SET LOCAL statement_timeout = '5000ms'")
                cursor.execute(
                    "SELECT current_database(), pg_is_in_recovery(), "
                    "current_setting('transaction_read_only'), "
                    "current_setting('server_version_num')::int"
                )
                db, replica, readonly, version_num = cursor.fetchone()
                verify_observation(
                    os.environ.get("RENDER_SERVICE_ID"),
                    db, replica, readonly, options["expected_sha"],
                    os.environ.get("RENDER_GIT_COMMIT", ""),
                )
                initial = capture_session(connection)
                if initial.username != EXPECTED_DATABASE_USER:
                    raise CommandError("Unexpected Production PostgreSQL user")
                assert_same_session(connection, initial)
                snapshot = {
                    "service_id": os.environ.get("RENDER_SERVICE_ID"),
                    "deploy_sha": os.environ.get("RENDER_GIT_COMMIT"),
                    "database": initial.database,
                    "username": initial.username,
                    "configured_host": connection.settings_dict.get("HOST", ""),
                    "server_port": initial.server_port,
                    "postgres_major": version_num // 10000,
                    "is_replica": initial.replica,
                    "transaction_read_only": initial.readonly,
                    "backend_pid": initial.backend_pid,
                }
            finally:
                cursor.execute("ROLLBACK")
        # Do not emit connection URLs, passwords, keys, or tokens.
        self.stdout.write(json.dumps(snapshot, sort_keys=True))
        self.stdout.write("C02_RUNTIME_SNAPSHOT_ONLY: NO MIGRATION GO")
