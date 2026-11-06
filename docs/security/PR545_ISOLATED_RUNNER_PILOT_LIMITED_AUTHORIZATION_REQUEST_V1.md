# P0_VORNEQ_PR545_ISOLATED_RUNNER_PILOT_LIMITED_AUTHORIZATION_REQUEST_V1

Date: 2026-11-06
Repository: 13640226/VORNEQ
PR: #545
Status: PROPOSED / DOCUMENTARY_REVIEW_ONLY / OWNER_EXECUTION_AUTHORIZATION_NOT_GRANTED
References:
- docs/security/PR545_FAIL_CLOSED_EGRESS_DESIGN_V1.md
- docs/security/PR545_ISOLATED_RUNNER_TECHNICAL_SPEC_V1.md
- PR #545 documentary review by hamidrezaasadian7-boop, comment 6691403840

## 1. Purpose
Request consideration of a tightly bounded nonproduction pilot of an ephemeral isolated runner and externally enforced fail-closed egress gateway. This document is a proposed authorization instrument, NOT an authorization to provision, run, migrate, merge, or deploy.

## 2. Proposed permitted scope — only after separate owner approval and governance clearance
- Inventory current runner groups, network topology, gateway ownership and required control-plane endpoints by STRICT_READ_ONLY inspection.
- Prepare a nonproduction pilot deployment plan with exact resource names, cloud account, region, cost ceiling, duration, and deletion procedure.
- Subject to a separate explicit, time-limited owner decision referencing this exact document revision, provision one ephemeral nonproduction runner in a dedicated isolated subnet with independently administered default-deny egress gateway.
- Run only synthetic positive/negative connectivity checks against approved test endpoints and non-sensitive public package/advisory endpoints. Collect redacted policy, deny logs, timestamps, runner identity, immutable image digests, and reproducible commands.
- Stop immediately on any unexpected outbound route, secret exposure, policy mismatch, missing evidence, or gateway failure.

## 3. Strict exclusions
- NO access to production, staging, or DR databases; NO SQL or migrations.
- NO access to production/staging secrets, GitHub Actions secrets, Render credentials, service tokens, or customer/tenant data.
- NO changes to main branch protection, required checks, repository permissions, organization runner policies, or governance locks.
- NO change to .github/workflows/security.yml or existing runner assignment as part of this document.
- NO commit of executable infrastructure, PR merge, release, or deploy under this authorization request.
- NO direct public egress fallback, privileged workloads, shared persistent runners, or untrusted fork-PR code on pilot runner.

## 4. Mandatory preconditions for any future pilot execution
A. Independently verify the authoritative HARD_STOP exception/authorization mechanism; if unresolved, pilot execution remains BLOCKED.
B. Obtain explicit owner approval specifying exact resources, identity, cloud/project, region, cost cap, TTL, test matrix, reviewer, and rollback.
C. Independently review the network gateway design and exact allowlist; independence of hamidrezaasadian7-boop must not be presumed (SC_07 remains OPEN_CRITICAL).
D. Demonstrate gateway administration is outside the runner compromise boundary and no unrestricted NAT/direct DNS/IPv6 bypass exists.
E. Confirm no database routes, no operational secrets, no production data, and no automatic deployment hooks.
F. Obtain separate approval before creating any paid resource or changing infrastructure.

## 5. Pilot evidence and acceptance
Required evidence: inventory snapshot, reviewed topology, policy revision and default-deny proof, runner image digest, runner lifecycle/TTL, positive and negative test logs (direct IP, DNS/DoH, IPv6, UDP/443, forbidden CONNECT, redirects, proxy outage, internal/metadata targets), exact test commands, UTC timestamps, cost, cleanup evidence and independent review.
A passing CI job or documentary acceptance alone is NOT sufficient.

## 6. Stop / rollback
On deviation: stop the pilot, isolate and destroy the ephemeral runner, preserve sanitized evidence, keep external gateway default-deny, and report the incident. Never relax production network restrictions or fall back to open egress. Deletion of a pilot resource requires the separately approved pilot scope.

## 7. Review and decision states
DOCUMENTARY_REVIEW = REQUESTED
OWNER_DECISION = PENDING
PILOT_PROVISIONING = NOT_AUTHORIZED
NETWORK_POLICY_CHANGE = NOT_AUTHORIZED
CI_WORKFLOW_MIGRATION = NOT_AUTHORIZED
COMMIT / MERGE / DEPLOY = NOT_AUTHORIZED_BY_THIS_DOCUMENT
HARD_STOP = UNRESOLVED
C02 = OPEN_CRITICAL
SC_07 = OPEN_CRITICAL
GOV_BREACH_01 = OPEN
FINAL_STATE = AUTHORIZATION_DRAFT_READY / SAFE_HOLD / NO_GO

## 8. Reviewer questions
1. Does the proposed scope truly avoid operational credentials, databases and production network routes?
2. Can the external gateway enforce default-deny even if the runner host is compromised?
3. Are fork PRs and GitHub Actions control-plane bootstrap isolated safely?
4. Are cost, TTL, cleanup, failure and rollback criteria sufficient?
5. What documentary corrections are required before the owner can consider a separate execution authorization?

No response to this request may be interpreted as permission to execute the pilot.
