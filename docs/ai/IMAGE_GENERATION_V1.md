# VORNEQ Image Generation V1 — Mock-first, default-off

Baseline: main 28672758efdc5fd7a7d49a23fc443eba9a4a7d02, 19 November 2026.

Scope: isolated feature implementation in apps/ai_core. No merge, no deployment, no real provider request, no live migration and no secret changes.

## Official API and model

Official reference: https://developers.openai.com/api/reference/resources/images/methods/generate
Image guide: https://developers.openai.com/api/docs/guides/image-generation
Prices: https://developers.openai.com/api/docs/pricing

OpenAI currently supports gpt-image-2, gpt-image-2.5-flare, gpt-image-2.5-sunburst, gpt-image-2.6-flare and gpt-image-2.6-sunburst.
Default image model (explicit, configurable): gpt-image-2.6-flare.
The Images API call uses one output, quality low, size from an allowlist, PNG and built-in automatic moderation. An additional omni-moderation-latest prompt check is performed before image generation.
OpenAI standard pricing for GPT-Image-2.6-Flare: image output $30/1M tokens, text input $5/1M tokens. Cost is not fixed per picture. This should be independently rechecked before any paid activation.

## Interfaces

POST /api/ai/v1/images/jobs/
Content type: application/json. Requires authenticated actor + CSRF + an enabled separate feature gate. Example JSON:
{"request_id":"e2b7053d-6e74-4dc9-b7cc-56c22de3ed1c","prompt":"An illustrated Persian garden","size":"1024x1024"}

GET /api/ai/v1/images/jobs/{job_id}/
Returns owner-only status and a signed storage URL after successful completion. Never returns a prompt or object key. Idempotency is tied to the client UUID and prompt digest. Replays never start another call.

Job states: queued, running, completed, failed, uncertain. Claimed jobs are NEVER automatically retried because the provider may charge before an interruption.

Durable queue authority: PostgreSQL AIImageJob, AIImageDailyQuota tables. Redis cache notification is optional/advisory. A separately deployed Render Background Worker would run:
python manage.py run_image_jobs --loop
No worker is created or started by this PR.

The mock provider returns a synthetic placeholder without network access. A real Images API adapter is implemented but cannot be invoked unless all independent paid gates are explicitly enabled. Tests mock OpenAI SDK construction to detect accidental use.

## Security and privacy

Feature is OFF in all environments by default and is not activated by the existing chat flags. Production is deliberately blocked in V1 even if misconfigured. Staging requires exact Render service ID, exact commit SHA, separate owner reference, allowlisted user, DEBUG false and emergency stop OFF.

Submitter is authenticated; cross-user job access is denied, URL is owner-bound, one request per minute and per-user/global daily caps are enforced inside database transactions. All errors returned to callers are generic; exceptions, API keys and original prompts are never logged by this capability. Prompts are cleared from job rows at terminal completion.

Image objects require a separate PRIVATE S3/R2 storage alias. Do not use Render ephemeral local disk. Storage URLs are signed and never public. PNG bytes carry a visible AI-generated/AI-mock watermark, and JSON explicitly labels mock previews. Verify label clarity and a privacy/retention policy before public launch.

## Ledger and monetary cap

The existing prepaid chat Ledger is model-specific; its account must never be reused for image models. Real image jobs require a dedicated BudgetAccount in the SAME ai_ledger PostgreSQL database, using VORNEQ_AI_IMAGE_LEDGER_ID different from chat's UUID, with matching approved model ID and correct image token prices. Reserve before any external call, settle on valid usage, otherwise keep reserved / uncertain. Never silently refund or retry.

A conservative, separately verified VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND is required. This is not a guaranteed provider price upper bound: budget monitoring, independent provider account spend caps and finance reconciliation are required before live image generation.

**Settlement acknowledgment (V1.1):** `ai_ledger.service.settle()` returns `finalized` or `uncertain` only after its transaction commits; it returns `None` on failure or if already settled. Existing text chat callers remain compatible because they do not depend on its return value. A paid image job may be `completed` and expose its signed URL **only** after an explicit `finalized` acknowledgment. Missing/invalid usage, failed or ambiguous settlement, and an unexpected settlement exception leave the image job `uncertain`, with its prompt removed and any private image object reference held for manual reconciliation. Neither the provider nor failed settlements are automatically retried. A crash after provider execution may still leave a `running` job requiring manual reconciliation; the Worker intentionally never retries it.

## Configuration (all default safe)

VORNEQ_AI_IMAGE_ENABLED=false
VORNEQ_AI_IMAGE_PROVIDER=mock
VORNEQ_AI_IMAGE_MODEL=gpt-image-2.6-flare
VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=false
VORNEQ_AI_IMAGE_AUTHORIZED_SHA=
VORNEQ_AI_IMAGE_OWNER_AUTH=
VORNEQ_AI_IMAGE_ALLOWED_USER_IDS=
VORNEQ_AI_IMAGE_LEDGER_ID=
VORNEQ_AI_IMAGE_OUTPUT_TOKENS_BOUND=0
VORNEQ_AI_IMAGE_DAILY_CAP_MICROUSD=0
VORNEQ_AI_IMAGE_DAILY_MAX_REQUESTS=3
VORNEQ_AI_IMAGE_GLOBAL_DAILY_MAX_REQUESTS=10

For an explicitly configured private bucket (none provisioned here):
VORNEQ_IMAGE_S3_BUCKET
VORNEQ_IMAGE_S3_ENDPOINT_URL
VORNEQ_IMAGE_S3_ACCESS_KEY_ID
VORNEQ_IMAGE_S3_SECRET_ACCESS_KEY

## Migration / deployment NO-GO

Migration ai_core.0004_image_generation_job_v1 is source code only. It has NOT been executed on Staging/Production. Apply only after DB identity, fresh verified restore evidence and an independent one-time permit.

This PR does not touch existing chat, AI key, text-ledger account, Render config, production database, or release processes.

## Test boundaries

Development tests use a disposable SQLite/PostgreSQL test database and in-memory storage. No real OpenAI calls. Minimum:
python manage.py test apps.ai_core.tests.test_image_generation_v1 --noinput

Review and test independently before activating even the mock Staging service. Additional blockers before paid staging: output-token price estimate validation, idempotency and uncertainty reconciliation, signed R2 storage verification, moderation evaluation, cost approval, and explicit owner permit. No Production enablement is provided in V1.
