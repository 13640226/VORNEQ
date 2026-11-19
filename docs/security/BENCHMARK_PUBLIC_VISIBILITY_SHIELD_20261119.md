# Benchmark public visibility shield — read-only code release (2026-11-19)

**Status:** Separate Draft PR; no merge, deployment, migration, data hide or delete.

## Scope and evidence

On 2026-11-19 a Production READ ONLY Django query returned:
- Article: seed content is expected to be 1,000 records (confirm complete Article output separately)
- Library: 500 strict seed items, 500 public, zero loose-but-not-strict
- Media: 200 strict seed assets, 200 active, zero loose-but-not-strict
- Library and Media showed no discovered direct dependent rows or ArtifactBindings

Historical source: 2026-09-06 `Seed Staging Search Data` run (reported
1,000 articles, 500 products, 500 Library items, 200 MediaAssets).
The actual historical DB target has **not** been cryptographically proven.

This PR is not a database cleanup. A future reversible database quarantine
and any subsequent deletion require **separate owner releases**, a fresh
database snapshot and restore rehearsal, frozen row ID hashes and full
dependency checks. Do not replay Marketplace product deletion #656.

## Changes

- `apps/core/benchmark_visibility.py` implements public-only QuerySet
  filters using specific observed seed signals; avoids generic keyword
  exclusion so genuine benchmark content stays discoverable. Articles
  require an explicit seed JSON marker, or the combination of both the
  benchmark slug namespace and dedicated seed category. Category alone
  or slug alone must not hide independently written articles.
- `apps/search/services.py` uses those filters at the adapter QuerySet
  source, covering search API, Discover, paginated narrow CTE and
  offline/grounded AI retrieval.
- `library/views.py` filters the index and rejects seed detail and PDF
  reader access before file I/O.
- `apps/core/services/context.py` rejects seed Library items during
  public Inspect/Artifact resolution.
- `apps/media/similarity.py` rejects seed MediaAssets during optional
  similarity indexing and candidate resolution. The production media
  similarity API remains on its existing independent HOLD.
- `apps/search/tests/test_benchmark_public_visibility.py` uses disposable
  test database records to verify each public boundary, non-fixture
  preservation, and database non-mutation.

**Important SQL detail:** Filtering a JSONField with a direct negated
predicate can produce SQL NULL effects that hide unrelated rows in SQLite.
The guard builds a subquery of matching IDs and excludes by PK instead.
The tests include a legitimate article and media row without seed JSON.

## Safety controls

- Does not change existing manager/global queryset behavior for administrative
  workflows, moderation, backup, provenance investigation or read-only audits.
- Does not block ordinary words `Benchmark` or `VORNEQ` or the normal
  Library category `benchmark` in genuinely independent content.
- MediaAssetAdapter remains unregistered from default public search.
- No migrations; no environment variable changes; no OpenAI/provider requests.
- No SQL writes against the Production source data.
- No automatic merge/deploy.

## Release dependencies

The open PRs #655 (Marketplace fixture visibility) and #657 (Marketplace UI V2)
are based on the old main. Reconcile this PR with them before any merge or
staging release. For any Production deploy, require new independent approval
and synchronise the authorized AI code SHA; do not silently change AI settings.
Validate unchanged real content and zero seed citations on Staging first.

A visible seed document in another unchecked public entrypoint is a
regression; inventory any added API views against this shared helper.
