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

## C1 Amendment — Decisions Recorded (2026-09-11)

This amendment records C1 governance decisions without changing the ADR status, implementing runtime behavior, or resolving evidence-gated implementation details. [session governance]

### Section A — OQ1–OQ4 Decisions

#### A.1 OQ4 — Unlink / Last-Authentication-Method Guard

Status: **Decided (session governance).** [session governance]

A user MUST NOT be allowed to unlink an authentication method if doing so would leave the user without any functional authentication method or verified recovery path. [session governance]

A functional alternative means at least one active authentication method, or a verified recovery path such as a verified email address plus a working password-reset path, or another separately approved recovery method. [session governance]

If at least two functional methods remain, unlinking MAY proceed subject to confirmation of the alternative path; if only one functional method remains, unlinking MUST be rejected. [session governance]

The invariant is policy-level and MUST NOT be weakened by UI behavior. [session governance]

The exact mechanism, timing/grace behavior, provider-initiated unlink behavior, support-mediated edge cases, exception authority, and implementation detection logic remain open. [open — implementation]

#### A.2 OQ2 — Support Workflow for Users Who Cannot Link Accounts

Status: **Decided (session governance).** [session governance]

A support workflow MUST exist for users who cannot link accounts. [session governance]

The workflow has four invariants: identity verification before manual action; no bypass of D5 Type 1 or Type 2 conflict policy; every support action is auditable; and the neutral rejection entry point directs the user to the support workflow. [session governance]

Whether the workflow is self-service, manual, or hybrid; the exact verification method; SLA/timing; escalation path; notification mechanism; support authority; and detailed interaction with OQ4 remain open. [open — implementation]

#### A.3 OQ1 — Neutral Wording for Linking Rejection

Status: **Decided (session governance), exact wording open.** [session governance]

User-facing rejection wording MUST NOT distinguish D5 Type 1 from Type 2, disclose another account owner, disclose an email-match condition, or expose backend audit-reason strings. [session governance]

The wording MUST provide a neutral support pointer consistent with OQ2. [session governance]

Backend reason codes such as `account_owned_by_other` and `email_match_other_user` remain audit semantics and MUST NOT be surfaced as user-facing wording. [ADR-015] [session governance]

Exact localized text, error codes, accessibility details, and any secondary notification channel remain open. [open — implementation]

#### A.4 OQ3 — AuditEvent Schema vs Structured Logs

Status: **Decided (session governance) across six governance axes; implementation/evidence gates remain open.** [session governance]

The six axes and their closure are recorded in Section B. [session governance]

### Section B — OQ3 Axis Closure

#### B.1 Failure Semantics (FS)

Canonical events are `social.signup` (E1), `social.login` (E2), `social.linking.attempted` (E3), and `social.linking.rejected` (E4). [ADR-015]

E4 is **Class A — security-critical, fail-loud**: linking rejection itself MUST remain enforced even if audit persistence fails; audit failure MUST NOT roll back the rejection; audit failure MUST be explicitly observable/alertable; silent failure is prohibited. [session governance]

E1, E2, and E3 are **Class B — operational observability, best-effort after-commit**: business flow continues if audit persistence fails; no rollback is required; a silent log is acceptable; alerting is optional. [session governance]

“Auditable” does not mean transactionally coupled or fail-closed. [session governance]

“Alertable” is a governance requirement and does not assert that alerting infrastructure currently exists. [session governance]

The classification is static-by-default and reviewable; class changes require explicit governance review and MUST NOT be runtime-configurable. [session governance]

#### B.2 PII Classification

This classification applies only to E1–E4 and does not establish a general VORNEQ logging/privacy policy. [session governance]

- F1 VORNEQ user id: **Required**, internal id only. [session governance]
- F2 provider name: **Required**, closed provider enum. [session governance]
- F3 provider subject/user id: **Allowed-bounded**, opaque, bounded type/length, with no semantic interpretation. [session governance]
- F4 provider email: **Prohibited** from the audit payload. [session governance]
- F5 IP address: **Deferred / prohibited-by-default**; it MUST NOT be collected until independently justified and approved. [session governance]
- F6 user-agent: **Deferred / prohibited-by-default**; it MUST NOT be collected until independently justified and approved. [session governance]
- F7 correlation id: **Required** only when generated by VORNEQ and not derived from PII. [session governance]
- F8 reason code: **Required where applicable and event-schema-bounded**; it is required for `social.linking.rejected` but is not globally required for successful events. [session governance]
- F9 raw provider payload, token, or credential material: **Prohibited absolutely** in the audit payload. [session governance]

Data minimization applies even to Class A events; auditability does not license raw provider identity or credential data. [session governance]

A `Prohibited` field may become allowed/required only through explicit governance review with independent justification; implementation/runtime configuration MUST NOT broaden the payload. [session governance]

#### B.3 Access / Query Audience

A1 Security/Incident, A2 Support, and A3 Privileged Operational/Admin are in-scope human read audiences; A4 Automated Alerting is in-scope as emission-side behavior, not a read audience; A5 User Self-Service and A6 External/Compliance Export are deferred pending independent use cases. [session governance]

A1 MAY read all four events and F1/F2/F3/F7/F8 only as necessary for a specific investigation. [session governance]

A2 defaults to E3/E4 and F1/F2/F7/F8; F3 is visible only for an explicit provider-conflict/provider-confusion use case. Support queries MUST use F1 as the input selector, not email or provider subject, and MUST remain single-user scoped. [session governance]

A3 is allowed only for approved, bounded operations and MUST NOT be broad-by-default or serve as a bypass around A1/A2 constraints. [session governance]

A4 is emission-side for E4, not a polling/read path, and uses only the minimal F1/F2/F7/F8 alert payload unless a separate justification is approved. [session governance]

Bulk browsing, unrestricted search, and default export are prohibited. Human queries MUST be selector-based and purpose-bound; result windows/counts MUST be bounded; rate limiting is required with exact values deferred to implementation. [session governance] [open — implementation]

Every privileged human audit read MUST itself be recorded through a non-recursive access-log channel containing at least actor, purpose, selector class, timestamp, and result count, without the returned payload. [session governance]

The persistence location of the access-log is deferred to topology/implementation. [open — implementation]

#### B.4 Retention

Status: **Partially Decided — class mapping and semantics decided; numeric duration and deletion mechanism evidence/implementation-gated.** [session governance]

For Art-1 social-auth events: E4 maps to `security`; E1/E2/E3 map to `standard`. A future E1 promotion to Class A would require a separate retention-class governance review rather than changing automatically. [session governance]

For Art-2 access logs: A1 and A3 access entries map to `security`; A2 access entries map to `standard`; A4 emission-side alerting creates no read-access-log artifact. [session governance]

Retention class does not determine retention duration; retention policy does not prove implementation; and longer retention is not automatically safer. [session governance] [repo evidence]

Numeric duration is deferred/evidence-gated. Security duration requires incident-detection and investigation-window evidence; standard duration requires support operational-window evidence; Art-2 duration requires an accountability/abuse-detection window. [open — evidence-gated]

After an approved duration, expiry semantics are **hard delete**; soft-delete is rejected because it continues retention. [session governance]

Archival is **none by default**. Archive/cold-storage/export requires an independent use case and governance review and MUST NOT be used to bypass retention. [session governance]

The deletion mechanism (TTL, periodic job, storage lifecycle, or equivalent) is implementation-gated and MUST be fail-observable and testable. [open — implementation]

Legal/compliance hold is absent by default and requires an independent obligation plus explicit governance review. [session governance] [open — evidence-gated]

Art-2 retention remains independent from Art-1 even when both use the same `standard` or `security` class label. [session governance]

Unresolved duration MUST NOT be interpreted as infinite retention or as authorization for arbitrary deletion. [session governance]

#### B.5 Immutability / Tamper-Evidence

Status: **Decided at requirements level; mechanism/topology-gated.** [session governance]

Immutability and tamper-evidence are distinct; the existing ORM append-only guard is application-layer evidence only and does not prove DB-level immutability or protection against privileged actors. [session governance] [repo evidence]

The bounded threat model is T1 application bug/ordinary application actor, T2 compromised application credential, and T3 privileged DB/operator actor. T1/T2 prevention is required; T3 requires independently verifiable detection rather than absolute prevention. [session governance]

For both Art-1 and Art-2, unauthorized UPDATE, pre-expiry DELETE, and unauthorized INSERT MUST be prevented against T1/T2 and detectable against T3. [session governance]

Authorized expiry deletion remains permitted and MUST be distinguishable and auditable. [session governance]

The protection level is an I6 bounded combination at requirements level: DB-level write separation/control for T1/T2 plus a tamper-evidence mechanism for T3. The concrete choice among hash-chain, external signing, WORM-like storage, or equivalent is deferred to topology discovery. [session governance] [open — implementation]

Tamper-evidence MUST be independently verifiable relative to the actor under threat. If the same actor/credential can rewrite both the authoritative audit record and its tamper evidence without leaving detectable evidence, the T3 requirement is not satisfied. [session governance]

The protection mechanism MUST NOT convert authorized hard expiry into infinite retention. [session governance]

#### B.6 Topology

Status: **Decided at architecture level; mechanism discovery-gated.** [session governance]

The selected architecture is **C-3 Hybrid bounded**. [session governance]

Art-1 authoritative source is the `AuditEvent` database store. [session governance] [repo evidence]

Art-2 uses an authoritative logical store independent from Art-1 in authority and lifecycle; it MAY later share the same physical database only with appropriate logical/role separation. [session governance] [open — implementation]

The tamper-evidence channel is non-authoritative, independent from the authoritative store, and exists only for tamper detection; it MUST NOT serve A1/A2/A3 queries. [session governance]

Structured logs remain non-authoritative non-audit observability and MUST NOT silently become a fallback source of truth for Art-1 or Art-2. [session governance]

Hybrid does not mean dual-authoritative. A mismatch between the authoritative record and the evidence channel MUST become a failure/security signal rather than causing one source to silently replace the other. [session governance]

A4 remains emission-side and MUST NOT poll or broadly read the authoritative audit store. [session governance]

C-1 Dedicated AuditEvent-only and C-2 Structured logs-only are rejected because they do not independently satisfy the T3 tamper-detection requirement; C-4 External audit backend is not selected and remains conditional because external SaaS is the last option. [session governance]

D-c (DB + independently controlled external evidence storage) and D-d (DB + signing service) enter a Topology Discovery Gate. [session governance] [open — evidence-gated]

The gate requires all of the following: (G1) a T3 actor may be able to alter the authoritative DB but cannot alter tamper evidence without a detectable trace; (G2) credential ownership/access boundaries proving this separation are demonstrable; (G3) authorized expiry remains possible and auditable; and (G4) failure mode and verification path are testable. [session governance]

D-c is preferred if it satisfies the gate because it has lower intended complexity/external dependency; if D-c fails, D-d is evaluated; if D-d also fails, C-4 may enter the decision space and the external-SaaS trust-boundary interaction requires explicit review. [session governance] [open — evidence-gated]

### Section C — Provenance Discipline

The C1 decisions in this amendment are session-governance decisions recorded against baseline `main@803a6d153a1819c41d678b3b0e6d5f60da4f4b5f`. [session governance]

Existing ADR statements are marked `[ADR-015]` where needed to distinguish source policy from the amendment. [session governance]

Read-only repository findings supporting this amendment are marked `[repo evidence]`; they establish repository state only and do not prove runtime-active behavior. [repo evidence]

Implementation and evidence gaps remain explicitly marked `[open — implementation]` or `[open — evidence-gated]` and MUST NOT be interpreted as implemented, deployed, or runtime-active. [session governance]

### Section D — Open Implementation / Evidence Gates

#### D.1 Retention gates

- Incident detection window data. [open — evidence-gated]
- Investigation window data. [open — evidence-gated]
- Support operational window. [open — evidence-gated]
- Numeric duration for `security`, `standard`, and Art-2 retention. [open — evidence-gated]
- Concrete deletion mechanism and deletion observability. [open — implementation]
- Structured-log retention interaction. [open — evidence-gated]

#### D.2 Topology / trust-boundary gates

- Demonstrate D-c against G1–G4 in actual infrastructure. [open — evidence-gated]
- If D-c fails, demonstrate D-d against G1–G4. [open — evidence-gated]
- If both fail, reopen C-4 External audit backend and explicitly review the external trust boundary. [open — evidence-gated]
- Concrete DB role/write-separation design for T1/T2 prevention. [open — implementation]
- Concrete tamper-evidence mechanism and independently-verifiable verification path. [open — implementation]

#### D.3 Social-audit implementation gates

- Add E1–E4 to the audit-event schema/validation gateway; the current repository gateway does not yet include the four social events. [repo evidence] [open — implementation]
- Implement the bounded A1/A2/A3 query/read layer without broad browsing. [open — implementation]
- Implement Art-2 non-recursive access-log storage and writer. [open — implementation]
- Select and implement the A4 alert target/channel. [open — implementation]
- Implement and test authorized-expiry deletion and its audit signal. [open — implementation]
- Define tests for T3 detection and tamper-evidence mismatch behavior. [open — implementation]

#### D.4 Other evidence gates

- Establish whether alerting infrastructure exists and is suitable for the Class A fail-loud requirement. [open — evidence-gated]
- Resolve applicable jurisdiction/privacy obligations, including any right-to-erasure interaction, before using them as retention requirements. [open — evidence-gated]
- Establish any independent legal/compliance-hold use case before introducing a hold mechanism. [open — evidence-gated]
- Establish any justified aggregation/anonymization window before retaining aggregates beyond raw-event expiry. [open — evidence-gated]
- F5 IP address and F6 user-agent remain prohibited-by-default unless a separate threat model or independent requirement justifies collection. [session governance] [open — evidence-gated]

### Section E — Cross-Cutting Boundaries

1. Least privilege and purpose-bound access apply to every human read; permission alone is insufficient. [session governance]
2. The PII classification is a ceiling, not a visibility floor for every audience. [session governance]
3. F4 provider email and F9 raw provider payload/token/credential material are prohibited from these audit payloads; F5/F6 are not collected while deferred. [session governance]
4. Auditability does not authorize raw provider data collection. [session governance]
5. Privileged audit reads are recorded through a non-recursive access-log path. [session governance]
6. Bulk browsing, unrestricted search, and default export are prohibited. [session governance]
7. Retention duration unresolved does not mean keep forever and does not authorize arbitrary deletion. [session governance]
8. Authorized hard-expiry deletion is compatible with immutability and MUST be distinguishable from unauthorized pre-expiry deletion. [session governance]
9. T3 tamper evidence must be independently verifiable relative to the privileged actor being detected. [session governance]
10. Hybrid topology has one authoritative source per artifact; the tamper-evidence channel is not a second source of truth. [session governance]
11. External audit SaaS/backend is not selected by this amendment and is considered only if the bounded hybrid discovery gate fails. [session governance]
12. Implementation/runtime configuration MUST NOT widen event classes, PII payload, audiences, authoritative-source definitions, retention policy, or protection requirements without explicit governance review. [session governance]

### Section F — Status of This Amendment

This amendment records session-canonical governance decisions for C1 and closes OQ1–OQ4 at the governance level, including the six-axis OQ3 decision. [session governance]

The ADR document status remains **Proposed (frozen architecture; implementation deferred)**. [ADR-015] [session governance]

This amendment does not implement social authentication, create migrations, modify settings, configure a provider, alter OAuth credentials, change runtime behavior, deploy code, or establish that any evidence-gated mechanism is active. [session governance]

Retention remains partially decided because numeric duration and deletion mechanism are still evidence/implementation-gated. [session governance]

Immutability is decided at requirements level while the concrete mechanism is topology-gated, and topology is decided at architecture level while D-c/D-d remain discovery-gated. [session governance]

Open Questions 1–4 remain textually present above for historical traceability; this amendment is the controlling C1 governance record for their decisions. Open Questions 5–6 remain unresolved by C1. [session governance]