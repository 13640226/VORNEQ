# ADR-014: Email Delivery Strategy

## Status

Proposed (frozen architecture; vendor deferred)

## Date

2026-09-10

## Decision Statement

Production transactional email MUST use an HTTPS API backend through `django-anymail`; direct SMTP MUST NOT be the primary delivery path on Render Free.

Resend is recorded as the preferred Phase-2 candidate, not as a binding architectural decision.

## Context

VORNEQ currently sends transactional email through Django's SMTP backend:

- `EMAIL_BACKEND = django.core.mail.backends.smtp.EmailBackend`
- `EMAIL_HOST` is environment-configured.
- `EMAIL_PORT` defaults to `587`.
- `EMAIL_USE_TLS = True` by default.
- `EMAIL_TIMEOUT` is not explicitly configured.

A staging password-reset POST on Render Free failed while connecting through `socket.create_connection`, eventually leading to worker termination and HTTP 500.

Render Free Web Services do not permit outbound traffic to SMTP ports `25`, `465`, and `587`. VORNEQ's default SMTP port (`587`) is therefore incompatible with this deployment tier. Render documents upgrading the service tier as the path for continuing direct SMTP delivery.

Two independent defects are tracked by this ADR context:

| Defect | Severity | Description |
| --- | --- | --- |
| P0 | Critical | Direct SMTP is blocked on Render Free. |
| P1 | High | No explicit email network timeout is configured. |

P0 is the deployment-compatibility root cause. P1 increases the duration and operational impact of network failures but does not solve the blocked-port constraint.

## Decision Drivers

1. Must work on Render Free without requiring a plan upgrade.
2. Reliable delivery behavior and useful operational visibility.
3. API-key-based secret management through environment configuration.
4. Minimal additional dependency and integration complexity.
5. Compatibility with existing Django/allauth email integration.
6. Operationally realistic rollback paths.
7. Local development and tests must not require an external provider.
8. Minimize vendor lock-in.

## Decision

### D1. Production delivery architecture

Production transactional email MUST use an HTTPS API backend through `django-anymail`.

`django-anymail` is the abstraction layer so that provider changes do not require reopening this architectural decision.

### D2. Vendor selection is deferred

The concrete provider is selected during Phase 2 execution. Resend is the preferred current candidate; Postmark remains an alternate candidate.

Changing provider within the Anymail abstraction does not, by itself, amend ADR-014.

### D3. Direct SMTP is not the primary Render Free path

Direct SMTP MUST NOT be the primary production delivery mechanism while the application runs on Render Free.

SMTP may remain useful in environments where outbound SMTP is available, but it is not an operational rollback path on Render Free.

## Options Considered

| Option | Works on Render Free | Complexity | Observability | Outcome |
| --- | --- | --- | --- | --- |
| A. SMTP + paid Render instance | No, requires upgrade | Low | Limited | Not selected |
| B. HTTPS API + Anymail | Yes | Moderate | Strong | **Selected** |
| C. Provider-specific HTTP SDK | Yes | High | Strong | Rejected: higher lock-in |
| D. SMTP + async queue | No | High | Limited | Rejected: blocked port remains |

## Provider Evaluation

Provider selection is intentionally not frozen by this ADR. As of 2026-09, the current evaluation is:

| Criterion | Resend | Postmark | SendGrid |
| --- | --- | --- | --- |
| Free tier | 3,000/month, 100/day cap | 100/month | Limited/current plan dependent |
| Anymail backend | Supported | Supported | Supported but no longer officially tested/supported by Anymail |
| Developer experience | Modern | Mature | Mature/legacy-heavy |
| Transactional focus | Strong | Very strong | Mixed transactional/marketing |

**Preferred Phase-2 candidate:** Resend.

This preference is execution guidance only and is not a binding architectural decision.

## Timeout Policy

`EMAIL_TIMEOUT` applies to Django's SMTP backend. Anymail API backends use independent HTTP request timeout configuration.

Two explicit timeout policies are required:

| Layer | Setting | Value | Scope |
| --- | --- | --- | --- |
| Django SMTP backend | `EMAIL_TIMEOUT` | `10s` | SMTP only |
| Anymail API backends | `ANYMAIL = {"REQUESTS_TIMEOUT": 10}` | `10s` | Anymail API calls |
| Gunicorn worker | `--timeout 30` | `30s` | Whole request |

No universal implicit network timeout is assumed. Each network backend must have an explicit timeout appropriate to its implementation.

The target leaves approximately 20 seconds between the email network timeout and the current 30-second worker timeout, allowing the application to fail the email operation before Gunicorn terminates the worker.

## Failure Semantics

Email-delivery failure is not universally equivalent to either success or failure of the originating user action. Behavior depends on the flow.

### Signup without mandatory verification

If email verification is not mandatory, user creation may complete even when an email-delivery attempt fails. The failure must be logged and observable.

### Signup with mandatory verification

Account creation and the ability to use the account are separate states.

If a verification email cannot be delivered:

- The account may persist in an unverified state.
- Exact persistence behavior is implementation-dependent and MUST be verified by integration tests against the pinned allauth version.
- User-facing behavior must avoid leaking account-enumeration information.
- A resend/recovery path depends on a functioning email provider.

### Password reset

Password reset responses MUST preserve user-enumeration protection. Delivery failures must be logged at an operationally visible severity and surfaced to operators without exposing account existence to the requester.

### Asynchronous bounce

Bounce and delivery events are a future webhook concern. They should feed structured logs, metrics, and later retry policy.

## Retry Policy

### V1

No automatic application-level retry. Fail fast, log the failure, and preserve a clear recovery path.

### V2 (future proposal)

An asynchronous queue may add exponential backoff and bounded retries. Queue technology and retry counts are outside this ADR.

## Observability

### V1

Structured events should cover:

- `email.attempt`
- `email.success`
- `email.failure`

Metrics should include counters equivalent to:

- `email_sent_total{provider,status}`
- `email_failed_total{provider,reason}`

Logs must avoid storing full recipient addresses when domain-level information is sufficient.

### V2

Provider webhooks may add delivery, bounce, and related status events, with alerts for significant failure or bounce-rate changes.

## Secrets and Environment Configuration

Provider credentials MUST remain in environment/secret management and MUST NOT be committed to the repository.

Local development and tests remain network-independent:

- Local development: Django console backend.
- Tests: Django locmem backend where appropriate.
- Staging/production: Anymail HTTPS provider after Phase 2 execution.

## Rollback

Rollback complexity is operational, not merely a backend-string change.

| Rollback | Complexity | Notes |
| --- | --- | --- |
| Remove `EMAIL_TIMEOUT` | Low | Single config change |
| HTTP provider A -> B | Moderate | Backend, API key, provider/domain setup |
| HTTP -> SMTP on Render Free | Not operational | SMTP ports remain blocked |

Provider-to-provider migration may also require domain verification and DNS changes before traffic can be moved safely.

## Rollout

### Phase 1 - Configuration-level resilience

Proposal only; separate execution PR:

1. Add `EMAIL_TIMEOUT = 10` for SMTP.
2. Add `ANYMAIL = {"REQUESTS_TIMEOUT": 10}` for Anymail API backends when the dependency/config is introduced.
3. Confirm local development remains compatible with the console backend.
4. Do not change the production delivery path merely by documenting this ADR.

### Phase 2 - Provider execution

After the Auth baseline is ready for execution:

1. Select the final provider; Resend is the preferred candidate.
2. Create the provider account and verify the sending domain.
3. Add the required `django-anymail` provider dependency.
4. Configure the Anymail backend in staging.
5. Test password-reset delivery in staging.
6. Monitor for 48 hours.
7. Promote to production after successful validation.

### Phase 3 - Extended observability

Optional future work: provider webhooks, richer metrics, and alerts.

## Open Questions

1. Final Phase-2 vendor: Resend vs Postmark or another suitable Anymail provider.
2. Whether a secondary provider is justified in V2.
3. Whether V2 requires Celery/RQ or another queue.
4. Webhook signature-verification policy in V3.
5. Final sending domain and provider-specific DNS records.

## Related ADRs

Contextual only; neither ADR is a binding precedent for this decision:

- ADR-004: Artifact Registry and Identity Layer.
- ADR-013: IdentityHandle - Canonical Handle Allocation.

Their failure-semantics discussions provide context, but Email Delivery Strategy stands on its own architectural decision.

## Consequences

### Positive

- Works with Render Free's HTTPS egress path.
- Reduces provider lock-in through the Anymail abstraction.
- Enables stronger provider-level observability.
- Uses environment-managed API credentials.
- Keeps development and tests independent of external email infrastructure.

### Negative

- Adds a `django-anymail` dependency when execution begins.
- Requires provider account and domain verification.
- May incur provider cost as volume grows.
- SMTP is not a usable fallback on Render Free.
- The current password-reset failure remains unresolved until Phase 2 is executed.

## Out of Scope

- Binding selection of the final provider.
- Async queue implementation.
- Webhook implementation.
- Backup-provider strategy.
- Changes to allauth flows.

## References

- Render: Free Web Services SMTP outbound-port restriction.
- django-anymail documentation for provider backends and request timeouts.
- Provider pricing and operational documentation are execution-time inputs and MUST be re-checked during Phase 2.
