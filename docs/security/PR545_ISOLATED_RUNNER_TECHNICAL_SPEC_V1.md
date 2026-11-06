# PR545 — Isolated Runner Technical Specification V1

Status: PROPOSED / DOCUMENTARY_ONLY / INDEPENDENT_REVIEW_PENDING
Repository: 13640226/VORNEQ
Parent: docs/security/PR545_FAIL_CLOSED_EGRESS_DESIGN_V1.md
Scope: design only; no provisioning, workflow switch, secrets, DB, merge or deploy.

## 1. Current observed baseline
The Security Audit workflow uses runs-on: ubuntu-24.04. Wheel acquisition and advisory lookup each use Docker --network bridge; installation uses --network none. The job has contents: read and checkout persist-credentials: false. Existing external proxy/firewall infrastructure has not been verified. GitHub-hosted runner success does not demonstrate destination-constrained egress.

## 2. Trust boundaries
T0: GitHub workflow source and untrusted PR inputs.
T1: isolated ephemeral runner (assume compromise during execution).
T2: runner host/container runtime and local Docker daemon (not a security boundary against arbitrary host execution).
T3: externally administered network firewall + forward proxy (security enforcement boundary).
T4: external approved package/advisory endpoints.
T5: GitHub Actions control plane (separate narrowly scoped connectivity policy).
A compromised T1/T2 must not be able to alter T3 policy or route around it.

## 3. Runner topology and lifecycle
- Dedicated, ephemeral self-hosted Linux runner; no shared production workloads; single job per runner; destroy VM after job.
- No VORNEQ production/staging/DR database network route, credentials, or attached production disks.
- Run in a dedicated subnet/VLAN with no unrestricted internet NAT. Route all outbound connections through an external deny-by-default gateway. Firewall policy and gateway administration live outside runner credentials.
- Explicitly deny access to RFC1918/internal networks, link-local, metadata services, Docker daemon remotely, and adjacent runner instances; allow only required management/control-plane routes after review.
- Do not install long-lived runner registration tokens in job environment. Registration/provisioning service must be independently controlled, short-lived, and auditable.
- Restrict self-hosted runner assignment to trusted workflow/ref; do not run untrusted fork PR code on privileged runners. Define a separate no-secret policy for fork PRs.
- GitHub Actions service connectivity, DNS and image retrieval are bootstrap dependencies: inventory and permit only after independent review; do not imply exact endpoint coverage from this document.

## 4. Egress gateway policy
- Gateway/firewall default DROP for both IPv4 and IPv6, TCP and UDP; only exact documented gateway and DNS resolver access permitted from runner subnet.
- HTTP CONNECT restricted to exact approved FQDN:443; no wildcard domains, raw-IP CONNECT, non-443 ports, HTTP downgrade, or unknown redirect destinations.
- Proxy checks DNS resolution and TLS SNI/certificate-host consistency where technically enforceable; if encrypted ClientHello or CONNECT obscures validation, reject or use a documented stronger enforcement design. Do not claim TLS interception without approval.
- Disallow direct destination IP and alternate resolvers (including DoH/DoT); block UDP/443 QUIC and all unapproved outbound protocols.
- Initial candidate wheel hosts: pypi.org and files.pythonhosted.org; initial advisory candidate: api.osv.dev. These are NOT approved allowlist entries until actual pip/pip-audit traffic and redirects are captured.
- No fallback to bridge networking or unrestricted public egress if proxy/gateway is unavailable.
- Separate policies for wheel download and advisory query; installation has --network none.
- Preserve audit logs for destination, policy decision, phase, timestamp, runner ID, and workflow SHA, without storing credentials or request payloads.

## 5. CI wiring proposal (not yet enabled)
- Job must be gated on a protected, independently verified runner label and group, plus immutable runner image evidence.
- Runner preflight checks gateway policy version, external policy attestation, default-deny status, and isolation; missing evidence fails the job.
- Enforce pinned container image digest and --cap-drop ALL, no-new-privileges, nonroot, read-only mounts, and no GitHub write token.
- Download only binary wheels with --require-hashes; verify local wheel manifest. Install with --network none and --no-index.
- Advisory tool must not have general-purpose internet access; an egress proxy enforces the reviewed endpoint policy.
- No privileged Docker socket exposed to workload containers. Runner host compromise remains within threat model; external gateway must remain independently protected.
- Do not turn off existing required checks or relax branch protection to migrate the job.

## 6. Validation plan and evidence
Positive: authorized package downloads and advisory requests work, exact lock hashes verify, offline install works, workflow checks succeed.
Negative: arbitrary domain, raw IP, redirect to forbidden domain, direct IPv4/IPv6, alternate DNS/DoH/DoT, UDP/443, proxy outage, gateway outage, internal/metadata addresses, unauthorized CONNECT port, and runner-policy tampering all fail closed.
Capture policy version, runner identity, immutable image digest, exact HEAD, firewall/proxy deny logs, test commands, timestamps, and GitHub Actions run/job IDs. Confirm no secrets in logs.
No negative-test evidence means EGRESS_UNVERIFIED, even if ordinary CI is green.

## 7. Required independent review
Reviewer must have demonstrable independence and access to real source, runner/network configuration, firewall policy, and positive/negative test evidence. A documentary acknowledgment or GitHub APPROVED flag alone does not close SC_07 or grant merge authority. The existing reviewer account hamidrezaasadian7-boop must not be assumed independent absent evidence.

## 8. Rollout / rollback
Phase A: documentary design and threat review.
Phase B: authorized isolated nonproduction pilot with no production connectivity.
Phase C: review gateway and runner evidence; exact HEAD security review.
Phase D: separately authorized migration of Security Audit to protected runner, retaining all required checks.
Rollback: disable pilot runner assignment and revert only the pilot workflow change under explicit authorization; retain default-deny gateway, do not fall back to unrestricted egress.

## 9. Decision gates
PILOT_PROVISIONING = NOT_AUTHORIZED
WORKFLOW_MIGRATION = NOT_AUTHORIZED
DB / SECRETS / MERGE / DEPLOY = NOT_AUTHORIZED
HARD_STOP = UNRESOLVED
C02 = OPEN_CRITICAL
SC_07 = OPEN_CRITICAL
GOV_BREACH_01 = OPEN
FINAL_STATE = DOCUMENTARY_DESIGN_READY / INDEPENDENT_REVIEW_PENDING / SAFE_HOLD / NO_GO
