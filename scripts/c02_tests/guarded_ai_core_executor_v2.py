"""C02 guarded ai_core migration executor: DISPOSABLE LAB ONLY, rollback always.

This is an executable design prototype for SHA-bound, locked, same-session
PostgreSQL migrations. It *cannot* apply in Production or Staging.
It does NOT prove Render's backend resource ID. That remains an external blocker.
No caller-provided DATABASE_URL, DB_HOST, DB_USER or DB_NAME is accepted.
"""
import argparse
import hmac
import os
import re
import subprocess
from pathlib import Path

GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
EXPECTED = (("ai_core", "0001_initial"), ("ai_core", "0002_aichatrequestguard"))
TARGET = EXPECTED[-1]

LAB_DB = "isolated_c02_test"
LAB_USER = "c02test"
LAB_PG_MAJOR = 18
LOCK_KEY = 62520261115  # cooperative transaction-scoped C02 lab mutex


class LabGateError(RuntimeError):
    pass


class DeliberateLabRollback(Exception):
    pass


def require_lab_environment(environ, expected_sha, actual_sha):
    """Deny Production, Staging, Render runtime and caller-supplied DB targets."""
    if environ.get("VORNEQ_ENV") != "development":
        raise LabGateError("C02 LAB ENV DENIED")
    if environ.get("C02_ENABLE_DISPOSABLE_DDL_REHEARSAL") != "YES":
        raise LabGateError("C02 LAB EXPLICIT ENABLE REQUIRED")
    if any(environ.get(x) for x in (
        "DATABASE_URL", "RENDER_SERVICE_ID", "RENDER_GIT_COMMIT",
        "RENDER_EXTERNAL_URL", "RENDER_API_KEY",
    )):
        raise LabGateError("C02 LAB RENDER OR DATABASE ENV DETECTED")
    if not isinstance(expected_sha, str) or not GIT_SHA.fullmatch(expected_sha):
        raise LabGateError("C02 LAB EXPECTED SHA MALFORMED")
    if not isinstance(actual_sha, str) or not GIT_SHA.fullmatch(actual_sha):
        raise LabGateError("C02 LAB SOURCE SHA MALFORMED")
    if not hmac.compare_digest(expected_sha, actual_sha):
        raise LabGateError("C02 LAB SHA MISMATCH")


def fixed_lab_target(environ):
    """Host is chosen from an exact allowlist; no dynamic URL input."""
    if environ.get("C02_TEST_LOOPBACK") == "1":
        return "127.0.0.1", 15432
    if environ.get("C02_TEST_LOOPBACK") in (None, "", "0"):
        return "vorneq-c02-db", 5432
    raise LabGateError("C02 LAB NETWORK MODE DENIED")


def require_db_identity(observed):
    """Exactly (database, user, PG major, is_replica)."""
    if observed != (LAB_DB, LAB_USER, LAB_PG_MAJOR, False):
        raise LabGateError("C02 LAB POSTGRES IDENTITY MISMATCH")


def verify_exact_plan(plan):
    items = tuple((m.app_label, m.name) for m, reverse in plan)
    if len(plan) != 2 or any(reverse for _, reverse in plan) or items != EXPECTED:
        raise LabGateError("C02 LAB MIGRATION PLAN MISMATCH")


def verify_same_write_transaction(initial, current, first_driver, connection):
    """Compare PostgreSQL backend identity and txid, not just a Django wrapper."""
    if connection.connection is not first_driver or initial != current:
        raise LabGateError("C02 LAB TOCTOU CONNECTION OR TXID CHANGED")
    if current[1:4] != (LAB_DB, LAB_USER, LAB_PG_MAJOR):
        raise LabGateError("C02 LAB WRITE SESSION IDENTITY CHANGED")
    if current[6] != "off" or current[7] is not False:
        raise LabGateError("C02 LAB WRITABLE PRIMARY SESSION REQUIRED")


def current_checkout_sha():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root),
        check=True, capture_output=True, text=True, timeout=10,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(root),
        check=True, capture_output=True, text=True, timeout=10,
    )
    if status.stdout.strip():
        raise LabGateError("C02 LAB CHECKOUT DIRTY OR UNTRACKED FILES")
    return result.stdout.strip()


def run_lab(expected_sha):
    environ = os.environ
    actual_sha = current_checkout_sha()
    require_lab_environment(environ, expected_sha, actual_sha)
    host, port = fixed_lab_target(environ)

    from django.conf import settings
    if settings.configured:
        raise LabGateError("C02 LAB DJANGO SETTINGS ALREADY CONFIGURED")
    settings.configure(
        DATABASES={"default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": LAB_DB, "USER": LAB_USER, "PASSWORD": "localonly",
            "HOST": host, "PORT": str(port), "CONN_MAX_AGE": 0,
        }},
        INSTALLED_APPS=["apps.ai_core"],
        SECRET_KEY="disposable-c02-v2-rollback-only",
        USE_TZ=True,
    )
    import django
    django.setup()
    from django.db import connection, transaction
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.recorder import MigrationRecorder

    def identity():
        with connection.cursor() as cur:
            cur.execute(
                "SELECT current_database(), current_user, "
                "current_setting('server_version_num')::int / 10000, "
                "pg_is_in_recovery()"
            )
            return cur.fetchone()

    def snapshot():
        with connection.cursor() as cur:
            cur.execute(
                "SELECT pg_backend_pid(), current_database(), current_user, "
                "current_setting('server_version_num')::int / 10000, "
                "inet_server_addr()::text, inet_server_port(), "
                "current_setting('transaction_read_only'), "
                "pg_is_in_recovery(), txid_current()"
            )
            return cur.fetchone()

    def counts():
        with connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'ai_core_%'")
            tables = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM django_migrations WHERE app='ai_core'")
            migrations = cur.fetchone()[0]
        return tables, migrations

    # Both database and user must be exact in the *live connected session*.
    # The disposable recorder DDL is deliberately outside the reversible test.
    require_db_identity(identity())
    if connection.settings_dict["HOST"] != host or int(connection.settings_dict["PORT"]) != port:
        raise LabGateError("C02 LAB DJANGO CONNECTION CONFIG MISMATCH")
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('public.django_migrations')")
        existing_recorder = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'ai_core_%'")
        if cur.fetchone()[0]:
            raise LabGateError("C02 LAB ALREADY HAS AI CORE TABLES")
        if existing_recorder:
            cur.execute("SELECT count(*) FROM django_migrations WHERE app='ai_core'")
            if cur.fetchone()[0]:
                raise LabGateError("C02 LAB ALREADY HAS AI CORE HISTORY")
    MigrationRecorder(connection).ensure_schema()  # DISPOSABLE DATABASE ONLY

    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout = '2000ms'")
                cur.execute("SET LOCAL statement_timeout = '25000ms'")
                cur.execute("LOCK TABLE django_migrations IN SHARE ROW EXCLUSIVE MODE NOWAIT")
                cur.execute("SELECT pg_try_advisory_xact_lock(%s)", [LOCK_KEY])
                if cur.fetchone()[0] is not True:
                    raise LabGateError("C02 LAB COOPERATIVE ADVISORY LOCK BUSY")
            first_driver = connection.connection
            before = snapshot()
            if before[6] != "off" or before[7] is not False:
                raise LabGateError("C02 LAB NOT A WRITABLE PRIMARY")
            require_db_identity((before[1], before[2], before[3], before[7]))
            if counts() != (0, 0):
                raise LabGateError("C02 LAB MIGRATION HISTORY OR TABLES NOT EMPTY")

            executor = MigrationExecutor(connection)
            executor.loader.check_consistent_history(connection)
            if executor.loader.detect_conflicts():
                raise LabGateError("C02 LAB CONFLICTING MIGRATIONS")
            verify_exact_plan(executor.migration_plan([TARGET]))
            verify_same_write_transaction(before, snapshot(), first_driver, connection)
            print("PASS: SHA, lab DB identity, recorder and advisory locks, exact migration plan")

            # ONLY disposable isolated_c02_test database; never executed by a
            # Production Django command or connected credentials.
            executor.migrate([TARGET])

            after = snapshot()
            verify_same_write_transaction(before, after, first_driver, connection)
            if current_checkout_sha() != actual_sha:
                raise LabGateError("C02 LAB SOURCE SHA DRIFT AFTER DDL")
            if counts() != (2, 2):
                raise LabGateError("C02 LAB POST MIGRATION SCHEMA/HISTORY MISMATCH")
            if MigrationExecutor(connection).migration_plan([TARGET]):
                raise LabGateError("C02 LAB MIGRATION PLAN NOT EMPTY AFTER APPLY")
            print("PASS: actual 0001/0002 DDL under same locked transaction and backend")
            raise DeliberateLabRollback()

    except DeliberateLabRollback:
        print("PASS: deliberate rollback of both ai_core DDL migrations")

    if counts() != (0, 0):
        raise LabGateError("C02 LAB ROLLBACK FAILED")
    print("PASS: no ai_core tables or recorder rows persisted")
    print("C02_GUARDED_LAB_REHEARSAL_PASS / PRODUCTION_GO=NO")
    connection.close()


def main():
    parser = argparse.ArgumentParser(description="C02 isolated guarded ai_core rehearsal only")
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    run_lab(args.expected_sha)


if __name__ == "__main__":
    main()
