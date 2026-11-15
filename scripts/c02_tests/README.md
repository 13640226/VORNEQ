# C02 isolated PostgreSQL regression scripts

These scripts are **destructive only to a disposable test database**. Never point them at Render or Production. The test hostname `vorneq-c02-db` resolves only within a dedicated Docker network; the sample `localonly` password is a throwaway fixture, not a secret.

Run in a temporary Docker network with a fresh `postgres:18` container named `vorneq-c02-db` and database `isolated_c02_test`, user `c02test`, password `localonly`. Run the Python scripts from a separate `python:3.12-slim` container on that network, with this repository mounted read-only as `/src` and `PYTHONPATH=/src`; install `django` and `psycopg[binary]` in the ephemeral Python container. Use a **fresh database for each run**. Do not publish PostgreSQL ports.

- `postgres_disconnect_negative.py`: real backend termination, connection replacement, writable-transaction rejection.
- `django_connection_lifecycle.py`: real Django DatabaseWrapper close/reconnect rejection.
- `migration_executor_lifecycle.py`: **only** Django's built-in `contenttypes` migrations in a disposable database, not VORNEQ's `ai_core` migrations.

These tests do not prove Render resource-ID binding or atomic Production migration TOCTOU safety. C02 remains open; they do not grant Migration GO.
