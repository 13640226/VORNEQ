# PR545 Pilot Resource, Cost, TTL and Authority Matrix V1
Date: 2026-11-06
Repository: 13640226/VORNEQ
PR: 545
Status: DOCUMENTARY_PROPOSAL / NO_EXECUTION_AUTHORIZATION

## Read-only infrastructure inventory
Render workspace tea-da71asm1egvs73f1fec0 lists VORNEQ (srv-dadn07eq1p3s73eccau0) and vorneq-staging (srv-dbm7dvc9v7es7393g70g). Both are explicitly excluded. No isolated runner, firewall gateway, provider account or pilot network has been independently identified or verified.

## Reference architecture — proposal, not selection
One ephemeral nonproduction Linux self-hosted GitHub Actions runner in a NEW isolated subnet/account with a separately administered external default-deny IPv4/IPv6 egress gateway, restrictive DNS, deny logs and a kill switch. No direct NAT bypass. Candidate sizing 2 vCPU / 4 GiB RAM, subject to provider verification. No existing workflows assigned to pilot. No operational GitHub Actions secrets or production tokens. GitHub registration bootstrap must be separately security-reviewed.
Provider/account, region, exact instance type, image digest, subnet, firewall identifiers, allowlist, runner group, executor and independent network administrator = NOT_SELECTED / NOT_VERIFIED.
Existing Render production/staging/DR infrastructure must not be reused.

## Proposed budget and duration — NOT APPROVED
Proposed total cost ceiling: EUR 10. This is a planning limit, NOT a verified quote or permission to spend. If secure external enforcement cannot fit this ceiling, stop and request a revised owner decision; never relax controls.
Proposed active test window: maximum 2 hours.
Proposed total resource lifetime: maximum 4 hours from provisioning, including teardown.
Proposed cost warning: EUR 5; stop at EUR 10 only if independently enforceable. Alerts alone do not enforce spending caps.
Exact UTC start/end, billing account and cost payer: PENDING OWNER DECISION.
Automatic expiration, resource cleanup and evidence retention: REQUIRED, NOT VERIFIED.

## Proposed actors
Decision owner: repository owner 13640226.
Executor: NOT_APPOINTED; must be authorized on selected provider account.
External gateway administrator: NOT_APPOINTED; must be outside runner compromise boundary.
Independent reviewer: NOT_APPOINTED / INDEPENDENCE_NOT_VERIFIED; hamidrezaasadian7-boop documentary comments do not resolve SC_07.
Payer and teardown verifier: NOT_APPOINTED.

## Permitted pilot tests only after separate valid authorization
Positive: approved hash-locked public wheel acquisition; offline installation without network; approved advisory lookup; narrowly approved control-plane registration bootstrap.
Negative: unauthorized FQDN, direct IPv4/IPv6, raw IP, DNS/DoH/DoT, UDP 443, forbidden CONNECT, redirects, private/internal/metadata endpoints, gateway outage, policy tampering and open-egress fallback.
Evidence: exact image digest, gateway revision, immutable test artifact SHA, sanitized allow/deny logs, UTC timestamps, reproducible commands, cost record and independently checked teardown.

## Prohibited without exception under this proposal
No production/staging/DR DB routes, SQL, migrations, customer data, operational secrets, Render credentials, production networks, privileged runner or untrusted fork PR execution. No workflow migration, GitHub ruleset changes, merge, deploy or product release.

## Authority validity review
Issue 340 comment 6684486039 prospectively removes blanket holds for ordinary development but explicitly requires target-specific authorization for sensitive CI infrastructure.
Issue 340 comment 6681771088 records original charter unrecovered and operational authority unresolved.
Issue 340 comment 6681819991 allows new scoped decisions to be considered without indefinite charter recovery; it does not grant execution.
PR 545 owner comment 6691539436 accepted documentary framework only.
Consequently this matrix is not an exception from HARD_STOP and cannot establish operational authority.
C02 OPEN_CRITICAL; SC_07 OPEN_CRITICAL; GOV_BREACH_01 OPEN.
OWNER_EXECUTION_APPROVAL = NOT_GRANTED.
PILOT_PROVISIONING = NOT_AUTHORIZED.
FIREWALL_CHANGE = NOT_AUTHORIZED.
CI_MIGRATION = NOT_AUTHORIZED.
MERGE / DEPLOY / DATABASE / SECRETS = NOT_AUTHORIZED.

## Mandatory next decision
Owner must select provider, account, region, resources, payer, executor, independent reviewer, actual enforceable budget, UTC execution window and cleanup plan. Review exact gateway and registration security. Then issue a distinct, specific execution decision only after authority reconciliation and safety review. If unknown, remain blocked.

Documentary decision A: accept this matrix as planning reference only.
Documentary decision B: return for corrections.
Neither authorizes execution.

FINAL_STATE: DOCUMENTARY_MATRIX_PREPARED / AUTHORITY_UNRESOLVED / PILOT_BLOCKED / SAFE_HOLD / NO_GO
