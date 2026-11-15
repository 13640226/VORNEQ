# VORNEQ — AI Chat Recovery Durable Guard V2 (Staging only)

**Date:** 2026-11-15
**Base main SHA:** `98023e65967b7dcf79f250484f48266211b67480`
**Status:** ISOLATED_LOCAL_PATCH — NOT COMMITTED / NOT PUSHED / NOT DEPLOYED

## Purpose

The existing 24-hour Redis guard is not enough to prevent duplicate paid AI
requests if Redis loses its keys. V2 adds a durable primary-key guard to the
**Staging application's default PostgreSQL database** before any AI quota,
retrieval, paid provider invocation or prepaid ledger action.

The guard stores only a UUIDv4 request ID, actor PK, HMAC of the session key,
SHA-256 question/language fingerprint, running/finished status and timestamps.
It deliberately does **not** store user questions, answer bodies, session IDs,
provider credentials or OpenAI secrets in PostgreSQL.

Redis remains an ephemeral result cache (15 minutes) and an additional
24-hour convenience guard. A missing Redis guard cannot authorize re-execution
while the PostgreSQL row exists. A missing or unavailable PostgreSQL table
causes a fail-closed 503 before provider access.

## Files

- `apps/ai_core/models.py`: new `AIChatRequestGuard` model
- `apps/ai_core/migrations/0002_aichatrequestguard.py`: **SCHEMA ONLY**
- `apps/ai_core/request_recovery.py`: durable claim, read-only owner/session
  recovery and result finalization
- `apps/ai_core/tests/test_ai_request_recovery.py`: negative and concurrency
  tests

## Verified local, offline tests

- Django SQLite scoped regression: 57 tests, pass (one PostgreSQL-only skip)
- Django disposable PostgreSQL 16 scoped regression: 57 tests, pass
- Django disposable PostgreSQL 16 + isolated Redis 7.0.15: 57 tests, pass
- PostgreSQL eight-worker unique-claim test: exactly one "claimed"
- Redis wiped after a completed response: same UUID remains blocked by the
  durable PostgreSQL guard; no second model invocation
- Database write outage / Redis outage: fail closed; no provider invocation
- OpenAI requests: 0; only synthetic fake-provider responses
- No Render operations, no actual Staging/Production SQL, no Git commit/push/merge

## Release boundaries

1. **Before Staging deployment**, independently review the migration and verify
   the application database identity. Migration is NOT part of the normal
   `scripts/build_ai_staging.sh`. Require explicit migration authorization.
2. Inspect the migration plan on the exact approved SHA with a correctly
   identified Staging PostgreSQL target. Do not run against Production.
3. Deploy code to Staging only after CI and explicit SHA-bound permission.
   Keep `VORNEQ_AI_CHAT_RECOVERY_ENABLED=false` during deployment.
4. Apply `ai_core.0002_aichatrequestguard` to the **Staging default app DB**
   only under a separately authorized, controlled change window.
   Do not migrate the shared `ai_ledger` database.
5. Verify the new table, indexes, DB identity, and that failure to access the
   table blocks new AI calls (503). Validate the Runtime-to-Redis connection
   without OpenAI, using synthetic responses and authorized test actors.
6. Enable the Staging-only flag only after the above checks, written approval
   and isolation of budget/ledger; Production must remain disabled.
7. Production deploy, migration, flag enablement or live OpenAI cost tests
   are **not covered** by this runbook or the local patch.

## Outstanding safety and operations questions

- Rows must not be silently purged: deleting a guard makes its UUID reusable.
  Define a retention/deletion policy with a quantified replay horizon, or keep
  rows indefinitely with storage monitoring. Ensure backups include this table.
- A rollback of the code must **not** delete the durable guard table/rows.
- A catastrophic PostgreSQL rollback/restore that loses guard rows can still
  permit duplicate billing; this is not a globally exactly-once guarantee.
- Redis cache eviction still makes a response unavailable after refresh, but
  the same UUID remains unable to trigger another paid request.
- No unverified claim is made that the flag is currently disabled in Render;
  source code defaults it off. Verify actual environment settings before any
  Staging activation.
