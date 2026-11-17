# Persistent Conversation V1 — Hosted Recovery Hardening

Date: 2026-11-17

Baseline: `6170bc46b9bd798b9828ebde14847f7230d93aaf`
Branch: `feat/ai-persistent-conversation-v1`

## Issue

When `VORNEQ_AI_CONVERSATIONS_ENABLED=true`, the message endpoint previously
allowed its `request_recovery.enabled() == false` fallback. In a hosted
environment, that could send a billable model request without the durable
idempotency request ID and claim.

## Change

- For `VORNEQ_ENV=staging` or `production`, sending a message now fails
  closed with HTTP 503 `recovery_unavailable` when request recovery is
  disabled. The check occurs before retrieval, ledger and provider work.
- A regression test asserts no provider/retriever calls and no conversation
  messages or request guards are written in this configuration.
- The existing development/offline fake-provider path remains available.
- The request UUID validation and duplicate-claim controls remain unchanged.

## Scope and release gates

Only the isolated development branch is modified. No existing production
feature flag, production/staging database, deploy or migration is changed.
The full test suite, GitHub CI, migration authorization and any subsequent
merge/deploy decisions remain separate gates.

## Known limits

This is a narrow fail-closed fix and does not solve provider/DB distributed
atomicity or the 15-minute cache-recovery window described in the remediation
report. Production still requires the C02 runner extension and a separate
migration approval.
