# Guarded ai_core.0003_conversation Runner — V1

Status: isolated branch and CI candidate; NO Production migration authorization.
Date: 2026-11-17. Base main: 0f3eb4b4841d03c7eb71722fbeca28cc6fda2e05.

The old 0001/0002 runner and owner release contract are unchanged.
The 0003 runner requires exactly applied 0001 and 0002, the old two
ai_core tables, and a Django plan with exactly one forward migration.
It expects two new tables, four named indexes and four named constraints.
Fail closed if schema/history, source SHA, backend session, role or transaction
identity changes. PostgreSQL locks and a short DDL timeout protect execution.

## Disposable lab

Only a disposable test PostgreSQL instance with VORNEQ_ENV=development,
C02_CONV_0003_LAB=YES, and a local allowlisted hostname may use lab mode.
Without --commit, the DDL runs in one PostgreSQL transaction then is
deliberately rolled back and the pre-state verified independently.
Use the exact clean checkout SHA in place of the placeholder:

    python manage.py c02_conversation_0003_runner --target lab --expected-sha <SHA>

CI runs unit and disposable PostgreSQL integration tests; these do not touch
Production or Staging. No live migration or provider operation is part of CI.

## Future Production release (NOT AUTHORIZED)

Before deploying code, obtain an independent SHA-bound owner Deploy decision.
Deploy does not run the new migration. The conversation feature flag remains
off by default; existing Production AI controls must be rechecked.

A future Production migration requires separate approval and all of:
1. Fresh provider backup plus independent restore/checksum proof.
2. Live service SHA, internal PostgreSQL URL, execution role, session user,
   database identity and exact plan verified at point of use.
3. Both global Production AI writes and conversation writes stopped.
4. One unedited, authenticated owner comment in GitHub Issue #407 using header
   C02_OWNER_CONVERSATION_0003_RELEASE_V1 and exact decision
   AUTHORIZE_PRODUCTION_AI_CORE_0003_CONVERSATION. Migration list must be
   only ["ai_core.0003_conversation"]. Grant must name exact release ID,
   target SHA, service, database resource, login and execution roles, backup
   SHA256 and restore evidence, risk acceptance, and expire in <=15 minutes.
5. Explicit, separately scoped runtime arm in new VORNEQ_C02_0003_* keys,
   read-only GitHub owner verifier token, and --commit for production.
6. One-use receipt consumed durably before DDL (not retried if unclear);
   owner proof and process SHA verified again before commit.
7. Post-commit read-only history, index, constraint and table verification,
   followed by disabling all temporary authorization values.

The old C02 approvals for 0001/0002 are NOT valid for 0003. This branch does
not issue any owner grant, modify Render variables, or broaden a Production
actor allowlist. No direct manage.py migrate in Production.

Notes: operational DB identity matching is not a signed cryptographic
attestation. Existing C02 residual risk acceptance is documentary, not
perpetual permission. The redundant index identified in the V1 design remains
intentionally unchanged and can be addressed in a separately tested change.
