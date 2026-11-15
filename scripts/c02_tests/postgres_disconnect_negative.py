"""Isolated localhost PostgreSQL 18 negative tests. No Render connections."""
import os
import psycopg
from django.core.management.base import CommandError
from apps.core.management.commands.postgres_session_guard import capture_session, assert_same_session

dsn = "host=vorneq-c02-db port=5432 dbname=isolated_c02_test user=c02test password=localonly"
class Wrapper:
    vendor = "postgresql"
    def __init__(self, db): self.connection = db
    def cursor(self): return self.connection.cursor()

def check(condition, label):
    if not condition: raise AssertionError(label)
    print("PASS:", label)

with psycopg.connect(dsn, autocommit=True) as first, psycopg.connect(dsn, autocommit=True) as killer:
    first.execute("BEGIN TRANSACTION READ ONLY")
    conn = Wrapper(first)
    baseline = capture_session(conn)
    check(assert_same_session(conn, baseline) == baseline, "stable session")
    killer.execute("SELECT pg_terminate_backend(%s)", (baseline.backend_pid,))
    try:
        assert_same_session(conn, baseline)
    except (psycopg.Error, CommandError):
        print("PASS: terminated backend fails closed")
    else:
        raise AssertionError("terminated backend accepted")
with psycopg.connect(dsn, autocommit=True) as second:
    second.execute("BEGIN TRANSACTION READ ONLY")
    conn.connection = second
    try:
        assert_same_session(conn, baseline)
    except CommandError:
        print("PASS: replaced driver rejected")
    else:
        raise AssertionError("replacement accepted")
with psycopg.connect(dsn, autocommit=True) as third:
    conn = Wrapper(third)
    try:
        capture_session(conn)
    except CommandError:
        print("PASS: writable transaction rejected")
    else:
        raise AssertionError("writable accepted")
print("ISOLATED_POSTGRES_NEGATIVE_TESTS_PASS")
