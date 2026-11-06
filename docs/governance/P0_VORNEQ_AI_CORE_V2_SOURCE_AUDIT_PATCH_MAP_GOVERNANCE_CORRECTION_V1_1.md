# VORNEQ — AI Core V2 Source Audit & Patch Target Map: Governance Correction V1.1

DOCUMENT_ID: P0_VORNEQ_AI_CORE_V2_SOURCE_AUDIT_PATCH_MAP_GOVERNANCE_CORRECTION_V1_1  
DATE: 2026-11-06  
STATUS: DOCUMENTARY_CORRECTION / OWNER_ACCEPTANCE_PENDING  
SCOPE: DOCUMENTARY_ONLY; no new source access, tests, code changes, runtime, DB, Render or deploy authorization  
FINAL_STATE: SAFE_HOLD / NO_GO

## Authority and provenance
The OP-2 authorized reference is `fee18d38e769aa98e2dd3094bdac165345b4e441` (as reported by the receiving governance note). The integration-contract reference `397c8a1b4b7982ec13c78ac53109cc5454321a85` and the source-audit observation snapshot `4dbe9f1309e2b502b4ccc1fae363d55e389bf147` are **not established as authorized OP-2 replacements**. The latter was observed as the then-current main commit, not an approved OP-3 baseline. The owner must separately decide any scope or baseline extension.

## KB-NEW-01 through KB-NEW-05
- **KB-NEW-01 — Accepted:** commit divergence is real; observation is not authorization.
- **KB-NEW-02 — Attribution clarified:** selected GitHub files were read by a ChatGPT assistant; the recipient reviewer did not inspect them. Neither independent verification nor OP-3 authorization is established. Findings remain assistant-reported technical observations.
- **KB-NEW-03 — Accepted:** six additional inspected paths were outside the historical nine-file OP-3 scope: `apps/core/capabilities/read_artifact.py`, `apps/documents/search_adapter.py`, `apps/documents/search_service.py`, `apps/verification/services/verification.py`, `apps/evidence/models/provenance.py`, `config/urls.py`. This document does not authorize them.
- **KB-NEW-04 — Accepted:** governance baseline below is completed.
- **KB-NEW-05 — Explained:** 794 was the total number of Git tree paths observed for the snapshot; 379 was a historically reported Python-file count. They are different metrics and may involve different commits; no direct equivalence was verified.

## Technical correction — Django transaction.on_commit
A callback registered via `transaction.on_commit()` runs after a successful commit, and is discarded on rollback of the relevant transaction. It does **not** normally execute after rollback. The relevant risk in the observed `apps/verification/services/verification.py` path is **audit failure after the main transaction has committed**, with the audit exception caught and logged rather than necessarily propagated to the caller. This observation must not be generalized to an unobserved AI runtime. SEC-AUD-04 class compatibility remains to be established from authoritative contract text.

## Preserved proposed patch map (NOT implementation authority)
- Authorization and retrieval: `apps/core/capabilities/read_artifact.py`, `apps/documents/search_adapter.py`, `apps/documents/search_service.py`, `apps/documents/services.py`.
- Audit and verification: `apps/audit/services.py`, `apps/audit/models.py`, `apps/verification/services/verification.py`.
- Evidence and citation: `apps/evidence/models/provenance.py`, `apps/search/services.py`.
- Future API integration candidate: `config/urls.py`.

The map is a proposal, not an authorized file scope. Reuse existing Django services before extension. Do not infer model egress authorization from document read access. Citation existence and claim support validation remain separate requirements.

## Historical governance baseline — reported, not independently reverified
```text
STOP_340=ACTIVE
HARD_STOP=ACTIVE
C02=OPEN_CRITICAL
GOV_BREACH_01=OPEN
P_06=BLOCKED
HARD_STOP_ORIGINAL_SOURCE=NOT_RECOVERED
HARD_STOP_AUTHORITY_CHAIN=NOT_ESTABLISHED
KL_C1_03=CLARIFICATION_REQUIRED
SC_07_HISTORICAL_STATUS=OPEN_CRITICAL
SC_07_OWNER_WAIVER=PRESERVED
SC_07_WAIVER_AUTHORITY=AUTHORITY_REVIEW_PENDING
SC_07_SECURITY_CLOSURE=NOT_VERIFIED
AI_CORE_V2_ACCEPTANCE=TO_BE_VERIFIED
AI_CORE_V2_COMPATIBILITY=NOT_VERIFIED
VLIE_SOURCE_AUDIT_AUTHORIZATION=NONE
REVIEWER_NOMINATION=OUTSTANDING
IMPLEMENTATION_AUTHORIZATION=NONE
PRODUCTION_AI_ACTIVATION=NOT_AUTHORIZED
```

## Open owner decisions
1. Whether to authorize a new baseline commit or return to OP-2 `fee18d38...`.
2. Whether to expand the nine-file OP-3 scope to include any of the six additional paths.
3. Whether the authoritative AI Core V2 Security Contract V1.2 is available for contract alignment.
4. Whether to commission a separate documentary patch contract.

## Execution boundary
This record **does not** approve source access, implementation, tests, migration, merge, deploy, external model transfer, or production AI activation. Creating a documentary PR does not itself close governance gates. Any merge decision requires a separate check against the applicable HARD_STOP authority.

```text
SOURCE_AUDIT=TECHNICALLY_REPORTED
OP3_AUTHORIZATION=NOT_ESTABLISHED
PATCH_DESIGN=NOT_STARTED
CODE_CHANGES=NONE
PRODUCTION_AI_ACTIVATION=NOT_AUTHORIZED
FINAL_STATE=SAFE_HOLD / NO_GO
```
