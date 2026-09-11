# Documentation Freshness Findings

**Status:** Active registry  
**Baseline:** `e2f9b9d0e2c03c48f529ddc14e0a259b4ada1bf2`  
**Nature:** Record-only — findings are recorded here; this registry does not modify the source documents or configuration that gave rise to a finding.

## DF-1 — Migration execution location inconsistency

**Status:** `[documentation-freshness finding] — operational correctness unresolved`  
**Source:** B3-D3 rollback plan discovery (2026-09-11)  
**Baseline:** `e2f9b9d0e2c03c48f529ddc14e0a259b4ada1bf2`

### Observed sides

- **Side A — documentation:** `docs/disaster-recovery.md` states that migrations run in Render `preDeployCommand`.
- **Side B — repository configuration:** `render.yaml` has `preDeployCommand` running `python manage.py migration_preflight --fail-on-breaking --format json`; migration execution is delegated to a separate GitHub workflow rather than being declared as migration execution in that `preDeployCommand`.

### Nature of the inconsistency

The two baseline repository artifacts make different statements about where migration execution occurs in the Render deployment context. This record preserves that inconsistency as a documentation-freshness finding; it does not resolve which side reflects effective operational behavior.

### What is not claimed

- `docs/disaster-recovery.md` is **not** declared outdated by this record.
- `render.yaml` is **not** declared canonical operational truth by this record.
- Neither side is proven incorrect by this record.
- No provider, runtime, deployment, migration, database, OAuth, or implementation state is inferred from this record.

### Resolution

`[open — requires provider evidence or historical review]`

Possible future resolution evidence may establish whether the documentation reflects an earlier or current operational mechanism, whether repository configuration is incomplete relative to provider state, or whether a documentation correction is warranted. No such determination is made here.

### Non-authorization

This finding is evidence documentation only. It does not authorize or claim any implementation change, provider/runtime access, deployment, migration execution, configuration change, or correction of either source artifact.

## Provenance Discipline

- `[B3-D3 evidence]` — source assessment in which DF-1 was identified.
- `[repo evidence]` — baseline-locked repository inspection supporting the two observed sides.
- `[open]` — resolution remains evidence-gated; no operational correctness determination is encoded here.

## Future Findings

Future `DF-N` findings may be added through separately scoped and authorized changes. No additional finding is recorded by this version of the registry.
