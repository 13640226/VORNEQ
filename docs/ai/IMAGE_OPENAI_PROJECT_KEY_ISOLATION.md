# Dedicated OpenAI project key for paid Staging images

Status: **code-only readiness; PAID_SMOKE_NO_GO**. No live API calls or billing in this change.

## Explicit isolation contract

- Chat retains `OPENAI_API_KEY` unchanged.
- Paid image generation reads **only** `VORNEQ_OPENAI_IMAGE_API_KEY` from the Render Staging process environment.
- There is **no fallback** to the chat key. Missing, empty or whitespace-only image key keeps the paid image gate closed. The SDK is not constructed in this state.
- Both the pre-moderation request and the image generation request use the same dedicated image-project SDK client.
- The value is never logged, printed, committed or returned by the preflight; only a boolean is checked.
- Mock image generation and unrelated chat API code remain unchanged.

## OpenAI project setup (owner-managed)

The owner has created OpenAI project `vorneq-staging-images`, with an enforced
USD 5 monthly spend limit, notifications at USD 1 and USD 5, and a dedicated
service-account key that expires 2026-12-20 (based on owner's dashboard evidence).
This is **not** proof that runtime is configured with that key.

Store the new secret in **Render Staging only**, under the exact name
`VORNEQ_OPENAI_IMAGE_API_KEY`; do not replace `OPENAI_API_KEY` or copy it
to Production. Choose minimally sufficient Project permissions for Moderations
and Images. Project spend limits may be enforced with some delay.

## Operational safety

Keep both service gates closed until independent owner authorization:
```text
VORNEQ_AI_IMAGE_ENABLED=false
VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=false
```
After a separately approved Staging deploy and secret configuration, run only
the default READ-ONLY preflight from
`run_staging_image_paid_smoke_once --expected-sha <EXACT_SHA>`.
Require `image_openai_key_present PASS` and all other required checks.
A successful preflight does **not** grant permission for paid smoke; that
requires a fresh, one-use owner release, valid backup, cost caps, and a
separate decision about the Ledger account's Emergency Stop.

Offline regression tests fake the SDK and check:
- Image requests use the dedicated key, never the chat key.
- A chat key on its own cannot enable the paid-image gate.
- Missing/blank image key fails closed before any paid request.
- The preflight reports missing image-key configuration without exposing it.

No migration, Ledger write, paid OpenAI call, or Production change is part of
this source-code change.
