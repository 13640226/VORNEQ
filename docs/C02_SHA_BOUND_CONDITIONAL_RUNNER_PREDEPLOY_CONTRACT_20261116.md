# C02 Stage C — SHA-bound conditional Production runner enablement (V1)

**Status: REVIEW CANDIDATE / NO-GO.** Implementation branch `feat/c02-sha-bound-conditional-runner-20261116` is based on `main` SHA `94115fa23afc9a945679e95e945386d7f5560e6e`. This document does not authorize Merge, Deploy, new Production secrets, PostgreSQL writes, a C02 one-use issuance, or migration execution. An exact final merged SHA must replace any earlier SHA once a *separate* deployment is approved.

## Scope

This minimal change enables a **conditional, SHA-pinned** opening of the existing guarded `c02_stage_c_runner`, while keeping the legacy `PRODUCTION_WRITE_ENABLED=False` constant false. It does **not** enable generic `manage.py migrate` or modify `.github/workflows/migrate-production.yml` (which still has its independent `ALLOW_PRODUCTION_TARGET=false` guard). No other Production SQL pathway is opened.

The new arm is explicitly evaluated by `production_write_gate_open(environ, expected_sha)`. It requires *all* of:

- `VORNEQ_C02_STAGE_C_WRITE_MODE=ONE_USE_OWNER_RELEASE` (exact value; no `true`, `yes` or `*`).
- `VORNEQ_C02_STAGE_C_ARMED_SHA=<exact deployed 40-character lowercase SHA>` (no wildcards).
- `VORNEQ_ENV=production`.
- `RENDER_SERVICE_ID=srv-dadn07eq1p3s73eccau0`.
- `RENDER_GIT_COMMIT` equal to the exact authorized SHA.

**No arm variables are created, saved, changed or deployed by this PR.** Both are absent by default. Overriding the old Python constant in isolation does not open the new arm. The public Production management command, `authorize()` and `run()` all require the new gate **before any SQL**. `run()` additionally rechecks the arm inside the transaction before the durable one-use receipt and just before commit. An arm removed at either point fails closed; a receipt already spent stays spent after rollback, so retry is denied.

## Existing independent protections preserved

- Independent HTTPS GitHub comment issuer verification: pinned GitHub repo 13640226/VORNEQ Issue #407, owner login and immutable numeric ID, exact SHA + service + DB identity + backup SHA/evidence + migration order + signed-in owner decision, no edits, fifteen-minute expiry, fresh refetch before receipt and precommit.
- Exact internal Render DB URL vs Django database settings and PG18 Primary login `vorneq_prod_app_rot_20261116`, SQL role `vorneq_production_db_user`; same driver, backend PID, transaction ID, source SHA and lock rechecks.
- Exactly two forward migrations `ai_core.0001_initial`, `ai_core.0002_aichatrequestguard`; old state (0 tables/0 migration records) mandatory; atomic migration with schema/index/constraint/history proof and read-only post-commit verification.
- Durable, unique `audit_auditevent.event_id` receipt with `ON CONFLICT DO NOTHING` to enforce exactly one **attempt**, not one successful retry.
- AI Production feature flags disabled during migration and separate C02 governance decision. No migration from GitHub-hosted runners; Render private One-Off Job is the future controlled transport.
- Existing `apply_ai_core_guarded --apply` remains hard-stopped; no uncontrolled migration path added.

## Security limitations — still OPEN / NO-GO

1. Provider export bytes for the 2026-11-16 11:37Z snapshot and isolated PG18 restore were previously verified, but **point-of-use freshness and independently fetched backup provenance are not enforced in this Runner**. The existing owner comment checks a hash and evidence string; those are not independent proof of a new Render export. Require a separate fresh evidence decision/implementation before executing.
2. Source identity is attributed by Render control plane + private URL HMAC + same-session checks. A cryptographic binding of PostgreSQL backend to Render resource ID is not available. The owner must explicitly accept this residual risk inside the 15-minute release for the exact SHA and database.
3. A GitHub read token is installed in Render; owner-provided screenshot showed `GITHUB_AUTH=PASS`, `ISSUE_READ=PASS`. Do not log or copy token; scoping to only `Issues: Read` should be separately verified from GitHub permissions.
4. Global STOP_340 was owner-retired and Issue #340 closed, but C02 remains `OPEN_CRITICAL`. Do not use blanket STOP retirement as a production migration authorization.
5. A future arm configuration/Deploy must have a **separate explicit owner permission**. A merged code change does nothing by itself.
6. No real `C02_OWNER_MIGRATION_RELEASE_V1` comment has been issued for a future *deployed* SHA. Issuance is time sensitive and must occur immediately before the approved execution, following a fresh DB/backup SHA preflight.
7. Failing loss-of-acknowledgment or GitHub API access remains fail-closed. Do not issue a second release as an automatic retry.

## Acceptance tests for this PR

- Production arm absent, malformed mode, wildcard, incorrect SHA, wrong service, wrong Render commit, wrong environment must all deny **before SQL** and before owner-network fetch.
- Command `--target production` without `--commit` must deny before SQL even when armed.
- With a synthetic exact arm, all existing identity, unauthorized GitHub comment, backup and migration-scope negative tests must still deny.
- Local isolated PostgreSQL tests must prove revocation **before** durable receipt causes no DB schema changes and no receipt; revocation **after** receipt but before commit rolls back DDL yet leaves the receipt consumed and blocks retries.
- Full CI matrix SQLite/PostgreSQL on Python 3.11/3.12, Security Audit, and Global Quality must pass on the exact PR head.

## Authorization boundary

```
SHA_BOUND_CONDITIONAL_RUNNER_PATCH = PROPOSED / BRANCH_ONLY
PRODUCTION_ARM_VARIABLES_INSTALLED = NO_ACTION_TAKEN
MERGE = NOT_AUTHORIZED_BY_THIS_IMPLEMENTATION
DEPLOY = NOT_AUTHORIZED
DATABASE_WRITE / MIGRATION = NOT_AUTHORIZED
STOP_340_GLOBAL_FREEZE = RETIRED
C02 = OPEN_CRITICAL
MIGRATION_GO = NO
PAID_AI_PRODUCTION_GO = NO
```
