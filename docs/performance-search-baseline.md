# Search Performance Baseline — VORNEQ

## Purpose

This document defines how VORNEQ measures Unified Search before introducing caching, PostgreSQL extensions, or new indexes.

The current Unified Search implementation preserves an exact API contract (`total`, `total_pages`, `has_next`, and `has_previous`) and performs retrieval-only ordering by recency. Performance work must preserve those semantics.

## Benchmark command

Run against a representative database, preferably staging data or a production-like copy:

```bash
python manage.py benchmark_search --query "" --query knowledge --query ai --repeat 5
```

For machine-readable output:

```bash
python manage.py benchmark_search --query knowledge --repeat 10 --json
```

The command reports:

- p50 wall-clock latency
- p95 wall-clock latency
- average Django database query count
- exact total result count returned by Unified Search

The benchmark is observational only. It does not enable caching, change query ordering, truncate candidates, or add indexes.

## Known query-path characteristic

`UnifiedSearch.collect()` currently evaluates every matching adapter queryset, serializes all matching rows, merges them in Python, sorts by recency, and paginates afterwards. This is a candidate scalability bottleneck because a small requested page does not bound the number of matching rows materialized.

## Decision sequence

Performance changes should be considered in this order:

1. Measure representative query latency and query counts.
2. Confirm whether full candidate materialization is a meaningful bottleneck at realistic dataset sizes.
3. If confirmed, design bounded candidate retrieval that preserves exact totals and global recency ordering.
4. Evaluate narrowly scoped caching only for read patterns with clear freshness and invalidation semantics.
5. Consider `pg_trgm`, GIN, or other PostgreSQL indexes only after query plans and measured latency show that database text matching remains the bottleneck.

## Non-goals for this baseline

This baseline intentionally does **not**:

- add `pg_trgm` or GIN indexes
- add Elasticsearch or another search service
- cache search responses
- add signal-based cache invalidation
- change ranking or introduce trust-aware ordering
- replace exact pagination totals with estimates

## Evidence required for an optimization PR

A follow-up optimization PR should include before/after measurements from the same dataset and query set. It should document:

- dataset size by searchable model
- p50 and p95 latency
- query count
- relevant PostgreSQL query plans when proposing an index
- whether exact API pagination semantics remain unchanged
- cache freshness and invalidation rules if caching is introduced
