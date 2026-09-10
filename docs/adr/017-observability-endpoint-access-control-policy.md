# ADR 017: Observability Endpoint Access-Control Policy

- **Status:** Proposed (frozen policy; implementation deferred)
- **Date:** 2026-09-10

## Context

VORNEQ currently exposes operational endpoints on the public URL surface. The canonical URL configuration includes:

```python
# config/urls.py
path("health/", health_check, name="health")
path("", include("django_prometheus.urls"))
```

The Prometheus `/metrics` endpoint is therefore routed directly from the root URL configuration. PR #224 documented that `/metrics` was externally reachable without authentication or an IP restriction and recorded this as an Observability/Security hardening gap rather than a release blocker. The canonical record is `docs/observability-gaps.md`.

`/health/` and `/metrics` are both operational endpoints, but they are not the same security class:

- `/health/` is intended to provide a minimal platform probe signal and may remain public when its response is intentionally low-information.
- `/metrics` exposes operational telemetry that can reveal topology, route names, traffic patterns, error rates, query behavior, and other reconnaissance-relevant details, and therefore requires an access-control boundary.

VORNEQ does not currently have a frozen policy defining these classes, the required default behavior for metrics access, or the preferred enforcement boundary.

## Decision Drivers

1. Reduce reconnaissance and operational-topology leakage.
2. Preserve machine-to-machine Prometheus scrape compatibility.
3. Keep observability access independent of user authentication and the current allauth/AXES runtime state.
4. Require fail-closed behavior for restricted telemetry.
5. Enforce data minimization and bounded metric-label cardinality.
6. Keep this policy independent of ADR-013, ADR-014, ADR-015, and ADR-016 implementation work.
7. Preserve rollback paths without making application availability depend on monitoring availability.

## Decision

### D1. Endpoint classification

Operational endpoints are divided into three independent security classes:

| Class | VORNEQ examples | Access policy |
| --- | --- | --- |
| Public Health | `/health/` with a minimal readiness/liveness response | May remain public |
| Restricted Metrics | `/metrics` and other Prometheus scrape surfaces | Fail-closed; requires an approved access-control boundary |
| Operator Diagnostics | Debug, inspect, or administrative troubleshooting APIs intended for operators | Fail-closed; requires a separately appropriate operator boundary |

An endpoint being "operational" does not make it public-safe. These classes MUST NOT be collapsed into one access policy.

The public application route `/context/<uuid:artifact_id>/` is not classified as Operator Diagnostics merely because it exposes contextual information; it remains an application route unless its product contract changes.

### D2. Metrics default is fail-closed

In staging and production-like environments:

- `/metrics` MUST be restricted.
- Anonymous public scraping MUST NOT be an accepted steady state.
- Absence, failure, or misconfiguration of the intended access-control boundary MUST NOT cause metrics to fall back to public exposure.

Local development MAY expose metrics without restriction when that is useful for development and testing.

### D3. Preferred control plane

Implementation SHOULD choose the narrowest practical control plane in this order:

1. Edge or platform restriction, such as an approved access layer or platform-native access control.
2. A trusted private or internal network scrape path.
3. An application-level machine access guard when the first two options are unavailable or unsuitable.

This ordering follows the remediation preference already recorded in `docs/observability-gaps.md`: prefer a narrowly scoped edge/configuration solution before introducing an application-code change.

### D4. Machine-to-machine authentication model

Browser/session authentication MUST NOT be the primary access model for Prometheus scraping.

Prometheus is a machine-to-machine consumer, and coupling metrics access to allauth, AXES, browser sessions, or end-user login state would introduce an unnecessary dependency on the user-authentication subsystem.

Approved implementations SHOULD use machine-oriented access such as:

- network identity or a private path,
- an edge allowlist,
- or a bearer credential at the appropriate boundary.

The exact mechanism is deferred to the implementation phase.

### D5. Trusted proxy requirement for IP policy

An IP-based metrics restriction MUST NOT trust `X-Forwarded-For`, `X-Real-IP`, or equivalent forwarded-client headers directly unless an explicit trusted-proxy boundary is defined and enforced.

A valid IP-based policy requires all of the following:

- requests reach the application through a known trusted proxy or edge,
- the trusted proxy chain is explicitly defined,
- spoofable client-supplied forwarding headers are rejected, replaced, or normalized at that boundary,
- and the enforcement code reads client identity only from the approved source of truth.

**Frozen principle:** no IP-based metrics restriction is valid without an explicit trusted-proxy boundary.

### D6. Health endpoint separation and minimization

`/health/` MUST remain separate from `/metrics` in purpose and data contract. It MUST NOT be expanded into a general telemetry endpoint merely to simplify monitoring.

A public health endpoint SHOULD be fast and low-information. It MAY report:

- an overall boolean or small-state readiness result such as `ok`, `degraded`, or `fail`,
- bounded dependency states such as `database: ok|fail`, `storage: ok|fail`, or `cache: ok|fail` when those states are intentionally public-safe.

A public health response MUST NOT expose, unless a future explicit decision classifies the field as public-safe:

- version numbers or release SHAs,
- runtime configuration,
- connection strings or credentials,
- database row counts or similar internal counts,
- infrastructure topology,
- route inventories,
- or telemetry detail that belongs in metrics or logs.

### D7. Metric-label data minimization

Metric labels MUST use bounded aggregate dimensions only.

Metric labels MUST NOT contain:

- user identifiers,
- raw email addresses,
- credentials, tokens, or secrets,
- correlation IDs,
- unrestricted raw URLs,
- query strings,
- arbitrary object identifiers,
- or other sensitive or high-cardinality values.

Cardinality risk is a reliability concern as well as a privacy and security concern and therefore belongs to the access-control policy boundary.

### D8. Logs and metrics have distinct data contracts

VORNEQ treats logs and metrics as complementary but distinct observability layers:

| Layer | Data contract |
| --- | --- |
| Logs | Request/event detail, structured context, and correlation |
| Metrics | Aggregate, bounded-cardinality telemetry suitable for time-series analysis |

Request-specific detail MUST NOT be copied into metric labels merely because it is useful in logs.

Current canonical evidence provides an acceptable example: the custom `vorneq_db_queries_total` counter uses only the `alias` label. Database alias is a bounded, low-cardinality, non-sensitive dimension in the current design.

Correlation IDs, raw paths containing identifiers, email addresses, unrestricted URLs, and similar request-level values MUST remain out of metric labels.

### D9. Failure semantics

Metrics access-control failures MUST deny access rather than expose metrics publicly.

Metrics collection or scrape failures MUST NOT make the application unavailable and MUST NOT determine the health endpoint response unless the health contract explicitly includes the monitoring subsystem as a dependency.

Application availability MUST NOT depend on Prometheus scrape success.

### D10. Environment policy

| Environment | Policy |
| --- | --- |
| Local/development | Unrestricted metrics access is acceptable |
| Staging | Metrics restricted |
| Production | Metrics restricted |

Any exception that temporarily permits public metrics in a production-like environment MUST be explicitly approved, documented with a reason, and time-bounded.

### D11. Auditability

The observability access layer SHOULD make the following operationally observable where the selected control plane supports it:

- access-policy changes,
- credential rotation events,
- scraper authentication or authorization failures,
- repeated unauthorized access attempts,
- and sustained scrape failures.

Observability of the control plane MUST NOT itself leak secret credentials or other protected values. Logs SHOULD avoid recording full sensitive request paths when a safer normalized representation is available.

### D12. Implementation independence

This ADR freezes the policy boundary but does not select the final implementation product or mechanism.

Potential compliant implementations include:

- Cloudflare Access or another suitable edge access-control layer,
- Render or another hosting platform's private/internal network capability,
- an IP allowlist that satisfies D5,
- or a Django-level machine guard when edge/network enforcement is not practical.

Any implementation MUST satisfy D1-D11.

This follows the same decision pattern used by ADR-014: the architectural policy is frozen while the concrete implementation value is intentionally deferred to a later execution phase. ADR-014 is a pattern reference, not a binding precedent for the selected observability tool.

## Options Considered

### Option A — Keep `/metrics` public

**Rejected.** This preserves the known hardening gap recorded by PR #224 and provides unnecessary operational reconnaissance value to anonymous clients.

### Option B — Protect metrics with application login/session authentication

**Rejected as the primary architecture.** Browser-oriented authentication is a poor fit for Prometheus scraping and would unnecessarily couple observability to allauth/AXES and the user-authentication runtime.

### Option C — Edge/network access control

**Preferred.** This keeps machine telemetry independent from Django user authentication, can fail closed before application routing, and aligns with the remediation preference in the existing gap document.

### Option D — Django-specific machine guard

**Accepted fallback.** This is appropriate when edge or private-network controls are unavailable or unsuitable, provided it is independent from browser sessions and satisfies the fail-closed, proxy-trust, and data-minimization requirements above.

## Failure Semantics Summary

| Scenario | Required behavior |
| --- | --- |
| Unauthorized scraper | `401`/`403`, `404` by deliberate policy, or network-level denial |
| Edge/access-policy failure | Deny; never public fallback |
| Metrics collection failure | Metrics may become unavailable; application traffic and health remain independent |
| Health dependency failure | Health may report a bounded degraded/fail state according to its own contract |

The exact unauthorized response code remains an implementation decision; the frozen requirement is denial rather than information disclosure.

## Rollout

### Phase 1 — Policy adoption

This ADR is documentation-only.

- No runtime, configuration, dependency, routing, Auth/AXES, or deployment change is made by adopting this ADR.
- The Public Metrics Exposure gap remains open until a later implementation phase deploys an approved restriction.

### Phase 2 — Access-control implementation

Before implementation:

1. Inspect the actual staging/production deployment topology.
2. Identify the intended metrics scraper and its source/network identity.
3. Determine whether edge or private-path enforcement is feasible.
4. Implement the smallest compliant restriction in a separate PR/change set.
5. Verify in staging that:
   - an authorized scrape succeeds,
   - an unauthorized request is denied,
   - the application remains available,
   - and `/health/` continues to satisfy platform probe requirements.

### Phase 3 — Production rollout

Production rollout requires:

- the same or stronger access-control boundary used in staging,
- successful authorized scrape verification,
- visibility into sustained scrape failures,
- confirmation that unauthorized access is denied,
- and confirmation that the platform health probe remains healthy and independent.

### Phase 4 — Metrics hygiene

Optional follow-up work MAY inventory metric families and labels for:

- bounded cardinality,
- sensitive-data leakage,
- secret/PII safety,
- and obsolete or redundant dimensions.

Numerical SLOs, alert thresholds, and broader alerting/on-call policy should be handled separately.

## Rollback

Rollback MUST NOT normally mean restoring anonymous public `/metrics` access.

If a newly introduced restriction causes loss of monitoring, the preferred response order is:

1. Correct the scraper or access rule.
2. Use a temporary alternate restricted scrape path if available.
3. Move enforcement to an application-level machine guard if necessary.
4. Use a public exception only as a last resort, with explicit approval, a documented reason, and a time limit.

Application availability MUST remain independent of Prometheus scrape success throughout rollback and remediation.

## Consequences

### Positive

- Establishes an explicit access-control policy for operational telemetry.
- Separates public health semantics from restricted metrics.
- Makes fail-closed behavior the default in production-like environments.
- Keeps metrics access independent of Auth/AXES and end-user login state.
- Preserves machine-to-machine compatibility.
- Freezes metric-label data-minimization and cardinality principles.

### Negative

- Phase 2 requires real deployment-topology inspection before selecting an enforcement mechanism.
- The preferred solution may require an edge/platform capability not currently configured.
- The scraper must be configured with the selected machine access path rather than only a public URL.

### Neutral

- This ADR does not remove Prometheus or change the current metrics set.
- This ADR does not change `/health/` runtime behavior.
- The existing Public Metrics Exposure remains open until Phase 2 is executed.

## Related Documents

- PR #224 — `docs: add observability hardening gap for public metrics exposure`
- `docs/observability-gaps.md` — canonical record of the current Public Metrics Exposure gap
- ADR-014 — architectural-decision pattern reference: policy frozen while concrete implementation value remains deferred

These references provide context but do not override the independent decisions in this ADR.

## Open Questions

1. What scraper/service will consume VORNEQ metrics, and from what network/source identity?
2. Does the final Render deployment topology provide an adequate private/internal scrape path, or is an edge access layer required?
3. Will Cloudflare or another edge access-control layer be part of the production topology?
4. Should unauthorized metrics access return `404`, `401`/`403`, or be denied before reaching Django?
5. Should `/health/` remain a combined readiness endpoint, or should liveness and dependency readiness become separate endpoints in a future ADR/change?
6. Does the current metric-label inventory require a dedicated hygiene hardening change beyond the policy frozen here?

## Out of Scope

- Prometheus hosting/vendor selection
- Grafana selection or dashboard design
- numerical SLO targets
- PagerDuty or other on-call tooling
- ADR-014 email observability implementation
- Auth/AXES changes
- PR #239
- PR A, PR B, or PR C implementation
- ADR-013 transaction-ownership selection
- ADR-015 social-auth implementation
- ADR-016 migration execution

## Status Summary

| Item | Status |
| --- | --- |
| ADR-017 policy | Proposed (frozen policy; implementation deferred) |
| Metrics security class | Restricted/private operational telemetry |
| Health security class | Public-minimal permitted |
| Failure default | Fail-closed |
| Preferred enforcement | Edge/network boundary |
| Concrete tool/mechanism | Deferred to Phase 2 |
| Auth dependency | None |
| Current Public Metrics Exposure gap | Open until Phase 2 implementation |
