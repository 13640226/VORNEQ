# VORNEQ — AI Core Staging Enablement V1

**Date:** 2026-11-13
**Base:** `468d210fb062c4bd2cf3169dd0be728c8a396c45`
**Status:** ISOLATED DEVELOPMENT / DEFAULT OFF / NO DEPLOY AUTHORIZATION

## Scope

Phase A public-only retrieval and Phase B OpenAI Responses are permitted in
**Staging only after separately recorded owner approval and explicit flags**.
Production remains prohibited; Phase C chat remains development-only.
No secrets, real API calls, deployment, or Render changes were made.

## Mandatory fail-closed runtime guards

- `VORNEQ_ENV=staging` and `DJANGO_DEBUG=false`.
- `VORNEQ_AI_STAGING_TRIAL_ENABLED=true`, `VORNEQ_AI_CORE_ENABLED=true`
  and `VORNEQ_AI_PHASE_B_ENABLED=true`.
- Authorized **exact 40-character commit SHA** must equal trusted
  `RENDER_GIT_COMMIT`.
- The trusted `RENDER_SERVICE_ID` must match the Staging service
  `srv-dbm7dvc9v7es7393g70g`.
- Owner authorization reference must have format
  `OWNER-AUTH-AI-STAGING-<APPROVED_ID>` and must be separately approved
  and documented. A string match is NOT itself proof of owner identity.
- Logged-in principal must be active, staff, superuser and on an explicit
  Django user-PK allowlist (up to five IDs).
- CSRF protection and strict JSON schema remain active.
- Provider requires a model matching the operator-approved exact model ID
  and a staging-scoped `OPENAI_API_KEY`, held only in protected secret storage.
- Model calls use `store=False`, `tools=[]`, max retries 0,
  timeout 10 seconds and maximum output 256 tokens.
- Public Article/Product/Library/Audio source-only retrieval, redaction and
  grounded citation checks are preserved. Private tenant, document and media
  sources remain outside the allowlist.

## Persistent quota and cost limitation

Migration `ai_core.0001_initial` creates a Staging AI daily reservation
ledger (`StagingAIBudgetDay`). Each call reserves an approved maximum allowance
**before** any provider call in a PostgreSQL transaction with row locking.
Daily requests are limited to 1–5, per-call reserved allowance to $0.001–$0.10,
and total reserved allowance to at most $0.25 per UTC day.
No automatic refund on errors, which could still incur provider charges.
Database outage or missing migration means no provider call.

**Important:** These are reserved cost allowances, NOT measured API charges.
Actual model billing may exceed estimates. Check current model pricing and
configure separate low spending budgets/alerts in the OpenAI project. A
provider-side budget may itself be a *soft* rather than a hard cap.
Inspect Usage and Logs after any future permitted live test.

## Example settings for a FUTURE approved Staging trial (DO NOT APPLY YET)

```text
VORNEQ_ENV=staging
DJANGO_DEBUG=false
VORNEQ_AI_STAGING_TRIAL_ENABLED=true
VORNEQ_AI_CORE_ENABLED=true
VORNEQ_AI_PHASE_B_ENABLED=true
VORNEQ_AI_PHASE_C_ENABLED=false

VORNEQ_AI_STAGING_OWNER_AUTH=OWNER-AUTH-AI-STAGING-<VERIFIED_OWNER_DECISION>
VORNEQ_AI_STAGING_AUTHORIZED_SHA=<EXACT_APPROVED_40_CHARACTER_SHA>
VORNEQ_AI_STAGING_ALLOWED_USER_IDS=<VERIFIED_DJANGO_OWNER_USER_PK>
VORNEQ_AI_PHASE_B_MODEL=<EXACT_APPROVED_PRICED_MODEL>
VORNEQ_AI_STAGING_APPROVED_MODEL=<SAME_MODEL>
OPENAI_API_KEY=<STAGING_PROJECT_SECRET_ONLY>
VORNEQ_AI_STAGING_DAILY_CAP_MICROUSD=100000
VORNEQ_AI_STAGING_RESERVE_MICROUSD=50000
VORNEQ_AI_STAGING_MAX_DAILY_REQUESTS=2
```

The example quota is two $0.05 **reservations** ($0.10/day), not a promise
or measurement of $0.10 charged. `RENDER_GIT_COMMIT` and
`RENDER_SERVICE_ID` must be provided by Render, never forged manually.

## Separate future operational decisions

1. Code review, commit and CI of this independent feature branch.
2. Separately approve Staging-only migration `ai_core.0001_initial` after
   read-only DB identity check. **Never run it on Production implicitly.**
3. Deploy new code with all Staging AI flags OFF, through the owner's
   authorized deploy procedure, without enabling AI or running migrations.
4. Independently approve Staging-only env/secrets change, specific owner
   principal, exact SHA, one priced model and minimal budget.
5. Execute only one owner-controlled live, public-source test; examine
   logs, local DB quota ledger, project Usage and cost. Abort on uncertainty.
6. Keep Production AI NO_GO unless separately reviewed and authorized.

## Tests (offline and isolated)

- 26/26 new Staging policy/budget/API tests: PASS on SQLite.
- 96/96 full AI regression: PASS on SQLite with external test-only
  staticfiles settings.
- 27/27 new tests: PASS on isolated PostgreSQL 16.
- 4-worker PostgreSQL race: exactly two accepted, two denied.
- No real key used; no OpenAI external egress performed.

```text
STAGING_RUNTIME_ENABLED=NO
STAGING_RENDER_ENV_MODIFIED=NO
REAL_PROVIDER_CALLS=0
PRODUCTION_AI_ENABLED=NO
DEPLOY_OR_MERGE_EXECUTED=NO
```
