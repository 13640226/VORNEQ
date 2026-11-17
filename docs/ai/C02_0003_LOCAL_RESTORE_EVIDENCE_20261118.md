# C02 — AI Core 0003 isolated restore evidence (sanitized)

**Record:** C02-0003-RESTORE-PG18-20261117-2247Z-V1  
**Status:** LOCAL_RESTORE_VERIFIED / PRODUCTION_MIGRATION_NO_GO  
**Recorded:** November 18, 2026 (Europe/Berlin; source export November 17, 22:47 UTC)  
**Scope:** isolated local PostgreSQL only; no Render Production operation

## Source and provenance

The owner downloaded the November 17, 2026, 22:47 UTC Render PostgreSQL
logical export as a compressed directory-format archive. Its SHA-256 matched
the privately recorded local checksum. The original backup, full digest,
credentials, and personal filesystem paths are not published in this public
repository.

Private source evidence filename:
**VORNEQ_C02_0003_LOCAL_RESTORE_EVIDENCE_20261117.txt**.

This is a sanitized summary of an owner-local verification, not a signed
attestation of the origin of the Render PostgreSQL resource.

## Local test observations

- The tar/gzip archive was readable; PostgreSQL directory-format restore
  catalog listing succeeded with **838 entries**.
- The restore target was a newly initialized, disposable **PostgreSQL 18.7**
  cluster on Windows, bound **only to 127.0.0.1** on a transient local port.
- A separate empty local test database was created. No Render, staging, or
  production endpoint was configured as a connection target.
- pg_restore used --no-owner, --no-privileges, --exit-on-error and
  --single-transaction. **Exit code: 0**.
- Read-only post-restore verification reported **91 public tables**.
- Django ai_core migration history contained **0001_initial** and
  **0002_aichatrequestguard**. The tables ai_core_aiconversation and
  ai_core_aimessage were **absent**, consistent with 0003 not being applied
  in the source export.
- The temporary PostgreSQL server was stopped; its disposable cluster and
  restored data were removed after checking server shutdown. The original
  downloaded archive and local evidence file were retained.

## Gate status

| Gate | Evidence/status |
|---|---|
| Local backup checksum agreement | PASS locally, full digest private |
| Restore catalog readable | PASS (838 entries) |
| Isolated PostgreSQL 18.7 restore | PASS (exit code 0) |
| Restored database has expected baseline | 91 tables; ai_core 0001 and 0002 |
| Conversation tables from 0003 | Not present |
| Provider-cryptographic database identity | NOT VERIFIED |
| Point-of-use backup freshness | NOT VERIFIED |
| Production 0003 migration | NOT EXECUTED |
| One-use owner migration authorization | NOT ISSUED |
| Production migration decision | **NO-GO** |

Successful restore **does not** close C02 or authorize a deploy, a Production
migration, feature activation, a cost adjustment, or a paid OpenAI retest.
Future permission must match the then-current Production SHA, verified backup
freshness, target DB identity, explicit one-use owner proof and rollback
controls. The local lab result is a distinct, limited piece of evidence.

## Security follow-up

An image shared during the workflow exposed a GitHub personal access token
in Render environment variables. The credential owner must revoke and rotate
that token separately. No token value is copied into this document.

## Change scope

**Documentation only**. No Runner, CI configuration, database, Render
environment, credential, or production operation changes. Push and PR checks
are allowed; Merge and Deploy are separate owner-authorized actions.
