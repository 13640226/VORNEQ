# SEC-CI-01 — Supply-chain pinning static review (2026-11-03)

Status: **PARTIAL_CORRECTION / OPEN**. Scope: PR #505, documentary and source-only. No CI execution, merge, deployment, Docker pull, dependency install, or database connection.

## Verified action commit references

- `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` — GitHub commit existence checked.
- `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065` — GitHub commit existence checked.
- `actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020` — GitHub commit existence checked.
- `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` — GitHub commit existence checked; release v4.6.2 corresponds to this commit.

The above verifies commit existence, not source authenticity, full transitive dependency integrity, or runtime isolation.

## Remaining blockers

1. Both PostgreSQL services in `.github/workflows/ci.yml` and `.github/workflows/backup-restore.yml` still use mutable `postgres:16` tag. **Do not insert an invented SHA256 digest.** Select a platform-specific immutable digest from trusted registry metadata and verify image architecture and provenance independently before changing either workflow.
2. `requirements.txt` and `requirements-security.txt` have version pins but no complete hash-lock coverage; transitive dependency integrity is not independently verified.
3. `quality/package-lock.json` integrity, browser binary distribution and OS packages require separate review.
4. The inspected workflows do not prove a network-egress allowlist or safe execution of install scripts.
5. A complete inventory of other workflow files and indirect actions remains outstanding.

## Exit conditions

All reachable actions and images pinned and reviewed; complete dependency and bootstrap integrity evidence; independent reviewer confirms exact PR head and findings; owner authorizes a specifically scoped next step. No implied CI execution permission.

```text
SEC_CI_01 = PARTIAL_CORRECTION / OPEN
CI_GO = NO
MERGE_GO = NO
DEPLOY_GO = NO
STOP_340 = ACTIVE
HARD_STOP = ACTIVE
C02 = OPEN_CRITICAL
SC_07 = OPEN_CRITICAL
FINAL_STATE = SAFE_HOLD / NO_GO
```
