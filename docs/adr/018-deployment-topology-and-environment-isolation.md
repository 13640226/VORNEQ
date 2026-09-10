# ADR-018: Deployment Topology and Environment Isolation

**Status:** Proposed (frozen architecture; implementation deferred)  
**Version:** v2  
**Date:** 2026-09-10  
**Related ADRs:** ADR-014, ADR-016, ADR-017  
**Execution:** Not authorized by this ADR

## Context

VORNEQ برای چند تصمیم معماری مهم به topology واقعی deployment وابسته است. ADR-014 مسیر HTTPS API را برای transactional email تعریف می‌کند، ADR-016 migration/rollback را به recovery boundaries متصل می‌کند، و ADR-017 مقرر می‌کند `/metrics` در staging و production عمومی نباشد.

با این حال، topology واقعی provider باید پیش از implementation به‌صورت read-only بررسی شود. این ADR provider-specific configuration را حدس نمی‌زند؛ بلکه contract معماری environment isolation، ingress، database، storage، metrics و recovery را freeze می‌کند.

## Decision

### D1 — Canonical Environment Classification

متغیر canonical محیط:

```text
VORNEQ_ENV
```

است و MUST یکی از مقادیر زیر باشد:

```text
development
staging
production
```

در implementation آینده:

```text
unset/invalid VORNEQ_ENV
    → application MUST fail at startup
```

`DEBUG` MUST NOT به‌عنوان environment classifier استفاده شود.

همچنین:

```text
VORNEQ_ENV == "production"
AND
DEBUG == True
    → application MUST fail at startup
```

نحوه‌ی دقیق derivation یا precedence بین `DEBUG` و `VORNEQ_ENV` در Phase 1 implementation تعیین می‌شود.

این requirement در ADR freeze شده است، اما **در runtime فعلی هنوز پیاده‌سازی نشده**.

### D2 — Staging / Production State Isolation

Staging و production MUST state مستقل داشته باشند.

حداقل این resourceها نباید writable-shared باشند:

```text
primary database
application secrets
OAuth credentials
email-provider credentials
metrics/scraper credentials
backup targets
external cache/session state, when present
external object storage, when active
```

اصل frozen:

```text
Production state MUST NOT be writable by staging credentials.
```

استفاده از یک billing account، workspace یا vendor account مشترک به‌خودی‌خود ممنوع نیست، مشروط بر اینکه mutable application state و effective credentials ایزوله باشند.

### D3 — Secret Isolation

Staging و production باید credential sets جدا داشته باشند.

Production secret نباید به‌طور عادی در:

```text
source tree
.env.example
CI logs
staging configuration
development configuration
```

وجود داشته باشد.

Secret rotation باید environment-scoped باشد.

### D4 — Database Topology

Staging و production MUST databases مستقل داشته باشند.

ترتیب ترجیح اتصال:

```text
1. provider-private/internal DB path
2. restricted network endpoint
3. externally reachable TLS endpoint with strong controls
```

انتخاب دقیق provider/path تا live topology discovery deferred است.

Database URL باید runtime configuration باشد و public HTTP ingress نباید database proxy عمومی ایجاد کند.

Pooling، PgBouncer و provider pooler در این ADR freeze نمی‌شوند.

### D5 — Conditional Object Storage Isolation

اگر external object storage در یک environment فعال باشد، staging و production MUST namespaces و credentials مستقل داشته باشند.

Canonical activation flag فعلی:

```text
USE_OBJECT_STORAGE
```

است.

بنابراین:

```text
USE_OBJECT_STORAGE=True
    → storage isolation invariants apply
```

اگر storage در environment فعال نباشد، این invariantها برای آن environment قابل اعمال نیستند.

Development/test MAY از storage ephemeral یا shared non-production استفاده کنند.

اصل ثابت:

```text
Publicly readable object != publicly writable storage
```

Storage vendor، CDN و signed-URL mechanism deferred هستند.

### D6 — Explicit Public Ingress Boundary

ورودی عمومی باید از boundary شناخته‌شده عبور کند:

```text
Internet
   ↓
trusted platform edge / proxy
   ↓
VORNEQ application
```

Headerهایی مانند:

```text
X-Forwarded-For
X-Real-IP
Forwarded
```

نباید بدون trusted proxy contract معتبر تلقی شوند.

Client-IP derivation فقط با proxy chain و normalization policy اثبات‌شده قابل اعتماد است.

این تصمیم به AXES مرتبط است ولی هیچ AXES configuration را تغییر نمی‌دهد.

### D7 — ADR-017 Endpoint Classes Preserved

کلاس‌های ADR-017 حفظ می‌شوند:

```text
Public Health:
    /health/

Restricted Metrics:
    /metrics

Operator Diagnostics:
    debug/admin/operator troubleshooting endpoints
```

`/health/` MAY public باقی بماند، ولی MUST minimal باشد.

`/metrics` در staging و production MUST از anonymous Internet access محافظت شود.

Browser/session authentication، Django admin و AXES نباید primary machine-to-machine metrics boundary باشند.

**ADR-018 does not authorize ADR-017 Phase 2 implementation. It prepares the topology preconditions. Phase 2 remains gated on the read-only discovery checklist defined by this ADR.**

### D8 — Metrics Scraper Boundary

Scraper باید network identity یا machine identity قابل اعتماد داشته باشد.

ترتیب ترجیح:

```text
A. private/internal path
B. trusted edge/network allowlist
C. application-level machine credential
```

انتخاب نهایی A/B/C تا discovery واقعی deployment deferred است.

این موارد به‌تنهایی کنترل معتبر metrics نیستند:

```text
browser login
allauth session
Django admin auth
AXES
robots.txt
obscure/random URL
```

### D9 — Metrics Access Must Fail Closed

در staging و production:

```text
metrics access-control missing/misconfigured
    → deny access
```

نه:

```text
missing config
    → public /metrics
```

در مقابل، metrics subsystem failure MUST NOT application availability را از بین ببرد.

### D10 — Health Must Not Leak Topology

Public `/health/` فقط MAY bounded readiness/liveness state ارائه کند.

مثلاً:

```json
{"status": "ok"}
```

نباید شامل این موارد باشد:

```text
internal hostname
DB URL
database name
credentials
storage namespace
instance identifier
deployment inventory
exact row counts
metrics detail
raw exception text
```

### D11 — Deployment Target Isolation

Staging و production باید independently deployable باشند.

Deployment staging نباید production را implicit deploy کند و بالعکس.

Reviewed build/artifact MAY مشترک باشد، ولی:

```text
configuration
secrets
mutable state
deployment target
```

باید environment-specific باقی بمانند.

### D12 — Environment-Scoped Change Gates

الگوی طبیعی rollout:

```text
review
  ↓
staging deploy
  ↓
staging verification
  ↓
explicit production GO
  ↓
production deploy
```

موفقیت staging خودبه‌خود authorization production نیست.

### D13 — Backup Isolation

Backup باید environment-scoped باشد.

Production backup نباید توسط staging process overwrite یا lifecycle-manage شود.

Restore production data به staging یک workflow عادی محسوب نمی‌شود و در صورت نیاز باید تحت privacy/security review و sanitization policy قرار گیرد.

این ADR کپی production DB به staging را default workflow نمی‌داند.

### D14 — Recovery Target Must Be Explicit

قبل از restore باید حداقل این موارد مشخص باشند:

```text
backup source
target environment
target database/storage boundary
compatibility decision
```

Restore به environment اشتباه یک STOP condition است.

ADR-016 همچنان مالک migration rollback semantics است.

### D15 — Forward-Fix Remains Default

ADR-018 تصمیم ADR-016 را تغییر نمی‌دهد.

Forward-fix همچنان default operational preference است و topology rollback نباید به حذف کورکورانه state یا resource منجر شود.

### D16 — External SaaS Is Outside Trust Boundary

Email provider، OAuth provider، external storage و SaaSهای مشابه internal VORNEQ process محسوب نمی‌شوند.

ارتباط با آن‌ها باید از protocol امن و credential محدود استفاده کند.

برای email:

```text
VORNEQ
   ↓ HTTPS API
external transactional email provider
```

ADR-014 همچنان مالک vendor selection است.

### D17 — Production Must Not Depend on Staging

Production normal operation MUST NOT به availability یا mutable state محیط staging وابسته باشد.

نمونه‌های ممنوع:

```text
production app → staging DB
production app → staging storage
production app → staging proxy dependency
production service → credential served by staging app
```

## Frozen Security Invariants

```text
S1  VORNEQ_ENV is explicit and validated
S2  production + DEBUG=True is invalid
S3  staging DB != production DB
S4  staging credentials cannot mutate production state
S5  production secrets are environment-isolated
S6  active external storage is environment-isolated
S7  /metrics is not anonymously public in staging/production
S8  /health remains public-minimal
S9  proxy/IP trust requires explicit verified boundary
S10 machine endpoints do not depend on browser authentication
S11 production normal operation does not depend on staging
S12 restore target is explicitly environment-scoped
S13 provider-specific topology is verified, not assumed
```

## Required Read-Only Discovery Before Implementation

قبل از ADR-017 Phase 2 یا implementation ناشی از ADR-018 باید topology واقعی بررسی شود:

| Evidence | Requirement |
|---|---|
| staging service identity | Required |
| production service identity | Required |
| database attached to each | Required |
| internal/external database paths | Required |
| private/network connectivity | Required |
| ingress/proxy chain | Required |
| `/metrics` current reachability | Required |
| scraper location | Required |
| secret isolation evidence | Required |
| backup destination boundaries | Required |
| deployment targets/pipeline | Required |
| storage namespaces | Required when storage active |

Secret values نباید در این inventory ثبت شوند؛ فقط boundary و وجودشان.

## STOP Conditions

Rollout باید متوقف شود اگر:

```text
staging and production share writable DB
staging credential can mutate production
production DB target is ambiguous
restore target is ambiguous
IP-based control exists without trusted proxy evidence
/metrics protection trusts spoofable forwarded headers
provider feature is assumed but not verified
production rollout proceeds without required environment evidence
```

## Non-Goals

ADR-018 این موارد را تعیین نمی‌کند:

```text
Render plan upgrade
email vendor
storage vendor
Prometheus hosting vendor
metrics token format
CIDR allowlist
PgBouncer/pooler choice
OAuth providers
AXES reset/change
PR A/B/C implementation
multi-region architecture
HA strategy
RPO/RTO numeric targets
CI/CD vendor replacement
```

## Rollout Model

```text
Phase 0 — ADR only
Phase 1 — read-only topology discovery
Phase 2 — gap analysis
Phase 3 — minimal isolated implementation PRs
Phase 4 — recovery topology validation
Phase 5 — production verification
```

هیچ Phase بعدی صرفاً با merge این ADR مجاز نمی‌شود.

## Current Canonical Boundary

```text
ADR-018 documentation        FROZEN v2 / proposal
ADR-018 runtime              NOT IMPLEMENTED
ADR-017 Phase 2              NOT AUTHORIZED
/metrics restriction         NOT IMPLEMENTED
Auth baseline                FAIL
PR A implementation          SUSPENDED
PR B implementation          SUSPENDED
PR C implementation          SUSPENDED
PR #239                      UNTOUCHED
```

### Freeze statement

**ADR-018 v2 architecture is frozen at the documentation layer.**

این freeze فقط contract معماری را تثبیت می‌کند. به‌طور صریح:

```text
ADR-018 freeze/merge ≠ runtime implementation
ADR-018 freeze/merge ≠ ADR-017 Phase 2 authorization
ADR-018 freeze/merge ≠ Auth unblock
ADR-018 freeze/merge ≠ PR A/B/C authorization
```
