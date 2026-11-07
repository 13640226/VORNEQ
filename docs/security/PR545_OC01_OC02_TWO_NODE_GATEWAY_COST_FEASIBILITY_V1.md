# PR545 OC-01/OC-02 — Two-Node Gateway Architecture and Cost Feasibility V1
Date: 2026-11-06
Scope: STRICT_READ_ONLY / DOCUMENTARY_ONLY
Status: DESIGN_CANDIDATE / NOT_SELECTED / NOT_EXECUTION_AUTHORIZATION
Repository: 13640226/VORNEQ; PR #545
Predecessor: docs/security/PR545_OC01_OC08_REMEDIATION_AND_PROVIDER_COST_V1.md
Reviewer: https://github.com/13640226/VORNEQ/pull/545#issuecomment-6692137005

## OC-01: proposed isolated topology, not provisioned
Provider candidate: Hetzner Cloud Germany, FSN or NBG, exact location and account NOT_SELECTED.
Candidate components:
A. Runner: CX23 2 vCPU/4 GiB, ephemeral, private-network-only, NO Primary IPv4 or IPv6, NO production/staging/DR routes, NO operational secrets, no privileged untrusted PR execution.
B. Egress gateway: separate CX23 2 vCPU/4 GiB with one paid Primary IPv4; gateway firewall/proxy and independently managed policy/logging; public interface limited to outbound allowlist and tightly scoped administrative ingress. IPv6 absent unless a separately verified IPv6 design is approved.
C. Dedicated isolated private cloud network; no connection to Render or any existing database or tenant networks.
D. Independently administered provider controls must prevent runner from adding a public IP, modifying cloud routes/firewall, reaching provider API, or modifying gateway policy. This cannot be inferred from a host firewall alone.
E. Exact runner bootstrap/GitHub registration flow, approved endpoints, tokens and revocation, immutable image digests, routing tables, network gateway ownership and logs are NOT_VERIFIED.
F. Hetzner Cloud Firewall is defense-in-depth only, NOT the sole external enforcement. Provider docs state metadata requests are locally answered and some provider DNS/rescue traffic is exempt, and private Cloud Network traffic is not secured by Cloud Firewall. Verify whether local metadata/DNS bypass violates contract; if unpreventable, FAIL design and choose another platform. Source: https://docs.hetzner.com/cloud/firewalls/faq/
G. Direct-IP, IPv4/IPv6, DoH/DoT, QUIC, DNS resolver, metadata, lateral movement, proxy outage, policy-tamper and route-reconfiguration denial must be proven by independent tests after a distinct authorization.
OC-01 RESULT: ARCHITECTURE_CANDIDATE_DEFINED / EXTERNAL_FAIL_CLOSED_NOT_VERIFIED / RESOURCE_IDENTITY_NOT_SELECTED.

## OC-02: sourced pricing and 4-hour reference estimate
Official Hetzner pricing effective 2026-06-15, Germany CX23 EUR 0.0088 per hour excluding VAT/IPv4. https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
Official Primary IPv4 EUR 0.0008 per hour excluding VAT. IPv6 free. https://docs.hetzner.com/cloud/servers/primary-ips/overview/
Four-hour rate-based estimate, excluding VAT:
Runner: 4 x 0.0088 = EUR 0.0352.
Gateway: 4 x 0.0088 = EUR 0.0352.
One gateway IPv4: 4 x 0.0008 = EUR 0.0032.
Subtotal: EUR 0.0736 excl VAT.
With 19% VAT: EUR 0.087584, approximately EUR 0.088, not EUR 0.084.
Correction: two CX23 servers + one IPv4, 4 hours = approximately EUR 0.088 incl VAT, before rounding and other charges.
Provider billing granularity, minimum charges, traffic, logs, backups, volumes, egress, gateway configuration, any paid support, payment authorization and actual bill NOT_VERIFIED.
No backup, paid volumes or load balancer are assumed, but their absence must be verified before approval.
Total proposed cap EUR 10: arithmetic headroom EUR 9.9124 against base estimate, but NO feasibility conclusion: unknown billing, costs and security requirements may exceed cap. Hard spend cap must be technically enforceable or independently controlled; billing alerts alone insufficient.
OC-02 RESULT: BASE_RATE_ESTIMATED / TOTAL_COST_NOT_QUOTED / EUR10_FEASIBILITY_UNPROVEN.

## OC-03..OC-08 follow-on documentary gates
OC-03 proposed 2h active/4h total TTL; need UTC window, independent forced cleanup and proof.
OC-04 payer, executor, independent gateway administrator and teardown verifier unassigned.
OC-05 no compliant gateway claim until all egress paths and provider exemptions independently verified.
OC-06 Issue #340 prospective ordinary-development policy is not pilot execution authority; historical precedence remains unresolved.
OC-07 reviewer independence not established; SC_07 remains OPEN_CRITICAL.
OC-08 tests and immutable evidence plan required; no runtime evidence.
C02 OPEN_CRITICAL; GOV_BREACH_01 OPEN.

## Next decision (DOCUMENTARY ONLY)
Owner may select this two-node topology for further design research or reject it. Neither option authorizes account creation, cost, resource provisioning, firewall modification, GitHub runner registration, CI changes, secrets/DB access, merge or deploy.
Require an independent provider billing and gateway security review before any operational owner decision.

FINAL_STATE: OC01_DESIGN_CANDIDATE / OC02_COST_BASELINE_ONLY / EUR10_NOT_VERIFIED / PILOT_BLOCKED / SAFE_HOLD / NO_GO
