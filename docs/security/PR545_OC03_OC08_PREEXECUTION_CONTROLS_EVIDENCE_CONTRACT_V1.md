# PR545 OC-03..OC-08 Pre-Execution Controls and Evidence Contract V1
Date: 2026-11-06
Repository: 13640226/VORNEQ
PR: #545
Scope: DOCUMENTARY_ONLY / NO_EXECUTION
Status: PROPOSED / REVIEW_PENDING / NOT_AUTHORIZED
References:
- docs/security/PR545_OC01_OC02_TWO_NODE_GATEWAY_COST_FEASIBILITY_V1.md
- docs/security/PR545_OC01_OC08_REMEDIATION_AND_PROVIDER_COST_V1.md
- Issue #340 authority comments 6681771088, 6681819991, 6684486039
- PR #545 reviewer comment 6692216857

## OC-03 — Time limit, independent stop and cleanup
Proposed maximum active tests: 2 hours; maximum resource lifetime: 4 hours from first provision. Neither is owner-approved as an operational window.
Before any authorization record absolute start and expiry timestamps in UTC, responsible operator, independent stop controller and cleanup verifier. An external control plane, outside the runner/gateway administrative boundary, must terminate runner registration, cloud instances, gateway, private network and billable IPs at expiry. Test that termination survives runner compromise, host shutdown and CI job failure. A job timeout, billing alert or operator reminder is not sufficient.
Immediate abort conditions: unexpected route/egress, secret exposure, DB connectivity, budget risk, missing logs, policy drift, gateway outage or failure of stop controller.
Acceptance evidence: design of independent expiration, deletion inventory, timestamped cleanup checklist, billing reconciliation. Current state: NOT_VERIFIED.

## OC-04 — Named actors and segregation of duties
Decision owner: 13640226, documentary owner only.
Executor: NOT_APPOINTED.
Cloud account owner / payer: NOT_APPOINTED.
External gateway policy administrator: NOT_APPOINTED.
Independent reviewer: NOT_APPOINTED / INDEPENDENCE_NOT_VERIFIED.
Cleanup verifier: NOT_APPOINTED.
Each actor must be identified by account, role, scope, authorization provenance, separation-of-duty matrix and revocation procedure. No self-approval assumption. Account ownership must be verified before any spending or API access.
Current state: RESPONSIBILITIES_PENDING.

## OC-05 — Fail-closed security acceptance
Candidate: Hetzner two-node topology, NOT proven compliant.
Security properties: deny by default for both IP families; runner has no public interface; provider API and cloud control-plane privilege unavailable to runner; gateway policy administered independently; exact FQDN/IP/port allowlist with TTL and DNS pinning considerations; prevent direct-IP, IPv6, DNS, DoH/DoT, UDP/443, HTTP CONNECT, redirect, metadata, private-network, internal and NAT bypass; deny on gateway outage and logging failure; no routes to Render production/staging/DR, databases, tenant networks or operational secrets.
Provider firewall caveat: Hetzner Cloud Firewall does not by itself prove enforcement for metadata, DNS and private cloud networking. Explicitly document and independently resolve all exemptions; if not possible, mark architecture REJECTED and do not run.
Required negative and positive acceptance criteria must be defined before any operational test. No runtime proof exists.
Current state: DESIGN_INCOMPLETE / FAIL_CLOSED_NOT_VERIFIED.

## OC-06 — Authority and governance validity
Issue #340 prospective removal of blanket holds for ordinary development is not specific authorization for sensitive pilot infrastructure. Historical charter precedence is unresolved. Owner's prior Option A is documentary acceptance only.
Required: cite applicable current owner governance decision, reconcile conflicts and security exceptions, explicitly list allowed and prohibited operations, provider resources, financial ceiling, actor, window, evidence and rollback in a distinct target-specific owner decision. Do not use this document as an exception or execution authority.
C02 OPEN_CRITICAL, SC_07 OPEN_CRITICAL, GOV_BREACH_01 OPEN; no closure claimed.
Current state: EXECUTION_AUTHORITY_NOT_ESTABLISHED.

## OC-07 — Independent reviewer eligibility
Reviewer identity, organization/account separation, prior authorship, financial and operational conflicts, exact source commit and scope must be recorded. Account hamidrezaasadian7-boop has submitted documentary comments but that does not establish SC_07 independence. Independent reviewer must have adequate read-only evidence access and must disclose limits. A formal GitHub APPROVED state on an older commit is not a current security clearance.
Current state: INDEPENDENCE_NOT_VERIFIED.

## OC-08 — Evidence and test acceptance matrix
Pre-execution evidence: immutable HEAD and file hashes; official pricing snapshot and total-cost worksheet; network diagram, exact cloud resource inventory and route table; runner/gateway image digests; signed allowlist/policy revision; actor approval and separation matrix; UTC window and independent stop design; detailed expected results for each test.
After separate authorization ONLY, positive tests: approved public hash-locked dependency download, offline install with no network, approved advisory lookup, narrowly controlled runner registration.
Negative tests: forbidden host/domain/IP (IPv4 and IPv6), DNS bypass/DoH/DoT, QUIC/UDP443, metadata, private and DB networks, proxy outage, policy edit, direct NAT/route bypass, redirects, unauthorized GitHub registration, gateway failure and timeout/forced cleanup.
For each case record test ID, source artifact SHA, command, expected result, actual result, UTC, observer, sanitized deny/allow logs, provider policy revision, pass/fail and incident link. Never put tokens or secrets in logs. No tests have been executed.
Final evidence: independent cleanup verification and final bill, token revocation and retained redacted logs.
Current state: TEST_PLAN_DEFINED / RUNTIME_EVIDENCE_ABSENT.

## Pre-execution acceptance gate
All of the following must be independently evidenced before any provisioning: exact cloud account/region/resources and total cost, externally enforced network topology, executor and payer, independent reviewer eligibility, owner-specific authority, stop controller, evidence plan and no-production/no-DB/no-operational-secret guarantees.
No gate may be inferred from document acceptance. If any remains unknown, pilot remains blocked.

## Documentary owner decision options
A: accept this OC-03..OC-08 contract for documentary review only, no execution.
B: return it for corrections.
Neither option permits spending, provisioning, firewall changes, runner registration, CI changes, DB/secrets, merge or deploy.

FINAL_STATE: OC03_OC08_DOCUMENTARY_CONTRACT_PREPARED / EXECUTION_NOT_AUTHORIZED / PILOT_BLOCKED / SAFE_HOLD / NO_GO
