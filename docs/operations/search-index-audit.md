# Search Index Audit

Status: Diagnostic / staging only

This audit captures evidence for search index modernization without changing search API semantics, ordering, filters, or database indexes.

## Scope

The audit covers the five production search adapters and the query set used by the search performance work:

- Article
- Product
- LibraryItem
- MediaAsset
- AudioItem
- query terms: empty, `ai`, `knowledge`, `science`
- page 1, page size 12

The command uses the same narrow CTE SQL builder as the production search path. It records PostgreSQL index definitions and usage counters, then runs `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` for each adapter/query pair.

## Safety

`audit_search_index` is PostgreSQL-only. Each EXPLAIN ANALYZE runs inside its own transaction with `SET TRANSACTION READ ONLY` and a bounded `statement_timeout` (30 seconds by default). The diagnostic performs no DDL and makes no index changes.

EXPLAIN ANALYZE executes the underlying SELECT and therefore creates real staging workload. Run it only through the manual staging workflow or an equivalently controlled staging environment.

The artifact stores SQL text and parameter metadata, but not parameter values. Query terms in the fixed diagnostic set are intentionally non-sensitive.

## Outputs

The canonical artifact is `audit-report.json`. `summary.md` is a human-readable view of the same run. The report includes index DDL from `pg_indexes`, usage counters from `pg_stat_user_indexes`, and the complete JSON execution plans.

An `idx_scan` value of zero is evidence for investigation, not sufficient evidence to drop an index. Statistics can be reset and an index may protect a rare or critical path.

## Manual workflow

Run **Audit Staging Search Index** from GitHub Actions on the branch being evaluated. The workflow verifies the staging database secret, checks migration status, runs the command, validates that all 20 adapter/query plans completed, and uploads the artifact.

## Decision gate

This phase is diagnostic only. Do not add or remove indexes from these results alone. Candidate index changes belong in a separate experiment with before/after staging evidence using the same query set and production-equivalent search path. Search ordering remains the historical `(published_at, key)` contract and must not be changed by an index experiment.
