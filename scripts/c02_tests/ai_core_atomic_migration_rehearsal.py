"""Actual ai_core 0001/0002 Django MigrationExecutor transaction rehearsal.

STRICTLY DISPOSABLE PostgreSQL 18 ONLY. NEVER RUN IN PRODUCTION/STAGING.
No network endpoint or credentials can be supplied by DATABASE_URL.
This intentionally executes real ai_core DDL inside a single transaction on
isolated_c02_test and then ROLLS IT BACK on purpose.
This is a lab proof, NOT an authorized Production migration apply path.
"""
import os

if os.environ.get("VORNEQ_ENV") == "production":
    raise SystemExit("PRODUCTION EXECUTION FORBIDDEN")

LOOPBACK = os.environ.get("C02_TEST_LOOPBACK") == "1"
HOST = "127.0.0.1" if LOOPBACK else "vorneq-c02-db"
PORT = "15432" if LOOPBACK else "5432"

from django.conf import settings

settings.configure(
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "isolated_c02_test",
            "USER": "c02test",
            "PASSWORD": "localonly",
            "HOST": HOST,
            "PORT": PORT,
        }
    },
    INSTALLED_APPS=["apps.ai_core"],
    SECRET_KEY="disposable-c02-test-only",
    USE_TZ=True,
)
import django

django.setup()

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

TARGET = ("ai_core", "0002_aichatrequestguard")
EXPECTED = (("ai_core", "0001_initial"), TARGET)


class DeliberateLabRollback(Exception):
    pass


with connection.cursor() as cursor:
    cursor.execute(
        "SELECT current_database(), current_user, "
        "current_setting('server_version_num')::int / 10000, pg_is_in_recovery()"
    )
    identity = cursor.fetchone()
    if identity != ("isolated_c02_test", "c02test", 18, False):
        raise SystemExit("Unsafe isolated database identity")
    cursor.execute(
        "SELECT count(*) FROM pg_tables WHERE schemaname='public' "
        "AND tablename LIKE 'ai_core_%'"
    )
    if cursor.fetchone()[0] != 0:
        raise SystemExit("Lab ai_core tables already exist: refusal to run")
    cursor.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='django_migrations'"
    )
    migration_table_exists = cursor.fetchone()[0] == 1
    if migration_table_exists:
        cursor.execute(
            "SELECT count(*) FROM django_migrations WHERE app='ai_core'"
        )
        if cursor.fetchone()[0] != 0:
            raise SystemExit("Lab ai_core migration history not empty")

MigrationRecorder(connection).ensure_schema()  # ONLY disposable lab DB

try:
    with transaction.atomic(using="default"):
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '2000ms'")
            cursor.execute("SET LOCAL statement_timeout = '20000ms'")
            cursor.execute(
                "LOCK TABLE django_migrations IN SHARE ROW EXCLUSIVE MODE NOWAIT"
            )
            cursor.execute("SELECT pg_backend_pid()")
            backend_pid_before = cursor.fetchone()[0]
        driver_before = connection.connection
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        original = executor.migration_plan([TARGET])
        planned = tuple((m.app_label, m.name) for m, reverse in original if not reverse)
        if any(reverse for _, reverse in original) or planned != EXPECTED:
            raise RuntimeError("Unexpected isolated ai_core migration plan")
        print("PASS: exact ai_core 0001/0002 plan under transaction-scoped recorder lock")

        # The only real DDL action here takes place in disposable test DB.
        executor.migrate([TARGET])

        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            backend_pid_after = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*) FROM django_migrations WHERE app='ai_core'"
            )
            applied = cursor.fetchone()[0]
            cursor.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname='public' "
                "AND tablename LIKE 'ai_core_%'"
            )
            new_tables = cursor.fetchone()[0]
        if connection.connection is not driver_before or backend_pid_after != backend_pid_before:
            raise RuntimeError("TOCTOU: PostgreSQL session replaced during migration")
        if applied != 2 or new_tables != 2:
            raise RuntimeError("Atomic migration did not create exact test state")
        remaining = MigrationExecutor(connection).migration_plan([TARGET])
        if remaining:
            raise RuntimeError("Post-migrate plan not empty in same lab transaction")
        print("PASS: real 0001/0002 DDL and migration history in SAME isolated transaction")
        print("PASS: stable PostgreSQL driver/backend PID and empty post-apply plan")
        raise DeliberateLabRollback()

except DeliberateLabRollback:
    print("PASS: intentional rollback of ALL ai_core DDL and migration records")

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT count(*) FROM django_migrations WHERE app='ai_core'"
    )
    migrated = cursor.fetchone()[0]
    cursor.execute(
        "SELECT count(*) FROM pg_tables WHERE schemaname='public' "
        "AND tablename LIKE 'ai_core_%'"
    )
    tables = cursor.fetchone()[0]
if migrated or tables:
    raise RuntimeError("Unsafe: isolation rollback left ai_core objects")
print("PASS: no ai_core schema or migration records persisted")
print("C02_ISOLATED_AI_CORE_ATOMIC_REHEARSAL_PASS")
connection.close()
