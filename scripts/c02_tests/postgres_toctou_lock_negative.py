"""Disposable PostgreSQL TOCTOU locking and same-session negative test.

DO NOT run against Production, staging, or restored real data.
Connects ONLY to the dedicated isolated_c02_test database on the
private Docker network alias vorneq-c02-db using throwaway credentials.

Creates and drops c02_isolated_fence_probe in that disposable database.
Demonstrates that a transaction-scoped PostgreSQL table lock serializes
participating writers and that a replaced driver/session fails closed.
This is NOT a VORNEQ ai_core MigrationExecutor application test and does
NOT authorize an actual Production migration.
"""
import os

import psycopg
from django.core.management.base import CommandError

from apps.core.management.commands.postgres_session_guard import (
    capture_session, assert_same_session,
)

if os.environ.get("VORNEQ_ENV") == "production":
    raise RuntimeError("PRODUCTION ACCESS FORBIDDEN")

# Explicit Windows host-side lab mode: still only a disposable, loopback-only DB.
# All other host, port, username and database combinations are forbidden.
if os.environ.get("C02_TEST_LOOPBACK") == "1":
    DSN = "host=127.0.0.1 port=15432 dbname=isolated_c02_test user=c02test password=localonly"
else:
    DSN = "host=vorneq-c02-db port=5432 dbname=isolated_c02_test user=c02test password=localonly"
TABLE = "c02_isolated_fence_probe"


class Wrapper:
    vendor = "postgresql"

    def __init__(self, driver):
        self.connection = driver

    def cursor(self):
        return self.connection.cursor()


with psycopg.connect(DSN) as setup:
    database, username, major, replica = setup.execute(
        "SELECT current_database(), current_user, "
        "current_setting('server_version_num')::int / 10000, pg_is_in_recovery()"
    ).fetchone()
    if (database, username, int(major), replica) != (
        "isolated_c02_test", "c02test", 18, False
    ):
        raise RuntimeError("Unsafe isolated database target identity")
    setup.execute("CREATE TABLE IF NOT EXISTS c02_isolated_fence_probe (id bigint PRIMARY KEY)")
print("PASS: disposable database identity")

try:
    with psycopg.connect(DSN) as a, psycopg.connect(DSN) as b:
        a.execute("SET LOCAL lock_timeout = '2000ms'")
        a.execute("LOCK TABLE c02_isolated_fence_probe IN SHARE ROW EXCLUSIVE MODE NOWAIT")
        try:
            b.execute("LOCK TABLE c02_isolated_fence_probe IN SHARE ROW EXCLUSIVE MODE NOWAIT")
        except psycopg.errors.LockNotAvailable:
            print("PASS: second transaction fails closed under held lock")
            b.rollback()
        else:
            raise AssertionError("Unsafe: competing writer acquired lock")
        a.commit()
        b.execute("SET LOCAL lock_timeout = '2000ms'")
        b.execute("LOCK TABLE c02_isolated_fence_probe IN SHARE ROW EXCLUSIVE MODE NOWAIT")
        print("PASS: lock can be acquired only after first transaction ends")
        b.rollback()

    with psycopg.connect(DSN, autocommit=True) as original:
        original.execute("BEGIN TRANSACTION READ ONLY")
        observed = Wrapper(original)
        session = capture_session(observed)
        assert_same_session(observed, session)
        print("PASS: same-session read-only observation")
        original.execute("ROLLBACK")
        with psycopg.connect(DSN, autocommit=True) as replacement:
            replacement.execute("BEGIN TRANSACTION READ ONLY")
            observed.connection = replacement
            try:
                assert_same_session(observed, session)
            except CommandError:
                print("PASS: replaced connection fails closed before migration")
            else:
                raise AssertionError("Unsafe: stale session accepted")
            replacement.execute("ROLLBACK")
finally:
    with psycopg.connect(DSN) as cleanup:
        cleanup.execute("DROP TABLE IF EXISTS c02_isolated_fence_probe")
print("C02_ISOLATED_TOCTOU_LOCK_TESTS_PASS")
