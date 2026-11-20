# VORNEQ — ai_core.0004 Staging one-use migration release

Status: **PROPOSED / NO_GO until all operational release gates are verified.**

This runbook is **not** an owner grant. Generic `migrate-staging.yml`,
`scripts/db_target_guard.py`, C02 Production guards, and Production image
generation remain unchanged and blocked.

## Exactly scoped target

- Service: `srv-dbm7dvc9v7es7393g70g` (Render Staging).
- PostgreSQL resource: `dpg-dbm74m8u01pc738j8r1g-a`.
- Database: `vorneq_staging_db_9i8v`.
- Authenticated and execution DB role: `vorneq_staging_db_9i8v_user`.
- Target: **exactly** `ai_core.0004_image_generation_job_v1`.
- The new tables are `ai_core_aiimagedailyquota` and
  `ai_core_aiimagejob`, with expected image-job indexes.
- Runtime source SHA must be an exact *deployed* 40-hex SHA, not just a GitHub
  branch name. A PR merge changes this SHA; the release must be re-bound.
- All paid/image generation gates remain disabled during migration.
- Release register: https://github.com/13640226/VORNEQ/issues/664

## Evidence already obtained (historical, **not** evergreen authorization)

- Nov 19 staging backup: `2026-11-19T23_19Z.dir.tar.gz`,
  SHA-256 `1b668f86b75de0e5a7a481301fbd2926091c4fcff55ef7f8cd92e74f051c90e3`.
- Isolated PostgreSQL 18 restore succeeded; 78 public tables, 82 migration
  records, 352 indexes, `ai_core.0001`–`0003` applied, `0004` absent.
- Separate isolated migration rehearsal of `0004` succeeded on the preceding
  backup; live staging migration remains pending.
- R2 private read/write/delete check succeeded without any OpenAI call.
- Production deployment and database were not changed.

**Refresh backup and isolated restore evidence immediately before a live
release. A previously verified backup may be stale.** Confirm source database
identity, archive SHA, restore logs, and same-backup provenance. Check for
other migrations or schema drift after any deployment.

## Scoped human independent-reviewer waiver (owner direction, 2026-11-20)

For **PR #665** and the **Staging-only `ai_core.0004_image_generation_job_v1`** release path, the repository administrator has waived the requirement for a separate human code reviewer. This decision is recorded in [Issue #664](https://github.com/13640226/VORNEQ/issues/664). It is not a GitHub owner execution permit, does not override required GitHub status checks (including any failed `merge-authorization` context), and does not waive CI, Security Audit, runtime identity, a fresh backup and isolated restore, scoped C02 authorization, or the authenticated 30-minute owner comment. All Production, other migrations, Worker, and paid image calls are excluded.

## Release prerequisites — all required

1. The merged one-use runner PR #665 does **not** require a human independent reviewer for this scope. CI and Security Audit must be green, and any failed required GitHub status must be investigated rather than misrepresented as passing. Deploy the current merged SHA to **Staging only**. Do not activate the image feature.
2. Verify Render control-plane service/DB metadata against the live runtime. From Render
   runtime verify the same database, PostgreSQL role, hostname resource prefix,
   current SHA, writable primary, and *exactly one* pending migration.
   Hostname/name match is operational evidence, **not** cryptographic
   proof of the physical DB backend. The owner must explicitly accept this
   residual risk in the scoped owner comment.
3. Validate a **fresh** Staging backup and isolated restore. Record its exact
   SHA-256 and evidence reference in the owner release manifest.
4. Owner personally issues a **new, unedited, expiring GitHub comment** on
   Issue #664. The runner independently fetches and checks comment identity,
   author, timestamps, scope and backup evidence from GitHub HTTPS. No
   assistant-authored manifest, env string alone, or issue body is approval.
5. Confirm availability of the append-only `audit_auditevent` table and
   isolated one-use receipt rights. Its deterministic UUID is inserted using a
   *separate autocommit database connection*, so reuse is rejected even if
   the DDL transaction rolls back. An ambiguous attempt **must not be retried**.
6. Separate authenticated **owner execution authorization** explicitly scoped to Staging, the new deployed SHA,
   this one migration, the backup, and this release ID must be recorded before
   arming. Operational C02 governance still needs separate sign-off; this is not a human reviewer requirement.

## New GitHub owner comment format — template, not approval

Only the verified GitHub account owner may post the actual release. Supply
real, current values for `release_id`, `sha`, `backup_sha256`,
`backup_evidence`, `backup_exported_at`, `restore_verified_at` and
`expires_at` after all checks have passed. The backup export and its
isolated restore must be within two hours of execution.
The expiry must be no more than 30 minutes after the *comment creation*.

```text
STAGING_IMAGE_0004_OWNER_RELEASE_V1
{"decision":"AUTHORIZE_STAGING_AI_CORE_0004_IMAGE","release_id":"IMAGE0004-EXAMPLE-REPLACE","sha":"<EXACT_STAGING_DEPLOY_SHA_40_HEX>","service_id":"srv-dbm7dvc9v7es7393g70g","postgres_id":"dpg-dbm74m8u01pc738j8r1g-a","database":"vorneq_staging_db_9i8v","session_user":"vorneq_staging_db_9i8v_user","current_user":"vorneq_staging_db_9i8v_user","migrations":["ai_core.0004_image_generation_job_v1"],"backup_sha256":"<FRESH_BACKUP_SHA256_64_HEX>","backup_evidence":"<VERIFIED_RESTORE_ID>","backup_exported_at":"<UTC_YYYY-MM-DDTHH:MM:SSZ>","restore_verified_at":"<UTC_YYYY-MM-DDTHH:MM:SSZ>","expires_at":"<UTC_YYYY-MM-DDTHH:MM:SSZ>","risk_acceptance":"ACCEPT_STAGING_OPERATIONAL_IDENTITY_RESIDUAL_RISK"}
```

Do **not** post that placeholder as a release. The GitHub comment is fetched
and checked again before receipt consumption and before migration commit.

## Dedicated command (not automatically run by deploy)

The command starts in **read-only** mode. Execute it within positively
identified Render Staging (only after deploying the merged runner):

```bash
DJANGO_SETTINGS_MODULE=config.settings_render \
python manage.py migrate_ai_image_0004_staging_once --expected-sha "$RENDER_GIT_COMMIT"
```

For a live release, Render Staging must have all of these scoped controls
configured **after** the owner approval and identity/backup verification:

```text
VORNEQ_IMAGE_0004_WRITE_MODE=ONE_USE_OWNER_RELEASE
VORNEQ_IMAGE_0004_ARMED_SHA=<EXACT_STAGING_DEPLOY_SHA_40_HEX>
VORNEQ_IMAGE_0004_MIGRATION_AUTH=OWNER-AUTH-STAGING-AI-0004-<RELEASE_ID> @ <EXACT_STAGING_DEPLOY_SHA_40_HEX>
VORNEQ_IMAGE_0004_OWNER_COMMENT_ID=<NEW_UNEDITED_GITHUB_COMMENT_ID>
VORNEQ_IMAGE_0004_BACKUP_SHA256=<FRESH_BACKUP_SHA256_64_HEX>
VORNEQ_IMAGE_0004_BACKUP_EVIDENCE=<VERIFIED_RESTORE_ID>
VORNEQ_IMAGE_0004_GITHUB_READ_TOKEN=<SCOPED_READ_ONLY_TOKEN_FROM_RENDER_SECRET>
```

The separately owner-approved one-use run is then scoped to:

```bash
DJANGO_SETTINGS_MODULE=config.settings_render \
python manage.py migrate_ai_image_0004_staging_once \
  --expected-sha "$RENDER_GIT_COMMIT" \
  --release-id "<APPROVED_RELEASE_ID>" --commit
```

**Do not run the command above until an authenticated fresh owner comment,
C02 scoped exception, Render identity, backup evidence, exact plan, and CI
are all verified.** No human independent reviewer is required for this scoped Staging release. Do not use bare `manage.py migrate`.

After an approved run, verify `showmigrations ai_core`, inspect both new
tables and indexes, check the append-only receipt and Render logs, remove
temporary approval variables, and confirm that Production is unchanged.
The image feature and paid OpenAI remain **OFF**.

## Worker and Mock E2E are later, separately authorized phases

After confirmed migration, first test the *Mock* API → PostgreSQL job →
worker-once → R2 object → signed owner URL → cleanup on Staging, without
OpenAI calls. The existing `run_image_jobs --loop` command is designed for
a separate Background Worker, but its Render-service identity policy must
be updated and separately tested before provisioning or running a Worker.
Neither this one-use release nor the migration itself authorizes that
deployment or paid image calls.
