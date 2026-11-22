# Production Image Studio ? phase 1: read-only migration preflight

Issue #679. Baseline: bbcb7a022aac801bd078ed59afbf32e5c686003d.

## Verified baseline

Production Web is live on the baseline. A read-only Render job
job-dc12vspksfps73flp0eg observed ai_core 0001?0003, no image migration,
no image object-storage config, no image API key, no image ledger config,
and disabled image gates. Admin 1 was active and staff/superuser.

## New read-only command

On a reviewed, deployed SHA, with all image gates closed:

```bash
DJANGO_SETTINGS_MODULE=config.settings_render python manage.py inspect_production_image_0004 --expected-sha "$RENDER_GIT_COMMIT"
```

The command pins Production service, source SHA, internal PostgreSQL URL
and configured login, verifies live SQL identity in an explicitly read-only
transaction, checks exact migration history/table set and a single forward
0004 plan. It uses the established C02 operational identity binding, not
cryptographic database resource attestation. It has no execute/commit flag,
and never authorizes migration. Unexpected post-state or drift is denied.

## Remaining release work (NO-GO)

1. Dedicated Production migration one-use owner proof, backup/restore,
   locking, durable receipt and TOCTOU checks, isolated PostgreSQL rehearsal.
2. Production-default-off Web and Worker policy, separate Production-only
   image ledger (not staging or chat), atomic independent daily reservation
   count/amount and per-request ceiling; no retry on uncertain output.
3. Production-private image storage, separate provider project/key, separate
   worker, distinct service/database and exact SHA bindings; separately
   authorized budgets and infrastructure. Do not copy staging credentials.
4. Production Image Studio UI, localized errors and recovery; test isolation,
   quota and emergency stop, and preserve staging behavior.
5. Owner approval for merge, official deployment, exact migration scope,
   operational gates and one paid smoke. No resource creation, migration,
   activation or OpenAI request is authorized by this PR.
