# VORNEQ Disaster Recovery Baseline

This document defines the V1 recovery procedure and the evidence required before VORNEQ claims a specific recovery objective. It intentionally does not promise an RTO or RPO that has not been measured in a rehearsal.

## Current deployment baseline

- Render hosts the staging web service.
- PostgreSQL is configured through `DATABASE_URL`.
- `/health/` is the deployment health endpoint.
- Database migration preflight and migrations run in Render's `preDeployCommand` before the new application process starts.
- The repository provides a portable PostgreSQL custom-format backup and an isolated restore rehearsal.

## Recovery objectives

RTO and RPO are **TBD until measured and approved**.

Do not publish a recovery commitment based only on backup frequency. Record actual timings from a staging recovery rehearsal, including:

1. incident declaration to recovery start;
2. backup/PITR selection time;
3. restore completion time;
4. application cutover time;
5. health and data-integrity verification time.

After at least three representative rehearsals, set an operational target and document its owner.

## Render-managed recovery

Render-managed PostgreSQL recovery depends on the database/workspace plan. Paid Render Postgres instances can provide point-in-time recovery; free Postgres instances do not provide Render-managed recovery. Logical exports in the Render dashboard are also plan-dependent.

Before relying on Render-managed recovery, verify the actual database plan and recovery window in the Render dashboard. Repository configuration alone does not prove that PITR or a specific retention window is enabled.

For current Render behavior, see:

- https://render.com/docs/postgresql-backups
- https://render.com/docs/blueprint-spec
- https://render.com/docs/health-checks

## Portable backup

Create a custom-format backup:

```bash
DATABASE_URL='postgresql://...' \
  bash scripts/postgres_backup.sh backup
```

Preview the operation without connecting to PostgreSQL:

```bash
DATABASE_URL='postgresql://...' \
  bash scripts/postgres_backup.sh backup --dry-run
```

List local backups:

```bash
bash scripts/postgres_backup.sh --list
```

Backups are written to `BACKUP_DIR` (default: `backups/`) as `vorneq_<UTC timestamp>.dump`.

The repository does **not** define long-term retention for these files. Production backup storage, encryption, retention, deletion, and access control must be selected explicitly before this mechanism is treated as the production backup system.

## Restore procedure

Restores require a separate `RESTORE_DATABASE_URL`. The script never defaults a restore target to `DATABASE_URL`.

Prefer restoring into a new or isolated database first:

```bash
RESTORE_DATABASE_URL='postgresql://isolated-target...' \
  bash scripts/postgres_backup.sh \
    --restore backups/vorneq_YYYYMMDDTHHMMSSZ.dump \
    --confirm-restore
```

The restore uses `pg_restore --clean --if-exists`. This is destructive to matching objects in the target database. Never point `RESTORE_DATABASE_URL` at a database containing data that has not been explicitly approved for replacement.

## Verification after restore

At minimum:

1. run Django system checks against the restored database;
2. run migrations in plan/check mode and verify schema state;
3. start the application against the restored database;
4. confirm `/health/` returns healthy;
5. execute smoke tests for Home, Search, Library, Marketplace, and Account;
6. verify representative trust, verification, entitlement, content, and media records;
7. record restore start/end timestamps and any manual steps.

Only after validation should consumers be cut over to the recovered database.

## Automated rehearsal

`.github/workflows/backup-restore.yml` creates two isolated PostgreSQL databases, backs up seeded data from one, restores into the other, and verifies the restored row. This proves the repository-level backup/restore contract but does not replace a staging infrastructure rehearsal.

Run an infrastructure rehearsal before making an RTO/RPO commitment. The rehearsal must use the same PostgreSQL major version and materially similar data volume as production/staging.

## Responsibilities

Until explicit on-call roles exist, responsibilities are role-based rather than person-based:

- **Incident lead:** coordinates recovery and cutover.
- **Database operator:** selects backup/PITR source and performs restore.
- **Application verifier:** executes health, smoke, and integrity checks.
- **Change approver:** approves cutover and destructive restore operations.

A future operations/governance PR should map these roles to named rotations or teams.

## Deployment reliability

Render migrations run in `preDeployCommand`; `startCommand` only starts Gunicorn. This separates one-time deployment work from application process startup and keeps the existing `/health/` deployment gate.

Schema changes must continue to follow expand/migrate/contract practices where backward compatibility is required. Moving migrations to pre-deploy does not make destructive migrations zero-downtime by itself.
