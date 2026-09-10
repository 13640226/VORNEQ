# ADR-015: Social Authentication & Account Linking Policy

**Status:** Proposed (frozen architecture; implementation deferred)  
**Date:** 2026-09-10

## Context

VORNEQ uses `django-allauth` for authentication. `allauth.account` and `allauth.socialaccount` are enabled, local signup uses username/email/password, and `SOCIALACCOUNT_AUTO_SIGNUP = True`. No social provider is currently configured.

The product roadmap requires Google OAuth first, Apple Sign In second, Phone Authentication as an independent subsystem, and potentially additional providers later.

Account linking is a security boundary rather than only a UX decision. This ADR freezes the policy before implementation.

The currently pinned dependency is `django-allauth==65.19.2`. Implementation details and exact adapter hooks MUST be verified against the pinned version at execution time.

## Decision Drivers

1. Account-takeover prevention.
2. No implicit trust in an asserted email address.
3. Avoid unnecessary duplicate accounts while preserving security boundaries.
4. Portable identity independent of any single provider.
5. Compatibility with allauth defaults and the pinned version.
6. Gradual provider-by-provider rollout.
7. Auditable authentication and linking decisions.

## Decision

### D1. HTTPS OAuth/OIDC only

Social providers MUST use HTTPS OAuth/OIDC flows. Insecure authentication methods such as basic authentication or direct plain credentials are not accepted as social authentication mechanisms.

### D2. Provider rollout order

The rollout order is frozen as:

1. Google OAuth.
2. Apple Sign In, after the Google callback and secret-management path is stable.
3. Phone Authentication, governed by a separate future ADR because it is an independent SMS/OTP subsystem.

Additional providers are evaluated case by case.

### D3. No email-based automatic authentication or connection

`SOCIALACCOUNT_AUTO_SIGNUP = True` does not itself mean automatic account linking.

On canonical `main`, `SOCIALACCOUNT_EMAIL_AUTHENTICATION` and `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT` are not explicitly configured; current effective behavior therefore relies on django-allauth defaults.

The social-auth implementation MUST explicitly configure:

```python
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
```

V1 MUST NOT automatically authenticate or connect accounts solely because email strings match. Changing either frozen value requires an explicit ADR amendment.

### D4. Explicit authenticated linking

Linking MUST begin from an authenticated VORNEQ session and use the provider's successful OAuth/OIDC authentication through allauth's connect flow.

The core security boundary is:

- the linking operation originates from an authenticated session;
- the provider authentication succeeds; and
- the provider account is not already owned by another VORNEQ user.

Email equality is not an inherent OAuth requirement. Nevertheless, V1 applies the conservative cross-email restriction in D5.

### D5. Conflict resolution

Two conflicts are distinguished.

**Type 1 — provider account already connected to another User:** linking MUST be rejected. This ownership conflict is a permanent invariant and MUST NOT be relaxed by a future provider-specific exception.

Audit reason: `account_owned_by_other`.

**Type 2 — provider email matches an email associated with another User:** V1 MUST reject linking. This is a conservative V1 policy rather than an inherent OAuth requirement and MAY be relaxed only by an explicit ADR amendment with an appropriate verified-provider trust model.

Audit reason: `email_match_other_user`.

Rejected linking MUST use neutral user-facing messaging and MUST NOT automatically merge accounts.

### D6. Verified-email exceptions are deferred

A future amendment MAY permit email-based automatic authentication or connection only if all of the following are true:

- the provider explicitly attests that the email is verified;
- the provider is present in a config-driven trusted-provider allowlist; and
- an explicit ADR amendment approves the exception.

V1 has no such exception.

### D7. Social-user provisioning and lifecycle integration

Social-user provisioning MUST eventually use the same canonical lifecycle adapter as local signup once that adapter is separately approved and implemented.

This ADR does not make the proposed PR B lifecycle adapter normative and does not choose transaction ownership. Exact transaction ownership remains governed by ADR-013 D3.1 and its future decision/amendment.

Expected future Identity/Handle failure semantics are therefore conditional on separate lifecycle approval and are not declared here as current executable behavior.

### D8. Phone Authentication is a separate subsystem

Phone Authentication requires its own decisions for an SMS provider, OTP generation and rate limiting, phone-number normalization and storage, SMS-bombing protection, enumeration resistance, and recovery semantics. It MUST be covered by a separate ADR before implementation.

### D9. Adapter-based policy enforcement

Policy enforcement MUST be implemented through `SOCIALACCOUNT_ADAPTER`, not through signals used to intervene in authentication flow.

The exact adapter hook or combination of hooks MUST be verified against the pinned django-allauth version during implementation. Candidate integration points include `pre_social_login()`, `can_authenticate_by_email()`, `is_email_verified()`, `authenticate_by_email()`, and connect-specific adapter behavior where supported.

This ADR freezes the policy, not a specific hook implementation.

## Options Considered

### Option A — email-match automatic authentication/linking (allauth opt-in)

This requires opting into email-based authentication behavior. It offers simpler UX but expands the account-takeover trust boundary to provider email assertions. Rejected for V1.

### Option B — no automatic linking; explicit adapter-enforced linking

Users explicitly initiate linking from an authenticated session. This adds a small UX cost but preserves a stronger ownership boundary. **Selected.**

### Option C — automatic connection for trusted verified-email providers

Potentially simpler UX, but security depends on a maintained provider trust list and verified-email semantics. Deferred to a future ADR amendment.

## Provider Details

### Google OAuth

Implementation MUST add `allauth.socialaccount.providers.google` to `INSTALLED_APPS` and choose exactly one canonical credentials source for VORNEQ: either `SocialApp` database configuration or `SOCIALACCOUNT_PROVIDERS` settings/environment configuration. The implementation MUST avoid duplicate provider-app configuration across both mechanisms.

Requested scopes are `profile` and `email`. Staging and production callback URLs MUST be configured separately. PKCE behavior and the exact setting name MUST be verified against the pinned django-allauth version rather than assumed from generic documentation.

### Apple Sign In

Implementation uses `allauth.socialaccount.providers.apple`. Apple configuration uses `APPS`, with Services ID for web callbacks and Bundle ID for iOS where applicable; `certificate_key` belongs to the relevant app settings.

Apple's cross-origin POST callback and its interaction with `SameSite=Lax` session behavior MUST be tested during implementation, including middleware that could create or replace sessions during callback processing.

### Phone Authentication

Deferred to a separate ADR.

## Failure Semantics

Identity fail-closed and Handle best-effort behavior are expected future lifecycle semantics only if the separately proposed lifecycle work is approved. ADR-015 does not establish them as current runtime behavior.

OAuth callback/authentication failures SHOULD be captured through supported `SOCIALACCOUNT_ADAPTER` error hooks, including `on_authentication_error()` where appropriate for the pinned version, with neutral UX.

Linking rejection MUST produce neutral UX and an auditable rejection reason.

## Observability

V1 SHOULD emit structured events equivalent to:

- `social.signup`
- `social.login`
- `social.linking.attempted`
- `social.linking.rejected`

Metrics SHOULD provide an equivalent of `social_auth_total{provider,action,status}` without exposing unnecessary personal data.

Authentication errors SHOULD be instrumented through supported adapter hooks rather than assuming a generic allauth event. A future phase MAY add alerts for abnormal linking-rejection or callback-failure rates.

## Rollout

### Phase 1 — Google OAuth

1. Register the application with Google.
2. Add the Google provider application and choose one credentials source.
3. Explicitly configure the frozen email-authentication and auto-connect settings as `False`.
4. Configure separate staging and production callback URLs.
5. Verify PKCE behavior against the pinned django-allauth version.
6. Test new social signup and explicit linking in staging.
7. Test Type 1 and Type 2 conflict rejection.
8. Monitor for 48 hours.
9. Promote to production only after the existing Auth baseline/runtime blockers and required recovery dependencies permit execution.

### Phase 2 — Apple Sign In

Proceed after Google is stable, with equivalent ownership/linking tests plus Apple credential, callback, and `SameSite=Lax` interaction testing.

### Phase 3 — Phone Authentication

Requires a separate ADR before execution.

## Rollback

Disabling a provider MUST NOT strand users whose only usable authentication method is that provider.

Before disabling a provider, operators MUST identify dependent social-only users and guarantee at least one usable alternative authentication or recovery method. Recovery through password reset depends on a functioning email-delivery path and therefore relates operationally to ADR-014.

Provider disablement can then remove or deactivate provider configuration and associated UI entry points. Existing users with a confirmed alternative authentication method remain able to authenticate through that method.

The no-email-auto-link security invariant itself is not an operational rollback switch. Relaxing it requires an explicit ADR amendment and review.

## Consequences

### Positive

- Reduces account-takeover risk from email-only matching.
- Preserves portable identity rather than provider-owned identity.
- Supports gradual provider rollout.
- Makes linking decisions auditable.
- Uses adapter-based policy enforcement rather than signal ordering.

### Negative

- Explicit linking adds UX friction.
- Provider secrets and callback URLs add operational complexity.
- Apple adds callback/session complexity.
- Safe provider rollback requires recovery-path planning.

### Neutral

- `SOCIALACCOUNT_AUTO_SIGNUP = True` may remain for new-user signup.
- Email-based authentication and automatic connection remain explicitly disabled in the future social-auth implementation.

## Open Questions

1. Exact neutral wording for linking rejection.
2. Support workflow for users who cannot link accounts.
3. Whether audit events extend the existing AuditEvent schema or remain structured logs.
4. Disconnect/unlink procedure and last-authentication-method guard.
5. Exact PKCE configuration for the pinned django-allauth version.
6. Apple `SameSite=Lax` callback behavior under VORNEQ middleware.

## Out of Scope

- Phone Authentication implementation.
- Passkeys/WebAuthn.
- Enterprise SSO/SAML.
- Automatic connection for trusted verified-email providers without a future amendment.
- Implementing the lifecycle adapter proposed outside this ADR.
- Changing transaction ownership defined/deferred by ADR-013.

## Related ADRs

- ADR-013: IdentityHandle — provisioning context and deferred transaction ownership.
- ADR-014: Email Delivery Strategy — recovery-path dependency.

These ADRs are contextual dependencies only where explicitly stated; ADR-015 establishes its own social-authentication and account-linking decisions.
