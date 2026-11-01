# VORNEQ CI Security Architecture V2.0 — Owner-Accepted Documentary Baseline

Status: DOCUMENTARY_FROZEN (owner decision 2026-11-01). Implementation: NOT_AUTHORIZED. This document is a design and acceptance contract, **not** evidence of enforcement.

## Security invariants
1. A proposal, owner acceptance, independent review, workflow execution, and verified runtime evidence are distinct gates.
2. No production credentials, production database, Render access, or implicit organization secrets in any PR-triggered job.
3. No merge, deploy, migration against persistent databases, status simulation, branch-protection bypass, or automatic promotion.
4. Jobs processing untrusted source/dependencies must not have usable sudo, Docker socket, writable host mounts, privileged containers, or write-capable GitHub tokens.
5. Explicit event/repository/ref/commit identity; check names and results must bind to the actual authorized SHA.
6. Network egress is default-deny per job, with a reviewed endpoint manifest and a recorded enforcement result.
7. Every database write is restricted to a disposable test service with explicit local destination, database/user identity, and network boundary; string checks alone do not prove isolation.
8. Evidence must be immutable or independently anchored, scoped to the run SHA, and exclude secrets.

## Execution zones
**Z0 — Documentary / static:** GitHub metadata and workflow YAML review only. No CI execution.

**Z1 — Dependency inspection:** No application dependency install, import, build hooks, setup.py execution, sudo, or Docker. Audit a reviewed, locked inventory using pre-provisioned or independently verified tooling. Read-only token; fail closed on missing inventory, version, integrity, or output evidence. PR #483 is a separate candidate and cannot impersonate the required `dependencies` check.

**Z2 — System preparation:** Privileged OS package installation must be isolated from untrusted repository code. Prefer a prebuilt, digest-pinned image from an independently approved build pipeline. Never assume separate steps in the same GitHub-hosted job remove privilege. Any image build is separately authorized and reviewed.

**Z3 — Application tests:** Unprivileged execution only; no production secrets or write token. Isolated disposable filesystem and network; dependency execution treated as untrusted. Test matrices 3.11 and 3.12 require real results on the exact SHA.

**Z4 — Disposable PostgreSQL:** Ephemeral service with isolated network namespace, non-production credentials, allowlisted loopback/service address, explicit database and role checks before writes. A hostname, `DATABASE_URL`, or `current_database()` check alone does not establish production exclusion. Any migration here requires separate runtime authorization and containment evidence.

**Z5 — Artifact evidence:** Separate upload-only endpoint allowlist; integrity digests and run metadata; no privileged token or sensitive environment disclosure. Endpoint allowlist must be verified against the actual upload implementation.

## Acceptance criteria
- AC-CI2-01: workflow trigger, actor, repository, SHA, and expected required-check names verified against GitHub APIs.
- AC-CI2-02: every job has explicit least-privilege token permissions and no inherited production secrets.
- AC-CI2-03: dependency inspection cannot execute project installation hooks or obtain sudo/Docker.
- AC-CI2-04: privileged preparation cannot share a mutable trust boundary with untrusted project execution.
- AC-CI2-05: egress enforcement and exact artifact endpoints proven in an authorized isolated run.
- AC-CI2-06: disposable PostgreSQL network isolation, identity, and scope proven independently before writes.
- AC-CI2-07: no database migration runs before explicit runtime authorization.
- AC-CI2-08: check results and evidence are genuine, SHA-bound, and independently reviewable.
- AC-CI2-09: independently eligible reviewer signs off, not an owner-controlled account.
- AC-CI2-10: rollback, failure handling, and denial audit are documented.

Acceptance: 0/10 RUNTIME_VERIFIED. Design acceptance is not implementation acceptance.

## Current findings and dependencies
CI-01 OPEN: sudo and dependency execution share a runner in existing CI; merely separating steps is insufficient.
CI-02 PARTIAL: proposed egress allowlist in PR #487; transport and enforcement unverified.
CI-03 OPEN: PostgreSQL URL and SQL identity checks do not establish network isolation.
PR #482, #483, #487 remain unmerged candidates; PR #486 has expected checks and no verified execution.
STOP_340 ACTIVE; HARD_STOP ACTIVE; SC_07 OPEN_CRITICAL; MERGE_GO NO; DEPLOY_GO NO; SAFE_HOLD / NO_GO.

## Implementation handoff
Future code must be proposed in a **separate** Draft PR and pass static security review before any separately authorized CI execution. Do not modify existing required check policies, claim green statuses, or merge this documentary baseline as authorization.
