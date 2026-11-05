# VORNEQ — SG01-UA03 Expanded Python 298: Final Documentary Reconciliation

**Document ID:** SG01-UA03-EXPANDED-298-FINAL-RECONCILIATION  
**Directive:** P0_VORNEQ_SG01_UA03_EXPANDED_298_FINAL_EVIDENCE_RECONCILIATION_READONLY_V1  
**Date:** 2026-10-28  
**Classification:** DOCUMENTARY ONLY — COMPLETED WITH LIMITATIONS  
**Security verdict:** SAFE_HOLD / NO_GO

## 1. Provenance and evidence grades

- Repository: `13640226/VORNEQ`
- Pinned base commit: `5446c9176e876d9a7a477b8203500a0e1d8334b1`
- Pinned Git tree: `5a930ae62231b36eed85b32855076a4e9f8b7122`
- Expanded manifest: `EXPANDED_PYTHON_298`
- Historical audit batches: 001–030, with 10 files each for batches 001–029 and 8 for batch 030.
- Historical static inspection coverage reported: 298/298 files (100% of this *selected* manifest).
- Manifest cardinality and batch partition: rechecked against the pinned tree.
- Historical per-file Blob SHA checks: reported in the batch records; **a new independent re-verification of all 298 file contents and SHA values was NOT completed during the final documentary reconciliation**.
- No claim of repository-wide coverage, live system verification, or security closure.

Evidence grades must remain distinct: `VERIFIED_SOURCE` (pinned source and blob evidence), `DOCUMENTARY_RECONCILED` (cross-referenced prior reports), and `RUNTIME_VERIFIED` (requires separate runtime evidence; **not obtained**). A test's existence does not establish that it passed.

## 2. Consolidated database write paths

| Source path and lines | Static observation | Classification |
| --- | --- | --- |
| `apps/documents/artifact_sync.py` | Artifact/Binding synchronization writes | RUNTIME / INDIRECT |
| `apps/documents/audit_service.py` | AuditLog creation | RUNTIME / DIRECT |
| `apps/documents/services.py:236` | DocumentAccess delete | RUNTIME / DIRECT DELETE |
| `apps/evidence/models/evidence_state.py:75` | EvidenceState update_or_create | RUNTIME / DIRECT |
| `apps/evidence/services/relation.py:64,132` | EvidenceRelation create | RUNTIME / DIRECT |
| `apps/evidence/signals.py:7,13` | post_save / post_delete downstream updates | RUNTIME / INDIRECT |
| `apps/evidence/services/snapshot.py:61-76` | Snapshot delete and update_or_create | RUNTIME / DIRECT |
| `apps/graph/services.py:176-199` | Graph Node/Edge upsert and edge deletion | RUNTIME / DIRECT |
| `apps/media/vector_index.py:115,130,163` | MediaEmbedding upsert and delete | RUNTIME / DIRECT |
| `apps/notes/services.py:52-91` | Note/Artifact writes and soft delete | RUNTIME / DIRECT |
| `apps/profiles/forms.py:26-28` | Form constructor get_or_create; potential GET-triggered INSERT via `apps/profiles/views.py:13-19` | RUNTIME / CONDITIONAL |
| `apps/profiles/forms.py:63-86` | User/Profile save, on_commit avatar deletion | RUNTIME / DIRECT + EXTERNAL |
| `apps/verification/services/verification.py:79,164,223,241` | ReviewRecord, VerificationRequest/Result/Evidence writes | RUNTIME / DIRECT |
| `marketplace/admin.py:282,312,340` | Bulk QuerySet.update bypasses Product.save | RUNTIME / DIRECT |
| `marketplace/views.py:267,349,480,572` | Product create/edit/review writes | RUNTIME / DIRECT |
| `apps/verification/public.py:26-29,95-98` | ContentType.objects.get_for_model may INSERT if missing | RUNTIME / CONDITIONAL INDIRECT |

This is a **consolidated finding index**, not proof of exhaustive runtime call-path coverage.

## 3. Signals, hooks, callbacks and read-path purity

- `apps/evidence/apps.py:10-11`: signal registration import in AppConfig.ready.
- `apps/evidence/signals.py:7,13`: EvidenceRelation post_save/post_delete may update EvidenceState.
- `apps/core/signals.py`: downstream reputation-related effects, per prior source audit.
- `apps/profiles/forms.py:83-86`: old avatar storage deletion scheduled via transaction.on_commit.
- `apps/verification/services/verification.py:54-59`: post-commit AuditEvent handling; failure delivery guarantees unproven.
- `apps/platform_shell/apps.py:9-12`: autodiscovery initialization.
- `apps/platform_shell/capabilities/invoker.py:103-110`: authorization precedes execution *inside the inspected invoker*; complete caller coverage unverified.
- `apps/profiles/views.py:13-19` -> `apps/profiles/forms.py:26-28`: potential GET-to-INSERT chain.
- `marketplace/templatetags/trust_context.py:9-11` and `library/templatetags/library_trust_context.py:9-11`: templates invoke verification summary; potential indirect ContentType write.
- `marketplace/templatetags/entitlements.py:9-11`: calls entitlement service; no direct writer in tag.

## 4. Deletion and cascade inventory

- `apps/documents/services.py:236`: DocumentAccess delete.
- `apps/evidence/services/snapshot.py:61-63`: AssessmentSnapshot delete.
- `apps/graph/services.py:199`: delete stale graph edges.
- `apps/media/vector_index.py:130,163`: MediaEmbedding delete.
- `apps/notes/services.py:88-91`: soft-delete Note and Artifact.
- `apps/profiles/models.py:22-25`: UserProfile.user CASCADE.
- `apps/verification/models.py:204-212`: VerificationEvidence result CASCADE, relation PROTECT.
- `marketplace/models.py:68-73,376-392`: Seller/Product and Product/Review CASCADE, moderator PROTECT.
- `library/models.py`: FileFields do not by themselves establish physical file deletion.

The full repository-wide cascading effect graph and actual runtime deletion behavior are **not verified**.

## 5. Storage and external effects

- `config/email_backends.py:109-123`: external HTTPS email delivery; partial delivery/retry semantics unresolved.
- `config/settings_render.py:14-24`: DATABASE_URL required, SSL configured; does **not** prove runtime target identity or fail-closed PRODUCTION/NON_PRODUCTION/UNKNOWN classification.
- `config/settings_render.py:29-67`: optional S3-style object storage.
- `apps/profiles/forms.py:83-86`: on-commit avatar deletion.
- `library/models.py`: PDF/audio FileFields.
- `marketplace/models.py`: digital file field.
- `library/views.py:383-429`: PDF read path relies on local .path; object storage compatibility unverified.
- `marketplace/tests.py:146-149,192-197`: storage delete calls are **TEST_ONLY**.

## 6. Additional unresolved static findings

- `marketplace/admin.py:310-315,338-343`: bulk moderation updates may leave is_published inconsistent because Product.save is bypassed.
- `marketplace/views.py:439,448-466`: staff-only review, but no explicit per-action permission check or select_for_update in this inspected path; concurrent review safety unverified.
- `library/views.py:43-51,355-370`: authenticated-user access to published non-public-reading PDFs appears possible absent object-specific policy.
- `apps/platform_shell/capabilities/invoker.py:25-33`: TypeError handling in type check may accept invalid types; impact unresolved.
- `apps/evidence/tests/test_signature.py:53`: TEST_ONLY QuerySet.update bypass of instance immutability guard; exploitability unverified.
- `apps/verification/tests/test_services.py:265-287`: TEST_ONLY post-commit audit persistence failure contract; tests not run.

## 7. TEST_ONLY vs RUNTIME

Test fixtures, ORM create/update/delete calls, and assertions under test modules are TEST_ONLY; they must not be presented as observed production mutations or executed test results. Examples: `apps/evidence/tests/test_signature.py:53`, `apps/graph/tests_read_purity.py:38-99`, `apps/verification/tests/test_services.py:265-287`, `marketplace/test_trust_context.py:20-117`, `marketplace/tests.py:146-197`. A separately verified count of all TEST_ONLY versus RUNTIME files was not produced in this final documentary pass.

## 8. Evidence gaps and hard stops

| Gap | State |
| --- | --- |
| Runtime database target identity | UNKNOWN |
| Guard fail-closed coverage of every sensitive execution path | NOT_VERIFIED |
| Full delete/cascade graph | INCOMPLETE |
| GET read purity across all call paths | NOT_VERIFIED |
| Authorization coverage of every runtime entry point | NOT_VERIFIED |
| Post-commit audit delivery guarantees | NOT_ESTABLISHED |
| Storage/database consistency | NOT_VERIFIED |
| Independent security review | PENDING |
| Independent re-verification of all 298 Blob SHAs in final reconciliation | NOT_COMPLETED |
| Excluded files outside EXPANDED_PYTHON_298, including scripts/migrations/commands/workflows | NOT_CLOSED |

### Non-negotiable holds

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
PRODUCTION_RELEASE = BLOCKED
FINAL_STATE = SAFE_HOLD / NO_GO
```

## 9. Final decision and change governance

**DOCUMENTARY_RECONCILIATION = COMPLETED_WITH_LIMITATIONS**  
**HISTORICAL_STATIC_MANIFEST_COVERAGE = 298/298**  
**REPOSITORY_WIDE_SECURITY_CLOSURE = NO**  
**RUNTIME_SECURITY_CLOSURE = NO**  
**FINAL_VERDICT = SAFE_HOLD / NO_GO**

This document is a historical documentary evidence index, **not** an execution authorization, approval to merge, approval to deploy, permission to access databases, or a claim that security findings are resolved.

`PROPOSAL ≠ APPROVAL ≠ EXECUTION_AUTHORIZATION ≠ VERIFIED_EVIDENCE`

Document created on a dedicated documentation branch for review via a **Draft Pull Request**. No application code, migrations, configuration, secrets, infrastructure or production state are changed by this document.
