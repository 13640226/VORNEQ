# PR545 OC-01..OC-08 Remediation Plan and Provider Cost Evidence V1
Date: 2026-11-06
Scope: STRICT_READ_ONLY / DOCUMENTARY_ONLY
Status: PROPOSED / OWNER_SELECTION_PENDING / NO_EXECUTION_AUTHORIZATION
Reviewer comment: https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692000877
Previous matrix: docs/security/PR545_PILOT_RESOURCE_COST_TTL_AUTHORITY_MATRIX_V1.md

## OC-01 Infrastructure identity
CANDIDATE PROVIDER: Hetzner Cloud, Germany (Falkenstein or Nuremberg; exact location not selected). CANDIDATE RUNNER: CX23 x86, 2 shared vCPU / 4 GiB RAM. This is not a purchase or owner-approved choice.
Provider account, project, subnet, runner image digest, firewall/gateway topology, exact location, GitHub runner group, image provenance, billing payer = NOT_SELECTED / NOT_VERIFIED.
Production, staging, DR, Render resources and networks explicitly excluded. A separate nonproduction account/project is required.
Acceptance: inventory exact IDs, isolation, no DB routes, no operational secrets, documented bootstrap and independent network enforcement before execution decision.

## OC-02 Cost evidence and authorization
Official Hetzner price adjustment effective 2026-06-15: CX23 Germany 0.0088 EUR/hour excluding VAT and IPv4, 5.49 EUR/month excluding VAT and IPv4.
Source: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
German VAT-inclusive official price: 0.0105 EUR/hour, 6.53 EUR/month, excluding IPv4.
Source: https://docs.hetzner.com/de/general/infrastructure-and-availability/price-adjustment/
Four-hour compute estimate: 4 x EUR 0.0088 = EUR 0.0352 ex VAT; approximately EUR 0.042 inclusive VAT (rounding varies).
This is COMPUTE ONLY. IPv4, gateway VM or service, volumes, traffic overage, logs, backups, taxes and billing rounding are NOT QUOTED and must be added. Proposed EUR 10 total ceiling is NOT PROVEN SUFFICIENT and NOT APPROVED.
Cost controls: verify enforceable provider hard limits or separate prepaid containment; alerts are not hard stops. No spending authorization.

## OC-03 Time and cleanup
Proposed active test TTL 2 hours; total resource TTL 4 hours. Exact UTC start/end NOT_SET. Required: independently enforced expiry, tested kill switch, automatic teardown, deletion of runner registration and all ephemeral resources, independent cleanup evidence. Do not rely solely on a job-level timeout.

## OC-04 Actors
Owner decision: 13640226, documentary approval only.
Executor: NOT_APPOINTED.
Provider billing payer: NOT_APPOINTED.
External gateway administrator: NOT_APPOINTED, must be outside runner administrative compromise boundary.
Independent reviewer and teardown verifier: NOT_APPOINTED / INDEPENDENCE_NOT_VERIFIED. Reviewer comments from hamidrezaasadian7-boop do not close SC_07.

## OC-05 Network/security correction
Hetzner Cloud Firewall alone DOES NOT meet the proposed fail-closed contract: provider FAQ says metadata requests do not traverse the firewall; some Hetzner DNS/rescue traffic is always allowed; private cloud network traffic is not protected by the cloud firewall; firewall updates affect new connections, not existing established connections.
Sources:
https://docs.hetzner.com/cloud/firewalls/faq/
https://docs.hetzner.com/cloud/firewalls/overview/
External egress gateway must independently prevent direct IPv4/IPv6, DNS/DoH/DoT, UDP/443, metadata and internal routing bypass; verify routing, bootstrap dependencies, exact destinations, failure mode and logs. If cannot prove these properties, reject Hetzner option or revise architecture; never declare firewall-only implementation compliant.
Provider firewall is free per official docs, but independent gateway cost is NOT established.
No untrusted fork PRs or privileged Docker socket.

## OC-06 Governance
Issue #340 prospective ordinary-development reopening is NOT target-specific runner execution authority. Historical charter precedence unresolved. Owner PR comment 6691539436 is documentary acceptance only. Require documented authority reconciliation and distinct execution decision bound to exact provider resources, operator, tests, costs, expiry and rollback.
C02 OPEN_CRITICAL / SC_07 OPEN_CRITICAL / GOV_BREACH_01 OPEN. No closure claimed.

## OC-07 Independent reviewer
Require independent reviewer identity, conflict check, exact HEAD/file hash and review scope. A documentary review by hamidrezaasadian7-boop does not itself establish SC_07 independence or runtime verification. Reviewer must inspect actual architecture and source/evidence, not only restate this proposal.

## OC-08 Evidence and test matrix
Before execution: signed/hashed test plan, immutable runner image, exact allowlist, negative/positive cases, sanitized logs and expected outcomes.
Only after separate authorization: allowlisted hash-locked public dependency fetch, offline install, advisory lookup; deny raw IP IPv4/IPv6, unauthorized domains, DNS bypass, DoH/DoT, QUIC, metadata/private endpoints, gateway outage, route bypass, redirects and policy tampering.
After: independently verify runner unregister, firewall/network deletion, final provider bill, no leaked credentials, retained logs and incident handling.

## Acceptance and blocker matrix
OC-01 PARTIALLY_SPECIFIED / PROVIDER_NOT_APPROVED
OC-02 COMPUTE_PRICE_SOURCED / TOTAL_COST_NOT_VERIFIED
OC-03 TTL_PROPOSED / CONTROLS_NOT_VERIFIED
OC-04 ACTORS_UNASSIGNED
OC-05 HETZNER_FIREWALL_ALONE_INSUFFICIENT / EXTERNAL_GATEWAY_UNVERIFIED
OC-06 EXECUTION_AUTHORITY_NOT_ESTABLISHED
OC-07 INDEPENDENCE_NOT_VERIFIED
OC-08 TEST_PLAN_DEFINED / RUNTIME_EVIDENCE_ABSENT

Next owner decision: documentary selection of candidate provider and whether to retain EUR 10 cap or revise after verified external-gateway quote. Neither documentary choice authorizes spending or provisioning.
No cloud resources created, changed or deleted; no GitHub CI settings, Render, secrets, databases, merge or deploy touched.

FINAL_STATE: REMEDIATION_PLAN_PREPARED / ALL_EXECUTION_GATES_BLOCKED / SAFE_HOLD / NO_GO
