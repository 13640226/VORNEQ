# CI V2 isolated correction review — evidence ledger

Base candidate: PR #487 head a1c50126e9769016b34fb67405ff34bbb58cd750.
Contract: PR #489 (documentary V2.0; remains DRAFT).
Scope: source-only changes; no CI runs, database connections, tests, merges, deploys or production access.

## Changes
- Removed the unsupported RUNNER_ENVIRONMENT=github-hosted equality assertion from backup/restore and quality workflows; this variable is not a trustworthy attestation of hosted runner identity.
- Preserved local-only database URL and database-name preflight checks. These checks are defense-in-depth, NOT proof of network isolation.

## Outstanding security blockers
- CI-01 OPEN: privileged apt installation and untrusted dependency execution still share a runner; splitting steps is not privilege isolation. Requires separately designed unprivileged job/container boundary and independent supply-chain review.
- CI-02 PARTIAL: artifact egress endpoints remain a proposed allowlist; no runtime proof of network enforcement or upload success.
- CI-03 OPEN: local URL and SQL identity checks do not exclude indirect access to production. Requires independently verified disposable network, secret absence and authorized runtime evidence.
- Github check runs are NOT evidence for this PR unless observed against exact HEAD SHA; [skip ci] deliberately suppresses runs.
- Owner-controlled reviewer is not independent (SC_07 OPEN_CRITICAL).

## Static acceptance
AC-CI2-01..10: 0/10 runtime verified. No security approval. No merge/deploy.
STOP_340 ACTIVE; HARD_STOP ACTIVE; FINAL_STATE SAFE_HOLD / NO_GO.
