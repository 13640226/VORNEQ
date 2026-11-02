# VORNEQ — Required Check Dispatch / Skip-CI Contract V1 (PROPOSED)

Status: DOCUMENTARY_PROPOSAL / NOT_IMPLEMENTED
Date: 2026-11-02
Scope: PR #496 and future pull requests; no workflow/ruleset changes authorized by this document.

## Verified evidence
- Main ruleset 22881408 requires test (3.11), test (3.12), dependencies, postgres-backup-restore.
- Names match jobs in ci.yml, security.yml and backup-restore.yml; each declares pull_request targeting main.
- PR #496 head 4ce3cfb7c4390fa7ee0ccd0cd5f806decd966dcb has zero reported workflow runs and check runs.
- Head commit message contains [skip ci]. This is a plausible dispatch suppression mechanism, not an independently observed dispatch decision.

## Proposed durable technical correction — gated
1. Define a pre-commit or pre-PR check preventing skip directives on branches targeting main *where required checks are expected*. Do not introduce bypass or fake success checks.
2. Keep required checks enforced; do not weaken main-protection ruleset to clear a documentary PR.
3. Design an isolated documentary-only verification job only after independent security review; avoid unsafe install scripts, privileged runners, secrets, DB, and network egress. A documentary job must not masquerade as the four operational required checks.
4. For existing skipped PRs, require explicit authorization before any new commit or rerun. No automatic replay is approved.
5. Before implementation verify GitHub Actions workflow enablement, trigger suppression, permissions, check-suite provenance and branch/ruleset behavior.
6. Validate proposed changes using static review first; runtime CI requires separate explicit owner authorization and closed applicable security gates.

## Acceptance gates
- Exact check-context-to-job mapping documented and preserved.
- No bypass of protected branch or Required Checks.
- No new auto-triggering workflows without owner approval and CI security acceptance.
- Explicit audit trail for skipped workflows and unresolved expected checks.
- Independent reviewer and security evidence required before merge.

## Governance
STOP_340=ACTIVE; HARD_STOP=ACTIVE; C02=OPEN_CRITICAL; SC_07=OPEN_CRITICAL; CI487_03=OPEN_BLOCKER; CI_GO=NO; MERGE_GO=NO; DEPLOY_GO=NO; FINAL_STATE=SAFE_HOLD/NO_GO.
