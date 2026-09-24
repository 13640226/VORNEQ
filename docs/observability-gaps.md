# Observability / Security Hardening Gaps

## 1. Public Metrics Exposure

**Date recorded:** 2026-09-09  
**Status:** Open (hardening gap, not blocker)  
**Environment:** Staging (and potentially Production)

### Gap description

- The Prometheus `/metrics` endpoint is exposed through the public URL surface without authentication or an IP restriction.
- The endpoint can expose operational metadata such as topology, route names, traffic patterns, error rates, and query behavior.

### Evidence

- A live read-only review of `main@153bea5a1189caba7cf078d895007b250b19855a` confirmed that `django_prometheus.urls` is included directly in `config/urls.py`.
- External operational verification confirmed that `/metrics` returns Prometheus-formatted metrics without authentication.

### Risk

- **Severity:** Moderate hardening risk; not a release blocker by itself.
- The exposure does not establish disclosure of sensitive user data, but it can provide useful reconnaissance about internal application behavior.

### Remediation options without application-code changes

1. Restrict access at the edge, for example with Cloudflare Access or an appropriate IP allowlist for the metrics scraper.
2. Disable public metrics exposure temporarily until a monitoring backend and restricted scrape path are available.

### Remediation option requiring application-code changes

3. Add explicit authentication or an IP-based access guard around the metrics endpoint in Django if edge-level controls are unavailable or unsuitable.

### Current decision

Record the exposure as an open Observability/Security hardening gap and take no immediate runtime action. If remediation becomes necessary, prefer a narrowly scoped edge/configuration solution before introducing an application-code change.
