# C02 0006 — schema-first guarded executor (draft)

Scope: ai_core.0006_message_feedback only. This PR grants NO hosted migration,
deployment, feature activation, or provider-call permission. The current live
V9.1 SHA is e25be58999920a98481d58c15f42bcfb295308d5; do not deploy V9.2 before
the schema exists. Do not spoof RENDER_GIT_COMMIT or remove any C02 hard stop.
Existing 0001–0004 release receipts are not valid for 0006.

## Isolated test
Use a disposable PostgreSQL database with a test_ name, the existing local
host allowlist, development settings and C02_FEEDBACK_0006_LAB=YES. No Render
environment or provider credentials. Prepare 0005 using synthetic data.
Default mode inspect is read-only. Rehearse performs exactly 0006 under a
migration-recorder lock and transaction advisory lock, verifies schema and
rolls back. lab_commit is explicit and only for the disposable test database.
The management command checks the actual clean Git SHA.

## Proposed hosted procedure — NOT authorized by this PR
A separate approved, clean checkout of the exact current main commit is
required in /tmp/vorneq-c02-0006-<source-sha> on the actual old web instance.
The running service's RENDER_GIT_COMMIT must remain the independently observed
V9.1 SHA. Verify availability of Git, the separate checkout, dependency
compatibility, internal DB binding, login/execution role, and closed chat,
conversation, feedback and job gates before issuing an owner release. The
operational artifact path has not been exercised on Render in this PR.
No changes to the deployed checkout, no public PostgreSQL access, no implicit
migrate, and no new service are authorized. Do not proceed if this path cannot
be independently attested.

The candidate hosted_commit mode requires explicit environment, source SHA,
old live SHA and release ID, an independent arm and a new authenticated,
unedited owner comment on PR #770. Its header is
C02_AI_MESSAGE_FEEDBACK_0006_OWNER_RELEASE_V1. The strict manifest fields are
defined in c02_message_feedback_0006_release.py, including exact environment,
both SHAs, DB resource, login/execution roles, 0006-only scope, backup digest,
restore evidence, backup and restore timestamps, expiry and risk acceptance.
Use a fresh backup (at most two hours old at point of use), proven restore,
a 30-minute-or-shorter grant, and independently verified source and live
deployment identities. Owner must explicitly accept residual operational
identity and rollback restrictions. Do not put credentials in the comment.

The command independently checks GitHub main and re-fetches owner evidence,
pins environment, service, live SHA, source SHA and internal DB URL; the
write arm must match both SHAs. It uses exact plan, read-only preflight,
same-session locks, a separate autocommit one-use audit receipt, verification
before commit and read-only post-commit verification. A consumed receipt
survives DDL rollback; never automatically retry. Any ambiguity requires
reconciliation and a new independent decision. The owner must separately
authorize each environment and later deployment. Existing generic migration
workflow stops remain intact.

## Rollback and compatibility
Django CASCADE is ORM-level; PostgreSQL NO ACTION is expected for the FK.
V9.1 can operate with an empty additive table, but deletion of a message
referenced by feedback after V9.2 activation can fail in V9.1. Do not declare
rollback safe with populated feedback; disable new writes, preserve rows,
and use a compatible rollback release/maintenance procedure. Do not drop the
table, change its FK to SQL CASCADE, or reverse migration to hide the problem.
Prove the old-runtime compatibility, current-runtime cascade, and exact
schema on disposable data before any operational release.
