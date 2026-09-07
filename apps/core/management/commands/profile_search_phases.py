from __future__ import annotations

import json
import statistics
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.search.services import UnifiedSearch


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
        "p99_ms": round(_percentile(values, 0.99), 2),
        "avg_ms": round(statistics.fmean(values), 2),
    }


class Command(BaseCommand):
    help = (
        "Profile the production UnifiedSearch.search() path. Use --interleaved to "
        "run queries round-robin and reduce time-order drift between scenarios."
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
            "--interleaved",
            action="store_true",
            help="Run one sample of each query per round instead of grouping by query.",
        )
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        repeat = options["repeat"]
        page = options["page"]
        page_size = options["page_size"]
        interleaved = options["interleaved"]
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
        measurements = [
            {
                "total_ms": [],
                "query_counts": [],
                "total_results": 0,
                "resolved_page": page,
            }
            for _ in queries
        ]

        def measure(query_index: int) -> None:
            raw_query = queries[query_index]
            started = perf_counter()
            with CaptureQueriesContext(connection) as captured:
                payload = service.search(
                    query=raw_query,
                    page=page,
                    page_size=page_size,
                )
            sample = measurements[query_index]
            sample["total_ms"].append((perf_counter() - started) * 1000)
            sample["query_counts"].append(len(captured))
            sample["total_results"] = payload["total"]
            sample["resolved_page"] = payload["page"]

        if interleaved:
            for _ in range(repeat):
                for query_index in range(len(queries)):
                    measure(query_index)
        else:
            for query_index in range(len(queries)):
                for _ in range(repeat):
                    measure(query_index)

        if not options["as_json"]:
            self.stdout.write(
                "query\trepeats\tinterleaved\ttotal_p50_ms\ttotal_p95_ms\t"
                "total_p99_ms\tavg_db_queries\ttotal_results"
            )

        for raw_query, sample in zip(queries, measurements):
            result = {
                "mode": "production",
                "query": raw_query,
                "normalized_query": service.normalize_query(raw_query),
                "repeats": repeat,
                "interleaved": interleaved,
                "page": sample["resolved_page"],
                "page_size": page_size,
                "total_results": sample["total_results"],
                "total": _summary(sample["total_ms"]),
                "avg_db_queries": round(statistics.fmean(sample["query_counts"]), 2),
            }

            if options["as_json"]:
                self.stdout.write(json.dumps(result, sort_keys=True))
            else:
                self.stdout.write(
                    "{query}\t{repeats}\t{interleaved}\t{p50:.2f}\t{p95:.2f}\t"
                    "{p99:.2f}\t{queries:.2f}\t{results}".format(
                        query=raw_query,
                        repeats=repeat,
                        interleaved=str(interleaved).lower(),
                        p50=result["total"]["p50_ms"],
                        p95=result["total"]["p95_ms"],
                        p99=result["total"]["p99_ms"],
                        queries=result["avg_db_queries"],
                        results=sample["total_results"],
                    )
                )
