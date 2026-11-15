"""Disposable PostgreSQL migration lifecycle negative test; no Render access."""
from django.conf import settings
settings.configure(
 DATABASES={"default":{"ENGINE":"django.db.backends.postgresql","NAME":"isolated_c02_test",
 "USER":"c02test","PASSWORD":"localonly","HOST":"vorneq-c02-db","PORT":"5432"}},
 SECRET_KEY="isolated",INSTALLED_APPS=["django.contrib.contenttypes"],USE_TZ=True)
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.core.management.base import CommandError
from apps.core.management.commands.postgres_session_guard import capture_session,assert_same_session

# Establish that actual MigrationExecutor plans DDL for a clean disposable database.
executor=MigrationExecutor(connection)
plan=executor.migration_plan(executor.loader.graph.leaf_nodes())
assert plan, "Expected migrations in fresh isolated DB"
print("PASS: real MigrationExecutor nonempty plan",len(plan))

# Preflight is a separate read-only transaction, never an apply authorization.
with connection.cursor() as cur:
    cur.execute("BEGIN TRANSACTION READ ONLY")
    before=capture_session(connection)
    assert_same_session(connection,before)
    cur.execute("ROLLBACK")
print("PASS: read-only plan observation completed")

# Simulate session replacement before apply. Gate must fail before migrate().
connection.close()
connection.ensure_connection()
with connection.cursor() as cur: cur.execute("BEGIN TRANSACTION READ ONLY")
try:
    assert_same_session(connection,before)
except CommandError:
    print("PASS: stale preflight session blocks migration apply")
else:
    raise AssertionError("Unsafe: stale preflight accepted")
with connection.cursor() as cur: cur.execute("ROLLBACK")

# Only the isolated test DB is migrated, to validate actual MigrationExecutor DDL path.
executor=MigrationExecutor(connection)
targets=executor.loader.graph.leaf_nodes()
executor.migrate(targets)
print("PASS: real Django MigrationExecutor applied to disposable DB only")
executor=MigrationExecutor(connection)
assert not executor.migration_plan(targets), "Plan not empty after migration"
print("PASS: isolated migration plan now empty")
print("ISOLATED_MIGRATION_LIFECYCLE_PASS")
