# VORNEQ — C02 consolidated security gap register

**Pinned commit:** `5446c9176e876d9a7a477b8203500a0e1d8334b1`  
**Status:** OPEN; documentary classification only. A risk family is not necessarily one independently proven vulnerability.

| ID | Family | Source pointers | Status | Closure evidence needed |
|---|---|---|---|---|
| SG-01 | Database identity / guard | `scripts/db_target_guard.py:103-120,150-168` | OPEN_CRITICAL | Explicit PRODUCTION/NON_PRODUCTION/UNKNOWN with UNKNOWN -> DENY; independent validation |
| SG-02 | Destructive operations | `scripts/dr_staging_rehearsal.py:101-137,293-320`; `apps/core/management/commands/seed_staging_data.py:68-71` | OPEN_CRITICAL | Proven non-production target binding and controlled destructive paths |
| SG-03 | Migration/deploy enforcement | `.github/workflows/migrate-production.yml:88`; `config/settings_render.py:14-24` | OPEN_CRITICAL | Independently verified mandatory pre-migration identity enforcement |
| SG-04 | ORM hooks / audit integrity | `marketplace/admin.py:280-343`; `marketplace/models.py:230-271` | OPEN | Review of bulk update invariants and audit trail |
| SG-05 | Authorization / private content | `library/views.py:43-51,342-486`; `marketplace/delivery.py:12-42`; `apps/verification/services/verification.py:62-66` | OPEN | Policy decision, object-level access review, independent verification |
| SG-06 | Indirect writes, cascade, signals | `apps/evidence/signals.py`; `apps/media/vector_index.py`; `apps/documents/services.py` | OPEN | Call graph and failure-semantics reconciliation |
| SG-07 | Runtime/independent evidence | C02, SC-07, historical evidence manifests | OPEN_CRITICAL | Independent reviewer and live read-only identity proof under separate authorization |

## Evidence discipline
E1 VERIFIED_SOURCE: pinned source retrieved and SHA verified.  
E2 VERIFIED_BATCH_REPORT: report contains directly attributable batch evidence.  
E3 HISTORICAL_REPORTED: prior assertion not independently rechecked.  
E4 RUNTIME_UNVERIFIED: live binding/behavior not established.  
E5 EVIDENCE_INCOMPLETE: absent or unreconciled historical proof.

## Non-closure
These families consolidate overlapping findings; deduplication is not remediation. No issue or gate is closed by this document. No production release, deploy, migration or database write is authorized.

```text
STOP_340 = ACTIVE
C02 = OPEN_CRITICAL
SC_07 = OPEN_CRITICAL
R01 = OPEN_CRITICAL
R02 = OPEN_CRITICAL
FINAL_STATE = SAFE_HOLD / NO_GO
```
