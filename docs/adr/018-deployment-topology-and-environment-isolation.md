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

## Amendment — A1 Partial Closure, Environment Definitions, and D3 Assessment (2026-09-11)

This amendment is append-only. It records session-governance decisions and read-only repository findings against baseline `main@30c1a6d04673668ef9deab6f8139f1e2143f4f90`. It does not change this ADR's `Proposed` status, does not authorize implementation or deployment, and does not convert any evidence-gated control into an implemented control. [session governance]

### A1 — Partial Closure Record

A1 is **partially closed** at the governance/assessment layer. [session governance]

For decisions D2–D17, the current classification is: [session governance]

- D12, D14, D16: **Decided — session governance**. [session governance]
- D7: **Policy-adopted**. [session governance]
- D10: **Policy-decided**. [session governance]
- D15: **Already-decided / inherited** from ADR-016. [ADR-018 existing] [session governance]
- D2, D3, D4, D5, D6, D8, D11, D13, D17: **Evidence-gated — open**. [open — evidence-gated]
- D9: **Runtime-deploy-gated — open**. [open — implementation]

This yields six resolved/inherited decisions and ten open decisions: nine evidence-gated and one runtime-deploy-gated. [session governance]

The current critical evidence path is D4/database association. The exact database attached to the observed application target remains unresolved, and the earlier B1 association assessment closed without resolving that mapping. [repo evidence] [open — evidence-gated]

### Environment Definitions — Two-Sided

For D3 and related environment-isolation reasoning, the following definitions are canonical for this governance record. [session governance]

**Staging configuration** means the set of configuration and credential references applied to or consumable by a deployment target explicitly classified as staging, independent of infrastructure-provider naming or grouping. [session governance]

**Production configuration** means the set of configuration and credential references applied to or consumable by a deployment target explicitly classified as production, independent of infrastructure-provider naming or grouping. [session governance]

The authoritative environment identity is the explicit approved application/deployment classification. Provider grouping is auxiliary evidence and MAY identify drift, but is not the classification authority. [session governance]

These definitions are static-by-default and are reviewable only through an explicit ADR amendment. They do not by themselves prove that any concrete provider resource belongs to either environment. [session governance] [open — evidence-gated]

The observed mismatch between `VORNEQ_ENV=staging` and the Render provider grouping labelled `Production` remains preserved as a drift signal. The definition does not erase the mismatch and does not assert which provider grouping is operationally correct. [session governance] [open — evidence-gated]

### D3 — Secret Isolation Assessment / Closure

Status: **Closed as Assessment / Unresolved as Control.** [session governance]

D3 remains evidence-gated in A1. The assessment is complete for the evidence gathered in the authorized scope, but compliance cannot be declared PASS or FAIL. [session governance] [open — evidence-gated]

The three D3 rules have the following final assessment state: [ADR-018 existing] [session governance]

- **R1 — Credential-set Separation:** Unresolved — evidence-gated; concrete service inventory is incomplete. [open — evidence-gated]
- **R2 — Production Secret Absence:** Partially proven. Three of five named surfaces are clean in the targeted read-only repository assessment: source tree, `.env.example`, and development configuration. Staging configuration and CI logs remain open. [repo evidence] [open — evidence-gated]
- **R3 — Environment-scoped Rotation:** Unresolved; rotation policy and provider evidence remain pending. [open — evidence-gated]

The D3 control is therefore **unresolved**, not passed and not failed. [session governance]

D3 is reopened for assessment if any of the following triggers occurs: [session governance]

1. **RT-1 — Provider membership evidence:** a concrete service/resource is explicitly bound to an environment classification. [open — evidence-gated]
2. **RT-2 — Credential-set evidence:** a staging target and a production target can be compared with sufficient boundary evidence. [open — evidence-gated]
3. **RT-3 — Rotation evidence:** policy or provider metadata establishes environment-scoped rotation. [open — evidence-gated]
4. **RT-4 — Remaining R2 evidence:** valid evidence becomes available for staging configuration or CI logs. [open — evidence-gated]
5. **RT-5 — Governance declaration:** the Change Approver explicitly classifies a concrete service/resource inventory. [session governance]
6. **RT-6 — ADR amendment:** ADR-018 is amended with an explicit concrete service inventory. [session governance]

Governance principle: **Governance is not a substitute for evidence about actual resource membership.** Boundary and policy may be decided through governance, but missing evidence about concrete resource membership MUST NOT be replaced by an unsupported assertion. [session governance]

### D3 Service-Inventory Finding

The read-only repository/ADR inventory completed with an **Incomplete** verdict under the locked explicit-declaration criterion. [repo evidence] [session governance]

- C1 — Explicitly staging-classified concrete services/resources: **0**. [repo evidence]
- C2 — Explicitly production-classified concrete services/resources: **0**. [repo evidence]
- C3 — Unclassified/ambiguous: multiple logical or intent-bearing targets exist, but concrete membership is not explicitly declared. [repo evidence]

`render.yaml` exists in the repository and is a Render Blueprint artifact. It does not provide a complete two-sided service inventory or an explicit environment-classification binding for the concrete targets required by this assessment. [repo evidence]

Accordingly, the corrected finding is not “no Blueprint evidence.” The correct finding is: **Blueprint evidence exists, but it does not provide a complete service inventory or classification binding.** [repo evidence]

Cross-artifact intent — including environment-bearing names, staging-oriented settings, workflow names, or logical secret roles — is not treated as an explicit concrete resource classification. [session governance]

### Provenance Discipline

Claims in this amendment use the following provenance labels: [session governance]

- `[ADR-018 existing]` — an existing ADR-018 policy or invariant used as source context.
- `[session governance]` — a decision or interpretation made in the governance session and recorded here without implying runtime implementation.
- `[repo evidence]` — a read-only repository finding; it establishes repository state only and does not prove provider/runtime state.
- `[open — evidence-gated]` — a control or conclusion that still requires evidence.
- `[open — implementation]` — a requirement whose implementation/runtime effectiveness remains open.

Nothing in this amendment authorizes provider mutation, database access, deployment, runtime verification, secret disclosure, or implementation work. [session governance]

## Amendment — D4 Database Topology Assessment / Closure (2026-09-11)

This amendment is append-only and records the authorized D4 repo-level deep check and the resulting governance closure against baseline `main@e2f9b9d0e2c03c48f529ddc14e0a259b4ada1bf2`. It does not change ADR-018 status, does not implement D4, and does not promote any evidence-gated control to PASS or FAIL. [session governance] [open — evidence-gated]

### D4 Deep Check Provenance

The D4 assessment has two independent provenance paths: (1) the earlier B1 read-only provider-UI inspection and (2) the authorized repo-level deep check. Both paths reached the same conclusion: the concrete database association remains unproven and provider-blocked. [session governance] [repo evidence] [open — evidence-gated]

| Output | Finding | Assessment |
|---|---|---|
| O1 — named DB resource in `render.yaml` | No named database resource mapping found | No declarative resource identity |
| O2 — `fromDatabase` / `connectionString` | Not present in the inspected Blueprint | No declarative DB binding |
| O3 — resource name in docs | No concrete named DB mapping found | Documentation intent only |
| O4 — resource in settings/config | `DATABASE_URL` abstraction only | No provider resource binding |
| O5 — CI resource binding | Environment-specific secret names exist, but no provider resource name | CI intent evidence only |
| O6 — usable repo mapping | No usable `DATABASE_URL` → concrete resource mapping found in targeted artifacts | D4 unresolved confirmed |

### D4 Verdict

Status: **Closed as Assessment / Unresolved as Control / Provider-blocked.** [session governance]

D4 remains evidence-gated. The authorized assessment is complete for the currently available evidence, but the control is neither passed nor failed. The absence of a proven binding MUST NOT be interpreted as proof that no binding exists. [session governance] [open — evidence-gated]

### Evidence Chain

The repository establishes the following staging path: [repo evidence]

```text
staging workflow / Render settings
  → DATABASE_URL abstraction
    → PostgreSQL
```

The repository establishes the following production-intent path: [repo evidence]

```text
production workflow
  → PRODUCTION_SOURCE_DATABASE_URL
    → DATABASE_URL abstraction
      → PostgreSQL
```

The key missing link is: [open — evidence-gated]

```text
DATABASE_URL
  → concrete provider PostgreSQL resource
```

That final mapping is not established by the repo-level evidence and was not resolved by the B1 provider-UI inspection. [session governance] [repo evidence] [open — evidence-gated]

### C3 / C4 State

- **C3 — DB mapping:** Unresolved — provider-blocked; the concrete resource behind the effective database URL is not proven. [open — evidence-gated]
- **C4 — Internal vs External:** Unresolved — repo-indeterminable; the repository does not establish whether the effective provider path is internal/private, restricted-network, or external TLS. [open — evidence-gated]

### Deep-Check Limitations

- GitHub Code Search returned `incomplete_results=true` for relevant searches. [repo evidence]
- A local clone fallback could not be completed because outbound DNS was unavailable in the execution runtime. [session execution evidence]
- Therefore, a null code-search result alone is **not** treated as proof of absence across the entire repository. [session governance]
- The directly inspected targeted artifacts in authorized scopes S1–S5 did not provide a named provider-resource binding. [repo evidence]

### D4 Reopening Triggers

D4 returns from Closed-as-Assessment to In-progress if any of the following becomes available: [session governance]

1. **RT-1 — Provider association metadata:** read-only provider UI evidence directly links the application/service to a concrete database resource.
2. **RT-2 — Declarative IaC binding:** a Render Blueprint or other approved IaC artifact introduces `fromDatabase`, `connectionString`, or an equivalent concrete resource binding.
3. **RT-3 — Provider support evidence:** a provider support response supplies verifiable resource-binding evidence.
4. **RT-4 — Read-only shell/hostname evidence:** a plan/tooling change permits a read-only inspection that reveals database hostname/resource identity without credential disclosure.
5. **RT-5 — Read-only resource identity path:** any approved read-only provider mechanism exposes the hostname/resource identity without secret values.
6. **RT-6 — GitHub secret metadata:** non-value metadata validly identifies the bound provider resource.
7. **RT-7 — Direct new evidence:** any new evidence directly binds `DATABASE_URL` to a concrete named provider resource.

After any reopening trigger, D4 must be reassessed before a PASS/FAIL or implementation claim is made. [session governance]

### Governance Principle

**Governance is not a substitute for evidence about actual resource membership.** The D4 closure records assessment completeness and the provider-blocked state; it does not manufacture a database identity, classify an unverified provider resource, or claim runtime implementation. [session governance] [open — evidence-gated]
