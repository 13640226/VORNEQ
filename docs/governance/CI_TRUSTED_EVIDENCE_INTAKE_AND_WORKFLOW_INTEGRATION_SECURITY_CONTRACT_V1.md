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
