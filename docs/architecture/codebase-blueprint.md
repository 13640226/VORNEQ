# VORNEQ Codebase Blueprint

Status: Canonical engineering reference for current architecture and explicitly marked future directions.

## 1. Snapshot metadata

- Repository: `13640226/VORNEQ`
- Baseline branch: `main`
- Baseline commit: `ea883c6fc9a29e7f8efdcbbf1c55f3dc5119651a` (PR #133)
- Last updated: 2026-09-07
- Scope: architecture documentation only; no runtime, schema, migration, API, or product-behavior changes.

This document distinguishes **Current**, **Implemented / Opt-in**, **Partially Implemented**, and **Target / Proposed** states. Future-looking items must not be read as production capabilities.

## 2. Current architecture

### 2.1 Project shape

The repository currently uses a mixed layout: several domain apps live under `apps/`, while `library` and `marketplace` remain top-level Django apps for backward compatibility.

```text
VORNEQ/
├── apps/
│   ├── core/
│   ├── evidence/
│   ├── graph/
│   ├── verification/
│   ├── profiles/
│   ├── content/
│   ├── media/
│   └── search/
├── library/
├── marketplace/
├── config/
├── templates/
├── assets/
├── docs/
├── .github/workflows/
├── render.yaml
├── requirements.txt
└── manage.py
```

`INSTALLED_APPS` currently includes Django core apps plus `allauth`, `axes`, `csp`, `django_prometheus`, `library`, `marketplace`, `apps.evidence`, `apps.graph`, `apps.core`, `apps.verification`, `apps.profiles`, `apps.content`, and `apps.media`. `apps.search` is routed and used but is not required to be listed as an installed app in the current configuration.

### 2.2 Trust-domain model

The current core is a staged trust-infrastructure architecture rather than a single monolithic trust score.

Key concepts include:

- `Artifact` and `ArtifactBinding` for canonical trust-layer representation of domain objects.
- `Identity` and `UserIdentity` for explicit identity binding; free-text names are not inferred into canonical identities.
- `ArtifactIdentityRole` for role-scoped relationships such as author, seller, creator, owner, and related roles.
- `Entitlement` for staged legacy (`user + product`) and canonical (`identity + artifact`) access relationships.
- Evidence/claim/provenance models in `apps.evidence`.
- Verification methods, requests, results, and evidence relationships in `apps.verification`.
- Contextual reputation projections, quality signals, scoring policies, and append-only reputation events in `apps.core`.

Legacy aggregate reputation data still exists for compatibility, but architectural decisions must not interpret a global aggregate as universal truth or as an authoritative cross-context trust score.

### 2.3 Search contract

`apps/search/services.py` provides retrieval-only unified search across Article, Product, LibraryItem, MediaAsset, and AudioItem.

Production behavior:

- Default page size: 12; maximum page size: 50.
- Exact historical global ordering: `(published_at, key)` descending.
- Search result keys use stable type prefixes such as `article:{pk}`, `product:{pk}`, `library:{pk}`, `media:{pk}`, and `audio:{pk}`.
- Per-adapter ordering can use timestamp plus text-cast primary key because the type prefix is constant inside one adapter; cross-adapter ties are resolved by the complete key in Python.
- Positive pages use `COUNT(*) OVER()` window-count pagination when the database supports window functions.
- Non-positive/invalid pages and unsupported backends use the bounded compatibility fallback.
- Search is retrieval only and must not be interpreted as Verification.

### 2.4 Search performance status after PR #133

The staging feasibility benchmark for PR #133 completed successfully with empty query, page 1, page size 12, `repeat=100`, total results 2200.

| Scenario | DB queries | wall p50 | wall p95 | wall p99 | SQL p50 | SQL p95 | SQL p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline production shape | 5 | 324.86 ms | 356.31 ms | 581.16 ms | 315.50 ms | 347.85 ms | 571.19 ms |
| Narrow + enrichment | 9 | 573.39 ms | 613.71 ms | 718.12 ms | 560.00 ms | 601.00 ms | 705.54 ms |
| Narrow CTE | 5 | 321.48 ms | 329.13 ms | 390.99 ms | 313.00 ms | 320.35 ms | 383.15 ms |

Interpretation:

- Narrow + enrichment is not a viable production direction for the current staging topology because added round trips erase the benefit of the narrow projection.
- Narrow CTE is the strongest measured candidate: it preserves five queries and materially improves tail latency versus the baseline in this run, especially p95/p99.
- PR #133 is a feasibility study only. Production `UnifiedSearch.search()` remains unchanged. Any rollout of Narrow CTE requires a separate production PR and regression/benchmark gate.
- The benchmark does not justify pg_trgm, caching, Elasticsearch, or pgvector for empty-query latency.

### 2.5 URL and compatibility architecture

Operational/API endpoints are non-localized; product/UI routes use `i18n_patterns`.

Important routes include:

```text
/health/              health check
/metrics               Prometheus routes via django-prometheus include
/i18n/                 language switch
/api/                  core API
/api/verification/     verification API
/api/media/            media API
/api/search/           unified search API
/{lang}/               home
/{lang}/profile/       profile
/{lang}/accounts/      allauth
/{lang}/library/       legacy index redirect to Marketplace
/{lang}/library/...    legacy detail/reader routes retained
/{lang}/marketplace/   Marketplace discovery hub
/{lang}/graph/         graph routes
```

The legacy Library index redirects to Marketplace, while legacy Library detail/reader routes are intentionally preserved until explicit equivalents exist.

### 2.6 Security and observability

Current settings include:

- django-axes brute-force protection.
- django-csp CSP middleware and policy.
- WhiteNoise static-file serving.
- Prometheus before/after middleware and metrics endpoint.
- Structured logging and request observability middleware.
- Secure production cookie/HSTS/SSL settings when `DEBUG` is false.
- allauth rate limits and anti-enumeration settings.

### 2.7 Deployment

Render deployment currently defines:

- dependency installation, message compilation, and collectstatic during build;
- `migration_preflight` followed by `migrate --noinput` in `preDeployCommand`;
- Gunicorn startup;
- `/health/` health check;
- environment-driven database and security settings.

This provides deployment safety primitives but is **not by itself a formal guarantee of zero-downtime deployment**.

Object-storage environment variables already exist behind `USE_OBJECT_STORAGE`; this capability is best described as **Implemented / Opt-in**, not mandatory infrastructure.

### 2.8 CI, staging operations, and recovery

Current workflow files:

```text
.github/workflows/backup-restore.yml
.github/workflows/benchmark-staging.yml
.github/workflows/ci.yml
.github/workflows/migrate-staging.yml
.github/workflows/profile-narrow-window-poc.yml
.github/workflows/profile-search-phases-staging.yml
.github/workflows/profile-search-tail-staging.yml
.github/workflows/security.yml
.github/workflows/seed-staging.yml
```

Backup/restore is **Implemented / Rehearsed** through the repository workflow. Staging migration, seed, benchmark, phase profiling, tail profiling, and Narrow Window PoC workflows are explicit operational tools rather than automatic production behavior.

## 3. Current follow-up work

### 3.1 Search rollout decision

**Proposed next step:** evaluate a production rollout PR for the Narrow CTE query shape based on the successful PR #133 feasibility result. The rollout must preserve exact pagination, ordering, filters, read-only behavior, backend fallback, and compatibility semantics.

A production rollout should not be considered accepted solely because of one staging benchmark; it requires CI, regression tests, and a post-rollout benchmark on the production code path.

### 3.2 Brand documentation

The VORNEQ Brand Constitution is approved conceptually but is not yet canonical repository documentation. Proposed path: `docs/brand/constitution.md`.

## 4. Target / Proposed architecture

Items in this section are not current production requirements unless explicitly promoted by a later ADR/PR.

### [Target] Cross-adapter query consolidation

If five database round trips remain a dominant latency floor after Narrow CTE rollout, investigate a PostgreSQL-first combined-query/`UNION ALL` feasibility study. Preserve historical `(published_at, key)` semantics and exact totals.

### [Target] pgvector / similarity infrastructure

Do not add pgvector by default. Add vector search only after a measured product requirement demonstrates that current PostgreSQL/search capabilities are insufficient. Any adoption requires an ADR covering data model, rebuildability, query semantics, cost, and operational impact.

### [Target] Zero-downtime deployment guarantee

Current deployment has pre-deploy migration checks and health checks, but a formal zero-downtime guarantee requires an explicit deployment strategy, compatibility rules for schema changes, rollback procedure, and validated release process.

### [Implemented / Opt-in] Object storage

Object-storage configuration exists and can be enabled by environment. It remains optional and should not become a hard dependency without an operational requirement.

### [Implemented / Rehearsed] Backup and recovery

Backup/restore rehearsal exists. Future work should continue validating recovery objectives and documenting restore expectations rather than replacing rehearsed recovery with untested scripts.

## 5. Architecture guardrails / non-goals

These guardrails are part of the engineering contract:

1. **Verification ≠ Truth.** Verification records method, evidence, provenance, and result; it does not claim ownership of truth.
2. **Trust context without a universal trust score.** Reputation is contextual by role, domain, method, and policy. Do not collapse it into an authoritative universal ranking.
3. **Search ≠ Verification.** Retrieval relevance or ordering is not evidence of validity.
4. **No identity inference from free text.** Author/name strings must not silently create or bind canonical `Identity` records.
5. **Marketplace is the discovery hub; backward compatibility is mandatory.** Preserve legacy routes/contracts until a deliberate migration removes them.
6. **PostgreSQL First.** Prefer the existing database and measured query improvements before introducing new infrastructure.
7. **No Elasticsearch, pgvector, cache tier, or other infrastructure without measured need.** New infrastructure requires evidence, an explicit operational benefit, and an ADR when architecture changes materially.
8. **Multi-theme UI uses design tokens.** New UI must not hard-code a single theme's visual assumptions.
9. **Performance changes must preserve semantics.** Optimizations must retain exact ordering, pagination, filtering, totals, read-only behavior, and compatibility fallback unless an explicit contract change is approved.

## 6. Maintenance rule

Update this document whenever a PR materially changes architecture, operational topology, compatibility contracts, or the status of a Target/Proposed item. Small implementation changes do not require edits unless they make a statement here inaccurate.

When code and this document disagree, **the code and accepted ADRs are authoritative until this document is corrected**.