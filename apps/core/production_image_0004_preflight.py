"""Read-only production image migration inspection; no execution permission."""
from __future__ import annotations

import os
import re

from django.conf import settings
from django.db import transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from apps.core import c02_operational_binding as binding

SERVICE = "srv-dadn07eq1p3s73eccau0"
TARGET = ("ai_core", "0004_image_generation_job_v1")
HISTORY_BEFORE = ("0001_initial", "0002_aichatrequestguard", "0003_conversation")
TABLES_BEFORE = frozenset({
    "ai_core_stagingaibudgetday", "ai_core_aichatrequestguard",
    "ai_core_aiconversation", "ai_core_aimessage",
})
IMAGE_TABLES = frozenset({"ai_core_aiimagejob", "ai_core_aiimagedailyquota"})
SHA = re.compile(r"[0-9a-f]{40}\Z")


class PreflightDenied(Exception):
    """No write authorization is provided by this module."""


def require(ok, message):
    if not ok:
        raise PreflightDenied(message)


def check_context(environ, sha, db_config, *, runtime=None):
    runtime = settings if runtime is None else runtime
    require(isinstance(sha, str) and SHA.fullmatch(sha), "invalid SHA")
    require(environ.get("VORNEQ_ENV") == "production"
            and getattr(runtime, "VORNEQ_ENV", None) == "production"
            and getattr(runtime, "DEBUG", True) is False, "production identity required")
    require(environ.get("RENDER_SERVICE_ID") == SERVICE, "wrong Render service")
    require(environ.get("RENDER_GIT_COMMIT") == sha, "runtime SHA mismatch")
    for key in ("VORNEQ_AI_IMAGE_ENABLED", "VORNEQ_AI_IMAGE_UI_ENABLED",
                "VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED", "VORNEQ_AI_IMAGE_PAID_WORKER_ENABLED"):
        require(getattr(runtime, key, False) is False
                and environ.get(key, "").lower() in ("", "false", "off", "0", "no"),
                "image gates must be closed")
    require(db_config.get("ENGINE", "").endswith("postgresql"), "PostgreSQL required")
    url = environ.get("DATABASE_URL", "")
    try:
        bound = (binding.classify_host(binding.parse_url(url)["HOST"]) == "INTERNAL_EXACT"
                 and binding.settings_match_url(db_config, url))
    except (ValueError, TypeError):
        bound = False
    require(bound, "configured connection does not match pinned internal URL")
    require(db_config.get("NAME") == binding.EXPECTED_DATABASE
            and db_config.get("USER") == binding.EXPECTED_DATABASE_USER
            and str(db_config.get("PORT") or "5432") == "5432", "unexpected database settings")


def check_identity(row):
    database, user, login, port, mode, recovery, major, xid = row
    require(database == binding.EXPECTED_DATABASE
            and login == binding.EXPECTED_DATABASE_USER
            and user in (binding.EXPECTED_DATABASE_USER, binding.EXPECTED_EXECUTION_ROLE)
            and port == 5432 and mode == "on" and recovery is False and major == 18
            and xid is None, "read-only database identity mismatch")


def check_state(history, tables, plan):
    require(history == HISTORY_BEFORE, "unexpected ai_core migration history")
    require(tables == TABLES_BEFORE, "unexpected ai_core table set")
    require(plan == ((TARGET[0], TARGET[1], False),), "not an exact forward 0004 plan")


def inspect(connection, sha, *, environ=None):
    """Return only a review result; no migrate, receipt, or permission path."""
    check_context(os.environ if environ is None else environ, sha, connection.settings_dict)
    require(connection.vendor == "postgresql" and not connection.in_atomic_block
            and connection.get_autocommit(), "outermost PostgreSQL transaction required")
    with transaction.atomic(using=connection.alias):
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '8000ms'")
            cursor.execute(
                "SELECT current_database(), current_user, session_user, inet_server_port(), "
                "current_setting('transaction_read_only'), pg_is_in_recovery(), "
                "current_setting('server_version_num')::int / 10000, txid_current_if_assigned()"
            )
            check_identity(cursor.fetchone())
            require(MigrationRecorder(connection).has_table(), "migration recorder missing")
            cursor.execute("SELECT name FROM django_migrations WHERE app = 'ai_core' ORDER BY name")
            history = tuple(row[0] for row in cursor.fetchall())
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema() "
                           "AND tablename LIKE 'ai_core_%'")
            tables = frozenset(row[0] for row in cursor.fetchall())
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        require(not executor.loader.detect_conflicts(), "migration graph conflict")
        plan = tuple((mig.app_label, mig.name, backwards)
                     for mig, backwards in executor.migration_plan([TARGET]))
        check_state(history, tables, plan)
    return {"read_only": True, "identity_and_plan_pass": True,
            "migration_authorized": False, "migration_executed": False,
            "identity_limit": "operational_internal_url_not_cryptographic"}
