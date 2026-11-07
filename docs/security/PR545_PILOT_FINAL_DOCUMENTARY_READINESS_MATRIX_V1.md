# PR545_PILOT_FINAL_DOCUMENTARY_READINESS_MATRIX_V1

Date: 2026-11-06
Repository: 13640226/VORNEQ
Pull request: #545
Scope: STRICT_READ_ONLY / DOCUMENTARY_ONLY
Document status: CONSOLIDATED_DRAFT / OWNER_DOCUMENTARY_DECISION_PENDING
Execution authorization: NOT_GRANTED
Principle: PROPOSAL != DOCUMENTARY_ACCEPTANCE != EXECUTION_AUTHORIZATION != VERIFIED_EVIDENCE

## Evidence index and provenance
E-01 OC-01..OC-08 remediation plan: docs/security/PR545_OC01_OC08_REMEDIATION_AND_PROVIDER_COST_V1.md, commit d54a521f0ccaded32be55f81896157652da13240; reviewer comment https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692137005
E-02 OC-01/02 two-node gateway and cost candidate: docs/security/PR545_OC01_OC02_TWO_NODE_GATEWAY_COST_FEASIBILITY_V1.md, commit ffd259d63b2a147b40aa6440b6245b076f501bbd; reviewer comment https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692216857
E-03 OC-03..OC-08 pre-execution controls: docs/security/PR545_OC03_OC08_PREEXECUTION_CONTROLS_EVIDENCE_CONTRACT_V1.md, commit e66da4a98ce58014406134df1851a5342e04c0df; reviewer comment https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692282080
E-04 Owner documentary-only Option A: https://github.com/13640226/VORNEQ/pull/545#issuecomment-6691539436
E-05 Issue #340 prospective policy and unresolved authority: https://github.com/13640226/VORNEQ/issues/340#issuecomment-6681771088 ; https://github.com/13640226/VORNEQ/issues/340#issuecomment-6681819991 ; https://github.com/13640226/VORNEQ/issues/340#issuecomment-6684486039
E-06 Official pricing sources: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ and https://docs.hetzner.com/cloud/servers/primary-ips/overview/
E-07 Provider firewall caveats: https://docs.hetzner.com/cloud/firewalls/faq/
Evidence caveat: cited GitHub comments document claimed reviews; they do not by themselves prove reviewer independence, source-level reproducibility or runtime verification. Earlier GitHub APPROVED review on older HEAD does not approve this consolidated document.

## Unified readiness matrix

| ID | Control | Existing documentary evidence | Outstanding prerequisites | Current result |
|---|---|---|---|---|
| OC-01 | Infrastructure identity and topology | E-01/E-02: candidate Hetzner Germany two CX23 nodes, runner private-only, gateway public IPv4, isolated network | Choose/verify provider account, region, network, exact IDs, images/digests, routes, independent control plane; demonstrate provider bypass handling | DESIGN_CANDIDATE_ONLY / OPEN |
| OC-02 | Full cost and budget | E-02/E-06: 4h base arithmetic: runner 0.0352 EUR + gateway 0.0352 + IPv4 0.0032 = 0.0736 excl VAT; approx 0.088 incl 19% VAT | Verify hourly billing granularity, other charges, gateway administration, traffic/logging, payer, actual total quotation and enforceable EUR10 ceiling | BASE_RATE_ESTIMATED / EUR10_NOT_VERIFIED / OPEN |
| OC-03 | TTL and independent cleanup | E-03: proposed 2h active/4h lifetime, UTC expiry, stop and cleanup criteria | Owner approve exact UTC window; independent stop controller, enforced expiry, teardown inventory and verification | DOCUMENTED / NOT_TESTED / OPEN |
| OC-04 | Responsible actors | E-03: roles and separation matrix required | Identify executor, payer, account owner, gateway admin, independent reviewer, cleanup verifier and authorizations | UNASSIGNED / OPEN |
| OC-05 | Fail-closed egress | E-02/E-03/E-07: default-deny gateway candidate, positive/negative test criteria, provider caveats | Independently resolve metadata/DNS/private-network exemptions; prevent IPv4/IPv6/direct IP/DoH/DoT/QUIC/routing/control-plane bypass; demonstrate outage fail-closed | SECURITY_DESIGN_INCOMPLETE / NOT_VERIFIED / OPEN |
| OC-06 | Governance authority | E-04/E-05: owner documentary acceptance, prospective Issue #340 ordinary-development policy | Resolve HARD_STOP authority/charter precedence, establish specific pilot owner decision, preserve C02/SC_07/GOV_BREACH_01 constraints | EXECUTION_AUTHORITY_NOT_ESTABLISHED / OPEN |
| OC-07 | Independent verification | E-01/E-02/E-03 reviewer comments with exact HEADs | Verify independent reviewer eligibility, conflicts, access, independent test scope, and SC_07 evidence | INDEPENDENCE_NOT_VERIFIED / OPEN |
| OC-08 | Security and financial evidence | E-03: test IDs, sanitized immutable logs, teardown and billing reconciliation plan | Obtain immutable preflight evidence and, only after separate authorization, runtime positive/negative results, cost and teardown proofs | TEST_PLAN_ONLY / RUNTIME_EVIDENCE_ABSENT / OPEN |

## Decision prerequisites and order
Gate 0 (documentary): independent source and pricing review of this exact consolidated HEAD; owner chooses documentary acceptance or correction.
Gate 1 (authority): reconcile Issue #340 HARD_STOP, C02, SC_07 and GOV_BREACH_01, define who can authorize what; no implied waiver.
Gate 2 (resources/finance): exact nonproduction cloud account, region, architecture, payer, resource inventory, total costs and enforceable budget; if EUR10 insufficient, reject or seek a separately authorized revised budget, never silently weaken controls.
Gate 3 (security): independent network policy ownership and design that demonstrably addresses provider exemptions; reject architecture if no enforceable fail-closed path.
Gate 4 (operators/TTL): separate executor, gateway admin, independent verifier, UTC timebox and independent kill switch.
Gate 5 (specific owner authorization): written target-scoped decision with provider/resources, financial maximum, duration, allowed tests, forbidden operations, evidence and revocation. This document is NOT that decision.
Gate 6 (future execution, if ever separately authorized): controlled positive/negative tests, independent validation, cleanup, token revocation, final billing reconciliation. No runtime tests authorized by this document.

## Owner documentary decision choices
A — DOCUMENTARY_ACCEPTED_WITH_OPEN_CONDITIONS: adopt this as a planning/status matrix only, all OC-01..08 remain open, no pilot execution.
B — CORRECTION_REQUIRED: request specific corrections to matrix or provenance.
Until a distinct valid authorization exists, no cloud spend, resource creation, network/firewall change, GitHub runner registration, CI migration, DB/operational secret access, merge or deploy.

## Final governance posture
HARD_STOP authority: UNRESOLVED
C02: OPEN_CRITICAL
SC_07: OPEN_CRITICAL
GOV_BREACH_01: OPEN
OC-01..OC-08: ALL OPEN (documentary preparation does not close conditions)
EXECUTION_AUTHORIZATION: NOT_GRANTED
FINAL_STATE: CONSOLIDATED_DOCUMENTARY_MATRIX_PREPARED / OWNER_DOCUMENTARY_DECISION_PENDING / PILOT_BLOCKED / SAFE_HOLD / NO_GO
