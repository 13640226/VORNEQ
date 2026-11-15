# VORNEQ — Production Paid AI Chat Guard Preparation V1

**Date:** 2026-11-15
**Base release SHA:** `3a1ca4ef4636d07e7257e96c08458b0cde57657e`
**Status:** CODE_PREPARATION_ONLY / SAFE_HOLD / NO_PRODUCTION_ACTIVATION

## Purpose

Make paid Production AI Chat opt in to the same **durable, per-request
PostgreSQL idempotency guard** previously verified in Staging. A missing
guard table, inaccessible DB or Redis outage must stop a new paid model call.
Do not treat a successful code commit or CI run as a release authorization.

## Changes in this patch

- New `VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED` setting: **false by
  default** and valid only when `VORNEQ_ENV=production`. It cannot inherit
  the independently enabled Staging recovery flag.
- Production `production_enabled()` additionally requires the explicit
  Production durable-recovery opt in. Existing exact SHA, service identity,
  owner reference, active prepaid ledger, approved model and emergency-stop
  requirements remain in place.
- `request_recovery.enabled()` supports an explicit Production opt in and
  preserves the existing Staging flag. All paid request UUID claims still
  commit to `AIChatRequestGuard` **before retrieval, budget reservation and
  model egress**.
- Production and Staging Redis cache keys are segregated. Durable PostgreSQL
  UUID uniqueness remains the primary replay guard; cache is not authoritative.
- `request-status/` applies the **Production actor policy** in Production,
  rather than the Staging-specific allowlist.
- Offline synthetic tests exercise fail-closed behavior, request UUIDs,
  replay, Redis eviction, actor/session isolation, and pre-provider DB outage.
  Existing Production prepaid-ledger tests are adapted to the required guard.

## Critical deployment prerequisite: Production schema

The repository already contains `ai_core.0002_aichatrequestguard`, adding
`ai_core_aichatrequestguard` and `ai_chat_guard_created_idx` in the
**application default DB**. It was applied and runtime tested in Staging.
**It is not confirmed to be applied in Production.** Neither the Production
build script nor this patch performs any migration.

Before ever enabling Production paid AI, an authorized operator must:
1. Independently verify exact Production Render service, deployed SHA,
   database ID `dpg-dagru1h42hec73eqr960-a` and DB name
   `vorneq_production_db`, plus database role and read-only transaction
   identity. Do not expose database credentials.
2. Verify a fresh Production backup and a restore rehearsal to a separate,
   disposable PostgreSQL database. Protect Production data and logs.
3. Resolve the open C02 runtime-identity, isolation, change-control and
   independent security-review requirements (Issue #407).
4. Inspect `showmigrations`, `migration_preflight`, the **exact target**
   `ai_core.0002_aichatrequestguard --plan`, and SQL. Other pending
   migrations must not be executed by an unrestricted `migrate`.
5. Only under a **separate, one-use, SHA-bound Production schema
   authorization** apply the one migration, then independently verify
   the table, index, recorder row and post-change health.
6. Confirm real shared Redis and its failure semantics, the separate shared
   prepaid ledger DB identity, remaining allowance, emergency-stop readiness
   and both runtime/model price settings. An internal ledger estimate is not
   the OpenAI account balance or invoice.

## Production activation is a second, independent decision

After the above gates, require explicit owner authorization for the **exact
live SHA**, approved model (currently tested in Staging: `gpt-5-mini`),
one specific Production user ID allowlist and conservative prepaid ledger
cap. Prefer `VORNEQ_AI_PRODUCTION_ACTOR_POLICY=allowlist`; do **not** set
`authenticated` or allow general paid traffic during the pilot.

The operator would separately review and set (never from a code merge):

- `VORNEQ_AI_CHAT_RECOVERY_PRODUCTION_ENABLED=true`
- `VORNEQ_GLOBAL_AI_PRODUCTION_ENABLED=true`
- `VORNEQ_AI_PRODUCTION_AUTHORIZED_SHA=<exact LIVE SHA>`
- `VORNEQ_AI_PRODUCTION_OWNER_AUTH=<fresh owner authorization reference>`
- `VORNEQ_AI_PRODUCTION_APPROVED_MODEL=<approved model>`
- `VORNEQ_AI_PRODUCTION_ALLOWED_USER_IDS=<approved principal only>`
- The existing protected `OPENAI_API_KEY` and shared ledger configuration
  must be verified by **presence and trusted identity, never printed**.

A failed HTTP/DB/Redis preflight must stop the pilot. Carry out one limited
authenticated HTTP+CSRF model call with verified budget reservation,
settlement, response citations and same-UUID replay; then independent mobile
UI testing, rate limits, incident response and operator review. No automatic
paid retries after timeout or incomplete response. Retain the emergency stop.

## Remaining risks and release limits

- Durability is only as strong as the application's PostgreSQL history.
  Restoring an older snapshot can lose previously recorded request IDs and
  permit duplicate billing. Do not promise globally exactly-once spending.
- Response bodies live in Redis briefly; after expiry, previously used UUIDs
  must **not** trigger a replacement paid model call automatically.
- Every Production error and billing trace should avoid leaking secrets,
  question contents, user identities or raw provider responses.
- **C02 = OPEN_CRITICAL**, and PR merge/deploy authorization remains
  independent. This patch **does not** authorize any Production migration,
  API-call spending, environment update, AI launch or new deploy.

```
PRODUCTION_AI_CODE_GUARD_PREPARED = TRUE
PRODUCTION_RECOVERY_FLAG_DEFAULT = FALSE
PRODUCTION_SCHEMA_VERIFIED = NO
PRODUCTION_AI_PAID_ACTIVATION = NO_GO
PRODUCTION_MIGRATION = NOT_AUTHORIZED
```
