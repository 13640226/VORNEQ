# VORNEQ Mock Image Worker — Staging-only preparation

Status: **CODE-ONLY / NO LIVE WORKER / NO LIVE MOCK E2E**.
This document is not an execution permit and does not authorize provisioning a
billable Render Background Worker.

## Identity and fail-closed gates

- Staging web service: `srv-dbm7dvc9v7es7393g70g`.
- Production service: `srv-dadn07eq1p3s73eccau0` (explicitly denied).
- A dedicated Render Background Worker must have its own exact Render service
  ID and set `VORNEQ_AI_IMAGE_WORKER_SERVICE_ID` to that ID.
- The worker must be `VORNEQ_ENV=staging`, `DEBUG=False`,
  `VORNEQ_AI_IMAGE_ENABLED=true`, provider **mock**, paid calls **false**,
  with a matched SHA, an owner authorization string, and a narrow user allowlist.
- Missing or mismatched service, Production ID, wrong SHA, emergency stop,
  paid flag and paid provider all deny Worker execution.
- The web API identity is not inherited by the Worker. Its queue selects only
  `provider=mock` jobs; paid jobs are never claimed.
- The Worker uses PostgreSQL as its queue authority. Redis is advisory.

## Before live Staging Mock E2E and any Worker provisioning

1. Obtain a separately recorded and strictly scoped owner authorization for
   Staging-only Mock API → PostgreSQL queue → worker-once → private R2 object →
   signed owner URL → deletion. No paid OpenAI calls.
2. Verify current Staging SHA, migration 0004, R2 private storage and database
   identity, and get fresh backup/recovery evidence.
3. Test with one explicitly disposable identity and job, bounded quotas and
   isolated cleanup. Never process unrelated queued jobs or auto-retry an
   uncertain job. Cleanup failures need incident investigation.
4. Do not open the web feature globally. Separate service provisioning may
   incur charges; obtain explicit service/cost approval before creating it.
5. No production modification, paid image calls, unattended worker loop,
   or live E2E is authorized by this code-only branch.

## No-network tests

`python manage.py test apps.ai_core.tests.test_image_worker_identity_v1`
