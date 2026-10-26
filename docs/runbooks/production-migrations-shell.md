# Production migrations via Render Shell

Status: active since 2026-10-26. Owner decisions recorded in the platform review.

## Why this path exists

- `vorneq-production-db` blocks all internet traffic (PostgreSQL inbound IP rules empty, 2026-10-26).
- GitHub Actions can no longer reach Production. These workflows are disabled:
  `migrate-production.yml`, `inspect-production-migration-preflight.yml`,
  `inspect-production-db-identity.yml`, `inspect-database-identity.yml`.
- The VORNEQ web service has **no Pre-Deploy Command**. Deploys never run migrations
  (also enforced for `render.yaml` by `apps/core/tests/test_render_blueprint.py`).
- Migrations run only from the Render **Shell** of the VORNEQ service, which reaches the
  database over Render's internal network.

Render One-Off Jobs are API-only and are not used here.

## Rules

1. Every step needs a separate, explicit owner approval in writing:
   deploy, preflight, apply. Approval of one step never covers the next.
2. Never print or paste `DATABASE_URL`, passwords or tokens.
3. The Shell runs inside the **currently deployed** build. A new migration is available
   only after the commit that contains it has been deployed.
4. Prefer backward-compatible migrations (add nullable columns first, use them later),
   because code is live before `migrate` runs. Use Render maintenance mode if not.

## Order for a commit that contains migrations

1. Merge the PR.
2. Deploy the commit (owner approval). Check the live commit and `/health/`.
3. Run **Preflight** (below). Read-only.
4. Owner reviews the Preflight output and approves Apply.
5. Run **Apply** (below).
6. Check `/health/` and record the result.

## Preflight (read-only)

Dashboard: VORNEQ, then Shell. Paste as one line:

```sh
export DJANGO_SETTINGS_MODULE=config.settings_render VORNEQ_ALLOW_INSPECT_MIGRATION_PREFLIGHT=yes VORNEQ_INSPECT_MIGRATION_PREFLIGHT_LABEL="Production Migration Preflight" && python manage.py shell -c "from django.db import connection; c=connection.cursor(); c.execute('select current_database()'); print('DB:', c.fetchone()[0])" && python manage.py migration_preflight && python manage.py inspect_migration_preflight && python manage.py migrate --plan
```

Expected:

- `DB: vorneq_production_db`
- `Migration preflight passed: history is consistent and no conflicts were detected.`
- `RESULT: SAFE`
- `migrate --plan` lists exactly the expected migrations (or `No planned migration operations.`)

Stop if any line differs, if a traceback appears, or if `DB:` is not `vorneq_production_db`.

Verified on 2026-10-26 20:03 (instance 754b2, commit 5ed0397): all four lines as expected,
no pending migrations.

## Apply (only after a separate approval of the Preflight output)

```sh
export DJANGO_SETTINGS_MODULE=config.settings_render && python manage.py shell -c "from django.db import connection; c=connection.cursor(); c.execute('select current_database()'); print('DB:', c.fetchone()[0])" && python manage.py migrate --noinput && python manage.py migrate --check && python manage.py showmigrations --plan
```

Expected: `DB: vorneq_production_db`, one `Applying ... OK` per planned migration,
`migrate --check` exits without error.

## Restoring the GitHub path

Only with a new owner decision: add a network path from GitHub Actions to the database
(inbound IP rule) and re-enable the four workflows with `gh workflow enable`.
