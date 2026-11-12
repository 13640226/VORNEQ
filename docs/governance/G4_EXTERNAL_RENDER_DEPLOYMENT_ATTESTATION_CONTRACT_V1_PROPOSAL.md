# VORNEQ — G4 External Render Deployment Attestation Contract V1 (PROPOSAL)

**Document ID:** P0_VORNEQ_G4_EXTERNAL_RENDER_DEPLOYMENT_ATTESTATION_CONTRACT_V1_PROPOSAL  
**Date:** 2026-11-12  
**Repository:** 13640226/VORNEQ  
**Baseline:** `3f723533623df5c3f932ca44e1384da0c82fdebf` (main)  
**Authority:** DESIGN_PROPOSAL_ONLY / NOT_ADOPTED / NO_EXECUTION_AUTHORIZATION  
**Tracking:** Issue #448, PR #584.

## 1. Purpose and historical incident

The current `scripts/deploy_control.py::preflight()` production gate accepts staging evidence only when a GitHub Deployment in environment `staging` has a successful status for the exact SHA. Render API deployments are not automatically GitHub Deployments.

A real staging release was observed:
- Workspace `tea-da71asm1egvs73f1fec0`
- Service `srv-dbm7dvc9v7es7393g70g`
- Deploy ID `dep-dbqio0uc6qcc73ffbrcg`
- Commit `3f723533623df5c3f932ca44e1384da0c82fdebf`
- Trigger `api`; started `2026-11-12T03:01:23.916622Z`, finished `2026-11-12T03:02:30.075889Z`
- Render returned `live`, matching start/end events and successful build; staging `/health/` reported HTTP 200, matching release, and database/cache/storage `ok`
- Authenticated GitHub API returned **zero** staging Deployment objects for this SHA
- The AI assistant initiated the Render API deploy, rather than the owner dispatching the authorized G4 workflow. This is an explicitly recorded **G4 path deviation**.

**Immutable classification:** TECHNICAL_RENDER_LIVE_VERIFIED / HISTORICAL_G4_PATH_DEVIATION / PRODUCTION_HOLD. Do not retroactively certify or conceal that deviation.

## 2. Trust model

Keep three separate claims:
1. `OBSERVED_DEPLOYMENT` — independent technical evidence of the deployment's existence and state.
2. `AUTHORIZED_STAGING_EVIDENCE` — actual G4-controlled staging success, or an independently justified *prospective* policy exception that allows consideration of earlier technical evidence for a future decision.
3. `PRODUCTION_DEPLOY_AUTHORIZATION` — separate owner-issued, one-time, environment- and SHA-bound authorization, followed by an owner-initiated G4 workflow.

No one claim implies another. Neither a human-authored Markdown/JSON document nor a GitHub comment is proof of Render state. Conversely, Render credential principal/trigger is **not** proof of a specific human actor or of prior authorization.

The new alternative path is **disabled by default**. It cannot be enabled by the mere merge of code, by local tests or by the owner's general wish to deploy. Competent prospective adoption and trusted credential custody must be established first.

## 3. Acceptance controls (EXT-01..EXT-14)

| ID | Required verification | Fail-closed condition |
|---|---|---|
| EXT-01 | Pin repository, `staging` environment, workspace, trusted service ID | Wrong/unpinned tenant, resource or environment |
| EXT-02 | Authenticated **GET** from Render for exact deploy ID | User-provided JSON, screenshot or nonexistent ID alone |
| EXT-03 | Exact deploy ID, full 40-character SHA, service repo and `main` branch | Mismatch, short SHA, wrong repo/branch |
| EXT-04 | Render status `live`; record actual `trigger` unmodified | Deactivated, failed, queued, canceled, rollback or transitional state |
| EXT-05 | Parse UTC created/started/finished timestamps; `created <= started <= finished <= verified_at` | Missing/future/inconsistent timestamp |
| EXT-06 | Confirm this **deploy ID** is the newest live release for the exact service | Superseded/deactivated deploy, even if SHA matches |
| EXT-07 | Match provider events: `deploy_started`, successful `deploy_ended`; build event consistent when present | Missing/conflicting critical events |
| EXT-08 | Pinned HTTPS `/health/` returns 200, full release SHA, `status=ok`, DB/cache/storage `ok`; GET-only smoke test | Unhealthy, redirected to untrusted host, mismatch |
| EXT-09 | SHA belongs to `main`, required trusted checks passed on **merged SHA** | PR-only SHA, missing/failed required checks |
| EXT-10 | Distinguish Render trigger, credential principal, and independently verified human initiator | Missing/disguised unknown attribution or AI-triggered deviation |
| EXT-11 | Record verification time, verifier/source, Render evidence IDs, checks/health, digest and limits in a trusted immutable evidence object | Editable/assertion-only report, untrusted workflow or secret leakage |
| EXT-12 | Independently verify a valid, *prospective* exception scoped to deploy ID/SHA/service/staging and next-stage purpose, with authority, expiry and revocation | Missing/expired/edited/fake authority, historical relabeling |
| EXT-13 | Repeat authenticated provider reads, newest-live, health, SHA/checks and exception/revocation checks inside **Production trigger**; bind evidence ID/SHA | TOCTOU drift or replay |
| EXT-14 | Preserve owner-initiated workflow and separate `OWNER-AUTH-DEPLOY ... production @ <sha>`, unedited/unrevoked/unused/one-time | Wrong actor, authorization or reuse |

**All EXT-01..14 are PROPOSED, not implemented or verified.**

## 4. Evidence and prospective exception records

Technical evidence is populated **by a trusted verifier doing real provider reads**, never by an applicant's text. Schema:

```json
{
  "schema": "g4.render.external_evidence.v1",
  "repository": "13640226/VORNEQ",
  "environment": "staging",
  "render_workspace_id": "tea-da71asm1egvs73f1fec0",
  "render_service_id": "srv-dbm7dvc9v7es7393g70g",
  "render_deploy_id": "dep-dbqio0uc6qcc73ffbrcg",
  "commit_sha": "3f723533623df5c3f932ca44e1384da0c82fdebf",
  "render_trigger": "api",
  "render_status_at_observation": "live",
  "historical_execution": "AI_ASSISTANT_API_TRIGGERED",
  "historical_g4_path_compliance": "DEVIATION_PRESERVED",
  "verified_at": "REQUIRED_ACTUAL_UTC_TIME",
  "attestation_digest": "NOT_CREATED",
  "production_gate_eligibility": "BLOCKED_UNLESS_VALID_EXCEPTION"
}
```

This is a **schema example**, *not* a newly issued verified attestation. A separate prospective decision, if authorized at all, must bind exact deploy ID, SHA, service, purpose, approving authority, actual effective UTC time, expiry and revocation. The decision is not retroactive and must not claim the AI-triggered deployment was owner-dispatched.

Proposed decision marker (illustrative only):

```text
G4-EXTERNAL-STAGING-EXCEPTION <EXCEPTION-ID>
PR #584 | staging | SHA <FULL_SHA> | Render deploy <DEPLOY_ID>
PURPOSE: CONSIDER_VERIFIED_STAGING_EVIDENCE_FOR_FUTURE_PRODUCTION_PREFLIGHT
HISTORICAL_G4_DEVIATION: PRESERVED
EFFECTIVE_AT: <ACTUAL_PROSPECTIVE_APPROVAL_UTC>
EXPIRES_AT: <UTC>
AUTHORITY: <VERIFIED_PROVENANCE>
STATUS: NOT_GRANTED
```

## 5. Minimal future code change (subject to approval)

Do **not** implement this from the proposal alone. Later, on a separately authorized fixed-SHA branch:
- Keep existing `deployment_succeeded()`, `decide_deploy()`, `authorization_used()` and `trigger_hook()` semantics unchanged.
- Add an isolated read-only Render verifier with exact pinned service/workspace, authenticated API, no redirects to arbitrary hosts, strict timestamps, latest-live deploy ID and event/health/check validation.
- Add a narrow staging-evidence predicate: accept existing genuine G4 GitHub staging success; otherwise require an **enabled/adopted contract**, fresh independently re-fetched technical evidence, and a separately verified valid prospective exception. Never fall back silently.
- Use the *same* predicate for Production preflight and trigger-time revalidation. Enforce one-time binding and detect changes between jobs.
- Make only minimal changes to `.github/workflows/deploy.yml` if secure read-only credentials exist. Never place a broadly write-capable Render token in GitHub Actions. If least-privilege credentials or trustworthy exception authority are unavailable, STOP rather than weaken controls.
- Make no changes to `render.yaml`, databases, live services, rulesets, GitHub Deployment history, checks/statuses or actual credentials.

The historical `dep-dbqio0uc6qcc73ffbrcg` may remain technically verified yet **policy-blocked** until a valid *prospective* exception is established. No automatic whitelisting by deploy ID.

## 6. Required isolated negative tests

| Test | Scenario | Expected |
|---|---|---|
| NEG-01 | Wrong service/workspace/environment | DENY |
| NEG-02 | Missing/fake/ambiguous deploy ID | DENY |
| NEG-03 | SHA mismatch, abbreviated, off-main or PR-only | DENY |
| NEG-04 | Failed/deactivated/queued/canceled or superseded deploy | DENY |
| NEG-05 | Invalid/missing/future/reordered timestamps | DENY |
| NEG-06 | Missing/mismatched or contradictory Render events | DENY |
| NEG-07 | Health status/SHA/cache/DB/storage mismatch | DENY |
| NEG-08 | Unknown human operator or undisclosed AI-triggered path | DENY policy eligibility |
| NEG-09 | Render API auth failure/timeout/rate limit | DENY |
| NEG-10 | Caller-supplied `live` JSON without GET | DENY |
| NEG-11 | Missing/edited/revoked/expired/unauthorized exception | DENY |
| NEG-12 | Wrong/missing/edited/reused Production owner authorization | DENY |
| NEG-13 | New deploy between preflight and trigger; stale evidence | DENY |
| NEG-14 | Evidence/exception replay for different SHA/PR/service/run | DENY |
| NEG-15 | Untrusted GitHub status or PR-supplied verifier | DENY |
| NEG-16 | Real G4-controlled staging success | ACCEPT original path unchanged |
| NEG-17 | Verified external staging + valid prospective exception + fresh trigger revalidation | ALLOW **staging prerequisite only** |
| NEG-18 | PR #584 AI-initiated staging with no exception | TECHNICAL PASS / POLICY DENY |

Use mocked API responses for unit/negative tests. Do not call live Render or production DB in CI tests. Keep reviewer independence and source credentials separately verified.

## 7. Rollout gate and decision

1. Competent authority prospectively adopts the *concept* and approves scope, provenance, SC_07 requirements, credential custody and one-time exception rules. This proposal itself is **not approval**.
2. Only after that authorization implement/test in a separate fixed-SHA branch, with mocked negative tests and regression checks.
3. Review and official CI must pass; branch status alone does not constitute merge authorization.
4. A separately approved activation enables the **new** alternative predicate; default OFF remains until then.
5. Every future production deployment still needs owner-dispatched G4 workflow, a distinct SHA-bound Production owner authorization, and trigger-time revalidation. The earlier G4 deviation must remain visible.

```text
CONTRACT=PROPOSED / NOT_ADOPTED
EXTERNAL_ATTESTATION_CODE=NOT_IMPLEMENTED
PR584_RENDER_STAGING_DEPLOY=LIVE_VERIFIED / API_TRIGGERED
HISTORICAL_G4_DEVIATION=OPEN / PRESERVED
GITHUB_STAGING_DEPLOYMENT_FOR_SHA=NONE
COMPETENT_EXCEPTION=NOT_GRANTED
PRODUCTION_STAGING_PREREQUISITE=NOT_SATISFIED
PRODUCTION=HOLD
```

**Technical evidence is not retrospective authorization. A code commit is not policy adoption.**

References:
- https://github.com/13640226/VORNEQ/issues/448
- https://github.com/13640226/VORNEQ/pull/584
- https://api-docs.render.com/reference/retrieve-deploy
- https://api-docs.render.com/reference/list-deploys
