from __future__ import annotations

import json
import statistics
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.core.paginator import Paginator
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils.translation import get_language

from apps.search.services import SearchResult, UnifiedSearch


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, int(round(fraction * len(ordered) + 0.5)) - 1),
    )
    return ordered[index]


def _phase_summary(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(_percentile(values, 0.95), 2),
        "avg_ms": round(statistics.fmean(values), 2),
    }


class Command(BaseCommand):
    help = (
        "Profile count, bounded candidate fetch, and merge phases of UnifiedSearch "
        "without changing production search behavior."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--query",
            action="append",
            dest="queries",
            help="Query to profile. Repeat the option to profile multiple queries.",
        )
        parser.add_argument("--repeat", type=int, default=5)
        parser.add_argument("--page", type=int, default=1)
        parser.add_argument("--page-size", type=int, default=UnifiedSearch.DEFAULT_PAGE_SIZE)
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit one JSON object per query.",
        )

    def handle(self, *args, **options):
        repeat = options["repeat"]
        page = options["page"]
        page_size = options["page_size"]
        queries = options.get("queries") or ["", "ai", "knowledge", "science"]

        if repeat < 1:
            raise CommandError("--repeat must be at least 1")
        if page < 1:
            raise CommandError("--page must be at least 1")
        if not 1 <= page_size <= UnifiedSearch.MAX_PAGE_SIZE:
            raise CommandError(
                f"--page-size must be between 1 and {UnifiedSearch.MAX_PAGE_SIZE}"
            )

        service = UnifiedSearch()
        language = get_language() or "en"

        if not options["as_json"]:
            self.stdout.write(
                "query\trepeats\tcount_p50_ms\tfetch_p50_ms\tmerge_p50_ms\t"
                "total_p50_ms\tavg_db_queries\ttotal_results"
            )

        for raw_query in queries:
            normalized_query = service.normalize_query(raw_query)
            timings = {
                "count": [],
                "fetch": [],
                "merge": [],
                "total": [],
            }
            query_counts: list[int] = []
            count_query_counts: list[int] = []
            fetch_query_counts: list[int] = []
            adapter_count_timings: dict[str, list[float]] = {
                adapter.type_name: [] for adapter in service.adapters
            }
            adapter_fetch_timings: dict[str, list[float]] = {
                adapter.type_name: [] for adapter in service.adapters
            }
            total_results = 0
            resolved_page = page

            for _ in range(repeat):
                iteration_started = perf_counter()
                querysets = []
                total = 0

                with CaptureQueriesContext(connection) as captured:
                    count_queries_before = len(captured)
                    count_started = perf_counter()
                    for adapter in service.adapters:
                        queryset = adapter.get_queryset(normalized_query, {})
                        adapter_started = perf_counter()
                        count = queryset.count()
                        adapter_count_timings[adapter.type_name].append(
                            (perf_counter() - adapter_started) * 1000
                        )
                        total += count
                        querysets.append((adapter, queryset, count))
                    timings["count"].append((perf_counter() - count_started) * 1000)
                    count_query_counts.append(len(captured) - count_queries_before)

                    paginator = Paginator(range(total), page_size)
                    page_obj = paginator.get_page(page)
                    resolved_page = page_obj.number
                    candidate_limit = resolved_page * page_size

                    fetch_queries_before = len(captured)
                    fetch_started = perf_counter()
                    candidates: list[SearchResult] = []
                    for adapter, queryset, count in querysets:
                        adapter_started = perf_counter()
                        if count:
                            candidates.extend(
                                adapter.serialize(instance, language=language)
                                for instance in adapter.top_candidates(
                                    queryset, candidate_limit
                                )
                            )
                        adapter_fetch_timings[adapter.type_name].append(
                            (perf_counter() - adapter_started) * 1000
                        )
                    timings["fetch"].append((perf_counter() - fetch_started) * 1000)
                    fetch_query_counts.append(len(captured) - fetch_queries_before)

                    merge_started = perf_counter()
                    candidates.sort(
                        key=lambda item: (item.published_at, item.key), reverse=True
                    )
                    start = (resolved_page - 1) * page_size
                    end = start + page_size
                    [item.as_dict() for item in candidates[start:end]]
                    timings["merge"].append((perf_counter() - merge_started) * 1000)

                timings["total"].append((perf_counter() - iteration_started) * 1000)
                query_counts.append(len(captured))
                total_results = total

            adapter_phases = {}
            for adapter in service.adapters:
                name = adapter.type_name
                adapter_phases[name] = {
                    "count": _phase_summary(adapter_count_timings[name]),
                    "fetch": _phase_summary(adapter_fetch_timings[name]),
                }

            result = {
                "query": raw_query,
                "normalized_query": normalized_query,
                "repeats": repeat,
                "page": resolved_page,
                "page_size": page_size,
                "total_results": total_results,
                "count": _phase_summary(timings["count"]),
                "fetch": _phase_summary(timings["fetch"]),
                "merge": _phase_summary(timings["merge"]),
                "total": _phase_summary(timings["total"]),
                "avg_db_queries": round(statistics.fmean(query_counts), 2),
                "avg_count_db_queries": round(
                    statistics.fmean(count_query_counts), 2
                ),
                "avg_fetch_db_queries": round(
                    statistics.fmean(fetch_query_counts), 2
                ),
                "adapters": adapter_phases,
            }

            if options["as_json"]:
                self.stdout.write(json.dumps(result, sort_keys=True))
            else:
                self.stdout.write(
                    "{query}\t{repeats}\t{count:.2f}\t{fetch:.2f}\t{merge:.2f}\t"
                    "{total:.2f}\t{queries:.2f}\t{results}".format(
                        query=raw_query,
                        repeats=repeat,
                        count=result["count"]["p50_ms"],
                        fetch=result["fetch"]["p50_ms"],
                        merge=result["merge"]["p50_ms"],
                        total=result["total"]["p50_ms"],
                        queries=result["avg_db_queries"],
                        results=total_results,
                    )
                )
