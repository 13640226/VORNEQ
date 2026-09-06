# VORNEQ Security Baseline

This document records the V1 application-security baseline. It does not change trust, verification, evidence, reputation, or entitlement semantics.

## Existing protections retained

- Django `SecurityMiddleware`
- HTTPS redirect in production
- one-year HSTS with subdomains and preload in production
- secure session and CSRF cookies in production
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- django-axes lockout with a five-failure threshold and username + IP lockout key

## Content Security Policy

`django-csp` provides the response header. The baseline uses `default-src 'self'`, blocks objects and framing, restricts forms to the same origin, and permits HTTPS images/media for opt-in object-storage/CDN deployments.

The current frontend still contains intentional inline theme/bootstrap and style code, so `script-src` and `style-src` temporarily include `unsafe-inline`. Removing those allowances requires a separate nonce/hash migration and should be treated as a tightening PR rather than silently breaking existing pages.

## Authentication rate limits

VORNEQ uses django-allauth's native cache-backed rate limiting rather than adding a second rate-limit package:

- login: `20/m/ip`
- failed login: `10/m/ip,5/5m/key`
- signup: `5/10m/ip`
- password reset request: `5/15m/ip,3/15m/key`
- password reset from key: `10/m/ip`

These controls complement django-axes. Allauth limits request/action rates; axes provides authentication-failure lockout.

## Client IP and reverse proxies

Client IP detection is security-sensitive. VORNEQ trusts zero proxies by default. Production must explicitly configure the actual deployment topology with:

- `ALLAUTH_TRUSTED_PROXY_COUNT`
- `ALLAUTH_TRUSTED_CLIENT_IP_HEADER`

Do not trust `X-Forwarded-For` generically without matching the real proxy chain.

## Dependency audit

`.github/workflows/security.yml` runs `pip-audit` for pull requests, pushes to `main`, and weekly. Findings block the security job instead of being marked `continue-on-error`.

## Secret scanning

A repository-wide secret scanner is intentionally not introduced as a non-blocking cosmetic check. A future PR should bootstrap a reviewed `detect-secrets` baseline, classify any existing findings, and then enforce prevention of new secrets.

## Follow-up hardening

Recommended separate changes after this baseline:

1. migrate inline scripts/styles to CSP nonces or hashes and remove `unsafe-inline`;
2. validate proxy/IP settings against the production ingress configuration;
3. bootstrap and audit a secret-scanning baseline;
4. add security-event observability without logging credentials or sensitive payloads.
