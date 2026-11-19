# VORNEQ Marketplace — audited fixture cleanup V1

Release state: DRAFT / NOT DEPLOYED / NO PRODUCTION MUTATION.

## Verified evidence
- Production service: srv-dadn07eq1p3s73eccau0
- Database: vorneq_production_db, PostgreSQL 18
- Production SHA at evidence time: 3c24668cf7eb55c4bb84276a21b5963a815f5ead
- Rows: 501 total; 500 strict benchmark seller+slug pairs, one strict smoke seller+slug pair
- Sorted ID set SHA-256: 8fb10e4590fb421a8270a1f85d74904f51e23186f8da76f5a8194d2ec2bdba7b
- Entitlements 0; reviews 0; product files 0; images 0
- Product 501: one GenericForeignKey ArtifactBinding to active canonical product Artifact
- No other direct product FK dependencies or Artifact FK dependencies observed.

## Full backup and isolated restore
- Full PostgreSQL 18.7 custom-format dump at 2026-11-19T00:16:44.638269Z
- Backup SHA-256: 16bf832ba27a68065322b80ea3f97bde5781e526afbd8b07211e9c2098070dec
- Laptop Downloads file: VORNEQ_PRODUCTION_FULL_BEFORE_MARKETPLACE_FIXTURE_DELETE_20261119_0016Z.dump
- Manifest: VORNEQ_MARKETPLACE_BACKUP_EVIDENCE_20261119_0016Z.json
- Restore manifest: VORNEQ_MARKETPLACE_RESTORE_EVIDENCE_20261119_0016Z.json
- Verified isolated PostgreSQL 18.7 restore: 501 products, 501 strict fixture identities, one ArtifactBinding, 88 Django migration rows.
- The lab instance was stopped. No production restore occurred.

This is a *historic point-in-time full database backup*, not an automatic
rollback of any subsequent unrelated user activity. Revalidate freshness,
hash and restore evidence at execution.

## Contract
- The management command is read-only by default.
- The apply mode requires the exact known product ID-set hash, two independent
  seller-and-slug markers, and zero new products or unexpected relations.
- Only the known product 501 ArtifactBinding is detached. Canonical Artifact
  is deactivated, not deleted, preserving identity and traceability.
- Product rows are removed only in the same atomic transaction as exact-schema
  started/completed append-only AuditEvents, same batch correlation ID.
- Any changed products, dependencies, audit failure or authorization mismatch
  aborts the entire transaction; no silent cascade or opportunistic bulk delete.

## Production release requirements
1. CI green; independently review code and data impact in draft PR.
2. Separate explicit owner approval of the exact new deployment SHA and batch.
3. Fresh validated recoverable backup and restoration proof, not just a dump file.
4. Preserve existing AI authorization gates across SHA changes.
5. Before execution, authorize *only in the approved Render release*:
   VORNEQ_MARKETPLACE_CLEANUP_EXECUTION=OWNER_APPROVED_ONE_TIME_501
   VORNEQ_MARKETPLACE_CLEANUP_AUTHORIZED_SHA=<running SHA>
   VORNEQ_MARKETPLACE_CLEANUP_BACKUP_SHA256=<verified backup hash>
   VORNEQ_MARKETPLACE_CLEANUP_RESTORE_EVIDENCE=<verified evidence ID>
   VORNEQ_MARKETPLACE_CLEANUP_OWNER_REFERENCE=<owner authorization ref>
6. Run the read-only preview first:
   python manage.py marketplace_fixture_cleanup
7. Only after preview passes, run the explicit apply command with all arguments:
   python manage.py marketplace_fixture_cleanup --apply --acknowledge-empty-catalog 501 --backup-sha256 <hash> --owner-reference <ref>
8. Verify zero products, one inactive canonical Artifact, zero broken bindings,
   two audit events, no unexpected changes, and public and AI health.
9. Revoke one-time execution gates after execution.

This PR does not set environment variables, merge, deploy, or run the
destructive command. The old local-only synthetic_quarantine tool stays
local-only and is never bypassed.

## Rollback policy
On a precommit failure: the transaction rolls back automatically.
After a committed deletion: recovering the full backup may overwrite
subsequent unrelated production activity. Do not automatically restore
a live database without separate reconciliation and authorization.

## Known product presentation
All 501 existing items are known fixtures; the legitimate Marketplace catalog
will be empty. Public fixture shielding remains an independent PR #655.
