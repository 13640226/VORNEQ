# C02 — backend identity evidence and SHA-bound atomic migration design V2

**Decision: C02 OPEN / PRODUCTION MIGRATION NO-GO / PAID AI OFF.**

**Scope:** source-only development in `audit/c02-sha-session-atomic-gate-v2-20261115`. The existing Production `apply_ai_core_guarded --apply` remains **disabled**. NO production/staging SQL writes, settings changes, merges or deploys are authorized by this design.

## 1. Cross-source evidence ledger

Verified from authenticated Render control-plane metadata (2026-11-15):
- Postgres resource `dpg-dagru1h42hec73eqr960-a`, database
  `vorneq_production_db`, user `vorneq_production_db_user`, PG major 18,
  primary, Oregon, available;
- web service `srv-dadn07eq1p3s73eccau0`, Oregon, identical environment ID,
  auto deploy disabled, branch `main`;
- operator captured non-secret Django runtime snapshot from Render Web Shell,
  showing a read-only connection on the same logical database/user/major version
  and expected live SHA `15ae7ce174c307e539487b08d926e9f5f22a218f`.

**Evidence classification:**
1. **Render control-plane identity: VERIFIED_METADATA.**
2. **Django session/logical database identity: VERIFIED_RUNTIME_SNAPSHOT.**
3. **Cross-source metadata match: CONSISTENT** (do not interpret as
   cryptographically bound, server-authenticated resource identity).
4. **Backend-bound proof that the PostgreSQL process belongs to resource ID:
   NOT_ESTABLISHED.** Exact Render resource ID is NOT returned by ordinary
   SQL current_database/current_user/inet_server_addr. The internal DNS address
   can differ from the PostgreSQL backend's `inet_server_addr()`; this
   divergence is diagnostic-only. External access is blocked by the empty
   allowlist; we will not widen it for the audit.

Render docs: Internal URLs are for same-region Render services and are not
subject to the external IP allowlist; the external URL requires TLS.
https://render.com/docs/postgresql-creating-connecting

Source-level config inspection: repository `render.yaml` currently describes
a **staging** service, not the live VORNEQ Production service, and its
`DATABASE_URL` entry is `sync: false`, not a `fromDatabase` control-plane
reference. `config/settings_render.py` consumes `DATABASE_URL` with
`dj_database_url`. Consequently this repository file does NOT provide
provider-managed resource-to-connection provenance for the current Production
service. A future `fromDatabase` Blueprint binding could strengthen
control-plane provenance but would require separate review and a Production
config authorization, and would still need runtime/backend validation.

A fresh external **read-only** query via the hosted Render connector was
attempted and rejected because `ipAllowList=[]` blocks all external clients;
the hosted connector reports that its IPs are not available for allowlisting.
**Do not change the firewall/allowlist for this audit.** This limitation is
recorded as `INDEPENDENT_POSTGRES_SQL=BLOCKED_BY_NETWORK`, not a database
fault and not a failed or successful backend identity attestation.

**Provider-dependent requirement:** Obtain a backend-bound, independently
authenticated mapping from the Render database resource ID to the PostgreSQL
server instance/session. A signed provider attestation, supported immutable
instance identifier, or other documented trustworthy control-plane/data-plane
binding would qualify if its issuer and freshness are independently verified.
Do **not** invent such an API, claim that DNS proves it, or treat matching
database name/Host prefix as an independent cryptographic proof.
Until this exists: `C02_BACKEND_IDENTITY: UNKNOWN` and `GO: NO`.

## 2. Future Production executor contract (NOT implemented/enabled)

A separately authorized single-purpose migration command must enforce the
following **within one PostgreSQL connection and transaction**:

1. **Before connecting:** owner-signed/recorded explicit SHA-bound approval;
   compare exact full SHA against latest independently fetched Render live
   deploy and active Django build SHA; prohibit concurrent deployment; verify
   `VORNEQ_AI_CORE_ENABLED=false`.
2. **Resource proof:** validate backend-bound independent Postgres resource
   attestation (above) from authenticated source. If missing/stale/ambiguous,
   abort before opening a writable migration transaction.
3. **Backup:** point-in-time recovery availability and tested restore at a
   known pre-migration point, linked to the attested source and within the
   approved freshness window. A local directory dump restore alone does not
   bind it cryptographically to the live backend.
4. **Locked transaction:** `transaction.atomic()` on the *same* psycopg
   driver/backend; `SET LOCAL lock_timeout` and `statement_timeout`;
   `LOCK TABLE django_migrations IN SHARE ROW EXCLUSIVE MODE NOWAIT` and
   dedicated `pg_try_advisory_xact_lock` for cooperative migrators. Ensure
   all writers to the schema are suspended/controlled because arbitrary
   non-cooperating DDL is NOT prevented by advisory locks.
5. **Re-attest before DDL:** verify DB/user/PG major 18/primary, expected
   source/schema/table baseline, active SHA, backend PID/driver identity and
   active transaction XID. `MigrationExecutor` must report precisely the
   forward `ai_core.0001_initial` and
   `ai_core.0002_aichatrequestguard` plan, no missing or extra steps, and a
   consistent migration recorder. Re-attest after plan preparation.
6. **Apply atomically:** execute exactly the two DDL migrations via
   `MigrationExecutor.migrate` with no connection replacement, no early
   COMMIT, and no re-entrant auto-migration. This requires verifying Django
   transaction behavior against the exact Production Django/PG version.
7. **Before COMMIT:** re-attest the same driver, backend PID, transaction XID,
   logical database and SHA; check exact migrated table/index/constraint
   inventory, 2 migration rows and empty pending plan. Any failure raises and
   causes PostgreSQL transaction ROLLBACK. No partial success or GO-on-error.
8. **After COMMIT:** independent read-only post-commit schema + application
   health/smoke check on authorized SHA. Preserve backup/PITR recovery option.
   Schema reverse migration or DB restore would require separate recovery
   authorization; do not promise an automatic Production rollback after commit.

This is a **design**, not an authorization or executable Production command.
`apply_ai_core_guarded --apply` remains intentionally blocked.

## 3. Executable disposable-only prototype

`scripts/c02_tests/guarded_ai_core_executor_v2.py` implements the guarded
mechanics on the fixed **throwaway** PostgreSQL 18 database
`isolated_c02_test` / user `c02test`, with a fixed loopback-only
`127.0.0.1:15432` or internal test alias `vorneq-c02-db:5432`:
- exact SHA from `git rev-parse HEAD`, clean source tree before DDL and
  second SHA check before rollback;
- explicit lab enable flag; hard deny Production, Staging, Render env,
  `DATABASE_URL` and non-lab host/user/database;
- real `django_migrations` table lock + transaction-scoped advisory lock;
- same connection object, backend PID, and transaction XID checks;
- exact two-step migration and schema/history postconditions;
- **mandatory deliberate rollback** and verification zero ai_core objects.
No option, flag, token, or caller-supplied connection string can turn this
prototype into a Production executor.

### Disposable local test invocation

Only on a trusted development machine with Python 3.12 and Django 5.2,
psycopg 3, and disposable PostgreSQL 18. Use unique container name and
make sure port 15432 is free:

```powershell
docker run -d --name vorneq-c02-v2-lab -p 127.0.0.1:15432:5432 `
  -e POSTGRES_USER=c02test -e POSTGRES_PASSWORD=localonly `
  -e POSTGRES_DB=isolated_c02_test postgres:18
$env:VORNEQ_ENV = "development"
$env:C02_TEST_LOOPBACK = "1"
$env:C02_ENABLE_DISPOSABLE_DDL_REHEARSAL = "YES"
$sha = (git rev-parse HEAD).Trim()
python -m unittest -v config.tests.test_c02_guarded_executor_v2
python -m scripts.c02_tests.guarded_ai_core_executor_v2 --expected-sha $sha
docker exec vorneq-c02-v2-lab psql -U c02test -d isolated_c02_test -X `
  -c "SELECT app, name FROM django_migrations WHERE app = 'ai_core'"
docker rm -f vorneq-c02-v2-lab
```

**Observed 2026-11-15 local run, including final source-tree-cleanliness and SHA recheck guards**, on exact SHA `dfe7c11a9fdaa1a34454224c944b47978857876f` (before this documentation-only update):
```text
14 unit tests PASS (Exit Code 0)
PASS: SHA, lab DB identity, recorder and advisory locks, exact migration plan
PASS: actual 0001/0002 DDL under same locked transaction and backend
PASS: deliberate rollback of both ai_core DDL migrations
PASS: no ai_core tables or recorder rows persisted
C02_GUARDED_LAB_REHEARSAL_PASS / PRODUCTION_GO=NO
LAB_EXIT_CODE=0; AFTER_ROLLBACK_AI_TABLES=0; AI_MIGRATIONS=0
```

## 4. Acceptance gates and current state

| Gate | Result |
| --- | --- |
| GitHub branch isolates changes | YES |
| Restore of production backup into independent Docker PG18 | PREVIOUSLY VERIFIED |
| SHA-bound fixture-only executor | IMPLEMENTED, LAB ONLY |
| Same-session locked/atomic DDL and rollback | VERIFIED IN LAB |
| Precise production resource metadata from Render API | VERIFIED |
| Independent, backend-bound PG resource proof | **MISSING** |
| End-to-end new guarded Production executor (write mode) | **NOT AUTHORIZED / DISABLED** |
| Formal CI on final PR SHA | PENDING |
| Owner approval to merge/deploy | NOT GRANTED BY THIS DOCUMENT |
| Production `ai_core` migration GO | **NO** |

**No automatic switch from C02 OPEN to GO.**
