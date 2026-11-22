# Production Image Studio — phase 1, closed-gate foundation

The Production web service currently runs the image code but **must not expose Image Studio or submit paid jobs**. Existing Staging-only policy rejects Production. This PR introduces independent Production-intent settings and a read-only readiness breakdown, without weakening that boundary.

## Flags (both default false)

- `VORNEQ_AI_IMAGE_PRODUCTION_ENABLED`
- `VORNEQ_AI_IMAGE_PRODUCTION_UI_ENABLED`

**Do not enable these in Render yet.** Even if both are true, `production_enabled()` remains false until a separate Production paid policy and independently authorized worker are implemented, reviewed and tested. No provider call, paid worker, migration or release is included.

## Required follow-up PRs before any activation

1. Independent Production SHA/deployment attestation and owner authorization, service/worker identity, allowlist, Emergency Stop and UI access controls.
2. Production-specific prepaid image Ledger account and strict per-request/daily limits, idempotency, reconciliation and durable private storage.
3. Production worker provisioning and owner grant, with fail-closed provider routing and no fallback to chat credentials.
4. End-to-end no-paid CI, concurrent reservation tests, authorization tests and security review; separately authorized Staging pilot, then Production deploy and activation.

Current `image_studio_allowed`, `enabled`, `paid_provider_enabled`, `paid_worker_enabled` remain Staging-only. This is intentional, not an environment-variable configuration bug.

## Phase 2 — independent release identity (still closed)

`VORNEQ_AI_IMAGE_PRODUCTION_AUTHORIZED_SHA`, `VORNEQ_AI_IMAGE_PRODUCTION_OWNER_AUTH` (pattern `OWNER-AUTH-AI-IMAGE-PRODUCTION-...`), and `VORNEQ_AI_IMAGE_PRODUCTION_ALLOWED_USER_IDS` (`1` only) are read-only identity inputs. `production_release_identity()` requires the exact Production Render service, SHA match and the successful owner-dispatched official Production GitHub deployment verified via `VORNEQ_AI_DEPLOY_READ_TOKEN`. All values default empty. They are **not** activation instructions. Production paid provider and worker remain unimplemented/closed regardless of configuration. No credentials should be committed.
