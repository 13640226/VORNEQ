# Staging recovery after a manual Render deploy

A manual Render deploy can put a commit live without producing the owner-dispatched GitHub Actions deployment evidence required by `apps/ai_core/deploy_authorization.py`. The chat gate correctly fails closed. The official deploy preflight also correctly rejects replaying an SHA already live. **Do not** weaken either guard, fabricate deployment statuses, or turn off `VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS`.

## Safe recovery

1. Verify the actual Render Staging live SHA and service identity. Record the failed official workflow and confirm the chat gate is closed; no paid AI call is needed.
2. Prepare a **new reviewed commit** on `main` through a separate PR, with CI and security checks green. Do not reuse the manually deployed SHA. This recovery runbook and its regression test are one such auditable change.
3. Owner posts a fresh single-line `OWNER-AUTH-DEPLOY <new-id> staging @ <new-40-character-main-SHA>` in Issue #448. The authorization must be unedited, unrevoked and unused.
4. **Owner only** dispatches `.github/workflows/deploy.yml` on `main`, selects `staging`, and enters the exact new full SHA. Assistants do not dispatch this workflow.
5. Verify the preflight, deploy job, GitHub deployment evidence, Render live SHA, and health checks all succeed. Only then re-evaluate `trial_enabled()` and `is_chat_enabled()` as read-only checks.
6. If any check fails, stop and inspect evidence. Do not redeploy the old SHA, disable financial or emergency gates, or make paid provider requests to diagnose the failure.

Production requires its own independent authorization and is outside this recovery. The existing rejection of an already-live SHA is intentional and remains enforced.
