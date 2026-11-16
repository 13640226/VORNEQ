# C02 private execution transport & one-use owner authorization — Design V1 (2026-11-16)

**Status: DOCUMENTARY_ONLY / NO_GO.** This is a proposal and a snapshot of independently observed evidence. It is **not** authority to change secrets, networking, roles, Render services, CI policy, deployments, or PostgreSQL. It must not be used to turn on `PRODUCTION_WRITE_ENABLED` or invoke a migration.

**Baseline:** `main` and Production `74c8eac8e0f4d7b0eae6e4de4bbe595ae477092f`. Service `srv-dadn07eq1p3s73eccau0`, database `dpg-dagru1h42hec73eqr960-a`, DB `vorneq_production_db`, login `vorneq_prod_app_rot_20261116`, execution role `vorneq_production_db_user`.

## 1. Verified physical path and constraints

| Source / property | Independently observed on 2026-11-16 |
|---|---|
| Render service + database | Both in workspace `tea-da71asm1egvs73f1fec0`, region `oregon`, environment `evm-da71gna6iojc7385it9g` |
| PostgreSQL | 18 primary, `available`, external IP allowlist **empty** |
| Production service | `main`, auto-deploy `no`, autoDeployTrigger `off`, exact SHA live |
| DB login | New authenticated login `vorneq_prod_app_rot_20261116`; SQL execution role differs intentionally |
| Runtime-to-control-plane URL | Owner's fresh-nonce HMAC matched authenticated Render Internal URL: `HMAC_MATCH=PASS`; application settings precheck PASS |
| Schema/backups | Owner's read-only DB snapshots show `ai_core` migrations absent; independent local PG18 **restore** of 2026-11-16 archive passed; AuditEvent valid unique `event_id` index and observed INSERT grants |
| DNS vs backend IP | No equality, **DIAGNOSTIC_ONLY**; Render private IP mapping / proxy is a plausible explanation, not a cryptographic proof |
| GitHub Actions `production` | Branch policy includes `main` only; **no required reviewers configured** |
| GitHub source secret | `PRODUCTION_SOURCE_DATABASE_URL` rotated to the *external* Render URL 2026-11-16; external IP allowlist still empty; direct DB access from hosted runners deliberately blocked |
| Render One-Off Job | Read-only PoC **SUCCEEDED** on Production base service; job `job-dbtlbq3rjlhs738l2ar0`, 2026-11-16T19:13:45Z–19:14:04Z |
| Render API key in GitHub | No relevant `RENDER_API_KEY` secret visible in repository or Production Environment metadata; do not assume scoped key access is enabled |

GitHub-hosted runners **do not** join Render's private network merely because they can authenticate to GitHub or call the Render API. Opening `0.0.0.0/0`, trusting ephemeral runner IP ranges or tunnelling a Production SQL connection through a public web endpoint is **not an approved solution**.

## 2. Selected transport pattern

```text
GitHub Actions (manual decision/evidence, no DB URL or direct SQL)
  -> optional authenticated Render API control call (ONLY after scoped, reviewed capability)
  -> Render One-Off Job (same region, private-network Internal DATABASE_URL)
  -> PostgreSQL dpg-dagru1h42hec73eqr960-a
```

Render documentation: `https://render.com/docs/one-off-jobs` and `https://render.com/docs/private-network`.

A One-Off Job inherits its base service's latest successful **build artifact** and environment **at job creation time**, not necessarily the SHA or environment GitHub currently expects. Therefore the Job **must** fail closed if `RENDER_GIT_COMMIT != owner-authorized SHA`, the `DATABASE_URL` is not the authenticated internal URL, or either current role or session login changed. It must repeat the identity/TOCTOU controls in the same transaction. Job-created logs and job IDs become explicit audit evidence.

**Executed read-only PoC:** Owner-controlled Render CLI created One-Off Job `job-dbtlbq3rjlhs738l2ar0` with the exact existing `c02_runtime_observation --expected-sha 74c8eac8e0f4d7b0eae6e4de4bbe595ae477092f` command (no DDL). Status `succeeded`, duration 19 seconds. Render job resource logs show: service ID `srv-dadn07eq1p3s73eccau0`, live SHA equal expected, database `vorneq_production_db`, `session_user=vorneq_prod_app_rot_20261116`, `current_user=vorneq_production_db_user`, configured host exactly the internal DB hostname, PG18 primary, port 5432, `transaction_read_only=on`, and `C02_RUNTIME_SNAPSHOT_ONLY: NO MIGRATION GO`. This **demonstrates private in-Render connectivity**, not GitHub automated dispatch, a migration run, or cryptographic backend identity proof. One-Off Jobs are billable per second.\n\n**Current authorized operating mode:** GitHub may prepare and record a read-only attestation request; the owner can run an approved **read-only** Render Job manually through Render CLI/API with an exact hard-coded read-only command after separate execution approval. No production migration Job is authorized by this design.

**Automation hold:** The Render API `POST /v1/services/{serviceId}/jobs` accepts an arbitrary `startCommand`; a general Render API key placed in GitHub would grant an unacceptable shell/exfiltration capability against a service that inherits Production credentials. Render Scoped API Keys are in early access, and their availability/per-action resource scoping has **not** been established for this account. Do not create or store a broad Render API key in GitHub Actions. For any later machine dispatch, first prove least-privilege scopes and use a separate restricted read-only verification service/credential; a scoped `jobs:create` permission alone does **not** constrain the startCommand's contents.

## 3. Source identity acceptance (operational, not cryptographic)

Use **separately obtained** Render control-plane metadata, current Production Web Shell HMAC, and one Render Job's live transaction snapshot. Required evidence fields:

1. Immutable target: resource ID, DB name, user, PG major, primary role, region, environment ID and service ID; current Render API response with timestamp.
2. Fresh nonce HMAC over the **current Render Internal Database URL** equals `DATABASE_URL` within the executing Render process. Do not persist raw URL, password, bearer key, or a full connection string.
3. `session_user=vorneq_prod_app_rot_20261116`, `current_user=vorneq_production_db_user`, expected DB, PG18, primary, correct service ID and `RENDER_GIT_COMMIT=expected SHA`. Compare before work, after acquiring locks, and just before commit in the **same backend session**; fail on PID/driver/transaction change.
4. This is a **Render control-plane trust** acceptance decision only. `POSTGRES_BACKEND_CRYPTOGRAPHIC_IDENTITY_PROVEN=False` remains truthful; no Render-supported cryptographic resource-ID-to-backend binding is available in the reviewed evidence.

Existing code: `apps/core/c02_operational_binding.py`, `apps/core/c02_resource_attestation.py`, `apps/core/management/commands/c02_runtime_observation.py` and `apps/core/c02_stage_c_runner.py`.

**Current status:** Control-plane + owner Web Shell operational prechecks PASS, and a separate read-only Render One-Off Job has **PASS** for the current SHA/session. A *fresh point-of-use check before any future migration* is still required; this job is not reusable authorization. Owner acceptance of residual identity risk and release decision are **not issued**. Thus **not a migration GO**.

## 4. Owner one-use release: required proof and remaining implementation gap

**Current source limitation:** `c02_stage_c_runner.authorize()` tests a regex for `VORNEQ_C02_MIGRATION_AUTH`, confirms it contains a matching SHA and validates a syntactic backup evidence string. That environment string alone is **not independent proof** that the owner issued it; merely setting an environment variable must never grant Production write permission. The code does maintain the separate transactional AuditEvent receipt `ON CONFLICT(event_id) DO NOTHING`, with a unique `event_id`, and guards replay. The owner issuance/identity and point-of-use backup provenance have to be independently attested.

**Required release record (future; no value currently issued):**

- Source of truth: explicit owner-issued record on a designated protected GitHub issue, identity authenticated from the GitHub API (not copied/claimed in an environment variable). Distinguish author account, immutable comment ID, issue/repository and timestamp. Issue edits or revocations require invalidation; fetch fresh at execution.
- Bind: unique release ID, **exact 40-hex main/live SHA**, Render service ID, Postgres resource ID, DB name, login and role, expected migrations `0001_initial` then `0002_aichatrequestguard`, Backup archive SHA-256 and observed restore reference, short expiry and separate migration authorization wording.
- Validate owner decision precedence (STOP_340 / C02 governance) and reject absent, expired, changed, revoked, duplicate/conflicting or non-owner records. Do not interpret a past deploy approval, PR merge approval or environment variable as a migration authorization.
- Atomically consume a deterministic release receipt in the authenticated Production audit ledger using the second independent autocommit connection with unique `event_id`; **one attempt only**, durable even if the migration transaction aborts. Validate exact expected payload, idempotency, session identity, real index and DB insert privileges. On uncertain ACK **do not automatically retry**.
- Re-check same-context identity, one-use receipt, SHA, exact migration plan, locks, backup point-of-use freshness and all stop flags immediately before any DDL/commit.
- Prefer a short-lived owner-signed release manifest or trusted GitHub API proof obtained inside the Render Job; never accept an unverified free-text `OWNER-AUTH` value as sufficient.

**Required negative tests in an isolated PostgreSQL lab:** fake author, missing/expired/revoked owner record, wrong SHA/DB/service, duplicate release, retry after rollback, concurrent consumers, changed backend PID/driver/session, changed live SHA, stale backup, API/issuer outage, and lost acknowledgement. Default is **deny** for every uncertainty.

**Do not issue, synthesize, or pre-authorize a release as part of this review.** No current single-use authorization for this SHA was found in the scoped issue audit (#340, #407, #448).

## 5. Necessary changes — not yet approved

1. Implement a GitHub-to-Render **read-only verification transport**, limited to a dedicated, non-public, minimal-credential verifier if scoped API calls and a narrowly restricted execution command can be proven; otherwise run owner-controlled Render Web Shell / One-Off Job manually. Check paid-job costs and obtain distinct operator approval before creating any Render Job.
2. Replace direct-PostgreSQL legacy CI preflight with a transport-only design; retain hard-stop controls on `.github/workflows/migrate-production.yml` and `migrate-production-db.yml` until explicitly reviewed. Do not remove `ALLOW_PRODUCTION_TARGET=false` or `if: false`.
3. Add an independently authenticated owner issuance verifier and time-bound release receipt; integrate it before enabling the production write gate, and test in isolated PostgreSQL.
4. Configure GitHub Production Environment explicit reviewers or an equally trustworthy independent manual decision control; branch `main` restriction alone is insufficient for one-use migration approval.
5. Only in a **later separate PR and independent decision**, once A1–A8 evidence from `docs/C02_STAGE_C_RUNNER_AND_ACCEPTANCE_CRITERION_V1.md` is complete, consider enabling the Production runner. Deploy approval and migration approval remain different actions.

## 6. Decision

```text
PRIVATE_POSTGRES_PATH = VERIFIED_AVAILABLE
PUBLIC_POSTGRES_INBOUND = BLOCKED / KEEP_BLOCKED
GITHUB_DIRECT_POSTGRES = NOT_AUTHORIZED
RENDER_ONE_OFF_JOB_TRANSPORT = READ_ONLY_POC_SUCCEEDED / NO_GITHUB_DISPATCH
RENDER_SCOPED_MACHINE_CREDENTIAL = NOT_VERIFIED / DO_NOT_INSTALL_BROAD_KEY
OPERATIONAL_CONTROL_PLANE_HMAC = PASS (prior operator evidence)
CRYPTOGRAPHIC_BACKEND_RESOURCE_IDENTITY = NOT_AVAILABLE
OWNER_ONE_USE_ISSUANCE_VERIFIER = NOT_IMPLEMENTED
PRODUCTION_ONE_USE_AUTHORIZATION = NOT_ISSUED
PRODUCTION_WRITE_ENABLED = False
STOP_340 = ACTIVE
C02 = OPEN_CRITICAL
MIGRATION_GO = NO
PAID_AI_PRODUCTION_GO = NO
```

This design record creates no new Production authority, dispatch and rollback capability. Future execution must use fresh SHA-bound evidence and a distinct explicit owner decision.
