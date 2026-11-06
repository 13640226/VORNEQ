# PR #545 — Fail-Closed Egress Control Design V1

Status: DESIGN_ONLY / NOT_IMPLEMENTED / SECURITY_REVIEW_REQUIRED
Repository: 13640226/VORNEQ
Target: .github/workflows/security.yml
Date: 2026-11-06

## Evidence and limitations
GitHub code search on the default branch for proxy, egress, squid, iptables, and firewall found no matching files. This does NOT prove that external network controls are absent. The PR workflow currently runs wheel acquisition and pip-audit advisory queries on Docker bridge networking, which is not a destination allowlist.

## Security objective
Deny all outbound traffic by default for the security-audit job. Allow only explicitly authorized HTTPS destinations during distinct acquisition and advisory phases. The offline install phase must have no network namespace connectivity. Prevent bypass via direct TCP, DNS, IPv6, alternative ports, container host gateway, Docker socket, or untrusted proxy environment overrides.

## Architecture decision (proposed)
Use a dedicated, ephemeral self-hosted Linux runner in an isolated network segment, with egress enforced by an external network firewall or egress gateway OUTSIDE the runner's administrative control. A GitHub-hosted runner with a user-controlled in-job proxy alone is insufficient for a verified fail-closed boundary: code executing on the runner may bypass it.

Runner policy:
- Default outbound DENY, including IPv4/IPv6 and DNS, except via a controlled resolver and gateway.
- No public inbound exposure; management/runner registration endpoints are separately scoped and monitored.
- Deny direct internet access from all containers and the host, except mandatory GitHub Actions control-plane endpoints via a separately reviewed policy.
- Deny access to metadata services, RFC1918 internal destinations, Docker socket, and cloud credentials from audit containers.
- Deny UDP/443 (QUIC) and all arbitrary outbound ports; require TLS verification and reject HTTP CONNECT to non-allowlisted destinations.
- Dedicated egress gateway validates destination hostname against exact approved FQDNs, verifies TLS SNI and destination certificate name, blocks redirects to disallowed hosts, and logs metadata without secrets.
- All external container images fetched and verified by immutable digest before running, using a separately controlled acquisition process.
- Audit workload has no GitHub write token or other secrets, runs as non-root with dropped capabilities, no-new-privileges, read-only filesystem, and isolated temporary directories.

## Phase policy
1. Acquisition: allow exact PyPI package index and artifact hosts needed by the locked dependency set (candidate names: pypi.org, files.pythonhosted.org). Verify observed redirect/CDN destinations before adding them. Require pinned hashes, binary-only wheels, and no build scripts.
2. Installation: --network none; --no-index; --require-hashes; only local verified wheels. No outbound exceptions.
3. Advisory lookup: allow only explicitly documented vulnerability advisory endpoints used by the pinned pip-audit version (candidate: api.osv.dev). Capture and review actual requests and redirects before finalizing.
4. Deny all other destinations in every phase; do not silently fall back to open bridge networking.

## Implementation gates
G0: Recover actual existing network/firewall/proxy inventory and runner ownership. If absent, provision isolated runner and external egress gateway; no security claim until evidence exists.
G1: Record exact FQDN, ports, DNS resolution, TLS/SNI validation, redirects, IPv6, and GitHub control-plane dependencies. Obtain independent approval for the list.
G2: Configure external default-deny firewall and allowlisted HTTPS proxy; verify container and host cannot bypass proxy via direct IP, DNS, IPv6, host gateway, or Docker socket.
G3: Update workflow to require explicit egress-gateway identity, proxy authentication without broad secrets, immutable images, and fail-closed preflight. Do not enable an unrestricted fallback.
G4: Execute controlled positive and negative tests and collect gateway deny logs and run IDs. Tests: approved PyPI wheel download succeeds with hashes; approved advisory succeeds; disallowed hostname/IP fails; DNS bypass fails; IPv6 bypass fails; proxy outage fails; redirect to forbidden host fails; offline install cannot connect; all expected GitHub Actions checks pass.
G5: Independent reviewer examines actual gateway configuration, source, test evidence, runner identity, and exact HEAD SHA. Formal review required; owner then makes a separate merge/deploy authorization decision under governance.

## Acceptance criteria
AC-EG-01: Default-deny externally enforced and demonstrated, including host and containers.
AC-EG-02: Exact destination allowlist documented, verified, and change-controlled.
AC-EG-03: No direct TCP/UDP/DNS/IPv6 bypass.
AC-EG-04: Redirects, TLS validation, and proxy failure are fail-closed.
AC-EG-05: Wheel download uses transitive hash lock and binary-only packages.
AC-EG-06: Installation has no network.
AC-EG-07: Advisory phase cannot reach arbitrary internet destinations.
AC-EG-08: Immutable container image digests and nonprivileged runtime enforced.
AC-EG-09: Negative test evidence includes logs, run IDs, SHA, timestamps, and no leaked secrets.
AC-EG-10: Independent review and explicit owner authorization before merge or deploy.

## Current decision
DESIGN_PREPARED / IMPLEMENTATION_NOT_AUTHORIZED_BY_THIS_DOCUMENT / EGRESS_UNVERIFIED / NO_MERGE / NO_DEPLOY.
A successful GitHub Actions run alone does not satisfy the criteria.
