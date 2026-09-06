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
        "avg_ms": round(statistics.fmean(values), 2),
    }


class Command(BaseCommand):
    help = (
        "Profile the production UnifiedSearch.search() path. After the window-count "
        "rollout, count and candidate retrieval intentionally share each adapter query."
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
        parser.add_argument("--json", action="store_true", dest="as_json")

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

        if not options["as_json"]:
            self.stdout.write(
                "query\trepeats\ttotal_p50_ms\ttotal_p95_ms\tavg_db_queries\ttotal_results"
            )

        for raw_query in queries:
            total_ms: list[float] = []
            query_counts: list[int] = []
            total_results = 0
            resolved_page = page

            for _ in range(repeat):
                started = perf_counter()
                with CaptureQueriesContext(connection) as captured:
                    payload = service.search(
                        query=raw_query,
                        page=page,
                        page_size=page_size,
                    )
                total_ms.append((perf_counter() - started) * 1000)
                query_counts.append(len(captured))
                total_results = payload["total"]
                resolved_page = payload["page"]

            result = {
                "mode": "production",
                "query": raw_query,
                "normalized_query": service.normalize_query(raw_query),
                "repeats": repeat,
                "page": resolved_page,
                "page_size": page_size,
                "total_results": total_results,
                "total": _summary(total_ms),
                "avg_db_queries": round(statistics.fmean(query_counts), 2),
            }

            if options["as_json"]:
                self.stdout.write(json.dumps(result, sort_keys=True))
            else:
                self.stdout.write(
                    "{query}\t{repeats}\t{p50:.2f}\t{p95:.2f}\t{queries:.2f}\t{results}".format(
                        query=raw_query,
                        repeats=repeat,
                        p50=result["total"]["p50_ms"],
                        p95=result["total"]["p95_ms"],
                        queries=result["avg_db_queries"],
                        results=total_results,
                    )
                )
