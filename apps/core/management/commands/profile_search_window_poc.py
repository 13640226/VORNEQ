from __future__ import annotations

import json
import statistics
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.search.services import UnifiedSearch
from apps.search.window_count_poc import window_count_search_poc


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, int(round(fraction * len(ordered) + 0.5)) - 1),
    )
    return ordered[index]


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(_percentile(values, 0.95), 2),
        "avg_ms": round(statistics.fmean(values), 2),
    }


class Command(BaseCommand):
    help = (
        "Profile the opt-in COUNT(*) OVER() search feasibility path without "
        "changing UnifiedSearch.search()."
    )

    def add_arguments(self, parser):
        parser.add_argument("--query", action="append", dest="queries")
        parser.add_argument("--repeat", type=int, default=5)
        parser.add_argument("--page", type=int, default=1)
        parser.add_argument("--page-size", type=int, default=UnifiedSearch.DEFAULT_PAGE_SIZE)
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        repeat = options["repeat"]
        page = options["page"]
        page_size = options["page_size"]
        queries = options.get("queries") or ["", "ai", "knowledge", "science"]

        if repeat < 1:
            raise CommandError("--repeat must be at least 1")
        if page < 1:
            raise CommandError("--page must be at least 1 for the window PoC profiler")
        if not 1 <= page_size <= UnifiedSearch.MAX_PAGE_SIZE:
            raise CommandError(
                f"--page-size must be between 1 and {UnifiedSearch.MAX_PAGE_SIZE}"
            )

        service = UnifiedSearch()

        if not options["as_json"]:
            self.stdout.write(
                "query\trepeats\tquery_p50_ms\tmerge_p50_ms\ttotal_p50_ms\t"
                "avg_db_queries\ttotal_results"
            )

        for raw_query in queries:
            query_ms: list[float] = []
            merge_ms: list[float] = []
            total_ms: list[float] = []
            query_counts: list[int] = []
            adapter_timings: dict[str, list[float]] = {
                adapter.type_name: [] for adapter in service.adapters
            }
            total_results = 0
            resolved_page = page

            for _ in range(repeat):
                started = perf_counter()
                with CaptureQueriesContext(connection) as captured:
                    profile = window_count_search_poc(
                        service,
                        raw_query,
                        page=page,
                        page_size=page_size,
                    )
                total_ms.append((perf_counter() - started) * 1000)
                query_ms.append(profile.query_phase_ms)
                merge_ms.append(profile.merge_ms)
                query_counts.append(len(captured))
                total_results = profile.payload["total"]
                resolved_page = profile.payload["page"]
                for name, value in profile.adapter_ms.items():
                    adapter_timings[name].append(value)

            adapters = {
                name: _summary(values)
                for name, values in adapter_timings.items()
                if values
            }
            result = {
                "query": raw_query,
                "normalized_query": service.normalize_query(raw_query),
                "repeats": repeat,
                "page": resolved_page,
                "page_size": page_size,
                "total_results": total_results,
                "query_phase": _summary(query_ms),
                "merge": _summary(merge_ms),
                "total": _summary(total_ms),
                "avg_db_queries": round(statistics.fmean(query_counts), 2),
                "adapters": adapters,
            }

            if options["as_json"]:
                self.stdout.write(json.dumps(result, sort_keys=True))
            else:
                self.stdout.write(
                    "{query}\t{repeats}\t{query_ms:.2f}\t{merge_ms:.2f}\t"
                    "{total_ms:.2f}\t{queries:.2f}\t{results}".format(
                        query=raw_query,
                        repeats=repeat,
                        query_ms=result["query_phase"]["p50_ms"],
                        merge_ms=result["merge"]["p50_ms"],
                        total_ms=result["total"]["p50_ms"],
                        queries=result["avg_db_queries"],
                        results=total_results,
                    )
                )
