# OWNER-DEC-PR545-ISOLATED-RUNNER-PILOT-V1 — Conditional Owner Decision Draft

Date: 2026-11-06
Repository: 13640226/VORNEQ
PR: #545
Status: PROPOSED / OWNER_FINAL_CONFIRMATION_PENDING / NO_EXECUTION_AUTHORIZATION
Authority references: Issue #340 comments 6681771088, 6681819991, 6684486039
Technical references:
- docs/security/PR545_FAIL_CLOSED_EGRESS_DESIGN_V1.md
- docs/security/PR545_ISOLATED_RUNNER_TECHNICAL_SPEC_V1.md
- docs/security/PR545_ISOLATED_RUNNER_PILOT_LIMITED_AUTHORIZATION_REQUEST_V1.md

## 1. Proposed decision
The owner may consider a **separately authorized, time-limited, nonproduction pilot** of an ephemeral isolated GitHub Actions runner and externally enforced fail-closed egress gateway. This document only establishes the decision criteria and does not authorize provisioning, execution, GitHub settings changes, workflow migration, merge, deploy or any other infrastructure mutation.

## 2. Target infrastructure (must be filled and independently verified before approval)
- Provider / cloud account: NOT_SELECTED
- Project / resource group: NOT_SELECTED
- Region: NOT_SELECTED
- Network / subnet identifiers: NOT_SELECTED
- External firewall / proxy owner and administrative boundary: NOT_VERIFIED
- Runner registration model / runner group / label: NOT_SELECTED
- Immutable runner image digest: NOT_SELECTED
- Public endpoint inventory and GitHub control-plane bootstrap paths: NOT_VERIFIED
- Resource deletion and evidence-retention locations: NOT_SELECTED

No existing Render production/staging/DR resource may be reused for this pilot.

## 3. Cost and time ceiling (mandatory decision fields)
- Maximum total pilot spend, currency included: OWNER_TO_SET
- Maximum pilot runtime (hours): OWNER_TO_SET
- Automatic expiration / destruction time (UTC): OWNER_TO_SET
- Cost alert threshold and payer: OWNER_TO_SET
- Resource cleanup owner and verification method: OWNER_TO_SET
Missing values block approval; no default budget, time or billing authorization is implied.

## 4. Actor and authorization boundary
- Proposed executor identity: NOT_SELECTED
- Proposed independent security reviewer identity: NOT_VERIFIED
- Owner approval must bind executor, resource identifiers, network policy version, exact tested artifacts and immutable commit SHA, approved test matrix, validity window and rollback.
- Historical reviewer comment by hamidrezaasadian7-boop is documentary only; SC_07 independence is not established.
- Owner's prospective removal of blanket development holds in Issue #340 does not provide target-specific execution authorization or retroactive charter compliance.

## 5. Permitted actions ONLY after separate explicit owner approval
- Provision exactly one short-lived, nonproduction runner and separately controlled default-deny egress gateway in a dedicated isolated network.
- Conduct narrowly scoped synthetic connectivity and publicly sourced dependency/advisory tests using no operational secrets or tenant data.
- Record redacted gateway decisions, runner identity, SHA, timestamps, test results and resource cleanup evidence.
- Terminate the pilot and remove its ephemeral resources within the approved window.

## 6. Explicitly prohibited actions
- Any production/staging/DR database route, SQL, migration, backup/restore, or data export.
- Any operational secrets, Render tokens, GitHub Actions secrets, tenant/customer data, production volumes or persistent production networks.
- Any production deployment, PR merge, product release, workflow switch, branch protection or ruleset relaxation.
- Any fallback to open bridge networking, unrestricted NAT, direct DNS, raw-IP internet access, or IPv6 bypass.
- Any use of privileged containers or untrusted fork PR code on the pilot runner.

## 7. Mandatory security gates
G1: Read-only inventory of existing runners, network policy and control-plane requirements.
G2: Documentary review of exact destination allowlist, external enforcement, DNS/IPv6 and bypass controls.
G3: Owner decision on all fields in sections 2–4; explicit scoped execution authorization only after governance reconciliation.
G4: Before test execution, verify the gateway is externally administered, default deny and isolated from DB/secrets.
G5: Positive tests: approved wheel acquisition with hashes; offline install; approved advisory lookup.
G6: Negative tests: forbidden domain, raw IP, direct IPv4/IPv6, DNS/DoH/DoT, QUIC/UDP443, forbidden CONNECT, redirect, proxy outage, gateway outage, metadata/internal destinations, policy tampering.
G7: Independent evidence review, exact SHA and runner identity reconciliation; no acceptance from CI green alone.
G8: Verified resource teardown, cost accounting, and preservation of sanitized evidence.

## 8. Stop and rollback
Immediately STOP, quarantine runner, deny all egress, and report if any secret or internal route is exposed, gateway policy cannot be attested, unexpected traffic succeeds, test scope expands, evidence is missing, or spend/time ceiling is reached. Destroy only pilot resources after separately scoped authorization. Never alter production controls or silently revert to unrestricted internet.

## 9. Authority and conflict assessment
Issue #340 comment 6684486039 declares prospective removal of blanket holds for ordinary development but explicitly preserves target-specific authorization and sensitive-runner safeguards. Issue #340 comment 6681771088 records unrecovered original charter and unresolved operational authority. Thus:
- DOCUMENTARY_PREPARATION = PERMITTED within current read-only scope
- PROSPECTIVE_OWNER_POLICY = RECORDED
- HISTORICAL_CHARTER_CONFORMITY = NOT_VERIFIED
- PILOT_EXCEPTION_AUTHORITY = NOT_ESTABLISHED
- PILOT_EXECUTION_AUTHORIZATION = NOT_GRANTED
- C02 = OPEN_CRITICAL
- SC_07 = OPEN_CRITICAL
- GOV_BREACH_01 = OPEN
- MERGE / DEPLOY / DB / SECRETS = NO_GO

## 10. Required next owner decision
Owner must explicitly select:
A — Accept this as a DOCUMENTARY decision framework only (no execution).
B — Return for correction.
A future execution decision must be a distinct instrument with completed infrastructure, cost, duration, actors, exact resources and evidence. Silence or a GitHub review does not grant execution authority.

FINAL_STATE: OWNER_DECISION_DRAFT_READY / PILOT_BLOCKED / SAFE_HOLD / NO_GO
