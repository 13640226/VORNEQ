# VORNEQ — CI Security Static Review / Remediation Gate V1

**Date:** 2026-11-03  
**Scope:** DOCUMENTARY_ONLY / STATIC_READ_ONLY_EVIDENCE  
**Related PR:** #503  
**Status:** DRAFT / CORRECTION_REQUIRED / INDEPENDENT_REVIEW_PENDING  
**Runtime validation:** NOT_PERFORMED

## Evidence boundary

Source files were read from the PR #503 head branch, without running any code, tests, workflow, SQL, migration or deployment. This is a bounded source inspection, **not** an independent runtime security acceptance. GitHub branch protection, organization settings, secrets availability, full transitive dependencies, and all indirect scripts were not exhaustively validated.

| Dimension | Finding | Decision |
|---|---|---|
| Static source review | Three workflow files, backup script and two requirements files inspected | `STATIC_SOURCE_REVIEW = COMPLETED (LIMITED_SCOPE)` |
| Secrets | No direct `secrets.*` reference in the three inspected workflows; `permissions: contents: read` declared | `SECRETS_DIRECT_REFERENCE = NOT_OBSERVED`; secrets exposure beyond inspected files NOT_VERIFIED |
| Database | Localhost PostgreSQL URLs and service declarations; `postgres:16` image; port 5432 published on runner | `DATABASE_ISOLATION = PARTIAL / NOT_VERIFIED` |
| Network | `apt-get`, `pip install`, action retrieval; no proven egress allowlist in inspected files | `NETWORK_EGRESS = NOT_RESTRICTED_BY_REVIEWED_FILES` |
| Code execution | `pip install`, Django commands, tests, shell backup/restore, `pg_restore --clean` | `INDIRECT_CODE_EXECUTION = PRESENT` |
| Supply chain | `actions/checkout@v4`, `actions/setup-python@v5`, `postgres:16` not digest/SHA pinned | `SUPPLY_CHAIN_PINNING = INCOMPLETE` |

## Inspected source paths

- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`
- `.github/workflows/backup-restore.yml`
- `scripts/postgres_backup.sh`
- `requirements.txt`
- `requirements-security.txt`

## Critical details

1. `ci.yml` has `test` matrix for Python 3.11/3.12 and a separate `test-postgres` matrix, including `python manage.py migrate --noinput` against a locally declared PostgreSQL service. Do not infer a production migration from this source alone; do not claim endpoint isolation is runtime-proven.
2. `security.yml` installs `requirements-security.txt` before running `pip_audit`; dependency installation is an executable supply-chain boundary.
3. `backup-restore.yml` supplies separate localhost source/restore URLs and invokes `scripts/postgres_backup.sh`. The script requires `--confirm-restore` and `RESTORE_DATABASE_URL`, but does not independently attest the target identity before `pg_restore --clean --if-exists`.
4. No effective runner egress deny-by-default policy or digest pinning was proven by these files.
5. PR #503's four `Expected` checks are plausibly associated with commits containing `[skip ci]`; the complete trigger/check-run cause is not independently established. Never disable required checks to work around this.

## Correction requirements (not implementation authorization)

- **CI-SEC-01:** Map every reachable workflow, reusable workflow, action, script and dependency-install path; verify least-privilege token and secret scope.
- **CI-SEC-02:** Define and independently validate a restricted network-egress path, including metadata endpoint denial.
- **CI-SEC-03:** Pin third-party actions and container images by immutable SHA/digest; define dependency integrity and bootstrap controls.
- **CI-SEC-04:** Prove ephemeral PostgreSQL isolation and fail-closed destination identity validation before destructive restore/migration paths.
- **CI-SEC-05:** Separate privileged orchestration from untrusted PR execution; no Docker socket exposure in untrusted jobs.
- **CI-SEC-06:** Define cleanup, unique resource naming, retention and independent verification evidence.
- **CI-SEC-07:** Require independent reviewer findings and explicit owner authorization bound to scope and commit before triggering CI.

## Decision / locks

```text
STATIC_SOURCE_REVIEW = COMPLETED (LIMITED_SCOPE)
SECRETS_DIRECT_REFERENCE = NOT_OBSERVED
DATABASE_ISOLATION = PARTIAL / NOT_VERIFIED
NETWORK_EGRESS = NOT_RESTRICTED_BY_REVIEWED_FILES
INDIRECT_CODE_EXECUTION = PRESENT
SUPPLY_CHAIN_PINNING = INCOMPLETE
CI_SECURITY_ACCEPTANCE = CORRECTION_REQUIRED
CI_GO = NO
MERGE_GO = NO
DEPLOY_GO = NO
STOP_340 = ACTIVE
HARD_STOP = ACTIVE
C02 = OPEN_CRITICAL
SC_07 = OPEN_CRITICAL
FINAL_STATE = SAFE_HOLD / NO_GO
```

This document neither authorizes nor performs workflow execution, CI-triggering commits, branch-protection changes, database access, migration, merge or deploy.
