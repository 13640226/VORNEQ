# VORNEQ — PR #405 — Consolidated Static Audit Register (SLV-001–026)

**Recorded:** 2026-10-28 UTC  
**Scope:** documentary-only; no code change, migration, database connection, workflow dispatch, merge, or deployment.  
**Repository:** 13640226/VORNEQ  
**Branch:** new/documentary-audit-298  
**PR:** #405 (no merge authorization)  
**Pinned source commit:** `5446c9176e876d9a7a477b8203500a0e1d8334b1`  
**Pinned Git tree:** `5a930ae62231b36eed85b32855076a4e9f8b7122`

## Evidence boundary

This document is a **consolidation of reported prior audit results**, not a fresh repository-wide verification. SLV-001–022 historical details are not reproduced in full here; consult their original batch records before relying on individual conclusions. SHA verification is **not** a security PASS. No live database identity or runtime behavior was verified. The current documentary ledger reports **123 distinct source files SHA-verified through Batch 025**; that count is inherited from sequential batch records and is not independently reconstructed here from a complete 123-file manifest.

| Batch | State | Source evidence / conclusion |
| --- | --- | --- |
| SLV-001–022 | Reported completed in prior records | Historical static audit; original individual evidence registers remain authoritative. |
| SLV-023 | Completed, 5/5 SHA | `benchmark_search.py`, benchmark test, `quality/verify.mjs`, `quality/lighthouse.mjs`, `quality/contract.mjs`. Benchmark query counting does not enforce DB read-only; quality product-threshold failures may be report-only. Cumulative 113 unique. |
| SLV-024 | Completed, 5/5 SHA | `apps/search/services.py`, `views.py`, `narrow_window.py`, `narrow_window_poc.py`, `audit_search_index.py`. No direct DB writer identified in audited search paths; `audit_search_index` uses `SET TRANSACTION READ ONLY` inside EXPLAIN transaction, but writes local JSON/Markdown reports and lacks target-identity guard. Cumulative 118 unique. |
| SLV-025 | Completed, 5/5 SHA | Staging search-index workflow plus four search test files. Workflow validates expected 20 EXPLAIN results and rejects rows with errors; it lacks independent target identity guard. Tests cover pagination and selected public-content filtering, not full no-write or DB-target assurance. Cumulative 123 unique. |
| SLV-026 | **PROPOSED / NOT AUTHORIZED / NOT STARTED** | Manifest pending verification; no files selected, no SHA/content audit claimed. |

## Selected verified evidence — latest batches

### SLV-023

- `apps/core/management/commands/benchmark_search.py` — `1ba57ec5341d4bce3ce22db77c95a9cb76f0f651`: query counting does not enforce read-only.
- `apps/core/tests/test_benchmark_search_command.py` — `e2afccedb8b7fbc15abbff78eeaf2920d862b2a5`: mock-based command contract, not DB write prohibition.
- `quality/verify.mjs` — `44de07ee891eea6c9b7e4730ce3c1a1507444830`: browser/HTTP checks and filesystem report writes; distinguish report-only product failures from infrastructure failure.
- `quality/lighthouse.mjs` — `75d9471ee8cb55d5552c83ced9a7c9261af456e8`: report-only product thresholds.
- `quality/contract.mjs` — `7291aaa2a1768ad5abe84c7961751bbb6438b021`: configurable QUALITY_BASE_URL; no standalone production-target deny.

### SLV-024

- `apps/search/services.py` — `e0321f75f04bf2a00f339559c3aa3cd73d7a3553`: adapter querysets and UnifiedSearch; direct writer not identified.
- `apps/search/views.py` — `778f2893b94050c4d679f87f7a10ac54fd12486e`: GET-only search API; no direct DB writer identified.
- `apps/search/narrow_window.py` — `4d16125baf72ce7953e2a4b010c4e71e613d4e47`: SELECT-based CTE construction and raw-query retrieval; runtime unverified.
- `apps/search/narrow_window_poc.py` — `45f69b58024d68e2cddd69efa02d196ec3967fc7`: PoC scenarios; production activation unverified.
- `apps/search/management/commands/audit_search_index.py` — `0901baf78710b00946e82eb40d7866b679c16a8e`: lines 138–155 transaction read-only EXPLAIN; lines 39–40, 63–68, 271–272 filesystem output; no independent DB identity guard.

### SLV-025

- `.github/workflows/audit-search-index-staging.yml` — `862cc4218b47c2336a3e3a628fd672303deddabd`: lines 34–60 use named staging secret without independent DB identity verification; lines 62–81 validate 20 results and reject any EXPLAIN error.
- `apps/core/tests/test_search_index_audit.py` — `39f02e38c8f1c782e9a5817740d34f44d454f58b`: two tests for shared SQL builder and nonpositive limit; not transaction/identity tests.
- `apps/core/tests/test_search_window_count_production.py` — `24a3d67b8152323f092f5593e7e3e3db0e80c9d7`: lines 68–71 compare Article row counts only; do not establish no writes to all tables.
- `apps/core/tests/test_search_bounded_pagination.py` — `04faf5c1cbb575d33873a4e89aa573080d75ed95`: pagination/filter/tie-breaking test coverage.
- `config/tests/test_unified_search.py` — `7a737afdbba0019fe330e48397f0a7fa0346294c`: public filtering/API contract; lines 79–88 exclude unpublished Article in one scenario.

## Open security blockers and evidence grades

1. **HIGH / VERIFIED_SOURCE:** staging search-index workflow has no independent database-target guard; a secret *name* does not prove destination identity. **No actual production connection is alleged.**
2. **PARTIAL / VERIFIED_SOURCE:** benchmark search counts SQL queries but does not enforce transaction-level read-only.
3. **PARTIAL / VERIFIED_SOURCE:** search-index audit uses read-only transaction for EXPLAIN but writes local reports; successful completion of the workflow is not a blanket security approval.
4. **TEST_ONLY:** selected tests validate query equivalence, pagination and limited publication rules, but not global absence of database writes or all authorization boundaries.
5. **RUNTIME_UNKNOWN:** runtime DB binding and all actual deployment behavior remain unverified.
6. **PENDING:** independent security review and original historical evidence reconciliation.

## Governance — preserved without modification

```text
STOP_340 = ACTIVE
HARD_STOP = ACTIVE
UA_03 = OPEN_CRITICAL
SG_01 = OPEN_CRITICAL
SG_02 = OPEN_CRITICAL
SG_03 = OPEN_CRITICAL
SG_07 = OPEN_CRITICAL
C02 = OPEN_CRITICAL
SC_07 = OPEN_CRITICAL
R01 = OPEN_CRITICAL
R02 = OPEN_CRITICAL
RUNTIME_DB_IDENTITY = UNKNOWN
INDEPENDENT_SECURITY_REVIEW = PENDING
DATABASE_GO = NO
MIGRATION_GO = NO
DEPLOY_GO = NO
PR_405_MERGE_AUTHORIZATION = NO
PRODUCTION_RELEASE = BLOCKED
FINAL_STATE = SAFE_HOLD / NO_GO
```

**Registration authorization:** Owner approved writing this documentation report to `new/documentary-audit-298` only. No approval for modifying `main`, merging PR #405, running code or workflows, accessing secrets or databases, or deploying.

**Final documentary verdict:** `SLV-001–025 REPORTED_COMPLETE / 123 UNIQUE SHA-VERIFIED (LEDGER) / SLV-026 PROPOSED_NOT_STARTED / SAFE_HOLD / NO_GO`.
