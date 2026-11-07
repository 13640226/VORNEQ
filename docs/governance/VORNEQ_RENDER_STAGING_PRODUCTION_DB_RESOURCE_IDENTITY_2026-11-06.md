# VORNEQ — Render Database Resource Identity Inventory (2026-11-06)

**Record type:** Documentary inventory, based on read-only Render control-plane metadata.
**Scope:** Resource identities only; not proof of Django runtime connection identity.
**Authorization:** Documentation-only. No SQL, secret retrieval, migrations, service configuration changes, or deploys.
**Observed date:** 2026-11-06 (UTC).
**Render workspace ID:** `tea-da71asm1egvs73f1fec0`.

## Production

| Field | Observed value |
| --- | --- |
| Render database resource name | `vorneq-production-db` |
| Render PostgreSQL resource ID | `dpg-dagru1h42hec73eqr960-a` |
| PostgreSQL database name | `vorneq_production_db` |
| PostgreSQL database user | `vorneq_production_db_user` |
| Region | `oregon` |
| PostgreSQL version | `18` |
| Control-plane status | `available` |
| Render environment ID | `evm-da71gna6iojc7385it9g` |
| Dashboard | https://dashboard.render.com/d/dpg-dagru1h42hec73eqr960-a |

**Associated Production web service (control-plane inventory, not connection proof):**
- Service: `VORNEQ`
- Service ID: `srv-dadn07eq1p3s73eccau0`
- Render environment ID: `evm-da71gna6iojc7385it9g`
- Source repository/branch: `13640226/VORNEQ` / `main`
- Latest observed deployment: `dep-dbmrauajnfac73b99qt0`; commit `397c8a1b4b7982ec13c78ac53109cc5454321a85`; Render status `live` at 2026-11-06 11:10 UTC.
- Service URL observed in Render: https://samankherad-staging-v2.onrender.com (legacy-looking hostname; hostname is **not** a database identity indicator).

## Staging

| Field | Observed value |
| --- | --- |
| Render database resource name | `vorneq-staging-db` |
| Render PostgreSQL resource ID | `dpg-dbm74m8u01pc738j8r1g-a` |
| PostgreSQL database name | `vorneq_staging_db_9i8v` |
| PostgreSQL database user | `vorneq_staging_db_9i8v_user` |
| Region | `oregon` |
| PostgreSQL version | `18` |
| Control-plane status | `available` |
| Dashboard | https://dashboard.render.com/d/dpg-dbm74m8u01pc738j8r1g-a |

**Associated Staging web service (control-plane inventory, not connection proof):**
- Service: `vorneq-staging`
- Service ID: `srv-dbm7dvc9v7es7393g70g`
- Source repository/branch: `13640226/VORNEQ` / `main`
- Service URL: https://vorneq-staging.onrender.com

## Separate DR restore resource — do not confuse with Production or Staging

- Render name: `vorneq-dr-restore`
- Render PostgreSQL resource ID: `dpg-dafs4did0e5s73dph9jg-a`
- PostgreSQL database name: `vorneq_dr_restore`
- Region: `oregon`
- Control-plane status: `available`
- Dashboard: https://dashboard.render.com/d/dpg-dafs4did0e5s73dph9jg-a

## Evidence limits / C02

1. The values above were read from the connected Render service and PostgreSQL resource inventory; they identify Render **resources**, not the actual runtime database destination selected by the Django application.
2. Matching Render environment IDs between Production service and Production database is **not** proof of the runtime connection. Staging has a separate service and database, but its runtime mapping is likewise **not verified**.
3. No database URL, password, token, secret, connection string, or query output is included in this document.
4. Successful web responses, a `live` deployment, and an `available` database do not establish which PostgreSQL instance is used by the application.
5. A separate, appropriately authorized and evidence-preserving runtime identity check is needed before declaring either application's database binding verified.

**PRODUCTION_DB_RESOURCE_IDENTITY = DOCUMENTED / CONTROL_PLANE_OBSERVED**

**STAGING_DB_RESOURCE_IDENTITY = DOCUMENTED / CONTROL_PLANE_OBSERVED**

**PRODUCTION_RUNTIME_DB_BINDING = UNVERIFIED**

**STAGING_RUNTIME_DB_BINDING = UNVERIFIED**

**C02 = OPEN_CRITICAL; NO_SECURITY_GATE_CLOSURE**

This document does not authorize a deploy, migration, SQL probe, merge exception, or change to any security gate.
