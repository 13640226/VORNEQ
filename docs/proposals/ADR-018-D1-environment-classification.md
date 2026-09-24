# ADR-018 D1 — Environment Classification Implementation Record

Status: Implemented / descriptive record

Related ADR: `docs/adr/018-deployment-topology-and-environment-isolation.md`

Implementation: PR #255 — `feat: enforce VORNEQ_ENV classification (ADR-018 D1)`

Canonical implementation baseline: `main@3a15acfb9c816acb0ca511fe866aeab512542550`

## Purpose

This document records the design and implemented contract for ADR-018 Decision D1 after implementation. It is retrospective and descriptive: it does not authorize implementation, deployment changes, environment mutations, or any later ADR-018 decision.

The D1 implementation was already merged through PR #255 before this record was created.

## Implemented contract

VORNEQ classifies each application process with the required `VORNEQ_ENV` environment variable.

The accepted values are exactly:

- `development`
- `staging`
- `production`

Classification is validated while Django settings are imported so invalid deployment state fails before the application begins serving requests.

### Boot behavior

| `VORNEQ_ENV` | `DEBUG` | Result |
| --- | --- | --- |
| unset or empty | any | fail at boot with `ImproperlyConfigured` |
| invalid value | any | fail at boot with `ImproperlyConfigured` |
| `development` | either | allowed |
| `staging` | `False` | allowed |
| `staging` | `True` | allowed with warning |
| `production` | `False` | allowed |
| `production` | `True` | fail at boot with `ImproperlyConfigured` |

Values are not normalized into an accepted environment. For example, a capitalized value such as `Production` is invalid rather than being silently converted to `production`.

## Repository implementation

PR #255 implemented D1 through a deliberately bounded change set:

- `config/settings.py` — defines and validates `VORNEQ_ENV` and the production/staging DEBUG rules.
- `.env.example` — documents the required environment classification and uses `development` as the example value.
- `.github/workflows/ci.yml` — explicitly classifies CI as `development`.
- `apps/core/tests/test_env_classification.py` — exercises the real settings-import path in subprocesses, including accepted and rejected combinations.

The implementation does not derive `DEBUG` from `VORNEQ_ENV`; the two settings remain independently configured and D1 validates prohibited combinations.

## Deployment evidence

After PR #255 was merged, the staging deployment initially failed at boot because `VORNEQ_ENV` was unset. Setting the staging service classification to `VORNEQ_ENV=staging` allowed the service to boot successfully. This behavior is consistent with the fail-at-boot D1 contract.

This record does not prescribe or perform any additional Render environment mutation.

## Failure semantics

D1 is intentionally fail-closed for missing or invalid classification and for the unsafe `production` plus `DEBUG=True` combination. A staging process with `DEBUG=True` remains bootable but emits a warning so that D1 does not silently reinterpret deployment configuration.

## Scope boundary

This record covers ADR-018 D1 only.

It does **not** implement, authorize, or change ADR-018 D2–D17. In particular, it does not establish live topology evidence for database, storage, ingress/proxy, observability, backup/recovery, or provider-specific isolation decisions.

It also makes no changes to authentication, AXES, email delivery, IdentityHandle provisioning, PR B, PR C, ADR-017 Phase 2, or PR #239.

## Status

D1 is implemented on the canonical baseline identified above. D2–D17 remain outside this document and retain their existing execution gates and evidence requirements.
