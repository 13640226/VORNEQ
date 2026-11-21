# VORNEQ Image Studio — Staging-only UI V1

**Scope: code only, default OFF.** Does not authorize Merge, Deploy, a Worker,
a database write, a real OpenAI request, Production access or a new paid release.

## Entry point and isolation

- Authenticated, allowlisted Staging actors only: \`GET /api/ai/v1/images/studio/\`.
- The link inside existing AI chat appears only for the same authorized actor.
- The independent \`VORNEQ_AI_IMAGE_UI_ENABLED\` flag defaults to **false**.
- UI gate also requires staging, \`DEBUG=False\`, the current SHA, owner binding,
  image feature gates, emergency-stop checks and provider gate (for OpenAI).
- Production always returns 404. No API or provider gate was weakened.
- Service flags currently remain OFF. **The successful one-use Paid Smoke does
  not authorize a general user-facing paid feature.**

## Client behavior

- Existing same-origin POST and owner-scoped GET endpoints; no browser OpenAI API.
- Confirmation checkbox and cost/uncertainty disclaimer before each submission.
- Generates one browser UUIDv4. At most one POST per page; **no automatic POST
  retry even on timeout, bad HTTP status or invalid JSON**.
- GET status is user-triggered, never sends an image generation request.
- Shows queued, running, completed, failed or uncertain safely. Signed URL
  displayed only if HTTPS, without referrer. No localStorage/sessionStorage,
  analytics, secret values, log of original prompt or job ID.
- Accessible, responsive Persian / German / English copy, Persian RTL support.
- A page reload deliberately loses the in-memory request ID and does **not**
  retry or recover it. Users must reconcile any uncertain result before a
  new request. This is a limitation, not an assurance against repeat charges.

## Operational blockers before any Staging activation

1. Separate, audited owner decision for this **UI feature** tied to current SHA,
   allowlisted user(s), service, budget, rate limits and expiry.
2. Independent production-code review and CI tests. Migration 0004 already
   applied in Staging; **do not repeat it**.
3. A separately authorized persistent worker to actually process UI-queued
   jobs. Existing Mock E2E and Paid Smoke were one-off synchronous runs;
   enabling the UI alone **does not** create a Worker.
4. Confirm private R2 and signed URL, image Ledger account, provider billing,
   emergency-stop behavior, request/day caps, and cost reconciliation.
5. Owner approval for paid requests *outside* the completed one-use smoke.
6. Controlled Staging deployment, read-only preflight, limited audience smoke.
   Do not switch on the UI or paid gates via this PR.

## Tests

\`python manage.py test apps.ai_core.tests.test_image_studio_ui --noinput\`

The tests use Django's test client and static source checks: no real OpenAI,
R2 or live database writes. Also run the existing image generation tests.

**Status: CODE_ONLY / NOT_DEPLOYED / NO_GO_FOR_GENERAL_PAID_UI.**
