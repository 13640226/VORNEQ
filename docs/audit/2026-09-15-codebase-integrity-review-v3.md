# VORNEQ — Holistic Codebase Integrity Review (v3)

**Baseline:** `main@925db1c22a95055b6397ff6bf891b397f50f0905`  
**Frozen Date:** 2026-09-15  
**Method:** Read-only Static GitHub Review (7 phases)  
**Related (informational):** PR Triage Final Summary (separate artifact 
in this directory)

**ID Convention:** Canonical Finding IDs, severities, and counts are 
preserved from v2 and become immutable upon v3 freeze. Former IDs 
preserved as `Former:` for traceability.

**Cross-Reference Convention:**
- `Related (Remediation)` — direct resolution
- `Background/Context` — informational
- `Background/Prerequisite` — dependency for future work

---

## 0. Executive Summary

This audit reviewed the fixed baseline `main@925db1c` across seven 
independent phases. No local test execution was performed. All 
evidence is drawn from the repository, workflow runs, and CI artifacts 
actually fetched.

### Consolidated Counts

| Category | Count |
|---|---|
| Debt Findings | 30 |
| └─ High | 1 |
| └─ Medium | 20 |
| └─ Low | 9 |
| Positive Controls | 19 |
| Preservation Conclusions | 5 (informational, non-counted) |
| Open Decisions | 5 |
| Cross-Cutting Clusters | 6 |

### Audit Verdict

No Critical finding or demonstrated security vulnerability was 
identified within the evidence and scope of this static audit.

The baseline includes several substantive positive controls: Production
fail-closed, pip-audit as a required gate, Backup/Restore behavioral
gate, multi-Python CI, and behavior-rich tests already exist. The main 
debt is not in security or runtime, but in **configuration contract**, 
**documentation freshness**, **frontend token coverage**, and **CI 
gate completeness**.

---

## 1. Methodology and Guardrails

### Guardrails

- Verification ≠ Truth
- Search ≠ Verification
- Reputation is contextual
- No inferred verified identity from free text
- PostgreSQL first
- Backward compatibility
- Findings first, fixes second
- A static audit cannot claim local test execution
- Only report CI evidence actually fetched

### Refinement History

Several findings were refined by later phases. To preserve provenance, 
each final finding keeps a `Refinement History` section.

---

## 2. Consolidated Debt Findings (30)

### HIGH

#### F-H-01: `VORNEQ_ENV` Missing from `render.yaml`

- **Severity:** High
- **Source phases:** 1 (F2), 6 (F5)
- **Former IDs:** F-H-01
- **Domain:** Configuration / Deployment
- **Cluster:** Cluster 1

**Evidence:**
- `config.settings` raises `ImproperlyConfigured` without `VORNEQ_ENV`; 
  only `development|staging|production` accepted.
- `settings_render.py` imports `from .settings import *` and inherits 
  the prerequisite.
- `render.yaml` defines `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, 
  `DATABASE_URL`, and object storage variables for staging, but 
  **`VORNEQ_ENV` is absent from `envVars`.**
- `.env.example` explicitly documents `VORNEQ_ENV=development` as 
  required.

**Impact:** Deployment is not reproducible from version-controlled 
configuration alone. Import of settings — and consequently build, 
pre-deploy, and runtime — can fail-fast. This finding does **not** 
claim the current deployment is broken; it states that 
configuration-as-code is incomplete.

**Recommendation:** Align the `VORNEQ_ENV` contract across settings, 
the Render blueprint, and deployment workflows. **Verify the actual 
Render state before making changes.**

**Related (Remediation):** pending (Cluster 1 issue not yet created)
**Background/Context:** F-M-03, F-M-12, PC-01

---

### MEDIUM

#### F-M-01: Staging Can Run with `DEBUG=True`

- **Severity:** Medium
- **Source phase:** 3 (F2)
- **Domain:** Security / Configuration

**Evidence:** Production fails on `DEBUG=True`; staging only logs a 
warning. Security controls (SSL/HSTS/secure cookies) activate based on 
`if not DEBUG`. This finding **does not claim the current staging 
environment is configured this way.**

**Impact:** If staging is provisioned with `DEBUG=true`, this exposes 
debug information and disables `SECURE_SSL_REDIRECT`, HSTS, and 
secure-cookie flags.

**Recommendation:** For shared/internet-facing staging, make 
`DEBUG=false` a deployment invariant, preferably fail-fast or through 
deployment validation.

**Related (Remediation):** pending
**Background/Context:** F-L-09

---

#### F-M-02: Secret Inventory Incomplete

- **Severity:** Medium
- **Source phases:** 1 (F7), 3 (F7)
- **Domain:** Secrets / Operations / Docs

**Evidence:** `.env.example` documents only core Django variables and 
the optional metrics token. `settings.py` also consumes email, Redis, 
allauth proxy, logging, and account verification variables. 
`settings_render.py` configures object storage. Secret / non-secret 
classification for DB/Redis/SMTP is incomplete.

**Impact:** An operator cannot discover the full configuration surface 
from `.env.example` alone.

**Recommendation:** Produce a single documented inventory with columns 
for Required/Optional, Secret/Non-secret, environment applicability, 
default, and fail behavior. Secret values must not be committed.

**Related (Remediation):** pending
**Background/Context:** F-M-03, F-L-01

---

#### F-M-03: `setup.md` Not Aligned with Runtime Contract

- **Severity:** Medium
- **Source phase:** 6 (F5)
- **Domain:** Docs / Settings
- **Cluster:** Cluster 1

**Evidence:** `README.md` directs the user to `docs/setup.md`. The 
setup guide still references `13640226/saman-kherad.git` and 
`cd saman-kherad`, and mentions only four `DJANGO_*` variables. 
`VORNEQ_ENV` is not mentioned, while the current code treats it as 
mandatory.

**Impact:** Fresh setup following the canonical README can fail before 
startup.

**Recommendation:** Update setup documentation to align with the 
runtime contract regarding `VORNEQ_ENV` and the current repository 
identity.

**Related (Remediation):** pending (same Cluster 1 issue as F-H-01)
**Background/Context:** F-H-01, F-M-12

---

#### F-M-04: Entitlement Dual-Schema (Transitional Live State)

- **Severity:** Medium
- **Source phases:** 2 (F1), 6 (F1)
- **Domain:** Models / Backward compatibility
- **Cluster:** Cluster 3
- **Preservation:** see Section 3.2 P-01

**Evidence:** Entitlement retains both `user+product` (legacy) and 
`identity+artifact` (canonical). Migration 
`0007_entitlement_canonical_fields` is additive. **ADR-005 explicitly 
defines the migration as staged and reversible.**

**Refinement history:** Phase 2 F1 recorded it as dual-schema; Phase 6 
F1 refined "legacy" to "transitional live compatibility state".

**Impact:** Correctness depends on parity between legacy and canonical 
resolution. This is the same semantic risk as #82.

**Recommendation:** Do not remove legacy fields yet. Parity and 
backfill coverage must be proven before any cutover.

**Related (Remediation):** #82 (via F-M-07 — parity matrix)
**Background/Context:** ADR-005

---

#### F-M-05: ContextualReputation Staged Migration

- **Severity:** Medium
- **Source phases:** 2 (F2), 6 (F2)
- **Domain:** Models / Identity / Reputation
- **Cluster:** Cluster 3
- **Preservation:** see Section 3.2 P-02

**Evidence:** `ContextualReputation.user` remains required; `identity` 
is nullable. The docstring explicitly describes `user` as "required 
legacy subject during the staged migration". **ADR-009 defines a 
seven-phase migration.**

**Refinement history:** Phase 6 F2 refined it to a transitional live 
field.

**Impact:** A reputation projection may carry both legacy user and 
canonical identity semantics.

**Recommendation:** Keep the migration staged; measure parity and 
identity-binding completeness before removing the legacy subject.

**Related (Remediation):** pending
**Background/Context:** ADR-009

---

#### F-M-06: PostgreSQL Contract Gap — Not Enforced in Base and Not Required in CI

- **Severity:** Medium
- **Source phases:** 1 (F3), 2 (F6), 5 (F1)
- **Former IDs:** F-M-06 + F-M-13 (merged)
- **Domain:** Architecture / Database configuration / CI

**Evidence:**
- Base settings silently fall back to SQLite when `DATABASE_URL` is absent.
- `settings_render.py` is stricter (SSL, health checks, required URL).
- CI has two jobs: `test` (SQLite) and `test-postgres` (PostgreSQL 16).
- Ruleset `main-protection` requires only `test (3.11)`, `test (3.12)`, 
  `dependencies`, and `postgres-backup-restore`. **`test-postgres` is 
  not required.**

**Refinement history:**
- Phase 1 F3: "not enforced"
- Phase 2 F6: PostgreSQL is a real gate in CI
- Phase 5 F1: PostgreSQL matrix not required

**Impact:** A PR can pass required gates while the application test 
suite fails on PostgreSQL. For a project that relies on narrow-window 
CTEs and DB-specific behavior, this gap matters.

**Recommendation:** Keep SQLite as an explicit and limited dev 
convenience backend. Treat PostgreSQL as authoritative on CI and 
integration paths. Promote `test-postgres` to a required-status 
candidate after a stability and runtime review.

**Related (Remediation):** pending
**Background/Context:** PC-04, PC-05

---

#### F-M-07: #82 Parity Matrix Incomplete

- **Severity:** Medium
- **Source phases:** 4 (F9), 5 (F4)
- **Domain:** Tests / Authorization
- **Cluster:** Cluster 3

**Evidence:** PR #82 introduces a separate classifier 
`_authorization_allowed()`. Its equality test only compares the 
canonical resolved happy path. Legacy-only, partial, mismatch, 
unresolved, expired, and inactive states are not covered in the matrix. 
`has_valid_entitlement()` in current `main` is canonical-first and 
fail-closed.

**Impact:** A duplicated classifier can drift from the production 
source of truth on non-happy-path states.

**Recommendation:** Prefer a shared classifier. Otherwise, add a 
table-driven parity matrix over all authorization states.

**Related (Remediation):** #82 (must be corrected before merge)
**Background/Context:** F-M-04

---

#### F-M-08: Proxy/IP Trust Configuration Sensitive

- **Severity:** Medium
- **Source phase:** 3 (F4)
- **Domain:** Auth / Rate limiting / Deployment

**Evidence:** `ALLAUTH_TRUSTED_PROXY_COUNT` and 
`ALLAUTH_TRUSTED_CLIENT_IP_HEADER` are env-configurable; defaults are 
`0` and `None`. Correctness of rate limiting and abuse attribution 
behind a reverse proxy or CDN depends on this deployment contract.

**Impact:** A wrong value can make all users appear as one IP, or can 
trust an untrusted forwarded header.

**Recommendation:** Document the real Render/proxy topology and 
validate these two values against it. Do not trust arbitrary forwarded 
headers.

**Related (Remediation):** pending
**Background/Context:** PC-06

---

#### F-M-09: API Rate Limiting Gaps — Public Search and Media Embedding

- **Severity:** Medium
- **Source phase:** 4 (F1, F6)
- **Former IDs:** F-M-10 + F-M-11 (merged)
- **Domain:** API / Rate limiting

**Evidence:**
- `/api/search/` uses only `@require_GET`, with no throttle decorator 
  or middleware. Page size is capped at `MAX_PAGE_SIZE=50`.
- Media search (`@require_POST`) is CSRF-protected but not rate-limited. 
  In production `_service()` returns `None` with a 503 fail-closed 
  response.

**Impact:** A search request can fan out into multiple adapters and 
database queries. Current production media exposure is zero, but once 
a real provider is enabled, embedding endpoints will be computationally 
expensive.

**Recommendation:**
- Search: collect traffic/cost evidence before adding throttling.
- Media: do not merge a production-provider PR without an explicit 
  abuse / rate-limit policy.

**Related (Remediation):** pending

---

#### F-M-10: Search Retrieval Is Not FTS/Ranking-Based

- **Severity:** Medium
- **Source phase:** 4 (F2)
- **Domain:** Search / Performance

**Evidence:** Adapters mostly compose `__icontains` predicates. Final 
ranking is `(published_at, key)` descending. This finding does **not** 
prove current performance regression.

**Impact:** As the corpus grows, broad substring matching can become 
expensive and result order will not reflect relevance.

**Recommendation:** Introduce PostgreSQL FTS, trigram, or ranking only 
after query-plan and staging benchmarks. The existing semantics should 
be the compatibility baseline.

**Related (Remediation):** pending
**Background/Context:** #178 (Search Evolution Principles — provides 
the framework for this migration)

---

#### F-M-11: No Coverage Architecture (Invariant Registry)

- **Severity:** Medium
- **Source phases:** 5 (F2, F8), 6 (F10)
- **Domain:** Tests / Quality gates / Docs
- **Cluster:** Cluster 5

**Evidence:** CI runs `python manage.py test` directly; there is no 
coverage invocation or threshold. `coverage.py` / `pytest-cov` are not 
in the dependency list. Tests are behavior-oriented. There is **no 
mapping from critical invariant → owning test → CI gate.**

**Refinement history:** Phase 5 F2 (no measurement) → Phase 5 F8 (no 
map) → Phase 6 F10 (invariant registry).

**Impact:** Coverage percentage cannot be reported, and CI cannot 
detect coverage regression. **This does not mean coverage is low; it 
means there is no measurement contract.**

**Recommendation:** Define a lightweight invariant matrix instead of a 
line-coverage-first approach.

**Related (Remediation):** pending
**Background/Context:** D-03

---

#### F-M-12: No `VORNEQ_ENV` Contract Test

- **Severity:** Medium
- **Source phase:** 5 (F9)
- **Domain:** Tests / Configuration
- **Cluster:** Cluster 1

**Evidence:** CI and GQV both set `VORNEQ_ENV: development` explicitly. 
A code search limited to `tests/` and `apps/` found no dedicated test. 
This is recorded as **"no proof of a dedicated test"**, not as proof 
of absence.

**Impact:** The fail-closed production contract may be protected 
primarily by runtime behavior rather than a regression test.

**Recommendation:** Add a small matrix for valid/invalid environment 
names and production-required settings.

**Related (Remediation):** pending (same Cluster 1 issue as F-H-01)
**Background/Context:** F-H-01, F-M-03

---

#### F-M-13: DF-1 — DR Documentation Inconsistent with Repo Config

- **Severity:** Medium
- **Source phase:** 6 (F4)
- **Domain:** Docs / Operations

**Evidence:** The repository's own registry already records **DF-1**: 
the DR document states that migrations run in Render 
`preDeployCommand`, but `render.yaml` explicitly keeps deploy 
schema-read-only, with `preDeployCommand` running only 
`migration_preflight`. `docs/disaster-recovery.md` still says twice 
that migrations run in Render preDeploy.

**Impact:** An operator may misunderstand where schema mutation 
actually occurs. This is not merely cosmetic staleness for recovery / 
deployment documentation.

**Recommendation:** Give DF-1 remediation priority. **Guardrail: 
provider evidence or historical confirmation.**

**Related (Remediation):** pending

---

#### F-M-14: ADR Statuses Out of Sync with Implementation

- **Severity:** Medium
- **Source phase:** 6 (F6)
- **Domain:** Docs / Architecture

**Evidence:** ADR-005 remains `Proposed` while the current model 
contains canonical fields. ADR-009 is also `Proposed` while 
`ContextualReputation.identity` exists in the current model.

**Impact:** "Proposed" no longer communicates whether a decision was 
accepted, is partially implemented, or is still in rollout. The 
ambiguity is risky for retirement decisions.

**Recommendation:** Define an ADR lifecycle vocabulary 
(`Accepted / Partially Implemented / Superseded`) and separate 
implementation status from decision status.

**Related (Remediation):** pending
**Background/Context:** D-04, F-M-04, F-M-05

---

#### F-M-15: PATH A/B Dual Token/Theme Contract

- **Severity:** Medium
- **Source phases:** 1 (F1), 7 (F1), 7 (F7)
- **Domain:** Frontend / CSS / Architecture
- **Cluster:** Cluster 2, Cluster 6

**Evidence:**
- PATH B (Django runtime) loads `tokens.css`, theme palettes, and 
  base/global/nav/layout CSS. The token layer defines color, typography, 
  spacing, radius, motion, z-index, and dark-theme semantics.
- PATH A (static) is a standalone document with its own stylesheet 
  `vorneq-home.css` and its own token namespace: `--ink`, `--paper`, 
  `--line`, `--focus`.
- PATH A keeps all copy as hard-coded English (`lang="en" dir="ltr"`).

**Refinement history:** Phase 1 F1 (surface) → Phase 7 F1 (token 
contract) → Phase 7 F7 (i18n dimension).

**Impact:** The dual homepage is not only duplicated content but two 
independent token/theme/accessibility evolution paths.

**Recommendation:** Preserve PATH A. Define its contract explicitly as 
either an independent static canonical surface or a consumer of shared 
design tokens.

**Related (Remediation):** pending
**Background/Context:** #303, D-02

---

#### F-M-16: PATH B Homepage — Token Coverage Gap

- **Severity:** Medium
- **Source phases:** 7 (F2), 7 (F3)
- **Domain:** CSS / Design system / Theme
- **Cluster:** Cluster 6

**Evidence:** `tokens.css` defines semantic tokens, but 
`homepage.css` uses extensive literals: `#fafafa`, `#0a0a0b`, 
`#5d5d65`, `#e2e2e6`, `#4a4a8c`, and literal spacing / type values. 
Focus states in the same file use color literals.

**Impact:** Theme selection cannot reliably govern the entire homepage. 
**This finding does not claim WCAG failure; it claims theme contract 
inconsistency.**

**Recommendation:** After #304 stabilizes, perform semantic mapping. 
**Do not mix token migration with hero consolidation.** Add a contrast 
matrix for text/CTA/focus.

**Related (Remediation):** pending (Token coverage issue not yet 
created)
**Background/Prerequisite:** #304 (Hero CSS consolidation must 
stabilize first)
**Background/Context:** F-M-15

---

#### F-M-17: RTL/LTR Foundation Present but Correctness Unproven

- **Severity:** Medium
- **Source phase:** 7 (F8)
- **Domain:** i18n / RTL

**Evidence:** Root HTML direction is `fa` → RTL, otherwise LTR. Base 
CSS uses logical properties (`padding-inline`, `margin-inline`, 
`inset-inline-start`). Standalone navigation is mostly direction-safe. 
**However**, static evidence is insufficient to prove geometry 
correctness for all `world-*` surfaces in Persian across breakpoints.

**Impact:** The historical #229 concern cannot be considered resolved 
simply because logical properties exist.

**Recommendation:** Perform real RTL/LTR verification across 
`fa/en/de` and the target breakpoints.

**Related (Remediation):** #305 (RTL/LTR audit — this issue is the 
audit)
**Background/Context:** #229 (historical, closed)

---

#### F-M-18: Login Language Selector Not Aligned with Supported Languages

- **Severity:** Medium
- **Source phase:** 7 (F9)
- **Domain:** i18n / Frontend

**Evidence:** The application contract supports `fa`, `en`, `de`. The 
login selector offers only Persian and English. The German catalog 
exists in the repository.

**Impact:** The authentication entry surface is not aligned with the 
global language contract. **Overlaps with in-flight language-picker 
work.**

**Recommendation:** During the language-selector reconciliation, place 
login in the `fa/en/de` matrix. **Before any change, re-check the 
current state of related PRs.**

**Related (Remediation):** #239
**Background/Context:** D-05

---

#### F-M-19: CSP `unsafe-inline` — Open Hardening Contract

- **Severity:** Medium
- **Source phases:** 3 (F5), 7 (F11)
- **Domain:** Frontend / Security
- **Cluster:** Cluster 6

**Evidence:** CSP has `script-src` limited to `SELF`. `style-src` 
includes `UNSAFE_INLINE`. **This finding does not claim an XSS 
vulnerability.** **Search ≠ Verification** — a zero-hit search cannot 
conclude that the entire repository has no inline styles.

**Impact:** Part of the CSP hardening envelope is reduced.

**Recommendation:** Before tightening CSP, produce a definitive 
inventory of inline styles across all template, render, and vendor 
surfaces. Tighten only if no real dependency remains.

**Related (Remediation):** pending
**Background/Context:** Phase 3 F5

---

#### F-M-20: Application-vs-Database Integrity Invariants — Coverage Unproven

- **Severity:** Medium
- **Source phases:** 2 (F3, F4, F5), 3 (F8), 4 (F7), 5 (F3)
- **Former IDs:** F-M-23 + F-M-24 (merged)
- **Domain:** Models / Data integrity / Audit
- **Cluster:** Cluster 4

**Evidence:**
- `ReputationHistory`, `QualitySignal`, `ScoringPolicy`, and 
  `ContextualReputationEvent` reject instance update/delete by 
  overriding `save()` / `delete()`.
- **`AuditEvent`** additionally rejects bulk `QuerySet.update()` and 
  `delete()`.
- **However**, no database-level immutability constraint or trigger was 
  observed.
- `VerificationRequest` uses `GenericForeignKey`; target existence and 
  allowed artifact types are enforced only in `clean()`.
- `clean()` is **not** invoked automatically on every `save()`.
- On the verification canonical path, `_require_permission()` + 
  transaction + `select_for_update()` + `full_clean()` are applied.

**Refinement history:**
- Phase 2 F3/F4/F5: general write-path concern
- Phase 3 F8: `AuditEvent` is stronger than the others
- Phase 4 F7: verification canonical path confirmed
- Phase 5 F3: best-effort-after-commit is **tested** (moved to D-01)

**Impact:** Enforcement is largely application-layer. **This does not 
prove a mutation vulnerability** — it only shows that DB invariants 
are not proven. Repository-wide write-path coverage is not 
demonstrated.

**Recommendation:** Define the threat / operational model first. 
Produce a dedicated inventory of non-canonical / direct write paths 
during remediation.

**Related (Remediation):** pending
**Background/Context:** D-01

---

### LOW

#### F-L-01: Split Environment Configuration

- **Source phase:** 1 (F4)
- **Domain:** Architecture / Configuration

**Evidence:** `base.py/dev.py/prod.py` is not used. `manage.py` uses 
`config.settings`; Render uses `config.settings_render` with a 
wildcard import plus overrides.

**Impact:** Two axes of environment selection. Inconsistency can 
produce an invalid configuration state.

**Recommendation:** Document a single contract for environment 
classification. Refactor only if real complexity increases.

**Related (Remediation):** pending
**Background/Context:** F-H-01

---

#### F-L-02: URL Configuration Mixes Composition with Application Routing

- **Source phase:** 1 (F5)
- **Domain:** Architecture / URL routing

**Evidence:** `config.urls` directly wires `home`, `discover`, 
`search_page`, `profile`, `inspect`, `health`, and `metrics`, in 
addition to app-level `include()` calls.

**Impact:** The URL root is both a composition root and part of 
product routing.

**Recommendation:** Keep product routes in app URLConfs where possible.

**Related (Remediation):** pending

---

#### F-L-03: Dependency Management Reproducible but Flat

- **Source phase:** 1 (F6)
- **Domain:** Configuration / Dependencies

**Evidence:** `requirements.txt` uses exact version pins. No 
`pyproject.toml` observed.

**Impact:** Runtime / dev / test / tooling separation is not 
explicit. **Not treated as a defect.**

**Recommendation:** Do not perform purely cosmetic packaging 
migration.

**Related (Remediation):** — (preservation-oriented; see Section 3.2 
P-05)

---

#### F-L-04: JSONField Without GIN Index

- **Source phase:** 2 (F8)
- **Domain:** Models / Performance

**Evidence:** Multiple `JSONField` columns for metadata/context/policy. 
No GIN / ArrayField / SearchVectorField observed.

**Impact:** If production queries target inner JSON keys, current 
B-tree indexes do not help.

**Recommendation:** Add GIN indexes only when driven by evidence, not 
just because a `JSONField` exists.

**Related (Remediation):** pending

---

#### F-L-05: API Error Schema Inconsistent

- **Source phase:** 4 (F5)
- **Domain:** API / Error handling

**Evidence:** Verification API uses `{"error": ..., "message": ...}`. 
Media API mixes `{"error": ...}` and `{"error": ..., "detail": ...}`. 
Core uses `{"detail": ...}`.

**Impact:** Client contract and telemetry parsing become more complex. 
No concrete security leak was demonstrated.

**Recommendation:** Define a standard envelope in a separate 
API-contract remediation; preserve backward compatibility.

**Related (Remediation):** pending

---

#### F-L-06: GQV Wide but Not Required

- **Source phase:** 5 (F5)
- **Domain:** CI / Quality gates

**Evidence:** Global Quality Verification runs on PRs but is not 
listed among required status checks.

**Impact:** Confirms the PR triage conclusion for #300.

**Recommendation:** Keep GQV as an evidence / reporting gate until 
infrastructure reliability (especially Lighthouse) is stable.

**Related (Remediation):** pending
**Background/Context:** #300

---

#### F-L-07: Lint/Format Merge Gate Not Proven

- **Source phase:** 5 (F10)
- **Domain:** CI / Quality gates

**Evidence:** Ruff / Black / isort are not visible in the main 
workflow.

**Impact:** Style and static-quality consistency are not enforced at 
merge time. Not a correctness defect.

**Recommendation:** Add a fast check only if the repository has a 
formal policy.

**Related (Remediation):** pending

---

#### F-L-08: Docs/ADR Governance Scattered

- **Source phase:** 6 (F7)
- **Domain:** Docs / Architecture

**Evidence:** `adr-018-evidence-closures.md` lives outside 
`docs/adr/`, in the root docs directory.

**Impact:** Discoverability is harder.

**Recommendation:** Establish a canonical ADR index and status 
registry. **Do not move files within this audit.**

**Related (Remediation):** pending

---

#### F-L-09: Email Verification Coupled to `DEBUG`

- **Source phase:** 3 (F10)
- **Domain:** Authentication
- **Former IDs:** F-M-09 (demoted)

**Evidence:** Default `ACCOUNT_EMAIL_VERIFICATION` is `none` when 
`DEBUG=true` and `mandatory` when `DEBUG=false`. Environment can 
override.

**Classification rationale:** Phase 3 accepted it as Low. Production 
already defaults to mandatory verification under `DEBUG=False`. 
Elevation to Medium would require new evidence (direct security 
reliance on verified email, or a real weak staging config), which was 
not demonstrated.

**Impact:** Staging/debug or an explicit override can weaken 
verification.

**Recommendation:** If verified email is part of the trust model, 
express the policy through environment/role rather than `DEBUG`.

**Related (Remediation):** pending
**Background/Context:** F-M-01

---

## 3. Controls and Preservation

### 3.1 Positive Controls (19)

#### Group 1 — Deployment resilience

| ID | Control | Source |
|---|---|---|
| PC-01 | Production fail-closed (secret + DEBUG constraints) | Phase 3 F1 |
| PC-02 | `pip-audit` required gate (`dependencies`) | Phase 5 F6 |
| PC-03 | Backup/Restore behavioral gate (real restore + payload assert) | Phase 5 F7 |
| PC-04 | Multi-Python CI (3.11 + 3.12) | Phase 5 F1 |
| PC-05 | Migration drift gate (`makemigrations --check`) | Phase 2 F7 |

#### Group 2 — Auth and security

| ID | Control | Source |
|---|---|---|
| PC-06 | Auth defense-in-depth (Axes + allauth + rate limits + no GET logout) | Phase 3 F3 |
| PC-07 | Metrics fail-closed + bearer + `compare_digest` | Phase 3 F6 |
| PC-08 | Audit write service schema allowlist + full_clean | Phase 3 F9 |

#### Group 3 — Search / API / Data

| ID | Control | Source |
|---|---|---|
| PC-09 | Narrow-window capability-gated (fallback + fault visibility) | Phase 4 F3 |
| PC-10 | Public search public-state-only (draft/pending never exposed) | Phase 4 F4 |
| PC-11 | Verification permission-bound (`_require_permission` + full_clean) | Phase 4 F7 |
| PC-12 | API surface small and explicit (no framework magic) | Phase 4 F10 |
| PC-13 | Explicit constraints/indexes in sensitive domains | Phase 2 F9 |

#### Group 4 — Accessibility and frontend

| ID | Control | Source |
|---|---|---|
| PC-14 | Reduced-motion global + component-specific | Phase 7 F5 |
| PC-15 | Core shell a11y primitives (skip-link, `:focus-visible`, 44px) | Phase 7 F6 |
| PC-16 | Account UI token adoption (design-system reference pattern) | Phase 7 F10 |

#### Group 5 — Code and data hygiene

| ID | Control | Source |
|---|---|---|
| PC-17 | Behavior-oriented tests (no meaningless-assertion anti-pattern) | Phase 5 F8 |
| PC-18 | Legacy library route intentional (purchased/historical links) | Phase 6 F8 |
| PC-19 | Inspect routes traceable (explicit URL + template inventory) | Phase 6 F9 |

### 3.2 Preservation / Non-Removal Conclusions (Informational)

This subsection is an informational classification. These items are 
not debt and are **not counted** in the finding total. They 
cross-reference findings in Section 2 whose recommendation is 
preservation rather than removal.

| ID | Item | Finding Ref | Rationale |
|---|---|---|---|
| P-01 | Legacy entitlement fields | F-M-04 | ADR-005 staged + reversible; removal would break the compatibility contract |
| P-02 | `ContextualReputation.user` | F-M-05 | ADR-009 seven-phase migration |
| P-03 | Migration/backfill commands | (not a finding — operator-invoked) | Management commands are inherently operator-invoked; zero reference count ≠ dead |
| P-04 | Legacy library route | PC-18 | Backward compatibility for purchased content and historical links |
| P-05 | Flat dependency structure | F-L-03 | Cosmetic migration not recommended |

---

## 4. Open Architecture / Product Decisions (5)

### Architecture Decisions

#### D-01: Audit Delivery Semantics — Best-Effort vs Mandatory Ledger

**Context:** `_emit_audit_event()` runs via `transaction.on_commit()` 
and only logs exceptions. The behavior is **explicitly tested** — 
`test_audit_failure_after_commit_does_not_rollback_business_transition`.

**Question:** Is the audit an operational observability layer or a 
security-grade mandatory ledger?

**Implication:**
- If the former, the current design is defensible.
- If the latter, a delivery guarantee (outbox / reconciliation) is 
  required.

**Note:** This is **not a bug**. Phase 5 established that the behavior 
is tested.

**Owner:** Architecture + Security

---

#### D-02: PATH A Long-Term Role

**Context:** PATH A (static) and PATH B (Django runtime) both render a 
homepage.

**Question:** Does PATH A remain a canonical reference surface, or is 
it intended to eventually replace / converge with PATH B?

**Owner:** Architecture + Frontend
**Background/Context:** #303, F-M-15

---

#### D-03: Coverage Architecture — Line % vs Invariant Registry

**Context:** No coverage measurement or gate. ADRs define explicit 
invariants.

**Question:** Is the coverage contract line-percentage-based or a 
critical-invariant registry?

**Owner:** QA + Architecture
**Background/Context:** F-M-11

---

#### D-04: ADR Lifecycle Vocabulary

**Context:** ADR-005 and ADR-009 remain `Proposed` while partially 
implemented.

**Question:** Adopt `Proposed / Accepted / Partially Implemented / 
Superseded`?

**Owner:** Architecture
**Background/Context:** F-M-14

---

### Product Decision

#### D-05: Login Language Selector Reconciliation

**Context:** Login offers `fa/en`; contract is `fa/en/de`.

**Question:** During #239's reconciliation, should login add `de`, or 
is a German auth surface deliberate?

**Owner:** Product + Frontend
**Related (Remediation):** #239
**Background/Context:** F-M-18

---

## 5. Cross-Cutting Clusters (6)

### Cluster 1: VORNEQ_ENV Contract
Findings: F-H-01, F-M-03, F-M-12  
Supporting positive: PC-01  
Type: config-code + docs + test gap  
P0 remediation unit.

### Cluster 2: Dual Homepage Architecture
Findings: F-M-15  
Background/Context: #303, D-02

### Cluster 3: Staged Migration and Authorization Parity
Findings: F-M-04, F-M-05, F-M-07  
Related (Remediation): #82  
Background/Context: ADR-005, ADR-009  
Type: transitional fields (preservation) + classifier parity (debt).

### Cluster 4: Application-vs-Database Integrity Invariants
Findings: F-M-20  
Background/Context: D-01  
Type: open architectural decision.

### Cluster 5: Coverage Architecture
Findings: F-M-11  
Background/Context: D-03  
Type: definition gap, not coverage gap.

### Cluster 6: Frontend Contract Fragmentation
Findings: F-M-15 (cross-cluster from Cluster 2), F-M-16, F-M-19  
Background/Prerequisite: #304 (for F-M-16)  
Background/Context: #303, D-02  
Type: dual token contract → token coverage → CSP hardening.

---

## 6. Priority Matrix

| Priority | Finding / Cluster | Type | Group |
|---|---|---|---|
| P0 | Cluster 1: VORNEQ_ENV Contract (F-H-01, F-M-03, F-M-12) | Cross-cutting | Remediation unit |
| P1 | F-M-13 (DF-1) | Operational docs | — |
| P1 | F-M-07 (#82 parity) | Pre-merge gate | Cluster 3 |
| P1 | F-M-14 (ADR status) | Governance | — |
| P2 | F-M-01, F-M-02, F-M-08 | Config/Auth | — |
| P2 | F-M-15, F-M-16, F-M-17, F-M-18 | Frontend | Cluster 2, 6 |
| P2 | F-M-11 (coverage) | Tests/CI | Cluster 5 |
| P2 | F-M-20 (app-vs-DB invariants) | Data integrity | Cluster 4 |
| P3 | F-M-06, F-M-09, F-M-10, F-M-19 | API/Search/Security | — |
| P3 | F-L-01 … F-L-09 | Low | — |

---

## 7. Recommended Next Steps

These are suggestions, not authorizations.

### Phase A — Proposed Remediation Actions (Unapproved)
- Convert **Cluster 1** into a single issue (F-H-01 + F-M-03 + F-M-12).
- Convert **F-M-13 (DF-1)** into a standalone issue.
- Add a **blocking note on #82** (F-M-07).
- Create a standalone **Token Coverage** issue (F-M-16).
- Create a standalone **CSP Tightening** issue (F-M-19).

### Phase B — Open decisions resolution
- Hold discussions for D-01 … D-05.

### Phase C — Frontend consolidation
- First: #304 (hero CSS debt).
- Next: token coverage migration (F-M-16) in a standalone issue.
- Next: RTL/LTR audit → #305.
- Next: language selector reconciliation → #239.

### Phase D — Long-term hygiene
- Coverage invariant registry (F-M-11).
- ADR status refresh (F-M-14).
- API error schema (F-L-05).
- Lint/format gate (F-L-07, only if a formal policy exists).

---

## 8. Appendix — Baseline and Limitations

### Baseline
- Commit: `main@925db1c22a95055b6397ff6bf891b397f50f0905`
- Audit date: 2026-09-15
- Phases: 7

### Limitations
- Static GitHub review only.
- No local test execution.
- CI evidence limited to runs actually fetched.
- Claims limited to explicit evidence; no inference from free text.

---

## 9. Appendix — Frozen PR Triage Context (Informational)

**Status:** Informational. **Not counted** in findings, positive 
controls, preservation conclusions, or open decisions. The source of 
truth for PR verdicts is the **PR Triage Final Summary** artifact 
(dated 2026-09-15) in this directory.

### 9.1 Frozen PR verdicts

| PR | Verdict | Cross-reference to this audit |
|---|---|---|
| #111 | Closed (Close-Candidate) | — |
| #229 | Closed (Close-Candidate) | Related to F-M-17 (RTL/LTR concern preserved) |
| #270 | Closed (Close-Candidate) | — |
| #300 | Active / Re-run-Recommended | — |
| #239 | Active / Needs-Rebase + Review | Related to F-M-18 and D-05 |
| #178 | Active / Review + Docs-Refresh | Background/Context for F-M-10 |
| #110 | Active / Fix-required + Review | — |
| #138 | Active / Review + Staging-Validation | Evidence-enabling context for F-M-10 |
| #82 | Active / Semantic-Refresh + Review | Related to F-M-04 and F-M-07 |

### 9.2 Follow-up issues created during triage

| Issue | Source PR | Related to this audit |
|---|---|---|
| #303 | Root hygiene (playground + atlas archive) | Background/Context for F-M-15 |
| #304 | Hero CSS debt consolidation | Background/Prerequisite for F-M-16 |
| #305 | RTL/LTR audit | Related to F-M-17 |
| #306 | Notes vs Discover decision | Not cross-referenced to any finding (product decision only) |

**Note on #306:** captures a product decision preserved from #270. It 
is **not** linked to D-05 (login language selector) — the two are 
unrelated product decisions.

### 9.3 Merge operations referenced

- **#301** — merge commit `5be8e9215f695676ed5127dc3623f16a06ecaba9`.
- **#302** — merge commit `925db1c22a95055b6397ff6bf891b397f50f0905` 
  (the baseline).

**Lineage note (record only):** PR #302 merge metadata indicates a 
second parent `80e4a9b`, while the intended amended head was `eea376d`. 
Recorded for audit transparency; does not affect the current baseline 
analysis.

### 9.4 Preservation notes

- Issue **#161** was closed as completed bookkeeping on 2026-09-15. 
  Not counted as a finding.
