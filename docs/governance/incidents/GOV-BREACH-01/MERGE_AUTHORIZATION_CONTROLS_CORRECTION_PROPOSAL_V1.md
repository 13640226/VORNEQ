# GOV-BREACH-01 — Merge Authorization Controls: Correction Proposal V1

Status: PROPOSED / DOCUMENTARY_ONLY / NOT_IMPLEMENTED
Repository: 13640226/VORNEQ
Target branch: main
Related incidents: PR #467 and PR #468; GOV-BREACH-01-F02
Owner authorization: authorizes creation of this review PR only. Does NOT authorize merging or activating controls.

## Verified evidence and limits
- PR #468 received an APPROVED review from hamidrezaasadian7-boop at 2026-10-31T18:12:12Z and merged at 2026-10-31T18:16:22Z, merge commit 78934c43368e7115eac907839bdcc666bcecf7ce.
- Review approval did not constitute separate owner merge authorization; no such authorization was found in the examined conversation.
- Owner-provided screenshots show an active `main-protection` ruleset targeting `refs/heads/main`, with two branch rules. A screenshot of a local JSON document appears to show one required approval and pull-request-related settings; its provenance, effective current configuration, bypass actors, and historical configuration at merge time are NOT independently verified.
- A reviewer approval alone cannot establish compliance with the project-specific MERGE_GO gate.

## Non-negotiable authorization model
PROPOSAL != APPROVAL != EXECUTION_AUTHORIZATION != VERIFIED_EVIDENCE.
A GitHub APPROVED review is documentary/code-review evidence, never the owner authorization to merge.
STOP_340 and HARD_STOP remain ACTIVE. C02 and SC_07 remain OPEN_CRITICAL.
DATABASE_GO = MIGRATION_GO = MERGE_GO = DEPLOY_GO = NO.

## Proposed controls (not yet active)
1. **Pinned owner authorization artifact:** For each intended merge, require an explicit owner-issued decision bound to repository, PR number, exact head SHA, base branch, scope, expiry, incident status, and a unique decision ID. Default DENY; comments, labels and approval reviews are not sufficient authorization.
2. **Independent verifier and provenance:** Validate the decision against an owner-controlled trusted source independent of the PR author and ordinary reviewer. PR-controlled files, comments, labels, or status spoofing MUST NOT self-authorize.
3. **Required merge gate:** Design a non-bypassable (to the extent supported by the repository plan and GitHub product) required status check for `main` that evaluates the decision at the exact candidate head SHA and fails closed on missing, stale, revoked, conflicting, or unverifiable evidence. If GitHub cannot enforce non-bypassability, explicitly document the residual risk and prohibit relying on the check alone.
4. **Ruleset review:** Verify the live `main-protection` rule target, enforcement mode, required approvals, required status checks, and bypass actors through authorized read-only owner evidence; compare effective controls and plan limitations. Do not infer settings from a local JSON file.
5. **Separation of duties:** Reviewer approval and owner merge decision must be separately evidenced. Reviewers may request changes; their approval must never flip MERGE_GO.
6. **Fail-closed incident gate:** If STOP_340/HARD_STOP is active, merge gate verdict must remain DENY regardless of approvals or owner authorization artifacts until a separate, explicit incident-resolution authorization is verified. No automatic reopening.
7. **Audit trail:** Capture PR, head SHA, review ID, authorization ID, verifier verdict, actor, UTC timestamps, and resulting merge commit in a non-secret audit record. Do not expose credentials or tokens.
8. **Safe rollout:** First inspect existing ruleset and permissions; design/test the guard in an isolated non-production context with separate owner authorization; independently review; only then request separate approval for actual GitHub settings changes.

## Acceptance tests required before any future activation
- Missing authorization -> DENY.
- Reviewer APPROVED without owner authorization -> DENY.
- Authorization for different PR/head SHA/base -> DENY.
- Expired/revoked/unverifiable authorization -> DENY.
- STOP_340/HARD_STOP active -> DENY.
- PR-controlled forged authorization -> DENY.
- Bypass actor or unsupported protection capability -> documented unresolved risk, no PASS.
- Valid evidence must still not auto-merge or deploy.

## Evidence gaps
- Effective GitHub ruleset settings and bypass actors: NOT_VERIFIED.
- Historical ruleset settings at PR #468 merge time: NOT_VERIFIED.
- Merge initiating actor and independent authorization: NOT_VERIFIED.
- Runtime/database impact: UNKNOWN.

## Change boundaries
This PR adds only this documentary proposal. It does not modify `.github/workflows`, executable code, repository rulesets, permissions, Render, or databases. No guard is implemented or enabled by this PR.
No merge, deploy, migration, restart, or secret access is authorized.

FINAL_STATE = SAFE_HOLD / INCIDENT_INVESTIGATION_ACTIVE
