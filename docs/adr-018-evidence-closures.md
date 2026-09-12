# ADR-018 Evidence Closure Records — B1 / B2

**Status:** Evidence closure record  
**Date:** 2026-09-11  
**Baseline:** `main@e2f9b9d0e2c03c48f529ddc14e0a259b4ada1bf2`  
**Related:** ADR-018 D3 / D4

This document records the session-canonical B1 and B2 evidence closures that support the ADR-018 D3 and D4 control assessments. It is evidence documentation only. It does not amend ADR-018, authorize implementation or deployment, establish provider/runtime state, or disclose secret values. [session governance]

## B1 — Database Mapping Evidence Closure

**Status:** **Closed — Unresolved / Provider UI Insufficient.** [session governance]

### Scope

B1 assessed the evidence chain required to answer:

```text
VORNEQ → DATABASE_URL → which concrete PostgreSQL resource?
```

The closure rests on two independent evidence paths: provider-side UI inspection and repository-level deep inspection. [B1 evidence] [repo evidence]

### Findings

- The application-side configuration path reaches PostgreSQL through the `DATABASE_URL` abstraction. [repo evidence]
- The provider-side inspection exposed a masked `DATABASE_URL` value without a usable resource reference or binding link. [B1 evidence]
- The inspected PostgreSQL resources did not provide usable `Used by` / `Connected services` association metadata sufficient to bind the application service to one concrete database resource. [B1 evidence]
- `render.yaml` contains the Render web-service Blueprint, but no `databases:` declaration, `fromDatabase`, `connectionString`, or other concrete database-resource binding. [repo evidence]
- Repository settings consume `DATABASE_URL` through `dj_database_url`; they do not name a provider PostgreSQL resource. [repo evidence]
- Environment-specific CI secret names establish deployment intent only; they do not identify the concrete provider database resource. [repo evidence]

### Verdict

**Unresolved — provider-blocked (confirmed with extended coverage).** [session governance] [open — evidence-gated]

The positive chain is established only to the abstraction boundary:

```text
VORNEQ / deployment configuration
  → DATABASE_URL
  → PostgreSQL
```

The final binding remains unproven:

```text
DATABASE_URL
  → concrete provider PostgreSQL resource
```

This closure does not mean that no mapping exists. It means the mapping was not proven by the authorized evidence paths. [session governance]

### Relationship to ADR-018

B1 is the execution-level evidence basis for the ADR-018 D4 database-topology assessment. The D4 closure is tracked separately; B1 does not replace or duplicate the D4 control-level record. [session governance]

The unresolved mapping also preserves the related C3/C4 uncertainty: concrete environment/resource membership remains unresolved and the internal/external database path is not determinable from repository evidence alone. [open — evidence-gated]

### Reopening Triggers

B1 may be reopened when direct binding evidence becomes available, including: [session governance]

1. provider UI association metadata sufficient to bind the application target to a database resource;
2. Blueprint/IaC evidence using `fromDatabase`, `connectionString`, or an equivalent explicit resource binding;
3. provider support evidence identifying the service-to-database binding;
4. read-only provider/database hostname or resource-identity evidence made available through an approved mechanism;
5. repository or CI metadata that names the concrete resource without exposing credentials;
6. a newly canonicalized configuration artifact that explicitly binds `DATABASE_URL` to a named resource; or
7. any other direct evidence that closes the abstraction-to-resource link.

## B2 — Secret Boundary Evidence Closure

**Status:** **Closed — Partial (single credential set observed; environment separation unresolved).** [session governance]

### Scope

B2 assessed secret-boundary evidence for the observed VORNEQ environment configuration, with the purpose of determining whether staging and production credential sets are concretely separated. Secret values are intentionally excluded from this record. [B2 evidence]

### Findings

- One complete observed credential/configuration set was available within the authorized evidence boundary. [B2 evidence]
- The observed configuration contained separately named credential/configuration families for database, Django/application, SMTP, object storage, diagnostic controls, environment classification, and storage diagnostics. [B2 evidence]
- Linked Environment Groups were not observed in the inspected provider evidence. [B2 evidence]
- No provider metadata proving shared-reference relationships between staging and production credential sets was available. [B2 evidence] [open — evidence-gated]
- Repository assessment established partial evidence for ADR-018 D3 R2: the targeted source tree, `.env.example`, and development configuration did not expose production secret values. Staging configuration and CI-log evidence remain open. [repo evidence] [open — evidence-gated]
- Concrete two-sided service/resource inventory remains incomplete, so the observed single credential set cannot prove environment-to-environment separation. [repo evidence] [open — evidence-gated]
- Environment-scoped rotation remains unproven because the required policy/provider evidence was not available. [open — evidence-gated]

### Verdict

**Partial — environment separation unresolved.** [session governance]

B2 neither proves nor disproves that production and staging use separate effective credential sets. The evidence is sufficient to record the observed credential families and the absence of a usable shared-reference signal in the authorized inspection, but not sufficient to establish a complete two-environment separation control. [session governance] [open — evidence-gated]

### Relationship to ADR-018

B2 is the execution-level evidence basis for the ADR-018 D3 secret-isolation assessment. D3 is separately recorded as **Closed as Assessment / Unresolved as Control**; B2 does not replace or duplicate that control-level closure. [session governance]

The remaining evidence gaps fall into three control families: [open — evidence-gated]

- **G1 — Credential-set separation:** complete concrete staging/production target inventory and enough provider membership evidence to compare their effective credential boundaries.
- **G2 — Production-secret absence:** remaining evidence for staging configuration and CI-log surfaces, without exposing secret values.
- **G3 — Environment-scoped rotation:** policy and/or provider metadata demonstrating that credential rotation is independently scoped by environment.

These gaps remain evidence requirements; governance labels are not substitutes for concrete resource-membership evidence. [session governance]

## Cross-References

- **B1 → ADR-018 D4:** database topology / concrete database-resource association. [session governance]
- **B2 → ADR-018 D3:** secret isolation / credential-set separation. [session governance]
- **B1/B2 ↔ C3/C4:** concrete resource membership and database-path evidence remain unresolved where direct provider evidence is absent. [open — evidence-gated]
- The observed mismatch between application classification `VORNEQ_ENV=staging` and the provider grouping labelled `Production` remains a drift signal. It does not, by itself, establish which provider grouping is operationally correct. [session governance] [open — evidence-gated]

## Provenance Discipline

Claims in this record use the following provenance labels:

- `[session governance]` — a governance decision, closure classification, or interpretation recorded in the session; it does not imply runtime implementation.
- `[B1 evidence]` — evidence gathered in the authorized B1 provider-side inspection.
- `[B2 evidence]` — evidence gathered in the authorized B2 provider-side inspection.
- `[repo evidence]` — a read-only repository finding; it establishes repository state only and does not prove provider/runtime state.
- `[open — evidence-gated]` — a conclusion or control that still requires additional evidence.

Secret values, partial secret values, credentials, connection strings, and other protected values are intentionally omitted. [session governance]

## Non-Duplication Statement

B1/B2 and the ADR-018 D3/D4 closures serve different layers and are complementary rather than duplicative: [session governance]

- **D3 closure:** control-level assessment of secret isolation.
- **D4 closure:** control-level assessment of database topology.
- **B2:** execution-level evidence on which the D3 assessment rests.
- **B1:** execution-level evidence on which the D4 assessment rests.

Recording B1/B2 here does not modify ADR-018, does not promote D3 or D4 to PASS/FAIL, does not establish provider resource membership, and does not authorize provider mutation, database access, deployment, runtime verification, migration execution, configuration changes, or implementation work. [session governance]
