# Runtime audit contract (Phase 00.1)

This command supplements `audit_environment_parity` and `ai_gateway_report`.
It makes no authorization decision and never changes flags, models, migrations,
queues, ledger balances, caches, storage, or provider state.

## Usage (after separately authorized deployment)

Run from the existing Render Shell using its normal Django settings, separately
for each web service. Obtain the expected SHA independently from the approved
release record (not by copying the running process's value).

    python manage.py audit_runtime --environment staging --expected-sha <40-hex-approved-SHA>
    python manage.py audit_runtime --environment production --expected-sha <40-hex-approved-SHA>

The command refuses an unknown environment, unexpected service identity, DEBUG
on, malformed or mismatched SHA, wrong database name/vendor, or a nested
transaction. The shared ledger alias must point to the separately configured
`vorneq_ai_ledger` database. Each PostgreSQL query section has its own read-only
transaction with a 10-second per-statement timeout and checks the live database
identity. SQLite uses query_only and restores its previous state on exit.
`--local-test` is development-only; use disposable, already migrated test
databases. PostgreSQL local mode requires host postgres/localhost/127.0.0.1
and a test_ database name. No production migration is part of this PR.

## Evidence and limitations

- Fixed-name boolean Django Settings, effective offline policy checks,
  numeric model limits from the existing gateway report, and presence-only
  credential indicators.
- No values of API keys, owner grants, model names, email addresses, prompts,
  conversation contents, user IDs, worker IDs, reservation IDs or connection
  strings are emitted. Financial totals are aggregate micro-USD estimates,
  not provider billing. Reservation counts are scoped to the configured account
  and current environment. The ledger may be shared across environments.
  Accounts can be observed while the paid-call gate is off; sharing the same
  account identifier for image and chat is explicitly reported as invalid.
- Migration graph counts are router-aware, with the 0005 chat job migration
  called out. Application and ledger migrations are reported independently
  from model queries so missing tables do not erase migration evidence.
- Aggregate chat/image job states, expired chat leases, running image jobs
  with a reservation, conversation/message counts, and verified-primary
  matching email/active human identity aggregate counts.
- pgvector availability and installation are distinct read-only observations;
  SQLite reports NOT_APPLICABLE.
- No GitHub network verification is attempted. Follow-owner policy checks
  requiring external evidence return NOT_VERIFIED; this is not an approval.
- Redis and image storage report configuration readiness only. No cache probe,
  live provider call, email delivery, queue admission, or worker execution.
  Worker service inventory, deployment evidence and worker process health
  require separate Render/GitHub observations.
- Sections are independent observations, not a simultaneous cross-database
  snapshot. COMPLETE means the selected queries completed, not that any gate
  is open, migrations are current, or a capability is production-ready.
- PARTIAL plus a nonzero exit indicates at least one section could not be
  observed. Error values and driver exceptions are never emitted. A missing
  ledger configuration or account is reported explicitly, not assumed healthy.

## Testing

    python manage.py test apps.core.tests.test_runtime_audit

Use the repository's existing SQLite/PostgreSQL test matrix. Tests create only
disposable Django test fixtures and verify read-only SQL enforcement and
transaction restoration. Do not execute against hosted services from CI.

## Rollback

Remove the management command, its tests and this document. No schema or
runtime configuration change is needed. Deployment and any follow-up
operational action require separate authorization.
