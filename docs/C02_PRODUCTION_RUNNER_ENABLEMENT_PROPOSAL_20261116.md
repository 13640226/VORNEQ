# C02 — Proposed conditional Production Runner activation (2026-11-16)

**Status:** DRAFT PR / NOT AN EXECUTION RELEASE. **C02 OPEN_CRITICAL; STOP_340 authority unresolved; MIGRATION_GO=NO.**

## Exact scope

- Service: `srv-dadn07eq1p3s73eccau0`
- PostgreSQL: `dpg-dagru1h42hec73eqr960-a`, Django `default` / `vorneq_production_db`
- Target migrations, in order: `ai_core.0001_initial`, `ai_core.0002_aichatrequestguard`
- Baseline GitHub main / Render live SHA at review: `37b2ce05ae59f984fd9181aa25395d098d24879f`
- This change only proposes enabling the Stage C Production code path and forbids non-committing Production rehearsals. The existing SHA, owner-authorization, backup-reference, internal URL, database name/user, primary, transaction/session, locking, exact-plan and pre-/post-commit checks remain.

## No implied authorization

**Creating, passing CI, merging or deploying this PR does not grant authority to run a Production migration.** The previous conditional one-use release for `6cd03395...` is not reusable on the new SHA. A new scoped authority decision and SHA-bound release are mandatory.

Before any Production run, explicitly determine the STOP_340 authority/precedence issue and preserve unrelated holds. Obtain fresh, verified backup restore and endpoint evidence, confirm the exact future live SHA and only intended migrations, complete official CI/security evaluation and a production-specific failure-path review.

The runner's `VORNEQ_C02_BACKUP_EVIDENCE` input is a **reference syntax check**, not independent attestation of backup freshness or recoverability. It MUST be verified outside this runner immediately before any write. Do not populate it with fictitious values. Runtime Internal URL matching is operational evidence, not independent PostgreSQL backend cryptographic attestation.

If any check fails, do not use unguarded `manage.py migrate`, change the target, bypass locks, or retry blindly. No paid AI, unrelated databases, Render config, secrets or deployment are authorized by this proposal.

## Tests

- Local Python 3.12/Django focused guard tests: 6 PASS.
- Production run is not performed by this change; full official CI is required on the PR commit.
