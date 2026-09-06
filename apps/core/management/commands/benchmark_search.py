from __future__ import annotations

import json
import statistics
from time import perf_counter

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.search.services import UnifiedSearch


class Command(BaseCommand):
    help = (
        "Measure UnifiedSearch latency and database query count without changing "
        "production search behavior."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--query",
            action="append",
            dest="queries",
            help="Query to benchmark. Repeat the option to benchmark multiple queries.",
        )
        parser.add_argument("--repeat", type=int, default=3)
        parser.add_argument("--page", type=int, default=1)
        parser.add_argument("--page-size", type=int, default=UnifiedSearch.DEFAULT_PAGE_SIZE)
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit one JSON object per query for machine-readable baselines.",
        )

    def handle(self, *args, **options):
        repeat = options["repeat"]
        page = options["page"]
        page_size = options["page_size"]
        queries = options.get("queries") or ["", "knowledge", "ai"]

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
                "query\trepeats\tp50_ms\tp95_ms\tavg_db_queries\ttotal_results"
            )

        for raw_query in queries:
            normalized_query = service.normalize_query(raw_query)
            durations_ms: list[float] = []
            query_counts: list[int] = []
            total_results = 0

            for _ in range(repeat):
                started = perf_counter()
                with CaptureQueriesContext(connection) as captured:
                    payload = service.search(
                        normalized_query,
                        page=page,
                        page_size=page_size,
                    )
                durations_ms.append((perf_counter() - started) * 1000)
                query_counts.append(len(captured))
                total_results = payload["total"]

            ordered = sorted(durations_ms)
            p50_ms = statistics.median(ordered)
            p95_index = max(0, min(len(ordered) - 1, int(round(0.95 * len(ordered) + 0.5)) - 1))
            p95_ms = ordered[p95_index]
            avg_db_queries = statistics.fmean(query_counts)

            result = {
                "query": raw_query,
                "normalized_query": normalized_query,
                "repeats": repeat,
                "page": page,
                "page_size": page_size,
                "p50_ms": round(p50_ms, 2),
                "p95_ms": round(p95_ms, 2),
                "avg_db_queries": round(avg_db_queries, 2),
                "total_results": total_results,
            }

            if options["as_json"]:
                self.stdout.write(json.dumps(result, sort_keys=True))
            else:
                self.stdout.write(
                    "{query}\t{repeats}\t{p50_ms:.2f}\t{p95_ms:.2f}\t"
                    "{avg_db_queries:.2f}\t{total_results}".format(**result)
                )
