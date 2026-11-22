# Voice core foundation (PR 1)

Mock-only, default-off foundation for future Voice AI. It never calls a paid provider, never touches
the ledger and adds no migration or settings entries.

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
