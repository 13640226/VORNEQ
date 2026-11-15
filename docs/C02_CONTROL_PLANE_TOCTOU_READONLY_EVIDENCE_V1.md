# C02 — independent Render control-plane metadata & TOCTOU evidence V1

**Mode:** GITHUB BRANCH ONLY / NO PROD CHANGE / NO MIGRATION / NO DEPLOY

**Production baseline recorded 2026-11-15:** `c0bb89c4c3e53a53fa4e6b577c0c78561e678a0d` (Render live before this PR).
Do not presume this SHA remains current later.

## 1. Evidence provenance (two distinct sources)

1. **Control plane:** authenticated Render API GET of
   `/v1/postgres/dpg-dagru1h42hec73eqr960-a` and
   `/v1/services/srv-dadn07eq1p3s73eccau0`.
   Expected Postgres resource ID, database/user, region, status, role, PG major
   and service environment/region/branch are compared by
   `apps/core/c02_resource_attestation.py`. API credentials belong only on
   an authorized, trusted operator workstation; never in GitHub/CI/Render app
   env variables, screenshots, issues, chat, logs, or committed files.
2. **Data plane:** `python manage.py c02_runtime_observation
   --expected-sha <live-40-hex-SHA>` from an authorized Production Render
   web shell produces **non-secret snapshot data** from one Django/PostgreSQL
   read-only transaction and validates SHA, primary state and stable connection.
   No migration is performed. The JSON must be stored outside this repo,
   preferably only briefly, with restricted local access.

The two reports have different provenance; copying Render values into a
Django-generated JSON file or supplying manually fabricated evidence does not
constitute independent verification. Do not upload any credentials.

## 2. Operator verification (read-only)

On **Render Production Web Shell** after deploying the command in a separate,
specifically approved future operation (NOT part of this PR):

```bash
DJANGO_SETTINGS_MODULE=config.settings_render python manage.py c02_runtime_observation --expected-sha <LIVE_SHA>
```

Capture **only** the one-line JSON object from stdout into a restricted local
file `c02-runtime.json` (do not commit it). The command prints a second
`C02_RUNTIME_SNAPSHOT_ONLY: NO MIGRATION GO` informational line.

On a separate trusted operator workstation **with a Render API token already
configured securely**, from the repository root:

```bash
python -m scripts.c02_tests.verify_render_control_plane --snapshot c02-runtime.json --expected-sha <LIVE_SHA>
```

The utility reads `RENDER_API_KEY` from its process environment and only makes
**GET** requests to the fixed Render API resource paths. It does not attempt
a Postgres SQL connection and never prints the token. Any missing or inconsistent
metadata fails closed. The two snapshots are not cryptographically bound to
each other; compare capture time and current Render deploy to reduce staleness.

Expected **limited** success:

- `CONTROL_PLANE_METADATA_MATCH: true`
- `DJANGO_RENDER_RUNTIME_METADATA_MATCH: true`
- `POSTGRES_BACKEND_RESOURCE_IDENTITY_PROVEN: false`
- `C02_MIGRATION_GO: false`

### Residual independent-attestation gap

These fields, a matching Render hostname prefix and Postgres database name,
or a DNS/backend-IP match **cannot prove** the actual backend's Render resource
ID in the presence of a proxy, DNS redirection, or a compromised runtime.
The previously observed Render DNS and `inet_server_addr()` mismatch remains
diagnostic, not an authorization. A trustworthy backend-bound identity signal
supported by Render (or other authenticated independent resource evidence)
is still needed. **Resource-ID authorization: UNKNOWN, not PASS.**

## 3. TOCTOU negative testing in disposable PostgreSQL

Run `scripts/c02_tests/postgres_toctou_lock_negative.py` ONLY in the disposable
Docker network `vorneq-c02-db`, database `isolated_c02_test`, user `c02test`.
The script intentionally creates/drops **only** a test table there and proves:

- A held `SHARE ROW EXCLUSIVE` PostgreSQL table lock rejects a second
  `NOWAIT` lock attempt (the second transaction is aborted and rolled back).
- The lock becomes available after transaction A commits.
- A replaced PostgreSQL driver/backend is rejected by
  `postgres_session_guard.assert_same_session`.

This demonstrates a *possible* serialization primitive for a future
single-transaction guarded migration executor. It does **not** show that
Django's actual `ai_core.0001` and `0002` DDL, its migration recorder and
the production routing run atomically in a locked, stable session. A rogue
schema writer can also ignore an advisory/app lock; arbitrary DDL is not
blocked by the tested lock on the unrelated test table.

## 4. Approval boundary

- Existing Production `apply_ai_core_guarded --apply` continues to fail
  before any writes. This PR does **not** add a Production apply path.
- All CI test fixtures are local/mocked or run against disposable PostgreSQL.
  No Render token or Production credentials in CI.
- `C02 = OPEN`, `PRODUCTION_MIGRATION = NO_GO`, `AI_PAID_PRODUCTION = OFF`.
- Future Production migration needs a **new explicit SHA-bound owner decision**
  after independently verified resource identity, successful same-session
  actual `ai_core` migration lifecycle in disposable PostgreSQL, backup
  restore evidence, lock budget and concurrency safety, and final runtime SHA
  + database + migration plan re-check immediately before use.
