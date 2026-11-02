# VORNEQ — Trusted GitHub Evidence Intake and Controlled Workflow Integration Security Contract V1

DOCUMENT_STATUS: DRAFT_FOR_INDEPENDENT_SECURITY_REVIEW
SCOPE: DOCUMENTARY_ONLY / NO_CI_EXECUTION / NO_WORKFLOW_MODIFICATION
PR: #498
STOP_340: ACTIVE
CI_GO / MERGE_GO / DEPLOY_GO: NO

## 1. Trust boundary
The offline preflight reads untrusted local JSON. Its `source`, `reported_total`, and `pagination_complete` fields are **assertions**, not cryptographic evidence. The preflight MUST NOT turn a clean scan into CI_GO or an accepted required status check. All results remain advisory until an independent trusted intake implementation is accepted.

## 2. Evidence collection contract (proposed, NOT implemented)
A dedicated read-only collector with a pinned GitHub repository and PR number MUST:
1. Fetch PR metadata and record HEAD SHA, base SHA, PR state, commit count and immutable request URLs.
2. Fetch **every** PR commit page (bounded page size, pagination until terminal page); compare unique count to PR metadata `commits`; reject missing, repeated, reordered, malformed or changing pages.
3. Fetch PR metadata again and reject any HEAD, base, commit count or PR-state drift during collection. Fail closed on pagination truncation, rate limits, timeout, auth failure, response ambiguity or >1000 commits.
4. Obtain the active branch Ruleset from GitHub independently; verify the required contexts and integration IDs. A local hardcoded context snapshot is only a drift detector.
5. Bind collected evidence to repo, PR, HEAD, base, observation time, request URLs, and a digest of canonical manifest bytes. Digest does not authenticate untrusted source.
6. Never collect secrets, tokens, environment variables, private DB credentials or unneeded user data. No external egress beyond allowlisted GitHub API endpoints.
7. Produce an explicit `EVIDENCE_UNKNOWN` when any independent check is unavailable. No synthetic SUCCESS statuses.

## 3. Skip semantics
For pull_request dispatch diagnosis, classify skip directives on the HEAD commit separately from historical commit messages. Historical directives are advisory, not conclusive proof of suppression. Check documented GitHub behavior and independently inspect Actions run/check-run evidence. Zero runs and a skip directive are strong correlation, not proof of sole root cause.

## 4. Controlled integration gate (proposed, NOT implemented)
- No workflow integration until a separate reviewed change and explicit owner authorization.
- No automatic `pull_request_target`, `workflow_run`, or elevated write token; minimum `contents: read` where required; pin third-party actions to immutable SHAs before execution.
- No untrusted PR code execution in a privileged context; no Docker socket mount; no secrets in PR jobs.
- Network egress allowlist and isolation must be independently verified, not inferred from YAML alone.
- The Django test job installs dependencies and executes application code; requires independent dependency/code-execution review.
- The dependency audit installs tooling; review package-install execution effects and dependency pinning.
- The backup/restore job uses a PostgreSQL service and shell scripts; verify isolation, exact DB identity, destructive-operation safeguards, credentials, and cleanup.
- Preserve all four required contexts: `test (3.11)`, `test (3.12)`, `dependencies`, `postgres-backup-restore`. Do not bypass, disable, rename or fake them.
- `[skip ci]` is present in the current PR HEAD; any future non-skip commit or trigger requires separate authorization because it may dispatch CI.

## 5. Acceptance criteria (all UNVERIFIED)
AC-01 Trusted complete paginated commit intake with HEAD/base stability.
AC-02 Independently fetched current Ruleset and context identity.
AC-03 Deterministic fail-closed handling of malformed, missing and drifting evidence.
AC-04 Separate HEAD/historical skip diagnosis and check-run correlation.
AC-05 Trusted path handling, size limits, no secret disclosure, no privilege escalation.
AC-06 Dependency install and untrusted code execution risks independently reviewed.
AC-07 PostgreSQL identity, isolation, destructive effects and cleanup independently reviewed.
AC-08 Third-party actions pinned and permissions/egress independently verified.
AC-09 Negative and adversarial test plan reviewed before any test execution.
AC-10 Independent reviewer approval and explicit owner authorization for a bounded trial.

## 6. Decision
CONTRACT = DRAFT_COMPLETED
IMPLEMENTATION = NOT_AUTHORIZED
AC_VERIFIED = 0/10
SECURITY_ACCEPTANCE = PENDING_INDEPENDENT_REVIEW
CI_GO = NO
MERGE_GO = NO
DEPLOY_GO = NO
FINAL_STATE = SAFE_HOLD / NO_GO


## 7. V1.1 static security review and corrections (2026-11-02)

REVIEW_SCOPE: DOCUMENTARY_SOURCE_INSPECTION_ONLY
REVIEWER_INDEPENDENCE: NOT_ESTABLISHED
VERDICT: CORRECTION_REQUIRED / NO_APPROVE
No test, workflow, GitHub Actions, migration, merge, deploy or runtime authorization is granted.

### Acceptance matrix — design presence is NOT verification
| AC | Design assessment | Evidence / unresolved gate |
|---|---|---|
| AC-01 | PARTIAL_DESIGN | Commit pagination must use a trusted API client; compare PR `commits` count, first/last commit, head, stable pagination and repeat metadata fetch; require authenticated response provenance; no trust in manifest assertions. |
| AC-02 | PARTIAL_EVIDENCE | Ruleset #22881408 currently exposes four required contexts and integration_id 15368; runtime effective protection, workflow enablement and all applicable overlapping rulesets remain unverified. |
| AC-03 | PARTIAL_DESIGN | Fail-closed for HTTP errors, truncation, SHA drift, JSON ambiguity, duplicate pages, rate limits, permission failures, redirects and empty results; tests not executed. |
| AC-04 | PARTIAL_EVIDENCE | HEAD skip directive and zero Actions/check runs observed for PR #498; sole causal mechanism not proved. Distinguish event type, workflow filters, disabled workflows and branch policy. |
| AC-05 | PARTIAL_DESIGN | File-descriptor controls do not authenticate parent directory, collector or data origin; require trusted cwd, immutable staging and strict non-secret diagnostics. |
| AC-06 | OPEN | `ci.yml` runs pip installs, Django checks, migrations drift and application tests; `security.yml` installs audit tooling. Dependency and arbitrary-code execution boundary unverified. |
| AC-07 | OPEN | `backup-restore.yml` uses PostgreSQL service, shell backup/restore and cleanup; runtime database identity, Docker privileges and destructive scope unverified. |
| AC-08 | OPEN | Actions use mutable version tags; permissions/egress/runner trust and full dependency chain not independently accepted. |
| AC-09 | PARTIAL_DESIGN | Negative/adversarial cases specified below; no test execution authorized. |
| AC-10 | OPEN_BLOCKER | No independently appointed reviewer or owner-approved bounded trial; owner-controlled accounts do not establish independent review. |

AC_VERIFIED = 0/10. Static observations do not close acceptance criteria.

### Mandatory evidence intake controls
- Pin repository owner/name, PR number, expected HEAD/base, endpoint host and API version. Record response status, pagination Link headers, request IDs and observation times without logging authorization tokens.
- Authenticate API transport and source; restrict token to least-privilege read-only access; never accept manifest claims as proof. Reject a PR whose metadata changes between before/after snapshots.
- Require complete commit pagination with deterministic sequence and a count equal to independently fetched PR metadata. For pagination ambiguity, concurrent mutation, or >1000 commits: UNKNOWN, not SUCCESS.
- Verify **all applicable** effective rulesets and branch protections, not only one pinned ruleset. If permissions prevent verification, report UNKNOWN.
- Inspect both workflow source at the relevant GitHub event ref and workflow state/enablement through authorized read-only evidence; missing endpoint access is UNKNOWN.
- Distinguish GitHub `pull_request` vs `push` vs `workflow_dispatch`; do not equate absence of check-runs with verified skip root cause.
- Bind evidence manifest digest to exact API responses, observed HEAD/base and immutable source references. A digest provides integrity against later accidental modification, not authenticity by itself.

### Workflow execution isolation gates
- A separate implementation PR MUST identify which workflow/job would invoke the collector, its triggering events, exact token permissions, runner isolation, environment/secrets exposure, dependency install effects and outbound network destinations.
- No privileged `pull_request_target`, no untrusted code checkout with write token, no Docker socket mount, no production/staging database secrets, and no implicit DB endpoint fallback.
- Pin external Actions by reviewed immutable full commit SHA; require provenance for dependencies, scripts and container images.
- Explicitly inventory shell scripts and indirect effects for backup/restore; assert isolated ephemeral PostgreSQL identity and prove it by independently reviewable evidence before execution.
- Do not modify required check names, weaken rulesets, manufacture success statuses or interpret the offline preflight as a required check.
- Any change to HEAD without `[skip ci]` may cause Actions dispatch; this requires explicit separate approval only after gates are accepted.

### Proposed negative and adversarial test plan (NOT EXECUTED)
T-01 Truncated pagination with self-consistent fake reported_total => UNKNOWN.
T-02 HEAD/base mutation between metadata snapshots => UNKNOWN.
T-03 Duplicate, reordered, invalid or missing commit => UNKNOWN.
T-04 Missing ruleset permission or conflicting applicable rulesets => UNKNOWN.
T-05 Symlink, untrusted parent path, oversized/invalid UTF-8/JSON => UNKNOWN.
T-06 HEAD skip directive => BLOCKED; historical-only skip => advisory UNKNOWN.
T-07 No workflow runs despite no skip => UNKNOWN, not PASS.
T-08 Dependency install, unexpected egress, Docker socket or DB identity mismatch => STOP.
T-09 Token/secret exposure or elevated permissions => STOP.
T-10 Unexpected workflow dispatch or non-ephemeral destructive side effect => STOP and incident review.

### Owner decision gate
CURRENT_STATE = SAFE_HOLD / NO_GO
CONTRACT_V1_1 = DOCUMENTARY_CORRECTION_COMPLETED / NOT_INDEPENDENTLY_ACCEPTED
INDEPENDENT_REVIEWER = NOT_APPOINTED_OR_NOT_VERIFIED
RUNTIME_TEST_AUTHORIZATION = NONE
CI_GO = NO
MERGE_GO = NO
DEPLOY_GO = NO
