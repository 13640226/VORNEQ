# Production Readiness Runbook

This document defines the minimum operational discipline for deploying VORNEQ.
The goal is to keep infrastructure changes observable, reversible, and separate
from trust-state/business logic.

## Deployment sequence

1. Confirm CI is green for the exact commit being deployed.
2. Confirm a recent database backup or managed-provider snapshot exists.
3. Run the read-only migration preflight:

   ```bash
   python manage.py migration_preflight
   ```

4. Review the pending migration plan printed by preflight.
5. Apply migrations:

   ```bash
   python manage.py migrate --noinput
   ```

6. Start the application and verify `/health/` returns HTTP 200.
7. Verify one authenticated path and one public path manually on staging.

## What migration preflight guarantees

`migration_preflight` is intentionally read-only. It checks:

- conflicting migration leaf nodes;
- inconsistent Django migration history;
- the pending migration plan.

It does **not** perform automatic repair, fake migrations, schema mutation, or a
complete PostgreSQL schema diff. Database-specific orphan objects or partial
DDL left by a failed migration still require a targeted diagnostic before any
repair is attempted.

## Backup and restore

Do not rely on the web service filesystem as a backup destination. Production
backups must live outside the application instance, for example a managed
PostgreSQL snapshot/export or a secure external backup target.

Before a risky migration, record:

- backup/snapshot identifier;
- database environment;
- application commit SHA;
- migration target;
- operator and timestamp.

A restore should be rehearsed on staging before being treated as a production
rollback strategy.

## Migration rollback

Do not automate generic reverse migrations. A Django reverse migration can be
destructive or may not restore deleted data. For every migration that requires
a rollback path:

1. inspect the migration's reverse operations;
2. determine whether restoring the database backup is safer;
3. test the rollback on staging;
4. document the exact previous migration target and expected data effects.

## Object storage

Local development uses `FileSystemStorage`. Render can opt in to S3-compatible
object storage by setting:

- `USE_OBJECT_STORAGE=True`
- `OBJECT_STORAGE_BUCKET`
- `OBJECT_STORAGE_ENDPOINT_URL` (required for R2/custom S3; optional for AWS)
- `OBJECT_STORAGE_REGION` (when applicable)
- `OBJECT_STORAGE_ACCESS_KEY_ID` (when not using provider credential discovery)
- `OBJECT_STORAGE_SECRET_ACCESS_KEY` (when not using provider credential discovery)

Objects are private by default, signed URLs are enabled, and file overwrite is
disabled. Static files continue to use WhiteNoise and are not moved to object
storage by this foundation.

Enabling object storage does not migrate existing local files. Existing avatar
or media objects must be copied and verified separately before the flag is
turned on for an environment containing user data.

## Health endpoint

`GET /health/` is unprefixed and read-only. It checks:

- database connectivity with `SELECT 1`;
- default storage reachability/configuration using a non-mutating `exists()`
  call.

The endpoint returns HTTP 200 when all checks pass and HTTP 503 when a check
fails. Exception details are logged server-side and are not exposed publicly.

## Environment parity

`config.settings` remains the common base. `config.settings_render` should only
override infrastructure-specific concerns such as `DATABASES` and optional
object storage. Feature/business settings should not diverge between local,
staging, and production without an explicit reason.
