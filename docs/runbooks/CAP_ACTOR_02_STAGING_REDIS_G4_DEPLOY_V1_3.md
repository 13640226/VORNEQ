# CAP_ACTOR_02 — Staging Redis activation through standard G4

Status: OPERATIONAL PREPARATION ONLY / NO EXECUTION AUTHORIZATION
Date: 2026-11-10
Repository: 13640226/VORNEQ
Target: vorneq-staging, srv-dbm7dvc9v7es7393g70g
Base SHA: 682fb3639aa27ce4361b94e03497bdb49575bc1c
Related Runbook: Issue #448, comment #6772467804

## Why a new source change is being reviewed

PR #571 installed the Redis Python runtime dependency. The owner saved the private Internal URL as the staging REDIS_URL, but the active Django process continued to report REDIS_URL_SET=False and LocMemCache. The latest observed deployment had the old environment. Re-deployment of a currently live SHA is refused by standard G4. This PR adds a substantive regression test for malformed Redis URL values encountered in the setup and documents the staging-only rollout. This change does not alter runtime code, migrations, production settings, or secrets.

No empty or artificial commit should be used to evade the same-SHA rejection. The rollout must be a genuine reviewed change with green CI, owner authorization and a fresh final merge commit.

## Governance limits

Issue #448, OWNER-DEC-DEPLOY-PATH-01, mandates owner-triggered GitHub Actions Deploy workflow as the only ordinary deployment path, with a valid unique SHA-bound OWNER-AUTH-DEPLOY comment. It expressly forbids AI assistants from initiating Deploy. Do not use a direct Render Dashboard deployment or an assistant-triggered workflow to get around this restriction.

HARD_STOP, STOP_340, C02, SC_07 and GOV_BREACH_01 remain unresolved; this runbook does not close or override any of them. Any outstanding higher-priority authorization conflict must be reconciled prior to execution.

Production and its settings, database, secrets and deployment must not be touched.

## Phase 1: review and merge

1. Review the actual diff, especially the invalid-URL negative regression test.
2. Wait for CI (SQLite and PostgreSQL), Security Audit, Quality and Backup checks to pass on the PR HEAD.
3. Obtain and verify owner merge authorization bound to the exact PR HEAD SHA.
4. Repository owner merges only when all mandatory checks are green.
5. Obtain the actual 40-character main merge SHA (different from PR HEAD after squash merging).
6. Wait for required CI checks on the final main SHA to finish successfully.

## Phase 2: controlled staging deployment (owner-operated only)

Prerequisites: confirm Redis Internal URL is saved correctly in the Render Environment of vorneq-staging only, without displaying the secret; ensure VORNEQ_ENV=staging, and diagnostic flag remains false. The Redis Key Value is vorneq-staging-redis in Oregon. No synthetic account or diagnostic Identity is needed for this step.

Owner posts one unique unedited comment to Issue #448 with the exact line:

    OWNER-AUTH-DEPLOY <UNIQUE-ID> staging @ <FINAL-40-CHAR-MAIN-SHA>

Owner opens GitHub Actions > Deploy > Run workflow, selects main, staging, and the exact final main SHA, then personally starts the run. AI assistants do not dispatch this workflow. If deploy-preflight rejects anything, STOP; do not substitute a direct Render deployment.

Record GitHub run ID and Render deploy ID. Do not use this staging-only permission for production.

## Phase 3: read-only post-release checks

1. Render shows the target service LIVE on the final main SHA.
2. GET https://vorneq-staging.onrender.com/health/ returns HTTP 200, database name vorneq_staging_db_9i8v, database/cache/storage OK, release matching that SHA.
3. On staging Render Shell execute the following read-only check without printing private values:

    python manage.py shell -c 'from django.conf import settings; from apps.platform_shell.diagnostics import _shared_redis_configured; u=getattr(settings,"REDIS_URL",None); b=settings.CACHES["default"]["BACKEND"]; print("STAGING_OK:",settings.VORNEQ_ENV=="staging"); print("REDIS_URL_PRESENT:",bool(u)); print("REDIS_SCHEME_VALID:",bool(u and u.startswith(("redis://","rediss://")))); print("REDISCACHE_ACTIVE:",b=="django.core.cache.backends.redis.RedisCache"); print("REDIS_GATE:",_shared_redis_configured())'

4. Require all five booleans TRUE, then perform a sanitized read-only Redis PING using the configured URL (do not print it).
5. Diagnostic endpoint must remain HTTP 404 while disabled.

A successful Redis connection alone is not evidence that Django uses RedisCache in the live application. Health cache=ok alone is also insufficient.

## Phase 4: separate positive-run authorization

The CAP_ACTOR_02 positive diagnostic run requires a synthetic Staging database subject, a diagnostic Identity, further Environment saves/restarts, S01-S11 tests and mandatory cleanup. These are NOT authorized by a normal Redis-enablement deployment. Update the SHA-bound Issue #448 Runbook and obtain the separately applicable authority before proceeding. Never create a diagnostic account in Production.

## Record template

BASE_SHA=682fb3639aa27ce4361b94e03497bdb49575bc1c
PR_HEAD_SHA=<observed>
MAIN_MERGE_SHA=<observed>
PR_CI=<observed>
MAIN_CI=<observed>
OWNER_AUTH_COMMENT=<url>
DEPLOY_WORKFLOW_RUN=<id>
RENDER_DEPLOY_ID=<id>
RENDER_DEPLOY_STATUS=<live/failed>
HEALTH_SHA=<observed>
REDISCACHE_ACTIVE=<true/false>
REDIS_PING=<pass/fail/not-tested>
DIAGNOSTIC_GATE_HTTP=<status>
PRODUCTION_CHANGED=NO
G4_RECONCILIATION=<pass/pending/deviation>
FINAL_RESULT=<pass/partial/fail/not-executed>

PROPOSAL != APPROVAL != EXECUTION_AUTHORIZATION != VERIFIED_EVIDENCE.
