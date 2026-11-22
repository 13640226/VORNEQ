# Voice core foundation (PR 1)

Mock-only, default-off foundation for future Voice AI. It never calls a paid provider, never touches
the ledger and adds no migration. Its five environment settings are wired into Django settings by PR #689; Voice remains default-off and production-blocked.

## Endpoints (`/api/ai/v1/`)
- `POST voice/sessions/` body `{"conversation_id": "<uuid>"}` (optional) → 201 `session_id`.
- `POST voice/sessions/<id>/events/` body `{"type":"text","text":"..."}` or `{"type":"audio_chunk","size":N}`.
- `POST voice/sessions/<id>/close/` → 200 once; unknown, expired, foreign or already closed → 404.

## Fail-closed gates (any failure answers 404 `unavailable`; unauthenticated 401)
`VORNEQ_ENV` must be `development` or `staging` (never `production`); `VORNEQ_AI_VOICE_ENABLED` must be
literally `True`; `VORNEQ_AI_VOICE_PROVIDER` must be `mock`; `VORNEQ_AI_VOICE_PAID_CALLS_ENABLED` must be off;
`VORNEQ_AI_VOICE_SESSION_TTL_SECONDS` an integer 30..3600 (default 300); `VORNEQ_AI_VOICE_ALLOWED_USER_IDS`
a non-empty comma-separated list of positive integers (max 50). Emergency Stop (`VORNEQ_AI_EMERGENCY_STOP`, any
value other than False/None) answers 503 and clears all live sessions.

## Behavior
One active session per user (429 with `Retry-After` and `retry_after_seconds`, computed under the store lock),
bounded store (100 sessions, 503 `capacity`), 50 events per session, body limit 16 KiB, text 2000 characters,
audio chunk size 1..65536 (size only, no audio is stored). Archived or trashed conversations are denied (409 on
create) and a session is released if its conversation is archived mid-session. The session record is frozen and
release is atomic under one lock.

## Not in PR 1
Shared Redis store (reserved namespace `ai_core:ai_core_voice:*`), any real provider, UI, Production enablement.
The store is process-local; with several workers the one-session-per-user rule applies per process.
## Controlled staging release after an out-of-band Render deploy

A Render `live` SHA is **not** a GitHub owner-authorized deployment record. The chat release guard (`VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=true`) verifies the official GitHub deployment and workflow evidence; a matching `VORNEQ_AI_STAGING_AUTHORIZED_SHA` alone does not grant access.

1. Prepare a real reviewed change on a new branch and merge it into `main` only after CI, Security Audit and required main checks pass. Never fabricate a deployment record or use an empty commit solely to evade the already-live guard.
2. Obtain the **new full 40-character main SHA**. The owner must post a new, unedited comment on Issue #448: `OWNER-AUTH-DEPLOY <unique-id> staging @ <full-sha>`. A comment for the previous SHA cannot authorize the new one.
3. **Only the owner** starts `.github/workflows/deploy.yml` using `workflow_dispatch` with `environment=staging` and `sha=<new-sha>`. The workflow enforces owner identity, required CI, unused authorization, correct Render hook, and that the SHA is not already live. Assistants must not dispatch this workflow.
4. Do not manually deploy the new SHA to Render before this official workflow. Wait for `deploy-preflight`, `deploy-staging`, and smoke verification to succeed, and verify `/health/` reports the new SHA.
5. Before enabling **paid chat** for admin 3, independently verify the Staging runtime: `trial_enabled()`, allowlist `3`, `ledger_enabled()`, `VORNEQ_AI_CHAT_STAGING_PREPAID_ONLY`, emergency stop, staging budget ceilings, model and provider authorization. No real paid call until those checks pass and the owner authorizes the bounded test.
6. Production requires a **separate** SHA-bound owner authorization, successful official staging deployment of that SHA, its own owner-triggered deploy workflow, ledger/backup checks, and admin-1-only actor policy. Staging authorization never grants Production access.

This runbook is documentation only. It does not enable paid chat, Voice paid calls, or modify runtime variables, deployments, or financial controls.
