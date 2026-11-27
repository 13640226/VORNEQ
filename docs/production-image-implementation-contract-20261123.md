# Production Image Studio — implementation contract (2026-11-23)

Status: **NOT IMPLEMENTED / NO-GO for paid Production**. This document is a staged engineering contract, not a release authorization.

## Existing verified code boundaries

- `image_generation.policy.production_enabled()` is hard-closed by `production_paid_policy_implemented=False` and `production_worker_authorized=False`.
- `image_generation.production_worker.process_production_image_job()` is a no-op.
- `image_generation.providers.OpenAIImageProvider` accepts Staging paid gates only.
- `ProductionImageUsage` exists in the ledger models but cannot alone guarantee safe claim, charge or settlement.
- Production preview is read-only; it does not submit image jobs.

## Required implementation sequence

1. **Production persistence & migration**: verify Production image schema, independently authorize any pending migration, ensure unique job request IDs and a durable claim/lease state. No migration in this PR.
2. **Independent Production ledger**: atomic, idempotent reservation intent before a provider call; one-time finalization; uncertainty recorded conservatively on ambiguous provider outcomes; no automatic retry after the request may have been sent. A budget-intent flag does not bypass provider billing limits or emergency stop.
3. **Provider adapter**: independent Production authorization, dedicated image API key, moderation, size/model allowlists, timeout and zero SDK retries. Do not inherit Staging or Chat grants.
4. **Worker**: dedicated Render worker service identity; PostgreSQL transactional claim with `select_for_update(skip_locked=True)`; recheck owner/actor/SHA/release/stop before any irreversible operation; write reservation intent durably before provider invocation; fail closed on storage, ledger or credential failure.
5. **Web UI and API**: authenticated Production submit/status/gallery endpoints with strict actor isolation, idempotent UUID requests and CSRF protections. No Production submission until provider and worker gates are ready.
6. **Operational controls**: dedicated private R2 bucket and short-lived SigV4 URLs, observability without secrets/prompts, manual reconciliation for uncertain charges, per-account external provider controls.
7. **Verification**: SQLite and PostgreSQL tests, concurrent claim/settle tests, permission and stop-race tests, CI + Security Audit, read-only preflight, separate owner authorization for migrations, Staging smoke, Production deployment, then one capped paid Production pilot with its own explicit authorization.

## Non-negotiable release checks

- No unverified `True` placeholders to open the Production paid gate.
- No real OpenAI call from CI or mock tests.
- No disabling of Emergency Stop, actor isolation or ledger accounting.
- An uncapped *internal* spending policy is not an unlimited OpenAI balance.
- PR #704 is test-only; merging it does not activate image generation.
