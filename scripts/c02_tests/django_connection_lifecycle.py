"""Real Django DatabaseWrapper lifecycle test on disposable Docker PostgreSQL."""
import os
from django.conf import settings
settings.configure(DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "isolated_c02_test", "USER": "c02test", "PASSWORD": "localonly", "HOST": "vorneq-c02-db", "PORT": "5432"}}, SECRET_KEY="isolated-only", INSTALLED_APPS=[])
import django
django.setup()
from django.db import connections
from django.core.management.base import CommandError
from apps.core.management.commands.postgres_session_guard import capture_session, assert_same_session

conn = connections["default"]
conn.settings_dict.update({
    "ENGINE":"django.db.backends.postgresql",
    "NAME":"isolated_c02_test", "USER":"c02test", "PASSWORD":"localonly",
    "HOST":"vorneq-c02-db", "PORT":"5432", "CONN_MAX_AGE":0,
    "OPTIONS":{},
})
conn.ensure_connection()
with conn.cursor() as c: c.execute("BEGIN TRANSACTION READ ONLY")
baseline = capture_session(conn)
assert assert_same_session(conn, baseline) == baseline
print("PASS: Django connection stable")
with conn.cursor() as c: c.execute("ROLLBACK")
conn.close()
conn.ensure_connection()
with conn.cursor() as c: c.execute("BEGIN TRANSACTION READ ONLY")
try:
    assert_same_session(conn, baseline)
except CommandError:
    print("PASS: Django close/reconnect rejected")
else:
    raise AssertionError("Django reconnect accepted")
with conn.cursor() as c: c.execute("ROLLBACK")
conn.close()
print("DJANGO_LIFECYCLE_NEGATIVE_TESTS_PASS")
