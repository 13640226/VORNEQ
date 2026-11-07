# PR545_PILOT_PREEXECUTION_INDEPENDENT_EVIDENCE_REVIEW_V1

Date: 2026-11-06
Repository: 13640226/VORNEQ
PR: #545
Review mode: STRICT_READ_ONLY / DOCUMENTARY_ONLY
Document role: evidence review framework and preliminary provenance assessment, NOT an independently performed audit
Owner documentary decision: https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692405917
Reference consolidated matrix commit: 44689483b4c9da1a88f9332e49103493fa68877f
Review target: current exact commit containing this document, to be specified in reviewer response
Authorization: NO_EXECUTION

## Evidence integrity and decision vocabulary
EVIDENCE_SUFFICIENT = sufficient documentary evidence for the explicitly scoped *next documentary decision*, never runtime approval.
EVIDENCE_INSUFFICIENT = missing or unverifiable evidence.
CORRECTION_REQUIRED = contradiction or testability defect with identified remedy.
BLOCKED = unresolved authority/security dependency preventing operational progression.
Evidence must cite exact source URL, immutable commit or comment identifier, retrieval date, author, reviewer, verification method and limitations. A GitHub comment records an assertion, not automatically independent verification. Do not claim that this document itself is an independent review.

## Track T1 — Governance authority and HARD_STOP
Sources:
- https://github.com/13640226/VORNEQ/issues/340#issuecomment-6681771088 (authority/charter uncertainty)
- https://github.com/13640226/VORNEQ/issues/340#issuecomment-6681819991 (prospective policy)
- https://github.com/13640226/VORNEQ/issues/340#issuecomment-6684486039 (ordinary development distinction)
- https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692405917 (owner documentary acceptance)
Acceptance criteria:
T1-AC01: inventory and exact text of all currently controlling owner/charter/HARD_STOP decisions, including supersession provenance and effective scope.
T1-AC02: reconcile conflicting interpretations and record whether sensitive isolated CI runner provisioning is covered (do not infer coverage from ordinary development policy).
T1-AC03: identify authorized owner, decision process, conditions and prohibited actions for any future target-specific pilot request.
T1-AC04: independently verify that C02 OPEN_CRITICAL, SC_07 OPEN_CRITICAL and GOV_BREACH_01 OPEN are not silently waived.
Missing: authoritative precedence resolution, signed target-scoped pilot decision, independent governance review.
Preliminary result: BLOCKED / EXECUTION_AUTHORITY_NOT_ESTABLISHED.

## Track T2 — Independent reviewer eligibility / SC_07
Sources:
- https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692137005
- https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692216857
- https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692282080
- https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692358594
- https://github.com/13640226/VORNEQ/issues/448#issuecomment-6679216394
Acceptance criteria:
T2-AC01: identify actual reviewer principal, access provenance and scope, with conflict-of-interest and authorship declarations.
T2-AC02: demonstrate separation from owner/executor/gateway admin and absence of self-review according to SC_07 authoritative criteria.
T2-AC03: reviewer directly inspects exact immutable target commit and source evidence; records file/section-level findings and method, including unverified areas.
T2-AC04: eligibility decision is itself made by an authorized non-conflicted authority, not self-certified by reviewer.
Missing: independent eligibility verification, authoritative SC_07 resolution, verifiable source inspection method.
Preliminary result: EVIDENCE_INSUFFICIENT / INDEPENDENCE_NOT_VERIFIED.

## Track T3 — Fail-closed egress and provider exceptions
Sources:
- docs/security/PR545_OC01_OC02_TWO_NODE_GATEWAY_COST_FEASIBILITY_V1.md @ ffd259d63b2a147b40aa6440b6245b076f501bbd
- docs/security/PR545_OC03_OC08_PREEXECUTION_CONTROLS_EVIDENCE_CONTRACT_V1.md @ e66da4a98ce58014406134df1851a5342e04c0df
- https://docs.hetzner.com/cloud/firewalls/faq/
Acceptance criteria:
T3-AC01: exact trust-boundary and route diagrams including cloud control plane, metadata, provider DNS, private networking and IPv4/IPv6.
T3-AC02: documented independently enforced default-deny egress with gateway outage fail-closed and no runner control of policy/routes/provider API.
T3-AC03: design-level countermeasures for direct IP, DNS/DoH/DoT, QUIC/UDP443, IPv6, metadata, private lateral routes, redirects, and bypass via bootstrap.
T3-AC04: positive/negative test matrix with expected deny/allow, observer, logs, immutable config hashes and rejection thresholds. Execution of tests requires separate authorization.
T3-AC05: if Hetzner exemptions cannot be independently controlled, reject candidate architecture rather than weaken requirements.
Missing: exact verified network/control-plane design, provider exemption resolution, independent network review, runtime tests.
Preliminary result: BLOCKED / FAIL_CLOSED_NOT_VERIFIED.

## Track T4 — Full cost and enforceable ceiling
Sources:
- docs/security/PR545_OC01_OC02_TWO_NODE_GATEWAY_COST_FEASIBILITY_V1.md @ ffd259d63b2a147b40aa6440b6245b076f501bbd
- https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- https://docs.hetzner.com/cloud/servers/primary-ips/overview/
Acceptance criteria:
T4-AC01: dated official provider rates, region, VAT treatment, hourly granularity and minimum charges verified against current billing terms.
T4-AC02: itemized four-hour and contingency costs for runner, gateway, IPv4, traffic, network, logging, storage, administration, cleanup, taxes and other paid dependencies, explicitly zero where confirmed.
T4-AC03: actual billing owner and funding authority, independently controlled spend stop, cost monitoring and final invoice reconciliation defined.
T4-AC04: demonstrate that entire compliant architecture (not just compute) fits proposed EUR10 ceiling; if not, block or seek separate budget decision.
Existing arithmetic: (2 * 4 * EUR0.0088) + (4 * EUR0.0008) = EUR0.0736 excluding VAT; approximately EUR0.087584 including 19% VAT (~EUR0.088), BASE RESOURCES ONLY.
Missing: complete binding quotation, payer, enforceable ceiling, actual final invoice and cost of independent gateway operations.
Preliminary result: EVIDENCE_INSUFFICIENT / TOTAL_COST_NOT_VERIFIED.

## Cross-track gate
No track is closed by this document or by a reviewer comment alone. For each finding reviewer must record source, method, exact quote/section, confidence/limitations, remediation owner, and result. If any T1 or T3 BLOCKED, no operational pilot decision. T2 independence and T4 full financial controls also required prior to any provisioning. All OC-01..OC-08 remain OPEN.

## Independent reviewer response template
Reviewer principal and eligibility basis:
Exact reviewed commit:
Evidence checked with URLs/sections:
T1 result + unmet AC:
T2 result + unmet AC:
T3 result + unmet AC:
T4 result + unmet AC:
Corrections and next documentary action:
No runtime verification claimed unless separately authorized and evidenced.

## Owner documentary next step
Option A: acknowledge receipt and request an eligible independent reviewer to perform strict read-only source and evidence review; no execution.
Option B: request corrections to this framework.
Neither option permits provider accounts, purchases, runner provisioning, network/firewall modifications, GitHub runner registration, CI migration, DB/operational secrets, merge or deploy.

HARD_STOP authority: UNRESOLVED
C02: OPEN_CRITICAL
SC_07: OPEN_CRITICAL
GOV_BREACH_01: OPEN
FINAL_STATE: EVIDENCE_REVIEW_FRAMEWORK_PREPARED / INDEPENDENT_REVIEW_PENDING / PILOT_BLOCKED / SAFE_HOLD / NO_GO
