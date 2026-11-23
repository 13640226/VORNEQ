# Production Image Studio — owner-approved uncapped internal budget (design)

Owner approved removing **internal financial caps** for Production image generation on 2026-11-23. This is a policy requirement, **not** permission to execute a paid request or open a production gate.

## Required implementation

- A Production-only, owner-authorized `uncapped_internal_budget` mode for admin ID 1; default disabled and fail-closed. Staging behavior and chat Ledger remain unchanged.
- No fixed internal daily/monthly USD spend ceiling, daily request-count ceiling, or prepaid balance gate in this mode. Provider billing and external account limits still apply.
- Preserve an independent image Ledger: atomic per-request reservations, actual usage reconciliation, uncertainty tracking, deduplication, idempotency, and audit trails. Never treat `uncapped` as a fake infinite numeric balance.
- Retain provider authorization, owner-attested deployment SHA, separate worker identity, emergency stop, authenticated actor policy, concurrency/rate abuse protections, and provider-side limits. Do not remove those to satisfy the financial-cap request.
- Paid Production requests stay blocked until a separately tested Production provider/worker path and an explicit activation authorization exist.
- Add integration tests for unlimited spend without budget rejection, duplicate requests, concurrent accounting, failed provider calls, uncertain reconciliation, stop/rollback, and Staging/Production isolation.

## Current status

Design requirement recorded only. Production image provider, worker, and UI are still disabled; no migration, deploy, paid call, or activation is authorized by this document.
