# Production AI Timeout Headroom — V1 (2026-11-17)

Scope: isolated branch + offline CI. No Render deployment, database migration,
budget mutation, paid model call, retry or AI feature enablement.

## Observed incident
Production POST /api/ai/v1/ask-global/ at 2026-11-17T22:04:27Z logged
Gunicorn WORKER TIMEOUT and HTTP 500 while inside the OpenAI Responses
request. A worker exited and was restarted. The SIGKILL message speculated
about OOM, but available memory metrics (~230 MB of 512 MB) do not prove it.
The worker timeout, not an OOM event, is directly supported by evidence.

Production AI ledger showed an UNCERTAIN reservation, unexpected_error,
and no observed token usage. The actual provider charge is unknown. Do not
refund, retry, delete a recovery guard, or reclassify that reservation without
independent evidence.

## Minimal changes
- Production provider timeout 30 -> 60 seconds.
- Production Gunicorn worker timeout 30 -> 100 seconds.
- Staging remains 60 / 100; development remains 15 / 30.
- No provider retries; max_retries=0.
- Keep 2048-token output limit, Ledger reserve/settle, request recovery,
  source citation validation, owner/SHA authorizations, and migration policy.

## Offline tests and release boundary
Tests verify environment-scoped timeout headroom, exact Production factory
timeout, single ledger wrapper, synthetic SDK timeout with one provider attempt,
one reserve, and one uncertain settlement. Existing Staging tests are updated
for the Production value. No test calls a real provider, Render database or
Redis. Run official GitHub Python 3.11/3.12 SQLite and PostgreSQL checks.

After successful CI, PR merge requires the normal owner gate. A new
Production deploy requires its own exact-SHA authorization in Issue #448
and owner-only manual Render deploy. Paid AI use needs separate owner SHA
authorization and cost/recovery review; C02/ai_core.0003 is not in scope.
